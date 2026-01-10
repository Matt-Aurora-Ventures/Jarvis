"""
Alert Management System
Prompt #100: Alerting for system issues

Manages alerts and notifications for system health issues.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.monitoring.alerts")


# =============================================================================
# MODELS
# =============================================================================

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """An alert instance"""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    notification_sent: bool = False


@dataclass
class AlertRule:
    """Rule for generating alerts"""
    name: str
    condition: Callable[[], bool]
    severity: AlertSeverity
    title_template: str
    message_template: str
    cooldown_minutes: int = 15  # Don't re-alert for this period


# =============================================================================
# ALERT MANAGER
# =============================================================================

class AlertManager:
    """
    Manages system alerts and notifications.

    Features:
    - Alert creation and lifecycle
    - Notification channels (Slack, Discord, email)
    - Alert suppression and cooldowns
    - Alert history and analytics
    """

    def __init__(
        self,
        db_path: str = None,
        slack_webhook: str = None,
        discord_webhook: str = None,
    ):
        self.db_path = db_path or os.getenv(
            "ALERTS_DB",
            "data/alerts.db"
        )
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK")
        self.discord_webhook = discord_webhook or os.getenv("DISCORD_WEBHOOK")

        self._rules: Dict[str, AlertRule] = {}
        self._cooldowns: Dict[str, datetime] = {}
        self._notification_handlers: List[Callable] = []

        self._init_database()

    def _init_database(self):
        """Initialize alerts database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                acknowledged_at TEXT,
                resolved_at TEXT,
                acknowledged_by TEXT,
                metadata_json TEXT,
                notification_sent INTEGER DEFAULT 0
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_status
            ON alerts(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_severity
            ON alerts(severity)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_created
            ON alerts(created_at)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # ALERT CREATION
    # =========================================================================

    async def create_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        metadata: Dict[str, Any] = None,
        notify: bool = True,
    ) -> Alert:
        """
        Create a new alert.

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level
            source: Source component
            metadata: Additional data
            notify: Whether to send notifications

        Returns:
            Created Alert
        """
        import hashlib

        alert_id = hashlib.sha256(
            f"{source}:{title}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        alert = Alert(
            id=alert_id,
            title=title,
            message=message,
            severity=severity,
            source=source,
            metadata=metadata or {},
        )

        # Save alert
        await self._save_alert(alert)

        logger.warning(f"Alert created: [{severity.value.upper()}] {title}")

        # Send notifications
        if notify:
            await self._send_notifications(alert)
            alert.notification_sent = True
            await self._update_alert(alert)

        return alert

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str = None,
    ) -> Optional[Alert]:
        """Acknowledge an alert"""
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = acknowledged_by

        await self._update_alert(alert)

        logger.info(f"Alert acknowledged: {alert_id}")

        return alert

    async def resolve_alert(
        self,
        alert_id: str,
    ) -> Optional[Alert]:
        """Resolve an alert"""
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)

        await self._update_alert(alert)

        logger.info(f"Alert resolved: {alert_id}")

        return alert

    async def suppress_alert(
        self,
        alert_id: str,
    ) -> Optional[Alert]:
        """Suppress an alert"""
        alert = await self.get_alert(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.SUPPRESSED

        await self._update_alert(alert)

        return alert

    # =========================================================================
    # ALERT RULES
    # =========================================================================

    def register_rule(self, rule: AlertRule):
        """Register an alert rule"""
        self._rules[rule.name] = rule

    async def check_rules(self):
        """Check all alert rules and create alerts as needed"""
        for name, rule in self._rules.items():
            # Check cooldown
            if name in self._cooldowns:
                if datetime.now(timezone.utc) < self._cooldowns[name]:
                    continue

            try:
                if await asyncio.to_thread(rule.condition):
                    # Create alert
                    await self.create_alert(
                        title=rule.title_template,
                        message=rule.message_template,
                        severity=rule.severity,
                        source=f"rule:{name}",
                    )

                    # Set cooldown
                    self._cooldowns[name] = (
                        datetime.now(timezone.utc) +
                        timedelta(minutes=rule.cooldown_minutes)
                    )

            except Exception as e:
                logger.error(f"Rule check failed for {name}: {e}")

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    def register_notification_handler(self, handler: Callable):
        """Register a notification handler"""
        self._notification_handlers.append(handler)

    async def _send_notifications(self, alert: Alert):
        """Send notifications for an alert"""
        # Custom handlers
        for handler in self._notification_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")

        # Slack
        if self.slack_webhook and alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            await self._send_slack_notification(alert)

        # Discord
        if self.discord_webhook and alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            await self._send_discord_notification(alert)

    async def _send_slack_notification(self, alert: Alert):
        """Send Slack notification"""
        try:
            import urllib.request

            color = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9800",
                AlertSeverity.ERROR: "#f44336",
                AlertSeverity.CRITICAL: "#9c27b0",
            }.get(alert.severity, "#808080")

            payload = {
                "attachments": [{
                    "color": color,
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Time", "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True},
                    ],
                    "footer": "JARVIS Alert System",
                }]
            }

            req = urllib.request.Request(
                self.slack_webhook,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                pass

            logger.debug(f"Slack notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    async def _send_discord_notification(self, alert: Alert):
        """Send Discord notification"""
        try:
            import urllib.request

            color = {
                AlertSeverity.INFO: 0x36a64f,
                AlertSeverity.WARNING: 0xff9800,
                AlertSeverity.ERROR: 0xf44336,
                AlertSeverity.CRITICAL: 0x9c27b0,
            }.get(alert.severity, 0x808080)

            payload = {
                "embeds": [{
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "description": alert.message,
                    "color": color,
                    "fields": [
                        {"name": "Source", "value": alert.source, "inline": True},
                    ],
                    "footer": {"text": "JARVIS Alert System"},
                    "timestamp": alert.created_at.isoformat(),
                }]
            }

            req = urllib.request.Request(
                self.discord_webhook,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                pass

            logger.debug(f"Discord notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Discord notification failed: {e}")

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return self._row_to_alert(row)

    async def get_active_alerts(
        self,
        severity: AlertSeverity = None,
    ) -> List[Alert]:
        """Get all active alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM alerts WHERE status = ?"
        params = [AlertStatus.ACTIVE.value]

        if severity:
            query += " AND severity = ?"
            params.append(severity.value)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)

        alerts = [self._row_to_alert(row) for row in cursor.fetchall()]

        conn.close()
        return alerts

    async def get_alert_history(
        self,
        hours: int = 24,
        source: str = None,
        severity: AlertSeverity = None,
    ) -> List[Alert]:
        """Get alert history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        query = "SELECT * FROM alerts WHERE created_at >= ?"
        params = [since]

        if source:
            query += " AND source = ?"
            params.append(source)

        if severity:
            query += " AND severity = ?"
            params.append(severity.value)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)

        alerts = [self._row_to_alert(row) for row in cursor.fetchall()]

        conn.close()
        return alerts

    async def get_alert_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get alert statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Count by severity
        cursor.execute("""
            SELECT severity, COUNT(*) FROM alerts
            WHERE created_at >= ?
            GROUP BY severity
        """, (since,))

        by_severity = {row[0]: row[1] for row in cursor.fetchall()}

        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM alerts
            WHERE created_at >= ?
            GROUP BY status
        """, (since,))

        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        # Count by source
        cursor.execute("""
            SELECT source, COUNT(*) FROM alerts
            WHERE created_at >= ?
            GROUP BY source
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """, (since,))

        by_source = {row[0]: row[1] for row in cursor.fetchall()}

        # MTTR (Mean Time To Resolve)
        cursor.execute("""
            SELECT AVG(
                julianday(resolved_at) - julianday(created_at)
            ) * 24 * 60  -- in minutes
            FROM alerts
            WHERE resolved_at IS NOT NULL
            AND created_at >= ?
        """, (since,))

        mttr = cursor.fetchone()[0]

        conn.close()

        return {
            "total": sum(by_severity.values()),
            "by_severity": by_severity,
            "by_status": by_status,
            "by_source": by_source,
            "mttr_minutes": mttr,
            "period_days": days,
        }

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _save_alert(self, alert: Alert):
        """Save alert to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alerts
            (id, title, message, severity, source, status, created_at,
             acknowledged_at, resolved_at, acknowledged_by, metadata_json,
             notification_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.id,
            alert.title,
            alert.message,
            alert.severity.value,
            alert.source,
            alert.status.value,
            alert.created_at.isoformat(),
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            alert.resolved_at.isoformat() if alert.resolved_at else None,
            alert.acknowledged_by,
            json.dumps(alert.metadata),
            1 if alert.notification_sent else 0,
        ))

        conn.commit()
        conn.close()

    async def _update_alert(self, alert: Alert):
        """Update alert in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE alerts SET
                status = ?,
                acknowledged_at = ?,
                resolved_at = ?,
                acknowledged_by = ?,
                notification_sent = ?
            WHERE id = ?
        """, (
            alert.status.value,
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            alert.resolved_at.isoformat() if alert.resolved_at else None,
            alert.acknowledged_by,
            1 if alert.notification_sent else 0,
            alert.id,
        ))

        conn.commit()
        conn.close()

    def _row_to_alert(self, row: tuple) -> Alert:
        """Convert database row to Alert"""
        return Alert(
            id=row[0],
            title=row[1],
            message=row[2],
            severity=AlertSeverity(row[3]),
            source=row[4],
            status=AlertStatus(row[5]),
            created_at=datetime.fromisoformat(row[6]),
            acknowledged_at=datetime.fromisoformat(row[7]) if row[7] else None,
            resolved_at=datetime.fromisoformat(row[8]) if row[8] else None,
            acknowledged_by=row[9],
            metadata=json.loads(row[10]) if row[10] else {},
            notification_sent=bool(row[11]),
        )


# =============================================================================
# SINGLETON
# =============================================================================

_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the alert manager singleton"""
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager
