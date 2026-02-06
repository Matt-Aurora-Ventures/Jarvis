"""
Tests for queue storage backends.

TDD: These tests define the expected behavior BEFORE implementation.
"""

import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


# Import will fail until implementation exists - that's expected in TDD
try:
    from core.queue.storage import (
        Message,
        InMemoryQueue,
        FileQueue,
        PriorityQueue,
        QueueStorage,
    )
except ImportError:
    # Define stubs for test discovery
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
    class FileQueue(QueueStorage):
        pass
    class PriorityQueue(QueueStorage):
        pass


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Message should have required fields."""
        msg = Message(
            id="msg-001",
            queue_name="test_queue",
            payload={"action": "process", "data": 123},
            priority=0,
        )
        assert msg.id == "msg-001"
        assert msg.queue_name == "test_queue"
        assert msg.payload == {"action": "process", "data": 123}
        assert msg.priority == 0
        assert msg.attempts == 0

    def test_message_with_priority(self):
        """Message should support priority levels."""
        msg = Message(
            id="msg-002",
            queue_name="urgent",
            payload={"urgent": True},
            priority=10,
        )
        assert msg.priority == 10

    def test_message_serialization(self):
        """Message should be JSON serializable."""
        msg = Message(
            id="msg-003",
            queue_name="test",
            payload={"key": "value"},
        )
        # Should be able to convert to dict and back
        msg_dict = {
            "id": msg.id,
            "queue_name": msg.queue_name,
            "payload": msg.payload,
            "priority": msg.priority,
            "created_at": msg.created_at,
            "attempts": msg.attempts,
        }
        json_str = json.dumps(msg_dict)
        assert json_str is not None


class TestInMemoryQueue:
    """Tests for InMemoryQueue - fast, non-persistent storage."""

    @pytest.fixture
    def queue(self):
        """Create a fresh in-memory queue."""
        return InMemoryQueue()

    @pytest.mark.asyncio
    async def test_push_and_pop(self, queue):
        """Should push and pop messages."""
        msg = Message(id="1", queue_name="test", payload={"x": 1})
        await queue.push("test", msg)
        result = await queue.pop("test")
        assert result is not None
        assert result.id == "1"
        assert result.payload == {"x": 1}

    @pytest.mark.asyncio
    async def test_pop_empty_queue(self, queue):
        """Pop from empty queue should return None."""
        result = await queue.pop("empty")
        assert result is None

    @pytest.mark.asyncio
    async def test_peek_does_not_remove(self, queue):
        """Peek should return message without removing it."""
        msg = Message(id="peek-1", queue_name="test", payload={})
        await queue.push("test", msg)

        peek1 = await queue.peek("test")
        peek2 = await queue.peek("test")

        assert peek1 is not None
        assert peek2 is not None
        assert peek1.id == peek2.id

    @pytest.mark.asyncio
    async def test_length(self, queue):
        """Should return correct queue length."""
        assert await queue.length("test") == 0

        await queue.push("test", Message(id="1", queue_name="test", payload={}))
        assert await queue.length("test") == 1

        await queue.push("test", Message(id="2", queue_name="test", payload={}))
        assert await queue.length("test") == 2

        await queue.pop("test")
        assert await queue.length("test") == 1

    @pytest.mark.asyncio
    async def test_clear(self, queue):
        """Should clear all messages from queue."""
        await queue.push("test", Message(id="1", queue_name="test", payload={}))
        await queue.push("test", Message(id="2", queue_name="test", payload={}))

        await queue.clear("test")

        assert await queue.length("test") == 0
        assert await queue.pop("test") is None

    @pytest.mark.asyncio
    async def test_multiple_queues_isolation(self, queue):
        """Messages in different queues should be isolated."""
        await queue.push("queue_a", Message(id="a1", queue_name="queue_a", payload={"q": "a"}))
        await queue.push("queue_b", Message(id="b1", queue_name="queue_b", payload={"q": "b"}))

        msg_a = await queue.pop("queue_a")
        msg_b = await queue.pop("queue_b")

        assert msg_a.id == "a1"
        assert msg_b.id == "b1"

    @pytest.mark.asyncio
    async def test_fifo_order(self, queue):
        """Should maintain FIFO order."""
        for i in range(5):
            await queue.push("test", Message(id=str(i), queue_name="test", payload={}))

        for i in range(5):
            msg = await queue.pop("test")
            assert msg.id == str(i)


class TestFileQueue:
    """Tests for FileQueue - persistent, JSON-based storage."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for queue files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def queue(self, temp_dir):
        """Create a file-based queue."""
        return FileQueue(storage_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_push_creates_file(self, queue, temp_dir):
        """Pushing message should create file on disk."""
        msg = Message(id="file-1", queue_name="test", payload={"data": 123})
        await queue.push("test", msg)

        # Check file exists
        queue_dir = Path(temp_dir) / "test"
        assert queue_dir.exists()
        files = list(queue_dir.glob("*.json"))
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_pop_removes_file(self, queue, temp_dir):
        """Popping message should remove file from disk."""
        msg = Message(id="file-2", queue_name="test", payload={})
        await queue.push("test", msg)

        await queue.pop("test")

        queue_dir = Path(temp_dir) / "test"
        files = list(queue_dir.glob("*.json"))
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, temp_dir):
        """Messages should persist when queue is recreated."""
        queue1 = FileQueue(storage_dir=temp_dir)
        await queue1.push("persist", Message(id="p1", queue_name="persist", payload={"saved": True}))

        # Create new queue instance pointing to same directory
        queue2 = FileQueue(storage_dir=temp_dir)
        msg = await queue2.pop("persist")

        assert msg is not None
        assert msg.id == "p1"
        assert msg.payload == {"saved": True}

    @pytest.mark.asyncio
    async def test_length(self, queue):
        """Should return correct queue length."""
        assert await queue.length("test") == 0

        await queue.push("test", Message(id="1", queue_name="test", payload={}))
        await queue.push("test", Message(id="2", queue_name="test", payload={}))

        assert await queue.length("test") == 2

    @pytest.mark.asyncio
    async def test_clear(self, queue, temp_dir):
        """Should clear all messages and files."""
        await queue.push("test", Message(id="1", queue_name="test", payload={}))
        await queue.push("test", Message(id="2", queue_name="test", payload={}))

        await queue.clear("test")

        assert await queue.length("test") == 0
        queue_dir = Path(temp_dir) / "test"
        if queue_dir.exists():
            files = list(queue_dir.glob("*.json"))
            assert len(files) == 0


