"""
Unit tests for core/events/persistence.py - Event storage and replay.

Tests cover:
- EventStore creation and initialization
- store_event(event) - storing events
- get_events(since, until, type) - querying events
- replay_events(handler) - replaying events through handlers
"""

import pytest
import sys
from pathlib import Path
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
import tempfile
import json

# Add project root to path to avoid core/__init__.py import chain issues
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestEventStoreCreation:
    """Tests for EventStore creation and initialization."""

    def test_event_store_creation_in_memory(self):
        """EventStore should be creatable for in-memory storage."""
        from core.events.persistence import EventStore

        store = EventStore()
        assert store is not None

    def test_event_store_creation_with_file_path(self):
        """EventStore should accept optional file path for persistence."""
        from core.events.persistence import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.json"
            store = EventStore(file_path=path)
            assert store.file_path == path

    def test_event_store_creation_with_max_events(self):
        """EventStore should accept max_events limit."""
        from core.events.persistence import EventStore

        store = EventStore(max_events=1000)
        assert store.max_events == 1000


class TestEventStoreStorage:
    """Tests for store_event() functionality."""

    @pytest.mark.asyncio
    async def test_store_event(self):
        """store_event should store an event."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()
        event = Event(type="test.event", data={"key": "value"})

        await store.store_event(event)

        assert store.event_count == 1

    @pytest.mark.asyncio
    async def test_store_multiple_events(self):
        """store_event should store multiple events."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        await store.store_event(Event(type="event.a"))
        await store.store_event(Event(type="event.b"))
        await store.store_event(Event(type="event.c"))

        assert store.event_count == 3

    @pytest.mark.asyncio
    async def test_store_event_respects_max_events(self):
        """store_event should respect max_events limit (FIFO eviction)."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore(max_events=3)

        await store.store_event(Event(type="event.1"))
        await store.store_event(Event(type="event.2"))
        await store.store_event(Event(type="event.3"))
        await store.store_event(Event(type="event.4"))

        assert store.event_count == 3
        events = await store.get_events()
        event_types = [e.type for e in events]
        assert "event.1" not in event_types
        assert "event.4" in event_types

    @pytest.mark.asyncio
    async def test_store_event_persists_to_file(self):
        """store_event should persist to file when configured."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.json"
            store = EventStore(file_path=path)

            await store.store_event(Event(type="test.event"))
            await store.flush()  # Ensure written to disk

            assert path.exists()
            content = path.read_text()
            assert "test.event" in content


class TestEventStoreQuerying:
    """Tests for get_events() functionality."""

    @pytest.mark.asyncio
    async def test_get_events_returns_all(self):
        """get_events without filters returns all events."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        await store.store_event(Event(type="event.a"))
        await store.store_event(Event(type="event.b"))

        events = await store.get_events()

        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_get_events_filter_by_type(self):
        """get_events should filter by event type."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        await store.store_event(Event(type="message.received"))
        await store.store_event(Event(type="message.sent"))
        await store.store_event(Event(type="error.occurred"))

        events = await store.get_events(event_type="message.received")

        assert len(events) == 1
        assert events[0].type == "message.received"

    @pytest.mark.asyncio
    async def test_get_events_filter_by_type_pattern(self):
        """get_events should support type pattern matching."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        await store.store_event(Event(type="message.received"))
        await store.store_event(Event(type="message.sent"))
        await store.store_event(Event(type="error.occurred"))

        events = await store.get_events(event_type="message.*")

        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_get_events_filter_by_since(self):
        """get_events should filter by since timestamp."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        old_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        new_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        await store.store_event(Event(type="old.event", timestamp=old_time))
        await store.store_event(Event(type="new.event", timestamp=new_time))

        cutoff = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        events = await store.get_events(since=cutoff)

        assert len(events) == 1
        assert events[0].type == "new.event"

    @pytest.mark.asyncio
    async def test_get_events_filter_by_until(self):
        """get_events should filter by until timestamp."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        old_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        new_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        await store.store_event(Event(type="old.event", timestamp=old_time))
        await store.store_event(Event(type="new.event", timestamp=new_time))

        cutoff = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        events = await store.get_events(until=cutoff)

        assert len(events) == 1
        assert events[0].type == "old.event"

    @pytest.mark.asyncio
    async def test_get_events_combined_filters(self):
        """get_events should support combined filters."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()

        times = [
            datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        ]

        await store.store_event(Event(type="message.received", timestamp=times[0]))
        await store.store_event(Event(type="message.sent", timestamp=times[1]))
        await store.store_event(Event(type="message.received", timestamp=times[2]))

        since = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        events = await store.get_events(
            event_type="message.received",
            since=since
        )

        assert len(events) == 1
        assert events[0].timestamp == times[2]


