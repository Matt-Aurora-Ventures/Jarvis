"""
Unit tests for Feature Flags System.

Tests:
- Flag evaluation logic (is_enabled)
- Percentage-based rollouts (hash-based consistency)
- User whitelist support
- Environment variable overrides (FF_*)
- Hot reload functionality
- Caching with TTL
- JSON config loading
"""

import pytest
import os
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestFeatureFlagModels:
    """Test data models for feature flags."""

    def test_feature_flag_config_creation(self):
        """Test creating a FeatureFlagConfig."""
        from core.config.feature_flag_models import FeatureFlagConfig

        flag = FeatureFlagConfig(
            name="TEST_FLAG",
            enabled=True,
            description="Test flag",
            rollout_percentage=50,
            user_whitelist=["user1", "user2"],
        )

        assert flag.name == "TEST_FLAG"
        assert flag.enabled is True
        assert flag.description == "Test flag"
        assert flag.rollout_percentage == 50
        assert flag.user_whitelist == ["user1", "user2"]

    def test_feature_flag_config_defaults(self):
        """Test default values for FeatureFlagConfig."""
        from core.config.feature_flag_models import FeatureFlagConfig

        flag = FeatureFlagConfig(name="TEST_FLAG")

        assert flag.enabled is False
        assert flag.description == ""
        assert flag.rollout_percentage == 0
        assert flag.user_whitelist == []

    def test_feature_flag_config_to_dict(self):
        """Test converting FeatureFlagConfig to dictionary."""
        from core.config.feature_flag_models import FeatureFlagConfig

        flag = FeatureFlagConfig(
            name="TEST_FLAG",
            enabled=True,
            description="Test",
        )

        data = flag.to_dict()
        assert data["name"] == "TEST_FLAG"
        assert data["enabled"] is True
        assert "created_at" in data
        assert "updated_at" in data

    def test_feature_flag_config_from_dict(self):
        """Test creating FeatureFlagConfig from dictionary."""
        from core.config.feature_flag_models import FeatureFlagConfig

        data = {
            "name": "TEST_FLAG",
            "enabled": True,
            "description": "Test flag",
            "rollout_percentage": 25,
            "user_whitelist": ["admin"],
            "created_at": "2026-01-18",
            "updated_at": "2026-01-18",
        }

        flag = FeatureFlagConfig.from_dict(data)
        assert flag.name == "TEST_FLAG"
        assert flag.enabled is True
        assert flag.rollout_percentage == 25


