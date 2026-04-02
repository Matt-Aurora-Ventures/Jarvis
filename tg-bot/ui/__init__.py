"""UI components for Telegram bot."""

from tg_bot.ui.inline_buttons import (
    TokenAnalysisButtons,
    TradingActionButtons,
    SettingsButtons,
    LimitOrderButtons,
    ButtonBuilder,
    QuickActionButtons,
    PositionButtons,
    CommandButtons,
    CallbackRouter,
    parse_callback_data,
    build_callback_data,
    build_watchlist_keyboard,
)
from tg_bot.ui.token_analysis_view import TokenAnalysisView
from tg_bot.ui.chart_handler import ChartHandler
from tg_bot.ui.watchlist_manager import (
    WatchlistManager,
    WatchlistToken,
    get_watchlist_manager,
)
from tg_bot.ui.command_framework import (
    CommandParser,
    CommandPermissions,
    CommandHistory,
    CommandAutocomplete,
    CommandExecutor,
    PermissionLevel,
    ParsedCommand,
    get_command_parser,
    get_command_permissions,
    get_command_history,
    get_command_autocomplete,
)
from tg_bot.ui.interactive_menus import (
    PortfolioMenu,
    TradingDashboard,
    SettingsMenu,
    MenuNavigator,
    get_menu_navigator,
)

__all__ = [
    # Inline buttons (original)
    "TokenAnalysisButtons",
    "TradingActionButtons",
    "SettingsButtons",
    "LimitOrderButtons",
    "TokenAnalysisView",
    "ChartHandler",
    # Inline buttons (new)
    "ButtonBuilder",
    "QuickActionButtons",
    "PositionButtons",
    "CommandButtons",
    "CallbackRouter",
    "parse_callback_data",
    "build_callback_data",
    "build_watchlist_keyboard",
    # Watchlist manager
    "WatchlistManager",
    "WatchlistToken",
    "get_watchlist_manager",
    # Command framework
    "CommandParser",
    "CommandPermissions",
    "CommandHistory",
    "CommandAutocomplete",
    "CommandExecutor",
    "PermissionLevel",
    "ParsedCommand",
    "get_command_parser",
    "get_command_permissions",
    "get_command_history",
    "get_command_autocomplete",
    # Interactive menus
    "PortfolioMenu",
    "TradingDashboard",
    "SettingsMenu",
    "MenuNavigator",
    "get_menu_navigator",
]
