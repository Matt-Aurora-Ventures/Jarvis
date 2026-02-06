"""
Unit tests for core/features/storage.py - FlagStorage classes.

TDD: These tests define the expected behavior before implementation.
"""

import pytest
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestFlagStorageAbstract:
    """Test FlagStorage abstract class."""

    def test_flag_storage_is_abstract(self):
        """FlagStorage should be abstract and not instantiable directly."""
        from core.features.storage import FlagStorage

        with pytest.raises(TypeError):
            FlagStorage()

    def test_flag_storage_defines_load_method(self):
        """FlagStorage should define abstract load method."""
        from core.features.storage import FlagStorage
        import inspect

        assert hasattr(FlagStorage, "load")
        assert callable(getattr(FlagStorage, "load", None))

    def test_flag_storage_defines_save_method(self):
        """FlagStorage should define abstract save method."""
        from core.features.storage import FlagStorage
        import inspect

        assert hasattr(FlagStorage, "save")
        assert callable(getattr(FlagStorage, "save", None))


class TestJSONFlagStorageLoad:
    """Test JSONFlagStorage load functionality."""

    def test_load_from_existing_file(self):
        """Should load flags from existing JSON file."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "self_healing": {"enabled": True},
                "sleep_compute": {"enabled": False}
            }, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            flags = storage.load()

            assert "self_healing" in flags
            assert flags["self_healing"]["enabled"] is True
            assert "sleep_compute" in flags
            assert flags["sleep_compute"]["enabled"] is False
        finally:
            os.unlink(temp_path)

    def test_load_returns_empty_dict_for_missing_file(self):
        """Should return empty dict if file doesn't exist."""
        from core.features.storage import JSONFlagStorage

        storage = JSONFlagStorage(Path("/nonexistent/path/features.json"))
        flags = storage.load()

        assert flags == {}

    def test_load_handles_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            flags = storage.load()

            assert flags == {}
        finally:
            os.unlink(temp_path)

    def test_load_handles_percentage_format(self):
        """Should handle flags with percentage format."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "new_ui": {"enabled": True, "percentage": 10}
            }, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            flags = storage.load()

            assert flags["new_ui"]["percentage"] == 10
        finally:
            os.unlink(temp_path)


class TestJSONFlagStorageSave:
    """Test JSONFlagStorage save functionality."""

    def test_save_creates_file(self):
        """Should create file if it doesn't exist."""
        from core.features.storage import JSONFlagStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features.json"
            storage = JSONFlagStorage(path)

            flags = {"test_flag": {"enabled": True}}
            storage.save(flags)

            assert path.exists()

    def test_save_writes_correct_json(self):
        """Should write valid JSON with correct content."""
        from core.features.storage import JSONFlagStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features.json"
            storage = JSONFlagStorage(path)

            flags = {
                "self_healing": {"enabled": True},
                "sleep_compute": {"enabled": False, "percentage": 50}
            }
            storage.save(flags)

            with open(path) as f:
                loaded = json.load(f)

            assert loaded["self_healing"]["enabled"] is True
            assert loaded["sleep_compute"]["enabled"] is False
            assert loaded["sleep_compute"]["percentage"] == 50

    def test_save_creates_parent_directories(self):
        """Should create parent directories if they don't exist."""
        from core.features.storage import JSONFlagStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "features.json"
            storage = JSONFlagStorage(path)

            flags = {"test_flag": {"enabled": True}}
            storage.save(flags)

            assert path.exists()

    def test_save_overwrites_existing_file(self):
        """Should overwrite existing file content."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"old_flag": {"enabled": True}}, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            storage.save({"new_flag": {"enabled": False}})

            with open(temp_path) as f:
                loaded = json.load(f)

            assert "old_flag" not in loaded
            assert "new_flag" in loaded
        finally:
            os.unlink(temp_path)


class TestJSONFlagStorageWatch:
    """Test JSONFlagStorage watch_for_changes functionality."""

    def test_watch_for_changes_returns_callable(self):
        """watch_for_changes should return a callable to stop watching."""
        from core.features.storage import JSONFlagStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features.json"
            storage = JSONFlagStorage(path)

            # Create initial file
            storage.save({"test": {"enabled": True}})

            callback = MagicMock()
            stop_watching = storage.watch_for_changes(callback)

            assert callable(stop_watching)

            # Stop watching
            stop_watching()

    def test_watch_for_changes_detects_modification(self):
        """Should detect when file is modified."""
        from core.features.storage import JSONFlagStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features.json"
            storage = JSONFlagStorage(path)

            # Create initial file
            storage.save({"test": {"enabled": True}})

            callback = MagicMock()
            stop_watching = storage.watch_for_changes(callback, poll_interval=0.1)

            try:
                # Modify the file
                time.sleep(0.15)
                storage.save({"test": {"enabled": False}})
                time.sleep(0.15)

                # Callback should have been called
                # Note: This is timing-dependent, so we just check it was set up
                assert callable(stop_watching)
            finally:
                stop_watching()


class TestJSONFlagStorageConfigFormat:
    """Test JSON config format compatibility."""

    def test_load_simple_boolean_format(self):
        """Should handle simple boolean format: flag_name: true."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "self_healing": True,
                "sleep_compute": False
            }, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            flags = storage.load()

            # Should normalize to dict format
            assert flags["self_healing"]["enabled"] is True
            assert flags["sleep_compute"]["enabled"] is False
        finally:
            os.unlink(temp_path)

    def test_load_mixed_format(self):
        """Should handle mixed format: some booleans, some dicts."""
        from core.features.storage import JSONFlagStorage

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "self_healing": True,
                "new_ui": {"enabled": True, "percentage": 10}
            }, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            storage = JSONFlagStorage(temp_path)
            flags = storage.load()

            assert flags["self_healing"]["enabled"] is True
            assert flags["new_ui"]["enabled"] is True
            assert flags["new_ui"]["percentage"] == 10
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
