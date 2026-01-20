"""
Portfolio Analytics - Advanced metrics and tracking for trading positions.

Features:
- Total portfolio value tracking
- P&L by token
- Win/loss ratio
- Average hold time
- Best/worst performers
- Historical performance
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class TokenPerformance:
    """Performance metrics for a specific token."""
    token_symbol: str
    token_mint: str
    total_positions: int
    open_positions: int
    closed_positions: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_usd: float
    avg_pnl_usd: float
    avg_pnl_pct: float
    best_pnl_pct: float
    worst_pnl_pct: float
    avg_hold_time_hours: float
    total_invested_usd: float
    current_value_usd: float
    unrealized_pnl_usd: float


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio state."""
    timestamp: str
    total_value_usd: float
    total_invested_usd: float
    unrealized_pnl_usd: float
    unrealized_pnl_pct: float
    realized_pnl_usd: float
    open_positions: int
    position_count_by_status: Dict[str, int]


@dataclass
class PerformanceMetrics:
    """Overall portfolio performance metrics."""
    total_positions: int
    open_positions: int
    closed_positions: int
    total_wins: int
    total_losses: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float  # Total wins / Total losses
    avg_hold_time_hours: float
    total_realized_pnl_usd: float
    total_unrealized_pnl_usd: float
    total_pnl_usd: float
    best_position: Optional[Dict[str, Any]]
    worst_position: Optional[Dict[str, Any]]
    current_streak: int  # Positive = wins, negative = losses
    longest_winning_streak: int
    longest_losing_streak: int


