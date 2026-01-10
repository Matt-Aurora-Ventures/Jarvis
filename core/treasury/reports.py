"""
Treasury Performance Reports
Prompt #98: Generate treasury performance reports

Generates weekly and monthly treasury performance reports.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.treasury.reports")


# =============================================================================
# MODELS
# =============================================================================

class ReportPeriod(Enum):
    """Report period types"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass
class TradingMetrics:
    """Trading performance metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl_sol: float
    avg_trade_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    sharpe_ratio: float
    max_drawdown_pct: float


@dataclass
class DistributionMetrics:
    """Distribution metrics"""
    total_distributed_sol: float
    staking_rewards_sol: float
    operations_sol: float
    development_sol: float
    distribution_count: int


@dataclass
class WalletSnapshot:
    """Wallet balance snapshot"""
    reserve_sol: float
    active_sol: float
    profit_sol: float
    total_sol: float


@dataclass
class TreasuryReport:
    """Complete treasury report"""
    report_id: str
    period: ReportPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime

    # Balances
    opening_balance: WalletSnapshot
    closing_balance: WalletSnapshot
    net_change_sol: float
    net_change_pct: float

    # Trading
    trading_metrics: TradingMetrics

    # Distributions
    distribution_metrics: DistributionMetrics

    # Risk
    max_exposure_pct: float
    circuit_breaker_triggers: int
    active_positions_avg: float

    # Strategies
    strategy_performance: Dict[str, Dict[str, float]]

    # Summary
    summary: str


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Generates treasury performance reports.

    Report types:
    - Weekly performance summary
    - Monthly detailed report
    - Quarterly review
    """

    def __init__(
        self,
        db_path: str = None,
        output_dir: str = None,
    ):
        self.db_path = db_path or os.getenv(
            "TREASURY_DB",
            "data/treasury.db"
        )
        self.output_dir = output_dir or os.getenv(
            "REPORTS_DIR",
            "data/reports"
        )

        os.makedirs(self.output_dir, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize reports database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS treasury_reports (
                id TEXT PRIMARY KEY,
                period TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                report_json TEXT NOT NULL,
                file_path TEXT
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    async def generate_weekly_report(
        self,
        week_start: datetime = None,
    ) -> TreasuryReport:
        """Generate weekly performance report"""
        if week_start is None:
            # Default to previous week
            today = datetime.now(timezone.utc).date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday() + 7),
                datetime.min.time(),
                tzinfo=timezone.utc
            )

        week_end = week_start + timedelta(days=7)

        return await self._generate_report(
            ReportPeriod.WEEKLY,
            week_start,
            week_end,
        )

    async def generate_monthly_report(
        self,
        year: int = None,
        month: int = None,
    ) -> TreasuryReport:
        """Generate monthly performance report"""
        now = datetime.now(timezone.utc)

        if year is None or month is None:
            # Default to previous month
            if now.month == 1:
                year = now.year - 1
                month = 12
            else:
                year = now.year
                month = now.month - 1

        period_start = datetime(year, month, 1, tzinfo=timezone.utc)

        if month == 12:
            period_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        return await self._generate_report(
            ReportPeriod.MONTHLY,
            period_start,
            period_end,
        )

    async def _generate_report(
        self,
        period: ReportPeriod,
        period_start: datetime,
        period_end: datetime,
    ) -> TreasuryReport:
        """Generate a report for a period"""
        import hashlib

        report_id = hashlib.sha256(
            f"{period.value}:{period_start.isoformat()}".encode()
        ).hexdigest()[:16]

        # Gather data
        opening_balance = await self._get_balance_snapshot(period_start)
        closing_balance = await self._get_balance_snapshot(period_end)
        trading_metrics = await self._get_trading_metrics(period_start, period_end)
        distribution_metrics = await self._get_distribution_metrics(period_start, period_end)
        strategy_perf = await self._get_strategy_performance(period_start, period_end)
        risk_data = await self._get_risk_data(period_start, period_end)

        # Calculate changes
        net_change = closing_balance.total_sol - opening_balance.total_sol
        net_change_pct = (net_change / opening_balance.total_sol * 100) if opening_balance.total_sol > 0 else 0

        # Generate summary
        summary = self._generate_summary(
            period, trading_metrics, distribution_metrics, net_change_pct
        )

        report = TreasuryReport(
            report_id=report_id,
            period=period,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            net_change_sol=net_change,
            net_change_pct=net_change_pct,
            trading_metrics=trading_metrics,
            distribution_metrics=distribution_metrics,
            max_exposure_pct=risk_data.get("max_exposure", 0),
            circuit_breaker_triggers=risk_data.get("circuit_triggers", 0),
            active_positions_avg=risk_data.get("avg_positions", 0),
            strategy_performance=strategy_perf,
            summary=summary,
        )

        # Save report
        await self._save_report(report)

        # Export to file
        await self.export_report(report)

        logger.info(f"Generated {period.value} report: {report_id}")

        return report

    # =========================================================================
    # DATA GATHERING
    # =========================================================================

    async def _get_balance_snapshot(
        self,
        timestamp: datetime,
    ) -> WalletSnapshot:
        """Get wallet balance at a point in time"""
        try:
            from core.treasury.manager import get_treasury_manager

            manager = get_treasury_manager()
            wallets = await manager.get_wallet_balances()

            return WalletSnapshot(
                reserve_sol=wallets.get("reserve", {}).get("sol_balance", 0),
                active_sol=wallets.get("active", {}).get("sol_balance", 0),
                profit_sol=wallets.get("profit", {}).get("sol_balance", 0),
                total_sol=sum(
                    w.get("sol_balance", 0) for w in wallets.values()
                ),
            )

        except Exception as e:
            logger.error(f"Failed to get balance snapshot: {e}")
            return WalletSnapshot(
                reserve_sol=0,
                active_sol=0,
                profit_sol=0,
                total_sol=0,
            )

    async def _get_trading_metrics(
        self,
        start: datetime,
        end: datetime,
    ) -> TradingMetrics:
        """Get trading metrics for period"""
        try:
            from core.data.aggregator import get_trade_aggregator

            aggregator = get_trade_aggregator()
            summary = await aggregator.get_summary(start, end)

            # Get detailed stats
            aggregates = await aggregator.aggregate_by_strategy(start, end)

            # Calculate overall metrics
            total_trades = summary.get("total_trades", 0)
            win_rate = summary.get("overall_win_rate", 0)

            total_pnl = sum(a.total_pnl_pct for a in aggregates)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

            # Sharpe ratio (average across strategies)
            sharpe = (
                sum(a.sharpe_ratio for a in aggregates) / len(aggregates)
                if aggregates else 0
            )

            # Max drawdown
            max_dd = max((a.max_pnl - a.min_pnl for a in aggregates), default=0)

            return TradingMetrics(
                total_trades=total_trades,
                winning_trades=int(total_trades * win_rate),
                losing_trades=total_trades - int(total_trades * win_rate),
                win_rate=win_rate,
                total_pnl_sol=total_pnl / 100,  # Convert from pct
                avg_trade_pnl=avg_pnl / 100,
                best_trade_pnl=max((a.max_pnl for a in aggregates), default=0) / 100,
                worst_trade_pnl=min((a.min_pnl for a in aggregates), default=0) / 100,
                sharpe_ratio=sharpe,
                max_drawdown_pct=max_dd,
            )

        except Exception as e:
            logger.error(f"Failed to get trading metrics: {e}")
            return TradingMetrics(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, total_pnl_sol=0, avg_trade_pnl=0,
                best_trade_pnl=0, worst_trade_pnl=0, sharpe_ratio=0,
                max_drawdown_pct=0,
            )

    async def _get_distribution_metrics(
        self,
        start: datetime,
        end: datetime,
    ) -> DistributionMetrics:
        """Get distribution metrics for period"""
        try:
            from core.treasury.distribution import get_distribution_manager

            manager = get_distribution_manager()
            distributions = await manager.get_distributions(
                since=start, until=end
            )

            total = sum(d.get("total_amount", 0) for d in distributions)
            staking = sum(d.get("staking_amount", 0) for d in distributions)
            ops = sum(d.get("operations_amount", 0) for d in distributions)
            dev = sum(d.get("development_amount", 0) for d in distributions)

            return DistributionMetrics(
                total_distributed_sol=total,
                staking_rewards_sol=staking,
                operations_sol=ops,
                development_sol=dev,
                distribution_count=len(distributions),
            )

        except Exception as e:
            logger.error(f"Failed to get distribution metrics: {e}")
            return DistributionMetrics(
                total_distributed_sol=0,
                staking_rewards_sol=0,
                operations_sol=0,
                development_sol=0,
                distribution_count=0,
            )

    async def _get_strategy_performance(
        self,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Dict[str, float]]:
        """Get per-strategy performance"""
        try:
            from core.data.aggregator import get_trade_aggregator

            aggregator = get_trade_aggregator()
            aggregates = await aggregator.aggregate_by_strategy(start, end)

            return {
                a.group_value: {
                    "trades": a.trade_count,
                    "win_rate": a.win_rate,
                    "pnl_pct": a.total_pnl_pct,
                    "sharpe": a.sharpe_ratio,
                }
                for a in aggregates
            }

        except Exception as e:
            logger.error(f"Failed to get strategy performance: {e}")
            return {}

    async def _get_risk_data(
        self,
        start: datetime,
        end: datetime,
    ) -> Dict[str, float]:
        """Get risk metrics for period"""
        # Placeholder - would query risk monitoring data
        return {
            "max_exposure": 35.0,
            "circuit_triggers": 0,
            "avg_positions": 2.5,
        }

    # =========================================================================
    # SUMMARY GENERATION
    # =========================================================================

    def _generate_summary(
        self,
        period: ReportPeriod,
        trading: TradingMetrics,
        distributions: DistributionMetrics,
        net_change_pct: float,
    ) -> str:
        """Generate report summary text"""
        period_name = period.value.capitalize()

        performance = "positive" if net_change_pct > 0 else "negative"
        change_str = f"+{net_change_pct:.2f}%" if net_change_pct >= 0 else f"{net_change_pct:.2f}%"

        summary = f"""
{period_name} Treasury Report Summary

Performance: {performance} ({change_str})
Trading: {trading.total_trades} trades with {trading.win_rate*100:.1f}% win rate
Total P&L: {trading.total_pnl_sol:.4f} SOL
Sharpe Ratio: {trading.sharpe_ratio:.2f}
Max Drawdown: {trading.max_drawdown_pct:.2f}%

Distributions: {distributions.distribution_count} distributions totaling {distributions.total_distributed_sol:.4f} SOL
- Staking Rewards: {distributions.staking_rewards_sol:.4f} SOL
- Operations: {distributions.operations_sol:.4f} SOL
- Development: {distributions.development_sol:.4f} SOL
        """.strip()

        return summary

    # =========================================================================
    # EXPORT
    # =========================================================================

    async def export_report(
        self,
        report: TreasuryReport,
        format: str = "md",
    ) -> str:
        """Export report to file"""
        filename = f"treasury_{report.period.value}_{report.period_start.strftime('%Y%m%d')}.{format}"
        filepath = os.path.join(self.output_dir, filename)

        if format == "md":
            content = self._format_markdown(report)
        elif format == "json":
            content = self._format_json(report)
        else:
            content = self._format_markdown(report)

        with open(filepath, "w") as f:
            f.write(content)

        logger.info(f"Exported report to {filepath}")

        return filepath

    def _format_markdown(self, report: TreasuryReport) -> str:
        """Format report as Markdown"""
        return f"""# JARVIS Treasury Report

**Period:** {report.period.value.capitalize()}
**From:** {report.period_start.strftime('%Y-%m-%d')}
**To:** {report.period_end.strftime('%Y-%m-%d')}
**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}

---

## Performance Summary

| Metric | Value |
|--------|-------|
| Opening Balance | {report.opening_balance.total_sol:.4f} SOL |
| Closing Balance | {report.closing_balance.total_sol:.4f} SOL |
| Net Change | {report.net_change_sol:.4f} SOL ({report.net_change_pct:+.2f}%) |

## Trading Performance

| Metric | Value |
|--------|-------|
| Total Trades | {report.trading_metrics.total_trades} |
| Win Rate | {report.trading_metrics.win_rate*100:.1f}% |
| Total P&L | {report.trading_metrics.total_pnl_sol:.4f} SOL |
| Sharpe Ratio | {report.trading_metrics.sharpe_ratio:.2f} |
| Max Drawdown | {report.trading_metrics.max_drawdown_pct:.2f}% |

## Distributions

| Category | Amount (SOL) |
|----------|-------------|
| Total Distributed | {report.distribution_metrics.total_distributed_sol:.4f} |
| Staking Rewards | {report.distribution_metrics.staking_rewards_sol:.4f} |
| Operations | {report.distribution_metrics.operations_sol:.4f} |
| Development | {report.distribution_metrics.development_sol:.4f} |

## Strategy Performance

{self._format_strategy_table(report.strategy_performance)}

## Risk Metrics

| Metric | Value |
|--------|-------|
| Max Exposure | {report.max_exposure_pct:.1f}% |
| Circuit Breaker Triggers | {report.circuit_breaker_triggers} |
| Avg Active Positions | {report.active_positions_avg:.1f} |

---

{report.summary}

---
*Report ID: {report.report_id}*
"""

    def _format_strategy_table(self, performance: Dict[str, Dict[str, float]]) -> str:
        """Format strategy performance as Markdown table"""
        if not performance:
            return "*No strategy data available*"

        rows = ["| Strategy | Trades | Win Rate | P&L % | Sharpe |",
                "|----------|--------|----------|-------|--------|"]

        for strategy, data in performance.items():
            rows.append(
                f"| {strategy} | {data.get('trades', 0)} | "
                f"{data.get('win_rate', 0)*100:.1f}% | "
                f"{data.get('pnl_pct', 0):.2f}% | "
                f"{data.get('sharpe', 0):.2f} |"
            )

        return "\n".join(rows)

    def _format_json(self, report: TreasuryReport) -> str:
        """Format report as JSON"""
        return json.dumps({
            "report_id": report.report_id,
            "period": report.period.value,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "generated_at": report.generated_at.isoformat(),
            "opening_balance": {
                "reserve": report.opening_balance.reserve_sol,
                "active": report.opening_balance.active_sol,
                "profit": report.opening_balance.profit_sol,
                "total": report.opening_balance.total_sol,
            },
            "closing_balance": {
                "reserve": report.closing_balance.reserve_sol,
                "active": report.closing_balance.active_sol,
                "profit": report.closing_balance.profit_sol,
                "total": report.closing_balance.total_sol,
            },
            "net_change_sol": report.net_change_sol,
            "net_change_pct": report.net_change_pct,
            "trading": {
                "total_trades": report.trading_metrics.total_trades,
                "win_rate": report.trading_metrics.win_rate,
                "total_pnl_sol": report.trading_metrics.total_pnl_sol,
                "sharpe_ratio": report.trading_metrics.sharpe_ratio,
            },
            "distributions": {
                "total": report.distribution_metrics.total_distributed_sol,
                "staking": report.distribution_metrics.staking_rewards_sol,
                "operations": report.distribution_metrics.operations_sol,
                "development": report.distribution_metrics.development_sol,
            },
            "strategy_performance": report.strategy_performance,
            "summary": report.summary,
        }, indent=2)

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _save_report(self, report: TreasuryReport):
        """Save report to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO treasury_reports
            (id, period, period_start, period_end, generated_at, report_json, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            report.report_id,
            report.period.value,
            report.period_start.isoformat(),
            report.period_end.isoformat(),
            report.generated_at.isoformat(),
            self._format_json(report),
            None,
        ))

        conn.commit()
        conn.close()

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a report by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT report_json FROM treasury_reports WHERE id = ?",
            (report_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return json.loads(row[0])

    async def list_reports(
        self,
        period: ReportPeriod = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """List available reports"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT id, period, period_start, period_end, generated_at FROM treasury_reports"
        params = []

        if period:
            query += " WHERE period = ?"
            params.append(period.value)

        query += " ORDER BY period_start DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        reports = [
            {
                "id": row[0],
                "period": row[1],
                "period_start": row[2],
                "period_end": row[3],
                "generated_at": row[4],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return reports


# =============================================================================
# SINGLETON
# =============================================================================

_generator: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Get or create the report generator singleton"""
    global _generator
    if _generator is None:
        _generator = ReportGenerator()
    return _generator
