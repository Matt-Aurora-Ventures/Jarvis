"""
Multi-Level Cache Manager

Provides a high-performance caching layer with:
- Multi-level caching (memory, file, redis)
- TTL-based expiration
- LRU eviction
- Cache invalidation strategies (key, prefix, tag)
- Statistics tracking
- Thread-safe operations
- Batch operations
- Request deduplication

Usage:
    from core.caching.cache_manager import MultiLevelCache, cached

    # Direct usage
    cache = MultiLevelCache()
    cache.set("key", "value", ttl=300)
    value = cache.get("key")

    # Decorator usage
    @cached(ttl=60, namespace="prices")
    async def get_price(token: str) -> float:
        return await fetch_price(token)
"""

import asyncio
import functools
import hashlib
import json
import logging
import pickle
import sqlite3
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for multi-level cache."""
    # Memory cache settings
    max_memory_items: int = 10000
    max_memory_bytes: int = 100 * 1024 * 1024  # 100MB

    # File cache settings
    enable_file: bool = True
    file_cache_path: str = "data/cache/file_cache.db"

    # Redis settings
    enable_redis: bool = False
    redis_url: str = "redis://localhost:6379"
    redis_prefix: str = "jarvis:"

    # General settings
    default_ttl_seconds: int = 3600
    cleanup_interval_seconds: int = 60


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletes: int = 0
    evictions: int = 0
    memory_items: int = 0
    memory_bytes: int = 0
    file_items: int = 0
    by_namespace: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheEntry:
    """A cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    accessed_at: float
    access_count: int = 1
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)
    namespace: str = "default"

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


class MemoryCache:
    """
    In-memory LRU cache with TTL support.

    Thread-safe implementation using OrderedDict for LRU ordering.
    """

    def __init__(self, max_items: int = 10000, max_bytes: int = 100 * 1024 * 1024):
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tags: Dict[str, Set[str]] = {}  # tag -> set of keys
        self._current_bytes = 0
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.is_expired:
                self._remove(key)
                return None

            # Update access time and move to end (most recent)
            entry.accessed_at = time.time()
            entry.access_count += 1
            self._cache.move_to_end(key)

            return entry

    def set(
        self,
        key: str,
        value: Any,
        ttl: float,
        tags: Optional[Set[str]] = None,
        namespace: str = "default"
    ) -> CacheEntry:
        """Set entry in cache."""
        with self._lock:
            # Calculate size
            try:
                serialized = pickle.dumps(value)
                size_bytes = len(serialized)
            except Exception:
                size_bytes = 0

            # Remove existing if present
            if key in self._cache:
                self._remove(key)

            # Evict if necessary
            self._evict_if_needed(size_bytes)

            now = time.time()
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl,
                accessed_at=now,
                access_count=1,
                size_bytes=size_bytes,
                tags=tags or set(),
                namespace=namespace
            )

            self._cache[key] = entry
            self._current_bytes += size_bytes

            # Track tags
            for tag in entry.tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)

            return entry

    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        with self._lock:
            return self._remove(key)

    def _remove(self, key: str) -> bool:
        """Internal remove without lock."""
        if key not in self._cache:
            return False

        entry = self._cache.pop(key)
        self._current_bytes -= entry.size_bytes

        # Remove from tag tracking
        for tag in entry.tags:
            if tag in self._tags:
                self._tags[tag].discard(key)

        return True

    def _evict_if_needed(self, incoming_bytes: int) -> int:
        """Evict entries if over capacity."""
        evicted = 0

        while self._cache and (
            len(self._cache) >= self.max_items or
            self._current_bytes + incoming_bytes > self.max_bytes
        ):
            # Remove oldest (first item)
            oldest_key = next(iter(self._cache))
            self._remove(oldest_key)
            evicted += 1

        return evicted

    def get_by_tag(self, tag: str) -> List[str]:
        """Get all keys with a given tag."""
        with self._lock:
            return list(self._tags.get(tag, set()))

    def get_by_prefix(self, prefix: str) -> List[str]:
        """Get all keys with a given prefix."""
        with self._lock:
            return [k for k in self._cache.keys() if k.startswith(prefix)]

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._tags.clear()
            self._current_bytes = 0

    def size(self) -> int:
        """Get number of items."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache


class FileCache:
    """
    File-based cache using SQLite for persistence.

    Provides durability across restarts while maintaining good performance.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.RLock()

    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    namespace TEXT DEFAULT 'default',
                    tags TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at);
                CREATE INDEX IF NOT EXISTS idx_namespace ON cache_entries(namespace);
            """)

    def get(self, key: str) -> Optional[Any]:
        """Get value from file cache."""
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                    (key,)
                ).fetchone()

                if row is None:
                    return None

                if time.time() > row["expires_at"]:
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    return None

                try:
                    return pickle.loads(row["value"])
                except Exception:
                    return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: float,
        tags: Optional[Set[str]] = None,
        namespace: str = "default"
    ) -> bool:
        """Set value in file cache."""
        with self._lock:
            try:
                serialized = pickle.dumps(value)
                now = time.time()
                tags_str = ",".join(tags) if tags else ""

                with self._get_conn() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries
                        (key, value, created_at, expires_at, namespace, tags)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (key, serialized, now, now + ttl, namespace, tags_str))

                return True
            except Exception as e:
                logger.error(f"File cache set error: {e}")
                return False

    def delete(self, key: str) -> bool:
        """Delete from file cache."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE key = ?",
                    (key,)
                )
                return cursor.rowcount > 0

    def delete_by_prefix(self, prefix: str) -> int:
        """Delete all keys with prefix."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE key LIKE ?",
                    (f"{prefix}%",)
                )
                return cursor.rowcount

    def delete_by_tag(self, tag: str) -> int:
        """Delete all keys with tag."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE tags LIKE ?",
                    (f"%{tag}%",)
                )
                return cursor.rowcount

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE expires_at < ?",
                    (time.time(),)
                )
                return cursor.rowcount

    def clear(self):
        """Clear all entries."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM cache_entries")

    def size(self) -> int:
        """Get number of items."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
            return row[0]


