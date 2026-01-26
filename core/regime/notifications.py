"""
Regime Change Notifications for Telegram.
==========================================

Sends notifications when market regime changes, with:
- Cooldown to prevent spam
- Priority for crash notifications
- Strategy change information
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Cooldown tracking
_last_notification_time: float = 0.0


async def send_regime_notification(
    message: str,
    chat_id: Optional[str] = None,
    priority: str = "normal",
) -> bool:
    """
    Send a regime change notification via Telegram.

    Args:
        message: Notification message
        chat_id: Optional specific chat ID (uses default if not provided)
        priority: Priority level (normal, high, urgent)

    Returns:
        True if notification sent successfully
    """
    try:
        # Try to use existing Telegram integration
        from tg_bot.handlers.notifications import send_notification

        await send_notification(
            message=message,
            notification_type="regime_change",
            priority=priority,
        )
        return True

    except ImportError:
        # Fall back to direct bot API if available
        try:
            import os
            import httpx

            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            default_chat = os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")

            if not token or not (chat_id or default_chat):
                logger.debug("Telegram credentials not available for notification")
                return False

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id or default_chat,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
                return response.status_code == 200

        except Exception as e:
            logger.debug(f"Failed to send Telegram notification: {e}")
            return False

    except Exception as e:
        logger.debug(f"Notification error: {e}")
        return False


class RegimeNotifier:
    """
    Manages regime change notifications with cooldown and priority.

    Features:
    - Cooldown between notifications to prevent spam
    - Crash notifications bypass cooldown
    - Includes strategy change information
    """

    def __init__(
        self,
        cooldown_minutes: float = 5.0,
        enabled: bool = True,
    ):
        """
        Initialize regime notifier.

        Args:
            cooldown_minutes: Minimum minutes between notifications
            enabled: Whether notifications are enabled
        """
        self._cooldown_seconds = cooldown_minutes * 60
        self._enabled = enabled
        self._last_notification = 0.0

    async def notify_regime_change(
        self,
        from_regime: str,
        to_regime: str,
        confidence: float,
        active_strategies: Optional[List[str]] = None,
        deactivated_strategies: Optional[List[str]] = None,
    ) -> bool:
        """
        Send notification about regime change.

        Args:
            from_regime: Previous regime
            to_regime: New regime
            confidence: Detection confidence (0-1)
            active_strategies: List of now-active strategies
            deactivated_strategies: List of now-inactive strategies

        Returns:
            True if notification was sent
        """
        if not self._enabled:
            return False

        # Check cooldown (crash bypasses)
        is_crash = to_regime.lower() == "crash"
        time_since_last = time.time() - self._last_notification

        if not is_crash and time_since_last < self._cooldown_seconds:
            logger.debug(f"Notification suppressed (cooldown): {time_since_last:.0f}s < {self._cooldown_seconds:.0f}s")
            return False

        # Build message
        message = self._format_message(
            from_regime=from_regime,
            to_regime=to_regime,
            confidence=confidence,
            active_strategies=active_strategies,
            deactivated_strategies=deactivated_strategies,
        )

        # Determine priority
        priority = "urgent" if is_crash else "normal"

        # Send notification
        success = await send_regime_notification(message, priority=priority)

        if success:
            self._last_notification = time.time()
            logger.info(f"Sent regime change notification: {from_regime} -> {to_regime}")

        return success

    def _format_message(
        self,
        from_regime: str,
        to_regime: str,
        confidence: float,
        active_strategies: Optional[List[str]] = None,
        deactivated_strategies: Optional[List[str]] = None,
    ) -> str:
        """Format the notification message."""
        # Emoji based on regime
        regime_emoji = {
            "trending": "📈",
            "ranging": "↔️",
            "high_vol": "⚡",
            "quiet": "😴",
            "crash": "🚨",
        }

        to_emoji = regime_emoji.get(to_regime.lower(), "📊")

        lines = [
            f"{to_emoji} <b>Market Regime Change</b>",
            "",
            f"<b>From:</b> {from_regime.upper()}",
            f"<b>To:</b> {to_regime.upper()}",
            f"<b>Confidence:</b> {confidence:.0%}",
        ]

        if active_strategies:
            lines.extend([
                "",
                "<b>Active Strategies:</b>",
                ", ".join(active_strategies[:5]),
            ])

        # Add warning for crash
        if to_regime.lower() == "crash":
            lines.extend([
                "",
                "⚠️ <b>CRASH DETECTED</b>",
                "Position sizes auto-reduced to 20%",
                "Only defensive strategies active",
            ])

        return "\n".join(lines)

    def reset_cooldown(self):
        """Reset the notification cooldown."""
        self._last_notification = 0.0


# Singleton
_regime_notifier: Optional[RegimeNotifier] = None


def get_regime_notifier() -> RegimeNotifier:
    """Get singleton regime notifier instance."""
    global _regime_notifier
    if _regime_notifier is None:
        _regime_notifier = RegimeNotifier()
    return _regime_notifier


__all__ = [
    "RegimeNotifier",
    "send_regime_notification",
    "get_regime_notifier",
]
