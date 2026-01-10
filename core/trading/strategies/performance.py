"""
Strategy Performance Tracker
Prompt #83: Treasury Strategy Manager - Performance tracking and analytics

Tracks and analyzes trading strategy performance.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import statistics

logger = logging.getLogger("jarvis.strategies.performance")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class TradeRecord:
    """Record of a completed trade"""
    id: str
    strategy_name: str
    token_mint: str
    symbol: str

    # Entry
    entry_price: Decimal
    entry_time: datetime
    entry_amount_sol: Decimal

    # Exit
    exit_price: Decimal
    exit_time: datetime
    exit_amount_sol: Decimal

    # Result
    pnl_sol: Decimal
    pnl_pct: float
    hold_duration_seconds: int

    # Context
    signal_confidence: float
    exit_reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy"""
    strategy_name: str
    period: str  # "24h", "7d", "30d", "all"
    period_start: datetime
    period_end: datetime

    # Trade counts
    total_trades: int
    winning_trades: int
    losing_trades: int
    break_even_trades: int

    # Returns
    total_pnl_sol: Decimal
    gross_profit_sol: Decimal
    gross_loss_sol: Decimal
    avg_pnl_sol: Decimal
    avg_pnl_pct: float

    # Rates
    win_rate: float
    profit_factor: float  # gross_profit / gross_loss
    avg_win_sol: Decimal
    avg_loss_sol: Decimal
    largest_win_sol: Decimal
    largest_loss_sol: Decimal

    # Risk metrics
    sharpe_ratio: float
    max_drawdown_pct: float
    avg_hold_duration_seconds: float

    # Streaks
    current_streak: int  # + for wins, - for losses
    max_win_streak: int
    max_loss_streak: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy_name,
            "period": self.period,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl_sol": float(self.total_pnl_sol),
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "avg_hold_duration_seconds": self.avg_hold_duration_seconds,
            "current_streak": self.current_streak,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
        }


@dataclass
class StrategyRanking:
    """Ranking of strategies by performance"""
    strategy_name: str
    rank: int
    score: float  # Composite score
    sharpe_ratio: float
    total_pnl_sol: float
    win_rate: float
    trade_count: int


# =============================================================================
# PERFORMANCE TRACKER
# =============================================================================

