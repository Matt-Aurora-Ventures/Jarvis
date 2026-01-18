"""
JARVIS Circuit Breaker Tests

Tests circuit breaker behavior and state transitions.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failures exceeded threshold, requests fail immediately
- HALF_OPEN: Testing if service recovered

Usage:
    pytest tests/resilience/test_circuit_breaker.py -v
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest


# Import the actual circuit breaker if available
try:
    from core.resilience.circuit_breaker import (
        CircuitBreaker,
        CircuitState,
        CircuitOpenError,
        CircuitStats,
        get_circuit_breaker,
        circuit_breaker,
    )
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

    # Minimal implementation for testing
    class CircuitState(str, Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"

    class CircuitOpenError(Exception):
        def __init__(self, name: str, remaining_seconds: float):
            self.name = name
            self.remaining_seconds = remaining_seconds
            super().__init__(f"Circuit '{name}' is open")


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: CircuitState
    to_state: CircuitState
    timestamp: float
    reason: str = ""


class CircuitBreakerTestHarness:
    """Test harness for circuit breaker testing."""

    def __init__(self, failure_threshold: int = 3, timeout: float = 1.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.transitions: List[StateTransition] = []
        self._opened_at: Optional[float] = None

    def _transition(self, new_state: CircuitState, reason: str = ""):
        """Record a state transition."""
        self.transitions.append(StateTransition(
            from_state=self.state,
            to_state=new_state,
            timestamp=time.time(),
            reason=reason,
        ))
        self.state = new_state

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()

    def record_success(self):
        """Record a successful call."""
        self.success_count += 1
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED, "Recovery confirmed")

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition(CircuitState.OPEN, f"Failures: {self.failure_count}")
        elif self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN, "Recovery failed")

    def should_allow_request(self) -> bool:
        """Determine if a request should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._opened_at and time.time() - self._opened_at >= self.timeout:
                self._transition(CircuitState.HALF_OPEN, "Timeout elapsed")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    async def execute(self, func: Callable) -> Any:
        """Execute a function through the circuit breaker."""
        if not self.should_allow_request():
            raise CircuitOpenError(
                "test_circuit",
                self.timeout - (time.time() - (self._opened_at or 0)),
            )

        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


# =============================================================================
# Circuit Breaker Test Scenarios
# =============================================================================

