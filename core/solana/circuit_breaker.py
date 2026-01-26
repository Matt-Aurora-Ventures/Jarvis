"""
RPC Circuit Breaker for Solana Endpoints.

Provides circuit breaker pattern specifically designed for RPC failures:
- Prevents cascading failures during network volatility
- Automatic recovery after cooldown period
- Integration with RPC health monitoring
- Callback hooks for state transitions

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests rejected immediately
- HALF_OPEN: Testing if service recovered

Usage:
    from core.solana.circuit_breaker import RPCCircuitBreaker, rpc_circuit_breaker

    # Direct usage
    cb = RPCCircuitBreaker(name="helius", failure_threshold=5)
    if cb.allow_request():
        try:
            result = await make_rpc_call()
            cb.record_success()
        except Exception as e:
            cb.record_failure(str(e))

    # Decorator usage
    @rpc_circuit_breaker(name="helius", failure_threshold=5)
    async def make_rpc_call():
        return await client.get_balance(pubkey)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_SUCCESS_THRESHOLD = 2
DEFAULT_RECOVERY_TIMEOUT = 60.0  # seconds


# =============================================================================
# ENUMS
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast, rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CircuitOpenError(Exception):
    """Raised when circuit is open and requests are rejected."""

    def __init__(self, name: str, remaining_seconds: float):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is open. Retry in {remaining_seconds:.1f}s"
        )


# =============================================================================
# STATISTICS
# =============================================================================

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
    last_error_message: Optional[str] = None
    state_changes: List[tuple] = field(default_factory=list)

    def record_success(self) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()

    def record_failure(self, error_message: str = None) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()
        self.last_error_message = error_message

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
        """Export stats as dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_rate": round(self.failure_rate, 4),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_error_message": self.last_error_message,
        }


# =============================================================================
# RPC CIRCUIT BREAKER
# =============================================================================

class RPCCircuitBreaker:
    """
    Circuit breaker implementation for RPC endpoints.

    Prevents cascading failures by tracking consecutive failures
    and temporarily rejecting requests when threshold is exceeded.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
        excluded_exceptions: List[Type[Exception]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_half_open: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit name for identification (typically endpoint name)
            failure_threshold: Consecutive failures before opening circuit
            success_threshold: Successes in half-open before closing
            recovery_timeout: Seconds before trying half-open state
            excluded_exceptions: Exceptions that don't count as failures
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            on_half_open: Callback when circuit goes half-open
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

        # Callbacks
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
        """Check if enough time has passed to try half-open."""
        if self._opened_at is None:
            return True
        return time.time() - self._opened_at >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """
        Transition to a new state.

        Note: Caller must hold the lock.
        """
        old_state = self._state
        self._state = new_state
        self._stats.record_state_change(old_state, new_state)

        logger.info(f"Circuit '{self.name}': {old_state.value} -> {new_state.value}")

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            if self._on_open:
                try:
                    self._on_open()
                except Exception as e:
                    logger.warning(f"on_open callback failed: {e}")
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            if self._on_close:
                try:
                    self._on_close()
                except Exception as e:
                    logger.warning(f"on_close callback failed: {e}")
        elif new_state == CircuitState.HALF_OPEN:
            if self._on_half_open:
                try:
                    self._on_half_open()
                except Exception as e:
                    logger.warning(f"on_half_open callback failed: {e}")

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

    def record_failure(self, error: str = None, exception: Exception = None) -> None:
        """
        Record a failed call.

        Args:
            error: Error message string
            exception: Exception instance (for excluded exception checking)
        """
        with self._lock:
            if exception and self._is_excluded_exception(exception):
                return

            self._stats.record_failure(error)

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Returns:
            True if request can proceed, False if rejected
        """
        state = self.state  # This triggers timeout check

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            return True
        else:  # OPEN
            self._stats.record_rejection()
            return False

    async def call(self, func: Callable) -> Any:
        """
        Execute a callable through the circuit breaker.

        Args:
            func: Async callable to execute

        Returns:
            Result of the callable

        Raises:
            CircuitOpenError: If circuit is open
            Any exception from the callable
        """
        if not self.allow_request():
            raise CircuitOpenError(self.name, self.get_remaining_timeout())

        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(str(e), e)
            raise

    def get_remaining_timeout(self) -> float:
        """Get remaining seconds until half-open."""
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return 0.0
        elapsed = time.time() - self._opened_at
        return max(0, self.recovery_timeout - elapsed)

    def reset(self) -> None:
        """Reset circuit to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats = CircuitStats()

    def force_open(self) -> None:
        """Force circuit to open state (e.g., for maintenance)."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": self._stats.to_dict(),
            "remaining_timeout": self.get_remaining_timeout(),
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# =============================================================================
# CIRCUIT BREAKER MANAGER
# =============================================================================

