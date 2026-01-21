"""
Enhanced Risk Management System

Enforces comprehensive trading limits and alerts for Jarvis Treasury.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Risk alert severity levels."""
    INFO = "INFO"           # Informational, no action needed
    WARNING = "WARNING"     # Approaching limits
    CRITICAL = "CRITICAL"   # Limit exceeded or imminent breach
    EMERGENCY = "EMERGENCY" # Circuit breaker triggered


class LimitType(Enum):
    """Types of risk limits."""
    POSITION_SIZE = "POSITION_SIZE"           # Max single position size
    DAILY_LOSS = "DAILY_LOSS"                 # Max daily loss limit
    CONCENTRATION = "CONCENTRATION"           # Max % in single token
    PORTFOLIO_ALLOCATION = "PORTFOLIO_ALLOCATION"  # Max % of total portfolio
    DRAWDOWN = "DRAWDOWN"                     # Max drawdown from peak
    TRADE_FREQUENCY = "TRADE_FREQUENCY"       # Max trades per period
    CORRELATION = "CORRELATION"               # Max correlated positions


@dataclass
class RiskLimit:
    """Defines a risk limit with threshold and warning levels."""
    limit_type: LimitType
    hard_limit: float           # Absolute maximum
    warning_threshold: float    # Warn when approaching (% of hard limit)
    enabled: bool = True
    description: str = ""

    def check_value(self, current: float) -> Tuple[bool, AlertLevel, str]:
        """
        Check if value is within limits.

        Returns:
            Tuple of (within_limit, alert_level, message)
        """
        if not self.enabled:
            return True, AlertLevel.INFO, ""

        warning_value = self.hard_limit * self.warning_threshold

        if current >= self.hard_limit:
            return False, AlertLevel.CRITICAL, (
                f"{self.limit_type.value} exceeded: {current:.2f} >= {self.hard_limit:.2f}"
            )
        elif current >= warning_value:
            pct = (current / self.hard_limit) * 100
            return True, AlertLevel.WARNING, (
                f"{self.limit_type.value} at {pct:.1f}% of limit ({current:.2f}/{self.hard_limit:.2f})"
            )
        else:
            return True, AlertLevel.INFO, ""


@dataclass
class RiskViolation:
    """Records a risk limit violation."""
    timestamp: str
    limit_type: LimitType
    current_value: float
    limit_value: float
    severity: AlertLevel
    message: str
    blocked_action: Optional[str] = None  # What action was prevented
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAlert:
    """Real-time risk alert."""
    timestamp: str
    level: AlertLevel
    limit_type: LimitType
    message: str
    current_value: float
    limit_value: float
    action_required: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_telegram_message(self) -> str:
        """Format alert for Telegram notification."""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.EMERGENCY: "🔴"
        }
        emoji = emoji_map.get(self.level, "⚠️")

        msg = f"{emoji} <b>RISK ALERT - {self.level.value}</b>\n\n"
        msg += f"<b>Type:</b> {self.limit_type.value}\n"
        msg += f"<b>Current:</b> {self.current_value:.2f}\n"
        msg += f"<b>Limit:</b> {self.limit_value:.2f}\n"
        msg += f"<b>Message:</b> {self.message}\n"

        if self.action_required:
            msg += f"\n<b>Action Required:</b> {self.action_required}"

        return msg


