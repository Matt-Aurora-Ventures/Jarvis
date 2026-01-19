"""
Alerter System - Multi-channel notification system with deduplication.

Alert channels:
- Telegram: admin notification
- Email: critical alerts only
- Slack: if configured
- Logs: all alerts logged

Alert types:
- CRITICAL: system down, data loss risk
- WARNING: performance degraded, API slow
- INFO: routine notifications

Features:
- Deduplication: don't alert twice for same issue within 1 hour
- History tracking
- Multiple channel support
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("jarvis.monitoring.alerter")


class AlertType(Enum):
    """Alert severity types."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AlertResult:
    """Result of sending an alert."""
    sent: bool
    alert_id: str
    channels: List[str]
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AlertRecord:
    """Record of a sent alert."""
    alert_id: str
    alert_type: str
    message: str
    channels: List[str]
    sent_at: datetime
    dedup_key: Optional[str] = None


class Alerter:
    """
    Multi-channel alerter with deduplication.

    Sends alerts to Telegram, email, Slack, and logs with
    configurable deduplication window.
    """

    def __init__(
        self,
        data_dir: str = "data/alerts",
        dedup_window_hours: int = 1,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dedup_window_hours = dedup_window_hours

        # Available channels
        self.channels = {
            "telegram": self._send_telegram,
            "email": self._send_email,
            "slack": self._send_slack,
            "log": self._send_log,
        }

        # Deduplication tracking
        self._sent_alerts: Dict[str, datetime] = {}
        self._alert_history: List[AlertRecord] = []

        # Load history from disk
        self._load_history()

    def _load_history(self):
        """Load alert history from disk."""
        history_path = self.data_dir / "alert_history.json"
        if history_path.exists():
            try:
                with open(history_path) as f:
                    data = json.load(f)
                    for record in data.get("history", [])[-1000:]:  # Keep last 1000
                        self._alert_history.append(AlertRecord(
                            alert_id=record["alert_id"],
                            alert_type=record["alert_type"],
                            message=record["message"],
                            channels=record["channels"],
                            sent_at=datetime.fromisoformat(record["sent_at"]),
                            dedup_key=record.get("dedup_key")
                        ))
                    # Rebuild dedup cache from recent history
                    cutoff = datetime.now(timezone.utc) - timedelta(hours=self.dedup_window_hours)
                    for record in self._alert_history:
                        if record.dedup_key and record.sent_at > cutoff:
                            self._sent_alerts[record.dedup_key] = record.sent_at
            except Exception as e:
                logger.warning(f"Failed to load alert history: {e}")

    def _save_history(self):
        """Save alert history to disk."""
        history_path = self.data_dir / "alert_history.json"
        try:
            data = {
                "history": [
                    {
                        "alert_id": r.alert_id,
                        "alert_type": r.alert_type,
                        "message": r.message,
                        "channels": r.channels,
                        "sent_at": r.sent_at.isoformat(),
                        "dedup_key": r.dedup_key
                    }
                    for r in self._alert_history[-1000:]  # Keep last 1000
                ]
            }
            with open(history_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save alert history: {e}")

    def _generate_alert_id(self) -> str:
        """Generate a unique alert ID."""
        return f"alert_{int(time.time() * 1000)}"

    def _should_deduplicate(self, alert_id: str) -> bool:
        """Check if this alert should be deduplicated."""
        if alert_id not in self._sent_alerts:
            return False

        last_sent = self._sent_alerts[alert_id]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.dedup_window_hours)

        return last_sent > cutoff

    async def send_alert(
        self,
        alert_type: AlertType,
        message: str,
        channels: List[str],
        alert_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AlertResult:
        """
        Send an alert to specified channels.

        Args:
            alert_type: Severity of the alert
            message: Alert message
            channels: List of channels to send to
            alert_id: Optional ID for deduplication
            metadata: Optional additional data

        Returns:
            AlertResult with send status
        """
        generated_id = self._generate_alert_id()
        dedup_key = alert_id or generated_id

        # Check deduplication
        if self._should_deduplicate(dedup_key):
            logger.debug(f"Alert {dedup_key} deduplicated")
            return AlertResult(
                sent=False,
                alert_id=dedup_key,
                channels=[],
                reason="deduplicated"
            )

        # Send to each channel
        sent_channels = []
        for channel in channels:
            if channel in self.channels:
                try:
                    await self.channels[channel](alert_type, message, metadata)
                    sent_channels.append(channel)
                except Exception as e:
                    logger.error(f"Failed to send alert to {channel}: {e}")

        # Record the alert
        record = AlertRecord(
            alert_id=generated_id,
            alert_type=alert_type.value,
            message=message,
            channels=sent_channels,
            sent_at=datetime.now(timezone.utc),
            dedup_key=dedup_key
        )
        self._alert_history.append(record)
        self._sent_alerts[dedup_key] = datetime.now(timezone.utc)

        # Persist history
        self._save_history()

        return AlertResult(
            sent=len(sent_channels) > 0,
            alert_id=generated_id,
            channels=sent_channels
        )

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alert history."""
        return [
            {
                "alert_id": r.alert_id,
                "alert_type": r.alert_type,
                "message": r.message,
                "channels": r.channels,
                "sent_at": r.sent_at.isoformat()
            }
            for r in self._alert_history[-limit:]
        ]

    # Channel implementations
    async def _send_telegram(
        self,
        alert_type: AlertType,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send alert to Telegram admins."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

        if not token or not admin_ids:
            logger.debug("Telegram not configured for alerts")
            return

        admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
        if not admin_list:
            return

        # Format message based on type
        emoji = {
            AlertType.CRITICAL: "🚨",
            AlertType.WARNING: "⚠️",
            AlertType.INFO: "ℹ️"
        }.get(alert_type, "📢")

        formatted = f"{emoji} <b>{alert_type.value.upper()}</b>\n\n{message}"

        if metadata:
            formatted += f"\n\n<pre>{json.dumps(metadata, indent=2)[:500]}</pre>"

        try:
            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:5]:  # Limit to 5 admins
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": formatted,
                        "parse_mode": "HTML"
                    })
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")

    async def _send_email(
        self,
        alert_type: AlertType,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send alert via email (for critical alerts only)."""
        if alert_type != AlertType.CRITICAL:
            return

        # Email sending would go here
        # For now, just log it
        logger.warning(f"EMAIL ALERT (not implemented): {message}")

    async def _send_slack(
        self,
        alert_type: AlertType,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send alert to Slack webhook."""
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return

        color = {
            AlertType.CRITICAL: "#ff0000",
            AlertType.WARNING: "#ffcc00",
            AlertType.INFO: "#0066ff"
        }.get(alert_type, "#999999")

        payload = {
            "attachments": [{
                "color": color,
                "title": f"JARVIS Alert: {alert_type.value.upper()}",
                "text": message,
                "footer": "JARVIS Monitoring System",
                "ts": int(time.time())
            }]
        }

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(webhook_url, json=payload)
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")

    async def _send_log(
        self,
        alert_type: AlertType,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log the alert."""
        log_func = {
            AlertType.CRITICAL: logger.critical,
            AlertType.WARNING: logger.warning,
            AlertType.INFO: logger.info
        }.get(alert_type, logger.info)

        log_func(f"ALERT [{alert_type.value}]: {message}")


# Singleton
_alerter: Optional[Alerter] = None


def get_alerter() -> Alerter:
    """Get or create the alerter singleton."""
    global _alerter
    if _alerter is None:
        _alerter = Alerter()
    return _alerter
