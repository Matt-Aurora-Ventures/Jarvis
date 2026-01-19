"""Chaos Engineering - Inject faults to test system resilience."""

import random
import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


class ChaosMonkey:
    """Inject random failures to test resilience."""

    def __init__(self, failure_rate: float = 0.1, enabled: bool = False):
        """Initialize chaos monkey.

        Args:
            failure_rate: Probability of failure (0-1)
            enabled: Enable chaos testing (disabled by default)
        """
        self.failure_rate = failure_rate
        self.enabled = enabled
        self.failures_injected = 0

    def inject_failure(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with random failures injected.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            ChaoticFailure: Random injected failure
        """
        if not self.enabled or random.random() > self.failure_rate:
            return func(*args, **kwargs)

        # Inject failure
        self.failures_injected += 1
        logger.warning(f"Chaos: Injecting failure (total: {self.failures_injected})")
        raise ChaoticFailure(f"Chaos monkey injected failure")

    def chaos(self):
        """Decorator for chaos injection."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return self.inject_failure(func, *args, **kwargs)

            wrapper._chaos = self
            return wrapper

        return decorator


class ChaoticFailure(Exception):
    """Raised by chaos monkey."""
    pass


__all__ = ["ChaosMonkey", "ChaoticFailure"]
