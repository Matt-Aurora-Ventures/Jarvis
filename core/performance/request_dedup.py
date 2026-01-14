"""
JARVIS Request Deduplication

Prevents duplicate concurrent requests from executing multiple times.
When multiple identical requests arrive simultaneously, only one
actually executes and others wait for and share the result.
"""

from typing import TypeVar, Generic, Dict, Optional, Any, Callable, Hashable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PendingRequest(Generic[T]):
    """Represents a pending request being deduplicated."""
    key: str
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.utcnow)
    waiters: int = 1


@dataclass
class DeduplicationResult(Generic[T]):
    """Result of a deduplicated request."""
    value: T
    was_deduplicated: bool
    original_request_time: datetime
    wait_time_ms: float = 0


class RequestDeduplicator(Generic[T]):
    """
    Deduplicates concurrent identical requests.

    When multiple requests with the same key arrive while one is being
    processed, subsequent requests wait for and share the first result.

    Usage:
        dedup = RequestDeduplicator()

        async def fetch_data(user_id: str) -> dict:
            return await dedup.execute(
                key=f"fetch_user:{user_id}",
                func=lambda: api.fetch_user(user_id)
            )
    """

    def __init__(self, ttl_seconds: float = 5.0):
        self._pending: Dict[str, PendingRequest] = {}
        self._lock = asyncio.Lock()
        self._ttl = timedelta(seconds=ttl_seconds)
        self._stats = {
            "total_requests": 0,
            "deduplicated": 0,
            "executed": 0,
        }

    async def execute(
        self,
        key: str,
        func: Callable[[], Any],
    ) -> DeduplicationResult[T]:
        """
        Execute a request with deduplication.

        If an identical request is already pending, wait for its result.
        """
        self._stats["total_requests"] += 1
        start_time = datetime.utcnow()

        async with self._lock:
            # Check for pending request
            if key in self._pending:
                pending = self._pending[key]

                # Check if still valid
                if datetime.utcnow() - pending.created_at < self._ttl:
                    pending.waiters += 1
                    self._stats["deduplicated"] += 1
                    logger.debug(f"Deduplicated request: {key} (waiters: {pending.waiters})")

                    # Wait for result outside lock
                    future = pending.future
                    wait_start = datetime.utcnow()
                else:
                    # Expired, create new
                    future = asyncio.Future()
                    self._pending[key] = PendingRequest(key=key, future=future)
                    self._stats["executed"] += 1
                    future = None  # Will execute
                    wait_start = None
            else:
                # No pending request, create one
                future = asyncio.Future()
                self._pending[key] = PendingRequest(key=key, future=future)
                self._stats["executed"] += 1
                future = None  # Will execute
                wait_start = None

        if future is not None:
            # Wait for existing request
            try:
                result = await future
                wait_time = (datetime.utcnow() - wait_start).total_seconds() * 1000
                return DeduplicationResult(
                    value=result,
                    was_deduplicated=True,
                    original_request_time=start_time,
                    wait_time_ms=wait_time,
                )
            except Exception as e:
                raise e
        else:
            # Execute the request
            try:
                result = await func()

                # Set result for waiters
                async with self._lock:
                    if key in self._pending:
                        self._pending[key].future.set_result(result)
                        del self._pending[key]

                return DeduplicationResult(
                    value=result,
                    was_deduplicated=False,
                    original_request_time=start_time,
                )

            except Exception as e:
                # Propagate exception to waiters
                async with self._lock:
                    if key in self._pending:
                        self._pending[key].future.set_exception(e)
                        del self._pending[key]
                raise

    async def cleanup_expired(self) -> int:
        """Clean up expired pending requests."""
        async with self._lock:
            now = datetime.utcnow()
            expired = [
                key for key, pending in self._pending.items()
                if now - pending.created_at > self._ttl
            ]

            for key in expired:
                pending = self._pending.pop(key)
                if not pending.future.done():
                    pending.future.cancel()

            return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        return {
            **self._stats,
            "pending_count": len(self._pending),
            "dedup_rate": (
                self._stats["deduplicated"] / self._stats["total_requests"]
                if self._stats["total_requests"] > 0 else 0
            ),
        }


def deduplicate(
    key_func: Optional[Callable[..., str]] = None,
    ttl_seconds: float = 5.0,
):
    """
    Decorator for request deduplication.

    Usage:
        @deduplicate(key_func=lambda user_id: f"get_user:{user_id}")
        async def get_user(user_id: str) -> dict:
            return await db.fetch_user(user_id)

        # Or with automatic key generation
        @deduplicate()
        async def fetch_prices(symbol: str) -> dict:
            return await api.get_prices(symbol)
    """
    dedup = RequestDeduplicator(ttl_seconds=ttl_seconds)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Auto-generate from function name and args
                key = _generate_key(func.__name__, args, kwargs)

            result = await dedup.execute(
                key=key,
                func=lambda: func(*args, **kwargs),
            )

            return result.value

        # Attach stats access
        wrapper.get_stats = dedup.get_stats
        return wrapper

    return decorator


