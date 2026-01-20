"""
Comprehensive tests for retry mechanisms in JARVIS.

Tests cover:
1. Exponential backoff calculations
2. Max retry limits
3. Retry conditions (which errors trigger retries)
4. Timeout handling during retries
5. Circuit breaker integration with retries
6. Multiple retry strategies (fixed, exponential, fibonacci, linear, random)
7. Jitter behavior
8. Sync and async retry execution

Modules tested:
- core.resilience.retry
- core.resilience.backoff
- core.retry_handler
- core.reliability.circuit_breaker
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta


# =============================================================================
# Test the Backoff Module (core/resilience/backoff.py)
# =============================================================================

class TestBackoffConfig:
    """Test BackoffConfig class."""

    def test_default_config(self):
        """BackoffConfig has sensible defaults."""
        from core.resilience.backoff import BackoffConfig

        config = BackoffConfig()
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.max_retries == 3
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert Exception in config.retryable_exceptions

    def test_custom_config(self):
        """BackoffConfig accepts custom parameters."""
        from core.resilience.backoff import BackoffConfig

        config = BackoffConfig(
            base_delay=0.5,
            max_delay=30.0,
            max_retries=5,
            exponential_base=3.0,
            jitter=False,
            retryable_exceptions=[ConnectionError, TimeoutError]
        )

        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.max_retries == 5
        assert config.exponential_base == 3.0
        assert config.jitter is False
        assert config.retryable_exceptions == [ConnectionError, TimeoutError]


class TestCalculateBackoffDelay:
    """Test exponential backoff delay calculation."""

    def test_exponential_growth(self):
        """Delay grows exponentially without jitter."""
        from core.resilience.backoff import calculate_backoff_delay, BackoffConfig

        config = BackoffConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        # First attempt (index 0): 1 * 2^0 = 1
        delay0 = calculate_backoff_delay(0, config)
        assert delay0 == 1.0

        # Second attempt (index 1): 1 * 2^1 = 2
        delay1 = calculate_backoff_delay(1, config)
        assert delay1 == 2.0

        # Third attempt (index 2): 1 * 2^2 = 4
        delay2 = calculate_backoff_delay(2, config)
        assert delay2 == 4.0

    def test_max_delay_cap(self):
        """Delay is capped at max_delay."""
        from core.resilience.backoff import calculate_backoff_delay, BackoffConfig

        config = BackoffConfig(base_delay=10.0, max_delay=30.0, exponential_base=2.0, jitter=False)

        # Attempt 5: 10 * 2^5 = 320, but capped at 30
        delay = calculate_backoff_delay(5, config)
        assert delay == 30.0

    def test_jitter_adds_randomness(self):
        """Jitter adds randomness to delays."""
        from core.resilience.backoff import calculate_backoff_delay, BackoffConfig

        config = BackoffConfig(base_delay=10.0, jitter=True)

        # Run multiple times to verify variance
        delays = [calculate_backoff_delay(0, config) for _ in range(20)]

        # All delays should be within jitter range (+-25%)
        for delay in delays:
            assert 7.5 <= delay <= 12.5

        # Should have some variance (not all identical)
        assert len(set(delays)) > 1

    def test_zero_attempt(self):
        """Zero attempt index works correctly."""
        from core.resilience.backoff import calculate_backoff_delay, BackoffConfig

        config = BackoffConfig(base_delay=2.0, exponential_base=2.0, jitter=False)
        delay = calculate_backoff_delay(0, config)
        assert delay == 2.0


class TestRetryWithBackoff:
    """Test async retry with backoff function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Function returns immediately on success."""
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_func)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Function retries and eventually succeeds."""
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        call_count = 0

        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Not yet")
            return "finally"

        config = BackoffConfig(base_delay=0.01, max_retries=5)
        result = await retry_with_backoff(eventually_succeeds, config=config)

        assert result == "finally"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Raises exception after max retries exhausted."""
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        config = BackoffConfig(base_delay=0.01, max_retries=3)

        with pytest.raises(ConnectionError, match="Always fails"):
            await retry_with_backoff(always_fails, config=config)

        # 4 total attempts (initial + 3 retries)
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_non_retryable_exception_fails_immediately(self):
        """Non-retryable exceptions fail without retry."""
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        call_count = 0

        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=5,
            retryable_exceptions=[ConnectionError]  # ValueError not included
        )

        with pytest.raises(ValueError, match="Invalid input"):
            await retry_with_backoff(raises_value_error, config=config)

        assert call_count == 1  # Only one attempt


class TestBackoffDecorators:
    """Test retry decorators."""

    @pytest.mark.asyncio
    async def test_retry_async_decorator(self):
        """Test retry_async decorator."""
        from core.resilience.backoff import retry_async, BackoffConfig

        call_count = 0

        @retry_async(BackoffConfig(base_delay=0.01, max_retries=2))
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Retry me")
            return "decorated success"

        result = await decorated_func()
        assert result == "decorated success"
        assert call_count == 2

    def test_retry_backoff_sync_decorator(self):
        """Test retry_backoff sync decorator."""
        from core.resilience.backoff import retry_backoff, BackoffConfig

        call_count = 0

        @retry_backoff(BackoffConfig(base_delay=0.01, max_retries=2))
        def sync_decorated():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Sync retry")
            return "sync success"

        result = sync_decorated()
        assert result == "sync success"
        assert call_count == 2


# =============================================================================
# Test the Retry Handler Module (core/retry_handler.py)
# =============================================================================

class TestRetryStrategy:
    """Test different retry strategies."""

    def test_strategy_enum_values(self):
        """RetryStrategy enum has expected values."""
        from core.retry_handler import RetryStrategy

        assert RetryStrategy.FIXED.value == "fixed"
        assert RetryStrategy.EXPONENTIAL.value == "exponential"
        assert RetryStrategy.FIBONACCI.value == "fibonacci"
        assert RetryStrategy.LINEAR.value == "linear"
        assert RetryStrategy.RANDOM.value == "random"


class TestRetryHandlerDelayCalculation:
    """Test delay calculation for different strategies."""

    @pytest.fixture
    def handler(self, temp_dir):
        """Create retry handler with temp DB."""
        from core.retry_handler import RetryHandler
        db_path = str(temp_dir / "test_retry.db")
        return RetryHandler(db_path=db_path)

    def test_fixed_delay_strategy(self, handler):
        """Fixed strategy returns constant delay."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay=5.0,
            max_delay=100.0,
            jitter=0.0
        )

        # All attempts should have same delay
        delay1 = handler.calculate_delay(1, config)
        delay2 = handler.calculate_delay(3, config)
        delay3 = handler.calculate_delay(5, config)

        assert delay1 == delay2 == delay3 == 5.0

    def test_exponential_delay_strategy(self, handler):
        """Exponential strategy doubles delay."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=100.0,
            jitter=0.0
        )

        # Delay = base * 2^(attempt-1)
        assert handler.calculate_delay(1, config) == 1.0   # 1 * 2^0
        assert handler.calculate_delay(2, config) == 2.0   # 1 * 2^1
        assert handler.calculate_delay(3, config) == 4.0   # 1 * 2^2
        assert handler.calculate_delay(4, config) == 8.0   # 1 * 2^3

    def test_fibonacci_delay_strategy(self, handler):
        """Fibonacci strategy uses fibonacci sequence."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.FIBONACCI,
            base_delay=1.0,
            max_delay=1000.0,
            jitter=0.0
        )

        # Fibonacci: 1, 1, 2, 3, 5, 8, 13...
        assert handler.calculate_delay(1, config) == 1.0   # fib[0] = 1
        assert handler.calculate_delay(2, config) == 1.0   # fib[1] = 1
        assert handler.calculate_delay(3, config) == 2.0   # fib[2] = 2
        assert handler.calculate_delay(4, config) == 3.0   # fib[3] = 3
        assert handler.calculate_delay(5, config) == 5.0   # fib[4] = 5

    def test_linear_delay_strategy(self, handler):
        """Linear strategy increases linearly."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            base_delay=2.0,
            max_delay=100.0,
            jitter=0.0
        )

        # Delay = base * attempt
        assert handler.calculate_delay(1, config) == 2.0
        assert handler.calculate_delay(2, config) == 4.0
        assert handler.calculate_delay(3, config) == 6.0
        assert handler.calculate_delay(4, config) == 8.0

    def test_random_delay_strategy(self, handler):
        """Random strategy returns random delay within range."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.RANDOM,
            base_delay=1.0,
            max_delay=10.0,
            jitter=0.0  # jitter handled differently for random
        )

        # Multiple samples should be within range
        delays = [handler.calculate_delay(1, config) for _ in range(20)]

        for delay in delays:
            assert 1.0 <= delay <= 10.0

    def test_delay_capped_at_max(self, handler):
        """All strategies cap delay at max_delay."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=10.0,
            max_delay=50.0,
            jitter=0.0
        )

        # Attempt 10: 10 * 2^9 = 5120, capped at 50
        delay = handler.calculate_delay(10, config)
        assert delay == 50.0

    def test_jitter_affects_delay(self, handler):
        """Jitter adds variance to delay."""
        from core.retry_handler import RetryConfig, RetryStrategy

        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay=10.0,
            max_delay=100.0,
            jitter=0.2  # 20% jitter
        )

        delays = [handler.calculate_delay(1, config) for _ in range(20)]

        # With 20% jitter, delays should be between 8 and 12
        for delay in delays:
            assert 8.0 <= delay <= 12.0

        # Should have variance
        assert len(set(round(d, 1) for d in delays)) > 1


class TestRetryHandlerExecution:
    """Test retry handler execution logic."""

    @pytest.fixture
    def handler(self, temp_dir):
        """Create retry handler with temp DB."""
        from core.retry_handler import RetryHandler
        db_path = str(temp_dir / "test_retry.db")
        return RetryHandler(db_path=db_path)

    @pytest.mark.asyncio
    async def test_execute_async_success(self, handler):
        """Async execution succeeds on first try."""
        async def success():
            return "result"

        result = await handler.execute_async(success)
        assert result == "result"
        assert handler.stats["total_successes"] == 1

    @pytest.mark.asyncio
    async def test_execute_async_with_retries(self, handler):
        """Async execution retries and succeeds."""
        from core.retry_handler import RetryConfig, RetryStrategy

        call_count = 0

        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Fail")
            return "success"

        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.FIXED,
            base_delay=0.01
        )

        result = await handler.execute_async(fails_twice, config=config)
        assert result == "success"
        assert call_count == 3

    def test_execute_sync_success(self, handler):
        """Sync execution succeeds."""
        def success():
            return "sync result"

        result = handler.execute(success)
        assert result == "sync result"

    def test_execute_sync_with_retries(self, handler):
        """Sync execution retries and succeeds."""
        from core.retry_handler import RetryConfig, RetryStrategy

        call_count = 0

        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Sync fail")
            return "sync success"

        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.FIXED,
            base_delay=0.01
        )

        result = handler.execute(fails_twice, config=config)
        assert result == "sync success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_respected(self, handler):
        """Max attempts limit is respected."""
        from core.retry_handler import RetryConfig, RetryExhaustedError

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(ConnectionError):
            await handler.execute_async(always_fails, config=config)

        assert call_count == 3
        assert handler.stats["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_non_retryable_exception_stops_immediately(self, handler):
        """Non-retryable exceptions stop retry loop immediately."""
        from core.retry_handler import RetryConfig

        call_count = 0

        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        config = RetryConfig(
            max_attempts=5,
            retryable_exceptions=(ConnectionError,),
            non_retryable_exceptions=(ValueError,),
            base_delay=0.01
        )

        with pytest.raises(ValueError):
            await handler.execute_async(raises_value_error, config=config)

        # Only one attempt for non-retryable
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self, handler):
        """On retry callback is called."""
        from core.retry_handler import RetryConfig

        retry_callbacks = []

        def on_retry(attempt, max_attempts, error):
            retry_callbacks.append((attempt, max_attempts, str(error)))

        async def fails_twice():
            if len(retry_callbacks) < 2:
                raise ConnectionError("Fail")
            return "success"

        config = RetryConfig(
            max_attempts=5,
            base_delay=0.01,
            on_retry=on_retry
        )

        await handler.execute_async(fails_twice, config=config)

        assert len(retry_callbacks) == 2
        assert retry_callbacks[0][0] == 1  # First retry
        assert retry_callbacks[1][0] == 2  # Second retry


class TestRetryHandlerStatistics:
    """Test retry handler statistics tracking."""

    @pytest.fixture
    def handler(self, temp_dir):
        """Create retry handler with temp DB."""
        from core.retry_handler import RetryHandler
        db_path = str(temp_dir / "test_retry.db")
        return RetryHandler(db_path=db_path)

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, handler):
        """Statistics are tracked correctly."""
        from core.retry_handler import RetryConfig

        config = RetryConfig(max_attempts=2, base_delay=0.01)

        # Success
        async def success():
            return "ok"
        await handler.execute_async(success, config=config)

        # Failure after retries
        async def fail():
            raise ConnectionError("Fail")

        try:
            await handler.execute_async(fail, config=config)
        except:
            pass

        stats = handler.get_statistics()
        assert stats["total_successes"] == 1
        assert stats["total_failures"] == 1
        assert stats["total_retries"] >= 1


# =============================================================================
# Test Circuit Breaker Integration with Retries
# =============================================================================

class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with retry logic."""

    @pytest.fixture
    def handler(self, temp_dir):
        """Create retry handler with temp DB."""
        from core.retry_handler import RetryHandler
        db_path = str(temp_dir / "test_retry.db")
        return RetryHandler(db_path=db_path)

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, handler):
        """Circuit breaker opens after repeated failures."""
        from core.retry_handler import RetryConfig, CircuitBreakerOpenError

        config = RetryConfig(max_attempts=1, base_delay=0.01)

        async def fail():
            raise ConnectionError("Service down")

        # Trigger failures to open circuit
        breaker = handler.get_circuit_breaker(
            "test_service",
            failure_threshold=3,
            cooldown_seconds=60
        )

        for _ in range(3):
            try:
                await handler.execute_async(
                    fail,
                    config=config,
                    circuit_breaker_name="test_service"
                )
            except ConnectionError:
                pass

        # Circuit should be open
        assert breaker.state == "open"

        # Next call should fail with circuit breaker error
        with pytest.raises(CircuitBreakerOpenError):
            await handler.execute_async(
                fail,
                config=config,
                circuit_breaker_name="test_service"
            )

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers(self, handler):
        """Circuit breaker recovers after cooldown and multiple successes."""
        from core.retry_handler import RetryConfig

        config = RetryConfig(max_attempts=1, base_delay=0.01)

        # Create breaker with short cooldown and success_threshold=1
        breaker = handler.get_circuit_breaker(
            "recovering_service",
            failure_threshold=2,
            success_threshold=1,  # Only need 1 success to close
            cooldown_seconds=0.1
        )

        async def fail():
            raise ConnectionError("Temp failure")

        async def success():
            return "recovered"

        # Trigger failures
        for _ in range(2):
            try:
                await handler.execute_async(
                    fail,
                    config=config,
                    circuit_breaker_name="recovering_service"
                )
            except ConnectionError:
                pass

        assert breaker.state == "open"

        # Wait for cooldown
        await asyncio.sleep(0.15)

        # Should allow attempt (half-open) and close on success
        result = await handler.execute_async(
            success,
            config=config,
            circuit_breaker_name="recovering_service"
        )

        assert result == "recovered"
        assert breaker.state == "closed"

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self, handler):
        """Retries work with circuit breaker."""
        from core.retry_handler import RetryConfig

        config = RetryConfig(max_attempts=5, base_delay=0.01)

        call_count = 0

        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Not yet")
            return "success"

        # Create breaker with high threshold
        handler.get_circuit_breaker(
            "retry_with_cb",
            failure_threshold=10
        )

        result = await handler.execute_async(
            eventually_succeeds,
            config=config,
            circuit_breaker_name="retry_with_cb"
        )

        assert result == "success"
        assert call_count == 3


