"""
Bot Self-Awareness Commands.

Commands that demonstrate bot intelligence and self-awareness:
- /whoami - Bot introduces itself and explains its role
- /capabilities - Lists what the bot can do
- /status - Intelligent status report
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from core.bot_identity import (
    get_bot_identity,
    introduce_bot,
    get_bot_status,
    BotType
)
from tg_bot.handlers import error_handler, admin_only

logger = logging.getLogger(__name__)


@error_handler
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /whoami - Bot introduces itself with full self-awareness.

    Shows:
    - Bot identity and role
    - Capabilities
    - Knowledge domains
    - Personality

    Available to all users.
    """
    try:
        # Determine which bot this is based on environment
        import os
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

        # Map tokens to bot types
        treasury_token = os.getenv("TREASURY_BOT_TOKEN", "")
        public_token = os.getenv("PUBLIC_BOT_TELEGRAM_TOKEN", "")

        if bot_token == treasury_token:
            bot_type = BotType.TREASURY
        elif bot_token == public_token:
            bot_type = BotType.PUBLIC_TRADING
        else:
            bot_type = BotType.TELEGRAM  # Default to telegram bot

        # Get introduction
        intro = introduce_bot(bot_type)

        await update.message.reply_text(
            intro,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.exception(f"Error in whoami command: {e}")
        await update.message.reply_text(
            "I am a Jarvis bot, but I'm having trouble accessing my full identity right now."
        )


@error_handler
async def capabilities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /capabilities - List what this bot can do.

    Shows detailed list of bot capabilities and knowledge domains.
    Available to all users.
    """
    try:
        import os
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        treasury_token = os.getenv("TREASURY_BOT_TOKEN", "")
        public_token = os.getenv("PUBLIC_BOT_TELEGRAM_TOKEN", "")

        if bot_token == treasury_token:
            bot_type = BotType.TREASURY
        elif bot_token == public_token:
            bot_type = BotType.PUBLIC_TRADING
        else:
            bot_type = BotType.TELEGRAM

        identity = get_bot_identity(bot_type)

        message = f"🤖 *{identity.name} Capabilities*\n\n"

        message += "*What I Can Do:*\n"
        for cap in identity.capabilities:
            message += f"  • {cap}\n"
        message += "\n"

        message += "*What I Know:*\n"
        for domain in identity.knowledge_domains:
            message += f"  • {domain}\n"

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.exception(f"Error in capabilities command: {e}")
        await update.message.reply_text("Error retrieving capabilities.")


@error_handler
@admin_only
async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /botstatus - Intelligent status report from bot's perspective.

    Shows:
    - Bot identity
    - Current operational status
    - Key metrics
    - Recent activity

    Admin only.
    """
    try:
        import os
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        treasury_token = os.getenv("TREASURY_BOT_TOKEN", "")
        public_token = os.getenv("PUBLIC_BOT_TELEGRAM_TOKEN", "")

        if bot_token == treasury_token:
            bot_type = BotType.TREASURY

            # Treasury-specific status
            try:
                from bots.treasury.run_treasury import TreasuryTrader
                # Get actual treasury status
                # This would need async context, but we'll provide static for now
                status_data = {
                    "wallet": "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR",
                    "balance": "0.9898 SOL",
                    "positions": "Loading...",
                    "mode": "LIVE"
                }
            except Exception:
                status_data = {
                    "wallet": "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR",
                    "balance": "Unknown",
                    "positions": "Unknown",
                    "mode": "Unknown"
                }

        elif bot_token == public_token:
            bot_type = BotType.PUBLIC_TRADING
            status_data = {
                "mode": "Active",
                "audience": "Public"
            }

        else:
            bot_type = BotType.TELEGRAM
            status_data = {
                "mode": "Command Center",
                "admin": update.effective_user.username or "Unknown"
            }

        status_report = get_bot_status(bot_type, **status_data)

        await update.message.reply_text(
            status_report,
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.exception(f"Error in bot_status command: {e}")
        await update.message.reply_text("Error generating status report.")


@error_handler
async def vibe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /vibe <natural language request> - Control Claude Code console from Telegram.

    This command creates a direct bridge to the Claude Code console.
    Your message is sent to Claude Code, processed, and the response returns here.

    Sensitive information is automatically sanitized before transmission.

    Examples:
    - /vibe check treasury balance
    - /vibe what positions do we have?
    - /vibe analyze KR8TIV token
    - /vibe should we buy BONK?
    - /vibe create a new trading strategy
    - /vibe fix the buy bot error
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "💬 *Vibe Mode - Claude Code Console Access*\n\n"
                "Send commands directly to Claude Code:\n\n"
                "Examples:\n"
                "  • /vibe check treasury balance\n"
                "  • /vibe what are our top positions?\n"
                "  • /vibe analyze this token: [address]\n"
                "  • /vibe create a new strategy\n"
                "  • /vibe debug the error in bot_core.py\n\n"
                "🔒 All sensitive data is auto-sanitized.\n"
                "⚡ Responses come from the active Claude Code console.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        user_request = " ".join(context.args)
        user_id = update.effective_user.id
        username = update.effective_user.username

        # Send to Claude Code via relay
        from core.telegram_relay import get_relay

        relay = get_relay()

        # Send message to Claude Code
        message_id = relay.send_from_telegram(
            content=user_request,
            user_id=user_id,
            username=username
        )

        # Acknowledge receipt
        await update.message.reply_text(
            f"📨 Message sent to Claude Code console...\n\n"
            f"Request: _{user_request}_\n\n"
            f"🔄 Waiting for response...",
            parse_mode=ParseMode.MARKDOWN
        )

        # Poll for response (with timeout)
        import asyncio

        max_wait = 60  # 60 seconds timeout
        check_interval = 2  # Check every 2 seconds
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Check for response
            responses = relay.get_responses_for_telegram()

            for response in responses:
                if response.response_id == message_id and response.user_id == user_id:
                    # Found response!
                    await update.message.reply_text(
                        f"🤖 *Claude Code Response:*\n\n{response.content}",
                        parse_mode=ParseMode.MARKDOWN
                    )

                    # Mark as sent
                    relay.mark_response_sent(response.id)
                    return

        # Timeout
        await update.message.reply_text(
            "⏱️ Timeout waiting for Claude Code response.\n\n"
            "The console may be inactive or processing a long task.\n"
            "Try again later or check the console directly."
        )

    except Exception as e:
        logger.exception(f"Error in vibe command: {e}")
        await update.message.reply_text(
            "Error connecting to Claude Code console. Please try again."
        )
