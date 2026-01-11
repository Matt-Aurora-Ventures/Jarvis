"""
Anti-Scam Protection - Detect and handle scam messages in Telegram groups.

Features:
- Keyword detection for common scams
- Auto-delete scam messages
- Restrict users (mute without kicking)
- Alert admins
- Logging for review
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScamDetection:
    """Result of scam detection."""
    is_scam: bool
    confidence: float  # 0.0 to 1.0
    triggers: List[str]
    category: str  # "refund", "impersonation", "phishing", etc.
    message_text: str
    user_id: int
    username: str


# Scam keyword patterns
SCAM_PATTERNS = {
    "refund_scam": [
        r"send\s*(your)?\s*tokens?\s*back",
        r"refund\s*(your)?\s*tokens?",
        r"return\s*(your)?\s*tokens?",
        r"send\s*back\s*(your)?\s*(sol|tokens?)",
        r"claim\s*your\s*refund",
        r"eligible\s*for\s*(a\s*)?refund",
        r"compensation\s*for\s*holders",
        r"send\s*to\s*(this|my)\s*wallet",
    ],
    "fake_admin": [
        r"i\s*am\s*(the|an)?\s*admin",
        r"official\s*support",
        r"support\s*team",
        r"moderator\s*here",
        r"dm\s*me\s*(for|about)",
        r"pm\s*me\s*(for|about)",
        r"message\s*me\s*privately",
        r"contact\s*me\s*directly",
    ],
    "phishing": [
        r"connect\s*your\s*wallet",
        r"verify\s*your\s*wallet",
        r"validate\s*your\s*wallet",
        r"sync\s*your\s*wallet",
        r"enter\s*your\s*(seed|private|recovery)",
        r"dapp\s*verification",
        r"wallet\s*validation",
    ],
    "fake_airdrop": [
        r"claim\s*free\s*tokens?",
        r"airdrop\s*claim",
        r"bonus\s*tokens?\s*for",
        r"send\s*\d+\s*(sol|eth)\s*get\s*\d+",
        r"double\s*your\s*(sol|eth|tokens?)",
        r"giveaway\s*event",
    ],
    "urgency_scam": [
        r"act\s*now\s*or\s*lose",
        r"last\s*chance\s*to",
        r"expires?\s*in\s*\d+\s*(min|hour|hr)",
        r"limited\s*time\s*only",
        r"hurry\s*up",
        r"don'?t\s*miss\s*out",
    ],
}

# Suspicious URL patterns
SUSPICIOUS_URLS = [
    r"bit\.ly",
    r"tinyurl",
    r"t\.co",
    r"goo\.gl",
    r"forms\.gle",  # Google forms often used for phishing
    r"discord\.gg",  # Discord invites in crypto chats = suspicious
]

# Whitelist - real admin user IDs that should never be flagged
ADMIN_WHITELIST: Set[int] = set()


class AntiScamProtection:
    """
    Anti-scam protection for Telegram groups.

    Usage:
        antiscam = AntiScamProtection(bot, admin_ids=[123, 456])

        # In message handler:
        detection = antiscam.check_message(message)
        if detection.is_scam:
            await antiscam.handle_scam(message, detection)
    """

    def __init__(
        self,
        bot,
        admin_ids: List[int],
        log_channel_id: Optional[int] = None,
        auto_restrict: bool = True,
        auto_delete: bool = True,
        alert_admins: bool = True,
    ):
        self.bot = bot
        self.admin_ids = set(admin_ids)
        self.log_channel_id = log_channel_id
        self.auto_restrict = auto_restrict
        self.auto_delete = auto_delete
        self.alert_admins = alert_admins

        # Compile patterns for efficiency
        self._compiled_patterns = {}
        for category, patterns in SCAM_PATTERNS.items():
            self._compiled_patterns[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        self._url_patterns = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_URLS]

        # Track recent detections to avoid spam
        self._recent_detections: List[ScamDetection] = []
        self._max_recent = 100

    def check_message(self, message) -> ScamDetection:
        """
        Check if a message is a potential scam.

        Args:
            message: Telegram message object

        Returns:
            ScamDetection with results
        """
        text = message.text or message.caption or ""
        user = message.from_user
        user_id = user.id if user else 0
        username = user.username or user.first_name if user else "Unknown"

        # Never flag whitelisted admins
        if user_id in self.admin_ids:
            return ScamDetection(
                is_scam=False,
                confidence=0.0,
                triggers=[],
                category="",
                message_text=text,
                user_id=user_id,
                username=username,
            )

        triggers = []
        categories_hit = []

        # Check each category
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    triggers.append(f"{category}: {match.group()}")
                    if category not in categories_hit:
                        categories_hit.append(category)

        # Check for suspicious URLs
        for pattern in self._url_patterns:
            match = pattern.search(text)
            if match:
                triggers.append(f"suspicious_url: {match.group()}")
                if "phishing" not in categories_hit:
                    categories_hit.append("phishing")

        # Calculate confidence based on triggers
        confidence = min(len(triggers) * 0.3, 1.0)

        # Boost confidence for certain combinations
        if "refund_scam" in categories_hit and "fake_admin" in categories_hit:
            confidence = min(confidence + 0.3, 1.0)
        if "phishing" in categories_hit and "urgency_scam" in categories_hit:
            confidence = min(confidence + 0.2, 1.0)

        # Check if user is impersonating an admin (similar username)
        if self._is_admin_impersonation(username):
            triggers.append("admin_impersonation: similar to admin username")
            confidence = min(confidence + 0.4, 1.0)
            categories_hit.append("impersonation")

        is_scam = confidence >= 0.5
        primary_category = categories_hit[0] if categories_hit else ""

        detection = ScamDetection(
            is_scam=is_scam,
            confidence=confidence,
            triggers=triggers,
            category=primary_category,
            message_text=text[:500],  # Truncate for logging
            user_id=user_id,
            username=username,
        )

        if is_scam:
            self._recent_detections.append(detection)
            if len(self._recent_detections) > self._max_recent:
                self._recent_detections = self._recent_detections[-self._max_recent:]

        return detection

    def _is_admin_impersonation(self, username: str) -> bool:
        """Check if username is trying to impersonate an admin."""
        if not username:
            return False

        username_lower = username.lower()

        # Common impersonation patterns
        impersonation_suffixes = ["_support", "_admin", "_official", "_help", "_mod"]
        for suffix in impersonation_suffixes:
            if username_lower.endswith(suffix):
                return True

        # Check for lookalike characters (l vs 1, o vs 0, etc.)
        # This is a simplified check
        suspicious_chars = {"l": "1", "o": "0", "i": "1", "e": "3", "a": "4", "s": "5"}

        return False

    async def handle_scam(self, message, detection: ScamDetection) -> dict:
        """
        Handle a detected scam message.

        Actions:
        1. Delete the message
        2. Restrict the user (mute)
        3. Alert admins
        4. Log the incident

        Returns:
            dict with action results
        """
        results = {
            "deleted": False,
            "restricted": False,
            "alerted": False,
            "logged": False,
        }

        chat_id = message.chat.id
        user_id = detection.user_id
        message_id = message.message_id

        # 1. Delete the scam message
        if self.auto_delete:
            try:
                await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
                results["deleted"] = True
                logger.info(f"Deleted scam message from {detection.username}")
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")

        # 2. Restrict the user (mute - can't send messages but stays in group)
        if self.auto_restrict:
            try:
                from telegram import ChatPermissions

                # Mute the user - they can still see messages but can't post
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                )

                await self.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=permissions,
                )
                results["restricted"] = True
                logger.info(f"Restricted user {detection.username} ({user_id})")
            except Exception as e:
                logger.error(f"Failed to restrict user: {e}")

        # 3. Alert admins
        if self.alert_admins:
            alert_text = self._format_alert(detection, results)

            # Send to log channel if configured
            if self.log_channel_id:
                try:
                    await self.bot.send_message(
                        chat_id=self.log_channel_id,
                        text=alert_text,
                        parse_mode="HTML",
                    )
                    results["logged"] = True
                except Exception as e:
                    logger.error(f"Failed to log to channel: {e}")

            # DM each admin
            for admin_id in self.admin_ids:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=alert_text,
                        parse_mode="HTML",
                    )
                    results["alerted"] = True
                except Exception as e:
                    logger.debug(f"Could not alert admin {admin_id}: {e}")

        return results

    def _format_alert(self, detection: ScamDetection, actions: dict) -> str:
        """Format alert message for admins."""
        status_icons = {
            "deleted": "Deleted" if actions.get("deleted") else "Failed to delete",
            "restricted": "Muted" if actions.get("restricted") else "Failed to mute",
        }

        return f"""<b>SCAM DETECTED</b>