@dataclass
class RiskMetrics:
    """Current risk metrics for the portfolio."""
    timestamp: str
    total_positions: int
    total_exposure_usd: float
    daily_pnl: float
    daily_loss: float
    max_position_size: float
    max_concentration: float  # Largest single token %
    portfolio_utilization: float  # % of capital in use
    drawdown_from_peak: float
    trades_today: int

    # Limit utilization percentages
    position_limit_usage: float = 0.0
    daily_loss_limit_usage: float = 0.0
    concentration_limit_usage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskManager:
    """
    Comprehensive risk management system.

    Features:
    - Multiple configurable limit types
    - Real-time limit checking
    - Alert generation and notifications
    - Historical violation tracking
    - Circuit breaker functionality
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        enable_alerts: bool = True
    ):
        """
        Initialize risk manager.

        Args:
            state_dir: Directory for state files (violations, metrics)
            enable_alerts: Whether to generate alerts
        """
        if state_dir is None:
            from core.state_paths import STATE_PATHS
            state_dir = STATE_PATHS.trading_dir / 'risk'

        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.enable_alerts = enable_alerts

        # State files
        self.violations_file = self.state_dir / 'violations.json'
        self.metrics_file = self.state_dir / 'metrics.json'
        self.limits_file = self.state_dir / 'limits.json'

        # Initialize limits with defaults
        self.limits: Dict[LimitType, RiskLimit] = self._load_limits()

        # Track violations and alerts
        self.violations: List[RiskViolation] = self._load_violations()
        self.active_alerts: List[RiskAlert] = []

        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at: Optional[datetime] = None

        logger.info(f"RiskManager initialized with {len(self.limits)} limits")

    def _load_limits(self) -> Dict[LimitType, RiskLimit]:
        """Load or create default limits."""
        if self.limits_file.exists():
            try:
                with open(self.limits_file) as f:
                    data = json.load(f)
                return {
                    LimitType(item['limit_type']): RiskLimit(
                        limit_type=LimitType(item['limit_type']),
                        hard_limit=item['hard_limit'],
                        warning_threshold=item['warning_threshold'],
                        enabled=item.get('enabled', True),
                        description=item.get('description', '')
                    )
                    for item in data
                }
            except Exception as e:
                logger.error(f"Failed to load limits: {e}, using defaults")

        # Default limits - ALL DISABLED per user request (no buying restrictions)
        return {
            LimitType.POSITION_SIZE: RiskLimit(
                limit_type=LimitType.POSITION_SIZE,
                hard_limit=100000.0,  # Effectively unlimited
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum USD value for single position"
            ),
            LimitType.DAILY_LOSS: RiskLimit(
                limit_type=LimitType.DAILY_LOSS,
                hard_limit=100000.0,  # Effectively unlimited
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum daily loss in USD"
            ),
            LimitType.CONCENTRATION: RiskLimit(
                limit_type=LimitType.CONCENTRATION,
                hard_limit=1.0,  # 100% allowed
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum portfolio % in single token"
            ),
            LimitType.PORTFOLIO_ALLOCATION: RiskLimit(
                limit_type=LimitType.PORTFOLIO_ALLOCATION,
                hard_limit=1.0,  # 100% of portfolio allowed
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum % of portfolio in active trades"
            ),
            LimitType.DRAWDOWN: RiskLimit(
                limit_type=LimitType.DRAWDOWN,
                hard_limit=1.0,  # 100% drawdown allowed
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum drawdown from portfolio peak"
            ),
            LimitType.TRADE_FREQUENCY: RiskLimit(
                limit_type=LimitType.TRADE_FREQUENCY,
                hard_limit=10000.0,  # Effectively unlimited
                warning_threshold=0.99,
                enabled=False,  # DISABLED
                description="Maximum trades per day"
            )
        }

    def _save_limits(self):
        """Save current limits to disk."""
        try:
            data = [
                {
                    'limit_type': limit.limit_type.value,
                    'hard_limit': limit.hard_limit,
                    'warning_threshold': limit.warning_threshold,
                    'enabled': limit.enabled,
                    'description': limit.description
                }
                for limit in self.limits.values()
            ]
            with open(self.limits_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save limits: {e}")

    def _load_violations(self) -> List[RiskViolation]:
        """Load violation history."""
        if not self.violations_file.exists():
            return []

        try:
            with open(self.violations_file) as f:
                data = json.load(f)
            return [
                RiskViolation(
                    timestamp=v['timestamp'],
                    limit_type=LimitType(v['limit_type']),
                    current_value=v['current_value'],
                    limit_value=v['limit_value'],
                    severity=AlertLevel(v['severity']),
                    message=v['message'],
                    blocked_action=v.get('blocked_action'),
                    metadata=v.get('metadata', {})
                )
                for v in data[-100:]  # Keep last 100
            ]
        except Exception as e:
            logger.error(f"Failed to load violations: {e}")
            return []

    def _save_violations(self):
        """Save violation history to disk."""
        try:
            data = [
                {
                    'timestamp': v.timestamp,
                    'limit_type': v.limit_type.value,
                    'current_value': v.current_value,
                    'limit_value': v.limit_value,
                    'severity': v.severity.value,
                    'message': v.message,
                    'blocked_action': v.blocked_action,
                    'metadata': v.metadata
                }
                for v in self.violations[-100:]  # Keep last 100
            ]
            with open(self.violations_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save violations: {e}")

    def update_limit(
        self,
        limit_type: LimitType,
        hard_limit: Optional[float] = None,
        warning_threshold: Optional[float] = None,
        enabled: Optional[bool] = None
    ):
        """Update a risk limit configuration."""
        if limit_type not in self.limits:
            logger.error(f"Unknown limit type: {limit_type}")
            return

        limit = self.limits[limit_type]

        if hard_limit is not None:
            limit.hard_limit = hard_limit
        if warning_threshold is not None:
            limit.warning_threshold = warning_threshold
        if enabled is not None:
            limit.enabled = enabled

        self._save_limits()
        logger.info(f"Updated limit {limit_type.value}: {limit.hard_limit}")

    def check_position_size(self, amount_usd: float) -> Tuple[bool, Optional[RiskAlert]]:
        """
        Check if position size is within limits.

        Args:
            amount_usd: Position size in USD

        Returns:
            Tuple of (allowed, alert)
        """
        limit = self.limits[LimitType.POSITION_SIZE]
        within_limit, alert_level, message = limit.check_value(amount_usd)

        alert = None
        if not within_limit or alert_level == AlertLevel.WARNING:
            alert = RiskAlert(
                timestamp=datetime.utcnow().isoformat(),
                level=alert_level,
                limit_type=LimitType.POSITION_SIZE,
                message=message,
                current_value=amount_usd,
                limit_value=limit.hard_limit,
                action_required="Reduce position size" if not within_limit else ""
            )

            if not within_limit:
                self._record_violation(
                    limit_type=LimitType.POSITION_SIZE,
                    current_value=amount_usd,
                    limit_value=limit.hard_limit,
                    severity=alert_level,
                    message=message,
                    blocked_action="open_position"
                )

        return within_limit, alert

    def check_daily_loss(self, current_loss: float) -> Tuple[bool, Optional[RiskAlert]]:
        """
        Check if daily loss is within limits.

        Args:
            current_loss: Current daily loss in USD (positive number)

        Returns:
            Tuple of (allowed, alert)
        """
        limit = self.limits[LimitType.DAILY_LOSS]
        within_limit, alert_level, message = limit.check_value(abs(current_loss))

        alert = None
        if not within_limit or alert_level == AlertLevel.WARNING:
            # Override alert level to EMERGENCY for exceeded daily loss
            final_alert_level = AlertLevel.EMERGENCY if not within_limit else alert_level

            alert = RiskAlert(
                timestamp=datetime.utcnow().isoformat(),
                level=final_alert_level,
                limit_type=LimitType.DAILY_LOSS,
                message=message,
                current_value=abs(current_loss),
                limit_value=limit.hard_limit,
                action_required="Stop trading for today" if not within_limit else "Monitor closely"
            )

            if not within_limit:
                self._record_violation(
                    limit_type=LimitType.DAILY_LOSS,
                    current_value=abs(current_loss),
                    limit_value=limit.hard_limit,
                    severity=AlertLevel.EMERGENCY,  # Daily loss is critical
                    message=message,
                    blocked_action="daily_trading"
                )
                # Activate circuit breaker
                self._activate_circuit_breaker("Daily loss limit exceeded")

        return within_limit, alert

    def check_concentration(
        self,
        token_symbol: str,
        token_exposure: float,
        total_portfolio: float
    ) -> Tuple[bool, Optional[RiskAlert]]:
        """
        Check if token concentration is within limits.

        Args:
            token_symbol: Token symbol
            token_exposure: Total exposure to this token in USD
            total_portfolio: Total portfolio value in USD

        Returns:
            Tuple of (allowed, alert)
        """
        if total_portfolio <= 0:
            return True, None

        concentration = token_exposure / total_portfolio
        limit = self.limits[LimitType.CONCENTRATION]
        within_limit, alert_level, message = limit.check_value(concentration)

        alert = None
        if not within_limit or alert_level == AlertLevel.WARNING:
            alert = RiskAlert(
                timestamp=datetime.utcnow().isoformat(),
                level=alert_level,
                limit_type=LimitType.CONCENTRATION,
                message=f"{token_symbol}: {message}",
                current_value=concentration * 100,  # As percentage
                limit_value=limit.hard_limit * 100,
                action_required=f"Reduce {token_symbol} exposure" if not within_limit else "",
                metadata={'token': token_symbol}
            )

            if not within_limit:
                self._record_violation(
                    limit_type=LimitType.CONCENTRATION,
                    current_value=concentration,
                    limit_value=limit.hard_limit,
                    severity=alert_level,
                    message=f"{token_symbol} concentration too high",
                    blocked_action="increase_position",
                    metadata={'token': token_symbol}
                )

        return within_limit, alert

    def check_portfolio_allocation(
        self,
        deployed_capital: float,
        total_portfolio: float
    ) -> Tuple[bool, Optional[RiskAlert]]:
        """
        Check if portfolio allocation is within limits.

        Args:
            deployed_capital: Capital currently in trades (USD)
            total_portfolio: Total portfolio value (USD)

        Returns:
            Tuple of (allowed, alert)
        """
        if total_portfolio <= 0:
            return True, None

        allocation = deployed_capital / total_portfolio
        limit = self.limits[LimitType.PORTFOLIO_ALLOCATION]
        within_limit, alert_level, message = limit.check_value(allocation)

        alert = None
        if not within_limit or alert_level == AlertLevel.WARNING:
            alert = RiskAlert(
                timestamp=datetime.utcnow().isoformat(),
                level=alert_level,
                limit_type=LimitType.PORTFOLIO_ALLOCATION,
                message=message,
                current_value=allocation * 100,
                limit_value=limit.hard_limit * 100,
                action_required="Close positions or add capital" if not within_limit else ""
            )

            if not within_limit:
                self._record_violation(
                    limit_type=LimitType.PORTFOLIO_ALLOCATION,
                    current_value=allocation,
                    limit_value=limit.hard_limit,
                    severity=alert_level,
                    message=message,
                    blocked_action="open_position"
                )

        return within_limit, alert

    def check_trade_frequency(self, trades_today: int) -> Tuple[bool, Optional[RiskAlert]]:
        """
        Check if trade frequency is within limits.

        Args:
            trades_today: Number of trades executed today

        Returns:
            Tuple of (allowed, alert)
        """
        limit = self.limits[LimitType.TRADE_FREQUENCY]
        within_limit, alert_level, message = limit.check_value(float(trades_today))

        alert = None
        if not within_limit or alert_level == AlertLevel.WARNING:
            alert = RiskAlert(
                timestamp=datetime.utcnow().isoformat(),
                level=alert_level,
                limit_type=LimitType.TRADE_FREQUENCY,
                message=message,
                current_value=float(trades_today),
                limit_value=limit.hard_limit,
                action_required="Stop trading for today" if not within_limit else "Reduce trade frequency"
            )

            if not within_limit:
                self._record_violation(
                    limit_type=LimitType.TRADE_FREQUENCY,
                    current_value=float(trades_today),
                    limit_value=limit.hard_limit,
                    severity=alert_level,
                    message=message,
                    blocked_action="new_trade"
                )

        return within_limit, alert

    def check_all_limits(
        self,
        position_size: Optional[float] = None,
        daily_loss: Optional[float] = None,
        token_concentration: Optional[Dict[str, Tuple[float, float]]] = None,  # {token: (exposure, portfolio)}
        deployed_capital: Optional[float] = None,
        total_portfolio: Optional[float] = None,
        trades_today: Optional[int] = None
    ) -> Tuple[bool, List[RiskAlert]]:
        """
        Check all applicable risk limits at once.

        Args:
            position_size: New position size to check (USD)
            daily_loss: Current daily loss (USD)
            token_concentration: Dict of {token: (exposure_usd, portfolio_usd)}
            deployed_capital: Capital currently in trades (USD)
            total_portfolio: Total portfolio value (USD)
            trades_today: Number of trades executed today

        Returns:
            Tuple of (all_passed, list_of_alerts)
        """
        alerts = []
        all_passed = True

        # Check position size
        if position_size is not None:
            passed, alert = self.check_position_size(position_size)
            if not passed:
                all_passed = False
            if alert:
                alerts.append(alert)

        # Check daily loss
        if daily_loss is not None:
            passed, alert = self.check_daily_loss(daily_loss)
            if not passed:
                all_passed = False
            if alert:
                alerts.append(alert)

        # Check concentration for each token
        if token_concentration:
            for token, (exposure, portfolio) in token_concentration.items():
                passed, alert = self.check_concentration(token, exposure, portfolio)
                if not passed:
                    all_passed = False
                if alert:
                    alerts.append(alert)

        # Check portfolio allocation
        if deployed_capital is not None and total_portfolio is not None:
            passed, alert = self.check_portfolio_allocation(deployed_capital, total_portfolio)
            if not passed:
                all_passed = False
            if alert:
                alerts.append(alert)

        # Check trade frequency
        if trades_today is not None:
            passed, alert = self.check_trade_frequency(trades_today)
            if not passed:
                all_passed = False
            if alert:
                alerts.append(alert)

        # Store active alerts
        if self.enable_alerts:
            self.active_alerts = alerts

        return all_passed, alerts

    def _record_violation(
        self,
        limit_type: LimitType,
        current_value: float,
        limit_value: float,
        severity: AlertLevel,
        message: str,
        blocked_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a risk violation."""
        violation = RiskViolation(
            timestamp=datetime.utcnow().isoformat(),
            limit_type=limit_type,
            current_value=current_value,
            limit_value=limit_value,
            severity=severity,
            message=message,
            blocked_action=blocked_action,
            metadata=metadata or {}
        )

        self.violations.append(violation)
        self._save_violations()

        logger.warning(
            f"Risk violation: {limit_type.value} - {message} "
            f"(current={current_value:.2f}, limit={limit_value:.2f})"
        )

    def _activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker to halt trading."""
        self.circuit_breaker_active = True
        self.circuit_breaker_triggered_at = datetime.utcnow()

        logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}")

        # Create emergency alert
        alert = RiskAlert(
            timestamp=datetime.utcnow().isoformat(),
            level=AlertLevel.EMERGENCY,
            limit_type=LimitType.DAILY_LOSS,  # Most likely cause
            message=f"Circuit breaker activated: {reason}",
            current_value=0.0,
            limit_value=0.0,
            action_required="Manual intervention required to resume trading"
        )

        self.active_alerts.append(alert)

    def reset_circuit_breaker(self):
        """Manually reset circuit breaker."""
        self.circuit_breaker_active = False
        self.circuit_breaker_triggered_at = None
        logger.info("Circuit breaker reset manually")

    def get_risk_metrics(
        self,
        positions: List[Any],
        daily_pnl: float,
        portfolio_peak: float,
        current_portfolio: float
    ) -> RiskMetrics:
        """
        Calculate current risk metrics.

        Args:
            positions: List of open positions
            daily_pnl: Today's P&L
            portfolio_peak: Peak portfolio value
            current_portfolio: Current portfolio value

        Returns:
            RiskMetrics object
        """
        total_exposure = sum(p.amount_usd for p in positions)
        max_position = max((p.amount_usd for p in positions), default=0.0)

        # Calculate concentration
        token_exposure: Dict[str, float] = {}
        for p in positions:
            token_exposure[p.token_symbol] = token_exposure.get(p.token_symbol, 0) + p.amount_usd

        max_concentration = 0.0
        if current_portfolio > 0:
            max_concentration = max(token_exposure.values(), default=0.0) / current_portfolio

        # Calculate drawdown
        drawdown = 0.0
        if portfolio_peak > 0:
            drawdown = (portfolio_peak - current_portfolio) / portfolio_peak

        # Count today's trades
        today = datetime.utcnow().date()
        trades_today = sum(
            1 for p in positions
            if datetime.fromisoformat(p.opened_at.replace('Z', '+00:00')).date() == today
        )

        # Calculate limit utilization
        position_limit_usage = 0.0
        if LimitType.POSITION_SIZE in self.limits:
            limit = self.limits[LimitType.POSITION_SIZE]
            position_limit_usage = (max_position / limit.hard_limit * 100) if limit.hard_limit > 0 else 0

        daily_loss_limit_usage = 0.0
        if LimitType.DAILY_LOSS in self.limits and daily_pnl < 0:
            limit = self.limits[LimitType.DAILY_LOSS]
            daily_loss_limit_usage = (abs(daily_pnl) / limit.hard_limit * 100) if limit.hard_limit > 0 else 0

        concentration_limit_usage = 0.0
        if LimitType.CONCENTRATION in self.limits:
            limit = self.limits[LimitType.CONCENTRATION]
            concentration_limit_usage = (max_concentration / limit.hard_limit * 100) if limit.hard_limit > 0 else 0

        return RiskMetrics(
            timestamp=datetime.utcnow().isoformat(),
            total_positions=len(positions),
            total_exposure_usd=total_exposure,
            daily_pnl=daily_pnl,
            daily_loss=abs(min(daily_pnl, 0)),
            max_position_size=max_position,
            max_concentration=max_concentration * 100,  # As percentage
            portfolio_utilization=(total_exposure / current_portfolio * 100) if current_portfolio > 0 else 0,
            drawdown_from_peak=drawdown * 100,  # As percentage
            trades_today=trades_today,
            position_limit_usage=position_limit_usage,
            daily_loss_limit_usage=daily_loss_limit_usage,
            concentration_limit_usage=concentration_limit_usage
        )

    def get_active_alerts(self) -> List[RiskAlert]:
        """Get current active alerts."""
        return self.active_alerts.copy()

    def get_recent_violations(self, hours: int = 24) -> List[RiskViolation]:
        """Get violations from last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            v for v in self.violations
            if datetime.fromisoformat(v.timestamp.replace('Z', '+00:00')) > cutoff
        ]

    def get_limit_config(self) -> Dict[str, Any]:
        """Get current limit configuration."""
        return {
            limit_type.value: {
                'hard_limit': limit.hard_limit,
                'warning_threshold': limit.warning_threshold,
                'enabled': limit.enabled,
                'description': limit.description
            }
            for limit_type, limit in self.limits.items()
        }
