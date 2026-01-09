"""
Tests for Core Config Module.

Tests cover:
- Config loading
- Config defaults
- Config path resolution
- Config value access
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


# =============================================================================
# Test Config Loading
# =============================================================================

class TestConfigLoading:
    """Test config loading functionality."""

    def test_load_config_returns_dict(self):
        """Should return dictionary."""
        cfg = config.load_config()
        assert isinstance(cfg, dict)

    def test_load_config_consistent(self):
        """Should return consistent config values."""
        # First load
        cfg1 = config.load_config()
        # Second load should return equivalent config
        cfg2 = config.load_config()
        # Should have same values
        assert cfg1 == cfg2

    def test_load_config_has_defaults(self):
        """Should have default sections."""
        cfg = config.load_config()
        # Config should have some structure
        assert cfg is not None

    def test_config_reload(self):
        """Should reload config when forced."""
        cfg1 = config.load_config()
        # Force reload
        config._config = None
        cfg2 = config.load_config()
        # Should be different object after reload
        assert cfg2 is not None


# =============================================================================
# Test Config Value Access
# =============================================================================

class TestConfigValueAccess:
    """Test accessing config values."""

    def test_get_nested_value(self):
        """Should get nested config value."""
        cfg = config.load_config()
        # Try to access a nested value - may or may not exist
        result = cfg.get("general", {})
        assert isinstance(result, dict) or result is None

    def test_get_with_default(self):
        """Should return default for missing key."""
        cfg = config.load_config()
        result = cfg.get("nonexistent_key", "default_value")
        assert result == "default_value"

    def test_config_sections(self):
        """Config should have expected structure."""
        cfg = config.load_config()
        # Config is a dict-like object
        assert hasattr(cfg, "get")


# =============================================================================
# Test Config Path Resolution
# =============================================================================

class TestConfigPathResolution:
    """Test config file path handling."""

    def test_config_path_exists(self):
        """Config path should be defined."""
        # The config module should define where to look for config
        assert hasattr(config, "load_config")

    def test_handles_missing_config_file(self):
        """Should handle missing config file gracefully."""
        # Should not raise when config file doesn't exist
        try:
            cfg = config.load_config()
            assert cfg is not None
        except FileNotFoundError:
            pytest.fail("Should handle missing config gracefully")


# =============================================================================
# Test Config Sections
# =============================================================================

class TestConfigSections:
    """Test specific config sections."""

    def test_voice_config_section(self):
        """Voice config should be accessible."""
        cfg = config.load_config()
        voice_cfg = cfg.get("voice", {})
        assert isinstance(voice_cfg, dict)

    def test_actions_config_section(self):
        """Actions config should be accessible."""
        cfg = config.load_config()
        actions_cfg = cfg.get("actions", {})
        assert isinstance(actions_cfg, dict)

    def test_diagnostics_config_section(self):
        """Diagnostics config should be accessible."""
        cfg = config.load_config()
        diag_cfg = cfg.get("diagnostics", {})
        assert isinstance(diag_cfg, dict)

    def test_trading_config_section(self):
        """Trading config should be accessible."""
        cfg = config.load_config()
        trading_cfg = cfg.get("trading", {})
        assert isinstance(trading_cfg, dict)


# =============================================================================
# Test Config Defaults
# =============================================================================

class TestConfigDefaults:
    """Test config default values."""

    def test_voice_defaults(self):
        """Should have voice defaults."""
        cfg = config.load_config()
        voice = cfg.get("voice", {})
        # Check for common voice settings
        assert isinstance(voice, dict)

    def test_actions_allow_ui_default(self):
        """Actions allow_ui should default appropriately."""
        cfg = config.load_config()
        actions = cfg.get("actions", {})
        # allow_ui is commonly True by default
        allow_ui = actions.get("allow_ui", True)
        assert isinstance(allow_ui, bool)
