"""
Inline Button UI Components for Telegram.

Provides reusable button templates for:
- TokenAnalysisButtons - drill-down token analysis
- TradingActionButtons - BUY/HOLD/SELL confirmation
- SettingsButtons - user preferences
- LimitOrderButtons - price alert setup
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================


def parse_callback_data(callback_data: str) -> Tuple[str, str]:
    """
    Parse callback data into action and payload.

    Format: "action:payload" or "action"

    Returns:
        Tuple of (action, payload)
    """
    if ":" in callback_data:
        parts = callback_data.split(":", 1)
        return parts[0], parts[1]
    return callback_data, ""


def build_callback_data(action: str, *args) -> str:
    """Build callback data string from action and arguments."""
    MAX_LENGTH = 64  # Telegram limit

    if args:
        data = f"{action}:{':'.join(str(a) for a in args)}"
    else:
        data = action

    # Truncate if too long
    if len(data.encode('utf-8')) > MAX_LENGTH:
        # Find a safe truncation point
        while len(data.encode('utf-8')) > MAX_LENGTH - 3 and len(data) > 0:
            data = data[:-1]
        data = data + "..."

    return data


# =============================================================================
# TokenAnalysisButtons
# =============================================================================


class TokenAnalysisButtons:
    """
    Build interactive keyboards for token analysis drill-down.

    Main keyboard layout:
    [Chart] [On-Chain] [Signals]
    [Risk] [Community] [DexScreener]
    [Back] [Close]
    """

    def build_main_keyboard(
        self,
        token_address: str,
        token_symbol: str,
    ) -> InlineKeyboardMarkup:
        """
        Build main analysis keyboard with drill-down options.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol (e.g., SOL)

        Returns:
            InlineKeyboardMarkup with interactive buttons
        """
        keyboard = [
            # Row 1: Primary analysis options
            [
                InlineKeyboardButton(
                    "📊 Chart",
                    callback_data=f"analyze_chart:{token_address}"
                ),
                InlineKeyboardButton(
                    "🧬 On-Chain",
                    callback_data=f"analyze_holders:{token_address}"
                ),
                InlineKeyboardButton(
                    "🔥 Signals",
                    callback_data=f"analyze_signals:{token_address}"
                ),
            ],
            # Row 2: Secondary options
            [
                InlineKeyboardButton(
                    "🛡️ Risk",
                    callback_data=f"analyze_risk:{token_address}"
                ),
                InlineKeyboardButton(
                    "💬 Community",
                    callback_data=f"analyze_community:{token_address}"
                ),
            ],
            # Row 3: External links
            [
                InlineKeyboardButton(
                    "🔗 DexScreener",
                    url=f"https://dexscreener.com/solana/{token_address}"
                ),
                InlineKeyboardButton(
                    "🦅 Birdeye",
                    url=f"https://birdeye.so/token/{token_address}?chain=solana"
                ),
            ],
            # Row 4: Navigation
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"analyze_back:{token_address}"
                ),
                InlineKeyboardButton(
                    "❌ Close",
                    callback_data=f"ui_close:{token_address}"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_chart_keyboard(
        self,
        token_address: str,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for chart view with timeframe selectors."""
        keyboard = [
            # Timeframe row
            [
                InlineKeyboardButton("1H", callback_data=f"chart_1h:{token_address}"),
                InlineKeyboardButton("4H", callback_data=f"chart_4h:{token_address}"),
                InlineKeyboardButton("1D", callback_data=f"chart_1d:{token_address}"),
                InlineKeyboardButton("1W", callback_data=f"chart_1w:{token_address}"),
            ],
            # External charts
            [
                InlineKeyboardButton(
                    "TradingView",
                    url=f"https://www.tradingview.com/chart/?symbol=RAYDIUM:{token_address}"
                ),
                InlineKeyboardButton(
                    "DexScreener",
                    url=f"https://dexscreener.com/solana/{token_address}"
                ),
            ],
            # Navigation
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"analyze_back:{token_address}"),
                InlineKeyboardButton("❌ Close", callback_data=f"ui_close:{token_address}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_holders_keyboard(
        self,
        token_address: str,
        page: int = 1,
        total_pages: int = 1,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for holder distribution with pagination."""
        nav_buttons = []

        # Previous button
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton("<", callback_data=f"holders_page:{token_address}:{page - 1}")
            )
        else:
            nav_buttons.append(InlineKeyboardButton(" ", callback_data="noop"))

        # Page indicator
        nav_buttons.append(
            InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop")
        )

        # Next button
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(">", callback_data=f"holders_page:{token_address}:{page + 1}")
            )
        else:
            nav_buttons.append(InlineKeyboardButton(" ", callback_data="noop"))

        keyboard = [
            nav_buttons,
            [
                InlineKeyboardButton("Top 100", callback_data=f"holders_top100:{token_address}"),
                InlineKeyboardButton("Whales", callback_data=f"holders_whales:{token_address}"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"analyze_back:{token_address}"),
                InlineKeyboardButton("❌ Close", callback_data=f"ui_close:{token_address}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_signals_keyboard(
        self,
        token_address: str,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for trading signals view."""
        keyboard = [
            [
                InlineKeyboardButton("📈 Details", callback_data=f"signal_details:{token_address}"),
                InlineKeyboardButton("🔔 Set Alert", callback_data=f"alert_set:{token_address}"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"analyze_back:{token_address}"),
                InlineKeyboardButton("❌ Close", callback_data=f"ui_close:{token_address}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_risk_keyboard(
        self,
        token_address: str,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for risk assessment view."""
        keyboard = [
            [
                InlineKeyboardButton("🐋 Whale Activity", callback_data=f"risk_whales:{token_address}"),
                InlineKeyboardButton("📋 Contract", callback_data=f"risk_contract:{token_address}"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"analyze_back:{token_address}"),
                InlineKeyboardButton("❌ Close", callback_data=f"ui_close:{token_address}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# TradingActionButtons
# =============================================================================


class TradingActionButtons:
    """
    Build confirmation keyboards for trading actions.

    Provides BUY/SELL confirmation with size options.
    """

    def build_buy_confirmation(
        self,
        token_address: str,
        token_symbol: str,
        amount_usd: float,
    ) -> InlineKeyboardMarkup:
        """Build buy confirmation keyboard."""
        keyboard = [
            # Amount row
            [
                InlineKeyboardButton(f"${amount_usd:.0f}", callback_data="noop"),
            ],
            # Confirmation row
            [
                InlineKeyboardButton(
                    "✅ Confirm Buy",
                    callback_data=f"trade_confirm_buy:{token_address}:{amount_usd}"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="trade_cancel"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_sell_confirmation(
        self,
        token_address: str,
        token_symbol: str,
        percentage: int,
    ) -> InlineKeyboardMarkup:
        """Build sell confirmation keyboard."""
        keyboard = [
            # Percentage options
            [
                InlineKeyboardButton("25%", callback_data=f"trade_sell:{token_address}:25"),
                InlineKeyboardButton("50%", callback_data=f"trade_sell:{token_address}:50"),
                InlineKeyboardButton("75%", callback_data=f"trade_sell:{token_address}:75"),
                InlineKeyboardButton("100%", callback_data=f"trade_sell:{token_address}:100"),
            ],
            # Confirmation row
            [
                InlineKeyboardButton(
                    f"✅ Confirm Sell {percentage}%",
                    callback_data=f"trade_confirm_sell:{token_address}:{percentage}"
                ),
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="trade_cancel"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_hold_view(
        self,
        token_address: str,
        token_symbol: str,
    ) -> InlineKeyboardMarkup:
        """Build hold/watch keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "📊 Analyze",
                    callback_data=f"analyze_{token_address}"
                ),
                InlineKeyboardButton(
                    "⭐ Add to Watchlist",
                    callback_data=f"watch_add:{token_address}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👍 OK",
                    callback_data="ui_close"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# SettingsButtons
# =============================================================================


class SettingsButtons:
    """
    Build settings/preferences keyboards.
    """

    def build_settings_keyboard(
        self,
        user_id: int,
        current_settings: Dict[str, Any],
    ) -> InlineKeyboardMarkup:
        """Build user settings keyboard."""
        notifications_on = current_settings.get("notifications", True)
        notif_text = "🔔 Notifications: ON" if notifications_on else "🔕 Notifications: OFF"

        risk_profile = current_settings.get("risk_profile", "moderate")

        keyboard = [
            # Notification toggle
            [
                InlineKeyboardButton(
                    notif_text,
                    callback_data=f"settings_toggle_notifications:{user_id}"
                ),
            ],
            # Risk profile
            [
                InlineKeyboardButton(
                    f"⚡ Risk Profile: {risk_profile.title()}",
                    callback_data=f"settings_risk_profile:{user_id}"
                ),
            ],
            # Alert preferences
            [
                InlineKeyboardButton(
                    "🔔 Alert Settings",
                    callback_data=f"settings_alerts:{user_id}"
                ),
            ],
            # Close
            [
                InlineKeyboardButton(
                    "❌ Close",
                    callback_data="ui_close"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_risk_profile_keyboard(
        self,
        user_id: int,
        current_profile: str,
    ) -> InlineKeyboardMarkup:
        """Build risk profile selection keyboard."""
        profiles = ["conservative", "moderate", "aggressive"]

        buttons = []
        for profile in profiles:
            check = "✓ " if profile == current_profile else ""
            buttons.append(
                InlineKeyboardButton(
                    f"{check}{profile.title()}",
                    callback_data=f"settings_set_risk:{user_id}:{profile}"
                )
            )

        keyboard = [
            buttons,
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"settings_back:{user_id}"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# LimitOrderButtons
# =============================================================================


class LimitOrderButtons:
    """
    Build price alert / limit order keyboards.
    """

    def build_price_alert_keyboard(
        self,
        token_address: str,
        token_symbol: str,
        current_price: float,
    ) -> InlineKeyboardMarkup:
        """Build price alert keyboard with common targets."""
        # Calculate percentage-based targets
        targets = [
            ("+5%", current_price * 1.05),
            ("+10%", current_price * 1.10),
            ("+25%", current_price * 1.25),
            ("-5%", current_price * 0.95),
            ("-10%", current_price * 0.90),
        ]

        # Build buttons
        up_row = []
        down_row = []

        for label, price in targets:
            callback = f"alert:{token_address}:{price:.8f}"
            btn = InlineKeyboardButton(f"{label} (${price:.4f})", callback_data=callback)

            if label.startswith("+"):
                up_row.append(btn)
            else:
                down_row.append(btn)

        keyboard = [
            up_row,
            down_row,
            [
                InlineKeyboardButton(
                    "📝 Custom Price",
                    callback_data=f"alert_custom:{token_address}"
                ),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data=f"analyze_back:{token_address}"),
                InlineKeyboardButton("❌ Close", callback_data=f"ui_close:{token_address}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def build_alert_confirmation(
        self,
        token_address: str,
        token_symbol: str,
        target_price: float,
        current_price: float,
    ) -> InlineKeyboardMarkup:
        """Build alert confirmation keyboard."""
        direction = "above" if target_price > current_price else "below"

        keyboard = [
            [
                InlineKeyboardButton(
                    f"✅ Set Alert: ${target_price:.4f} ({direction})",
                    callback_data=f"alert_confirm:{token_address}:{target_price}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data=f"analyze_signals:{token_address}"
                ),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# Watchlist Buttons (imported from interactive_ui)
# =============================================================================


def build_watchlist_keyboard(
    watchlist: List[Dict],
    user_id: int,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for watchlist display.

    Each token gets: [View] [Remove]
    Bottom: [Add Token] [Refresh] [Close]
    """
    keyboard = []

    for item in watchlist[:10]:  # Max 10 visible
        symbol = item.get("symbol", "???")
        address = item.get("address", "")

        keyboard.append([
            InlineKeyboardButton(f"📊 {symbol}", callback_data=f"watch_view:{address}"),
            InlineKeyboardButton("❌", callback_data=f"watch_remove:{address}"),
        ])

    # Action buttons
    keyboard.append([
        InlineKeyboardButton("➕ Add Token", callback_data="watch_add"),
        InlineKeyboardButton("🔄 Refresh", callback_data="watch_refresh"),
    ])

    keyboard.append([
        InlineKeyboardButton("🗑️ Clear All", callback_data="watch_clear"),
        InlineKeyboardButton("❌ Close", callback_data="ui_close"),
    ])

    return InlineKeyboardMarkup(keyboard)


# =============================================================================
# ButtonBuilder - Generic Button Construction
# =============================================================================


class ButtonBuilder:
    """
    Generic button builder for creating Telegram inline keyboards.

    Provides a fluent interface for building buttons and keyboards.
    """

    MAX_CALLBACK_DATA_LENGTH = 64  # Telegram limit

    def button(
        self,
        text: str,
        callback_data: str,
    ) -> InlineKeyboardButton:
        """
        Create a callback button.

        Args:
            text: Button display text
            callback_data: Callback data string

        Returns:
            InlineKeyboardButton instance
        """
        # Truncate callback_data if too long
        if len(callback_data.encode('utf-8')) > self.MAX_CALLBACK_DATA_LENGTH:
            callback_data = callback_data[:self.MAX_CALLBACK_DATA_LENGTH - 3] + "..."
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    def url_button(
        self,
        text: str,
        url: str,
    ) -> InlineKeyboardButton:
        """
        Create a URL button.

        Args:
            text: Button display text
            url: URL to open

        Returns:
            InlineKeyboardButton instance
        """
        return InlineKeyboardButton(text=text, url=url)

    def row(
        self,
        buttons: List[InlineKeyboardButton],
    ) -> List[InlineKeyboardButton]:
        """
        Create a row of buttons.

        Args:
            buttons: List of buttons for this row

        Returns:
            List of buttons (row)
        """
        return buttons

    def keyboard(
        self,
        rows: List[List[InlineKeyboardButton]],
    ) -> InlineKeyboardMarkup:
        """
        Create a complete keyboard from rows.

        Args:
            rows: List of button rows

        Returns:
            InlineKeyboardMarkup instance
        """
        return InlineKeyboardMarkup(rows)


# =============================================================================
# QuickActionButtons - Buy/Sell/Hold Quick Actions
# =============================================================================


class QuickActionButtons:
    """
    Build quick action keyboards for trading decisions.

    Provides BUY/SELL/HOLD buttons with confirmation flows.
    """

    def __init__(self):
        self.builder = ButtonBuilder()

    def buy_button(
        self,
        token_address: str,
        token_symbol: str,
        amount_usd: float = 50.0,
    ) -> InlineKeyboardMarkup:
        """
        Build a buy action keyboard with amount options.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol (e.g., SOL)
            amount_usd: Default amount in USD

        Returns:
            InlineKeyboardMarkup with buy options
        """
        amounts = [25, 50, 100, 250]

        amount_row = [
            self.builder.button(
                f"${amt}",
                f"buy_amount:{token_address}:{amt}"
            )
            for amt in amounts
        ]

        keyboard = [
            amount_row,
            [
                self.builder.button(
                    f"Confirm Buy ${amount_usd:.0f}",
                    f"buy_confirm:{token_address}:{amount_usd}"
                ),
                self.builder.button("Cancel", "buy_cancel"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def sell_button(
        self,
        token_address: str,
        token_symbol: str,
        default_percent: int = 100,
    ) -> InlineKeyboardMarkup:
        """
        Build a sell action keyboard with percentage options.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol
            default_percent: Default sell percentage

        Returns:
            InlineKeyboardMarkup with sell options
        """
        percentages = [25, 50, 75, 100]

        percent_row = [
            self.builder.button(
                f"{pct}%",
                f"sell_pct:{token_address}:{pct}"
            )
            for pct in percentages
        ]

        keyboard = [
            percent_row,
            [
                self.builder.button(
                    f"Confirm Sell {default_percent}%",
                    f"sell_confirm:{token_address}:{default_percent}"
                ),
                self.builder.button("Cancel", "sell_cancel"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def hold_button(
        self,
        token_address: str,
        token_symbol: str,
    ) -> InlineKeyboardMarkup:
        """
        Build a hold/watch keyboard.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol

        Returns:
            InlineKeyboardMarkup with hold options
        """
        keyboard = [
            [
                self.builder.button("Analyze", f"analyze:{token_address}"),
                self.builder.button("Add to Watchlist", f"watch_add:{token_address}"),
            ],
            [
                self.builder.button("Set Alert", f"alert_set:{token_address}"),
                self.builder.button("OK", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# PositionButtons - Position Management
# =============================================================================


class PositionButtons:
    """
    Build keyboards for position management.

    Provides buttons for selling, adjusting TP/SL, and viewing details.
    """

    def __init__(self):
        self.builder = ButtonBuilder()

    def position_actions(
        self,
        position_id: str,
        token_symbol: str,
        current_pnl_pct: float = 0.0,
    ) -> InlineKeyboardMarkup:
        """
        Build position action keyboard.

        Args:
            position_id: Position identifier
            token_symbol: Token symbol
            current_pnl_pct: Current P&L percentage

        Returns:
            InlineKeyboardMarkup with position actions
        """
        pnl_emoji = "" if current_pnl_pct >= 0 else ""

        keyboard = [
            [
                self.builder.button(
                    f"{pnl_emoji} {token_symbol} Details",
                    f"pos_detail:{position_id}"
                ),
            ],
            [
                self.builder.button("Sell 50%", f"pos_sell:{position_id}:50"),
                self.builder.button("Sell 100%", f"pos_sell:{position_id}:100"),
            ],
            [
                self.builder.button("Adjust TP/SL", f"pos_adjust:{position_id}"),
                self.builder.button("Close", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def close_confirmation(
        self,
        position_id: str,
        token_symbol: str,
        sell_percent: int = 100,
    ) -> InlineKeyboardMarkup:
        """
        Build position close confirmation keyboard.

        Args:
            position_id: Position identifier
            token_symbol: Token symbol
            sell_percent: Percentage to sell

        Returns:
            InlineKeyboardMarkup with confirmation buttons
        """
        keyboard = [
            [
                self.builder.button(
                    f"Confirm Sell {sell_percent}% {token_symbol}",
                    f"pos_confirm_sell:{position_id}:{sell_percent}"
                ),
            ],
            [
                self.builder.button("Cancel", f"pos_cancel:{position_id}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def adjust_tp_sl(
        self,
        position_id: str,
        current_tp: float,
        current_sl: float,
    ) -> InlineKeyboardMarkup:
        """
        Build TP/SL adjustment keyboard.

        Args:
            position_id: Position identifier
            current_tp: Current take profit price
            current_sl: Current stop loss price

        Returns:
            InlineKeyboardMarkup with adjustment buttons
        """
        keyboard = [
            [
                self.builder.button("TP +5%", f"adj_tp:{position_id}:5"),
                self.builder.button("TP +10%", f"adj_tp:{position_id}:10"),
                self.builder.button("TP -5%", f"adj_tp:{position_id}:-5"),
            ],
            [
                self.builder.button("SL +5%", f"adj_sl:{position_id}:5"),
                self.builder.button("SL -5%", f"adj_sl:{position_id}:-5"),
                self.builder.button("SL -10%", f"adj_sl:{position_id}:-10"),
            ],
            [
                self.builder.button("Save", f"adj_save:{position_id}"),
                self.builder.button("Cancel", f"adj_cancel:{position_id}"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# CommandButtons - Quick Command Selection
# =============================================================================


class CommandButtons:
    """
    Build keyboards for quick command selection.

    Provides menus for accessing common commands.
    """

    def __init__(self):
        self.builder = ButtonBuilder()

    def main_menu(self, is_admin: bool = False) -> InlineKeyboardMarkup:
        """
        Build main menu keyboard.

        Args:
            is_admin: Whether user is admin

        Returns:
            InlineKeyboardMarkup with menu options
        """
        keyboard = [
            [
                self.builder.button("Trending", "cmd:trending"),
                self.builder.button("Status", "cmd:status"),
            ],
            [
                self.builder.button("Watchlist", "cmd:watchlist"),
                self.builder.button("Help", "cmd:help"),
            ],
        ]

        if is_admin:
            admin_row = [
                self.builder.button("Dashboard", "cmd:dashboard"),
                self.builder.button("Positions", "cmd:positions"),
            ]
            keyboard.insert(0, admin_row)

            keyboard.append([
                self.builder.button("Report", "cmd:report"),
                self.builder.button("Config", "cmd:config"),
            ])

        keyboard.append([
            self.builder.button("Close", "ui_close"),
        ])

        return InlineKeyboardMarkup(keyboard)

    def trading_commands(self) -> InlineKeyboardMarkup:
        """
        Build trading command keyboard.

        Returns:
            InlineKeyboardMarkup with trading commands
        """
        keyboard = [
            [
                self.builder.button("Dashboard", "cmd:dashboard"),
                self.builder.button("Positions", "cmd:positions"),
            ],
            [
                self.builder.button("Balance", "cmd:balance"),
                self.builder.button("Report", "cmd:report"),
            ],
            [
                self.builder.button("Back", "nav:main"),
                self.builder.button("Close", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)

    def analysis_commands(self) -> InlineKeyboardMarkup:
        """
        Build analysis command keyboard.

        Returns:
            InlineKeyboardMarkup with analysis commands
        """
        keyboard = [
            [
                self.builder.button("Trending", "cmd:trending"),
                self.builder.button("Signals", "cmd:signals"),
            ],
            [
                self.builder.button("Analyze", "cmd:analyze"),
                self.builder.button("Chart", "cmd:chart"),
            ],
            [
                self.builder.button("Digest", "cmd:digest"),
                self.builder.button("Sentiment", "cmd:sentiment"),
            ],
            [
                self.builder.button("Back", "nav:main"),
                self.builder.button("Close", "ui_close"),
            ],
        ]

        return InlineKeyboardMarkup(keyboard)


# =============================================================================
# CallbackRouter - Route Callbacks to Handlers
# =============================================================================


class CallbackRouter:
    """
    Routes callback queries to appropriate handlers.

    Supports handler registration and middleware.
    """

    def __init__(self):
        self._handlers: Dict[str, Any] = {}

    def register(self, action: str, handler) -> None:
        """
        Register a callback handler.

        Args:
            action: Action prefix to match
            handler: Async handler function
        """
        self._handlers[action] = handler

    def handler(self, action: str):
        """
        Decorator to register a callback handler.

        Args:
            action: Action prefix to match

        Returns:
            Decorator function
        """
        def decorator(func):
            self.register(action, func)
            return func
        return decorator

    def has_handler(self, action: str) -> bool:
        """
        Check if handler exists for action.

        Args:
            action: Action to check

        Returns:
            True if handler exists
        """
        return action in self._handlers

    async def route(self, query, context) -> bool:
        """
        Route a callback query to its handler.

        Args:
            query: Telegram CallbackQuery
            context: Telegram context

        Returns:
            True if handled, False otherwise
        """
        if not query.data:
            return False

        action, payload = parse_callback_data(query.data)

        if action not in self._handlers:
            return False

        handler = self._handlers[action]
        await handler(query, context, payload)
        return True


__all__ = [
    "TokenAnalysisButtons",
    "TradingActionButtons",
    "SettingsButtons",
    "LimitOrderButtons",
    "parse_callback_data",
    "build_callback_data",
    "build_watchlist_keyboard",
    "ButtonBuilder",
    "QuickActionButtons",
    "PositionButtons",
    "CommandButtons",
    "CallbackRouter",
]