class TestFeatureFlagManager:
    """Test FeatureFlagManager class."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "flags": {
                    "TEST_ENABLED": {
                        "enabled": True,
                        "description": "Test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "TEST_DISABLED": {
                        "enabled": False,
                        "description": "Disabled test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "TEST_PERCENTAGE": {
                        "enabled": True,
                        "description": "Percentage rollout test",
                        "rollout_percentage": 50,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "TEST_WHITELIST": {
                        "enabled": True,
                        "description": "Whitelist test",
                        "rollout_percentage": 0,
                        "user_whitelist": ["user123", "user456"],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)
            f.flush()
            yield Path(f.name)
        os.unlink(f.name)

    def test_manager_singleton(self, temp_flags_file):
        """Test that FeatureFlagManager is a singleton."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()

        manager1 = FeatureFlagManager(config_path=temp_flags_file)
        manager2 = FeatureFlagManager(config_path=temp_flags_file)

        assert manager1 is manager2
        _reset_manager()

    def test_is_enabled_basic(self, temp_flags_file):
        """Test basic is_enabled check."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        assert manager.is_enabled("TEST_ENABLED") is True
        assert manager.is_enabled("TEST_DISABLED") is False
        assert manager.is_enabled("NONEXISTENT") is False

        _reset_manager()

    def test_is_enabled_with_user_whitelist(self, temp_flags_file):
        """Test is_enabled respects user whitelist."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        # User in whitelist should have access
        assert manager.is_enabled("TEST_WHITELIST", user_id="user123") is True

        # User not in whitelist - depends on percentage (0 here, so should be false)
        assert manager.is_enabled("TEST_WHITELIST", user_id="other_user") is False

        _reset_manager()

    def test_is_enabled_percentage_rollout(self, temp_flags_file):
        """Test percentage-based rollout is consistent for same user."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        # Same user should get same result every time (hash-based)
        result1 = manager.is_enabled("TEST_PERCENTAGE", user_id="consistent_user")
        result2 = manager.is_enabled("TEST_PERCENTAGE", user_id="consistent_user")

        assert result1 == result2  # Must be consistent

        _reset_manager()

    def test_is_enabled_percentage_distribution(self, temp_flags_file):
        """Test percentage rollout distributes correctly over many users."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        # With 50% rollout, roughly half of users should get True
        enabled_count = 0
        total_users = 1000

        for i in range(total_users):
            if manager.is_enabled("TEST_PERCENTAGE", user_id=f"user_{i}"):
                enabled_count += 1

        # Allow 10% tolerance (40-60% range for 50% target)
        ratio = enabled_count / total_users
        assert 0.40 <= ratio <= 0.60, f"Expected ~50% but got {ratio*100:.1f}%"

        _reset_manager()

    def test_get_flag(self, temp_flags_file):
        """Test get_flag returns flag config."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        flag = manager.get_flag("TEST_ENABLED")
        assert flag is not None
        assert flag.name == "TEST_ENABLED"
        assert flag.enabled is True

        missing = manager.get_flag("NONEXISTENT")
        assert missing is None

        _reset_manager()

    def test_set_flag(self, temp_flags_file):
        """Test set_flag updates flag config."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        # Disable TEST_ENABLED
        manager.set_flag("TEST_ENABLED", enabled=False)
        assert manager.is_enabled("TEST_ENABLED") is False

        # Re-enable with percentage
        manager.set_flag("TEST_ENABLED", enabled=True, percentage=30)
        flag = manager.get_flag("TEST_ENABLED")
        assert flag.rollout_percentage == 30

        _reset_manager()

    def test_set_flag_with_user_list(self, temp_flags_file):
        """Test set_flag with user whitelist."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        manager.set_flag("TEST_ENABLED", enabled=True, user_list=["vip_user"])

        assert manager.is_enabled("TEST_ENABLED", user_id="vip_user") is True
        assert manager.is_enabled("TEST_ENABLED", user_id="regular_user") is False

        _reset_manager()


class TestEnvironmentOverrides:
    """Test environment variable overrides for feature flags."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "flags": {
                    "DEXTER_ENABLED": {
                        "enabled": False,
                        "description": "Enable Dexter ReAct agent",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)
            f.flush()
            yield Path(f.name)
        os.unlink(f.name)

    def test_env_override_enables_flag(self, temp_flags_file):
        """Test FF_* environment variable enables a disabled flag."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()

        # Set env var to enable
        os.environ["FF_DEXTER_ENABLED"] = "true"

        try:
            manager = FeatureFlagManager(config_path=temp_flags_file)

            # Flag should be enabled via env override
            assert manager.is_enabled("DEXTER_ENABLED") is True
        finally:
            os.environ.pop("FF_DEXTER_ENABLED", None)
            _reset_manager()

    def test_env_override_disables_flag(self, temp_flags_file):
        """Test FF_* environment variable disables an enabled flag."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()

        # Create file with enabled flag
        with open(temp_flags_file, 'w') as f:
            json.dump({
                "flags": {
                    "DEXTER_ENABLED": {
                        "enabled": True,
                        "description": "Enable Dexter ReAct agent",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)

        # Set env var to disable
        os.environ["FF_DEXTER_ENABLED"] = "false"

        try:
            manager = FeatureFlagManager(config_path=temp_flags_file)

            # Flag should be disabled via env override
            assert manager.is_enabled("DEXTER_ENABLED") is False
        finally:
            os.environ.pop("FF_DEXTER_ENABLED", None)
            _reset_manager()

    def test_env_override_case_variations(self, temp_flags_file):
        """Test various case variations of true/false in env vars."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO"]

        for val in true_values:
            _reset_manager()
            os.environ["FF_DEXTER_ENABLED"] = val
            try:
                manager = FeatureFlagManager(config_path=temp_flags_file)
                assert manager.is_enabled("DEXTER_ENABLED") is True, f"'{val}' should be True"
            finally:
                os.environ.pop("FF_DEXTER_ENABLED", None)

        for val in false_values:
            _reset_manager()
            os.environ["FF_DEXTER_ENABLED"] = val
            try:
                manager = FeatureFlagManager(config_path=temp_flags_file)
                assert manager.is_enabled("DEXTER_ENABLED") is False, f"'{val}' should be False"
            finally:
                os.environ.pop("FF_DEXTER_ENABLED", None)

        _reset_manager()


class TestHotReload:
    """Test hot reload functionality."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "flags": {
                    "HOT_RELOAD_TEST": {
                        "enabled": False,
                        "description": "Hot reload test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)
            f.flush()
            yield Path(f.name)
        os.unlink(f.name)

    def test_reload_from_file(self, temp_flags_file):
        """Test reload_from_file updates flags from JSON."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file)

        # Initially disabled
        assert manager.is_enabled("HOT_RELOAD_TEST") is False

        # Modify file to enable
        with open(temp_flags_file, 'w') as f:
            json.dump({
                "flags": {
                    "HOT_RELOAD_TEST": {
                        "enabled": True,
                        "description": "Hot reload test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)

        # Reload and check
        manager.reload_from_file()
        assert manager.is_enabled("HOT_RELOAD_TEST") is True

        _reset_manager()

    def test_reload_preserves_env_overrides(self, temp_flags_file):
        """Test that reload preserves environment variable overrides."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()

        os.environ["FF_HOT_RELOAD_TEST"] = "true"

        try:
            manager = FeatureFlagManager(config_path=temp_flags_file)

            # Should be True due to env override
            assert manager.is_enabled("HOT_RELOAD_TEST") is True

            # Modify file to keep it disabled
            with open(temp_flags_file, 'w') as f:
                json.dump({
                    "flags": {
                        "HOT_RELOAD_TEST": {
                            "enabled": False,
                            "description": "Hot reload test flag",
                            "rollout_percentage": 0,
                            "user_whitelist": [],
                            "created_at": "2026-01-18",
                            "updated_at": "2026-01-18",
                        },
                    }
                }, f)

            # Reload
            manager.reload_from_file()

            # Should still be True due to env override
            assert manager.is_enabled("HOT_RELOAD_TEST") is True
        finally:
            os.environ.pop("FF_HOT_RELOAD_TEST", None)
            _reset_manager()


class TestCaching:
    """Test caching with TTL."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "flags": {
                    "CACHE_TEST": {
                        "enabled": True,
                        "description": "Cache test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)
            f.flush()
            yield Path(f.name)
        os.unlink(f.name)

    def test_caching_returns_cached_result(self, temp_flags_file):
        """Test that results are cached."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file, cache_ttl_seconds=60)

        # First call should load from file
        result1 = manager.is_enabled("CACHE_TEST")
        assert result1 is True

        # Modify file (but cache should still return old value)
        with open(temp_flags_file, 'w') as f:
            json.dump({
                "flags": {
                    "CACHE_TEST": {
                        "enabled": False,
                        "description": "Cache test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)

        # Should still return cached True value
        result2 = manager.is_enabled("CACHE_TEST")
        assert result2 is True

        _reset_manager()

    def test_cache_expires_after_ttl(self, temp_flags_file):
        """Test that cache expires after TTL."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=temp_flags_file, cache_ttl_seconds=0.1)

        # First call
        result1 = manager.is_enabled("CACHE_TEST")
        assert result1 is True

        # Modify file
        with open(temp_flags_file, 'w') as f:
            json.dump({
                "flags": {
                    "CACHE_TEST": {
                        "enabled": False,
                        "description": "Cache test flag",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)

        # Wait for TTL to expire
        time.sleep(0.15)

        # Should now return new value
        result2 = manager.is_enabled("CACHE_TEST")
        assert result2 is False

        _reset_manager()


class TestSpecificFlags:
    """Test the specific flags required by the architect."""

    @pytest.fixture
    def default_flags_file(self):
        """Create flags file with required default flags."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "flags": {
                    "DEXTER_ENABLED": {
                        "enabled": False,
                        "description": "Enable Dexter ReAct agent",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "ADVANCED_TRADING_ENABLED": {
                        "enabled": False,
                        "description": "Trailing stops, DCA strategies",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "NEW_TELEGRAM_UI_ENABLED": {
                        "enabled": False,
                        "description": "Inline buttons, drill-down",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "LIVE_TRADING_ENABLED": {
                        "enabled": True,
                        "description": "Allow real trades",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                    "STRUCTURED_LOGGING_ENABLED": {
                        "enabled": False,
                        "description": "New logging system",
                        "rollout_percentage": 0,
                        "user_whitelist": [],
                        "created_at": "2026-01-18",
                        "updated_at": "2026-01-18",
                    },
                }
            }, f)
            f.flush()
            yield Path(f.name)
        os.unlink(f.name)

    def test_dexter_disabled_by_default(self, default_flags_file):
        """Test DEXTER_ENABLED is false by default."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=default_flags_file)

        assert manager.is_enabled("DEXTER_ENABLED") is False
        _reset_manager()

    def test_advanced_trading_disabled_by_default(self, default_flags_file):
        """Test ADVANCED_TRADING_ENABLED is false by default."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=default_flags_file)

        assert manager.is_enabled("ADVANCED_TRADING_ENABLED") is False
        _reset_manager()

    def test_live_trading_enabled_by_default(self, default_flags_file):
        """Test LIVE_TRADING_ENABLED is true by default."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=default_flags_file)

        assert manager.is_enabled("LIVE_TRADING_ENABLED") is True
        _reset_manager()

    def test_all_required_flags_exist(self, default_flags_file):
        """Test all 5 required flags exist."""
        from core.config.feature_flags import FeatureFlagManager, _reset_manager

        _reset_manager()
        manager = FeatureFlagManager(config_path=default_flags_file)

        required_flags = [
            "DEXTER_ENABLED",
            "ADVANCED_TRADING_ENABLED",
            "NEW_TELEGRAM_UI_ENABLED",
            "LIVE_TRADING_ENABLED",
            "STRUCTURED_LOGGING_ENABLED",
        ]

        for flag_name in required_flags:
            flag = manager.get_flag(flag_name)
            assert flag is not None, f"Flag {flag_name} should exist"

        _reset_manager()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