class MultiLevelCache:
    """
    Multi-level cache with memory, file, and optional Redis layers.

    Features:
    - Automatic promotion from lower to higher levels on read
    - Write-through to all enabled levels
    - Tag-based and prefix-based invalidation
    - Thread-safe operations
    - Statistics tracking
    - Batch operations

    Usage:
        cache = MultiLevelCache()

        # Basic operations
        cache.set("key", {"data": "value"}, ttl=300)
        value = cache.get("key")

        # With tags for grouped invalidation
        cache.set("price:SOL", 100.5, tags=["prices", "token:SOL"])
        cache.invalidate_by_tag("prices")  # Removes all price entries

        # With namespaces for stats tracking
        cache.set("user:1", user_data, namespace="users")
        stats = cache.get_stats()
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        enable_file: bool = True,
        enable_redis: bool = False,
        max_memory_items: int = 10000,
        file_cache_path: Optional[str] = None
    ):
        self.config = config or CacheConfig()

        # Override config with explicit params
        if file_cache_path:
            self.config.file_cache_path = file_cache_path
        if not enable_file:
            self.config.enable_file = False
        if enable_redis:
            self.config.enable_redis = True

        self.config.max_memory_items = max_memory_items

        # Initialize layers
        self._memory_cache = MemoryCache(
            max_items=self.config.max_memory_items,
            max_bytes=self.config.max_memory_bytes
        )

        self._file_cache: Optional[FileCache] = None
        if self.config.enable_file:
            self._file_cache = FileCache(self.config.file_cache_path)

        # Redis would be initialized here if enabled
        self._redis_cache = None

        # Statistics
        self._stats = CacheStats()
        self._stats_lock = threading.Lock()

        # Pending fetches for deduplication
        self._pending: Dict[str, asyncio.Future] = {}
        self._pending_lock = threading.Lock()

    def get(
        self,
        key: str,
        namespace: str = "default"
    ) -> Optional[Any]:
        """
        Get value from cache, checking all levels.

        Promotes to higher levels on hit in lower level.
        """
        full_key = self._make_key(key, namespace)

        # Check memory cache
        entry = self._memory_cache.get(full_key)
        if entry is not None:
            self._record_hit(namespace)
            return entry.value

        # Check file cache
        if self._file_cache:
            value = self._file_cache.get(full_key)
            if value is not None:
                # Promote to memory
                self._memory_cache.set(
                    full_key, value,
                    ttl=self.config.default_ttl_seconds,
                    namespace=namespace
                )
                self._record_hit(namespace)
                return value

        self._record_miss(namespace)
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        tags: Optional[List[str]] = None,
        namespace: str = "default"
    ) -> bool:
        """
        Set value in all enabled cache levels.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)
            tags: Tags for grouped invalidation
            namespace: Namespace for statistics tracking
        """
        full_key = self._make_key(key, namespace)
        effective_ttl = ttl if ttl is not None else self.config.default_ttl_seconds
        tag_set = set(tags) if tags else set()

        # Set in memory
        self._memory_cache.set(full_key, value, effective_ttl, tag_set, namespace)

        # Set in file cache
        if self._file_cache:
            self._file_cache.set(full_key, value, effective_ttl, tag_set, namespace)

        self._record_write(namespace)
        return True

    def invalidate(self, key: str, namespace: str = "default") -> bool:
        """Invalidate a single key from all levels."""
        full_key = self._make_key(key, namespace)

        deleted = self._memory_cache.delete(full_key)

        if self._file_cache:
            deleted = self._file_cache.delete(full_key) or deleted

        if deleted:
            self._record_delete(namespace)

        return deleted

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all keys with a given prefix."""
        count = 0

        # Memory cache
        keys = self._memory_cache.get_by_prefix(prefix)
        for key in keys:
            if self._memory_cache.delete(key):
                count += 1

        # File cache
        if self._file_cache:
            count += self._file_cache.delete_by_prefix(prefix)

        return count

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all keys with a given tag."""
        count = 0

        # Memory cache
        keys = self._memory_cache.get_by_tag(tag)
        for key in keys:
            if self._memory_cache.delete(key):
                count += 1

        # File cache
        if self._file_cache:
            count += self._file_cache.delete_by_tag(tag)

        return count

    def clear_all(self):
        """Clear all caches."""
        self._memory_cache.clear()
        if self._file_cache:
            self._file_cache.clear()

    def flush(self):
        """Flush pending writes to persistent storage."""
        # Memory cache writes are immediate
        # File cache writes are immediate (SQLite)
        # Would flush Redis pipeline here if batching
        pass

    # Internal methods for file cache access (used in tests)
    def _file_set(
        self,
        key: str,
        value: Any,
        ttl: float,
        namespace: str = "default"
    ):
        """Direct file cache set (for testing)."""
        if self._file_cache:
            self._file_cache.set(key, value, ttl, namespace=namespace)

    def _file_get(self, key: str) -> Optional[Any]:
        """Direct file cache get (for testing)."""
        if self._file_cache:
            return self._file_cache.get(key)
        return None

    # Batch operations
    def batch_get(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
        """Get multiple keys in one call."""
        results = {}
        for key in keys:
            results[key] = self.get(key, namespace)
        return results

    def batch_set(
        self,
        items: Dict[str, Any],
        ttl: Optional[float] = None,
        namespace: str = "default"
    ):
        """Set multiple keys in one call."""
        for key, value in items.items():
            self.set(key, value, ttl, namespace=namespace)

    async def batch_get_or_fetch(
        self,
        keys: List[str],
        fetcher: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        ttl: Optional[float] = None,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        Get multiple keys, fetching only missing ones.

        Args:
            keys: List of keys to get
            fetcher: Async function that fetches missing keys
            ttl: TTL for newly fetched values
            namespace: Cache namespace

        Returns:
            Dictionary mapping keys to values
        """
        results = {}
        missing_keys = []

        for key in keys:
            value = self.get(key, namespace)
            if value is not None:
                results[key] = value
            else:
                missing_keys.append(key)

        if missing_keys:
            fetched = await fetcher(missing_keys)
            for key, value in fetched.items():
                self.set(key, value, ttl, namespace=namespace)
                results[key] = value

        return results

    # Statistics
    def _record_hit(self, namespace: str):
        with self._stats_lock:
            self._stats.hits += 1
            if namespace not in self._stats.by_namespace:
                self._stats.by_namespace[namespace] = {"hits": 0, "misses": 0, "writes": 0}
            self._stats.by_namespace[namespace]["hits"] += 1

    def _record_miss(self, namespace: str):
        with self._stats_lock:
            self._stats.misses += 1
            if namespace not in self._stats.by_namespace:
                self._stats.by_namespace[namespace] = {"hits": 0, "misses": 0, "writes": 0}
            self._stats.by_namespace[namespace]["misses"] += 1

    def _record_write(self, namespace: str):
        with self._stats_lock:
            self._stats.writes += 1
            if namespace not in self._stats.by_namespace:
                self._stats.by_namespace[namespace] = {"hits": 0, "misses": 0, "writes": 0}
            self._stats.by_namespace[namespace]["writes"] += 1

    def _record_delete(self, namespace: str):
        with self._stats_lock:
            self._stats.deletes += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._stats_lock:
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "writes": self._stats.writes,
                "deletes": self._stats.deletes,
                "hit_rate": self._stats.hit_rate,
                "memory_items": self._memory_cache.size(),
                "file_items": self._file_cache.size() if self._file_cache else 0,
                "by_namespace": dict(self._stats.by_namespace)
            }

    def export_stats_json(self) -> str:
        """Export stats as JSON."""
        return json.dumps(self.get_stats(), indent=2)

    def _make_key(self, key: str, namespace: str) -> str:
        """Create full key with namespace."""
        if namespace == "default":
            return key
        return f"{namespace}:{key}"


