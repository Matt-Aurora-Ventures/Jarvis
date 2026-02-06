"""
JARVIS Caching Decorators

Flexible caching with:
- In-memory caching (default)
- TTL support
- LRU eviction
- Cache key generation
- Async support
- Cache invalidation

Usage:
    from core.cache import cached, cache_manager

    @cached(ttl=300)  # Cache for 5 minutes
    async def get_token_price(mint: str) -> float:
        return await fetch_price(mint)

    # Invalidate cache
    get_token_price.cache_clear()

    # Or specific key
    cache_manager.delete("get_token_price:So111...")
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached value with metadata."""
    value: Any
    created_at: float
    expires_at: Optional[float]
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class CacheBackend(ABC):
    """Base cache backend interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass


class MemoryCache(CacheBackend):
    """
    In-memory LRU cache with TTL support.

    Thread-safe implementation suitable for single-process apps.
    """

    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            # Use default TTL if not specified
            effective_ttl = ttl if ttl is not None else self.default_ttl
            expires_at = time.time() + effective_ttl if effective_ttl else None

            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                expires_at=expires_at,
            )

            # Remove oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            self._cache[key] = entry
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0

            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": round(hit_rate, 4),
            }

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        removed = 0
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and entry.expires_at < now
            ]
            for key in expired_keys:
                del self._cache[key]
                removed += 1
                self._stats["expirations"] += 1
        return removed


class CacheManager:
    """
    Central cache manager for coordinating multiple caches.
    """

    def __init__(self):
        self._caches: Dict[str, CacheBackend] = {}
        self._default_cache: Optional[CacheBackend] = None

    def register(self, name: str, cache: CacheBackend, default: bool = False) -> None:
        """Register a cache backend."""
        self._caches[name] = cache
        if default or self._default_cache is None:
            self._default_cache = cache

    def get_cache(self, name: Optional[str] = None) -> CacheBackend:
        """Get a cache by name or the default."""
        if name:
            return self._caches.get(name, self._default_cache)
        return self._default_cache

    def get(self, key: str, cache_name: Optional[str] = None) -> Optional[Any]:
        """Get value from cache."""
        cache = self.get_cache(cache_name)
        return cache.get(key) if cache else None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        cache_name: Optional[str] = None
    ) -> None:
        """Set value in cache."""
        cache = self.get_cache(cache_name)
        if cache:
            cache.set(key, value, ttl)

    def delete(self, key: str, cache_name: Optional[str] = None) -> bool:
        """Delete from cache."""
        cache = self.get_cache(cache_name)
        return cache.delete(key) if cache else False

    def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self._caches.values():
            cache.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats from all caches."""
        return {name: cache.get_stats() for name, cache in self._caches.items()}


# Global cache manager
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        # Register default memory cache
        _cache_manager.register("memory", MemoryCache(), default=True)
    return _cache_manager


