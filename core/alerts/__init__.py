"""
JARVIS Alert System

Real-time alerts for price thresholds, whale activity, sentiment shifts,
volume spikes, and strategy signals.

Features:
- Price threshold alerts (above/below)
- Percentage change alerts (up/down)
- Volume spike alerts
- Alert persistence (survives restarts)
- Telegram integration
- Multi-channel delivery
"""

from .alert_engine import (
    AlertEngine,
    Alert,
    AlertType,
    AlertPriority,
    AlertSubscription,
    get_alert_engine,
)
from .delivery import (
    AlertDeliveryManager,
    AlertMessage,
    DeliveryBot,
    DeliveryChannel,
    DeliveryConfig,
    DeliveryResult,
    DeliveryStatus,
    DiscordBot,
    TelegramBot,
    WebhookBot,
    EmailBot,
    PushBot,
    get_delivery_manager,
)
from .price_monitor import (
    PriceAlertMonitor,
    PriceBaseline,
    get_price_monitor,
)

__all__ = [
    # Engine
    "AlertEngine",
    "Alert",
    "AlertType",
    "AlertPriority",
    "AlertSubscription",
    "get_alert_engine",
    # Delivery
    "AlertDeliveryManager",
    "AlertMessage",
    "DeliveryBot",
    "DeliveryChannel",
    "DeliveryConfig",
    "DeliveryResult",
    "DeliveryStatus",
    "DiscordBot",
    "TelegramBot",
    "WebhookBot",
    "EmailBot",
    "PushBot",
    "get_delivery_manager",
    # Monitoring
    "PriceAlertMonitor",
    "PriceBaseline",
    "get_price_monitor",
]
