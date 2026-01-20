"""
Comprehensive Tests for Async Task Management

Tests cover core/async_utils.py:
1. TaskTracker - tracked task management
2. RateLimiter - async rate limiting
3. Throttle decorator
4. gather_with_concurrency - concurrent execution with limits
5. retry_async - async retry with backoff
6. timeout_context - async timeout handling
7. fire_and_forget - background task execution

Acceptance Criteria:
- Tasks execute in correct order
- Concurrent task limits are respected
- Task cancellation works properly
- Task timeouts are enforced
- Task results are properly collected
- Error handling in tasks is correct
"""

import asyncio
import logging
import pytest
import time
from datetime import datetime
from typing import List, Any
from unittest.mock import MagicMock, AsyncMock, patch

from core.async_utils import (
    TaskTracker,
    TaskInfo,
    create_tracked_task,
    fire_and_forget,
    RateLimiter,
    Throttle,
    retry_async,
    timeout_context,
    gather_with_concurrency,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def tracker():
    """Create a fresh TaskTracker for each test."""
    return TaskTracker("test_component")


@pytest.fixture
def execution_log():
    """Track execution order and state."""
    return {
        "order": [],
        "timestamps": [],
        "errors": [],
        "results": [],
    }


# =============================================================================
# TASK TRACKER: BASIC OPERATIONS
# =============================================================================

class TestTaskTrackerBasic:
    """Test TaskTracker basic functionality."""

    @pytest.mark.asyncio
    async def test_create_task_returns_asyncio_task(self, tracker):
        """Test that create_task returns a valid asyncio.Task."""
        async def simple_coro():
            return "done"

        task = tracker.create_task(simple_coro(), name="test_task")

        assert isinstance(task, asyncio.Task)
        result = await task
        assert result == "done"

    @pytest.mark.asyncio
    async def test_task_naming_convention(self, tracker):
        """Test task names follow component.task_name pattern."""
        async def dummy():
            return True

        task = tracker.create_task(dummy(), name="my_task")

        assert task.get_name() == "test_component.my_task"

    @pytest.mark.asyncio
    async def test_auto_generated_task_name(self, tracker):
        """Test auto-generated task names when not specified."""
        async def dummy():
            return True

        task1 = tracker.create_task(dummy())
        task2 = tracker.create_task(dummy())

        # Names should increment
        assert "task_1" in task1.get_name()
        assert "task_2" in task2.get_name()

        await task1
        await task2

    @pytest.mark.asyncio
    async def test_task_info_tracking(self, tracker):
        """Test TaskInfo is properly populated."""
        async def slow_task():
            await asyncio.sleep(0.1)
            return "result"

        task = tracker.create_task(slow_task(), name="tracked")

        # Check task is tracked
        running = tracker.get_running_tasks()
        assert len(running) == 1
        assert running[0].name == "test_component.tracked"
        assert running[0].created_at is not None
        assert running[0].completed_at is None

        await task

        # After completion, cleanup removes it
        tracker._cleanup_completed()
        running = tracker.get_running_tasks()
        assert len(running) == 0


# =============================================================================
# TASK TRACKER: EXECUTION ORDER
# =============================================================================

class TestTaskExecutionOrder:
    """Test tasks execute in correct order."""

    @pytest.mark.asyncio
    async def test_sequential_execution_preserves_order(self, tracker, execution_log):
        """Test sequential tasks execute in order."""
        async def ordered_task(name: str, delay: float = 0.01):
            await asyncio.sleep(delay)
            execution_log["order"].append(name)
            return name

        # Create tasks sequentially and await each
        for i in range(5):
            task = tracker.create_task(ordered_task(f"task_{i}"))
            await task

        assert execution_log["order"] == ["task_0", "task_1", "task_2", "task_3", "task_4"]

    @pytest.mark.asyncio
    async def test_concurrent_tasks_all_execute(self, tracker, execution_log):
        """Test concurrent tasks all complete (order may vary)."""
        async def concurrent_task(name: str):
            await asyncio.sleep(0.05)
            execution_log["order"].append(name)
            return name

        tasks = [
            tracker.create_task(concurrent_task(f"task_{i}"))
            for i in range(5)
        ]

        await asyncio.gather(*tasks)

        # All tasks should complete
        assert len(execution_log["order"]) == 5
        assert set(execution_log["order"]) == {"task_0", "task_1", "task_2", "task_3", "task_4"}


# =============================================================================
# TASK TRACKER: ERROR HANDLING
# =============================================================================

class TestTaskTrackerErrors:
    """Test error handling in TaskTracker."""

    @pytest.mark.asyncio
    async def test_task_error_is_logged(self, tracker):
        """Test that task errors are logged and tracked."""
        async def failing_task():
            raise ValueError("Test error")

        task = tracker.create_task(failing_task(), name="failing")

        # Wait for task to complete (with error)
        with pytest.raises(ValueError):
            await task

        # Error should be tracked
        failed = tracker.get_failed_tasks()
        assert len(failed) == 1
        assert "ValueError" in failed[0].error
        assert "Test error" in failed[0].error

    @pytest.mark.asyncio
    async def test_on_error_callback_invoked(self, tracker, execution_log):
        """Test on_error callback is called when task fails."""
        def error_handler(exc: Exception):
            execution_log["errors"].append(str(exc))

        async def failing_task():
            raise RuntimeError("Failure!")

        task = tracker.create_task(
            failing_task(),
            name="failing",
            on_error=error_handler
        )

        try:
            await task
        except RuntimeError:
            pass

        # Give callback time to execute
        await asyncio.sleep(0.05)

        assert len(execution_log["errors"]) == 1
        assert "Failure!" in execution_log["errors"][0]

    @pytest.mark.asyncio
    async def test_on_complete_callback_invoked(self, tracker, execution_log):
        """Test on_complete callback is called on success."""
        def complete_handler(result: Any):
            execution_log["results"].append(result)

        async def success_task():
            return {"status": "ok", "value": 42}

        task = tracker.create_task(
            success_task(),
            name="success",
            on_complete=complete_handler
        )

        await task
        await asyncio.sleep(0.05)

        assert len(execution_log["results"]) == 1
        assert execution_log["results"][0] == {"status": "ok", "value": 42}

    @pytest.mark.asyncio
    async def test_callback_error_does_not_propagate(self, tracker):
        """Test that callback errors don't crash the task system."""
        def bad_callback(result):
            raise Exception("Callback crashed!")

        async def task_with_bad_callback():
            return "success"

        task = tracker.create_task(
            task_with_bad_callback(),
            name="test",
            on_complete=bad_callback
        )

        # Should not raise, even though callback fails
        result = await task
        assert result == "success"

    @pytest.mark.asyncio
    async def test_stats_track_success_and_failure(self, tracker):
        """Test statistics track successes and failures."""
        async def success():
            return True

        async def failure():
            raise Exception("fail")

        # Create success tasks
        t1 = tracker.create_task(success())
        t2 = tracker.create_task(success())
        await t1
        await t2

        # Create failure task
        t3 = tracker.create_task(failure())
        try:
            await t3
        except Exception:
            pass

        stats = tracker.get_stats()
        assert stats["total_created"] == 3
        assert stats["total_succeeded"] == 2
        assert stats["total_failed"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.1)


# =============================================================================
# TASK TRACKER: CANCELLATION
# =============================================================================

class TestTaskCancellation:
    """Test task cancellation functionality."""

    @pytest.mark.asyncio
    async def test_cancel_all_running_tasks(self, tracker):
        """Test cancel_all cancels all running tasks."""
        cancel_detected = []

        async def long_running_task(name: str):
            try:
                await asyncio.sleep(10.0)
                return name
            except asyncio.CancelledError:
                cancel_detected.append(name)
                raise

        # Start several tasks
        tasks = [
            tracker.create_task(long_running_task(f"task_{i}"))
            for i in range(3)
        ]

        # Give them time to start
        await asyncio.sleep(0.1)

        # Cancel all
        cancelled_count = await tracker.cancel_all(timeout=2.0)

        assert cancelled_count == 3
        assert len(cancel_detected) == 3

    @pytest.mark.asyncio
    async def test_cancel_respects_timeout(self, tracker):
        """Test cancel_all respects timeout for stubborn tasks."""
        async def stubborn_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                # Ignore cancellation (bad practice, but test it)
                await asyncio.sleep(100)

        task = tracker.create_task(stubborn_task())
        await asyncio.sleep(0.1)

        start = time.time()
        await tracker.cancel_all(timeout=0.5)
        elapsed = time.time() - start

        # Should timeout around 0.5s, not wait forever
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_individual_task_cancellation(self, tracker):
        """Test cancelling individual tasks."""
        execution_log = []

        async def cancellable_task(name: str):
            try:
                await asyncio.sleep(10)
                execution_log.append(f"{name}_completed")
            except asyncio.CancelledError:
                execution_log.append(f"{name}_cancelled")
                raise

        task = tracker.create_task(cancellable_task("test"))
        await asyncio.sleep(0.1)

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        assert "test_cancelled" in execution_log


# =============================================================================
# CONCURRENT TASK LIMITS
# =============================================================================

class TestConcurrentTaskLimits:
    """Test gather_with_concurrency respects limits."""

    @pytest.mark.asyncio
    async def test_concurrency_limit_enforced(self):
        """Test that concurrent task limit is enforced."""
        concurrent_count = 0
        max_concurrent = 0

        async def tracked_task(name: str):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return name

        coros = [tracked_task(f"task_{i}") for i in range(10)]
        results = await gather_with_concurrency(3, *coros)

        # Never exceeded limit of 3
        assert max_concurrent <= 3
        # All tasks completed
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_gather_with_concurrency_preserves_order(self):
        """Test results are in original order despite concurrent execution."""
        async def ordered_task(index: int):
            await asyncio.sleep(0.01 * (10 - index))  # Reverse delay
            return index

        coros = [ordered_task(i) for i in range(5)]
        results = await gather_with_concurrency(2, *coros)

        # Results should be in original order (0, 1, 2, 3, 4)
        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_gather_with_concurrency_handles_errors(self):
        """Test error handling in gather_with_concurrency."""
        async def maybe_fail(index: int):
            if index == 2:
                raise ValueError(f"Task {index} failed")
            return index

        coros = [maybe_fail(i) for i in range(5)]
        results = await gather_with_concurrency(2, *coros, return_exceptions=True)

        # Should have results and one exception
        assert results[0] == 0
        assert results[1] == 1
        assert isinstance(results[2], ValueError)
        assert results[3] == 3
        assert results[4] == 4

    @pytest.mark.asyncio
    async def test_gather_raises_without_return_exceptions(self):
        """Test that errors propagate when return_exceptions=False."""
        async def failing():
            raise RuntimeError("Test failure")

        async def success():
            return "ok"

        with pytest.raises(RuntimeError, match="Test failure"):
            await gather_with_concurrency(
                2,
                success(),
                failing(),
                success(),
                return_exceptions=False
            )


# =============================================================================
# TASK TIMEOUT ENFORCEMENT
# =============================================================================

class TestTaskTimeouts:
    """Test timeout enforcement."""

    @pytest.mark.asyncio
    async def test_timeout_context_raises_on_timeout(self):
        """Test timeout_context raises TimeoutError."""
        with pytest.raises(asyncio.TimeoutError) as exc_info:
            async with timeout_context(0.1, "Test operation"):
                await asyncio.sleep(1.0)

        assert "Test operation after 0.1s" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_context_allows_fast_operations(self):
        """Test timeout_context allows operations that complete in time."""
        result = None

        async with timeout_context(1.0, "Fast operation"):
            await asyncio.sleep(0.05)
            result = "completed"

        assert result == "completed"

    @pytest.mark.asyncio
    async def test_timeout_with_custom_message(self):
        """Test timeout context uses custom message."""
        with pytest.raises(asyncio.TimeoutError) as exc_info:
            async with timeout_context(0.05, "Database query"):
                await asyncio.sleep(1.0)

        assert "Database query" in str(exc_info.value)


# =============================================================================
# TASK RESULT COLLECTION
# =============================================================================

class TestTaskResultCollection:
    """Test proper collection of task results."""

    @pytest.mark.asyncio
    async def test_tracker_collects_results(self, tracker):
        """Test TaskTracker stores task results."""
        async def returning_task(value: int):
            return value * 2

        task = tracker.create_task(returning_task(21))
        result = await task

        assert result == 42

    @pytest.mark.asyncio
    async def test_gather_collects_all_results(self):
        """Test gather_with_concurrency collects all results."""
        async def data_task(data: dict):
            await asyncio.sleep(0.01)
            return {"processed": data}

        inputs = [{"id": i} for i in range(5)]
        coros = [data_task(inp) for inp in inputs]

        results = await gather_with_concurrency(3, *coros)

        assert len(results) == 5
        assert all("processed" in r for r in results)
        ids = [r["processed"]["id"] for r in results]
        assert ids == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_mixed_result_types(self):
        """Test collection of different result types."""
        async def str_task():
            return "string"

        async def int_task():
            return 42

        async def dict_task():
            return {"key": "value"}

        async def list_task():
            return [1, 2, 3]

        results = await gather_with_concurrency(
            4,
            str_task(),
            int_task(),
            dict_task(),
            list_task(),
        )

        assert results[0] == "string"
        assert results[1] == 42
        assert results[2] == {"key": "value"}
        assert results[3] == [1, 2, 3]


# =============================================================================
# RATE LIMITER
# =============================================================================

class TestRateLimiter:
    """Test async rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_throttles_calls(self):
        """Test rate limiter enforces rate limits."""
        limiter = RateLimiter(calls_per_second=10.0, burst=1)
        timestamps = []

        async def rate_limited_call():
            async with limiter:
                timestamps.append(time.monotonic())

        # Make 5 calls
        for _ in range(5):
            await rate_limited_call()

        # Should take at least 0.4s (5 calls at 10/sec with burst=1)
        elapsed = timestamps[-1] - timestamps[0]
        assert elapsed >= 0.35  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_burst(self):
        """Test rate limiter allows burst."""
        limiter = RateLimiter(calls_per_second=10.0, burst=5)
        timestamps = []

        async def burst_call():
            async with limiter:
                timestamps.append(time.monotonic())

        # Make 5 calls quickly (should all be in burst)
        for _ in range(5):
            await burst_call()

        # Burst should be fast
        elapsed = timestamps[-1] - timestamps[0]
        assert elapsed < 0.1  # All in burst window

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_access(self):
        """Test rate limiter handles concurrent access."""
        limiter = RateLimiter(calls_per_second=20.0, burst=2)
        call_count = 0

        async def concurrent_call():
            nonlocal call_count
            async with limiter:
                call_count += 1
                await asyncio.sleep(0.01)

        # Run many concurrent calls
        await asyncio.gather(*[concurrent_call() for _ in range(10)])

        assert call_count == 10


# =============================================================================
# THROTTLE DECORATOR
# =============================================================================

class TestThrottleDecorator:
    """Test Throttle decorator."""

    @pytest.mark.asyncio
    async def test_throttle_decorator_limits_rate(self):
        """Test @Throttle limits function call rate."""
        timestamps = []

        @Throttle(calls_per_second=5.0)
        async def throttled_func():
            timestamps.append(time.monotonic())
            return True

        # Make 5 calls
        for _ in range(5):
            await throttled_func()

        # Should take at least 0.8s (5 calls at 5/sec)
        elapsed = timestamps[-1] - timestamps[0]
        assert elapsed >= 0.7

    @pytest.mark.asyncio
    async def test_throttle_preserves_return_value(self):
        """Test throttled function returns correct value."""
        @Throttle(calls_per_second=100.0)
        async def returning_func(x: int):
            return x * 2

        result = await returning_func(21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_throttle_preserves_exceptions(self):
        """Test throttled function propagates exceptions."""
        @Throttle(calls_per_second=100.0)
        async def failing_func():
            raise ValueError("Expected error")

        with pytest.raises(ValueError, match="Expected error"):
            await failing_func()


# =============================================================================
# RETRY ASYNC
# =============================================================================

class TestRetryAsync:
    """Test async retry with backoff."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_first_attempt(self):
        """Test retry returns immediately on success."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(success_func, max_attempts=3)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failures(self):
        """Test retry succeeds after transient failures."""
        attempt = 0

        async def flaky_func():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError("Temporary failure")
            return "recovered"

        result = await retry_async(
            flaky_func,
            max_attempts=5,
            delay=0.05,
            exceptions=(ConnectionError,)
        )

        assert result == "recovered"
        assert attempt == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        """Test retry raises after exhausting attempts."""
        async def always_fails():
            raise RuntimeError("Permanent failure")

        with pytest.raises(RuntimeError, match="Permanent failure"):
            await retry_async(
                always_fails,
                max_attempts=3,
                delay=0.01
            )

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Test retry uses exponential backoff."""
        timestamps = []

        async def tracked_failure():
            timestamps.append(time.monotonic())
            raise ValueError("fail")

        try:
            await retry_async(
                tracked_failure,
                max_attempts=4,
                delay=0.1,
                backoff=2.0,
                exceptions=(ValueError,)
            )
        except ValueError:
            pass

        # Check delays increase exponentially
        # Delays should be ~0.1, ~0.2, ~0.4
        delays = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]

        assert len(delays) == 3
        assert delays[0] >= 0.08  # ~0.1
        assert delays[1] >= 0.16  # ~0.2
        assert delays[2] >= 0.32  # ~0.4

    @pytest.mark.asyncio
    async def test_retry_only_catches_specified_exceptions(self):
        """Test retry only catches specified exception types."""
        async def wrong_exception():
            raise KeyError("unexpected")

        with pytest.raises(KeyError):
            await retry_async(
                wrong_exception,
                max_attempts=3,
                exceptions=(ValueError,)  # Not KeyError
            )

    @pytest.mark.asyncio
    async def test_retry_with_args_and_kwargs(self):
        """Test retry passes args and kwargs correctly."""
        async def param_func(a: int, b: int, multiplier: int = 1):
            return (a + b) * multiplier

        result = await retry_async(
            param_func,
            5, 10,  # args
            multiplier=2,  # kwarg
            max_attempts=1
        )

        assert result == 30


