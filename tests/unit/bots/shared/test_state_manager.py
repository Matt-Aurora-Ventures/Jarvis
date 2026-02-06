"""
Tests for bots/shared/state_manager.py

State management system for ClawdBots with:
- Persistent state storage per bot
- Atomic state updates with file locking
- State snapshots and rollback capability
- State change history tracking
- Concurrent access safety

Tests cover:
- StateManager initialization and defaults
- get_state/set_state basic operations
- get_full_state for complete bot state
- Atomic updates (concurrent safety)
- Snapshot creation and management
- Snapshot restoration (rollback)
- State history tracking
- Concurrent access with file locking
- Snapshot cleanup (keep last 10)
"""

import json
import os
import sys
import tempfile
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.state_manager import (
    StateManager,
    StateError,
    StateChange,
)


class TestStateManagerInitialization:
    """Test StateManager initialization."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create temporary state directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_init_creates_state_dir(self, temp_state_dir):
        """Should create state directory on initialization."""
        state_dir = os.path.join(temp_state_dir, "state")
        manager = StateManager(bot_name="jarvis", state_dir=state_dir)
        assert os.path.exists(state_dir)

    def test_init_creates_snapshots_dir(self, temp_state_dir):
        """Should create snapshots subdirectory."""
        state_dir = os.path.join(temp_state_dir, "state")
        manager = StateManager(bot_name="jarvis", state_dir=state_dir)
        snapshots_dir = os.path.join(state_dir, "snapshots")
        assert os.path.exists(snapshots_dir)

    def test_init_creates_empty_state_file(self, temp_state_dir):
        """Should create empty state file for bot."""
        manager = StateManager(bot_name="jarvis", state_dir=temp_state_dir)
        state_file = os.path.join(temp_state_dir, "jarvis.json")
        assert os.path.exists(state_file)

    def test_init_loads_existing_state(self, temp_state_dir):
        """Should load existing state file on init."""
        # Pre-create state file
        state_file = os.path.join(temp_state_dir, "jarvis.json")
        existing_state = {"counter": 42, "name": "test"}
        with open(state_file, "w") as f:
            json.dump({"state": existing_state, "history": [], "metadata": {}}, f)

        manager = StateManager(bot_name="jarvis", state_dir=temp_state_dir)
        assert manager.get_state("jarvis", "counter") == 42

    def test_init_with_invalid_bot_name_raises(self, temp_state_dir):
        """Should raise error for invalid bot name."""
        with pytest.raises(StateError):
            StateManager(bot_name="", state_dir=temp_state_dir)

    def test_init_with_path_traversal_raises(self, temp_state_dir):
        """Should raise error for path traversal attempt."""
        with pytest.raises(StateError):
            StateManager(bot_name="../etc/passwd", state_dir=temp_state_dir)


class TestGetState:
    """Test get_state method."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_get_state_returns_value(self, manager):
        """Should return stored value."""
        manager.set_state("jarvis", "counter", 10)
        assert manager.get_state("jarvis", "counter") == 10

    def test_get_state_returns_none_for_missing_key(self, manager):
        """Should return None for missing key."""
        assert manager.get_state("jarvis", "nonexistent") is None

    def test_get_state_with_default(self, manager):
        """Should return default for missing key."""
        assert manager.get_state("jarvis", "nonexistent", default=100) == 100

    def test_get_state_different_types(self, manager):
        """Should handle different value types."""
        manager.set_state("jarvis", "string_val", "hello")
        manager.set_state("jarvis", "int_val", 42)
        manager.set_state("jarvis", "float_val", 3.14)
        manager.set_state("jarvis", "list_val", [1, 2, 3])
        manager.set_state("jarvis", "dict_val", {"nested": "value"})
        manager.set_state("jarvis", "bool_val", True)

        assert manager.get_state("jarvis", "string_val") == "hello"
        assert manager.get_state("jarvis", "int_val") == 42
        assert manager.get_state("jarvis", "float_val") == 3.14
        assert manager.get_state("jarvis", "list_val") == [1, 2, 3]
        assert manager.get_state("jarvis", "dict_val") == {"nested": "value"}
        assert manager.get_state("jarvis", "bool_val") is True

    def test_get_state_cross_bot(self):
        """Should access state from different bots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two managers for different bots
            jarvis = StateManager(bot_name="jarvis", state_dir=tmpdir)
            matt = StateManager(bot_name="matt", state_dir=tmpdir)

            jarvis.set_state("jarvis", "role", "CTO")
            matt.set_state("matt", "role", "COO")

            # Each can read their own state
            assert jarvis.get_state("jarvis", "role") == "CTO"
            assert matt.get_state("matt", "role") == "COO"

            # Can also read other bot's state
            assert jarvis.get_state("matt", "role") == "COO"


class TestSetState:
    """Test set_state method."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_set_state_returns_true(self, manager):
        """Should return True on success."""
        result = manager.set_state("jarvis", "key", "value")
        assert result is True

    def test_set_state_persists(self, manager):
        """Should persist state to disk."""
        manager.set_state("jarvis", "persistent", "value")

        # Re-read from disk
        state_file = manager._get_state_file("jarvis")
        with open(state_file, "r") as f:
            data = json.load(f)
        assert data["state"]["persistent"] == "value"

    def test_set_state_overwrites_existing(self, manager):
        """Should overwrite existing key."""
        manager.set_state("jarvis", "key", "first")
        manager.set_state("jarvis", "key", "second")
        assert manager.get_state("jarvis", "key") == "second"

    def test_set_state_records_history(self, manager):
        """Should record change in history."""
        manager.set_state("jarvis", "tracked", "value1")
        manager.set_state("jarvis", "tracked", "value2")

        history = manager.get_state_history("jarvis", "tracked")
        assert len(history) >= 2
        # Most recent change should be "value2"
        assert history[-1].new_value == "value2"
        assert history[-1].old_value == "value1"

    def test_set_state_with_metadata(self, manager):
        """Should store metadata with state change."""
        manager.set_state(
            "jarvis",
            "with_meta",
            "value",
            metadata={"source": "test", "reason": "testing"}
        )
        history = manager.get_state_history("jarvis", "with_meta")
        assert history[-1].metadata["source"] == "test"


