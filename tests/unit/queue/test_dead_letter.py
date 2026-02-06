"""
Tests for DeadLetterQueue.

TDD: These tests define the expected behavior BEFORE implementation.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

# Import will fail until implementation exists - that's expected in TDD
try:
    from core.queue.dead_letter import DeadLetterQueue, FailedMessage
    from core.queue.storage import Message
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

    @dataclass
    class FailedMessage:
        message: Message
        error: str
        failed_at: str
        retry_count: int = 0
        original_queue: str = ""

    class DeadLetterQueue:
        pass


class TestDeadLetterQueueBasics:
    """Basic DLQ operations."""

    @pytest.fixture
    def dlq(self):
        """Create a dead letter queue."""
        return DeadLetterQueue()

    @pytest.mark.asyncio
    async def test_move_to_dlq(self, dlq):
        """Should move failed message to DLQ."""
        msg = Message(id="fail-1", queue_name="tasks", payload={"data": 123})
        error = "Processing failed: timeout"

        await dlq.move_to_dlq(msg, error)

        items = await dlq.list_dlq()
        assert len(items) == 1
        assert items[0].message.id == "fail-1"
        assert items[0].error == "Processing failed: timeout"

    @pytest.mark.asyncio
    async def test_failed_message_has_timestamp(self, dlq):
        """Failed message should have timestamp."""
        msg = Message(id="fail-2", queue_name="tasks", payload={})
        await dlq.move_to_dlq(msg, "Error")

        items = await dlq.list_dlq()
        assert items[0].failed_at is not None

    @pytest.mark.asyncio
    async def test_failed_message_tracks_original_queue(self, dlq):
        """Failed message should track original queue."""
        msg = Message(id="fail-3", queue_name="priority_tasks", payload={})
        await dlq.move_to_dlq(msg, "Error")

        items = await dlq.list_dlq()
        assert items[0].original_queue == "priority_tasks"

    @pytest.mark.asyncio
    async def test_list_dlq_empty(self, dlq):
        """Empty DLQ should return empty list."""
        items = await dlq.list_dlq()
        assert items == []


class TestDeadLetterRetry:
    """Tests for retrying failed messages."""

    @pytest.fixture
    def dlq(self):
        return DeadLetterQueue()

    @pytest.mark.asyncio
    async def test_retry_from_dlq(self, dlq):
        """Should return message for retry."""
        msg = Message(id="retry-1", queue_name="tasks", payload={"x": 1})
        await dlq.move_to_dlq(msg, "Temporary error")

        retried = await dlq.retry_from_dlq("retry-1")

        assert retried is not None
        assert retried.id == "retry-1"
        assert retried.payload == {"x": 1}

    @pytest.mark.asyncio
    async def test_retry_removes_from_dlq(self, dlq):
        """Retried message should be removed from DLQ."""
        msg = Message(id="retry-2", queue_name="tasks", payload={})
        await dlq.move_to_dlq(msg, "Error")

        await dlq.retry_from_dlq("retry-2")

        items = await dlq.list_dlq()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_retry_nonexistent_returns_none(self, dlq):
        """Retrying non-existent message should return None."""
        result = await dlq.retry_from_dlq("does-not-exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_increments_count(self, dlq):
        """Retry count should be tracked."""
        msg = Message(id="retry-3", queue_name="tasks", payload={})
        await dlq.move_to_dlq(msg, "Error 1")

        retried = await dlq.retry_from_dlq("retry-3")

        # Retry count should be incremented
        assert retried.attempts >= 1


class TestDeadLetterFiltering:
    """Tests for filtering DLQ entries."""

    @pytest.fixture
    def dlq(self):
        return DeadLetterQueue()

    @pytest.mark.asyncio
    async def test_list_by_queue(self, dlq):
        """Should filter DLQ entries by original queue."""
        msg1 = Message(id="q1-1", queue_name="queue_a", payload={})
        msg2 = Message(id="q2-1", queue_name="queue_b", payload={})
        msg3 = Message(id="q1-2", queue_name="queue_a", payload={})

        await dlq.move_to_dlq(msg1, "Error")
        await dlq.move_to_dlq(msg2, "Error")
        await dlq.move_to_dlq(msg3, "Error")

        items = await dlq.list_dlq(queue_name="queue_a")
        assert len(items) == 2
        assert all(i.original_queue == "queue_a" for i in items)

    @pytest.mark.asyncio
    async def test_list_limit(self, dlq):
        """Should support limiting results."""
        for i in range(10):
            msg = Message(id=f"limit-{i}", queue_name="tasks", payload={})
            await dlq.move_to_dlq(msg, "Error")

        items = await dlq.list_dlq(limit=5)
        assert len(items) == 5


class TestDeadLetterCleanup:
    """Tests for DLQ cleanup and maintenance."""

    @pytest.fixture
    def dlq(self):
        return DeadLetterQueue()

    @pytest.mark.asyncio
    async def test_clear_dlq(self, dlq):
        """Should clear all DLQ entries."""
        for i in range(5):
            msg = Message(id=f"clear-{i}", queue_name="tasks", payload={})
            await dlq.move_to_dlq(msg, "Error")

        await dlq.clear()

        items = await dlq.list_dlq()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_delete_specific_entry(self, dlq):
        """Should delete specific DLQ entry."""
        msg1 = Message(id="del-1", queue_name="tasks", payload={})
        msg2 = Message(id="del-2", queue_name="tasks", payload={})

        await dlq.move_to_dlq(msg1, "Error")
        await dlq.move_to_dlq(msg2, "Error")

        await dlq.delete("del-1")

        items = await dlq.list_dlq()
        assert len(items) == 1
        assert items[0].message.id == "del-2"

    @pytest.mark.asyncio
    async def test_get_dlq_size(self, dlq):
        """Should return DLQ size."""
        assert await dlq.size() == 0

        for i in range(3):
            msg = Message(id=f"size-{i}", queue_name="tasks", payload={})
            await dlq.move_to_dlq(msg, "Error")

        assert await dlq.size() == 3


class TestDeadLetterStats:
    """Tests for DLQ statistics."""

    @pytest.fixture
    def dlq(self):
        return DeadLetterQueue()

    @pytest.mark.asyncio
    async def test_get_stats(self, dlq):
        """Should return DLQ statistics."""
        msg1 = Message(id="stat-1", queue_name="queue_a", payload={})
        msg2 = Message(id="stat-2", queue_name="queue_b", payload={})
        msg3 = Message(id="stat-3", queue_name="queue_a", payload={})

        await dlq.move_to_dlq(msg1, "Error type 1")
        await dlq.move_to_dlq(msg2, "Error type 2")
        await dlq.move_to_dlq(msg3, "Error type 1")

        stats = await dlq.get_stats()

        assert "total_failed" in stats
        assert "by_queue" in stats
        assert stats["total_failed"] == 3

    @pytest.mark.asyncio
    async def test_stats_by_queue(self, dlq):
        """Should track failures by queue."""
        for i in range(3):
            msg = Message(id=f"qa-{i}", queue_name="queue_a", payload={})
            await dlq.move_to_dlq(msg, "Error")

        for i in range(2):
            msg = Message(id=f"qb-{i}", queue_name="queue_b", payload={})
            await dlq.move_to_dlq(msg, "Error")

        stats = await dlq.get_stats()

        assert stats["by_queue"]["queue_a"] == 3
        assert stats["by_queue"]["queue_b"] == 2


class TestDeadLetterRetention:
    """Tests for DLQ retention policies."""

    @pytest.mark.asyncio
    async def test_max_retention(self):
        """DLQ should respect max retention limit."""
        dlq = DeadLetterQueue(max_size=5)

        for i in range(10):
            msg = Message(id=f"ret-{i}", queue_name="tasks", payload={})
            await dlq.move_to_dlq(msg, "Error")

        items = await dlq.list_dlq()
        assert len(items) <= 5

    @pytest.mark.asyncio
    async def test_oldest_removed_when_full(self):
        """Oldest entries should be removed when DLQ is full."""
        dlq = DeadLetterQueue(max_size=3)

        for i in range(5):
            msg = Message(id=f"old-{i}", queue_name="tasks", payload={})
            await dlq.move_to_dlq(msg, f"Error {i}")
            await asyncio.sleep(0.01)  # Ensure different timestamps

        items = await dlq.list_dlq()
        ids = [i.message.id for i in items]

        # Should have the newest 3
        assert "old-0" not in ids
        assert "old-1" not in ids
        assert "old-4" in ids
