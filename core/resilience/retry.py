"""
JARVIS Retry and Backoff Utilities

Provides resilient execution with:
- Exponential backoff
- Jitter for thundering herd prevention
- Configurable retry policies
- Exception filtering
- Async support

Usage:
    from core.resilience.retry import retry, RetryPolicy

    @retry(max_attempts=3)
    async def fetch_data():
        return await api.get("/data")
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.5
    retryable_exceptions: List[Type[Exception]] = field(
        default_factory=lambda: [Exception]
    )
    non_retryable_exceptions: List[Type[Exception]] = field(
        default_factory=lambda: [KeyboardInterrupt, SystemExit]
    )
    on_retry: Optional[Callable[[int, Exception, float], None]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return delay

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception should trigger retry."""
        for exc_type in self.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        for exc_type in self.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        return False


# Preset policies
AGGRESSIVE_RETRY = RetryPolicy(max_attempts=5, base_delay=0.5, max_delay=30.0)
CONSERVATIVE_RETRY = RetryPolicy(max_attempts=3, base_delay=2.0, max_delay=60.0, exponential_base=3.0)
API_RETRY = RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=10.0, retryable_exceptions=[ConnectionError, TimeoutError, OSError])
RPC_RETRY = RetryPolicy(max_attempts=5, base_delay=0.5, max_delay=15.0, jitter=True)

# API-specific retry policies
JUPITER_QUOTE_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError]
)

JUPITER_SWAP_RETRY = RetryPolicy(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.5,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError]
)

BIRDEYE_API_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=15.0,
    jitter=True,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError]
)

TWITTER_API_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError]
)

SOLANA_RPC_RETRY = RetryPolicy(
    max_attempts=5,
    base_delay=0.5,
    max_delay=20.0,
    jitter=True,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError]
)


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(f"Retry exhausted after {attempts} attempts. Last error: {last_exception}")


@dataclass
class RetryStats:
    """Statistics for retry execution."""
    attempts: int = 0
    total_delay: float = 0.0
    success: bool = False
    final_exception: Optional[Exception] = None
    exceptions: List[Tuple[int, Exception]] = field(default_factory=list)


def retry(
    max_attempts: int = None,
    base_delay: float = None,
    policy: RetryPolicy = None,
    **policy_kwargs,
) -> Callable:
    """
    Decorator for retrying functions with backoff.

    Usage:
        @retry(max_attempts=3)
        async def unstable_operation():
            ...
    """
    if policy is None:
        policy = RetryPolicy()

    if max_attempts is not None:
        policy.max_attempts = max_attempts
    if base_delay is not None:
        policy.base_delay = base_delay

    for key, value in policy_kwargs.items():
        if hasattr(policy, key):
            setattr(policy, key, value)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not policy.should_retry(e):
                        raise

                    if attempt >= policy.max_attempts:
                        raise RetryExhausted(attempt, e) from e

                    delay = policy.get_delay(attempt)

                    logger.warning(
                        f"Retry {attempt}/{policy.max_attempts} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )

                    if policy.on_retry:
                        try:
                            policy.on_retry(attempt, e, delay)
                        except Exception:
                            pass

                    await asyncio.sleep(delay)

            raise RetryExhausted(policy.max_attempts, last_exception)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not policy.should_retry(e):
                        raise

                    if attempt >= policy.max_attempts:
                        raise RetryExhausted(attempt, e) from e

                    delay = policy.get_delay(attempt)

                    logger.warning(
                        f"Retry {attempt}/{policy.max_attempts} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )

                    if policy.on_retry:
                        try:
                            policy.on_retry(attempt, e, delay)
                        except Exception:
                            pass

                    time.sleep(delay)

            raise RetryExhausted(policy.max_attempts, last_exception)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def retry_async(func: Callable, *args, policy: RetryPolicy = None, **kwargs) -> Any:
    """Execute async function with retry."""
    policy = policy or RetryPolicy()

    @retry(policy=policy)
    async def wrapper():
        return await func(*args, **kwargs)

    return await wrapper()


def retry_sync(func: Callable, *args, policy: RetryPolicy = None, **kwargs) -> Any:
    """Execute sync function with retry."""
    policy = policy or RetryPolicy()

    @retry(policy=policy)
    def wrapper():
        return func(*args, **kwargs)

    return wrapper()


class RetryContext:
    """Context manager for retry with manual control."""

    def __init__(self, policy: RetryPolicy = None, **policy_kwargs):
        self.policy = policy or RetryPolicy(**policy_kwargs)
        self.attempt = 0
        self._succeeded = False
        self._exhausted = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def should_continue(self) -> bool:
        return not self._succeeded and not self._exhausted and self.attempt < self.policy.max_attempts

    def success(self) -> None:
        self._succeeded = True

    async def failed(self, exception: Exception) -> None:
        self.attempt += 1

        if not self.policy.should_retry(exception):
            self._exhausted = True
            raise exception

        if self.attempt >= self.policy.max_attempts:
            self._exhausted = True
            raise RetryExhausted(self.attempt, exception)

        delay = self.policy.get_delay(self.attempt)
        await asyncio.sleep(delay)
