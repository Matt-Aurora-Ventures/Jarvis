"""
Notification Service - Real-time alerts and notifications for users

Provides:
- Price alerts (token reaches target)
- Trade alerts (execution confirmation, fills)
- Performance alerts (milestone reached)
- Risk alerts (liquidation risk, drawdown)
- Algorithm alerts (high confidence signal)
- Fee alerts (fee earned, claim available)

Handles:
- Rate limiting (prevent alert spam)
- User preferences (opt-in/out)
- Multi-channel delivery (Telegram, email)
- Batching (send multiple alerts at once)
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    PRICE_ALERT = "price"
    TRADE_ALERT = "trade"
    PERFORMANCE = "performance"
    RISK_ALERT = "risk"
    ALGORITHM = "algorithm"
    FEE = "fee"
    SYSTEM = "system"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Notification:
    """A notification message."""
    notification_id: str
    user_id: int
    notification_type: NotificationType
    priority: NotificationPriority

    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    # Action buttons (callback_data)
    action_buttons: List[Dict[str, str]] = field(default_factory=list)

    @property
    def is_read(self) -> bool:
        """Has user read this notification?"""
        return self.read_at is not None

    @property
    def time_since_creation(self) -> timedelta:
        """Time elapsed since notification created."""
        return datetime.utcnow() - self.created_at

    def to_telegram_message(self) -> str:
        """Format as Telegram message."""
        priority_emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.MEDIUM: "📌",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.CRITICAL: "🚨",
        }[self.priority]

        lines = [
            f"{priority_emoji} <b>{self.title}</b>",
            self.message,
        ]

        # Add details
        for key, value in self.details.items():
            if isinstance(value, float):
                lines.append(f"<b>{key}:</b> <code>{value:.2f}</code>")
            else:
                lines.append(f"<b>{key}:</b> <code>{value}</code>")

        # Timestamp
        lines.append(f"\n<i>{self.created_at.strftime('%H:%M:%S UTC')}</i>")

        return "\n".join(lines)


@dataclass
class NotificationPreferences:
    """User notification preferences."""
    user_id: int

    # Enable/disable notification types
    price_alerts_enabled: bool = True
    trade_alerts_enabled: bool = True
    performance_alerts_enabled: bool = True
    risk_alerts_enabled: bool = True
    algorithm_alerts_enabled: bool = True
    fee_alerts_enabled: bool = True
    system_alerts_enabled: bool = True

    # Rate limiting
    max_alerts_per_hour: int = 30
    max_alerts_per_day: int = 200

    # Quiet hours (no alerts)
    quiet_hours_enabled: bool = False
    quiet_hours_start: int = 23  # Hour in UTC
    quiet_hours_end: int = 7

    # Channels
    telegram_enabled: bool = True
    email_enabled: bool = False

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_notification_enabled(self, notification_type: NotificationType) -> bool:
        """Check if notification type is enabled."""
        checks = {
            NotificationType.PRICE_ALERT: self.price_alerts_enabled,
            NotificationType.TRADE_ALERT: self.trade_alerts_enabled,
            NotificationType.PERFORMANCE: self.performance_alerts_enabled,
            NotificationType.RISK_ALERT: self.risk_alerts_enabled,
            NotificationType.ALGORITHM: self.algorithm_alerts_enabled,
            NotificationType.FEE: self.fee_alerts_enabled,
            NotificationType.SYSTEM: self.system_alerts_enabled,
        }
        return checks.get(notification_type, False)

    def is_in_quiet_hours(self) -> bool:
        """Check if currently in quiet hours."""
        if not self.quiet_hours_enabled:
            return False

        current_hour = datetime.utcnow().hour

        if self.quiet_hours_start < self.quiet_hours_end:
            # Normal range (e.g., 23-7 wraps around midnight)
            return self.quiet_hours_start <= current_hour < self.quiet_hours_end
        else:
            # Wraps around midnight
            return current_hour >= self.quiet_hours_start or current_hour < self.quiet_hours_end


class NotificationService:
    """
    Manages notifications, delivery, and user preferences.

    Features:
    - Multi-type notifications
    - User preferences (enable/disable types)
    - Rate limiting (prevent spam)
    - Quiet hours (no notifications at night)
    - Batching (send multiple at once)
    - History tracking
    """

    def __init__(self):
        """Initialize notification service."""
        self.notifications: Dict[int, List[Notification]] = defaultdict(list)
        self.preferences: Dict[int, NotificationPreferences] = {}
        self.alert_counts: Dict[int, List[datetime]] = defaultdict(list)  # Track frequency

    # ==================== NOTIFICATION CREATION ====================

    async def send_notification(self, user_id: int, notification: Notification,
                               context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Send a notification to user.

        Args:
            user_id: User ID
            notification: Notification to send
            context: Telegram context

        Returns:
            True if sent successfully
        """
        try:
            # Get preferences
            prefs = self.get_preferences(user_id)

            # Check if notification type is enabled
            if not prefs.is_notification_enabled(notification.notification_type):
                logger.debug(f"Notification type {notification.notification_type.value} disabled for user {user_id}")
                return False

            # Check quiet hours
            if prefs.is_in_quiet_hours():
                logger.debug(f"User {user_id} in quiet hours, delaying notification")
                return False

            # Check rate limits
            allowed, reason = self._check_rate_limit(user_id, prefs)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}: {reason}")
                return False

            # Send via Telegram
            if prefs.telegram_enabled:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=notification.to_telegram_message(),
                        parse_mode=ParseMode.HTML,
                    )
                    notification.sent_at = datetime.utcnow()
                    logger.info(f"Notification sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification: {e}")
                    return False

            # Store in history
            self.notifications[user_id].append(notification)

            # Track alert count (for rate limiting)
            self.alert_counts[user_id].append(datetime.utcnow())

            return True

        except Exception as e:
            logger.error(f"Send notification failed: {e}")
            return False

    def _check_rate_limit(self, user_id: int, prefs: NotificationPreferences) -> tuple:
        """
        Check if user has exceeded rate limits.

        Returns:
            (allowed, reason)
        """
        try:
            now = datetime.utcnow()

            # Count alerts in last hour
            hour_ago = now - timedelta(hours=1)
            alerts_this_hour = len([ts for ts in self.alert_counts[user_id] if ts > hour_ago])

            if alerts_this_hour >= prefs.max_alerts_per_hour:
                return False, f"Max alerts per hour ({prefs.max_alerts_per_hour}) exceeded"

            # Count alerts today
            day_ago = now - timedelta(days=1)
            alerts_today = len([ts for ts in self.alert_counts[user_id] if ts > day_ago])

            if alerts_today >= prefs.max_alerts_per_day:
                return False, f"Max alerts today ({prefs.max_alerts_per_day}) exceeded"

            return True, "OK"

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, "Check failed, allowing"

    # ==================== SPECIFIC NOTIFICATIONS ====================

    async def notify_price_alert(self, user_id: int, symbol: str, current_price: float,
                                target_price: float, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send price alert."""
        notification = Notification(
            notification_id=f"price_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.MEDIUM,
            title=f"🎯 Price Alert: {symbol}",
            message=f"Reached target price ${target_price:.6f}",
            details={
                'Symbol': symbol,
                'Current': f"${current_price:.6f}",
                'Target': f"${target_price:.6f}",
            },
            action_buttons=[
                {'text': '📊 Analyze', 'callback_data': f'analyze_{symbol}'},
                {'text': '💰 Buy', 'callback_data': f'buy_{symbol}'},
            ]
        )
        return await self.send_notification(user_id, notification, context)

    async def notify_trade_executed(self, user_id: int, symbol: str, action: str,
                                   amount_usd: float, price: float,
                                   context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send trade execution alert."""
        emoji = "✅" if action == "BUY" else "📤"
        notification = Notification(
            notification_id=f"trade_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.TRADE_ALERT,
            priority=NotificationPriority.HIGH,
            title=f"{emoji} Trade Executed: {action} {symbol}",
            message=f"Position opened at ${price:.6f}",
            details={
                'Symbol': symbol,
                'Action': action,
                'Amount': f"${amount_usd:.2f}",
                'Price': f"${price:.6f}",
            },
        )
        return await self.send_notification(user_id, notification, context)

    async def notify_milestone(self, user_id: int, milestone: str, value: float,
                              context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send performance milestone alert."""
        notification = Notification(
            notification_id=f"milestone_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.PERFORMANCE,
            priority=NotificationPriority.HIGH,
            title=f"🏆 {milestone}",
            message=f"Congratulations! You've reached {value:.2f}",
            details={
                'Milestone': milestone,
                'Value': f"{value:.2f}",
            },
        )
        return await self.send_notification(user_id, notification, context)

    async def notify_risk_alert(self, user_id: int, risk_type: str, current_value: float,
                               threshold: float, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send risk alert."""
        notification = Notification(
            notification_id=f"risk_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.RISK_ALERT,
            priority=NotificationPriority.CRITICAL,
            title=f"⚠️ Risk Alert: {risk_type}",
            message=f"Current value: {current_value:.2f}, Threshold: {threshold:.2f}",
            details={
                'Risk Type': risk_type,
                'Current': f"{current_value:.2f}",
                'Threshold': f"{threshold:.2f}",
                'Percent': f"{(current_value / threshold * 100):.1f}%",
            },
        )
        return await self.send_notification(user_id, notification, context)

    async def notify_high_confidence_signal(self, user_id: int, symbol: str,
                                           action: str, confidence: float,
                                           reason: str,
                                           context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send algorithm signal notification."""
        confidence_emoji = "🟢" if confidence > 80 else "🟡" if confidence > 60 else "🔴"
        notification = Notification(
            notification_id=f"signal_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.ALGORITHM,
            priority=NotificationPriority.HIGH,
            title=f"{confidence_emoji} {action} Signal: {symbol}",
            message=reason,
            details={
                'Symbol': symbol,
                'Action': action,
                'Confidence': f"{confidence:.0f}%",
            },
            action_buttons=[
                {'text': f'💰 {action}', 'callback_data': f'{action.lower()}_{symbol}'},
                {'text': '📊 Analyze', 'callback_data': f'analyze_{symbol}'},
            ]
        )
        return await self.send_notification(user_id, notification, context)

    async def notify_fees_earned(self, user_id: int, amount: float, symbol: str,
                                context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Send fee earned notification."""
        notification = Notification(
            notification_id=f"fee_{user_id}_{datetime.utcnow().timestamp():.0f}",
            user_id=user_id,
            notification_type=NotificationType.FEE,
            priority=NotificationPriority.MEDIUM,
            title=f"💰 Fees Earned",
            message=f"You earned ${amount:.4f} from your {symbol} trade",
            details={
                'Amount': f"${amount:.4f}",
                'Symbol': symbol,
                'Type': 'Success Fee (75%)',
            },
            action_buttons=[
                {'text': '👤 Claim', 'callback_data': 'claim_fees'},
                {'text': '💵 Reinvest', 'callback_data': 'reinvest_fees'},
            ]
        )
        return await self.send_notification(user_id, notification, context)

    # ==================== PREFERENCE MANAGEMENT ====================

    def get_preferences(self, user_id: int) -> NotificationPreferences:
        """Get user notification preferences."""
        if user_id not in self.preferences:
            self.preferences[user_id] = NotificationPreferences(user_id=user_id)
        return self.preferences[user_id]

    def update_preferences(self, user_id: int, **kwargs) -> bool:
        """Update notification preferences."""
        try:
            prefs = self.get_preferences(user_id)

            # Update only valid fields
            valid_fields = {
                'price_alerts_enabled', 'trade_alerts_enabled',
                'performance_alerts_enabled', 'risk_alerts_enabled',
                'algorithm_alerts_enabled', 'fee_alerts_enabled',
                'system_alerts_enabled',
                'max_alerts_per_hour', 'max_alerts_per_day',
                'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
                'telegram_enabled', 'email_enabled',
            }

            for key, value in kwargs.items():
                if key in valid_fields and hasattr(prefs, key):
                    setattr(prefs, key, value)

            prefs.updated_at = datetime.utcnow()
            logger.info(f"Updated preferences for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Preference update failed: {e}")
            return False

    # ==================== NOTIFICATION HISTORY ====================

    def get_notifications(self, user_id: int, limit: int = 20) -> List[Notification]:
        """Get recent notifications for user."""
        return self.notifications[user_id][-limit:]

    def mark_as_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        try:
            for user_notifications in self.notifications.values():
                for notification in user_notifications:
                    if notification.notification_id == notification_id:
                        notification.read_at = datetime.utcnow()
                        return True
            return False
        except Exception as e:
            logger.error(f"Mark as read failed: {e}")
            return False

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self.notifications[user_id] if not n.is_read)

    def clear_notifications(self, user_id: int) -> bool:
        """Clear notification history."""
        try:
            self.notifications[user_id] = []
            self.alert_counts[user_id] = []
            return True
        except Exception as e:
            logger.error(f"Clear notifications failed: {e}")
            return False
