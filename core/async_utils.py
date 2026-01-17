"""
Async Utilities - Safe asyncio patterns for production use.

This module provides:
- Tracked task management (no silent failures)
- Safe background task creation with error handling
- Async context managers for resource cleanup
- Rate limiting and throttling utilities

Usage:
    from core.async_utils import TaskTracker, create_tracked_task

    tracker = TaskTracker("my_component")

    # Create tracked task
    task = tracker.create_task(my_coroutine(), name="fetch_data")

    # Or use module-level helper
    task = create_tracked_task(my_coroutine(), name="fetch_data")
"""

import asyncio
import functools
import logging
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class TaskInfo:
    """Information about a tracked task."""
    name: str
    created_at: datetime
    task: asyncio.Task
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Any = None


class TaskTracker:
    """
    Tracks asyncio tasks to prevent silent failures and memory leaks.

    Features:
    - Automatic error logging when tasks fail
    - Task lifecycle tracking
    - Cleanup of completed tasks
    - Statistics on task execution
    """

    def __init__(self, component_name: str = "default"):
        """
        Initialize task tracker.

        Args:
            component_name: Name of the component for logging
        """
        self.component_name = component_name
        self._tasks: Dict[str, TaskInfo] = {}
        self._task_counter = 0
        self._total_created = 0
        self._total_succeeded = 0
        self._total_failed = 0

    def create_task(
        self,
        coro: Coroutine,
        name: Optional[str] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_complete: Optional[Callable[[Any], None]] = None,
    ) -> asyncio.Task:
        """
        Create a tracked asyncio task with error handling.

        Args:
            coro: Coroutine to run
            name: Optional name for the task
            on_error: Optional callback when task fails
            on_complete: Optional callback when task completes successfully

        Returns:
            The created asyncio.Task
        """
        self._task_counter += 1
        self._total_created += 1
        task_name = name or f"task_{self._task_counter}"
        full_name = f"{self.component_name}.{task_name}"

        task = asyncio.create_task(coro, name=full_name)

        info = TaskInfo(
            name=full_name,
            created_at=datetime.now(),
            task=task,
        )
        self._tasks[full_name] = info

        # Add completion callback
        task.add_done_callback(
            functools.partial(
                self._on_task_done,
                task_name=full_name,
                on_error=on_error,
                on_complete=on_complete,
            )
        )

        return task

    def _on_task_done(
        self,
        task: asyncio.Task,
        task_name: str,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_complete: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """Handle task completion."""
        info = self._tasks.get(task_name)
        if info:
            info.completed_at = datetime.now()

        try:
            exc = task.exception()
            if exc:
                self._total_failed += 1
                error_msg = f"{type(exc).__name__}: {exc}"
                if info:
                    info.error = error_msg

                logger.error(
                    f"[{task_name}] Task failed: {error_msg}\n"
                    f"{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"
                )

                if on_error:
                    try:
                        on_error(exc)
                    except Exception as callback_err:
                        logger.error(f"[{task_name}] on_error callback failed: {callback_err}")
            else:
                self._total_succeeded += 1
                result = task.result()
                if info:
                    info.result = result

                if on_complete:
                    try:
                        on_complete(result)
                    except Exception as callback_err:
                        logger.error(f"[{task_name}] on_complete callback failed: {callback_err}")

        except asyncio.CancelledError:
            logger.debug(f"[{task_name}] Task was cancelled")
        except asyncio.InvalidStateError:
            pass

    def get_running_tasks(self) -> List[TaskInfo]:
        """Get all currently running tasks."""
        self._cleanup_completed()
        return [info for info in self._tasks.values() if not info.task.done()]

    def get_failed_tasks(self) -> List[TaskInfo]:
        """Get all failed tasks."""
        return [info for info in self._tasks.values() if info.error is not None]

    def _cleanup_completed(self) -> int:
        """Remove completed tasks from tracking. Returns count removed."""
        completed = [name for name, info in self._tasks.items() if info.task.done()]
        for name in completed:
            del self._tasks[name]
        return len(completed)

    async def cancel_all(self, timeout: float = 5.0) -> int:
        """
        Cancel all running tasks.

        Args:
            timeout: Seconds to wait for tasks to complete

        Returns:
            Number of tasks cancelled
        """
        running = self.get_running_tasks()
        if not running:
            return 0

        for info in running:
            info.task.cancel()

        # Wait for cancellation
        tasks = [info.task for info in running]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"[{self.component_name}] Some tasks did not cancel within {timeout}s")

        return len(running)

    def get_stats(self) -> Dict[str, Any]:
        """Get task tracker statistics."""
        self._cleanup_completed()
        return {
            "component": self.component_name,
            "total_created": self._total_created,
            "total_succeeded": self._total_succeeded,
            "total_failed": self._total_failed,
            "currently_running": len(self._tasks),
            "success_rate": (
                self._total_succeeded / self._total_created * 100
                if self._total_created > 0 else 0
            ),
        }


