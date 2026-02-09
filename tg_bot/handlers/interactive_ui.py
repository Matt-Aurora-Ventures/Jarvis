"""
Interactive UI components for enhanced Telegram experience.

Provides:
- Inline keyboard builders for token analysis
- Session state management for drill-down navigation
- Watchlist management
- Callback routing for interactive buttons
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Default session directory
DEFAULT_SESSIONS_DIR = Path(__file__).parent.parent.parent / "data" / "telegram_sessions"

# Global session manager instance
_session_manager: Optional["SessionManager"] = None


def is_new_ui_enabled() -> bool:
    """Check if the new interactive UI is enabled via feature flag."""
    # Check environment variable first
    env_flag = os.environ.get("NEW_TELEGRAM_UI_ENABLED", "").lower()
    if env_flag:
        return env_flag in ("true", "1", "yes", "on")

    # Check feature flags file
    try:
        flags_file = Path(__file__).parent.parent.parent / "data" / "feature_flags.json"
        if flags_file.exists():
            with open(flags_file) as f:
                flags = json.load(f)
            ui_flag = flags.get("new_telegram_ui", {})
            return ui_flag.get("state", "off") == "on"
    except Exception:
        pass

    # Default to enabled
    return True


# =============================================================================
# Keyboard Builders
# =============================================================================


def build_analyze_keyboard(token_address: str, token_symbol: str) -> InlineKeyboardMarkup:
    """
    Build interactive keyboard for /analyze command response.

    Layout:
    [Chart] [Holders] [Trades]
    [Signal] [Details] [Close]
    """
    keyboard = [
        [
            InlineKeyboardButton("Chart", callback_data=f"chart:{token_address}"),
            InlineKeyboardButton("Holders", callback_data=f"holders:{token_address}"),
            InlineKeyboardButton("Trades", callback_data=f"trades:{token_address}"),
        ],
        [
            InlineKeyboardButton("Signal", callback_data=f"signal:{token_address}"),
            InlineKeyboardButton("Details", callback_data=f"details:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ],
        [InlineKeyboardButton("↩️ Previous Menu", callback_data="menu_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_holder_pagination_keyboard(
    token_address: str,
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    """
    Build pagination keyboard for holder drill-down.

    Layout:
    [<] Page X/Y [>]
    [Top 100] [Back] [Close]
    """
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
            InlineKeyboardButton("↩️ Previous Menu", callback_data=f"analyze_back:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_signal_keyboard(token_address: str, token_symbol: str) -> InlineKeyboardMarkup:
    """
    Build keyboard for trading signal panel.

    Layout:
    [View Details] [Trade Now]
    [Set Reminder] [Close]
    """
    keyboard = [
        [
            InlineKeyboardButton("View Details", callback_data=f"signal_details:{token_address}"),
            InlineKeyboardButton("Trade Now", callback_data=f"trade_{token_address}"),
        ],
        [
            InlineKeyboardButton("Set Reminder", callback_data=f"signal_remind:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ],
        [InlineKeyboardButton("↩️ Previous Menu", callback_data=f"analyze_back:{token_address}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_comparison_keyboard(tokens: List[str]) -> InlineKeyboardMarkup:
    """
    Build keyboard for token comparison view.

    Layout:
    [Sort by Grade] [Sort by Risk]
    [Compare Details] [Close]
    """
    token_str = ",".join(tokens[:5])  # Max 5 tokens

    keyboard = [
        [
            InlineKeyboardButton("Sort by Grade", callback_data=f"compare_sort:grade:{token_str}"),
            InlineKeyboardButton("Sort by Risk", callback_data=f"compare_sort:risk:{token_str}"),
        ],
        [
            InlineKeyboardButton("Compare Details", callback_data=f"compare_details:{token_str}"),
            InlineKeyboardButton("Close", callback_data="ui_close:compare"),
        ],
        [InlineKeyboardButton("↩️ Previous Menu", callback_data="menu_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_watchlist_keyboard(watchlist: List[Dict], user_id: int) -> InlineKeyboardMarkup:
    """
    Build keyboard for watchlist display.

    Each token gets: [View] [Remove]
    Bottom: [Add Token] [Clear All] [Refresh]
    """
    keyboard = []

    for item in watchlist[:10]:  # Max 10 visible
        symbol = item.get("symbol", "???")
        address = item.get("address", "")

        keyboard.append([
            InlineKeyboardButton(f"{symbol}", callback_data=f"watch_view:{address}"),
            InlineKeyboardButton("View", callback_data=f"analyze_{address}"),
            InlineKeyboardButton("X", callback_data=f"watch_remove:{address}"),
        ])

    # Action buttons
    keyboard.append([
        InlineKeyboardButton("Add Token", callback_data="watch_add"),
        InlineKeyboardButton("Clear All", callback_data="watch_clear"),
        InlineKeyboardButton("Refresh", callback_data="watch_refresh"),
    ])
    keyboard.append([InlineKeyboardButton("↩️ Previous Menu", callback_data="menu_back")])

    return InlineKeyboardMarkup(keyboard)


def build_trades_keyboard(token_address: str) -> InlineKeyboardMarkup:
    """Build keyboard for trades drill-down view."""
    keyboard = [
        [
            InlineKeyboardButton("Whales Only", callback_data=f"trades_whales:{token_address}"),
            InlineKeyboardButton("Last 100", callback_data=f"trades_100:{token_address}"),
        ],
        [
            InlineKeyboardButton("↩️ Previous Menu", callback_data=f"analyze_back:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_chart_keyboard(token_address: str) -> InlineKeyboardMarkup:
    """Build keyboard for chart view."""
    keyboard = [
        [
            InlineKeyboardButton("1H", callback_data=f"chart_1h:{token_address}"),
            InlineKeyboardButton("4H", callback_data=f"chart_4h:{token_address}"),
            InlineKeyboardButton("1D", callback_data=f"chart_1d:{token_address}"),
            InlineKeyboardButton("1W", callback_data=f"chart_1w:{token_address}"),
        ],
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
        [
            InlineKeyboardButton("↩️ Previous Menu", callback_data=f"analyze_back:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# =============================================================================
# Session Management
# =============================================================================


class SessionManager:
    """
    Manages drill-down session state for users.

    Sessions are persisted to disk and expire after timeout_minutes of inactivity.
    """

    def __init__(
        self,
        sessions_dir: Optional[str] = None,
        timeout_minutes: int = 30,
    ):
        self.sessions_dir = Path(sessions_dir) if sessions_dir else DEFAULT_SESSIONS_DIR
        self.timeout_minutes = timeout_minutes
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, user_id: int) -> Path:
        """Get path to session file for user."""
        return self.sessions_dir / f"{user_id}.json"

    def create_session(
        self,
        user_id: int,
        token_address: str,
        token_symbol: str,
        current_view: str = "main",
    ) -> Dict[str, Any]:
        """Create a new drill-down session."""
        now = datetime.now(timezone.utc)

        session = {
            "user_id": user_id,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "current_view": current_view,
            "page": 1,
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
        }

        self._save_session(user_id, session)
        return session

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get session for user if it exists and is not expired.

        Returns None if session doesn't exist or has expired.
        """
        session_path = self._get_session_path(user_id)

        if not session_path.exists():
            return None

        try:
            with open(session_path) as f:
                session = json.load(f)

            # Check for timeout
            last_activity = datetime.fromisoformat(session.get("last_activity", ""))
            now = datetime.now(timezone.utc)

            # Ensure last_activity is timezone-aware
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            age_minutes = (now - last_activity).total_seconds() / 60

            if age_minutes > self.timeout_minutes:
                # Session expired, clean up
                self.clear_session(user_id)
                return None

            return session

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to load session for user {user_id}: {e}")
            return None

    def update_session(self, user_id: int, **updates) -> Optional[Dict[str, Any]]:
        """Update session with new values."""
        session = self.get_session(user_id)

        if session is None:
            return None

        session.update(updates)
        session["last_activity"] = datetime.now(timezone.utc).isoformat()

        self._save_session(user_id, session)
        return session

    def clear_session(self, user_id: int) -> None:
        """Clear/delete a user's session."""
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
        now = datetime.now(timezone.utc)

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    session = json.load(f)

                last_activity = datetime.fromisoformat(session.get("last_activity", ""))
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)

                age_minutes = (now - last_activity).total_seconds() / 60

                if age_minutes > self.timeout_minutes:
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

    def _save_session(self, user_id: int, session: Dict[str, Any]) -> None:
        """Save session to disk."""
        session_path = self._get_session_path(user_id)

        try:
            with open(session_path, "w") as f:
                json.dump(session, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save session for user {user_id}: {e}")


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# =============================================================================
# Watchlist Management
# =============================================================================


class WatchlistManager:
    """
    Manages user watchlists.

    Watchlists are stored per-user in data directory.
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_tokens: int = 20,
    ):
        default_dir = Path(__file__).parent.parent.parent / "data" / "watchlists"
        self.data_dir = Path(data_dir) if data_dir else default_dir
        self.max_tokens = max_tokens
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_watchlist_path(self, user_id: int) -> Path:
        """Get path to watchlist file for user."""
        return self.data_dir / f"{user_id}_watchlist.json"

    def get_watchlist(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's watchlist."""
        watchlist_path = self._get_watchlist_path(user_id)

        if not watchlist_path.exists():
            return []

        try:
            with open(watchlist_path) as f:
                data = json.load(f)
            return data.get("tokens", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load watchlist for user {user_id}: {e}")
            return []

    def add_token(
        self,
        user_id: int,
        token_address: str,
        token_symbol: str,
    ) -> bool:
        """
        Add token to watchlist.

        Returns True if added, False if already exists or at limit.
        """
        watchlist = self.get_watchlist(user_id)

        # Check if already exists
        if any(t.get("address") == token_address for t in watchlist):
            return False

        # Check limit
        if len(watchlist) >= self.max_tokens:
            # Remove oldest to make room
            watchlist = watchlist[-(self.max_tokens - 1):]

        watchlist.append({
            "address": token_address,
            "symbol": token_symbol,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })

        self._save_watchlist(user_id, watchlist)
        return True

    def remove_token(self, user_id: int, token_address: str) -> bool:
        """
        Remove token from watchlist.

        Returns True if removed, False if not found.
        """
        watchlist = self.get_watchlist(user_id)

        original_len = len(watchlist)
        watchlist = [t for t in watchlist if t.get("address") != token_address]

        if len(watchlist) < original_len:
            self._save_watchlist(user_id, watchlist)
            return True

        return False

    def clear_watchlist(self, user_id: int) -> None:
        """Clear all tokens from watchlist."""
        self._save_watchlist(user_id, [])

    def _save_watchlist(self, user_id: int, tokens: List[Dict]) -> None:
        """Save watchlist to disk."""
        watchlist_path = self._get_watchlist_path(user_id)

        try:
            with open(watchlist_path, "w") as f:
                json.dump({"tokens": tokens}, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save watchlist for user {user_id}: {e}")


# =============================================================================
# Callback Routing
# =============================================================================


async def route_interactive_callback(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> bool:
    """
    Route interactive UI callbacks.

    Returns True if callback was handled, False otherwise.
    """
    data = query.data
    session_manager = get_session_manager()

    # Always answer callback first
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback: {e}")

    # Parse callback data
    if ":" in data:
        action, payload = data.split(":", 1)
    else:
        action = data
        payload = ""

    # Route based on action
    try:
        if action == "chart":
            await _handle_chart_callback(query, context, payload, user_id)
            return True

        elif action == "holders":
            await _handle_holders_callback(query, context, payload, user_id)
            return True

        elif action == "holders_page":
            parts = payload.split(":")
            if len(parts) >= 2:
                token_address = parts[0]
                page = int(parts[1])
                await _handle_holders_page(query, context, token_address, page, user_id)
            return True

        elif action == "trades":
            await _handle_trades_callback(query, context, payload, user_id)
            return True

        elif action == "signal":
            await _handle_signal_callback(query, context, payload, user_id)
            return True

        elif action == "details":
            await _handle_details_callback(query, context, payload, user_id)
            return True

        elif action == "analyze_back":
            await _handle_back_callback(query, context, payload, user_id)
            return True

        elif action == "ui_close":
            await _handle_close_callback(query, context, payload, user_id)
            return True

        elif action == "noop":
            # No-op callback for placeholder buttons
            return True

        else:
            return False

    except Exception as e:
        logger.error(f"Error handling interactive callback {data}: {e}")
        return False


async def _handle_chart_callback(query, context, token_address: str, user_id: int):
    """Handle chart button press."""
    from tg_bot.handlers.analyze_drill_down import format_chart_view

    session_manager = get_session_manager()
    session_manager.update_session(user_id, current_view="chart")

    message = format_chart_view(token_address)
    keyboard = build_chart_keyboard(token_address)

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_holders_callback(query, context, token_address: str, user_id: int):
    """Handle holders button press."""
    from tg_bot.handlers.analyze_drill_down import format_holders_view, fetch_holder_data

    session_manager = get_session_manager()
    session_manager.update_session(user_id, current_view="holders", page=1)

    # Fetch holder data
    holders = await fetch_holder_data(token_address)
    total_pages = max(1, (len(holders) + 24) // 25)

    message = format_holders_view(token_address, holders[:25], page=1, total_pages=total_pages)
    keyboard = build_holder_pagination_keyboard(token_address, page=1, total_pages=total_pages)

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_holders_page(query, context, token_address: str, page: int, user_id: int):
    """Handle holder pagination."""
    from tg_bot.handlers.analyze_drill_down import format_holders_view, fetch_holder_data

    session_manager = get_session_manager()
    session_manager.update_session(user_id, page=page)

    holders = await fetch_holder_data(token_address)
    total_pages = max(1, (len(holders) + 24) // 25)

    start_idx = (page - 1) * 25
    end_idx = start_idx + 25
    page_holders = holders[start_idx:end_idx]

    message = format_holders_view(token_address, page_holders, page=page, total_pages=total_pages)
    keyboard = build_holder_pagination_keyboard(token_address, page=page, total_pages=total_pages)

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_trades_callback(query, context, token_address: str, user_id: int):
    """Handle trades button press."""
    from tg_bot.handlers.analyze_drill_down import format_trades_view, fetch_recent_trades

    session_manager = get_session_manager()
    session_manager.update_session(user_id, current_view="trades")

    trades = await fetch_recent_trades(token_address)
    message = format_trades_view(token_address, trades)
    keyboard = build_trades_keyboard(token_address)

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_signal_callback(query, context, token_address: str, user_id: int):
    """Handle signal button press."""
    from tg_bot.handlers.analyze_drill_down import format_signal_view

    session_manager = get_session_manager()
    session_manager.update_session(user_id, current_view="signal")

    message = await format_signal_view(token_address)
    keyboard = build_signal_keyboard(token_address, "")

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_details_callback(query, context, token_address: str, user_id: int):
    """Handle details button press."""
    from tg_bot.handlers.analyze_drill_down import format_details_view

    session_manager = get_session_manager()
    session_manager.update_session(user_id, current_view="details")

    message = await format_details_view(token_address)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("↩️ Previous Menu", callback_data=f"analyze_back:{token_address}"),
            InlineKeyboardButton("Close", callback_data=f"ui_close:{token_address}"),
        ]
    ])

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_back_callback(query, context, token_address: str, user_id: int):
    """Handle back button press - return to main analysis view."""
    from tg_bot.handlers.analyze_drill_down import format_main_analysis

    session_manager = get_session_manager()
    session = session_manager.get_session(user_id)

    token_symbol = session.get("token_symbol", "") if session else ""
    session_manager.update_session(user_id, current_view="main")

    message = await format_main_analysis(token_address, token_symbol)
    keyboard = build_analyze_keyboard(token_address, token_symbol)

    try:
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def _handle_close_callback(query, context, token_address: str, user_id: int):
    """Handle close button press - delete message and clear session."""
    session_manager = get_session_manager()
    session_manager.clear_session(user_id)

    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete message: {e}")
        # Fallback: edit to show closed message
        try:
            await query.message.edit_text("_Analysis closed._", parse_mode="Markdown")
        except Exception:
            pass


__all__ = [
    "is_new_ui_enabled",
    "build_analyze_keyboard",
    "build_holder_pagination_keyboard",
    "build_signal_keyboard",
    "build_comparison_keyboard",
    "build_watchlist_keyboard",
    "build_trades_keyboard",
    "build_chart_keyboard",
    "SessionManager",
    "WatchlistManager",
    "get_session_manager",
    "route_interactive_callback",
]