class RPCCircuitBreakerManager:
    """
    Manages circuit breakers for multiple RPC endpoints.

    Provides centralized control and monitoring of all circuit breakers.
    """

    def __init__(self):
        self._breakers: Dict[str, RPCCircuitBreaker] = {}
        self._lock = threading.Lock()

    def register_endpoint(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
        **kwargs
    ) -> RPCCircuitBreaker:
        """
        Register a circuit breaker for an endpoint.

        Args:
            name: Endpoint name/identifier
            failure_threshold: Failures before opening
            success_threshold: Successes to close
            recovery_timeout: Seconds before half-open
            **kwargs: Additional CircuitBreaker arguments

        Returns:
            The registered circuit breaker
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = RPCCircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    success_threshold=success_threshold,
                    recovery_timeout=recovery_timeout,
                    **kwargs
                )
            return self._breakers[name]

    def get_breaker(self, name: str) -> Optional[RPCCircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        **kwargs
    ) -> RPCCircuitBreaker:
        """Get existing or create new circuit breaker."""
        with self._lock:
            if name not in self._breakers:
                # Create breaker directly instead of calling register_endpoint
                # to avoid deadlock (register_endpoint also acquires lock)
                self._breakers[name] = RPCCircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    **kwargs
                )
            return self._breakers[name]

    def get_available_endpoints(self) -> List[str]:
        """
        Get list of endpoints with closed/half-open circuits.

        Returns:
            List of endpoint names that can accept requests
        """
        available = []
        for name, breaker in self._breakers.items():
            if breaker.allow_request():
                available.append(name)
        return available

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers to closed state."""
        for breaker in self._breakers.values():
            breaker.reset()

    def list_endpoints(self) -> List[str]:
        """List all registered endpoint names."""
        return list(self._breakers.keys())


# =============================================================================
# GLOBAL REGISTRY
# =============================================================================

_global_manager: Optional[RPCCircuitBreakerManager] = None
_manager_lock = threading.Lock()


def get_rpc_circuit_manager() -> RPCCircuitBreakerManager:
    """Get the global RPC circuit breaker manager."""
    global _global_manager
    with _manager_lock:
        if _global_manager is None:
            _global_manager = RPCCircuitBreakerManager()
        return _global_manager


def get_rpc_circuit_breaker(name: str, **kwargs) -> RPCCircuitBreaker:
    """Get or create a circuit breaker from the global manager."""
    return get_rpc_circuit_manager().get_or_create(name, **kwargs)


# =============================================================================
# DECORATOR
# =============================================================================

def rpc_circuit_breaker(
    name: str = None,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
    excluded_exceptions: List[Type[Exception]] = None,
) -> Callable:
    """
    Decorator to wrap async function with RPC circuit breaker.

    Usage:
        @rpc_circuit_breaker(name="helius", failure_threshold=5)
        async def call_rpc():
            return await client.get_balance(pubkey)

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Consecutive failures before opening
        success_threshold: Successes in half-open before closing
        recovery_timeout: Seconds before trying half-open
        excluded_exceptions: Exceptions that don't count as failures
    """
    def decorator(func: Callable) -> Callable:
        circuit_name = name or func.__name__
        breaker = get_rpc_circuit_breaker(
            circuit_name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            recovery_timeout=recovery_timeout,
            excluded_exceptions=excluded_exceptions,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            if not breaker.allow_request():
                raise CircuitOpenError(circuit_name, breaker.get_remaining_timeout())

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(str(e), e)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if not breaker.allow_request():
                raise CircuitOpenError(circuit_name, breaker.get_remaining_timeout())

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(str(e), e)
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# PRE-CONFIGURED RPC BREAKERS
# =============================================================================

# Default configurations for common RPC providers
RPC_PROVIDER_CONFIGS = {
    "helius": {"failure_threshold": 5, "recovery_timeout": 60.0},
    "quicknode": {"failure_threshold": 5, "recovery_timeout": 60.0},
    "alchemy": {"failure_threshold": 5, "recovery_timeout": 60.0},
    "triton": {"failure_threshold": 3, "recovery_timeout": 30.0},
    "public": {"failure_threshold": 10, "recovery_timeout": 120.0},
}


def get_rpc_provider_breaker(provider: str) -> RPCCircuitBreaker:
    """
    Get circuit breaker with pre-configured settings for known RPC providers.

    Args:
        provider: Provider name (helius, quicknode, etc.)

    Returns:
        Configured circuit breaker
    """
    config = RPC_PROVIDER_CONFIGS.get(provider, {})
    return get_rpc_circuit_breaker(provider, **config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CircuitState",
    "CircuitStats",
    "CircuitOpenError",
    "RPCCircuitBreaker",
    "RPCCircuitBreakerManager",
    "get_rpc_circuit_manager",
    "get_rpc_circuit_breaker",
    "rpc_circuit_breaker",
    "get_rpc_provider_breaker",
    "RPC_PROVIDER_CONFIGS",
]
