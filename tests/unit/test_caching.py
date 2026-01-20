"""
Unit tests for the multi-level caching system.

Tests the following components:
- Multi-level caching (memory, file, redis)
- TTL-based cache expiration
- Cache invalidation strategies
- Cache hit/miss statistics
- Concurrent access safety
"""
import pytest
import asyncio
import tempfile
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


class TestMemoryCache:
    """Tests for in-memory caching layer."""

    def test_memory_cache_set_and_get(self):
        """Memory cache should store and retrieve values."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")

        assert result == {"data": "value"}

    def test_memory_cache_miss_returns_none(self):
        """Memory cache should return None for missing keys."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        result = cache.get("nonexistent_key")
        assert result is None

    def test_memory_cache_ttl_expiration(self):
        """Memory cache should expire entries based on TTL."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("expiring_key", "value", ttl=0.1)  # 100ms TTL
        assert cache.get("expiring_key") == "value"

        time.sleep(0.15)
        assert cache.get("expiring_key") is None

    def test_memory_cache_lru_eviction(self):
        """Memory cache should evict least recently used items when full."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(
            enable_file=False,
            enable_redis=False,
            max_memory_items=3
        )

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4, should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"  # Recently accessed
        assert cache.get("key2") is None      # Should be evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"


class TestFileCache:
    """Tests for file-based caching layer."""

    def test_file_cache_persistence(self):
        """File cache should persist data across instances."""
        from core.caching.cache_manager import MultiLevelCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache"

            # Write with first instance
            cache1 = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )
            cache1.set("persistent_key", {"data": "persisted"})
            cache1.flush()

            # Read with second instance
            cache2 = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )
            result = cache2.get("persistent_key")

            assert result == {"data": "persisted"}

    def test_file_cache_ttl_across_restarts(self):
        """File cache should respect TTL even after restart."""
        from core.caching.cache_manager import MultiLevelCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache"

            # Write with short TTL
            cache1 = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )
            cache1.set("expiring", "value", ttl=0.1)
            cache1.flush()

            time.sleep(0.15)

            # Should be expired in new instance
            cache2 = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )
            assert cache2.get("expiring") is None


class TestMultiLevelCaching:
    """Tests for multi-level cache coordination."""

    def test_cache_promotion(self):
        """Reading from file should promote to memory cache."""
        from core.caching.cache_manager import MultiLevelCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache"

            # Write to file cache only
            cache = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )

            # Directly write to file level
            cache._file_set("promoted_key", {"data": "value"}, ttl=3600)

            # Clear memory cache
            cache._memory_cache.clear()

            # Read - should promote to memory
            result = cache.get("promoted_key")
            assert result == {"data": "value"}

            # Should now be in memory
            assert "promoted_key" in cache._memory_cache

    def test_cache_write_through(self):
        """Writes should go to all enabled levels."""
        from core.caching.cache_manager import MultiLevelCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache"

            cache = MultiLevelCache(
                enable_file=True,
                enable_redis=False,
                file_cache_path=str(cache_path)
            )

            cache.set("write_through_key", {"data": "value"})

            # Should be in memory
            assert "write_through_key" in cache._memory_cache

            # Should be in file (after flush)
            cache.flush()
            file_result = cache._file_get("write_through_key")
            assert file_result == {"data": "value"}


class TestCacheInvalidation:
    """Tests for cache invalidation strategies."""

    def test_invalidate_single_key(self):
        """Should invalidate a single key from all levels."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_by_prefix(self):
        """Should invalidate all keys with a given prefix."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("user:1:profile", {"name": "Alice"})
        cache.set("user:1:settings", {"theme": "dark"})
        cache.set("user:2:profile", {"name": "Bob"})
        cache.set("product:1", {"price": 100})

        # Invalidate all user:1:* keys
        count = cache.invalidate_by_prefix("user:1:")

        assert count == 2
        assert cache.get("user:1:profile") is None
        assert cache.get("user:1:settings") is None
        assert cache.get("user:2:profile") == {"name": "Bob"}
        assert cache.get("product:1") == {"price": 100}

    def test_invalidate_by_tag(self):
        """Should invalidate all keys with a given tag."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("key1", "value1", tags=["price", "token:SOL"])
        cache.set("key2", "value2", tags=["price", "token:BTC"])
        cache.set("key3", "value3", tags=["balance"])

        # Invalidate all price-related keys
        count = cache.invalidate_by_tag("price")

        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    def test_clear_all(self):
        """Should clear all entries from all levels."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        for i in range(10):
            cache.set(f"key{i}", f"value{i}")

        cache.clear_all()

        for i in range(10):
            assert cache.get(f"key{i}") is None


