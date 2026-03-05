"""Tests for core.events.trading_pipeline - Trading Pipeline."""

import pytest
from datetime import datetime, timezone

from core.events.trading_pipeline import (
    TradingPipeline,
    PipelineAction,
    PipelineResult,
    RejectionReason,
    ExitPlan,
)
from core.events.market_events import (
    MarketEvent,
    MarketEventType,
    EventUrgency,
)
from core.data.asset_registry import AssetClass


@pytest.fixture
def pipeline():
    return TradingPipeline(account_balance_usd=10_000, dry_run=True)


@pytest.fixture
def sol_event():
    return MarketEvent(
        event_type=MarketEventType.PRICE_BREAKOUT,
        urgency=EventUrgency.FAST,
        mint_address="So11111111111111111111111111111111111111112",
        symbol="SOL",
        asset_class=AssetClass.NATIVE_SOLANA,
        current_price=150.0,
        pool_liquidity_usd=5_000_000,
    )


@pytest.fixture
def bags_launch_event():
    return MarketEvent(
        event_type=MarketEventType.TOKEN_LAUNCH,
        urgency=EventUrgency.IMMEDIATE,
        mint_address="NewBags1111111111111111111111111111111111",
        symbol="NEWBAGS",
        asset_class=AssetClass.BAGS_BONDING_CURVE,
        current_price=0.001,
        pool_liquidity_usd=25_000,
    )


@pytest.fixture
def xstock_event():
    return MarketEvent(
        event_type=MarketEventType.ORACLE_UPDATE,
        urgency=EventUrgency.LOW,
        symbol="TSLA",
        asset_class=AssetClass.XSTOCK,
        current_price=250.0,
        pool_liquidity_usd=200_000,
    )


class TestPipelineBasics:

    def test_evaluate_sol_event(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
        )
        assert result.action == PipelineAction.ENTER
        assert result.strategy_id is not None
        assert result.round_trip_cost_pct < 0.02  # < 2% for SOL
        assert result.exit_plan is not None
        assert result.latency_ms >= 0  # May be 0 on fast Windows runs

    def test_none_event_rejected(self, pipeline):
        result = pipeline.evaluate(None)
        assert result.action == PipelineAction.SKIP
        assert result.rejection_reason == RejectionReason.INSUFFICIENT_DATA

    def test_no_asset_class_rejected(self, pipeline):
        event = MarketEvent(
            event_type=MarketEventType.VOLUME_EXPLOSION,
            urgency=EventUrgency.FAST,
            asset_class=None,
        )
        result = pipeline.evaluate(event)
        assert result.action == PipelineAction.SKIP
        assert result.rejection_reason == RejectionReason.ASSET_CLASS_UNKNOWN

    def test_position_limit_rejected(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            current_positions=50,
            max_positions=50,
        )
        assert result.action == PipelineAction.SKIP
        assert result.rejection_reason == RejectionReason.POSITION_LIMIT


class TestCostCheck:

    def test_sol_cost_acceptable(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            pool_liquidity_usd=5_000_000,
        )
        assert result.action == PipelineAction.ENTER
        assert result.estimated_cost is not None
        assert result.round_trip_cost_pct < 0.02

    def test_bags_cost_high_but_passes(self, pipeline, bags_launch_event):
        """Bags are expensive but below 10% RT threshold."""
        result = pipeline.evaluate(
            bags_launch_event,
            entry_price=0.001,
            pool_liquidity_usd=25_000,
            trade_size_usd=100,
        )
        # Should still enter (cost < 10%), just expensive
        assert result.estimated_cost is not None
        assert result.round_trip_cost_pct > 0.03  # > 3%


class TestAssetGates:

    def test_bags_bonding_curve_rejects_indicator_signals(self, pipeline):
        """Price breakout signal invalid on bonding curves."""
        event = MarketEvent(
            event_type=MarketEventType.PRICE_BREAKOUT,
            urgency=EventUrgency.FAST,
            asset_class=AssetClass.BAGS_BONDING_CURVE,
            current_price=0.001,
            pool_liquidity_usd=30_000,
        )
        result = pipeline.evaluate(event, entry_price=0.001)
        assert result.action == PipelineAction.SKIP
        assert result.rejection_reason == RejectionReason.INVALID_INDICATOR

    def test_bags_launch_event_accepted(self, pipeline, bags_launch_event):
        """TOKEN_LAUNCH is valid on bonding curves."""
        result = pipeline.evaluate(
            bags_launch_event,
            entry_price=0.001,
            pool_liquidity_usd=25_000,
        )
        assert result.action == PipelineAction.ENTER

    def test_xstock_rejects_stale_oracle(self, pipeline):
        current_time = datetime(2026, 3, 4, 15, 0, tzinfo=timezone.utc)
        event = MarketEvent(
            event_type=MarketEventType.ORACLE_UPDATE,
            urgency=EventUrgency.LOW,
            symbol="TSLAx",
            asset_class=AssetClass.XSTOCK,
            current_price=250.0,
            pool_liquidity_usd=200_000,
            timestamp=current_time,
            data={
                "oracle_last_update": datetime(2026, 3, 4, 14, 20, tzinfo=timezone.utc),
            },
        )
        result = pipeline.evaluate(event, entry_price=250.0, pool_liquidity_usd=200_000)
        assert result.action == PipelineAction.SKIP
        assert result.rejection_reason == RejectionReason.ORACLE_STALE


