"""
Usage Tracker - Clawdbot-style usage tracking and quota management.

Provides:
- Token usage tracking per user
- Hourly, daily, monthly quotas with auto-reset
- Cost estimation per model
- Alerts at configurable thresholds
"""

import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .config import DEFAULT_QUOTAS, MODEL_PRICING, ALERT_THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class UsageQuota:
    """Represents a usage quota for a specific period."""

    name: str
    limit: int  # -1 means unlimited
    period: str  # "hour", "day", "month"
    used: int
    reset_at: datetime

    @property
    def remaining(self) -> int:
        """Tokens remaining in this quota period."""
        if self.is_unlimited:
            return float('inf')
        return max(0, self.limit - self.used)

    @property
    def percentage_left(self) -> float:
        """Percentage of quota remaining."""
        if self.is_unlimited:
            return 100.0
        if self.limit <= 0:
            return 0.0
        return (self.remaining / self.limit) * 100

    @property
    def percentage_used(self) -> float:
        """Percentage of quota used."""
        return 100.0 - self.percentage_left

    @property
    def time_until_reset(self) -> timedelta:
        """Time until quota resets."""
        now = datetime.now(timezone.utc)
        if self.reset_at <= now:
            return timedelta(seconds=0)
        return self.reset_at - now

    @property
    def is_unlimited(self) -> bool:
        """Check if quota is unlimited."""
        return self.limit == -1


