"""
User Preferences Module for ClawdBots.

Provides per-user preference management with:
- Preference inheritance (defaults)
- Cross-bot sync via shared storage
- Change tracking
- Value validation

Storage: /root/clawdbots/user_preferences.json
"""

import json
import os
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Default storage path
DEFAULT_STORAGE_PATH = "/root/clawdbots/user_preferences.json"


class NotificationLevel(Enum):
    """Notification verbosity levels."""
    NONE = "none"
    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"


class ResponseStyle(Enum):
    """Response style preferences."""
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


# Default preference values
DEFAULT_PREFERENCES: Dict[str, Any] = {
    "notification_level": "normal",
    "language": "en",
    "timezone": "UTC",
    "response_style": "balanced",
    "enable_suggestions": True,
}

# Preference validation schema
PREFERENCE_VALIDATORS: Dict[str, Dict[str, Any]] = {
    "notification_level": {
        "type": "enum",
        "allowed_values": ["none", "minimal", "normal", "verbose"],
        "description": "Notification verbosity level",
    },
    "language": {
        "type": "string",
        "allowed_values": None,  # Any string allowed
        "description": "User interface language code (e.g., en, es, fr)",
    },
    "timezone": {
        "type": "string",
        "allowed_values": None,  # Any string allowed
        "description": "User timezone (e.g., UTC, America/New_York)",
    },
    "response_style": {
        "type": "enum",
        "allowed_values": ["concise", "balanced", "detailed"],
        "description": "Bot response verbosity style",
    },
    "enable_suggestions": {
        "type": "boolean",
        "allowed_values": [True, False],
        "description": "Enable proactive suggestions from bots",
    },
}


class PreferenceValidationError(Exception):
    """Raised when a preference value fails validation."""
    pass


@dataclass
class PreferenceSchema:
    """Schema entry for a preference."""
    key: str
    type: str
    default: Any
    allowed_values: Optional[List[Any]] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "key": self.key,
            "type": self.type,
            "default": self.default,
            "allowed_values": self.allowed_values,
            "description": self.description,
        }


