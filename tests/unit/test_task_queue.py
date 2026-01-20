"""
Tests for async task queue with long-running operations.

Tests cover:
- Basic queue operations
- Priority handling
- Retry logic
- Task callbacks (on_complete, on_error, on_progress)
- Task status tracking
- Progress reporting
- Long-running task integration
"""

import asyncio
import pytest
from datetime import datetime
from typing import List

from core.tasks import (
    TaskQueue,
    TaskStatus,
    TaskResult,
    task,
    get_task_queue,
    start_task_queue,
    stop_task_queue,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def queue():
    """Create a fresh task queue for each test."""
    q = TaskQueue(max_workers=3, max_queue_size=100)
    await q.start()
    yield q
    await q.stop(wait=True, timeout=5.0)


@pytest.fixture
def callback_tracker():
    """Track callback invocations."""
    return {
        "completed": [],
        "errors": [],
        "progress": [],
    }


# =============================================================================
# BASIC QUEUE OPERATIONS
# =============================================================================

@pytest.mark.asyncio
async def test_queue_start_stop():
    """Test queue lifecycle."""
    q = TaskQueue(max_workers=2)
    assert not q.is_running

    await q.start()
    assert q.is_running

    await q.stop()
    assert not q.is_running


@pytest.mark.asyncio
async def test_enqueue_simple_task(queue):
    """Test enqueuing and executing a simple task."""
    result_value = None

    async def simple_task():
        await asyncio.sleep(0.1)
        return "completed"

    task_id = await queue.enqueue(simple_task)
    assert task_id is not None

    result = await queue.get_result(task_id, timeout=5.0)
    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert result.result == "completed"


@pytest.mark.asyncio
async def test_enqueue_with_args_kwargs(queue):
    """Test task with arguments."""
    async def add_numbers(a: int, b: int, multiplier: int = 1):
        return (a + b) * multiplier

    task_id = await queue.enqueue(add_numbers, 5, 10, multiplier=2)
    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.COMPLETED
    assert result.result == 30  # (5 + 10) * 2


@pytest.mark.asyncio
async def test_sync_function_execution(queue):
    """Test that sync functions work in the queue."""
    def sync_task(x: int):
        return x * 2

    task_id = await queue.enqueue(sync_task, 21)
    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.COMPLETED
    assert result.result == 42


# =============================================================================
# PRIORITY HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_priority_ordering(queue):
    """Test that tasks execute in priority order."""
    execution_order = []

    async def tracking_task(name: str):
        execution_order.append(name)
        await asyncio.sleep(0.05)
        return name

    # Enqueue with different priorities (lower = higher priority)
    await queue.enqueue(tracking_task, "low", priority=10)
    await queue.enqueue(tracking_task, "high", priority=1)
    await queue.enqueue(tracking_task, "medium", priority=5)

    # Wait for all to complete
    await asyncio.sleep(0.5)

    # High priority should execute first
    assert execution_order[0] == "high"
    assert "medium" in execution_order
    assert "low" in execution_order


# =============================================================================
# RETRY LOGIC
# =============================================================================

@pytest.mark.asyncio
async def test_retry_on_failure(queue):
    """Test that failed tasks retry."""
    attempt_count = 0

    async def flaky_task():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ValueError("Not yet!")
        return "success"

    task_id = await queue.enqueue(
        flaky_task,
        max_retries=3,
        retry_delay=0.1
    )

    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.COMPLETED
    assert result.attempts == 3
    assert result.result == "success"


@pytest.mark.asyncio
async def test_permanent_failure(queue):
    """Test task that fails all retries."""
    async def always_fails():
        raise RuntimeError("Always fails")

    task_id = await queue.enqueue(
        always_fails,
        max_retries=2,
        retry_delay=0.1
    )

    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.FAILED
    assert "Always fails" in result.error
    assert result.attempts == 2


# =============================================================================
# CALLBACKS
# =============================================================================

@pytest.mark.asyncio
async def test_on_complete_callback(queue, callback_tracker):
    """Test completion callback is invoked."""
    def on_complete(result):
        callback_tracker["completed"].append(result)

    async def success_task():
        return "done"

    task_id = await queue.enqueue(
        success_task,
        on_complete=on_complete
    )

    await queue.get_result(task_id, timeout=5.0)
    await asyncio.sleep(0.1)  # Give callback time

    assert len(callback_tracker["completed"]) == 1
    assert callback_tracker["completed"][0] == "done"


@pytest.mark.asyncio
async def test_on_error_callback(queue, callback_tracker):
    """Test error callback is invoked on permanent failure."""
    def on_error(exc):
        callback_tracker["errors"].append(str(exc))

    async def failing_task():
        raise ValueError("Test error")

    task_id = await queue.enqueue(
        failing_task,
        max_retries=1,
        retry_delay=0.1,
        on_error=on_error
    )

    await queue.get_result(task_id, timeout=5.0)
    await asyncio.sleep(0.1)

    assert len(callback_tracker["errors"]) == 1
    assert "Test error" in callback_tracker["errors"][0]


@pytest.mark.asyncio
async def test_on_progress_callback(queue, callback_tracker):
    """Test progress callback tracking."""
    def on_progress(progress: float, message: str):
        callback_tracker["progress"].append((progress, message))

    async def progressive_task(progress_callback):
        progress_callback(0.25, "Quarter done")
        await asyncio.sleep(0.05)
        progress_callback(0.50, "Half done")
        await asyncio.sleep(0.05)
        progress_callback(0.75, "Almost done")
        await asyncio.sleep(0.05)
        return "finished"

    task_id = await queue.enqueue(
        progressive_task,
        on_progress=on_progress
    )

    result = await queue.get_result(task_id, timeout=5.0)
    await asyncio.sleep(0.1)

    assert result.status == TaskStatus.COMPLETED
    assert len(callback_tracker["progress"]) >= 3
    assert callback_tracker["progress"][0] == (0.25, "Quarter done")


@pytest.mark.asyncio
async def test_async_callbacks(queue, callback_tracker):
    """Test async callbacks work correctly."""
    async def async_on_complete(result):
        await asyncio.sleep(0.05)
        callback_tracker["completed"].append(result)

    async def simple_task():
        return "test"

    task_id = await queue.enqueue(
        simple_task,
        on_complete=async_on_complete
    )

    await queue.get_result(task_id, timeout=5.0)
    await asyncio.sleep(0.2)

    assert len(callback_tracker["completed"]) == 1


# =============================================================================
# TASK STATUS & PROGRESS TRACKING
# =============================================================================

@pytest.mark.asyncio
async def test_task_status_lifecycle(queue):
    """Test task progresses through status lifecycle."""
    async def slow_task():
        await asyncio.sleep(0.2)
        return "done"

    task_id = await queue.enqueue(slow_task)

    # Initially pending
    status = queue.get_status(task_id)
    assert status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    # Should eventually complete
    result = await queue.get_result(task_id, timeout=5.0)
    assert result.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_get_progress(queue):
    """Test progress tracking."""
    async def task_with_progress(progress_callback):
        progress_callback(0.5, "Halfway")
        await asyncio.sleep(0.1)
        return "done"

    task_id = await queue.enqueue(task_with_progress)

    # Wait a bit for task to start
    await asyncio.sleep(0.05)

    progress = queue.get_progress(task_id)
    assert progress is not None
    assert "progress" in progress
    assert "task_id" in progress


@pytest.mark.asyncio
async def test_task_result_metadata(queue):
    """Test that task metadata is tracked."""
    async def test_task():
        return "result"

    task_id = await queue.enqueue(
        test_task,
        task_type="test_type"
    )

    result = await queue.get_result(task_id, timeout=5.0)
    assert result.task_type == "test_type"
    assert result.started_at is not None
    assert result.completed_at is not None
    assert result.duration_ms is not None


# =============================================================================
# TASK TYPES & FILTERING
# =============================================================================

@pytest.mark.asyncio
async def test_get_tasks_by_type(queue):
    """Test filtering tasks by type."""
    async def dummy_task():
        return "done"

    # Enqueue tasks of different types
    await queue.enqueue(dummy_task, task_type="report")
    await queue.enqueue(dummy_task, task_type="report")
    await queue.enqueue(dummy_task, task_type="analysis")

    await asyncio.sleep(0.3)

    report_tasks = queue.get_tasks_by_type("report")
    analysis_tasks = queue.get_tasks_by_type("analysis")

    assert len(report_tasks) == 2
    assert len(analysis_tasks) == 1


@pytest.mark.asyncio
async def test_get_running_tasks_by_type(queue):
    """Test getting running tasks by type."""
    async def slow_task():
        await asyncio.sleep(1.0)
        return "done"

    task_id = await queue.enqueue(slow_task, task_type="slow")
    await asyncio.sleep(0.1)  # Let it start

    running = queue.get_running_tasks_by_type("slow")
    assert len(running) >= 1


# =============================================================================
# TIMEOUT HANDLING
# =============================================================================

@pytest.mark.asyncio
async def test_task_timeout(queue):
    """Test task timeout."""
    async def slow_task():
        await asyncio.sleep(10.0)
        return "never"

    task_id = await queue.enqueue(slow_task, timeout=0.2)
    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.FAILED
    assert "timed out" in result.error.lower()


# =============================================================================
# SCHEDULED TASKS
# =============================================================================

@pytest.mark.asyncio
async def test_scheduled_task(queue):
    """Test task scheduled for future execution."""
    executed_at = None

    async def scheduled_task():
        nonlocal executed_at
        executed_at = asyncio.get_event_loop().time()
        return "scheduled"

    start_time = asyncio.get_event_loop().time()
    task_id = await queue.enqueue(scheduled_task, delay=0.3)

    result = await queue.get_result(task_id, timeout=5.0)

    assert result.status == TaskStatus.COMPLETED
    # Should have executed after delay
    assert executed_at - start_time >= 0.3


# =============================================================================
# TASK CANCELLATION
# =============================================================================

@pytest.mark.asyncio
async def test_cancel_pending_task(queue):
    """Test cancelling a pending task."""
    async def pending_task():
        await asyncio.sleep(5.0)
        return "never"

    task_id = await queue.enqueue(pending_task, priority=10)
    cancelled = await queue.cancel(task_id)

    assert cancelled
    status = queue.get_status(task_id)
    assert status == TaskStatus.CANCELLED


# =============================================================================
# QUEUE STATISTICS
# =============================================================================

@pytest.mark.asyncio
async def test_queue_stats(queue):
    """Test queue statistics."""
    async def quick_task():
        return "done"

    # Enqueue a few tasks
    await queue.enqueue(quick_task)
    await queue.enqueue(quick_task)
    await queue.enqueue(quick_task)

    await asyncio.sleep(0.2)

    stats = queue.get_stats()
    assert "enqueued" in stats
    assert "completed" in stats
    assert "max_workers" in stats
    assert stats["max_workers"] == 3


# =============================================================================
# DECORATOR USAGE
# =============================================================================

@pytest.mark.asyncio
async def test_task_decorator(queue):
    """Test using @task decorator."""
    @task(queue, retry=2)
    async def decorated_task(value: int):
        return value * 2

    # Use .delay() to enqueue
    task_id = await decorated_task.delay(value=21)
    result = await queue.get_result(task_id, timeout=5.0)

    assert result.result == 42


@pytest.mark.asyncio
async def test_task_decorator_schedule(queue):
    """Test scheduling with decorator."""
    @task(queue)
    async def scheduled_task(value: str):
        return value

    task_id = await scheduled_task.schedule(0.2, value="delayed")
    result = await queue.get_result(task_id, timeout=5.0)

    assert result.result == "delayed"


# =============================================================================
# CONCURRENCY & QUEUE SIZE
# =============================================================================

@pytest.mark.asyncio
async def test_max_workers_limit():
    """Test that max_workers limits concurrency."""
    q = TaskQueue(max_workers=2)
    await q.start()

    concurrent_count = 0
    max_concurrent = 0

    async def concurrent_task():
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.2)
        concurrent_count -= 1
        return "done"

    # Enqueue 10 tasks
    for _ in range(10):
        await q.enqueue(concurrent_task)

    await asyncio.sleep(1.5)
    await q.stop()

    # Should never exceed max_workers
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_queue_size_limit():
    """Test that queue respects max_queue_size."""
    q = TaskQueue(max_workers=1, max_queue_size=5)
    await q.start()

    async def dummy_task():
        await asyncio.sleep(10.0)

    # Fill the queue
    for _ in range(5):
        await q.enqueue(dummy_task)

    # Next enqueue should fail
    with pytest.raises(RuntimeError, match="queue is full"):
        await q.enqueue(dummy_task)

    await q.stop(wait=False)