class TestCircuitBreakerFromReliability:
    """Test circuit breaker from core/reliability/circuit_breaker.py."""

    def test_circuit_breaker_initial_state(self):
        """Circuit breaker starts closed."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="test")
        assert cb.state == CircuitState.CLOSED

    def test_circuit_opens_after_threshold(self):
        """Circuit opens after failure threshold."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpen

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name="threshold_test")

        def failing():
            raise ConnectionError("Service down")

        for _ in range(3):
            try:
                cb.call(failing)
            except ConnectionError:
                pass

        assert cb.state == CircuitState.OPEN

        # Should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            cb.call(failing)

    def test_circuit_breaker_decorator(self):
        """Test circuit_breaker decorator."""
        from core.reliability.circuit_breaker import circuit_breaker, CircuitBreakerOpen

        call_count = 0

        @circuit_breaker(failure_threshold=2, recovery_timeout=60)
        def decorated_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Decorated failure")

        # Trigger failures
        for _ in range(2):
            try:
                decorated_func()
            except ConnectionError:
                pass

        # Should be open now
        with pytest.raises(CircuitBreakerOpen):
            decorated_func()

        assert call_count == 2

    def test_circuit_breaker_get_status(self):
        """Circuit breaker returns status dict."""
        from core.reliability.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="status_test")

        status = cb.get_status()

        assert "name" in status
        assert "state" in status
        assert "failures" in status
        assert "successes" in status


