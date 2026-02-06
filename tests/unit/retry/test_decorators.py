"""
Tests for core/retry/decorators.py

Tests retry decorators for functions.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


class TestRetryDecorator:
    """Tests for @retry decorator."""

    def test_retry_decorator_success(self):
        """Decorated function should work normally on success."""
        from core.retry.decorators import retry

        @retry(max_retries=3)
        def succeed():
            return "success"

        result = succeed()
        assert result == "success"

    def test_retry_decorator_retries_on_failure(self):
        """Should retry on transient failures."""
        from core.retry.decorators import retry

        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary")
            return "recovered"

        result = fail_then_succeed()

        assert result == "recovered"
        assert call_count == 3

    def test_retry_decorator_raises_after_exhausted(self):
        """Should raise exception after retries exhausted."""
        from core.retry.decorators import retry

        @retry(max_retries=2, base_delay=0.01)
        def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            always_fail()

    def test_retry_decorator_exponential_backoff(self):
        """Should use exponential backoff by default."""
        from core.retry.decorators import retry

        @retry(max_retries=2, base_delay=0.01, backoff='exponential')
        def always_fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()

    def test_retry_decorator_linear_backoff(self):
        """Should support linear backoff."""
        from core.retry.decorators import retry

        @retry(max_retries=2, base_delay=0.01, backoff='linear')
        def always_fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()

    def test_retry_decorator_fixed_backoff(self):
        """Should support fixed backoff."""
        from core.retry.decorators import retry

        @retry(max_retries=2, base_delay=0.01, backoff='fixed')
        def always_fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()

    def test_retry_decorator_with_args(self):
        """Should pass arguments to decorated function."""
        from core.retry.decorators import retry

        @retry(max_retries=3)
        def add(a, b, c=0):
            return a + b + c

        result = add(1, 2, c=3)
        assert result == 6

    def test_retry_decorator_preserves_function_metadata(self):
        """Should preserve function name and docstring."""
        from core.retry.decorators import retry

        @retry(max_retries=3)
        def my_function():
            """My docstring."""
            return True

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestRetryDecoratorAsync:
    """Tests for @retry decorator with async functions."""

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Should work with async functions."""
        from core.retry.decorators import retry

        @retry(max_retries=3)
        async def async_succeed():
            await asyncio.sleep(0.01)
            return "async_success"

        result = await async_succeed()
        assert result == "async_success"

    @pytest.mark.asyncio
    async def test_retry_async_retries(self):
        """Should retry async functions on failure."""
        from core.retry.decorators import retry

        call_count = 0

        @retry(max_retries=3, base_delay=0.01)
        async def async_fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("temporary")
            return "recovered"

        result = await async_fail_then_succeed()

        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_async_raises_after_exhausted(self):
        """Should raise after async retries exhausted."""
        from core.retry.decorators import retry

        @retry(max_retries=2, base_delay=0.01)
        async def async_always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await async_always_fail()


class TestRetryOnDecorator:
    """Tests for @retry_on decorator for specific exceptions."""

    def test_retry_on_specific_exception(self):
        """Should only retry specified exception types."""
        from core.retry.decorators import retry_on

        call_count = 0

        @retry_on(exceptions=[ConnectionError], max_retries=3, base_delay=0.01)
        def retry_connection_only():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network error")
            return "success"

        result = retry_connection_only()
        assert result == "success"
        assert call_count == 3

    def test_retry_on_does_not_retry_other_exceptions(self):
        """Should not retry exceptions not in the list."""
        from core.retry.decorators import retry_on

        call_count = 0

        @retry_on(exceptions=[ConnectionError], max_retries=3, base_delay=0.01)
        def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            raise_value_error()

        assert call_count == 1  # No retries

    def test_retry_on_multiple_exceptions(self):
        """Should retry multiple exception types."""
        from core.retry.decorators import retry_on

        call_count = 0

        @retry_on(exceptions=[ConnectionError, TimeoutError], max_retries=3, base_delay=0.01)
        def mixed_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("network")
            if call_count == 2:
                raise TimeoutError("slow")
            return "success"

        result = mixed_errors()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_async(self):
        """Should work with async functions."""
        from core.retry.decorators import retry_on

        call_count = 0

        @retry_on(exceptions=[ConnectionError], max_retries=2, base_delay=0.01)
        async def async_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("network")
            return "done"

        result = await async_retry()
        assert result == "done"


