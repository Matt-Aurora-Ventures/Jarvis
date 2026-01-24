"""
Demo Bot - Analysis Callback Handler

Handles: analyze:*
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_analysis(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle analysis callbacks.

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
    DemoMenuBuilder = ctx.DemoMenuBuilder

    if data.startswith("demo:analyze:"):
        parts = data.split(":")
        if len(parts) >= 3:
            token_ref = parts[2]
            token_address = ctx.resolve_token_ref(context, token_ref)
            sentiment_data = await ctx.get_ai_sentiment_for_token(token_address)
            token_data = {
                "symbol": sentiment_data.get("symbol", "TOKEN"),
                "address": token_address,
                "token_id": token_ref,
                "price_usd": sentiment_data.get("price", 0),
                "change_24h": sentiment_data.get("change_24h", 0),
                "volume": sentiment_data.get("volume", 0),
                "liquidity": sentiment_data.get("liquidity", 0),
                "sentiment": sentiment_data.get("sentiment", "neutral"),
                "score": sentiment_data.get("score", 0),
                "confidence": sentiment_data.get("confidence", 0),
                "signal": sentiment_data.get("signal", "NEUTRAL"),
                "reasons": sentiment_data.get("reasons", []),
            }
            return DemoMenuBuilder.token_analysis_menu(token_data)
        else:
            return DemoMenuBuilder.error_message("Invalid token address")

    # Default
    return DemoMenuBuilder.error_message("Invalid analysis request")
