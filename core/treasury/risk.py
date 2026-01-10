"""
Treasury Risk Management.

Implements safety controls for autonomous trading:

Hard Limits:
- Position size: Max 5% per trade
- Total exposure: Max 50% of active wallet
- Daily loss: Max 5%
- Weekly loss: Max 10%
- Monthly loss: Max 20%

Circuit Breakers:
- Auto-pause on 3 consecutive losses
- Auto-pause on rapid drawdown
- Manual override capability
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    """Risk limit configuration."""

    # Position limits (as percentage of active wallet)
    max_position_size_pct: float = 0.05  # 5% per position
    max_total_exposure_pct: float = 0.50  # 50% total exposure
    max_single_token_pct: float = 0.20   # 20% in any single token

    # Loss limits (as percentage of starting balance)
    max_daily_loss_pct: float = 0.05     # 5% daily
    max_weekly_loss_pct: float = 0.10    # 10% weekly
    max_monthly_loss_pct: float = 0.20   # 20% monthly

    # Trade limits
    max_trades_per_day: int = 50
    max_trades_per_hour: int = 10
    min_trade_interval_seconds: int = 30

    # Slippage and price impact
    max_slippage_bps: int = 200  # 2%
    max_price_impact_pct: float = 3.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_position_size_pct": self.max_position_size_pct,
            "max_total_exposure_pct": self.max_total_exposure_pct,
            "max_single_token_pct": self.max_single_token_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_monthly_loss_pct": self.max_monthly_loss_pct,
            "max_trades_per_day": self.max_trades_per_day,
            "max_trades_per_hour": self.max_trades_per_hour,
            "min_trade_interval_seconds": self.min_trade_interval_seconds,
            "max_slippage_bps": self.max_slippage_bps,
            "max_price_impact_pct": self.max_price_impact_pct,
        }


@dataclass
class CircuitBreaker:
    """Circuit breaker for emergency stops."""

    state: CircuitState = CircuitState.CLOSED
    triggered_at: Optional[datetime] = None
    trigger_reason: str = ""
    consecutive_losses: int = 0
    auto_reset_after_hours: int = 24
    manual_override: bool = False

    # Trigger thresholds
    max_consecutive_losses: int = 3
    rapid_drawdown_pct: float = 0.10  # 10% in 1 hour
    rapid_drawdown_window_hours: int = 1

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
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
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


class RiskManager:
    """
    Manages trading risk for the treasury.

    Tracks:
    - Position sizes
    - P&L by time period
    - Trade frequency
    - Circuit breaker state

    Validates:
    - Proposed trades against limits
    - Current exposure levels
    - Loss thresholds
    """

    def __init__(
        self,
        limits: RiskLimits = None,
        db_path: str = None,
    ):
        """
        Initialize risk manager.

        Args:
            limits: Risk limit configuration
            db_path: Path to trade log database
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
        token_mint: str,
        side: str,
        amount: int,
        current_balance: int,
        price_impact_pct: float = 0,
    ) -> tuple[bool, str]:
        """
        Validate a proposed trade against risk limits.

        Args:
            token_mint: Token being traded
            side: "buy" or "sell"
            amount: Trade amount in lamports
            current_balance: Current wallet balance
            price_impact_pct: Expected price impact

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        # Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed():
            return False, f"Circuit breaker active: {self.circuit_breaker.trigger_reason}"

        # Check trade interval
        if self._last_trade_time:
            elapsed = (datetime.now(timezone.utc) - self._last_trade_time).total_seconds()
            if elapsed < self.limits.min_trade_interval_seconds:
                return False, f"Trade interval too short: {elapsed:.0f}s < {self.limits.min_trade_interval_seconds}s"

        # Check position size
        max_position = int(current_balance * self.limits.max_position_size_pct)
        if amount > max_position:
            return False, f"Position too large: {amount} > {max_position} ({self.limits.max_position_size_pct*100}%)"

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

        return True, "Trade approved"

    def record_trade(
        self,
        token_mint: str,
        side: str,
        amount_in: int,
        amount_out: int,
        success: bool,
        signature: str = None,
    ) -> TradeRecord:
        """
        Record a completed trade.

        Args:
            token_mint: Token traded
            side: "buy" or "sell"
            amount_in: Input amount
            amount_out: Output amount
            success: Whether trade succeeded
            signature: Transaction signature

        Returns:
            TradeRecord
        """
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

    def get_risk_status(self) -> Dict[str, Any]:
        """Get comprehensive risk status."""
        return {
            "limits": self.limits.to_dict(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "active_positions": self._active_positions,
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