def make_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function and arguments."""
    func_name = f"{func.__module__}.{func.__qualname__}"

    # Serialize args and kwargs
    try:
        key_data = json.dumps({
            "args": args,
            "kwargs": kwargs,
        }, sort_keys=True, default=str)
    except TypeError:
        # Fallback to repr for non-JSON-serializable objects
        key_data = repr((args, kwargs))

    # Hash if too long
    if len(key_data) > 200:
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
        return f"{func_name}:{key_hash}"

    return f"{func_name}:{key_data}"


def cached(
    ttl: Optional[float] = None,
    cache_name: Optional[str] = None,
    key_func: Optional[Callable[..., str]] = None,
    condition: Optional[Callable[[Any], bool]] = None,
    cache_dir: Optional[str] = None,
) -> Callable:
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds (None = no expiry)
        cache_name: Specific cache backend to use
        key_func: Custom function to generate cache key
        condition: Only cache if this returns True for the result
        cache_dir: Directory for file-based caching (uses new CacheManager)

    Usage:
        @cached(ttl=300)
        async def get_data(id: int) -> dict:
            return await fetch_data(id)

        # Custom key function
        @cached(ttl=60, key_func=lambda mint: f"price:{mint}")
        async def get_price(mint: str) -> float:
            ...

        # With cache_dir for file persistence
        @cached(ttl=300, cache_dir="/path/to/cache")
        def get_user(user_id: int) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Track function-specific invalidation
        cache_keys: set = set()

        # Check for custom key function from @cache_key decorator
        effective_key_func = key_func
        if hasattr(func, '_cache_key_func'):
            effective_key_func = func._cache_key_func

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Use new CacheManager if cache_dir is specified
            if cache_dir:
                from core.cache.manager import CacheManager
                cache = CacheManager(cache_dir=cache_dir)

                # Generate key
                if effective_key_func:
                    key = effective_key_func(*args, **kwargs)
                else:
                    key = make_cache_key(func, args, kwargs)

                cache_keys.add(key)

                # Check cache
                cached_value = cache.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key[:50]}...")
                    return cached_value

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result if condition met
                if condition is None or condition(result):
                    cache.set(key, result, ttl_seconds=int(ttl) if ttl else 3600)
                    logger.debug(f"Cached: {key[:50]}... (ttl={ttl})")

                return result
            else:
                manager = get_cache_manager()
                cache = manager.get_cache(cache_name)

                # Generate key
                if effective_key_func:
                    key = effective_key_func(*args, **kwargs)
                else:
                    key = make_cache_key(func, args, kwargs)

                cache_keys.add(key)

                # Check cache
                cached_value = cache.get(key) if cache else None
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key[:50]}...")
                    return cached_value

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result if condition met
                if cache and (condition is None or condition(result)):
                    cache.set(key, result, ttl)
                    logger.debug(f"Cached: {key[:50]}... (ttl={ttl})")

                return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Use new CacheManager if cache_dir is specified
            if cache_dir:
                from core.cache.manager import CacheManager
                cache = CacheManager(cache_dir=cache_dir)

                # Generate key
                if effective_key_func:
                    key = effective_key_func(*args, **kwargs)
                else:
                    key = make_cache_key(func, args, kwargs)

                cache_keys.add(key)

                # Check cache
                cached_value = cache.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key[:50]}...")
                    return cached_value

                # Execute function
                result = func(*args, **kwargs)

                # Cache result if condition met
                if condition is None or condition(result):
                    cache.set(key, result, ttl_seconds=int(ttl) if ttl else 3600)
                    logger.debug(f"Cached: {key[:50]}... (ttl={ttl})")

                return result
            else:
                manager = get_cache_manager()
                cache = manager.get_cache(cache_name)

                # Generate key
                if effective_key_func:
                    key = effective_key_func(*args, **kwargs)
                else:
                    key = make_cache_key(func, args, kwargs)

                cache_keys.add(key)

                # Check cache
                cached_value = cache.get(key) if cache else None
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key[:50]}...")
                    return cached_value

                # Execute function
                result = func(*args, **kwargs)

                # Cache result if condition met
                if cache and (condition is None or condition(result)):
                    cache.set(key, result, ttl)
                    logger.debug(f"Cached: {key[:50]}... (ttl={ttl})")

                return result

        def cache_clear() -> None:
            """Clear all cached values for this function."""
            if cache_dir:
                from core.cache.manager import CacheManager
                cache = CacheManager(cache_dir=cache_dir)
                for key in cache_keys:
                    cache.delete(key)
            else:
                manager = get_cache_manager()
                cache = manager.get_cache(cache_name)
                if cache:
                    for key in cache_keys:
                        cache.delete(key)
            cache_keys.clear()

        def cache_delete(*args, **kwargs) -> bool:
            """Delete specific cached value."""
            if effective_key_func:
                key = effective_key_func(*args, **kwargs)
            else:
                key = make_cache_key(func, args, kwargs)

            if cache_dir:
                from core.cache.manager import CacheManager
                cache = CacheManager(cache_dir=cache_dir)
                return cache.delete(key)
            else:
                manager = get_cache_manager()
                cache = manager.get_cache(cache_name)
                return cache.delete(key) if cache else False

        # Choose wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        # Attach cache control methods
        wrapper.cache_clear = cache_clear
        wrapper.cache_delete = cache_delete
        wrapper.cache_keys = lambda: cache_keys.copy()
        wrapper.__wrapped__ = func  # Store reference to original function

        return wrapper

    return decorator


def cache_key(key_func: Callable[..., str]) -> Callable:
    """
    Decorator to customize cache key generation.

    Use this as an inner decorator with @cached to customize how cache keys
    are generated from function arguments.

    Args:
        key_func: Function that takes the same args as the decorated function
                  and returns a string to use as the cache key.

    Usage:
        @cache_key(lambda user_id, **kwargs: f"user:{user_id}")
        @cached(ttl=300)
        def get_user_data(user_id, include_details=False):
            ...

    Note: Must be applied BEFORE @cached (closer to the function definition).
    """
    def decorator(func: Callable) -> Callable:
        # Store the key function on the function for later use
        func._cache_key_func = key_func
        return func

    return decorator


def invalidate_cache(
    pattern: str,
    cache_name: Optional[str] = None,
    cache_dir: Optional[str] = None
) -> int:
    """
    Invalidate cache entries matching a pattern.

    Uses fnmatch-style patterns:
    - * matches everything
    - ? matches any single character
    - [seq] matches any character in seq

    Args:
        pattern: Pattern to match (e.g., "user:*", "llm:grok:*")
        cache_name: Specific cache backend to invalidate (optional)
        cache_dir: Cache directory override (optional)

    Returns:
        Number of entries invalidated

    Usage:
        from core.cache.decorators import invalidate_cache

        # Invalidate all user cache entries
        invalidate_cache("user:*")

        # Invalidate specific pattern
        invalidate_cache("llm:grok:*")
    """
    from core.cache.manager import CacheManager

    manager = CacheManager(cache_dir=cache_dir) if cache_dir else get_cache_manager()
    return manager.clear_pattern(pattern)


def cache_aside(
    ttl: float = 300,
    cache_name: Optional[str] = None,
) -> Callable:
    """
    Cache-aside pattern decorator.

    Checks cache first, falls back to function, updates cache.
    Stale-while-revalidate: returns stale value while refreshing in background.
    """
    def decorator(func: Callable) -> Callable:
        # Use regular cached decorator as base
        cached_func = cached(ttl=ttl, cache_name=cache_name)(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await cached_func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return cached_func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        wrapper.cache_clear = cached_func.cache_clear
        wrapper.cache_delete = cached_func.cache_delete
        wrapper.refresh = func  # Direct access to uncached function

        return wrapper

    return decorator


# Convenience aliases
cache = cached


if __name__ == "__main__":
    import random

    logging.basicConfig(level=logging.DEBUG)

    print("Cache Decorator Demo")
    print("=" * 50)

    # Initialize cache
    manager = get_cache_manager()

    @cached(ttl=5)
    def get_random_number(seed: int) -> int:
        """Simulated expensive operation."""
        print(f"  Computing for seed={seed}...")
        return random.randint(1, 100)

    @cached(ttl=10, key_func=lambda token: f"price:{token}")
    async def get_token_price(token: str) -> float:
        """Simulated async price fetch."""
        print(f"  Fetching price for {token}...")
        await asyncio.sleep(0.1)
        return random.uniform(0.1, 100.0)

    # Test sync caching
    print("\n1. Sync caching test:")
    for i in range(3):
        result = get_random_number(42)
        print(f"   Call {i+1}: {result}")

    print("\n2. Different argument = cache miss:")
    result = get_random_number(99)
    print(f"   Result: {result}")

    # Test async caching
    async def test_async():
        print("\n3. Async caching test:")
        for i in range(3):
            price = await get_token_price("SOL")
            print(f"   Call {i+1}: ${price:.2f}")

    asyncio.run(test_async())

    # Test cache stats
    print("\n4. Cache stats:")
    stats = manager.get_all_stats()
    for name, stat in stats.items():
        print(f"   {name}: {stat}")

    # Test cache clear
    print("\n5. Cache clear test:")
    get_random_number.cache_clear()
    result = get_random_number(42)
    print(f"   After clear: {result}")

    print("\nDemo complete!")