# =============================================================================
# FIRE AND FORGET
# =============================================================================

class TestFireAndForget:
    """Test fire_and_forget background task execution."""

    @pytest.mark.asyncio
    async def test_fire_and_forget_executes(self, execution_log):
        """Test fire_and_forget tasks execute in background."""
        async def background_task():
            await asyncio.sleep(0.05)
            execution_log["order"].append("background_done")

        fire_and_forget(background_task(), name="bg_task")

        # Should not block
        execution_log["order"].append("main_continues")

        # Wait for background task
        await asyncio.sleep(0.2)

        assert "main_continues" in execution_log["order"]
        assert "background_done" in execution_log["order"]
        # Main should have continued first
        assert execution_log["order"].index("main_continues") < execution_log["order"].index("background_done")

    @pytest.mark.asyncio
    async def test_fire_and_forget_logs_errors(self):
        """Test fire_and_forget logs errors without raising."""
        async def failing_background():
            raise ValueError("Background error")

        # Should not raise
        task = fire_and_forget(failing_background(), name="failing_bg")

        # Wait for it to complete (with error)
        await asyncio.sleep(0.1)

        # Task completed (with error)
        assert task.done()


# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================

class TestModuleLevelHelpers:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_create_tracked_task_uses_default_tracker(self):
        """Test create_tracked_task uses global default tracker."""
        async def simple():
            return "tracked"

        task = create_tracked_task(simple(), name="global_test")
        result = await task

        assert result == "tracked"
        assert "global" in task.get_name()

    @pytest.mark.asyncio
    async def test_create_tracked_task_custom_tracker(self):
        """Test create_tracked_task with custom tracker."""
        custom_tracker = TaskTracker("custom")

        async def task_func():
            return "custom_result"

        task = create_tracked_task(
            task_func(),
            name="custom_task",
            tracker=custom_tracker
        )

        result = await task
        assert result == "custom_result"
        assert "custom.custom_task" in task.get_name()


