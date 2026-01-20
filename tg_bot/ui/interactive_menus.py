"""
Interactive Menus for Telegram UI.

Provides:
- Portfolio overview with buttons
- Trading dashboard with quick actions
- Settings management menu
- Menu navigation system
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


# =============================================================================
# Base Menu Class
# =============================================================================


class BaseMenu:
    """Base class for interactive menus."""

    def _button(
        self,
        text: str,
        callback_data: str,
    ) -> InlineKeyboardButton:
        """Create a callback button."""
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    def _url_button(
        self,
        text: str,
        url: str,
    ) -> InlineKeyboardButton:
        """Create a URL button."""
        return InlineKeyboardButton(text=text, url=url)


# =============================================================================
# Portfolio Menu
# =============================================================================


class PortfolioMenu(BaseMenu):
    """
    Build portfolio overview menus.

    Displays positions with P&L and quick actions.
    """

    def build(self) -> InlineKeyboardMarkup:
        """
        Build basic portfolio menu.

        Returns:
            InlineKeyboardMarkup with portfolio options
        """
        keyboard = [
            [
                self._button("Positions", "port:positions"),
                self._button("Balance", "port:balance"),
            ],
            [
                self._button("P&L Summary", "port:pnl"),
                self._button("History", "port:history"),
            ],
            [
                self._button("Refresh", "port:refresh"),
                self._button("Back", "nav:back"),
                self._button("Close", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_with_positions(
        self,
        positions: List[Dict[str, Any]],
    ) -> InlineKeyboardMarkup:
        """
        Build portfolio menu with position buttons.

        Args:
            positions: List of position dicts with symbol, pnl_pct, id

        Returns:
            InlineKeyboardMarkup with position rows
        """
        keyboard = []

        for pos in positions[:10]:  # Max 10 positions displayed
            symbol = pos.get("symbol", "???")
            pnl_pct = pos.get("pnl_pct", 0)
            pos_id = pos.get("id", "")

            emoji = "" if pnl_pct >= 0 else ""
            text = f"{emoji} {symbol} {pnl_pct:+.1f}%"

            keyboard.append([
                self._button(text, f"pos:view:{pos_id}"),
                self._button("Sell", f"pos:sell:{pos_id}"),
            ])

        # Navigation row
        keyboard.append([
            self._button("Refresh", "port:refresh"),
            self._button("Back", "nav:back"),
            self._button("Close", "ui_close"),
        ])

        return InlineKeyboardMarkup(keyboard)

    def build_empty(self) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build empty portfolio view.

        Returns:
            Tuple of (message text, keyboard)
        """
        text = "*portfolio*\n\n_no positions open._\n\nrun /report to find opportunities."

        keyboard = InlineKeyboardMarkup([
            [
                self._button("Report", "cmd:report"),
                self._button("Trending", "cmd:trending"),
            ],
            [
                self._button("Back", "nav:back"),
                self._button("Close", "ui_close"),
            ],
        ])

        return text, keyboard


# =============================================================================
# Trading Dashboard
# =============================================================================


