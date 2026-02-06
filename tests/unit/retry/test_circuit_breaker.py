"""
Tests for core/retry/circuit_breaker.py

Tests the CircuitBreaker class and its states.
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch


class TestCircuitBreakerStates:
    """Tests for circuit breaker state enum."""

    def test_states_exist(self):
        """All required states should be defined."""
        from core.retry.circuit_breaker import CircuitState

        assert hasattr(CircuitState, 'CLOSED')
        assert hasattr(CircuitState, 'OPEN')
        assert hasattr(CircuitState, 'HALF_OPEN')

    def test_state_values(self):
        """States should have string values."""
        from core.retry.circuit_breaker import CircuitState

        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerInitialization:
    """Tests for CircuitBreaker initialization."""

    def test_default_initialization(self):
        """Should have sensible defaults."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test")

        assert cb.name == "test"
        assert cb.failure_threshold == 5
        assert cb.success_threshold == 2
        assert cb.recovery_timeout == 30.0
        assert cb.state == CircuitState.CLOSED

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(
            name="custom",
            failure_threshold=3,
            success_threshold=1,
            recovery_timeout=60.0
        )

        assert cb.name == "custom"
        assert cb.failure_threshold == 3
        assert cb.success_threshold == 1
        assert cb.recovery_timeout == 60.0


class TestCircuitBreakerIsAvailable:
    """Tests for is_available() method."""

    def test_is_available_when_closed(self):
        """Should be available when closed."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test")

        assert cb.is_available() is True

    def test_is_not_available_when_open(self):
        """Should not be available when open."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2)

        # Trip the circuit
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_is_available_when_half_open(self):
        """Should be available when half-open (for testing recovery)."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)

        # Trip the circuit
        cb.record_failure()
        cb.record_failure()

        # Wait for timeout
        time.sleep(0.02)

        # Should transition to half-open when checked
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN


class TestCircuitBreakerRecordSuccess:
    """Tests for record_success() method."""

    def test_record_success_stays_closed(self):
        """Success in closed state should stay closed."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test")

        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_record_success_resets_failure_count(self):
        """Success should reset consecutive failure count."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=5)

        # Accumulate some failures
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        # Now succeed
        cb.record_success()

        # More failures shouldn't trip circuit (count reset)
        cb.record_failure()
        cb.record_failure()

        assert cb.stats.consecutive_failures == 2

    def test_record_success_in_half_open(self):
        """Success in half-open should eventually close circuit."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2, success_threshold=2, recovery_timeout=0.01)

        # Trip circuit
        cb.record_failure()
        cb.record_failure()

        # Wait for half-open
        time.sleep(0.02)
        cb.is_available()  # Trigger transition

        # Record successes
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRecordFailure:
    """Tests for record_failure() method."""

    def test_record_failure_increments_count(self):
        """Failure should increment consecutive failure count."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test")

        cb.record_failure()
        assert cb.stats.consecutive_failures == 1

        cb.record_failure()
        assert cb.stats.consecutive_failures == 2

    def test_record_failure_opens_circuit(self):
        """Enough failures should open circuit."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_record_failure_in_half_open_reopens(self):
        """Failure in half-open should reopen circuit."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)

        # Trip circuit
        cb.record_failure()
        cb.record_failure()

        # Wait for half-open
        time.sleep(0.02)
        cb.is_available()

        # Fail again
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerStats:
    """Tests for circuit breaker statistics."""

    def test_stats_track_calls(self):
        """Should track total, successful, and failed calls."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=10)

        cb.record_success()
        cb.record_success()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()

        assert cb.stats.total_calls == 5
        assert cb.stats.successful_calls == 3
        assert cb.stats.failed_calls == 2

    def test_stats_failure_rate(self):
        """Should calculate failure rate."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=10)

        cb.record_success()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()

        assert cb.stats.failure_rate == 0.5

    def test_stats_track_state_changes(self):
        """Should track state transitions."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)

        # Trip circuit
        cb.record_failure()
        cb.record_failure()

        # Wait and recover
        time.sleep(0.02)
        cb.is_available()

        # Close circuit
        cb.record_success()
        cb.record_success()

        # Should have recorded: CLOSED->OPEN, OPEN->HALF_OPEN, HALF_OPEN->CLOSED
        assert len(cb.stats.state_changes) >= 2

    def test_stats_to_dict(self):
        """Stats should be serializable to dict."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_failure()

        stats_dict = cb.stats.to_dict()

        assert "total_calls" in stats_dict
        assert "failure_rate" in stats_dict
        assert stats_dict["total_calls"] == 2


class TestCircuitBreakerReset:
    """Tests for circuit breaker reset."""

    def test_reset_closes_circuit(self):
        """Reset should close an open circuit."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=2)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Reset it
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_stats(self):
        """Reset should clear statistics."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=10)

        cb.record_success()
        cb.record_failure()

        cb.reset()

        assert cb.stats.total_calls == 0
        assert cb.stats.consecutive_failures == 0


class TestCircuitBreakerForceOpen:
    """Tests for force_open() method."""

    def test_force_open(self):
        """Should allow manual circuit opening."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test")

        cb.force_open()

        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False


