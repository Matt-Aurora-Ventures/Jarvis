"""
Circuit Breaker Pattern - Prevent cascading failures by stopping calls to failing services.

Implements the circuit breaker pattern with three states:
- CLOSED: Normal operation, calls pass through
- OPEN: Too many failures, calls are blocked
- HALF_OPEN: Testing if service recovered
"""

import time
import logging
from enum import Enum
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Service failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Circuit breaker for API calls."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, name: str = ""):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            name: Breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_call_time = None

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit {self.name} attempting reset (HALF_OPEN)")
            else:
                raise CircuitBreakerOpen(f"Circuit breaker {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.success_count += 1

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit {self.name} RECOVERED (CLOSED)")

    def _on_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} OPENED after {self.failure_count} failures")

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failure_count,
            "successes": self.success_count,
            "last_failure": self.last_failure_time,
        }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60):
    """Decorator for circuit breaker pattern.

    Args:
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before trying reset
    """
    breaker = CircuitBreaker(failure_threshold, recovery_timeout)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        wrapper._breaker = breaker
        return wrapper

    return decorator


__all__ = ["CircuitBreaker", "CircuitBreakerOpen", "CircuitState", "circuit_breaker"]
