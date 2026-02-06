"""
Caching Module for ClawdBots

Provides in-memory and file-based caching with:
- TTL (time-to-live) support
- Auto-eviction of expired entries
- LRU eviction when max entries reached
- Cache hit/miss statistics
- Thread-safe operations
- Optional file persistence

Usage:
    # Module-level (global cache)
    from bots.shared.cache import cache_get, cache_set, cache_stats

    cache_set("user_123", {"name": "Alice"}, ttl_seconds=3600)
    user = cache_get("user_123")
    stats = cache_stats()

    # Instance-level (custom cache)
    from bots.shared.cache import Cache

    cache = Cache(max_entries=500, default_ttl=1800)
    cache.cache_set("api_response", data)

    # Decorator for caching function results
    from bots.shared.cache import cached

    @cached(ttl_seconds=600)
    def expensive_api_call(endpoint):
        return requests.get(endpoint).json()
"""

import functools
import hashlib
import json
import logging
import os
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger("clawdbots.cache")

# Default paths
DEFAULT_CACHE_FILE = "/root/clawdbots/cache.json"
DEFAULT_MAX_ENTRIES = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    value: Any
    created_at: float
    expires_at: float
    last_accessed: float

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            "value": self.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Deserialize from dictionary."""
        return cls(
            value=data["value"],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            last_accessed=data.get("last_accessed", data["created_at"]),
        )


class Cache:
    """
    Thread-safe cache with TTL, LRU eviction, and optional file persistence.

    Args:
        persistence_path: Path to JSON file for persistence (None for memory-only)
        max_entries: Maximum number of entries before LRU eviction (default 1000)
        default_ttl: Default TTL in seconds for entries (default 3600)
        auto_persist: Whether to auto-persist on changes (default True)
        cleanup_interval: Seconds between auto-cleanup runs (default 60)
    """

    def __init__(
        self,
        persistence_path: Optional[str] = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        default_ttl: int = DEFAULT_TTL_SECONDS,
        auto_persist: bool = True,
        cleanup_interval: int = 60,
    ):
        self._persistence_path = persistence_path
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._auto_persist = auto_persist
        self._cleanup_interval = cleanup_interval

        # Thread safety
        self._lock = threading.RLock()

        # In-memory cache (OrderedDict for LRU ordering)
        self._memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # Statistics
        self._hits = 0
        self._misses = 0

        # Last cleanup time
        self._last_cleanup = time.time()

        # Load from persistence if available
        self._load_from_file()

        logger.debug(
            f"Cache initialized: max_entries={max_entries}, "
            f"default_ttl={default_ttl}, persistence={persistence_path}"
        )

    def _load_from_file(self) -> None:
        """Load cache from persistence file."""
        if not self._persistence_path:
            return

        try:
            path = Path(self._persistence_path)
            if not path.exists():
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.warning("Invalid cache file format, starting fresh")
                return

            # Load entries, filtering out expired ones
            now = time.time()
            for key, entry_data in data.items():
                if isinstance(entry_data, dict) and "expires_at" in entry_data:
                    if entry_data["expires_at"] > now:
                        self._memory_cache[key] = entry_data
                else:
                    # Legacy format or invalid entry, skip
                    pass

            logger.info(f"Loaded {len(self._memory_cache)} entries from cache file")

        except json.JSONDecodeError as e:
            logger.warning(f"Cache file corrupted, starting fresh: {e}")
        except Exception as e:
            logger.warning(f"Failed to load cache file: {e}")

    def _persist(self) -> None:
        """Persist cache to file."""
        if not self._persistence_path:
            return

        try:
            # Create parent directory if needed
            path = Path(self._persistence_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Filter out expired entries before persisting
            now = time.time()
            valid_entries = {
                k: v
                for k, v in self._memory_cache.items()
                if v.get("expires_at", 0) > now
            }

            # Write atomically (write to temp, then rename)
            temp_path = path.with_suffix(".json.tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(valid_entries, f, indent=2, ensure_ascii=False)

            # Atomic replace
            os.replace(temp_path, path)

            logger.debug(f"Persisted {len(valid_entries)} entries to cache file")

        except Exception as e:
            logger.error(f"Failed to persist cache: {e}")

    def _maybe_cleanup(self) -> None:
        """Periodically cleanup expired entries."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        with self._lock:
            now = time.time()
            expired_keys = [
                k
                for k, v in self._memory_cache.items()
                if v.get("expires_at", 0) <= now
            ]

            for key in expired_keys:
                del self._memory_cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

                if self._auto_persist:
                    self._persist()

    def _evict_lru(self) -> None:
        """Evict least recently used entries to make room."""
        with self._lock:
            while len(self._memory_cache) >= self._max_entries:
                # OrderedDict.popitem(last=False) removes oldest item
                oldest_key = next(iter(self._memory_cache))
                del self._memory_cache[oldest_key]
                logger.debug(f"Evicted LRU entry: {oldest_key}")

    def cache_get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache.

        Args:
            key: Cache key
            default: Value to return if key not found or expired

        Returns:
            Cached value or default
        """
        self._maybe_cleanup()

        with self._lock:
            entry = self._memory_cache.get(key)

            if entry is None:
                self._misses += 1
                return default

            # Check expiration
            if entry.get("expires_at", 0) <= time.time():
                # Expired - remove and return default
                del self._memory_cache[key]
                self._misses += 1
                return default

            # Cache hit - update access time and move to end (most recent)
            entry["last_accessed"] = time.time()
            self._memory_cache.move_to_end(key)
            self._hits += 1

            return entry.get("value")

    def cache_set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable for persistence)
            ttl_seconds: Time-to-live in seconds (uses default if not specified)
        """
        self._maybe_cleanup()

        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = time.time()

        entry = {
            "value": value,
            "created_at": now,
            "expires_at": now + ttl,
            "last_accessed": now,
        }

        with self._lock:
            # If key exists, update in place (maintains order)
            if key in self._memory_cache:
                self._memory_cache[key] = entry
                self._memory_cache.move_to_end(key)
            else:
                # New entry - may need to evict
                self._evict_lru()
                self._memory_cache[key] = entry

            if self._auto_persist:
                self._persist()

    def cache_delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._memory_cache:
                del self._memory_cache[key]

                if self._auto_persist:
                    self._persist()

                return True
            return False

    def cache_clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._memory_cache.clear()
            self._hits = 0
            self._misses = 0

            if self._auto_persist:
                self._persist()

        logger.info("Cache cleared")

    def cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Hit rate as float (0.0 to 1.0)
            - entries: Number of entries in cache
            - size_bytes: Estimated size of cache in bytes
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0

            # Estimate size
            try:
                size_bytes = len(json.dumps(dict(self._memory_cache)))
            except (TypeError, ValueError):
                # Fall back to rough estimate
                size_bytes = sys.getsizeof(self._memory_cache)

            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "entries": len(self._memory_cache),
                "size_bytes": size_bytes,
            }


