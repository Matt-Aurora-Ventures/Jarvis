"""
ClawdBot Analytics Module.

Provides analytics tracking and reporting for ClawdBots.

Features:
- Track bot usage metrics (messages, commands, API calls, errors)
- Generate daily and weekly usage reports
- Identify trends and patterns
- Support custom events

Storage:
- Daily aggregates: /root/clawdbots/analytics/daily_{date}.json
- Rolling events: /root/clawdbots/analytics/events.json (max 1000)

Usage:
    from bots.shared.analytics import (
        track_event,
        get_daily_stats,
        get_weekly_report,
        get_popular_commands,
        get_active_users,
    )

    # Track an event
    track_event("clawdjarvis", "message_received", {"user_id": "123"})

    # Get daily stats
    stats = get_daily_stats(bot_name="clawdjarvis")

    # Get weekly report
    report = get_weekly_report()
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Default analytics directory (VPS path)
DEFAULT_ANALYTICS_DIR = "/root/clawdbots/analytics"

# Maximum rolling events to keep
MAX_ROLLING_EVENTS = 1000

# Supported event types
EVENT_TYPES = {
    "message_received",
    "message_sent",
    "command_executed",
    "api_called",
    "error_occurred",
    "user_joined",
}

# =============================================================================
# Module State
# =============================================================================

# Allow override for testing
_analytics_dir: Optional[str] = None

# In-memory caches (for performance)
_events_cache: List[Dict[str, Any]] = []
_daily_aggregates: Dict[str, Dict[str, Any]] = {}


def _get_analytics_dir() -> str:
    """Get analytics directory, creating if needed."""
    global _analytics_dir

    if _analytics_dir is not None:
        path = Path(_analytics_dir)
    else:
        # Use environment variable or default
        path = Path(os.environ.get("CLAWDBOT_ANALYTICS_DIR", DEFAULT_ANALYTICS_DIR))

    # Create directory if it doesn't exist
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        logger.warning(f"Could not create analytics dir {path}: {e}")
        # Fall back to temp directory
        import tempfile
        path = Path(tempfile.gettempdir()) / "clawdbot_analytics"
        path.mkdir(parents=True, exist_ok=True)

    return str(path)


def _events_file() -> Path:
    """Get path to events.json file."""
    return Path(_get_analytics_dir()) / "events.json"


def _daily_file(date: str) -> Path:
    """Get path to daily aggregate file."""
    return Path(_get_analytics_dir()) / f"daily_{date}.json"


# =============================================================================
# Event Storage
# =============================================================================


def _load_events() -> List[Dict[str, Any]]:
    """Load events from file."""
    global _events_cache

    events_path = _events_file()

    if events_path.exists():
        try:
            with open(events_path, "r") as f:
                _events_cache = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading events: {e}")
            _events_cache = []
    else:
        _events_cache = []

    return _events_cache


def _save_events(events: List[Dict[str, Any]]) -> None:
    """Save events to file."""
    global _events_cache

    _events_cache = events

    events_path = _events_file()

    try:
        with open(events_path, "w") as f:
            json.dump(events, f, indent=2, default=str)
    except IOError as e:
        logger.error(f"Error saving events: {e}")


def _load_daily_aggregates(date: str) -> Dict[str, Any]:
    """Load daily aggregates from file."""
    daily_path = _daily_file(date)

    if daily_path.exists():
        try:
            with open(daily_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading daily aggregates: {e}")

    return {
        "date": date,
        "total_events": 0,
        "by_type": defaultdict(int),
        "by_bot": defaultdict(int),
        "commands": defaultdict(int),
        "users": set(),
    }


def _save_daily_aggregates(date: str, data: Dict[str, Any]) -> None:
    """Save daily aggregates to file."""
    daily_path = _daily_file(date)

    # Convert sets and defaultdicts for JSON serialization
    serializable = {
        "date": data["date"],
        "total_events": data["total_events"],
        "by_type": dict(data.get("by_type", {})),
        "by_bot": dict(data.get("by_bot", {})),
        "commands": dict(data.get("commands", {})),
        "unique_users": len(data.get("users", set())),
        "user_list": list(data.get("users", set())),
    }

    try:
        with open(daily_path, "w") as f:
            json.dump(serializable, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving daily aggregates: {e}")


def _save_daily_aggregates_for_testing(aggregates: List[Dict[str, Any]]) -> None:
    """Helper for tests to save multiple daily aggregates."""
    for agg in aggregates:
        date = agg["date"]
        data = {
            "date": date,
            "total_events": agg.get("total", 0),
            "by_type": {},
            "by_bot": {},
            "commands": {},
            "users": set(),
        }
        _save_daily_aggregates(date, data)


# =============================================================================
# Core Functions
# =============================================================================


def track_event(
    bot_name: str,
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Track a bot event.

    Args:
        bot_name: Name of the bot (e.g., "clawdjarvis", "clawdmatt")
        event_type: Type of event (message_received, command_executed, etc.)
        data: Additional event data (user_id, command, error, etc.)

    Event types:
        - message_received: Bot received a message
        - message_sent: Bot sent a message
        - command_executed: Bot executed a command
        - api_called: Bot made an API call
        - error_occurred: An error occurred
        - user_joined: New user started interacting
    """
    if data is None:
        data = {}

    timestamp = datetime.utcnow()

    event = {
        "bot_name": bot_name,
        "event_type": event_type,
        "timestamp": timestamp.isoformat(),
        "data": data,
    }

    # Load current events
    events = _load_events()

    # Add new event
    events.append(event)

    # Enforce rolling limit
    if len(events) > MAX_ROLLING_EVENTS:
        events = events[-MAX_ROLLING_EVENTS:]

    # Save events
    _save_events(events)

    # Update daily aggregates
    _update_daily_aggregates(event, timestamp)

    logger.debug(f"Tracked event: {event_type} for {bot_name}")


