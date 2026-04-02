"""
Theme Manager for Telegram UI.

Provides dark/light mode theming for message formatting.
"""

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ThemeMode(Enum):
    """Available theme modes."""
    DARK = "dark"
    LIGHT = "light"


@dataclass
class ThemeColors:
    """Color scheme for a theme."""
    # Text colors (using markdown styles as Telegram is limited)
    heading: str  # Emoji prefix for headings
    success: str  # Emoji for positive values
    warning: str  # Emoji for caution
    error: str    # Emoji for negative values
    info: str     # Emoji for information
    muted: str    # Style for secondary text

    # Number formatting
    positive_prefix: str
    negative_prefix: str

    # Emoji density
    use_separators: bool  # Use line separators
    use_decorative: bool  # Use decorative emojis


# Theme definitions
DARK_THEME = ThemeColors(
    heading="\U0001f4ca",       # Chart emoji
    success="\u2705",           # Green check
    warning="\u26a0\ufe0f",     # Warning
    error="\u274c",             # Red X
    info="\u2139\ufe0f",        # Info
    muted="_",                  # Italic for muted
    positive_prefix="\U0001f7e2",  # Green circle
    negative_prefix="\U0001f534",  # Red circle
    use_separators=True,
    use_decorative=True,
)


LIGHT_THEME = ThemeColors(
    heading="\u25b6\ufe0f",     # Play button (less harsh)
    success="\u2714\ufe0f",     # Check mark
    warning="\u25b2",           # Triangle
    error="\u2717",             # X mark
    info="\u25cf",              # Circle
    muted="_",                  # Italic for muted
    positive_prefix="+",
    negative_prefix="-",
    use_separators=False,
    use_decorative=False,
)


@dataclass
class UserTheme:
    """User's theme preferences."""
    user_id: int
    mode: str = "dark"
    custom_colors: Optional[Dict] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserTheme":
        return cls(**data)


class ThemeManager:
    """
    Manages user theme preferences.

    Stores preferences in a JSON file for persistence.
    """

    DEFAULT_STORAGE_PATH = Path.home() / ".lifeos" / "trading" / "user_themes.json"

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize ThemeManager.

        Args:
            storage_path: Path to store user preferences
        """
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self._themes: Dict[int, UserTheme] = {}
        self._load_themes()

    def _load_themes(self) -> None:
        """Load themes from storage."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            for user_id_str, theme_data in data.items():
                user_id = int(user_id_str)
                self._themes[user_id] = UserTheme.from_dict(theme_data)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to load themes: {e}")

    def _save_themes(self) -> None:
        """Save themes to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                str(user_id): theme.to_dict()
                for user_id, theme in self._themes.items()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except OSError as e:
            logger.error(f"Failed to save themes: {e}")

    def get_theme(self, user_id: int) -> ThemeMode:
        """
        Get a user's theme mode.

        Args:
            user_id: Telegram user ID

        Returns:
            ThemeMode for the user (defaults to DARK)
        """
        theme = self._themes.get(user_id)
        if theme is None:
            return ThemeMode.DARK

        try:
            return ThemeMode(theme.mode)
        except ValueError:
            return ThemeMode.DARK

    def set_theme(self, user_id: int, mode: ThemeMode) -> None:
        """
        Set a user's theme mode.

        Args:
            user_id: Telegram user ID
            mode: ThemeMode to set
        """
        if user_id in self._themes:
            self._themes[user_id].mode = mode.value
        else:
            self._themes[user_id] = UserTheme(user_id=user_id, mode=mode.value)

        self._save_themes()

    def get_colors(self, user_id: int) -> ThemeColors:
        """
        Get the color scheme for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            ThemeColors for the user's theme
        """
        mode = self.get_theme(user_id)

        if mode == ThemeMode.LIGHT:
            return LIGHT_THEME
        return DARK_THEME

    def toggle_theme(self, user_id: int) -> ThemeMode:
        """
        Toggle a user's theme between dark and light.

        Args:
            user_id: Telegram user ID

        Returns:
            The new ThemeMode
        """
        current = self.get_theme(user_id)
        new_mode = ThemeMode.LIGHT if current == ThemeMode.DARK else ThemeMode.DARK
        self.set_theme(user_id, new_mode)
        return new_mode


class ThemedFormatter:
    """
    Formatter that applies theme-aware styling to messages.
    """

    def __init__(self, colors: ThemeColors):
        """
        Initialize ThemedFormatter.

        Args:
            colors: ThemeColors to use for formatting
        """
        self.colors = colors

    def heading(self, text: str) -> str:
        """Format a heading."""
        return f"{self.colors.heading} *{text}*"

    def success(self, text: str) -> str:
        """Format a success message."""
        return f"{self.colors.success} {text}"

    def warning(self, text: str) -> str:
        """Format a warning message."""
        return f"{self.colors.warning} {text}"

    def error(self, text: str) -> str:
        """Format an error message."""
        return f"{self.colors.error} {text}"

    def info(self, text: str) -> str:
        """Format an info message."""
        return f"{self.colors.info} {text}"

    def muted(self, text: str) -> str:
        """Format muted/secondary text."""
        return f"{self.colors.muted}{text}{self.colors.muted}"

    def number(self, value: float, show_sign: bool = True) -> str:
        """
        Format a number with appropriate styling.

        Args:
            value: The numeric value
            show_sign: Whether to show +/- prefix

        Returns:
            Formatted number string
        """
        if not show_sign:
            return f"{value:,.2f}"

        if value >= 0:
            return f"{self.colors.positive_prefix} {value:,.2f}"
        return f"{self.colors.negative_prefix} {value:,.2f}"

    def percentage(self, value: float) -> str:
        """
        Format a percentage with color coding.

        Args:
            value: The percentage value

        Returns:
            Formatted percentage string
        """
        if value >= 0:
            return f"{self.colors.positive_prefix} +{value:.2f}%"
        return f"{self.colors.negative_prefix} {value:.2f}%"

    def separator(self) -> str:
        """Return a line separator if enabled by theme."""
        if self.colors.use_separators:
            return "\n" + "\u2500" * 20 + "\n"
        return "\n"

    def decorative(self, emoji: str) -> str:
        """Return a decorative emoji if enabled by theme."""
        if self.colors.use_decorative:
            return emoji
        return ""


# Singleton instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def get_formatter_for_user(user_id: int) -> ThemedFormatter:
    """
    Get a themed formatter for a specific user.

    Args:
        user_id: Telegram user ID

    Returns:
        ThemedFormatter configured for the user's theme
    """
    manager = get_theme_manager()
    colors = manager.get_colors(user_id)
    return ThemedFormatter(colors)


__all__ = [
    "ThemeMode",
    "ThemeColors",
    "UserTheme",
    "ThemeManager",
    "ThemedFormatter",
    "get_theme_manager",
    "get_formatter_for_user",
    "DARK_THEME",
    "LIGHT_THEME",
]
