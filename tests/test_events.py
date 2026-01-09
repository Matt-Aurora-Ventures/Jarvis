"""
Tests for lifeos/events (Event Bus System).

Tests cover:
- Event creation and matching
- Event bus emission and subscription
- Middleware functionality
- History and replay
- Dead letter queue
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.events import (
    Event,
    EventPriority,
    EventBus,
    EventMiddleware,
    LoggingMiddleware,
)
from lifeos.events.middleware import (
    FilterMiddleware,
    ThrottleMiddleware,
    TransformMiddleware,
    MetricsMiddleware,
)


# =============================================================================
# Test Event
# =============================================================================

class TestEvent:
    """Test Event class."""

    def test_create_event(self):
        """Should create event with topic."""
        event = Event(topic="test.event")

        assert event.topic == "test.event"
        assert event.data == {}
        assert event.priority == EventPriority.NORMAL

    def test_create_event_with_data(self):
        """Should create event with data."""
        event = Event(
            topic="test.event",
            data={"key": "value"},
        )

        assert event.data["key"] == "value"

    def test_event_has_id(self):
        """Should have unique ID."""
        event1 = Event(topic="test")
        event2 = Event(topic="test")

        assert event1.id != event2.id

    def test_event_matches_exact(self):
        """Should match exact topic."""
        event = Event(topic="user.login")

        assert event.matches_pattern("user.login")
        assert not event.matches_pattern("user.logout")

    def test_event_matches_single_wildcard(self):
        """Should match single segment wildcard."""
        event = Event(topic="user.login")

        assert event.matches_pattern("user.*")
        assert event.matches_pattern("*.login")
        assert not event.matches_pattern("*.logout")

    def test_event_matches_multi_wildcard(self):
        """Should match multi-segment wildcard."""
        event = Event(topic="user.profile.update")

        assert event.matches_pattern("user.**")
        assert event.matches_pattern("**.update")
        assert event.matches_pattern("**")

    def test_event_matches_mixed_wildcards(self):
        """Should match mixed wildcards."""
        event = Event(topic="api.user.profile.get")

        assert event.matches_pattern("api.*.profile.*")
        assert event.matches_pattern("api.**")
        assert event.matches_pattern("**.get")

    def test_stop_propagation(self):
        """Should stop propagation."""
        event = Event(topic="test")

        assert not event.is_propagation_stopped
        event.stop_propagation()
        assert event.is_propagation_stopped

    def test_mark_handled(self):
        """Should track handled state."""
        event = Event(topic="test")

        assert not event.is_handled
        event.mark_handled()
        assert event.is_handled

    def test_set_error(self):
        """Should track errors."""
        event = Event(topic="test")
        error = ValueError("test error")

        assert not event.has_error
        event.set_error(error)
        assert event.has_error
        assert event.error is error

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize."""
        original = Event(
            topic="test.event",
            data={"key": "value"},
            priority=EventPriority.HIGH,
            source="test",
        )

        data = original.to_dict()
        restored = Event.from_dict(data)

        assert restored.topic == original.topic
        assert restored.data == original.data
        assert restored.priority == original.priority
        assert restored.source == original.source

    def test_create_reply(self):
        """Should create reply event."""
        original = Event(topic="request", correlation_id="123")

        reply = original.create_reply("response", {"result": "ok"})

        assert reply.topic == "response"
        assert reply.correlation_id == "123"
        assert reply.source == "request"

    def test_create_derived(self):
        """Should create derived event."""
        original = Event(
            topic="original",
            data={"key": "value"},
            metadata={"trace": "123"},
        )

        derived = original.create_derived("derived")

        assert derived.topic == "derived"
        assert derived.data["key"] == "value"
        assert derived.metadata["parent_event_id"] == original.id


# =============================================================================
# Test EventBus
# =============================================================================

