"""
Tests for bots/shared/user_preferences.py

User preferences module for ClawdBots (Jarvis/CTO, Matt/COO, Friday/CMO).

Tests cover:
- PreferenceManager initialization and storage
- Getting/setting preferences with defaults
- Preference inheritance (defaults)
- Preference validation
- Cross-bot sync support
- Change tracking
- Preference schema
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.user_preferences import (
    PreferenceManager,
    NotificationLevel,
    ResponseStyle,
    PreferenceSchema,
    PreferenceChange,
    PreferenceValidationError,
    DEFAULT_PREFERENCES,
)


class TestNotificationLevel:
    """Test NotificationLevel enum."""

    def test_none_level(self):
        """Should have none notification level."""
        assert NotificationLevel.NONE.value == "none"

    def test_minimal_level(self):
        """Should have minimal notification level."""
        assert NotificationLevel.MINIMAL.value == "minimal"

    def test_normal_level(self):
        """Should have normal notification level."""
        assert NotificationLevel.NORMAL.value == "normal"

    def test_verbose_level(self):
        """Should have verbose notification level."""
        assert NotificationLevel.VERBOSE.value == "verbose"


class TestResponseStyle:
    """Test ResponseStyle enum."""

    def test_concise_style(self):
        """Should have concise response style."""
        assert ResponseStyle.CONCISE.value == "concise"

    def test_balanced_style(self):
        """Should have balanced response style."""
        assert ResponseStyle.BALANCED.value == "balanced"

    def test_detailed_style(self):
        """Should have detailed response style."""
        assert ResponseStyle.DETAILED.value == "detailed"


class TestPreferenceSchema:
    """Test PreferenceSchema dataclass."""

    def test_create_schema(self):
        """Should create preference schema entry."""
        schema = PreferenceSchema(
            key="notification_level",
            type="enum",
            default="normal",
            allowed_values=["none", "minimal", "normal", "verbose"],
            description="Notification verbosity level",
        )
        assert schema.key == "notification_level"
        assert schema.type == "enum"
        assert schema.default == "normal"
        assert "verbose" in schema.allowed_values

    def test_to_dict(self):
        """Should serialize schema to dict."""
        schema = PreferenceSchema(
            key="language",
            type="string",
            default="en",
            allowed_values=["en", "es", "fr", "de"],
            description="User interface language",
        )
        data = schema.to_dict()
        assert data["key"] == "language"
        assert data["type"] == "string"
        assert data["default"] == "en"


class TestPreferenceChange:
    """Test PreferenceChange dataclass."""

    def test_create_change(self):
        """Should create preference change record."""
        change = PreferenceChange(
            user_id=123456,
            key="notification_level",
            old_value="normal",
            new_value="verbose",
        )
        assert change.user_id == 123456
        assert change.key == "notification_level"
        assert change.old_value == "normal"
        assert change.new_value == "verbose"
        assert change.timestamp is not None

    def test_to_dict(self):
        """Should serialize change to dict."""
        change = PreferenceChange(
            user_id=789,
            key="timezone",
            old_value="UTC",
            new_value="America/New_York",
        )
        data = change.to_dict()
        assert data["user_id"] == 789
        assert data["key"] == "timezone"
        assert data["old_value"] == "UTC"
        assert data["new_value"] == "America/New_York"
        assert "timestamp" in data


class TestDefaultPreferences:
    """Test default preference values."""

    def test_notification_level_default(self):
        """Notification level should default to normal."""
        assert DEFAULT_PREFERENCES["notification_level"] == "normal"

    def test_language_default(self):
        """Language should default to en."""
        assert DEFAULT_PREFERENCES["language"] == "en"

    def test_timezone_default(self):
        """Timezone should default to UTC."""
        assert DEFAULT_PREFERENCES["timezone"] == "UTC"

    def test_response_style_default(self):
        """Response style should default to balanced."""
        assert DEFAULT_PREFERENCES["response_style"] == "balanced"

    def test_enable_suggestions_default(self):
        """Enable suggestions should default to True."""
        assert DEFAULT_PREFERENCES["enable_suggestions"] is True


class TestPreferenceManager:
    """Test PreferenceManager class."""

    @pytest.fixture
    def temp_prefs_file(self):
        """Create temporary preferences file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def manager(self, temp_prefs_file):
        """Create PreferenceManager with temp storage file."""
        return PreferenceManager(storage_path=temp_prefs_file)

    # Initialization tests

    def test_init_creates_storage_file(self, temp_prefs_file):
        """Should initialize storage file on creation."""
        os.unlink(temp_prefs_file)  # Remove the file
        manager = PreferenceManager(storage_path=temp_prefs_file)
        assert os.path.exists(temp_prefs_file)

    def test_init_loads_existing_preferences(self, temp_prefs_file):
        """Should load existing preferences on init."""
        # Pre-populate preferences
        prefs = {
            "users": {
                "123": {
                    "notification_level": "verbose",
                    "language": "es",
                }
            },
            "changes": [],
        }
        with open(temp_prefs_file, 'w') as f:
            json.dump(prefs, f)

        manager = PreferenceManager(storage_path=temp_prefs_file)
        assert manager.get_preference(123, "notification_level") == "verbose"
        assert manager.get_preference(123, "language") == "es"

    # Get preference tests

    def test_get_preference_with_default(self, manager):
        """Should return default when preference not set."""
        value = manager.get_preference(999, "notification_level")
        assert value == "normal"  # Default value

    def test_get_preference_custom_default(self, manager):
        """Should return custom default when preference not set."""
        value = manager.get_preference(999, "custom_key", default="custom_default")
        assert value == "custom_default"

    def test_get_preference_user_value(self, manager):
        """Should return user's set value."""
        manager.set_preference(123, "notification_level", "verbose")
        value = manager.get_preference(123, "notification_level")
        assert value == "verbose"

    def test_get_preference_respects_inheritance(self, manager):
        """Should inherit from defaults when not explicitly set."""
        # User has some preferences but not all
        manager.set_preference(456, "language", "fr")

        # Should get user's value for language
        assert manager.get_preference(456, "language") == "fr"
        # Should inherit default for timezone
        assert manager.get_preference(456, "timezone") == "UTC"

    # Set preference tests

    def test_set_preference(self, manager):
        """Should set user preference."""
        manager.set_preference(123, "timezone", "America/New_York")
        assert manager.get_preference(123, "timezone") == "America/New_York"

    def test_set_preference_persists(self, temp_prefs_file):
        """Should persist preference changes."""
        manager1 = PreferenceManager(storage_path=temp_prefs_file)
        manager1.set_preference(123, "language", "de")

        # Create new manager instance (simulates restart)
        manager2 = PreferenceManager(storage_path=temp_prefs_file)
        assert manager2.get_preference(123, "language") == "de"

    def test_set_preference_tracks_change(self, manager):
        """Should track preference changes."""
        manager.set_preference(789, "response_style", "concise")
        manager.set_preference(789, "response_style", "detailed")

        changes = manager.get_preference_changes(789)
        assert len(changes) >= 1
        # Find the change for response_style
        style_changes = [c for c in changes if c.key == "response_style"]
        assert len(style_changes) >= 1
        assert style_changes[-1].new_value == "detailed"

    # Validation tests

    def test_set_preference_validates_enum(self, manager):
        """Should validate enum preference values."""
        with pytest.raises(PreferenceValidationError):
            manager.set_preference(123, "notification_level", "invalid_level")

    def test_set_preference_validates_response_style(self, manager):
        """Should validate response style values."""
        with pytest.raises(PreferenceValidationError):
            manager.set_preference(123, "response_style", "ultra_detailed")

    def test_set_preference_validates_boolean(self, manager):
        """Should validate boolean preference values."""
        with pytest.raises(PreferenceValidationError):
            manager.set_preference(123, "enable_suggestions", "yes")  # Should be bool

    def test_set_preference_allows_valid_enum(self, manager):
        """Should allow valid enum values."""
        manager.set_preference(123, "notification_level", "verbose")
        assert manager.get_preference(123, "notification_level") == "verbose"

    def test_set_preference_allows_valid_boolean(self, manager):
        """Should allow valid boolean values."""
        manager.set_preference(123, "enable_suggestions", False)
        assert manager.get_preference(123, "enable_suggestions") is False

    # Get all preferences tests

    def test_get_all_preferences_new_user(self, manager):
        """Should return defaults for new user."""
        prefs = manager.get_all_preferences(999)
        assert prefs["notification_level"] == "normal"
        assert prefs["language"] == "en"
        assert prefs["timezone"] == "UTC"
        assert prefs["response_style"] == "balanced"
        assert prefs["enable_suggestions"] is True

    def test_get_all_preferences_with_custom(self, manager):
        """Should merge user preferences with defaults."""
        manager.set_preference(123, "language", "es")
        manager.set_preference(123, "timezone", "Europe/Madrid")

        prefs = manager.get_all_preferences(123)
        assert prefs["language"] == "es"
        assert prefs["timezone"] == "Europe/Madrid"
        # Defaults should still be present
        assert prefs["notification_level"] == "normal"
        assert prefs["response_style"] == "balanced"

    # Reset preferences tests

    def test_reset_preferences(self, manager):
        """Should reset all user preferences to defaults."""
        manager.set_preference(123, "language", "de")
        manager.set_preference(123, "timezone", "Europe/Berlin")
        manager.set_preference(123, "notification_level", "verbose")

        manager.reset_preferences(123)

        prefs = manager.get_all_preferences(123)
        assert prefs["language"] == "en"
        assert prefs["timezone"] == "UTC"
        assert prefs["notification_level"] == "normal"

    def test_reset_preferences_tracks_changes(self, manager):
        """Should track reset as changes."""
        manager.set_preference(456, "language", "fr")
        manager.reset_preferences(456)

        changes = manager.get_preference_changes(456)
        reset_changes = [c for c in changes if c.new_value == "en" and c.key == "language"]
        assert len(reset_changes) >= 1

    # Schema tests

    def test_get_preference_schema(self, manager):
        """Should return complete preference schema."""
        schema = manager.get_preference_schema()
        assert isinstance(schema, list)
        assert len(schema) >= 5  # At least 5 default preferences

        # Check required schema entries exist
        keys = [s.key for s in schema]
        assert "notification_level" in keys
        assert "language" in keys
        assert "timezone" in keys
        assert "response_style" in keys
        assert "enable_suggestions" in keys

    def test_schema_includes_types(self, manager):
        """Schema entries should have type information."""
        schema = manager.get_preference_schema()
        notification = next(s for s in schema if s.key == "notification_level")
        assert notification.type == "enum"
        assert notification.allowed_values is not None

    def test_schema_includes_descriptions(self, manager):
        """Schema entries should have descriptions."""
        schema = manager.get_preference_schema()
        for entry in schema:
            assert entry.description is not None
            assert len(entry.description) > 0

    # Cross-bot sync tests

    def test_sync_preferences_across_bots(self, temp_prefs_file):
        """Multiple managers should see same preferences."""
        manager1 = PreferenceManager(storage_path=temp_prefs_file)
        manager2 = PreferenceManager(storage_path=temp_prefs_file)

        manager1.set_preference(123, "language", "ja")

        # Force reload in manager2
        manager2.reload()
        assert manager2.get_preference(123, "language") == "ja"

    def test_get_sync_timestamp(self, manager):
        """Should track last sync timestamp."""
        manager.set_preference(123, "language", "ko")
        ts = manager.get_last_modified()
        assert ts is not None
        assert isinstance(ts, datetime)

    # Change tracking tests

    def test_get_preference_changes_empty(self, manager):
        """Should return empty list for user with no changes."""
        changes = manager.get_preference_changes(999)
        assert changes == []

    def test_get_preference_changes_ordered(self, manager):
        """Changes should be ordered by timestamp."""
        manager.set_preference(123, "language", "es")
        manager.set_preference(123, "language", "fr")
        manager.set_preference(123, "language", "de")

        changes = manager.get_preference_changes(123)
        lang_changes = [c for c in changes if c.key == "language"]

        # Should be in chronological order
        for i in range(len(lang_changes) - 1):
            assert lang_changes[i].timestamp <= lang_changes[i + 1].timestamp

    def test_get_all_changes(self, manager):
        """Should get all changes across all users."""
        manager.set_preference(111, "language", "es")
        manager.set_preference(222, "timezone", "Asia/Tokyo")
        manager.set_preference(333, "notification_level", "verbose")

        all_changes = manager.get_all_changes()
        assert len(all_changes) >= 3

        user_ids = {c.user_id for c in all_changes}
        assert 111 in user_ids
        assert 222 in user_ids
        assert 333 in user_ids

    # Edge cases

    def test_user_id_as_string(self, manager):
        """Should handle user_id as string or int."""
        manager.set_preference("123", "language", "pt")
        # Should work with int as well
        assert manager.get_preference(123, "language") == "pt"

    def test_user_id_as_int(self, manager):
        """Should handle user_id as int."""
        manager.set_preference(456, "language", "pt")
        # Should work with string as well
        assert manager.get_preference("456", "language") == "pt"

    def test_unknown_preference_key(self, manager):
        """Should allow custom/unknown preference keys."""
        manager.set_preference(123, "custom_preference", "custom_value")
        assert manager.get_preference(123, "custom_preference") == "custom_value"

    def test_preference_value_types(self, manager):
        """Should preserve value types (string, int, bool, list)."""
        manager.set_preference(123, "string_pref", "hello")
        manager.set_preference(123, "int_pref", 42)
        manager.set_preference(123, "bool_pref", True)
        manager.set_preference(123, "list_pref", ["a", "b", "c"])

        assert manager.get_preference(123, "string_pref") == "hello"
        assert manager.get_preference(123, "int_pref") == 42
        assert manager.get_preference(123, "bool_pref") is True
        assert manager.get_preference(123, "list_pref") == ["a", "b", "c"]

    def test_concurrent_writes(self, temp_prefs_file):
        """Should handle concurrent writes safely."""
        manager1 = PreferenceManager(storage_path=temp_prefs_file)
        manager2 = PreferenceManager(storage_path=temp_prefs_file)

        # Both write different users
        manager1.set_preference(111, "language", "en")
        manager2.set_preference(222, "language", "es")

        # Both should be persisted
        manager3 = PreferenceManager(storage_path=temp_prefs_file)
        assert manager3.get_preference(111, "language") == "en"
        assert manager3.get_preference(222, "language") == "es"

    def test_empty_user_id(self, manager):
        """Should handle empty/None user_id gracefully."""
        with pytest.raises((ValueError, TypeError)):
            manager.get_preference(None, "language")

    def test_empty_key(self, manager):
        """Should handle empty key gracefully."""
        with pytest.raises((ValueError, TypeError)):
            manager.get_preference(123, "")

    # Storage path tests

    def test_default_storage_path(self):
        """Should use default storage path if not specified."""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock()):
                manager = PreferenceManager()
                assert manager.storage_path == "/root/clawdbots/user_preferences.json"
