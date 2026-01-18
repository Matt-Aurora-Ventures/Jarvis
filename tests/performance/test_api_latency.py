"""
Performance Tests for API Latency and Caching

Tests:
- API response caching with TTL management
- Cache hit rate tracking
- Parallel request handling
- Request deduplication
- Performance baselines
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


class TestAPICacheBasics:
    """Test basic API caching functionality."""

    def test_api_cache_import(self):
        """API cache module should be importable."""
        from core.cache.api_cache import APICache, get_api_cache

        assert APICache is not None
        assert get_api_cache is not None

    def test_api_cache_creation(self):
        """API cache should be creatable with default TTLs."""
        from core.cache.api_cache import APICache

        cache = APICache()

        assert cache is not None
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "invalidate")
        assert hasattr(cache, "get_stats")

    def test_default_ttl_configuration(self):
        """Cache should have correct default TTLs for each API."""
        from core.cache.api_cache import APICache, DEFAULT_TTLS

        # Check expected TTLs (in seconds)
        assert DEFAULT_TTLS["jupiter"] == 300  # 5 minutes
        assert DEFAULT_TTLS["solscan"] == 3600  # 1 hour
        assert DEFAULT_TTLS["coingecko"] == 1800  # 30 minutes
        assert DEFAULT_TTLS["grok"] == 7200  # 2 hours


class TestAPICacheOperations:
    """Test cache get/set operations."""

    def test_cache_set_and_get(self):
        """Cache should store and retrieve values."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "test_key", {"price": 100})
        result = cache.get("jupiter", "test_key")

        assert result is not None
        assert result["price"] == 100

    def test_cache_miss_returns_none(self):
        """Cache miss should return None."""
        from core.cache.api_cache import APICache

        cache = APICache()
        result = cache.get("jupiter", "nonexistent_key")

        assert result is None

    def test_cache_ttl_expiration(self):
        """Cache entries should expire after TTL."""
        from core.cache.api_cache import APICache

        cache = APICache()

        # Set with very short TTL
        cache.set("jupiter", "test_key", {"price": 100}, ttl=0.01)

        # Should be present immediately
        assert cache.get("jupiter", "test_key") is not None

        # Wait for expiration
        time.sleep(0.02)

        # Should be expired now
        assert cache.get("jupiter", "test_key") is None

    def test_cache_namespace_isolation(self):
        """Different API namespaces should be isolated."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "shared_key", {"source": "jupiter"})
        cache.set("solscan", "shared_key", {"source": "solscan"})

        jupiter_result = cache.get("jupiter", "shared_key")
        solscan_result = cache.get("solscan", "shared_key")

        assert jupiter_result["source"] == "jupiter"
        assert solscan_result["source"] == "solscan"


class TestCacheInvalidation:
    """Test cache invalidation features."""

    def test_invalidate_single_key(self):
        """Should invalidate a single key."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key1", {"value": 1})
        cache.set("jupiter", "key2", {"value": 2})

        cache.invalidate("jupiter", "key1")

        assert cache.get("jupiter", "key1") is None
        assert cache.get("jupiter", "key2") is not None

    def test_invalidate_api_namespace(self):
        """Should invalidate all keys for an API."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key1", {"value": 1})
        cache.set("jupiter", "key2", {"value": 2})
        cache.set("solscan", "key3", {"value": 3})

        cache.invalidate_api("jupiter")

        assert cache.get("jupiter", "key1") is None
        assert cache.get("jupiter", "key2") is None
        assert cache.get("solscan", "key3") is not None

    def test_clear_all_caches(self):
        """Should clear all caches."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key1", {"value": 1})
        cache.set("solscan", "key2", {"value": 2})

        cache.clear_all()

        assert cache.get("jupiter", "key1") is None
        assert cache.get("solscan", "key2") is None


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_stats_track_hits_and_misses(self):
        """Stats should track cache hits and misses."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "existing", {"value": 1})

        # Hit
        cache.get("jupiter", "existing")

        # Miss
        cache.get("jupiter", "nonexistent")

        stats = cache.get_stats()

        assert stats["total_hits"] >= 1
        assert stats["total_misses"] >= 1

    def test_stats_hit_rate_calculation(self):
        """Stats should calculate hit rate correctly."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key", {"value": 1})

        # 3 hits
        cache.get("jupiter", "key")
        cache.get("jupiter", "key")
        cache.get("jupiter", "key")

        # 1 miss
        cache.get("jupiter", "miss")

        stats = cache.get_stats()

        # 3 hits / 4 total = 0.75
        assert stats["hit_rate"] == 0.75

    def test_stats_per_api_breakdown(self):
        """Stats should have per-API breakdown."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key", {"value": 1})
        cache.set("solscan", "key", {"value": 2})

        cache.get("jupiter", "key")  # hit
        cache.get("solscan", "miss")  # miss

        stats = cache.get_stats()

        assert "by_api" in stats
        assert "jupiter" in stats["by_api"]
        assert "solscan" in stats["by_api"]
        assert stats["by_api"]["jupiter"]["hits"] >= 1
        assert stats["by_api"]["solscan"]["misses"] >= 1

    def test_stats_include_size(self):
        """Stats should include cache size."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key1", {"value": 1})
        cache.set("jupiter", "key2", {"value": 2})

        stats = cache.get_stats()

        assert stats["total_entries"] >= 2


