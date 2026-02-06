"""
Tests for ClawdBot caching layer.

Tests:
- CacheManager with get, set, delete, clear_pattern, get_stats
- InMemoryCache - fast single-process caching
- FileCache - persistent JSON file caching
- TTLCache - automatic expiration
- LRUCache - least recently used eviction
- @cached decorator with TTL
- @cache_key for custom key generation
- invalidate_cache(pattern) for pattern-based invalidation
- APIResponseCache for LLM response caching
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Import the modules we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    cache_dir = tempfile.mkdtemp(prefix="clawdbot_cache_test_")
    yield cache_dir
    shutil.rmtree(cache_dir, ignore_errors=True)


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create a CacheManager instance for testing."""
    from core.cache.manager import CacheManager
    return CacheManager(cache_dir=temp_cache_dir)


@pytest.fixture
def in_memory_cache():
    """Create an InMemoryCache instance for testing."""
    from core.cache.backends import InMemoryCache
    return InMemoryCache(max_size=100)


@pytest.fixture
def file_cache(temp_cache_dir):
    """Create a FileCache instance for testing."""
    from core.cache.backends import FileCache
    return FileCache(cache_dir=temp_cache_dir)


@pytest.fixture
def ttl_cache():
    """Create a TTLCache instance for testing."""
    from core.cache.backends import TTLCache
    return TTLCache(default_ttl=1)  # 1 second for fast testing


@pytest.fixture
def lru_cache():
    """Create an LRUCache instance for testing."""
    from core.cache.backends import LRUCache
    return LRUCache(max_size=3)


@pytest.fixture
def api_cache(temp_cache_dir):
    """Create an APIResponseCache instance for testing."""
    from core.cache.api_cache import LLMResponseCache
    return LLMResponseCache(cache_dir=temp_cache_dir)


# =============================================================================
# CACHE MANAGER TESTS
# =============================================================================

class TestCacheManager:
    """Tests for CacheManager class."""

    def test_get_returns_none_for_missing_key(self, cache_manager):
        """Test that get returns None for non-existent key."""
        result = cache_manager.get("nonexistent_key")
        assert result is None

    def test_set_and_get_basic(self, cache_manager):
        """Test basic set and get operations."""
        cache_manager.set("key1", "value1", ttl_seconds=300)
        result = cache_manager.get("key1")
        assert result == "value1"

    def test_set_and_get_complex_value(self, cache_manager):
        """Test caching complex data structures."""
        data = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"a": 1, "b": 2}
        }
        cache_manager.set("complex_key", data, ttl_seconds=300)
        result = cache_manager.get("complex_key")
        assert result == data

    def test_delete_removes_key(self, cache_manager):
        """Test that delete removes a key."""
        cache_manager.set("key1", "value1", ttl_seconds=300)
        assert cache_manager.get("key1") == "value1"

        cache_manager.delete("key1")
        assert cache_manager.get("key1") is None

    def test_delete_returns_false_for_missing_key(self, cache_manager):
        """Test that delete returns False for non-existent key."""
        result = cache_manager.delete("nonexistent")
        assert result is False

    def test_clear_pattern_removes_matching_keys(self, cache_manager):
        """Test that clear_pattern removes all matching keys."""
        # Set up keys with a pattern
        cache_manager.set("llm:grok:prompt1", "response1", ttl_seconds=300)
        cache_manager.set("llm:grok:prompt2", "response2", ttl_seconds=300)
        cache_manager.set("llm:claude:prompt1", "response3", ttl_seconds=300)
        cache_manager.set("other:key", "value", ttl_seconds=300)

        # Clear all grok keys
        count = cache_manager.clear_pattern("llm:grok:*")

        assert count == 2
        assert cache_manager.get("llm:grok:prompt1") is None
        assert cache_manager.get("llm:grok:prompt2") is None
        assert cache_manager.get("llm:claude:prompt1") == "response3"
        assert cache_manager.get("other:key") == "value"

    def test_get_stats_returns_cache_stats(self, cache_manager):
        """Test that get_stats returns CacheStats."""
        from core.cache.manager import CacheStats

        # Generate some cache activity
        cache_manager.set("key1", "value1", ttl_seconds=300)
        cache_manager.get("key1")  # hit
        cache_manager.get("key2")  # miss

        stats = cache_manager.get_stats()

        assert isinstance(stats, CacheStats)
        assert stats.hits >= 1
        assert stats.misses >= 1
        assert stats.entries >= 1
        assert 0 <= stats.hit_rate <= 1

    def test_ttl_expiration(self, cache_manager):
        """Test that entries expire after TTL."""
        cache_manager.set("expiring_key", "value", ttl_seconds=0.1)

        # Should be available immediately
        assert cache_manager.get("expiring_key") == "value"

        # Wait for expiration
        time.sleep(0.2)

        # Should be expired
        assert cache_manager.get("expiring_key") is None