class TestGetFullState:
    """Test get_full_state method."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_get_full_state_returns_dict(self, manager):
        """Should return dictionary of all state."""
        manager.set_state("jarvis", "key1", "value1")
        manager.set_state("jarvis", "key2", "value2")

        full_state = manager.get_full_state("jarvis")
        assert isinstance(full_state, dict)
        assert full_state["key1"] == "value1"
        assert full_state["key2"] == "value2"

    def test_get_full_state_returns_copy(self, manager):
        """Should return a copy, not the internal state."""
        manager.set_state("jarvis", "key", "original")
        full_state = manager.get_full_state("jarvis")
        full_state["key"] = "modified"

        # Original should not be affected
        assert manager.get_state("jarvis", "key") == "original"

    def test_get_full_state_empty_bot(self, manager):
        """Should return empty dict for bot with no state."""
        full_state = manager.get_full_state("jarvis")
        assert full_state == {}


class TestSnapshots:
    """Test snapshot creation and management."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_save_snapshot_returns_id(self, manager):
        """Should return snapshot ID."""
        manager.set_state("jarvis", "key", "value")
        snapshot_id = manager.save_snapshot("jarvis")
        assert snapshot_id is not None
        assert isinstance(snapshot_id, str)
        assert len(snapshot_id) > 0

    def test_save_snapshot_creates_file(self, manager):
        """Should create snapshot file on disk."""
        manager.set_state("jarvis", "key", "value")
        snapshot_id = manager.save_snapshot("jarvis")

        # Check snapshot file exists
        snapshots_dir = os.path.join(manager._state_dir, "snapshots")
        snapshot_files = [f for f in os.listdir(snapshots_dir) if f.startswith("jarvis_")]
        assert len(snapshot_files) == 1

    def test_save_snapshot_preserves_state(self, manager):
        """Should preserve complete state in snapshot."""
        manager.set_state("jarvis", "key1", "value1")
        manager.set_state("jarvis", "key2", {"nested": "data"})
        snapshot_id = manager.save_snapshot("jarvis")

        # Verify snapshot contents
        snapshots_dir = os.path.join(manager._state_dir, "snapshots")
        snapshot_file = [
            f for f in os.listdir(snapshots_dir)
            if f.startswith("jarvis_")
        ][0]
        with open(os.path.join(snapshots_dir, snapshot_file), "r") as f:
            snapshot_data = json.load(f)

        assert snapshot_data["state"]["key1"] == "value1"
        assert snapshot_data["state"]["key2"]["nested"] == "data"

    def test_list_snapshots(self, manager):
        """Should list all snapshots for a bot."""
        manager.set_state("jarvis", "key", "v1")
        snap1 = manager.save_snapshot("jarvis")

        manager.set_state("jarvis", "key", "v2")
        snap2 = manager.save_snapshot("jarvis")

        snapshots = manager.list_snapshots("jarvis")
        assert len(snapshots) == 2
        assert snap1 in [s["id"] for s in snapshots]
        assert snap2 in [s["id"] for s in snapshots]


