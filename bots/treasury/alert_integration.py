"""
Position Alert Integration

Connects position monitoring alerts to Telegram notifications and core alert engine.
"""

import logging
from typing import Optional, List
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .position_alerts import PositionMonitor, PositionAlert, AlertThreshold

# Import core alert engine if available
try:
    from core.alerts.alert_engine import AlertEngine, AlertType, AlertPriority
    CORE_ALERTS_AVAILABLE = True
except ImportError:
    CORE_ALERTS_AVAILABLE = False
    AlertEngine = None

# Import Telegram alert system if available
try:
    from tg_bot.services.alert_system import AlertSystem as TelegramAlertSystem
    TELEGRAM_ALERTS_AVAILABLE = True
except ImportError:
    TELEGRAM_ALERTS_AVAILABLE = False
    TelegramAlertSystem = None

logger = logging.getLogger(__name__)


class AlertIntegration:
    """
    Integrates position monitoring with notification systems.

    Supports:
    - Direct Telegram messages
    - Core alert engine
    - Telegram alert system
    """

    def __init__(
        self,
        position_monitor: PositionMonitor,
        admin_ids: List[int],
        telegram_context: Optional[ContextTypes.DEFAULT_TYPE] = None,
        core_alert_engine: Optional[AlertEngine] = None,
        telegram_alert_system: Optional[TelegramAlertSystem] = None
    ):
        """
        Initialize alert integration.

        Args:
            position_monitor: PositionMonitor instance
            admin_ids: List of Telegram admin user IDs
            telegram_context: Telegram bot context for sending messages
            core_alert_engine: Core AlertEngine instance (optional)
            telegram_alert_system: Telegram AlertSystem instance (optional)
        """
        self.monitor = position_monitor
        self.admin_ids = admin_ids
        self.telegram_context = telegram_context
        self.core_alert_engine = core_alert_engine
        self.telegram_alert_system = telegram_alert_system

        # Register as alert handler
        self.monitor.register_alert_handler(self.handle_alert)

        logger.info("Alert integration initialized")

    async def handle_alert(self, alert: PositionAlert):
        """
        Handle a position alert by sending to all configured channels.

        Args:
            alert: PositionAlert to deliver
        """
        # Send to Telegram
        await self._send_telegram_alert(alert)

        # Send to core alert engine
        if CORE_ALERTS_AVAILABLE and self.core_alert_engine:
            await self._send_core_alert(alert)

        # Send to Telegram alert system
        if TELEGRAM_ALERTS_AVAILABLE and self.telegram_alert_system and self.telegram_context:
            await self._send_telegram_system_alert(alert)

    async def _send_telegram_alert(self, alert: PositionAlert):
        """Send alert directly via Telegram."""
        if not self.telegram_context:
            logger.debug("No Telegram context, skipping direct message")
            return

        message = alert.to_telegram_message()

        for admin_id in self.admin_ids:
            try:
                await self.telegram_context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                logger.debug(f"Sent Telegram alert to {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send Telegram alert to {admin_id}: {e}")

    async def _send_core_alert(self, alert: PositionAlert):
        """Send alert through core alert engine."""
        if not self.core_alert_engine:
            return

        try:
            # Map position alert type to core alert type
            alert_type_map = {
                "profit_threshold": AlertType.STRATEGY_SIGNAL,
                "loss_threshold": AlertType.STRATEGY_SIGNAL,
                "stop_loss_triggered": AlertType.SYSTEM,
                "take_profit_reached": AlertType.STRATEGY_SIGNAL,
                "stop_loss_near": AlertType.SYSTEM,
                "take_profit_near": AlertType.SYSTEM,
                "size_change": AlertType.WHALE_ACTIVITY,
                "volume_spike": AlertType.VOLUME_SPIKE,
                "stale_position": AlertType.SYSTEM,
                "rapid_loss": AlertType.SYSTEM
            }

            # Map severity to priority
            priority_map = {
                "ℹ️": AlertPriority.LOW,
                "✅": AlertPriority.MEDIUM,
                "⚠️": AlertPriority.HIGH,
                "🚨": AlertPriority.CRITICAL
            }

            core_alert_type = alert_type_map.get(
                alert.alert_type.value,
                AlertType.SYSTEM
            )
            priority = priority_map.get(
                alert.severity.value,
                AlertPriority.MEDIUM
            )

            await self.core_alert_engine.create_alert(
                alert_type=core_alert_type,
                title=alert.title,
                message=alert.message,
                priority=priority,
                data=alert.data,
                token=alert.token_symbol
            )

            logger.debug(f"Sent alert to core alert engine: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send core alert: {e}")

    async def _send_telegram_system_alert(self, alert: PositionAlert):
        """Send alert through Telegram alert system."""
        if not self.telegram_alert_system or not self.telegram_context:
            return

        try:
            # Import Alert and AlertLevel from telegram alert system
            from tg_bot.services.alert_system import Alert as TgAlert, AlertLevel, AlertType as TgAlertType

            # Map severity to alert level
            level_map = {
                "ℹ️": AlertLevel.INFO,
                "✅": AlertLevel.SUCCESS,
                "⚠️": AlertLevel.WARNING,
                "🚨": AlertLevel.CRITICAL
            }

            # Map alert type
            type_map = {
                "profit_threshold": TgAlertType.PROFIT_ALERT,
                "loss_threshold": TgAlertType.PROFIT_ALERT,
                "stop_loss_triggered": TgAlertType.STOP_LOSS_ALERT,
                "take_profit_reached": TgAlertType.PROFIT_ALERT,
                "stop_loss_near": TgAlertType.STOP_LOSS_ALERT,
                "take_profit_near": TgAlertType.PROFIT_ALERT,
                "volume_spike": TgAlertType.VOLATILITY_ALERT,
                "stale_position": TgAlertType.CUSTOM,
                "rapid_loss": TgAlertType.RISK_THRESHOLD
            }

            tg_alert = TgAlert(
                type=type_map.get(alert.alert_type.value, TgAlertType.CUSTOM),
                level=level_map.get(alert.severity.value, AlertLevel.INFO),
                title=alert.title,
                message=alert.message,
                symbol=alert.token_symbol,
                data=alert.data
            )

            await self.telegram_alert_system.send_alert(tg_alert, self.telegram_context)

            logger.debug(f"Sent alert to Telegram alert system: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send Telegram system alert: {e}")

    def set_telegram_context(self, context: ContextTypes.DEFAULT_TYPE):
        """Update Telegram context for alert delivery."""
        self.telegram_context = context
        logger.info("Telegram context updated")

    def update_admin_ids(self, admin_ids: List[int]):
        """Update admin IDs for notifications."""
        self.admin_ids = admin_ids
        logger.info(f"Admin IDs updated: {len(admin_ids)} admins")


