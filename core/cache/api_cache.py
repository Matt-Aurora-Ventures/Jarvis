"""
API Response Caching with TTL Management

Provides optimized caching for external APIs with:
- Per-API TTL configuration
- Cache hit/miss tracking
- Request deduplication
- Batch operations
- Parallel fetch support

Default TTLs:
- Jupiter quotes: 5 minutes (prices change but not constantly)
- Solscan data: 1 hour (on-chain data stable)
- Coingecko: 30 minutes (market data relatively stable)
- Grok analysis: 2 hours (sentiment stable within window)

Usage:
    from core.cache.api_cache import cached_api, get_api_cache

    @cached_api("jupiter", ttl=300)
    async def get_quote(token: str) -> dict:
        return await fetch_quote(token)

    # Or manually
    cache = get_api_cache()
    cache.set("jupiter", "quote:SOL", data)
    result = cache.get("jupiter", "quote:SOL")
"""

import asyncio
import hashlib
import json
import logging
import sys
import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Awaitable

logger = logging.getLogger(__name__)

# Default TTLs in seconds for each API
DEFAULT_TTLS: Dict[str, int] = {
    "jupiter": 300,      # 5 minutes - prices change but not constantly
    "solscan": 3600,     # 1 hour - on-chain data stable
    "coingecko": 1800,   # 30 minutes - market data relatively stable
    "grok": 7200,        # 2 hours - sentiment stable within window
    "birdeye": 600,      # 10 minutes
    "dexscreener": 300,  # 5 minutes
    "binance": 120,      # 2 minutes - prices change frequently
    "yahoo": 300,        # 5 minutes
    "default": 300,      # 5 minutes fallback
}


@dataclass
class CacheEntry:
    """A cached value with metadata."""
    value: Any
    created_at: float
    expires_at: float
    hits: int = 0
    api_name: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        return max(0, self.expires_at - time.time())