class TestCircuitBreakerStates:
    """Tests for circuit breaker state machine."""

    @pytest.fixture
    def breaker(self):
        return CircuitBreakerTestHarness(failure_threshold=3, timeout=0.5)

    def test_initial_state_closed(self, breaker: CircuitBreakerTestHarness):
        """Circuit breaker starts in CLOSED state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.should_allow_request()

    @pytest.mark.asyncio
    async def test_closed_allows_requests(self, breaker: CircuitBreakerTestHarness):
        """CLOSED state allows all requests."""
        call_count = 0

        async def mock_call():
            nonlocal call_count
            call_count += 1
            return "success"

        for _ in range(5):
            result = await breaker.execute(mock_call)
            assert result == "success"

        assert call_count == 5
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self, breaker: CircuitBreakerTestHarness):
        """Circuit opens after failure threshold is reached."""
        async def failing_call():
            raise Exception("Service unavailable")

        # First failures
        for _ in range(3):
            with pytest.raises(Exception, match="Service unavailable"):
                await breaker.execute(failing_call)

        assert breaker.state == CircuitState.OPEN
        assert len(breaker.transitions) == 1
        assert breaker.transitions[0].to_state == CircuitState.OPEN

        print(f"\n[CLOSED -> OPEN Transition]")
        print(f"  Failures before open: {breaker.failure_threshold}")
        print(f"  Transition reason: {breaker.transitions[0].reason}")

    @pytest.mark.asyncio
    async def test_open_rejects_requests(self, breaker: CircuitBreakerTestHarness):
        """OPEN state rejects all requests immediately."""
        # Force open state
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        async def any_call():
            return "should not execute"

        with pytest.raises(CircuitOpenError):
            await breaker.execute(any_call)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, breaker: CircuitBreakerTestHarness):
        """Circuit transitions to HALF_OPEN after timeout."""
        # Force open state
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.6)

        # Should transition to half-open on next request attempt
        assert breaker.should_allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

        print(f"\n[OPEN -> HALF_OPEN Transition]")
        print(f"  Timeout: {breaker.timeout}s")

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self, breaker: CircuitBreakerTestHarness):
        """Success in HALF_OPEN closes the circuit."""
        # Force open state
        for _ in range(3):
            breaker.record_failure()

        # Wait for timeout
        await asyncio.sleep(0.6)
        breaker.should_allow_request()  # Triggers half-open

        assert breaker.state == CircuitState.HALF_OPEN

        # Successful call
        async def success_call():
            return "recovered"

        result = await breaker.execute(success_call)
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

        print(f"\n[HALF_OPEN -> CLOSED Transition]")
        print(f"  Reason: Recovery confirmed")

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, breaker: CircuitBreakerTestHarness):
        """Failure in HALF_OPEN reopens the circuit."""
        # Force open state
        for _ in range(3):
            breaker.record_failure()

        # Wait for timeout
        await asyncio.sleep(0.6)
        breaker.should_allow_request()  # Triggers half-open

        assert breaker.state == CircuitState.HALF_OPEN

        # Failed call
        async def failing_call():
            raise Exception("Still failing")

        with pytest.raises(Exception):
            await breaker.execute(failing_call)

        assert breaker.state == CircuitState.OPEN

        print(f"\n[HALF_OPEN -> OPEN Transition]")
        print(f"  Reason: Recovery failed")


class TestCircuitBreakerStatistics:
    """Tests for circuit breaker statistics tracking."""

    @pytest.fixture
    def breaker(self):
        return CircuitBreakerTestHarness(failure_threshold=3, timeout=1.0)

    @pytest.mark.asyncio
    async def test_success_counter(self, breaker: CircuitBreakerTestHarness):
        """Success counter increments correctly."""
        async def success_call():
            return "ok"

        for _ in range(5):
            await breaker.execute(success_call)

        assert breaker.success_count == 5

    @pytest.mark.asyncio
    async def test_failure_counter(self, breaker: CircuitBreakerTestHarness):
        """Failure counter increments correctly."""
        async def failing_call():
            raise Exception("fail")

        for _ in range(2):
            try:
                await breaker.execute(failing_call)
            except Exception:
                pass

        assert breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_success_resets_failures(self, breaker: CircuitBreakerTestHarness):
        """Success resets failure counter."""
        async def failing_call():
            raise Exception("fail")

        async def success_call():
            return "ok"

        # Record some failures
        for _ in range(2):
            try:
                await breaker.execute(failing_call)
            except Exception:
                pass

        assert breaker.failure_count == 2

        # Success resets
        await breaker.execute(success_call)
        assert breaker.failure_count == 0

    def test_transition_history(self, breaker: CircuitBreakerTestHarness):
        """Transition history is recorded."""
        # Force transitions
        for _ in range(3):
            breaker.record_failure()

        assert len(breaker.transitions) == 1
        assert breaker.transitions[0].from_state == CircuitState.CLOSED
        assert breaker.transitions[0].to_state == CircuitState.OPEN


class TestCircuitBreakerBehavior:
    """Tests for circuit breaker behavioral scenarios."""

    @pytest.fixture
    def breaker(self):
        return CircuitBreakerTestHarness(failure_threshold=5, timeout=0.5)

    @pytest.mark.asyncio
    async def test_intermittent_failures_dont_trip(
        self,
        breaker: CircuitBreakerTestHarness
    ):
        """Intermittent failures with successes don't trip the breaker."""
        async def alternating_call(succeed: bool):
            if succeed:
                return "ok"
            raise Exception("fail")

        # Alternate success/failure
        for i in range(10):
            try:
                await breaker.execute(lambda: alternating_call(i % 2 == 0))
            except Exception:
                pass

        # Should still be closed (failures were reset by successes)
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_gradual_recovery(self, breaker: CircuitBreakerTestHarness):
        """Test gradual recovery with backoff."""
        # Trip the breaker
        for _ in range(5):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        recovery_attempts = 0
        max_attempts = 10
        recovered = False

        while recovery_attempts < max_attempts:
            await asyncio.sleep(0.6)  # Wait for timeout

            if breaker.should_allow_request():
                breaker.record_success()
                recovery_attempts += 1

                if breaker.state == CircuitState.CLOSED:
                    recovered = True
                    break

        print(f"\n[Gradual Recovery Test]")
        print(f"  Recovery attempts: {recovery_attempts}")
        print(f"  Final state: {breaker.state.value}")

        assert recovered

    @pytest.mark.asyncio
    async def test_rapid_succession_failures(self, breaker: CircuitBreakerTestHarness):
        """Rapid failures in succession trip the breaker quickly."""
        async def rapid_fail():
            raise Exception("rapid failure")

        start = time.time()

        for _ in range(5):
            try:
                await breaker.execute(rapid_fail)
            except CircuitOpenError:
                break
            except Exception:
                pass

        elapsed = time.time() - start

        print(f"\n[Rapid Failure Test]")
        print(f"  Time to trip: {elapsed*1000:.2f}ms")
        print(f"  State: {breaker.state.value}")

        assert breaker.state == CircuitState.OPEN
        assert elapsed < 0.1  # Should trip quickly


