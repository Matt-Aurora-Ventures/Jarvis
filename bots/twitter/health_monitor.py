"""
Health Monitor - Shadowban Detection & Self-Healing for Jarvis Twitter Bot

Implements monitoring patterns from 2026 agent architecture:
1. Engagement drop detection (potential shadowban indicator)
2. API quota tracking
3. Circuit breakers for velocity limits
4. Auto cool-down when issues detected

Per xbot.md: "The most reliable internal sign of a shadowban is a sudden,
drastic drop in impressions or engagement despite consistent posting."
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# State file for persistence
from core.state_paths import STATE_PATHS
HEALTH_STATE_FILE = STATE_PATHS.data_dir / "x_health_state.json"


class HealthStatus(Enum):
    """Overall health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    COOLDOWN = "cooldown"


@dataclass
class HealthMetrics:
    """Current health metrics."""
    status: HealthStatus = HealthStatus.HEALTHY
    avg_impressions_7d: float = 0.0
    avg_impressions_24h: float = 0.0
    impression_drop_pct: float = 0.0
    posts_today: int = 0
    replies_today: int = 0
    api_calls_today: int = 0
    last_post_time: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    warnings: List[str] = field(default_factory=list)
    last_check: Optional[datetime] = None


@dataclass
class VelocityLimits:
    """
    Rate limits per xbot.md recommendations:
    - Max 15 original tweets/day
    - Max 20 replies/day
    - Max 10 quote tweets/day
    - 2.5-4 hr spacing between posts
    """
    max_posts_per_day: int = 15
    max_replies_per_day: int = 20
    max_quotes_per_day: int = 10
    min_post_interval_seconds: int = 10800  # 3 hours
    impression_drop_threshold: float = 0.5  # 50% drop = warning
    cooldown_hours: int = 48  # Cooldown period if shadowbanned


