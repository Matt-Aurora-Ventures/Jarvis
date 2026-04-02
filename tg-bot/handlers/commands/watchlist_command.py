"""
/watchlist Command Handler.

Provides user watchlist management with:
- Add/remove tokens
- View watchlist with current prices
- Interactive buttons for each token
- Persistence to user-specific files
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler

logger = logging.getLogger(__name__)

# Default watchlist directory
DEFAULT_WATCHLIST_DIR = Path.home() / ".lifeos" / "trading" / "user_watchlists"

# Known token mappings
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
}


class WatchlistManager:
    """
    Manages user watchlists with file persistence.

    Each user has their own watchlist file with max 50 tokens.
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_tokens: int = 50,
    ):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_WATCHLIST_DIR
        self.max_tokens = max_tokens

        # Create directory if needed
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create watchlist directory: {e}")

    def _get_watchlist_path(self, user_id: int) -> Path:
        """Get path to user's watchlist file."""
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

        # Enforce limit - remove oldest if needed
        if len(watchlist) >= self.max_tokens:
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


def format_watchlist_display(
    watchlist: List[Dict[str, Any]],
    prices: Dict[str, Dict[str, Any]],
) -> str:
    """
    Format watchlist for display.

    Args:
        watchlist: List of token entries
        prices: Dict of address -> price data

    Returns:
        Formatted markdown string
    """
    lines = []

    lines.append(f"*Your Watchlist* ({len(watchlist)} tokens)")
    lines.append("")

    if not watchlist:
        lines.append("_Your watchlist is empty_")
        lines.append("")
        lines.append("Add tokens with `/watchlist add <token>`")
        return "\n".join(lines)

    for item in watchlist:
        symbol = item.get("symbol", "???")
        address = item.get("address", "")

        price_data = prices.get(address, {})
        price = price_data.get("price_usd", 0)
        change = price_data.get("price_change_24h", 0)

        # Status indicator
        if change > 5:
            status = "🟢"
        elif change > 0:
            status = "📈"
        elif change < -5:
            status = "🔴"
        elif change < 0:
            status = "📉"
        else:
            status = "⚪"

        if price > 0:
            if price >= 1:
                price_str = f"${price:.2f}"
            elif price >= 0.01:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:.6f}"

            change_str = f"{'+'if change >= 0 else ''}{change:.1f}%"
            lines.append(f"{status} *{symbol}* - {price_str} {change_str}")
        else:
            lines.append(f"{status} *{symbol}*")

    return "\n".join(lines)


