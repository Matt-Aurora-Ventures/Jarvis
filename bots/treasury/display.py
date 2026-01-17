"""
Treasury Display System - Beautiful portfolio visualization with real-time P&L tracking.

Displays:
- Open positions with entry price, current price, P&L
- Portfolio performance metrics (Sharpe ratio, max drawdown, win rate)
- Win/loss streaks with direction tracking
- Sector exposure visualization
- Closed trades history
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics
import json
from pathlib import Path
import sys
import os

# Fix Windows encoding for emoji
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@dataclass
class Position:
    """Open position tracking."""
    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    entry_time: datetime
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100
    
    @property
    def position_value(self) -> float:
        """Current position value."""
        return self.current_price * self.quantity
    
    @property
    def distance_to_tp(self) -> Optional[float]:
        """Percentage distance to take profit."""
        if self.take_profit is None:
            return None
        return ((self.take_profit - self.current_price) / self.current_price) * 100 if self.current_price > 0 else None
    
    @property
    def distance_to_sl(self) -> Optional[float]:
        """Percentage distance to stop loss."""
        if self.stop_loss is None:
            return None
        return ((self.current_price - self.stop_loss) / self.current_price) * 100 if self.current_price > 0 else None
    
    @property
    def status_emoji(self) -> str:
        """Get status emoji based on P&L."""
        if self.unrealized_pnl_pct >= 50:
            return "🟢"  # 50%+ profit
        elif self.unrealized_pnl_pct >= 20:
            return "🟡"  # 20-50% profit
        elif self.unrealized_pnl_pct >= 5:
            return "🟠"  # 5-20% profit
        elif self.unrealized_pnl_pct >= 0:
            return "⚪"  # Small profit or breakeven
        elif self.unrealized_pnl_pct > -20:
            return "🔴"  # -20% to 0
        else:
            return "💀"  # < -20%
    
    @property
    def tp_sl_status(self) -> str:
        """Get TP/SL status emoji."""
        if self.distance_to_tp is not None and self.distance_to_tp <= 5:
            return "🎯"  # Close to TP
        if self.distance_to_sl is not None and self.distance_to_sl <= 5:
            return "⚠️"  # Close to SL
        return "  "  # Normal


@dataclass
class ClosedTrade:
    """Closed trade history entry."""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    reason: str  # "TP", "SL", "Manual"
    
    @property
    def realized_pnl_pct(self) -> float:
        """Calculate realized P&L percentage."""
        if self.entry_price == 0:
            return 0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100
    
    @property
    def status(self) -> str:
        """Get trade outcome indicator."""
        return "✅" if self.realized_pnl > 0 else "❌"
    
    @property
    def duration(self) -> str:
        """Get trade duration in human-readable format."""
        delta = self.exit_time - self.entry_time
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return f"{int(delta.total_seconds() / 60)}m"
        elif hours < 24:
            return f"{int(hours)}h"
        else:
            return f"{int(hours / 24)}d"


class TreasuryDisplay:
    """Generate beautiful treasury displays with real portfolio data."""
    
    def __init__(self, positions: List[Position] = None, closed_trades: List[ClosedTrade] = None):
        """Initialize treasury display."""
        self.positions = positions or []
        self.closed_trades = closed_trades or []
    
    # ==================== Calculations ====================
    
    def calculate_total_portfolio_value(self) -> float:
        """Calculate total portfolio value (open positions only)."""
        return sum(pos.position_value for pos in self.positions)
    
    def calculate_total_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L across all open positions."""
        return sum(pos.unrealized_pnl for pos in self.positions)
    
    def calculate_total_realized_pnl(self) -> float:
        """Calculate total realized P&L from closed trades."""
        return sum(trade.realized_pnl for trade in self.closed_trades)
    
    def calculate_total_pnl(self) -> float:
        """Calculate total P&L (realized + unrealized)."""
        return self.calculate_total_realized_pnl() + self.calculate_total_unrealized_pnl()
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate percentage from closed trades."""
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for trade in self.closed_trades if trade.realized_pnl > 0)
        return (wins / len(self.closed_trades)) * 100
    
    def calculate_profit_factor(self) -> float:
        """Calculate profit factor (total wins / total losses)."""
        wins = sum(trade.realized_pnl for trade in self.closed_trades if trade.realized_pnl > 0)
        losses = abs(sum(trade.realized_pnl for trade in self.closed_trades if trade.realized_pnl < 0))
        if losses == 0:
            return wins if wins > 0 else 1.0
        return wins / losses if wins > 0 else 0.0
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio from closed trades."""
        if len(self.closed_trades) < 2:
            return 0.0
        
        pnl_returns = [trade.realized_pnl_pct for trade in self.closed_trades]
        avg_return = statistics.mean(pnl_returns)
        std_dev = statistics.stdev(pnl_returns) if len(pnl_returns) > 1 else 0
        
        if std_dev == 0:
            return 0.0
        
        # Annualize Sharpe ratio (assuming 365 trades per year for simplicity)
        return ((avg_return - (risk_free_rate * 100)) / std_dev) * (365 ** 0.5)
    
    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from cumulative returns."""
        if not self.closed_trades:
            return 0.0

        cumulative_pnl = []
        running_total = 0
        for trade in sorted(self.closed_trades, key=lambda t: t.exit_time):
            running_total += trade.realized_pnl
            cumulative_pnl.append(running_total)

        if not cumulative_pnl or len(cumulative_pnl) < 2:
            return 0.0

        peak = cumulative_pnl[0]
        max_dd = 0.0

        for value in cumulative_pnl:
            if value > peak:
                peak = value

            if peak != 0:
                drawdown = ((peak - value) / abs(peak)) * 100
                max_dd = max(max_dd, drawdown)

        return max_dd
    
    def calculate_streaks(self) -> Dict[str, any]:
        """Calculate current, best, and worst win/loss streaks."""
        streaks = {
            "current_streak": 0,
            "current_direction": None,  # "win" or "loss"
            "best_win_streak": 0,
            "best_loss_streak": 0,
            "worst_win_streak": 0,
            "worst_loss_streak": 0,
        }
        
        if not self.closed_trades:
            return streaks
        
        current_streak = 0
        current_direction = None
        win_streaks = []
        loss_streaks = []
        
        for trade in sorted(self.closed_trades, key=lambda t: t.exit_time):
            is_win = trade.realized_pnl > 0
            direction = "win" if is_win else "loss"
            
            if direction == current_direction:
                current_streak += 1
            else:
                # Streak ended
                if current_direction and current_streak > 0:
                    if current_direction == "win":
                        win_streaks.append(current_streak)
                    else:
                        loss_streaks.append(current_streak)
                
                current_streak = 1
                current_direction = direction
        
        # Record final streak
        if current_streak > 0 and current_direction:
            if current_direction == "win":
                win_streaks.append(current_streak)
            else:
                loss_streaks.append(current_streak)
        
        # Update streaks
        if current_direction:
            streaks["current_streak"] = current_streak
            streaks["current_direction"] = current_direction
        
        if win_streaks:
            streaks["best_win_streak"] = max(win_streaks)
            streaks["worst_win_streak"] = min(win_streaks)
        
        if loss_streaks:
            streaks["best_loss_streak"] = max(loss_streaks)
            streaks["worst_loss_streak"] = min(loss_streaks)
        
        return streaks
    
    def get_sector_breakdown(self) -> Dict[str, Tuple[int, float]]:
        """Get sector breakdown: {sector: (count, pct_of_portfolio)}."""
        try:
            from core.assets import AssetRegistry
        except ImportError:
            # Fallback if AssetRegistry not available
            return {"Unknown": (len(self.positions), 100.0 if self.positions else 0.0)}

        sector_values = defaultdict(float)
        sector_counts = defaultdict(int)
        total_value = self.calculate_total_portfolio_value()

        for pos in self.positions:
            asset = AssetRegistry.get_asset(pos.symbol)
            if asset:
                sector_values[asset.sector] += pos.position_value
                sector_counts[asset.sector] += 1
            else:
                sector_values["Uncategorized"] += pos.position_value
                sector_counts["Uncategorized"] += 1

        if total_value == 0:
            return {sector: (count, 0) for sector, count in sector_counts.items()}

        return {
            sector: (sector_counts[sector], (value / total_value * 100))
            for sector, value in sector_values.items()
        }

    @classmethod
    def from_json_files(cls, positions_file: str, trades_file: str) -> 'TreasuryDisplay':
        """Load treasury data from JSON files."""
        positions = []
        closed_trades = []

        # Load positions
        if Path(positions_file).exists():
            with open(positions_file, 'r') as f:
                pos_data = json.load(f)
                for p in pos_data:
                    if p.get('status') == 'OPEN':
                        positions.append(Position(
                            symbol=p.get('token_symbol', 'UNKNOWN'),
                            entry_price=float(p.get('entry_price', 0)),
                            current_price=float(p.get('current_price', 0)),
                            quantity=float(p.get('amount', 0)),
                            entry_time=datetime.fromisoformat(p.get('opened_at', datetime.now().isoformat())),
                            take_profit=float(p.get('take_profit_price')) if p.get('take_profit_price') else None,
                            stop_loss=float(p.get('stop_loss_price')) if p.get('stop_loss_price') else None,
                        ))

        # Load trades
        if Path(trades_file).exists():
            with open(trades_file, 'r') as f:
                trade_data = json.load(f)
                for t in trade_data:
                    if t.get('status') == 'CLOSED':
                        exit_time_str = t.get('closed_at')
                        if exit_time_str:
                            try:
                                exit_time = datetime.fromisoformat(exit_time_str)
                            except (ValueError, TypeError):
                                exit_time = datetime.now()
                        else:
                            exit_time = datetime.now()

                        closed_trades.append(ClosedTrade(
                            symbol=t.get('token_symbol', 'UNKNOWN'),
                            entry_price=float(t.get('entry_price', 0)),
                            exit_price=float(t.get('exit_price', 0)),
                            quantity=float(t.get('amount', 0)),
                            entry_time=datetime.fromisoformat(t.get('opened_at', datetime.now().isoformat())),
                            exit_time=exit_time,
                            realized_pnl=float(t.get('pnl_usd', 0)),
                            reason=("TP" if t.get('pnl_pct', 0) > 0 else "SL") if t.get('pnl_pct') != 0 else "Manual",
                        ))

        return cls(positions, closed_trades)
    
    # ==================== Display Builders ====================
    
    def _build_portfolio_section(self) -> str:
        """Build open positions portfolio section."""
        if not self.positions:
            return "📊 PORTFOLIO (Empty)\n"
        
        lines = ["📊 PORTFOLIO"]
        lines.append("─" * 120)
        
        # Header
        lines.append(f"{'Symbol':<10} {'Entry':<12} {'Current':<12} {'Qty':<12} {'PnL':<15} {'PnL %':<10} {'TP':<10} {'SL':<10}")
        lines.append("─" * 120)
        
        # Positions sorted by P&L
        for pos in sorted(self.positions, key=lambda p: p.unrealized_pnl, reverse=True):
            tp_dist = f"{pos.distance_to_tp:.1f}%" if pos.distance_to_tp else "N/A"
            sl_dist = f"{pos.distance_to_sl:.1f}%" if pos.distance_to_sl else "N/A"
            
            pnl_str = f"${pos.unrealized_pnl:,.2f}"
            pnl_pct_str = f"{pos.unrealized_pnl_pct:+.2f}%"
            
            lines.append(
                f"{pos.symbol:<10} "
                f"${pos.entry_price:<11,.4f} "
                f"${pos.current_price:<11,.4f} "
                f"{pos.quantity:<12.4f} "
                f"{pnl_str:<15} "
                f"{pnl_pct_str:<10} "
                f"{tp_dist:<10} "
                f"{sl_dist:<10} "
                f"{pos.status_emoji} {pos.tp_sl_status}"
            )
        
        lines.append("─" * 120)
        
        # Summary
        total_value = self.calculate_total_portfolio_value()
        total_unrealized = self.calculate_total_unrealized_pnl()
        total_pnl_pct = (total_unrealized / total_value * 100) if total_value > 0 else 0
        
        lines.append(
            f"{'TOTAL':<10} "
            f"{'':12} "
            f"{'':12} "
            f"{len(self.positions):<12} "
            f"${total_unrealized:,.2f}{'':5} "
            f"{total_pnl_pct:+.2f}%"
        )
        
        return "\n".join(lines) + "\n"
    
    def _build_performance_section(self) -> str:
        """Build performance metrics section."""
        lines = ["📈 PERFORMANCE"]
        lines.append("─" * 80)
        
        total_pnl = self.calculate_total_pnl()
        realized_pnl = self.calculate_total_realized_pnl()
        unrealized_pnl = self.calculate_total_unrealized_pnl()
        win_rate = self.calculate_win_rate()
        profit_factor = self.calculate_profit_factor()
        sharpe = self.calculate_sharpe_ratio()
        max_dd = self.calculate_max_drawdown()
        
        lines.append(f"Total PnL:           ${total_pnl:>15,.2f}")
        lines.append(f"  Realized:          ${realized_pnl:>15,.2f}")
        lines.append(f"  Unrealized:        ${unrealized_pnl:>15,.2f}")
        lines.append("")
        lines.append(f"Win Rate:            {win_rate:>15.1f}%")
        lines.append(f"Profit Factor:       {profit_factor:>15.2f}x")
        lines.append(f"Sharpe Ratio:        {sharpe:>15.2f}")
        lines.append(f"Max Drawdown:        {max_dd:>15.2f}%")
        lines.append("")
        lines.append(f"Closed Trades:       {len(self.closed_trades):>15}")
        lines.append(f"Open Positions:      {len(self.positions):>15}")
        
        lines.append("─" * 80)
        
        return "\n".join(lines) + "\n"
    
    def _build_streaks_section(self) -> str:
        """Build win/loss streaks section."""
        lines = ["🎯 STREAKS"]
        lines.append("─" * 80)
        
        streaks = self.calculate_streaks()
        
        current = streaks["current_streak"]
        direction = streaks["current_direction"]
        current_str = f"{current} {direction.upper()}" if direction else "N/A"
        current_emoji = "🟢" if direction == "win" else "🔴" if direction == "loss" else "⚪"
        
        lines.append(f"Current:             {current_emoji} {current_str:<15}")
        lines.append(f"Best Win Streak:     {streaks['best_win_streak']:>15}")
        lines.append(f"Worst Win Streak:    {streaks['worst_win_streak']:>15}")
        lines.append(f"Best Loss Streak:    {streaks['best_loss_streak']:>15}")
        lines.append(f"Worst Loss Streak:   {streaks['worst_loss_streak']:>15}")
        
        lines.append("─" * 80)
        
        return "\n".join(lines) + "\n"
    
    def _build_sector_section(self) -> str:
        """Build sector exposure visualization."""
        lines = ["🏢 SECTOR EXPOSURE"]
        lines.append("─" * 80)
        
        sector_breakdown = self.get_sector_breakdown()
        
        if not sector_breakdown:
            lines.append("No open positions")
        else:
            for sector, (count, pct) in sorted(sector_breakdown.items(), key=lambda x: x[1][1], reverse=True):
                bar_length = int(pct / 2)  # 50% width = 50 chars
                bar = "█" * bar_length
                lines.append(f"{sector:<25} {pct:>6.1f}% │{bar}")
        
        lines.append("─" * 80)
        
        return "\n".join(lines) + "\n"
    
    def _build_recent_trades_section(self, limit: int = 10) -> str:
        """Build recent closed trades section."""
        lines = ["📋 RECENT TRADES (Last {})".format(min(limit, len(self.closed_trades)))]
        lines.append("─" * 100)
        
        if not self.closed_trades:
            lines.append("No closed trades")
        else:
            lines.append(f"{'Symbol':<10} {'Entry':<12} {'Exit':<12} {'PnL':<15} {'PnL %':<10} {'Reason':<10} {'Duration':<10}")
            lines.append("─" * 100)
            
            for trade in sorted(self.closed_trades, key=lambda t: t.exit_time, reverse=True)[:limit]:
                lines.append(
                    f"{trade.symbol:<10} "
                    f"${trade.entry_price:<11,.4f} "
                    f"${trade.exit_price:<11,.4f} "
                    f"${trade.realized_pnl:<14,.2f} "
                    f"{trade.realized_pnl_pct:+.2f}%{' ':>4} "
                    f"{trade.reason:<10} "
                    f"{trade.duration:<10} "
                    f"{trade.status}"
                )
            
            lines.append("─" * 100)
        
        return "\n".join(lines) + "\n"
    
    # ==================== Main Display ====================
    
    def generate_full_display(self, include_recent_trades: bool = True) -> str:
        """Generate complete treasury display."""
        output = []
        
        # Header with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output.append(f"\n💎 TREASURY DISPLAY - {timestamp}")
        output.append("=" * 120)
        output.append("")
        
        # Portfolio
        output.append(self._build_portfolio_section())
        
        # Performance
        output.append(self._build_performance_section())
        
        # Streaks
        output.append(self._build_streaks_section())
        
        # Sector Exposure
        output.append(self._build_sector_section())
        
        # Recent Trades
        if include_recent_trades:
            output.append(self._build_recent_trades_section())
        
        output.append("=" * 120)
        
        return "\n".join(output)
    
    def save_display(self, filepath: str) -> None:
        """Save display to file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.generate_full_display())
    
    def to_json(self) -> str:
        """Export portfolio data as JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "portfolio_value": self.calculate_total_portfolio_value(),
                "total_pnl": self.calculate_total_pnl(),
                "realized_pnl": self.calculate_total_realized_pnl(),
                "unrealized_pnl": self.calculate_total_unrealized_pnl(),
                "win_rate": self.calculate_win_rate(),
                "profit_factor": self.calculate_profit_factor(),
                "sharpe_ratio": self.calculate_sharpe_ratio(),
                "max_drawdown": self.calculate_max_drawdown(),
                "open_positions": len(self.positions),
                "closed_trades": len(self.closed_trades),
            },
            "streaks": self.calculate_streaks(),
            "sector_breakdown": {k: {"count": v[0], "pct": v[1]} for k, v in self.get_sector_breakdown().items()},
            "positions": [
                {
                    "symbol": p.symbol,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "quantity": p.quantity,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                    "distance_to_tp": p.distance_to_tp,
                    "distance_to_sl": p.distance_to_sl,
                }
                for p in self.positions
            ],
            "closed_trades": [
                {
                    "symbol": t.symbol,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "realized_pnl": t.realized_pnl,
                    "realized_pnl_pct": t.realized_pnl_pct,
                    "reason": t.reason,
                    "duration": t.duration,
                }
                for t in self.closed_trades
            ]
        }
        return json.dumps(data, indent=2, default=str)


__all__ = [
    'Position',
    'ClosedTrade',
    'TreasuryDisplay',
]


if __name__ == "__main__":
    # Load from actual JSON files
    jarvis_path = Path(__file__).parent.parent.parent
    positions_file = jarvis_path / "bots" / "treasury" / ".positions.json"
    trades_file = jarvis_path / "bots" / "treasury" / ".trade_history.json"

    print(f"Loading positions from: {positions_file}")
    print(f"Loading trades from: {trades_file}")
    print()

    display = TreasuryDisplay.from_json_files(str(positions_file), str(trades_file))
    print(display.generate_full_display())

    # Also save to file
    output_file = jarvis_path / "treasury_display.txt"
    display.save_display(str(output_file))
    print(f"\nDisplay saved to: {output_file}")