<b>User:</b> {detection.username} (ID: {detection.user_id})
<b>Category:</b> {detection.category}
<b>Confidence:</b> {detection.confidence:.0%}

<b>Triggers:</b>
{chr(10).join('- ' + t for t in detection.triggers[:5])}

<b>Message Preview:</b>
<code>{detection.message_text[:200]}...</code>

<b>Actions Taken:</b>
- {status_icons['deleted']}
- {status_icons['restricted']}

<i>Use /unban {detection.user_id} to restore posting ability if this was a false positive.</i>"""

    async def unban_user(self, chat_id: int, user_id: int) -> bool:
        """
        Restore posting ability for a user.

        Args:
            chat_id: The chat to unban in
            user_id: User to unban

        Returns:
            True if successful
        """
        try:
            from telegram import ChatPermissions

            # Restore normal permissions
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            )

            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
            )

            logger.info(f"Unbanned user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unban user: {e}")
            return False

    def get_recent_detections(self) -> List[ScamDetection]:
        """Get recent scam detections for review."""
        return list(self._recent_detections)

    def add_admin(self, user_id: int):
        """Add a user to the admin whitelist."""
        self.admin_ids.add(user_id)

    def remove_admin(self, user_id: int):
        """Remove a user from the admin whitelist."""
        self.admin_ids.discard(user_id)


def create_antiscam_handler(antiscam: AntiScamProtection):
    """
    Create a message handler for anti-scam protection.

    Usage with python-telegram-bot:
        from telegram.ext import MessageHandler, filters

        antiscam = AntiScamProtection(bot, admin_ids=[...])
        handler = create_antiscam_handler(antiscam)
        app.add_handler(handler)
    """
    async def handler(update, context):
        message = update.message or update.edited_message
        if not message or not message.text:
            return

        detection = antiscam.check_message(message)
        if detection.is_scam:
            await antiscam.handle_scam(message, detection)

    from telegram.ext import MessageHandler, filters
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handler)
