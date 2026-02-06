"""
Tests for ClawdBots Configuration Loader.

Tests the config_loader module which provides:
- Configuration loading from environment and files
- Config validation with schema
- Hot-reload support
- Default values

TDD: These tests are written FIRST, before implementation.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest


class TestGetConfig:
    """Tests for get_config() function."""

    def test_get_config_from_environment(self):
        """Environment variables should take highest priority."""
        from bots.shared.config_loader import get_config

        with patch.dict(os.environ, {"DEBUG_MODE": "true"}, clear=False):
            result = get_config("DEBUG_MODE")
            assert result == "true"

    def test_get_config_with_default(self):
        """Should return default when key not found."""
        from bots.shared.config_loader import get_config

        # Use a key that definitely doesn't exist
        result = get_config("NONEXISTENT_KEY_12345", default="fallback")
        assert result == "fallback"

    def test_get_config_returns_none_when_missing(self):
        """Should return None when key missing and no default."""
        from bots.shared.config_loader import get_config

        # Ensure key doesn't exist
        if "NONEXISTENT_KEY_67890" in os.environ:
            del os.environ["NONEXISTENT_KEY_67890"]

        result = get_config("NONEXISTENT_KEY_67890")
        assert result is None

    def test_get_config_bool_conversion(self):
        """Should handle boolean type conversion."""
        from bots.shared.config_loader import get_config

        with patch.dict(os.environ, {"TEST_BOOL": "true"}, clear=False):
            result = get_config("TEST_BOOL", type_=bool)
            assert result is True

        with patch.dict(os.environ, {"TEST_BOOL": "false"}, clear=False):
            result = get_config("TEST_BOOL", type_=bool)
            assert result is False

        with patch.dict(os.environ, {"TEST_BOOL": "1"}, clear=False):
            result = get_config("TEST_BOOL", type_=bool)
            assert result is True

    def test_get_config_int_conversion(self):
        """Should handle integer type conversion."""
        from bots.shared.config_loader import get_config

        with patch.dict(os.environ, {"TEST_INT": "42"}, clear=False):
            result = get_config("TEST_INT", type_=int)
            assert result == 42

    def test_get_config_list_conversion(self):
        """Should handle comma-separated list conversion."""
        from bots.shared.config_loader import get_config

        with patch.dict(os.environ, {"TEST_LIST": "a,b,c"}, clear=False):
            result = get_config("TEST_LIST", type_=list)
            assert result == ["a", "b", "c"]


class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_config_returns_dict(self):
        """Should return a dictionary."""
        from bots.shared.config_loader import load_config

        config = load_config()
        assert isinstance(config, dict)

    def test_load_config_includes_defaults(self):
        """Should include default values."""
        from bots.shared.config_loader import load_config

        config = load_config()
        # DEBUG_MODE should have a default value
        assert "DEBUG_MODE" in config

    def test_load_config_from_file(self):
        """Should load config from JSON file."""
        from bots.shared.config_loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({
                "CUSTOM_KEY": "custom_value"
            }))

            config = load_config(config_path=str(config_path))
            assert config.get("CUSTOM_KEY") == "custom_value"

    def test_load_config_env_overrides_file(self):
        """Environment should override file config."""
        from bots.shared.config_loader import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({
                "TEST_OVERRIDE": "from_file"
            }))

            with patch.dict(os.environ, {"TEST_OVERRIDE": "from_env"}, clear=False):
                config = load_config(config_path=str(config_path))
                assert config.get("TEST_OVERRIDE") == "from_env"

    def test_load_config_handles_missing_file(self):
        """Should handle missing config file gracefully."""
        from bots.shared.config_loader import load_config

        config = load_config(config_path="/nonexistent/path/config.json")
        # Should still return dict with defaults
        assert isinstance(config, dict)


class TestReloadConfig:
    """Tests for reload_config() function."""

    def test_reload_config_refreshes_values(self):
        """Should reload values from sources."""
        from bots.shared.config_loader import get_config, reload_config, load_config

        # Initial load
        load_config()

        # Change environment
        with patch.dict(os.environ, {"RELOAD_TEST_KEY": "new_value"}, clear=False):
            reload_config()
            result = get_config("RELOAD_TEST_KEY")
            assert result == "new_value"

    def test_reload_config_returns_new_config(self):
        """Should return the new config dict."""
        from bots.shared.config_loader import reload_config

        config = reload_config()
        assert isinstance(config, dict)


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validate_config_returns_list(self):
        """Should return a list of errors."""
        from bots.shared.config_loader import validate_config

        errors = validate_config()
        assert isinstance(errors, list)

    def test_validate_config_detects_missing_required(self):
        """Should detect missing required config keys."""
        from bots.shared.config_loader import validate_config, load_config

        # Load without TELEGRAM_BOT_TOKEN in env
        with patch.dict(os.environ, {}, clear=True):
            load_config()
            errors = validate_config()
            # Should have at least one error about TELEGRAM_BOT_TOKEN
            assert any("TELEGRAM_BOT_TOKEN" in str(e) for e in errors)

    def test_validate_config_accepts_valid_config(self):
        """Should return empty list for valid config."""
        from bots.shared.config_loader import validate_config, load_config

        # Provide minimum required config
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token_12345"
        }, clear=False):
            load_config()
            errors = validate_config()
            # No errors about TELEGRAM_BOT_TOKEN
            assert not any("TELEGRAM_BOT_TOKEN" in str(e) for e in errors)

    def test_validate_config_checks_admin_user_ids_format(self):
        """Should validate ADMIN_USER_IDS is comma-separated integers."""
        from bots.shared.config_loader import validate_config, load_config

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "ADMIN_USER_IDS": "not_a_number"
        }, clear=False):
            load_config()
            errors = validate_config()
            # Should have error about ADMIN_USER_IDS format
            assert any("ADMIN_USER_IDS" in str(e) for e in errors)

    def test_validate_config_accepts_valid_admin_ids(self):
        """Should accept valid comma-separated admin IDs."""
        from bots.shared.config_loader import validate_config, load_config

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "ADMIN_USER_IDS": "123,456,789"
        }, clear=False):
            load_config()
            errors = validate_config()
            # No errors about ADMIN_USER_IDS
            assert not any("ADMIN_USER_IDS" in str(e) for e in errors)


class TestConfigSchema:
    """Tests for config schema validation."""

    def test_debug_mode_must_be_boolean(self):
        """DEBUG_MODE should be validated as boolean."""
        from bots.shared.config_loader import validate_config, load_config

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test",
            "DEBUG_MODE": "invalid_bool"
        }, clear=False):
            load_config()
            errors = validate_config()
            # Should warn about invalid boolean
            assert any("DEBUG_MODE" in str(e) for e in errors)

    def test_valid_debug_mode_values(self):
        """DEBUG_MODE should accept true/false/1/0."""
        from bots.shared.config_loader import validate_config, load_config

        for value in ["true", "false", "1", "0", "True", "False"]:
            with patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "test",
                "DEBUG_MODE": value
            }, clear=False):
                load_config()
                errors = validate_config()
                assert not any("DEBUG_MODE" in str(e) for e in errors), f"Failed for {value}"


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_default_debug_mode(self):
        """DEBUG_MODE should default to False."""
        from bots.shared.config_loader import get_config, load_config

        # Remove DEBUG_MODE from env if present
        env_copy = os.environ.copy()
        env_copy.pop("DEBUG_MODE", None)

        with patch.dict(os.environ, env_copy, clear=True):
            load_config()
            result = get_config("DEBUG_MODE", type_=bool)
            assert result is False

    def test_optional_api_keys_allowed_missing(self):
        """Optional API keys (OPENAI, ANTHROPIC, XAI) should not cause errors when missing."""
        from bots.shared.config_loader import validate_config, load_config

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test"
        }, clear=True):
            load_config()
            errors = validate_config()
            # These are optional, so no errors
            assert not any("OPENAI_API_KEY" in str(e) for e in errors)
            assert not any("ANTHROPIC_API_KEY" in str(e) for e in errors)
            assert not any("XAI_API_KEY" in str(e) for e in errors)


class TestHotReload:
    """Tests for hot-reload functionality."""

    def test_file_config_reloads_on_change(self):
        """Should pick up config file changes on reload."""
        from bots.shared.config_loader import load_config, reload_config, get_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"HOT_RELOAD_KEY": "initial"}))

            # Initial load
            load_config(config_path=str(config_path))
            assert get_config("HOT_RELOAD_KEY") == "initial"

            # Modify file
            config_path.write_text(json.dumps({"HOT_RELOAD_KEY": "updated"}))

            # Reload
            reload_config()
            assert get_config("HOT_RELOAD_KEY") == "updated"


class TestConfigSourcePriority:
    """Tests for config source priority order."""

    def test_env_beats_file(self):
        """Environment variables should override file config."""
        from bots.shared.config_loader import load_config, get_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"PRIORITY_KEY": "from_file"}))

            with patch.dict(os.environ, {"PRIORITY_KEY": "from_env"}, clear=False):
                load_config(config_path=str(config_path))
                assert get_config("PRIORITY_KEY") == "from_env"

    def test_file_beats_default(self):
        """File config should override defaults."""
        from bots.shared.config_loader import load_config, get_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            # Override DEBUG_MODE default (False) with True
            config_path.write_text(json.dumps({"DEBUG_MODE": "true"}))

            # Ensure DEBUG_MODE not in env
            env_copy = os.environ.copy()
            env_copy.pop("DEBUG_MODE", None)

            with patch.dict(os.environ, env_copy, clear=True):
                load_config(config_path=str(config_path))
                result = get_config("DEBUG_MODE", type_=bool)
                assert result is True


class TestConfigThreadSafety:
    """Tests for thread-safety of config operations."""

    def test_concurrent_get_config(self):
        """get_config should be safe for concurrent access."""
        import threading
        from bots.shared.config_loader import get_config, load_config

        load_config()
        results = []
        errors = []

        def read_config():
            try:
                for _ in range(100):
                    get_config("DEBUG_MODE")
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_config) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10


class TestConfigSecrets:
    """Tests for secure handling of secret values."""

    def test_api_keys_not_logged(self):
        """API keys should be masked when getting debug info."""
        from bots.shared.config_loader import get_config_debug_info, load_config

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "super_secret_token_12345",
            "ANTHROPIC_API_KEY": "sk-ant-api-xxx"
        }, clear=False):
            load_config()
            debug_info = get_config_debug_info()
            # Should not contain full tokens
            assert "super_secret_token_12345" not in debug_info
            assert "sk-ant-api-xxx" not in debug_info
            # Should have masked versions
            assert "***" in debug_info or "..." in debug_info
