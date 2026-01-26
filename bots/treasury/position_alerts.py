"""
Position Monitoring Alert System

Real-time monitoring of trading positions with intelligent alerting.

Features:
- P&L threshold alerts (+20%, -10%, etc.)
- Stop loss triggered notifications
- Take profit reached alerts
- Position size change detection
- Unusual trading volume alerts
- Configurable thresholds per position
- Integration with Telegram and core alert engine
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PositionAlertType(Enum):
    """Types of position alerts."""
    PROFIT_THRESHOLD = "profit_threshold"  # Hit +20%, +50%, etc.
    LOSS_THRESHOLD = "loss_threshold"      # Hit -10%, -20%, etc.
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_REACHED = "take_profit_reached"
    STOP_LOSS_NEAR = "stop_loss_near"      # Within 5% of SL
    TAKE_PROFIT_NEAR = "take_profit_near"  # Within 5% of TP
    SIZE_CHANGE = "size_change"            # Position size changed significantly
    VOLUME_SPIKE = "volume_spike"          # Unusual trading volume
    STALE_POSITION = "stale_position"      # Position open too long
    RAPID_LOSS = "rapid_loss"              # Quick drawdown


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "ℹ️"
    SUCCESS = "✅"
    WARNING = "⚠️"
    CRITICAL = "🚨"


@dataclass
class AlertThreshold:
    """Configurable alert thresholds."""
    # Profit thresholds (percentages)
    profit_levels: List[float] = field(default_factory=lambda: [5.0, 10.0, 20.0, 50.0, 100.0])

    # Loss thresholds (percentages, positive values)
    loss_levels: List[float] = field(default_factory=lambda: [5.0, 10.0, 20.0, 30.0])

    # Proximity to TP/SL (percentage)
    tp_proximity_pct: float = 5.0  # Alert when within 5% of TP
    sl_proximity_pct: float = 5.0  # Alert when within 5% of SL

    # Volume monitoring
    volume_spike_multiplier: float = 3.0  # Alert when volume is 3x average

    # Position age
    stale_position_hours: float = 72.0  # Alert if position open > 72h with no action

    # Rapid loss detection
    rapid_loss_pct: float = 15.0  # Alert if position loses 15% in short time
    rapid_loss_window_minutes: float = 30.0


@dataclass
class PositionAlert:
    """A position alert instance."""
    alert_id: str
    position_id: str
    token_symbol: str
    alert_type: PositionAlertType
    severity: AlertSeverity
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_telegram_message(self) -> str:
        """Format alert for Telegram."""
        lines = [
            f"{self.severity.value} <b>{self.title}</b>",
            f"<b>Symbol:</b> <code>{self.token_symbol}</code>",
            "",
            self.message,
            ""
        ]

        # Add data fields
        for key, value in self.data.items():
            if isinstance(value, float):
                if 'pct' in key.lower() or '%' in str(value):
                    lines.append(f"<b>{key}:</b> <code>{value:+.2f}%</code>")
                elif '$' in str(value) or 'usd' in key.lower():
                    lines.append(f"<b>{key}:</b> <code>${value:+,.2f}</code>")
                else:
                    lines.append(f"<b>{key}:</b> <code>{value}</code>")
            else:
                lines.append(f"<b>{key}:</b> <code>{value}</code>")

        lines.append(f"\n<i>{self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</i>")

        return "\n".join(lines)


@dataclass
class PositionSnapshot:
    """Snapshot of position state for monitoring."""
    position_id: str
    token_symbol: str
    current_price: float
    entry_price: float
    unrealized_pnl_pct: float
    unrealized_pnl_usd: float
    position_value_usd: float
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    opened_at: datetime
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Tracking data
    highest_pnl_pct: float = 0.0  # Track peak for drawdown alerts
    lowest_pnl_pct: float = 0.0   # Track bottom for recovery alerts
    alerted_profit_levels: Set[float] = field(default_factory=set)
    alerted_loss_levels: Set[float] = field(default_factory=set)
    last_volume_alert: Optional[datetime] = None


class PositionMonitor:
    """
    Position monitoring system with real-time alerts.

    Monitors all open positions and triggers alerts based on configurable thresholds.
    Integrates with both Telegram notifications and core alert engine.
    """

    def __init__(
        self,
        trading_engine,
        thresholds: Optional[AlertThreshold] = None,
        alert_cooldown_seconds: int = 300  # 5 min cooldown per alert type
    ):
        """
        Initialize position monitor.

        Args:
            trading_engine: TradingEngine instance to monitor
            thresholds: Alert threshold configuration
            alert_cooldown_seconds: Cooldown between similar alerts
        """
        self.engine = trading_engine
        self.thresholds = thresholds or AlertThreshold()
        self.alert_cooldown = alert_cooldown_seconds

        # State tracking
        self.position_snapshots: Dict[str, PositionSnapshot] = {}
        self.recent_alerts: Dict[str, datetime] = {}  # alert_key -> timestamp
        self.alert_handlers: List[Callable] = []

        # Monitoring control
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Stats
        self.total_alerts_sent = 0
        self.alerts_by_type: Dict[PositionAlertType, int] = {}

    def register_alert_handler(self, handler: Callable):
        """
        Register a callback for alert delivery.

        Args:
            handler: Async function(alert: PositionAlert) -> None
        """
        self.alert_handlers.append(handler)
        logger.info(f"Registered alert handler: {handler.__name__}")

    async def _deliver_alert(self, alert: PositionAlert):
        """Send alert to all registered handlers."""
        # Check cooldown
        alert_key = f"{alert.position_id}:{alert.alert_type.value}"

        if self._is_on_cooldown(alert_key):
            logger.debug(f"Alert {alert_key} on cooldown, skipping")
            return

        # Deliver to all handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler {handler.__name__} failed: {e}")

        # Update tracking
        self.recent_alerts[alert_key] = datetime.utcnow()
        self.total_alerts_sent += 1
        self.alerts_by_type[alert.alert_type] = self.alerts_by_type.get(alert.alert_type, 0) + 1

        logger.info(f"Alert delivered: {alert.alert_type.value} for {alert.token_symbol}")

    def _is_on_cooldown(self, alert_key: str) -> bool:
        """Check if alert is on cooldown."""
        if alert_key not in self.recent_alerts:
            return False

        time_since = (datetime.utcnow() - self.recent_alerts[alert_key]).total_seconds()
        return time_since < self.alert_cooldown

    def _update_snapshot(self, position) -> PositionSnapshot:
        """Update or create position snapshot."""
        pos_id = position.id

        # Parse opened_at if it's a string
        opened_at = position.opened_at
        if isinstance(opened_at, str):
            try:
                opened_at = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse opened_at timestamp '{opened_at}': {e}")
                opened_at = datetime.utcnow()

        if pos_id in self.position_snapshots:
            snapshot = self.position_snapshots[pos_id]
            snapshot.current_price = position.current_price
            snapshot.unrealized_pnl_pct = position.unrealized_pnl_pct
            snapshot.unrealized_pnl_usd = position.unrealized_pnl
            snapshot.last_updated = datetime.utcnow()

            # Track peaks and valleys
            snapshot.highest_pnl_pct = max(snapshot.highest_pnl_pct, position.unrealized_pnl_pct)
            snapshot.lowest_pnl_pct = min(snapshot.lowest_pnl_pct, position.unrealized_pnl_pct)
        else:
            snapshot = PositionSnapshot(
                position_id=pos_id,
                token_symbol=position.token_symbol,
                current_price=position.current_price,
                entry_price=position.entry_price,
                unrealized_pnl_pct=position.unrealized_pnl_pct,
                unrealized_pnl_usd=position.unrealized_pnl,
                position_value_usd=position.amount_usd,
                stop_loss_price=position.stop_loss_price,
                take_profit_price=position.take_profit_price,
                opened_at=opened_at,
                highest_pnl_pct=position.unrealized_pnl_pct,
                lowest_pnl_pct=position.unrealized_pnl_pct
            )
            self.position_snapshots[pos_id] = snapshot

        return snapshot

    async def _check_profit_thresholds(self, position, snapshot: PositionSnapshot):
        """Check if position hit profit thresholds."""
        pnl_pct = position.unrealized_pnl_pct

        for level in self.thresholds.profit_levels:
            if pnl_pct >= level and level not in snapshot.alerted_profit_levels:
                snapshot.alerted_profit_levels.add(level)

                # Determine severity
                if level >= 50:
                    severity = AlertSeverity.SUCCESS
                elif level >= 20:
                    severity = AlertSeverity.SUCCESS
                else:
                    severity = AlertSeverity.INFO

                alert = PositionAlert(
                    alert_id=f"PROFIT-{position.id}-{level}",
                    position_id=position.id,
                    token_symbol=position.token_symbol,
                    alert_type=PositionAlertType.PROFIT_THRESHOLD,
                    severity=severity,
                    title=f"🎯 Profit Milestone: +{level:.0f}%",
                    message=f"Position has reached <b>+{level:.0f}%</b> profit!",
                    data={
                        "Entry Price": position.entry_price,
                        "Current Price": position.current_price,
                        "Unrealized P&L": position.unrealized_pnl,
                        "P&L %": pnl_pct,
                        "Take Profit": position.take_profit_price if position.take_profit_price else "Not Set"
                    }
                )

                await self._deliver_alert(alert)

    async def _check_loss_thresholds(self, position, snapshot: PositionSnapshot):
        """Check if position hit loss thresholds."""
        pnl_pct = position.unrealized_pnl_pct

        for level in self.thresholds.loss_levels:
            # Loss levels are stored as positive values, negate for comparison
            if pnl_pct <= -level and level not in snapshot.alerted_loss_levels:
                snapshot.alerted_loss_levels.add(level)

                # Determine severity
                if level >= 20:
                    severity = AlertSeverity.CRITICAL
                elif level >= 10:
                    severity = AlertSeverity.WARNING
                else:
                    severity = AlertSeverity.INFO

                alert = PositionAlert(
                    alert_id=f"LOSS-{position.id}-{level}",
                    position_id=position.id,
                    token_symbol=position.token_symbol,
                    alert_type=PositionAlertType.LOSS_THRESHOLD,
                    severity=severity,
                    title=f"📉 Loss Alert: -{level:.0f}%",
                    message=f"Position has lost <b>{level:.0f}%</b> of value.",
                    data={
                        "Entry Price": position.entry_price,
                        "Current Price": position.current_price,
                        "Unrealized P&L": position.unrealized_pnl,
                        "P&L %": pnl_pct,
                        "Stop Loss": position.stop_loss_price if position.stop_loss_price else "Not Set"
                    }
                )

                await self._deliver_alert(alert)

    async def _check_tp_sl_proximity(self, position, snapshot: PositionSnapshot):
        """Check if position is near TP or SL."""
        current_price = position.current_price

        # Check proximity to take profit
        if position.take_profit_price:
            distance_pct = abs((position.take_profit_price - current_price) / current_price) * 100

            if distance_pct <= self.thresholds.tp_proximity_pct:
                alert = PositionAlert(
                    alert_id=f"TP-NEAR-{position.id}",
                    position_id=position.id,
                    token_symbol=position.token_symbol,
                    alert_type=PositionAlertType.TAKE_PROFIT_NEAR,
                    severity=AlertSeverity.INFO,
                    title=f"🎯 Near Take Profit",
                    message=f"Position is within <b>{distance_pct:.1f}%</b> of take profit target.",
                    data={
                        "Current Price": current_price,
                        "Take Profit": position.take_profit_price,
                        "Distance": f"{distance_pct:.2f}%",
                        "P&L %": position.unrealized_pnl_pct
                    }
                )

                await self._deliver_alert(alert)

        # Check proximity to stop loss
        if position.stop_loss_price:
            distance_pct = abs((current_price - position.stop_loss_price) / current_price) * 100

            if distance_pct <= self.thresholds.sl_proximity_pct:
                alert = PositionAlert(
                    alert_id=f"SL-NEAR-{position.id}",
                    position_id=position.id,
                    token_symbol=position.token_symbol,
                    alert_type=PositionAlertType.STOP_LOSS_NEAR,
                    severity=AlertSeverity.WARNING,
                    title=f"⚠️ Near Stop Loss",
                    message=f"Position is within <b>{distance_pct:.1f}%</b> of stop loss!",
                    data={
                        "Current Price": current_price,
                        "Stop Loss": position.stop_loss_price,
                        "Distance": f"{distance_pct:.2f}%",
                        "P&L %": position.unrealized_pnl_pct
                    }
                )

                await self._deliver_alert(alert)

    async def _check_tp_sl_triggered(self, position, snapshot: PositionSnapshot):
        """Check if TP or SL was actually triggered."""
        current_price = position.current_price

        # Check if take profit hit
        if position.take_profit_price and current_price >= position.take_profit_price:
            alert = PositionAlert(
                alert_id=f"TP-HIT-{position.id}",
                position_id=position.id,
                token_symbol=position.token_symbol,
                alert_type=PositionAlertType.TAKE_PROFIT_REACHED,
                severity=AlertSeverity.SUCCESS,
                title=f"✅ Take Profit Hit!",
                message=f"Position reached take profit target at <b>${position.take_profit_price:.6f}</b>",
                data={
                    "Entry Price": position.entry_price,
                    "Target Price": position.take_profit_price,
                    "Current Price": current_price,
                    "Profit": position.unrealized_pnl,
                    "Profit %": position.unrealized_pnl_pct
                }
            )

            await self._deliver_alert(alert)

        # Check if stop loss hit
        if position.stop_loss_price and current_price <= position.stop_loss_price:
            alert = PositionAlert(
                alert_id=f"SL-HIT-{position.id}",
                position_id=position.id,
                token_symbol=position.token_symbol,
                alert_type=PositionAlertType.STOP_LOSS_TRIGGERED,
                severity=AlertSeverity.CRITICAL,
                title=f"🛑 Stop Loss Triggered!",
                message=f"Position hit stop loss at <b>${position.stop_loss_price:.6f}</b>",
                data={
                    "Entry Price": position.entry_price,
                    "Stop Loss": position.stop_loss_price,
                    "Current Price": current_price,
                    "Loss": position.unrealized_pnl,
                    "Loss %": position.unrealized_pnl_pct
                }
            )

            await self._deliver_alert(alert)

    async def _check_stale_position(self, position, snapshot: PositionSnapshot):
        """Check if position is stale (open too long)."""
        time_open = (datetime.utcnow() - snapshot.opened_at).total_seconds() / 3600

        if time_open >= self.thresholds.stale_position_hours:
            alert = PositionAlert(
                alert_id=f"STALE-{position.id}",
                position_id=position.id,
                token_symbol=position.token_symbol,
                alert_type=PositionAlertType.STALE_POSITION,
                severity=AlertSeverity.WARNING,
                title=f"⏰ Stale Position",
                message=f"Position has been open for <b>{time_open:.1f} hours</b> with no action.",
                data={
                    "Opened At": snapshot.opened_at.strftime("%Y-%m-%d %H:%M"),
                    "Hours Open": f"{time_open:.1f}",
                    "Current P&L": position.unrealized_pnl,
                    "P&L %": position.unrealized_pnl_pct
                }
            )

            await self._deliver_alert(alert)

    async def _check_rapid_loss(self, position, snapshot: PositionSnapshot):
        """Check for rapid loss events."""
        # Check if position lost significantly in short window
        current_pnl = position.unrealized_pnl_pct
        time_since_update = (datetime.utcnow() - snapshot.last_updated).total_seconds() / 60

        # If we've dropped from peak rapidly
        drawdown_from_peak = snapshot.highest_pnl_pct - current_pnl

        if (drawdown_from_peak >= self.thresholds.rapid_loss_pct and
            time_since_update <= self.thresholds.rapid_loss_window_minutes):

            alert = PositionAlert(
                alert_id=f"RAPID-LOSS-{position.id}",
                position_id=position.id,
                token_symbol=position.token_symbol,
                alert_type=PositionAlertType.RAPID_LOSS,
                severity=AlertSeverity.CRITICAL,
                title=f"⚡ Rapid Loss Detected",
                message=f"Position dropped <b>{drawdown_from_peak:.1f}%</b> from peak in {time_since_update:.0f} minutes!",
                data={
                    "Peak P&L": f"{snapshot.highest_pnl_pct:.2f}%",
                    "Current P&L": f"{current_pnl:.2f}%",
                    "Drawdown": f"{drawdown_from_peak:.2f}%",
                    "Time Window": f"{time_since_update:.0f} min"
                }
            )

            await self._deliver_alert(alert)

    async def check_position(self, position):
        """
        Check a single position for all alert conditions.

        Args:
            position: Position object from trading engine
        """
        if position.status.value != "OPEN":
            return

        # Update snapshot
        snapshot = self._update_snapshot(position)

        # Run all checks
        await asyncio.gather(
            self._check_profit_thresholds(position, snapshot),
            self._check_loss_thresholds(position, snapshot),
            self._check_tp_sl_proximity(position, snapshot),
            self._check_tp_sl_triggered(position, snapshot),
            self._check_stale_position(position, snapshot),
            self._check_rapid_loss(position, snapshot),
            return_exceptions=True
        )

    async def check_all_positions(self):
        """Check all open positions for alerts."""
        try:
            positions = self.engine.get_open_positions()

            # Check each position if any exist
            if positions:
                tasks = [self.check_position(pos) for pos in positions]
                await asyncio.gather(*tasks, return_exceptions=True)

            # Clean up closed positions from snapshots
            # (do this even if positions is empty to clear all snapshots)
            open_ids = {pos.id for pos in positions} if positions else set()
            closed_ids = set(self.position_snapshots.keys()) - open_ids

            for pos_id in closed_ids:
                del self.position_snapshots[pos_id]
                logger.debug(f"Removed snapshot for closed position: {pos_id}")

        except Exception as e:
            logger.error(f"Error checking positions: {e}")

    async def start_monitoring(self, check_interval: int = 30):
        """
        Start background monitoring loop.

        Args:
            check_interval: Seconds between position checks
        """
        if self._monitoring:
            logger.warning("Position monitoring already running")
            return

        self._monitoring = True
        logger.info(f"Position monitoring started (interval: {check_interval}s)")

        while self._monitoring:
            try:
                await self.check_all_positions()
                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
                await asyncio.sleep(check_interval)

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False
        logger.info("Position monitoring stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "monitoring_active": self._monitoring,
            "positions_tracked": len(self.position_snapshots),
            "total_alerts_sent": self.total_alerts_sent,
            "alerts_by_type": {k.value: v for k, v in self.alerts_by_type.items()},
            "alert_handlers": len(self.alert_handlers)
        }