class TradingDashboard(BaseMenu):
    """
    Build trading dashboard menus.

    Provides overview of trading activity with quick actions.
    """

    def build(
        self,
        mode: str = "paper",
        is_admin: bool = True,
    ) -> InlineKeyboardMarkup:
        """
        Build basic dashboard menu.

        Args:
            mode: Trading mode ("paper" or "live")
            is_admin: Whether user is admin

        Returns:
            InlineKeyboardMarkup with dashboard options
        """
        mode_text = "PAPER" if mode == "paper" else "LIVE"

        keyboard = [
            [
                self._button(f"Mode: {mode_text}", "dash:toggle_mode"),
            ],
            [
                self._button("Positions", "dash:positions"),
                self._button("Balance", "dash:balance"),
            ],
            [
                self._button("Report", "dash:report"),
                self._button("Signals", "dash:signals"),
            ],
        ]

        if is_admin:
            keyboard.append([
                self._button("Config", "dash:config"),
                self._button("Logs", "dash:logs"),
            ])

        keyboard.append([
            self._button("Refresh", "dash:refresh"),
            self._button("Close", "ui_close"),
        ])

        return InlineKeyboardMarkup(keyboard)

    def build_with_stats(
        self,
        stats: Dict[str, Any],
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build dashboard with statistics.

        Args:
            stats: Dict with sol_balance, usd_value, open_positions,
                   total_pnl, win_rate

        Returns:
            Tuple of (message text, keyboard)
        """
        sol_balance = stats.get("sol_balance", 0)
        usd_value = stats.get("usd_value", 0)
        open_positions = stats.get("open_positions", 0)
        total_pnl = stats.get("total_pnl", 0)
        win_rate = stats.get("win_rate", 0)

        pnl_emoji = "" if total_pnl >= 0 else ""

        lines = [
            "*dashboard*",
            "",
            f"Balance: `{sol_balance:.4f}` SOL (~${usd_value:,.0f})",
            f"Positions: {open_positions}",
            f"P&L: {pnl_emoji} ${total_pnl:+.2f}",
            f"Win Rate: {win_rate:.1f}%",
        ]

        text = "\n".join(lines)

        keyboard = self.build()

        return text, keyboard


# =============================================================================
# Settings Menu
# =============================================================================


class SettingsMenu(BaseMenu):
    """
    Build settings management menus.

    Provides toggles and options for user preferences.
    """

    def __init__(self, user_id: int = 0):
        """Initialize with optional user_id for template creation."""
        self._default_user_id = user_id

    def build(
        self,
        user_id: Optional[int] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> InlineKeyboardMarkup:
        """
        Build settings menu.

        Args:
            user_id: User ID
            settings: Current settings dict

        Returns:
            InlineKeyboardMarkup with settings options
        """
        user_id = user_id or self._default_user_id
        settings = settings or {}

        # Notification toggle
        notif_on = settings.get("notifications", True)
        notif_text = "Notifications: ON" if notif_on else "Notifications: OFF"

        # Theme toggle
        theme = settings.get("theme", "dark")
        theme_text = f"Theme: {theme.title()}"

        # Risk profile
        risk = settings.get("risk_profile", "moderate")
        risk_text = f"Risk: {risk.title()}"

        keyboard = [
            [
                self._button(notif_text, f"settings:toggle_notifications:{user_id}"),
            ],
            [
                self._button(theme_text, f"settings:toggle_theme:{user_id}"),
                self._button("Display", f"settings:display:{user_id}"),
            ],
            [
                self._button(risk_text, f"settings:risk_profile:{user_id}"),
            ],
            [
                self._button("Alert Settings", f"settings:alerts:{user_id}"),
            ],
            [
                self._button("Back", "nav:back"),
                self._button("Close", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# Menu Navigator
# =============================================================================


class MenuNavigator:
    """
    Navigate between menus with breadcrumb tracking.

    Maintains navigation state per user.
    """

    def __init__(self):
        self._user_states: Dict[int, List[str]] = {}
        self._portfolio_menu = PortfolioMenu()
        self._dashboard = TradingDashboard()
        self._settings_menu = SettingsMenu()
        self._menus: Dict[str, Any] = {
            "main": self._build_main_menu,
            "portfolio": self._portfolio_menu.build,
            "dashboard": self._dashboard.build,
            "settings": self._settings_menu.build,
        }

    def _build_main_menu(self) -> InlineKeyboardMarkup:
        """Build the main menu."""
        keyboard = [
            [
                InlineKeyboardButton("Portfolio", callback_data="nav:portfolio"),
                InlineKeyboardButton("Dashboard", callback_data="nav:dashboard"),
            ],
            [
                InlineKeyboardButton("Watchlist", callback_data="nav:watchlist"),
                InlineKeyboardButton("Settings", callback_data="nav:settings"),
            ],
            [
                InlineKeyboardButton("Help", callback_data="cmd:help"),
                InlineKeyboardButton("Close", callback_data="ui_close"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def navigate_to(
        self,
        menu_name: str,
        user_id: int = 0,
    ) -> InlineKeyboardMarkup:
        """
        Navigate to a menu.

        Args:
            menu_name: Name of menu to show
            user_id: User ID for state tracking

        Returns:
            InlineKeyboardMarkup for the menu
        """
        # Track navigation
        if user_id not in self._user_states:
            self._user_states[user_id] = []

        self._user_states[user_id].append(menu_name)

        # Build menu
        if menu_name in self._menus:
            builder = self._menus[menu_name]
            if callable(builder):
                return builder()

        # Default fallback
        return self._build_main_menu()

    def back_to_main(self) -> InlineKeyboardMarkup:
        """Navigate back to main menu."""
        return self._build_main_menu()

    def get_breadcrumbs(self, user_id: int = 0) -> List[str]:
        """
        Get navigation breadcrumbs.

        Args:
            user_id: User ID

        Returns:
            List of menu names in order visited
        """
        return self._user_states.get(user_id, []).copy()

    def go_back(self, user_id: int = 0) -> str:
        """
        Go back to previous menu.

        Args:
            user_id: User ID

        Returns:
            Name of menu navigated to
        """
        states = self._user_states.get(user_id, [])

        if len(states) > 1:
            states.pop()  # Remove current
            return states[-1] if states else "main"

        return "main"

    def get_current_menu(self, user_id: int = 0) -> str:
        """
        Get current menu for user.

        Args:
            user_id: User ID

        Returns:
            Current menu name
        """
        states = self._user_states.get(user_id, [])
        return states[-1] if states else "main"

    async def handle_callback(self, query) -> bool:
        """
        Handle navigation callback.

        Args:
            query: Telegram CallbackQuery

        Returns:
            True if handled
        """
        if not query.data or not query.data.startswith("nav:"):
            return False

        await query.answer()

        menu_name = query.data.replace("nav:", "")
        user_id = query.from_user.id if query.from_user else 0

        if menu_name == "back":
            menu_name = self.go_back(user_id)

        keyboard = self.navigate_to(menu_name, user_id)

        try:
            await query.message.edit_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.debug(f"Failed to edit menu: {e}")
            await query.message.reply_text(
                f"*{menu_name}*",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

        return True


# =============================================================================
# Singleton Instances
# =============================================================================

_navigator: Optional[MenuNavigator] = None


def get_menu_navigator() -> MenuNavigator:
    """Get the global MenuNavigator instance."""
    global _navigator
    if _navigator is None:
        _navigator = MenuNavigator()
    return _navigator


__all__ = [
    "PortfolioMenu",
    "TradingDashboard",
    "SettingsMenu",
    "MenuNavigator",
    "get_menu_navigator",
]
