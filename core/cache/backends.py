"""
Cache Backend Implementations

Provides multiple caching strategies:
- InMemoryCache: Fast, single-process caching
- FileCache: Persistent JSON file caching
- TTLCache: Time-based expiration
- LRUCache: Least Recently Used eviction

Usage:
    from core.cache.backends import InMemoryCache, FileCache, TTLCache, LRUCache

    # In-memory with max size
    cache = InMemoryCache(max_size=1000)
    cache.set("key", "value")

    # File-based persistence
    cache = FileCache(cache_dir="bots/data/cache")
    cache.set("key", {"data": "value"}, ttl_seconds=300)

    # TTL-based expiration
    cache = TTLCache(default_ttl=60)  # 1 minute default
    cache.set("key", "value")  # Expires in 60 seconds

    # LRU eviction
    cache = LRUCache(max_size=100)  # Evicts least recently used when full
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached entry with metadata."""
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class TTLCacheStats:
    """Lightweight stats container for TTLCache integration tests."""
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletes: int = 0
    evictions: int = 0
    entries: int = 0


class InMemoryCache:
    """
    Fast in-memory cache with max size eviction.

    Thread-safe implementation suitable for single-process applications.
    When max_size is reached, oldest entries are evicted.

    Args:
        max_size: Maximum number of entries (default: 1000)
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                return None

            if entry.is_expired:
                del self._cache[key]
                return None

            entry.access_count += 1
            entry.last_accessed = time.time()
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a value in the cache."""
        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                # Remove oldest by creation time
                if self._cache:
                    oldest_key = min(
                        self._cache.keys(),
                        key=lambda k: self._cache[k].created_at
                    )
                    del self._cache[oldest_key]
                else:
                    break

            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + ttl_seconds if ttl_seconds else None,
                access_count=1,
                last_accessed=now,
            )
            self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of entries."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists (and is not expired)."""
        return self.get(key) is not None


class FileCache:
    """
    Persistent cache using JSON files.

    Each cache entry is stored as a separate JSON file.
    Suitable for data that should survive process restarts.

    Args:
        cache_dir: Directory for cache files
        default_ttl: Default TTL in seconds (default: 3600)
    """

    def __init__(self, cache_dir: str, default_ttl: int = 3600):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self._lock = threading.RLock()

        # Ensure cache directory exists
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return Path(self.cache_dir) / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        with self._lock:
            file_path = self._get_file_path(key)

            if not file_path.exists():
                return None

            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                # Check expiration
                expires_at = data.get("expires_at")
                if expires_at and time.time() > expires_at:
                    file_path.unlink(missing_ok=True)
                    return None

                # Check key match (in case of hash collision)
                if data.get("key") != key:
                    return None

                return data.get("value")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"FileCache read error: {e}")
                return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a value in the cache."""
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        with self._lock:
            file_path = self._get_file_path(key)

            try:
                data = {
                    "key": key,
                    "value": value,
                    "created_at": time.time(),
                    "expires_at": time.time() + effective_ttl,
                }

                with open(file_path, 'w') as f:
                    json.dump(data, f, default=str)
            except (IOError, TypeError) as e:
                logger.warning(f"FileCache write error: {e}")

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self._lock:
            file_path = self._get_file_path(key)

            if file_path.exists():
                try:
                    file_path.unlink()
                    return True
                except IOError:
                    return False
            return False

    def clear(self) -> None:
        """Clear all cache files."""
        with self._lock:
            cache_path = Path(self.cache_dir)

            if not cache_path.exists():
                return

            for file_path in cache_path.glob("*.json"):
                try:
                    file_path.unlink()
                except IOError:
                    continue

    def cleanup_expired(self) -> int:
        """Remove expired cache files."""
        count = 0
        now = time.time()

        with self._lock:
            cache_path = Path(self.cache_dir)

            if not cache_path.exists():
                return 0

            for file_path in cache_path.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)

                    expires_at = data.get("expires_at")
                    if expires_at and now > expires_at:
                        file_path.unlink()
                        count += 1
                except (json.JSONDecodeError, IOError):
                    continue

        return count


class TTLCache:
    """
    Cache with automatic time-based expiration.

    All entries have a TTL and are automatically expired on access.

    Args:
        default_ttl: Default TTL in seconds
        max_size: Maximum number of entries (default: 10000)
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 10000):
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = TTLCacheStats()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                return None

            entry.access_count += 1
            entry.last_accessed = time.time()
            self._stats.hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a value with TTL."""
        # Backward compatibility: accept both ttl_seconds and ttl keyword names.
        effective_ttl = (
            ttl
            if ttl is not None
            else ttl_seconds if ttl_seconds is not None else self.default_ttl
        )

        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                if self._evict_oldest():
                    self._stats.evictions += 1

            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + effective_ttl,
                access_count=1,
                last_accessed=now,
            )
            self._cache[key] = entry
            self._stats.writes += 1

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.deletes += 1
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        count = 0
        now = time.time()

        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and entry.expires_at < now
            ]

            for key in expired_keys:
                del self._cache[key]
                count += 1

        return count

    def _evict_oldest(self) -> bool:
        """Evict the oldest entry."""
        if self._cache:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            del self._cache[oldest_key]
            return True
        return False

    def size(self) -> int:
        """Get number of entries."""
        return len(self._cache)

    def get_stats(self) -> TTLCacheStats:
        """Return cache statistics in a test-friendly shape."""
        with self._lock:
            self._stats.entries = len(self._cache)
            return TTLCacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                writes=self._stats.writes,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions,
                entries=self._stats.entries,
            )


class LRUCache:
    """
    Least Recently Used (LRU) cache.

    When the cache is full, the least recently accessed entry is evicted.
    Uses OrderedDict for O(1) LRU operations.

    Args:
        max_size: Maximum number of entries
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get a value and mark it as recently used."""
        with self._lock:
            if key not in self._cache:
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any, **kwargs) -> None:
        """Set a value, evicting LRU if necessary."""
        with self._lock:
            if key in self._cache:
                # Update existing and move to end
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                # Evict LRU if at capacity
                while len(self._cache) >= self.max_size:
                    # Remove first item (least recently used)
                    self._cache.popitem(last=False)

                self._cache[key] = value

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get number of entries."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._cache