# -----------------------------
# Global Cache Instance
# -----------------------------

_global_cache: Optional[Cache] = None
_global_lock = threading.Lock()


def _get_global_cache() -> Cache:
    """Get or create the global cache instance."""
    global _global_cache

    if _global_cache is None:
        with _global_lock:
            if _global_cache is None:
                # Determine persistence path
                # Use environment variable or default
                cache_path = os.environ.get("CLAWDBOT_CACHE_PATH", DEFAULT_CACHE_FILE)

                _global_cache = Cache(
                    persistence_path=cache_path,
                    max_entries=DEFAULT_MAX_ENTRIES,
                    default_ttl=DEFAULT_TTL_SECONDS,
                )

    return _global_cache


def cache_get(key: str, default: Any = None) -> Any:
    """
    Get a value from the global cache.

    Args:
        key: Cache key
        default: Value to return if key not found or expired

    Returns:
        Cached value or default
    """
    return _get_global_cache().cache_get(key, default)


def cache_set(key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """
    Set a value in the global cache.

    Args:
        key: Cache key
        value: Value to cache
        ttl_seconds: Time-to-live in seconds (default 3600)
    """
    _get_global_cache().cache_set(key, value, ttl_seconds)


def cache_delete(key: str) -> bool:
    """
    Delete a key from the global cache.

    Args:
        key: Cache key to delete

    Returns:
        True if key was deleted, False if not found
    """
    return _get_global_cache().cache_delete(key)


def cache_clear() -> None:
    """Clear all entries from the global cache."""
    _get_global_cache().cache_clear()


def cache_stats() -> Dict[str, Any]:
    """
    Get statistics from the global cache.

    Returns:
        Dictionary with hits, misses, hit_rate, entries, size_bytes
    """
    return _get_global_cache().cache_stats()


# -----------------------------
# Caching Decorator
# -----------------------------

T = TypeVar("T")


def cached(
    cache: Optional[Cache] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    key_prefix: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to cache function results.

    Args:
        cache: Cache instance to use (uses global cache if None)
        ttl_seconds: TTL for cached results
        key_prefix: Prefix for cache keys (defaults to function name)

    Usage:
        @cached(ttl_seconds=600)
        def expensive_function(x, y):
            return x + y

        @cached(key_prefix="my_api")
        def api_call(endpoint):
            return requests.get(endpoint).json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Get cache instance
            cache_instance = cache or _get_global_cache()

            # Build cache key
            prefix = key_prefix or func.__name__

            # Create hash of arguments
            arg_str = json.dumps(
                {"args": args, "kwargs": kwargs},
                sort_keys=True,
                default=str,
            )
            arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:12]
            cache_key = f"{prefix}:{arg_hash}"

            # Check cache
            result = cache_instance.cache_get(cache_key)
            if result is not None:
                return result

            # Call function
            result = func(*args, **kwargs)

            # Cache result
            cache_instance.cache_set(cache_key, result, ttl_seconds)

            return result

        return wrapper

    return decorator


# -----------------------------
# Utility Functions
# -----------------------------


def warm_cache(
    keys_values: Dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    cache: Optional[Cache] = None,
) -> int:
    """
    Warm the cache with multiple key-value pairs.

    Args:
        keys_values: Dictionary of keys to values
        ttl_seconds: TTL for all entries
        cache: Cache instance (uses global if None)

    Returns:
        Number of entries added
    """
    cache_instance = cache or _get_global_cache()

    count = 0
    for key, value in keys_values.items():
        cache_instance.cache_set(key, value, ttl_seconds)
        count += 1

    logger.info(f"Warmed cache with {count} entries")
    return count


def get_cache_health() -> Dict[str, Any]:
    """
    Get health information about the global cache.

    Returns:
        Dictionary with health metrics
    """
    stats = cache_stats()

    health = {
        "status": "healthy",
        "stats": stats,
        "utilization": stats["entries"] / DEFAULT_MAX_ENTRIES,
    }

    # Check for issues
    if stats["entries"] >= DEFAULT_MAX_ENTRIES * 0.9:
        health["status"] = "warning"
        health["warning"] = "Cache near capacity"

    if stats["hit_rate"] < 0.3 and (stats["hits"] + stats["misses"]) > 100:
        health["status"] = "warning"
        health["warning"] = "Low cache hit rate"

    return health
