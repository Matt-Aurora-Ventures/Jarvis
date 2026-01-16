"""
API Cost Tracker Service.

Tracks all API calls, costs, and enforces daily limits.
Persists to SQLite for accurate tracking across restarts.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from tg_bot.config import API_COSTS, get_config

logger = logging.getLogger(__name__)

GROK_COST_PER_CALL = 0.10


@dataclass
class APICall:
    """Record of a single API call."""
    service: str
    endpoint: str
    cost_usd: float
    timestamp: float
    success: bool
    tokens_used: int = 0


@dataclass
class DailyStats:
    """Daily API usage statistics."""
    date: str
    total_calls: int
    total_cost_usd: float
    calls_by_service: Dict[str, int]
    cost_by_service: Dict[str, float]
    sentiment_checks: int


class CostTracker:
    """
    Tracks API costs and enforces limits.

    Features:
    - Per-service cost tracking
    - Daily cost limits
    - Rate limiting enforcement
    - Persistent storage
    """

    def __init__(self, db_path: Optional[Path] = None):
        config = get_config()
        self.db_path = db_path or config.db_path.parent / "cost_tracker.db"
        self.daily_limit = config.daily_cost_limit_usd
        self._init_db()
        self._last_sentiment_time: float = 0
        self._sentiment_count_today: int = 0
        self._load_today_stats()

    def _init_db(self):
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    endpoint TEXT,
                    cost_usd REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    success INTEGER NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    date TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_calls_date
                ON api_calls(date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_calls_service
                ON api_calls(service, date)
            """)
            conn.commit()

    def _load_today_stats(self):
        """Load today's stats from database."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            # Get sentiment count
            cursor = conn.execute("""
                SELECT COUNT(*) FROM api_calls
                WHERE date = ? AND service = 'grok' AND endpoint = 'sentiment'
            """, (today,))
            self._sentiment_count_today = cursor.fetchone()[0]

            # Get last sentiment time
            cursor = conn.execute("""
                SELECT MAX(timestamp) FROM api_calls
                WHERE date = ? AND service = 'grok' AND endpoint = 'sentiment'
            """, (today,))
            result = cursor.fetchone()[0]
            self._last_sentiment_time = result or 0

    def record_call(
        self,
        service: str,
        endpoint: str = "",
        success: bool = True,
        tokens_used: int = 0,
        custom_cost: Optional[float] = None,
    ) -> APICall:
        """
        Record an API call.

        Args:
            service: Service name (grok, claude, birdeye, etc.)
            endpoint: Specific endpoint called
            success: Whether call succeeded
            tokens_used: Number of tokens used (for LLM calls)
            custom_cost: Override default cost calculation

        Returns:
            APICall record
        """
        # Calculate cost
        if custom_cost is not None:
            cost = custom_cost
        elif service == "grok":
            cost = GROK_COST_PER_CALL
        elif tokens_used > 0 and service in ["grok", "claude"]:
            # Token-based pricing
            cost = (tokens_used / 1000) * API_COSTS.get(service, 0.001)
        else:
            cost = API_COSTS.get(service, 0)

        timestamp = time.time()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        call = APICall(
            service=service,
            endpoint=endpoint,
            cost_usd=cost,
            timestamp=timestamp,
            success=success,
            tokens_used=tokens_used,
        )

        # Persist to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO api_calls (service, endpoint, cost_usd, timestamp, success, tokens_used, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (service, endpoint, cost, timestamp, int(success), tokens_used, today))
            conn.commit()

        # Update in-memory counters
        if service == "grok" and endpoint == "sentiment":
            self._sentiment_count_today += 1
            self._last_sentiment_time = timestamp

        return call

    def can_make_sentiment_call(self) -> tuple[bool, str]:
        """
        Check if a sentiment call is allowed.

        Returns:
            (allowed, reason) tuple
        """
        config = get_config()
        now = time.time()

        # Check rate limit (1 hour between calls)
        time_since_last = now - self._last_sentiment_time
        if time_since_last < config.sentiment_interval_seconds:
            remaining = int(config.sentiment_interval_seconds - time_since_last)
            mins = remaining // 60
            secs = remaining % 60
            return False, f"Rate limited. Next check in {mins}m {secs}s"

        # Check daily limit
        if self._sentiment_count_today >= config.max_sentiment_per_day:
            return False, f"Daily limit reached ({config.max_sentiment_per_day} checks)"

        # Check cost limit
        today_cost = self.get_today_cost()
        if today_cost >= config.daily_cost_limit_usd:
            return False, f"Daily cost limit reached (${today_cost:.3f}/${config.daily_cost_limit_usd:.2f})"

        return True, "OK"

    def can_make_call(self) -> tuple[bool, str]:
        """
        Check if a Grok API call is allowed within the daily budget.

        Returns:
            (allowed, reason) tuple
        """
        today_cost = self.get_today_cost()
        projected = today_cost + GROK_COST_PER_CALL
        if projected > self.daily_limit:
            return False, f"Daily cost limit reached (${today_cost:.3f}/${self.daily_limit:.2f})"
        return True, "OK"

    def get_today_cost(self) -> float:
        """Get total cost for today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls WHERE date = ?
            """, (today,))
            return cursor.fetchone()[0]

    def get_today_stats(self) -> DailyStats:
        """Get comprehensive stats for today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            # Total calls and cost
            cursor = conn.execute("""
                SELECT COUNT(*), COALESCE(SUM(cost_usd), 0)
                FROM api_calls WHERE date = ?
            """, (today,))
            total_calls, total_cost = cursor.fetchone()

            # By service
            cursor = conn.execute("""
                SELECT service, COUNT(*), COALESCE(SUM(cost_usd), 0)
                FROM api_calls WHERE date = ?
                GROUP BY service
            """, (today,))

            calls_by_service = {}
            cost_by_service = {}
            for service, count, cost in cursor.fetchall():
                calls_by_service[service] = count
                cost_by_service[service] = cost

            # Sentiment checks
            cursor = conn.execute("""
                SELECT COUNT(*) FROM api_calls
                WHERE date = ? AND service = 'grok' AND endpoint = 'sentiment'
            """, (today,))
            sentiment_checks = cursor.fetchone()[0]

        return DailyStats(
            date=today,
            total_calls=total_calls,
            total_cost_usd=total_cost,
            calls_by_service=calls_by_service,
            cost_by_service=cost_by_service,
            sentiment_checks=sentiment_checks,
        )

    def get_monthly_cost(self) -> float:
        """Get total cost for current month."""
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls
                WHERE date LIKE ?
            """, (f"{month_prefix}%",))
            return cursor.fetchone()[0]

    def get_cost_report(self) -> str:
        """Generate human-readable cost report."""
        config = get_config()
        stats = self.get_today_stats()
        monthly = self.get_monthly_cost()

        lines = [
            "📊 API Cost Report",
            "═" * 20,
            "",
            f"📅 Today ({stats.date})",
            f"   Calls: {stats.total_calls}",
            f"   Cost: ${stats.total_cost_usd:.4f} / ${config.daily_cost_limit_usd:.2f} limit",
            f"   Sentiment checks: {stats.sentiment_checks} / {config.max_sentiment_per_day}",
            "",
        ]

        if stats.calls_by_service:
            lines.append("📈 By Service:")
            for service, count in sorted(stats.calls_by_service.items()):
                cost = stats.cost_by_service.get(service, 0)
                lines.append(f"   {service}: {count} calls (${cost:.4f})")

        lines.extend([
            "",
            f"📆 This Month: ${monthly:.4f}",
        ])

        # Time until next sentiment check
        can_check, reason = self.can_make_sentiment_call()
        if not can_check:
            lines.extend(["", f"⏳ {reason}"])

        return "\n".join(lines)

    def reset_daily_counters(self):
        """Reset daily counters (called at midnight UTC)."""
        self._sentiment_count_today = 0
        # Note: _last_sentiment_time is NOT reset to maintain rate limiting


# Singleton instance
_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get singleton tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
