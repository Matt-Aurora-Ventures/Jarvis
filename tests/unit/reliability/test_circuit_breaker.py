"""Tests for enhanced circuit breaker.

These tests verify:
- State machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Async support
- Persistence of circuit state
- Health monitoring
- Service-specific breakers
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock


class TestCircuitBreakerStateMachine:
    """Test circuit breaker state transitions."""

    def test_starts_closed(self):
        """Circuit breaker should start in CLOSED state."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=3, timeout=10)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        """Should open after failure_threshold consecutive failures."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=3, timeout=10)

        failing_func = Mock(side_effect=Exception("fail"))

        for i in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_blocks_calls_when_open(self):
        """Should block calls when circuit is OPEN."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpen
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout=60)

        # Force open
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()

        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not execute")

    def test_transitions_to_half_open_after_timeout(self):
        """Should transition to HALF_OPEN after timeout."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout=1)

        # Open the circuit
        failing_func = Mock(side_effect=Exception("fail"))
        with pytest.raises(Exception):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.1)

        # Next call should attempt (half-open)
        success_func = Mock(return_value="success")
        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        """Should reopen if call fails during HALF_OPEN."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout=0.1)

        # Open the circuit
        cb.state = CircuitState.HALF_OPEN

        failing_func = Mock(side_effect=Exception("still failing"))
        with pytest.raises(Exception):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN


class TestAsyncCircuitBreaker:
    """Test async support for circuit breaker."""

    @pytest.mark.asyncio
    async def test_async_call_success(self):
        """Should handle async functions successfully."""
        from core.reliability.circuit_breaker import AsyncCircuitBreaker, CircuitState

        cb = AsyncCircuitBreaker(name="async_test", failure_threshold=3, timeout=10)

        async def async_success():
            return "async_result"

        result = await cb.call(async_success)
        assert result == "async_result"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_async_call_failure(self):
        """Should track failures from async functions."""
        from core.reliability.circuit_breaker import AsyncCircuitBreaker, CircuitState

        cb = AsyncCircuitBreaker(name="async_test", failure_threshold=2, timeout=10)

        async def async_fail():
            raise ValueError("async error")

        for i in range(2):
            with pytest.raises(ValueError):
                await cb.call(async_fail)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_async_decorator(self):
        """Should work as async decorator."""
        from core.reliability.circuit_breaker import async_circuit_breaker

        call_count = 0

        @async_circuit_breaker(failure_threshold=2, timeout=10)
        async def protected_call():
            nonlocal call_count
            call_count += 1
            return f"call_{call_count}"

        result = await protected_call()
        assert result == "call_1"


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry for managing multiple breakers."""

    def test_register_breaker(self):
        """Should register named circuit breakers."""
        from core.reliability.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        registry.register("jupiter", failure_threshold=5, timeout=30)
        registry.register("helius", failure_threshold=3, timeout=60)

        assert registry.get("jupiter") is not None
        assert registry.get("helius") is not None

    def test_get_or_create(self):
        """Should create breaker if not exists."""
        from core.reliability.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        cb = registry.get_or_create("new_service")

        assert cb is not None
        assert cb.name == "new_service"

    def test_get_all_statuses(self):
        """Should return status of all breakers."""
        from core.reliability.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        registry.register("service_a")
        registry.register("service_b")

        statuses = registry.get_all_statuses()
        assert len(statuses) == 2
        assert all(s["state"] == "closed" for s in statuses)

    def test_reset_all(self):
        """Should reset all circuit breakers."""
        from core.reliability.circuit_breaker import CircuitBreakerRegistry, CircuitState

        registry = CircuitBreakerRegistry()
        cb1 = registry.register("service_a")
        cb2 = registry.register("service_b")

        # Force open
        cb1.state = CircuitState.OPEN
        cb2.state = CircuitState.OPEN

        registry.reset_all()

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


class TestCircuitBreakerPersistence:
    """Test circuit breaker state persistence."""

    def test_save_state(self):
        """Should save circuit state to storage."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="persist_test", failure_threshold=3, timeout=60)
        cb.state = CircuitState.OPEN
        cb.failure_count = 5

        state = cb.save_state()

        assert state["name"] == "persist_test"
        assert state["state"] == "open"
        assert state["failure_count"] == 5

    def test_restore_state(self):
        """Should restore circuit state from storage."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        saved_state = {
            "name": "persist_test",
            "state": "open",
            "failure_count": 5,
            "last_failure_time": time.time() - 10,
            "success_count": 100
        }

        cb = CircuitBreaker.from_state(saved_state)

        assert cb.name == "persist_test"
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 5


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics and monitoring."""

    def test_tracks_success_rate(self):
        """Should track success rate."""
        from core.reliability.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="metrics_test")

        for _ in range(8):
            cb.call(lambda: "success")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(Mock(side_effect=Exception("fail")))

        metrics = cb.get_metrics()
        assert metrics["success_count"] == 8
        assert metrics["failure_count"] == 2
        assert 0.7 <= metrics["success_rate"] <= 0.9

    def test_tracks_latency(self):
        """Should track call latency."""
        from core.reliability.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="latency_test")

        def slow_call():
            time.sleep(0.1)
            return "done"

        cb.call(slow_call)

        metrics = cb.get_metrics()
        assert "avg_latency_ms" in metrics
        assert metrics["avg_latency_ms"] >= 100

    def test_tracks_state_transitions(self):
        """Should track state transition history."""
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="transition_test", failure_threshold=1, timeout=0.1)

        # Trigger open
        with pytest.raises(Exception):
            cb.call(Mock(side_effect=Exception("fail")))

        time.sleep(0.2)

        # Trigger close
        cb.call(lambda: "success")

        transitions = cb.get_state_transitions()
        assert len(transitions) >= 2
        assert transitions[-1]["to_state"] == "closed"
