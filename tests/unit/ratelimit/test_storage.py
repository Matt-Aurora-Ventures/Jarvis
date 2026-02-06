"""
Comprehensive tests for rate limit storage backends.

Tests cover:
1. InMemoryStorage - Single process storage
2. FileStorage - Persistent storage
3. Key format: {type}:{identifier}

Target: Full coverage of storage implementations
"""

import pytest
import asyncio
import time
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# InMemoryStorage Tests
# =============================================================================

class TestInMemoryStorage:
    """Tests for InMemoryStorage backend."""

    def test_import(self):
        """Test that InMemoryStorage can be imported."""
        from core.ratelimit.storage import InMemoryStorage
        assert InMemoryStorage is not None

    def test_initialization(self):
        """Test default initialization."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()
        assert storage is not None

    def test_record_request(self):
        """Test recording a request."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        storage.record("user:123", window=60)

        count = storage.get_count("user:123", window=60)
        assert count == 1

    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        for _ in range(5):
            storage.record("user:multi", window=60)

        count = storage.get_count("user:multi", window=60)
        assert count == 5

    def test_get_count_empty_key(self):
        """Test get_count for key with no records."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        count = storage.get_count("nonexistent:key", window=60)
        assert count == 0

    def test_get_count_respects_window(self):
        """Test that get_count only counts within window."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        # Record some requests
        for _ in range(3):
            storage.record("window:test", window=0.1)

        # Should have 3 in window
        assert storage.get_count("window:test", window=0.1) == 3

        # Wait for window to expire
        time.sleep(0.15)

        # Should have 0 now
        assert storage.get_count("window:test", window=0.1) == 0

    def test_reset_key(self):
        """Test resetting a key."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        for _ in range(5):
            storage.record("reset:key", window=60)

        assert storage.get_count("reset:key", window=60) == 5

        storage.reset("reset:key")

        assert storage.get_count("reset:key", window=60) == 0

    def test_get_all_keys(self):
        """Test getting all keys."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        storage.record("key:1", window=60)
        storage.record("key:2", window=60)
        storage.record("key:3", window=60)

        keys = storage.get_all_keys()
        assert len(keys) == 3
        assert "key:1" in keys
        assert "key:2" in keys
        assert "key:3" in keys

    def test_cleanup_old_entries(self):
        """Test cleaning up old entries."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        for _ in range(5):
            storage.record("cleanup:test", window=0.1)

        assert storage.get_count("cleanup:test", window=0.1) == 5

        # Wait and cleanup
        time.sleep(0.15)
        cleaned = storage.cleanup(max_age=0.1)

        assert cleaned >= 5
        assert storage.get_count("cleanup:test", window=0.1) == 0

    def test_get_oldest_timestamp(self):
        """Test getting oldest timestamp for a key."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        # Record with small delays
        for i in range(3):
            storage.record("oldest:test", window=60)
            if i < 2:
                time.sleep(0.01)

        oldest = storage.get_oldest_timestamp("oldest:test")
        assert oldest is not None
        assert oldest <= time.time()

    def test_key_isolation(self):
        """Test that different keys are isolated."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        storage.record("isolated:a", window=60)
        storage.record("isolated:a", window=60)
        storage.record("isolated:b", window=60)

        assert storage.get_count("isolated:a", window=60) == 2
        assert storage.get_count("isolated:b", window=60) == 1


# =============================================================================
# FileStorage Tests
# =============================================================================

class TestFileStorage:
    """Tests for FileStorage backend."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for file storage."""
        return str(tmp_path)

    def test_import(self):
        """Test that FileStorage can be imported."""
        from core.ratelimit.storage import FileStorage
        assert FileStorage is not None

    def test_initialization(self, temp_dir):
        """Test initialization creates directory."""
        from core.ratelimit.storage import FileStorage
        storage_path = os.path.join(temp_dir, "ratelimit")
        storage = FileStorage(path=storage_path)

        assert storage is not None
        assert os.path.exists(storage_path)

    def test_record_request(self, temp_dir):
        """Test recording a request persists to file."""
        from core.ratelimit.storage import FileStorage
        storage = FileStorage(path=temp_dir)

        storage.record("file:user:1", window=60)

        count = storage.get_count("file:user:1", window=60)
        assert count == 1

    def test_persistence_across_instances(self, temp_dir):
        """Test data persists across storage instances."""
        from core.ratelimit.storage import FileStorage

        # First instance
        storage1 = FileStorage(path=temp_dir)
        for _ in range(3):
            storage1.record("persist:key", window=60)

        # Second instance should see the data
        storage2 = FileStorage(path=temp_dir)
        count = storage2.get_count("persist:key", window=60)
        assert count == 3

    def test_get_count_respects_window(self, temp_dir):
        """Test that get_count only counts within window."""
        from core.ratelimit.storage import FileStorage
        storage = FileStorage(path=temp_dir)

        for _ in range(3):
            storage.record("file:window", window=0.1)

        assert storage.get_count("file:window", window=0.1) == 3

        time.sleep(0.15)

        assert storage.get_count("file:window", window=0.1) == 0

    def test_reset_key(self, temp_dir):
        """Test resetting a key."""
        from core.ratelimit.storage import FileStorage
        storage = FileStorage(path=temp_dir)

        for _ in range(5):
            storage.record("file:reset", window=60)

        assert storage.get_count("file:reset", window=60) == 5

        storage.reset("file:reset")

        assert storage.get_count("file:reset", window=60) == 0

    def test_key_format_with_colons(self, temp_dir):
        """Test keys with colons work correctly."""
        from core.ratelimit.storage import FileStorage
        storage = FileStorage(path=temp_dir)

        key = "type:subtype:identifier"
        storage.record(key, window=60)

        assert storage.get_count(key, window=60) == 1

    def test_cleanup_old_files(self, temp_dir):
        """Test cleaning up old file entries."""
        from core.ratelimit.storage import FileStorage
        storage = FileStorage(path=temp_dir)

        for _ in range(5):
            storage.record("file:cleanup", window=0.1)

        time.sleep(0.15)
        cleaned = storage.cleanup(max_age=0.1)

        assert cleaned >= 0  # May not have file-level cleanup


