"""
/health and /status commands - System health and provider status

Shows:
- Provider health status (XAI, Groq, Ollama, etc.)
- Circuit breaker states
- Success rates
- Last errors
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from core.resilient_provider import get_resilient_provider
from tg_bot.middleware.resilient_errors import safe_reply

logger = logging.getLogger(__name__)


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show provider health status.

    Usage: /health or /status
    """
    try:
        provider = get_resilient_provider()

        # Get human-readable status
        status_message = provider.get_status_message()

        await safe_reply(update.effective_message, status_message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in health_command: {e}")
        await safe_reply(
            update.effective_message,
            "⚠️ Could not retrieve system health. Please try again.",
            parse_mode=None
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Alias for /health command.

    Usage: /status
    """
    await health_command(update, context)
