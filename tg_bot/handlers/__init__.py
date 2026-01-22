"""Handlers for Jarvis Telegram Bot."""

import logging
from typing import Callable, Awaitable, Any

from telegram.constants import ParseMode
from telegram.error import RetryAfter, BadRequest

from tg_bot.config import get_config
from tg_bot.services.cost_tracker import get_tracker
from tg_bot.services import digest_formatter as fmt

# Import error tracker for centralized error logging
try:
    from core.logging.error_tracker import error_tracker
    ERROR_TRACKER_AVAILABLE = True
except ImportError:
    error_tracker = None
    ERROR_TRACKER_AVAILABLE = False

logger = logging.getLogger(__name__)


def error_handler(func: Callable[..., Awaitable[Any]]):
    """Decorator to catch handler errors and respond safely."""
    async def wrapper(update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as exc:
            if isinstance(exc, RetryAfter):
                logger.warning(
                    "Rate limited in %s, retry after %ss",
                    func.__name__,
                    exc.retry_after,
                )
                return None

            if isinstance(exc, BadRequest) and "Can't parse entities" in str(exc):
                logger.warning(
                    "Parse error in %s; skipping reply to avoid retries",
                    func.__name__,
                )
                return None
            if isinstance(exc, BadRequest) and "Message is not modified" in str(exc):
                logger.debug(
                    "Message unchanged in %s; skipping edit",
                    func.__name__,
                )
                return None

            logger.exception(f"Handler error in {func.__name__}")

            # Track error for deduplication and persistence
            if ERROR_TRACKER_AVAILABLE and error_tracker:
                user_id = update.effective_user.id if update and update.effective_user else 0
                error_tracker.track_error(
                    exc,
                    context=f"telegram_handler.{func.__name__}",
                    component="telegram_bot",
                    metadata={"user_id": user_id, "handler": func.__name__}
                )

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
        import logging
        logger = logging.getLogger(__name__)

        config = get_config()
        user_id = update.effective_user.id if update and update.effective_user else 0
        username = update.effective_user.username if update and update.effective_user else None

        if not config.is_admin(user_id, username):
            logger.warning(f"Unauthorized admin command attempt by user {user_id} (@{username})")
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