class TestCacheStatistics:
    """Tests for cache hit/miss statistics."""

    def test_hit_miss_tracking(self):
        """Should track cache hits and misses."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2/3, rel=0.01)

    def test_per_namespace_stats(self):
        """Should track stats per namespace."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("prices:SOL", 100, namespace="prices")
        cache.set("balances:wallet1", 500, namespace="balances")

        cache.get("prices:SOL", namespace="prices")  # Hit
        cache.get("prices:BTC", namespace="prices")  # Miss
        cache.get("balances:wallet1", namespace="balances")  # Hit

        stats = cache.get_stats()

        assert "by_namespace" in stats
        assert stats["by_namespace"]["prices"]["hits"] == 1
        assert stats["by_namespace"]["prices"]["misses"] == 1
        assert stats["by_namespace"]["balances"]["hits"] == 1

    def test_stats_export_json(self):
        """Should export stats as JSON."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("key", "value")
        cache.get("key")

        json_stats = cache.export_stats_json()
        parsed = json.loads(json_stats)

        assert "hits" in parsed
        assert "misses" in parsed
        assert "hit_rate" in parsed


class TestConcurrentAccess:
    """Tests for thread-safe cache operations."""

    def test_concurrent_writes(self):
        """Cache should handle concurrent writes safely."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)
        errors = []

        def writer(thread_id):
            try:
                for i in range(100):
                    cache.set(f"thread{thread_id}:key{i}", f"value{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify some keys
        assert cache.get("thread0:key50") == "value50"
        assert cache.get("thread4:key99") == "value99"

    def test_concurrent_reads(self):
        """Cache should handle concurrent reads safely."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        # Pre-populate
        for i in range(100):
            cache.set(f"key{i}", f"value{i}")

        results = []
        errors = []

        def reader(thread_id):
            try:
                for i in range(100):
                    result = cache.get(f"key{i}")
                    results.append((thread_id, i, result))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 500  # 5 threads * 100 reads


class TestCacheDecorator:
    """Tests for the @cached decorator."""

    def test_cached_decorator_basic(self):
        """@cached decorator should cache function results."""
        from core.caching.cache_manager import cached, get_multi_level_cache

        call_count = 0

        @cached(ttl=60)
        def expensive_operation(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_operation(5)
        result2 = expensive_operation(5)  # Should hit cache
        result3 = expensive_operation(10)  # Different arg, no cache

        assert result1 == 10
        assert result2 == 10
        assert result3 == 20
        assert call_count == 2  # Only 2 actual calls

    @pytest.mark.asyncio
    async def test_cached_decorator_async(self):
        """@cached decorator should work with async functions."""
        from core.caching.cache_manager import cached

        call_count = 0

        @cached(ttl=60)
        async def async_operation(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 3

        result1 = await async_operation(5)
        result2 = await async_operation(5)  # Should hit cache

        assert result1 == 15
        assert result2 == 15
        assert call_count == 1

    def test_cached_decorator_with_namespace(self):
        """@cached decorator should support namespaces."""
        from core.caching.cache_manager import cached, get_multi_level_cache

        @cached(ttl=60, namespace="prices")
        def get_price(token):
            return {"token": token, "price": 100}

        result = get_price("SOL")
        assert result["token"] == "SOL"

        # Check it's in the right namespace
        cache = get_multi_level_cache()
        stats = cache.get_stats()
        assert "prices" in stats.get("by_namespace", {})


class TestBatchOperations:
    """Tests for batch cache operations."""

    def test_batch_get(self):
        """Should get multiple keys in one call."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        results = cache.batch_get(["key1", "key2", "nonexistent"])

        assert results["key1"] == "value1"
        assert results["key2"] == "value2"
        assert results["nonexistent"] is None

    def test_batch_set(self):
        """Should set multiple keys in one call."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        cache.batch_set({
            "batch1": "value1",
            "batch2": "value2",
            "batch3": "value3"
        })

        assert cache.get("batch1") == "value1"
        assert cache.get("batch2") == "value2"
        assert cache.get("batch3") == "value3"

    @pytest.mark.asyncio
    async def test_batch_get_or_fetch(self):
        """Should fetch only missing keys in batch."""
        from core.caching.cache_manager import MultiLevelCache

        cache = MultiLevelCache(enable_file=False, enable_redis=False)

        # Pre-populate some keys
        cache.set("key1", "cached_value1")

        fetched_keys = []

        async def fetcher(keys):
            fetched_keys.extend(keys)
            return {k: f"fetched_{k}" for k in keys}

        results = await cache.batch_get_or_fetch(
            keys=["key1", "key2", "key3"],
            fetcher=fetcher
        )

        assert results["key1"] == "cached_value1"  # From cache
        assert results["key2"] == "fetched_key2"   # Fetched
        assert results["key3"] == "fetched_key3"   # Fetched
        assert fetched_keys == ["key2", "key3"]     # Only missing keys fetched
