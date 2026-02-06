"""
Unit tests for extended core/events/bus.py functionality.

Tests cover:
- subscribe(event_type, handler) direct method (not decorator)
- unsubscribe(event_type, handler)
- publish(event) sync delivery
- publish_async(event) async delivery
- get_subscribers(event_type)
"""

import pytest
import sys
from pathlib import Path
import asyncio
from typing import List
from datetime import datetime

# Add project root to path to avoid core/__init__.py import chain issues
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestEventBusSingleton:
    """Tests for EventBus singleton pattern."""

    def test_get_event_bus_returns_singleton(self):
        """get_event_bus should return same instance."""
        from core.events.bus import get_event_bus

        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

    def test_event_bus_direct_instantiation(self):
        """EventBus should be directly instantiable for testing."""
        from core.events.bus import EventBus

        bus = EventBus()
        assert bus is not None


class TestSubscribeMethod:
    """Tests for subscribe(event_type, handler) method."""

    @pytest.mark.asyncio
    async def test_subscribe_with_handler_object(self):
        """subscribe should accept handler objects."""
        from core.events.bus import EventBus
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class TestHandler(EventHandler):
            def __init__(self):
                self.events: List[Event] = []

            async def handle(self, event: Event) -> None:
                self.events.append(event)

        bus = EventBus()
        handler = TestHandler()

        bus.subscribe("test.event", handler)

        event = Event(type="test.event")
        await bus.publish(event)

        assert len(handler.events) == 1

    @pytest.mark.asyncio
    async def test_subscribe_with_async_function(self):
        """subscribe should accept async functions."""
        from core.events.bus import EventBus
        from core.events.types import Event

        events_received: List[Event] = []

        async def handler(event: Event) -> None:
            events_received.append(event)

        bus = EventBus()
        bus.subscribe("test.event", handler)

        await bus.publish(Event(type="test.event"))

        assert len(events_received) == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers_same_type(self):
        """Multiple handlers can subscribe to same event type."""
        from core.events.bus import EventBus
        from core.events.types import Event

        results = {"handler1": 0, "handler2": 0}

        async def handler1(event: Event) -> None:
            results["handler1"] += 1

        async def handler2(event: Event) -> None:
            results["handler2"] += 1

        bus = EventBus()
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)

        await bus.publish(Event(type="test.event"))

        assert results["handler1"] == 1
        assert results["handler2"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_handler_to_multiple_types(self):
        """Same handler can subscribe to multiple event types."""
        from core.events.bus import EventBus
        from core.events.types import Event

        events_received: List[Event] = []

        async def handler(event: Event) -> None:
            events_received.append(event)

        bus = EventBus()
        bus.subscribe("event.a", handler)
        bus.subscribe("event.b", handler)

        await bus.publish(Event(type="event.a"))
        await bus.publish(Event(type="event.b"))

        assert len(events_received) == 2


class TestUnsubscribeMethod:
    """Tests for unsubscribe(event_type, handler) method."""

    @pytest.mark.asyncio
    async def test_unsubscribe_handler(self):
        """unsubscribe should remove handler from event type."""
        from core.events.bus import EventBus
        from core.events.types import Event

        events_received: List[Event] = []

        async def handler(event: Event) -> None:
            events_received.append(event)

        bus = EventBus()
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)

        await bus.publish(Event(type="test.event"))

        assert len(events_received) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_returns_true_on_success(self):
        """unsubscribe should return True when handler was removed."""
        from core.events.bus import EventBus

        async def handler(event) -> None:
            pass

        bus = EventBus()
        bus.subscribe("test.event", handler)
        result = bus.unsubscribe("test.event", handler)

        assert result is True

    def test_unsubscribe_returns_false_when_not_found(self):
        """unsubscribe should return False when handler not found."""
        from core.events.bus import EventBus

        async def handler(event) -> None:
            pass

        bus = EventBus()
        result = bus.unsubscribe("test.event", handler)

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_one_keeps_others(self):
        """unsubscribe one handler should keep others."""
        from core.events.bus import EventBus
        from core.events.types import Event

        results = {"handler1": 0, "handler2": 0}

        async def handler1(event: Event) -> None:
            results["handler1"] += 1

        async def handler2(event: Event) -> None:
            results["handler2"] += 1

        bus = EventBus()
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        bus.unsubscribe("test.event", handler1)

        await bus.publish(Event(type="test.event"))

        assert results["handler1"] == 0
        assert results["handler2"] == 1