# =============================================================================
# Test Timeout Handling During Retries
# =============================================================================

class TestTimeoutHandling:
    """Test timeout handling during retry operations."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self):
        """Timeout errors trigger retries."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=[TimeoutError, asyncio.TimeoutError]
        ))
        async def times_out_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError("Request timed out")
            return "eventually succeeded"

        result = await times_out_twice()
        assert result == "eventually succeeded"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_in_backoff_module(self):
        """Timeout handling in backoff module."""
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        call_count = 0

        async def timeout_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timed out")
            return "success after timeout"

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=3,
            retryable_exceptions=[TimeoutError]
        )

        result = await retry_with_backoff(timeout_then_success, config=config)
        assert result == "success after timeout"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_error_is_retryable(self):
        """Test that TimeoutError can be configured as retryable."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=[TimeoutError]
        ))
        async def operation_with_timeout():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Operation timed out")
            return "completed"

        result = await operation_with_timeout()
        assert result == "completed"
        assert call_count == 2


# =============================================================================
# Test Retry Policy (core/resilience/retry.py)
# =============================================================================

class TestRetryPolicy:
    """Test RetryPolicy class from core/resilience/retry.py."""

    def test_default_policy(self):
        """RetryPolicy has sensible defaults."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter is True

    def test_get_delay_exponential(self):
        """get_delay calculates exponential backoff."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=100.0,
            jitter=False
        )

        # delay = base_delay * exponential_base^(attempt-1)
        assert policy.get_delay(1) == 1.0    # 1 * 2^0
        assert policy.get_delay(2) == 2.0    # 1 * 2^1
        assert policy.get_delay(3) == 4.0    # 1 * 2^2
        assert policy.get_delay(4) == 8.0    # 1 * 2^3

    def test_get_delay_max_cap(self):
        """get_delay caps at max_delay."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            base_delay=10.0,
            exponential_base=2.0,
            max_delay=50.0,
            jitter=False
        )

        # Attempt 10: 10 * 2^9 = 5120, capped at 50
        assert policy.get_delay(10) == 50.0

    def test_get_delay_with_jitter(self):
        """get_delay adds jitter."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            base_delay=10.0,
            jitter=True,
            jitter_factor=0.5
        )

        delays = [policy.get_delay(1) for _ in range(20)]

        # With 50% jitter, delays should be between 5 and 15
        for delay in delays:
            assert 5.0 <= delay <= 15.0

        # Should have variance
        assert len(set(round(d, 1) for d in delays)) > 1

    def test_should_retry_retryable_exception(self):
        """should_retry returns True for retryable exceptions."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[ConnectionError, TimeoutError]
        )

        assert policy.should_retry(ConnectionError("test")) is True
        assert policy.should_retry(TimeoutError("test")) is True

    def test_should_retry_non_retryable_exception(self):
        """should_retry returns False for non-retryable exceptions."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[ConnectionError],
            non_retryable_exceptions=[KeyboardInterrupt, SystemExit, ValueError]
        )

        assert policy.should_retry(ValueError("test")) is False
        assert policy.should_retry(KeyboardInterrupt()) is False
        assert policy.should_retry(SystemExit()) is False

    def test_should_retry_non_retryable_takes_precedence(self):
        """Non-retryable exceptions take precedence."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[Exception],  # All exceptions retryable
            non_retryable_exceptions=[ValueError]  # Except ValueError
        )

        assert policy.should_retry(ValueError("test")) is False
        assert policy.should_retry(RuntimeError("test")) is True


