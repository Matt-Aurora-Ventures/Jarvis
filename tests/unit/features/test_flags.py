"""
Unit tests for core/features/flags.py - FeatureFlags class.

TDD: These tests define the expected behavior before implementation.
"""

import pytest
import hashlib
from unittest.mock import MagicMock, patch


class TestFeatureFlagsBasic:
    """Test basic FeatureFlags functionality."""

    def test_is_enabled_returns_false_for_unknown_flag(self):
        """Unknown flags return False."""
        from core.features.flags import FeatureFlags

        flags = FeatureFlags()
        assert flags.is_enabled("unknown_flag") is False

    def test_is_enabled_returns_true_for_enabled_flag(self):
        """Enabled flags return True."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True}
        }

        flags = FeatureFlags(storage=storage)
        assert flags.is_enabled("test_flag") is True

    def test_is_enabled_returns_false_for_disabled_flag(self):
        """Disabled flags return False."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": False}
        }

        flags = FeatureFlags(storage=storage)
        assert flags.is_enabled("test_flag") is False

    def test_enable_flag(self):
        """Enable should turn on a flag."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": False}
        }

        flags = FeatureFlags(storage=storage)
        flags.enable("test_flag")

        assert flags.is_enabled("test_flag") is True
        storage.save.assert_called()

    def test_disable_flag(self):
        """Disable should turn off a flag."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True}
        }

        flags = FeatureFlags(storage=storage)
        flags.disable("test_flag")

        assert flags.is_enabled("test_flag") is False
        storage.save.assert_called()

    def test_enable_creates_flag_if_not_exists(self):
        """Enable should create flag if it doesn't exist."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {}

        flags = FeatureFlags(storage=storage)
        flags.enable("new_flag")

        assert flags.is_enabled("new_flag") is True


class TestPercentageRollout:
    """Test percentage-based rollout functionality."""

    def test_set_percentage(self):
        """Set percentage should update rollout percentage."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 0}
        }

        flags = FeatureFlags(storage=storage)
        flags.set_percentage("test_flag", 50)

        storage.save.assert_called()

    def test_set_percentage_clamps_to_valid_range(self):
        """Percentage should be clamped to 0-100."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 0}
        }

        flags = FeatureFlags(storage=storage)

        # Test upper bound
        flags.set_percentage("test_flag", 150)
        # Should be clamped to 100

        # Test lower bound
        flags.set_percentage("test_flag", -10)
        # Should be clamped to 0


class TestUserBasedRollout:
    """Test user-based rollout functionality."""

    def test_is_enabled_for_without_percentage_returns_base_state(self):
        """Without percentage, is_enabled_for returns base enabled state."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)
        assert flags.is_enabled_for("test_flag", "user123") is True

    def test_is_enabled_for_with_percentage_is_consistent(self):
        """Same user should always get same result for same flag."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 50}
        }

        flags = FeatureFlags(storage=storage)

        # Call multiple times, should be consistent
        result1 = flags.is_enabled_for("test_flag", "user123")
        result2 = flags.is_enabled_for("test_flag", "user123")
        result3 = flags.is_enabled_for("test_flag", "user123")

        assert result1 == result2 == result3

    def test_is_enabled_for_distributes_correctly(self):
        """With 50% rollout, roughly half of users should be enabled."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 50}
        }

        flags = FeatureFlags(storage=storage)

        enabled_count = 0
        total = 1000

        for i in range(total):
            if flags.is_enabled_for("test_flag", f"user_{i}"):
                enabled_count += 1

        ratio = enabled_count / total
        # Allow 10% tolerance
        assert 0.40 <= ratio <= 0.60, f"Expected ~50% but got {ratio*100:.1f}%"

    def test_is_enabled_for_with_zero_percentage_returns_false(self):
        """With 0% rollout, no users should be enabled."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 0}
        }

        flags = FeatureFlags(storage=storage)

        for i in range(100):
            assert flags.is_enabled_for("test_flag", f"user_{i}") is False

    def test_is_enabled_for_with_100_percentage_returns_true(self):
        """With 100% rollout, all users should be enabled."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)

        for i in range(100):
            assert flags.is_enabled_for("test_flag", f"user_{i}") is True

    def test_is_enabled_for_disabled_flag_returns_false(self):
        """Disabled flag returns False regardless of user."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": False, "percentage": 100}
        }

        flags = FeatureFlags(storage=storage)
        assert flags.is_enabled_for("test_flag", "user123") is False


class TestFlagListing:
    """Test flag listing functionality."""

    def test_list_all_flags(self):
        """Should list all registered flags."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "flag_a": {"enabled": True},
            "flag_b": {"enabled": False},
            "flag_c": {"enabled": True, "percentage": 50},
        }

        flags = FeatureFlags(storage=storage)
        all_flags = flags.list_flags()

        assert "flag_a" in all_flags
        assert "flag_b" in all_flags
        assert "flag_c" in all_flags
        assert len(all_flags) == 3

    def test_get_flag_returns_flag_config(self):
        """Should return flag configuration."""
        from core.features.flags import FeatureFlags
        from core.features.storage import JSONFlagStorage

        storage = MagicMock(spec=JSONFlagStorage)
        storage.load.return_value = {
            "test_flag": {"enabled": True, "percentage": 25, "description": "Test"}
        }

        flags = FeatureFlags(storage=storage)
        config = flags.get_flag("test_flag")

        assert config is not None
        assert config.get("enabled") is True
        assert config.get("percentage") == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