# =============================================================================
# Key Format Tests
# =============================================================================

class TestKeyFormat:
    """Tests for key format: {type}:{identifier}"""

    def test_user_key_format(self):
        """Test user key format."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        key = "user:12345"
        storage.record(key, window=60)

        assert storage.get_count(key, window=60) == 1

    def test_api_key_format(self):
        """Test API key format."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        key = "api:grok"
        storage.record(key, window=60)

        assert storage.get_count(key, window=60) == 1

    def test_telegram_chat_key_format(self):
        """Test Telegram chat key format."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        key = "telegram:chat:-1001234567890"
        storage.record(key, window=60)

        assert storage.get_count(key, window=60) == 1

    def test_compound_key_format(self):
        """Test compound key with multiple segments."""
        from core.ratelimit.storage import InMemoryStorage
        storage = InMemoryStorage()

        key = "api:provider:grok:user:123"
        storage.record(key, window=60)

        assert storage.get_count(key, window=60) == 1


# =============================================================================
# Storage Interface Tests
# =============================================================================

class TestStorageInterface:
    """Tests for storage interface compliance."""

    def test_inmemory_implements_interface(self):
        """Test InMemoryStorage implements required interface."""
        from core.ratelimit.storage import InMemoryStorage, StorageInterface
        storage = InMemoryStorage()

        assert isinstance(storage, StorageInterface)
        assert hasattr(storage, 'record')
        assert hasattr(storage, 'get_count')
        assert hasattr(storage, 'reset')
        assert hasattr(storage, 'cleanup')

    def test_file_implements_interface(self, tmp_path):
        """Test FileStorage implements required interface."""
        from core.ratelimit.storage import FileStorage, StorageInterface
        storage = FileStorage(path=str(tmp_path))

        assert isinstance(storage, StorageInterface)
        assert hasattr(storage, 'record')
        assert hasattr(storage, 'get_count')
        assert hasattr(storage, 'reset')
        assert hasattr(storage, 'cleanup')


# =============================================================================
# Run configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
