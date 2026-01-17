"""
Auto-responder service for Telegram.

When admin is away, automatically responds to messages with a custom message
and estimated return time. Useful for autonomous operation.

Commands:
- /away [duration] [message] - Enable auto-responder
- /back - Disable auto-responder
- /awaystatus - Check auto-responder status

Example:
  /away 2h Going for lunch
  /away 30m Quick break
  /back
"""

import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# State file for persistence across restarts
STATE_FILE = Path.home() / ".lifeos" / "telegram" / "away_status.json"


class AutoResponder:
    """
    Telegram auto-responder for when admin is away.

    Features:
    - Configurable away message
    - Estimated return time display
    - Rate limiting to avoid spam
    - Persistence across restarts
    """

    def __init__(self, rate_limit_minutes: int = 5):
        self.rate_limit_minutes = rate_limit_minutes
        self._enabled = False
        self._message = "The admin is currently away."
        self._return_time: Optional[datetime] = None
        self._enabled_at: Optional[datetime] = None
        self._last_response: Dict[int, datetime] = {}  # chat_id -> last response time

        # Load state from file
        self._load_state()

    def _load_state(self):
        """Load state from file if exists."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            if STATE_FILE.exists():
                with open(STATE_FILE) as f:
                    state = json.load(f)
                    self._enabled = state.get("enabled", False)
                    self._message = state.get("message", "The admin is currently away.")

                    if state.get("return_time"):
                        self._return_time = datetime.fromisoformat(state["return_time"])
                        # If return time passed, disable
                        if self._return_time < datetime.now():
                            self._enabled = False
                            self._return_time = None
                            self._save_state()

                    if state.get("enabled_at"):
                        self._enabled_at = datetime.fromisoformat(state["enabled_at"])

                    logger.info(f"Auto-responder state loaded (enabled: {self._enabled})")
        except Exception as e:
            logger.warning(f"Failed to load auto-responder state: {e}")

    def _save_state(self):
        """Save state to file."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "enabled": self._enabled,
                "message": self._message,
                "return_time": self._return_time.isoformat() if self._return_time else None,
                "enabled_at": self._enabled_at.isoformat() if self._enabled_at else None,
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save auto-responder state: {e}")

    @property
    def is_enabled(self) -> bool:
        """Check if auto-responder is enabled."""
        if not self._enabled:
            return False

        # Auto-disable if return time passed
        if self._return_time and self._return_time < datetime.now():
            self._enabled = False
            self._return_time = None
            self._save_state()
            logger.info("Auto-responder auto-disabled (return time passed)")
            return False

        return True

    def enable(self, message: str = None, duration_minutes: int = None) -> str:
        """
        Enable auto-responder.

        Args:
            message: Custom away message
            duration_minutes: How long to be away (optional)

        Returns:
            Confirmation message
        """
        self._enabled = True
        self._enabled_at = datetime.now()

        if message:
            self._message = message
        else:
            self._message = "The admin is currently away."

        if duration_minutes:
            self._return_time = datetime.now() + timedelta(minutes=duration_minutes)
        else:
            self._return_time = None

        self._save_state()

        response = "Auto-responder enabled."
        if self._return_time:
            response += f" Expected back at {self._return_time.strftime('%H:%M')}."
        return response

    def disable(self) -> str:
        """Disable auto-responder."""
        was_enabled = self._enabled
        self._enabled = False
        self._return_time = None
        self._enabled_at = None
        self._last_response.clear()
        self._save_state()

        if was_enabled:
            return "Auto-responder disabled. Welcome back!"
        return "Auto-responder was not enabled."

    def get_status(self) -> Dict[str, Any]:
        """Get current auto-responder status."""
        status = {
            "enabled": self.is_enabled,
            "message": self._message if self._enabled else None,
        }

        if self._return_time:
            status["return_time"] = self._return_time.strftime("%H:%M")
            remaining = self._return_time - datetime.now()
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() / 60)
                status["remaining"] = f"{mins}m" if mins < 60 else f"{mins // 60}h {mins % 60}m"

        if self._enabled_at:
            status["enabled_at"] = self._enabled_at.strftime("%H:%M")

        return status

    def should_respond(self, chat_id: int) -> bool:
        """
        Check if we should auto-respond to this chat.

        Implements rate limiting to avoid spam.
        """
        if not self.is_enabled:
            return False

        # Rate limit: don't respond to same chat too frequently
        last = self._last_response.get(chat_id)
        if last:
            elapsed = (datetime.now() - last).total_seconds() / 60
            if elapsed < self.rate_limit_minutes:
                return False

        return True

    def get_response(self, chat_id: int) -> Optional[str]:
        """
        Get auto-response for a chat.

        Returns None if should not respond (rate limited or disabled).
        """
        if not self.should_respond(chat_id):
            return None

        # Record response time for rate limiting
        self._last_response[chat_id] = datetime.now()

        # Build response
        response = f"{self._message}"

        if self._return_time:
            remaining = self._return_time - datetime.now()
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() / 60)
                if mins < 60:
                    response += f"\nExpected back in ~{mins} minutes."
                else:
                    hours = mins // 60
                    mins = mins % 60
                    response += f"\nExpected back in ~{hours}h {mins}m."
            else:
                response += "\nShould be back soon."

        response += "\n\nThis is an automated response."
        return response


def parse_duration(text: str) -> Optional[int]:
    """
    Parse duration string to minutes.

    Examples:
        "30m" -> 30
        "2h" -> 120
        "1h30m" -> 90
        "90" -> 90 (assumed minutes)
    """
    text = text.lower().strip()

    # Pattern: 1h30m or 1h 30m
    match = re.match(r"(\d+)h\s*(\d+)?m?", text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        return hours * 60 + minutes

    # Pattern: 30m
    match = re.match(r"(\d+)m", text)
    if match:
        return int(match.group(1))

    # Pattern: 2h
    match = re.match(r"(\d+)h", text)
    if match:
        return int(match.group(1)) * 60

    # Just a number (assume minutes)
    match = re.match(r"(\d+)", text)
    if match:
        return int(match.group(1))

    return None


# Singleton
_auto_responder: Optional[AutoResponder] = None


def get_auto_responder() -> AutoResponder:
    """Get singleton auto-responder instance."""
    global _auto_responder
    if _auto_responder is None:
        _auto_responder = AutoResponder()
    return _auto_responder
