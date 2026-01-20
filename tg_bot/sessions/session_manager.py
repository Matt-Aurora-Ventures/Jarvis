"""
Session Manager for interactive Telegram UI.

Manages drill-down session state for users with:
- Session creation and retrieval
- View state tracking
- Timeout-based expiration
- In-memory storage with file persistence
- User preferences (theme, timezone, history)
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default directories
DEFAULT_SESSIONS_DIR = Path.home() / ".lifeos" / "trading" / "telegram_sessions"
DEFAULT_PREFS_DIR = Path.home() / ".lifeos" / "trading" / "user_preferences"


@dataclass
class UserPreferences:
    """Persistent user preferences."""

    user_id: int
    theme: str = "dark"  # dark or light
    timezone: str = "UTC"
    last_tokens: List[str] = field(default_factory=list)  # Last 5 tokens viewed
    last_analyzed: str = ""  # Last analyzed token address
    notifications_enabled: bool = True
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        # Handle missing fields for backwards compatibility
        if "last_tokens" not in data:
            data["last_tokens"] = []
        if "last_analyzed" not in data:
            data["last_analyzed"] = ""
        if "notifications_enabled" not in data:
            data["notifications_enabled"] = True
        return cls(**data)

    def add_viewed_token(self, token_address: str) -> None:
        """Add a token to the recently viewed list."""
        if token_address in self.last_tokens:
            self.last_tokens.remove(token_address)
        self.last_tokens.insert(0, token_address)
        self.last_tokens = self.last_tokens[:5]  # Keep only 5
        self.last_analyzed = token_address
        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class UserSession:
    """Session state for a user's token analysis drill-down."""

    user_id: int
    token_address: str
    token_symbol: str
    current_view: str = "main"  # main, chart, holders, trades, signals, risk
    page: int = 1
    created_at: str = ""
    last_activity: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_activity:
            self.last_activity = now

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSession":
        return cls(**data)


