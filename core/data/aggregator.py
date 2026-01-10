"""
Trade Outcome Aggregator
Prompt #91: Aggregate anonymized trade outcomes for insights

Aggregates trade data for strategy optimization and market analysis.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json
import statistics

logger = logging.getLogger("jarvis.data.aggregator")


# =============================================================================
# MODELS
# =============================================================================

class AggregationPeriod(Enum):
    """Time period for aggregation"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MarketCondition(Enum):
    """Market condition categories"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    LOW_VOLUME = "low_volume"


@dataclass
class AggregatedOutcome:
    """Aggregated trade outcome statistics"""
    group_key: str
    group_value: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl_pct: float
    median_pnl_pct: float
    total_pnl_pct: float
    std_dev_pnl: float
    avg_hold_duration: float
    sharpe_ratio: float
    max_pnl: float
    min_pnl: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class HourlyPattern:
    """Trading patterns by hour"""
    hour: int
    trade_count: int
    win_rate: float
    avg_pnl_pct: float
    best_strategies: List[str]


@dataclass
class TokenPerformance:
    """Performance metrics for a token"""
    token_mint: str
    symbol: str
    trade_count: int
    win_rate: float
    avg_pnl_pct: float
    total_volume_bucket: int
    unique_traders: int
    best_strategy: str


# =============================================================================
# TRADE AGGREGATOR
# =============================================================================

class TradeAggregator:
    """
    Aggregates anonymized trade data for insights.

    Provides:
    - Strategy performance comparisons
    - Token performance analysis
    - Market condition correlations
    - Time-based patterns
    - Volume-weighted metrics
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("TRADE_DATA_DB", "data/trade_data.db")

    # =========================================================================
    # STRATEGY AGGREGATION
    # =========================================================================

    async def aggregate_by_strategy(
        self,
        since: datetime = None,
        until: datetime = None,
        min_trades: int = 10,
    ) -> List[AggregatedOutcome]:
        """
        Aggregate outcomes by trading strategy.

        Args:
            since: Start date
            until: End date
            min_trades: Minimum trades to include strategy

        Returns:
            List of aggregated outcomes per strategy
        """
        records = await self._get_records(since, until)

        # Group by strategy
        strategy_groups: Dict[str, List[Dict]] = {}
        for record in records:
            strategy = record.get("strategy_name") or "unknown"
            if strategy not in strategy_groups:
                strategy_groups[strategy] = []
            strategy_groups[strategy].append(record)

        # Calculate aggregates
        results = []
        for strategy, trades in strategy_groups.items():
            if len(trades) < min_trades:
                continue

            outcome = self._calculate_outcome(
                "strategy", strategy, trades, since, until
            )
            results.append(outcome)

        # Sort by win rate
        results.sort(key=lambda x: -x.win_rate)

        return results

    async def aggregate_by_token(
        self,
        since: datetime = None,
        until: datetime = None,
        min_trades: int = 5,
    ) -> List[TokenPerformance]:
        """
        Aggregate outcomes by token.

        Args:
            since: Start date
            until: End date
            min_trades: Minimum trades to include token

        Returns:
            List of token performance metrics
        """
        records = await self._get_records(since, until)

        # Group by token
        token_groups: Dict[str, List[Dict]] = {}
        for record in records:
            token = record.get("token_mint", "")
            if token not in token_groups:
                token_groups[token] = []
            token_groups[token].append(record)

        results = []
        for token, trades in token_groups.items():
            if len(trades) < min_trades:
                continue

            pnl_values = [t.get("pnl_pct", 0) for t in trades if t.get("pnl_pct") is not None]
            outcomes = [t.get("outcome", "") for t in trades]
            win_count = sum(1 for o in outcomes if o == "win")

            # Find best strategy for this token
            strategy_counts: Dict[str, int] = {}
            strategy_wins: Dict[str, int] = {}
            for t in trades:
                s = t.get("strategy_name", "unknown")
                strategy_counts[s] = strategy_counts.get(s, 0) + 1
                if t.get("outcome") == "win":
                    strategy_wins[s] = strategy_wins.get(s, 0) + 1

            best_strategy = max(
                strategy_counts.keys(),
                key=lambda s: strategy_wins.get(s, 0) / max(strategy_counts.get(s, 1), 1),
                default="unknown"
            )

            # Unique traders
            unique_traders = len(set(t.get("user_hash", "") for t in trades))

            results.append(TokenPerformance(
                token_mint=token,
                symbol=trades[0].get("symbol", ""),
                trade_count=len(trades),
                win_rate=win_count / len(trades) if trades else 0,
                avg_pnl_pct=statistics.mean(pnl_values) if pnl_values else 0,
                total_volume_bucket=sum(t.get("amount_bucket", 0) for t in trades),
                unique_traders=unique_traders,
                best_strategy=best_strategy,
            ))

        # Sort by trade count
        results.sort(key=lambda x: -x.trade_count)

        return results

    async def aggregate_by_market_condition(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> Dict[str, AggregatedOutcome]:
        """
        Aggregate outcomes by market condition.

        Args:
            since: Start date
            until: End date

        Returns:
            Dict of market condition to aggregated outcome
        """
        records = await self._get_records(since, until)

        # Group by market condition
        condition_groups: Dict[str, List[Dict]] = {}
        for record in records:
            conditions_json = record.get("market_conditions_json", "{}")
            try:
                conditions = json.loads(conditions_json) if conditions_json else {}
            except (json.JSONDecodeError, TypeError):
                conditions = {}

            condition = conditions.get("trend", "unknown")
            if condition not in condition_groups:
                condition_groups[condition] = []
            condition_groups[condition].append(record)

        results = {}
        for condition, trades in condition_groups.items():
            if len(trades) < 5:
                continue

            results[condition] = self._calculate_outcome(
                "market_condition", condition, trades, since, until
            )

        return results

    async def aggregate_hourly_patterns(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> List[HourlyPattern]:
        """
        Analyze trading patterns by hour of day.

        Args:
            since: Start date
            until: End date

        Returns:
            List of hourly patterns
        """
        records = await self._get_records(since, until)

        # Group by hour
        hourly_groups: Dict[int, List[Dict]] = {h: [] for h in range(24)}

        for record in records:
            time_bucket = record.get("time_bucket", "")
            try:
                # Parse time bucket (format: YYYY-MM-DD HH:00)
                if time_bucket:
                    dt = datetime.fromisoformat(time_bucket.replace(" ", "T"))
                    hourly_groups[dt.hour].append(record)
            except (ValueError, AttributeError):
                pass

        results = []
        for hour, trades in hourly_groups.items():
            if not trades:
                continue

            outcomes = [t.get("outcome", "") for t in trades]
            win_count = sum(1 for o in outcomes if o == "win")
            pnl_values = [t.get("pnl_pct", 0) for t in trades if t.get("pnl_pct") is not None]

            # Find best strategies for this hour
            strategy_performance: Dict[str, Tuple[int, int]] = {}  # (wins, total)
            for t in trades:
                s = t.get("strategy_name", "unknown")
                wins, total = strategy_performance.get(s, (0, 0))
                if t.get("outcome") == "win":
                    wins += 1
                strategy_performance[s] = (wins, total + 1)

            best_strategies = sorted(
                strategy_performance.keys(),
                key=lambda s: strategy_performance[s][0] / max(strategy_performance[s][1], 1),
                reverse=True
            )[:3]

            results.append(HourlyPattern(
                hour=hour,
                trade_count=len(trades),
                win_rate=win_count / len(trades) if trades else 0,
                avg_pnl_pct=statistics.mean(pnl_values) if pnl_values else 0,
                best_strategies=best_strategies,
            ))

        return results

    # =========================================================================
    # COMPARATIVE ANALYSIS
    # =========================================================================

    async def compare_strategies(
        self,
        strategy_a: str,
        strategy_b: str,
        since: datetime = None,
        until: datetime = None,
    ) -> Dict[str, Any]:
        """
        Compare two strategies head-to-head.

        Args:
            strategy_a: First strategy name
            strategy_b: Second strategy name
            since: Start date
            until: End date

        Returns:
            Comparison metrics
        """
        aggregates = await self.aggregate_by_strategy(since, until, min_trades=1)

        outcome_a = next((a for a in aggregates if a.group_value == strategy_a), None)
        outcome_b = next((a for a in aggregates if a.group_value == strategy_b), None)

        if not outcome_a or not outcome_b:
            return {"error": "One or both strategies not found"}

        return {
            "strategies": [strategy_a, strategy_b],
            "comparison": {
                "trade_count": {
                    strategy_a: outcome_a.trade_count,
                    strategy_b: outcome_b.trade_count,
                },
                "win_rate": {
                    strategy_a: outcome_a.win_rate,
                    strategy_b: outcome_b.win_rate,
                    "winner": strategy_a if outcome_a.win_rate > outcome_b.win_rate else strategy_b,
                },
                "avg_pnl": {
                    strategy_a: outcome_a.avg_pnl_pct,
                    strategy_b: outcome_b.avg_pnl_pct,
                    "winner": strategy_a if outcome_a.avg_pnl_pct > outcome_b.avg_pnl_pct else strategy_b,
                },
                "sharpe_ratio": {
                    strategy_a: outcome_a.sharpe_ratio,
                    strategy_b: outcome_b.sharpe_ratio,
                    "winner": strategy_a if outcome_a.sharpe_ratio > outcome_b.sharpe_ratio else strategy_b,
                },
                "risk_adjusted_winner": (
                    strategy_a if outcome_a.sharpe_ratio > outcome_b.sharpe_ratio else strategy_b
                ),
            },
        }

    async def get_top_strategies(
        self,
        n: int = 5,
        metric: str = "sharpe_ratio",
        since: datetime = None,
        until: datetime = None,
    ) -> List[AggregatedOutcome]:
        """
        Get top N strategies by a metric.

        Args:
            n: Number of strategies to return
            metric: Metric to sort by (win_rate, avg_pnl_pct, sharpe_ratio)
            since: Start date
            until: End date

        Returns:
            Top N strategies
        """
        aggregates = await self.aggregate_by_strategy(since, until)

        # Sort by requested metric
        if metric == "win_rate":
            aggregates.sort(key=lambda x: -x.win_rate)
        elif metric == "avg_pnl_pct":
            aggregates.sort(key=lambda x: -x.avg_pnl_pct)
        else:  # sharpe_ratio
            aggregates.sort(key=lambda x: -x.sharpe_ratio)

        return aggregates[:n]

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _calculate_outcome(
        self,
        group_key: str,
        group_value: str,
        trades: List[Dict],
        since: datetime = None,
        until: datetime = None,
    ) -> AggregatedOutcome:
        """Calculate aggregated outcome for a group of trades"""
        pnl_values = [
            t.get("pnl_pct", 0) for t in trades
            if t.get("pnl_pct") is not None
        ]
        outcomes = [t.get("outcome", "") for t in trades]
        durations = [
            t.get("hold_duration_seconds", 0) for t in trades
            if t.get("hold_duration_seconds") is not None
        ]

        win_count = sum(1 for o in outcomes if o == "win")
        loss_count = sum(1 for o in outcomes if o == "loss")

        # Calculate statistics
        avg_pnl = statistics.mean(pnl_values) if pnl_values else 0
        median_pnl = statistics.median(pnl_values) if pnl_values else 0
        total_pnl = sum(pnl_values)
        std_dev = statistics.stdev(pnl_values) if len(pnl_values) > 1 else 0
        avg_duration = statistics.mean(durations) if durations else 0

        # Calculate Sharpe ratio (simplified, assuming 0 risk-free rate)
        sharpe = avg_pnl / std_dev if std_dev > 0 else 0

        return AggregatedOutcome(
            group_key=group_key,
            group_value=group_value,
            trade_count=len(trades),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_count / len(trades) if trades else 0,
            avg_pnl_pct=avg_pnl,
            median_pnl_pct=median_pnl,
            total_pnl_pct=total_pnl,
            std_dev_pnl=std_dev,
            avg_hold_duration=avg_duration,
            sharpe_ratio=sharpe,
            max_pnl=max(pnl_values) if pnl_values else 0,
            min_pnl=min(pnl_values) if pnl_values else 0,
            period_start=since,
            period_end=until,
        )

    async def _get_records(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> List[Dict]:
        """Get trade records for aggregation"""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM anonymized_trades WHERE 1=1"
        params = []

        if since:
            query += " AND time_bucket >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND time_bucket <= ?"
            params.append(until.isoformat())

        try:
            cursor.execute(query, params)
            columns = [d[0] for d in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error:
            records = []

        conn.close()
        return records

    # =========================================================================
    # SUMMARY
    # =========================================================================

    async def get_summary(
        self,
        since: datetime = None,
        until: datetime = None,
    ) -> Dict[str, Any]:
        """Get overall aggregation summary"""
        records = await self._get_records(since, until)

        if not records:
            return {"total_trades": 0}

        pnl_values = [
            t.get("pnl_pct", 0) for t in records
            if t.get("pnl_pct") is not None
        ]
        outcomes = [t.get("outcome", "") for t in records]

        strategies = set(t.get("strategy_name", "unknown") for t in records)
        tokens = set(t.get("token_mint", "") for t in records)
        users = set(t.get("user_hash", "") for t in records)

        win_count = sum(1 for o in outcomes if o == "win")

        return {
            "total_trades": len(records),
            "unique_strategies": len(strategies),
            "unique_tokens": len(tokens),
            "unique_users": len(users),
            "overall_win_rate": win_count / len(records) if records else 0,
            "avg_pnl_pct": statistics.mean(pnl_values) if pnl_values else 0,
            "total_pnl_pct": sum(pnl_values),
            "period_start": since.isoformat() if since else None,
            "period_end": until.isoformat() if until else None,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_aggregator: Optional[TradeAggregator] = None


def get_trade_aggregator() -> TradeAggregator:
    """Get or create the trade aggregator singleton"""
    global _aggregator
    if _aggregator is None:
        _aggregator = TradeAggregator()
    return _aggregator
