"""Tests for core.analytics.strategy_metrics — Metrics display and thresholds."""

import pytest

from core.analytics.strategy_metrics import (
    MetricTier,
    classify_metric,
    estimate_live_sharpe,
    format_strategy_status,
    get_annualization_note,
    get_metric_color,
    LIVE_DISCOUNT_FACTOR,
)


class TestClassifyMetric:

    def test_sharpe_poor(self):
        assert classify_metric("sharpe", 0.3) == MetricTier.POOR

    def test_sharpe_acceptable(self):
        assert classify_metric("sharpe", 0.7) == MetricTier.ACCEPTABLE

    def test_sharpe_good(self):
        assert classify_metric("sharpe", 1.5) == MetricTier.GOOD

    def test_sharpe_excellent(self):
        assert classify_metric("sharpe", 2.5) == MetricTier.EXCELLENT

    def test_drawdown_poor(self):
        assert classify_metric("max_drawdown", 0.50) == MetricTier.POOR

    def test_drawdown_excellent(self):
        assert classify_metric("max_drawdown", 0.05) == MetricTier.EXCELLENT

    def test_wilson_tiers(self):
        assert classify_metric("wilson_lb", 0.45) == MetricTier.POOR
        assert classify_metric("wilson_lb", 0.54) == MetricTier.ACCEPTABLE
        assert classify_metric("wilson_lb", 0.59) == MetricTier.GOOD
        assert classify_metric("wilson_lb", 0.65) == MetricTier.EXCELLENT

    def test_profit_factor(self):
        assert classify_metric("profit_factor", 0.8) == MetricTier.POOR
        assert classify_metric("profit_factor", 2.5) == MetricTier.EXCELLENT

    def test_unknown_metric(self):
        assert classify_metric("unknown_metric", 999) == MetricTier.ACCEPTABLE


class TestEstimateLiveSharpe:

    def test_discount(self):
        assert estimate_live_sharpe(2.0) == 2.0 * LIVE_DISCOUNT_FACTOR

    def test_zero(self):
        assert estimate_live_sharpe(0.0) == 0.0


class TestGetMetricColor:

    def test_returns_hex_color(self):
        color = get_metric_color("sharpe", 2.5)
        assert color.startswith("#")


class TestGetAnnualizationNote:

    def test_crypto(self):
        note = get_annualization_note("native_solana")
        assert "365" in note

    def test_xstock(self):
        note = get_annualization_note("xstock")
        assert "252" in note


class TestFormatStrategyStatus:

    def test_pump_fresh_tight(self):
        """Test the PUMP FRESH TIGHT strategy display."""
        status = format_strategy_status(
            name="PUMP FRESH TIGHT",
            total_trades=246,
            wins=140,
            gross_profit=5000,
            gross_loss=4400,
            sharpe=1.14,
        )
        assert status.name == "PUMP FRESH TIGHT"
        assert status.total_trades == 246
        assert status.wilson_lb > 0  # Should have a value now
        assert status.live_sharpe_estimate is not None

        d = status.to_display_dict()
        assert d["confidence_score"] > 0
        assert d["progress_pct"] == 100  # 246 > 30
        assert "sharpe" in d
        assert "live_sharpe_estimate" in d

    def test_unverified_strategy(self):
        """Strategy with only 15 trades — should show progress bar."""
        status = format_strategy_status(
            name="NEW_STRAT",
            total_trades=15,
            wins=10,
            gross_profit=500,
            gross_loss=300,
        )
        assert not status.deployable
        d = status.to_display_dict()
        assert d["progress_pct"] == 50  # 15/30 = 50%

    def test_strong_strategy(self):
        status = format_strategy_status(
            name="STRONG",
            total_trades=500,
            wins=320,
            gross_profit=20000,
            gross_loss=8000,
            sharpe=2.1,
            max_drawdown=0.08,
        )
        assert status.deployable
        d = status.to_display_dict()
        assert d["sharpe_tier"] == "excellent"
        assert d["drawdown_tier"] == "excellent"