@dataclass
class APIStats:
    """Statistics for a single API."""
    hits: int = 0
    misses: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class APICache:
    """
    In-memory cache for API responses with per-API TTL management.

    Features:
    - Per-API namespace isolation
    - Configurable TTLs
    - LRU eviction
    - Statistics tracking
    - Request deduplication
    - Batch operations
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize API cache.

        Args:
            max_size: Maximum total entries across all APIs
        """
        self.max_size = max_size
        self._cache: Dict[str, OrderedDict[str, CacheEntry]] = {}
        self._ttls = DEFAULT_TTLS.copy()
        self._stats: Dict[str, APIStats] = {}
        self._lock = threading.Lock()
        self._pending: Dict[str, asyncio.Future] = {}  # For deduplication

        # Initialize namespaces for known APIs
        for api_name in DEFAULT_TTLS.keys():
            self._cache[api_name] = OrderedDict()
            self._stats[api_name] = APIStats()

    def _get_namespace(self, api_name: str) -> OrderedDict:
        """Get or create cache namespace for API."""
        if api_name not in self._cache:
            self._cache[api_name] = OrderedDict()
            self._stats[api_name] = APIStats()
        return self._cache[api_name]

    def _get_ttl(self, api_name: str) -> int:
        """Get TTL for API."""
        return self._ttls.get(api_name, self._ttls["default"])

    def get(self, api_name: str, key: str) -> Optional[Any]:
        """
        Get a cached value.

        Args:
            api_name: API namespace (jupiter, solscan, etc.)
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            namespace = self._get_namespace(api_name)
            entry = namespace.get(key)

            if entry is None:
                self._stats[api_name].misses += 1
                return None

            if entry.is_expired:
                del namespace[key]
                self._stats[api_name].entries = len(namespace)
                self._stats[api_name].misses += 1
                return None

            # Move to end (most recently used)
            namespace.move_to_end(key)
            entry.hits += 1
            self._stats[api_name].hits += 1

            return entry.value

    def set(
        self,
        api_name: str,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """
        Set a cached value.

        Args:
            api_name: API namespace
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override (uses API default if not specified)
        """
        with self._lock:
            namespace = self._get_namespace(api_name)

            # Evict if at capacity
            self._evict_if_needed()

            effective_ttl = ttl if ttl is not None else self._get_ttl(api_name)

            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                expires_at=time.time() + effective_ttl,
                api_name=api_name
            )

            namespace[key] = entry
            namespace.move_to_end(key)
            self._stats[api_name].entries = len(namespace)

    def invalidate(self, api_name: str, key: str) -> bool:
        """
        Invalidate a specific cached entry.

        Args:
            api_name: API namespace
            key: Cache key

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            namespace = self._get_namespace(api_name)
            if key in namespace:
                del namespace[key]
                self._stats[api_name].entries = len(namespace)
                return True
            return False

    def invalidate_api(self, api_name: str) -> int:
        """
        Invalidate all entries for an API.

        Args:
            api_name: API namespace

        Returns:
            Number of entries removed
        """
        with self._lock:
            namespace = self._get_namespace(api_name)
            count = len(namespace)
            namespace.clear()
            self._stats[api_name].entries = 0
            return count

    def clear_all(self) -> int:
        """
        Clear all caches.

        Returns:
            Total entries removed
        """
        with self._lock:
            total = sum(len(ns) for ns in self._cache.values())
            for namespace in self._cache.values():
                namespace.clear()
            for stats in self._stats.values():
                stats.entries = 0
            return total

    def _evict_if_needed(self) -> int:
        """Evict oldest entries if over capacity."""
        total_entries = sum(len(ns) for ns in self._cache.values())
        evicted = 0

        while total_entries >= self.max_size:
            # Find oldest entry across all namespaces
            oldest_key = None
            oldest_api = None
            oldest_time = float('inf')

            for api_name, namespace in self._cache.items():
                if namespace:
                    first_key = next(iter(namespace))
                    entry = namespace[first_key]
                    if entry.created_at < oldest_time:
                        oldest_time = entry.created_at
                        oldest_key = first_key
                        oldest_api = api_name

            if oldest_api and oldest_key:
                del self._cache[oldest_api][oldest_key]
                self._stats[oldest_api].entries = len(self._cache[oldest_api])
                evicted += 1
                total_entries -= 1
            else:
                break

        return evicted

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate, and per-API breakdown
        """
        with self._lock:
            total_hits = sum(s.hits for s in self._stats.values())
            total_misses = sum(s.misses for s in self._stats.values())
            total_entries = sum(s.entries for s in self._stats.values())
            total = total_hits + total_misses

            by_api = {}
            for api_name, stats in self._stats.items():
                api_total = stats.hits + stats.misses
                by_api[api_name] = {
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "entries": stats.entries,
                    "hit_rate": stats.hits / api_total if api_total > 0 else 0.0,
                    "ttl_seconds": self._ttls.get(api_name, self._ttls["default"])
                }

            return {
                "total_hits": total_hits,
                "total_misses": total_misses,
                "total_entries": total_entries,
                "hit_rate": total_hits / total if total > 0 else 0.0,
                "by_api": by_api,
                "max_size": self.max_size
            }

    def get_ttl(self, api_name: str) -> int:
        """Get current TTL for API."""
        return self._ttls.get(api_name, self._ttls["default"])

    def set_ttl(self, api_name: str, ttl_seconds: int) -> None:
        """Set TTL for API (affects new entries only)."""
        self._ttls[api_name] = ttl_seconds

    def get_info(self) -> Dict[str, Any]:
        """Get comprehensive cache info."""
        with self._lock:
            apis = {}
            total_entries = 0
            memory_estimate = 0

            for api_name, namespace in self._cache.items():
                entry_count = len(namespace)
                total_entries += entry_count

                # Rough memory estimate
                for entry in namespace.values():
                    memory_estimate += sys.getsizeof(entry.value)

                apis[api_name] = {
                    "entries": entry_count,
                    "ttl_seconds": self._ttls.get(api_name, self._ttls["default"]),
                    "oldest_entry_age": self._get_oldest_age(namespace),
                    "newest_entry_age": self._get_newest_age(namespace),
                }

            return {
                "apis": apis,
                "total_entries": total_entries,
                "memory_usage_bytes": memory_estimate,
                "max_size": self.max_size,
            }

    def _get_oldest_age(self, namespace: OrderedDict) -> Optional[float]:
        """Get age of oldest entry in seconds."""
        if not namespace:
            return None
        first_key = next(iter(namespace))
        return time.time() - namespace[first_key].created_at

    def _get_newest_age(self, namespace: OrderedDict) -> Optional[float]:
        """Get age of newest entry in seconds."""
        if not namespace:
            return None
        last_key = next(reversed(namespace))
        return time.time() - namespace[last_key].created_at

    def export_stats_json(self) -> str:
        """Export stats as JSON string."""
        return json.dumps(self.get_stats(), indent=2)

    async def get_or_fetch(
        self,
        api_name: str,
        key: str,
        fetcher: Callable[[str], Awaitable[Any]],
        ttl: Optional[float] = None
    ) -> Any:
        """
        Get from cache or fetch with request deduplication.

        If multiple concurrent requests for the same key arrive,
        only one fetch is made and all requests share the result.

        Args:
            api_name: API namespace
            key: Cache key
            fetcher: Async function to fetch value (receives key)
            ttl: Optional TTL override

        Returns:
            Cached or freshly fetched value
        """
        # Check cache first
        cached = self.get(api_name, key)
        if cached is not None:
            return cached

        # Create deduplication key
        dedup_key = f"{api_name}:{key}"

        # Check if a fetch is already pending
        if dedup_key in self._pending:
            # Wait for the pending fetch
            return await self._pending[dedup_key]

        # Create a future for this fetch
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[dedup_key] = future

        try:
            # Perform the fetch
            result = await fetcher(key)

            # Cache the result
            self.set(api_name, key, result, ttl)

            # Resolve the future
            future.set_result(result)

            return result

        except Exception as e:
            future.set_exception(e)
            raise

        finally:
            # Clean up pending
            self._pending.pop(dedup_key, None)

    async def batch_get_or_fetch(
        self,
        api_name: str,
        keys: List[str],
        batch_fetcher: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        ttl: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Batch get from cache, fetching only missing keys.

        Args:
            api_name: API namespace
            keys: List of cache keys
            batch_fetcher: Async function that takes list of keys, returns dict
            ttl: Optional TTL override

        Returns:
            Dictionary mapping keys to values
        """
        result = {}
        missing_keys = []

        # Check cache for each key
        for key in keys:
            cached = self.get(api_name, key)
            if cached is not None:
                result[key] = cached
            else:
                missing_keys.append(key)

        # Fetch missing keys if any
        if missing_keys:
            fetched = await batch_fetcher(missing_keys)

            # Cache and add to result
            for key, value in fetched.items():
                self.set(api_name, key, value, ttl)
                result[key] = value

        return result