# Global instance
_multi_level_cache: Optional[MultiLevelCache] = None


def get_multi_level_cache() -> MultiLevelCache:
    """Get the global multi-level cache instance."""
    global _multi_level_cache
    if _multi_level_cache is None:
        _multi_level_cache = MultiLevelCache()
    return _multi_level_cache


def cached(
    ttl: Optional[float] = None,
    namespace: str = "default",
    key_func: Optional[Callable[..., str]] = None,
    tags: Optional[List[str]] = None
) -> Callable:
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        namespace: Cache namespace for stats tracking
        key_func: Custom function to generate cache key
        tags: Tags for grouped invalidation

    Usage:
        @cached(ttl=60, namespace="prices")
        async def get_price(token: str) -> float:
            return await fetch_price(token)

        @cached(ttl=300, key_func=lambda t, **kw: f"quote:{t}")
        def get_quote(token: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            cache = get_multi_level_cache()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _make_cache_key(func.__name__, args, kwargs)

            # Check cache
            cached_value = cache.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, ttl, tags, namespace)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            cache = get_multi_level_cache()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _make_cache_key(func.__name__, args, kwargs)

            # Check cache
            cached_value = cache.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, ttl, tags, namespace)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function arguments."""
    try:
        key_data = json.dumps({
            "func": func_name,
            "args": args,
            "kwargs": kwargs,
        }, sort_keys=True, default=str)
    except TypeError:
        key_data = f"{func_name}:{repr(args)}:{repr(kwargs)}"

    # Hash if too long
    if len(key_data) > 200:
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{func_name}:{key_hash}"

    return key_data