class TestRetryDecorator:
    """Additional tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_retry_preserves_function_metadata(self):
        """Retry decorator preserves function name and docstring."""
        from core.resilience.retry import retry, RetryPolicy

        @retry(policy=RetryPolicy(max_attempts=2))
        async def documented_function():
            """This is the docstring."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."

    @pytest.mark.asyncio
    async def test_retry_with_on_retry_callback(self):
        """on_retry callback is invoked on each retry."""
        from core.resilience.retry import retry, RetryPolicy

        callbacks = []

        def on_retry_callback(attempt, exception, delay):
            callbacks.append({
                "attempt": attempt,
                "exception": str(exception),
                "delay": delay
            })

        policy = RetryPolicy(
            max_attempts=3,
            base_delay=0.01,
            jitter=False,
            on_retry=on_retry_callback
        )

        call_count = 0

        @retry(policy=policy)
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"Attempt {call_count}")
            return "success"

        await fails_twice()

        assert len(callbacks) == 2
        assert callbacks[0]["attempt"] == 1
        assert "Attempt 1" in callbacks[0]["exception"]

    def test_sync_retry_decorator(self):
        """Sync function retry works."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.01))
        def sync_fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Sync fail")
            return "sync success"

        result = sync_fails_twice()
        assert result == "sync success"
        assert call_count == 3


class TestRetryContext:
    """Test RetryContext for manual retry control."""

    @pytest.mark.asyncio
    async def test_retry_context_success(self):
        """RetryContext tracks success."""
        from core.resilience.retry import RetryContext, RetryPolicy

        ctx = RetryContext(policy=RetryPolicy(max_attempts=3))

        async with ctx:
            while ctx.should_continue():
                try:
                    result = "success"
                    ctx.success()
                    break
                except Exception as e:
                    await ctx.failed(e)

        assert ctx._succeeded is True

    @pytest.mark.asyncio
    async def test_retry_context_exhausted(self):
        """RetryContext tracks exhaustion."""
        from core.resilience.retry import RetryContext, RetryPolicy, RetryExhausted

        ctx = RetryContext(policy=RetryPolicy(max_attempts=2, base_delay=0.01))

        with pytest.raises(RetryExhausted):
            async with ctx:
                while ctx.should_continue():
                    try:
                        raise ConnectionError("Always fails")
                    except Exception as e:
                        await ctx.failed(e)


# =============================================================================
# Test Error Recovery (core/errors/recovery.py)
# =============================================================================

class TestRecoveryStrategy:
    """Test RecoveryStrategy class."""

    @pytest.mark.asyncio
    async def test_retry_strategy(self):
        """RecoveryStrategy.retry with async function."""
        from core.errors.recovery import RecoveryStrategy

        call_count = 0

        async def eventually_works():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Not yet")
            return "worked"

        result = await RecoveryStrategy.retry(eventually_works, max_attempts=5, delay=0.01)
        assert result == "worked"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fallback_strategy(self):
        """RecoveryStrategy.fallback uses fallback on failure."""
        from core.errors.recovery import RecoveryStrategy

        async def primary_fails():
            raise ConnectionError("Primary failed")

        async def fallback_works():
            return "fallback result"

        result = await RecoveryStrategy.fallback(primary_fails, fallback_works)
        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_timeout_strategy(self):
        """RecoveryStrategy.timeout raises on timeout."""
        from core.errors.recovery import RecoveryStrategy

        async def slow_operation():
            await asyncio.sleep(10)
            return "too slow"

        with pytest.raises(TimeoutError, match="timed out"):
            await RecoveryStrategy.timeout(slow_operation, seconds=0.05)

    @pytest.mark.asyncio
    async def test_bulkhead_strategy(self):
        """RecoveryStrategy.bulkhead limits concurrency."""
        from core.errors.recovery import RecoveryStrategy

        semaphore = asyncio.Semaphore(2)
        concurrent_calls = 0
        max_concurrent = 0

        async def track_concurrency():
            nonlocal concurrent_calls, max_concurrent
            concurrent_calls += 1
            max_concurrent = max(max_concurrent, concurrent_calls)
            await asyncio.sleep(0.1)
            concurrent_calls -= 1
            return "done"

        # Run 5 calls with semaphore of 2
        results = await asyncio.gather(*[
            RecoveryStrategy.bulkhead(track_concurrency, semaphore)
            for _ in range(5)
        ])

        assert all(r == "done" for r in results)
        assert max_concurrent <= 2


# =============================================================================
# Test Bot Error Recovery (core/bot/error_recovery.py)
# =============================================================================

class TestBotErrorHandler:
    """Test BotErrorHandler class."""

    @pytest.mark.asyncio
    async def test_error_classification(self):
        """Errors are classified correctly."""
        from core.bot.error_recovery import classify_error, ErrorSeverity

        assert classify_error(TimeoutError("test")) == ErrorSeverity.LOW
        assert classify_error(ConnectionError("test")) == ErrorSeverity.MEDIUM
        assert classify_error(PermissionError("test")) == ErrorSeverity.HIGH

    @pytest.mark.asyncio
    async def test_error_handler_low_severity(self):
        """Low severity errors get immediate retry."""
        from core.bot.error_recovery import (
            BotErrorHandler, ErrorContext, ErrorSeverity, RecoveryAction
        )

        handler = BotErrorHandler()
        context = ErrorContext(
            error=TimeoutError("test"),
            severity=ErrorSeverity.LOW,
            bot_type="telegram",
            attempt=1,
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.should_retry is True
        assert result.action == RecoveryAction.RETRY
        assert result.delay_seconds == 0.5

    @pytest.mark.asyncio
    async def test_error_handler_medium_severity(self):
        """Medium severity errors get exponential backoff."""
        from core.bot.error_recovery import (
            BotErrorHandler, ErrorContext, ErrorSeverity, RecoveryAction
        )

        handler = BotErrorHandler()
        context = ErrorContext(
            error=ConnectionError("test"),
            severity=ErrorSeverity.MEDIUM,
            bot_type="twitter",
            attempt=2,
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.should_retry is True
        assert result.action == RecoveryAction.RETRY
        # Exponential: 2^2 = 4
        assert result.delay_seconds == 4.0

    @pytest.mark.asyncio
    async def test_error_handler_max_retries_exhausted(self):
        """Max retries exhausted returns appropriate action."""
        from core.bot.error_recovery import (
            BotErrorHandler, ErrorContext, ErrorSeverity, RecoveryAction
        )

        handler = BotErrorHandler()
        context = ErrorContext(
            error=TimeoutError("test"),
            severity=ErrorSeverity.LOW,
            bot_type="telegram",
            attempt=3,
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.should_retry is False
        assert result.action == RecoveryAction.SKIP


class TestBotCircuitBreaker:
    """Test bot circuit breaker."""

    def test_bot_circuit_breaker_opens(self):
        """Bot circuit breaker opens after threshold."""
        from core.bot.error_recovery import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        for _ in range(3):
            cb.record_failure()

        assert cb.is_open is True
        assert cb.is_closed is False

    def test_bot_circuit_breaker_recovers(self):
        """Bot circuit breaker recovers."""
        from core.bot.error_recovery import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        # Should be half-open now
        assert cb.is_open is False  # Allows one request

        # Success closes it
        cb.record_success()
        assert cb.is_closed is True


class TestWithErrorRecoveryDecorator:
    """Test with_error_recovery decorator."""

    @pytest.mark.asyncio
    async def test_decorator_retries_on_failure(self):
        """Decorator retries on transient failures."""
        from core.bot.error_recovery import with_error_recovery

        call_count = 0

        @with_error_recovery("telegram", max_attempts=3)
        async def handler():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Transient error")
            return "success"

        result = await handler()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_raises_original_after_max_attempts(self):
        """Decorator raises original exception after max attempts."""
        from core.bot.error_recovery import with_error_recovery

        call_count = 0

        @with_error_recovery("twitter", max_attempts=2)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        # The decorator re-raises the original exception after max attempts
        with pytest.raises(ConnectionError, match="Always fails"):
            await always_fails()

        assert call_count == 2


# =============================================================================
# Integration Tests: Multiple Components Together
# =============================================================================

class TestRetryCircuitBreakerIntegration:
    """Test retry and circuit breaker working together."""

    @pytest.mark.asyncio
    async def test_retry_with_high_threshold_circuit_breaker(self):
        """Retries complete before circuit opens when threshold is high."""
        from core.resilience.retry import retry, RetryPolicy
        from core.reliability.circuit_breaker import CircuitBreaker

        # High threshold so circuit won't open during test
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=60, name="high_threshold_test")
        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=5, base_delay=0.01))
        async def protected_operation():
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                cb._on_failure()  # Record failure
                raise ConnectionError("Service temporarily unavailable")

            cb._on_success()
            return "success"

        result = await protected_operation()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_opens_stops_retries(self):
        """When circuit opens, retries stop."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60, name="stops_retries_test")
        call_count = 0

        async def operation_with_cb():
            nonlocal call_count
            call_count += 1

            # Manually check circuit
            if cb.state.value == "open":
                raise CircuitBreakerOpen("stops_retries_test")

            # This always fails, which should open circuit
            try:
                raise ConnectionError("Always fails")
            finally:
                cb._on_failure()

        # First 2 calls fail normally
        for _ in range(2):
            try:
                await operation_with_cb()
            except ConnectionError:
                pass

        # Circuit should be open
        assert cb.state.value == "open"

        # Next call should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            await operation_with_cb()

        # Call count stays at 2 because circuit open check happens first
        assert call_count == 3  # 2 failures + 1 circuit check