# Global API cache instance
_api_cache: Optional[APICache] = None


def get_api_cache() -> APICache:
    """Get the global API cache instance."""
    global _api_cache
    if _api_cache is None:
        _api_cache = APICache()
    return _api_cache


def cached_api(
    api_name: str,
    ttl: Optional[float] = None,
    key_func: Optional[Callable[..., str]] = None,
    condition: Optional[Callable[[Any], bool]] = None
) -> Callable:
    """
    Decorator to cache API function results.

    Args:
        api_name: API namespace (jupiter, solscan, etc.)
        ttl: TTL in seconds (uses API default if not specified)
        key_func: Custom function to generate cache key from args
        condition: Only cache if this returns True for the result

    Usage:
        @cached_api("jupiter", ttl=300)
        async def get_quote(token: str) -> dict:
            return await fetch_quote(token)

        @cached_api("solscan", key_func=lambda mint: f"token:{mint}")
        async def get_token_info(mint: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            cache = get_api_cache()

            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = _make_cache_key(func.__name__, args, kwargs)

            # Check cache
            cached_value = cache.get(api_name, key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {api_name}:{key[:30]}...")
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result if condition met
            if condition is None or condition(result):
                cache.set(api_name, key, result, ttl)
                logger.debug(f"Cached: {api_name}:{key[:30]}... (ttl={ttl})")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            cache = get_api_cache()

            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = _make_cache_key(func.__name__, args, kwargs)

            # Check cache
            cached_value = cache.get(api_name, key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {api_name}:{key[:30]}...")
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Cache result if condition met
            if condition is None or condition(result):
                cache.set(api_name, key, result, ttl)
                logger.debug(f"Cached: {api_name}:{key[:30]}... (ttl={ttl})")

            return result

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        # Attach cache control methods
        wrapper.cache_clear = lambda: get_api_cache().invalidate_api(api_name)

        return wrapper

    return decorator


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function name and arguments."""
    try:
        key_data = json.dumps({
            "args": args,
            "kwargs": kwargs,
        }, sort_keys=True, default=str)
    except TypeError:
        key_data = repr((args, kwargs))

    # Hash if too long
    if len(key_data) > 100:
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
        return f"{func_name}:{key_hash}"

    return f"{func_name}:{key_data}"


