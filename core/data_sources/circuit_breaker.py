"""
Circuit Breaker Pattern for API Fault Tolerance

Implements the circuit breaker pattern to protect against cascading failures
when external APIs become unavailable or unreliable.

States:
- CLOSED: Normal operation, requests flow through
- OPEN: Failures exceeded threshold, requests fail immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed

Per guide: "Implement circuit breakers to gracefully handle API failures
and prevent cascading failures in dependent systems."
"""

import time
import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 2          # Successes in half-open before closing
    timeout: float = 60.0               # Seconds before transitioning to half-open
    half_open_max_calls: int = 3        # Max calls in half-open state
    excluded_exceptions: tuple = ()     # Exceptions that don't count as failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Usage:
        breaker = CircuitBreaker("my_api")

        # Async function
        result = await breaker.call_async(my_async_func, arg1, arg2)

        # Sync function
        result = breaker.call(my_sync_func, arg1, arg2)

        # As decorator
        @breaker.protect
        async def my_func():
            ...
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self.stats = CircuitBreakerStats()

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout transition."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               time.time() - self._last_failure_time >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        if self._state != new_state:
            logger.info(f"Circuit '{self.name}': {self._state.value} -> {new_state.value}")
            self._state = new_state
            self.stats.state_changes += 1

            if new_state == CircuitState.HALF_OPEN:
                self._half_open_calls = 0
                self._success_count = 0
            elif new_state == CircuitState.CLOSED:
                self._failure_count = 0

    def _record_success(self):
        """Record a successful call."""
        self.stats.successful_calls += 1
        self.stats.last_success_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0  # Reset failure count on success

    def _record_failure(self, exception: Exception):
        """Record a failed call."""
        # Check if exception is excluded
        if isinstance(exception, self.config.excluded_exceptions):
            return

        self.stats.failed_calls += 1
        self.stats.last_failure_time = time.time()
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _can_execute(self) -> bool:
        """Check if request can be executed."""
        state = self.state  # This may trigger timeout transition

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            self.stats.rejected_calls += 1
            return False
        elif state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            self.stats.rejected_calls += 1
            return False

        return False

    async def call_async(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        async with self._lock:
            if not self._can_execute():
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is open. "
                    f"Retry after {self.config.timeout}s"
                )

        self.stats.total_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    def call(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute sync function with circuit breaker protection.

        Args:
            func: Sync function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        if not self._can_execute():
            raise CircuitOpenError(
                f"Circuit '{self.name}' is open. "
                f"Retry after {self.config.timeout}s"
            )

        self.stats.total_calls += 1

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker.

        Usage:
            @breaker.protect
            async def my_api_call():
                ...
        """
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self.call(func, *args, **kwargs)
            return sync_wrapper

    def reset(self):
        """Manually reset the circuit breaker to closed state."""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(f"Circuit '{self.name}' manually reset")

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "state_changes": self.stats.state_changes,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            }
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# ==================== Circuit Breaker Registry ====================

class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Usage:
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("twelve_data")
        result = await breaker.call_async(api_call)
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.

        Args:
            name: Circuit breaker name
            config: Configuration (only used if creating new)

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def list_all(self) -> list[str]:
        """List all registered circuit breaker names."""
        return list(self._breakers.keys())

    def get_all_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers."""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry instance
_registry: Optional[CircuitBreakerRegistry] = None


def get_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


def get_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Convenience function to get or create a circuit breaker.

    Args:
        name: Circuit breaker name (e.g., "twelve_data", "hyperliquid")
        config: Optional configuration

    Returns:
        CircuitBreaker instance
    """
    return get_registry().get_or_create(name, config)


# ==================== Pre-configured Breakers ====================

# Default configurations for known APIs
API_CONFIGS = {
    "twelve_data": CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=120.0,  # 2 minutes - rate limit recovery
    ),
    "hyperliquid": CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=30.0,  # Quick recovery for high-frequency
    ),
    "coingecko": CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
    ),
    "birdeye": CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=30.0,
    ),
    "dexscreener": CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
    ),
    "jupiter": CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=30.0,
    ),
}


def get_api_breaker(api_name: str) -> CircuitBreaker:
    """
    Get circuit breaker with pre-configured settings for known APIs.

    Args:
        api_name: API name (e.g., "twelve_data", "hyperliquid")

    Returns:
        Pre-configured CircuitBreaker
    """
    config = API_CONFIGS.get(api_name)
    return get_breaker(api_name, config)
