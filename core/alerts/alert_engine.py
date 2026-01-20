"""
Alert Engine Core

Real-time alert system with subscription management,
multi-channel delivery, and rate limiting.

Prompt #101: Alert Engine Core
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from enum import Enum
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of alerts"""
    PRICE_THRESHOLD = "price_threshold"
    WHALE_ACTIVITY = "whale_activity"
    SENTIMENT_SHIFT = "sentiment_shift"
    VOLUME_SPIKE = "volume_spike"
    STRATEGY_SIGNAL = "strategy_signal"
    PREDICTION = "prediction"
    SYSTEM = "system"


class AlertPriority(str, Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryChannel(str, Enum):
    """Alert delivery channels"""
    PUSH = "push"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"


class SubscriptionTier(str, Enum):
    """Alert subscription tiers"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    STAKER = "staker"


@dataclass
class TierLimits:
    """Limits per subscription tier"""
    alerts_per_day: int
    delay_seconds: int
    channels: List[DeliveryChannel]


TIER_LIMITS = {
    SubscriptionTier.FREE: TierLimits(
        alerts_per_day=3,
        delay_seconds=900,  # 15 minutes
        channels=[DeliveryChannel.PUSH]
    ),
    SubscriptionTier.STARTER: TierLimits(
        alerts_per_day=50,
        delay_seconds=300,  # 5 minutes
        channels=[DeliveryChannel.PUSH, DeliveryChannel.TELEGRAM]
    ),
    SubscriptionTier.PRO: TierLimits(
        alerts_per_day=10000,  # Unlimited
        delay_seconds=0,  # Real-time
        channels=[DeliveryChannel.PUSH, DeliveryChannel.TELEGRAM, DeliveryChannel.DISCORD, DeliveryChannel.WEBHOOK]
    ),
    SubscriptionTier.STAKER: TierLimits(
        alerts_per_day=10000,
        delay_seconds=0,
        channels=[DeliveryChannel.PUSH, DeliveryChannel.TELEGRAM, DeliveryChannel.DISCORD, DeliveryChannel.WEBHOOK, DeliveryChannel.EMAIL]
    ),
}


@dataclass
class AlertSubscription:
    """User's alert subscription configuration"""
    user_id: str
    alert_type: AlertType
    enabled: bool = True
    channels: List[DeliveryChannel] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "alert_type": self.alert_type.value,
            "enabled": self.enabled,
            "channels": [c.value for c in self.channels],
            "filters": self.filters,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertSubscription":
        return cls(
            user_id=data["user_id"],
            alert_type=AlertType(data["alert_type"]),
            enabled=data.get("enabled", True),
            channels=[DeliveryChannel(c) for c in data.get("channels", [])],
            filters=data.get("filters", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )


@dataclass
class Alert:
    """An alert instance"""
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    token: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    delivered_to: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.alert_id:
            data = f"{self.alert_type}{self.title}{self.created_at.isoformat()}"
            self.alert_id = f"ALERT-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "token": self.token,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "delivered_to": list(self.delivered_to)
        }

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at


class AlertEngine:
    """
    Core alert engine with subscription management

    Features:
    - Multiple alert types
    - User subscriptions with filters
    - Rate limiting per tier
    - Deduplication
    - Multi-channel delivery
    """

    def __init__(
        self,
        storage_path: str = "data/alerts/",
        delivery_service: Any = None
    ):
        self.storage_path = Path(storage_path)
        self.delivery_service = delivery_service

        # In-memory state
        self.subscriptions: Dict[str, List[AlertSubscription]] = {}  # user_id -> subscriptions
        self.recent_alerts: List[Alert] = []
        self.alert_counts: Dict[str, Dict[str, int]] = {}  # user_id -> {date: count}
        self.delivered_hashes: Set[str] = set()  # For deduplication

        # Load state
        self._load()

        # Background tasks
        self.running = False

    def _load(self):
        """Load subscriptions and state from storage"""
        subs_path = self.storage_path / "subscriptions.json"

        if subs_path.exists():
            try:
                with open(subs_path) as f:
                    data = json.load(f)

                for user_id, subs_data in data.get("subscriptions", {}).items():
                    self.subscriptions[user_id] = [
                        AlertSubscription.from_dict(s) for s in subs_data
                    ]

                logger.info(f"Loaded {len(self.subscriptions)} user subscriptions")

            except Exception as e:
                logger.error(f"Failed to load subscriptions: {e}")

    def _save(self):
        """Save state to storage"""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)

            subs_path = self.storage_path / "subscriptions.json"
            data = {
                "subscriptions": {
                    user_id: [s.to_dict() for s in subs]
                    for user_id, subs in self.subscriptions.items()
                },
                "updated_at": datetime.now().isoformat()
            }

            with open(subs_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save subscriptions: {e}")

    # ==================== SUBSCRIPTION MANAGEMENT ====================

    async def subscribe(
        self,
        user_id: str,
        alert_type: AlertType,
        channels: List[DeliveryChannel],
        filters: Optional[Dict[str, Any]] = None,
        replace_existing: bool = False
    ) -> AlertSubscription:
        """Subscribe user to an alert type"""

        subscription = AlertSubscription(
            user_id=user_id,
            alert_type=alert_type,
            channels=channels,
            filters=filters or {}
        )

        if user_id not in self.subscriptions:
            self.subscriptions[user_id] = []

        # Remove existing subscription for same type (only if replace_existing)
        if replace_existing:
            self.subscriptions[user_id] = [
                s for s in self.subscriptions[user_id]
                if s.alert_type != alert_type
            ]

        self.subscriptions[user_id].append(subscription)
        self._save()

        logger.info(f"User {user_id} subscribed to {alert_type.value}")
        return subscription

    async def unsubscribe(
        self,
        user_id: str,
        alert_type: AlertType
    ) -> bool:
        """Unsubscribe user from an alert type"""

        if user_id not in self.subscriptions:
            return False

        original_count = len(self.subscriptions[user_id])
        self.subscriptions[user_id] = [
            s for s in self.subscriptions[user_id]
            if s.alert_type != alert_type
        ]

        if len(self.subscriptions[user_id]) < original_count:
            self._save()
            logger.info(f"User {user_id} unsubscribed from {alert_type.value}")
            return True

        return False

    async def get_subscriptions(self, user_id: str) -> List[AlertSubscription]:
        """Get user's subscriptions"""
        return self.subscriptions.get(user_id, [])

    async def update_subscription(
        self,
        user_id: str,
        alert_type: AlertType,
        enabled: Optional[bool] = None,
        channels: Optional[List[DeliveryChannel]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[AlertSubscription]:
        """Update an existing subscription"""

        if user_id not in self.subscriptions:
            return None

        for sub in self.subscriptions[user_id]:
            if sub.alert_type == alert_type:
                if enabled is not None:
                    sub.enabled = enabled
                if channels is not None:
                    sub.channels = channels
                if filters is not None:
                    sub.filters = filters

                self._save()
                return sub

        return None

    # ==================== ALERT CREATION & DELIVERY ====================

    async def create_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        ttl_seconds: int = 3600
    ) -> Alert:
        """Create a new alert"""

        alert = Alert(
            alert_id="",
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            token=token,
            expires_at=datetime.now() + timedelta(seconds=ttl_seconds)
        )

        # Check for duplicate
        alert_hash = hashlib.sha256(
            f"{alert_type}{title}{message}".encode()
        ).hexdigest()[:16]

        if alert_hash in self.delivered_hashes:
            logger.debug(f"Duplicate alert suppressed: {title}")
            return alert

        self.delivered_hashes.add(alert_hash)

        # Add to recent alerts
        self.recent_alerts.append(alert)
        self._prune_old_alerts()

        # Trigger delivery
        await self._deliver_alert(alert)

        logger.info(f"Created alert: {alert.alert_id} - {title}")
        return alert

    async def _deliver_alert(self, alert: Alert):
        """Deliver alert to all subscribed users"""

        for user_id, subscriptions in self.subscriptions.items():
            for sub in subscriptions:
                if sub.alert_type != alert.alert_type:
                    continue

                if not sub.enabled:
                    continue

                # Check filters
                if not self._matches_filters(alert, sub.filters):
                    continue

                # Check rate limit
                if not self._check_rate_limit(user_id, SubscriptionTier.FREE):  # Would get actual tier
                    logger.debug(f"Rate limit exceeded for {user_id}")
                    continue

                # Deliver through each channel
                for channel in sub.channels:
                    await self._deliver_to_channel(alert, user_id, channel)

                alert.delivered_to.add(user_id)
                self._increment_count(user_id)

    def _matches_filters(self, alert: Alert, filters: Dict[str, Any]) -> bool:
        """Check if alert matches subscription filters"""

        if not filters:
            return True

        # Token filter
        if "tokens" in filters:
            if alert.token and alert.token not in filters["tokens"]:
                return False

        # Priority filter
        if "min_priority" in filters:
            priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.CRITICAL]
            min_idx = priority_order.index(AlertPriority(filters["min_priority"]))
            alert_idx = priority_order.index(alert.priority)
            if alert_idx < min_idx:
                return False

        return True

    def _check_rate_limit(self, user_id: str, tier: SubscriptionTier) -> bool:
        """Check if user is within rate limits"""

        limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
        today = datetime.now().strftime("%Y-%m-%d")

        if user_id not in self.alert_counts:
            self.alert_counts[user_id] = {}

        count = self.alert_counts[user_id].get(today, 0)
        return count < limits.alerts_per_day

    def _increment_count(self, user_id: str):
        """Increment user's daily alert count"""

        today = datetime.now().strftime("%Y-%m-%d")

        if user_id not in self.alert_counts:
            self.alert_counts[user_id] = {}

        self.alert_counts[user_id][today] = self.alert_counts[user_id].get(today, 0) + 1

    async def _deliver_to_channel(
        self,
        alert: Alert,
        user_id: str,
        channel: DeliveryChannel
    ):
        """Deliver alert to a specific channel"""

        if self.delivery_service:
            try:
                await self.delivery_service.deliver(alert, user_id, channel)
            except Exception as e:
                logger.error(f"Failed to deliver to {channel.value}: {e}")
        else:
            # Log for now
            logger.info(f"Would deliver to {user_id} via {channel.value}: {alert.title}")

    def _prune_old_alerts(self):
        """Remove expired alerts"""

        now = datetime.now()
        self.recent_alerts = [
            a for a in self.recent_alerts
            if not a.is_expired() and (now - a.created_at).seconds < 86400
        ]

        # Clean old dedup hashes (keep last 1000)
        if len(self.delivered_hashes) > 1000:
            self.delivered_hashes = set(list(self.delivered_hashes)[-500:])

        # Clean old counts
        today = datetime.now().strftime("%Y-%m-%d")
        for user_id in list(self.alert_counts.keys()):
            self.alert_counts[user_id] = {
                d: c for d, c in self.alert_counts[user_id].items()
                if d >= today
            }

    # ==================== PRICE ALERT MANAGEMENT ====================

    async def add_price_alert(
        self,
        user_id: str,
        token: str,
        threshold_price: float,
        direction: str,  # "above" or "below"
        percentage: Optional[float] = None
    ) -> str:
        """
        Add a price alert for a user

        Args:
            user_id: User ID
            token: Token symbol
            threshold_price: Price threshold (absolute)
            direction: "above" or "below"
            percentage: Optional percentage change threshold

        Returns:
            Alert ID
        """
        alert_id = hashlib.sha256(
            f"{user_id}{token}{threshold_price}{direction}".encode()
        ).hexdigest()[:12].upper()

        filters = {
            "tokens": [token],
            "price_threshold": threshold_price,
            "direction": direction,
            "alert_id": f"PRICE-{alert_id}"
        }

        if percentage is not None:
            filters["percentage_change"] = percentage

        await self.subscribe(
            user_id=user_id,
            alert_type=AlertType.PRICE_THRESHOLD,
            channels=[DeliveryChannel.TELEGRAM],
            filters=filters
        )

        return f"PRICE-{alert_id}"

    async def add_percentage_alert(
        self,
        user_id: str,
        token: str,
        percentage_change: float,
        direction: str  # "up" or "down"
    ) -> str:
        """
        Add a percentage change alert

        Args:
            user_id: User ID
            token: Token symbol
            percentage_change: Percentage threshold (e.g., 5.0 for 5%)
            direction: "up" or "down"

        Returns:
            Alert ID
        """
        alert_id = hashlib.sha256(
            f"{user_id}{token}{percentage_change}{direction}".encode()
        ).hexdigest()[:12].upper()

        filters = {
            "tokens": [token],
            "percentage_change": percentage_change,
            "direction": direction,
            "alert_id": f"PCT-{alert_id}"
        }

        await self.subscribe(
            user_id=user_id,
            alert_type=AlertType.PRICE_THRESHOLD,
            channels=[DeliveryChannel.TELEGRAM],
            filters=filters
        )

        return f"PCT-{alert_id}"

    async def remove_alert(self, user_id: str, alert_id: str) -> bool:
        """Remove a specific alert by ID"""
        if user_id not in self.subscriptions:
            return False

        # Find and remove subscription with matching alert_id
        for sub in self.subscriptions[user_id][:]:
            if sub.filters.get("alert_id") == alert_id:
                self.subscriptions[user_id].remove(sub)
                self._save()
                return True

        return False

    async def get_user_alerts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all alerts for a user"""
        if user_id not in self.subscriptions:
            return []

        alerts = []
        for sub in self.subscriptions[user_id]:
            if sub.alert_type == AlertType.PRICE_THRESHOLD:
                alert_info = {
                    "alert_id": sub.filters.get("alert_id", "UNKNOWN"),
                    "token": sub.filters.get("tokens", ["UNKNOWN"])[0],
                    "type": "price" if "price_threshold" in sub.filters else "percentage",
                }

                if "price_threshold" in sub.filters:
                    alert_info["threshold"] = sub.filters["price_threshold"]
                    alert_info["direction"] = sub.filters.get("direction", "unknown")

                if "percentage_change" in sub.filters:
                    alert_info["percentage"] = sub.filters["percentage_change"]
                    alert_info["direction"] = sub.filters.get("direction", "unknown")

                alerts.append(alert_info)

        return alerts

    # ==================== ALERT TRIGGERS ====================

    async def trigger_price_alert(
        self,
        token: str,
        current_price: float,
        threshold_price: float,
        direction: str  # "above" or "below"
    ):
        """Trigger a price threshold alert"""

        title = f"${token} Price Alert"
        message = f"${token} is now ${current_price:.6f} ({direction} ${threshold_price:.6f})"

        await self.create_alert(
            alert_type=AlertType.PRICE_THRESHOLD,
            title=title,
            message=message,
            priority=AlertPriority.HIGH,
            data={
                "current_price": current_price,
                "threshold_price": threshold_price,
                "direction": direction
            },
            token=token
        )

    async def trigger_percentage_alert(
        self,
        token: str,
        current_price: float,
        baseline_price: float,
        percentage_change: float,
        direction: str  # "up" or "down"
    ):
        """Trigger a percentage change alert"""

        emoji = "📈" if direction == "up" else "📉"
        title = f"{emoji} ${token} {abs(percentage_change):.1f}% {direction.upper()}"
        message = f"${token} moved {percentage_change:+.2f}% from ${baseline_price:.6f} to ${current_price:.6f}"

        await self.create_alert(
            alert_type=AlertType.PRICE_THRESHOLD,
            title=title,
            message=message,
            priority=AlertPriority.HIGH if abs(percentage_change) > 10 else AlertPriority.MEDIUM,
            data={
                "current_price": current_price,
                "baseline_price": baseline_price,
                "percentage_change": percentage_change,
                "direction": direction
            },
            token=token
        )

    async def trigger_whale_alert(
        self,
        token: str,
        wallet: str,
        action: str,  # "buy" or "sell"
        amount: float,
        value_usd: float
    ):
        """Trigger a whale activity alert"""

        title = f"Whale {action.capitalize()} - ${token}"
        message = f"Whale {wallet[:8]}... {action}ing {amount:,.0f} ${token} (${value_usd:,.0f})"

        await self.create_alert(
            alert_type=AlertType.WHALE_ACTIVITY,
            title=title,
            message=message,
            priority=AlertPriority.HIGH,
            data={
                "wallet": wallet,
                "action": action,
                "amount": amount,
                "value_usd": value_usd
            },
            token=token
        )

    async def trigger_sentiment_alert(
        self,
        token: str,
        old_sentiment: float,
        new_sentiment: float,
        change: float
    ):
        """Trigger a sentiment shift alert"""

        direction = "positive" if change > 0 else "negative"
        title = f"${token} Sentiment Shift"
        message = f"${token} sentiment shifted {direction}: {old_sentiment:.2f} -> {new_sentiment:.2f} ({change:+.2f})"

        priority = AlertPriority.HIGH if abs(change) > 0.3 else AlertPriority.MEDIUM

        await self.create_alert(
            alert_type=AlertType.SENTIMENT_SHIFT,
            title=title,
            message=message,
            priority=priority,
            data={
                "old_sentiment": old_sentiment,
                "new_sentiment": new_sentiment,
                "change": change
            },
            token=token
        )

    async def trigger_volume_alert(
        self,
        token: str,
        current_volume: float,
        average_volume: float,
        multiplier: float
    ):
        """Trigger a volume spike alert"""

        title = f"${token} Volume Spike"
        message = f"${token} volume {multiplier:.1f}x above average (${current_volume:,.0f} vs ${average_volume:,.0f})"

        await self.create_alert(
            alert_type=AlertType.VOLUME_SPIKE,
            title=title,
            message=message,
            priority=AlertPriority.MEDIUM,
            data={
                "current_volume": current_volume,
                "average_volume": average_volume,
                "multiplier": multiplier
            },
            token=token
        )

    async def trigger_strategy_signal(
        self,
        strategy_name: str,
        signal: str,  # "buy", "sell", "close"
        token: str,
        confidence: float,
        reason: str
    ):
        """Trigger a strategy signal alert"""

        emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "⚪"
        title = f"{emoji} {strategy_name} Signal"
        message = f"{signal.upper()} ${token} (Confidence: {confidence:.0%})\n{reason}"

        priority = AlertPriority.HIGH if confidence > 0.8 else AlertPriority.MEDIUM

        await self.create_alert(
            alert_type=AlertType.STRATEGY_SIGNAL,
            title=title,
            message=message,
            priority=priority,
            data={
                "strategy": strategy_name,
                "signal": signal,
                "confidence": confidence,
                "reason": reason
            },
            token=token
        )

    # ==================== HISTORY & STATS ====================

    async def get_recent_alerts(
        self,
        user_id: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 50
    ) -> List[Alert]:
        """Get recent alerts"""

        alerts = self.recent_alerts

        if user_id:
            alerts = [a for a in alerts if user_id in a.delivered_to]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return alerts[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert engine statistics"""

        total_subscriptions = sum(len(s) for s in self.subscriptions.values())

        by_type = {}
        for subs in self.subscriptions.values():
            for sub in subs:
                t = sub.alert_type.value
                by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_users": len(self.subscriptions),
            "total_subscriptions": total_subscriptions,
            "subscriptions_by_type": by_type,
            "recent_alerts": len(self.recent_alerts),
            "dedup_cache_size": len(self.delivered_hashes)
        }


# Singleton instance
_alert_engine: Optional[AlertEngine] = None


def get_alert_engine() -> AlertEngine:
    """Get alert engine singleton"""
    global _alert_engine

    if _alert_engine is None:
        _alert_engine = AlertEngine()

    return _alert_engine


# Testing
if __name__ == "__main__":
    async def test():
        engine = AlertEngine("test_alerts/")

        # Subscribe
        await engine.subscribe(
            user_id="USER_123",
            alert_type=AlertType.WHALE_ACTIVITY,
            channels=[DeliveryChannel.TELEGRAM, DeliveryChannel.PUSH],
            filters={"tokens": ["SOL", "JUP", "BONK"]}
        )

        # Trigger alert
        await engine.trigger_whale_alert(
            token="SOL",
            wallet="WHALE_WALLET_123",
            action="buy",
            amount=100000,
            value_usd=15000000
        )

        # Get stats
        print(f"Stats: {engine.get_stats()}")

        # Get recent alerts
        alerts = await engine.get_recent_alerts()
        print(f"Recent alerts: {len(alerts)}")

    asyncio.run(test())