async def parallel_fetch(**fetchers: Awaitable[Any]) -> Dict[str, Any]:
    """
    Fetch from multiple APIs in parallel.

    Args:
        **fetchers: Named coroutines to execute in parallel

    Returns:
        Dictionary mapping names to results (None for failed fetches)

    Usage:
        results = await parallel_fetch(
            jupiter=fetch_jupiter_data(),
            solscan=fetch_solscan_data(),
            coingecko=fetch_coingecko_data()
        )
    """
    results = {}

    async def safe_fetch(name: str, coro: Awaitable[Any]) -> tuple:
        try:
            result = await coro
            return (name, result)
        except Exception as e:
            logger.warning(f"Parallel fetch failed for {name}: {e}")
            return (name, None)

    # Execute all fetches in parallel
    tasks = [safe_fetch(name, coro) for name, coro in fetchers.items()]
    completed = await asyncio.gather(*tasks)

    # Collect results
    for name, result in completed:
        results[name] = result

    return results


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG)

    async def demo():
        print("API Cache Demo")
        print("=" * 50)

        cache = get_api_cache()

        # Test basic operations
        print("\n1. Basic set/get:")
        cache.set("jupiter", "quote:SOL", {"price": 100.5})
        result = cache.get("jupiter", "quote:SOL")
        print(f"   Cached: {result}")

        # Test stats
        print("\n2. Cache stats:")
        stats = cache.get_stats()
        print(f"   Total hits: {stats['total_hits']}")
        print(f"   Total misses: {stats['total_misses']}")
        print(f"   Hit rate: {stats['hit_rate']:.2%}")

        # Test decorator
        print("\n3. Decorator test:")

        call_count = 0

        @cached_api("jupiter", ttl=60)
        async def get_price(token: str) -> float:
            nonlocal call_count
            call_count += 1
            print(f"   Fetching price for {token}...")
            return 150.0

        price1 = await get_price("SOL")
        price2 = await get_price("SOL")  # Should hit cache
        print(f"   Price: {price1}, calls: {call_count}")

        # Test parallel fetch
        print("\n4. Parallel fetch:")

        async def fetch_a():
            await asyncio.sleep(0.1)
            return {"a": 1}

        async def fetch_b():
            await asyncio.sleep(0.1)
            return {"b": 2}

        import time
        start = time.time()
        results = await parallel_fetch(
            api_a=fetch_a(),
            api_b=fetch_b()
        )
        elapsed = time.time() - start
        print(f"   Results: {results}")
        print(f"   Time: {elapsed:.3f}s (should be ~0.1s)")

        # Final stats
        print("\n5. Final stats:")
        stats = cache.get_stats()
        for api, api_stats in stats["by_api"].items():
            if api_stats["hits"] > 0 or api_stats["entries"] > 0:
                print(f"   {api}: {api_stats['hits']} hits, {api_stats['entries']} entries")

    asyncio.run(demo())
