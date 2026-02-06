"""
Tests for bots/shared/cache.py - ClawdBots caching module.

Tests cover:
1. In-memory caching (cache_get, cache_set, cache_delete, cache_clear)
2. TTL expiration and auto-eviction
3. File-based persistence
4. LRU eviction when max entries reached
5. Cache statistics (hit rate, entries, size)
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCacheBasicOperations:
    """Test basic cache get/set/delete/clear operations."""

    def test_cache_set_and_get_basic(self):
        """Test basic set and get operations."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)  # Memory-only

        cache.cache_set("key1", "value1")
        result = cache.cache_get("key1")

        assert result == "value1"

    def test_cache_get_nonexistent_returns_default(self):
        """Test get returns default for missing key."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        result = cache.cache_get("nonexistent", default="default_val")

        assert result == "default_val"

    def test_cache_get_nonexistent_returns_none_by_default(self):
        """Test get returns None for missing key when no default specified."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        result = cache.cache_get("nonexistent")

        assert result is None

    def test_cache_set_overwrites_existing(self):
        """Test set overwrites existing value."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_set("key1", "value2")
        result = cache.cache_get("key1")

        assert result == "value2"

    def test_cache_delete_removes_entry(self):
        """Test delete removes entry."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_delete("key1")
        result = cache.cache_get("key1")

        assert result is None

    def test_cache_delete_nonexistent_no_error(self):
        """Test delete on nonexistent key doesn't raise."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        # Should not raise
        cache.cache_delete("nonexistent")

    def test_cache_clear_removes_all(self):
        """Test clear removes all entries."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")
        cache.cache_clear()

        assert cache.cache_get("key1") is None
        assert cache.cache_get("key2") is None
        assert cache.cache_get("key3") is None

    def test_cache_stores_various_types(self):
        """Test cache stores different value types."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        # String
        cache.cache_set("str_key", "string_value")
        assert cache.cache_get("str_key") == "string_value"

        # Integer
        cache.cache_set("int_key", 42)
        assert cache.cache_get("int_key") == 42

        # Float
        cache.cache_set("float_key", 3.14)
        assert cache.cache_get("float_key") == 3.14

        # List
        cache.cache_set("list_key", [1, 2, 3])
        assert cache.cache_get("list_key") == [1, 2, 3]

        # Dict
        cache.cache_set("dict_key", {"a": 1, "b": 2})
        assert cache.cache_get("dict_key") == {"a": 1, "b": 2}

        # Boolean
        cache.cache_set("bool_key", True)
        assert cache.cache_get("bool_key") is True

        # None
        cache.cache_set("none_key", None)
        # Note: None is stored, should be distinguishable from missing
        assert "none_key" in cache._memory_cache


class TestCacheTTL:
    """Test TTL (time-to-live) functionality."""

    def test_cache_set_with_ttl(self):
        """Test set with TTL stores correctly."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1", ttl_seconds=3600)
        result = cache.cache_get("key1")

        assert result == "value1"

    def test_cache_entry_expires_after_ttl(self):
        """Test entry expires after TTL."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        # Set with very short TTL
        cache.cache_set("key1", "value1", ttl_seconds=0.1)

        # Should be available immediately
        assert cache.cache_get("key1") == "value1"

        # Wait for expiration
        time.sleep(0.15)

        # Should be gone
        assert cache.cache_get("key1") is None

    def test_cache_expired_entry_returns_default(self):
        """Test expired entry returns default."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1", ttl_seconds=0.1)
        time.sleep(0.15)

        result = cache.cache_get("key1", default="expired")

        assert result == "expired"

    def test_cache_default_ttl(self):
        """Test default TTL is applied."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, default_ttl=3600)

        cache.cache_set("key1", "value1")  # No explicit TTL

        # Entry should have TTL metadata
        entry = cache._memory_cache.get("key1")
        assert entry is not None
        assert "expires_at" in entry

    def test_cache_auto_evicts_expired_on_cleanup(self):
        """Test auto-eviction of expired entries."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1", ttl_seconds=0.1)
        cache.cache_set("key2", "value2", ttl_seconds=3600)

        time.sleep(0.15)

        # Trigger cleanup
        cache._cleanup_expired()

        # Expired entry should be gone
        assert "key1" not in cache._memory_cache
        # Valid entry should remain
        assert "key2" in cache._memory_cache