# =============================================================================
# Performance and Edge Case Tests
# =============================================================================

class TestRetryPerformance:
    """Test retry performance characteristics."""

    @pytest.mark.asyncio
    async def test_no_delay_on_success(self):
        """No delay is added when function succeeds immediately."""
        from core.resilience.retry import retry, RetryPolicy

        start = time.time()

        @retry(policy=RetryPolicy(max_attempts=5, base_delay=10.0))
        async def instant_success():
            return "fast"

        await instant_success()
        elapsed = time.time() - start

        # Should be much less than base_delay
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_total_delay_accumulates(self):
        """Total delay accumulates across retries."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(
            max_attempts=3,
            base_delay=0.1,
            exponential_base=2.0,
            jitter=False
        ))
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Fail")
            return "success"

        start = time.time()
        await fails_twice()
        elapsed = time.time() - start

        # Total delay: 0.1 + 0.2 = 0.3
        assert 0.25 < elapsed < 0.5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_max_attempts_one(self):
        """max_attempts=1 means no retries."""
        from core.resilience.retry import retry, RetryPolicy, RetryExhausted

        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=1, base_delay=0.01))
        async def single_attempt():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Single failure")

        with pytest.raises(RetryExhausted):
            await single_attempt()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_zero_base_delay(self):
        """Zero base delay is handled."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.0, jitter=False))
        async def quick_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Quick")
            return "done"

        start = time.time()
        await quick_retry()
        elapsed = time.time() - start

        # Should be very fast with no delay
        assert elapsed < 0.1
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_empty_retryable_exceptions(self):
        """Empty retryable exceptions means nothing is retried."""
        from core.resilience.retry import retry, RetryPolicy

        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=5, retryable_exceptions=[]))
        async def not_retried():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Not retryable")

        with pytest.raises(ConnectionError):
            await not_retried()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_retries(self):
        """Multiple concurrent retry operations work independently."""
        from core.resilience.retry import retry, RetryPolicy

        call_counts = {"a": 0, "b": 0}

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.01))
        async def operation_a():
            call_counts["a"] += 1
            if call_counts["a"] < 2:
                raise ConnectionError("A fails")
            return "A done"

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.01))
        async def operation_b():
            call_counts["b"] += 1
            if call_counts["b"] < 3:
                raise ConnectionError("B fails")
            return "B done"

        results = await asyncio.gather(operation_a(), operation_b())

        assert results == ["A done", "B done"]
        assert call_counts["a"] == 2
        assert call_counts["b"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
