"""
Health Reporter Module

Provides the HealthReporter class for:
- Formatting health status for display
- Sending alerts via Telegram
- Sending recovery notifications
- Managing alert cooldowns to prevent spam
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .status import HealthStatus

# Try to import aiohttp
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

logger = logging.getLogger("jarvis.health.reporter")


@dataclass
class AlertResult:
    """Result of sending an alert."""
    sent: bool
    channels: List[str] = field(default_factory=list)
    message: str = ""
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HealthReporter:
    """
    Report health status and send alerts.

    Features:
    - Format status for human-readable display
    - Format status for Telegram (markdown)
    - Format status as JSON
    - Send alerts via Telegram
    - Send recovery notifications
    - Alert cooldown to prevent spam
    """

    def __init__(
        self,
        alert_cooldown: int = 300,  # 5 minutes
        telegram_token: Optional[str] = None,
        telegram_chat_ids: Optional[List[str]] = None,
    ):
        """
        Initialize HealthReporter.

        Args:
            alert_cooldown: Minimum seconds between alerts for same bot
            telegram_token: Telegram bot token (or read from TELEGRAM_BOT_TOKEN)
            telegram_chat_ids: Chat IDs to send alerts to (or read from TELEGRAM_ADMIN_IDS)
        """
        self._alert_cooldown = alert_cooldown

        # Telegram configuration
        self._telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_ids_env = os.getenv("TELEGRAM_ADMIN_IDS", "")
        self._telegram_chat_ids = telegram_chat_ids or [
            cid.strip() for cid in chat_ids_env.split(",") if cid.strip()
        ]

        # Track alert timestamps for cooldown
        self._last_alerts: Dict[str, float] = {}

        # Track which bots have active alerts (for recovery notifications)
        self._active_alerts: Dict[str, bool] = {}

    def format_status(
        self,
        status: Any,  # BotStatus from monitor.py
        format: str = "text",
    ) -> str:
        """
        Format a bot status for display.

        Args:
            status: BotStatus object
            format: Output format - "text", "telegram", or "json"

        Returns:
            Formatted status string
        """
        if format == "json":
            return json.dumps(status.to_dict(), indent=2, default=str)

        elif format == "telegram":
            # Telegram markdown format
            status_emoji = self._get_status_emoji(status.status)
            lines = [
                f"{status_emoji} *{status.name}*",
                f"Status: `{status.status.value}`",
            ]
            if status.message:
                lines.append(f"Message: {status.message}")
            if status.latency_ms > 0:
                lines.append(f"Latency: {status.latency_ms:.1f}ms")
            return "\n".join(lines)

        else:  # text format
            lines = [
                f"Bot: {status.name}",
                f"Status: {status.status.value.upper()}",
            ]
            if status.message:
                lines.append(f"Message: {status.message}")
            if status.latency_ms > 0:
                lines.append(f"Latency: {status.latency_ms:.1f}ms")
            return "\n".join(lines)

    def format_summary(self, statuses: Dict[str, Any]) -> str:
        """
        Format a summary of multiple bot statuses.

        Args:
            statuses: Dictionary mapping bot names to BotStatus objects

        Returns:
            Formatted summary string
        """
        if not statuses:
            return "No bots registered"

        # Count by status
        healthy = 0
        unhealthy = 0
        other = 0

        for status in statuses.values():
            if status.status == HealthStatus.HEALTHY:
                healthy += 1
            elif status.status.is_problematic:
                unhealthy += 1
            else:
                other += 1

        total = len(statuses)

        # Determine overall status
        if unhealthy > 0:
            overall = "DEGRADED" if healthy > 0 else "UNHEALTHY"
        elif other > 0:
            overall = "MIXED"
        else:
            overall = "HEALTHY"

        lines = [
            "=" * 40,
            "HEALTH SUMMARY",
            "=" * 40,
            f"Overall: {overall}",
            f"Total bots: {total}",
            f"  Healthy: {healthy}",
            f"  Unhealthy: {unhealthy}",
            f"  Other: {other}",
            "-" * 40,
        ]

        # Add individual bot statuses
        for name, status in sorted(statuses.items()):
            emoji = self._get_status_emoji(status.status)
            lines.append(f"{emoji} {name}: {status.status.value}")

        lines.append("=" * 40)

        return "\n".join(lines)

    async def send_alert(self, status: Any) -> AlertResult:
        """
        Send an alert for a bot status.

        Args:
            status: BotStatus object

        Returns:
            AlertResult indicating if alert was sent
        """
        bot_name = status.name

        # Check cooldown
        last_alert = self._last_alerts.get(bot_name, 0)
        if time.time() - last_alert < self._alert_cooldown:
            return AlertResult(
                sent=False,
                reason="cooldown",
                message=f"Alert suppressed due to cooldown ({self._alert_cooldown}s)",
            )

        # Check if Telegram is configured
        if not self._telegram_token or not self._telegram_chat_ids:
            return AlertResult(
                sent=False,
                reason="Telegram not configured",
                message="TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_IDS not set",
            )

        # Format message
        message = self._format_alert_message(status)

        # Send to Telegram
        try:
            await self._send_telegram(message)
            self._last_alerts[bot_name] = time.time()
            self._active_alerts[bot_name] = True

            return AlertResult(
                sent=True,
                channels=["telegram"],
                message="Alert sent successfully",
            )

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return AlertResult(
                sent=False,
                reason="error",
                message=str(e),
            )

    async def send_recovery(self, status: Any) -> AlertResult:
        """
        Send a recovery notification for a bot.

        Args:
            status: BotStatus object (should be healthy)

        Returns:
            AlertResult indicating if recovery was sent
        """
        bot_name = status.name

        # Check if Telegram is configured
        if not self._telegram_token or not self._telegram_chat_ids:
            return AlertResult(
                sent=False,
                reason="Telegram not configured",
            )

        # Format recovery message
        message = self._format_recovery_message(status)

        # Send to Telegram
        try:
            await self._send_telegram(message)
            self._active_alerts[bot_name] = False

            return AlertResult(
                sent=True,
                channels=["telegram"],
                message="Recovery notification sent",
            )

        except Exception as e:
            logger.error(f"Failed to send recovery: {e}")
            return AlertResult(
                sent=False,
                reason="error",
                message=str(e),
            )

    async def _send_telegram(self, message: str) -> None:
        """Send message to Telegram chat(s)."""
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp not available")

        url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            for chat_id in self._telegram_chat_ids:
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }

                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        logger.warning(
                            f"Telegram send failed for {chat_id}: {response.status} - {error_data}"
                        )

    def _format_alert_message(self, status: Any) -> str:
        """Format an alert message for Telegram."""
        emoji = self._get_status_emoji(status.status)
        lines = [
            f"{emoji} *HEALTH ALERT*",
            "",
            f"*Bot:* `{status.name}`",
            f"*Status:* `{status.status.value}`",
        ]

        if status.message:
            lines.append(f"*Message:* {status.message}")

        lines.append(f"\n_Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_")

        return "\n".join(lines)

    def _format_recovery_message(self, status: Any) -> str:
        """Format a recovery message for Telegram."""
        lines = [
            "RECOVERY",
            "",
            f"*Bot:* `{status.name}`",
            f"*Status:* `{status.status.value}` (Healthy)",
        ]

        if status.latency_ms > 0:
            lines.append(f"*Latency:* {status.latency_ms:.1f}ms")

        lines.append(f"\n_Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_")

        return "\n".join(lines)

    def _get_status_emoji(self, status: HealthStatus) -> str:
        """Get emoji for status."""
        emoji_map = {
            HealthStatus.HEALTHY: "[OK]",
            HealthStatus.AVAILABLE: "[OK]",
            HealthStatus.DEGRADED: "[WARN]",
            HealthStatus.WARNING: "[WARN]",
            HealthStatus.UNHEALTHY: "[FAIL]",
            HealthStatus.CRITICAL: "[CRIT]",
            HealthStatus.ERROR: "[ERR]",
            HealthStatus.TIMEOUT: "[TIME]",
            HealthStatus.NOT_RUNNING: "[DOWN]",
            HealthStatus.NOT_CONFIGURED: "[CFG]",
            HealthStatus.RATE_LIMITED: "[RATE]",
            HealthStatus.UNKNOWN: "[???]",
        }
        return emoji_map.get(status, "[???]")
