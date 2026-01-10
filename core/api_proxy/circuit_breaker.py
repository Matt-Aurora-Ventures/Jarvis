"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by stopping requests to failing upstreams.

Prompts #45: API Proxy System - Circuit Breaker
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation, requests flow through
    OPEN = "open"           # Failing, requests blocked
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 3      # Successes to close after half-open
    timeout_seconds: float = 30.0   # Time before trying again (half-open)
    half_open_requests: int = 3     # Concurrent requests allowed in half-open


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker"""
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0


class CircuitBreaker:
    """
    Circuit breaker for API calls.

    Prevents cascading failures by:
    1. Tracking failures per upstream
    2. Opening circuit after threshold failures
    3. Testing recovery with half-open state
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitBreakerState.CLOSED
        self._stats = CircuitStats()
        self._last_state_change = time.time()
        self._half_open_count = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit state with automatic transition check"""
        if self._state == CircuitBreakerState.OPEN:
            # Check if timeout elapsed -> transition to half-open
            elapsed = time.time() - self._last_state_change
            if elapsed >= self.config.timeout_seconds:
                self._transition_to(CircuitBreakerState.HALF_OPEN)
        return self._state

    @property
    def stats(self) -> CircuitStats:
        return self._stats

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitBreakerState.OPEN

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        current_state = self.state

        if current_state == CircuitBreakerState.CLOSED:
            return True

        if current_state == CircuitBreakerState.OPEN:
            return False

        # Half-open: allow limited requests
        if current_state == CircuitBreakerState.HALF_OPEN:
            return self._half_open_count < self.config.half_open_requests

        return False

    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with circuit breaker protection"""
        if not self.can_execute():
            raise CircuitOpenError(
                f"Circuit '{self.name}' is open. "
                f"Retry after {self._remaining_timeout():.1f}s"
            )

        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_count += 1

        self._stats.total_requests += 1

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        """Handle successful request"""
        async with self._lock:
            self._stats.total_successes += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = datetime.utcnow()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_count -= 1

                # Check if we should close the circuit
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)

    async def _on_failure(self, error: Exception):
        """Handle failed request"""
        async with self._lock:
            self._stats.total_failures += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = datetime.utcnow()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_count -= 1
                # Any failure in half-open reopens the circuit
                self._transition_to(CircuitBreakerState.OPEN)
                logger.warning(
                    f"Circuit '{self.name}' reopened due to failure: {error}"
                )

            elif self._state == CircuitBreakerState.CLOSED:
                # Check if we should open the circuit
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitBreakerState.OPEN)
                    logger.warning(
                        f"Circuit '{self.name}' opened after "
                        f"{self._stats.consecutive_failures} failures"
                    )

    def _transition_to(self, new_state: CircuitBreakerState):
        """Transition to a new state"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        self._stats.state_changes += 1

        if new_state == CircuitBreakerState.HALF_OPEN:
            self._half_open_count = 0

        if new_state == CircuitBreakerState.CLOSED:
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0

        logger.info(
            f"Circuit '{self.name}' transitioned: {old_state.value} -> {new_state.value}"
        )

    def _remaining_timeout(self) -> float:
        """Get remaining timeout seconds"""
        if self._state != CircuitBreakerState.OPEN:
            return 0
        elapsed = time.time() - self._last_state_change
        return max(0, self.config.timeout_seconds - elapsed)

    def reset(self):
        """Manually reset the circuit breaker"""
        self._state = CircuitBreakerState.CLOSED
        self._stats = CircuitStats()
        self._last_state_change = time.time()
        self._half_open_count = 0
        logger.info(f"Circuit '{self.name}' manually reset")

    def force_open(self):
        """Manually open the circuit"""
        self._transition_to(CircuitBreakerState.OPEN)
        logger.info(f"Circuit '{self.name}' manually opened")

    def to_dict(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_requests": self._stats.total_requests,
                "total_failures": self._stats.total_failures,
                "total_successes": self._stats.total_successes,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "last_failure": (
                    self._stats.last_failure_time.isoformat()
                    if self._stats.last_failure_time else None
                ),
                "last_success": (
                    self._stats.last_success_time.isoformat()
                    if self._stats.last_success_time else None
                ),
                "state_changes": self._stats.state_changes
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds
            },
            "remaining_timeout": self._remaining_timeout()
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open"""
    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name"""
        return self._breakers.get(name)

    def all(self) -> Dict[str, CircuitBreaker]:
        """Get all circuit breakers"""
        return self._breakers.copy()

    def status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        return {
            name: breaker.to_dict()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker from global registry"""
    return _registry.get_or_create(name, config)


def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
):
    """Decorator for circuit breaker protection"""
    def decorator(func):
        breaker = get_circuit_breaker(name, config)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.execute(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, create event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(breaker.execute(func, *args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Testing
if __name__ == "__main__":
    async def test():
        # Create circuit breaker
        cb = CircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=3, timeout_seconds=5)
        )

        # Simulate failures
        async def failing_func():
            raise ValueError("Test failure")

        async def success_func():
            return "success"

        # Test failures
        print("Testing failures...")
        for i in range(5):
            try:
                await cb.execute(failing_func)
            except ValueError:
                print(f"  Failure {i+1}, state: {cb.state.value}")
            except CircuitOpenError as e:
                print(f"  Circuit open: {e}")

        print(f"\nCircuit state: {cb.state.value}")
        print(f"Stats: {cb.stats}")

        # Wait for timeout
        print("\nWaiting for timeout...")
        await asyncio.sleep(6)

        print(f"Circuit state: {cb.state.value}")

        # Test recovery
        print("\nTesting recovery...")
        for i in range(5):
            try:
                result = await cb.execute(success_func)
                print(f"  Success {i+1}: {result}, state: {cb.state.value}")
            except CircuitOpenError as e:
                print(f"  Circuit open: {e}")

    asyncio.run(test())
