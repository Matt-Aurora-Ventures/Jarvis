"""
Unit tests for ConfigManager singleton.

Tests:
- Singleton pattern
- get(key, default)
- set(key, value)
- reload()
- watch(key, callback)
- validate_config(schema)
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestConfigManagerSingleton:
    """Test ConfigManager singleton pattern."""

    def test_get_instance_returns_same_object(self):
        """ConfigManager.get_instance() should return the same object."""
        from core.config.manager import ConfigManager

        # Reset for clean test
        ConfigManager._instance = None

        manager1 = ConfigManager.get_instance()
        manager2 = ConfigManager.get_instance()

        assert manager1 is manager2

    def test_singleton_prevents_direct_instantiation_warning(self):
        """Direct instantiation should work but return singleton."""
        from core.config.manager import ConfigManager

        ConfigManager._instance = None

        manager1 = ConfigManager()
        manager2 = ConfigManager()

        # Both should be the same singleton
        assert manager1 is manager2

    def test_reset_clears_singleton(self):
        """reset() should clear the singleton instance."""
        from core.config.manager import ConfigManager

        ConfigManager._instance = None
        manager1 = ConfigManager.get_instance()

        ConfigManager.reset()

        manager2 = ConfigManager.get_instance()

        # Should be different instances after reset
        assert manager1 is not manager2


class TestConfigManagerGet:
    """Test ConfigManager.get() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_get_existing_key(self):
        """get() should return value for existing key."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager._config["test.key"] = "test_value"

        result = manager.get("test.key")

        assert result == "test_value"

    def test_get_missing_key_returns_default(self):
        """get() should return default for missing key."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()

        result = manager.get("nonexistent.key", default="default_value")

        assert result == "default_value"

    def test_get_missing_key_no_default_returns_none(self):
        """get() should return None for missing key with no default."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()

        result = manager.get("nonexistent.key")

        assert result is None

    def test_get_nested_key(self):
        """get() should support dot-notation for nested keys."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager._config["database.host"] = "localhost"
        manager._config["database.port"] = 5432

        assert manager.get("database.host") == "localhost"
        assert manager.get("database.port") == 5432


class TestConfigManagerSet:
    """Test ConfigManager.set() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_set_creates_new_key(self):
        """set() should create a new key."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager.set("new.key", "new_value")

        assert manager.get("new.key") == "new_value"

    def test_set_updates_existing_key(self):
        """set() should update an existing key."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager.set("existing.key", "original")
        manager.set("existing.key", "updated")

        assert manager.get("existing.key") == "updated"

    def test_set_supports_various_types(self):
        """set() should support various value types."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()

        manager.set("string.key", "string_value")
        manager.set("int.key", 42)
        manager.set("float.key", 3.14)
        manager.set("bool.key", True)
        manager.set("list.key", [1, 2, 3])
        manager.set("dict.key", {"nested": "value"})

        assert manager.get("string.key") == "string_value"
        assert manager.get("int.key") == 42
        assert manager.get("float.key") == 3.14
        assert manager.get("bool.key") is True
        assert manager.get("list.key") == [1, 2, 3]
        assert manager.get("dict.key") == {"nested": "value"}


class TestConfigManagerReload:
    """Test ConfigManager.reload() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_reload_refreshes_config_from_sources(self):
        """reload() should refresh config from sources."""
        from core.config.manager import ConfigManager
        from core.config.sources import EnvSource

        manager = ConfigManager.get_instance()

        # Set environment variable
        os.environ["TEST_RELOAD_VAR"] = "initial"

        # Add env source
        env_source = EnvSource(prefix="TEST_")
        manager.add_source(env_source)
        manager.reload()

        assert manager.get("RELOAD_VAR") == "initial"

        # Change env var and reload
        os.environ["TEST_RELOAD_VAR"] = "updated"
        manager.reload()

        assert manager.get("RELOAD_VAR") == "updated"

        # Cleanup
        del os.environ["TEST_RELOAD_VAR"]

    def test_reload_preserves_runtime_overrides(self):
        """reload() should optionally preserve runtime overrides."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager.set("runtime.override", "value", persist=False)

        manager.reload(preserve_overrides=True)

        assert manager.get("runtime.override") == "value"


