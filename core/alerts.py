"""
Alert System - Price alerts, notifications, and webhooks.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PCT = "price_change_pct"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    MA_CROSS = "ma_cross"
    WHALE_MOVEMENT = "whale_movement"
    LIQUIDITY_CHANGE = "liquidity_change"
    CUSTOM = "custom"


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"


class NotificationChannel(Enum):
    """Notification channels."""
    CONSOLE = "console"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    PUSH = "push"


@dataclass
class AlertCondition:
    """Alert trigger condition."""
    alert_type: AlertType
    symbol: str
    threshold: float
    comparison: str = "gte"
    secondary_threshold: Optional[float] = None
    time_window_minutes: int = 0


@dataclass
class Alert:
    """An alert configuration."""
    id: str
    name: str
    condition: AlertCondition
    priority: AlertPriority
    channels: List[NotificationChannel]
    status: AlertStatus
    created_at: str
    expires_at: Optional[str]
    cooldown_minutes: int = 60
    max_triggers: int = 0
    trigger_count: int = 0
    last_triggered: Optional[str] = None
    message_template: str = ""
    webhook_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertTrigger:
    """A triggered alert event."""
    alert_id: str
    alert_name: str
    symbol: str
    alert_type: AlertType
    trigger_value: float
    threshold: float
    message: str
    priority: AlertPriority
    timestamp: str
    channels_notified: List[str]
    notification_status: Dict[str, bool]


class AlertDB:
    """SQLite storage for alerts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    threshold REAL,
                    comparison TEXT,
                    secondary_threshold REAL,
                    time_window_minutes INTEGER,
                    priority TEXT,
                    channels_json TEXT,
                    status TEXT,
                    created_at TEXT,
                    expires_at TEXT,
                    cooldown_minutes INTEGER,
                    max_triggers INTEGER,
                    trigger_count INTEGER DEFAULT 0,
                    last_triggered TEXT,
                    message_template TEXT,
                    webhook_url TEXT,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL,
                    alert_name TEXT,
                    symbol TEXT,
                    alert_type TEXT,
                    trigger_value REAL,
                    threshold REAL,
                    message TEXT,
                    priority TEXT,
                    timestamp TEXT,
                    channels_notified_json TEXT,
                    notification_status_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_configs (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    url TEXT NOT NULL,
                    channel TEXT,
                    headers_json TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class AlertManager:
    """
    Manage alerts and notifications.

    Usage:
        manager = AlertManager()

        # Create price alert
        alert = await manager.create_alert(
            name="SOL Above $100",
            condition=AlertCondition(
                alert_type=AlertType.PRICE_ABOVE,
                symbol="SOL",
                threshold=100.0
            ),
            channels=[NotificationChannel.CONSOLE]
        )

        # Check alerts
        await manager.check_alerts({"SOL": 105.0})
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "alerts.db"
        self.db = AlertDB(db_path)
        self._alerts: Dict[str, Alert] = {}
        self._webhooks: Dict[str, Dict] = {}
        self._price_history: Dict[str, List[Tuple[float, str]]] = {}
        self._custom_handlers: Dict[str, Callable] = {}
        self._notification_handlers: Dict[NotificationChannel, Callable] = {}
        self._load_alerts()
        self._setup_default_handlers()

    def _load_alerts(self):
        """Load active alerts from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts WHERE status = 'active'")

            for row in cursor.fetchall():
                condition = AlertCondition(
                    alert_type=AlertType(row['alert_type']),
                    symbol=row['symbol'],
                    threshold=row['threshold'],
                    comparison=row['comparison'] or 'gte',
                    secondary_threshold=row['secondary_threshold'],
                    time_window_minutes=row['time_window_minutes'] or 0
                )

                channels = json.loads(row['channels_json']) if row['channels_json'] else []

                alert = Alert(
                    id=row['id'],
                    name=row['name'],
                    condition=condition,
                    priority=AlertPriority(row['priority']),
                    channels=[NotificationChannel(c) for c in channels],
                    status=AlertStatus(row['status']),
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    cooldown_minutes=row['cooldown_minutes'] or 60,
                    max_triggers=row['max_triggers'] or 0,
                    trigger_count=row['trigger_count'] or 0,
                    last_triggered=row['last_triggered'],
                    message_template=row['message_template'] or "",
                    webhook_url=row['webhook_url'],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )

                self._alerts[alert.id] = alert

        logger.info(f"Loaded {len(self._alerts)} active alerts")

    def _setup_default_handlers(self):
        """Setup default notification handlers."""
        self._notification_handlers[NotificationChannel.CONSOLE] = self._notify_console

    async def _notify_console(self, trigger: AlertTrigger):
        """Console notification handler."""
        priority_emoji = {
            AlertPriority.LOW: "i",
            AlertPriority.MEDIUM: "!",
            AlertPriority.HIGH: "!!",
            AlertPriority.CRITICAL: "!!!"
        }
        emoji = priority_emoji.get(trigger.priority, "")
        print(f"[{emoji}] ALERT: {trigger.message}")

    async def create_alert(
        self,
        name: str,
        condition: AlertCondition,
        channels: List[NotificationChannel] = None,
        priority: AlertPriority = AlertPriority.MEDIUM,
        expires_at: Optional[datetime] = None,
        cooldown_minutes: int = 60,
        max_triggers: int = 0,
        message_template: str = "",
        webhook_url: str = "",
        metadata: Dict[str, Any] = None
    ) -> Alert:
        """Create a new alert."""
        alert_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        if channels is None:
            channels = [NotificationChannel.CONSOLE]

        if not message_template:
            message_template = f"{condition.symbol} {condition.alert_type.value}: {{value}} (threshold: {{threshold}})"

        alert = Alert(
            id=alert_id,
            name=name,
            condition=condition,
            priority=priority,
            channels=channels,
            status=AlertStatus.ACTIVE,
            created_at=now,
            expires_at=expires_at.isoformat() if expires_at else None,
            cooldown_minutes=cooldown_minutes,
            max_triggers=max_triggers,
            message_template=message_template,
            webhook_url=webhook_url,
            metadata=metadata or {}
        )

        self._save_alert(alert)
        self._alerts[alert_id] = alert

        logger.info(f"Created alert {alert_id}: {name}")
        return alert

    def _save_alert(self, alert: Alert):
        """Save alert to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alerts
                (id, name, alert_type, symbol, threshold, comparison,
                 secondary_threshold, time_window_minutes, priority, channels_json,
                 status, created_at, expires_at, cooldown_minutes, max_triggers,
                 trigger_count, last_triggered, message_template, webhook_url,
                 metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.id, alert.name, alert.condition.alert_type.value,
                alert.condition.symbol, alert.condition.threshold,
                alert.condition.comparison, alert.condition.secondary_threshold,
                alert.condition.time_window_minutes, alert.priority.value,
                json.dumps([c.value for c in alert.channels]),
                alert.status.value, alert.created_at, alert.expires_at,
                alert.cooldown_minutes, alert.max_triggers, alert.trigger_count,
                alert.last_triggered, alert.message_template, alert.webhook_url,
                json.dumps(alert.metadata)
            ))
            conn.commit()

    async def check_alerts(
        self,
        prices: Dict[str, float],
        volumes: Dict[str, float] = None,
        indicators: Dict[str, Dict] = None
    ) -> List[AlertTrigger]:
        """Check all active alerts against current data."""
        now = datetime.now(timezone.utc)
        triggered = []

        for alert_id, alert in list(self._alerts.items()):
            if alert.status != AlertStatus.ACTIVE:
                continue

            # Check expiration
            if alert.expires_at:
                expires = datetime.fromisoformat(alert.expires_at.replace('Z', '+00:00'))
                if now > expires:
                    alert.status = AlertStatus.EXPIRED
                    self._save_alert(alert)
                    continue

            # Check cooldown
            if alert.last_triggered:
                last = datetime.fromisoformat(alert.last_triggered.replace('Z', '+00:00'))
                if (now - last).total_seconds() < alert.cooldown_minutes * 60:
                    continue

            # Check max triggers
            if alert.max_triggers > 0 and alert.trigger_count >= alert.max_triggers:
                alert.status = AlertStatus.TRIGGERED
                self._save_alert(alert)
                continue

            # Check condition
            symbol = alert.condition.symbol
            current_value = None
            should_trigger = False

            if alert.condition.alert_type in [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW]:
                current_value = prices.get(symbol)
                if current_value:
                    should_trigger = self._check_threshold(
                        current_value,
                        alert.condition.threshold,
                        alert.condition.alert_type
                    )

            elif alert.condition.alert_type == AlertType.RSI_OVERBOUGHT:
                if indicators and symbol in indicators:
                    rsi = indicators[symbol].get('rsi')
                    if rsi is not None:
                        current_value = rsi
                        should_trigger = rsi >= alert.condition.threshold

            elif alert.condition.alert_type == AlertType.RSI_OVERSOLD:
                if indicators and symbol in indicators:
                    rsi = indicators[symbol].get('rsi')
                    if rsi is not None:
                        current_value = rsi
                        should_trigger = rsi <= alert.condition.threshold

            if should_trigger and current_value is not None:
                trigger = await self._trigger_alert(alert, current_value)
                if trigger:
                    triggered.append(trigger)

        return triggered

    def _check_threshold(
        self,
        value: float,
        threshold: float,
        alert_type: AlertType
    ) -> bool:
        """Check if value meets threshold condition."""
        if alert_type == AlertType.PRICE_ABOVE:
            return value >= threshold
        elif alert_type == AlertType.PRICE_BELOW:
            return value <= threshold
        return False

    async def _trigger_alert(self, alert: Alert, trigger_value: float) -> Optional[AlertTrigger]:
        """Trigger an alert and send notifications."""
        now = datetime.now(timezone.utc)

        message = alert.message_template.format(
            symbol=alert.condition.symbol,
            value=trigger_value,
            threshold=alert.condition.threshold,
            alert_type=alert.condition.alert_type.value,
            name=alert.name
        )

        trigger = AlertTrigger(
            alert_id=alert.id,
            alert_name=alert.name,
            symbol=alert.condition.symbol,
            alert_type=alert.condition.alert_type,
            trigger_value=trigger_value,
            threshold=alert.condition.threshold,
            message=message,
            priority=alert.priority,
            timestamp=now.isoformat(),
            channels_notified=[c.value for c in alert.channels],
            notification_status={}
        )

        # Send notifications
        for channel in alert.channels:
            try:
                if channel in self._notification_handlers:
                    await self._notification_handlers[channel](trigger)
                    trigger.notification_status[channel.value] = True
                else:
                    trigger.notification_status[channel.value] = False
            except Exception as e:
                logger.error(f"Failed to send {channel.value} notification: {e}")
                trigger.notification_status[channel.value] = False

        # Update alert state
        alert.trigger_count += 1
        alert.last_triggered = now.isoformat()
        self._save_alert(alert)

        # Save trigger
        self._save_trigger(trigger)

        logger.info(f"Alert triggered: {alert.name} - {message}")
        return trigger

    def _save_trigger(self, trigger: AlertTrigger):
        """Save alert trigger to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alert_triggers
                (alert_id, alert_name, symbol, alert_type, trigger_value,
                 threshold, message, priority, timestamp, channels_notified_json,
                 notification_status_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trigger.alert_id, trigger.alert_name, trigger.symbol,
                trigger.alert_type.value, trigger.trigger_value,
                trigger.threshold, trigger.message, trigger.priority.value,
                trigger.timestamp, json.dumps(trigger.channels_notified),
                json.dumps(trigger.notification_status)
            ))
            conn.commit()

    def add_webhook(self, channel: str, url: str, name: str = ""):
        """Add webhook configuration."""
        webhook_id = str(uuid.uuid4())[:8]

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO webhook_configs (id, name, url, channel, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (
                webhook_id, name or channel, url, channel,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

        self._webhooks[channel] = {'name': name, 'url': url, 'channel': channel}
        logger.info(f"Added webhook for {channel}")

    def set_notification_handler(self, channel: NotificationChannel, handler: Callable):
        """Set custom notification handler for a channel."""
        self._notification_handlers[channel] = handler

    async def cancel_alert(self, alert_id: str) -> bool:
        """Cancel an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.CANCELLED
        self._save_alert(alert)
        del self._alerts[alert_id]

        logger.info(f"Cancelled alert {alert_id}")
        return True

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)

    def get_active_alerts(self, symbol: Optional[str] = None) -> List[Alert]:
        """Get all active alerts."""
        alerts = [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]
        if symbol:
            alerts = [a for a in alerts if a.condition.symbol == symbol.upper()]
        return alerts

    def get_trigger_history(self, alert_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get alert trigger history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if alert_id:
                cursor.execute("""
                    SELECT * FROM alert_triggers WHERE alert_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (alert_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM alert_triggers ORDER BY timestamp DESC LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]


# Singleton
_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get singleton alert manager."""
    global _manager
    if _manager is None:
        _manager = AlertManager()
    return _manager
