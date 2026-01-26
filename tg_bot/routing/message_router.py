"""Message routing logic for Telegram bot.

Implements chain-of-responsibility pattern for message routing:
1. Spam detection (blocks if spam)
2. Terminal commands (admin only)
3. Vibe coding requests (admin only)
4. AI response routing (Dexter/Grok)
5. Ignore (no route matched)
"""

import logging
import os
from typing import Dict, Any, List

from telegram import Update
from telegram.ext import ContextTypes

from tg_bot.log_utils import StructuredLogger

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Message router using chain-of-responsibility pattern.

    Routes messages to appropriate handlers based on:
    - User admin status
    - Message content patterns
    - Spam detection results

    Routing order is important - spam check happens first,
    then terminal commands, then vibe coding, then AI response.
    """

    # Explicit prefixes that trigger vibe coding (admin only)
    VIBE_PREFIXES = (
        "code:",
        "cli:",
        "vibe:",
        "rw:",
        "ralph wiggum",
        "vibe code",
        "cascade",
        "jarvis fix",
        "jarvis add",
        "jarvis create",
        "jarvis implement",
        "jarvis build",
        "jarvis update",
        "jarvis modify",
        "jarvis refactor",
        "jarvis run",
        "jarvis execute",
        "jarvis pull",
        "jarvis push",
        "go to console",
        "run in console",
        "run in cli",
    )

    def __init__(self):
        """Initialize router with admin IDs from environment."""
        self.admin_ids = self._load_admin_ids()

    @staticmethod
    def _load_admin_ids() -> List[int]:
        """Load admin IDs from environment."""
        admin_ids_str = os.environ.get("TELEGRAM_ADMIN_IDS", "")
        return [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.admin_ids

    async def route_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Dict[str, Any]:
        """
        Route incoming message to appropriate handler.

        Args:
            update: Telegram Update object
            context: Telegram Context object

        Returns:
            dict with keys:
                - route: str (spam_blocked, terminal, vibe_coding, ai_response, ignored)
                - should_continue: bool (whether to continue processing)
                - data: dict (route-specific data)
        """
        # Handle empty/missing message
        if not update.message or not update.message.text:
            return {"route": "ignored", "should_continue": False, "data": {}}

        text = update.message.text.strip()
        user_id = update.effective_user.id if update.effective_user else 0
        username = update.effective_user.username or "" if update.effective_user else ""

        is_admin = self.is_admin(user_id)

        # 1. Spam detection (skip for admin)
        if not is_admin:
            spam_result = await self._check_spam(update, context, text, user_id)
            if spam_result["is_spam"]:
                StructuredLogger.log_message_flow(
                    user_id, text, "spam_blocked", is_admin, False
                )
                return {
                    "route": "spam_blocked",
                    "should_continue": False,
                    "data": spam_result
                }

        # 2. Terminal commands (> or /term prefix)
        if self._is_terminal_command(text):
            StructuredLogger.log_message_flow(
                user_id, text, "terminal", is_admin, is_admin
            )
            return {
                "route": "terminal",
                "should_continue": is_admin,  # Only process if admin
                "data": {"text": text, "is_admin": is_admin}
            }

        # 3. Vibe coding requests (admin only)
        if is_admin and self._is_vibe_request(text):
            StructuredLogger.log_message_flow(
                user_id, text, "vibe_coding", is_admin, True
            )
            return {
                "route": "vibe_coding",
                "should_continue": True,
                "data": {"text": text, "user_id": user_id, "username": username}
            }

        # 4. AI response routing
        should_reply = self._should_reply_with_ai(update, context, text, is_admin)
        if should_reply:
            StructuredLogger.log_message_flow(
                user_id, text, "ai_response", is_admin, True
            )
            return {
                "route": "ai_response",
                "should_continue": True,
                "data": {
                    "text": text,
                    "user_id": user_id,
                    "username": username,
                    "is_admin": is_admin
                }
            }

        # 5. Ignore (no route matched)
        StructuredLogger.log_message_flow(
            user_id, text, "ignored", is_admin, False
        )
        return {"route": "ignored", "should_continue": False, "data": {}}

    async def _check_spam(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Check if message is spam.

        Returns dict with:
            - is_spam: bool
            - user_id: int
        """
        # Import here to avoid circular dependency
        from tg_bot.bot_core import check_and_ban_spam

        is_spam = await check_and_ban_spam(update, context, text, user_id)

        return {
            "is_spam": is_spam,
            "user_id": user_id,
        }

    @staticmethod
    def _is_terminal_command(text: str) -> bool:
        """Check if message is a terminal command (> or /term prefix)."""
        return text.startswith('>') or text.lower().startswith('/term ')

    @staticmethod
    def _is_vibe_request(text: str) -> bool:
        """Check if message is a vibe coding request (explicit prefixes only)."""
        text_lower = text.lower().strip()
        return text_lower.startswith(MessageRouter.VIBE_PREFIXES)

    def _should_reply_with_ai(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        is_admin: bool
    ) -> bool:
        """
        Determine if bot should generate AI response.

        Logic:
        - Admin: Use _is_message_for_jarvis (mentions, questions, etc.)
        - Non-admin: Use _should_reply (basic filters)
        """
        # Import here to avoid circular dependency
        from tg_bot.bot_core import _should_reply, _is_message_for_jarvis

        if is_admin:
            return _is_message_for_jarvis(text, update)
        else:
            return _should_reply(update, context)
