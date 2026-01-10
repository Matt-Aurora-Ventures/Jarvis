"""
Request Caching System

Caches API responses to reduce upstream calls and improve latency.

Prompts #45: API Proxy System - Caching
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from collections import OrderedDict
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration"""
    max_size: int = 1000                # Maximum entries
    default_ttl: int = 300              # Default TTL in seconds (5 min)
    min_ttl: int = 10                   # Minimum TTL
    max_ttl: int = 3600                 # Maximum TTL (1 hour)
    enable_compression: bool = False     # Compress large values
    compression_threshold: int = 1024    # Compress if larger than this


@dataclass
class CacheEntry:
    """A cached entry"""
    key: str
    value: Any
    created_at: float
    ttl: int
    hits: int = 0
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def remaining_ttl(self) -> float:
        return max(0, self.expires_at - time.time())


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0
    total_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class RequestCache:
    """
    LRU cache for API responses.

    Features:
    - TTL-based expiration
    - LRU eviction when full
    - Cache key generation from request params
    - Statistics tracking
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def _generate_key(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        body: Optional[Any] = None
    ) -> str:
        """Generate cache key from request"""
        key_data = {
            "method": method,
            "url": url,
            "params": params or {},
            "body": body
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of a value in bytes"""
        try:
            return len(json.dumps(value, default=str).encode())
        except Exception:
            return 0

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired:
                del self._cache[key]
                self._stats.expirations += 1
                self._stats.misses += 1
                self._stats.entry_count -= 1
                self._stats.total_bytes -= entry.size_bytes
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1

            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict] = None
    ):
        """Set a value in cache"""
        ttl = ttl or self.config.default_ttl
        ttl = max(self.config.min_ttl, min(self.config.max_ttl, ttl))
        size = self._estimate_size(value)

        async with self._lock:
            # Remove if exists
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._stats.total_bytes -= old_entry.size_bytes
                self._stats.entry_count -= 1

            # Evict if full
            while len(self._cache) >= self.config.max_size:
                self._evict_one()

            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl,
                size_bytes=size,
                metadata=metadata or {}
            )

            self._cache[key] = entry
            self._stats.sets += 1
            self._stats.entry_count += 1
            self._stats.total_bytes += size

    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._stats.entry_count -= 1
                self._stats.total_bytes -= entry.size_bytes
                return True
            return False

    async def clear(self):
        """Clear all entries"""
        async with self._lock:
            self._cache.clear()
            self._stats.entry_count = 0
            self._stats.total_bytes = 0

    async def cleanup(self) -> int:
        """Remove expired entries"""
        removed = 0
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                entry = self._cache.pop(key)
                self._stats.total_bytes -= entry.size_bytes
                self._stats.expirations += 1
                removed += 1
            self._stats.entry_count = len(self._cache)
        return removed

    def _evict_one(self):
        """Evict the least recently used entry"""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self._stats.evictions += 1
            self._stats.total_bytes -= entry.size_bytes
            self._stats.entry_count -= 1

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and set"""
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Get cache status"""
        return {
            "config": {
                "max_size": self.config.max_size,
                "default_ttl": self.config.default_ttl
            },
            "stats": {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "sets": self._stats.sets,
                "evictions": self._stats.evictions,
                "expirations": self._stats.expirations,
                "hit_rate": round(self._stats.hit_rate * 100, 2),
                "entry_count": self._stats.entry_count,
                "total_bytes": self._stats.total_bytes
            }
        }


class CacheManager:
    """Manages multiple named caches"""

    def __init__(self):
        self._caches: Dict[str, RequestCache] = {}
        self._default_config = CacheConfig()

    def get_cache(
        self,
        name: str,
        config: Optional[CacheConfig] = None
    ) -> RequestCache:
        """Get or create a named cache"""
        if name not in self._caches:
            self._caches[name] = RequestCache(config or self._default_config)
        return self._caches[name]

    async def cleanup_all(self) -> Dict[str, int]:
        """Cleanup expired entries in all caches"""
        results = {}
        for name, cache in self._caches.items():
            removed = await cache.cleanup()
            results[name] = removed
        return results

    async def clear_all(self):
        """Clear all caches"""
        for cache in self._caches.values():
            await cache.clear()

    def status(self) -> Dict[str, Any]:
        """Get status of all caches"""
        return {
            name: cache.to_dict()
            for name, cache in self._caches.items()
        }


# Global cache manager
_cache_manager = CacheManager()


def get_cache(
    name: str = "default",
    config: Optional[CacheConfig] = None
) -> RequestCache:
    """Get a named cache"""
    return _cache_manager.get_cache(name, config)


def cached(
    cache_name: str = "default",
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None
):
    """Decorator for caching function results"""
    def decorator(func):
        cache = get_cache(cache_name)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key_data = {
                    "func": func.__name__,
                    "args": args,
                    "kwargs": kwargs
                }
                key = hashlib.sha256(
                    json.dumps(key_data, sort_keys=True, default=str).encode()
                ).hexdigest()[:32]

            return await cache.get_or_set(key, lambda: func(*args, **kwargs), ttl)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Background cleanup task
async def cache_cleanup_task(interval: int = 60):
    """Background task to cleanup expired entries"""
    while True:
        try:
            await asyncio.sleep(interval)
            results = await _cache_manager.cleanup_all()
            total = sum(results.values())
            if total > 0:
                logger.debug(f"Cache cleanup: removed {total} expired entries")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")


# Testing
if __name__ == "__main__":
    async def test():
        cache = RequestCache(CacheConfig(max_size=3, default_ttl=2))

        # Test set and get
        await cache.set("key1", {"data": "value1"})
        result = await cache.get("key1")
        print(f"Get key1: {result}")

        # Test miss
        result = await cache.get("nonexistent")
        print(f"Get nonexistent: {result}")

        # Test eviction
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # Should evict key1

        result = await cache.get("key1")
        print(f"Get key1 after eviction: {result}")

        # Test expiration
        await cache.set("key5", "value5", ttl=1)
        result = await cache.get("key5")
        print(f"Get key5 immediately: {result}")

        await asyncio.sleep(1.5)
        result = await cache.get("key5")
        print(f"Get key5 after expiration: {result}")

        # Print stats
        print(f"\nCache stats: {cache.to_dict()}")

    asyncio.run(test())
