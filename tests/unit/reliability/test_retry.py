"""Tests for retry logic with exponential backoff.

These tests verify:
- Basic retry behavior
- Exponential backoff timing
- Max attempts limiting
- Exception filtering
- Callback hooks
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, call


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_succeeds_without_retry(self):
        """Should return result on first success."""
        from core.reliability.retry import retry

        call_count = 0

        @retry(max_attempts=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count == 1

    def test_retries_on_failure(self):
        """Should retry on failure."""
        from core.reliability.retry import retry

        attempt = 0

        @retry(max_attempts=3, backoff_factor=0.01)
        def fails_twice():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError("not yet")
            return "eventually_succeeds"

        result = fails_twice()
        assert result == "eventually_succeeds"
        assert attempt == 3

    def test_raises_after_max_attempts(self):
        """Should raise after exhausting max_attempts."""
        from core.reliability.retry import retry

        @retry(max_attempts=3, backoff_factor=0.01)
        def always_fails():
            raise RuntimeError("permanent failure")

        with pytest.raises(RuntimeError, match="permanent failure"):
            always_fails()

    def test_respects_exception_filter(self):
        """Should only retry specified exceptions."""
        from core.reliability.retry import retry

        call_count = 0

        @retry(
            max_attempts=3,
            exceptions=(ValueError,),
            backoff_factor=0.01
        )
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            raises_type_error()

        assert call_count == 1  # No retry for TypeError


class TestExponentialBackoff:
    """Test exponential backoff timing."""

    def test_backoff_increases_exponentially(self):
        """Backoff delay should increase exponentially."""
        from core.reliability.retry import ExponentialBackoff

        backoff = ExponentialBackoff(base_delay=1.0, factor=2)

        delays = [backoff.get_delay(i) for i in range(5)]

        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0

    def test_backoff_respects_max_delay(self):
        """Backoff should cap at max_delay."""
        from core.reliability.retry import ExponentialBackoff

        backoff = ExponentialBackoff(base_delay=1.0, factor=2, max_delay=5.0)

        delay = backoff.get_delay(10)
        assert delay == 5.0

    def test_backoff_with_jitter(self):
        """Backoff should add jitter when configured."""
        from core.reliability.retry import ExponentialBackoff

        backoff = ExponentialBackoff(base_delay=1.0, factor=2, jitter=True)

        # With jitter, delays should vary
        delays = [backoff.get_delay(1) for _ in range(10)]

        # Not all delays should be exactly the same
        assert len(set(delays)) > 1


class TestAsyncRetry:
    """Test async retry functionality."""

    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Should retry async functions."""
        from core.reliability.retry import async_retry

        attempt = 0

        @async_retry(max_attempts=3, backoff_factor=0.01)
        async def async_fails_once():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise ValueError("first fail")
            return "success"

        result = await async_fails_once()
        assert result == "success"
        assert attempt == 2

    @pytest.mark.asyncio
    async def test_async_retry_timeout_handling(self):
        """Should handle asyncio.TimeoutError."""
        from core.reliability.retry import async_retry

        attempt = 0

        @async_retry(max_attempts=2, backoff_factor=0.01)
        async def timeout_once():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise asyncio.TimeoutError()
            return "recovered"

        result = await timeout_once()
        assert result == "recovered"


class TestRetryCallbacks:
    """Test retry callback hooks."""

    def test_on_retry_callback(self):
        """Should call on_retry callback before each retry."""
        from core.reliability.retry import retry

        retry_calls = []

        def on_retry(exc, attempt, delay):
            retry_calls.append((type(exc).__name__, attempt, delay))

        attempt = 0

        @retry(max_attempts=3, backoff_factor=0.1, on_retry=on_retry)
        def fails_twice():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError(f"attempt {attempt}")
            return "done"

        fails_twice()

        assert len(retry_calls) == 2
        assert retry_calls[0][0] == "ValueError"
        assert retry_calls[0][1] == 1

    def test_on_success_callback(self):
        """Should call on_success after successful call."""
        from core.reliability.retry import retry

        success_data = {}

        def on_success(result, attempts):
            success_data["result"] = result
            success_data["attempts"] = attempts

        @retry(max_attempts=3, on_success=on_success, backoff_factor=0.01)
        def succeeds_third():
            if success_data.get("attempts", 0) < 2:
                raise ValueError()
            return "finally"

        # Need different approach - track externally
        attempt = 0

        @retry(max_attempts=3, on_success=on_success, backoff_factor=0.01)
        def track_attempts():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError()
            return "success"

        result = track_attempts()
        assert success_data["result"] == "success"
        assert success_data["attempts"] == 3

    def test_on_failure_callback(self):
        """Should call on_failure after all attempts exhausted."""
        from core.reliability.retry import retry

        failure_data = {}

        def on_failure(exc, attempts):
            failure_data["error"] = str(exc)
            failure_data["attempts"] = attempts

        @retry(max_attempts=2, on_failure=on_failure, backoff_factor=0.01)
        def always_fails():
            raise RuntimeError("persistent error")

        with pytest.raises(RuntimeError):
            always_fails()

        assert failure_data["error"] == "persistent error"
        assert failure_data["attempts"] == 2


class TestRetryContext:
    """Test retry context information."""

    def test_retry_context_in_exception(self):
        """Should include retry context in final exception."""
        from core.reliability.retry import retry, RetryExhaustedError

        @retry(max_attempts=2, backoff_factor=0.01, wrap_errors=True)
        def always_fails():
            raise ValueError("original error")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_fails()

        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_preserves_original_traceback(self):
        """Should preserve original exception traceback."""
        from core.reliability.retry import retry
        import traceback

        @retry(max_attempts=2, backoff_factor=0.01)
        def fails_with_traceback():
            raise ValueError("deep error")

        try:
            fails_with_traceback()
        except ValueError as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            assert "fails_with_traceback" in "".join(tb)