class TestPriorityQueue:
    """Tests for PriorityQueue - processes by priority."""

    @pytest.fixture
    def queue(self):
        """Create a priority queue."""
        return PriorityQueue()

    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Higher priority (lower number) should be processed first."""
        await queue.push("test", Message(id="low", queue_name="test", payload={}, priority=10))
        await queue.push("test", Message(id="high", queue_name="test", payload={}, priority=1))
        await queue.push("test", Message(id="medium", queue_name="test", payload={}, priority=5))

        msg1 = await queue.pop("test")
        msg2 = await queue.pop("test")
        msg3 = await queue.pop("test")

        assert msg1.id == "high"    # priority 1
        assert msg2.id == "medium"  # priority 5
        assert msg3.id == "low"     # priority 10

    @pytest.mark.asyncio
    async def test_same_priority_fifo(self, queue):
        """Messages with same priority should be FIFO."""
        await queue.push("test", Message(id="first", queue_name="test", payload={}, priority=5))
        await queue.push("test", Message(id="second", queue_name="test", payload={}, priority=5))
        await queue.push("test", Message(id="third", queue_name="test", payload={}, priority=5))

        msg1 = await queue.pop("test")
        msg2 = await queue.pop("test")
        msg3 = await queue.pop("test")

        assert msg1.id == "first"
        assert msg2.id == "second"
        assert msg3.id == "third"

    @pytest.mark.asyncio
    async def test_peek_returns_highest_priority(self, queue):
        """Peek should return highest priority message."""
        await queue.push("test", Message(id="low", queue_name="test", payload={}, priority=10))
        await queue.push("test", Message(id="high", queue_name="test", payload={}, priority=1))

        msg = await queue.peek("test")
        assert msg.id == "high"

    @pytest.mark.asyncio
    async def test_length(self, queue):
        """Length should work correctly."""
        await queue.push("test", Message(id="1", queue_name="test", payload={}, priority=1))
        await queue.push("test", Message(id="2", queue_name="test", payload={}, priority=2))

        assert await queue.length("test") == 2

    @pytest.mark.asyncio
    async def test_clear(self, queue):
        """Clear should remove all messages."""
        await queue.push("test", Message(id="1", queue_name="test", payload={}, priority=1))
        await queue.push("test", Message(id="2", queue_name="test", payload={}, priority=2))

        await queue.clear("test")

        assert await queue.length("test") == 0


class TestQueueStorageInterface:
    """Test that all backends implement the same interface."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("queue_class", [InMemoryQueue, PriorityQueue])
    async def test_interface_methods(self, queue_class):
        """All queue classes should have required methods."""
        queue = queue_class()

        # Should have all required methods
        assert hasattr(queue, 'push')
        assert hasattr(queue, 'pop')
        assert hasattr(queue, 'peek')
        assert hasattr(queue, 'length')
        assert hasattr(queue, 'clear')

        # Methods should be callable
        assert callable(queue.push)
        assert callable(queue.pop)
        assert callable(queue.peek)
        assert callable(queue.length)
        assert callable(queue.clear)
