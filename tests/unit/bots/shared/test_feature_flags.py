"""
Unit tests for ClawdBots Feature Flags module.

Tests:
- is_enabled: Flag evaluation with user overrides
- set_flag: Setting flags with rollout percentage
- get_all_flags: Getting all flag states
- override_for_user: Per-user overrides
- get_flag_history: Audit trail for flag changes
- Percentage-based rollouts (consistent hashing)
- Default flags initialization
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestFeatureFlagsIsEnabled:
    """Test is_enabled function."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file for testing."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "test_flag": {
                        "name": "test_flag",
                        "enabled": True,
                        "rollout_percent": 100,
                        "description": "Test flag",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    },
                    "disabled_flag": {
                        "name": "disabled_flag",
                        "enabled": False,
                        "rollout_percent": 0,
                        "description": "Disabled flag",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    },
                    "partial_rollout": {
                        "name": "partial_rollout",
                        "enabled": True,
                        "rollout_percent": 50,
                        "description": "50% rollout",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": []
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_is_enabled_returns_true_for_enabled_flag(self, temp_flags_file):
        """Test that enabled flag returns True."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        assert flags.is_enabled("test_flag") is True

    def test_is_enabled_returns_false_for_disabled_flag(self, temp_flags_file):
        """Test that disabled flag returns False."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        assert flags.is_enabled("disabled_flag") is False

    def test_is_enabled_returns_false_for_nonexistent_flag(self, temp_flags_file):
        """Test that nonexistent flag returns False."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        assert flags.is_enabled("nonexistent") is False

    def test_is_enabled_respects_user_override_true(self, temp_flags_file):
        """Test that user override can enable a disabled flag."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.override_for_user("disabled_flag", "user123", True)

        # Without user_id, still disabled
        assert flags.is_enabled("disabled_flag") is False
        # With user_id, enabled
        assert flags.is_enabled("disabled_flag", user_id="user123") is True

    def test_is_enabled_respects_user_override_false(self, temp_flags_file):
        """Test that user override can disable an enabled flag."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.override_for_user("test_flag", "user456", False)

        # Without user_id, still enabled
        assert flags.is_enabled("test_flag") is True
        # With user_id, disabled
        assert flags.is_enabled("test_flag", user_id="user456") is False


class TestFeatureFlagsSetFlag:
    """Test set_flag function."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary empty flags file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({"flags": {}, "history": []}, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_set_flag_creates_new_flag(self, temp_flags_file):
        """Test creating a new flag."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("new_feature", enabled=True, rollout_percent=100)

        assert flags.is_enabled("new_feature") is True

    def test_set_flag_updates_existing_flag(self, temp_flags_file):
        """Test updating an existing flag."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("feature", enabled=True, rollout_percent=100)
        assert flags.is_enabled("feature") is True

        flags.set_flag("feature", enabled=False, rollout_percent=0)
        assert flags.is_enabled("feature") is False

    def test_set_flag_with_partial_rollout(self, temp_flags_file):
        """Test setting a flag with percentage rollout."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("rollout_feature", enabled=True, rollout_percent=50)

        all_flags = flags.get_all_flags()
        assert all_flags["rollout_feature"]["rollout_percent"] == 50

    def test_set_flag_persists_to_file(self, temp_flags_file):
        """Test that set_flag persists changes to file."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("persist_test", enabled=True, rollout_percent=100)

        # Create new instance to read from file
        flags2 = ClawdBotFeatureFlags(config_path=temp_flags_file)
        assert flags2.is_enabled("persist_test") is True


class TestFeatureFlagsGetAllFlags:
    """Test get_all_flags function."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "flag_a": {
                        "name": "flag_a",
                        "enabled": True,
                        "rollout_percent": 100,
                        "description": "Flag A",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    },
                    "flag_b": {
                        "name": "flag_b",
                        "enabled": False,
                        "rollout_percent": 0,
                        "description": "Flag B",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": []
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_get_all_flags_returns_all_flags(self, temp_flags_file):
        """Test that get_all_flags returns all configured flags."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        all_flags = flags.get_all_flags()

        assert "flag_a" in all_flags
        assert "flag_b" in all_flags
        assert len(all_flags) == 2

    def test_get_all_flags_includes_state(self, temp_flags_file):
        """Test that get_all_flags includes enabled state."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        all_flags = flags.get_all_flags()

        assert all_flags["flag_a"]["enabled"] is True
        assert all_flags["flag_b"]["enabled"] is False


class TestFeatureFlagsOverrideForUser:
    """Test override_for_user function."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "user_test": {
                        "name": "user_test",
                        "enabled": False,
                        "rollout_percent": 0,
                        "description": "User test flag",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": []
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_override_for_user_creates_override(self, temp_flags_file):
        """Test that override_for_user creates a user override."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.override_for_user("user_test", "user_abc", True)

        assert flags.is_enabled("user_test", user_id="user_abc") is True

    def test_override_for_user_persists(self, temp_flags_file):
        """Test that user overrides persist to file."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.override_for_user("user_test", "persistent_user", True)

        # New instance should have the override
        flags2 = ClawdBotFeatureFlags(config_path=temp_flags_file)
        assert flags2.is_enabled("user_test", user_id="persistent_user") is True

    def test_override_for_user_records_history(self, temp_flags_file):
        """Test that user overrides are recorded in history."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.override_for_user("user_test", "history_user", True)

        history = flags.get_flag_history("user_test")
        assert len(history) >= 1
        # Most recent should be the override
        latest = history[-1]
        assert latest["action"] == "user_override"
        assert latest["user_id"] == "history_user"


class TestFeatureFlagsGetFlagHistory:
    """Test get_flag_history function."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file with history."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "history_test": {
                        "name": "history_test",
                        "enabled": True,
                        "rollout_percent": 100,
                        "description": "History test flag",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": [
                    {
                        "timestamp": "2026-02-01T00:00:00Z",
                        "flag_name": "history_test",
                        "action": "created",
                        "old_value": None,
                        "new_value": {"enabled": False, "rollout_percent": 0}
                    },
                    {
                        "timestamp": "2026-02-02T00:00:00Z",
                        "flag_name": "history_test",
                        "action": "updated",
                        "old_value": {"enabled": False, "rollout_percent": 0},
                        "new_value": {"enabled": True, "rollout_percent": 100}
                    }
                ]
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_get_flag_history_returns_history(self, temp_flags_file):
        """Test that get_flag_history returns change history."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        history = flags.get_flag_history("history_test")

        assert len(history) == 2
        assert history[0]["action"] == "created"
        assert history[1]["action"] == "updated"

    def test_get_flag_history_empty_for_nonexistent(self, temp_flags_file):
        """Test that get_flag_history returns empty for nonexistent flag."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        history = flags.get_flag_history("nonexistent_flag")

        assert history == []

    def test_set_flag_records_history(self, temp_flags_file):
        """Test that set_flag records changes in history."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("new_flag", enabled=True, rollout_percent=50)

        history = flags.get_flag_history("new_flag")
        assert len(history) == 1
        assert history[0]["action"] == "created"


class TestFeatureFlagsPercentageRollout:
    """Test percentage-based rollout functionality."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "partial_flag": {
                        "name": "partial_flag",
                        "enabled": True,
                        "rollout_percent": 50,
                        "description": "50% rollout",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": []
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_percentage_rollout_consistent_for_same_user(self, temp_flags_file):
        """Test that same user always gets same result (consistent hashing)."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)

        # Call multiple times - should be consistent
        result1 = flags.is_enabled("partial_flag", user_id="consistent_user")
        result2 = flags.is_enabled("partial_flag", user_id="consistent_user")
        result3 = flags.is_enabled("partial_flag", user_id="consistent_user")

        assert result1 == result2 == result3

    def test_percentage_rollout_varies_by_user(self, temp_flags_file):
        """Test that different users can get different results."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)

        # With 50% rollout, roughly half should get True
        # Test with many users to verify distribution
        results = []
        for i in range(100):
            result = flags.is_enabled("partial_flag", user_id=f"user_{i}")
            results.append(result)

        # With 50%, expect roughly 40-60 true values (allowing variance)
        true_count = sum(results)
        assert 30 < true_count < 70  # Reasonable range for 50%

    def test_zero_percent_always_false(self, temp_flags_file):
        """Test that 0% rollout is always false."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("zero_rollout", enabled=True, rollout_percent=0)

        for i in range(10):
            assert flags.is_enabled("zero_rollout", user_id=f"user_{i}") is False

    def test_hundred_percent_always_true(self, temp_flags_file):
        """Test that 100% rollout is always true (if enabled)."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags = ClawdBotFeatureFlags(config_path=temp_flags_file)
        flags.set_flag("full_rollout", enabled=True, rollout_percent=100)

        for i in range(10):
            assert flags.is_enabled("full_rollout", user_id=f"user_{i}") is True


class TestFeatureFlagsDefaultFlags:
    """Test default flags initialization."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for flags file."""
        import tempfile
        temp = tempfile.mkdtemp()
        yield temp
        import shutil
        shutil.rmtree(temp, ignore_errors=True)

    def test_default_flags_created_on_init(self, temp_dir):
        """Test that default flags are created when file doesn't exist."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags_path = Path(temp_dir) / "feature_flags.json"
        flags = ClawdBotFeatureFlags(config_path=str(flags_path))

        all_flags = flags.get_all_flags()

        # Check default flags exist
        assert "self_healing" in all_flags
        assert "sleep_compute" in all_flags
        assert "proactive_heartbeat" in all_flags
        assert "campaign_mode" in all_flags
        assert "debug_mode" in all_flags

    def test_default_flag_values(self, temp_dir):
        """Test that default flags have correct initial values."""
        from bots.shared.feature_flags import ClawdBotFeatureFlags

        flags_path = Path(temp_dir) / "feature_flags.json"
        flags = ClawdBotFeatureFlags(config_path=str(flags_path))

        # Check expected default values
        assert flags.is_enabled("self_healing") is True
        assert flags.is_enabled("sleep_compute") is True
        assert flags.is_enabled("proactive_heartbeat") is True
        assert flags.is_enabled("campaign_mode") is False
        assert flags.is_enabled("debug_mode") is False


class TestFeatureFlagsConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary flags file."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump({
                "flags": {
                    "convenience_test": {
                        "name": "convenience_test",
                        "enabled": True,
                        "rollout_percent": 100,
                        "description": "Test flag",
                        "user_overrides": {},
                        "created_at": "2026-02-02T00:00:00Z",
                        "updated_at": "2026-02-02T00:00:00Z"
                    }
                },
                "history": []
            }, f)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_is_enabled_module_function(self, temp_flags_file):
        """Test module-level is_enabled function."""
        from bots.shared import feature_flags
        from bots.shared.feature_flags import is_enabled, _reset_instance

        # Reset singleton and set custom path
        _reset_instance()

        with patch.object(
            feature_flags, 'DEFAULT_CONFIG_PATH', temp_flags_file
        ):
            _reset_instance()
            result = is_enabled("convenience_test")
            assert result is True

    def test_set_flag_module_function(self, temp_flags_file):
        """Test module-level set_flag function."""
        from bots.shared import feature_flags
        from bots.shared.feature_flags import (
            set_flag, is_enabled, _reset_instance
        )

        _reset_instance()

        with patch.object(
            feature_flags, 'DEFAULT_CONFIG_PATH', temp_flags_file
        ):
            _reset_instance()
            set_flag("new_module_flag", enabled=True, rollout_percent=100)
            assert is_enabled("new_module_flag") is True

    def test_get_all_flags_module_function(self, temp_flags_file):
        """Test module-level get_all_flags function."""
        from bots.shared import feature_flags
        from bots.shared.feature_flags import get_all_flags, _reset_instance

        _reset_instance()

        with patch.object(
            feature_flags, 'DEFAULT_CONFIG_PATH', temp_flags_file
        ):
            _reset_instance()
            all_flags = get_all_flags()
            assert "convenience_test" in all_flags
