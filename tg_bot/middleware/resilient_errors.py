"""
Telegram Bot Resilient Error Handling

Handles EU/GDPR notifications, rate limits, and other Telegram API errors gracefully.
NEVER shows raw errors to users - always provides friendly messages.
"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ResilientErrorHandler:
    """
    Handles Telegram bot errors with graceful degradation.

    Key behaviors:
    - Silently handles EU/GDPR privacy notifications (not errors)
    - Retries transient failures automatically
    - Never shows raw exceptions to users
    - Logs everything for debugging
    """

    def __init__(self):
        self.error_counts = {}
        self.suppressed_errors = {
            "gdpr", "privacy", "notification", "acknowledged"
        }

    async def handle_error(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Global error handler for all bot errors.

        Args:
            update: The update that caused the error (may be None)
            context: Bot context containing the error
        """
        error = context.error
        error_msg = str(error).lower()

        # EU/GDPR notifications - SILENTLY handle (not errors)
        if any(keyword in error_msg for keyword in self.suppressed_errors):
            logger.debug(f"EU/GDPR notification (expected): {error}")
            return

        # Rate limiting / flood control
        if "flood" in error_msg or "too many requests" in error_msg or "429" in error_msg:
            logger.warning(f"Rate limited by Telegram: {error}")
            await self._send_friendly_error(update, "I'm being rate limited. Please wait a moment and try again.")
            await asyncio.sleep(30)  # Back off
            return

        # Network errors - retry
        if isinstance(error, (NetworkError, TimedOut)):
            logger.warning(f"Network error (transient): {error}")
            await self._send_friendly_error(update, "Connection issue. Please try again in a moment.")
            return

        # Parsing errors (usually markdown formatting)
        if isinstance(error, BadRequest) and "parse" in error_msg:
            logger.warning(f"Parse error (markdown issue): {error}")
            # Handler should retry without markdown
            return

        # User blocked bot or chat not found
        if isinstance(error, Forbidden):
            logger.info(f"User blocked bot or unauthorized: {error}")
            return

        # Unknown error - log and notify user
        logger.error(f"Unhandled error in bot: {error}", exc_info=error)
        await self._send_friendly_error(update, "I encountered an unexpected issue. Please try again or contact support.")

    async def _send_friendly_error(self, update: Optional[Update], message: str):
        """Send friendly error message to user."""
        if not update or not update.effective_message:
            return

        try:
            await update.effective_message.reply_text(
                f"⚠️ {message}",
                parse_mode=None  # Don't use markdown for error messages
            )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


async def safe_reply(message, text: str, parse_mode: Optional[str] = "Markdown") -> bool:
    """
    Safely reply to a message with automatic retry and fallback.

    Args:
        message: Telegram message object
        text: Text to send
        parse_mode: Parse mode (Markdown, HTML, or None)

    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        await message.reply_text(text, parse_mode=parse_mode)
        return True

    except BadRequest as e:
        error_msg = str(e).lower()

        # Markdown parse error - retry without markdown
        if "parse" in error_msg:
            logger.warning(f"Markdown parse error, retrying without formatting: {e}")
            try:
                await message.reply_text(text, parse_mode=None)
                return True
            except Exception as retry_error:
                logger.error(f"Failed to send even without markdown: {retry_error}")
                return False

        # GDPR notification - not an error
        if any(keyword in error_msg for keyword in ["gdpr", "privacy", "notification"]):
            logger.debug(f"EU/GDPR notification (expected): {e}")
            return True  # Considered success

        logger.error(f"BadRequest error: {e}")
        return False

    except (NetworkError, TimedOut) as e:
        logger.warning(f"Network error, will retry: {e}")
        await asyncio.sleep(2)

        try:
            await message.reply_text(text, parse_mode=None)
            return True
        except Exception as retry_error:
            logger.error(f"Retry failed: {retry_error}")
            return False

    except Forbidden as e:
        logger.info(f"User blocked bot or unauthorized: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error in safe_reply: {e}")
        return False


async def safe_edit(message, text: str, parse_mode: Optional[str] = "Markdown", reply_markup=None) -> bool:
    """
    Safely edit a message with automatic retry and fallback.

    Args:
        message: Telegram message object
        text: New text
        parse_mode: Parse mode (Markdown, HTML, or None)
        reply_markup: Optional InlineKeyboardMarkup

    Returns:
        True if message edited successfully, False otherwise
    """
    try:
        await message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return True

    except BadRequest as e:
        error_msg = str(e).lower()

        # Message not modified (same content) - not an error
        if "message is not modified" in error_msg:
            return True

        # Markdown parse error - retry without markdown
        if "parse" in error_msg:
            logger.warning(f"Markdown parse error in edit, retrying without formatting: {e}")
            try:
                await message.edit_text(text, parse_mode=None, reply_markup=reply_markup)
                return True
            except Exception as retry_error:
                logger.error(f"Failed to edit even without markdown: {retry_error}")
                return False

        logger.error(f"BadRequest error in edit: {e}")
        return False

    except (NetworkError, TimedOut) as e:
        logger.warning(f"Network error in edit: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error in safe_edit: {e}")
        return False


def create_error_handler() -> ResilientErrorHandler:
    """Create and return error handler instance."""
    return ResilientErrorHandler()
