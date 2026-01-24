"""
Demo Bot - Navigation Callback Handler

Handles: main, refresh, close, noop
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_navigation(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle navigation callbacks: main, refresh, close, noop.

    Args:
        ctx: DemoContextLoader instance
        action: The action (main, refresh, close, noop)
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict with:
            - wallet_address
            - sol_balance
            - usd_value
            - is_live
            - positions
            - market_regime
            - ai_auto_enabled

    Returns:
        Tuple of (text, keyboard)
    """
    query = update.callback_query

    if action == "noop":
        # No-op for label buttons
        await query.answer("This is a label")
        return None, None  # Signal to not edit message

    if action == "close":
        # Delete the message
        await query.message.delete()
        return None, None  # Signal already handled

    # main or refresh - show main menu
    return ctx.DemoMenuBuilder.main_menu(
        wallet_address=state.get("wallet_address", "Not configured"),
        sol_balance=state.get("sol_balance", 0.0),
        usd_value=state.get("usd_value", 0.0),
        is_live=state.get("is_live", False),
        open_positions=len(state.get("positions", [])),
        total_pnl=state.get("total_pnl", 0.0),
        market_regime=state.get("market_regime", {}),
        ai_auto_enabled=state.get("ai_auto_enabled", False),
    )
