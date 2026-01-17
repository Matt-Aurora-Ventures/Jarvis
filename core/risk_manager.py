"""
Risk Manager Module for Life OS Trading Bot
============================================

Implements critical risk management safeguards:
- Stop-Loss / Take-Profit automation
- Position sizing (1-2% rule)
- Max drawdown circuit breaker
- Over-trading throttle
- Trade journaling

Usage:
    from core.risk_manager import RiskManager, PositionSizer
    
    rm = RiskManager(max_drawdown_pct=10.0)
    
    # Check if trade is allowed
    if rm.can_trade():
        # Size the position
        position = rm.calculate_position_size(capital=10000, entry=100, stop_loss=95)
        # Execute trade...
        rm.record_trade(...)
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# Default data directory
DATA_DIR = Path(os.environ.get("LIFEOS_DATA_DIR", Path.home() / ".lifeos" / "trading"))


@dataclass
class Trade:
    """Represents a single trade for journaling."""
    id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    entry_price: float
    quantity: float
    timestamp: float = field(default_factory=time.time)
    exit_price: Optional[float] = None
    exit_timestamp: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = "unknown"
    status: str = "OPEN"  # OPEN, CLOSED, STOPPED_OUT, TOOK_PROFIT
    pnl: float = 0.0
    pnl_pct: float = 0.0
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "action": self.action,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "timestamp": self.timestamp,
            "exit_price": self.exit_price,
            "exit_timestamp": self.exit_timestamp,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy": self.strategy,
            "status": self.status,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trade":
        return cls(**data)


@dataclass
class RiskLimits:
    """Configurable risk limits."""
    max_position_pct: float = 2.0        # Max % of capital per trade
    max_daily_loss_pct: float = 5.0      # Max daily loss before stopping
    max_drawdown_pct: float = 10.0       # Max drawdown before circuit breaker
    max_trades_per_hour: int = 10        # Throttle limit
    stop_loss_pct: float = 2.0           # Default stop-loss %
    take_profit_pct: float = 6.0         # Default take-profit %
    max_open_positions: int = 50          # Max concurrent positions
    min_risk_reward: float = 2.0         # Minimum risk/reward ratio


class PositionSizer:
    """Calculate position sizes based on risk parameters."""
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
    
    def calculate_position(
        self,
        capital: float,
        entry_price: float,
        stop_loss_price: float,
        risk_pct: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate position size based on Kelly-inspired risk management.
        
        Args:
            capital: Total trading capital
            entry_price: Planned entry price
            stop_loss_price: Stop-loss price
            risk_pct: Override risk percentage (default: max_position_pct)
        
        Returns:
            Dict with position_size, quantity, risk_amount, etc.
        """
        risk_pct = risk_pct or self.limits.max_position_pct
        
        # Calculate risk per share
        if entry_price <= 0 or stop_loss_price <= 0:
            return {"error": "Invalid prices", "quantity": 0}
        
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit == 0:
            return {"error": "Stop-loss equals entry", "quantity": 0}
        
        # Max amount we're willing to risk
        risk_amount = capital * (risk_pct / 100)
        
        # Calculate quantity
        quantity = risk_amount / risk_per_unit
        position_value = quantity * entry_price
        
        # Ensure we don't exceed a reasonable position size
        max_position_value = capital * 0.25  # Never more than 25% of capital in one position
        if position_value > max_position_value:
            quantity = max_position_value / entry_price
            position_value = max_position_value
        
        return {
            "quantity": round(quantity, 8),
            "position_value": round(position_value, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_per_unit": round(risk_per_unit, 4),
            "position_pct_of_capital": round((position_value / capital) * 100, 2),
            "effective_risk_pct": round((risk_amount / capital) * 100, 2),
        }
    
    def calculate_stop_take(
        self,
        entry_price: float,
        direction: str = "LONG",
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate stop-loss and take-profit prices.
        
        Args:
            entry_price: Entry price
            direction: "LONG" or "SHORT"
            stop_loss_pct: Override stop-loss percentage
            take_profit_pct: Override take-profit percentage
        """
        sl_pct = stop_loss_pct or self.limits.stop_loss_pct
        tp_pct = take_profit_pct or self.limits.take_profit_pct
        
        if direction.upper() == "LONG":
            stop_loss = entry_price * (1 - sl_pct / 100)
            take_profit = entry_price * (1 + tp_pct / 100)
        else:
            stop_loss = entry_price * (1 + sl_pct / 100)
            take_profit = entry_price * (1 - tp_pct / 100)
        
        risk_reward = tp_pct / sl_pct if sl_pct > 0 else 0
        
        return {
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "stop_loss_pct": sl_pct,
            "take_profit_pct": tp_pct,
            "risk_reward_ratio": round(risk_reward, 2),
            "meets_min_rr": risk_reward >= self.limits.min_risk_reward,
        }


class RiskManager:
    """
    Central risk management controller.
    
    Monitors portfolio risk, enforces limits, and provides circuit breakers.
    """
    
    def __init__(
        self,
        limits: Optional[RiskLimits] = None,
        data_dir: Optional[Path] = None
    ):
        self.limits = limits or RiskLimits()
        self.sizer = PositionSizer(self.limits)
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Runtime state
        self._trades: List[Trade] = []
        self._trade_times: List[float] = []  # For throttling
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._circuit_breaker_active: bool = False
        self._circuit_breaker_reason: str = ""
        self._circuit_breaker_triggered_at: float = 0.0  # Timestamp for auto-recovery
        self._consecutive_losses: int = 0  # Track consecutive losing trades
        
        # Load existing data
        self._load_state()
    
    def _load_state(self) -> None:
        """Load persisted state from disk."""
        state_file = self.data_dir / "risk_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)
                self._peak_equity = state.get("peak_equity", 0.0)
                self._current_equity = state.get("current_equity", 0.0)
                self._circuit_breaker_active = state.get("circuit_breaker_active", False)
                self._circuit_breaker_reason = state.get("circuit_breaker_reason", "")
                self._circuit_breaker_triggered_at = state.get("circuit_breaker_triggered_at", 0.0)
                self._consecutive_losses = state.get("consecutive_losses", 0)
            except Exception:
                pass
        
        trades_file = self.data_dir / "trades.json"
        if trades_file.exists():
            try:
                with open(trades_file) as f:
                    trades_data = json.load(f)
                self._trades = [Trade.from_dict(t) for t in trades_data]
            except Exception:
                pass
    
    def _save_state(self) -> None:
        """Persist state to disk."""
        state_file = self.data_dir / "risk_state.json"
        state = {
            "peak_equity": self._peak_equity,
            "current_equity": self._current_equity,
            "circuit_breaker_active": self._circuit_breaker_active,
            "circuit_breaker_reason": self._circuit_breaker_reason,
            "circuit_breaker_triggered_at": self._circuit_breaker_triggered_at,
            "consecutive_losses": self._consecutive_losses,
            "updated_at": time.time(),
        }
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        
        trades_file = self.data_dir / "trades.json"
        with open(trades_file, "w") as f:
            json.dump([t.to_dict() for t in self._trades], f, indent=2)
    
    def update_equity(self, equity: float) -> Dict[str, Any]:
        """
        Update current equity and check for drawdown.
        
        Args:
            equity: Current portfolio equity
        
        Returns:
            Status dict with drawdown info
        """
        self._current_equity = equity
        
        # Update peak
        if equity > self._peak_equity:
            self._peak_equity = equity
        
        # Calculate drawdown
        drawdown = 0.0
        if self._peak_equity > 0:
            drawdown = ((self._peak_equity - equity) / self._peak_equity) * 100
        
        # Check circuit breaker
        if drawdown >= self.limits.max_drawdown_pct:
            if not self._circuit_breaker_active:  # Only set timestamp on initial trigger
                self._circuit_breaker_triggered_at = time.time()
            self._circuit_breaker_active = True
            self._circuit_breaker_reason = f"Max drawdown exceeded: {drawdown:.2f}%"
        
        self._save_state()
        
        return {
            "current_equity": equity,
            "peak_equity": self._peak_equity,
            "drawdown_pct": round(drawdown, 2),
            "max_drawdown_pct": self.limits.max_drawdown_pct,
            "circuit_breaker_active": self._circuit_breaker_active,
        }
    
    def can_trade(self) -> Dict[str, Any]:
        """
        Check if trading is allowed based on all risk limits.
        
        Returns:
            Dict with 'allowed' bool and reasons if not.
        """
        issues = []
        
        # Check circuit breaker with auto-recovery
        if self._circuit_breaker_active:
            recovery_hours = self.limits.circuit_breaker_recovery_hours
            hours_since_trigger = (time.time() - self._circuit_breaker_triggered_at) / 3600
            if hours_since_trigger >= recovery_hours:
                # Auto-recover after configured hours
                self._circuit_breaker_active = False
                self._circuit_breaker_reason = ""
                self._circuit_breaker_triggered_at = 0.0
                self._consecutive_losses = 0  # Reset consecutive losses too
                self._save_state()
            else:
                hours_remaining = recovery_hours - hours_since_trigger
                issues.append(f"Circuit breaker: {self._circuit_breaker_reason} (auto-reset in {hours_remaining:.1f}h)")
        
        # Check consecutive losses
        if self._consecutive_losses >= self.limits.max_consecutive_losses:
            issues.append(f"Consecutive losses: {self._consecutive_losses}/{self.limits.max_consecutive_losses}")
        
        # Check throttle (trades per hour)
        now = time.time()
        hour_ago = now - 3600
        recent_trades = [t for t in self._trade_times if t > hour_ago]
        if len(recent_trades) >= self.limits.max_trades_per_hour:
            issues.append(f"Throttle: {len(recent_trades)}/{self.limits.max_trades_per_hour} trades in last hour")
        
        # Check open positions
        open_positions = [t for t in self._trades if t.status == "OPEN"]
        if len(open_positions) >= self.limits.max_open_positions:
            issues.append(f"Max positions: {len(open_positions)}/{self.limits.max_open_positions}")
        
        # Check daily loss
        today = date.today().isoformat()
        daily_pnl = sum(
            t.pnl for t in self._trades
            if datetime.fromtimestamp(t.timestamp).date().isoformat() == today
            and t.status != "OPEN"
        )
        if self._current_equity > 0:
            daily_loss_pct = abs(min(0, daily_pnl)) / self._current_equity * 100
            if daily_loss_pct >= self.limits.max_daily_loss_pct:
                issues.append(f"Daily loss limit: {daily_loss_pct:.2f}%/{self.limits.max_daily_loss_pct}%")
        
        return {
            "allowed": len(issues) == 0,
            "issues": issues,
            "recent_trades_hour": len(recent_trades),
            "open_positions": len(open_positions),
        }
    
    def record_trade(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy: str = "manual"
    ) -> Trade:
        """
        Record a new trade.
        
        Returns:
            The created Trade object
        """
        trade_id = f"{symbol}_{int(time.time() * 1000)}"
        
        trade = Trade(
            id=trade_id,
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
        )
        
        self._trades.append(trade)
        self._trade_times.append(time.time())
        self._save_state()
        
        return trade
    
    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        reason: str = "CLOSED"
    ) -> Optional[Trade]:
        """
        Close an existing trade and calculate P&L.
        
        Args:
            trade_id: ID of trade to close
            exit_price: Exit price
            reason: CLOSED, STOPPED_OUT, TOOK_PROFIT
        
        Returns:
            Updated Trade or None if not found
        """
        for trade in self._trades:
            if trade.id == trade_id and trade.status == "OPEN":
                trade.exit_price = exit_price
                trade.exit_timestamp = time.time()
                trade.status = reason
                
                # Calculate P&L
                if trade.action == "BUY":
                    trade.pnl = (exit_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.quantity
                
                trade.pnl_pct = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                
                # Track consecutive losses for circuit breaker
                if trade.pnl < 0:
                    self._consecutive_losses += 1
                    if self._consecutive_losses >= self.limits.max_consecutive_losses:
                        self._circuit_breaker_active = True
                        self._circuit_breaker_triggered_at = time.time()
                        self._circuit_breaker_reason = f"Consecutive losses: {self._consecutive_losses}"
                else:
                    self._consecutive_losses = 0  # Reset on winning trade
                
                self._save_state()
                return trade
        
        return None
    
    def check_stops(
        self,
        current_prices: Dict[str, float],
        *,
        ignore_strategies: Optional[Iterable[str]] = None,
    ) -> List[Trade]:
        """
        Check all open trades against current prices for stop-loss/take-profit.
        
        Args:
            current_prices: Dict of symbol -> current price
        
        Returns:
            List of trades that should be closed
        """
        to_close = []
        
        ignore = {s.lower() for s in ignore_strategies or [] if s}
        for trade in self._trades:
            if trade.status != "OPEN":
                continue

            if trade.strategy and trade.strategy.lower() in ignore:
                continue
            
            price = current_prices.get(trade.symbol)
            if price is None:
                continue
            
            # Check stop-loss
            if trade.stop_loss is not None:
                if trade.action == "BUY" and price <= trade.stop_loss:
                    to_close.append((trade, price, "STOPPED_OUT"))
                elif trade.action == "SELL" and price >= trade.stop_loss:
                    to_close.append((trade, price, "STOPPED_OUT"))
            
            # Check take-profit
            if trade.take_profit is not None:
                if trade.action == "BUY" and price >= trade.take_profit:
                    to_close.append((trade, price, "TOOK_PROFIT"))
                elif trade.action == "SELL" and price <= trade.take_profit:
                    to_close.append((trade, price, "TOOK_PROFIT"))
        
        # Close triggered trades
        closed = []
        for trade, price, reason in to_close:
            result = self.close_trade(trade.id, price, reason)
            if result:
                closed.append(result)
        
        return closed
    
    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker (use with caution)."""
        self._circuit_breaker_active = False
        self._circuit_breaker_reason = ""
        self._save_state()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive trading statistics."""
        closed_trades = [t for t in self._trades if t.status != "OPEN"]
        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        
        win_rate = len(winning) / len(closed_trades) if closed_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            "total_trades": len(self._trades),
            "open_trades": len([t for t in self._trades if t.status == "OPEN"]),
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate * 100, 2),
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
            "peak_equity": self._peak_equity,
            "current_equity": self._current_equity,
            "circuit_breaker_active": self._circuit_breaker_active,
        }
    
    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades."""
        return [t.to_dict() for t in self._trades if t.status == "OPEN"]


# ============================================================================
# Convenience functions
# ============================================================================

_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> RiskManager:
    """Get or create the global risk manager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager


def calculate_position(
    capital: float,
    entry: float,
    stop_loss: float,
    risk_pct: float = 2.0
) -> Dict[str, float]:
    """Convenience function for position sizing."""
    return get_risk_manager().sizer.calculate_position(capital, entry, stop_loss, risk_pct)


def can_trade() -> Dict[str, Any]:
    """Convenience function to check if trading is allowed."""
    return get_risk_manager().can_trade()


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Life OS Risk Manager")
    parser.add_argument("--stats", action="store_true", help="Show trading stats")
    parser.add_argument("--can-trade", action="store_true", help="Check if can trade")
    parser.add_argument("--position", nargs=3, metavar=("CAPITAL", "ENTRY", "STOP"),
                        help="Calculate position size")
    parser.add_argument("--reset-cb", action="store_true", help="Reset circuit breaker")
    
    args = parser.parse_args()
    
    rm = get_risk_manager()
    
    if args.stats:
        print(json.dumps(rm.get_stats(), indent=2))
    elif args.can_trade:
        print(json.dumps(rm.can_trade(), indent=2))
    elif args.position:
        capital, entry, stop = map(float, args.position)
        result = rm.sizer.calculate_position(capital, entry, stop)
        print(json.dumps(result, indent=2))
    elif args.reset_cb:
        rm.reset_circuit_breaker()
        print("Circuit breaker reset.")
    else:
        print("=== Risk Manager Demo ===")
        print("\nLimits:", json.dumps(rm.limits.__dict__, indent=2))
        print("\nCan Trade:", json.dumps(rm.can_trade(), indent=2))
        print("\nPosition sizing (10000 capital, 100 entry, 95 stop):")
        print(json.dumps(rm.sizer.calculate_position(10000, 100, 95), indent=2))
        print("\nStop/Take calculation (entry=100, LONG):")
        print(json.dumps(rm.sizer.calculate_stop_take(100, "LONG"), indent=2))
