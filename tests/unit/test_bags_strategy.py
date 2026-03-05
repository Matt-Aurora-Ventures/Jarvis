"""Tests for core.trading.bags_strategy — Bonding curve logic."""

import pytest
from datetime import datetime, timezone, timedelta

from core.trading.bags_strategy import (
    BagsCurveAnalyzer,
    BagsPhase,
    BagsSignal,
    BagsStrategyConfig,
    GraduationEvent,
    PostGraduationHandler,
    DISABLED_INDICATORS_PRE_GRAD,
    should_use_indicator,
)


class TestCurveSaturation:

    def test_zero_sol(self):
        analyzer = BagsCurveAnalyzer()
        assert analyzer.calculate_curve_saturation(0.0) == 0.0

    def test_half_filled(self):
        analyzer = BagsCurveAnalyzer()
        sat = analyzer.calculate_curve_saturation(42.5, graduation_threshold_sol=85.0)
        assert abs(sat - 0.5) < 0.01

    def test_at_threshold(self):
        analyzer = BagsCurveAnalyzer()
        assert abs(analyzer.calculate_curve_saturation(85.0) - 1.0) < 0.01

    def test_above_threshold(self):
        analyzer = BagsCurveAnalyzer()
        assert analyzer.calculate_curve_saturation(90.0) > 1.0

    def test_zero_threshold_returns_zero(self):
        analyzer = BagsCurveAnalyzer()
        assert analyzer.calculate_curve_saturation(50.0, graduation_threshold_sol=0) == 0.0


class TestInflowVelocity:

    def test_increasing_inflow(self):
        analyzer = BagsCurveAnalyzer()
        volumes = [100, 200, 300, 400, 500]
        velocity = analyzer.calculate_inflow_velocity(volumes)
        assert velocity > 0

    def test_decreasing_inflow(self):
        analyzer = BagsCurveAnalyzer()
        volumes = [500, 400, 300, 200, 100]
        velocity = analyzer.calculate_inflow_velocity(volumes)
        assert velocity < 0

    def test_flat_inflow(self):
        analyzer = BagsCurveAnalyzer()
        volumes = [100, 100, 100, 100, 100]
        velocity = analyzer.calculate_inflow_velocity(volumes)
        assert abs(velocity) < 0.01

    def test_single_sample_returns_zero(self):
        analyzer = BagsCurveAnalyzer()
        assert analyzer.calculate_inflow_velocity([100]) == 0.0

    def test_empty_returns_zero(self):
        analyzer = BagsCurveAnalyzer()
        assert analyzer.calculate_inflow_velocity([]) == 0.0


class TestGetSignal:

    def test_entry_when_conditions_met(self):
        """Entry requires: saturation > 85%, velocity positive, 3+ consecutive increases."""
        analyzer = BagsCurveAnalyzer()
        # Warm up with increasing velocities
        for v in [0.1, 0.2, 0.3, 0.4]:
            analyzer.get_signal(0.9, v, has_position=False)

        signal = analyzer.get_signal(0.90, 0.5, has_position=False)
        assert signal == BagsSignal.ENTRY

    def test_no_entry_below_saturation(self):
        analyzer = BagsCurveAnalyzer()
        for v in [0.1, 0.2, 0.3, 0.4]:
            analyzer.get_signal(0.5, v, has_position=False)
        signal = analyzer.get_signal(0.50, 0.5, has_position=False)
        assert signal == BagsSignal.NO_TRADE

    def test_no_entry_negative_velocity(self):
        analyzer = BagsCurveAnalyzer()
        signal = analyzer.get_signal(0.90, -0.5, has_position=False)
        assert signal == BagsSignal.NO_TRADE

    def test_graduation_event_closes_position(self):
        analyzer = BagsCurveAnalyzer()
        signal = analyzer.get_signal(0.95, 0.5, is_graduating=True, has_position=True)
        assert signal == BagsSignal.CLOSE_GRADUATION

    def test_graduation_event_no_position(self):
        analyzer = BagsCurveAnalyzer()
        signal = analyzer.get_signal(0.95, 0.5, is_graduating=True, has_position=False)
        assert signal == BagsSignal.NO_TRADE

    def test_exit_on_velocity_drop(self):
        analyzer = BagsCurveAnalyzer()
        # Build up velocity
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            analyzer.update_velocity(v)

        # Velocity drops 60% from peak (5.0 → 2.0)
        signal = analyzer.get_signal(0.90, 2.0, has_position=True)
        assert signal == BagsSignal.EXIT

    def test_hold_when_velocity_stable(self):
        analyzer = BagsCurveAnalyzer()
        for v in [1.0, 1.1, 1.2]:
            analyzer.update_velocity(v)
        signal = analyzer.get_signal(0.90, 1.1, has_position=True)
        assert signal == BagsSignal.HOLD

    def test_reset_clears_state(self):
        analyzer = BagsCurveAnalyzer()
        for v in [1.0, 2.0, 3.0]:
            analyzer.update_velocity(v)
        analyzer.reset()
        assert analyzer._peak_velocity == 0.0
        assert analyzer._consecutive_increases == 0