class TestConfigManagerWatch:
    """Test ConfigManager.watch() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_watch_callback_called_on_change(self):
        """watch() callback should be called when value changes."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        callback = MagicMock()

        manager.watch("watched.key", callback)
        manager.set("watched.key", "new_value")

        callback.assert_called_once_with("watched.key", None, "new_value")

    def test_watch_callback_receives_old_and_new_values(self):
        """watch() callback should receive old and new values."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        manager.set("watched.key", "old_value")

        callback = MagicMock()
        manager.watch("watched.key", callback)
        manager.set("watched.key", "new_value")

        callback.assert_called_once_with("watched.key", "old_value", "new_value")

    def test_watch_multiple_callbacks(self):
        """Multiple callbacks can watch the same key."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()

        callback1 = MagicMock()
        callback2 = MagicMock()

        manager.watch("multi.key", callback1)
        manager.watch("multi.key", callback2)
        manager.set("multi.key", "value")

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_unwatch_removes_callback(self):
        """unwatch() should remove a callback."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        callback = MagicMock()

        manager.watch("unwatch.key", callback)
        manager.unwatch("unwatch.key", callback)
        manager.set("unwatch.key", "value")

        callback.assert_not_called()

    def test_watch_pattern_matching(self):
        """watch() should support pattern matching (e.g., 'database.*')."""
        from core.config.manager import ConfigManager

        manager = ConfigManager.get_instance()
        callback = MagicMock()

        manager.watch("database.*", callback)
        manager.set("database.host", "localhost")
        manager.set("database.port", 5432)

        assert callback.call_count == 2


class TestConfigManagerValidation:
    """Test ConfigManager.validate_config() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_validate_with_valid_config(self):
        """validate_config() should return no errors for valid config."""
        from core.config.manager import ConfigManager
        from core.config.schema import ConfigSchema

        manager = ConfigManager.get_instance()
        manager.set("required.key", "value")

        schema = ConfigSchema()
        schema.require("required.key", str)

        errors = manager.validate_config(schema)

        assert errors == []

    def test_validate_with_missing_required(self):
        """validate_config() should return error for missing required key."""
        from core.config.manager import ConfigManager
        from core.config.schema import ConfigSchema

        manager = ConfigManager.get_instance()

        schema = ConfigSchema()
        schema.require("missing.key", str)

        errors = manager.validate_config(schema)

        assert len(errors) == 1
        assert "missing.key" in errors[0].key

    def test_validate_with_wrong_type(self):
        """validate_config() should return error for wrong type."""
        from core.config.manager import ConfigManager
        from core.config.schema import ConfigSchema

        manager = ConfigManager.get_instance()
        manager.set("typed.key", "not_an_int")

        schema = ConfigSchema()
        schema.require("typed.key", int)

        errors = manager.validate_config(schema)

        assert len(errors) == 1
        assert "type" in errors[0].message.lower()

    def test_validate_with_custom_validator(self):
        """validate_config() should support custom validators."""
        from core.config.manager import ConfigManager
        from core.config.schema import ConfigSchema

        manager = ConfigManager.get_instance()
        manager.set("port", 70000)  # Invalid port

        schema = ConfigSchema()
        schema.require("port", int, validator=lambda x: 1 <= x <= 65535)

        errors = manager.validate_config(schema)

        assert len(errors) == 1


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.manager import ConfigManager
        ConfigManager._instance = None

    def test_load_from_multiple_sources(self):
        """ConfigManager should load from multiple sources with priority."""
        from core.config.manager import ConfigManager
        from core.config.sources import EnvSource, FileSource, ChainedSource

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write('{"file.key": "file_value", "shared.key": "from_file"}')
            config_file = f.name

        try:
            os.environ["TEST_ENV_KEY"] = "env_value"
            os.environ["TEST_SHARED_KEY"] = "from_env"

            manager = ConfigManager.get_instance()

            # Env source has higher priority (added last)
            file_source = FileSource(config_file)
            env_source = EnvSource(prefix="TEST_")

            chained = ChainedSource([file_source, env_source])
            manager.add_source(chained)
            manager.reload()

            # File-only key should come from file
            assert manager.get("file.key") == "file_value"

            # Env-only key should come from env
            assert manager.get("ENV_KEY") == "env_value"

            # Shared key should come from env (higher priority)
            assert manager.get("SHARED_KEY") == "from_env"

        finally:
            os.unlink(config_file)
            del os.environ["TEST_ENV_KEY"]
            del os.environ["TEST_SHARED_KEY"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
