"""Tests for core.events.market_events - Market Event Engine."""

import pytest
from datetime import datetime, timezone

from core.events.market_events import (
    MarketEvent,
    MarketEventType,
    EventUrgency,
    EVENT_URGENCY,
    VolumeTracker,
    precheck_cost,
)
from core.data.asset_registry import AssetClass


class TestMarketEvent:

    def test_create_basic_event(self):
        event = MarketEvent(
            event_type=MarketEventType.TOKEN_LAUNCH,
            urgency=EventUrgency.IMMEDIATE,
            mint_address="So11111111111111111111111111111111111111112",
            symbol="TEST",
            asset_class=AssetClass.BAGS_BONDING_CURVE,
        )
        assert event.event_type == MarketEventType.TOKEN_LAUNCH
        assert event.urgency == EventUrgency.IMMEDIATE
        assert event.is_tradeable is False  # Not yet cost-checked
        assert not event.processed

    def test_mark_processed(self):
        import time
        event = MarketEvent(
            event_type=MarketEventType.GRADUATION,
            urgency=EventUrgency.IMMEDIATE,
        )
        start = time.time()
        time.sleep(0.01)
        event.mark_processed(start)
        assert event.processed
        assert event.processing_latency_ms >= 5  # At least 5ms

    def test_repr(self):
        event = MarketEvent(
            event_type=MarketEventType.VOLUME_EXPLOSION,
            urgency=EventUrgency.FAST,
            symbol="BONK",
        )
        s = repr(event)
        assert "BONK" in s
        assert "volume_explosion" in s

    def test_repr_with_mint_only(self):
        event = MarketEvent(
            event_type=MarketEventType.TOKEN_LAUNCH,
            urgency=EventUrgency.IMMEDIATE,
            mint_address="ABCDEFGH12345678",
        )
        s = repr(event)
        assert "ABCDEFGH" in s


class TestEventUrgency:

    def test_launch_is_immediate(self):
        assert EVENT_URGENCY[MarketEventType.TOKEN_LAUNCH] == EventUrgency.IMMEDIATE

    def test_graduation_is_immediate(self):
        assert EVENT_URGENCY[MarketEventType.GRADUATION] == EventUrgency.IMMEDIATE

    def test_volume_explosion_is_fast(self):
        assert EVENT_URGENCY[MarketEventType.VOLUME_EXPLOSION] == EventUrgency.FAST

    def test_oracle_update_is_low(self):
        assert EVENT_URGENCY[MarketEventType.ORACLE_UPDATE] == EventUrgency.LOW

    def test_all_events_have_urgency(self):
        for evt in MarketEventType:
            assert evt in EVENT_URGENCY, f"{evt} missing urgency mapping"


class TestVolumeTracker:

    def test_no_explosion_with_normal_volume(self):
        tracker = VolumeTracker(explosion_multiplier=5.0, window_size=5)
        # Feed 6 bars of normal volume
        for _ in range(6):
            result = tracker.update("TOKEN_A", 1000.0)
        assert result is None

    def test_explosion_detected(self):
        tracker = VolumeTracker(explosion_multiplier=3.0, window_size=5)
        # Feed 5 bars of normal volume
        for _ in range(5):
            tracker.update("TOKEN_A", 1000.0)
        # Bar 6: 5x volume spike
        result = tracker.update("TOKEN_A", 5000.0)
        assert result is not None
        assert result.event_type == MarketEventType.VOLUME_EXPLOSION
        assert result.volume_ratio >= 3.0
        assert result.data["ratio"] >= 3.0

    def test_no_explosion_below_threshold(self):
        tracker = VolumeTracker(explosion_multiplier=5.0, window_size=5)
        for _ in range(5):
            tracker.update("TOKEN_A", 1000.0)
        # 3x is below 5x threshold
        result = tracker.update("TOKEN_A", 3000.0)
        assert result is None

    def test_needs_full_window(self):
        tracker = VolumeTracker(window_size=10)
        # Only 5 bars, window needs 10+1
        for _ in range(5):
            result = tracker.update("TOKEN_A", 1000.0)
        assert result is None

    def test_separate_tracking_per_token(self):
        tracker = VolumeTracker(explosion_multiplier=3.0, window_size=3)
        # Fill TOKEN_A history
        for _ in range(3):
            tracker.update("TOKEN_A", 1000.0)
        # TOKEN_B has no history yet
        result = tracker.update("TOKEN_B", 10000.0)
        assert result is None  # Not enough data for TOKEN_B

    def test_reset(self):
        tracker = VolumeTracker(window_size=3)
        for _ in range(4):
            tracker.update("TOKEN_A", 1000.0)
        assert tracker.tracked_count >= 1
        tracker.reset("TOKEN_A")
        # After reset, needs to rebuild history
        result = tracker.update("TOKEN_A", 5000.0)
        assert result is None  # Not enough data after reset

    def test_zero_avg_volume(self):
        tracker = VolumeTracker(window_size=3)
        for _ in range(3):
            tracker.update("TOKEN_A", 0.0)
        result = tracker.update("TOKEN_A", 1000.0)
        assert result is None  # avg=0, can't compute ratio


