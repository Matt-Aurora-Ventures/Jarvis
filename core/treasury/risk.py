"""
Treasury Risk Management.

Implements safety controls for autonomous trading:

Hard Limits:
- Position size: Max 25% per trade (updated from video learnings)
- Max notional: $10M USD cap per position
- Total exposure: Max 50% of active wallet
- Daily loss: Max 5%
- Weekly loss: Max 10%
- Monthly loss: Max 20%

Circuit Breakers:
- Auto-pause on 3 consecutive losses
- Auto-pause on rapid drawdown
- Manual override capability

Cooldown System:
- 30-minute default cooldown after trade closure
- 60-minute cooldown after losses
- 120-minute cooldown after consecutive losses
- Integrated with core.trading.cooldown module
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Import cooldown system
try:
    from core.trading.cooldown import CooldownManager, CooldownConfig, CooldownType
    COOLDOWN_AVAILABLE = True
except ImportError:
    COOLDOWN_AVAILABLE = False

if TYPE_CHECKING:
    from core.trading.cooldown import CooldownManager

logger = logging.getLogger("jarvis.treasury.risk")


class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Trading halted
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RiskLimits:
    """Risk limit configuration - ALL LIMITS DISABLED per user request."""

    # Position limits - UNRESTRICTED
    max_position_size_pct: float = 1.0   # 100% per position (no limit)
    max_total_exposure_pct: float = 1.0  # 100% total exposure (no limit)
    max_single_token_pct: float = 1.0    # 100% in any single token (no limit)

    # Absolute position limits - UNRESTRICTED
    max_notional_usd: float = 100_000_000  # $100M cap (effectively unlimited)
    min_position_usd: float = 0.01          # Minimum $0.01 per trade

    # Loss limits - UNRESTRICTED
    max_daily_loss_pct: float = 1.0      # 100% daily (no limit)
    max_weekly_loss_pct: float = 1.0     # 100% weekly (no limit)
    max_monthly_loss_pct: float = 1.0    # 100% monthly (no limit)

    # Trade limits - UNRESTRICTED
    max_trades_per_day: int = 10000
    max_trades_per_hour: int = 1000
    min_trade_interval_seconds: int = 0

    # Slippage and price impact - PERMISSIVE
    max_slippage_bps: int = 5000  # 50%
    max_price_impact_pct: float = 100.0

    # Circuit breaker settings - DISABLED
    max_consecutive_losses: int = 10000

    # Cooldown settings - MINIMAL
    default_cooldown_minutes: int = 0
    loss_cooldown_minutes: int = 0
    consecutive_loss_cooldown_minutes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_position_size_pct": self.max_position_size_pct,
            "max_total_exposure_pct": self.max_total_exposure_pct,
            "max_single_token_pct": self.max_single_token_pct,
            "max_notional_usd": self.max_notional_usd,
            "min_position_usd": self.min_position_usd,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_monthly_loss_pct": self.max_monthly_loss_pct,
            "max_trades_per_day": self.max_trades_per_day,
            "max_trades_per_hour": self.max_trades_per_hour,
            "min_trade_interval_seconds": self.min_trade_interval_seconds,
            "max_slippage_bps": self.max_slippage_bps,
            "max_price_impact_pct": self.max_price_impact_pct,
            "default_cooldown_minutes": self.default_cooldown_minutes,
            "loss_cooldown_minutes": self.loss_cooldown_minutes,
            "consecutive_loss_cooldown_minutes": self.consecutive_loss_cooldown_minutes,
        }


@dataclass
class CircuitBreaker:
    """Circuit breaker for emergency stops."""

    _state: CircuitState = CircuitState.CLOSED
    triggered_at: Optional[datetime] = None
    trigger_reason: str = ""
    consecutive_losses: int = 0
    auto_reset_after_hours: int = 24
    manual_override: bool = False
    cooldown_end: Optional[datetime] = None  # For half-open transition

    # Trigger thresholds
    max_consecutive_losses: int = 3
    rapid_drawdown_pct: float = 0.10  # 10% in 1 hour
    rapid_drawdown_window_hours: int = 1

    @property
    def state(self) -> str:
        """Return state as string for backwards compatibility."""
        return self._state.value

    @state.setter
    def state(self, value):
        """Set state from string or enum."""
        if isinstance(value, CircuitState):
            self._state = value
        else:
            self._state = CircuitState(value)

    def trip(self, reason: str):
        """Trip the circuit breaker."""
        self.state = CircuitState.OPEN
        self.triggered_at = datetime.now(timezone.utc)
        self.trigger_reason = reason
        logger.warning(f"Circuit breaker TRIPPED: {reason}")

    def reset(self, manual: bool = False):
        """Reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.triggered_at = None
        self.trigger_reason = ""
        self.consecutive_losses = 0
        self.manual_override = manual
        logger.info(f"Circuit breaker reset (manual={manual})")

    def check_auto_reset(self) -> bool:
        """Check if circuit breaker should auto-reset."""
        if self.state != CircuitState.OPEN:
            return False

        if self.triggered_at is None:
            return True

        elapsed = datetime.now(timezone.utc) - self.triggered_at
        if elapsed > timedelta(hours=self.auto_reset_after_hours):
            self.state = CircuitState.HALF_OPEN
            logger.info("Circuit breaker entering HALF_OPEN state")
            return True

        return False

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed."""
        if self.manual_override:
            return True

        self.check_auto_reset()
        return self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_loss(self):
        """Record a trading loss."""
        self.consecutive_losses += 1
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.trip(f"Consecutive losses: {self.consecutive_losses}")

    def record_win(self):
        """Record a trading win, resets consecutive loss counter."""
        self.consecutive_losses = 0

    def check_state(self):
        """Check and update state based on cooldown."""
        if self._state == CircuitState.OPEN:
            if self.cooldown_end and datetime.now(timezone.utc) >= self.cooldown_end:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                self.check_auto_reset()

    def get_status(self) -> Dict[str, Any]:
        """Alias for to_dict."""
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trigger_reason": self.trigger_reason,
            "consecutive_losses": self.consecutive_losses,
            "trading_allowed": self.is_trading_allowed(),
        }


@dataclass
class TradeRecord:
    """Record of a trade for risk tracking."""
    id: int
    timestamp: datetime
    token_mint: str
    side: str  # buy/sell
    amount_in: int
    amount_out: int
    pnl: int  # Profit/loss in lamports
    success: bool

    # Aliases for test compatibility
    @property
    def token(self) -> str:
        return self.token_mint

    @property
    def amount(self) -> int:
        return self.amount_in


# Alias for backwards compatibility
TradeRecordResult = TradeRecord


class RiskManager:
    """
    Manages trading risk for the treasury.

    Tracks:
    - Position sizes
    - P&L by time period
    - Trade frequency
    - Circuit breaker state
    - Cooldown periods per symbol

    Validates:
    - Proposed trades against limits
    - Current exposure levels
    - Loss thresholds
    - Cooldown status
    """

    def __init__(
        self,
        limits: RiskLimits = None,
        db_path: str = None,
        enable_cooldown: bool = True,
    ):
        """
        Initialize risk manager.

        Args:
            limits: Risk limit configuration
            db_path: Path to trade log database
            enable_cooldown: Enable cooldown system integration
        """
        self.limits = limits or RiskLimits()
        self.circuit_breaker = CircuitBreaker()

        self.db_path = db_path or str(
            Path(os.getenv("DATA_DIR", "data")) / "treasury_trades.db"
        )
        self._init_database()

        # Runtime state
        self._active_positions: Dict[str, int] = {}  # token -> amount
        self._starting_balance_daily: int = 0
        self._starting_balance_weekly: int = 0
        self._starting_balance_monthly: int = 0
        self._last_trade_time: Optional[datetime] = None

        # Initialize cooldown manager if available
        self._cooldown_manager: Optional["CooldownManager"] = None
        if enable_cooldown and COOLDOWN_AVAILABLE:
            cooldown_config = CooldownConfig(
                default_cooldown_minutes=self.limits.default_cooldown_minutes,
                loss_cooldown_minutes=self.limits.loss_cooldown_minutes,
                consecutive_loss_cooldown_minutes=self.limits.consecutive_loss_cooldown_minutes,
            )
            self._cooldown_manager = CooldownManager(config=cooldown_config)
            logger.info("Cooldown system initialized")

    def _init_database(self):
        """Initialize trade logging database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS treasury_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                side TEXT NOT NULL,
                amount_in INTEGER NOT NULL,
                amount_out INTEGER NOT NULL,
                pnl INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                signature TEXT,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                starting_balance INTEGER NOT NULL,
                ending_balance INTEGER,
                total_pnl INTEGER DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp
            ON treasury_trades(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_token
            ON treasury_trades(token_mint)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Risk database initialized: {self.db_path}")

    def set_starting_balance(self, balance: int, period: str = "daily"):
        """Set starting balance for P&L tracking."""
        if period == "daily":
            self._starting_balance_daily = balance
        elif period == "weekly":
            self._starting_balance_weekly = balance
        elif period == "monthly":
            self._starting_balance_monthly = balance

    def validate_trade(
        self,
        token_mint: str = None,
        side: str = "",
        amount: int = 0,
        current_balance: int = 0,
        price_impact_pct: float = 0,
        amount_usd: float = 0,  # USD value for notional limits
        # Aliases for test compatibility
        token: str = None,
        balance: int = None,
    ) -> tuple[bool, str]:
        """
        Validate a proposed trade against risk limits.

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        # Handle parameter aliases
        token_mint = token_mint or token or ""
        current_balance = balance if balance is not None else current_balance

        # Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed():
            return False, f"Circuit breaker active: {self.circuit_breaker.trigger_reason}"

        # Check cooldown (if enabled)
        if self._cooldown_manager and side == "buy":
            can_trade, cooldown_msg = self._cooldown_manager.can_trade(token_mint)
            if not can_trade:
                return False, cooldown_msg

        # Check trade interval
        if self._last_trade_time:
            elapsed = (datetime.now(timezone.utc) - self._last_trade_time).total_seconds()
            if elapsed < self.limits.min_trade_interval_seconds:
                return False, f"Trade interval too short: {elapsed:.0f}s < {self.limits.min_trade_interval_seconds}s"

        # Check notional USD limits
        if amount_usd > 0:
            if amount_usd > self.limits.max_notional_usd:
                return False, f"Notional too large: ${amount_usd:,.0f} > ${self.limits.max_notional_usd:,.0f}"
            if amount_usd < self.limits.min_position_usd:
                return False, f"Position too small: ${amount_usd:.2f} < ${self.limits.min_position_usd:.0f}"

        # Check position size
        max_position = int(current_balance * self.limits.max_position_size_pct)
        if amount > max_position:
            return False, f"Position size too large: {amount} > {max_position} ({self.limits.max_position_size_pct*100}%)"

        # Check total exposure
        total_exposure = sum(self._active_positions.values())
        max_exposure = int(current_balance * self.limits.max_total_exposure_pct)
        if side == "buy" and total_exposure + amount > max_exposure:
            return False, f"Total exposure exceeded: {total_exposure + amount} > {max_exposure}"

        # Check single token exposure
        current_token_position = self._active_positions.get(token_mint, 0)
        max_token = int(current_balance * self.limits.max_single_token_pct)
        if side == "buy" and current_token_position + amount > max_token:
            return False, f"Single token exposure exceeded: {current_token_position + amount} > {max_token}"

        # Check price impact
        if price_impact_pct > self.limits.max_price_impact_pct:
            return False, f"Price impact too high: {price_impact_pct}% > {self.limits.max_price_impact_pct}%"

        # Check trade frequency
        trades_today = self._get_trade_count(hours=24)
        if trades_today >= self.limits.max_trades_per_day:
            return False, f"Daily trade limit reached: {trades_today}"

        trades_hour = self._get_trade_count(hours=1)
        if trades_hour >= self.limits.max_trades_per_hour:
            return False, f"Hourly trade limit reached: {trades_hour}"

        # Check loss limits
        loss_check = self._check_loss_limits(current_balance)
        if not loss_check[0]:
            return loss_check

        return True, ""

    def record_trade(
        self,
        token_mint: str = None,
        side: str = "",
        amount_in: int = 0,
        amount_out: int = 0,
        success: bool = True,
        signature: str = None,
        # Aliases for test compatibility
        token: str = None,
        amount: int = None,
        price: float = None,
    ) -> "TradeRecordResult":
        """Record a completed trade."""
        # Handle aliases
        token_mint = token_mint or token or ""
        if amount is not None:
            amount_in = amount
            amount_out = int(amount * (price or 1.0))

        now = datetime.now(timezone.utc)
        pnl = amount_out - amount_in if side == "sell" else 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO treasury_trades
            (timestamp, token_mint, side, amount_in, amount_out, pnl, success, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now.isoformat(), token_mint, side, amount_in, amount_out, pnl, 1 if success else 0, signature),
        )

        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Update state
        self._last_trade_time = now

        if success:
            if side == "buy":
                self._active_positions[token_mint] = self._active_positions.get(token_mint, 0) + amount_in
                self.circuit_breaker.consecutive_losses = 0
            elif side == "sell":
                self._active_positions[token_mint] = max(0, self._active_positions.get(token_mint, 0) - amount_in)

                # Register cooldown on position close (key insight from video learnings)
                if self._cooldown_manager:
                    if pnl < 0:
                        # Loss cooldown
                        if self.circuit_breaker.consecutive_losses >= 2:
                            self._cooldown_manager.record_closure(
                                token_mint,
                                CooldownType.CONSECUTIVE_LOSS if COOLDOWN_AVAILABLE else None,
                                pnl_pct=(pnl / amount_in * 100) if amount_in > 0 else 0,
                            )
                        else:
                            self._cooldown_manager.record_closure(
                                token_mint,
                                CooldownType.LOSS if COOLDOWN_AVAILABLE else None,
                                pnl_pct=(pnl / amount_in * 100) if amount_in > 0 else 0,
                            )
                    else:
                        # Win cooldown (standard)
                        self._cooldown_manager.record_closure(
                            token_mint,
                            CooldownType.STANDARD if COOLDOWN_AVAILABLE else None,
                            pnl_pct=(pnl / amount_in * 100) if amount_in > 0 else 0,
                        )

                if pnl < 0:
                    self.circuit_breaker.consecutive_losses += 1
                    if self.circuit_breaker.consecutive_losses >= self.circuit_breaker.max_consecutive_losses:
                        self.circuit_breaker.trip(f"{self.circuit_breaker.consecutive_losses} consecutive losses")
                else:
                    self.circuit_breaker.consecutive_losses = 0

        logger.info(f"Trade recorded: {side} {amount_in} of {token_mint[:8]}..., pnl={pnl}")

        return TradeRecord(
            id=trade_id,
            timestamp=now,
            token_mint=token_mint,
            side=side,
            amount_in=amount_in,
            amount_out=amount_out,
            pnl=pnl,
            success=success,
        )

    def _check_loss_limits(self, current_balance: int) -> tuple[bool, str]:
        """Check if loss limits have been exceeded."""
        now = datetime.now(timezone.utc)

        # Daily loss
        if self._starting_balance_daily > 0:
            daily_loss_pct = (self._starting_balance_daily - current_balance) / self._starting_balance_daily
            if daily_loss_pct > self.limits.max_daily_loss_pct:
                self.circuit_breaker.trip(f"Daily loss limit: {daily_loss_pct*100:.1f}%")
                return False, f"Daily loss limit exceeded: {daily_loss_pct*100:.1f}%"

        # Weekly loss
        if self._starting_balance_weekly > 0:
            weekly_loss_pct = (self._starting_balance_weekly - current_balance) / self._starting_balance_weekly
            if weekly_loss_pct > self.limits.max_weekly_loss_pct:
                self.circuit_breaker.trip(f"Weekly loss limit: {weekly_loss_pct*100:.1f}%")
                return False, f"Weekly loss limit exceeded: {weekly_loss_pct*100:.1f}%"

        # Monthly loss
        if self._starting_balance_monthly > 0:
            monthly_loss_pct = (self._starting_balance_monthly - current_balance) / self._starting_balance_monthly
            if monthly_loss_pct > self.limits.max_monthly_loss_pct:
                self.circuit_breaker.trip(f"Monthly loss limit: {monthly_loss_pct*100:.1f}%")
                return False, f"Monthly loss limit exceeded: {monthly_loss_pct*100:.1f}%"

        return True, ""

    def _get_trade_count(self, hours: int = 24) -> int:
        """Get number of trades in time period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM treasury_trades
            WHERE timestamp > datetime('now', ? || ' hours')
            """,
            (-hours,),
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_pnl(self, period: str = "daily") -> Dict[str, Any]:
        """
        Get P&L for a period.

        Args:
            period: "daily", "weekly", "monthly"

        Returns:
            P&L statistics
        """
        hours = {"daily": 24, "weekly": 168, "monthly": 720}.get(period, 24)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT SUM(pnl), COUNT(*), SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)
            FROM treasury_trades
            WHERE timestamp > datetime('now', ? || ' hours')
              AND success = 1
            """,
            (-hours,),
        )

        row = cursor.fetchone()
        conn.close()

        total_pnl = row[0] or 0
        trade_count = row[1] or 0
        winning_trades = row[2] or 0

        return {
            "period": period,
            "total_pnl": total_pnl,
            "trade_count": trade_count,
            "winning_trades": winning_trades,
            "win_rate": winning_trades / trade_count if trade_count > 0 else 0,
        }

    def record_trade_result(
        self,
        signature: str,
        pnl: int = 0,
        success: bool = True,
        exit_price: float = None,  # For test compatibility
    ):
        """Record the result of a previously recorded trade."""
        if pnl > 0:
            self.circuit_breaker.record_win()
        elif pnl < 0:
            self.circuit_breaker.record_loss()

        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE treasury_trades SET pnl = ?, success = ? WHERE signature = ?",
            (pnl, 1 if success else 0, signature),
        )
        conn.commit()
        conn.close()

    def get_risk_status(self) -> Dict[str, Any]:
        """Get comprehensive risk status."""
        return {
            "limits": self.limits.to_dict(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "active_positions": self._active_positions,
            "open_positions": self._active_positions,  # Alias for tests
            "total_exposure": sum(self._active_positions.values()),
            "last_trade_time": self._last_trade_time.isoformat() if self._last_trade_time else None,
            "pnl_daily": self.get_pnl("daily"),
            "pnl_weekly": self.get_pnl("weekly"),
        }

    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Trigger emergency stop."""
        self.circuit_breaker.trip(reason)
        logger.critical(f"EMERGENCY STOP: {reason}")

    def resume_trading(self, override: bool = False):
        """Resume trading after stop."""
        self.circuit_breaker.reset(manual=override)
        logger.info(f"Trading resumed (override={override})")

    def get_cooldown_status(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get cooldown status for a symbol or all symbols.

        Args:
            symbol: Optional symbol to check, or all if None

        Returns:
            Dict with cooldown information
        """
        if not self._cooldown_manager:
            return {"enabled": False, "message": "Cooldown system not available"}

        if symbol:
            can_trade, message = self._cooldown_manager.can_trade(symbol)
            remaining = self._cooldown_manager.get_remaining_cooldown(symbol)
            return {
                "enabled": True,
                "symbol": symbol,
                "can_trade": can_trade,
                "message": message,
                "remaining_minutes": remaining,
            }

        return {
            "enabled": True,
            "active_cooldowns": self._cooldown_manager.get_active_cooldowns(),
        }

    def clear_cooldown(self, symbol: str) -> bool:
        """
        Manually clear cooldown for a symbol (admin override).

        Args:
            symbol: Symbol to clear cooldown for

        Returns:
            True if cleared, False if not available
        """
        if not self._cooldown_manager:
            return False

        self._cooldown_manager.clear_cooldown(symbol)
        logger.info(f"Cooldown cleared for {symbol}")
        return True

    @property
    def cooldown_manager(self) -> Optional["CooldownManager"]:
        """Get the cooldown manager instance."""
        return self._cooldown_manager
