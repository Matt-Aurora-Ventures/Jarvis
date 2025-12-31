"""
Economics Dashboard - P&L visibility and breakeven alerts.

Provides:
- Real-time P&L summary
- Cost/revenue trends
- Breakeven tracking
- Alert generation
"""

import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.economics.costs import get_cost_tracker, CostSummary
from core.economics.revenue import get_revenue_tracker, RevenueSummary
from core.economics.database import get_economics_db, PnLMetrics


@dataclass
class EconomicStatus:
    """Current economic status of the system."""
    is_profitable: bool
    net_pnl_today: float
    net_pnl_30d: float
    roi_30d_percent: float
    costs_today: float
    revenue_today: float
    trading_pnl: float
    time_saved_value: float
    api_calls_today: int
    tokens_today: int
    status_message: str
    alerts: List[str]


class EconomicsDashboard:
    """
    Real-time economic visibility.

    Usage:
        dashboard = EconomicsDashboard()

        # Get current status
        status = dashboard.get_status()

        # Check for alerts
        alerts = dashboard.check_alerts()

        # Generate report
        report = dashboard.generate_report(days=30)
    """

    def __init__(self):
        self._cost_tracker = get_cost_tracker()
        self._revenue_tracker = get_revenue_tracker()
        self._db = get_economics_db()

        # Alert thresholds
        self.daily_cost_warning = 5.00    # Warn if > $5/day
        self.daily_cost_critical = 20.00  # Critical if > $20/day
        self.negative_pnl_days = 3        # Alert after 3 consecutive loss days

    def get_status(self) -> EconomicStatus:
        """Get current economic status."""
        # Today's data
        cost_summary = self._cost_tracker.get_summary(days=1)
        revenue_summary = self._revenue_tracker.get_summary(days=1)

        # 30-day metrics
        metrics = self._db.get_metrics(days=30)

        net_today = revenue_summary.total_usd - cost_summary.total_usd
        is_profitable = metrics.net_pnl > 0

        # Generate status message
        if is_profitable and metrics.roi_percent > 100:
            status = f"Excellent! ROI: {metrics.roi_percent:.0f}%"
        elif is_profitable:
            status = f"Profitable. ROI: {metrics.roi_percent:.0f}%"
        elif metrics.breakeven_days:
            status = f"~{metrics.breakeven_days} days to breakeven"
        else:
            status = f"Loss: ${abs(metrics.net_pnl):.2f}"

        # Check for alerts
        alerts = self.check_alerts()

        return EconomicStatus(
            is_profitable=is_profitable,
            net_pnl_today=net_today,
            net_pnl_30d=metrics.net_pnl,
            roi_30d_percent=metrics.roi_percent,
            costs_today=cost_summary.total_usd,
            revenue_today=revenue_summary.total_usd,
            trading_pnl=revenue_summary.trading_pnl,
            time_saved_value=revenue_summary.total_usd - revenue_summary.trading_pnl,
            api_calls_today=cost_summary.api_calls,
            tokens_today=cost_summary.total_tokens,
            status_message=status,
            alerts=alerts,
        )

    def check_alerts(self) -> List[str]:
        """Check for economic alerts and return messages."""
        alerts = []

        cost_summary = self._cost_tracker.get_summary(days=1)

        # Check daily cost thresholds
        if cost_summary.total_usd > self.daily_cost_critical:
            msg = f"CRITICAL: Daily costs ${cost_summary.total_usd:.2f} exceed ${self.daily_cost_critical:.2f}"
            alerts.append(msg)
            self._db.record_alert("cost_critical", msg, "critical")

        elif cost_summary.total_usd > self.daily_cost_warning:
            msg = f"WARNING: Daily costs ${cost_summary.total_usd:.2f} exceed ${self.daily_cost_warning:.2f}"
            alerts.append(msg)
            self._db.record_alert("cost_warning", msg, "warning")

        # Check for consecutive loss days
        recent_pnl = self._db.get_pnl_range(days=self.negative_pnl_days)
        if len(recent_pnl) >= self.negative_pnl_days:
            if all(d.net_pnl < 0 for d in recent_pnl):
                msg = f"WARNING: {self.negative_pnl_days} consecutive loss days"
                alerts.append(msg)
                self._db.record_alert("consecutive_loss", msg, "warning")

        # Check ROI
        metrics = self._db.get_metrics(days=7)
        if metrics.total_days >= 7 and metrics.roi_percent < -50:
            msg = f"CRITICAL: Weekly ROI is {metrics.roi_percent:.0f}%"
            alerts.append(msg)
            self._db.record_alert("roi_critical", msg, "critical")

        return alerts

    def generate_report(self, days: int = 30) -> str:
        """Generate a text report of economic status."""
        status = self.get_status()
        metrics = self._db.get_metrics(days=days)

        lines = [
            "=" * 60,
            "JARVIS ECONOMIC REPORT",
            "=" * 60,
            "",
            f"Period: Last {days} days",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "SUMMARY",
            "-" * 40,
            f"  Status: {'PROFITABLE' if status.is_profitable else 'LOSS'}",
            f"  Net P&L: ${metrics.net_pnl:+.2f}",
            f"  ROI: {metrics.roi_percent:+.1f}%",
            "",
            "COSTS",
            "-" * 40,
            f"  Total: ${metrics.total_costs:.2f}",
            f"  Daily Avg: ${metrics.daily_avg_cost:.2f}",
            f"  Today: ${status.costs_today:.2f}",
            f"  API Calls Today: {status.api_calls_today}",
            f"  Tokens Today: {status.tokens_today:,}",
            "",
            "REVENUE",
            "-" * 40,
            f"  Total: ${metrics.total_revenue:.2f}",
            f"  Daily Avg: ${metrics.daily_avg_revenue:.2f}",
            f"  Today: ${status.revenue_today:.2f}",
            f"  Trading P&L: ${status.trading_pnl:.2f}",
            f"  Time Savings: ${status.time_saved_value:.2f}",
            "",
            "PERFORMANCE",
            "-" * 40,
            f"  Profitable Days: {metrics.profitable_days}/{metrics.total_days}",
            f"  Best Day: ${metrics.best_day_pnl:+.2f}",
            f"  Worst Day: ${metrics.worst_day_pnl:+.2f}",
        ]

        if metrics.breakeven_days:
            lines.append(f"  Est. Breakeven: {metrics.breakeven_days} days")

        if status.alerts:
            lines.extend([
                "",
                "ALERTS",
                "-" * 40,
            ])
            for alert in status.alerts:
                lines.append(f"  ! {alert}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    def get_trend(self, days: int = 7) -> Dict[str, Any]:
        """Get P&L trend data for visualization."""
        daily_data = self._db.get_pnl_range(days=days)

        return {
            "dates": [d.date for d in reversed(daily_data)],
            "costs": [d.costs for d in reversed(daily_data)],
            "revenue": [d.revenue for d in reversed(daily_data)],
            "net_pnl": [d.net_pnl for d in reversed(daily_data)],
            "trading": [d.trading_pnl for d in reversed(daily_data)],
        }


# Convenience functions
def get_pnl_summary(days: int = 30) -> Dict[str, Any]:
    """Get P&L summary as a dictionary."""
    dashboard = EconomicsDashboard()
    status = dashboard.get_status()
    return asdict(status)


def check_economic_health() -> bool:
    """Quick check if system is economically healthy."""
    dashboard = EconomicsDashboard()
    status = dashboard.get_status()
    return status.is_profitable and len(status.alerts) == 0