class TestCachedAPIDecorator:
    """Test the @cached_api decorator."""

    @pytest.mark.asyncio
    async def test_decorator_caches_result(self):
        """Decorator should cache function results."""
        from core.cache.api_cache import cached_api, get_api_cache

        call_count = 0

        @cached_api("jupiter", ttl=60)
        async def fetch_price(token: str) -> float:
            nonlocal call_count
            call_count += 1
            return 100.0

        # First call - should execute function
        result1 = await fetch_price("SOL")
        assert result1 == 100.0
        assert call_count == 1

        # Second call - should use cache
        result2 = await fetch_price("SOL")
        assert result2 == 100.0
        assert call_count == 1  # Not incremented

        # Clear cache for cleanup
        get_api_cache().clear_all()

    @pytest.mark.asyncio
    async def test_decorator_different_args_different_cache(self):
        """Different arguments should have different cache entries."""
        from core.cache.api_cache import cached_api, get_api_cache

        call_count = 0

        @cached_api("jupiter", ttl=60)
        async def fetch_price(token: str) -> float:
            nonlocal call_count
            call_count += 1
            return 100.0 if token == "SOL" else 50.0

        result1 = await fetch_price("SOL")
        result2 = await fetch_price("ETH")

        assert result1 == 100.0
        assert result2 == 50.0
        assert call_count == 2  # Both called

        # Clear cache for cleanup
        get_api_cache().clear_all()


