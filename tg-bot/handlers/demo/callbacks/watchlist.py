"""
Demo Bot - Watchlist Callback Handler

Handles: watchlist, watchlist_add, watchlist_remove
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_watchlist(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle watchlist callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme
    DemoMenuBuilder = ctx.DemoMenuBuilder

    if action == "watchlist":
        watchlist = context.user_data.get("watchlist", [])

        # Fetch live prices for watchlist tokens
        if watchlist:
            for token in watchlist:
                try:
                    address = token.get("address", "")
                    if address:
                        sentiment = await ctx.get_ai_sentiment_for_token(address)
                        token["price"] = sentiment.get("price", token.get("price", 0))
                        token["change_24h"] = sentiment.get("change_24h", token.get("change_24h", 0))
                        token["token_id"] = ctx.register_token_id(context, address)
                except Exception:
                    pass

        return DemoMenuBuilder.watchlist_menu(watchlist)

    elif action == "watchlist_add":
        text = f"""
{theme.GEM} *ADD TO WATCHLIST*
{'=' * 20}

Paste a Solana token address
to add it to your watchlist.

Example:
`DezXAZ8z7PnrnRJjz3...`

The token will be tracked with
live price updates!
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Cancel", callback_data="demo:watchlist")],
        ])
        context.user_data["awaiting_watchlist_token"] = True
        return text, keyboard

    elif data.startswith("demo:watchlist_remove:"):
        parts = data.split(":")
        if len(parts) >= 3:
            try:
                index = int(parts[2])
                watchlist = context.user_data.get("watchlist", [])
                if 0 <= index < len(watchlist):
                    removed = watchlist.pop(index)
                    context.user_data["watchlist"] = watchlist
                    return DemoMenuBuilder.success_message(
                        action="Token Removed",
                        details=f"Removed {removed.get('symbol', 'token')} from watchlist",
                    )
                else:
                    return DemoMenuBuilder.error_message("Invalid watchlist index")
            except Exception as e:
                return DemoMenuBuilder.error_message(f"Failed to remove: {e}")
        else:
            return DemoMenuBuilder.error_message("Invalid remove command")

    # Default
    watchlist = context.user_data.get("watchlist", [])
    return DemoMenuBuilder.watchlist_menu(watchlist)