class TestRestoreSnapshot:
    """Test snapshot restoration."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_restore_snapshot_basic(self, manager):
        """Should restore state from snapshot."""
        # Set initial state
        manager.set_state("jarvis", "key", "original")
        snapshot_id = manager.save_snapshot("jarvis")

        # Modify state
        manager.set_state("jarvis", "key", "modified")
        assert manager.get_state("jarvis", "key") == "modified"

        # Restore
        result = manager.restore_snapshot("jarvis", snapshot_id)
        assert result is True
        assert manager.get_state("jarvis", "key") == "original"

    def test_restore_snapshot_invalid_id(self, manager):
        """Should raise error for invalid snapshot ID."""
        with pytest.raises(StateError):
            manager.restore_snapshot("jarvis", "nonexistent_snapshot_123")

    def test_restore_snapshot_creates_backup(self, manager):
        """Should create backup snapshot before restore."""
        manager.set_state("jarvis", "key", "original")
        snapshot_id = manager.save_snapshot("jarvis")

        manager.set_state("jarvis", "key", "modified")
        manager.restore_snapshot("jarvis", snapshot_id)

        # Should have 2 snapshots now (original + pre-restore backup)
        snapshots = manager.list_snapshots("jarvis")
        assert len(snapshots) >= 2

    def test_restore_complex_state(self, manager):
        """Should restore complex nested state."""
        complex_state = {
            "config": {"api_key": "secret", "timeout": 30},
            "counters": [1, 2, 3],
            "active": True,
        }
        manager.set_state("jarvis", "complex", complex_state)
        snapshot_id = manager.save_snapshot("jarvis")

        # Modify
        manager.set_state("jarvis", "complex", {"replaced": True})

        # Restore
        manager.restore_snapshot("jarvis", snapshot_id)
        restored = manager.get_state("jarvis", "complex")
        assert restored == complex_state


class TestStateHistory:
    """Test state history tracking."""

    @pytest.fixture
    def manager(self):
        """Create StateManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield StateManager(bot_name="jarvis", state_dir=tmpdir)

    def test_get_state_history_returns_list(self, manager):
        """Should return list of StateChange objects."""
        manager.set_state("jarvis", "key", "value")
        history = manager.get_state_history("jarvis", "key")
        assert isinstance(history, list)
        assert len(history) >= 1

    def test_state_change_has_required_fields(self, manager):
        """StateChange should have timestamp, old_value, new_value."""
        manager.set_state("jarvis", "key", "value")
        history = manager.get_state_history("jarvis", "key")

        change = history[0]
        assert hasattr(change, "timestamp")
        assert hasattr(change, "old_value")
        assert hasattr(change, "new_value")
        assert hasattr(change, "key")

    def test_history_tracks_changes_in_order(self, manager):
        """Should track all changes in chronological order."""
        manager.set_state("jarvis", "counter", 1)
        manager.set_state("jarvis", "counter", 2)
        manager.set_state("jarvis", "counter", 3)

        history = manager.get_state_history("jarvis", "counter")
        assert len(history) == 3
        # Verify order (oldest first)
        assert history[0].new_value == 1
        assert history[1].new_value == 2
        assert history[2].new_value == 3

    def test_history_for_nonexistent_key(self, manager):
        """Should return empty list for key with no history."""
        history = manager.get_state_history("jarvis", "nonexistent")
        assert history == []

    def test_history_limit(self, manager):
        """Should limit history to configured max entries."""
        # Set many values
        for i in range(100):
            manager.set_state("jarvis", "key", i)

        history = manager.get_state_history("jarvis", "key")
        # Default limit should prevent unbounded growth
        assert len(history) <= 50  # Assuming 50 as reasonable limit