class SessionManager:
    """
    Manages drill-down session state and user preferences.

    Sessions are stored in memory with optional file persistence
    and expire after timeout_minutes of inactivity.

    Preferences are persistent across sessions.
    """

    def __init__(
        self,
        sessions_dir: Optional[str] = None,
        prefs_dir: Optional[str] = None,
        timeout_minutes: int = 30,
    ):
        self.sessions_dir = Path(sessions_dir) if sessions_dir else DEFAULT_SESSIONS_DIR
        self.prefs_dir = Path(prefs_dir) if prefs_dir else DEFAULT_PREFS_DIR
        self.timeout_minutes = timeout_minutes
        self._sessions: Dict[int, UserSession] = {}
        self._preferences: Dict[int, UserPreferences] = {}

        # Create directories if they don't exist
        try:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.prefs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create directories: {e}")

    def create_session(
        self,
        user_id: int,
        token_address: str,
        token_symbol: str,
        current_view: str = "main",
    ) -> Dict[str, Any]:
        """Create a new drill-down session."""
        session = UserSession(
            user_id=user_id,
            token_address=token_address,
            token_symbol=token_symbol,
            current_view=current_view,
        )

        self._sessions[user_id] = session
        self._save_session(user_id, session)

        return session.to_dict()

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get session for user if it exists and is not expired.

        Returns None if session doesn't exist or has expired.
        """
        # Check memory first
        if user_id in self._sessions:
            session = self._sessions[user_id]

            if self._is_expired(session):
                self.clear_session(user_id)
                return None

            return session.to_dict()

        # Try loading from file
        session = self._load_session(user_id)
        if session:
            if self._is_expired(session):
                self.clear_session(user_id)
                return None

            self._sessions[user_id] = session
            return session.to_dict()

        return None

    def update_session(self, user_id: int, **updates) -> Optional[Dict[str, Any]]:
        """Update session with new values."""
        session_dict = self.get_session(user_id)

        if session_dict is None:
            return None

        session = self._sessions.get(user_id)
        if not session:
            return None

        # Update fields
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        # Update last activity
        session.last_activity = datetime.now(timezone.utc).isoformat()

        self._save_session(user_id, session)
        return session.to_dict()

    def clear_session(self, user_id: int) -> None:
        """Clear/delete a user's session."""
        # Remove from memory
        if user_id in self._sessions:
            del self._sessions[user_id]

        # Remove from disk
        session_path = self._get_session_path(user_id)
        if session_path.exists():
            try:
                session_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete session file: {e}")

    def cleanup_expired(self) -> int:
        """
        Remove all expired session files.

        Returns count of removed sessions.
        """
        removed = 0

        # Clean memory
        expired_users = [
            uid for uid, session in self._sessions.items()
            if self._is_expired(session)
        ]
        for uid in expired_users:
            self.clear_session(uid)
            removed += 1

        # Clean files
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)

                session = UserSession.from_dict(data)
                if self._is_expired(session):
                    session_file.unlink()
                    removed += 1

            except (json.JSONDecodeError, ValueError, OSError) as e:
                # Corrupted file, remove it
                try:
                    session_file.unlink()
                    removed += 1
                except OSError:
                    pass

        return removed

    def _is_expired(self, session: UserSession) -> bool:
        """Check if session is expired."""
        try:
            last_activity = datetime.fromisoformat(session.last_activity)
            now = datetime.now(timezone.utc)

            # Ensure last_activity is timezone-aware
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            age_minutes = (now - last_activity).total_seconds() / 60
            return age_minutes > self.timeout_minutes

        except (ValueError, TypeError):
            return True  # Invalid timestamp = expired

    def _get_session_path(self, user_id: int) -> Path:
        """Get path to session file for user."""
        return self.sessions_dir / f"{user_id}.json"

    def _save_session(self, user_id: int, session: UserSession) -> None:
        """Save session to disk."""
        session_path = self._get_session_path(user_id)

        try:
            with open(session_path, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save session for user {user_id}: {e}")

    def _load_session(self, user_id: int) -> Optional[UserSession]:
        """Load session from disk."""
        session_path = self._get_session_path(user_id)

        if not session_path.exists():
            return None

        try:
            with open(session_path) as f:
                data = json.load(f)
            return UserSession.from_dict(data)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to load session for user {user_id}: {e}")
            return None


    # =========================================================================
    # User Preferences Methods
    # =========================================================================

    def get_preferences(self, user_id: int) -> UserPreferences:
        """
        Get user preferences, creating defaults if not found.

        Args:
            user_id: Telegram user ID

        Returns:
            UserPreferences for the user
        """
        # Check memory first
        if user_id in self._preferences:
            return self._preferences[user_id]

        # Try loading from file
        prefs = self._load_preferences(user_id)
        if prefs:
            self._preferences[user_id] = prefs
            return prefs

        # Create default preferences
        prefs = UserPreferences(user_id=user_id)
        self._preferences[user_id] = prefs
        self._save_preferences(user_id, prefs)
        return prefs

    def update_preferences(self, user_id: int, **updates) -> UserPreferences:
        """
        Update user preferences.

        Args:
            user_id: Telegram user ID
            **updates: Fields to update

        Returns:
            Updated UserPreferences
        """
        prefs = self.get_preferences(user_id)

        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        prefs.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_preferences(user_id, prefs)
        return prefs

    def record_token_view(self, user_id: int, token_address: str) -> None:
        """
        Record that a user viewed a token.

        Args:
            user_id: Telegram user ID
            token_address: Token that was viewed
        """
        prefs = self.get_preferences(user_id)
        prefs.add_viewed_token(token_address)
        self._save_preferences(user_id, prefs)

    def get_last_token(self, user_id: int) -> Optional[str]:
        """
        Get the last token a user analyzed.

        Args:
            user_id: Telegram user ID

        Returns:
            Token address or None
        """
        prefs = self.get_preferences(user_id)
        return prefs.last_analyzed if prefs.last_analyzed else None

    def get_recent_tokens(self, user_id: int) -> List[str]:
        """
        Get the user's recently viewed tokens.

        Args:
            user_id: Telegram user ID

        Returns:
            List of up to 5 token addresses
        """
        prefs = self.get_preferences(user_id)
        return prefs.last_tokens

    def _get_prefs_path(self, user_id: int) -> Path:
        """Get path to preferences file for user."""
        return self.prefs_dir / f"{user_id}_prefs.json"

    def _save_preferences(self, user_id: int, prefs: UserPreferences) -> None:
        """Save preferences to disk."""
        prefs_path = self._get_prefs_path(user_id)

        try:
            with open(prefs_path, "w") as f:
                json.dump(prefs.to_dict(), f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save preferences for user {user_id}: {e}")

    def _load_preferences(self, user_id: int) -> Optional[UserPreferences]:
        """Load preferences from disk."""
        prefs_path = self._get_prefs_path(user_id)

        if not prefs_path.exists():
            return None

        try:
            with open(prefs_path) as f:
                data = json.load(f)
            return UserPreferences.from_dict(data)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to load preferences for user {user_id}: {e}")
            return None


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


__all__ = [
    "SessionManager",
    "get_session_manager",
    "UserSession",
    "UserPreferences",
]
