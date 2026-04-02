"""
Timezone Service for Telegram Bot.

Provides timezone-aware time formatting for users.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List

try:
    import zoneinfo
    ZONEINFO_AVAILABLE = True
except ImportError:
    ZONEINFO_AVAILABLE = False

logger = logging.getLogger(__name__)


# Common timezones for quick selection
COMMON_TIMEZONES = [
    # US
    ("America/New_York", "US Eastern (ET)", "UTC-5/-4"),
    ("America/Chicago", "US Central (CT)", "UTC-6/-5"),
    ("America/Denver", "US Mountain (MT)", "UTC-7/-6"),
    ("America/Los_Angeles", "US Pacific (PT)", "UTC-8/-7"),
    # Europe
    ("Europe/London", "UK (GMT/BST)", "UTC+0/+1"),
    ("Europe/Paris", "Central Europe (CET)", "UTC+1/+2"),
    ("Europe/Berlin", "Germany (CET)", "UTC+1/+2"),
    # Asia
    ("Asia/Tokyo", "Japan (JST)", "UTC+9"),
    ("Asia/Shanghai", "China (CST)", "UTC+8"),
    ("Asia/Singapore", "Singapore (SGT)", "UTC+8"),
    ("Asia/Dubai", "Dubai (GST)", "UTC+4"),
    ("Asia/Kolkata", "India (IST)", "UTC+5:30"),
    # Australia
    ("Australia/Sydney", "Australia Eastern", "UTC+10/+11"),
    # Others
    ("UTC", "UTC", "UTC+0"),
]


class TimezoneService:
    """
    Manages user timezone preferences and time formatting.
    """

    DEFAULT_STORAGE_PATH = Path.home() / ".lifeos" / "trading" / "user_timezones.json"

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize TimezoneService.

        Args:
            storage_path: Path to store user preferences
        """
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self._user_timezones: Dict[int, str] = {}
        self._load_preferences()

    def _load_preferences(self) -> None:
        """Load timezone preferences from storage."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r") as f:
                self._user_timezones = json.load(f)

            # Convert string keys to int
            self._user_timezones = {
                int(k): v for k, v in self._user_timezones.items()
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to load timezone preferences: {e}")

    def _save_preferences(self) -> None:
        """Save timezone preferences to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert int keys to string for JSON
            data = {str(k): v for k, v in self._user_timezones.items()}

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except OSError as e:
            logger.error(f"Failed to save timezone preferences: {e}")

    def get_timezone(self, user_id: int) -> str:
        """
        Get a user's timezone.

        Args:
            user_id: Telegram user ID

        Returns:
            Timezone string (e.g., "America/New_York"), defaults to "UTC"
        """
        return self._user_timezones.get(user_id, "UTC")

    def set_timezone(self, user_id: int, tz_name: str) -> bool:
        """
        Set a user's timezone.

        Args:
            user_id: Telegram user ID
            tz_name: Timezone name (e.g., "America/New_York")

        Returns:
            True if timezone was valid and set, False otherwise
        """
        if not self.is_valid_timezone(tz_name):
            return False

        self._user_timezones[user_id] = tz_name
        self._save_preferences()
        return True

    def is_valid_timezone(self, tz_name: str) -> bool:
        """
        Check if a timezone name is valid.

        Args:
            tz_name: Timezone name to validate

        Returns:
            True if valid, False otherwise
        """
        if not ZONEINFO_AVAILABLE:
            # Without zoneinfo, accept common timezones
            valid_names = {tz[0] for tz in COMMON_TIMEZONES}
            return tz_name in valid_names

        try:
            zoneinfo.ZoneInfo(tz_name)
            return True
        except (KeyError, ValueError):
            return False

    def format_time(
        self,
        dt: datetime,
        user_id: int,
        format_str: str = "%Y-%m-%d %H:%M",
    ) -> str:
        """
        Format a datetime in user's timezone.

        Args:
            dt: Datetime to format (should be UTC or timezone-aware)
            user_id: Telegram user ID
            format_str: strftime format string

        Returns:
            Formatted time string with timezone abbreviation
        """
        tz_name = self.get_timezone(user_id)

        # Convert to user's timezone
        local_dt = self.convert_to_timezone(dt, tz_name)

        # Format with timezone abbreviation
        formatted = local_dt.strftime(format_str)

        # Add timezone abbreviation
        if ZONEINFO_AVAILABLE:
            tz_abbr = local_dt.strftime("%Z")
            return f"{formatted} {tz_abbr}"

        # Fallback: show timezone name
        return f"{formatted} ({tz_name.split('/')[-1]})"

    def format_time_short(self, dt: datetime, user_id: int) -> str:
        """
        Format a datetime in a short format (HH:MM TZ).

        Args:
            dt: Datetime to format
            user_id: Telegram user ID

        Returns:
            Short formatted time string
        """
        return self.format_time(dt, user_id, "%H:%M")

    def format_time_full(self, dt: datetime, user_id: int) -> str:
        """
        Format a datetime in full format.

        Args:
            dt: Datetime to format
            user_id: Telegram user ID

        Returns:
            Full formatted time string
        """
        return self.format_time(dt, user_id, "%Y-%m-%d %H:%M:%S")

    def convert_to_timezone(self, dt: datetime, tz_name: str) -> datetime:
        """
        Convert a datetime to a specific timezone.

        Args:
            dt: Datetime to convert (should be UTC or timezone-aware)
            tz_name: Target timezone name

        Returns:
            Datetime in target timezone
        """
        # Ensure input is timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if not ZONEINFO_AVAILABLE:
            # Without zoneinfo, return as UTC
            return dt

        try:
            target_tz = zoneinfo.ZoneInfo(tz_name)
            return dt.astimezone(target_tz)
        except (KeyError, ValueError):
            return dt

    def get_current_time(self, user_id: int) -> datetime:
        """
        Get current time in user's timezone.

        Args:
            user_id: Telegram user ID

        Returns:
            Current datetime in user's timezone
        """
        now = datetime.now(timezone.utc)
        tz_name = self.get_timezone(user_id)
        return self.convert_to_timezone(now, tz_name)

    def get_common_timezones(self) -> List[tuple]:
        """
        Get list of common timezones for selection.

        Returns:
            List of (tz_name, display_name, offset) tuples
        """
        return COMMON_TIMEZONES

    def search_timezone(self, query: str) -> List[tuple]:
        """
        Search for timezones matching a query.

        Args:
            query: Search query (e.g., "new york", "eastern")

        Returns:
            List of matching (tz_name, display_name, offset) tuples
        """
        query_lower = query.lower()

        results = []
        for tz_name, display_name, offset in COMMON_TIMEZONES:
            if (query_lower in tz_name.lower() or
                query_lower in display_name.lower() or
                query_lower in offset.lower()):
                results.append((tz_name, display_name, offset))

        return results

    def format_timezone_info(self, user_id: int) -> str:
        """
        Format timezone info message for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Formatted markdown message
        """
        tz_name = self.get_timezone(user_id)
        current = self.get_current_time(user_id)
        formatted_time = self.format_time_full(current, user_id)

        lines = [
            "\u23f0 *Your Timezone*",
            "",
            f"*Zone:* `{tz_name}`",
            f"*Current time:* {formatted_time}",
            "",
            "_Use `/timezone <zone>` to change._",
            "",
            "*Common zones:*",
        ]

        for tz, display, offset in COMMON_TIMEZONES[:5]:
            lines.append(f"  `{tz}` - {display}")

        return "\n".join(lines)


# Singleton instance
_timezone_service: Optional[TimezoneService] = None


def get_timezone_service() -> TimezoneService:
    """Get the global timezone service instance."""
    global _timezone_service
    if _timezone_service is None:
        _timezone_service = TimezoneService()
    return _timezone_service


__all__ = [
    "TimezoneService",
    "get_timezone_service",
    "COMMON_TIMEZONES",
]