class PortfolioAnalytics:
    """
    Advanced analytics for trading portfolio.

    Integrates with existing treasury positions from .positions.json
    and scorekeeper data.

    Usage:
        analytics = PortfolioAnalytics()

        # Get overall metrics
        metrics = analytics.get_performance_metrics()

        # Get per-token breakdown
        token_perf = analytics.get_token_performance()

        # Get best/worst performers
        best, worst = analytics.get_top_performers(limit=5)

        # Get portfolio value over time
        history = analytics.get_portfolio_history(days=30)
    """

    def __init__(
        self,
        positions_file: Optional[Path] = None,
        scorekeeper_file: Optional[Path] = None
    ):
        """Initialize analytics with data sources."""
        from pathlib import Path
        import os

        # Default paths match existing treasury structure
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        self.positions_file = positions_file or Path("bots/treasury/.positions.json")
        self.scorekeeper_file = scorekeeper_file or data_dir / "treasury_scorekeeper.json"

        self.positions: List[Dict] = []
        self.closed_positions: List[Dict] = []

        self._load_data()

    def _load_data(self):
        """Load position data from JSON files."""
        # Load current positions
        if self.positions_file.exists():
            try:
                with open(self.positions_file) as f:
                    self.positions = json.load(f)
                logger.info(f"Loaded {len(self.positions)} positions")
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")
                self.positions = []

        # Load scorekeeper data (has historical closed positions)
        if self.scorekeeper_file.exists():
            try:
                with open(self.scorekeeper_file) as f:
                    data = json.load(f)
                    # Scorekeeper stores closed positions in trade_history
                    self.closed_positions = data.get("trade_history", [])
                logger.info(f"Loaded {len(self.closed_positions)} closed positions")
            except Exception as e:
                logger.error(f"Failed to load scorekeeper: {e}")
                self.closed_positions = []

    def reload(self):
        """Reload data from disk."""
        self._load_data()

    def get_all_positions(self) -> List[Dict]:
        """Get all positions (open + closed)."""
        return self.positions + self.closed_positions

    def get_portfolio_value(self) -> Tuple[float, float, float]:
        """
        Calculate current portfolio value.

        Returns:
            (total_value_usd, total_invested_usd, unrealized_pnl_usd)
        """
        total_value = 0.0
        total_invested = 0.0

        for pos in self.positions:
            if pos.get("status") == "OPEN":
                # Current value based on current price
                amount = pos.get("amount", 0)
                current_price = pos.get("current_price", pos.get("entry_price", 0))
                total_value += amount * current_price

                # Invested amount based on entry
                entry_price = pos.get("entry_price", 0)
                total_invested += amount * entry_price

        unrealized_pnl = total_value - total_invested
        return total_value, total_invested, unrealized_pnl

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate overall portfolio performance metrics."""
        all_positions = self.get_all_positions()

        if not all_positions:
            return PerformanceMetrics(
                total_positions=0,
                open_positions=0,
                closed_positions=0,
                total_wins=0,
                total_losses=0,
                win_rate=0.0,
                avg_win_pct=0.0,
                avg_loss_pct=0.0,
                profit_factor=0.0,
                avg_hold_time_hours=0.0,
                total_realized_pnl_usd=0.0,
                total_unrealized_pnl_usd=0.0,
                total_pnl_usd=0.0,
                best_position=None,
                worst_position=None,
                current_streak=0,
                longest_winning_streak=0,
                longest_losing_streak=0
            )

        # Categorize positions
        open_pos = [p for p in all_positions if p.get("status") == "OPEN"]
        closed_pos = [p for p in all_positions if p.get("status") != "OPEN"]

        # Win/loss tracking
        wins = [p for p in closed_pos if p.get("pnl_usd", 0) > 0]
        losses = [p for p in closed_pos if p.get("pnl_usd", 0) <= 0]

        win_rate = len(wins) / len(closed_pos) * 100 if closed_pos else 0

        # Average win/loss percentages
        avg_win_pct = statistics.mean([p.get("pnl_pct", 0) for p in wins]) if wins else 0
        avg_loss_pct = statistics.mean([p.get("pnl_pct", 0) for p in losses]) if losses else 0

        # Profit factor
        total_wins_usd = sum(p.get("pnl_usd", 0) for p in wins)
        total_losses_usd = abs(sum(p.get("pnl_usd", 0) for p in losses))
        profit_factor = total_wins_usd / total_losses_usd if total_losses_usd > 0 else 0

        # Hold time calculation
        hold_times = []
        for p in closed_pos:
            if p.get("opened_at") and p.get("closed_at"):
                try:
                    opened = datetime.fromisoformat(p["opened_at"].replace('Z', '+00:00'))
                    closed = datetime.fromisoformat(p["closed_at"].replace('Z', '+00:00'))
                    hold_time = (closed - opened).total_seconds() / 3600
                    hold_times.append(hold_time)
                except Exception:
                    pass

        avg_hold_time = statistics.mean(hold_times) if hold_times else 0

        # Realized and unrealized PnL
        total_realized_pnl = sum(p.get("pnl_usd", 0) for p in closed_pos)
        total_unrealized_pnl = sum(p.get("pnl_usd", 0) for p in open_pos)
        total_pnl = total_realized_pnl + total_unrealized_pnl

        # Best and worst positions
        sorted_by_pnl = sorted(all_positions, key=lambda p: p.get("pnl_pct", 0), reverse=True)
        best_pos = sorted_by_pnl[0] if sorted_by_pnl else None
        worst_pos = sorted_by_pnl[-1] if sorted_by_pnl else None

        # Streak calculation
        current_streak = 0
        longest_winning = 0
        longest_losing = 0
        current_win_streak = 0
        current_loss_streak = 0

        # Sort by close time for streak calculation
        closed_sorted = sorted(
            closed_pos,
            key=lambda p: p.get("closed_at", ""),
            reverse=False
        )

        for p in closed_sorted:
            pnl = p.get("pnl_usd", 0)
            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                longest_winning = max(longest_winning, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                longest_losing = max(longest_losing, current_loss_streak)

        # Current streak is the last active streak
        current_streak = current_win_streak if current_win_streak > 0 else -current_loss_streak

        return PerformanceMetrics(
            total_positions=len(all_positions),
            open_positions=len(open_pos),
            closed_positions=len(closed_pos),
            total_wins=len(wins),
            total_losses=len(losses),
            win_rate=win_rate,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            profit_factor=profit_factor,
            avg_hold_time_hours=avg_hold_time,
            total_realized_pnl_usd=total_realized_pnl,
            total_unrealized_pnl_usd=total_unrealized_pnl,
            total_pnl_usd=total_pnl,
            best_position=best_pos,
            worst_position=worst_pos,
            current_streak=current_streak,
            longest_winning_streak=longest_winning,
            longest_losing_streak=longest_losing
        )

    def get_token_performance(self) -> List[TokenPerformance]:
        """Get performance breakdown by token."""
        all_positions = self.get_all_positions()

        # Group by token
        by_token: Dict[str, List[Dict]] = defaultdict(list)
        for p in all_positions:
            token_symbol = p.get("token_symbol", "UNKNOWN")
            by_token[token_symbol].append(p)

        results = []

        for token_symbol, positions in by_token.items():
            open_pos = [p for p in positions if p.get("status") == "OPEN"]
            closed_pos = [p for p in positions if p.get("status") != "OPEN"]

            wins = [p for p in closed_pos if p.get("pnl_usd", 0) > 0]
            losses = [p for p in closed_pos if p.get("pnl_usd", 0) <= 0]

            win_rate = len(wins) / len(closed_pos) * 100 if closed_pos else 0

            total_pnl = sum(p.get("pnl_usd", 0) for p in positions)
            avg_pnl_usd = statistics.mean([p.get("pnl_usd", 0) for p in closed_pos]) if closed_pos else 0
            avg_pnl_pct = statistics.mean([p.get("pnl_pct", 0) for p in closed_pos]) if closed_pos else 0

            pnl_pcts = [p.get("pnl_pct", 0) for p in closed_pos]
            best_pnl = max(pnl_pcts) if pnl_pcts else 0
            worst_pnl = min(pnl_pcts) if pnl_pcts else 0

            # Calculate hold times
            hold_times = []
            for p in closed_pos:
                if p.get("opened_at") and p.get("closed_at"):
                    try:
                        opened = datetime.fromisoformat(p["opened_at"].replace('Z', '+00:00'))
                        closed = datetime.fromisoformat(p["closed_at"].replace('Z', '+00:00'))
                        hold_time = (closed - opened).total_seconds() / 3600
                        hold_times.append(hold_time)
                    except Exception:
                        pass

            avg_hold_time = statistics.mean(hold_times) if hold_times else 0

            # Calculate invested vs current value
            total_invested = sum(
                p.get("amount", 0) * p.get("entry_price", 0)
                for p in open_pos
            )

            current_value = sum(
                p.get("amount", 0) * p.get("current_price", p.get("entry_price", 0))
                for p in open_pos
            )

            unrealized_pnl = current_value - total_invested

            # Get token mint (use first position's mint)
            token_mint = positions[0].get("token_mint", "") if positions else ""

            results.append(TokenPerformance(
                token_symbol=token_symbol,
                token_mint=token_mint,
                total_positions=len(positions),
                open_positions=len(open_pos),
                closed_positions=len(closed_pos),
                wins=len(wins),
                losses=len(losses),
                win_rate=win_rate,
                total_pnl_usd=total_pnl,
                avg_pnl_usd=avg_pnl_usd,
                avg_pnl_pct=avg_pnl_pct,
                best_pnl_pct=best_pnl,
                worst_pnl_pct=worst_pnl,
                avg_hold_time_hours=avg_hold_time,
                total_invested_usd=total_invested,
                current_value_usd=current_value,
                unrealized_pnl_usd=unrealized_pnl
            ))

        # Sort by total PnL descending
        results.sort(key=lambda x: x.total_pnl_usd, reverse=True)

        return results

    def get_top_performers(
        self,
        limit: int = 5,
        metric: str = "pnl_pct"
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get top and bottom performing positions.

        Args:
            limit: Number of positions to return
            metric: Metric to sort by (pnl_pct, pnl_usd, hold_time)

        Returns:
            (best_positions, worst_positions)
        """
        all_positions = self.get_all_positions()

        # Only consider positions with actual PnL (closed or open with unrealized)
        positions_with_pnl = [
            p for p in all_positions
            if p.get(metric, 0) != 0
        ]

        # Sort by metric
        sorted_positions = sorted(
            positions_with_pnl,
            key=lambda p: p.get(metric, 0),
            reverse=True
        )

        best = sorted_positions[:limit]
        worst = sorted_positions[-limit:][::-1]  # Reverse to show worst first

        return best, worst

    def get_portfolio_history(self, days: int = 30) -> List[PortfolioSnapshot]:
        """
        Get portfolio value history over time.

        This is a simplified version that creates snapshots based on
        position open/close events. For true time-series tracking,
        integrate with a time-series database.

        Args:
            days: Number of days of history

        Returns:
            List of portfolio snapshots
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all position events (opens and closes) in time range
        events = []

        for p in self.get_all_positions():
            if p.get("opened_at"):
                try:
                    opened_time = datetime.fromisoformat(p["opened_at"].replace('Z', '+00:00'))
                    if opened_time > cutoff:
                        events.append(("open", opened_time, p))
                except Exception:
                    pass

            if p.get("closed_at"):
                try:
                    closed_time = datetime.fromisoformat(p["closed_at"].replace('Z', '+00:00'))
                    if closed_time > cutoff:
                        events.append(("close", closed_time, p))
                except Exception:
                    pass

        # Sort events by time
        events.sort(key=lambda x: x[1])

        # Create snapshots at each event
        snapshots = []

        # Current state
        current_value, current_invested, unrealized_pnl = self.get_portfolio_value()
        realized_pnl = sum(
            p.get("pnl_usd", 0)
            for p in self.closed_positions
        )

        # Add current snapshot
        snapshots.append(PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_value_usd=current_value,
            total_invested_usd=current_invested,
            unrealized_pnl_usd=unrealized_pnl,
            unrealized_pnl_pct=(unrealized_pnl / current_invested * 100) if current_invested > 0 else 0,
            realized_pnl_usd=realized_pnl,
            open_positions=len([p for p in self.positions if p.get("status") == "OPEN"]),
            position_count_by_status={
                "OPEN": len([p for p in self.positions if p.get("status") == "OPEN"]),
                "CLOSED": len(self.closed_positions)
            }
        ))

        return snapshots

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get a comprehensive summary of portfolio analytics."""
        metrics = self.get_performance_metrics()
        current_value, invested, unrealized = self.get_portfolio_value()
        token_perf = self.get_token_performance()
        best, worst = self.get_top_performers(limit=3)

        return {
            "portfolio_value": {
                "current_usd": current_value,
                "invested_usd": invested,
                "unrealized_pnl_usd": unrealized,
                "unrealized_pnl_pct": (unrealized / invested * 100) if invested > 0 else 0
            },
            "performance": {
                "total_positions": metrics.total_positions,
                "open_positions": metrics.open_positions,
                "closed_positions": metrics.closed_positions,
                "win_rate": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "total_pnl_usd": metrics.total_pnl_usd,
                "realized_pnl_usd": metrics.total_realized_pnl_usd,
                "unrealized_pnl_usd": metrics.total_unrealized_pnl_usd
            },
            "streaks": {
                "current": metrics.current_streak,
                "longest_winning": metrics.longest_winning_streak,
                "longest_losing": metrics.longest_losing_streak
            },
            "tokens": {
                "total_unique_tokens": len(token_perf),
                "top_performer": token_perf[0].token_symbol if token_perf else None,
                "top_performer_pnl_usd": token_perf[0].total_pnl_usd if token_perf else 0
            },
            "best_position": best[0] if best else None,
            "worst_position": worst[0] if worst else None,
            "avg_hold_time_hours": metrics.avg_hold_time_hours
        }


# Singleton instance
_analytics: Optional[PortfolioAnalytics] = None


def get_portfolio_analytics() -> PortfolioAnalytics:
    """Get singleton portfolio analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = PortfolioAnalytics()
    return _analytics
