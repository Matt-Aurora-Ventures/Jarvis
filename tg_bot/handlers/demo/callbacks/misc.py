"""
Demo Bot - Miscellaneous Callback Handler

Handles: new_pairs and other misc callbacks
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_misc(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle miscellaneous callbacks.

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

    if action == "new_pairs":
        text = f"""
{theme.GEM} *NEW PAIRS*
{'=' * 20}

_Scanning for new liquidity pools..._

This feature monitors Raydium and Orca
for fresh token launches.

Coming soon in V2!
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:main")],
        ])
        return text, keyboard

    # Default - return to main menu
    DemoMenuBuilder = ctx.DemoMenuBuilder
    return DemoMenuBuilder.main_menu(
        wallet_address=state.get("wallet_address", "Not configured"),
        sol_balance=state.get("sol_balance", 0.0),
        usd_value=state.get("usd_value", 0.0),
        is_live=state.get("is_live", False),
        open_positions=len(state.get("positions", [])),
        total_pnl=state.get("total_pnl", 0.0),
        market_regime=state.get("market_regime", {}),
        ai_auto_enabled=state.get("ai_auto_enabled", False),
    )