@dataclass
class UsageRecord:
    """A single usage record for tracking history."""

    user_id: int
    session_id: Optional[str]
    model_id: str
    tokens_in: int
    tokens_out: int
    estimated_cost: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this record."""
        return self.tokens_in + self.tokens_out


class UsageTracker:
    """
    Tracks API usage, enforces quotas, and estimates costs.

    Features:
    - Per-user quota tracking (hourly, daily, monthly)
    - Automatic quota reset on period expiration
    - Cost estimation based on model pricing
    - Alert generation at configurable thresholds
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the usage tracker.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.lifeos/usage/tracker.db
        """
        if db_path is None:
            db_path = Path.home() / ".lifeos" / "usage" / "tracker.db"

        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Usage quotas table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_quotas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    token_limit INTEGER NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    reset_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, period)
                )
            """)

            # Usage history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id TEXT,
                    model_id TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL,
                    estimated_cost REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_history_user_id
                ON usage_history(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_history_timestamp
                ON usage_history(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_quotas_user_period
                ON usage_quotas(user_id, period)
            """)

            conn.commit()

    def _ensure_user_quotas(self, user_id: int, tier: str = "free_tier"):
        """Ensure user has quota records for all periods."""
        now = datetime.now(timezone.utc)
        tier_quotas = DEFAULT_QUOTAS.get(tier, DEFAULT_QUOTAS["free_tier"])

        with sqlite3.connect(self.db_path) as conn:
            for period, limit in tier_quotas.items():
                reset_at = self._calculate_reset_time(period, now)
                conn.execute("""
                    INSERT OR IGNORE INTO usage_quotas (user_id, period, token_limit, tokens_used, reset_at)
                    VALUES (?, ?, ?, 0, ?)
                """, (user_id, period, limit, reset_at.isoformat()))
            conn.commit()

    def _calculate_reset_time(self, period: str, from_time: datetime) -> datetime:
        """Calculate next reset time for a period."""
        if period == "hour":
            # Reset at the next hour
            return from_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        elif period == "day":
            # Reset at midnight UTC
            return from_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif period == "month":
            # Reset on first of next month
            if from_time.month == 12:
                return from_time.replace(year=from_time.year + 1, month=1, day=1,
                                        hour=0, minute=0, second=0, microsecond=0)
            return from_time.replace(month=from_time.month + 1, day=1,
                                    hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unknown period: {period}")

    def _check_and_reset_expired_quota(self, user_id: int, period: str) -> bool:
        """Check if quota is expired and reset if needed. Returns True if reset."""
        now = datetime.now(timezone.utc)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT reset_at FROM usage_quotas
                WHERE user_id = ? AND period = ?
            """, (user_id, period))
            row = cursor.fetchone()

            if row:
                reset_at = datetime.fromisoformat(row[0])
                if reset_at <= now:
                    # Quota has expired, reset it
                    new_reset = self._calculate_reset_time(period, now)
                    conn.execute("""
                        UPDATE usage_quotas
                        SET tokens_used = 0, reset_at = ?
                        WHERE user_id = ? AND period = ?
                    """, (new_reset.isoformat(), user_id, period))
                    conn.commit()
                    logger.info(f"Reset {period} quota for user {user_id}")
                    return True
        return False

    def track_usage(
        self,
        user_id: int,
        tokens_in: int,
        tokens_out: int,
        model_id: str,
        session_id: Optional[str] = None,
    ) -> UsageRecord:
        """
        Track token usage for a user.

        Args:
            user_id: User ID
            tokens_in: Input tokens used
            tokens_out: Output tokens used
            model_id: Model used
            session_id: Optional session identifier

        Returns:
            UsageRecord for this usage
        """
        total_tokens = tokens_in + tokens_out
        cost = self.estimate_cost(tokens_in, tokens_out, model_id)
        timestamp = datetime.now(timezone.utc)

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Record in history
                conn.execute("""
                    INSERT INTO usage_history (user_id, session_id, model_id, tokens_in, tokens_out, estimated_cost, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, session_id, model_id, tokens_in, tokens_out, cost, timestamp.isoformat()))

                # Update all quota periods
                for period in ["hour", "day", "month"]:
                    self._check_and_reset_expired_quota(user_id, period)
                    conn.execute("""
                        UPDATE usage_quotas
                        SET tokens_used = tokens_used + ?
                        WHERE user_id = ? AND period = ?
                    """, (total_tokens, user_id, period))

                conn.commit()

        return UsageRecord(
            user_id=user_id,
            session_id=session_id,
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost=cost,
            timestamp=timestamp,
        )

    def get_quota(self, user_id: int, period: str) -> Optional[UsageQuota]:
        """
        Get quota for a user and period.

        Args:
            user_id: User ID
            period: "hour", "day", or "month"

        Returns:
            UsageQuota or None if not found
        """
        # Check for expired quota first
        self._check_and_reset_expired_quota(user_id, period)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT period, token_limit, tokens_used, reset_at
                FROM usage_quotas
                WHERE user_id = ? AND period = ?
            """, (user_id, period))
            row = cursor.fetchone()

            if row:
                return UsageQuota(
                    name=f"{period}_quota",
                    limit=row[1],
                    period=row[0],
                    used=row[2],
                    reset_at=datetime.fromisoformat(row[3]),
                )
        return None

    def check_quota(self, user_id: int, tokens_needed: int) -> Tuple[bool, str]:
        """
        Check if user has sufficient quota for tokens.

        Args:
            user_id: User ID
            tokens_needed: Tokens needed for operation

        Returns:
            (allowed, reason) tuple
        """
        for period in ["hour", "day", "month"]:
            quota = self.get_quota(user_id, period)
            if quota and not quota.is_unlimited:
                if quota.remaining < tokens_needed:
                    return False, f"{period.capitalize()} quota exceeded. {quota.remaining:,} tokens remaining, need {tokens_needed:,}"

        return True, "OK"

    def estimate_cost(self, tokens_in: int, tokens_out: int, model_id: str) -> float:
        """
        Estimate cost for token usage.

        Args:
            tokens_in: Input tokens
            tokens_out: Output tokens
            model_id: Model identifier

        Returns:
            Estimated cost in USD
        """
        pricing = MODEL_PRICING.get(model_id, MODEL_PRICING["default"])

        cost_in = (tokens_in * pricing["input"]) / 1_000_000
        cost_out = (tokens_out * pricing["output"]) / 1_000_000

        return cost_in + cost_out

    def get_usage_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive usage summary for a user.

        Returns dict with:
        - hourly, daily, monthly quota status
        - cost_today, cost_month
        - total_tokens_today
        """
        summary = {
            "user_id": user_id,
            "hourly": None,
            "daily": None,
            "monthly": None,
            "cost_today": 0.0,
            "cost_month": 0.0,
            "total_tokens_today": 0,
        }

        # Get quotas
        for period in ["hour", "day", "month"]:
            quota = self.get_quota(user_id, period)
            if quota:
                summary[period.replace("hour", "hourly").replace("day", "daily").replace("month", "monthly")] = {
                    "used": quota.used,
                    "limit": quota.limit,
                    "remaining": quota.remaining if not quota.is_unlimited else "unlimited",
                    "percentage_left": quota.percentage_left,
                    "reset_at": quota.reset_at.isoformat(),
                    "time_until_reset": str(quota.time_until_reset),
                }

        # Get cost summaries
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        with sqlite3.connect(self.db_path) as conn:
            # Today's cost
            cursor = conn.execute("""
                SELECT COALESCE(SUM(estimated_cost), 0), COALESCE(SUM(tokens_in + tokens_out), 0)
                FROM usage_history
                WHERE user_id = ? AND timestamp LIKE ?
            """, (user_id, f"{today}%"))
            row = cursor.fetchone()
            summary["cost_today"] = row[0]
            summary["total_tokens_today"] = row[1]

            # Month's cost
            cursor = conn.execute("""
                SELECT COALESCE(SUM(estimated_cost), 0)
                FROM usage_history
                WHERE user_id = ? AND timestamp LIKE ?
            """, (user_id, f"{month}%"))
            summary["cost_month"] = cursor.fetchone()[0]

        return summary

    def reset_quota(self, user_id: int, period: str):
        """
        Manually reset a user's quota for a period.

        Args:
            user_id: User ID
            period: "hour", "day", or "month"
        """
        now = datetime.now(timezone.utc)
        new_reset = self._calculate_reset_time(period, now)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE usage_quotas
                SET tokens_used = 0, reset_at = ?
                WHERE user_id = ? AND period = ?
            """, (new_reset.isoformat(), user_id, period))
            conn.commit()

        logger.info(f"Manually reset {period} quota for user {user_id}")

    def get_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get usage alerts for a user.

        Returns list of alerts with level, period, and message.
        """
        alerts = []

        for period in ["hour", "day", "month"]:
            quota = self.get_quota(user_id, period)
            if quota and not quota.is_unlimited:
                pct_used = quota.percentage_used

                if pct_used >= ALERT_THRESHOLDS["critical"]:
                    alerts.append({
                        "level": "critical",
                        "period": period,
                        "message": f"{period.capitalize()} quota at {pct_used:.0f}% - nearly exhausted!",
                        "percentage_used": pct_used,
                    })
                elif pct_used >= ALERT_THRESHOLDS["warning"]:
                    alerts.append({
                        "level": "warning",
                        "period": period,
                        "message": f"{period.capitalize()} quota at {pct_used:.0f}% - approaching limit",
                        "percentage_used": pct_used,
                    })

        return alerts

    def format_usage_status(self, user_id: int) -> str:
        """
        Format Clawdbot-style usage status string.

        Returns something like:
        "5h 98% left T3h 58m - Day 59% left T2d 11h - $2.34/$10"
        """
        summary = self.get_usage_summary(user_id)
        parts = []

        # Hourly status
        hourly = summary.get("hourly")
        if hourly and hourly.get("limit", -1) != -1:
            pct = hourly["percentage_left"]
            quota = self.get_quota(user_id, "hour")
            if quota:
                time_left = quota.time_until_reset
                mins = int(time_left.total_seconds() // 60)
                parts.append(f"5h {pct:.0f}% left T{mins}m")

        # Daily status
        daily = summary.get("daily")
        if daily and daily.get("limit", -1) != -1:
            pct = daily["percentage_left"]
            quota = self.get_quota(user_id, "day")
            if quota:
                time_left = quota.time_until_reset
                hours = int(time_left.total_seconds() // 3600)
                parts.append(f"Day {pct:.0f}% left T{hours}h")

        # Cost today
        cost_today = summary.get("cost_today", 0)
        parts.append(f"${cost_today:.2f}")

        return " - ".join(parts)

    def set_custom_quota(self, user_id: int, period: str, new_limit: int):
        """
        Set a custom quota limit for a user.

        Args:
            user_id: User ID
            period: "hour", "day", or "month"
            new_limit: New token limit (-1 for unlimited)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE usage_quotas
                SET token_limit = ?
                WHERE user_id = ? AND period = ?
            """, (new_limit, user_id, period))

            if conn.total_changes == 0:
                # Row doesn't exist, create it
                now = datetime.now(timezone.utc)
                reset_at = self._calculate_reset_time(period, now)
                conn.execute("""
                    INSERT INTO usage_quotas (user_id, period, token_limit, tokens_used, reset_at)
                    VALUES (?, ?, ?, 0, ?)
                """, (user_id, period, new_limit, reset_at.isoformat()))

            conn.commit()

        logger.info(f"Set custom {period} quota for user {user_id}: {new_limit}")

    def get_all_users_usage(self) -> List[Dict[str, Any]]:
        """
        Get usage summary for all users (admin function).

        Returns list of user summaries.
        """
        users = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT user_id FROM usage_quotas
            """)
            user_ids = [row[0] for row in cursor.fetchall()]

        for user_id in user_ids:
            summary = self.get_usage_summary(user_id)
            users.append(summary)

        return users

    def get_cost_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate cost report for the specified period.

        Args:
            days: Number of days to include

        Returns:
            Report with total_cost, by_model, by_day breakdowns
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        report = {
            "period_days": days,
            "total_cost": 0.0,
            "total_tokens": 0,
            "by_model": {},
            "by_day": {},
        }

        with sqlite3.connect(self.db_path) as conn:
            # Total cost
            cursor = conn.execute("""
                SELECT COALESCE(SUM(estimated_cost), 0), COALESCE(SUM(tokens_in + tokens_out), 0)
                FROM usage_history
                WHERE timestamp >= ?
            """, (cutoff,))
            row = cursor.fetchone()
            report["total_cost"] = row[0]
            report["total_tokens"] = row[1]

            # By model
            cursor = conn.execute("""
                SELECT model_id, SUM(estimated_cost), SUM(tokens_in + tokens_out), COUNT(*)
                FROM usage_history
                WHERE timestamp >= ?
                GROUP BY model_id
            """, (cutoff,))
            for row in cursor.fetchall():
                report["by_model"][row[0]] = {
                    "cost": row[1],
                    "tokens": row[2],
                    "requests": row[3],
                }

            # By day
            cursor = conn.execute("""
                SELECT DATE(timestamp), SUM(estimated_cost), SUM(tokens_in + tokens_out)
                FROM usage_history
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp) DESC
            """, (cutoff,))
            for row in cursor.fetchall():
                report["by_day"][row[0]] = {
                    "cost": row[1],
                    "tokens": row[2],
                }

        return report


# Singleton instance
_tracker: Optional[UsageTracker] = None
_tracker_lock = threading.Lock()


def get_usage_tracker(db_path: Optional[Path] = None) -> UsageTracker:
    """Get or create singleton UsageTracker instance."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = UsageTracker(db_path=db_path)
    return _tracker