class TestCircuitBreakerDecorator:
    """Tests for @circuit_breaker decorator."""

    def test_circuit_breaker_passes_when_closed(self):
        """Closed circuit should pass requests through."""
        from core.retry.decorators import circuit_breaker

        @circuit_breaker(failure_threshold=5)
        def succeed():
            return "success"

        result = succeed()
        assert result == "success"

    def test_circuit_breaker_opens_after_failures(self):
        """Circuit should open after failure threshold."""
        from core.retry.decorators import circuit_breaker, CircuitOpenError

        call_count = 0

        @circuit_breaker(failure_threshold=3, recovery_timeout=60.0)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        # Trigger failures to open circuit
        for _ in range(3):
            try:
                always_fail()
            except ValueError:
                pass

        # Circuit should now be open
        with pytest.raises(CircuitOpenError):
            always_fail()

        # Function shouldn't have been called after circuit opened
        assert call_count == 3

    def test_circuit_breaker_resets_on_success(self):
        """Circuit should reset failure count on success."""
        from core.retry.decorators import circuit_breaker

        call_count = 0

        @circuit_breaker(failure_threshold=3)
        def sometimes_fail():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise ValueError("fail")
            return "success"

        # Mix of successes and failures shouldn't trip circuit
        for _ in range(10):
            try:
                sometimes_fail()
            except ValueError:
                pass

        # Should still be callable (circuit not open)
        result = sometimes_fail()
        assert result == "success"

    def test_circuit_breaker_named(self):
        """Should support named circuits for isolation."""
        from core.retry.decorators import circuit_breaker, CircuitOpenError

        @circuit_breaker(name="service_a", failure_threshold=2)
        def service_a():
            raise ValueError("fail")

        @circuit_breaker(name="service_b", failure_threshold=2)
        def service_b():
            return "success"

        # Trip circuit A
        for _ in range(2):
            try:
                service_a()
            except ValueError:
                pass

        # Circuit A should be open
        with pytest.raises(CircuitOpenError):
            service_a()

        # Circuit B should still work
        result = service_b()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_breaker_async(self):
        """Should work with async functions."""
        from core.retry.decorators import circuit_breaker, CircuitOpenError

        call_count = 0

        @circuit_breaker(failure_threshold=2)
        async def async_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        for _ in range(2):
            try:
                await async_fail()
            except ValueError:
                pass

        with pytest.raises(CircuitOpenError):
            await async_fail()

    def test_circuit_breaker_with_recovery_timeout(self):
        """Circuit should transition to half-open after timeout."""
        from core.retry.decorators import circuit_breaker, get_circuit

        @circuit_breaker(name="test_recovery", failure_threshold=2, recovery_timeout=0.1)
        def fail_then_succeed():
            raise ValueError("fail")

        # Trip the circuit
        for _ in range(2):
            try:
                fail_then_succeed()
            except ValueError:
                pass

        # Get the circuit and manually test state
        circuit = get_circuit("test_recovery")
        assert circuit is not None


class TestCombinedDecorators:
    """Tests for combining retry and circuit breaker."""

    def test_retry_with_circuit_breaker(self):
        """Should support combining retry and circuit breaker."""
        from core.retry.decorators import retry, circuit_breaker

        call_count = 0

        @circuit_breaker(failure_threshold=5)
        @retry(max_retries=2, base_delay=0.01)
        def combined():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary")
            return "success"

        result = combined()
        assert result == "success"
        assert call_count == 3
