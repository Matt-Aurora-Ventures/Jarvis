"""
Unit tests for EventBus.

Tests:
- Event emission and handling
- Priority queue ordering
- Handler timeout wrapping (Issue #4 fix)
- Backpressure handling
- Dead letter queue
- Trace ID propagation
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from core.event_bus.event_bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    EventHandler,
)


class SimpleHandler(EventHandler):
    """Simple handler implementation."""

    def __init__(self, name: str, delay: float = 0.0, fail: bool = False):
        self._name = name
        self.delay = delay
        self.fail = fail
        self.handled_events = []

    @property
    def name(self) -> str:
        return self._name

    def handles(self, event_type: EventType) -> bool:
        return True

    async def handle(self, event: Event):
        """Handle event with optional delay and failure."""
        await asyncio.sleep(self.delay)
        self.handled_events.append(event)

        if self.fail:
            return False, "Test failure"
        return True, None


class SlowHandler(EventHandler):
    """Handler that times out."""

    @property
    def name(self) -> str:
        return "slow_handler"

    def handles(self, event_type: EventType) -> bool:
        return True

    async def handle(self, event: Event):
        """Simulate a hung task by sleeping longer than timeout."""
        try:
            await asyncio.sleep(100)  # Will timeout
            return True, None
        except asyncio.CancelledError:
            return False, "Cancelled"


@pytest.mark.asyncio
async def test_basic_event_emission():
    """Test basic event emission and handling."""
    bus = EventBus(max_queue_size=100, handler_timeout=5.0)
    handler = SimpleHandler("test_handler")

    bus.register_handler(handler, [EventType.TWEET_POSTED])
    await bus.start()

    # Emit event
    event = Event(
        event_type=EventType.TWEET_POSTED,
        data={"content": "Test tweet"},
        source="test"
    )
    result = await bus.emit(event)
    assert result is True

    # Wait for processing
    await asyncio.sleep(0.1)
    await bus.stop()

    # Verify handler processed event
    assert len(handler.handled_events) == 1
    assert handler.handled_events[0].event_type == EventType.TWEET_POSTED


@pytest.mark.asyncio
async def test_priority_queue_ordering():
    """Test that high-priority events are processed first."""
    bus = EventBus(max_queue_size=100, handler_timeout=5.0)
    handler = SimpleHandler("test_handler", delay=0.05)

    bus.register_handler(handler, [EventType.TRADE_EXECUTED, EventType.ERROR])
    await bus.start()

    # Emit events in order: NORMAL, LOW, HIGH
    events = [
        Event(EventType.TRADE_EXECUTED, {"data": "1"}, priority=EventPriority.NORMAL),
        Event(EventType.TRADE_EXECUTED, {"data": "2"}, priority=EventPriority.LOW),
        Event(EventType.TRADE_EXECUTED, {"data": "3"}, priority=EventPriority.HIGH),
    ]

    for event in events:
        await bus.emit(event)

    # Wait for processing
    await asyncio.sleep(0.5)
    await bus.stop()

    # Verify high priority was processed early
    # HIGH (data=3) should be first, then NORMAL (data=1), then LOW (data=2)
    processed_data = [e.data["data"] for e in handler.handled_events]
    assert processed_data[0] == "3"  # HIGH priority first
    assert processed_data[1] == "1"  # NORMAL priority second
    assert processed_data[2] == "2"  # LOW priority last


@pytest.mark.asyncio
async def test_handler_timeout_wrapping():
    """Test that slow handlers timeout correctly (Issue #4 fix)."""
    bus = EventBus(max_queue_size=100, handler_timeout=0.1)

    # Create a handler that will definitely timeout
    class TimeoutingHandler(EventHandler):
        @property
        def name(self) -> str:
            return "timeouting_handler"

        def handles(self, event_type: EventType) -> bool:
            return True

        async def handle(self, event: Event):
            # Sleep longer than timeout
            await asyncio.sleep(10.0)
            return True, None

    timeout_handler = TimeoutingHandler()
    bus.register_handler(timeout_handler, [EventType.ERROR])
    await bus.start()

    event = Event(EventType.ERROR, {"type": "test"})
    result = await bus.emit(event)
    assert result is True

    # Wait for timeout to occur
    await asyncio.sleep(0.5)
    await bus.stop()

    # Verify timeout was recorded
    stats = bus.get_stats()
    assert stats["handler_timeouts"] > 0


@pytest.mark.asyncio
async def test_backpressure_handling():
    """Test that backpressure blocks producers when queue is full."""
    bus = EventBus(max_queue_size=5, handler_timeout=5.0)
    handler = SimpleHandler("slow_handler", delay=0.2)  # Slow to process

    bus.register_handler(handler, [EventType.TWEET_POSTED])
    await bus.start()

    # Emit many events rapidly (more than queue size)
    queued = 0
    dropped = 0

    for i in range(20):
        event = Event(
            EventType.TWEET_POSTED,
            {"id": i},
            source="test"
        )
        if await bus.emit(event):
            queued += 1
        else:
            dropped += 1

    # Some events should be queued, some may timeout/drop
    assert queued > 0
    assert queued + dropped == 20

    await asyncio.sleep(0.5)
    await bus.stop()

    # Verify events were processed
    assert len(handler.handled_events) > 0


@pytest.mark.asyncio
async def test_dead_letter_queue():
    """Test that failed events go to DLQ."""
    bus = EventBus(max_queue_size=100, handler_timeout=5.0)
    failing_handler = SimpleHandler("failing", fail=True)

    bus.register_handler(failing_handler, [EventType.BUY_FAILED])
    await bus.start()

    # Emit event
    event = Event(EventType.BUY_FAILED, {"reason": "test"})
    await bus.emit(event)

    # Wait for processing
    await asyncio.sleep(0.1)
    await bus.stop()

    # Verify DLQ has the failed event
    dlq = bus.get_dead_letter_queue()
    assert len(dlq) > 0
    assert dlq[0]["event_type"] == "buy_failed"


@pytest.mark.asyncio
async def test_trace_id_propagation():
    """Test that trace IDs are propagated for debugging."""
    bus = EventBus()
    handler = SimpleHandler("test")

    bus.register_handler(handler, [EventType.SENTIMENT_ANALYSIS])
    await bus.start()

    # Create event with specific trace ID
    event = Event(
        EventType.SENTIMENT_ANALYSIS,
        {"token": "KR8TIV"},
        source="test"
    )
    custom_trace = event.trace_id

    await bus.emit(event)
    await asyncio.sleep(0.1)
    await bus.stop()

    # Verify trace ID is preserved
    assert handler.handled_events[0].trace_id == custom_trace


@pytest.mark.asyncio
async def test_event_expiration():
    """Test that expired events are dropped."""
    bus = EventBus()
    handler = SimpleHandler("test")

    bus.register_handler(handler, [EventType.STARTUP])
    await bus.start()

    # Create expired event
    past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    event = Event(
        EventType.STARTUP,
        {"data": "test"},
        expires_at=past_time
    )

    result = await bus.emit(event)
    await asyncio.sleep(0.1)
    await bus.stop()

    # Expired event should not be processed
    assert result is False
    assert len(handler.handled_events) == 0


@pytest.mark.asyncio
async def test_statistics():
    """Test event bus statistics collection."""
    bus = EventBus(max_queue_size=100, handler_timeout=5.0)
    handler = SimpleHandler("test")

    bus.register_handler(handler, [EventType.TRADE_EXECUTED])
    await bus.start()

    # Emit events
    for i in range(5):
        event = Event(EventType.TRADE_EXECUTED, {"id": i})
        await bus.emit(event)

    await asyncio.sleep(0.2)
    await bus.stop()

    # Verify stats
    stats = bus.get_stats()
    assert stats["events_processed"] >= 5
    assert stats["max_queue_size"] == 100
    assert stats["handler_timeout"] == 5.0


@pytest.mark.asyncio
async def test_multiple_handlers_for_event():
    """Test that multiple handlers can process same event type."""
    bus = EventBus()
    handler1 = SimpleHandler("handler1")
    handler2 = SimpleHandler("handler2")

    bus.register_handler(handler1, [EventType.POSITION_OPENED])
    bus.register_handler(handler2, [EventType.POSITION_OPENED])
    await bus.start()

    event = Event(EventType.POSITION_OPENED, {"position_id": 123})
    await bus.emit(event)

    await asyncio.sleep(0.1)
    await bus.stop()

    # Both handlers should have processed the event
    assert len(handler1.handled_events) == 1
    assert len(handler2.handled_events) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
