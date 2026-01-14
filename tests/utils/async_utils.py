"""
Async Test Utilities

Provides utilities for testing async code including timeout wrappers,
mock async iterators, and condition waiters.
"""

import asyncio
import functools
from typing import (
    TypeVar, Callable, Any, Optional, Awaitable,
    AsyncIterator, List, Tuple, Union
)
from unittest.mock import MagicMock, AsyncMock
from contextlib import asynccontextmanager
import time

T = TypeVar('T')


def async_timeout(seconds: float = 5.0):
    """
    Decorator to add timeout to async test functions.

    Usage:
        @async_timeout(seconds=10.0)
        async def test_slow_operation():
            await slow_operation()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Test {func.__name__} timed out after {seconds} seconds"
                )
        return wrapper
    return decorator


def run_async(coro: Awaitable[T]) -> T:
    """
    Run an async coroutine synchronously.

    Useful for running async code in synchronous test contexts.

    Usage:
        result = run_async(async_function())
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def async_mock(**kwargs) -> AsyncMock:
    """
    Create an AsyncMock with sensible defaults.

    Usage:
        mock = async_mock(return_value={"key": "value"})
        result = await mock()
    """
    return AsyncMock(**kwargs)


class AsyncContextManager:
    """
    Mock async context manager for testing.

    Usage:
        mock_cm = AsyncContextManager(return_value=mock_resource)
        async with mock_cm as resource:
            assert resource == mock_resource
    """

    def __init__(
        self,
        return_value: Any = None,
        enter_side_effect: Optional[Exception] = None,
        exit_side_effect: Optional[Exception] = None
    ):
        self.return_value = return_value
        self.enter_side_effect = enter_side_effect
        self.exit_side_effect = exit_side_effect
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        if self.enter_side_effect:
            raise self.enter_side_effect
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        if self.exit_side_effect:
            raise self.exit_side_effect
        return False


class AsyncIteratorMock:
    """
    Mock async iterator for testing.

    Usage:
        mock_iter = AsyncIteratorMock([1, 2, 3])
        async for item in mock_iter:
            print(item)
    """

    def __init__(self, items: List[Any], delay: float = 0.0):
        self.items = items
        self.delay = delay
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self.items):
            raise StopAsyncIteration

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        item = self.items[self._index]
        self._index += 1
        return item


async def wait_for_condition(
    condition: Callable[[], Union[bool, Awaitable[bool]]],
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition was not met"
) -> bool:
    """
    Wait for a condition to become true.

    Args:
        condition: Function returning bool (sync or async)
        timeout: Maximum time to wait
        interval: Check interval
        message: Error message if timeout

    Returns:
        True if condition met

    Raises:
        TimeoutError: If condition not met within timeout
    """
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result

        if result:
            return True

        await asyncio.sleep(interval)

    raise TimeoutError(f"{message} (waited {timeout}s)")


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    delay: float = 0.1,
    exceptions: Tuple[type, ...] = (Exception,),
    **kwargs
) -> T:
    """
    Retry an async function on failure.

    Args:
        func: Async function to retry
        *args: Positional arguments
        max_attempts: Maximum retry attempts
        delay: Delay between retries
        exceptions: Tuple of exceptions to catch
        **kwargs: Keyword arguments

    Returns:
        Function result

    Raises:
        Last exception if all attempts fail
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay * (attempt + 1))

    raise last_exception  # type: ignore


async def gather_with_errors(
    *coros: Awaitable[T],
    return_exceptions: bool = True
) -> List[Union[T, Exception]]:
    """
    Gather coroutines and optionally return exceptions.

    Args:
        *coros: Coroutines to gather
        return_exceptions: If True, return exceptions instead of raising

    Returns:
        List of results or exceptions
    """
    return await asyncio.gather(*coros, return_exceptions=return_exceptions)


@asynccontextmanager
async def async_timer():
    """
    Async context manager for timing operations.

    Usage:
        async with async_timer() as timer:
            await slow_operation()
        print(f"Took {timer.elapsed}s")
    """
    class Timer:
        def __init__(self):
            self.start: float = 0
            self.end: float = 0
            self.elapsed: float = 0

    timer = Timer()
    timer.start = time.monotonic()
    try:
        yield timer
    finally:
        timer.end = time.monotonic()
        timer.elapsed = timer.end - timer.start


class AsyncEventRecorder:
    """
    Record async events for testing.

    Usage:
        recorder = AsyncEventRecorder()
        await recorder.record("event1", data={"key": "value"})
        assert len(recorder.events) == 1
    """

    def __init__(self):
        self.events: List[dict] = []
        self._lock = asyncio.Lock()

    async def record(self, name: str, **data) -> None:
        """Record an event."""
        async with self._lock:
            self.events.append({
                "name": name,
                "timestamp": time.monotonic(),
                "data": data,
            })

    def get_events(self, name: Optional[str] = None) -> List[dict]:
        """Get events, optionally filtered by name."""
        if name:
            return [e for e in self.events if e["name"] == name]
        return self.events.copy()

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()


class AsyncQueue:
    """
    Async queue for testing producer/consumer patterns.

    Usage:
        queue = AsyncQueue()
        await queue.put("item")
        item = await queue.get()
    """

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._items_processed = 0

    async def put(self, item: Any) -> None:
        """Put an item in the queue."""
        await self._queue.put(item)

    async def get(self, timeout: Optional[float] = None) -> Any:
        """Get an item from the queue."""
        if timeout:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        return await self._queue.get()

    def qsize(self) -> int:
        """Get queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()


async def create_async_generator(
    items: List[T],
    delay: float = 0.0
) -> AsyncIterator[T]:
    """
    Create an async generator from a list.

    Usage:
        async for item in create_async_generator([1, 2, 3]):
            print(item)
    """
    for item in items:
        if delay > 0:
            await asyncio.sleep(delay)
        yield item


class AsyncMockWithHistory:
    """
    AsyncMock that records call history.

    Usage:
        mock = AsyncMockWithHistory()
        await mock("arg1", key="value")
        assert mock.call_count == 1
        assert mock.calls[0] == (("arg1",), {"key": "value"})
    """

    def __init__(
        self,
        return_value: Any = None,
        side_effect: Optional[Callable] = None
    ):
        self.return_value = return_value
        self.side_effect = side_effect
        self.calls: List[Tuple[tuple, dict]] = []
        self.call_count = 0

    async def __call__(self, *args, **kwargs) -> Any:
        self.calls.append((args, kwargs))
        self.call_count += 1

        if self.side_effect:
            result = self.side_effect(*args, **kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result

        return self.return_value

    def reset(self) -> None:
        """Reset call history."""
        self.calls.clear()
        self.call_count = 0

    def assert_called(self) -> None:
        """Assert was called at least once."""
        assert self.call_count > 0, "Expected to be called"

    def assert_called_with(self, *args, **kwargs) -> None:
        """Assert was called with specific arguments."""
        assert (args, kwargs) in self.calls, \
            f"Expected call with {args}, {kwargs} not found"
