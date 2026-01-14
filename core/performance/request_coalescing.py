"""
Request Coalescing

Combines multiple identical requests into a single operation.
Useful for reducing database/API calls when many concurrent
requests need the same data.
"""
import asyncio
import time
from typing import Dict, Any, Optional, TypeVar, Callable, Awaitable, Set
from dataclasses import dataclass, field
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PendingRequest:
    """A request waiting for a coalesced result."""
    key: str
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)


@dataclass
class CoalescedResult:
    """Result of a coalesced request."""
    value: Any
    timestamp: float
    request_count: int
    hit_cache: bool


class RequestCoalescer:
    """
    Coalesces multiple identical concurrent requests into one.

    When multiple requests for the same key arrive while a request is
    in-flight, they all receive the same result instead of triggering
    multiple operations.

    Usage:
        coalescer = RequestCoalescer()

        async def fetch_user(user_id: str) -> dict:
            return await coalescer.coalesce(
                key=f"user:{user_id}",
                fetch_fn=lambda: db.get_user(user_id)
            )

        # Multiple concurrent calls with same key will only
        # trigger one database query
    """

    def __init__(
        self,
        cache_ttl: float = 0,  # 0 = no caching after request completes
        max_pending: int = 1000
    ):
        self.cache_ttl = cache_ttl
        self.max_pending = max_pending

        self._pending: Dict[str, asyncio.Future] = {}
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._request_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def coalesce(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[T]],
        cache_ttl: Optional[float] = None
    ) -> T:
        """
        Execute or coalesce a request.

        Args:
            key: Unique key for this request type
            fetch_fn: Async function to fetch the data
            cache_ttl: Override cache TTL for this request

        Returns:
            The fetched data (from cache, pending request, or new fetch)
        """
        ttl = cache_ttl if cache_ttl is not None else self.cache_ttl

        # Check cache first
        if ttl > 0 and key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < ttl:
                logger.debug(f"Cache hit for {key}")
                return value

        async with self._lock:
            # Double-check cache under lock
            if ttl > 0 and key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < ttl:
                    return value

            # Check if request is already pending
            if key in self._pending:
                logger.debug(f"Coalescing request for {key}")
                self._request_counts[key] = self._request_counts.get(key, 1) + 1
                # Wait for the pending request
                future = self._pending[key]

        # If we found a pending request, wait for it outside the lock
        if key in self._pending:
            return await future

        # Start new request
        async with self._lock:
            # Check again in case another coroutine started the request
            if key in self._pending:
                future = self._pending[key]
                return await future

            # Create new future for this request
            future = asyncio.get_event_loop().create_future()
            self._pending[key] = future
            self._request_counts[key] = 1

        # Execute the fetch
        try:
            result = await fetch_fn()

            # Cache result if TTL > 0
            if ttl > 0:
                self._cache[key] = (result, time.time())

            # Resolve the future
            future.set_result(result)

            count = self._request_counts.get(key, 1)
            if count > 1:
                logger.info(f"Coalesced {count} requests for {key}")

            return result

        except Exception as e:
            future.set_exception(e)
            raise

        finally:
            async with self._lock:
                self._pending.pop(key, None)
                self._request_counts.pop(key, None)

    def invalidate(self, key: str) -> None:
        """Invalidate cached data for a key."""
        self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cached keys matching pattern."""
        import fnmatch

        to_remove = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
        for key in to_remove:
            del self._cache[key]

        return len(to_remove)

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get coalescer statistics."""
        return {
            "pending_requests": len(self._pending),
            "cached_items": len(self._cache),
            "cache_ttl": self.cache_ttl,
            "pending_keys": list(self._pending.keys()),
            "cached_keys": list(self._cache.keys())
        }


class BatchCoalescer:
    """
    Batches multiple requests and executes them together.

    Collects requests for a short window, then executes them
    all in a single batch operation.

    Usage:
        batch_coalescer = BatchCoalescer(
            batch_fn=lambda ids: db.get_users_batch(ids),
            max_batch_size=100,
            max_wait_ms=10
        )

        # Multiple concurrent calls get batched
        user = await batch_coalescer.get("user123")
    """

    def __init__(
        self,
        batch_fn: Callable[[list], Awaitable[Dict[str, Any]]],
        max_batch_size: int = 100,
        max_wait_ms: float = 10
    ):
        self.batch_fn = batch_fn
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms

        self._pending: Dict[str, asyncio.Future] = {}
        self._batch_keys: Set[str] = set()
        self._batch_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any:
        """
        Get item, batching with other concurrent requests.

        Args:
            key: The key to fetch

        Returns:
            The fetched value
        """
        async with self._lock:
            # Check if already pending
            if key in self._pending:
                return await self._pending[key]

            # Create future for this request
            future = asyncio.get_event_loop().create_future()
            self._pending[key] = future
            self._batch_keys.add(key)

            # Schedule batch execution if not already scheduled
            if self._batch_task is None:
                self._batch_task = asyncio.create_task(self._execute_batch())

            # Check if batch is full
            if len(self._batch_keys) >= self.max_batch_size:
                self._batch_task.cancel()
                self._batch_task = asyncio.create_task(self._execute_batch_now())

        return await future

    async def _execute_batch(self) -> None:
        """Wait for batch window then execute."""
        await asyncio.sleep(self.max_wait_ms / 1000)
        await self._execute_batch_now()

    async def _execute_batch_now(self) -> None:
        """Execute the batch immediately."""
        async with self._lock:
            if not self._batch_keys:
                return

            keys = list(self._batch_keys)
            futures = {k: self._pending[k] for k in keys}

            self._batch_keys.clear()
            self._pending.clear()
            self._batch_task = None

        try:
            # Execute batch function
            results = await self.batch_fn(keys)

            # Resolve futures
            for key, future in futures.items():
                if key in results:
                    future.set_result(results[key])
                else:
                    future.set_exception(KeyError(f"Key not found: {key}"))

            logger.debug(f"Executed batch of {len(keys)} requests")

        except Exception as e:
            # Propagate exception to all waiters
            for future in futures.values():
                if not future.done():
                    future.set_exception(e)


def coalesce(key_fn: Callable[..., str], cache_ttl: float = 0):
    """
    Decorator to add request coalescing to an async function.

    Args:
        key_fn: Function to generate cache key from arguments
        cache_ttl: How long to cache results

    Usage:
        @coalesce(key_fn=lambda user_id: f"user:{user_id}", cache_ttl=60)
        async def get_user(user_id: str) -> dict:
            return await db.get_user(user_id)
    """
    coalescer = RequestCoalescer(cache_ttl=cache_ttl)

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            key = key_fn(*args, **kwargs)
            return await coalescer.coalesce(
                key=key,
                fetch_fn=lambda: fn(*args, **kwargs)
            )

        wrapper.coalescer = coalescer
        wrapper.invalidate = coalescer.invalidate
        wrapper.clear_cache = coalescer.clear_cache

        return wrapper

    return decorator


# Global coalescer instance
_default_coalescer: Optional[RequestCoalescer] = None


def get_coalescer() -> RequestCoalescer:
    """Get the global request coalescer."""
    global _default_coalescer
    if _default_coalescer is None:
        _default_coalescer = RequestCoalescer(cache_ttl=60)
    return _default_coalescer