@pytest.mark.skipif(not CIRCUIT_BREAKER_AVAILABLE, reason="Circuit breaker module not available")
class TestActualCircuitBreaker:
    """Tests using the actual circuit breaker implementation."""

    @pytest.mark.asyncio
    async def test_real_circuit_breaker_closed(self):
        """Test actual circuit breaker in closed state."""
        cb = CircuitBreaker("test_closed", failure_threshold=3)

        assert cb.state == CircuitState.CLOSED

        async def success_op():
            return "success"

        # Successful calls
        for _ in range(5):
            result = await cb.call(success_op)
            assert result == "success"

        assert cb.state == CircuitState.CLOSED
        assert cb.stats.successful_calls == 5

    @pytest.mark.asyncio
    async def test_real_circuit_breaker_opens(self):
        """Test actual circuit breaker opens on failures."""
        cb = CircuitBreaker("test_opens", failure_threshold=3, timeout=0.5)

        async def failing():
            raise Exception("fail")

        # Trigger failures
        for _ in range(3):
            try:
                await cb.call(failing)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN
        assert cb.stats.failed_calls == 3

    @pytest.mark.asyncio
    async def test_real_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""
        call_count = 0

        @circuit_breaker(name="decorator_test", failure_threshold=2)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("fail")
            return "success"

        # First two calls fail
        for _ in range(2):
            try:
                await decorated_func()
            except Exception:
                pass

        # Circuit should be open
        with pytest.raises(CircuitOpenError):
            await decorated_func()


class TestStateTransitionDiagram:
    """Visual test of state transition diagram."""

    def test_all_valid_transitions(self):
        """Document all valid state transitions."""
        valid_transitions = {
            CircuitState.CLOSED: [CircuitState.OPEN],
            CircuitState.OPEN: [CircuitState.HALF_OPEN],
            CircuitState.HALF_OPEN: [CircuitState.CLOSED, CircuitState.OPEN],
        }

        print("\n[Circuit Breaker State Transitions]")
        print("=" * 50)
        for from_state, to_states in valid_transitions.items():
            for to_state in to_states:
                print(f"  {from_state.value:10} -> {to_state.value}")
        print("=" * 50)

        # Verify completeness
        assert len(valid_transitions) == 3
        assert CircuitState.CLOSED in valid_transitions[CircuitState.HALF_OPEN]
        assert CircuitState.OPEN in valid_transitions[CircuitState.HALF_OPEN]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
