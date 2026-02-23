"""
test_position_manager.py — Tests for position tracking and exit triggers.

Tests:
    1. Position registration and retrieval
    2. Price updates and peak tracking
    3. Stop loss trigger
    4. Take profit trigger
    5. Trailing stop trigger (activation + drawdown)
    6. Time decay trigger
    7. Funding bleed trigger
    8. Emergency stop trigger
    9. Signal reversal trigger
    10. Trigger priority (highest severity wins)
    11. Entry price fill on first tick
    12. Pending exit prevents re-triggering
    13. Daily P&L tracking
"""

import time
from unittest.mock import patch

import pytest

from core.jupiter_perps.position_manager import (
    ExitDecision,
    PositionManager,
    PositionManagerConfig,
    TrackedPosition,
    _check_emergency_stop,
    _check_funding_bleed,
    _check_stop_loss,
    _check_take_profit,
    _check_time_decay,
    _check_trailing_stop,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _cfg(**overrides) -> PositionManagerConfig:
    defaults = dict(
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        trailing_stop_pct=8.0,
        trailing_activate_pct=3.0,
        max_hold_hours=48.0,
        max_borrow_pct=2.0,
        emergency_stop_pct=15.0,
    )
    defaults.update(overrides)
    return PositionManagerConfig(**defaults)


def _pos(
    side="long",
    entry_price=100.0,
    current_price=100.0,
    peak_price=None,
    leverage=5.0,
    size_usd=500.0,
    collateral_usd=100.0,
    opened_at=None,
    cumulative_borrow_usd=0.0,
    market="SOL-USD",
) -> TrackedPosition:
    now = time.time()
    return TrackedPosition(
        pda="test-pda",
        idempotency_key="test-key",
        market=market,
        side=side,
        size_usd=size_usd,
        collateral_usd=collateral_usd,
        leverage=leverage,
        entry_price=entry_price,
        opened_at=opened_at or now,
        peak_price=peak_price if peak_price is not None else entry_price,
        current_price=current_price,
        source="test",
        cumulative_borrow_usd=cumulative_borrow_usd,
    )


# ─── TrackedPosition Properties ─────────────────────────────────────────────

class TestTrackedPositionProperties:
    def test_long_positive_pnl(self):
        pos = _pos(side="long", entry_price=100.0, current_price=102.0, leverage=5.0)
        # raw = (102 - 100) / 100 = 0.02, * 5 * 100 = 10%
        assert abs(pos.unrealized_pnl_pct - 10.0) < 0.01

    def test_long_negative_pnl(self):
        pos = _pos(side="long", entry_price=100.0, current_price=99.0, leverage=5.0)
        # raw = (99 - 100) / 100 = -0.01, * 5 * 100 = -5%
        assert abs(pos.unrealized_pnl_pct - (-5.0)) < 0.01

    def test_short_positive_pnl(self):
        pos = _pos(side="short", entry_price=100.0, current_price=98.0, leverage=5.0)
        # raw = (100 - 98) / 100 = 0.02, * 5 * 100 = 10%
        assert abs(pos.unrealized_pnl_pct - 10.0) < 0.01

    def test_short_negative_pnl(self):
        pos = _pos(side="short", entry_price=100.0, current_price=101.0, leverage=5.0)
        # raw = (100 - 101) / 100 = -0.01, * 5 * 100 = -5%
        assert abs(pos.unrealized_pnl_pct - (-5.0)) < 0.01

    def test_pnl_usd(self):
        pos = _pos(side="long", entry_price=100.0, current_price=102.0,
                   leverage=5.0, collateral_usd=100.0)
        # pnl_pct = 10%, usd = 100 * 0.10 = 10
        assert abs(pos.unrealized_pnl_usd - 10.0) < 0.01

    def test_zero_entry_price_returns_zero_pnl(self):
        pos = _pos(entry_price=0.0, current_price=100.0)
        assert pos.unrealized_pnl_pct == 0.0

    def test_peak_pnl_pct_long(self):
        pos = _pos(side="long", entry_price=100.0, peak_price=105.0,
                   current_price=103.0, leverage=5.0)
        # peak P&L: (105 - 100) / 100 * 5 * 100 = 25%
        assert abs(pos.peak_pnl_pct - 25.0) < 0.01

    def test_drawdown_from_peak(self):
        pos = _pos(side="long", entry_price=100.0, peak_price=105.0,
                   current_price=103.0, leverage=5.0)
        # peak = 25%, current = 15%, drawdown = 10%
        assert abs(pos.drawdown_from_peak_pct - 10.0) < 0.01

    def test_drawdown_is_never_negative(self):
        pos = _pos(side="long", entry_price=100.0, peak_price=100.0,
                   current_price=105.0, leverage=5.0)
        assert pos.drawdown_from_peak_pct >= 0.0


# ─── Stop Loss Trigger ──────────────────────────────────────────────────────

class TestStopLoss:
    def test_fires_at_threshold(self):
        # 5% stop loss -> need -1% raw move at 5x leverage
        pos = _pos(side="long", entry_price=100.0, current_price=99.0, leverage=5.0)
        result = _check_stop_loss(pos, _cfg())
        assert result is not None
        assert result.trigger == "stop_loss"
        assert result.urgency == "urgent"

    def test_does_not_fire_above_threshold(self):
        pos = _pos(side="long", entry_price=100.0, current_price=99.5, leverage=5.0)
        # pnl = -2.5%, threshold = -5%
        result = _check_stop_loss(pos, _cfg())
        assert result is None

    def test_fires_for_short_position(self):
        pos = _pos(side="short", entry_price=100.0, current_price=101.0, leverage=5.0)
        result = _check_stop_loss(pos, _cfg())
        assert result is not None


# ─── Take Profit Trigger ────────────────────────────────────────────────────

class TestTakeProfit:
    def test_fires_at_threshold(self):
        # 10% take profit -> need +2% raw move at 5x leverage
        pos = _pos(side="long", entry_price=100.0, current_price=102.0, leverage=5.0)
        result = _check_take_profit(pos, _cfg())
        assert result is not None
        assert result.trigger == "take_profit"
        assert result.urgency == "normal"

    def test_does_not_fire_below_threshold(self):
        pos = _pos(side="long", entry_price=100.0, current_price=101.5, leverage=5.0)
        # pnl = 7.5%, threshold = 10%
        result = _check_take_profit(pos, _cfg())
        assert result is None

    def test_fires_for_short_in_profit(self):
        pos = _pos(side="short", entry_price=100.0, current_price=98.0, leverage=5.0)
        result = _check_take_profit(pos, _cfg())
        assert result is not None


# ─── Trailing Stop Trigger ──────────────────────────────────────────────────

class TestTrailingStop:
    def test_inactive_before_activation_threshold(self):
        # Peak P&L must be >= 3% for trailing stop to activate
        pos = _pos(side="long", entry_price=100.0, peak_price=100.5,
                   current_price=99.0, leverage=5.0)
        # peak P&L = 2.5% < 3% activation threshold
        result = _check_trailing_stop(pos, _cfg())
        assert result is None

    def test_fires_after_sufficient_drawdown(self):
        # Peak P&L 10%, now dropped 8%+ from peak
        pos = _pos(side="long", entry_price=100.0, peak_price=102.0,
                   current_price=100.39, leverage=5.0)
        # peak P&L = 10%, current P&L = 2%, drawdown = 8% -> fires
        result = _check_trailing_stop(pos, _cfg())
        assert result is not None
        assert result.trigger == "trailing_stop"

    def test_does_not_fire_with_small_drawdown(self):
        pos = _pos(side="long", entry_price=100.0, peak_price=102.0,
                   current_price=101.5, leverage=5.0)
        # peak = 10%, current = 7.5%, drawdown = 2.5% < 8%
        result = _check_trailing_stop(pos, _cfg())
        assert result is None


# ─── Time Decay Trigger ────────────────────────────────────────────────────

class TestTimeDecay:
    def test_fires_after_max_hold(self):
        old_time = time.time() - (49 * 3600)  # 49 hours ago
        pos = _pos(opened_at=old_time)
        result = _check_time_decay(pos, _cfg())
        assert result is not None
        assert result.trigger == "time_decay"

    def test_does_not_fire_within_limit(self):
        recent_time = time.time() - (10 * 3600)  # 10 hours ago
        pos = _pos(opened_at=recent_time)
        result = _check_time_decay(pos, _cfg())
        assert result is None


# ─── Funding Bleed Trigger ──────────────────────────────────────────────────

class TestFundingBleed:
    def test_fires_at_threshold(self):
        # 2% of $500 notional = $10
        pos = _pos(size_usd=500.0, cumulative_borrow_usd=10.0)
        result = _check_funding_bleed(pos, _cfg())
        assert result is not None
        assert result.trigger == "funding_bleed"

    def test_does_not_fire_below_threshold(self):
        pos = _pos(size_usd=500.0, cumulative_borrow_usd=5.0)
        result = _check_funding_bleed(pos, _cfg())
        assert result is None


# ─── Emergency Stop Trigger ────────────────────────────────────────────────

class TestEmergencyStop:
    def test_fires_at_threshold(self):
        # -15% emergency -> -3% raw at 5x
        pos = _pos(side="long", entry_price=100.0, current_price=97.0, leverage=5.0)
        # pnl = -15%
        result = _check_emergency_stop(pos, _cfg())
        assert result is not None
        assert result.trigger == "emergency_stop"
        assert result.urgency == "urgent"

    def test_does_not_fire_above_threshold(self):
        # -10% is below emergency threshold of -15%
        pos = _pos(side="long", entry_price=100.0, current_price=98.0, leverage=5.0)
        result = _check_emergency_stop(pos, _cfg())
        assert result is None


# ─── Position Manager ───────────────────────────────────────────────────────

class TestPositionManager:
    def test_register_and_count(self):
        pm = PositionManager(_cfg())
        pm.register_open(
            idempotency_key="key1", market="SOL-USD", side="long",
            size_usd=500.0, collateral_usd=100.0, leverage=5.0,
            entry_price=100.0, source="test",
        )
        assert pm.get_position_count() == 1
        assert pm.get_total_exposure_usd() == 500.0

    def test_register_multiple(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        pm.register_open("key2", "BTC-USD", "short", 1000.0, 200.0, 5.0, 50000.0, "test")
        assert pm.get_position_count() == 2
        assert pm.get_total_exposure_usd() == 1500.0

    def test_update_price_long_peak_tracking(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        pm.update_price("SOL-USD", 105.0)
        pos = pm.get_open_positions()[0]
        assert pos.peak_price == 105.0
        assert pos.current_price == 105.0

    def test_update_price_short_peak_tracking(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "short", 500.0, 100.0, 5.0, 100.0, "test")
        pm.update_price("SOL-USD", 95.0)
        pos = pm.get_open_positions()[0]
        assert pos.peak_price == 95.0  # For shorts, lower is better

    def test_update_price_triggers_stop_loss(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.update_price("SOL-USD", 99.0)  # -5% P&L at 5x
        assert len(exits) == 1
        assert exits[0].trigger == "stop_loss"

    def test_entry_price_fill_on_first_tick(self):
        """Positions registered with entry_price=0.0 get filled on first tick."""
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 0.0, "test")
        # First tick fills entry price, no exit triggers
        exits = pm.update_price("SOL-USD", 150.0)
        assert len(exits) == 0
        pos = pm.get_open_positions()[0]
        assert pos.entry_price == 150.0
        assert pos.peak_price == 150.0

    def test_mark_closed_removes_position(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        closed = pm.mark_closed("key1")
        assert closed is not None
        assert pm.get_position_count() == 0

    def test_mark_closed_returns_none_for_missing(self):
        pm = PositionManager(_cfg())
        assert pm.mark_closed("nonexistent") is None

    def test_pending_exit_prevents_retrigger(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits1 = pm.update_price("SOL-USD", 99.0)  # triggers stop loss
        assert len(exits1) == 1
        exits2 = pm.update_price("SOL-USD", 98.0)  # should NOT re-trigger
        assert len(exits2) == 0

    def test_cancel_pending_exit_allows_retrigger(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        pm.update_price("SOL-USD", 99.0)  # triggers stop loss, adds to pending
        pm.cancel_pending_exit("key1")
        exits = pm.update_price("SOL-USD", 98.5)  # should trigger again
        assert len(exits) == 1

    def test_has_position(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        assert pm.has_position("SOL-USD", "long") is True
        assert pm.has_position("SOL-USD", "short") is False
        assert pm.has_position("BTC-USD", "long") is False

    def test_asset_exposure(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        pm.register_open("key2", "SOL-USD", "short", 300.0, 60.0, 5.0, 100.0, "test")
        assert pm.get_asset_exposure_usd("SOL-USD") == 800.0
        assert pm.get_asset_exposure_usd("BTC-USD") == 0.0

    def test_emergency_fires_before_stop_loss(self):
        """Emergency stop (-15%) should fire instead of stop loss (-5%)."""
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.update_price("SOL-USD", 97.0)  # -15% at 5x
        assert len(exits) == 1
        assert exits[0].trigger == "emergency_stop"  # Not stop_loss


# ─── Signal Reversal ────────────────────────────────────────────────────────

class TestSignalReversal:
    def test_reversal_closes_opposite_position(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.check_signal_reversal("SOL", "short", 0.60)
        assert len(exits) == 1
        assert exits[0].trigger == "signal_reversal"

    def test_same_direction_signal_does_not_close(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.check_signal_reversal("SOL", "long", 0.90)
        assert len(exits) == 0

    def test_low_confidence_reversal_does_not_close(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.check_signal_reversal("SOL", "short", 0.40)
        assert len(exits) == 0

    def test_different_asset_not_affected(self):
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        exits = pm.check_signal_reversal("BTC", "short", 0.90)
        assert len(exits) == 0


# ─── On-chain TP/SL Trigger Price Computation ────────────────────────────────

class TestTPSLTriggerPrices:
    # Fee adjustment: 8 bps (0.08%) of entry price pushed outward on TP
    # For entry=150: fee_delta = 150 * 8/10000 = 0.12
    # For entry=60000: fee_delta = 60000 * 8/10000 = 48.0

    def test_long_trigger_prices(self):
        """Long position: SL below entry, TP above entry (fee-adjusted)."""
        pm = PositionManager(_cfg(stop_loss_pct=5.0, take_profit_pct=10.0))
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 150.0, "test")
        triggers = pm.compute_tpsl_trigger_prices("key1")
        assert len(triggers) == 2

        sl = next(t for t in triggers if t["kind"] == "stop_loss")
        tp = next(t for t in triggers if t["kind"] == "take_profit")

        # SL: entry - (stop_loss_pct * entry / (leverage * 100))
        # = 150 - (5 * 150 / 500) = 150 - 1.5 = 148.5 (NO fee adjustment on SL)
        assert sl["trigger_price"] == pytest.approx(148.5, abs=0.01)
        assert sl["trigger_above_threshold"] is False  # trigger when price drops

        # TP: entry + tp_delta + fee_delta
        # tp_delta = 10 * 150 / 500 = 3.0
        # fee_delta = 150 * 8/10000 = 0.12
        # = 150 + 3.0 + 0.12 = 153.12
        assert tp["trigger_price"] == pytest.approx(153.12, abs=0.01)
        assert tp["trigger_above_threshold"] is True  # trigger when price rises

    def test_short_trigger_prices(self):
        """Short position: SL above entry, TP below entry (fee-adjusted)."""
        pm = PositionManager(_cfg(stop_loss_pct=5.0, take_profit_pct=10.0))
        pm.register_open("key1", "BTC-USD", "short", 5000.0, 1000.0, 5.0, 60000.0, "test")
        triggers = pm.compute_tpsl_trigger_prices("key1")
        assert len(triggers) == 2

        sl = next(t for t in triggers if t["kind"] == "stop_loss")
        tp = next(t for t in triggers if t["kind"] == "take_profit")

        # Short SL: entry + delta = 60000 + 600 = 60600 (NO fee adjustment)
        assert sl["trigger_price"] == pytest.approx(60600.0, abs=1.0)
        assert sl["trigger_above_threshold"] is True  # trigger when price rises (bad for short)

        # Short TP: entry - tp_delta - fee_delta
        # tp_delta = 10 * 60000 / 500 = 1200
        # fee_delta = 60000 * 8/10000 = 48
        # = 60000 - 1200 - 48 = 58752
        assert tp["trigger_price"] == pytest.approx(58752.0, abs=1.0)
        assert tp["trigger_above_threshold"] is False  # trigger when price drops (good for short)

    def test_no_triggers_without_entry_price(self):
        """Positions with entry_price=0.0 should not produce trigger prices."""
        pm = PositionManager(_cfg())
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 0.0, "test")
        triggers = pm.compute_tpsl_trigger_prices("key1")
        assert len(triggers) == 0

    def test_no_triggers_for_missing_position(self):
        pm = PositionManager(_cfg())
        triggers = pm.compute_tpsl_trigger_prices("nonexistent")
        assert len(triggers) == 0

    def test_high_leverage_narrow_triggers(self):
        """Higher leverage = trigger prices closer to entry (fee still applies to TP)."""
        pm = PositionManager(_cfg(stop_loss_pct=5.0, take_profit_pct=10.0))
        pm.register_open("key1", "SOL-USD", "long", 5000.0, 100.0, 50.0, 150.0, "test")
        triggers = pm.compute_tpsl_trigger_prices("key1")

        sl = next(t for t in triggers if t["kind"] == "stop_loss")
        tp = next(t for t in triggers if t["kind"] == "take_profit")

        # SL delta = 5.0 * 150 / (50 * 100) = 0.15
        assert sl["trigger_price"] == pytest.approx(149.85, abs=0.01)
        # TP delta = 10.0 * 150 / (50 * 100) = 0.30
        # fee_delta = 150 * 8/10000 = 0.12
        # TP = 150 + 0.30 + 0.12 = 150.42
        assert tp["trigger_price"] == pytest.approx(150.42, abs=0.01)

    def test_tp_fee_adjustment_ensures_real_profit(self):
        """TP trigger must be pushed outward enough to cover close fees."""
        pm = PositionManager(_cfg(stop_loss_pct=5.0, take_profit_pct=10.0))
        pm.register_open("key1", "SOL-USD", "long", 500.0, 100.0, 5.0, 100.0, "test")
        triggers = pm.compute_tpsl_trigger_prices("key1")

        tp = next(t for t in triggers if t["kind"] == "take_profit")
        # fee_delta = 100 * 8/10000 = 0.08
        # tp_delta = 10 * 100 / 500 = 2.0
        # TP = 100 + 2.0 + 0.08 = 102.08 (not 102.00)
        assert tp["trigger_price"] > 102.0  # strictly above the raw target
