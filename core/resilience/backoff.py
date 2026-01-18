"""
Exponential Backoff Retry Logic
Centralized retry utility with exponential backoff for all API calls.

Features:
- Exponential backoff with jitter
- Configurable retry limits
- Circular breaker detection
- Logging for debugging
"""

import asyncio
import logging
import random
import time
from typing import Callable, Any, Optional, Type, List
from functools import wraps

logger = logging.getLogger(__name__)


class BackoffConfig:
    """Configuration for exponential backoff."""

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_retries: int = 3,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: List[Type[Exception]] = None,
    ):
        """
        Initialize backoff configuration.

        Args:
            base_delay: Starting delay in seconds
            max_delay: Maximum delay between retries
            max_retries: Maximum number of retry attempts
            exponential_base: Base for exponential calculation
            jitter: Whether to add random jitter to delays
            retryable_exceptions: Exception types to retry on
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]


def calculate_backoff_delay(
    attempt: int,
    config: BackoffConfig,
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Backoff configuration

    Returns:
        Delay in seconds
    """
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter (±25%)
        jitter_factor = 1 + random.uniform(-0.25, 0.25)
        delay *= jitter_factor

    return delay


async def retry_with_backoff(
    func: Callable,
    *args,
    config: BackoffConfig = None,
    **kwargs,
) -> Any:
    """
    Execute async function with exponential backoff retry.

    USAGE:
        from core.resilience.backoff import retry_with_backoff, BackoffConfig

        config = BackoffConfig(base_delay=1, max_retries=3)
        result = await retry_with_backoff(
            some_async_function,
            arg1, arg2,
            config=config,
            kwarg1=value1
        )

    Args:
        func: Async function to retry
        config: Backoff configuration
        args: Positional arguments for function
        kwargs: Keyword arguments for function

    Returns:
        Function result on success

    Raises:
        Last exception if all retries exhausted
    """
    if config is None:
        config = BackoffConfig()

    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.info(f"Succeeded on retry {attempt}/{config.max_retries}")
            return result

        except Exception as e:
            last_exception = e
            is_retryable = any(
                isinstance(e, exc_type)
                for exc_type in config.retryable_exceptions
            )

            if not is_retryable:
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

            if attempt >= config.max_retries:
                logger.error(
                    f"Max retries ({config.max_retries}) exhausted: {type(e).__name__}: {e}"
                )
                raise

            # Calculate and wait for backoff
            delay = calculate_backoff_delay(attempt, config)
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {type(e).__name__}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    raise last_exception


def retry_async(config: BackoffConfig = None):
    """
    Decorator for async functions with exponential backoff.

    USAGE:
        from core.resilience.backoff import retry_async, BackoffConfig

        @retry_async(BackoffConfig(base_delay=2, max_retries=5))
        async def fetch_data():
            result = await external_api.get()
            return result

    Args:
        config: Backoff configuration

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await retry_with_backoff(func, *args, config=config, **kwargs)

        return wrapper

    return decorator


def retry_backoff(config: BackoffConfig = None):
    """
    Decorator for sync functions with exponential backoff.

    USAGE:
        from core.resilience.backoff import retry_backoff, BackoffConfig

        @retry_backoff(BackoffConfig(base_delay=1, max_retries=3))
        def connect_db():
            return db.connect()

    Args:
        config: Backoff configuration

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if config is None:
                _config = BackoffConfig()
            else:
                _config = config

            last_exception = None

            for attempt in range(_config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"Succeeded on retry {attempt}/{_config.max_retries}")
                    return result

                except Exception as e:
                    last_exception = e
                    is_retryable = any(
                        isinstance(e, exc_type)
                        for exc_type in _config.retryable_exceptions
                    )

                    if not is_retryable:
                        logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                        raise

                    if attempt >= _config.max_retries:
                        logger.error(
                            f"Max retries ({_config.max_retries}) exhausted: {type(e).__name__}: {e}"
                        )
                        raise

                    # Calculate and wait for backoff
                    delay = calculate_backoff_delay(attempt, _config)
                    logger.warning(
                        f"Attempt {attempt + 1}/{_config.max_retries + 1} failed: {type(e).__name__}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for failure detection.

    Prevents cascading failures by stopping requests after threshold of failures.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker identifier
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type that triggers failure
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            RuntimeError if circuit is open
            Original exception if function fails
        """
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker {self.name}: Entering HALF_OPEN state")
            else:
                raise RuntimeError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result

        except self.expected_exception as e:
            self.on_failure()
            raise

    def on_success(self):
        """Record successful call."""
        self.failure_count = 0
        if self.state != "CLOSED":
            self.state = "CLOSED"
            logger.info(f"Circuit breaker {self.name}: Reset to CLOSED state")

    def on_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(
                f"Circuit breaker {self.name}: OPENED after {self.failure_count} failures"
            )

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function through circuit breaker.

        Args:
            func: Async function to execute
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            RuntimeError if circuit is open
            Original exception if function fails
        """
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit breaker {self.name}: Entering HALF_OPEN state")
            else:
                raise RuntimeError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result

        except self.expected_exception as e:
            self.on_failure()
            raise