def setup_position_alerts(
    trading_engine,
    admin_ids: List[int],
    telegram_context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    custom_thresholds: Optional[AlertThreshold] = None
) -> tuple[PositionMonitor, AlertIntegration]:
    """
    Quick setup for position monitoring with alerts.

    Args:
        trading_engine: TradingEngine instance
        admin_ids: List of admin Telegram user IDs
        telegram_context: Telegram bot context (optional)
        custom_thresholds: Custom alert thresholds (optional)

    Returns:
        Tuple of (PositionMonitor, AlertIntegration)
    """
    # Create monitor
    monitor = PositionMonitor(
        trading_engine=trading_engine,
        thresholds=custom_thresholds
    )

    # Try to get core alert engine
    core_engine = None
    if CORE_ALERTS_AVAILABLE:
        try:
            from core.alerts.alert_engine import get_alert_engine
            core_engine = get_alert_engine()
            logger.info("Connected to core alert engine")
        except Exception as e:
            logger.warning(f"Could not connect to core alert engine: {e}")

    # Create integration
    integration = AlertIntegration(
        position_monitor=monitor,
        admin_ids=admin_ids,
        telegram_context=telegram_context,
        core_alert_engine=core_engine
    )

    logger.info("Position alert system configured")

    return monitor, integration