class TestPostGraduationHandler:

    def test_record_and_retrieve(self):
        handler = PostGraduationHandler()
        event = handler.record_graduation("MINT123", "POOL456")
        assert event.mint_address == "MINT123"
        assert handler.get_event("MINT123") is event

    def test_not_stable_immediately(self):
        handler = PostGraduationHandler()
        handler.record_graduation("MINT123")
        assert not handler.can_trade_post_graduation("MINT123")

    def test_stable_after_conditions_met(self):
        config = BagsStrategyConfig(
            post_grad_stabilize_minutes=0,  # No wait for test
            post_grad_min_liquidity_usd=1000,
        )
        handler = PostGraduationHandler(config)
        handler.record_graduation("MINT123")
        handler.update_liquidity("MINT123", 2000)
        assert handler.can_trade_post_graduation("MINT123")

    def test_not_stable_with_low_liquidity(self):
        config = BagsStrategyConfig(
            post_grad_stabilize_minutes=0,
            post_grad_min_liquidity_usd=100_000,
        )
        handler = PostGraduationHandler(config)
        handler.record_graduation("MINT123")
        handler.update_liquidity("MINT123", 5_000)
        assert not handler.can_trade_post_graduation("MINT123")

    def test_unknown_mint(self):
        handler = PostGraduationHandler()
        assert not handler.can_trade_post_graduation("NONEXISTENT")


class TestGraduationEvent:

    def test_minutes_since_graduation(self):
        event = GraduationEvent(
            mint_address="MINT",
            graduation_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert abs(event.minutes_since_graduation() - 5.0) < 0.5


class TestIndicatorGating:

    def test_rsi_disabled_pre_grad(self):
        assert not should_use_indicator("RSI", BagsPhase.PRE_GRADUATION)

    def test_macd_disabled_pre_grad(self):
        assert not should_use_indicator("MACD", BagsPhase.PRE_GRADUATION)

    def test_bollinger_disabled_pre_grad(self):
        assert not should_use_indicator("BOLLINGER_BANDS", BagsPhase.PRE_GRADUATION)

    def test_all_disabled_during_graduating(self):
        for ind in DISABLED_INDICATORS_PRE_GRAD:
            assert not should_use_indicator(ind, BagsPhase.GRADUATING)

    def test_re_enabled_post_grad(self):
        assert should_use_indicator("RSI", BagsPhase.POST_GRADUATION)
        assert should_use_indicator("MACD", BagsPhase.POST_GRADUATION)

    def test_volume_always_allowed(self):
        assert should_use_indicator("VOLUME", BagsPhase.PRE_GRADUATION)
        assert should_use_indicator("VOLUME", BagsPhase.POST_GRADUATION)
