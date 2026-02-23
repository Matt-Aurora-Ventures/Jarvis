"""
test_self_adjuster.py — Tests for the self-adjusting trade outcome tracker.

Tests:
    1. Recording outcomes increments counts
    2. Tuning skips when below min trades
    3. Tuning updates weights after enough trades
    4. Weight normalization (sum to 1.0)
    5. Half-Kelly position sizing
    6. Confidence calibration
    7. Extract base source from consensus strings
    8. Auto-tune triggers after N trades
    9. Default weights match expected sources
    10. Summary returns correct structure
"""

import time

import pytest

from core.jupiter_perps.self_adjuster import (
    PerpsAutoTuner,
    TradeOutcome,
    TuneResult,
    TunerConfig,
    _DEFAULT_WEIGHTS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _cfg(**overrides) -> TunerConfig:
    defaults = dict(
        min_trades=5,         # lower for tests
        learning_rate=0.10,
        min_weight=0.10,
        tune_interval_hours=24.0,
        tune_after_trades=5,  # lower for tests
        sqlite_path="",
    )
    defaults.update(overrides)
    return TunerConfig(**defaults)


def _winning_trade(source: str = "grok_perps", pnl_pct: float = 5.0) -> TradeOutcome:
    return TradeOutcome(
        source=source,
        asset="SOL",
        direction="long",
        confidence_at_entry=0.80,
        entry_price=100.0,
        exit_price=105.0,
        pnl_usd=50.0,
        pnl_pct=pnl_pct,
        hold_hours=4.0,
        fees_usd=2.0,
        exit_trigger="take_profit",
        regime="bull",
    )


def _losing_trade(source: str = "grok_perps", pnl_pct: float = -3.0) -> TradeOutcome:
    return TradeOutcome(
        source=source,
        asset="SOL",
        direction="long",
        confidence_at_entry=0.80,
        entry_price=100.0,
        exit_price=97.0,
        pnl_usd=-30.0,
        pnl_pct=pnl_pct,
        hold_hours=2.0,
        fees_usd=1.5,
        exit_trigger="stop_loss",
        regime="ranging",
    )


# ─── TradeOutcome ───────────────────────────────────────────────────────────

class TestTradeOutcome:
    def test_is_win_when_positive_pnl(self):
        assert _winning_trade().is_win is True

    def test_is_loss_when_negative_pnl(self):
        assert _losing_trade().is_win is False

    def test_timestamp_is_set(self):
        outcome = _winning_trade()
        assert outcome.timestamp > 0


# ─── Recording Outcomes ─────────────────────────────────────────────────────

class TestRecordOutcome:
    def test_increments_count(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=100))  # high min to avoid auto-tune
        tuner.record_outcome(_winning_trade())
        assert len(tuner._outcomes) == 1

    def test_increments_trades_since_tune(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=100))
        tuner.record_outcome(_winning_trade())
        tuner.record_outcome(_losing_trade())
        assert tuner._trades_since_tune == 2


# ─── Tuning ─────────────────────────────────────────────────────────────────