def _generate_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a cache key from function name and arguments."""
    try:
        key_parts = [func_name]

        for arg in args:
            if isinstance(arg, Hashable):
                key_parts.append(str(hash(arg)))
            else:
                key_parts.append(hashlib.md5(
                    json.dumps(arg, sort_keys=True, default=str).encode()
                ).hexdigest()[:8])

        for k, v in sorted(kwargs.items()):
            if isinstance(v, Hashable):
                key_parts.append(f"{k}:{hash(v)}")
            else:
                key_parts.append(f"{k}:{hashlib.md5(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:8]}")

        return ":".join(key_parts)
    except Exception:
        # Fallback to simple key
        return f"{func_name}:{id(args)}:{id(kwargs)}"


class RequestCoalescer:
    """
    Coalesces multiple rapid requests into batches.

    Waits for a short period to collect requests, then processes
    them together for efficiency.

    Usage:
        coalescer = RequestCoalescer(
            batch_func=lambda ids: db.fetch_users_batch(ids),
            wait_ms=50,
            max_batch_size=100
        )

        # These calls made within 50ms will be batched
        user1 = await coalescer.get("user_1")
        user2 = await coalescer.get("user_2")
    """

    def __init__(
        self,
        batch_func: Callable[[list], Any],
        wait_ms: int = 50,
        max_batch_size: int = 100,
    ):
        self._batch_func = batch_func
        self._wait_ms = wait_ms
        self._max_batch_size = max_batch_size
        self._pending: Dict[str, asyncio.Future] = {}
        self._batch: list = []
        self._batch_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._processing = False
        self._stats = {
            "total_requests": 0,
            "batches_processed": 0,
            "avg_batch_size": 0,
        }

    async def get(self, key: str) -> Any:
        """Get a value, coalescing with other concurrent requests."""
        self._stats["total_requests"] += 1

        async with self._lock:
            if key in self._pending:
                # Already pending, wait for it
                return await self._pending[key]

            # Create future for this request
            future = asyncio.Future()
            self._pending[key] = future
            self._batch.append(key)

            # Start processing if batch is full or not already processing
            if len(self._batch) >= self._max_batch_size:
                asyncio.create_task(self._process_batch())
            elif not self._processing:
                self._processing = True
                asyncio.create_task(self._wait_and_process())

        return await future

    async def _wait_and_process(self):
        """Wait for more requests, then process batch."""
        await asyncio.sleep(self._wait_ms / 1000)
        await self._process_batch()
        self._processing = False

    async def _process_batch(self):
        """Process the current batch."""
        async with self._lock:
            if not self._batch:
                return

            batch = self._batch.copy()
            self._batch.clear()

        try:
            # Execute batch function
            results = await self._batch_func(batch)

            # Distribute results
            if isinstance(results, dict):
                for key in batch:
                    if key in self._pending:
                        future = self._pending.pop(key)
                        if key in results:
                            future.set_result(results[key])
                        else:
                            future.set_exception(KeyError(f"Key not in results: {key}"))
            elif isinstance(results, list):
                for i, key in enumerate(batch):
                    if key in self._pending:
                        future = self._pending.pop(key)
                        if i < len(results):
                            future.set_result(results[i])
                        else:
                            future.set_exception(IndexError(f"No result for index {i}"))

            # Update stats
            self._stats["batches_processed"] += 1
            total_batches = self._stats["batches_processed"]
            self._stats["avg_batch_size"] = (
                (self._stats["avg_batch_size"] * (total_batches - 1) + len(batch))
                / total_batches
            )

        except Exception as e:
            # Propagate exception to all waiters
            for key in batch:
                if key in self._pending:
                    future = self._pending.pop(key)
                    future.set_exception(e)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "pending_count": len(self._pending),
            "current_batch_size": len(self._batch),
        }


# Global deduplicator for common use
_global_dedup: Optional[RequestDeduplicator] = None


def get_global_deduplicator() -> RequestDeduplicator:
    """Get the global request deduplicator."""
    global _global_dedup
    if _global_dedup is None:
        _global_dedup = RequestDeduplicator()
    return _global_dedup


async def deduplicated_execute(key: str, func: Callable) -> Any:
    """Execute a function with global deduplication."""
    dedup = get_global_deduplicator()
    result = await dedup.execute(key, func)
    return result.value