async def fetch_current_prices(
    addresses: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current prices for multiple tokens.

    Returns dict of address -> {price_usd, price_change_24h}
    """
    prices = {}

    try:
        from tg_bot.services.signal_service import get_signal_service

        service = get_signal_service()

        for address in addresses:
            try:
                signal = await service.get_comprehensive_signal(
                    address,
                    include_sentiment=False,
                )
                prices[address] = {
                    "price_usd": signal.price_usd,
                    "price_change_24h": signal.price_change_24h,
                }
            except Exception:
                prices[address] = {}

    except Exception as e:
        logger.warning(f"Failed to fetch prices: {e}")

    return prices


@error_handler
async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /watchlist command.

    Usage:
    - /watchlist - Show watchlist
    - /watchlist add SOL - Add token
    - /watchlist remove SOL - Remove token
    - /watchlist alert SOL 100 above - Set price alert
    - /watchlist alerts - Show active alerts
    """
    user_id = update.effective_user.id if update.effective_user else 0

    if not user_id:
        await update.message.reply_text("Could not identify user.")
        return

    manager = WatchlistManager()

    # Parse subcommand
    if context.args and len(context.args) >= 2:
        subcommand = context.args[0].lower()
        token = context.args[1]

        # Resolve token
        address = KNOWN_TOKENS.get(token.upper(), token)
        symbol = token.upper() if token.upper() in KNOWN_TOKENS else token[:8]

        if subcommand == "add":
            added = manager.add_token(user_id, address, symbol)

            if added:
                await update.message.reply_text(
                    f"Added *{symbol}* to your watchlist.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    f"*{symbol}* is already on your watchlist or limit reached.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        elif subcommand == "remove":
            removed = manager.remove_token(user_id, address)

            if removed:
                await update.message.reply_text(
                    f"Removed *{symbol}* from your watchlist.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    f"*{symbol}* was not on your watchlist.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        elif subcommand == "alert":
            # /watchlist alert SOL 100 above
            if len(context.args) < 4:
                await update.message.reply_text(
                    "*Usage:* `/watchlist alert <token> <price> <above|below>`\n\n"
                    "Example: `/watchlist alert SOL 100 above`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            try:
                target_price = float(context.args[2])
                direction = context.args[3].lower()

                if direction not in ["above", "below"]:
                    await update.message.reply_text(
                        "Direction must be 'above' or 'below'",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                # Create alert using core price_alerts system
                from core.price_alerts import create_price_alert, AlertType

                alert_type = AlertType.PRICE_ABOVE if direction == "above" else AlertType.PRICE_BELOW
                alert = create_price_alert(
                    token_symbol=symbol,
                    token_mint=address,
                    alert_type=alert_type,
                    threshold=target_price,
                    note=f"Watchlist alert for {symbol}",
                    repeat=False,
                )

                await update.message.reply_text(
                    f"Alert set for *{symbol}*\n"
                    f"Price {direction} ${target_price:.6f}\n\n"
                    f"Alert ID: `{alert.id}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except ValueError:
                await update.message.reply_text(
                    "Invalid price value. Use a number.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

    # Show active alerts
    if context.args and context.args[0].lower() == "alerts":
        from core.price_alerts import get_alert_manager, AlertStatus

        alert_mgr = get_alert_manager()
        alerts = alert_mgr.list_alerts(status=AlertStatus.ACTIVE)

        if not alerts:
            await update.message.reply_text(
                "*Active Alerts*\n\nNo active alerts.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        lines = ["*Active Price Alerts*", ""]
        for alert in alerts:
            direction = "above" if "above" in alert.alert_type.value else "below"
            lines.append(
                f"• *{alert.token_symbol}* - {direction} ${alert.threshold:.6f}\n"
                f"  ID: `{alert.id}`"
            )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Show watchlist
    watchlist = manager.get_watchlist(user_id)

    # Fetch current prices
    addresses = [item.get("address") for item in watchlist if item.get("address")]
    prices = await fetch_current_prices(addresses) if addresses else {}

    # Format display
    message = format_watchlist_display(watchlist, prices)

    # Build keyboard
    from tg_bot.ui.inline_buttons import build_watchlist_keyboard
    keyboard = build_watchlist_keyboard(watchlist, user_id)

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def handle_watchlist_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle watchlist inline button callbacks.

    Callback formats:
    - watch_view:<address>
    - watch_remove:<address>
    - watch_add
    - watch_refresh
    - watch_clear
    - watch_alert:<address>
    """
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    user_id = query.from_user.id if query.from_user else 0

    # Parse callback
    parts = data.split(":", 1)
    action = parts[0]
    payload = parts[1] if len(parts) > 1 else ""

    manager = WatchlistManager()

    try:
        if action == "watch_alert":
            # Set price alert for watchlisted token
            await query.message.edit_text(
                "*Set Price Alert*\n\n"
                "Use command:\n"
                "`/watchlist alert <token> <price> [above|below]`\n\n"
                "Examples:\n"
                "`/watchlist alert SOL 100 above`\n"
                "`/watchlist alert BONK 0.00001 below`",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif action == "watch_view":
            # View token analysis
            from tg_bot.services.signal_service import get_signal_service
            from tg_bot.ui.token_analysis_view import TokenAnalysisView
            from tg_bot.ui.inline_buttons import TokenAnalysisButtons

            service = get_signal_service()
            signal = await service.get_comprehensive_signal(payload, include_sentiment=False)

            view = TokenAnalysisView()
            buttons = TokenAnalysisButtons()

            message = view.format_main_view(signal)
            keyboard = buttons.build_main_keyboard(payload, signal.symbol)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        elif action == "watch_remove":
            # Remove token
            removed = manager.remove_token(user_id, payload)

            # Refresh display
            watchlist = manager.get_watchlist(user_id)
            addresses = [item.get("address") for item in watchlist if item.get("address")]
            prices = await fetch_current_prices(addresses) if addresses else {}

            message = format_watchlist_display(watchlist, prices)

            from tg_bot.ui.inline_buttons import build_watchlist_keyboard
            keyboard = build_watchlist_keyboard(watchlist, user_id)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "watch_add":
            # Prompt for token
            await query.message.edit_text(
                "*Add Token*\n\n"
                "Use command:\n"
                "`/watchlist add <token>`\n\n"
                "Examples:\n"
                "`/watchlist add SOL`\n"
                "`/watchlist add BONK`",
                parse_mode=ParseMode.MARKDOWN,
            )

        elif action == "watch_refresh":
            # Refresh prices
            watchlist = manager.get_watchlist(user_id)
            addresses = [item.get("address") for item in watchlist if item.get("address")]
            prices = await fetch_current_prices(addresses) if addresses else {}

            message = format_watchlist_display(watchlist, prices)

            from tg_bot.ui.inline_buttons import build_watchlist_keyboard
            keyboard = build_watchlist_keyboard(watchlist, user_id)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "watch_clear":
            # Clear watchlist
            manager.clear_watchlist(user_id)

            message = format_watchlist_display([], {})

            from tg_bot.ui.inline_buttons import build_watchlist_keyboard
            keyboard = build_watchlist_keyboard([], user_id)

            await query.message.edit_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        elif action == "ui_close":
            try:
                await query.message.delete()
            except Exception:
                await query.message.edit_text(
                    "_Watchlist closed._",
                    parse_mode=ParseMode.MARKDOWN,
                )

    except Exception as e:
        logger.error(f"Watchlist callback error: {e}")
        try:
            await query.message.edit_text(
                f"*Error*\n\n_Failed to process action_\n\n`{str(e)[:100]}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


@error_handler
async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Quick command to add token to watchlist.

    Usage: /watch <token>
    Example: /watch SOL
    """
    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/watch <token>`\n\n"
            "Example: `/watch SOL`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id if update.effective_user else 0
    if not user_id:
        await update.message.reply_text("Could not identify user.")
        return

    token = context.args[0]
    address = KNOWN_TOKENS.get(token.upper(), token)
    symbol = token.upper() if token.upper() in KNOWN_TOKENS else token[:8]

    manager = WatchlistManager()
    added = manager.add_token(user_id, address, symbol)

    if added:
        await update.message.reply_text(
            f"Added *{symbol}* to your watchlist.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"*{symbol}* is already on your watchlist or limit reached.",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Quick command to remove token from watchlist.

    Usage: /unwatch <token>
    Example: /unwatch SOL
    """
    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/unwatch <token>`\n\n"
            "Example: `/unwatch SOL`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = update.effective_user.id if update.effective_user else 0
    if not user_id:
        await update.message.reply_text("Could not identify user.")
        return

    token = context.args[0]
    address = KNOWN_TOKENS.get(token.upper(), token)
    symbol = token.upper() if token.upper() in KNOWN_TOKENS else token[:8]

    manager = WatchlistManager()
    removed = manager.remove_token(user_id, address)

    if removed:
        await update.message.reply_text(
            f"Removed *{symbol}* from your watchlist.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"*{symbol}* was not on your watchlist.",
            parse_mode=ParseMode.MARKDOWN,
        )


__all__ = [
    "watchlist_command",
    "watch_command",
    "unwatch_command",
    "handle_watchlist_callback",
    "WatchlistManager",
    "format_watchlist_display",
    "fetch_current_prices",
]
