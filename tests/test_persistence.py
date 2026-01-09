"""
Tests for Persistence Layer.

Tests cover:
- JSONStore operations
- SQLiteStore operations
- PersistenceManager functionality
- Backup/restore operations
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.persistence.store import JSONStore, SQLiteStore, PersistenceStore
from lifeos.persistence.manager import PersistenceManager


# =============================================================================
# Test JSONStore
# =============================================================================

class TestJSONStore:
    """Test JSON file-based store."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create temporary JSON store."""
        store = JSONStore(base_path=tmp_path)
        yield store
        store.close()

    def test_set_and_get(self, store):
        """Should set and get values."""
        store.set("test", "key1", "value1")
        result = store.get("test", "key1")
        assert result == "value1"

    def test_get_nonexistent(self, store):
        """Should return None for nonexistent keys."""
        result = store.get("test", "nonexistent")
        assert result is None

    def test_set_complex_value(self, store):
        """Should handle complex values."""
        value = {
            "name": "test",
            "count": 42,
            "items": ["a", "b", "c"],
        }
        store.set("test", "complex", value)
        result = store.get("test", "complex")
        assert result == value

    def test_delete(self, store):
        """Should delete values."""
        store.set("test", "key1", "value1")
        deleted = store.delete("test", "key1")
        assert deleted is True
        assert store.get("test", "key1") is None

    def test_delete_nonexistent(self, store):
        """Should return False for nonexistent key."""
        deleted = store.delete("test", "nonexistent")
        assert deleted is False

    def test_list_keys(self, store):
        """Should list keys in namespace."""
        store.set("test", "key1", "value1")
        store.set("test", "key2", "value2")
        store.set("other", "key3", "value3")

        keys = store.list_keys("test")
        assert sorted(keys) == ["key1", "key2"]

    def test_list_namespaces(self, store):
        """Should list all namespaces."""
        store.set("ns1", "key", "value")
        store.set("ns2", "key", "value")

        namespaces = store.list_namespaces()
        assert "ns1" in namespaces
        assert "ns2" in namespaces

    def test_clear_namespace(self, store):
        """Should clear all keys in namespace."""
        store.set("test", "key1", "value1")
        store.set("test", "key2", "value2")

        count = store.clear_namespace("test")
        assert count == 2
        assert store.list_keys("test") == []

    def test_persistence(self, tmp_path):
        """Should persist data across instances."""
        # First instance
        store1 = JSONStore(base_path=tmp_path)
        store1.set("test", "key", "value")
        store1.close()

        # Second instance
        store2 = JSONStore(base_path=tmp_path)
        result = store2.get("test", "key")
        store2.close()

        assert result == "value"


# =============================================================================
# Test SQLiteStore
# =============================================================================

class TestSQLiteStore:
    """Test SQLite database store."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create temporary SQLite store."""
        db_path = tmp_path / "test.db"
        store = SQLiteStore(db_path=db_path)
        yield store
        store.close()

    def test_set_and_get(self, store):
        """Should set and get values."""
        store.set("test", "key1", "value1")
        result = store.get("test", "key1")
        assert result == "value1"

    def test_get_nonexistent(self, store):
        """Should return None for nonexistent keys."""
        result = store.get("test", "nonexistent")
        assert result is None

    def test_set_complex_value(self, store):
        """Should handle complex values."""
        value = {
            "name": "test",
            "count": 42,
            "items": ["a", "b", "c"],
        }
        store.set("test", "complex", value)
        result = store.get("test", "complex")
        assert result == value

    def test_update_value(self, store):
        """Should update existing values."""
        store.set("test", "key", "value1")
        store.set("test", "key", "value2")
        result = store.get("test", "key")
        assert result == "value2"

    def test_delete(self, store):
        """Should delete values."""
        store.set("test", "key1", "value1")
        deleted = store.delete("test", "key1")
        assert deleted is True
        assert store.get("test", "key1") is None

    def test_list_keys(self, store):
        """Should list keys in namespace."""
        store.set("test", "key1", "value1")
        store.set("test", "key2", "value2")
        store.set("other", "key3", "value3")

        keys = store.list_keys("test")
        assert sorted(keys) == ["key1", "key2"]

    def test_list_namespaces(self, store):
        """Should list all namespaces."""
        store.set("ns1", "key", "value")
        store.set("ns2", "key", "value")

        namespaces = store.list_namespaces()
        assert "ns1" in namespaces
        assert "ns2" in namespaces

    def test_clear_namespace(self, store):
        """Should clear all keys in namespace."""
        store.set("test", "key1", "value1")
        store.set("test", "key2", "value2")

        count = store.clear_namespace("test")
        assert count == 2
        assert store.list_keys("test") == []

    def test_persistence(self, tmp_path):
        """Should persist data across instances."""
        db_path = tmp_path / "persist.db"

        # First instance
        store1 = SQLiteStore(db_path=db_path)
        store1.set("test", "key", "value")
        store1.close()

        # Second instance
        store2 = SQLiteStore(db_path=db_path)
        result = store2.get("test", "key")
        store2.close()

        assert result == "value"


# =============================================================================
# Test PersistenceManager
# =============================================================================

