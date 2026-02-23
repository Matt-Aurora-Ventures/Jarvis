"""Handle token address input for buying."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import time

from ..demo_ui import DemoMenuBuilder
from tg_bot.handlers.demo.demo_trading import _register_token_id

logger = logging.getLogger(__name__)


async def handle_token_input(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str
) -> bool:
    """
    Handle token address input for buying.
    
    Args:
        update: Telegram update
        context: Bot context
        text: User input (token address)
        
    Returns:
        True if handled, False if not applicable
    """
    if not context.user_data.get("awaiting_token"):
        return False
        
    context.user_data["awaiting_token"] = False

    # Validate address length
    if len(text) < 32 or len(text) > 44:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid Solana address. Must be 32-44 characters."
        )
        try:
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        except Exception:
            pass
        return True

    # Store pending token context for follow-up actions (buy buttons, etc.)
    context.user_data["pending_token"] = text
    context.user_data["pending_token_time"] = time.time()

    amount = context.user_data.get("buy_amount", 0.1)

    # IMPORTANT: Use the same token-ref registry as the trading callbacks
    # (demo_trading._resolve_token_ref expects token_id_map)
    token_ref = _register_token_id(context, text)

    confirm_text, keyboard = DemoMenuBuilder.buy_confirmation(
        token_symbol="TOKEN",
        token_address=text,
        amount_sol=amount,
        estimated_tokens=1000000,
        price_usd=0.00001,
        token_ref=token_ref,
    )

    try:
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception:
        pass
    return True