class TestCacheLRUEviction:
    """Test LRU eviction when max entries reached."""

    def test_cache_max_entries_evicts_oldest(self):
        """Test LRU eviction when max entries reached."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, max_entries=3)

        # Add 3 entries
        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")

        # Add 4th entry - should evict key1 (oldest)
        cache.cache_set("key4", "value4")

        assert cache.cache_get("key1") is None  # Evicted
        assert cache.cache_get("key2") == "value2"
        assert cache.cache_get("key3") == "value3"
        assert cache.cache_get("key4") == "value4"

    def test_cache_access_updates_lru_order(self):
        """Test accessing an entry updates its LRU position."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, max_entries=3)

        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")

        # Access key1 to make it recently used
        cache.cache_get("key1")

        # Add new entry - should evict key2 (now oldest)
        cache.cache_set("key4", "value4")

        assert cache.cache_get("key1") == "value1"  # Still present
        assert cache.cache_get("key2") is None  # Evicted
        assert cache.cache_get("key3") == "value3"
        assert cache.cache_get("key4") == "value4"

    def test_cache_update_updates_lru_order(self):
        """Test updating an entry updates its LRU position."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, max_entries=3)

        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")

        # Update key1 to make it recently used
        cache.cache_set("key1", "value1_updated")

        # Add new entry - should evict key2 (now oldest)
        cache.cache_set("key4", "value4")

        assert cache.cache_get("key1") == "value1_updated"  # Still present
        assert cache.cache_get("key2") is None  # Evicted


class TestCacheFilePersistence:
    """Test file-based persistence."""

    def test_cache_persists_to_file(self):
        """Test cache persists to file."""
        from bots.shared.cache import Cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "cache.json")

            cache = Cache(persistence_path=cache_file)
            cache.cache_set("key1", "value1")
            cache.cache_set("key2", "value2")

            # Force persistence
            cache._persist()

            # Verify file exists and has content
            assert os.path.exists(cache_file)
            with open(cache_file) as f:
                data = json.load(f)
            assert "key1" in data
            assert "key2" in data

    def test_cache_loads_from_file_on_init(self):
        """Test cache loads from existing file on init."""
        from bots.shared.cache import Cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "cache.json")

            # Create initial cache and persist
            cache1 = Cache(persistence_path=cache_file)
            cache1.cache_set("key1", "value1")
            cache1._persist()

            # Create new cache instance - should load from file
            cache2 = Cache(persistence_path=cache_file)

            assert cache2.cache_get("key1") == "value1"

    def test_cache_handles_missing_file(self):
        """Test cache handles missing persistence file gracefully."""
        from bots.shared.cache import Cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "nonexistent", "cache.json")

            # Should not raise
            cache = Cache(persistence_path=cache_file)

            # Should work normally
            cache.cache_set("key1", "value1")
            assert cache.cache_get("key1") == "value1"

    def test_cache_handles_corrupted_file(self):
        """Test cache handles corrupted persistence file gracefully."""
        from bots.shared.cache import Cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "cache.json")

            # Write corrupted JSON
            with open(cache_file, "w") as f:
                f.write("not valid json {{{")

            # Should not raise, should start with empty cache
            cache = Cache(persistence_path=cache_file)

            # Should work normally
            cache.cache_set("key1", "value1")
            assert cache.cache_get("key1") == "value1"

    def test_cache_doesnt_persist_expired(self):
        """Test expired entries are not persisted."""
        from bots.shared.cache import Cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "cache.json")

            cache = Cache(persistence_path=cache_file)
            cache.cache_set("expired_key", "expired_value", ttl_seconds=0.1)
            cache.cache_set("valid_key", "valid_value", ttl_seconds=3600)

            time.sleep(0.15)

            # Force persistence
            cache._persist()

            # Load file and check
            with open(cache_file) as f:
                data = json.load(f)

            assert "expired_key" not in data
            assert "valid_key" in data


class TestCacheStats:
    """Test cache statistics."""

    def test_cache_stats_initial(self):
        """Test initial stats are zero."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        stats = cache.cache_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["entries"] == 0
        assert stats["size_bytes"] >= 0

    def test_cache_stats_tracks_hits(self):
        """Test stats track cache hits."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_get("key1")
        cache.cache_get("key1")
        cache.cache_get("key1")

        stats = cache.cache_stats()

        assert stats["hits"] == 3
        assert stats["misses"] == 0

    def test_cache_stats_tracks_misses(self):
        """Test stats track cache misses."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_get("nonexistent1")
        cache.cache_get("nonexistent2")

        stats = cache.cache_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 2

    def test_cache_stats_calculates_hit_rate(self):
        """Test stats calculate hit rate correctly."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_get("key1")  # Hit
        cache.cache_get("key1")  # Hit
        cache.cache_get("nonexistent")  # Miss
        cache.cache_get("key1")  # Hit

        stats = cache.cache_stats()

        # 3 hits, 1 miss = 75% hit rate
        assert stats["hits"] == 3
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.75

    def test_cache_stats_tracks_entries(self):
        """Test stats track entry count."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")

        stats = cache.cache_stats()

        assert stats["entries"] == 3

    def test_cache_stats_estimates_size(self):
        """Test stats estimate cache size."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("key1", "a" * 1000)  # 1KB string
        cache.cache_set("key2", "b" * 1000)  # 1KB string

        stats = cache.cache_stats()

        # Size should be at least 2000 bytes
        assert stats["size_bytes"] >= 2000


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_module_cache_get_set(self):
        """Test module-level cache_get and cache_set."""
        from bots.shared.cache import cache_clear, cache_get, cache_set

        cache_clear()  # Start fresh

        cache_set("module_key", "module_value")
        result = cache_get("module_key")

        assert result == "module_value"

        cache_clear()  # Cleanup

    def test_module_cache_delete(self):
        """Test module-level cache_delete."""
        from bots.shared.cache import cache_clear, cache_delete, cache_get, cache_set

        cache_clear()

        cache_set("del_key", "del_value")
        cache_delete("del_key")
        result = cache_get("del_key")

        assert result is None

        cache_clear()

    def test_module_cache_stats(self):
        """Test module-level cache_stats."""
        from bots.shared.cache import cache_clear, cache_get, cache_set, cache_stats

        cache_clear()

        cache_set("stats_key", "stats_value")
        cache_get("stats_key")
        cache_get("nonexistent")

        stats = cache_stats()

        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert "hit_rate" in stats
        assert "entries" in stats
        assert "size_bytes" in stats

        cache_clear()


class TestCacheThreadSafety:
    """Test thread safety of cache operations."""

    def test_concurrent_access(self):
        """Test cache handles concurrent access."""
        import threading

        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, max_entries=100)
        errors = []

        def writer(thread_id):
            try:
                for i in range(100):
                    cache.cache_set(f"key_{thread_id}_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader(thread_id):
            try:
                for i in range(100):
                    cache.cache_get(f"key_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"


class TestCacheDecorator:
    """Test caching decorator for functions."""

    def test_cached_decorator_caches_result(self):
        """Test @cached decorator caches function results."""
        from bots.shared.cache import Cache, cached

        cache = Cache(persistence_path=None)
        call_count = 0

        @cached(cache=cache, ttl_seconds=3600)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # First call - should execute function
        result1 = expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = expensive_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # Not incremented

        # Different args - should execute function
        result3 = expensive_function(3, 4)
        assert result3 == 7
        assert call_count == 2

    def test_cached_decorator_with_key_prefix(self):
        """Test @cached decorator with custom key prefix."""
        from bots.shared.cache import Cache, cached

        cache = Cache(persistence_path=None)

        @cached(cache=cache, key_prefix="my_func")
        def my_function(x):
            return x * 2

        my_function(5)

        # Check key format
        keys = list(cache._memory_cache.keys())
        assert any("my_func" in k for k in keys)