class TestEventBus:
    """Test EventBus functionality."""

    @pytest.mark.asyncio
    async def test_emit_and_handle(self):
        """Should emit event and call handler."""
        bus = EventBus()
        received = []

        @bus.on("test")
        async def handler(event):
            received.append(event)

        await bus.emit("test", {"data": 1})

        assert len(received) == 1
        assert received[0].topic == "test"
        assert received[0].data["data"] == 1

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self):
        """Should match wildcard patterns."""
        bus = EventBus()
        received = []

        @bus.on("user.*")
        async def handler(event):
            received.append(event)

        await bus.emit("user.login")
        await bus.emit("user.logout")
        await bus.emit("system.start")  # Should not match

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_multi_wildcard(self):
        """Should match multi-segment wildcards."""
        bus = EventBus()
        received = []

        @bus.on("**")
        async def handler(event):
            received.append(event)

        await bus.emit("a")
        await bus.emit("a.b")
        await bus.emit("a.b.c")

        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_handler_priority(self):
        """Should call handlers in priority order."""
        bus = EventBus()
        order = []

        @bus.on("test", priority=1)
        async def low_priority(event):
            order.append("low")

        @bus.on("test", priority=10)
        async def high_priority(event):
            order.append("high")

        @bus.on("test", priority=5)
        async def medium_priority(event):
            order.append("medium")

        await bus.emit("test")

        assert order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_once_handler(self):
        """Should remove once handler after first call."""
        bus = EventBus()
        count = [0]

        @bus.on("test", once=True)
        async def handler(event):
            count[0] += 1

        await bus.emit("test")
        await bus.emit("test")
        await bus.emit("test")

        assert count[0] == 1

    @pytest.mark.asyncio
    async def test_stop_propagation(self):
        """Should stop propagation when requested."""
        bus = EventBus()
        called = []

        @bus.on("test", priority=10)
        async def first(event):
            called.append("first")
            event.stop_propagation()

        @bus.on("test", priority=1)
        async def second(event):
            called.append("second")

        await bus.emit("test")

        assert called == ["first"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Should unsubscribe handlers."""
        bus = EventBus()
        count = [0]

        async def handler(event):
            count[0] += 1

        bus.subscribe("test", handler)
        await bus.emit("test")

        bus.unsubscribe("test", handler)
        await bus.emit("test")

        assert count[0] == 1

    @pytest.mark.asyncio
    async def test_filter_function(self):
        """Should filter events."""
        bus = EventBus()
        received = []

        @bus.on("test", filter_fn=lambda e: e.data.get("important"))
        async def handler(event):
            received.append(event)

        await bus.emit("test", {"important": True})
        await bus.emit("test", {"important": False})
        await bus.emit("test", {})

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_handler_error(self):
        """Should handle errors and add to dead letters."""
        bus = EventBus()

        @bus.on("test")
        async def failing_handler(event):
            raise ValueError("Handler failed")

        event = await bus.emit("test")

        assert event.has_error
        assert len(bus.get_dead_letters()) == 1

    @pytest.mark.asyncio
    async def test_event_history(self):
        """Should keep event history."""
        bus = EventBus(max_history=10)

        await bus.emit("event.1")
        await bus.emit("event.2")
        await bus.emit("event.3")

        history = bus.get_history()

        assert len(history) == 3
        assert history[0].topic == "event.1"

    @pytest.mark.asyncio
    async def test_history_pattern_filter(self):
        """Should filter history by pattern."""
        bus = EventBus()

        await bus.emit("user.login")
        await bus.emit("user.logout")
        await bus.emit("system.start")

        user_events = bus.get_history(pattern="user.*")

        assert len(user_events) == 2

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """Should pause and queue events."""
        bus = EventBus()
        received = []

        @bus.on("test")
        async def handler(event):
            received.append(event)

        bus.pause()
        await bus.emit("test", {"n": 1})
        await bus.emit("test", {"n": 2})

        assert len(received) == 0
        assert bus.is_paused

        count = await bus.resume()

        assert count == 2
        assert len(received) == 2
        assert not bus.is_paused

    @pytest.mark.asyncio
    async def test_emit_many(self):
        """Should emit multiple events."""
        bus = EventBus()
        received = []

        @bus.on("**")
        async def handler(event):
            received.append(event)

        await bus.emit_many([
            ("event.1", {"data": 1}),
            ("event.2", {"data": 2}),
        ])

        assert len(received) == 2

    def test_get_stats(self):
        """Should return statistics."""
        bus = EventBus()
        stats = bus.get_stats()

        assert "events_emitted" in stats
        assert "subscription_count" in stats
        assert "history_size" in stats

    @pytest.mark.asyncio
    async def test_replay(self):
        """Should replay events."""
        bus = EventBus()
        received = []

        @bus.on("test")
        async def handler(event):
            received.append(event)

        await bus.emit("test", {"n": 1})
        await bus.emit("test", {"n": 2})

        received.clear()

        count = await bus.replay(pattern="test")

        assert count == 2
        assert len(received) == 2


# =============================================================================
# Test Middleware
# =============================================================================

class TestMiddleware:
    """Test event middleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware(self):
        """LoggingMiddleware should log events."""
        bus = EventBus()
        middleware = LoggingMiddleware()
        bus.use(middleware)

        # Should not raise
        await bus.emit("test")

    @pytest.mark.asyncio
    async def test_filter_middleware_deny(self):
        """FilterMiddleware should block denied events."""
        bus = EventBus()
        received = []

        @bus.on("**")
        async def handler(event):
            received.append(event)

        bus.use(FilterMiddleware(deny_patterns=["blocked.*"]))

        await bus.emit("allowed")
        await bus.emit("blocked.event")

        assert len(received) == 1
        assert received[0].topic == "allowed"

    @pytest.mark.asyncio
    async def test_filter_middleware_allow(self):
        """FilterMiddleware should only allow matching events."""
        bus = EventBus()
        received = []

        @bus.on("**")
        async def handler(event):
            received.append(event)

        bus.use(FilterMiddleware(allow_patterns=["allowed.*"]))

        await bus.emit("allowed.event")
        await bus.emit("other.event")

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_throttle_middleware(self):
        """ThrottleMiddleware should rate limit."""
        bus = EventBus()
        received = []

        @bus.on("test")
        async def handler(event):
            received.append(event)

        bus.use(ThrottleMiddleware(max_per_second=1, burst_size=2))

        # Burst should allow first 2
        await bus.emit("test")
        await bus.emit("test")
        await bus.emit("test")  # Should be throttled
        await bus.emit("test")  # Should be throttled

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_transform_middleware(self):
        """TransformMiddleware should transform events."""
        bus = EventBus()
        received = []

        @bus.on("test")
        async def handler(event):
            received.append(event)

        def add_metadata(event):
            event.metadata["transformed"] = True
            return event

        bus.use(TransformMiddleware(add_metadata))

        await bus.emit("test")

        assert received[0].metadata.get("transformed") is True

    @pytest.mark.asyncio
    async def test_metrics_middleware(self):
        """MetricsMiddleware should collect metrics."""
        bus = EventBus()
        metrics = MetricsMiddleware()
        bus.use(metrics)

        await bus.emit("topic.a")
        await bus.emit("topic.a")
        await bus.emit("topic.b")

        result = metrics.get_metrics()

        assert result["topic.a"]["count"] == 2
        assert result["topic.b"]["count"] == 1

    @pytest.mark.asyncio
    async def test_middleware_chain(self):
        """Should apply middleware in order."""
        bus = EventBus()
        order = []

        class TrackingMiddleware(EventMiddleware):
            def __init__(self, name):
                self.name = name

            async def before_emit(self, event):
                order.append(f"before:{self.name}")
                return event

            async def after_emit(self, event):
                order.append(f"after:{self.name}")

        bus.use(TrackingMiddleware("first"))
        bus.use(TrackingMiddleware("second"))

        @bus.on("test")
        async def handler(event):
            order.append("handler")

        await bus.emit("test")

        assert order == [
            "before:first",
            "before:second",
            "handler",
            "after:second",
            "after:first",
        ]

    @pytest.mark.asyncio
    async def test_remove_middleware(self):
        """Should remove middleware."""
        bus = EventBus()
        middleware = FilterMiddleware(deny_patterns=["blocked"])
        bus.use(middleware)

        received = []

        @bus.on("**")
        async def handler(event):
            received.append(event)

        await bus.emit("blocked")
        assert len(received) == 0

        bus.remove_middleware(middleware)
        await bus.emit("blocked")
        assert len(received) == 1


# =============================================================================
# Test Dead Letters
# =============================================================================

class TestDeadLetters:
    """Test dead letter queue functionality."""

    @pytest.mark.asyncio
    async def test_dead_letter_on_error(self):
        """Should add failed events to dead letter queue."""
        bus = EventBus()

        @bus.on("test")
        async def failing(event):
            raise RuntimeError("Handler error")

        await bus.emit("test")

        dead_letters = bus.get_dead_letters()
        assert len(dead_letters) == 1
        assert isinstance(dead_letters[0].error, RuntimeError)

    @pytest.mark.asyncio
    async def test_clear_dead_letters(self):
        """Should clear dead letters."""
        bus = EventBus()

        @bus.on("test")
        async def failing(event):
            raise RuntimeError()

        await bus.emit("test")
        count = bus.clear_dead_letters()

        assert count == 1
        assert len(bus.get_dead_letters()) == 0

    @pytest.mark.asyncio
    async def test_dead_letter_limit(self):
        """Should limit dead letter queue size."""
        bus = EventBus(max_dead_letters=5)

        @bus.on("test")
        async def failing(event):
            raise RuntimeError()

        for _ in range(10):
            await bus.emit("test")

        assert len(bus.get_dead_letters()) == 5


# =============================================================================
# Integration Tests
# =============================================================================

class TestEventBusIntegration:
    """Integration tests for event bus."""

    @pytest.mark.asyncio
    async def test_complex_workflow(self):
        """Test complex event workflow."""
        bus = EventBus()
        log = []

        # Set up middleware
        bus.use(MetricsMiddleware())

        # Register handlers
        @bus.on("order.created", priority=10)
        async def validate_order(event):
            log.append(f"validate:{event.data['order_id']}")
            # Emit derived event
            await bus.emit_event(
                event.create_derived("order.validated")
            )

        @bus.on("order.validated")
        async def process_order(event):
            log.append(f"process:{event.data['order_id']}")

        @bus.on("order.**")
        async def audit(event):
            log.append(f"audit:{event.topic}")

        # Emit initial event
        await bus.emit("order.created", {"order_id": 123})

        # Verify workflow
        assert "validate:123" in log
        assert "process:123" in log
        assert log.count("audit:order.created") == 1
        assert log.count("audit:order.validated") == 1

    @pytest.mark.asyncio
    async def test_correlation_tracking(self):
        """Test correlation ID tracking."""
        bus = EventBus()
        events = []

        @bus.on("**")
        async def collect(event):
            events.append(event)

        # Emit with correlation ID
        original = await bus.emit(
            "request",
            {"data": 1},
            correlation_id="request-123",
        )

        # Create and emit reply
        reply = original.create_reply("response", {"result": "ok"})
        await bus.emit_event(reply)

        # All events should share correlation ID
        assert all(e.correlation_id == "request-123" for e in events)

    @pytest.mark.asyncio
    async def test_concurrent_handlers(self):
        """Test concurrent event handling."""
        bus = EventBus()
        results = []
        lock = asyncio.Lock()

        @bus.on("concurrent")
        async def slow_handler(event):
            await asyncio.sleep(0.01)
            async with lock:
                results.append(event.data["n"])

        # Emit multiple events
        await bus.emit_many([
            ("concurrent", {"n": 1}),
            ("concurrent", {"n": 2}),
            ("concurrent", {"n": 3}),
        ])

        # All should complete
        assert len(results) == 3
        assert set(results) == {1, 2, 3}