class PerformanceTracker:
    """
    Tracks and analyzes trading strategy performance.

    Features:
    - Trade recording and history
    - Performance calculation by period
    - Strategy ranking
    - Drawdown tracking
    - Recommendations
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv(
            "STRATEGY_PERFORMANCE_DB",
            "data/strategy_performance.db"
        )
        self._init_database()

        # In-memory tracking
        self._equity_curve: Dict[str, List[tuple]] = {}  # strategy -> [(time, equity)]
        self._current_equity: Dict[str, Decimal] = {}

    def _init_database(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                symbol TEXT,
                entry_price REAL,
                entry_time TEXT,
                entry_amount_sol REAL,
                exit_price REAL,
                exit_time TEXT,
                exit_amount_sol REAL,
                pnl_sol REAL,
                pnl_pct REAL,
                hold_duration_seconds INTEGER,
                signal_confidence REAL,
                exit_reason TEXT,
                metadata_json TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_strategy
            ON trades(strategy_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_time
            ON trades(exit_time)
        """)

        # Daily performance snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                date TEXT NOT NULL,
                trades_count INTEGER,
                pnl_sol REAL,
                win_rate REAL,
                equity_sol REAL,
                UNIQUE(strategy_name, date)
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # TRADE RECORDING
    # =========================================================================

    async def record_trade(self, trade: TradeRecord):
        """Record a completed trade"""
        import json

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO trades
            (id, strategy_name, token_mint, symbol, entry_price, entry_time,
             entry_amount_sol, exit_price, exit_time, exit_amount_sol,
             pnl_sol, pnl_pct, hold_duration_seconds, signal_confidence,
             exit_reason, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.id,
            trade.strategy_name,
            trade.token_mint,
            trade.symbol,
            float(trade.entry_price),
            trade.entry_time.isoformat(),
            float(trade.entry_amount_sol),
            float(trade.exit_price),
            trade.exit_time.isoformat(),
            float(trade.exit_amount_sol),
            float(trade.pnl_sol),
            trade.pnl_pct,
            trade.hold_duration_seconds,
            trade.signal_confidence,
            trade.exit_reason,
            json.dumps(trade.metadata),
        ))

        conn.commit()
        conn.close()

        # Update equity curve
        self._update_equity(trade.strategy_name, trade.pnl_sol)

        logger.info(f"Recorded trade {trade.id} for {trade.strategy_name}: "
                   f"PnL={trade.pnl_sol:.4f} SOL ({trade.pnl_pct:.2f}%)")

    def _update_equity(self, strategy: str, pnl: Decimal):
        """Update equity curve"""
        current = self._current_equity.get(strategy, Decimal(0))
        new_equity = current + pnl
        self._current_equity[strategy] = new_equity

        if strategy not in self._equity_curve:
            self._equity_curve[strategy] = []
        self._equity_curve[strategy].append((datetime.now(timezone.utc), float(new_equity)))

    # =========================================================================
    # PERFORMANCE CALCULATION
    # =========================================================================

    async def get_performance(
        self,
        strategy_name: str,
        period: str = "30d",
    ) -> StrategyPerformance:
        """
        Calculate performance metrics for a strategy.

        Args:
            strategy_name: Strategy to analyze
            period: "24h", "7d", "30d", or "all"

        Returns:
            Performance metrics
        """
        # Calculate period bounds
        now = datetime.now(timezone.utc)
        if period == "24h":
            start = now - timedelta(hours=24)
        elif period == "7d":
            start = now - timedelta(days=7)
        elif period == "30d":
            start = now - timedelta(days=30)
        else:
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)

        # Fetch trades
        trades = await self._fetch_trades(strategy_name, start, now)

        if not trades:
            return self._empty_performance(strategy_name, period, start, now)

        # Calculate metrics
        return self._calculate_metrics(strategy_name, period, start, now, trades)

    async def _fetch_trades(
        self,
        strategy_name: str,
        start: datetime,
        end: datetime,
    ) -> List[TradeRecord]:
        """Fetch trades from database"""
        import json

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, strategy_name, token_mint, symbol, entry_price, entry_time,
                   entry_amount_sol, exit_price, exit_time, exit_amount_sol,
                   pnl_sol, pnl_pct, hold_duration_seconds, signal_confidence,
                   exit_reason, metadata_json
            FROM trades
            WHERE strategy_name = ?
              AND exit_time >= ?
              AND exit_time <= ?
            ORDER BY exit_time ASC
        """, (strategy_name, start.isoformat(), end.isoformat()))

        trades = []
        for row in cursor.fetchall():
            trades.append(TradeRecord(
                id=row[0],
                strategy_name=row[1],
                token_mint=row[2],
                symbol=row[3],
                entry_price=Decimal(str(row[4])),
                entry_time=datetime.fromisoformat(row[5]),
                entry_amount_sol=Decimal(str(row[6])),
                exit_price=Decimal(str(row[7])),
                exit_time=datetime.fromisoformat(row[8]),
                exit_amount_sol=Decimal(str(row[9])),
                pnl_sol=Decimal(str(row[10])),
                pnl_pct=row[11],
                hold_duration_seconds=row[12],
                signal_confidence=row[13],
                exit_reason=row[14],
                metadata=json.loads(row[15]) if row[15] else {},
            ))

        conn.close()
        return trades

    def _calculate_metrics(
        self,
        strategy_name: str,
        period: str,
        start: datetime,
        end: datetime,
        trades: List[TradeRecord],
    ) -> StrategyPerformance:
        """Calculate performance metrics from trades"""
        # Basic counts
        winning = [t for t in trades if t.pnl_sol > 0]
        losing = [t for t in trades if t.pnl_sol < 0]
        break_even = [t for t in trades if t.pnl_sol == 0]

        # P&L
        total_pnl = sum(t.pnl_sol for t in trades)
        gross_profit = sum(t.pnl_sol for t in winning)
        gross_loss = abs(sum(t.pnl_sol for t in losing))

        # Averages
        avg_pnl = total_pnl / len(trades) if trades else Decimal(0)
        avg_pnl_pct = statistics.mean(t.pnl_pct for t in trades) if trades else 0
        avg_win = gross_profit / len(winning) if winning else Decimal(0)
        avg_loss = gross_loss / len(losing) if losing else Decimal(0)

        # Win/loss
        win_rate = len(winning) / len(trades) if trades else 0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Extremes
        largest_win = max((t.pnl_sol for t in winning), default=Decimal(0))
        largest_loss = abs(min((t.pnl_sol for t in losing), default=Decimal(0)))

        # Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = [float(t.pnl_pct) for t in trades]
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        max_dd = self._calculate_max_drawdown(trades)

        # Hold duration
        avg_hold = statistics.mean(t.hold_duration_seconds for t in trades) if trades else 0

        # Streaks
        streaks = self._calculate_streaks(trades)

        return StrategyPerformance(
            strategy_name=strategy_name,
            period=period,
            period_start=start,
            period_end=end,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            break_even_trades=len(break_even),
            total_pnl_sol=total_pnl,
            gross_profit_sol=gross_profit,
            gross_loss_sol=Decimal(str(gross_loss)),
            avg_pnl_sol=avg_pnl,
            avg_pnl_pct=avg_pnl_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win_sol=avg_win,
            avg_loss_sol=Decimal(str(avg_loss)),
            largest_win_sol=largest_win,
            largest_loss_sol=Decimal(str(largest_loss)),
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            avg_hold_duration_seconds=avg_hold,
            current_streak=streaks["current"],
            max_win_streak=streaks["max_win"],
            max_loss_streak=streaks["max_loss"],
        )

    def _calculate_max_drawdown(self, trades: List[TradeRecord]) -> float:
        """Calculate maximum drawdown from trades"""
        if not trades:
            return 0

        equity = Decimal(0)
        peak = Decimal(0)
        max_dd = 0

        for trade in trades:
            equity += trade.pnl_sol
            peak = max(peak, equity)
            dd = float((peak - equity) / peak * 100) if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_streaks(self, trades: List[TradeRecord]) -> Dict[str, int]:
        """Calculate win/loss streaks"""
        if not trades:
            return {"current": 0, "max_win": 0, "max_loss": 0}

        current_streak = 0
        max_win = 0
        max_loss = 0
        win_streak = 0
        loss_streak = 0

        for trade in trades:
            if trade.pnl_sol > 0:
                if win_streak >= 0:
                    win_streak += 1
                else:
                    win_streak = 1
                loss_streak = 0
                max_win = max(max_win, win_streak)
            elif trade.pnl_sol < 0:
                if loss_streak <= 0:
                    loss_streak -= 1
                else:
                    loss_streak = -1
                win_streak = 0
                max_loss = max(max_loss, abs(loss_streak))

        current_streak = win_streak if win_streak > 0 else loss_streak

        return {
            "current": current_streak,
            "max_win": max_win,
            "max_loss": max_loss,
        }

    def _empty_performance(
        self,
        strategy_name: str,
        period: str,
        start: datetime,
        end: datetime,
    ) -> StrategyPerformance:
        """Return empty performance for strategy with no trades"""
        return StrategyPerformance(
            strategy_name=strategy_name,
            period=period,
            period_start=start,
            period_end=end,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            break_even_trades=0,
            total_pnl_sol=Decimal(0),
            gross_profit_sol=Decimal(0),
            gross_loss_sol=Decimal(0),
            avg_pnl_sol=Decimal(0),
            avg_pnl_pct=0,
            win_rate=0,
            profit_factor=0,
            avg_win_sol=Decimal(0),
            avg_loss_sol=Decimal(0),
            largest_win_sol=Decimal(0),
            largest_loss_sol=Decimal(0),
            sharpe_ratio=0,
            max_drawdown_pct=0,
            avg_hold_duration_seconds=0,
            current_streak=0,
            max_win_streak=0,
            max_loss_streak=0,
        )

    # =========================================================================
    # RANKINGS
    # =========================================================================

    async def get_rankings(self, period: str = "30d") -> List[StrategyRanking]:
        """
        Rank strategies by performance.

        Args:
            period: Period to analyze

        Returns:
            List of rankings (best first)
        """
        # Get all strategies with trades
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT strategy_name FROM trades")
        strategies = [row[0] for row in cursor.fetchall()]
        conn.close()

        rankings = []
        for strategy in strategies:
            perf = await self.get_performance(strategy, period)

            # Composite score: Sharpe * sqrt(trade_count) * (1 + win_rate)
            score = (
                perf.sharpe_ratio
                * (perf.total_trades ** 0.5)
                * (1 + perf.win_rate)
            )

            rankings.append(StrategyRanking(
                strategy_name=strategy,
                rank=0,  # Will be set after sorting
                score=score,
                sharpe_ratio=perf.sharpe_ratio,
                total_pnl_sol=float(perf.total_pnl_sol),
                win_rate=perf.win_rate,
                trade_count=perf.total_trades,
            ))

        # Sort by score
        rankings.sort(key=lambda r: r.score, reverse=True)

        # Assign ranks
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        return rankings

    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================

    async def get_recommendations(self) -> Dict[str, Any]:
        """
        Get performance-based recommendations.

        Returns:
            Dictionary of recommendations
        """
        rankings = await self.get_rankings("30d")

        recommendations = {
            "top_performers": [],
            "underperformers": [],
            "high_potential": [],
            "actions": [],
        }

        for ranking in rankings[:3]:
            recommendations["top_performers"].append({
                "strategy": ranking.strategy_name,
                "sharpe": ranking.sharpe_ratio,
                "pnl": ranking.total_pnl_sol,
            })

        for ranking in rankings[-3:]:
            if ranking.sharpe_ratio < 0:
                recommendations["underperformers"].append({
                    "strategy": ranking.strategy_name,
                    "sharpe": ranking.sharpe_ratio,
                    "action": "Consider disabling or parameter optimization",
                })

        # Check for potential improvements
        for ranking in rankings:
            if ranking.win_rate > 0.6 and ranking.sharpe_ratio < 1:
                recommendations["high_potential"].append({
                    "strategy": ranking.strategy_name,
                    "reason": "High win rate but low Sharpe - optimize position sizing",
                })

        return recommendations


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_performance_endpoints(tracker: PerformanceTracker):
    """Create performance API endpoints"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/treasury/performance", tags=["Performance"])

    @router.get("/strategy/{name}")
    async def get_strategy_performance(name: str, period: str = "30d"):
        """Get performance for a strategy"""
        perf = await tracker.get_performance(name, period)
        return perf.to_dict()

    @router.get("/rankings")
    async def get_rankings(period: str = "30d"):
        """Get strategy rankings"""
        rankings = await tracker.get_rankings(period)
        return [
            {
                "rank": r.rank,
                "strategy": r.strategy_name,
                "score": r.score,
                "sharpe_ratio": r.sharpe_ratio,
                "total_pnl_sol": r.total_pnl_sol,
                "win_rate": r.win_rate,
                "trade_count": r.trade_count,
            }
            for r in rankings
        ]

    @router.get("/recommendations")
    async def get_recommendations():
        """Get performance recommendations"""
        return await tracker.get_recommendations()

    return router


# =============================================================================
# SINGLETON
# =============================================================================

_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get or create the performance tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker
