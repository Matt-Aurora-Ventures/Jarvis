"""
ReasoningState - Per-user/session state management

Handles:
- Per-user preference storage
- State persistence to database
- Session management
- Global defaults
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Default values
DEFAULT_THINKING_LEVEL = "low"
DEFAULT_REASONING_MODE = "off"
DEFAULT_VERBOSE_MODE = "off"


@dataclass
class ReasoningState:
    """
    State container for reasoning preferences.

    Stores per-user or per-session reasoning settings.
    """

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    thinking_level: str = DEFAULT_THINKING_LEVEL
    reasoning_mode: str = DEFAULT_REASONING_MODE
    verbose_mode: str = DEFAULT_VERBOSE_MODE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize state to dict.

        Returns:
            Dict representation of state
        """
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "thinking_level": self.thinking_level,
            "reasoning_mode": self.reasoning_mode,
            "verbose_mode": self.verbose_mode,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReasoningState:
        """
        Create state from dict.

        Args:
            data: Dict with state data

        Returns:
            ReasoningState instance
        """
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        # Parse datetime strings if needed
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return cls(
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            thinking_level=data.get("thinking_level", DEFAULT_THINKING_LEVEL),
            reasoning_mode=data.get("reasoning_mode", DEFAULT_REASONING_MODE),
            verbose_mode=data.get("verbose_mode", DEFAULT_VERBOSE_MODE),
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
        )


class StateManager:
    """
    Manager for reasoning states across users and sessions.

    Provides:
    - Per-user state storage
    - State persistence
    - Global defaults
    - Engine factory
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize StateManager.

        Args:
            storage_path: Optional path for state persistence
        """
        self._states: Dict[str, ReasoningState] = {}
        self._global_defaults = {
            "thinking_level": DEFAULT_THINKING_LEVEL,
            "reasoning_mode": DEFAULT_REASONING_MODE,
            "verbose_mode": DEFAULT_VERBOSE_MODE,
        }
        self._storage_path = storage_path or Path.home() / ".lifeos" / "reasoning_state.json"
        self._modified_users: set = set()

    def get_state(self, user_id: str) -> ReasoningState:
        """
        Get state for a user, creating default if not exists.

        Args:
            user_id: User identifier

        Returns:
            ReasoningState for user
        """
        if user_id not in self._states:
            # Create new state with global defaults
            self._states[user_id] = ReasoningState(
                user_id=user_id,
                thinking_level=self._global_defaults["thinking_level"],
                reasoning_mode=self._global_defaults["reasoning_mode"],
                verbose_mode=self._global_defaults["verbose_mode"],
            )
            logger.debug(f"Created new state for user {user_id}")

        return self._states[user_id]

    def set_thinking_level(self, user_id: str, level: str) -> None:
        """
        Set thinking level for a user.

        Args:
            user_id: User identifier
            level: Thinking level
        """
        state = self.get_state(user_id)
        state.thinking_level = level.lower()
        state.updated_at = datetime.now(timezone.utc)
        self._modified_users.add(user_id)
        logger.info(f"User {user_id} thinking level set to {level}")

    def set_reasoning_mode(self, user_id: str, mode: str) -> None:
        """
        Set reasoning mode for a user.

        Args:
            user_id: User identifier
            mode: Reasoning mode
        """
        state = self.get_state(user_id)
        state.reasoning_mode = mode.lower()
        state.updated_at = datetime.now(timezone.utc)
        self._modified_users.add(user_id)
        logger.info(f"User {user_id} reasoning mode set to {mode}")

    def set_verbose_mode(self, user_id: str, mode: str) -> None:
        """
        Set verbose mode for a user.

        Args:
            user_id: User identifier
            mode: Verbose mode
        """
        state = self.get_state(user_id)
        state.verbose_mode = mode.lower()
        state.updated_at = datetime.now(timezone.utc)
        self._modified_users.add(user_id)
        logger.info(f"User {user_id} verbose mode set to {mode}")

    def set_global_defaults(
        self,
        thinking_level: Optional[str] = None,
        reasoning_mode: Optional[str] = None,
        verbose_mode: Optional[str] = None,
    ) -> None:
        """
        Set global default values for new users.

        Args:
            thinking_level: Default thinking level
            reasoning_mode: Default reasoning mode
            verbose_mode: Default verbose mode
        """
        if thinking_level is not None:
            self._global_defaults["thinking_level"] = thinking_level.lower()
        if reasoning_mode is not None:
            self._global_defaults["reasoning_mode"] = reasoning_mode.lower()
        if verbose_mode is not None:
            self._global_defaults["verbose_mode"] = verbose_mode.lower()
        logger.info(f"Global defaults updated: {self._global_defaults}")

    def reset_state(self, user_id: str) -> None:
        """
        Reset a user's state to defaults.

        Args:
            user_id: User identifier
        """
        if user_id in self._states:
            del self._states[user_id]
            self._modified_users.discard(user_id)
        logger.info(f"State reset for user {user_id}")

    def reset_all(self) -> None:
        """Reset all user states to defaults."""
        self._states.clear()
        self._modified_users.clear()
        logger.info("All states reset to defaults")

    def get_engine(self, user_id: str) -> "ReasoningEngine":
        """
        Get a ReasoningEngine configured for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Configured ReasoningEngine
        """
        from core.reasoning.engine import ReasoningEngine

        state = self.get_state(user_id)
        return ReasoningEngine(
            thinking_level=state.thinking_level,
            reasoning_mode=state.reasoning_mode,
            verbose_mode=state.verbose_mode,
        )

    async def save_state(self, user_id: str) -> None:
        """
        Save a user's state to persistent storage.

        Args:
            user_id: User identifier
        """
        try:
            # Ensure directory exists
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing data
            all_states = {}
            if self._storage_path.exists():
                try:
                    all_states = json.loads(self._storage_path.read_text())
                except (json.JSONDecodeError, IOError):
                    all_states = {}

            # Update with user's state
            if user_id in self._states:
                all_states[user_id] = self._states[user_id].to_dict()

            # Save back
            self._storage_path.write_text(json.dumps(all_states, indent=2, default=str))
            self._modified_users.discard(user_id)
            logger.debug(f"Saved state for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to save state for user {user_id}: {e}")

    async def load_state(self, user_id: str) -> None:
        """
        Load a user's state from persistent storage.

        Args:
            user_id: User identifier
        """
        try:
            if not self._storage_path.exists():
                return

            all_states = json.loads(self._storage_path.read_text())
            if user_id in all_states:
                self._states[user_id] = ReasoningState.from_dict(all_states[user_id])
                logger.debug(f"Loaded state for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to load state for user {user_id}: {e}")

    async def save_all(self) -> None:
        """Save all modified states to persistent storage."""
        for user_id in list(self._modified_users):
            await self.save_state(user_id)
        logger.info(f"Saved states for {len(self._modified_users)} users")


# Singleton instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """
    Get singleton StateManager instance.

    Returns:
        StateManager singleton
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def reset_state_manager() -> None:
    """Reset the singleton StateManager (for testing)."""
    global _state_manager
    _state_manager = None
