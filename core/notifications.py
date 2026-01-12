"""
Notification Manager - Unified notification system for all channels.
Supports Telegram, Discord, webhooks, email, and push notifications.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import json


class NotificationChannel(Enum):
    """Notification channels."""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    CONSOLE = "console"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    """Types of notifications."""
    TRADE_EXECUTED = "trade_executed"
    PRICE_ALERT = "price_alert"
    POSITION_UPDATE = "position_update"
    RISK_WARNING = "risk_warning"
    SYSTEM_ERROR = "system_error"
    BALANCE_UPDATE = "balance_update"
    WHALE_ALERT = "whale_alert"
    NEWS_ALERT = "news_alert"
    CUSTOM = "custom"


@dataclass
class ChannelConfig:
    """Configuration for a notification channel."""
    channel: NotificationChannel
    enabled: bool
    endpoint: str                  # URL, chat_id, email, etc.
    api_key: Optional[str]
    min_priority: NotificationPriority
    rate_limit_per_minute: int
    template: Optional[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class Notification:
    """A notification to send."""
    notification_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    channels: List[NotificationChannel]
    data: Dict
    created_at: datetime
    sent_at: Optional[datetime]
    delivered: bool
    error: Optional[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class NotificationTemplate:
    """Template for notifications."""
    template_id: str
    notification_type: NotificationType
    title_template: str
    message_template: str
    default_channels: List[NotificationChannel]
    default_priority: NotificationPriority


class NotificationManager:
    """
    Unified notification manager for all channels.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "notifications.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.channels: Dict[NotificationChannel, ChannelConfig] = {}
        self.templates: Dict[NotificationType, NotificationTemplate] = {}
        self.handlers: Dict[NotificationChannel, Callable] = {}
        self.queue: asyncio.Queue = asyncio.Queue()

        # Rate limiting
        self.rate_counters: Dict[NotificationChannel, List[datetime]] = {}

        self._lock = threading.Lock()
        self._running = False

        self._setup_default_templates()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS channel_configs (
                    channel TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 1,
                    endpoint TEXT NOT NULL,
                    api_key TEXT,
                    min_priority TEXT NOT NULL,
                    rate_limit_per_minute INTEGER DEFAULT 10,
                    template TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    channels TEXT NOT NULL,
                    data TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    delivered INTEGER DEFAULT 0,
                    error TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS notification_stats (
                    channel TEXT NOT NULL,
                    date TEXT NOT NULL,
                    sent_count INTEGER DEFAULT 0,
                    delivered_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    PRIMARY KEY (channel, date)
                );

                CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);
                CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at);
            """)

    def _setup_default_templates(self):
        """Setup default notification templates."""
        self.templates[NotificationType.TRADE_EXECUTED] = NotificationTemplate(
            template_id="trade_executed",
            notification_type=NotificationType.TRADE_EXECUTED,
            title_template="Trade Executed: {symbol}",
            message_template="{side} {amount} {symbol} @ ${price}\nTotal: ${total}\nPnL: {pnl}",
            default_channels=[NotificationChannel.TELEGRAM, NotificationChannel.DISCORD],
            default_priority=NotificationPriority.MEDIUM
        )

        self.templates[NotificationType.PRICE_ALERT] = NotificationTemplate(
            template_id="price_alert",
            notification_type=NotificationType.PRICE_ALERT,
            title_template="Price Alert: {symbol}",
            message_template="{symbol} has reached ${price}\nCondition: {condition}",
            default_channels=[NotificationChannel.TELEGRAM],
            default_priority=NotificationPriority.HIGH
        )

        self.templates[NotificationType.RISK_WARNING] = NotificationTemplate(
            template_id="risk_warning",
            notification_type=NotificationType.RISK_WARNING,
            title_template="Risk Warning: {symbol}",
            message_template="Position at risk!\n{symbol}: {message}\nAction required: {action}",
            default_channels=[NotificationChannel.TELEGRAM, NotificationChannel.DISCORD],
            default_priority=NotificationPriority.CRITICAL
        )

        self.templates[NotificationType.WHALE_ALERT] = NotificationTemplate(
            template_id="whale_alert",
            notification_type=NotificationType.WHALE_ALERT,
            title_template="Whale Alert: {symbol}",
            message_template="Large {side} detected!\n{symbol}: {amount} (${value})\nFrom: {wallet}",
            default_channels=[NotificationChannel.TELEGRAM],
            default_priority=NotificationPriority.HIGH
        )

    def configure_channel(
        self,
        channel: NotificationChannel,
        endpoint: str,
        api_key: Optional[str] = None,
        min_priority: NotificationPriority = NotificationPriority.LOW,
        rate_limit: int = 10,
        enabled: bool = True
    ) -> ChannelConfig:
        """Configure a notification channel."""
        config = ChannelConfig(
            channel=channel,
            enabled=enabled,
            endpoint=endpoint,
            api_key=api_key,
            min_priority=min_priority,
            rate_limit_per_minute=rate_limit,
            template=None
        )

        self.channels[channel] = config
        self.rate_counters[channel] = []

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO channel_configs
                (channel, enabled, endpoint, api_key, min_priority,
                 rate_limit_per_minute, template, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
            """, (
                channel.value, 1 if enabled else 0, endpoint, api_key,
                min_priority.value, rate_limit, None
            ))

        return config

    def register_handler(
        self,
        channel: NotificationChannel,
        handler: Callable[[Notification, ChannelConfig], bool]
    ):
        """Register a handler for a notification channel."""
        self.handlers[channel] = handler

    async def send(
        self,
        notification_type: NotificationType,
        data: Dict,
        title: Optional[str] = None,
        message: Optional[str] = None,
        priority: Optional[NotificationPriority] = None,
        channels: Optional[List[NotificationChannel]] = None
    ) -> Notification:
        """Send a notification."""
        import uuid

        # Get template
        template = self.templates.get(notification_type)

        # Build notification
        if template and not title:
            title = self._format_template(template.title_template, data)
        if template and not message:
            message = self._format_template(template.message_template, data)

        if not priority:
            priority = template.default_priority if template else NotificationPriority.MEDIUM
        if not channels:
            channels = template.default_channels if template else [NotificationChannel.CONSOLE]

        now = datetime.now()
        notification = Notification(
            notification_id=str(uuid.uuid4())[:12],
            notification_type=notification_type,
            title=title or "",
            message=message or "",
            priority=priority,
            channels=channels,
            data=data,
            created_at=now,
            sent_at=None,
            delivered=False,
            error=None
        )

        # Queue notification
        await self.queue.put(notification)

        # Process immediately if not running worker
        if not self._running:
            await self._process_notification(notification)

        return notification

    def _format_template(self, template: str, data: Dict) -> str:
        """Format a template with data."""
        try:
            return template.format(**data)
        except KeyError:
            # Return template with available data
            for key, value in data.items():
                template = template.replace(f"{{{key}}}", str(value))
            return template

    async def _process_notification(self, notification: Notification):
        """Process and send a notification."""
        errors = []

        for channel in notification.channels:
            config = self.channels.get(channel)

            if not config or not config.enabled:
                continue

            # Check priority
            priority_order = list(NotificationPriority)
            if priority_order.index(notification.priority) < priority_order.index(config.min_priority):
                continue

            # Check rate limit
            if not self._check_rate_limit(channel, config):
                errors.append(f"{channel.value}: rate limited")
                continue

            # Send via handler
            handler = self.handlers.get(channel)
            if handler:
                try:
                    success = await self._call_handler(handler, notification, config)
                    if not success:
                        errors.append(f"{channel.value}: handler failed")
                except Exception as e:
                    errors.append(f"{channel.value}: {str(e)}")
            else:
                # Use default handlers
                success = await self._send_default(notification, channel, config)
                if not success:
                    errors.append(f"{channel.value}: send failed")

        # Update notification
        notification.sent_at = datetime.now()
        notification.delivered = len(errors) == 0
        notification.error = "; ".join(errors) if errors else None

        # Save to database
        self._save_notification(notification)

    async def _call_handler(
        self,
        handler: Callable,
        notification: Notification,
        config: ChannelConfig
    ) -> bool:
        """Call handler (sync or async)."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(notification, config)
        else:
            return handler(notification, config)

    async def _send_default(
        self,
        notification: Notification,
        channel: NotificationChannel,
        config: ChannelConfig
    ) -> bool:
        """Send using default channel handlers."""
        if channel == NotificationChannel.CONSOLE:
            print(f"[{notification.priority.value.upper()}] {notification.title}")
            print(notification.message)
            return True

        elif channel == NotificationChannel.WEBHOOK:
            return await self._send_webhook(notification, config)

        elif channel == NotificationChannel.TELEGRAM:
            return await self._send_telegram(notification, config)

        elif channel == NotificationChannel.DISCORD:
            return await self._send_discord(notification, config)

        return False

    async def _send_webhook(
        self,
        notification: Notification,
        config: ChannelConfig
    ) -> bool:
        """Send webhook notification."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "type": notification.notification_type.value,
                    "data": notification.data,
                    "timestamp": notification.created_at.isoformat()
                }
                headers = {}
                if config.api_key:
                    headers["Authorization"] = f"Bearer {config.api_key}"

                async with session.post(
                    config.endpoint,
                    json=payload,
                    headers=headers
                ) as resp:
                    return resp.status < 400
        except Exception:
            return False

    async def _send_telegram(
        self,
        notification: Notification,
        config: ChannelConfig
    ) -> bool:
        """Send Telegram notification."""
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{config.api_key}/sendMessage"
            payload = {
                "chat_id": config.endpoint,
                "text": f"*{notification.title}*\n\n{notification.message}",
                "parse_mode": "Markdown"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _send_discord(
        self,
        notification: Notification,
        config: ChannelConfig
    ) -> bool:
        """Send Discord webhook notification."""
        try:
            import aiohttp
            color_map = {
                NotificationPriority.LOW: 0x808080,
                NotificationPriority.MEDIUM: 0x0099ff,
                NotificationPriority.HIGH: 0xffcc00,
                NotificationPriority.CRITICAL: 0xff0000
            }
            payload = {
                "embeds": [{
                    "title": notification.title,
                    "description": notification.message,
                    "color": color_map.get(notification.priority, 0x0099ff),
                    "timestamp": notification.created_at.isoformat()
                }]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(config.endpoint, json=payload) as resp:
                    return resp.status < 400
        except Exception:
            return False

    def _check_rate_limit(
        self,
        channel: NotificationChannel,
        config: ChannelConfig
    ) -> bool:
        """Check if rate limit allows sending."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        with self._lock:
            if channel not in self.rate_counters:
                self.rate_counters[channel] = []

            # Clean old entries
            self.rate_counters[channel] = [
                t for t in self.rate_counters[channel] if t > cutoff
            ]

            if len(self.rate_counters[channel]) >= config.rate_limit_per_minute:
                return False

            self.rate_counters[channel].append(now)
            return True

    def _save_notification(self, notification: Notification):
        """Save notification to database."""
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO notifications
                (notification_id, notification_type, title, message, priority,
                 channels, data, created_at, sent_at, delivered, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification.notification_id,
                notification.notification_type.value,
                notification.title, notification.message,
                notification.priority.value,
                json.dumps([c.value for c in notification.channels]),
                json.dumps(notification.data),
                notification.created_at.isoformat(),
                notification.sent_at.isoformat() if notification.sent_at else None,
                1 if notification.delivered else 0,
                notification.error,
                json.dumps(notification.metadata)
            ))

    async def start_worker(self):
        """Start notification worker."""
        self._running = True
        while self._running:
            try:
                notification = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                await self._process_notification(notification)
            except asyncio.TimeoutError:
                continue
            except Exception:
                pass

    def stop_worker(self):
        """Stop notification worker."""
        self._running = False

    def get_history(
        self,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50
    ) -> List[Notification]:
        """Get notification history."""
        with self._get_db() as conn:
            if notification_type:
                rows = conn.execute("""
                    SELECT * FROM notifications
                    WHERE notification_type = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (notification_type.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM notifications
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()

            return [
                Notification(
                    notification_id=row["notification_id"],
                    notification_type=NotificationType(row["notification_type"]),
                    title=row["title"],
                    message=row["message"],
                    priority=NotificationPriority(row["priority"]),
                    channels=[NotificationChannel(c) for c in json.loads(row["channels"])],
                    data=json.loads(row["data"] or "{}"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
                    delivered=bool(row["delivered"]),
                    error=row["error"],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                for row in rows
            ]


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get or create the notification manager singleton."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
