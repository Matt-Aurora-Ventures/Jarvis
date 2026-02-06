"""
Tests for core/retry/executor.py

Tests the RetryExecutor class for sync and async execution with retry.
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch


class TestRetryResult:
    """Tests for RetryResult class."""

    def test_result_success(self):
        """Successful result should have value and no exception."""
        from core.retry.executor import RetryResult

        result = RetryResult(
            success=True,
            value="test_value",
            attempts=1,
            total_duration=0.5
        )

        assert result.success is True
        assert result.value == "test_value"
        assert result.exception is None
        assert result.attempts == 1
        assert result.total_duration == 0.5

    def test_result_failure(self):
        """Failed result should have exception and no value."""
        from core.retry.executor import RetryResult

        exc = ValueError("test error")
        result = RetryResult(
            success=False,
            exception=exc,
            attempts=3,
            total_duration=5.0
        )

        assert result.success is False
        assert result.value is None
        assert result.exception is exc
        assert result.attempts == 3

    def test_result_attempt_history(self):
        """Result should track attempt history."""
        from core.retry.executor import RetryResult, AttemptRecord

        attempts = [
            AttemptRecord(attempt=1, duration=0.1, exception=ValueError("e1")),
            AttemptRecord(attempt=2, duration=0.2, exception=ValueError("e2")),
            AttemptRecord(attempt=3, duration=0.3, success=True, value="ok"),
        ]

        result = RetryResult(
            success=True,
            value="ok",
            attempts=3,
            total_duration=0.6,
            attempt_history=attempts
        )

        assert len(result.attempt_history) == 3
        assert result.attempt_history[0].attempt == 1
        assert result.attempt_history[2].success is True


class TestRetryExecutor:
    """Tests for RetryExecutor class."""

    def test_execute_success_first_try(self):
        """Should succeed on first try without retries."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=3)
        executor = RetryExecutor(policy)

        def success_fn():
            return "success"

        result = executor.execute(success_fn)

        assert result.success is True
        assert result.value == "success"
        assert result.attempts == 1

    def test_execute_retries_on_failure(self):
        """Should retry on transient failures."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=3, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        call_count = 0

        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary failure")
            return "success"

        result = executor.execute(fail_then_succeed)

        assert result.success is True
        assert result.value == "success"
        assert result.attempts == 3

    def test_execute_exhausts_retries(self):
        """Should return failure after all retries exhausted."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        def always_fail():
            raise ValueError("permanent failure")

        result = executor.execute(always_fail)

        assert result.success is False
        assert isinstance(result.exception, ValueError)
        assert result.attempts == 3  # 1 initial + 2 retries

    def test_execute_respects_non_retryable(self):
        """Should not retry non-retryable exceptions."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(
            max_retries=3,
            non_retryable_exceptions=[KeyError]
        )
        executor = RetryExecutor(policy)

        call_count = 0

        def raise_keyerror():
            nonlocal call_count
            call_count += 1
            raise KeyError("not retryable")

        result = executor.execute(raise_keyerror)

        assert result.success is False
        assert call_count == 1  # No retries

    def test_execute_tracks_duration(self):
        """Should track total execution duration."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=1, base_delay=0.1, jitter=False)
        executor = RetryExecutor(policy)

        def slow_fail():
            time.sleep(0.05)
            raise ValueError("fail")

        result = executor.execute(slow_fail)

        # Should have ~0.05s for attempt 1, 0.1s delay, 0.05s for attempt 2
        assert result.total_duration >= 0.15

    def test_execute_with_args(self):
        """Should pass arguments to function."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()
        executor = RetryExecutor(policy)

        def add(a, b, c=0):
            return a + b + c

        result = executor.execute(add, 1, 2, c=3)

        assert result.success is True
        assert result.value == 6


class TestRetryExecutorAsync:
    """Tests for async execution."""

    @pytest.mark.asyncio
    async def test_async_execute_success(self):
        """Should handle async functions successfully."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=3)
        executor = RetryExecutor(policy)

        async def async_success():
            await asyncio.sleep(0.01)
            return "async_success"

        result = await executor.async_execute(async_success)

        assert result.success is True
        assert result.value == "async_success"

    @pytest.mark.asyncio
    async def test_async_execute_retries(self):
        """Should retry async functions on failure."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=3, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("temporary")
            return "success"

        result = await executor.async_execute(fail_then_succeed)

        assert result.success is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_async_execute_with_args(self):
        """Should pass arguments to async function."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()
        executor = RetryExecutor(policy)

        async def async_add(a, b):
            return a + b

        result = await executor.async_execute(async_add, 10, 20)

        assert result.success is True
        assert result.value == 30


class TestRetryExecutorCallbacks:
    """Tests for executor callbacks."""

    def test_on_retry_callback(self):
        """Should call on_retry callback before each retry."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        retry_calls = []

        def on_retry(attempt, exception, delay):
            retry_calls.append((attempt, str(exception), delay))

        def always_fail():
            raise ValueError("fail")

        executor.execute(always_fail, on_retry=on_retry)

        assert len(retry_calls) == 2
        assert retry_calls[0][0] == 1  # First retry after attempt 1
        assert retry_calls[1][0] == 2  # Second retry after attempt 2

    def test_on_success_callback(self):
        """Should call on_success callback on successful execution."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()
        executor = RetryExecutor(policy)

        success_result = []

        def on_success(result, attempts):
            success_result.append((result, attempts))

        def succeed():
            return "done"

        executor.execute(succeed, on_success=on_success)

        assert len(success_result) == 1
        assert success_result[0] == ("done", 1)

    def test_on_failure_callback(self):
        """Should call on_failure callback on exhausted retries."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=1, base_delay=0.01)
        executor = RetryExecutor(policy)

        failure_result = []

        def on_failure(exception, attempts):
            failure_result.append((str(exception), attempts))

        def always_fail():
            raise ValueError("permanent")

        executor.execute(always_fail, on_failure=on_failure)

        assert len(failure_result) == 1
        assert "permanent" in failure_result[0][0]


class TestRetryExecutorMetrics:
    """Tests for executor metrics tracking."""

    def test_tracks_attempt_history(self):
        """Should track history of all attempts."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=2, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        call_count = 0

        def fail_twice_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"fail {call_count}")
            return "ok"

        result = executor.execute(fail_twice_then_succeed)

        assert result.success is True
        assert len(result.attempt_history) == 3
        assert result.attempt_history[0].exception is not None
        assert result.attempt_history[1].exception is not None
        assert result.attempt_history[2].success is True

    def test_metrics_per_attempt(self):
        """Should track duration for each attempt."""
        from core.retry.executor import RetryExecutor
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(max_retries=1, base_delay=0.01, jitter=False)
        executor = RetryExecutor(policy)

        def slow_then_fast():
            if not hasattr(slow_then_fast, 'called'):
                slow_then_fast.called = True
                time.sleep(0.05)
                raise ValueError("slow fail")
            return "fast success"

        result = executor.execute(slow_then_fast)

        assert len(result.attempt_history) == 2
        assert result.attempt_history[0].duration >= 0.05