class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry."""

    def test_get_or_create(self):
        """Should get existing or create new circuit."""
        from core.retry.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("service_a")
        cb2 = registry.get_or_create("service_a")

        assert cb1 is cb2  # Same instance

    def test_get_nonexistent(self):
        """Should return None for nonexistent circuit."""
        from core.retry.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_list_all(self):
        """Should list all registered circuits."""
        from core.retry.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()

        registry.get_or_create("service_a")
        registry.get_or_create("service_b")

        names = registry.list_all()

        assert "service_a" in names
        assert "service_b" in names

    def test_reset_all(self):
        """Should reset all circuits."""
        from core.retry.circuit_breaker import CircuitBreakerRegistry, CircuitState

        registry = CircuitBreakerRegistry()

        cb_a = registry.get_or_create("service_a", failure_threshold=1)
        cb_b = registry.get_or_create("service_b", failure_threshold=1)

        # Open both
        cb_a.record_failure()
        cb_b.record_failure()

        assert cb_a.state == CircuitState.OPEN
        assert cb_b.state == CircuitState.OPEN

        # Reset all
        registry.reset_all()

        assert cb_a.state == CircuitState.CLOSED
        assert cb_b.state == CircuitState.CLOSED

    def test_get_all_status(self):
        """Should get status of all circuits."""
        from core.retry.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()

        registry.get_or_create("service_a")
        registry.get_or_create("service_b")

        status = registry.get_all_status()

        assert "service_a" in status
        assert "service_b" in status
        assert "state" in status["service_a"]


class TestCircuitBreakerCallbacks:
    """Tests for circuit breaker callbacks."""

    def test_on_open_callback(self):
        """Should call on_open when circuit opens."""
        from core.retry.circuit_breaker import CircuitBreaker

        on_open_called = []

        def on_open():
            on_open_called.append(True)

        cb = CircuitBreaker("test", failure_threshold=2, on_open=on_open)

        cb.record_failure()
        cb.record_failure()

        assert len(on_open_called) == 1

    def test_on_close_callback(self):
        """Should call on_close when circuit closes."""
        from core.retry.circuit_breaker import CircuitBreaker

        on_close_called = []

        def on_close():
            on_close_called.append(True)

        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            success_threshold=1,
            recovery_timeout=0.01,
            on_close=on_close
        )

        # Open circuit
        cb.record_failure()

        # Wait and recover
        time.sleep(0.02)
        cb.is_available()

        # Close it
        cb.record_success()

        assert len(on_close_called) == 1

    def test_on_half_open_callback(self):
        """Should call on_half_open when transitioning."""
        from core.retry.circuit_breaker import CircuitBreaker

        on_half_open_called = []

        def on_half_open():
            on_half_open_called.append(True)

        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.01,
            on_half_open=on_half_open
        )

        # Open circuit
        cb.record_failure()

        # Wait and check (triggers half-open)
        time.sleep(0.02)
        cb.is_available()

        assert len(on_half_open_called) == 1


class TestCircuitBreakerAsync:
    """Tests for async circuit breaker operations."""

    @pytest.mark.asyncio
    async def test_async_call(self):
        """Should support async call method."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test")

        async def async_fn():
            await asyncio.sleep(0.01)
            return "success"

        result = await cb.call(async_fn)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_call_records_success(self):
        """Async call should record success."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test")

        async def async_fn():
            return "ok"

        await cb.call(async_fn)

        assert cb.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_async_call_records_failure(self):
        """Async call should record failure."""
        from core.retry.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test", failure_threshold=10)

        async def async_fail():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await cb.call(async_fail)

        assert cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_async_call_rejects_when_open(self):
        """Async call should reject when circuit open."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitOpenError

        cb = CircuitBreaker("test", failure_threshold=1)

        cb.record_failure()

        async def async_fn():
            return "should not reach"

        with pytest.raises(CircuitOpenError):
            await cb.call(async_fn)


class TestCircuitBreakerExcludedExceptions:
    """Tests for excluded exceptions."""

    def test_excluded_exceptions_not_counted(self):
        """Excluded exceptions should not count as failures."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            excluded_exceptions=[KeyboardInterrupt, SystemExit]
        )

        # These should not count
        cb.record_failure(KeyboardInterrupt())
        cb.record_failure(KeyboardInterrupt())
        cb.record_failure(KeyboardInterrupt())

        # Circuit should still be closed
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.consecutive_failures == 0

    def test_non_excluded_exceptions_counted(self):
        """Non-excluded exceptions should count as failures."""
        from core.retry.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            "test",
            failure_threshold=2,
            excluded_exceptions=[KeyboardInterrupt]
        )

        cb.record_failure(ValueError("error"))
        cb.record_failure(RuntimeError("error"))

        assert cb.state == CircuitState.OPEN
