"""
Retry Policy Module

Defines retry policies with configurable backoff strategies and jitter.

Usage:
    from core.retry.policy import RetryPolicy, BackoffStrategy

    policy = RetryPolicy(
        max_retries=3,
        base_delay=1.0,
        backoff=BackoffStrategy.EXPONENTIAL,
        jitter=True
    )

    delay = policy.get_delay(attempt=2)
    should_retry = policy.should_retry(exception)
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Type


class BackoffStrategy(Enum):
    """Backoff strategies for retry delays."""
    FIXED = "fixed"         # Same delay every time
    LINEAR = "linear"       # Delay increases linearly: base * attempt
    EXPONENTIAL = "exponential"  # Delay doubles: base * 2^(attempt-1)


@dataclass(frozen=True)
class RetryPolicy:
    """
    Configuration for retry behavior.

    Immutable policy defining how retries should be handled including
    backoff strategy, jitter, and exception filtering.

    Attributes:
        max_retries: Maximum number of retry attempts (not counting initial try)
        base_delay: Base delay in seconds between retries
        max_delay: Maximum delay in seconds (caps exponential growth)
        backoff: Strategy for calculating delays between retries
        exponential_base: Base for exponential backoff (default 2.0)
        jitter: Whether to add randomness to delays
        jitter_factor: Range of jitter as fraction of delay (0.5 = +/- 50%)
        retryable_exceptions: Exception types that trigger retry (None = all)
        non_retryable_exceptions: Exception types that never retry
    """
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.5
    retryable_exceptions: Optional[tuple] = None
    non_retryable_exceptions: tuple = field(default_factory=lambda: (KeyboardInterrupt, SystemExit))

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Args:
            attempt: Attempt number (1-indexed, where 1 is the first retry)

        Returns:
            Delay in seconds before the next attempt
        """
        if self.backoff == BackoffStrategy.FIXED:
            delay = self.base_delay
        elif self.backoff == BackoffStrategy.LINEAR:
            delay = self.base_delay * attempt
        elif self.backoff == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        else:
            delay = self.base_delay

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0.0, delay)  # Ensure non-negative

        return delay

    def should_retry(self, exception: Exception) -> bool:
        """
        Check if the given exception should trigger a retry.

        Non-retryable exceptions take precedence over retryable ones.

        Args:
            exception: The exception that was raised

        Returns:
            True if the exception should trigger a retry
        """
        # Non-retryable takes precedence
        for exc_type in self.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # If retryable_exceptions is None, retry all (except non-retryable)
        if self.retryable_exceptions is None:
            return True

        # Check if in retryable list
        for exc_type in self.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        return False


# Preset policies for common use cases

AGGRESSIVE_RETRY = RetryPolicy(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True
)

CONSERVATIVE_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=2.0,
    max_delay=60.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    exponential_base=3.0,
    jitter=True
)

API_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    max_delay=15.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError)
)

RPC_RETRY = RetryPolicy(
    max_retries=5,
    base_delay=0.5,
    max_delay=20.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True,  # Prevent thundering herd
    retryable_exceptions=(ConnectionError, TimeoutError, OSError)
)

# Database retry policy
DATABASE_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=0.5,
    max_delay=10.0,
    backoff=BackoffStrategy.EXPONENTIAL,
    jitter=True
)

# Quick retry for fast-fail scenarios
QUICK_RETRY = RetryPolicy(
    max_retries=2,
    base_delay=0.1,
    max_delay=1.0,
    backoff=BackoffStrategy.FIXED,
    jitter=False
)
