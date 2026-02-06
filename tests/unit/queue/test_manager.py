"""
Tests for QueueManager.

TDD: These tests define the expected behavior BEFORE implementation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

# Import will fail until implementation exists - that's expected in TDD
try:
    from core.queue.manager import QueueManager, Message
    from core.queue.storage import InMemoryQueue, QueueStorage
except ImportError:
    # Define stubs for test discovery
    from dataclasses import dataclass

    @dataclass
    class Message:
        id: str
        queue_name: str
        payload: dict
        priority: int = 0
        created_at: Optional[str] = None
        attempts: int = 0

    class QueueStorage:
        pass

    class InMemoryQueue(QueueStorage):
        pass

    class QueueManager:
        pass


class TestQueueManager:
    """Tests for QueueManager class."""

    @pytest.fixture
    def manager(self):
        """Create a queue manager with in-memory storage."""
        return QueueManager()

    @pytest.mark.asyncio
    async def test_enqueue_creates_message(self, manager):
        """Enqueue should create and store a message."""
        msg_id = await manager.enqueue("tasks", {"action": "test"})

        assert msg_id is not None
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, manager):
        """Enqueue should support priority parameter."""
        msg_id = await manager.enqueue("urgent", {"data": 1}, priority=10)
        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_dequeue_returns_message(self, manager):
        """Dequeue should return the next message."""
        await manager.enqueue("tasks", {"action": "process"})
        msg = await manager.dequeue("tasks")

        assert msg is not None
        assert msg.payload == {"action": "process"}

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self, manager):
        """Dequeue from empty queue should return None."""
        msg = await manager.dequeue("empty")
        assert msg is None

    @pytest.mark.asyncio
    async def test_peek_returns_without_removing(self, manager):
        """Peek should return message without removing it."""
        await manager.enqueue("tasks", {"x": 1})

        msg1 = await manager.peek("tasks")
        msg2 = await manager.peek("tasks")

        assert msg1 is not None
        assert msg2 is not None
        assert msg1.id == msg2.id

    @pytest.mark.asyncio
    async def test_peek_empty_returns_none(self, manager):
        """Peek from empty queue should return None."""
        msg = await manager.peek("empty")
        assert msg is None

    @pytest.mark.asyncio
    async def test_get_queue_length(self, manager):
        """Should return correct queue length."""
        assert await manager.get_queue_length("tasks") == 0

        await manager.enqueue("tasks", {"x": 1})
        assert await manager.get_queue_length("tasks") == 1

        await manager.enqueue("tasks", {"x": 2})
        assert await manager.get_queue_length("tasks") == 2

    @pytest.mark.asyncio
    async def test_clear_queue(self, manager):
        """Should clear all messages from queue."""
        await manager.enqueue("tasks", {"x": 1})
        await manager.enqueue("tasks", {"x": 2})

        await manager.clear_queue("tasks")

        assert await manager.get_queue_length("tasks") == 0

    @pytest.mark.asyncio
    async def test_multiple_queues(self, manager):
        """Manager should support multiple named queues."""
        await manager.enqueue("queue_a", {"q": "a"})
        await manager.enqueue("queue_b", {"q": "b"})

        msg_a = await manager.dequeue("queue_a")
        msg_b = await manager.dequeue("queue_b")

        assert msg_a.payload == {"q": "a"}
        assert msg_b.payload == {"q": "b"}

    @pytest.mark.asyncio
    async def test_message_has_timestamp(self, manager):
        """Messages should have creation timestamp."""
        await manager.enqueue("tasks", {"data": 123})
        msg = await manager.dequeue("tasks")

        assert msg.created_at is not None

    @pytest.mark.asyncio
    async def test_message_id_unique(self, manager):
        """Message IDs should be unique."""
        ids = []
        for i in range(100):
            msg_id = await manager.enqueue("tasks", {"i": i})
            ids.append(msg_id)

        # All IDs should be unique
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_custom_storage_backend(self):
        """Manager should accept custom storage backend."""
        mock_storage = AsyncMock()
        mock_storage.push = AsyncMock()
        mock_storage.pop = AsyncMock(return_value=None)
        mock_storage.peek = AsyncMock(return_value=None)
        mock_storage.length = AsyncMock(return_value=0)
        mock_storage.clear = AsyncMock()

        manager = QueueManager(storage=mock_storage)

        await manager.enqueue("test", {"data": 1})
        mock_storage.push.assert_called_once()


class TestQueueManagerStats:
    """Tests for QueueManager statistics."""

    @pytest.fixture
    def manager(self):
        return QueueManager()

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """Should return queue statistics."""
        await manager.enqueue("tasks", {"x": 1})
        await manager.enqueue("tasks", {"x": 2})
        await manager.dequeue("tasks")

        stats = await manager.get_stats()

        assert "total_enqueued" in stats
        assert "total_dequeued" in stats
        assert "queues" in stats

    @pytest.mark.asyncio
    async def test_stats_track_operations(self, manager):
        """Stats should track enqueue and dequeue counts."""
        await manager.enqueue("q1", {"x": 1})
        await manager.enqueue("q1", {"x": 2})
        await manager.enqueue("q2", {"y": 1})
        await manager.dequeue("q1")

        stats = await manager.get_stats()

        assert stats["total_enqueued"] == 3
        assert stats["total_dequeued"] == 1


class TestQueueManagerErrors:
    """Tests for error handling."""

    @pytest.fixture
    def manager(self):
        return QueueManager()

    @pytest.mark.asyncio
    async def test_invalid_queue_name(self, manager):
        """Should handle empty queue name gracefully."""
        with pytest.raises(ValueError):
            await manager.enqueue("", {"data": 1})

    @pytest.mark.asyncio
    async def test_none_payload(self, manager):
        """Should handle None payload gracefully."""
        # Should either work or raise clear error
        try:
            await manager.enqueue("test", None)
        except (ValueError, TypeError):
            pass  # Acceptable to reject None

    @pytest.mark.asyncio
    async def test_large_payload(self, manager):
        """Should handle large payloads."""
        large_data = {"data": "x" * 100000}  # 100KB of data
        msg_id = await manager.enqueue("test", large_data)
        msg = await manager.dequeue("test")

        assert msg.payload == large_data