class HealthMonitor:
    """
    Monitors account health and implements self-healing behaviors.

    Features:
    - Tracks engagement metrics over time
    - Detects potential shadowbans via impression drops
    - Enforces velocity limits to avoid triggering filters
    - Auto cool-down when issues detected
    """

    def __init__(self):
        """Initialize the health monitor."""
        self.limits = VelocityLimits()
        self.metrics = HealthMetrics()
        self._impression_history: List[Dict[str, Any]] = []
        self._load_state()

    def _load_state(self):
        """Load persisted state from disk."""
        try:
            if HEALTH_STATE_FILE.exists():
                data = json.loads(HEALTH_STATE_FILE.read_text())
                self.metrics.posts_today = data.get("posts_today", 0)
                self.metrics.replies_today = data.get("replies_today", 0)
                self.metrics.api_calls_today = data.get("api_calls_today", 0)
                self.metrics.avg_impressions_7d = data.get("avg_impressions_7d", 0)

                if data.get("cooldown_until"):
                    self.metrics.cooldown_until = datetime.fromisoformat(data["cooldown_until"])

                if data.get("last_post_time"):
                    self.metrics.last_post_time = datetime.fromisoformat(data["last_post_time"])

                self._impression_history = data.get("impression_history", [])

                # Reset daily counters if new day
                last_reset = data.get("last_reset_date")
                today = datetime.now().strftime("%Y-%m-%d")
                if last_reset != today:
                    self.metrics.posts_today = 0
                    self.metrics.replies_today = 0
                    self.metrics.api_calls_today = 0

                logger.info(f"Health state loaded: {self.metrics.status.value}")
        except Exception as e:
            logger.warning(f"Failed to load health state: {e}")

    def _save_state(self):
        """Persist state to disk."""
        try:
            HEALTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "posts_today": self.metrics.posts_today,
                "replies_today": self.metrics.replies_today,
                "api_calls_today": self.metrics.api_calls_today,
                "avg_impressions_7d": self.metrics.avg_impressions_7d,
                "cooldown_until": self.metrics.cooldown_until.isoformat() if self.metrics.cooldown_until else None,
                "last_post_time": self.metrics.last_post_time.isoformat() if self.metrics.last_post_time else None,
                "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
                "impression_history": self._impression_history[-168:],  # Keep 7 days (24 * 7)
            }
            HEALTH_STATE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save health state: {e}")

    def is_in_cooldown(self) -> bool:
        """Check if we're in a cooldown period."""
        if self.metrics.cooldown_until:
            if datetime.now() < self.metrics.cooldown_until:
                return True
            else:
                # Cooldown expired
                self.metrics.cooldown_until = None
                self.metrics.status = HealthStatus.HEALTHY
                self._save_state()
        return False

    def can_post(self) -> tuple[bool, str]:
        """
        Check if posting is allowed based on health and velocity limits.

        Returns:
            (allowed, reason)
        """
        # Check cooldown
        if self.is_in_cooldown():
            remaining = (self.metrics.cooldown_until - datetime.now()).total_seconds() / 3600
            return False, f"In cooldown for {remaining:.1f} more hours"

        # Check daily post limit
        if self.metrics.posts_today >= self.limits.max_posts_per_day:
            return False, f"Daily post limit reached ({self.limits.max_posts_per_day})"

        # Check posting interval
        if self.metrics.last_post_time:
            elapsed = (datetime.now() - self.metrics.last_post_time).total_seconds()
            if elapsed < self.limits.min_post_interval_seconds:
                remaining = (self.limits.min_post_interval_seconds - elapsed) / 60
                return False, f"Too soon since last post. Wait {remaining:.0f} min"

        return True, "OK"

    def can_reply(self) -> tuple[bool, str]:
        """Check if replying is allowed."""
        if self.is_in_cooldown():
            return False, "In cooldown"

        if self.metrics.replies_today >= self.limits.max_replies_per_day:
            return False, f"Daily reply limit reached ({self.limits.max_replies_per_day})"

        return True, "OK"

    def record_post(self):
        """Record that a post was made."""
        self.metrics.posts_today += 1
        self.metrics.last_post_time = datetime.now()
        self._save_state()
        logger.info(f"Post recorded. Today: {self.metrics.posts_today}/{self.limits.max_posts_per_day}")

    def record_reply(self):
        """Record that a reply was made."""
        self.metrics.replies_today += 1
        self._save_state()

    def record_api_call(self):
        """Record an API call for quota tracking."""
        self.metrics.api_calls_today += 1

    def record_impressions(self, impressions: int, tweet_id: str):
        """
        Record impression data for trend analysis.

        Args:
            impressions: Number of impressions
            tweet_id: The tweet ID
        """
        self._impression_history.append({
            "timestamp": datetime.now().isoformat(),
            "impressions": impressions,
            "tweet_id": tweet_id,
        })
        self._save_state()

    def check_shadowban_indicators(self) -> tuple[bool, List[str]]:
        """
        Check for potential shadowban indicators.

        Returns:
            (is_concerning, list of warning messages)
        """
        warnings = []

        if len(self._impression_history) < 10:
            return False, ["Insufficient data for shadowban detection"]

        # Calculate 7-day average
        week_ago = datetime.now() - timedelta(days=7)
        recent_impressions = [
            h["impressions"] for h in self._impression_history
            if datetime.fromisoformat(h["timestamp"]) > week_ago
        ]

        if recent_impressions:
            self.metrics.avg_impressions_7d = sum(recent_impressions) / len(recent_impressions)

        # Calculate 24-hour average
        day_ago = datetime.now() - timedelta(days=1)
        today_impressions = [
            h["impressions"] for h in self._impression_history
            if datetime.fromisoformat(h["timestamp"]) > day_ago
        ]

        if today_impressions:
            self.metrics.avg_impressions_24h = sum(today_impressions) / len(today_impressions)

        # Check for significant drop
        if self.metrics.avg_impressions_7d > 0:
            drop_pct = 1 - (self.metrics.avg_impressions_24h / self.metrics.avg_impressions_7d)
            self.metrics.impression_drop_pct = drop_pct

            if drop_pct >= self.limits.impression_drop_threshold:
                warnings.append(
                    f"Impressions dropped {drop_pct*100:.0f}% vs 7-day avg. "
                    f"(Today: {self.metrics.avg_impressions_24h:.0f}, "
                    f"7d avg: {self.metrics.avg_impressions_7d:.0f})"
                )

        return len(warnings) > 0, warnings

    def trigger_cooldown(self, reason: str, hours: Optional[int] = None):
        """
        Enter cooldown mode (self-healing response to potential issues).

        Args:
            reason: Why cooldown was triggered
            hours: Override default cooldown duration
        """
        cooldown_hours = hours or self.limits.cooldown_hours
        self.metrics.cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
        self.metrics.status = HealthStatus.COOLDOWN
        self.metrics.warnings.append(f"{datetime.now().isoformat()}: {reason}")
        self._save_state()

        logger.warning(f"COOLDOWN TRIGGERED: {reason}. Resuming in {cooldown_hours}h")

        # Try to send alert
        try:
            from bots.twitter.telegram_sync import send_telegram_alert
            send_telegram_alert(f"X Bot Cooldown: {reason}")
        except Exception:
            pass

    async def run_health_check(self) -> HealthMetrics:
        """
        Run a comprehensive health check.

        Returns:
            Current health metrics
        """
        self.metrics.last_check = datetime.now()
        self.metrics.warnings = []

        # Check cooldown status
        if self.is_in_cooldown():
            self.metrics.status = HealthStatus.COOLDOWN
            return self.metrics

        # Check shadowban indicators
        is_concerning, warnings = self.check_shadowban_indicators()
        self.metrics.warnings.extend(warnings)

        if is_concerning:
            self.metrics.status = HealthStatus.WARNING
            # Auto-trigger cooldown if drop is severe (>70%)
            if self.metrics.impression_drop_pct >= 0.7:
                self.trigger_cooldown("Severe impression drop detected (>70%)")
        else:
            self.metrics.status = HealthStatus.HEALTHY

        self._save_state()
        return self.metrics

    def get_status_report(self) -> str:
        """Generate a human-readable status report."""
        lines = [
            f"=== X Bot Health Report ===",
            f"Status: {self.metrics.status.value.upper()}",
            f"Posts today: {self.metrics.posts_today}/{self.limits.max_posts_per_day}",
            f"Replies today: {self.metrics.replies_today}/{self.limits.max_replies_per_day}",
            f"7d avg impressions: {self.metrics.avg_impressions_7d:.0f}",
            f"24h avg impressions: {self.metrics.avg_impressions_24h:.0f}",
        ]

        if self.metrics.impression_drop_pct > 0:
            lines.append(f"Impression change: {-self.metrics.impression_drop_pct*100:.1f}%")

        if self.metrics.cooldown_until:
            remaining = (self.metrics.cooldown_until - datetime.now()).total_seconds() / 3600
            lines.append(f"Cooldown remaining: {remaining:.1f} hours")

        if self.metrics.warnings:
            lines.append("\nWarnings:")
            for w in self.metrics.warnings[-5:]:
                lines.append(f"  - {w}")

        return "\n".join(lines)


# Singleton instance
_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the singleton health monitor."""
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
    return _monitor
