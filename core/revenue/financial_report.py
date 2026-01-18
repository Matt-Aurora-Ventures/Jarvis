"""
Financial Reporting - Generate daily/monthly/yearly reports.

Features:
- Daily fee summaries
- Monthly revenue breakdowns
- Top earners and tokens
- HTML dashboard export
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FeeEntry:
    """A fee entry for reporting."""
    user_id: str
    amount: float
    symbol: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FinancialReporter:
    """
    Generates financial reports.

    Usage:
        reporter = FinancialReporter()

        # Record fees
        reporter.record_fee("user_1", 1.0, "SOL/USDC")

        # Generate daily report
        daily = reporter.generate_daily_report()

        # Generate monthly report
        monthly = reporter.generate_monthly_report("2026-01")
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.fees_file = self.data_dir / "report_fees.jsonl"
        self.reports_dir = self.data_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._today_fees: List[FeeEntry] = []

    def record_fee(
        self,
        user_id: str,
        amount: float,
        symbol: str
    ) -> FeeEntry:
        """
        Record a fee for reporting.

        Args:
            user_id: User identifier
            amount: Fee amount
            symbol: Trading pair

        Returns:
            Fee entry
        """
        entry = FeeEntry(
            user_id=user_id,
            amount=amount,
            symbol=symbol,
        )

        # Cache in memory
        self._today_fees.append(entry)

        # Persist to file
        with open(self.fees_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        return entry

    def _load_fees(
        self,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None
    ) -> List[FeeEntry]:
        """Load fees from file within time range."""
        fees: List[FeeEntry] = []

        if self.fees_file.exists():
            with open(self.fees_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        ts = data.get('timestamp', 0)

                        if start_ts and ts < start_ts:
                            continue
                        if end_ts and ts >= end_ts:
                            continue

                        fees.append(FeeEntry(**data))
                    except json.JSONDecodeError:
                        continue

        return fees

    def generate_daily_report(
        self,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate daily report.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Daily report data
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        start_ts = datetime.strptime(date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).timestamp()
        end_ts = start_ts + 86400

        # Use cache if today, otherwise load from file
        if date == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            fees = self._today_fees
        else:
            fees = self._load_fees(start_ts, end_ts)

        total_fees = sum(f.amount for f in fees)

        return {
            'date': date,
            'total_fees': round(total_fees, 6),
            'user_earnings': round(total_fees * 0.75, 6),  # 75%
            'charity_payout': round(total_fees * 0.05, 6),  # 5%
            'company_revenue': round(total_fees * 0.20, 6),  # 20%
            'fee_count': len(fees),
            'unique_users': len(set(f.user_id for f in fees)),
            'unique_symbols': len(set(f.symbol for f in fees)),
            'generated_at': time.time(),
        }

    def generate_monthly_report(
        self,
        month: str
    ) -> Dict[str, Any]:
        """
        Generate monthly report.

        Args:
            month: Month string (YYYY-MM)

        Returns:
            Monthly report data
        """
        # Parse month to get date range
        year, mon = map(int, month.split('-'))
        start_dt = datetime(year, mon, 1, tzinfo=timezone.utc)

        # Next month
        if mon == 12:
            end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_dt = datetime(year, mon + 1, 1, tzinfo=timezone.utc)

        fees = self._load_fees(start_dt.timestamp(), end_dt.timestamp())

        total_fees = sum(f.amount for f in fees)

        # Calculate daily breakdown
        daily_breakdown: Dict[str, float] = {}
        for fee in fees:
            day = datetime.fromtimestamp(fee.timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
            daily_breakdown[day] = daily_breakdown.get(day, 0) + fee.amount

        # User metrics
        user_totals: Dict[str, float] = {}
        for fee in fees:
            user_totals[fee.user_id] = user_totals.get(fee.user_id, 0) + fee.amount

        return {
            'month': month,
            'total_fees': round(total_fees, 6),
            'revenue_breakdown': {
                'user_earnings': round(total_fees * 0.75, 6),
                'charity_payout': round(total_fees * 0.05, 6),
                'company_revenue': round(total_fees * 0.20, 6),
            },
            'user_metrics': {
                'total_users': len(user_totals),
                'avg_fee_per_user': round(total_fees / max(len(user_totals), 1), 6),
                'top_user_fees': max(user_totals.values()) if user_totals else 0,
            },
            'profitability': {
                'gross_revenue': round(total_fees * 0.20, 6),
                'days_with_fees': len(daily_breakdown),
            },
            'daily_breakdown': daily_breakdown,
            'generated_at': time.time(),
        }

    def get_top_earners(
        self,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get top earners by fee generation.

        Args:
            limit: Number of top earners
            days: Number of days to consider

        Returns:
            List of top earners
        """
        start_ts = time.time() - (days * 86400)
        fees = self._load_fees(start_ts)

        # Aggregate by user
        user_totals: Dict[str, float] = {}
        for fee in fees:
            user_totals[fee.user_id] = user_totals.get(fee.user_id, 0) + fee.amount

        # Sort and limit
        top_earners = sorted(
            [{'user_id': uid, 'total_fees': total} for uid, total in user_totals.items()],
            key=lambda x: x['total_fees'],
            reverse=True
        )

        return top_earners[:limit]

    def get_top_tokens(
        self,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get top tokens by fee generation.

        Args:
            limit: Number of top tokens
            days: Number of days to consider

        Returns:
            List of top tokens
        """
        start_ts = time.time() - (days * 86400)
        fees = self._load_fees(start_ts)

        # Aggregate by symbol
        symbol_totals: Dict[str, float] = {}
        for fee in fees:
            symbol_totals[fee.symbol] = symbol_totals.get(fee.symbol, 0) + fee.amount

        # Sort and limit
        top_tokens = sorted(
            [{'symbol': sym, 'total_fees': total} for sym, total in symbol_totals.items()],
            key=lambda x: x['total_fees'],
            reverse=True
        )

        return top_tokens[:limit]

    def export_html_dashboard(
        self,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Export HTML dashboard.

        Args:
            output_path: Output file path

        Returns:
            Path to generated HTML
        """
        if output_path is None:
            output_path = self.reports_dir / "dashboard.html"

        # Get data
        daily = self.generate_daily_report()
        top_earners = self.get_top_earners(limit=5)
        top_tokens = self.get_top_tokens(limit=5)

        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Jarvis Revenue Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .card {{ background: #16213e; padding: 20px; margin: 10px; border-radius: 8px; }}
        .metric {{ font-size: 24px; font-weight: bold; color: #00d4ff; }}
        .label {{ font-size: 12px; color: #888; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        h2 {{ color: #00d4ff; }}
    </style>
</head>
<body>
    <h1>Jarvis Revenue Dashboard</h1>
    <p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

    <div class="grid">
        <div class="card">
            <div class="label">Total Fees</div>
            <div class="metric">${daily['total_fees']:.2f}</div>
        </div>
        <div class="card">
            <div class="label">User Earnings</div>
            <div class="metric">${daily['user_earnings']:.2f}</div>
        </div>
        <div class="card">
            <div class="label">Charity</div>
            <div class="metric">${daily['charity_payout']:.2f}</div>
        </div>
        <div class="card">
            <div class="label">Company Revenue</div>
            <div class="metric">${daily['company_revenue']:.2f}</div>
        </div>
    </div>

    <h2>Top Earners (30 days)</h2>
    <div class="card">
        <table>
            <tr><th>User</th><th>Total Fees</th></tr>
            {''.join(f"<tr><td>{e['user_id']}</td><td>${e['total_fees']:.2f}</td></tr>" for e in top_earners)}
        </table>
    </div>

    <h2>Top Tokens (30 days)</h2>
    <div class="card">
        <table>
            <tr><th>Symbol</th><th>Total Fees</th></tr>
            {''.join(f"<tr><td>{t['symbol']}</td><td>${t['total_fees']:.2f}</td></tr>" for t in top_tokens)}
        </table>
    </div>
</body>
</html>
"""

        Path(output_path).write_text(html)

        return str(output_path)

    def export_json_report(
        self,
        report_type: str = 'daily',
        output_path: Optional[Path] = None
    ) -> str:
        """
        Export JSON report.

        Args:
            report_type: 'daily' or 'monthly'
            output_path: Output file path

        Returns:
            Path to generated JSON
        """
        if report_type == 'daily':
            data = self.generate_daily_report()
            default_name = f"daily_{data['date']}.json"
        else:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            data = self.generate_monthly_report(month)
            default_name = f"monthly_{month}.json"

        if output_path is None:
            output_path = self.reports_dir / default_name

        Path(output_path).write_text(json.dumps(data, indent=2))

        return str(output_path)