class TestRequestDeduplication:
    """Test request deduplication to prevent duplicate API calls."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_deduplicated(self):
        """Concurrent identical requests should be deduplicated."""
        from core.cache.api_cache import APICache

        cache = APICache()
        call_count = 0

        async def mock_fetch(key: str) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate network delay
            return {"value": key}

        # Start multiple concurrent requests
        tasks = [
            asyncio.create_task(
                cache.get_or_fetch("jupiter", "same_key", mock_fetch)
            )
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should get same result
        for r in results:
            assert r["value"] == "same_key"

        # But only one actual call should be made
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_deduplication_window(self):
        """Deduplication should work within time window."""
        from core.cache.api_cache import APICache

        cache = APICache()
        call_count = 0

        async def mock_fetch(key: str) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"value": call_count}

        # First request
        result1 = await cache.get_or_fetch("jupiter", "key", mock_fetch)

        # Immediate second request - should use cache
        result2 = await cache.get_or_fetch("jupiter", "key", mock_fetch)

        assert result1 == result2
        assert call_count == 1


class TestBatchAPIOperations:
    """Test batch API call optimization."""

    @pytest.mark.asyncio
    async def test_batch_fetch_multiple_tokens(self):
        """Should batch multiple token price requests."""
        from core.cache.api_cache import APICache

        cache = APICache()

        async def batch_fetcher(keys: list) -> Dict[str, Any]:
            return {key: {"price": idx * 100} for idx, key in enumerate(keys)}

        result = await cache.batch_get_or_fetch(
            "jupiter",
            ["SOL", "ETH", "BTC"],
            batch_fetcher
        )

        assert "SOL" in result
        assert "ETH" in result
        assert "BTC" in result

    @pytest.mark.asyncio
    async def test_batch_uses_cached_values(self):
        """Batch fetch should use cached values and only fetch missing."""
        from core.cache.api_cache import APICache

        cache = APICache()

        # Pre-cache SOL
        cache.set("jupiter", "SOL", {"price": 200})

        fetched_keys = []

        async def batch_fetcher(keys: list) -> Dict[str, Any]:
            fetched_keys.extend(keys)
            return {key: {"price": 100} for key in keys}

        result = await cache.batch_get_or_fetch(
            "jupiter",
            ["SOL", "ETH"],
            batch_fetcher
        )

        # SOL should come from cache with original value
        assert result["SOL"]["price"] == 200

        # Only ETH should have been fetched
        assert "ETH" in fetched_keys
        assert "SOL" not in fetched_keys


class TestParallelAPIOperations:
    """Test parallel API call execution."""

    @pytest.mark.asyncio
    async def test_parallel_fetch_independent_apis(self):
        """Should fetch from multiple APIs in parallel."""
        from core.cache.api_cache import parallel_fetch

        call_times = []

        async def mock_jupiter():
            call_times.append(("jupiter", time.time()))
            await asyncio.sleep(0.1)
            return {"jupiter": "data"}

        async def mock_solscan():
            call_times.append(("solscan", time.time()))
            await asyncio.sleep(0.1)
            return {"solscan": "data"}

        start = time.time()
        results = await parallel_fetch(
            jupiter=mock_jupiter(),
            solscan=mock_solscan()
        )
        elapsed = time.time() - start

        # Both should complete
        assert "jupiter" in results
        assert "solscan" in results

        # Should run in parallel (total time ~0.1s, not 0.2s)
        assert elapsed < 0.15

    @pytest.mark.asyncio
    async def test_parallel_fetch_handles_errors(self):
        """Parallel fetch should handle individual failures gracefully."""
        from core.cache.api_cache import parallel_fetch

        async def mock_success():
            return {"success": True}

        async def mock_failure():
            raise Exception("API Error")

        results = await parallel_fetch(
            success=mock_success(),
            failure=mock_failure()
        )

        assert results["success"]["success"] is True
        assert results["failure"] is None  # Failed but didn't crash


class TestTTLAdjustment:
    """Test TTL adjustment functionality."""

    def test_adjust_api_ttl(self):
        """Should be able to adjust TTL for specific API."""
        from core.cache.api_cache import APICache

        cache = APICache()

        original_ttl = cache.get_ttl("jupiter")

        cache.set_ttl("jupiter", 600)  # 10 minutes

        new_ttl = cache.get_ttl("jupiter")

        assert new_ttl == 600
        assert new_ttl != original_ttl

    def test_ttl_applied_to_new_entries(self):
        """New entries should use the adjusted TTL."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set_ttl("jupiter", 0.01)  # Very short

        cache.set("jupiter", "key", {"value": 1})

        # Should exist immediately
        assert cache.get("jupiter", "key") is not None

        # Wait for expiration
        time.sleep(0.02)

        # Should be expired
        assert cache.get("jupiter", "key") is None


class TestCacheManagementScriptFunctions:
    """Test functions used by cache management script."""

    def test_get_cache_info(self):
        """Should get comprehensive cache info."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key1", {"value": 1})
        cache.set("solscan", "key2", {"value": 2})

        info = cache.get_info()

        assert "apis" in info
        assert "total_entries" in info
        assert "memory_usage_bytes" in info

    def test_export_stats_json(self):
        """Should export stats as JSON."""
        from core.cache.api_cache import APICache
        import json

        cache = APICache()

        cache.set("jupiter", "key", {"value": 1})
        cache.get("jupiter", "key")

        json_stats = cache.export_stats_json()

        # Should be valid JSON
        parsed = json.loads(json_stats)
        assert "total_hits" in parsed


class TestPerformanceBaselines:
    """Test performance baseline measurements."""

    @pytest.mark.asyncio
    async def test_cache_get_latency(self):
        """Cache get should be fast (<1ms)."""
        from core.cache.api_cache import APICache

        cache = APICache()

        cache.set("jupiter", "key", {"value": 1})

        # Warm up
        cache.get("jupiter", "key")

        # Measure
        start = time.perf_counter()
        for _ in range(100):
            cache.get("jupiter", "key")
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000

        # Should average under 1ms per get
        assert avg_ms < 1.0

    @pytest.mark.asyncio
    async def test_cache_set_latency(self):
        """Cache set should be fast (<1ms)."""
        from core.cache.api_cache import APICache

        cache = APICache()

        # Measure
        start = time.perf_counter()
        for i in range(100):
            cache.set("jupiter", f"key_{i}", {"value": i})
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000

        # Should average under 1ms per set
        assert avg_ms < 1.0