def _update_daily_aggregates(event: Dict[str, Any], timestamp: datetime) -> None:
    """Update daily aggregates with new event."""
    date_str = timestamp.strftime("%Y-%m-%d")

    # Load or create daily data
    if date_str not in _daily_aggregates:
        _daily_aggregates[date_str] = _load_daily_aggregates(date_str)

    daily = _daily_aggregates[date_str]

    # Ensure proper types
    if not isinstance(daily.get("by_type"), dict):
        daily["by_type"] = defaultdict(int)
    if not isinstance(daily.get("by_bot"), dict):
        daily["by_bot"] = defaultdict(int)
    if not isinstance(daily.get("commands"), dict):
        daily["commands"] = defaultdict(int)
    if not isinstance(daily.get("users"), set):
        daily["users"] = set(daily.get("user_list", []))

    # Update counts
    daily["total_events"] = daily.get("total_events", 0) + 1
    daily["by_type"][event["event_type"]] = daily["by_type"].get(event["event_type"], 0) + 1
    daily["by_bot"][event["bot_name"]] = daily["by_bot"].get(event["bot_name"], 0) + 1

    # Track commands
    if event["event_type"] == "command_executed" and "command" in event["data"]:
        cmd = event["data"]["command"]
        daily["commands"][cmd] = daily["commands"].get(cmd, 0) + 1

    # Track unique users
    if "user_id" in event["data"]:
        daily["users"].add(event["data"]["user_id"])

    # Save (could be optimized with periodic flush)
    _save_daily_aggregates(date_str, daily)


def _flush_daily_aggregates() -> None:
    """Flush all daily aggregates to disk."""
    for date_str, daily in _daily_aggregates.items():
        _save_daily_aggregates(date_str, daily)