class TestPublishSync:
    """Tests for publish(event) sync delivery."""

    @pytest.mark.asyncio
    async def test_publish_delivers_to_handlers(self):
        """publish should deliver event to subscribed handlers."""
        from core.events.bus import EventBus
        from core.events.types import Event

        events_received: List[Event] = []

        async def handler(event: Event) -> None:
            events_received.append(event)

        bus = EventBus()
        bus.subscribe("test.event", handler)

        await bus.publish(Event(type="test.event", data={"key": "value"}))

        assert len(events_received) == 1
        assert events_received[0].data["key"] == "value"

    @pytest.mark.asyncio
    async def test_publish_returns_handler_count(self):
        """publish should return number of handlers that received event."""
        from core.events.bus import EventBus
        from core.events.types import Event

        async def handler1(event: Event) -> None:
            pass

        async def handler2(event: Event) -> None:
            pass

        bus = EventBus()
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)

        count = await bus.publish(Event(type="test.event"))

        assert count == 2

    @pytest.mark.asyncio
    async def test_publish_no_handlers_returns_zero(self):
        """publish with no subscribers should return 0."""
        from core.events.bus import EventBus
        from core.events.types import Event

        bus = EventBus()
        count = await bus.publish(Event(type="unsubscribed.event"))

        assert count == 0


class TestPublishAsync:
    """Tests for publish_async(event) async delivery."""

    @pytest.mark.asyncio
    async def test_publish_async_does_not_block(self):
        """publish_async should not block caller."""
        from core.events.bus import EventBus
        from core.events.types import Event

        handler_called = False
        handler_finished = False

        async def slow_handler(event: Event) -> None:
            nonlocal handler_called, handler_finished
            handler_called = True
            await asyncio.sleep(0.1)
            handler_finished = True

        bus = EventBus()
        bus.subscribe("test.event", slow_handler)

        # publish_async should return immediately
        await bus.publish_async(Event(type="test.event"))

        # Handler started but may not be finished
        await asyncio.sleep(0.01)
        assert handler_called is True

        # Wait for handler to complete
        await asyncio.sleep(0.2)
        assert handler_finished is True


class TestGetSubscribers:
    """Tests for get_subscribers(event_type) method."""

    def test_get_subscribers_returns_list(self):
        """get_subscribers should return list of handlers."""
        from core.events.bus import EventBus

        async def handler(event) -> None:
            pass

        bus = EventBus()
        bus.subscribe("test.event", handler)

        subscribers = bus.get_subscribers("test.event")

        assert isinstance(subscribers, list)
        assert len(subscribers) == 1

    def test_get_subscribers_empty_when_none(self):
        """get_subscribers should return empty list when no subscribers."""
        from core.events.bus import EventBus

        bus = EventBus()
        subscribers = bus.get_subscribers("no.subscribers")

        assert subscribers == []

    def test_get_subscribers_includes_all(self):
        """get_subscribers should include all handlers for type."""
        from core.events.bus import EventBus

        async def handler1(event) -> None:
            pass

        async def handler2(event) -> None:
            pass

        bus = EventBus()
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)

        subscribers = bus.get_subscribers("test.event")

        assert len(subscribers) == 2


class TestEventBusWithHandlers:
    """Integration tests with EventHandler implementations."""

    @pytest.mark.asyncio
    async def test_bus_with_logging_handler(self):
        """EventBus should work with LoggingHandler."""
        from core.events.bus import EventBus
        from core.events.handlers import LoggingHandler
        from core.events.types import Event

        bus = EventBus()
        handler = LoggingHandler()
        bus.subscribe("*", handler)

        # Should not raise
        await bus.publish(Event(type="test.event"))

    @pytest.mark.asyncio
    async def test_bus_with_metrics_handler(self):
        """EventBus should work with MetricsHandler."""
        from core.events.bus import EventBus
        from core.events.handlers import MetricsHandler
        from core.events.types import Event

        bus = EventBus()
        handler = MetricsHandler()
        bus.subscribe("*", handler)

        await bus.publish(Event(type="test.event"))
        await bus.publish(Event(type="test.event"))

        metrics = handler.get_metrics()
        assert metrics["test.event"]["count"] == 2


class TestWildcardSubscription:
    """Tests for wildcard event subscriptions."""

    @pytest.mark.asyncio
    async def test_wildcard_matches_all(self):
        """Wildcard '*' should match all event types."""
        from core.events.bus import EventBus
        from core.events.types import Event

        events_received: List[Event] = []

        async def handler(event: Event) -> None:
            events_received.append(event)

        bus = EventBus()
        bus.subscribe("*", handler)

        await bus.publish(Event(type="event.a"))
        await bus.publish(Event(type="event.b"))
        await bus.publish(Event(type="totally.different"))

        assert len(events_received) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