class TestPersistenceManager:
    """Test persistence manager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create persistence manager with temporary store."""
        store = JSONStore(base_path=tmp_path)
        manager = PersistenceManager(store=store, auto_save_interval=0)
        yield manager

    def test_get_set(self, manager):
        """Should get and set values."""
        manager.set("test", "key", "value")
        result = manager.get("test", "key")
        assert result == "value"

    def test_get_with_default(self, manager):
        """Should return default for missing keys."""
        result = manager.get("test", "missing", default="default")
        assert result == "default"

    def test_delete(self, manager):
        """Should delete values."""
        manager.set("test", "key", "value")
        deleted = manager.delete("test", "key")
        assert deleted is True
        assert manager.get("test", "key") is None

    def test_list_keys(self, manager):
        """Should list keys."""
        manager.set("test", "key1", "value1")
        manager.set("test", "key2", "value2")

        keys = manager.list_keys("test")
        assert sorted(keys) == ["key1", "key2"]

    def test_list_namespaces(self, manager):
        """Should list namespaces."""
        manager.set("ns1", "key", "value")
        manager.set("ns2", "key", "value")

        namespaces = manager.list_namespaces()
        assert "ns1" in namespaces
        assert "ns2" in namespaces

    def test_clear_namespace(self, manager):
        """Should clear namespace."""
        manager.set("test", "key1", "value1")
        manager.set("test", "key2", "value2")

        count = manager.clear_namespace("test")
        assert count == 2

    # State Management

    def test_save_state(self, manager):
        """Should save state."""
        state = {"running": True, "uptime": 100}
        success = manager.save_state("jarvis", state)
        assert success is True

    def test_load_state(self, manager):
        """Should load state."""
        state = {"running": True, "uptime": 100}
        manager.save_state("jarvis", state)

        loaded = manager.load_state("jarvis")
        assert loaded["running"] is True
        assert loaded["uptime"] == 100
        assert "_saved_at" in loaded

    def test_list_states(self, manager):
        """Should list states."""
        manager.save_state("state1", {"a": 1})
        manager.save_state("state2", {"b": 2})

        states = manager.list_states()
        assert "state1" in states
        assert "state2" in states

    def test_delete_state(self, manager):
        """Should delete state."""
        manager.save_state("temp", {"x": 1})
        deleted = manager.delete_state("temp")
        assert deleted is True
        assert manager.load_state("temp") is None

    # Callbacks

    def test_on_change_callback(self, manager):
        """Should call callback on change."""
        changes = []

        def callback(ns, key, value):
            changes.append((ns, key, value))

        manager.on_change("test", callback)
        manager.set("test", "key", "value")

        assert len(changes) == 1
        assert changes[0] == ("test", "key", "value")

    def test_wildcard_callback(self, manager):
        """Should call wildcard callback."""
        changes = []

        def callback(ns, key, value):
            changes.append((ns, key, value))

        manager.on_change("*", callback)
        manager.set("ns1", "key1", "value1")
        manager.set("ns2", "key2", "value2")

        assert len(changes) == 2

    # Backup/Restore

    def test_create_backup(self, manager):
        """Should create backup."""
        manager.set("test", "key1", "value1")
        manager.set("test", "key2", "value2")

        backup_name = manager.create_backup("test_backup")
        assert backup_name == "test_backup"

    def test_list_backups(self, manager):
        """Should list backups."""
        manager.create_backup("backup1")
        manager.create_backup("backup2")

        backups = manager.list_backups()
        names = [b["name"] for b in backups]
        assert "backup1" in names
        assert "backup2" in names

    def test_restore_backup(self, manager):
        """Should restore from backup."""
        manager.set("test", "key", "original")
        manager.create_backup("snapshot")

        manager.set("test", "key", "modified")
        assert manager.get("test", "key") == "modified"

        success = manager.restore_backup("snapshot")
        assert success is True
        assert manager.get("test", "key") == "original"

    def test_delete_backup(self, manager):
        """Should delete backup."""
        manager.create_backup("temp_backup")
        deleted = manager.delete_backup("temp_backup")
        assert deleted is True

        backups = manager.list_backups()
        names = [b["name"] for b in backups]
        assert "temp_backup" not in names

    # Statistics

    def test_get_stats(self, manager):
        """Should return statistics."""
        manager.set("ns1", "key1", "value1")
        manager.set("ns2", "key2", "value2")
        manager.save_state("state1", {"x": 1})

        stats = manager.get_stats()
        assert stats["namespace_count"] >= 2
        assert stats["total_keys"] >= 2
        assert stats["state_count"] >= 1


# =============================================================================
# Test Async Operations
# =============================================================================

class TestPersistenceManagerAsync:
    """Test async operations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create persistence manager."""
        store = JSONStore(base_path=tmp_path)
        return PersistenceManager(store=store, auto_save_interval=0.1)

    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """Should start and stop cleanly."""
        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_flush(self, manager):
        """Should flush dirty namespaces."""
        await manager.start()

        manager.set("test", "key", "value")
        manager._dirty_namespaces.add("test")

        count = await manager.flush()
        assert count >= 0

        await manager.stop()

    @pytest.mark.asyncio
    async def test_auto_save_disabled(self, tmp_path):
        """Should work without auto-save."""
        store = JSONStore(base_path=tmp_path)
        manager = PersistenceManager(store=store, auto_save_interval=0)

        await manager.start()
        assert manager._auto_save_task is None

        await manager.stop()