class TestEventStoreReplay:
    """Tests for replay_events() functionality."""

    @pytest.mark.asyncio
    async def test_replay_events_to_handler(self):
        """replay_events should send all events to handler."""
        from core.events.persistence import EventStore
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class CollectingHandler(EventHandler):
            def __init__(self):
                self.events: List[Event] = []

            async def handle(self, event: Event) -> None:
                self.events.append(event)

        store = EventStore()
        await store.store_event(Event(type="event.a"))
        await store.store_event(Event(type="event.b"))

        handler = CollectingHandler()
        replayed = await store.replay_events(handler)

        assert replayed == 2
        assert len(handler.events) == 2

    @pytest.mark.asyncio
    async def test_replay_events_with_filter(self):
        """replay_events should support filtering."""
        from core.events.persistence import EventStore
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class CollectingHandler(EventHandler):
            def __init__(self):
                self.events: List[Event] = []

            async def handle(self, event: Event) -> None:
                self.events.append(event)

        store = EventStore()
        await store.store_event(Event(type="event.a"))
        await store.store_event(Event(type="event.b"))
        await store.store_event(Event(type="event.a"))

        handler = CollectingHandler()
        replayed = await store.replay_events(handler, event_type="event.a")

        assert replayed == 2
        assert all(e.type == "event.a" for e in handler.events)

    @pytest.mark.asyncio
    async def test_replay_events_preserves_order(self):
        """replay_events should preserve chronological order."""
        from core.events.persistence import EventStore
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class CollectingHandler(EventHandler):
            def __init__(self):
                self.events: List[Event] = []

            async def handle(self, event: Event) -> None:
                self.events.append(event)

        store = EventStore()
        times = [
            datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        ]

        # Store out of order
        await store.store_event(Event(type="event.2", timestamp=times[1]))
        await store.store_event(Event(type="event.1", timestamp=times[0]))
        await store.store_event(Event(type="event.3", timestamp=times[2]))

        handler = CollectingHandler()
        await store.replay_events(handler)

        # Should be in chronological order
        event_types = [e.type for e in handler.events]
        assert event_types == ["event.1", "event.2", "event.3"]


class TestEventStorePersistence:
    """Tests for file-based persistence."""

    @pytest.mark.asyncio
    async def test_store_loads_from_file_on_init(self):
        """EventStore should load events from file on initialization."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.json"

            # Create and populate store
            store1 = EventStore(file_path=path)
            await store1.store_event(Event(type="persisted.event"))
            await store1.flush()

            # Create new store from same file
            store2 = EventStore(file_path=path)
            await store2.load()

            events = await store2.get_events()
            assert len(events) == 1
            assert events[0].type == "persisted.event"

    @pytest.mark.asyncio
    async def test_clear_events(self):
        """EventStore should support clearing all events."""
        from core.events.persistence import EventStore
        from core.events.types import Event

        store = EventStore()
        await store.store_event(Event(type="event.a"))
        await store.store_event(Event(type="event.b"))

        await store.clear()

        assert store.event_count == 0
        events = await store.get_events()
        assert len(events) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