# Global default tracker for convenience
_default_tracker = TaskTracker("global")


def create_tracked_task(
    coro: Coroutine,
    name: Optional[str] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    on_complete: Optional[Callable[[Any], None]] = None,
    tracker: Optional[TaskTracker] = None,
) -> asyncio.Task:
    """
    Create a tracked task using the default or specified tracker.

    This is a drop-in replacement for asyncio.create_task() that
    automatically logs errors and tracks task lifecycle.
    """
    tracker = tracker or _default_tracker
    return tracker.create_task(coro, name=name, on_error=on_error, on_complete=on_complete)


def fire_and_forget(
    coro: Coroutine,
    name: Optional[str] = None,
    tracker: Optional[TaskTracker] = None,
) -> asyncio.Task:
    """
    Run a coroutine in the background, logging any errors.

    Use this for tasks where you don't need the result but want
    errors to be logged rather than silently swallowed.
    """
    return create_tracked_task(coro, name=name, tracker=tracker)


class RateLimiter:
    """
    Async rate limiter using token bucket algorithm.

    Usage:
        limiter = RateLimiter(calls_per_second=10)

        async def fetch():
            async with limiter:
                return await make_request()
    """

    def __init__(self, calls_per_second: float = 10.0, burst: int = 1):
        """
        Initialize rate limiter.

        Args:
            calls_per_second: Maximum sustained rate
            burst: Maximum burst size (tokens available at once)
        """
        self.rate = calls_per_second
        self.burst = burst
        self._tokens = burst
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit token, waiting if necessary."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
                self._last_update = now

                if self._tokens >= 1:
                    self._tokens -= 1
                    return

                # Wait for next token
                wait_time = (1 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class Throttle:
    """
    Decorator to throttle async function calls.

    Usage:
        @Throttle(calls_per_second=5)
        async def api_call():
            ...
    """

    def __init__(self, calls_per_second: float = 10.0):
        self.limiter = RateLimiter(calls_per_second=calls_per_second)

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async with self.limiter:
                return await func(*args, **kwargs)
        return wrapper


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to call
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                    f"Retrying in {current_delay:.1f}s..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff

    raise last_exception


@asynccontextmanager
async def timeout_context(seconds: float, message: str = "Operation timed out"):
    """
    Async context manager with timeout.

    Usage:
        async with timeout_context(5.0, "API call"):
            await long_operation()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"{message} after {seconds}s")


async def gather_with_concurrency(
    n: int,
    *coros: Coroutine,
    return_exceptions: bool = False,
) -> List[Any]:
    """
    Run coroutines with limited concurrency.

    Args:
        n: Maximum concurrent coroutines
        coros: Coroutines to run
        return_exceptions: If True, return exceptions instead of raising

    Returns:
        List of results in order
    """
    semaphore = asyncio.Semaphore(n)

    async def limited_coro(coro: Coroutine) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *[limited_coro(c) for c in coros],
        return_exceptions=return_exceptions,
    )
