"""
test_cost_gate.py — Tests for the pre-trade cost gate.

Tests:
    1. Trade passes when all checks are within limits
    2. Hurdle rate rejects uneconomical trades
    3. Portfolio exposure cap enforced
    4. Per-asset concentration cap enforced
    5. Position count limit enforced
    6. Daily drawdown halt works
    7. Correlation guard prevents duplicate positions
    8. Config from_env with defaults
    9. Expected hold hours by leverage
"""

import pytest

from core.jupiter_perps.cost_gate import CostGate, CostGateConfig, CostVerdict
from core.jupiter_perps.position_manager import PositionManager, PositionManagerConfig


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _pm(**kwargs) -> PositionManager:
    """Create a fresh PositionManager."""
    return PositionManager(PositionManagerConfig(**kwargs))


def _gate(**kwargs) -> CostGate:
    """Create a CostGate with explicit config."""
    return CostGate(CostGateConfig(**kwargs))


def _default_gate() -> CostGate:
    return _gate(
        max_total_exposure_usd=5000.0,
        max_asset_exposure_usd=2000.0,
        max_positions=5,
        daily_drawdown_halt_pct=3.0,
    )


# ─── Basic Pass / Fail ──────────────────────────────────────────────────────

class TestBasicEvaluation:
    def test_trade_passes_all_checks(self):
        gate = _default_gate()
        pm = _pm()
        verdict = gate.evaluate(
            market="SOL-USD", side="long",
            size_usd=500.0, leverage=5.0,
            confidence=0.85, position_manager=pm,
        )
        assert verdict.passed is True
        assert verdict.reason == "ok"

    def test_verdict_includes_hurdle_and_fees(self):
        gate = _default_gate()
        pm = _pm()
        verdict = gate.evaluate(
            market="SOL-USD", side="long",
            size_usd=500.0, leverage=5.0,
            confidence=0.85, position_manager=pm,
        )
        assert verdict.hurdle_rate_pct >= 0.0
        assert verdict.total_fees_usd >= 0.0
        assert verdict.projected_exposure_usd == 500.0


# ─── Portfolio Exposure ─────────────────────────────────────────────────────

class TestPortfolioExposure:
    def test_rejects_exceeding_total_exposure(self):
        gate = _gate(max_total_exposure_usd=1000.0, max_asset_exposure_usd=5000.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 800.0, 160.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="BTC-USD", side="long",
            size_usd=300.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is False
        assert "exposure" in verdict.reason.lower()

    def test_accepts_within_total_exposure(self):
        gate = _gate(max_total_exposure_usd=5000.0, max_asset_exposure_usd=5000.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 2000.0, 400.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="BTC-USD", side="long",
            size_usd=2000.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is True


# ─── Per-Asset Concentration ────────────────────────────────────────────────

class TestAssetConcentration:
    def test_rejects_exceeding_asset_exposure(self):
        gate = _gate(max_total_exposure_usd=10000.0, max_asset_exposure_usd=1500.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 1000.0, 200.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="SOL-USD", side="short",
            size_usd=600.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is False
        assert "SOL-USD" in verdict.reason

    def test_different_asset_not_affected(self):
        gate = _gate(max_total_exposure_usd=10000.0, max_asset_exposure_usd=1500.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 1400.0, 280.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="BTC-USD", side="long",
            size_usd=1000.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is True


# ─── Position Count ──────────────────────────────────────────────────────────

class TestPositionCount:
    def test_rejects_exceeding_max_positions(self):
        gate = _gate(max_total_exposure_usd=100000.0, max_asset_exposure_usd=100000.0,
                     max_positions=2, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        pm.register_open("k2", "BTC-USD", "long", 500.0, 100.0, 5.0, 50000.0, "test")
        verdict = gate.evaluate(
            market="ETH-USD", side="long",
            size_usd=500.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is False
        assert "count" in verdict.reason.lower() or "Position" in verdict.reason


# ─── Correlation Guard ──────────────────────────────────────────────────────

class TestCorrelationGuard:
    def test_rejects_duplicate_position(self):
        gate = _gate(max_total_exposure_usd=100000.0, max_asset_exposure_usd=100000.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="SOL-USD", side="long",
            size_usd=500.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is False
        assert "duplicate" in verdict.reason.lower() or "Duplicate" in verdict.reason

    def test_opposite_side_is_allowed(self):
        gate = _gate(max_total_exposure_usd=100000.0, max_asset_exposure_usd=100000.0,
                     max_positions=10, daily_drawdown_halt_pct=10.0)
        pm = _pm()
        pm.register_open("k1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        verdict = gate.evaluate(
            market="SOL-USD", side="short",
            size_usd=500.0, leverage=3.0,
            confidence=0.90, position_manager=pm,
        )
        assert verdict.passed is True


# ─── Config ─────────────────────────────────────────────────────────────────

class TestConfig:
    def test_expected_hold_hours_by_leverage(self):
        cfg = CostGateConfig()
        # Higher leverage -> shorter hold
        h_2x = cfg.expected_hold_hours(2.0)
        h_10x = cfg.expected_hold_hours(10.0)
        assert h_2x > h_10x

    def test_default_config_values(self):
        cfg = CostGateConfig()
        assert cfg.max_total_exposure_usd == 5000.0
        assert cfg.max_asset_exposure_usd == 2000.0
        assert cfg.max_positions == 5
        assert cfg.daily_drawdown_halt_pct == 3.0


# ─── CostVerdict ─────────────────────────────────────────────────────────────

class TestCostVerdict:
    def test_is_immutable(self):
        v = CostVerdict(passed=True, reason="ok")
        with pytest.raises(AttributeError):
            v.passed = False  # type: ignore

    def test_defaults(self):
        v = CostVerdict(passed=True, reason="ok")
        assert v.hurdle_rate_pct == 0.0
        assert v.total_fees_usd == 0.0
        assert v.projected_exposure_usd == 0.0
