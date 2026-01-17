"""
JARVIS Circuit Breaker Pattern

Prevents cascading failures by:
- Tracking failure rates
- Opening circuit on threshold breach
- Auto-recovery with half-open state
- Per-service isolation

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failures exceeded threshold, requests fail fast
- HALF_OPEN: Testing if service recovered

Usage:
    from core.resilience.circuit_breaker import circuit_breaker, CircuitBreaker

    @circuit_breaker(name="api", failure_threshold=5)
    async def call_external_api():
        return await api.get("/data")
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Circuit breaker statistics."""
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
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

    def record_rejection(self) -> None:
        self.rejected_calls += 1

    def record_state_change(self, from_state: CircuitState, to_state: CircuitState) -> None:
        self.state_changes.append((time.time(), from_state.value, to_state.value))
        # Keep last 100 changes
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": round(self.failure_rate, 4),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open."""

    def __init__(self, name: str, remaining_seconds: float):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is open. Retry in {remaining_seconds:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Tracks failures and opens circuit when threshold is exceeded.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
        excluded_exceptions: List[Type[Exception]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit name for identification
            failure_threshold: Failures before opening
            success_threshold: Successes in half-open before closing
            timeout: Seconds before trying half-open
            excluded_exceptions: Exceptions that don't count as failures
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            on_half_open: Callback when circuit goes half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
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
        return self._stats

    def _should_try_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._opened_at is None:
            return True
        return time.time() - self._opened_at >= self.timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        old_state = self._state
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

    def _is_excluded_exception(self, exception: Exception) -> bool:
        """Check if exception should be excluded from failure count."""
        for exc_type in self.excluded_exceptions:
            if isinstance(exception, exc_type):
                return True
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.record_success()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, exception: Exception = None) -> None:
        """Record a failed call."""
        with self._lock:
            if exception and self._is_excluded_exception(exception):
                return

            self._stats.record_failure()

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        state = self.state  # This checks for timeout transition

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            return True
        else:  # OPEN
            self._stats.record_rejection()
            return False

    def get_remaining_timeout(self) -> float:
        """Get remaining seconds until half-open."""
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return 0.0
        elapsed = time.time() - self._opened_at
        return max(0, self.timeout - elapsed)

    def reset(self) -> None:
        """Reset circuit to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats = CircuitStats()

    def force_open(self) -> None:
        """Force circuit to open state."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)

    def get_status(self) -> Dict[str, Any]:
        """Get circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": self._stats.to_dict(),
            "remaining_timeout": self.get_remaining_timeout(),
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "timeout": self.timeout,
        }


# Global circuit breaker registry
_circuits: Dict[str, CircuitBreaker] = {}
_circuits_lock = threading.Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    with _circuits_lock:
        if name not in _circuits:
            _circuits[name] = CircuitBreaker(name, **kwargs)
        return _circuits[name]


def get_all_circuits() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    return _circuits.copy()


def circuit_breaker(
    name: str = None,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 30.0,
    excluded_exceptions: List[Type[Exception]] = None,
) -> Callable:
    """
    Decorator to wrap function with circuit breaker.

    Usage:
        @circuit_breaker(name="external_api", failure_threshold=5)
        async def call_api():
            return await api.get("/data")
    """
    def decorator(func: Callable) -> Callable:
        circuit_name = name or func.__name__
        circuit = get_circuit_breaker(
            circuit_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            excluded_exceptions=excluded_exceptions,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not circuit.allow_request():
                raise CircuitOpenError(circuit_name, circuit.get_remaining_timeout())

            try:
                result = await func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure(e)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if not circuit.allow_request():
                raise CircuitOpenError(circuit_name, circuit.get_remaining_timeout())

            try:
                result = func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure(e)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator



# Backward compatibility aliases
CircuitBreakerState = CircuitState
APICircuitBreaker = CircuitBreaker


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    half_open_max_calls: int = 3
    excluded_exceptions: tuple = ()


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(self, name: str, config=None, **kwargs) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, **kwargs)
        return self._breakers[name]

    def get(self, name: str):
        return self._breakers.get(name)

    def all(self) -> Dict[str, CircuitBreaker]:
        return self._breakers.copy()

    def list_all(self):
        return list(self._breakers.keys())

    def status(self) -> Dict[str, Any]:
        return {name: b.get_status() for name, b in self._breakers.items()}

    def get_all_status(self):
        return self.status()

    def reset_all(self):
        for breaker in self._breakers.values():
            breaker.reset()


_registry = None


def get_registry() -> CircuitBreakerRegistry:
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


# Alias for backward compatibility
get_breaker = get_circuit_breaker


# Pre-configured API breaker configs
API_CONFIGS = {
    "twelve_data": {"failure_threshold": 5, "success_threshold": 2, "timeout": 120.0},
    "hyperliquid": {"failure_threshold": 3, "success_threshold": 2, "timeout": 30.0},
    "coingecko": {"failure_threshold": 5, "success_threshold": 2, "timeout": 60.0},
    "birdeye": {"failure_threshold": 3, "success_threshold": 2, "timeout": 30.0},
    "dexscreener": {"failure_threshold": 5, "success_threshold": 2, "timeout": 60.0},
    "jupiter": {"failure_threshold": 3, "success_threshold": 2, "timeout": 30.0},
    "twitter": {"failure_threshold": 5, "success_threshold": 2, "timeout": 300.0},
    "grok": {"failure_threshold": 5, "success_threshold": 2, "timeout": 300.0},
}


def get_api_breaker(api_name: str) -> CircuitBreaker:
    """Get circuit breaker with pre-configured settings for known APIs."""
    config = API_CONFIGS.get(api_name, {})
    return get_circuit_breaker(api_name, **config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Circuit Breaker Demo")
    print("=" * 50)

    # Create circuit
    cb = CircuitBreaker("demo", failure_threshold=3, timeout=5.0)
    print(f"Initial state: {cb.state.value}")

    # Simulate failures
    print("\nSimulating failures...")
    for i in range(5):
        if cb.allow_request():
            cb.record_failure()
            print(f"  Failure {i+1}: state={cb.state.value}")
        else:
            print(f"  Request {i+1}: REJECTED (circuit open)")

    print(f"\nCircuit is {cb.state.value}")
    print(f"Remaining timeout: {cb.get_remaining_timeout():.1f}s")

    # Wait for timeout
    print("\nWaiting for timeout...")
    time.sleep(5.5)

    print(f"State after timeout: {cb.state.value}")

    # Simulate recovery
    if cb.allow_request():
        cb.record_success()
        print("Success 1 recorded")
    if cb.allow_request():
        cb.record_success()
        print("Success 2 recorded")

    print(f"Final state: {cb.state.value}")
    print(f"\nStats: {cb.stats.to_dict()}")
