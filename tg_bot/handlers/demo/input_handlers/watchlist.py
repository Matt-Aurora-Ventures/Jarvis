"""Handle watchlist token addition."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..demo_ui import DemoMenuBuilder
from ..demo_sentiment import get_ai_sentiment_for_token
from .utils import register_token_id

logger = logging.getLogger(__name__)


async def handle_watchlist_token(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str
) -> bool:
    """
    Handle watchlist token addition input.
    
    Args:
        update: Telegram update
        context: Bot context
        text: User input (token address)
        
    Returns:
        True if handled, False if not applicable
    """
    if not context.user_data.get("awaiting_watchlist_token"):
        return False
        
    context.user_data["awaiting_watchlist_token"] = False

    # Validate address length
    if len(text) < 32 or len(text) > 44:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid Solana address. Must be 32-44 characters."
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        return True

    try:
        sentiment = await get_ai_sentiment_for_token(text)
        token_data = {
            "symbol": sentiment.get("symbol", "TOKEN"),
            "address": text,
            "price": sentiment.get("price", 0),
            "change_24h": sentiment.get("change_24h", 0),
        }
        token_data["token_id"] = register_token_id(context, text)

        watchlist = context.user_data.get("watchlist", [])
        if any(t.get("address") == text for t in watchlist):
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Token already in watchlist"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return True

        watchlist.append(token_data)
        context.user_data["watchlist"] = watchlist

        success_text, keyboard = DemoMenuBuilder.success_message(
            action="Token Added",
            details=f"Added {token_data['symbol']} to your watchlist!\n\n"
                    f"Current price: ${token_data['price']:.6f}",
        )
        await update.message.reply_text(
            success_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as exc:
        error_text, keyboard = DemoMenuBuilder.error_message(
            f"Failed to add token: {str(exc)[:50]}"
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    
    return True
