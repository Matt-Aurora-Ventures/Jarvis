"""
ClawdBot Cache Manager

Central cache management with support for:
- Multiple backends (memory, file, TTL, LRU)
- Pattern-based invalidation
- Statistics tracking
- Configurable TTL

Cache location: bots/data/cache/

Usage:
    from core.cache.manager import CacheManager, get_cache_manager

    # Get global instance
    cache = get_cache_manager()

    # Basic operations
    cache.set("key", value, ttl_seconds=300)
    value = cache.get("key")
    cache.delete("key")

    # Pattern-based operations
    cache.clear_pattern("llm:*")

    # Statistics
    stats = cache.get_stats()
    print(f"Hit rate: {stats.hit_rate:.2%}")
"""

import fnmatch
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = str(Path(__file__).parent.parent.parent / "bots" / "data" / "cache")


@dataclass
class CacheStats:
    """Statistics for cache operations."""
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletes: int = 0
    evictions: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "entries": self.entries,
            "hit_rate": self.hit_rate,
        }


@dataclass
class CacheEntry:
    """A cached entry with metadata."""
    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        """Get remaining TTL in seconds."""
        return max(0, self.expires_at - time.time())


class CacheManager:
    """
    Central cache manager for ClawdBots.

    Provides a unified interface for caching with support for:
    - In-memory caching with TTL
    - Pattern-based invalidation
    - Statistics tracking
    - Thread-safe operations

    Args:
        cache_dir: Directory for persistent cache (default: bots/data/cache/)
        max_size: Maximum number of entries in memory cache
        default_ttl: Default TTL in seconds
        enable_file_cache: Whether to persist cache to files
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_size: int = 10000,
        default_ttl: int = 3600,
        enable_file_cache: bool = True,
    ):
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_file_cache = enable_file_cache

        # Ensure cache directory exists
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        # In-memory cache storage
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

        # Statistics
        self._stats = CacheStats()
        self._stats_lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                # Try file cache if enabled
                if self.enable_file_cache:
                    value = self._file_get(key)
                    if value is not None:
                        self._record_hit()
                        return value

                self._record_miss()
                return None

            if entry.is_expired:
                self._remove_entry(key)
                self._record_miss()
                return None

            entry.access_count += 1
            self._record_hit()
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (uses default if not specified)
        """
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.time()

        with self._lock:
            # Evict if at capacity
            self._evict_if_needed()

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + effective_ttl,
                access_count=1,
            )

            self._cache[key] = entry
            self._record_write()

            # Persist to file if enabled
            if self.enable_file_cache:
                self._file_set(key, value, effective_ttl)

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted, False otherwise
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)

                # Remove from file cache if enabled
                if self.enable_file_cache:
                    self._file_delete(key)

                self._record_delete()
                return True

            # Try file cache
            if self.enable_file_cache and self._file_delete(key):
                self._record_delete()
                return True

            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.

        Uses fnmatch-style patterns:
        - * matches everything
        - ? matches any single character
        - [seq] matches any character in seq

        Args:
            pattern: Pattern to match (e.g., "llm:grok:*")

        Returns:
            Number of keys removed
        """
        count = 0

        with self._lock:
            # Find matching keys in memory cache
            keys_to_remove = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]

            for key in keys_to_remove:
                self._remove_entry(key)
                count += 1

            # Clear matching files if enabled
            if self.enable_file_cache:
                count += self._file_clear_pattern(pattern)

        return count

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats with hits, misses, writes, etc.
        """
        with self._stats_lock:
            # Update entry count
            self._stats.entries = len(self._cache)
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                writes=self._stats.writes,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions,
                entries=self._stats.entries,
            )

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

            if self.enable_file_cache:
                self._file_clear_all()

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        count = 0
        now = time.time()

        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at < now
            ]

            for key in expired_keys:
                self._remove_entry(key)
                count += 1

        return count

    def _remove_entry(self, key: str) -> None:
        """Remove an entry from the in-memory cache."""
        self._cache.pop(key, None)

    def _evict_if_needed(self) -> int:
        """Evict entries if cache is at capacity."""
        evicted = 0

        while len(self._cache) >= self.max_size:
            # Evict oldest entry
            if self._cache:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].created_at
                )
                self._remove_entry(oldest_key)
                evicted += 1
                self._stats.evictions += 1
            else:
                break

        return evicted

    def _record_hit(self) -> None:
        """Record a cache hit."""
        with self._stats_lock:
            self._stats.hits += 1

    def _record_miss(self) -> None:
        """Record a cache miss."""
        with self._stats_lock:
            self._stats.misses += 1

    def _record_write(self) -> None:
        """Record a cache write."""
        with self._stats_lock:
            self._stats.writes += 1

    def _record_delete(self) -> None:
        """Record a cache delete."""
        with self._stats_lock:
            self._stats.deletes += 1

    # File cache operations

    def _get_file_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        # Hash the key to create a valid filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return Path(self.cache_dir) / f"{key_hash}.json"

    def _file_get(self, key: str) -> Optional[Any]:
        """Get a value from file cache."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Check expiration
            if time.time() > data.get("expires_at", 0):
                file_path.unlink(missing_ok=True)
                return None

            # Check key match (in case of hash collision)
            if data.get("key") != key:
                return None

            return data.get("value")
        except (json.JSONDecodeError, IOError):
            return None

    def _file_set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Set a value in file cache."""
        file_path = self._get_file_path(key)

        try:
            data = {
                "key": key,
                "value": value,
                "created_at": time.time(),
                "expires_at": time.time() + ttl_seconds,
            }

            with open(file_path, 'w') as f:
                json.dump(data, f)
        except (IOError, TypeError) as e:
            logger.warning(f"Failed to write to file cache: {e}")

    def _file_delete(self, key: str) -> bool:
        """Delete a key from file cache."""
        file_path = self._get_file_path(key)

        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except IOError:
                return False
        return False

    def _file_clear_pattern(self, pattern: str) -> int:
        """Clear files matching a pattern."""
        count = 0
        cache_path = Path(self.cache_dir)

        if not cache_path.exists():
            return 0

        for file_path in cache_path.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)

                key = data.get("key", "")
                if fnmatch.fnmatch(key, pattern):
                    file_path.unlink()
                    count += 1
            except (json.JSONDecodeError, IOError):
                continue

        return count

    def _file_clear_all(self) -> None:
        """Clear all file cache entries."""
        cache_path = Path(self.cache_dir)

        if not cache_path.exists():
            return

        for file_path in cache_path.glob("*.json"):
            try:
                file_path.unlink()
            except IOError:
                continue


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(cache_dir: Optional[str] = None) -> CacheManager:
    """
    Get or create the global cache manager instance.

    Args:
        cache_dir: Optional cache directory override

    Returns:
        CacheManager instance
    """
    global _cache_manager

    if _cache_manager is None or (cache_dir and cache_dir != _cache_manager.cache_dir):
        _cache_manager = CacheManager(cache_dir=cache_dir)

    return _cache_manager


def reset_cache_manager() -> None:
    """Reset the global cache manager (for testing)."""
    global _cache_manager
    _cache_manager = None