class TestTune:
    def test_skips_when_below_min_trades(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=10))
        for _ in range(5):
            tuner._outcomes.append(_winning_trade())
        result = tuner.tune()
        assert result.weights_updated is False

    def test_updates_weights_with_enough_trades(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=5))
        for _ in range(3):
            tuner._outcomes.append(_winning_trade("grok_perps"))
        for _ in range(3):
            tuner._outcomes.append(_winning_trade("momentum"))
        result = tuner.tune()
        assert result.weights_updated is True
        assert result.total_trades == 6

    def test_weights_sum_to_one(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(3):
            tuner._outcomes.append(_winning_trade("grok_perps"))
        for _ in range(3):
            tuner._outcomes.append(_losing_trade("momentum"))
        tuner.tune()
        total = sum(tuner._source_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_winning_source_gets_higher_weight(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        # grok_perps: all wins
        for _ in range(5):
            tuner._outcomes.append(_winning_trade("grok_perps", pnl_pct=8.0))
        # momentum: all losses
        for _ in range(5):
            tuner._outcomes.append(_losing_trade("momentum", pnl_pct=-4.0))
        tuner.tune()
        assert tuner._source_weights["grok_perps"] > tuner._source_weights.get("momentum", 0)

    def test_resets_trades_since_tune(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(5):
            tuner._outcomes.append(_winning_trade())
        tuner._trades_since_tune = 10
        tuner.tune()
        assert tuner._trades_since_tune == 0

    def test_tune_result_has_source_stats(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(5):
            tuner._outcomes.append(_winning_trade("grok_perps"))
        result = tuner.tune()
        assert "grok_perps" in result.source_stats
        stats = result.source_stats["grok_perps"]
        assert stats["win_rate"] == 1.0
        assert stats["trades"] == 5

    def test_tune_result_has_regime_stats(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(5):
            tuner._outcomes.append(_winning_trade())
        result = tuner.tune()
        assert "bull" in result.regime_stats


# ─── Position Sizing ────────────────────────────────────────────────────────

class TestPositionSizing:
    def test_default_multiplier_is_one(self):
        tuner = PerpsAutoTuner(_cfg())
        assert tuner.get_position_size_multiplier("grok_perps") == 1.0

    def test_multiplier_after_tuning(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(5):
            tuner._outcomes.append(_winning_trade("grok_perps", pnl_pct=5.0))
        for _ in range(5):
            tuner._outcomes.append(_losing_trade("grok_perps", pnl_pct=-3.0))
        tuner.tune()
        mult = tuner.get_position_size_multiplier("grok_perps")
        assert 0.25 <= mult <= 1.5

    def test_multiplier_clamped_to_range(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        # All wins with big payoff should give high but capped multiplier
        for _ in range(10):
            tuner._outcomes.append(_winning_trade("grok_perps", pnl_pct=20.0))
        tuner.tune()
        mult = tuner.get_position_size_multiplier("grok_perps")
        assert mult <= 1.5


# ─── Confidence Calibration ─────────────────────────────────────────────────

class TestConfidenceCalibration:
    def test_default_calibration_is_neutral(self):
        tuner = PerpsAutoTuner(_cfg())
        assert tuner.get_calibrated_confidence("grok_perps", 0.80) == 0.80

    def test_calibration_after_tuning(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(10):
            tuner._outcomes.append(_winning_trade("grok_perps"))
        tuner.tune()
        cal = tuner.get_calibrated_confidence("grok_perps", 0.80)
        # Win rate is 100% vs 80% claimed confidence -> calibration > 1.0
        assert cal >= 0.80

    def test_calibration_clamped_to_zero_one(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3))
        for _ in range(10):
            tuner._outcomes.append(_winning_trade("grok_perps"))
        tuner.tune()
        # Very high raw confidence should be clamped at 1.0
        cal = tuner.get_calibrated_confidence("grok_perps", 0.99)
        assert cal <= 1.0


# ─── Extract Base Source ────────────────────────────────────────────────────

class TestExtractBaseSource:
    def test_simple_source(self):
        assert PerpsAutoTuner._extract_base_source("grok_perps") == "grok_perps"

    def test_consensus_source(self):
        result = PerpsAutoTuner._extract_base_source("consensus(grok_perps,momentum)")
        assert result == "grok_perps"

    def test_consensus_with_spaces(self):
        result = PerpsAutoTuner._extract_base_source("consensus( grok_perps , momentum )")
        assert result.strip() == "grok_perps"


# ─── Auto-Tune Trigger ─────────────────────────────────────────────────────

class TestAutoTuneTrigger:
    def test_auto_tunes_after_n_trades(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=3, tune_after_trades=3))
        # Record 3 trades (should trigger auto-tune on the 3rd)
        for _ in range(3):
            tuner.record_outcome(_winning_trade())
        # After auto-tune, trades_since_tune should be reset
        assert tuner._trades_since_tune == 0


# ─── Summary ────────────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_structure(self):
        tuner = PerpsAutoTuner(_cfg())
        summary = tuner.get_summary()
        assert "total_outcomes" in summary
        assert "source_weights" in summary
        assert "size_multipliers" in summary
        assert "confidence_calibration" in summary
        assert "trades_since_tune" in summary
        assert "last_tune_age_hours" in summary

    def test_summary_reflects_state(self):
        tuner = PerpsAutoTuner(_cfg(min_trades=100))  # high min to avoid auto-tune
        tuner.record_outcome(_winning_trade())
        summary = tuner.get_summary()
        assert summary["total_outcomes"] == 1
        assert summary["trades_since_tune"] == 1


# ─── Default Weights ────────────────────────────────────────────────────────

class TestDefaultWeights:
    def test_default_weights_match_sources(self):
        assert "grok_perps" in _DEFAULT_WEIGHTS
        assert "momentum" in _DEFAULT_WEIGHTS
        assert "aggregate" in _DEFAULT_WEIGHTS

    def test_default_weights_sum_to_one(self):
        total = sum(_DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_tuner_starts_with_defaults(self):
        tuner = PerpsAutoTuner(_cfg())
        weights = tuner.get_weights()
        assert weights == dict(_DEFAULT_WEIGHTS)
