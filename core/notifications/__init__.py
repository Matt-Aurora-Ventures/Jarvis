"""
Notifications module for Jarvis.

Provides cross-platform notifications for:
- Git push events (Telegram, X)
- System alerts
- Trading signals
- Sentiment updates
- Multi-channel routing with rate limiting and delivery tracking
"""

from .git_notify import (
    GitCommitInfo,
    GitNotifier,
    get_notifier,
    notify_push,
    notify_push_sync,
)

from .router import (
    ChannelConfig,
    ChannelResult,
    ChannelType,
    CircuitBreakerState,
    DeliveryRecord,
    DeliveryStatus,
    NonRetryableError,
    Notification,
    NotificationPriority,
    NotificationRouter,
    NotificationType,
    RouteResult,
    RoutingRule,
    get_notification_router,
)

__all__ = [
    # Git notifications
    "GitCommitInfo",
    "GitNotifier",
    "get_notifier",
    "notify_push",
    "notify_push_sync",
    # Router
    "ChannelConfig",
    "ChannelResult",
    "ChannelType",
    "CircuitBreakerState",
    "DeliveryRecord",
    "DeliveryStatus",
    "NonRetryableError",
    "Notification",
    "NotificationPriority",
    "NotificationRouter",
    "NotificationType",
    "RouteResult",
    "RoutingRule",
    "get_notification_router",
]
