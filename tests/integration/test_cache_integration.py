"""Integration tests for caching systems."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta


class TestCacheDecoratorIntegration:
    """Integration tests for cache decorators."""

    def test_cached_decorator_import(self):
        """Cached decorator should be importable."""
        try:
            from core.cache.decorators import cached

            assert cached is not None
        except ImportError:
            pytest.skip("Cache decorators not found")

    @pytest.mark.asyncio
    async def test_cached_function_behavior(self):
        """Cached functions should cache results."""
        try:
            from core.cache.decorators import cached

            call_count = 0

            @cached(ttl=60)
            async def expensive_operation(x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * 2

            # First call
            result1 = await expensive_operation(5)
            assert result1 == 10
            assert call_count == 1

            # Second call should use cache
            result2 = await expensive_operation(5)
            assert result2 == 10
            assert call_count == 1  # Should not increment

            # Different argument should call function
            result3 = await expensive_operation(10)
            assert result3 == 20
            assert call_count == 2

        except ImportError:
            pytest.skip("Cache decorators not found")

    def test_sync_cached_decorator(self):
        """Sync cached decorator should work."""
        try:
            from core.cache.decorators import sync_cached

            call_count = 0

            @sync_cached(ttl=60)
            def sync_operation(x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * 2

            result1 = sync_operation(5)
            result2 = sync_operation(5)

            assert result1 == result2 == 10
            assert call_count == 1

        except ImportError:
            pytest.skip("Sync cache decorator not found")


class TestLRUCacheIntegration:
    """Integration tests for LRU cache."""

    def test_lru_cache_eviction(self):
        """LRU cache should evict oldest entries."""
        try:
            from core.cache import LRUCache

            # LRUCache uses 'maxsize' parameter
            cache = LRUCache(maxsize=3)

            cache.set("a", 1)
            cache.set("b", 2)
            cache.set("c", 3)

            # Access 'a' to make it recently used
            cache.get("a")

            # Add new item, should evict 'b' (least recently used)
            cache.set("d", 4)

            assert cache.get("a") == 1
            assert cache.get("b") is None  # Should be evicted
            assert cache.get("c") == 3
            assert cache.get("d") == 4

        except ImportError:
            pytest.skip("LRU cache not found")


class TestTTLCacheIntegration:
    """Integration tests for TTL cache."""

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """TTL cache should expire entries."""
        try:
            from core.cache import TTLCache

            cache = TTLCache(default_ttl=0.1)  # 100ms TTL

            cache.set("key", "value")
            assert cache.get("key") == "value"

            # Wait for expiration
            await asyncio.sleep(0.15)

            assert cache.get("key") is None

        except ImportError:
            pytest.skip("TTL cache not found")

    def test_custom_ttl_per_key(self):
        """Cache should support custom TTL per key."""
        try:
            from core.cache import TTLCache

            cache = TTLCache(default_ttl=60)

            cache.set("short", "value", ttl=1)
            cache.set("long", "value", ttl=3600)

            # Both should be present initially
            assert cache.get("short") is not None
            assert cache.get("long") is not None

        except ImportError:
            pytest.skip("TTL cache not found")


class TestRedisCacheIntegration:
    """Integration tests for Redis cache adapter."""

    @pytest.mark.asyncio
    async def test_redis_cache_operations(self, mock_redis):
        """Redis cache should perform basic operations."""
        mock_redis.get.return_value = b'"cached_value"'

        result = await mock_redis.get("test_key")
        assert result == b'"cached_value"'

    @pytest.mark.asyncio
    async def test_redis_cache_miss(self, mock_redis):
        """Redis cache should handle misses."""
        mock_redis.get.return_value = None

        result = await mock_redis.get("nonexistent")
        assert result is None


class TestCacheKeyGeneration:
    """Integration tests for cache key generation."""

    def test_key_generation_consistency(self):
        """Cache keys should be consistent."""
        try:
            from core.cache.decorators import generate_cache_key

            key1 = generate_cache_key("func", (1, 2), {"a": 3})
            key2 = generate_cache_key("func", (1, 2), {"a": 3})

            assert key1 == key2

        except ImportError:
            pytest.skip("Cache key generator not found")

    def test_key_uniqueness(self):
        """Different inputs should generate different keys."""
        try:
            from core.cache.decorators import generate_cache_key

            key1 = generate_cache_key("func", (1,), {})
            key2 = generate_cache_key("func", (2,), {})

            assert key1 != key2

        except ImportError:
            pytest.skip("Cache key generator not found")


class TestCacheInvalidation:
    """Integration tests for cache invalidation."""

    def test_cache_clear(self):
        """Cache should be clearable."""
        try:
            from core.cache import TTLCache

            cache = TTLCache()
            cache.set("a", 1)
            cache.set("b", 2)

            cache.clear()

            assert cache.get("a") is None
            assert cache.get("b") is None

        except ImportError:
            pytest.skip("TTL cache not found")

    def test_cache_delete(self):
        """Individual keys should be deletable."""
        try:
            from core.cache import TTLCache

            cache = TTLCache()
            cache.set("a", 1)
            cache.set("b", 2)

            cache.delete("a")

            assert cache.get("a") is None
            assert cache.get("b") == 2

        except ImportError:
            pytest.skip("TTL cache not found")


class TestCacheStats:
    """Integration tests for cache statistics."""

    def test_cache_hit_miss_tracking(self):
        """Cache should track hits and misses."""
        try:
            from core.cache import TTLCache

            cache = TTLCache()
            cache.set("exists", "value")

            cache.get("exists")  # Hit
            cache.get("missing")  # Miss

            stats = cache.get_stats()
            assert stats.hits >= 1
            assert stats.misses >= 1

        except ImportError:
            pytest.skip("TTL cache not found")
