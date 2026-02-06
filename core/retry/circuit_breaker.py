"""
Circuit Breaker Module

Implements the circuit breaker pattern to prevent cascade failures.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service unhealthy, requests fail fast
- HALF_OPEN: Testing if service has recovered

Usage:
    from core.retry.circuit_breaker import CircuitBreaker, CircuitState

    cb = CircuitBreaker("my_service", failure_threshold=5)

    if cb.is_available():
        try:
            result = await cb.call(my_function)
        except Exception:
            pass  # Circuit records the failure
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""

    def __init__(self, name: str, remaining_seconds: float = 0.0):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is open. Retry in {remaining_seconds:.1f}s"
        )


@dataclass
class CircuitStats:
    """Statistics for circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: List[tuple] = field(default_factory=list)

    def record_success(self) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

    def record_rejection(self) -> None:
        """Record a rejected call (circuit open)."""
        self.rejected_calls += 1

    def record_state_change(self, from_state: CircuitState, to_state: CircuitState) -> None:
        """Record a state transition."""
        self.state_changes.append((time.time(), from_state.value, to_state.value))
        # Keep last 100 changes
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": round(self.failure_rate, 4),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state_changes = []


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Tracks failures and opens circuit when threshold is exceeded,
    preventing cascade failures by failing fast.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        recovery_timeout: float = 30.0,
        excluded_exceptions: Optional[List[Type[Exception]]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit
            failure_threshold: Consecutive failures before opening
            success_threshold: Successes in half-open before closing
            recovery_timeout: Seconds before trying half-open
            excluded_exceptions: Exceptions that don't count as failures
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            on_half_open: Callback when circuit enters half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout
        self.excluded_exceptions = excluded_exceptions or []

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

        self._on_open = on_open
        self._on_close = on_close
        self._on_half_open = on_half_open

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout transition."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_try_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    def _should_try_reset(self) -> bool:
        """Check if enough time passed for half-open."""
        if self._opened_at is None:
            return True
        return time.time() - self._opened_at >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state with callbacks."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._stats.record_state_change(old_state, new_state)

        logger.info(f"Circuit '{self.name}': {old_state.value} -> {new_state.value}")

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            if self._on_open:
                try:
                    self._on_open()
                except Exception:
                    pass
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            if self._on_close:
                try:
                    self._on_close()
                except Exception:
                    pass
        elif new_state == CircuitState.HALF_OPEN:
            if self._on_half_open:
                try:
                    self._on_half_open()
                except Exception:
                    pass

    def _is_excluded(self, exception: Exception) -> bool:
        """Check if exception is excluded from failure count."""
        for exc_type in self.excluded_exceptions:
            if isinstance(exception, exc_type):
                return True
        return False

    def is_available(self) -> bool:
        """
        Check if circuit allows requests.

        Returns:
            True if requests can proceed (CLOSED or HALF_OPEN)
        """
        state = self.state  # Property checks timeout
        if state == CircuitState.OPEN:
            self._stats.record_rejection()
            return False
        return True

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.record_success()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """
        Record a failed call.

        Args:
            exception: The exception that occurred (for filtering)
        """
        with self._lock:
            if exception and self._is_excluded(exception):
                return

            self._stats.record_failure()

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens circuit
                self._transition_to(CircuitState.OPEN)

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Async callable to execute
            *args: Arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from the function

        Raises:
            CircuitOpenError: If circuit is open
            Any exception from the function
        """
        if not self.is_available():
            remaining = self.get_remaining_timeout()
            raise CircuitOpenError(self.name, remaining)

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    def get_remaining_timeout(self) -> float:
        """Get seconds until half-open transition."""
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return 0.0
        elapsed = time.time() - self._opened_at
        return max(0, self.recovery_timeout - elapsed)

    def reset(self) -> None:
        """Reset circuit to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats.reset()

    def force_open(self) -> None:
        """Manually open the circuit."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)

    def get_status(self) -> Dict[str, Any]:
        """Get circuit status as dictionary."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": self._stats.to_dict(),
            "remaining_timeout": self.get_remaining_timeout(),
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(self, name: str, **kwargs) -> CircuitBreaker:
        """
        Get existing or create new circuit breaker.

        Args:
            name: Circuit identifier
            **kwargs: Arguments for CircuitBreaker if creating new

        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, **kwargs)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit by name, or None if not found."""
        return self._breakers.get(name)

    def list_all(self) -> List[str]:
        """List all registered circuit names."""
        return list(self._breakers.keys())

    def reset_all(self) -> None:
        """Reset all circuits to closed state."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuits."""
        return {name: b.get_status() for name, b in self._breakers.items()}


# Global registry instance
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_global_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry


def get_circuit(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit from the global registry."""
    return get_global_registry().get_or_create(name, **kwargs)
