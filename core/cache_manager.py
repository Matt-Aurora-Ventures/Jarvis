"""
Cache Manager - Multi-layer caching with TTL and invalidation.
Supports in-memory, file-based, and Redis-compatible caching.
"""
import asyncio
import hashlib
import pickle
import sqlite3
import threading

from core.security.safe_pickle import safe_pickle_loads
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import json


class CacheLayer(Enum):
    """Cache layers."""
    MEMORY = "memory"              # In-memory LRU cache
    FILE = "file"                  # File-based cache
    DATABASE = "database"          # SQLite cache
    REDIS = "redis"                # Redis (if available)


class CachePolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"                    # Least Recently Used
    LFU = "lfu"                    # Least Frequently Used
    FIFO = "fifo"                  # First In First Out
    TTL = "ttl"                    # Time To Live only


@dataclass
class CacheEntry:
    """A cache entry."""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    expires_at: Optional[datetime]
    access_count: int
    size_bytes: int
    layer: CacheLayer
    metadata: Dict = field(default_factory=dict)


@dataclass
class CacheConfig:
    """Cache configuration."""
    max_memory_items: int = 10000
    max_memory_bytes: int = 100 * 1024 * 1024  # 100MB
    default_ttl_seconds: int = 3600
    policy: CachePolicy = CachePolicy.LRU
    layers: List[CacheLayer] = field(
        default_factory=lambda: [CacheLayer.MEMORY, CacheLayer.DATABASE]
    )
    persist_to_disk: bool = True
    compression: bool = False


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    writes: int = 0
    deletes: int = 0
    memory_items: int = 0
    memory_bytes: int = 0
    disk_items: int = 0
    disk_bytes: int = 0


class LRUCache:
    """In-memory LRU cache implementation."""

    def __init__(self, max_items: int = 10000, max_bytes: int = 100 * 1024 * 1024):
        self.max_items = max_items
        self.max_bytes = max_bytes
        self.cache: OrderedDict = OrderedDict()
        self.sizes: Dict[str, int] = {}
        self.current_bytes = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self.cache:
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]

    def set(self, key: str, value: Any, size_bytes: int = 0) -> bool:
        """Set value in cache."""
        with self._lock:
            # Remove if exists
            if key in self.cache:
                self.current_bytes -= self.sizes.get(key, 0)
                del self.cache[key]

            # Evict if necessary
            while (len(self.cache) >= self.max_items or
                   self.current_bytes + size_bytes > self.max_bytes):
                if not self.cache:
                    break
                oldest_key, _ = self.cache.popitem(last=False)
                self.current_bytes -= self.sizes.pop(oldest_key, 0)

            self.cache[key] = value
            self.sizes[key] = size_bytes
            self.current_bytes += size_bytes
            return True

    def delete(self, key: str) -> bool:
        """Delete from cache."""
        with self._lock:
            if key in self.cache:
                self.current_bytes -= self.sizes.pop(key, 0)
                del self.cache[key]
                return True
            return False

    def clear(self):
        """Clear the cache."""
        with self._lock:
            self.cache.clear()
            self.sizes.clear()
            self.current_bytes = 0

    def size(self) -> int:
        """Get number of items."""
        return len(self.cache)


