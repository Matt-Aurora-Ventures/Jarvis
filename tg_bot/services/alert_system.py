"""
Real-Time Alert System for Telegram Treasury Bot

Features:
- Price alerts (above/below threshold)
- Position P&L alerts (profit target, stop loss)
- Trade execution alerts
- Risk threshold alerts
- Market volatility alerts
- Sentiment shift alerts
- Liquidation alerts
- Custom webhook alerts
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "ℹ️"
    SUCCESS = "✅"
    WARNING = "⚠️"
    CRITICAL = "🚨"


class AlertType(Enum):
    """Types of alerts."""
    PRICE_ALERT = "price"
    PROFIT_ALERT = "profit"
    STOP_LOSS_ALERT = "stoploss"
    TRADE_EXECUTED = "trade_executed"
    POSITION_CLOSED = "position_closed"
    RISK_THRESHOLD = "risk_threshold"
    VOLATILITY_ALERT = "volatility"
    SENTIMENT_ALERT = "sentiment"
    LIQUIDATION_ALERT = "liquidation"
    CUSTOM = "custom"


@dataclass
class Alert:
    """Alert message definition."""
    type: AlertType
    level: AlertLevel
    title: str
    message: str
    symbol: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    requires_action: bool = False
    action_buttons: List[Dict[str, str]] = field(default_factory=list)

    def to_telegram_message(self) -> str:
        """Format as Telegram message."""
        lines = [
            f"{self.level.value} <b>{self.title}</b>",
            self.message,
        ]

        if self.symbol:
            lines.append(f"\n<b>Symbol:</b> <code>{self.symbol}</code>")

        for key, value in self.data.items():
            lines.append(f"<b>{key}:</b> <code>{value}</code>")

        lines.append(f"\n<i>{self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</i>")

        return "\n".join(lines)


class AlertSystem:
    """
    Real-time alert system for Treasury Bot.

    Monitors:
    - Price movements
    - Position P&L
    - Risk metrics
    - Market conditions
    - Custom triggers
    """

    # Alert cooldown (prevent spam)
    ALERT_COOLDOWN_SECONDS = 60

    def __init__(self, trader_instance):
        """Initialize alert system."""
        self.trader = trader_instance
        self.admin_ids: List[int] = []

        # Alert subscriptions
        self._alert_subscriptions: Dict[AlertType, List[int]] = {}
        self._recent_alerts: Dict[str, datetime] = {}  # key -> last alert time

        # Alert thresholds
        self.price_alert_threshold = 0.05  # 5%
        self.pnl_alert_threshold = 10  # $10
        self.risk_threshold_pct = 20  # 20% drawdown

        # Background monitoring
        self._monitoring = False

    def set_admin_ids(self, admin_ids: List[int]):
        """Set admin IDs for alerts."""
        self.admin_ids = admin_ids

    def subscribe_to_alert(self, alert_type: AlertType, user_id: int):
        """Subscribe user to alert type."""
        if alert_type not in self._alert_subscriptions:
            self._alert_subscriptions[alert_type] = []

        if user_id not in self._alert_subscriptions[alert_type]:
            self._alert_subscriptions[alert_type].append(user_id)
            logger.info(f"User {user_id} subscribed to {alert_type.value}")

    def unsubscribe_from_alert(self, alert_type: AlertType, user_id: int):
        """Unsubscribe user from alert type."""
        if alert_type in self._alert_subscriptions:
            self._alert_subscriptions[alert_type] = [
                uid for uid in self._alert_subscriptions[alert_type]
                if uid != user_id
            ]

    # ==================== ALERT TRIGGERS ====================

    async def send_alert(
        self,
        alert: Alert,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Send alert to subscribed users."""
        # Check cooldown
        alert_key = f"{alert.type.value}:{alert.symbol or 'global'}"
        if self._is_on_cooldown(alert_key):
            logger.debug(f"Alert {alert_key} on cooldown, skipping")
            return

        # Get recipients
        recipients = self._get_recipients(alert.type)

        if not recipients:
            logger.debug(f"No recipients for {alert.type.value}")
            return

        # Send to all recipients
        message = alert.to_telegram_message()

        for user_id in recipients:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.warning(f"Failed to send alert to {user_id}: {e}")

        self._recent_alerts[alert_key] = datetime.utcnow()

    def _is_on_cooldown(self, alert_key: str) -> bool:
        """Check if alert is on cooldown."""
        if alert_key not in self._recent_alerts:
            return False

        time_since_last = datetime.utcnow() - self._recent_alerts[alert_key]
        return time_since_last.total_seconds() < self.ALERT_COOLDOWN_SECONDS

    def _get_recipients(self, alert_type: AlertType) -> Set[int]:
        """Get user IDs subscribed to alert type."""
        subscribers = set(self._alert_subscriptions.get(alert_type, []))
        return subscribers | set(self.admin_ids)  # Always alert admins

    # ==================== SPECIFIC ALERTS ====================

    async def check_price_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitor positions for price alerts."""
        try:
            positions = self.trader.get_open_positions()

            for pos in positions:
                # Price movement
                price_change = abs(pos.current_price - pos.entry_price) / pos.entry_price

                if price_change >= self.price_alert_threshold:
                    direction = "📈 UP" if pos.current_price > pos.entry_price else "📉 DOWN"

                    alert = Alert(
                        type=AlertType.PRICE_ALERT,
                        level=AlertLevel.WARNING if price_change >= 0.1 else AlertLevel.INFO,
                        title=f"Price Alert: {pos.token_symbol}",
                        message=f"{direction} {price_change:.1%} since entry",
                        symbol=pos.token_symbol,
                        data={
                            'Entry': f"${pos.entry_price:.6f}",
                            'Current': f"${pos.current_price:.6f}",
                            'Change': f"{price_change:+.2%}",
                        }
                    )

                    await self.send_alert(alert, context)

        except Exception as e:
            logger.error(f"Price alert check failed: {e}")

    async def check_profit_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitor positions for significant P&L changes."""
        try:
            positions = self.trader.get_open_positions()

            for pos in positions:
                # Major profit milestone
                if pos.unrealized_pnl_usd >= self.pnl_alert_threshold and pos.unrealized_pnl_pct >= 5:
                    alert = Alert(
                        type=AlertType.PROFIT_ALERT,
                        level=AlertLevel.SUCCESS,
                        title=f"🎯 Profit Target Reached: {pos.token_symbol}",
                        message=f"Position is now profitable with significant gains",
                        symbol=pos.token_symbol,
                        data={
                            'P&L': f"${pos.unrealized_pnl_usd:+,.2f}",
                            'Return': f"{pos.unrealized_pnl_pct:+.2f}%",
                            'Duration': self._format_duration(datetime.utcnow() - pos.entry_time),
                        },
                        requires_action=True,
                    )

                    await self.send_alert(alert, context)

        except Exception as e:
            logger.error(f"Profit alert check failed: {e}")

    async def check_stop_loss_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitor for stop loss triggers."""
        try:
            positions = self.trader.get_open_positions()

            for pos in positions:
                if pos.stop_loss_price and pos.current_price <= pos.stop_loss_price:
                    alert = Alert(
                        type=AlertType.STOP_LOSS_ALERT,
                        level=AlertLevel.CRITICAL,
                        title=f"🛑 Stop Loss Triggered: {pos.token_symbol}",
                        message=f"Position has hit stop loss threshold",
                        symbol=pos.token_symbol,
                        data={
                            'Entry': f"${pos.entry_price:.6f}",
                            'Stop Loss': f"${pos.stop_loss_price:.6f}",
                            'Current': f"${pos.current_price:.6f}",
                            'Loss': f"${pos.unrealized_pnl_usd:+,.2f}",
                        },
                        requires_action=True,
                    )

                    await self.send_alert(alert, context)

        except Exception as e:
            logger.error(f"Stop loss alert check failed: {e}")

    async def check_risk_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitor overall portfolio risk."""
        try:
            # Get portfolio metrics
            positions = self.trader.get_open_positions()
            total_value = sum(p.current_value_usd for p in positions) if positions else 0
            total_pnl = sum(p.unrealized_pnl_usd for p in positions) if positions else 0

            # Compute max drawdown from open positions (worst losing position %)
            if not positions:
                return
            drawdowns = [
                abs(p.unrealized_pnl_pct)
                for p in positions
                if hasattr(p, "unrealized_pnl_pct") and (p.unrealized_pnl_pct or 0) < 0
            ]
            max_drawdown = max(drawdowns) if drawdowns else 0.0

            if max_drawdown >= self.risk_threshold_pct:
                alert = Alert(
                    type=AlertType.RISK_THRESHOLD,
                    level=AlertLevel.CRITICAL,
                    title="⚠️ Risk Threshold Exceeded",
                    message=f"Portfolio drawdown has exceeded {self.risk_threshold_pct}% threshold",
                    data={
                        'Max Drawdown': f"{max_drawdown:.1f}%",
                        'Threshold': f"{self.risk_threshold_pct}%",
                        'Total Value': f"${total_value:,.2f}",
                        'Total P&L': f"${total_pnl:+,.2f}",
                    },
                    requires_action=True,
                )

                await self.send_alert(alert, context)

        except Exception as e:
            logger.error(f"Risk alert check failed: {e}")

    async def check_volatility_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Monitor for high market volatility based on BTC 24h price change."""
        try:
            # Attempt to get BTC 24h change as a volatility proxy
            try:
                from tg_bot.services.market_intelligence import _price_cache
                btc_data = _price_cache[1].get("bitcoin", {}) if _price_cache[1] else {}
                btc_24h = abs(btc_data.get("usd_24h_change", 0) or 0)
                # Map 24h abs% change to a 0-100 volatility scale
                # >10% abs move → ~80 vol; <3% abs move → ~25 vol
                market_volatility = min(100.0, btc_24h * 7.0)
            except Exception:
                return  # No live data — skip alert rather than spam

            if market_volatility > 40:
                alert = Alert(
                    type=AlertType.VOLATILITY_ALERT,
                    level=AlertLevel.WARNING,
                    title="⚡ High Market Volatility",
                    message=f"Market volatility is elevated. Exercise caution on new positions.",
                    data={
                        'Volatility': f"{market_volatility:.1f}%",
                        'Status': 'HIGH' if market_volatility > 40 else 'NORMAL',
                    }
                )

                await self.send_alert(alert, context)

        except Exception as e:
            logger.error(f"Volatility alert check failed: {e}")

    async def send_trade_executed_alert(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        size: float,
        value_usd: float,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    ):
        """Send alert when trade is executed."""
        alert = Alert(
            type=AlertType.TRADE_EXECUTED,
            level=AlertLevel.SUCCESS,
            title=f"Trade Executed: {direction} {symbol}",
            message=f"New position opened",
            symbol=symbol,
            data={
                'Direction': direction,
                'Entry Price': f"${entry_price:.6f}",
                'Size': f"{size:.2f} tokens",
                'Value': f"${value_usd:,.2f}",
            }
        )

        if context:
            await self.send_alert(alert, context)
        else:
            logger.info(f"Trade executed: {symbol} @ ${entry_price}")

    async def send_position_closed_alert(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        duration: timedelta,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    ):
        """Send alert when position is closed."""
        emoji = "💰" if pnl >= 0 else "💸"
        level = AlertLevel.SUCCESS if pnl >= 0 else AlertLevel.WARNING

        alert = Alert(
            type=AlertType.POSITION_CLOSED,
            level=level,
            title=f"{emoji} Position Closed: {symbol}",
            message=f"Trade result: ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
            symbol=symbol,
            data={
                'Entry': f"${entry_price:.6f}",
                'Exit': f"${exit_price:.6f}",
                'P&L': f"${pnl:+,.2f}",
                'Return': f"{pnl_pct:+.2f}%",
                'Duration': self._format_duration(duration),
            }
        )

        if context:
            await self.send_alert(alert, context)
        else:
            logger.info(f"Position closed: {symbol} @ ${exit_price}")

    # ==================== BACKGROUND MONITORING ====================

    async def start_monitoring(self, context: ContextTypes.DEFAULT_TYPE):
        """Start background alert monitoring."""
        self._monitoring = True
        logger.info("Alert system monitoring started")

        while self._monitoring:
            try:
                # Check all alert types
                await asyncio.gather(
                    self.check_price_alerts(context),
                    self.check_profit_alerts(context),
                    self.check_stop_loss_alerts(context),
                    self.check_risk_alerts(context),
                    self.check_volatility_alerts(context),
                )

                # Check every 10 seconds
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Alert monitoring error: {e}")
                await asyncio.sleep(10)

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        logger.info("Alert system monitoring stopped")

    # ==================== HELPER METHODS ====================

    def _format_duration(self, duration: timedelta) -> str:
        """Format duration nicely."""
        total_seconds = int(duration.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
