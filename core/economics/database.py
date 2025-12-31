"""
Economics Database - SQLite storage for P&L tracking.

Provides:
- Historical cost/revenue data
- Aggregated metrics
- Trend analysis
- Breakeven calculations
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from core import config


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "economics" / "economics.db"


@dataclass
class DailyPnL:
    """Daily profit and loss record."""
    date: str
    costs: float
    revenue: float
    net_pnl: float
    trading_pnl: float
    time_saved_value: float
    api_calls: int
    tokens_used: int


@dataclass
class PnLMetrics:
    """Aggregate P&L metrics."""
    total_costs: float
    total_revenue: float
    net_pnl: float
    roi_percent: float
    breakeven_days: Optional[int]
    daily_avg_cost: float
    daily_avg_revenue: float
    best_day_pnl: float
    worst_day_pnl: float
    profitable_days: int
    total_days: int


class EconomicsDB:
    """
    SQLite database for economic tracking.

    Tables:
    - daily_summary: Aggregated daily costs/revenue
    - cost_events: Individual cost entries
    - revenue_events: Individual revenue entries
    - alerts: Breakeven and economic alerts
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date TEXT PRIMARY KEY,
                    costs REAL DEFAULT 0,
                    revenue REAL DEFAULT 0,
                    net_pnl REAL DEFAULT 0,
                    trading_pnl REAL DEFAULT 0,
                    time_saved_value REAL DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    tokens_used INTEGER DEFAULT 0,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS cost_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    category TEXT,
                    provider TEXT,
                    cost_usd REAL,
                    details TEXT,
                    date TEXT
                );

                CREATE TABLE IF NOT EXISTS revenue_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    category TEXT,
                    amount_usd REAL,
                    description TEXT,
                    verified INTEGER DEFAULT 0,
                    details TEXT,
                    date TEXT
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    alert_type TEXT,
                    message TEXT,
                    severity TEXT,
                    acknowledged INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_cost_date ON cost_events(date);
                CREATE INDEX IF NOT EXISTS idx_revenue_date ON revenue_events(date);
                CREATE INDEX IF NOT EXISTS idx_alerts_ack ON alerts(acknowledged);
            """)
            conn.commit()

    def record_cost(
        self,
        category: str,
        provider: str,
        cost_usd: float,
        details: Dict[str, Any],
    ) -> None:
        """Record a cost event."""
        now = time.time()
        date = datetime.fromtimestamp(now).strftime("%Y-%m-%d")

        with self._get_conn() as conn:
            # Insert event
            conn.execute("""
                INSERT INTO cost_events (timestamp, category, provider, cost_usd, details, date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, category, provider, cost_usd, json.dumps(details), date))

            # Update daily summary
            tokens = details.get("total_tokens", 0)
            conn.execute("""
                INSERT INTO daily_summary (date, costs, api_calls, tokens_used, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    costs = costs + ?,
                    api_calls = api_calls + 1,
                    tokens_used = tokens_used + ?,
                    net_pnl = revenue - (costs + ?),
                    updated_at = ?
            """, (date, cost_usd, tokens, now, cost_usd, tokens, cost_usd, now))

            conn.commit()

    def record_revenue(
        self,
        category: str,
        amount_usd: float,
        description: str,
        verified: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a revenue event."""
        now = time.time()
        date = datetime.fromtimestamp(now).strftime("%Y-%m-%d")

        with self._get_conn() as conn:
            # Insert event
            conn.execute("""
                INSERT INTO revenue_events
                (timestamp, category, amount_usd, description, verified, details, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, category, amount_usd, description, int(verified),
                  json.dumps(details or {}), date))

            # Update daily summary
            trading = amount_usd if category == "trading" else 0
            time_val = amount_usd if category == "time_saved" else 0

            conn.execute("""
                INSERT INTO daily_summary (date, revenue, trading_pnl, time_saved_value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    revenue = revenue + ?,
                    trading_pnl = trading_pnl + ?,
                    time_saved_value = time_saved_value + ?,
                    net_pnl = (revenue + ?) - costs,
                    updated_at = ?
            """, (date, amount_usd, trading, time_val, now,
                  amount_usd, trading, time_val, amount_usd, now))

            conn.commit()

    def get_daily_pnl(self, date: str) -> Optional[DailyPnL]:
        """Get P&L for a specific date."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM daily_summary WHERE date = ?", (date,)
            ).fetchone()

            if row:
                return DailyPnL(
                    date=row["date"],
                    costs=row["costs"],
                    revenue=row["revenue"],
                    net_pnl=row["net_pnl"],
                    trading_pnl=row["trading_pnl"],
                    time_saved_value=row["time_saved_value"],
                    api_calls=row["api_calls"],
                    tokens_used=row["tokens_used"],
                )
            return None

    def get_pnl_range(self, days: int = 30) -> List[DailyPnL]:
        """Get P&L for the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM daily_summary
                WHERE date >= ?
                ORDER BY date DESC
            """, (cutoff,)).fetchall()

            return [
                DailyPnL(
                    date=row["date"],
                    costs=row["costs"],
                    revenue=row["revenue"],
                    net_pnl=row["net_pnl"],
                    trading_pnl=row["trading_pnl"],
                    time_saved_value=row["time_saved_value"],
                    api_calls=row["api_calls"],
                    tokens_used=row["tokens_used"],
                )
                for row in rows
            ]

    def get_metrics(self, days: int = 30) -> PnLMetrics:
        """Calculate aggregate P&L metrics."""
        daily_data = self.get_pnl_range(days)

        if not daily_data:
            return PnLMetrics(
                total_costs=0,
                total_revenue=0,
                net_pnl=0,
                roi_percent=0,
                breakeven_days=None,
                daily_avg_cost=0,
                daily_avg_revenue=0,
                best_day_pnl=0,
                worst_day_pnl=0,
                profitable_days=0,
                total_days=0,
            )

        total_costs = sum(d.costs for d in daily_data)
        total_revenue = sum(d.revenue for d in daily_data)
        net_pnl = total_revenue - total_costs
        roi = (net_pnl / total_costs * 100) if total_costs > 0 else 0

        # Calculate days to breakeven
        daily_avg_pnl = net_pnl / len(daily_data) if daily_data else 0
        if net_pnl < 0 and daily_avg_pnl > 0:
            breakeven_days = int(abs(net_pnl) / daily_avg_pnl)
        else:
            breakeven_days = None

        profitable_days = sum(1 for d in daily_data if d.net_pnl > 0)
        pnl_values = [d.net_pnl for d in daily_data]

        return PnLMetrics(
            total_costs=total_costs,
            total_revenue=total_revenue,
            net_pnl=net_pnl,
            roi_percent=roi,
            breakeven_days=breakeven_days,
            daily_avg_cost=total_costs / len(daily_data),
            daily_avg_revenue=total_revenue / len(daily_data),
            best_day_pnl=max(pnl_values),
            worst_day_pnl=min(pnl_values),
            profitable_days=profitable_days,
            total_days=len(daily_data),
        )

    def record_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
    ) -> None:
        """Record an economic alert."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO alerts (timestamp, alert_type, message, severity)
                VALUES (?, ?, ?, ?)
            """, (time.time(), alert_type, message, severity))
            conn.commit()

    def get_unacknowledged_alerts(self) -> List[Dict[str, Any]]:
        """Get all unacknowledged alerts."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM alerts
                WHERE acknowledged = 0
                ORDER BY timestamp DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def acknowledge_alert(self, alert_id: int) -> None:
        """Acknowledge an alert."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE id = ?",
                (alert_id,)
            )
            conn.commit()


# Global instance
_economics_db: Optional[EconomicsDB] = None


def get_economics_db() -> EconomicsDB:
    """Get the global economics database."""
    global _economics_db
    if _economics_db is None:
        _economics_db = EconomicsDB()
    return _economics_db