# =============================================================================
# GLOBAL QUEUE INSTANCE
# =============================================================================

@pytest.mark.asyncio
async def test_global_queue():
    """Test global queue instance."""
    await start_task_queue()

    q = get_task_queue()
    assert q is not None
    assert q.is_running

    async def test_task():
        return "global"

    task_id = await q.enqueue(test_task)
    result = await q.get_result(task_id, timeout=5.0)

    assert result.result == "global"

    await stop_task_queue()


# =============================================================================
# LONG-RUNNING TASK INTEGRATION
# =============================================================================

@pytest.mark.asyncio
async def test_long_running_task_with_progress(queue):
    """Test a realistic long-running task with progress updates."""
    progress_updates = []

    def track_progress(p: float, msg: str):
        progress_updates.append((p, msg))

    async def long_running_analysis(progress_callback):
        """Simulate a long analysis task."""
        steps = ["Loading data", "Processing", "Analyzing", "Finalizing"]
        for i, step in enumerate(steps):
            progress = (i + 1) / len(steps)
            progress_callback(progress, step)
            await asyncio.sleep(0.05)
        return {"status": "complete", "items_processed": 100}

    task_id = await queue.enqueue(
        long_running_analysis,
        task_type="analysis",
        timeout=5.0,
        on_progress=track_progress
    )

    result = await queue.get_result(task_id, timeout=10.0)

    assert result.status == TaskStatus.COMPLETED
    assert result.result["status"] == "complete"
    assert len(progress_updates) == 4
    assert progress_updates[-1][0] == 1.0  # Final progress


@pytest.mark.asyncio
async def test_batch_operation(queue):
    """Test batch operation pattern."""
    results = []

    def on_complete(result):
        results.append(result)

    async def process_item(item_id: int):
        await asyncio.sleep(0.05)
        return f"processed_{item_id}"

    # Queue multiple items
    task_ids = []
    for i in range(5):
        task_id = await queue.enqueue(
            process_item,
            item_id=i,
            task_type="batch_item",
            on_complete=on_complete
        )
        task_ids.append(task_id)

    # Wait for all
    for task_id in task_ids:
        await queue.get_result(task_id, timeout=5.0)

    await asyncio.sleep(0.2)

    assert len(results) == 5
    assert all("processed_" in r for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
