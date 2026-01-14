"""
JARVIS Bot Analytics

Tracks and analyzes bot usage patterns, user engagement,
command popularity, and performance metrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class BotPlatform(Enum):
    """Supported bot platforms."""
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    DISCORD = "discord"


class EventType(Enum):
    """Types of bot events."""
    MESSAGE = "message"
    COMMAND = "command"
    CALLBACK = "callback"
    MENTION = "mention"
    REPLY = "reply"
    ERROR = "error"


@dataclass
class UserSession:
    """Represents a user session."""
    user_id: str
    platform: BotPlatform
    start_time: datetime
    last_activity: datetime
    message_count: int = 0
    command_count: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CommandStats:
    """Statistics for a command."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    unique_users: Set[str] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def average_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "average_latency_ms": self.average_latency_ms,
            "unique_users": len(self.unique_users),
        }


@dataclass
class DailyStats:
    """Daily statistics snapshot."""
    date: str
    total_messages: int = 0
    total_commands: int = 0
    unique_users: int = 0
    new_users: int = 0
    errors: int = 0
    average_response_time_ms: float = 0.0


class BotAnalytics:
    """
    Collects and analyzes bot usage analytics.

    Usage:
        analytics = BotAnalytics()
        analytics.track_event(
            platform=BotPlatform.TELEGRAM,
            event_type=EventType.COMMAND,
            user_id="123",
            command="/help"
        )
        stats = analytics.get_daily_stats()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events: List[Dict[str, Any]] = []
        self._sessions: Dict[str, UserSession] = {}
        self._command_stats: Dict[str, CommandStats] = {}
        self._known_users: Set[str] = set()
        self._daily_stats: Dict[str, DailyStats] = {}

    # =========================================================================
    # Event Tracking
    # =========================================================================

    def track_event(
        self,
        platform: BotPlatform,
        event_type: EventType,
        user_id: str,
        command: Optional[str] = None,
        latency_ms: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a bot event."""
        now = datetime.utcnow()

        event = {
            "platform": platform.value,
            "event_type": event_type.value,
            "user_id": user_id,
            "command": command,
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": now,
            "metadata": metadata or {},
        }

        with self._lock:
            self._events.append(event)
            self._update_session(user_id, platform, event_type, now)
            self._update_command_stats(command, user_id, latency_ms, success)
            self._update_daily_stats(now, event_type, user_id, success)

        logger.debug(f"Tracked event: {event_type.value} from {user_id}")

    def _update_session(
        self,
        user_id: str,
        platform: BotPlatform,
        event_type: EventType,
        timestamp: datetime
    ) -> None:
        """Update or create user session."""
        session_key = f"{platform.value}:{user_id}"

        if session_key not in self._sessions:
            self._sessions[session_key] = UserSession(
                user_id=user_id,
                platform=platform,
                start_time=timestamp,
                last_activity=timestamp,
            )

        session = self._sessions[session_key]
        session.last_activity = timestamp

        if event_type == EventType.MESSAGE:
            session.message_count += 1
        elif event_type == EventType.COMMAND:
            session.command_count += 1

    def _update_command_stats(
        self,
        command: Optional[str],
        user_id: str,
        latency_ms: Optional[float],
        success: bool
    ) -> None:
        """Update command statistics."""
        if not command:
            return

        if command not in self._command_stats:
            self._command_stats[command] = CommandStats(name=command)

        stats = self._command_stats[command]
        stats.total_calls += 1
        stats.unique_users.add(user_id)

        if success:
            stats.successful_calls += 1
        else:
            stats.failed_calls += 1

        if latency_ms is not None:
            stats.total_latency_ms += latency_ms

    def _update_daily_stats(
        self,
        timestamp: datetime,
        event_type: EventType,
        user_id: str,
        success: bool
    ) -> None:
        """Update daily statistics."""
        date_str = timestamp.strftime("%Y-%m-%d")

        if date_str not in self._daily_stats:
            self._daily_stats[date_str] = DailyStats(date=date_str)

        stats = self._daily_stats[date_str]

        if event_type == EventType.MESSAGE:
            stats.total_messages += 1
        elif event_type == EventType.COMMAND:
            stats.total_commands += 1
        elif event_type == EventType.ERROR:
            stats.errors += 1

        # Track new users
        if user_id not in self._known_users:
            self._known_users.add(user_id)
            stats.new_users += 1

    # =========================================================================
    # Analytics Queries
    # =========================================================================

    def get_command_stats(self, command: Optional[str] = None) -> Dict[str, Any]:
        """Get command statistics."""
        with self._lock:
            if command:
                if command in self._command_stats:
                    return self._command_stats[command].to_dict()
                return {}

            return {
                name: stats.to_dict()
                for name, stats in self._command_stats.items()
            }

    def get_top_commands(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top commands by usage."""
        with self._lock:
            sorted_commands = sorted(
                self._command_stats.values(),
                key=lambda x: x.total_calls,
                reverse=True
            )
            return [cmd.to_dict() for cmd in sorted_commands[:limit]]

    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily statistics for the past N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self._lock:
            result = []
            for date_str, stats in self._daily_stats.items():
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    if date >= cutoff:
                        result.append({
                            "date": date_str,
                            "total_messages": stats.total_messages,
                            "total_commands": stats.total_commands,
                            "unique_users": stats.unique_users,
                            "new_users": stats.new_users,
                            "errors": stats.errors,
                        })
                except ValueError:
                    pass

            return sorted(result, key=lambda x: x["date"])

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        with self._lock:
            user_sessions = [
                s for s in self._sessions.values()
                if s.user_id == user_id
            ]

            user_events = [
                e for e in self._events
                if e["user_id"] == user_id
            ]

            if not user_sessions:
                return {"user_id": user_id, "exists": False}

            total_messages = sum(s.message_count for s in user_sessions)
            total_commands = sum(s.command_count for s in user_sessions)

            first_seen = min(s.start_time for s in user_sessions)
            last_seen = max(s.last_activity for s in user_sessions)

            return {
                "user_id": user_id,
                "exists": True,
                "total_messages": total_messages,
                "total_commands": total_commands,
                "first_seen": first_seen.isoformat(),
                "last_seen": last_seen.isoformat(),
                "platforms": list(set(s.platform.value for s in user_sessions)),
                "events_count": len(user_events),
            }

    def get_active_users(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get list of active users in the past N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        with self._lock:
            active = {}
            for session in self._sessions.values():
                if session.last_activity > cutoff:
                    if session.user_id not in active:
                        active[session.user_id] = {
                            "user_id": session.user_id,
                            "last_activity": session.last_activity.isoformat(),
                            "message_count": 0,
                            "command_count": 0,
                            "platforms": [],
                        }
                    user = active[session.user_id]
                    user["message_count"] += session.message_count
                    user["command_count"] += session.command_count
                    user["platforms"].append(session.platform.value)

            return list(active.values())

    def get_engagement_metrics(self) -> Dict[str, Any]:
        """Get overall engagement metrics."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        with self._lock:
            events_24h = [e for e in self._events if e["timestamp"] > day_ago]
            events_7d = [e for e in self._events if e["timestamp"] > week_ago]
            events_30d = [e for e in self._events if e["timestamp"] > month_ago]

            users_24h = set(e["user_id"] for e in events_24h)
            users_7d = set(e["user_id"] for e in events_7d)
            users_30d = set(e["user_id"] for e in events_30d)

            # Calculate retention
            retention_7d = len(users_24h & users_7d) / len(users_7d) if users_7d else 0

            return {
                "total_users": len(self._known_users),
                "active_users_24h": len(users_24h),
                "active_users_7d": len(users_7d),
                "active_users_30d": len(users_30d),
                "events_24h": len(events_24h),
                "events_7d": len(events_7d),
                "events_30d": len(events_30d),
                "retention_rate_7d": retention_7d,
                "commands_tracked": len(self._command_stats),
            }

    def get_platform_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Get event breakdown by platform."""
        with self._lock:
            breakdown = defaultdict(lambda: defaultdict(int))

            for event in self._events:
                platform = event["platform"]
                event_type = event["event_type"]
                breakdown[platform][event_type] += 1
                breakdown[platform]["total"] += 1

            return dict(breakdown)

    def get_hourly_distribution(self, days: int = 7) -> Dict[int, int]:
        """Get event distribution by hour of day."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self._lock:
            hourly = defaultdict(int)

            for event in self._events:
                if event["timestamp"] > cutoff:
                    hour = event["timestamp"].hour
                    hourly[hour] += 1

            return dict(sorted(hourly.items()))

    # =========================================================================
    # Reports
    # =========================================================================

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a comprehensive analytics summary."""
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "engagement": self.get_engagement_metrics(),
            "top_commands": self.get_top_commands(5),
            "daily_stats": self.get_daily_stats(7),
            "platform_breakdown": self.get_platform_breakdown(),
            "hourly_distribution": self.get_hourly_distribution(),
        }

    # =========================================================================
    # Maintenance
    # =========================================================================

    def cleanup_old_events(self, days: int = 30) -> int:
        """Remove events older than N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self._lock:
            original_count = len(self._events)
            self._events = [
                e for e in self._events
                if e["timestamp"] > cutoff
            ]
            removed = original_count - len(self._events)

        logger.info(f"Cleaned up {removed} old analytics events")
        return removed


# Global instance
_analytics: Optional[BotAnalytics] = None


def get_bot_analytics() -> BotAnalytics:
    """Get the global bot analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = BotAnalytics()
    return _analytics


# Convenience functions
def track_telegram_message(user_id: str, **kwargs) -> None:
    """Track a Telegram message."""
    get_bot_analytics().track_event(
        platform=BotPlatform.TELEGRAM,
        event_type=EventType.MESSAGE,
        user_id=user_id,
        **kwargs
    )


def track_telegram_command(user_id: str, command: str, **kwargs) -> None:
    """Track a Telegram command."""
    get_bot_analytics().track_event(
        platform=BotPlatform.TELEGRAM,
        event_type=EventType.COMMAND,
        user_id=user_id,
        command=command,
        **kwargs
    )


def track_twitter_mention(user_id: str, **kwargs) -> None:
    """Track a Twitter mention."""
    get_bot_analytics().track_event(
        platform=BotPlatform.TWITTER,
        event_type=EventType.MENTION,
        user_id=user_id,
        **kwargs
    )


def track_bot_error(platform: BotPlatform, user_id: str, **kwargs) -> None:
    """Track a bot error."""
    get_bot_analytics().track_event(
        platform=platform,
        event_type=EventType.ERROR,
        user_id=user_id,
        success=False,
        **kwargs
    )
