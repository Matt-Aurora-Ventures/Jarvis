"""
Retry Executor Module

Provides manual retry execution with detailed result tracking.

Usage:
    from core.retry.executor import RetryExecutor, RetryResult
    from core.retry.policy import RetryPolicy

    policy = RetryPolicy(max_retries=3)
    executor = RetryExecutor(policy)

    # Sync execution
    result = executor.execute(my_function, arg1, arg2)

    # Async execution
    result = await executor.async_execute(async_function, arg1)

    if result.success:
        print(f"Success: {result.value}")
    else:
        print(f"Failed after {result.attempts} attempts: {result.exception}")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, TypeVar

from .policy import RetryPolicy

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class AttemptRecord:
    """Record of a single execution attempt."""
    attempt: int
    duration: float
    success: bool = False
    value: Any = None
    exception: Optional[Exception] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class RetryResult:
    """
    Result of a retry execution.

    Contains the outcome, timing information, and history of all attempts.
    """
    success: bool
    attempts: int
    total_duration: float
    value: Any = None
    exception: Optional[Exception] = None
    attempt_history: List[AttemptRecord] = field(default_factory=list)


class RetryExecutor:
    """
    Executes functions with retry logic and detailed tracking.

    Provides both sync and async execution methods with callbacks
    and comprehensive metrics.
    """

    def __init__(self, policy: RetryPolicy):
        """
        Initialize executor with retry policy.

        Args:
            policy: RetryPolicy defining retry behavior
        """
        self.policy = policy

    def execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        on_success: Optional[Callable[[T, int], None]] = None,
        on_failure: Optional[Callable[[Exception, int], None]] = None,
        **kwargs
    ) -> RetryResult:
        """
        Execute a synchronous function with retry.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            on_retry: Callback(attempt, exception, delay) before each retry
            on_success: Callback(result, attempts) on success
            on_failure: Callback(exception, attempts) on final failure
            **kwargs: Keyword arguments for function

        Returns:
            RetryResult with execution outcome and metrics
        """
        start_time = time.time()
        attempt_history: List[AttemptRecord] = []
        last_exception: Optional[Exception] = None
        max_attempts = self.policy.max_retries + 1  # Initial try + retries

        for attempt in range(1, max_attempts + 1):
            attempt_start = time.time()

            try:
                result = func(*args, **kwargs)
                attempt_duration = time.time() - attempt_start

                attempt_history.append(AttemptRecord(
                    attempt=attempt,
                    duration=attempt_duration,
                    success=True,
                    value=result
                ))

                if on_success:
                    try:
                        on_success(result, attempt)
                    except Exception:
                        pass

                return RetryResult(
                    success=True,
                    value=result,
                    attempts=attempt,
                    total_duration=time.time() - start_time,
                    attempt_history=attempt_history
                )

            except Exception as e:
                attempt_duration = time.time() - attempt_start
                last_exception = e

                attempt_history.append(AttemptRecord(
                    attempt=attempt,
                    duration=attempt_duration,
                    success=False,
                    exception=e
                ))

                # Check if should retry
                if not self.policy.should_retry(e):
                    logger.debug(f"Non-retryable exception: {type(e).__name__}")
                    break

                if attempt >= max_attempts:
                    logger.debug(f"Max attempts ({max_attempts}) exhausted")
                    break

                # Calculate delay and wait
                delay = self.policy.get_delay(attempt)

                if on_retry:
                    try:
                        on_retry(attempt, e, delay)
                    except Exception:
                        pass

                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {type(e).__name__}. "
                    f"Retrying in {delay:.2f}s"
                )

                time.sleep(delay)

        # All attempts exhausted
        if on_failure:
            try:
                on_failure(last_exception, len(attempt_history))
            except Exception:
                pass

        return RetryResult(
            success=False,
            exception=last_exception,
            attempts=len(attempt_history),
            total_duration=time.time() - start_time,
            attempt_history=attempt_history
        )

    async def async_execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        on_success: Optional[Callable[[T, int], None]] = None,
        on_failure: Optional[Callable[[Exception, int], None]] = None,
        **kwargs
    ) -> RetryResult:
        """
        Execute an async function with retry.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            on_retry: Callback(attempt, exception, delay) before each retry
            on_success: Callback(result, attempts) on success
            on_failure: Callback(exception, attempts) on final failure
            **kwargs: Keyword arguments for function

        Returns:
            RetryResult with execution outcome and metrics
        """
        start_time = time.time()
        attempt_history: List[AttemptRecord] = []
        last_exception: Optional[Exception] = None
        max_attempts = self.policy.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            attempt_start = time.time()

            try:
                result = await func(*args, **kwargs)
                attempt_duration = time.time() - attempt_start

                attempt_history.append(AttemptRecord(
                    attempt=attempt,
                    duration=attempt_duration,
                    success=True,
                    value=result
                ))

                if on_success:
                    try:
                        on_success(result, attempt)
                    except Exception:
                        pass

                return RetryResult(
                    success=True,
                    value=result,
                    attempts=attempt,
                    total_duration=time.time() - start_time,
                    attempt_history=attempt_history
                )

            except Exception as e:
                attempt_duration = time.time() - attempt_start
                last_exception = e

                attempt_history.append(AttemptRecord(
                    attempt=attempt,
                    duration=attempt_duration,
                    success=False,
                    exception=e
                ))

                if not self.policy.should_retry(e):
                    logger.debug(f"Non-retryable exception: {type(e).__name__}")
                    break

                if attempt >= max_attempts:
                    logger.debug(f"Max attempts ({max_attempts}) exhausted")
                    break

                delay = self.policy.get_delay(attempt)

                if on_retry:
                    try:
                        on_retry(attempt, e, delay)
                    except Exception:
                        pass

                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {type(e).__name__}. "
                    f"Retrying in {delay:.2f}s"
                )

                await asyncio.sleep(delay)

        if on_failure:
            try:
                on_failure(last_exception, len(attempt_history))
            except Exception:
                pass

        return RetryResult(
            success=False,
            exception=last_exception,
            attempts=len(attempt_history),
            total_duration=time.time() - start_time,
            attempt_history=attempt_history
        )