# =============================================================================
# IN-MEMORY CACHE TESTS
# =============================================================================

class TestInMemoryCache:
    """Tests for InMemoryCache backend."""

    def test_basic_operations(self, in_memory_cache):
        """Test basic set/get/delete operations."""
        in_memory_cache.set("key1", "value1")
        assert in_memory_cache.get("key1") == "value1"

        in_memory_cache.delete("key1")
        assert in_memory_cache.get("key1") is None

    def test_max_size_eviction(self):
        """Test that cache evicts old entries when at max size."""
        from core.cache.backends import InMemoryCache
        cache = InMemoryCache(max_size=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_thread_safety(self, in_memory_cache):
        """Test that cache operations are thread-safe."""
        import threading

        errors = []

        def writer():
            try:
                for i in range(100):
                    in_memory_cache.set(f"key_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    in_memory_cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =============================================================================
# FILE CACHE TESTS
# =============================================================================

class TestFileCache:
    """Tests for FileCache backend (persistent JSON)."""

    def test_basic_operations(self, file_cache):
        """Test basic set/get/delete operations."""
        file_cache.set("key1", {"data": "value1"})
        result = file_cache.get("key1")
        assert result == {"data": "value1"}

        file_cache.delete("key1")
        assert file_cache.get("key1") is None

    def test_persistence_across_instances(self, temp_cache_dir):
        """Test that data persists across cache instances."""
        from core.cache.backends import FileCache

        # Write with first instance
        cache1 = FileCache(cache_dir=temp_cache_dir)
        cache1.set("persistent_key", {"value": 42}, ttl_seconds=300)

        # Read with second instance
        cache2 = FileCache(cache_dir=temp_cache_dir)
        result = cache2.get("persistent_key")

        assert result == {"value": 42}

    def test_ttl_expiration(self, file_cache):
        """Test that file cache entries expire."""
        file_cache.set("expiring_key", "value", ttl_seconds=0.1)

        assert file_cache.get("expiring_key") == "value"

        time.sleep(0.2)

        assert file_cache.get("expiring_key") is None

    def test_clear_removes_all_files(self, file_cache, temp_cache_dir):
        """Test that clear removes all cache files."""
        file_cache.set("key1", "value1")
        file_cache.set("key2", "value2")

        file_cache.clear()

        assert file_cache.get("key1") is None
        assert file_cache.get("key2") is None


# =============================================================================
# TTL CACHE TESTS
# =============================================================================

class TestTTLCache:
    """Tests for TTLCache with automatic expiration."""

    def test_default_ttl(self, ttl_cache):
        """Test that entries expire with default TTL."""
        ttl_cache.set("key1", "value1")

        assert ttl_cache.get("key1") == "value1"

        time.sleep(1.1)  # Default TTL is 1 second

        assert ttl_cache.get("key1") is None

    def test_custom_ttl_overrides_default(self, ttl_cache):
        """Test that custom TTL overrides default."""
        ttl_cache.set("key1", "value1", ttl_seconds=0.2)
        ttl_cache.set("key2", "value2", ttl_seconds=2)

        time.sleep(0.3)

        assert ttl_cache.get("key1") is None  # Expired
        assert ttl_cache.get("key2") == "value2"  # Not expired

    def test_cleanup_expired(self, ttl_cache):
        """Test cleanup of expired entries."""
        ttl_cache.set("key1", "value1", ttl_seconds=0.1)
        ttl_cache.set("key2", "value2", ttl_seconds=10)

        time.sleep(0.2)

        removed = ttl_cache.cleanup_expired()

        assert removed >= 1
        assert ttl_cache.get("key2") == "value2"


# =============================================================================
# LRU CACHE TESTS
# =============================================================================

class TestLRUCache:
    """Tests for LRUCache with least-recently-used eviction."""

    def test_lru_eviction(self, lru_cache):
        """Test that least recently used entries are evicted first."""
        lru_cache.set("key1", "value1")
        lru_cache.set("key2", "value2")
        lru_cache.set("key3", "value3")

        # Access key1 to make it recently used
        lru_cache.get("key1")

        # Add key4, should evict key2 (least recently used)
        lru_cache.set("key4", "value4")

        assert lru_cache.get("key1") == "value1"  # Not evicted (recently accessed)
        assert lru_cache.get("key2") is None  # Evicted (least recently used)
        assert lru_cache.get("key3") == "value3"  # Not evicted
        assert lru_cache.get("key4") == "value4"  # Newly added

    def test_set_updates_existing_key(self, lru_cache):
        """Test that setting an existing key updates its value and recency."""
        lru_cache.set("key1", "value1")
        lru_cache.set("key2", "value2")
        lru_cache.set("key3", "value3")

        # Update key1
        lru_cache.set("key1", "updated_value1")

        # Add key4, should evict key2 (key1 was updated so it's recent)
        lru_cache.set("key4", "value4")

        assert lru_cache.get("key1") == "updated_value1"
        assert lru_cache.get("key2") is None  # Evicted


# =============================================================================
# DECORATOR TESTS
# =============================================================================

class TestCachedDecorator:
    """Tests for @cached decorator."""

    def test_cached_decorator_basic(self, temp_cache_dir):
        """Test that @cached decorator caches function results."""
        from core.cache.decorators import cached

        call_count = 0

        @cached(ttl=300, cache_dir=temp_cache_dir)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - computes
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - cached
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

        # Different argument - computes
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator_async(self, temp_cache_dir):
        """Test that @cached decorator works with async functions."""
        from core.cache.decorators import cached

        call_count = 0

        @cached(ttl=300, cache_dir=temp_cache_dir)
        async def async_expensive_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2

        # First call - computes
        result1 = await async_expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - cached
        result2 = await async_expensive_function(5)
        assert result2 == 10
        assert call_count == 1

    def test_cached_decorator_ttl_expiration(self, temp_cache_dir):
        """Test that @cached decorator respects TTL."""
        from core.cache.decorators import cached

        call_count = 0

        @cached(ttl=0.1, cache_dir=temp_cache_dir)
        def short_ttl_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = short_ttl_function(5)
        assert call_count == 1

        # Wait for expiration
        time.sleep(0.2)

        # Should recompute after expiration
        result2 = short_ttl_function(5)
        assert call_count == 2


class TestCacheKeyDecorator:
    """Tests for @cache_key custom key generation."""

    def test_custom_cache_key(self, temp_cache_dir):
        """Test custom cache key generation."""
        from core.cache.decorators import cached, cache_key

        call_count = 0

        @cache_key(lambda user_id, **kwargs: f"user:{user_id}")
        @cached(ttl=300, cache_dir=temp_cache_dir)
        def get_user_data(user_id, include_details=False):
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": f"User {user_id}"}

        # First call
        result1 = get_user_data(123, include_details=False)
        assert call_count == 1

        # Same user, different kwargs - should still hit cache
        # because custom key only uses user_id
        result2 = get_user_data(123, include_details=True)
        assert call_count == 1  # Cached based on custom key


class TestInvalidateCache:
    """Tests for invalidate_cache function."""

    def test_invalidate_single_key(self, temp_cache_dir):
        """Test invalidating a single key."""
        from core.cache.decorators import cached, invalidate_cache

        @cached(ttl=300, cache_dir=temp_cache_dir)
        def cacheable_function(x):
            return x * 2

        # Populate cache
        cacheable_function(5)

        # Invalidate
        invalidate_cache("cacheable_function:5", cache_dir=temp_cache_dir)

        # Cache should be invalidated
        call_count = 0
        original_func = cacheable_function.__wrapped__

        @cached(ttl=300, cache_dir=temp_cache_dir)
        def cacheable_function_v2(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result = cacheable_function_v2(5)
        assert call_count == 1  # Should recompute

    def test_invalidate_pattern(self, temp_cache_dir):
        """Test invalidating with a pattern."""
        from core.cache.manager import CacheManager

        manager = CacheManager(cache_dir=temp_cache_dir)

        # Set up multiple keys
        manager.set("user:1:profile", {"name": "Alice"}, ttl_seconds=300)
        manager.set("user:1:settings", {"theme": "dark"}, ttl_seconds=300)
        manager.set("user:2:profile", {"name": "Bob"}, ttl_seconds=300)
        manager.set("post:1", {"title": "Hello"}, ttl_seconds=300)

        # Invalidate all user:1 keys
        from core.cache.decorators import invalidate_cache
        count = invalidate_cache("user:1:*", cache_dir=temp_cache_dir)

        assert count == 2
        assert manager.get("user:1:profile") is None
        assert manager.get("user:1:settings") is None
        assert manager.get("user:2:profile") == {"name": "Bob"}
        assert manager.get("post:1") == {"title": "Hello"}


# =============================================================================
# LLM RESPONSE CACHE TESTS
# =============================================================================

class TestLLMResponseCache:
    """Tests for LLM response caching."""

    def test_cache_llm_response(self, api_cache):
        """Test caching an LLM response."""
        prompt = "What is the capital of France?"
        response = "The capital of France is Paris."

        api_cache.cache_llm_response(prompt, response, model="grok")

        cached = api_cache.get_cached_response(prompt, model="grok")
        assert cached == response

    def test_cache_llm_response_with_hash(self, api_cache):
        """Test caching with explicit prompt hash."""
        import hashlib

        prompt = "What is 2 + 2?"
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        response = "2 + 2 equals 4."

        api_cache.cache_llm_response(prompt_hash, response, model="claude")

        cached = api_cache.get_cached_response(prompt_hash, model="claude")
        assert cached == response

    def test_different_models_different_caches(self, api_cache):
        """Test that different models have separate cache namespaces."""
        prompt = "Hello"
        response_grok = "Grok response"
        response_claude = "Claude response"

        api_cache.cache_llm_response(prompt, response_grok, model="grok")
        api_cache.cache_llm_response(prompt, response_claude, model="claude")

        assert api_cache.get_cached_response(prompt, model="grok") == response_grok
        assert api_cache.get_cached_response(prompt, model="claude") == response_claude

    def test_cache_with_metadata(self, api_cache):
        """Test caching with metadata."""
        prompt = "Analyze this token"
        response = {"sentiment": "bullish", "score": 75}
        metadata = {"tokens_used": 150, "latency_ms": 500}

        api_cache.cache_llm_response(
            prompt, response, model="grok", metadata=metadata
        )

        cached, cached_metadata = api_cache.get_cached_response(
            prompt, model="grok", include_metadata=True
        )

        assert cached == response
        assert cached_metadata["tokens_used"] == 150
        assert cached_metadata["latency_ms"] == 500

    def test_get_stats(self, api_cache):
        """Test getting cache stats."""
        # Generate some activity
        api_cache.cache_llm_response("p1", "r1", model="grok")
        api_cache.get_cached_response("p1", model="grok")  # hit
        api_cache.get_cached_response("p2", model="grok")  # miss

        stats = api_cache.get_stats()

        assert stats.hits >= 1
        assert stats.misses >= 1
        assert "grok" in stats.by_model

    def test_ttl_expiration(self, api_cache):
        """Test that LLM responses expire."""
        api_cache.cache_llm_response(
            "prompt", "response", model="grok", ttl_seconds=0.1
        )

        assert api_cache.get_cached_response("prompt", model="grok") == "response"

        time.sleep(0.2)

        assert api_cache.get_cached_response("prompt", model="grok") is None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestCacheIntegration:
    """Integration tests for the caching layer."""

    def test_cache_manager_uses_default_location(self):
        """Test that cache manager uses bots/data/cache/ by default."""
        from core.cache.manager import CacheManager, DEFAULT_CACHE_DIR

        assert "bots/data/cache" in DEFAULT_CACHE_DIR or "bots\\data\\cache" in DEFAULT_CACHE_DIR

    def test_end_to_end_caching_workflow(self, temp_cache_dir):
        """Test a complete caching workflow."""
        from core.cache.manager import CacheManager
        from core.cache.decorators import cached

        manager = CacheManager(cache_dir=temp_cache_dir)

        # Direct cache operations
        manager.set("direct:key", {"value": 1}, ttl_seconds=300)
        assert manager.get("direct:key") == {"value": 1}

        # Decorator-based caching
        call_count = 0

        @cached(ttl=300, cache_dir=temp_cache_dir)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x ** 2

        assert compute(5) == 25
        assert compute(5) == 25  # Cached
        assert call_count == 1

        # Stats tracking
        stats = manager.get_stats()
        assert stats.entries > 0

        # Pattern-based invalidation
        manager.set("user:1:data", "data1", ttl_seconds=300)
        manager.set("user:2:data", "data2", ttl_seconds=300)
        manager.clear_pattern("user:*")

        assert manager.get("user:1:data") is None
        assert manager.get("user:2:data") is None