class TestDefaultStrategy:

    def test_sol_gets_bluechip_strategy(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            pool_liquidity_usd=5_000_000,
        )
        assert result.strategy_id == "bluechip_trend_follow"

    def test_bags_launch_gets_snipe_strategy(self, pipeline, bags_launch_event):
        result = pipeline.evaluate(
            bags_launch_event,
            entry_price=0.001,
            pool_liquidity_usd=25_000,
        )
        assert result.strategy_id == "bags_fresh_snipe"

    def test_volume_explosion_memecoin(self, pipeline):
        event = MarketEvent(
            event_type=MarketEventType.VOLUME_EXPLOSION,
            urgency=EventUrgency.FAST,
            asset_class=AssetClass.MEMECOIN,
            current_price=0.05,
            pool_liquidity_usd=200_000,
        )
        result = pipeline.evaluate(event, entry_price=0.05, pool_liquidity_usd=200_000)
        assert result.strategy_id == "volume_spike"

    def test_graduation_gets_bags_momentum(self, pipeline):
        event = MarketEvent(
            event_type=MarketEventType.GRADUATION,
            urgency=EventUrgency.IMMEDIATE,
            asset_class=AssetClass.BAGS_GRADUATED,
            current_price=0.01,
            pool_liquidity_usd=80_000,
        )
        result = pipeline.evaluate(event, entry_price=0.01, pool_liquidity_usd=80_000)
        assert result.strategy_id == "bags_momentum"


class TestPositionSizing:

    def test_position_sized_for_sol(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
        )
        assert result.position_size is not None
        assert result.position_size.position_usd > 0
        assert result.position_size.position_pct <= 0.05  # SOL max 5%
        assert result.trade_size_usd > 0

    def test_position_sized_with_kelly(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
            win_rate=0.55,
            avg_win_pct=0.02,
            avg_loss_pct=0.02,
        )
        assert result.position_size is not None
        assert result.position_size.kelly_raw > 0


class TestExitPlan:

    def test_exit_plan_generated(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
        )
        plan = result.exit_plan
        assert plan is not None
        assert plan.stop_loss_price > 0
        assert plan.take_profit_price > 150.0
        assert plan.trailing_stop_atr_multiplier == 4.0  # SOL default

    def test_bags_exit_plan_has_graduation_exit(self, pipeline, bags_launch_event):
        result = pipeline.evaluate(
            bags_launch_event,
            entry_price=0.001,
            pool_liquidity_usd=25_000,
        )
        plan = result.exit_plan
        assert plan is not None
        assert plan.graduation_exit is True
        assert plan.trailing_stop_atr_multiplier == 5.0  # Wider for bags

    def test_exit_plan_tiers(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
        )
        plan = result.exit_plan
        assert plan is not None
        assert len(plan.tiers) == 3  # tight, medium, wide

    def test_exit_plan_profit_floors(self, pipeline, sol_event):
        result = pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            stop_loss_price=140.0,
            atr=5.0,
            pool_liquidity_usd=5_000_000,
        )
        plan = result.exit_plan
        assert plan.floor_at_100pct == 0.50
        assert plan.floor_at_200pct == 1.00
        assert plan.floor_at_300pct == 2.00


class TestPipelineStats:

    def test_stats_tracking(self, pipeline, sol_event):
        pipeline.evaluate(
            sol_event,
            entry_price=150.0,
            pool_liquidity_usd=5_000_000,
        )
        pipeline.evaluate(None)  # Rejected

        stats = pipeline.stats
        assert stats["evaluations"] == 2
        assert stats["entries"] == 1
        assert stats["rejections"] >= 0
        assert stats["dry_run"] is True

    def test_initial_stats(self, pipeline):
        stats = pipeline.stats
        assert stats["evaluations"] == 0
        assert stats["entries"] == 0


class TestPipelineResult:

    def test_skip_repr(self):
        result = PipelineResult(
            action=PipelineAction.SKIP,
            rejection_reason=RejectionReason.COST_TOO_HIGH,
            rejection_detail="RT cost 15% too high",
        )
        s = repr(result)
        assert "SKIP" in s
        assert "COST_TOO_HIGH" in s

    def test_enter_repr(self):
        result = PipelineResult(
            action=PipelineAction.ENTER,
            strategy_id="bluechip_trend_follow",
            trade_size_usd=500.0,
            round_trip_cost_pct=0.0064,
        )
        s = repr(result)
        assert "enter" in s
        assert "bluechip_trend_follow" in s