@dataclass
class PreferenceChange:
    """Record of a preference change."""
    user_id: int
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "user_id": self.user_id,
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PreferenceChange":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(timezone.utc)

        return cls(
            user_id=int(data["user_id"]),
            key=data["key"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            timestamp=timestamp,
        )


class PreferenceManager:
    """
    Manages user preferences with persistence and validation.

    Supports:
    - Per-user preference storage
    - Default value inheritance
    - Value validation
    - Change tracking
    - Cross-bot synchronization via shared storage file
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the preference manager.

        Args:
            storage_path: Path to JSON storage file.
                         Defaults to /root/clawdbots/user_preferences.json
        """
        self.storage_path = storage_path or DEFAULT_STORAGE_PATH
        # Reentrant lock allows helper methods that also acquire the lock.
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "users": {},
            "changes": [],
            "last_modified": None,
        }
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        """Ensure storage file and directory exist."""
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, 'w') as f:
                json.dump({"users": {}, "changes": [], "last_modified": None}, f)

    def _load(self) -> None:
        """Load preferences from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                content = f.read().strip()
                if content:
                    self._data = json.loads(content)
                    # Ensure required keys exist
                    if "users" not in self._data:
                        self._data["users"] = {}
                    if "changes" not in self._data:
                        self._data["changes"] = []
                    if "last_modified" not in self._data:
                        self._data["last_modified"] = None
        except (json.JSONDecodeError, FileNotFoundError, TypeError) as e:
            logger.warning(f"Failed to load preferences: {e}")
            self._data = {"users": {}, "changes": [], "last_modified": None}

    def _save(self) -> None:
        """Save preferences to storage."""
        self._data["last_modified"] = datetime.now(timezone.utc).isoformat()
        with open(self.storage_path, 'w') as f:
            json.dump(self._data, f, indent=2)

    def reload(self) -> None:
        """Reload preferences from storage (for cross-bot sync)."""
        with self._lock:
            self._load()

    def _normalize_user_id(self, user_id: Union[int, str]) -> str:
        """Normalize user_id to string for storage."""
        if user_id is None or user_id == "":
            raise ValueError("user_id cannot be None or empty")
        return str(int(user_id))  # Convert to int then string to normalize

    def _validate_key(self, key: str) -> None:
        """Validate preference key."""
        if not key or not isinstance(key, str):
            raise ValueError("key cannot be None or empty")

    def _validate_value(self, key: str, value: Any) -> None:
        """
        Validate a preference value against its schema.

        Args:
            key: Preference key
            value: Value to validate

        Raises:
            PreferenceValidationError: If validation fails
        """
        if key not in PREFERENCE_VALIDATORS:
            # Unknown keys are allowed (custom preferences)
            return

        validator = PREFERENCE_VALIDATORS[key]
        pref_type = validator["type"]
        allowed = validator.get("allowed_values")

        if pref_type == "enum" and allowed is not None:
            if value not in allowed:
                raise PreferenceValidationError(
                    f"Invalid value '{value}' for {key}. "
                    f"Allowed: {allowed}"
                )
        elif pref_type == "boolean":
            if not isinstance(value, bool):
                raise PreferenceValidationError(
                    f"Invalid value '{value}' for {key}. Expected boolean."
                )
        elif pref_type == "string":
            if not isinstance(value, str):
                raise PreferenceValidationError(
                    f"Invalid value '{value}' for {key}. Expected string."
                )

    def get_preference(
        self,
        user_id: Union[int, str],
        key: str,
        default: Any = None
    ) -> Any:
        """
        Get a user preference value.

        Args:
            user_id: Telegram user ID
            key: Preference key
            default: Default value if not set (overrides DEFAULT_PREFERENCES)

        Returns:
            Preference value, falling back to defaults
        """
        self._validate_key(key)
        uid = self._normalize_user_id(user_id)

        with self._lock:
            user_prefs = self._data["users"].get(uid, {})

            if key in user_prefs:
                return user_prefs[key]

            # Fall back to system default
            if key in DEFAULT_PREFERENCES:
                return DEFAULT_PREFERENCES[key]

            # Finally, use provided default
            return default

    def set_preference(
        self,
        user_id: Union[int, str],
        key: str,
        value: Any
    ) -> None:
        """
        Set a user preference value.

        Args:
            user_id: Telegram user ID
            key: Preference key
            value: New value

        Raises:
            PreferenceValidationError: If value fails validation
        """
        self._validate_key(key)
        uid = self._normalize_user_id(user_id)

        # Validate before setting
        self._validate_value(key, value)

        with self._lock:
            # Get old value for change tracking
            old_value = self.get_preference(user_id, key)

            # Ensure user dict exists
            if uid not in self._data["users"]:
                self._data["users"][uid] = {}

            self._data["users"][uid][key] = value

            # Track change
            change = PreferenceChange(
                user_id=int(uid),
                key=key,
                old_value=old_value,
                new_value=value,
            )
            self._data["changes"].append(change.to_dict())

            self._save()

    def get_all_preferences(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get all preferences for a user, merged with defaults.

        Args:
            user_id: Telegram user ID

        Returns:
            Dict of all preferences with defaults filled in
        """
        uid = self._normalize_user_id(user_id)

        with self._lock:
            # Start with defaults
            result = dict(DEFAULT_PREFERENCES)

            # Overlay user preferences
            user_prefs = self._data["users"].get(uid, {})
            result.update(user_prefs)

            return result

    def reset_preferences(self, user_id: Union[int, str]) -> None:
        """
        Reset all preferences for a user to defaults.

        Args:
            user_id: Telegram user ID
        """
        uid = self._normalize_user_id(user_id)

        with self._lock:
            # Get current preferences for change tracking
            old_prefs = self._data["users"].get(uid, {})

            # Track changes for each reset preference
            for key, old_value in old_prefs.items():
                new_value = DEFAULT_PREFERENCES.get(key)
                change = PreferenceChange(
                    user_id=int(uid),
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                )
                self._data["changes"].append(change.to_dict())

            # Clear user preferences
            self._data["users"][uid] = {}

            self._save()

    def get_preference_schema(self) -> List[PreferenceSchema]:
        """
        Get the preference schema with available preferences.

        Returns:
            List of PreferenceSchema entries
        """
        schema = []
        for key, default in DEFAULT_PREFERENCES.items():
            validator = PREFERENCE_VALIDATORS.get(key, {})
            schema.append(PreferenceSchema(
                key=key,
                type=validator.get("type", "any"),
                default=default,
                allowed_values=validator.get("allowed_values"),
                description=validator.get("description", ""),
            ))
        return schema

    def get_preference_changes(
        self,
        user_id: Union[int, str]
    ) -> List[PreferenceChange]:
        """
        Get change history for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of PreferenceChange records, ordered by timestamp
        """
        uid = self._normalize_user_id(user_id)
        uid_int = int(uid)

        with self._lock:
            changes = [
                PreferenceChange.from_dict(c)
                for c in self._data["changes"]
                if c.get("user_id") == uid_int
            ]
            return sorted(changes, key=lambda c: c.timestamp)

    def get_all_changes(self) -> List[PreferenceChange]:
        """
        Get all change history across all users.

        Returns:
            List of all PreferenceChange records
        """
        with self._lock:
            changes = [
                PreferenceChange.from_dict(c)
                for c in self._data["changes"]
            ]
            return sorted(changes, key=lambda c: c.timestamp)

    def get_last_modified(self) -> Optional[datetime]:
        """
        Get timestamp of last modification.

        Returns:
            datetime of last modification, or None
        """
        with self._lock:
            ts = self._data.get("last_modified")
            if ts and isinstance(ts, str):
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return None


# Convenience functions for module-level access
_default_manager: Optional[PreferenceManager] = None


def get_manager() -> PreferenceManager:
    """Get or create the default preference manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PreferenceManager()
    return _default_manager


def get_preference(
    user_id: Union[int, str],
    key: str,
    default: Any = None
) -> Any:
    """Get a user preference value."""
    return get_manager().get_preference(user_id, key, default)


def set_preference(
    user_id: Union[int, str],
    key: str,
    value: Any
) -> None:
    """Set a user preference value."""
    get_manager().set_preference(user_id, key, value)


def get_all_preferences(user_id: Union[int, str]) -> Dict[str, Any]:
    """Get all preferences for a user."""
    return get_manager().get_all_preferences(user_id)


def reset_preferences(user_id: Union[int, str]) -> None:
    """Reset all preferences for a user to defaults."""
    get_manager().reset_preferences(user_id)


def get_preference_schema() -> List[PreferenceSchema]:
    """Get the preference schema."""
    return get_manager().get_preference_schema()
