"""
Auto-Moderation Actions - Autonomous enforcement of community guidelines.

Actions:
- WARNING: Log but allow (first offense)
- MUTE: Ignore user for 1 hour
- BAN: Block user from platform
- DELETE: Remove offending content
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ModerationAction(Enum):
    """Actions Jarvis can take."""
    LOG = "log"          # Just record
    WARN = "warn"        # Notify user
    MUTE = "mute"        # Ignore for 1 hour
    BAN = "ban"          # Block permanently
    DELETE = "delete"    # Remove message
    ESCALATE = "escalate"  # Alert admin


@dataclass
class ModerationEvent:
    """Record of a moderation action."""
    user_id: int
    username: str
    platform: str  # "telegram" or "twitter"
    content: str
    toxicity_level: str
    action_taken: ModerationAction
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    auto_generated: bool = True


class AutoActions:
    """
    Autonomous moderation engine.

    Makes real-time decisions to protect communities:
    - Blocks scams automatically
    - Mutes spam
    - Escalates to admin when needed
    """

    # Action matrix: ToxicityLevel -> ModerationAction
    ACTION_MATRIX = {
        "CLEAN": ModerationAction.LOG,
        "WARNING": ModerationAction.WARN,
        "MODERATE": ModerationAction.MUTE,
        "SEVERE": ModerationAction.BAN,
        "CRITICAL": ModerationAction.BAN,
    }

    def __init__(self, data_dir: str = "data/moderation"):
        """Initialize moderation system."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.muted_users: Dict[int, datetime] = {}  # user_id -> unmute_time
        self.banned_users: Dict[int, str] = {}  # user_id -> ban_reason
        self.warnings: Dict[int, List[ModerationEvent]] = {}  # user_id -> [events]
        self.history: List[ModerationEvent] = []

        self._load_state()

    def should_moderate(self, user_id: int, toxicity_level: str) -> Tuple[bool, ModerationAction]:
        """
        Determine if content should be moderated.

        Returns:
            (should_moderate, action)
        """
        # Check if user is muted
        if user_id in self.muted_users:
            if datetime.now(timezone.utc) < self.muted_users[user_id]:
                logger.info(f"User {user_id} is muted")
                return (True, ModerationAction.MUTE)
            else:
                # Mute expired
                del self.muted_users[user_id]

        # Check if user is banned
        if user_id in self.banned_users:
            logger.warning(f"User {user_id} attempted to post while banned")
            return (True, ModerationAction.BAN)

        # Get action for toxicity level
        action = self.ACTION_MATRIX.get(toxicity_level, ModerationAction.LOG)
        should_moderate = action != ModerationAction.LOG

        return (should_moderate, action)

    async def execute_action(
        self,
        user_id: int,
        username: str,
        platform: str,
        content: str,
        toxicity_level: str,
        action: ModerationAction,
        reason: str = ""
    ) -> bool:
        """
        Execute a moderation action.

        Returns:
            True if action executed successfully
        """
        try:
            event = ModerationEvent(
                user_id=user_id,
                username=username,
                platform=platform,
                content=content[:100],  # Truncate for storage
                toxicity_level=toxicity_level,
                action_taken=action,
                reason=reason
            )

            # Execute action
            if action == ModerationAction.LOG:
                logger.info(f"Moderation event: {username} - {toxicity_level}")

            elif action == ModerationAction.WARN:
                logger.warning(f"Warning issued to {username}: {reason}")
                if user_id not in self.warnings:
                    self.warnings[user_id] = []
                self.warnings[user_id].append(event)

                # 3 warnings = mute
                if len(self.warnings[user_id]) >= 3:
                    await self._execute_mute(user_id, username, platform, "3 strikes")
                    event.action_taken = ModerationAction.MUTE

            elif action == ModerationAction.MUTE:
                await self._execute_mute(user_id, username, platform, reason)

            elif action == ModerationAction.BAN:
                await self._execute_ban(user_id, username, platform, reason)

            elif action == ModerationAction.DELETE:
                logger.info(f"Deleted content from {username}: {reason}")

            elif action == ModerationAction.ESCALATE:
                logger.critical(f"ESCALATED: {username} - {reason}")

            # Record event
            self.history.append(event)
            self._save_state()

            return True

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    async def _execute_mute(self, user_id: int, username: str, platform: str, reason: str):
        """Mute user for 1 hour."""
        unmute_time = datetime.now(timezone.utc) + timedelta(hours=1)
        self.muted_users[user_id] = unmute_time
        logger.warning(f"Muted {username} ({platform}) until {unmute_time.isoformat()}: {reason}")

    async def _execute_ban(self, user_id: int, username: str, platform: str, reason: str):
        """Ban user permanently."""
        self.banned_users[user_id] = reason
        logger.critical(f"Banned {username} ({platform}): {reason}")

    def get_warnings(self, user_id: int) -> List[ModerationEvent]:
        """Get user's warning history."""
        return self.warnings.get(user_id, [])

    def is_muted(self, user_id: int) -> bool:
        """Check if user is currently muted."""
        if user_id not in self.muted_users:
            return False

        if datetime.now(timezone.utc) < self.muted_users[user_id]:
            return True

        # Mute expired
        del self.muted_users[user_id]
        return False

    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned."""
        return user_id in self.banned_users

    def get_mute_time(self, user_id: int) -> Optional[datetime]:
        """Get when user will be unmuted."""
        return self.muted_users.get(user_id)

    def appeal_ban(self, user_id: int, appeal_reason: str) -> bool:
        """User appeals ban (requires admin review)."""
        if user_id in self.banned_users:
            logger.info(f"Ban appeal from {user_id}: {appeal_reason}")
            # In production, this would go to admin review queue
            return True
        return False

    def _save_state(self):
        """Persist moderation state."""
        try:
            state = {
                "muted_users": {
                    k: v.isoformat() for k, v in self.muted_users.items()
                },
                "banned_users": self.banned_users,
                "history_count": len(self.history),
            }

            with open(self.data_dir / "moderation_state.json", "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save moderation state: {e}")

    def _load_state(self):
        """Load previous moderation state."""
        try:
            state_file = self.data_dir / "moderation_state.json"
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)

                # Restore muted users (only if still muted)
                for user_id_str, unmute_time_str in state.get("muted_users", {}).items():
                    user_id = int(user_id_str)
                    unmute_time = datetime.fromisoformat(unmute_time_str)

                    if unmute_time > datetime.now(timezone.utc):
                        self.muted_users[user_id] = unmute_time

                # Restore banned users
                self.banned_users = {int(k): v for k, v in state.get("banned_users", {}).items()}

                logger.info(f"Loaded moderation state: {len(self.muted_users)} muted, {len(self.banned_users)} banned")

        except Exception as e:
            logger.error(f"Failed to load moderation state: {e}")

    def get_statistics(self) -> Dict:
        """Get moderation statistics."""
        return {
            "total_events": len(self.history),
            "currently_muted": len(self.muted_users),
            "currently_banned": len(self.banned_users),
            "total_warnings_issued": sum(len(v) for v in self.warnings.values()),
        }
