"""Handle custom buy amount input."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..demo_ui import DemoMenuBuilder, JarvisTheme, safe_symbol
from ..demo_sentiment import get_ai_sentiment_for_token
from ..demo_trading import validate_buy_amount
from .utils import resolve_token_ref

logger = logging.getLogger(__name__)


async def handle_custom_buy_amount(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str
) -> bool:
    """
    Handle custom buy amount input.
    
    Args:
        update: Telegram update
        context: Bot context
        text: User input text
        
    Returns:
        True if handled, False if not applicable
    """
    if not context.user_data.get("awaiting_custom_buy_amount"):
        return False
        
    context.user_data["awaiting_custom_buy_amount"] = False
    token_ref = context.user_data.pop("custom_buy_token_ref", "")

    try:
        amount = float(text)
        is_valid, error_msg = validate_buy_amount(amount)

        if not is_valid:
            error_text, keyboard = DemoMenuBuilder.error_message(error_msg)
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return True

        token_addr = resolve_token_ref(context, token_ref)
        sentiment_data = await get_ai_sentiment_for_token(token_addr)
        token_symbol = sentiment_data.get("symbol", "TOKEN")
        token_price = sentiment_data.get("price", 0) or 0
        sentiment = sentiment_data.get("sentiment", "neutral")
        score = sentiment_data.get("score", 0)
        signal = sentiment_data.get("signal", "NEUTRAL")

        theme = JarvisTheme
        confirm_text = f"""
{theme.BUY} *CONFIRM CUSTOM BUY*

*Token:* {safe_symbol(token_symbol)}
*Amount:* {amount} SOL
*Est. Price:* ${token_price:.8f}

{theme.AUTO} *AI Analysis*
- Sentiment: *{sentiment.upper()}*
- Score: *{score:.2f}*
- Signal: *{signal}*

_Tap Confirm to execute_
"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{theme.SUCCESS} Confirm Buy",
                    callback_data=f"demo:execute_buy:{token_ref}:{amount}",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{theme.CLOSE} Cancel",
                    callback_data="demo:main",
                ),
            ],
        ])

        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except ValueError:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid amount. Please enter a number like 0.5 or 2.5"
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as exc:
        logger.error(f"Custom buy amount error: {exc}")
        error_text, keyboard = DemoMenuBuilder.error_message(
            f"Error: {str(exc)[:50]}"
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    
    return True


async def handle_custom_hub_amount(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str
) -> bool:
    """
    Handle custom hub buy amount input (from Blue Chips menu).
    
    Args:
        update: Telegram update
        context: Bot context
        text: User input text
        
    Returns:
        True if handled, False if not applicable
    """
    if not context.user_data.get("awaiting_custom_hub_amount"):
        return False
        
    context.user_data["awaiting_custom_hub_amount"] = False
    token_ref = context.user_data.pop("custom_hub_token_ref", "")
    sl_percent = context.user_data.pop("custom_hub_sl_percent", 15.0)
    address = context.user_data.pop("custom_hub_address", "")

    try:
        amount = float(text)
        
        # Validate amount
        if amount < 0.01:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Minimum buy amount is 0.01 SOL"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return True
        
        if amount > 10:
            error_text, keyboard = DemoMenuBuilder.error_message(
                "Maximum buy amount is 10 SOL for safety"
            )
            await update.message.reply_text(
                error_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
            return True

        # Get token info
        sentiment_data = await get_ai_sentiment_for_token(address)
        token_symbol = sentiment_data.get("symbol", "TOKEN")
        token_price = sentiment_data.get("price", 0) or 0
        sentiment = sentiment_data.get("sentiment", "neutral")
        score = sentiment_data.get("score", 0)

        theme = JarvisTheme
        confirm_text = f"""
{theme.BUY} *CONFIRM CUSTOM BUY*
{'=' * 24}

*Token:* {safe_symbol(token_symbol)}
*Amount:* {amount} SOL
*Price:* ${token_price:.8f}
*Stop-Loss:* -{sl_percent}%

{theme.AUTO} *AI Sentiment*
- {sentiment.upper()} | Score: {score:.0f}/100

_Tap Confirm to execute trade_
"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ Confirm {amount} SOL",
                    callback_data=f"demo:hub_buy:{token_ref}:{sl_percent}:{amount}",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"❌ Cancel",
                    callback_data="demo:hub_bluechips",
                ),
            ],
        ])

        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except ValueError:
        error_text, keyboard = DemoMenuBuilder.error_message(
            "Invalid amount. Please enter a number like 0.25, 0.5, or 1.5"
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as exc:
        logger.error(f"Custom hub amount error: {exc}")
        error_text, keyboard = DemoMenuBuilder.error_message(
            f"Error: {str(exc)[:50]}"
        )
        await update.message.reply_text(
            error_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    
    return True
