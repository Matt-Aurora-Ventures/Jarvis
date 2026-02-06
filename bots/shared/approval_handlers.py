"""
Shared /approve and /deny handler registration for ClawdBots.

Usage in any bot:
    from bots.shared.approval_handlers import register_approval_handlers, get_confirmation
    register_approval_handlers(bot, bot_name="ClawdMatt", admin_chat_id=123)

    # Later, to request approval:
    conf = get_confirmation()
    result = await conf.request_confirmation("buy_token", "Buy 100 SOL")
"""

import os
import logging
from bots.shared.action_confirmation import ActionConfirmation

logger = logging.getLogger(__name__)

# Singleton confirmation instance shared across a bot process
_confirmation: ActionConfirmation | None = None


def get_confirmation() -> ActionConfirmation | None:
    """Get the singleton ActionConfirmation instance (None if not yet registered)."""
    return _confirmation


def register_approval_handlers(bot, bot_name: str = "ClawdBot", admin_chat_id: int | str | None = None):
    """Register /approve and /deny command handlers on an AsyncTeleBot instance.

    Also creates the singleton ActionConfirmation wired to this bot.
    """
    global _confirmation

    if admin_chat_id is None:
        admin_chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or os.environ.get(
            "TELEGRAM_BUY_BOT_CHAT_ID"
        )

    admin_id = int(admin_chat_id) if admin_chat_id else None

    _confirmation = ActionConfirmation(
        bot_name=bot_name,
        telegram_bot=bot,
        admin_chat_id=str(admin_id) if admin_id else None,
    )

    @bot.message_handler(commands=["approve"])
    async def handle_approve(message):
        if admin_id and message.chat.id != admin_id:
            return  # silently ignore non-admin

        parts = message.text.split()
        if len(parts) < 2:
            await bot.reply_to(message, "Usage: /approve <id>")
            return

        approval_id = parts[1]
        if _confirmation.approve(approval_id, approved_by=str(message.from_user.id)):
            await bot.reply_to(message, f"Approved: {approval_id}")
        else:
            await bot.reply_to(message, f"Unknown or expired ID: {approval_id}")

    @bot.message_handler(commands=["deny"])
    async def handle_deny(message):
        if admin_id and message.chat.id != admin_id:
            return

        parts = message.text.split()
        if len(parts) < 2:
            await bot.reply_to(message, "Usage: /deny <id>")
            return

        approval_id = parts[1]
        if _confirmation.deny(approval_id, denied_by=str(message.from_user.id)):
            await bot.reply_to(message, f"Denied: {approval_id}")
        else:
            await bot.reply_to(message, f"Unknown or expired ID: {approval_id}")

    logger.info(f"Registered /approve and /deny handlers for {bot_name} (admin={admin_id})")