class CacheManager:
    """
    Multi-layer cache manager with TTL and multiple eviction policies.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config: Optional[CacheConfig] = None
    ):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "cache.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.config = config or CacheConfig()
        self._init_db()

        # Memory cache
        self.memory_cache = LRUCache(
            max_items=self.config.max_memory_items,
            max_bytes=self.config.max_memory_bytes
        )

        # TTL tracking
        self.ttl_map: Dict[str, datetime] = {}

        # Statistics
        self.stats = CacheStats()

        # Invalidation callbacks
        self.invalidation_callbacks: Dict[str, List[Callable]] = {}

        self._lock = threading.Lock()

        # Start cleanup task
        self._cleanup_running = False

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    expires_at TEXT,
                    access_count INTEGER DEFAULT 1,
                    size_bytes INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS cache_tags (
                    key TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (key, tag),
                    FOREIGN KEY (key) REFERENCES cache(key)
                );

                CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
                CREATE INDEX IF NOT EXISTS idx_cache_accessed ON cache(accessed_at);
                CREATE INDEX IF NOT EXISTS idx_tags_tag ON cache_tags(tag);
            """)

    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage.

        WARNING: Cache poisoning could lead to code execution.
        Consider switching to JSON for non-ML data.
        """
        return safe_pickle_loads(data)

    def _cache_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Generate cache key with optional namespace."""
        if namespace:
            return f"{namespace}:{key}"
        return key

    def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """Get value from cache."""
        cache_key = self._cache_key(key, namespace)

        # Check memory cache first
        if CacheLayer.MEMORY in self.config.layers:
            value = self.memory_cache.get(cache_key)
            if value is not None:
                # Check TTL
                if cache_key in self.ttl_map:
                    if datetime.now() > self.ttl_map[cache_key]:
                        self.delete(key, namespace)
                        self.stats.misses += 1
                        return default

                self.stats.hits += 1
                return value

        # Check database cache
        if CacheLayer.DATABASE in self.config.layers:
            with self._get_db() as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?",
                    (cache_key,)
                ).fetchone()

                if row:
                    # Check expiry
                    if row["expires_at"]:
                        expires = datetime.fromisoformat(row["expires_at"])
                        if datetime.now() > expires:
                            self.delete(key, namespace)
                            self.stats.misses += 1
                            return default

                    value = self._deserialize(row["value"])

                    # Update access time
                    conn.execute("""
                        UPDATE cache SET
                        accessed_at = ?, access_count = access_count + 1
                        WHERE key = ?
                    """, (datetime.now().isoformat(), cache_key))

                    # Promote to memory cache
                    if CacheLayer.MEMORY in self.config.layers:
                        self.memory_cache.set(cache_key, value, len(row["value"]))

                    self.stats.hits += 1
                    return value

        self.stats.misses += 1
        return default

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in cache."""
        cache_key = self._cache_key(key, namespace)
        serialized = self._serialize(value)
        size_bytes = len(serialized)

        now = datetime.now()
        ttl = ttl if ttl is not None else self.config.default_ttl_seconds
        expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None

        # Set in memory cache
        if CacheLayer.MEMORY in self.config.layers:
            self.memory_cache.set(cache_key, value, size_bytes)
            if expires_at:
                self.ttl_map[cache_key] = expires_at

        # Set in database cache
        if CacheLayer.DATABASE in self.config.layers:
            with self._get_db() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache
                    (key, value, created_at, accessed_at, expires_at, access_count, size_bytes, metadata)
                    VALUES (?, ?, ?, ?, ?, 1, ?, '{}')
                """, (
                    cache_key, serialized, now.isoformat(), now.isoformat(),
                    expires_at.isoformat() if expires_at else None, size_bytes
                ))

                # Set tags
                if tags:
                    conn.execute("DELETE FROM cache_tags WHERE key = ?", (cache_key,))
                    for tag in tags:
                        conn.execute(
                            "INSERT INTO cache_tags (key, tag) VALUES (?, ?)",
                            (cache_key, tag)
                        )

        self.stats.writes += 1
        return True

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete from cache."""
        cache_key = self._cache_key(key, namespace)

        # Delete from memory
        if CacheLayer.MEMORY in self.config.layers:
            self.memory_cache.delete(cache_key)
            self.ttl_map.pop(cache_key, None)

        # Delete from database
        if CacheLayer.DATABASE in self.config.layers:
            with self._get_db() as conn:
                conn.execute("DELETE FROM cache_tags WHERE key = ?", (cache_key,))
                cursor = conn.execute("DELETE FROM cache WHERE key = ?", (cache_key,))

        self.stats.deletes += 1

        # Trigger invalidation callbacks
        if cache_key in self.invalidation_callbacks:
            for callback in self.invalidation_callbacks[cache_key]:
                try:
                    callback(cache_key)
                except Exception:
                    pass

        return True

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a tag."""
        count = 0

        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT key FROM cache_tags WHERE tag = ?",
                (tag,)
            ).fetchall()

            for row in rows:
                self.delete(row["key"])
                count += 1

        return count

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all cache entries with a key prefix."""
        count = 0

        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT key FROM cache WHERE key LIKE ?",
                (f"{prefix}%",)
            ).fetchall()

            for row in rows:
                self.delete(row["key"])
                count += 1

        return count

    def clear(self, namespace: Optional[str] = None):
        """Clear cache."""
        if namespace:
            self.invalidate_by_prefix(f"{namespace}:")
        else:
            self.memory_cache.clear()
            self.ttl_map.clear()

            with self._get_db() as conn:
                conn.execute("DELETE FROM cache_tags")
                conn.execute("DELETE FROM cache")

    def cleanup_expired(self) -> int:
        """Clean up expired entries."""
        count = 0
        now = datetime.now()

        # Clean memory cache
        for key in list(self.ttl_map.keys()):
            if self.ttl_map[key] < now:
                self.memory_cache.delete(key)
                del self.ttl_map[key]
                count += 1

        # Clean database cache
        with self._get_db() as conn:
            cursor = conn.execute("""
                DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?
            """, (now.isoformat(),))
            count += cursor.rowcount

        self.stats.evictions += count
        return count

    async def start_cleanup_task(self, interval_seconds: int = 60):
        """Start periodic cleanup task."""
        self._cleanup_running = True

        while self._cleanup_running:
            self.cleanup_expired()
            await asyncio.sleep(interval_seconds)

    def stop_cleanup_task(self):
        """Stop cleanup task."""
        self._cleanup_running = False

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> Any:
        """Get from cache or set using factory function."""
        value = self.get(key, namespace)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl, namespace)
        return value

    async def get_or_set_async(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> Any:
        """Async version of get_or_set."""
        value = self.get(key, namespace)
        if value is not None:
            return value

        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        self.set(key, value, ttl, namespace)
        return value

    def cached(
        self,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        key_builder: Optional[Callable] = None
    ):
        """Decorator for caching function results."""
        def decorator(func):
            import functools

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = self._build_key(func.__name__, args, kwargs)

                return self.get_or_set(cache_key, lambda: func(*args, **kwargs), ttl, namespace)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = self._build_key(func.__name__, args, kwargs)

                return await self.get_or_set_async(
                    cache_key, lambda: func(*args, **kwargs), ttl, namespace
                )

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper

        return decorator

    def _build_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Build cache key from function arguments."""
        key_parts = [func_name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def register_invalidation_callback(
        self,
        key: str,
        callback: Callable[[str], None]
    ):
        """Register callback for cache invalidation."""
        if key not in self.invalidation_callbacks:
            self.invalidation_callbacks[key] = []
        self.invalidation_callbacks[key].append(callback)

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        self.stats.memory_items = self.memory_cache.size()
        self.stats.memory_bytes = self.memory_cache.current_bytes

        with self._get_db() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as size
                FROM cache
            """).fetchone()
            self.stats.disk_items = row["count"]
            self.stats.disk_bytes = row["size"]

        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "hit_rate": self.stats.hits / (self.stats.hits + self.stats.misses)
                       if (self.stats.hits + self.stats.misses) > 0 else 0,
            "writes": self.stats.writes,
            "deletes": self.stats.deletes,
            "evictions": self.stats.evictions,
            "memory_items": self.stats.memory_items,
            "memory_bytes": self.stats.memory_bytes,
            "disk_items": self.stats.disk_items,
            "disk_bytes": self.stats.disk_bytes
        }


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the cache manager singleton."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