# =============================================================================
# EDGE CASES AND STRESS TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_gather(self):
        """Test gather_with_concurrency with no coroutines."""
        results = await gather_with_concurrency(5)
        assert results == []

    @pytest.mark.asyncio
    async def test_single_task_gather(self):
        """Test gather_with_concurrency with single coroutine."""
        async def single():
            return "alone"

        results = await gather_with_concurrency(5, single())
        assert results == ["alone"]

    @pytest.mark.asyncio
    async def test_concurrency_higher_than_tasks(self):
        """Test when concurrency limit exceeds task count."""
        async def quick():
            return "fast"

        coros = [quick() for _ in range(3)]
        results = await gather_with_concurrency(100, *coros)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_tracker_cleanup_completed(self, tracker):
        """Test cleanup removes only completed tasks."""
        async def quick():
            return True

        async def slow():
            await asyncio.sleep(10)
            return True

        quick_task = tracker.create_task(quick())
        slow_task = tracker.create_task(slow())

        await quick_task

        # Cleanup should remove completed but not running
        removed = tracker._cleanup_completed()

        # One was removed (quick), one still running (slow)
        running = tracker.get_running_tasks()
        assert len(running) == 1

        slow_task.cancel()
        try:
            await slow_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_rapid_task_creation(self, tracker):
        """Test creating many tasks rapidly."""
        async def instant():
            return True

        tasks = [tracker.create_task(instant()) for _ in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert all(r is True for r in results)

        stats = tracker.get_stats()
        assert stats["total_created"] == 100
        assert stats["total_succeeded"] == 100

    @pytest.mark.asyncio
    async def test_zero_timeout_raises_immediately(self):
        """Test zero timeout raises immediately."""
        with pytest.raises(asyncio.TimeoutError):
            async with timeout_context(0, "Zero timeout"):
                await asyncio.sleep(0.001)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_tracked_tasks_with_rate_limiting(self, tracker):
        """Test combining TaskTracker with RateLimiter."""
        limiter = RateLimiter(calls_per_second=10.0, burst=2)
        results = []

        async def rate_limited_task(value: int):
            async with limiter:
                await asyncio.sleep(0.01)
                results.append(value)
                return value

        tasks = [
            tracker.create_task(rate_limited_task(i))
            for i in range(5)
        ]

        await asyncio.gather(*tasks)

        assert len(results) == 5
        assert tracker.get_stats()["total_succeeded"] == 5

    @pytest.mark.asyncio
    async def test_retry_with_gather(self):
        """Test retry_async combined with gather."""
        call_counts = {}

        async def flaky_operation(key: str):
            call_counts[key] = call_counts.get(key, 0) + 1
            if call_counts[key] < 2:
                raise ConnectionError(f"Transient error for {key}")
            return f"success_{key}"

        async def retryable(key: str):
            return await retry_async(
                flaky_operation,
                key,
                max_attempts=3,
                delay=0.01
            )

        results = await gather_with_concurrency(
            2,
            retryable("a"),
            retryable("b"),
            retryable("c"),
        )

        assert results == ["success_a", "success_b", "success_c"]

    @pytest.mark.asyncio
    async def test_complex_task_pipeline(self, tracker):
        """Test complex pipeline with multiple async features."""
        pipeline_results = []
        # Track attempts per item to simulate transient failures
        fetch_attempts = {}

        async def fetch_data(item_id: int):
            """Simulate fetching data with transient failure for item 3."""
            await asyncio.sleep(0.01)
            fetch_attempts[item_id] = fetch_attempts.get(item_id, 0) + 1
            # Item 3 fails first 2 attempts, succeeds on 3rd
            if item_id == 3 and fetch_attempts[item_id] < 3:
                raise ConnectionError(f"Network error (attempt {fetch_attempts[item_id]})")
            return {"id": item_id, "data": f"data_{item_id}"}

        async def process_item(item: dict):
            """Process fetched data."""
            await asyncio.sleep(0.01)
            return {"processed": item["id"], "result": item["data"].upper()}

        async def pipeline_stage(item_id: int):
            """Complete pipeline for one item."""
            try:
                data = await retry_async(
                    fetch_data,
                    item_id,
                    max_attempts=5,
                    delay=0.01,
                    exceptions=(ConnectionError,)
                )
                result = await process_item(data)
                pipeline_results.append(result)
                return result
            except Exception as e:
                return {"error": str(e), "id": item_id}

        # Process items with limited concurrency
        coros = [pipeline_stage(i) for i in range(5)]
        results = await gather_with_concurrency(2, *coros, return_exceptions=True)

        # All should succeed (item 3 retries and succeeds on 3rd attempt)
        assert len(results) == 5
        successful = [r for r in results if "processed" in r]
        assert len(successful) == 5
        # Verify item 3 required retries
        assert fetch_attempts[3] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
