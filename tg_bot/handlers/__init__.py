"""Handlers for Jarvis Telegram Bot."""

import logging
from typing import Callable, Awaitable, Any

from telegram.constants import ParseMode

from tg_bot.config import get_config
from tg_bot.services.cost_tracker import get_tracker
from tg_bot.services import digest_formatter as fmt

logger = logging.getLogger(__name__)


def error_handler(func: Callable[..., Awaitable[Any]]):
    """Decorator to catch handler errors and respond safely."""
    async def wrapper(update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as exc:
            logger.exception(f"Handler error in {func.__name__}")

            # Send user-friendly message
            try:
                message = "Sorry, something went wrong. Please try again later."
                if update and getattr(update, "effective_message", None):
                    await update.effective_message.reply_text(message)
                elif update and getattr(update, "effective_chat", None):
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message
                    )
            except Exception:
                pass

            # Optional admin notification
            try:
                config = get_config()
                for admin_id in config.admin_ids:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"Handler error in {func.__name__}: {exc}"
                    )
            except Exception:
                pass

            return None

    return wrapper


def admin_only(func: Callable[..., Awaitable[Any]]):
    """Decorator to restrict command to admins only."""
    async def wrapper(update, context, *args, **kwargs):
        config = get_config()
        user_id = update.effective_user.id if update and update.effective_user else 0

        if user_id not in config.admin_ids:
            await update.message.reply_text(
                fmt.format_unauthorized(),
                parse_mode=ParseMode.MARKDOWN,
            )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def rate_limited(func: Callable[..., Awaitable[Any]]):
    """Decorator to check rate limits for expensive operations."""
    async def wrapper(update, context, *args, **kwargs):
        tracker = get_tracker()
        can_proceed, reason = tracker.can_make_sentiment_call()

        if not can_proceed:
            await update.message.reply_text(
                fmt.format_rate_limit(reason),
                parse_mode=ParseMode.MARKDOWN,
            )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


# Import handler modules for easy access
from tg_bot.handlers import system
from tg_bot.handlers import paper_trading

__all__ = [
    "error_handler",
    "admin_only",
    "rate_limited",
    "system",
    "paper_trading",
]
