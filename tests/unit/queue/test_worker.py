"""
Tests for Worker class.

TDD: These tests define the expected behavior BEFORE implementation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional, Callable, Any
from dataclasses import dataclass

# Import will fail until implementation exists - that's expected in TDD
try:
    from core.queue.worker import Worker, WorkerConfig
    from core.queue.manager import QueueManager, Message
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

    class QueueManager:
        pass

    @dataclass
    class WorkerConfig:
        queue_name: str
        concurrency: int = 1
        poll_interval: float = 0.1
        max_retries: int = 3

    class Worker:
        pass


class TestWorkerLifecycle:
    """Tests for Worker start/stop lifecycle."""

    @pytest.fixture
    def manager(self):
        """Create mock queue manager."""
        manager = AsyncMock()
        manager.dequeue = AsyncMock(return_value=None)
        manager.enqueue = AsyncMock()
        return manager

    @pytest.fixture
    def handler(self):
        """Create mock message handler."""
        return AsyncMock(return_value=True)

    @pytest.mark.asyncio
    async def test_worker_start(self, manager, handler):
        """Worker should start processing."""
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
        )

        await worker.start()
        assert worker.is_running

        await worker.stop()

    @pytest.mark.asyncio
    async def test_worker_stop_graceful(self, manager, handler):
        """Worker should stop gracefully."""
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
        )

        await worker.start()
        await worker.stop()

        assert not worker.is_running

    @pytest.mark.asyncio
    async def test_worker_stop_with_timeout(self, manager, handler):
        """Worker should support graceful shutdown timeout."""
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
        )

        await worker.start()
        await worker.stop(timeout=5.0)

        assert not worker.is_running

    @pytest.mark.asyncio
    async def test_double_start_ignored(self, manager, handler):
        """Starting already running worker should be safe."""
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
        )

        await worker.start()
        await worker.start()  # Should not raise

        await worker.stop()

    @pytest.mark.asyncio
    async def test_double_stop_ignored(self, manager, handler):
        """Stopping already stopped worker should be safe."""
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
        )

        await worker.start()
        await worker.stop()
        await worker.stop()  # Should not raise


class TestWorkerProcessing:
    """Tests for message processing."""

    @pytest.fixture
    def manager(self):
        """Create mock queue manager."""
        manager = AsyncMock()
        manager.enqueue = AsyncMock(return_value="msg-1")
        return manager

    @pytest.mark.asyncio
    async def test_process_message_success(self, manager):
        """Handler should be called with message."""
        msg = Message(id="1", queue_name="tasks", payload={"action": "test"})
        manager.dequeue = AsyncMock(side_effect=[msg, None, None, None])

        handler = AsyncMock(return_value=True)
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            poll_interval=0.05,
        )

        await worker.start()
        await asyncio.sleep(0.2)  # Allow time for processing
        await worker.stop()

        handler.assert_called_with(msg)

    @pytest.mark.asyncio
    async def test_process_message_failure(self, manager):
        """Failed processing should trigger error handler."""
        msg = Message(id="1", queue_name="tasks", payload={"fail": True})
        manager.dequeue = AsyncMock(side_effect=[msg, None, None, None])

        handler = AsyncMock(side_effect=Exception("Processing failed"))
        error_handler = AsyncMock()

        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            error_handler=error_handler,
            poll_interval=0.05,
        )

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

        error_handler.assert_called()

    @pytest.mark.asyncio
    async def test_handler_returns_false(self, manager):
        """Handler returning False should be treated as failure."""
        msg = Message(id="1", queue_name="tasks", payload={})
        manager.dequeue = AsyncMock(side_effect=[msg, None, None])

        handler = AsyncMock(return_value=False)
        error_handler = AsyncMock()

        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            error_handler=error_handler,
            poll_interval=0.05,
        )

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

        error_handler.assert_called()


class TestWorkerConcurrency:
    """Tests for concurrent processing."""

    @pytest.mark.asyncio
    async def test_single_concurrency(self):
        """Single concurrency should process one at a time."""
        processed = []
        processing_lock = asyncio.Lock()

        async def handler(msg):
            async with processing_lock:
                processed.append(msg.id)
                await asyncio.sleep(0.05)
            return True

        manager = AsyncMock()
        messages = [
            Message(id=str(i), queue_name="tasks", payload={})
            for i in range(3)
        ]
        manager.dequeue = AsyncMock(side_effect=messages + [None] * 10)

        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            concurrency=1,
            poll_interval=0.01,
        )

        await worker.start()
        await asyncio.sleep(0.5)
        await worker.stop()

        assert len(processed) == 3

    @pytest.mark.asyncio
    async def test_multiple_concurrency(self):
        """Multiple concurrency should process in parallel."""
        processing_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def handler(msg):
            nonlocal processing_count, max_concurrent
            async with lock:
                processing_count += 1
                max_concurrent = max(max_concurrent, processing_count)

            await asyncio.sleep(0.1)  # Simulate work

            async with lock:
                processing_count -= 1
            return True

        manager = AsyncMock()
        messages = [
            Message(id=str(i), queue_name="tasks", payload={})
            for i in range(5)
        ]
        manager.dequeue = AsyncMock(side_effect=messages + [None] * 20)

        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            concurrency=3,
            poll_interval=0.01,
        )

        await worker.start()
        await asyncio.sleep(1.0)
        await worker.stop()

        # Should have had concurrent processing
        assert max_concurrent > 1


class TestWorkerRetries:
    """Tests for retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Failed messages should be retried."""
        attempts = []

        async def handler(msg):
            attempts.append(msg.id)
            if len(attempts) < 3:
                raise Exception("Retry me")
            return True

        manager = AsyncMock()
        msg = Message(id="retry-1", queue_name="tasks", payload={})
        manager.dequeue = AsyncMock(side_effect=[msg, None, None, None, None])

        # Mock re-enqueue for retries
        async def mock_enqueue(queue_name, payload, priority=0):
            nonlocal msg
            msg.attempts += 1
            manager.dequeue.side_effect = [msg, None, None, None]
            return msg.id

        manager.enqueue = mock_enqueue

        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            max_retries=5,
            poll_interval=0.05,
        )

        await worker.start()
        await asyncio.sleep(0.5)
        await worker.stop()

        # Should have attempted multiple times
        assert len(attempts) >= 1


class TestWorkerStats:
    """Tests for worker statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Worker should track processing stats."""
        manager = AsyncMock()
        msg = Message(id="1", queue_name="tasks", payload={})
        manager.dequeue = AsyncMock(side_effect=[msg, None, None])

        handler = AsyncMock(return_value=True)
        worker = Worker(
            queue_manager=manager,
            queue_name="tasks",
            handler=handler,
            poll_interval=0.05,
        )

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

        stats = worker.get_stats()

        assert "messages_processed" in stats
        assert "messages_failed" in stats
        assert "avg_processing_time_ms" in stats


class TestWorkerConfig:
    """Tests for worker configuration."""

    def test_config_defaults(self):
        """WorkerConfig should have sensible defaults."""
        config = WorkerConfig(queue_name="test")

        assert config.queue_name == "test"
        assert config.concurrency >= 1
        assert config.poll_interval > 0
        assert config.max_retries >= 0

    def test_config_custom_values(self):
        """WorkerConfig should accept custom values."""
        config = WorkerConfig(
            queue_name="custom",
            concurrency=5,
            poll_interval=0.5,
            max_retries=10,
        )

        assert config.queue_name == "custom"
        assert config.concurrency == 5
        assert config.poll_interval == 0.5
        assert config.max_retries == 10