class TestConcurrentAccess:
    """Test concurrent access safety."""

    def test_concurrent_writes(self):
        """Should handle concurrent writes safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)

            results = []
            errors = []

            def writer(value):
                try:
                    for _ in range(10):
                        manager.set_state("jarvis", "counter", value)
                        time.sleep(0.01)
                    results.append(True)
                except Exception as e:
                    errors.append(str(e))

            # Launch concurrent writers
            threads = [
                threading.Thread(target=writer, args=(i,))
                for i in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All writes should succeed
            assert len(errors) == 0
            assert len(results) == 5

            # State should be valid (any of the written values)
            final_value = manager.get_state("jarvis", "counter")
            assert final_value in range(5)

    def test_concurrent_read_write(self):
        """Should handle concurrent reads and writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)
            manager.set_state("jarvis", "value", 0)

            read_results = []
            write_errors = []

            def reader():
                for _ in range(20):
                    val = manager.get_state("jarvis", "value")
                    read_results.append(val)
                    time.sleep(0.005)

            def writer():
                try:
                    for i in range(20):
                        manager.set_state("jarvis", "value", i)
                        time.sleep(0.005)
                except Exception as e:
                    write_errors.append(str(e))

            # Launch concurrent operations
            t_reader = threading.Thread(target=reader)
            t_writer = threading.Thread(target=writer)

            t_reader.start()
            t_writer.start()

            t_reader.join()
            t_writer.join()

            # No errors should occur
            assert len(write_errors) == 0
            # All reads should return valid values
            assert all(v is not None and isinstance(v, int) for v in read_results)


class TestSnapshotCleanup:
    """Test snapshot cleanup (keep last N)."""

    def test_cleanup_keeps_last_10(self):
        """Should keep only last 10 snapshots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir, max_snapshots=10)

            # Create 15 snapshots
            for i in range(15):
                manager.set_state("jarvis", "version", i)
                manager.save_snapshot("jarvis")

            # Should only have 10 snapshots
            snapshots = manager.list_snapshots("jarvis")
            assert len(snapshots) == 10

    def test_cleanup_keeps_most_recent(self):
        """Should keep the most recent snapshots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir, max_snapshots=3)

            # Create snapshots with identifiable values
            for i in range(5):
                manager.set_state("jarvis", "marker", f"snapshot_{i}")
                manager.save_snapshot("jarvis")
                time.sleep(0.01)  # Ensure different timestamps

            snapshots = manager.list_snapshots("jarvis")
            assert len(snapshots) == 3

            # Most recent should be preserved (snapshot_4, snapshot_3, snapshot_2)
            # Oldest (snapshot_0, snapshot_1) should be deleted
            snapshot_markers = []
            for snap in snapshots:
                snapshot_file = manager._get_snapshot_file(snap["id"])
                with open(snapshot_file, "r") as f:
                    data = json.load(f)
                    snapshot_markers.append(data["state"].get("marker"))

            assert "snapshot_4" in snapshot_markers
            assert "snapshot_3" in snapshot_markers
            assert "snapshot_2" in snapshot_markers


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_json_recovery(self):
        """Should recover from corrupted state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "jarvis.json")
            with open(state_file, "w") as f:
                f.write("invalid json {{{")

            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)
            # Should initialize with empty state
            assert manager.get_full_state("jarvis") == {}

    def test_delete_state_key(self):
        """Should support deleting a state key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)
            manager.set_state("jarvis", "to_delete", "value")
            assert manager.get_state("jarvis", "to_delete") == "value"

            manager.delete_state("jarvis", "to_delete")
            assert manager.get_state("jarvis", "to_delete") is None

    def test_special_characters_in_key(self):
        """Should handle special characters in keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)

            manager.set_state("jarvis", "key.with.dots", "value1")
            manager.set_state("jarvis", "key/with/slashes", "value2")
            manager.set_state("jarvis", "key with spaces", "value3")

            assert manager.get_state("jarvis", "key.with.dots") == "value1"
            assert manager.get_state("jarvis", "key/with/slashes") == "value2"
            assert manager.get_state("jarvis", "key with spaces") == "value3"

    def test_unicode_values(self):
        """Should handle unicode values correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)

            manager.set_state("jarvis", "emoji", "test 123")
            manager.set_state("jarvis", "chinese", "test")
            manager.set_state("jarvis", "arabic", "test")

            assert manager.get_state("jarvis", "emoji") == "test 123"
            assert manager.get_state("jarvis", "chinese") == "test"
            assert manager.get_state("jarvis", "arabic") == "test"

    def test_large_state_value(self):
        """Should handle large state values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(bot_name="jarvis", state_dir=tmpdir)

            large_value = "x" * 100000  # 100KB string
            manager.set_state("jarvis", "large", large_value)
            assert manager.get_state("jarvis", "large") == large_value