class TestPrecheckCost:

    def test_sol_is_tradeable(self):
        event = MarketEvent(
            event_type=MarketEventType.PRICE_BREAKOUT,
            urgency=EventUrgency.FAST,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=5_000_000,
        )
        result = precheck_cost(event, trade_size_usd=500)
        assert result.is_tradeable
        assert result.estimated_cost is not None
        assert result.estimated_cost.total_round_trip_pct < 0.02  # < 2%

    def test_bags_pre_grad_high_cost(self):
        event = MarketEvent(
            event_type=MarketEventType.TOKEN_LAUNCH,
            urgency=EventUrgency.IMMEDIATE,
            asset_class=AssetClass.BAGS_BONDING_CURVE,
            pool_liquidity_usd=30_000,
        )
        result = precheck_cost(event, trade_size_usd=100)
        # Bags pre-grad is expensive but below 10% threshold
        assert result.estimated_cost is not None
        assert result.estimated_cost.total_round_trip_pct > 0.03  # > 3%

    def test_edge_check_viable(self):
        event = MarketEvent(
            event_type=MarketEventType.PRICE_BREAKOUT,
            urgency=EventUrgency.FAST,
            asset_class=AssetClass.NATIVE_SOLANA,
            pool_liquidity_usd=5_000_000,
        )
        # 5% edge on SOL (0.64% cost) -> very viable
        result = precheck_cost(event, trade_size_usd=500, min_edge_pct=0.05)
        assert result.is_tradeable

    def test_edge_check_insufficient(self):
        event = MarketEvent(
            event_type=MarketEventType.TOKEN_LAUNCH,
            urgency=EventUrgency.IMMEDIATE,
            asset_class=AssetClass.BAGS_GRADUATED,
            pool_liquidity_usd=100_000,
        )
        # 2% edge on post-grad bags (5.88% cost) -> NOT viable
        result = precheck_cost(event, trade_size_usd=200, min_edge_pct=0.02)
        assert not result.is_tradeable
        assert "insufficient_edge" in result.cost_check_reason

    def test_missing_asset_class(self):
        event = MarketEvent(
            event_type=MarketEventType.VOLUME_EXPLOSION,
            urgency=EventUrgency.FAST,
            asset_class=None,
        )
        result = precheck_cost(event)
        assert not result.is_tradeable
        assert "missing" in result.cost_check_reason


class TestClassifyStreamEvent:

    def test_graduation_event(self):
        """Test classification of graduation stream event."""
        from core.events.market_events import classify_stream_event
        from core.data.streams import StreamEvent, StreamEventType

        stream_evt = StreamEvent(
            event_type=StreamEventType.GRADUATION,
            program_id="BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv",
            signature="5abc123" * 8,
            mint_address="TokenMint111111111111111111111111111111111",
            pool_address="Pool11111111111111111111111111111111111111",
        )

        market_evt = classify_stream_event(stream_evt)
        assert market_evt is not None
        assert market_evt.event_type == MarketEventType.GRADUATION
        assert market_evt.urgency == EventUrgency.IMMEDIATE
        assert market_evt.source_type == "stream"

    def test_pump_fun_launch(self):
        from core.events.market_events import classify_stream_event
        from core.data.streams import StreamEvent, StreamEventType

        stream_evt = StreamEvent(
            event_type=StreamEventType.NEW_POOL,
            program_id="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            signature="sig123" * 11,
            mint_address="NewToken111111111111111111111111111111111",
        )

        market_evt = classify_stream_event(stream_evt)
        assert market_evt is not None
        assert market_evt.event_type == MarketEventType.TOKEN_LAUNCH

    def test_raydium_pool_created(self):
        from core.events.market_events import classify_stream_event
        from core.data.streams import StreamEvent, StreamEventType

        stream_evt = StreamEvent(
            event_type=StreamEventType.NEW_POOL,
            program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            signature="sig456" * 11,
        )

        market_evt = classify_stream_event(stream_evt)
        assert market_evt is not None
        assert market_evt.event_type == MarketEventType.POOL_CREATED

    def test_swap_returns_none(self):
        """Swaps are aggregated, not individual events."""
        from core.events.market_events import classify_stream_event
        from core.data.streams import StreamEvent, StreamEventType

        stream_evt = StreamEvent(
            event_type=StreamEventType.SWAP,
            program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
            signature="sig789" * 11,
        )

        market_evt = classify_stream_event(stream_evt)
        assert market_evt is None

    def test_none_input(self):
        from core.events.market_events import classify_stream_event
        assert classify_stream_event(None) is None
