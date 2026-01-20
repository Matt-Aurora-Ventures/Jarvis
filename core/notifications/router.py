"""
Notification Router - Multi-channel notification routing with rate limiting,
batching, retry logic, and delivery tracking.

Supports:
- Multiple channels (Telegram, X/Twitter, Email, Webhook)
- Priority-based routing
- Per-channel rate limiting
- Automatic retries with exponential backoff
- Batch processing for low-priority notifications
- Delivery confirmation and tracking
- Circuit breaker pattern for failing channels
"""
import asyncio
import json
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class ChannelType(Enum):
    """Supported notification channel types."""
    TELEGRAM = "telegram"
    X_TWITTER = "x_twitter"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    SMS = "sms"
    CONSOLE = "console"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __lt__(self, other):
        if isinstance(other, NotificationPriority):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, NotificationPriority):
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, NotificationPriority):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, NotificationPriority):
            return self.value >= other.value
        return NotImplemented


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


class DeliveryStatus(Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    DELIVERED = "delivered"
    PARTIAL = "partial"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    QUEUED = "queued"


@dataclass
class ChannelConfig:
    """Configuration for a notification channel."""
    channel_type: ChannelType
    name: str
    endpoint: str
    api_key: Optional[str] = None
    min_priority: NotificationPriority = NotificationPriority.LOW
    rate_limit_per_minute: int = 60
    enabled: bool = True
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Notification:
    """A notification to be routed."""
    notification_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    data: Dict[str, Any]
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRule:
    """Rule for routing notifications to channels."""
    notification_type: NotificationType
    channels: List[str]
    min_priority: Optional[NotificationPriority] = None
    conditions: Optional[Dict[str, Any]] = None


@dataclass
class ChannelResult:
    """Result of sending to a single channel."""
    channel_name: str
    success: bool
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    latency_ms: float = 0
    retry_count: int = 0


@dataclass
class DeliveryRecord:
    """Record of notification delivery."""
    notification_id: str
    status: DeliveryStatus
    channel_results: Dict[str, ChannelResult]
    created_at: datetime
    completed_at: Optional[datetime] = None
    retry_count: int = 0


@dataclass
class RouteResult:
    """Result of routing a notification."""
    notification_id: str
    channels_sent: int
    channels_failed: int
    channels_rate_limited: int
    delivery_record: Optional[DeliveryRecord] = None


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    is_open: bool
    failure_count: int
    last_failure: Optional[datetime]
    opened_at: Optional[datetime]
    cooldown_until: Optional[datetime]


class NonRetryableError(Exception):
    """Error that should not trigger retry."""
    pass


class NotificationRouter:
    """
    Multi-channel notification router with rate limiting, batching,
    retry logic, and delivery tracking.
    """

    # Class-level exception for non-retryable errors
    NonRetryableError = NonRetryableError

    def __init__(
        self,
        batch_low_priority: bool = False,
        batch_interval_seconds: float = 60.0,
        batch_max_size: int = 10,
    ):
        # Channel configurations
        self._channels: Dict[str, ChannelConfig] = {}

        # Routing rules
        self._routing_rules: Dict[NotificationType, List[RoutingRule]] = defaultdict(list)

        # Rate limiting state
        self._rate_counters: Dict[str, List[datetime]] = defaultdict(list)

        # Circuit breakers
        self._circuit_breakers: Dict[str, Dict] = {}

        # Delivery tracking
        self._delivery_records: Dict[str, DeliveryRecord] = {}

        # Statistics
        self._stats = {
            "total_notifications": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_rate_limited": 0,
            "channels": defaultdict(lambda: {
                "sent": 0,
                "failed": 0,
                "rate_limited": 0,
                "total_latency_ms": 0,
            }),
        }

        # Batching configuration
        self._batch_low_priority = batch_low_priority
        self._batch_interval_seconds = batch_interval_seconds
        self._batch_max_size = batch_max_size
        self._batch_queue: List[Notification] = []
        self._batch_lock = threading.Lock()

        # General lock
        self._lock = threading.Lock()

    def register_channel(
        self,
        channel_type: ChannelType,
        name: str,
        endpoint: str,
        api_key: Optional[str] = None,
        min_priority: NotificationPriority = NotificationPriority.LOW,
        rate_limit_per_minute: int = 60,
        enabled: bool = True,
        retry_count: int = 3,
        retry_delay_seconds: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChannelConfig:
        """Register a notification channel."""
        config = ChannelConfig(
            channel_type=channel_type,
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            min_priority=min_priority,
            rate_limit_per_minute=rate_limit_per_minute,
            enabled=enabled,
            retry_count=retry_count,
            retry_delay_seconds=retry_delay_seconds,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_timeout=circuit_breaker_timeout,
            metadata=metadata or {},
        )

        with self._lock:
            self._channels[name] = config
            self._rate_counters[name] = []
            self._circuit_breakers[name] = {
                "failure_count": 0,
                "last_failure": None,
                "opened_at": None,
                "is_open": False,
            }
            self._stats["channels"][name] = {
                "sent": 0,
                "failed": 0,
                "rate_limited": 0,
                "total_latency_ms": 0,
            }

        return config

    def get_channel(self, name: str) -> Optional[ChannelConfig]:
        """Get channel configuration by name."""
        return self._channels.get(name)

    def disable_channel(self, name: str) -> None:
        """Disable a channel."""
        if name in self._channels:
            self._channels[name].enabled = False

    def enable_channel(self, name: str) -> None:
        """Enable a channel."""
        if name in self._channels:
            self._channels[name].enabled = True

    def add_routing_rule(
        self,
        notification_type: NotificationType,
        channels: List[str],
        min_priority: Optional[NotificationPriority] = None,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> RoutingRule:
        """Add a routing rule for a notification type."""
        rule = RoutingRule(
            notification_type=notification_type,
            channels=channels,
            min_priority=min_priority,
            conditions=conditions,
        )

        with self._lock:
            self._routing_rules[notification_type].append(rule)

        return rule

    def get_routing_rules(self, notification_type: NotificationType) -> List[RoutingRule]:
        """Get routing rules for a notification type."""
        return self._routing_rules.get(notification_type, [])

    def get_target_channels(self, notification: Notification) -> List[ChannelConfig]:
        """Get target channels for a notification based on rules and priority."""
        rules = self._routing_rules.get(notification.notification_type, [])
        target_channels: Set[str] = set()

        for rule in rules:
            # Check rule-level priority filter
            if rule.min_priority and notification.priority < rule.min_priority:
                continue

            target_channels.update(rule.channels)

        # Filter channels by their own priority settings and enabled status
        result = []
        for channel_name in target_channels:
            config = self._channels.get(channel_name)
            if config and config.enabled:
                if notification.priority >= config.min_priority:
                    result.append(config)

        return result

    def _check_rate_limit(self, channel_name: str) -> bool:
        """Check if channel is within rate limit. Returns True if allowed."""
        config = self._channels.get(channel_name)
        if not config:
            return False

        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        with self._lock:
            # Clean old entries
            self._rate_counters[channel_name] = [
                t for t in self._rate_counters[channel_name] if t > cutoff
            ]

            if len(self._rate_counters[channel_name]) >= config.rate_limit_per_minute:
                return False

            self._rate_counters[channel_name].append(now)
            return True

    def reset_rate_limit(self, channel_name: str) -> None:
        """Reset rate limit counter for a channel."""
        with self._lock:
            self._rate_counters[channel_name] = []

    def _check_circuit_breaker(self, channel_name: str) -> bool:
        """Check if circuit breaker allows request. Returns True if allowed."""
        config = self._channels.get(channel_name)
        if not config:
            return False

        with self._lock:
            cb = self._circuit_breakers.get(channel_name, {})

            if not cb.get("is_open", False):
                return True

            # Check if cooldown has passed
            opened_at = cb.get("opened_at")
            if opened_at:
                cooldown_end = opened_at + timedelta(seconds=config.circuit_breaker_timeout)
                if datetime.now() > cooldown_end:
                    # Reset circuit breaker
                    cb["is_open"] = False
                    cb["failure_count"] = 0
                    return True

            return False

    def _record_circuit_breaker_failure(self, channel_name: str) -> None:
        """Record a failure for circuit breaker."""
        config = self._channels.get(channel_name)
        if not config:
            return

        with self._lock:
            cb = self._circuit_breakers.setdefault(channel_name, {
                "failure_count": 0,
                "last_failure": None,
                "opened_at": None,
                "is_open": False,
            })

            cb["failure_count"] = cb.get("failure_count", 0) + 1
            cb["last_failure"] = datetime.now()

            if cb["failure_count"] >= config.circuit_breaker_threshold:
                cb["is_open"] = True
                cb["opened_at"] = datetime.now()

    def _record_circuit_breaker_success(self, channel_name: str) -> None:
        """Record a success for circuit breaker."""
        with self._lock:
            cb = self._circuit_breakers.get(channel_name)
            if cb:
                cb["failure_count"] = 0

    def get_circuit_breaker_state(self, channel_name: str) -> CircuitBreakerState:
        """Get circuit breaker state for a channel."""
        config = self._channels.get(channel_name)
        cb = self._circuit_breakers.get(channel_name, {})

        cooldown_until = None
        if cb.get("opened_at") and config:
            cooldown_until = cb["opened_at"] + timedelta(seconds=config.circuit_breaker_timeout)

        return CircuitBreakerState(
            is_open=cb.get("is_open", False),
            failure_count=cb.get("failure_count", 0),
            last_failure=cb.get("last_failure"),
            opened_at=cb.get("opened_at"),
            cooldown_until=cooldown_until,
        )

    async def _send_to_channel(
        self,
        channel_config: ChannelConfig,
        notification: Notification,
    ) -> bool:
        """
        Send notification to a specific channel.
        Override this method for actual channel implementations.
        """
        # Default implementation - override for actual sending
        if channel_config.channel_type == ChannelType.CONSOLE:
            print(f"[{notification.priority.name}] {notification.title}: {notification.message}")
            return True

        if channel_config.channel_type == ChannelType.TELEGRAM:
            return await self._send_telegram(channel_config, notification)

        if channel_config.channel_type == ChannelType.WEBHOOK:
            return await self._send_webhook(channel_config, notification)

        if channel_config.channel_type == ChannelType.X_TWITTER:
            return await self._send_x_twitter(channel_config, notification)

        if channel_config.channel_type == ChannelType.EMAIL:
            return await self._send_email(channel_config, notification)

        return False

    async def _send_telegram(
        self,
        config: ChannelConfig,
        notification: Notification,
    ) -> bool:
        """Send notification via Telegram."""
        try:
            import aiohttp

            url = f"https://api.telegram.org/bot{config.api_key}/sendMessage"
            payload = {
                "chat_id": config.endpoint,
                "text": f"*{notification.title}*\n\n{notification.message}",
                "parse_mode": "Markdown",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _send_webhook(
        self,
        config: ChannelConfig,
        notification: Notification,
    ) -> bool:
        """Send notification via webhook."""
        try:
            import aiohttp

            payload = {
                "notification_id": notification.notification_id,
                "type": notification.notification_type.value,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.name,
                "data": notification.data,
                "timestamp": notification.created_at.isoformat(),
            }

            headers = {}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config.endpoint,
                    json=payload,
                    headers=headers,
                ) as resp:
                    return resp.status < 400
        except Exception:
            return False

    async def _send_x_twitter(
        self,
        config: ChannelConfig,
        notification: Notification,
    ) -> bool:
        """Send notification via X/Twitter."""
        # Implementation would use Twitter API
        # For now, return False (not implemented)
        return False

    async def _send_email(
        self,
        config: ChannelConfig,
        notification: Notification,
    ) -> bool:
        """Send notification via email."""
        # Implementation would use SMTP
        # For now, return False (not implemented)
        return False

    async def _send_with_retry(
        self,
        channel_config: ChannelConfig,
        notification: Notification,
    ) -> ChannelResult:
        """Send with retry logic."""
        start_time = time.time()
        retry_count = 0
        last_error = None

        for attempt in range(channel_config.retry_count + 1):
            try:
                success = await self._send_to_channel(channel_config, notification)

                latency_ms = (time.time() - start_time) * 1000

                if success:
                    self._record_circuit_breaker_success(channel_config.name)
                    return ChannelResult(
                        channel_name=channel_config.name,
                        success=True,
                        sent_at=datetime.now(),
                        latency_ms=latency_ms,
                        retry_count=retry_count,
                    )
                else:
                    last_error = "Send returned False"
                    retry_count += 1
                    self._record_circuit_breaker_failure(channel_config.name)

                    if attempt < channel_config.retry_count:
                        await asyncio.sleep(
                            channel_config.retry_delay_seconds * (2 ** attempt)
                        )

            except NonRetryableError as e:
                # Don't retry non-retryable errors
                self._record_circuit_breaker_failure(channel_config.name)
                return ChannelResult(
                    channel_name=channel_config.name,
                    success=False,
                    error=str(e),
                    latency_ms=(time.time() - start_time) * 1000,
                    retry_count=0,
                )

            except Exception as e:
                last_error = str(e)
                retry_count += 1
                self._record_circuit_breaker_failure(channel_config.name)

                if attempt < channel_config.retry_count:
                    await asyncio.sleep(
                        channel_config.retry_delay_seconds * (2 ** attempt)
                    )

        return ChannelResult(
            channel_name=channel_config.name,
            success=False,
            error=last_error,
            latency_ms=(time.time() - start_time) * 1000,
            retry_count=retry_count,
        )

    async def route(self, notification: Notification) -> RouteResult:
        """Route a notification to appropriate channels."""
        self._stats["total_notifications"] += 1

        target_channels = self.get_target_channels(notification)

        if not target_channels:
            return RouteResult(
                notification_id=notification.notification_id,
                channels_sent=0,
                channels_failed=0,
                channels_rate_limited=0,
            )

        channel_results: Dict[str, ChannelResult] = {}
        channels_sent = 0
        channels_failed = 0
        channels_rate_limited = 0

        for channel_config in target_channels:
            # Check circuit breaker
            if not self._check_circuit_breaker(channel_config.name):
                channels_failed += 1
                channel_results[channel_config.name] = ChannelResult(
                    channel_name=channel_config.name,
                    success=False,
                    error="Circuit breaker open",
                )
                continue

            # Check rate limit
            if not self._check_rate_limit(channel_config.name):
                channels_rate_limited += 1
                self._stats["channels"][channel_config.name]["rate_limited"] += 1
                channel_results[channel_config.name] = ChannelResult(
                    channel_name=channel_config.name,
                    success=False,
                    error="Rate limited",
                )
                continue

            # Send with retry
            result = await self._send_with_retry(channel_config, notification)
            channel_results[channel_config.name] = result

            if result.success:
                channels_sent += 1
                self._stats["channels"][channel_config.name]["sent"] += 1
                self._stats["channels"][channel_config.name]["total_latency_ms"] += result.latency_ms
            else:
                channels_failed += 1
                self._stats["channels"][channel_config.name]["failed"] += 1

        # Determine overall status
        if channels_sent == len(target_channels):
            status = DeliveryStatus.DELIVERED
            self._stats["total_delivered"] += 1
        elif channels_sent > 0:
            status = DeliveryStatus.PARTIAL
            self._stats["total_delivered"] += 1
        elif channels_rate_limited == len(target_channels):
            status = DeliveryStatus.RATE_LIMITED
            self._stats["total_rate_limited"] += 1
        else:
            status = DeliveryStatus.FAILED
            self._stats["total_failed"] += 1

        # Create delivery record
        max_retry = max((r.retry_count for r in channel_results.values()), default=0)
        delivery_record = DeliveryRecord(
            notification_id=notification.notification_id,
            status=status,
            channel_results=channel_results,
            created_at=notification.created_at,
            completed_at=datetime.now(),
            retry_count=max_retry,
        )

        with self._lock:
            self._delivery_records[notification.notification_id] = delivery_record

        return RouteResult(
            notification_id=notification.notification_id,
            channels_sent=channels_sent,
            channels_failed=channels_failed,
            channels_rate_limited=channels_rate_limited,
            delivery_record=delivery_record,
        )

    async def queue(self, notification: Notification) -> None:
        """Queue a notification for batched sending (low priority)."""
        if notification.priority >= NotificationPriority.HIGH:
            # High priority notifications are sent immediately
            await self.route(notification)
            return

        with self._batch_lock:
            self._batch_queue.append(notification)

            # Flush if batch is full
            if len(self._batch_queue) >= self._batch_max_size:
                await self._flush_batch_internal()

    async def flush_batch(self) -> None:
        """Flush the batch queue."""
        with self._batch_lock:
            await self._flush_batch_internal()

    async def _flush_batch_internal(self) -> None:
        """Internal method to flush batch (must hold batch_lock)."""
        if not self._batch_queue:
            return

        # Create a batch notification
        batch_ids = [n.notification_id for n in self._batch_queue]
        batch_messages = [f"- {n.title}: {n.message}" for n in self._batch_queue]

        batch_notification = Notification(
            notification_id=f"batch-{uuid.uuid4().hex[:8]}",
            notification_type=NotificationType.CUSTOM,
            title=f"Batch Notification ({len(self._batch_queue)} items)",
            message="\n".join(batch_messages),
            priority=NotificationPriority.LOW,
            data={"batched_ids": batch_ids},
            created_at=datetime.now(),
        )

        self._batch_queue.clear()

        # Route the batch
        await self.route(batch_notification)

    def get_delivery_status(self, notification_id: str) -> Optional[DeliveryRecord]:
        """Get delivery status for a notification."""
        return self._delivery_records.get(notification_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "total_notifications": self._stats["total_notifications"],
            "total_delivered": self._stats["total_delivered"],
            "total_failed": self._stats["total_failed"],
            "total_rate_limited": self._stats["total_rate_limited"],
            "channels": dict(self._stats["channels"]),
        }

    def get_channel_statistics(self, channel_name: str) -> Dict[str, Any]:
        """Get statistics for a specific channel."""
        stats = self._stats["channels"].get(channel_name, {})
        sent = stats.get("sent", 0)

        return {
            "sent": sent,
            "failed": stats.get("failed", 0),
            "rate_limited": stats.get("rate_limited", 0),
            "total_latency_ms": stats.get("total_latency_ms", 0),
            "avg_latency_ms": stats.get("total_latency_ms", 0) / sent if sent > 0 else 0,
        }


# Singleton instance
_notification_router: Optional[NotificationRouter] = None


def get_notification_router() -> NotificationRouter:
    """Get or create the notification router singleton."""
    global _notification_router
    if _notification_router is None:
        _notification_router = NotificationRouter()
    return _notification_router