def get_daily_stats(bot_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get daily statistics.

    Args:
        bot_name: Optional bot name filter. If None, returns aggregate stats.

    Returns:
        Dict with:
        - date: Today's date
        - total_events: Total event count
        - by_type: Events broken down by type
        - by_bot: Events broken down by bot
        - unique_users: Count of unique users
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Load today's aggregates
    if today in _daily_aggregates:
        daily = _daily_aggregates[today]
    else:
        daily = _load_daily_aggregates(today)

    if bot_name:
        # Filter to specific bot
        events = _load_events()
        today_events = [
            e for e in events
            if e["timestamp"].startswith(today) and e["bot_name"] == bot_name
        ]

        by_type = defaultdict(int)
        users = set()

        for e in today_events:
            by_type[e["event_type"]] += 1
            if "user_id" in e["data"]:
                users.add(e["data"]["user_id"])

        return {
            "date": today,
            "bot_name": bot_name,
            "total_events": len(today_events),
            "by_type": dict(by_type),
            "by_bot": {bot_name: len(today_events)},
            "unique_users": len(users),
        }
    else:
        # Return aggregate stats
        return {
            "date": today,
            "total_events": daily.get("total_events", 0),
            "by_type": dict(daily.get("by_type", {})),
            "by_bot": dict(daily.get("by_bot", {})),
            "unique_users": len(daily.get("users", set())) or daily.get("unique_users", 0),
        }


def get_weekly_report(bot_name: Optional[str] = None) -> str:
    """
    Generate a weekly usage report.

    Args:
        bot_name: Optional bot name filter

    Returns:
        Formatted report string
    """
    # Gather data for last 7 days
    today = datetime.utcnow()
    daily_data = []

    for i in range(7):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        daily = _load_daily_aggregates(date)
        daily_data.append(daily)

    # Calculate totals
    total_events = sum(d.get("total_events", 0) for d in daily_data)
    all_types = defaultdict(int)
    all_bots = defaultdict(int)
    all_commands = defaultdict(int)
    all_users = set()

    for d in daily_data:
        for t, count in d.get("by_type", {}).items():
            all_types[t] += count
        for b, count in d.get("by_bot", {}).items():
            all_bots[b] += count
        for c, count in d.get("commands", {}).items():
            all_commands[c] += count
        for u in d.get("user_list", []):
            all_users.add(u)

    # Filter by bot if specified
    if bot_name:
        all_bots = {k: v for k, v in all_bots.items() if k == bot_name}
        total_events = all_bots.get(bot_name, 0)

    # Build report
    lines = [
        "=" * 50,
        f"CLAWDBOT WEEKLY REPORT",
        f"Period: {(today - timedelta(days=6)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}",
        "=" * 50,
        "",
        f"Total Events: {total_events:,}",
        f"Unique Users: {len(all_users):,}",
        "",
        "Events by Type:",
    ]

    for event_type, count in sorted(all_types.items(), key=lambda x: -x[1]):
        lines.append(f"  - {event_type}: {count:,}")

    if not bot_name:
        lines.append("")
        lines.append("Events by Bot:")
        for bot, count in sorted(all_bots.items(), key=lambda x: -x[1]):
            lines.append(f"  - {bot}: {count:,}")

    lines.append("")
    lines.append("Top Commands:")
    top_commands = sorted(all_commands.items(), key=lambda x: -x[1])[:10]
    for cmd, count in top_commands:
        lines.append(f"  - {cmd}: {count:,}")

    # Add trend
    trend = detect_usage_trend()
    lines.append("")
    lines.append(f"Usage Trend: {trend['direction'].upper()} ({trend['change_percent']:+.1f}%)")
    lines.append("=" * 50)

    return "\n".join(lines)


def get_popular_commands(
    bot_name: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get most popular commands.

    Args:
        bot_name: Optional bot name filter
        limit: Maximum number of commands to return

    Returns:
        List of {command, count, bot_name} dicts sorted by popularity
    """
    events = _load_events()

    command_counts = defaultdict(lambda: {"count": 0, "bots": set()})

    for event in events:
        if event["event_type"] != "command_executed":
            continue
        if "command" not in event["data"]:
            continue
        if bot_name and event["bot_name"] != bot_name:
            continue

        cmd = event["data"]["command"]
        command_counts[cmd]["count"] += 1
        command_counts[cmd]["bots"].add(event["bot_name"])

    # Sort by count
    sorted_commands = sorted(
        command_counts.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:limit]

    return [
        {
            "command": cmd,
            "count": data["count"],
            "bots": list(data["bots"]),
        }
        for cmd, data in sorted_commands
    ]


def get_active_users(
    bot_name: Optional[str] = None,
    period: str = "day",
) -> int:
    """
    Get count of active users.

    Args:
        bot_name: Optional bot name filter
        period: "day" or "week"

    Returns:
        Count of unique active users
    """
    events = _load_events()

    # Determine cutoff
    now = datetime.utcnow()
    if period == "week":
        cutoff = now - timedelta(days=7)
    else:  # day
        cutoff = now - timedelta(days=1)

    cutoff_str = cutoff.isoformat()

    users = set()

    for event in events:
        if event["timestamp"] < cutoff_str:
            continue
        if bot_name and event["bot_name"] != bot_name:
            continue
        if "user_id" in event["data"]:
            users.add(event["data"]["user_id"])

    return len(users)


def detect_usage_trend() -> Dict[str, Any]:
    """
    Detect usage trend over recent days.

    Returns:
        Dict with:
        - direction: "increasing", "decreasing", or "stable"
        - change_percent: Percentage change
    """
    today = datetime.utcnow()

    # Get last 7 days of totals
    totals = []
    for i in range(7):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        daily = _load_daily_aggregates(date)
        totals.append(daily.get("total_events", 0))

    totals.reverse()  # Oldest first

    if len(totals) < 2:
        return {"direction": "stable", "change_percent": 0.0}

    # Calculate trend using linear comparison
    first_half = sum(totals[:len(totals)//2]) or 1
    second_half = sum(totals[len(totals)//2:]) or 1

    change_percent = ((second_half - first_half) / first_half) * 100

    # Determine direction
    if change_percent > 10:
        direction = "increasing"
    elif change_percent < -10:
        direction = "decreasing"
    else:
        direction = "stable"

    return {
        "direction": direction,
        "change_percent": round(change_percent, 1),
        "daily_totals": totals,
    }


# =============================================================================
# Convenience Functions
# =============================================================================


def track_message_received(bot_name: str, user_id: str, **kwargs) -> None:
    """Track a message received event."""
    track_event(bot_name, "message_received", {"user_id": user_id, **kwargs})


def track_message_sent(bot_name: str, user_id: Optional[str] = None, **kwargs) -> None:
    """Track a message sent event."""
    data = kwargs
    if user_id:
        data["user_id"] = user_id
    track_event(bot_name, "message_sent", data)


def track_command(bot_name: str, command: str, user_id: str, **kwargs) -> None:
    """Track a command execution."""
    track_event(bot_name, "command_executed", {
        "command": command,
        "user_id": user_id,
        **kwargs,
    })


def track_api_call(bot_name: str, endpoint: str, **kwargs) -> None:
    """Track an API call."""
    track_event(bot_name, "api_called", {"endpoint": endpoint, **kwargs})


def track_error(bot_name: str, error: str, **kwargs) -> None:
    """Track an error."""
    track_event(bot_name, "error_occurred", {"error": error, **kwargs})


def track_user_joined(bot_name: str, user_id: str, **kwargs) -> None:
    """Track a new user joining."""
    track_event(bot_name, "user_joined", {"user_id": user_id, **kwargs})


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core functions
    "track_event",
    "get_daily_stats",
    "get_weekly_report",
    "get_popular_commands",
    "get_active_users",
    "detect_usage_trend",
    # Convenience functions
    "track_message_received",
    "track_message_sent",
    "track_command",
    "track_api_call",
    "track_error",
    "track_user_joined",
    # Internal (for testing)
    "_load_events",
    "_save_events",
    "_flush_daily_aggregates",
    "_save_daily_aggregates_for_testing",
]
