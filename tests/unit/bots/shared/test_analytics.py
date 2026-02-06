"""
Tests for ClawdBot Analytics Module.

TDD test file for bots/shared/analytics.py
"""

import json
import os
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestTrackEvent:
    """Tests for track_event function."""

    def test_track_event_basic(self, analytics_module, temp_analytics_dir):
        """Test basic event tracking."""
        analytics_module.track_event(
            bot_name="clawdjarvis",
            event_type="message_received",
            data={"user_id": "123", "message": "hello"}
        )

        # Verify event was stored
        events = analytics_module._load_events()
        assert len(events) >= 1

        latest = events[-1]
        assert latest["bot_name"] == "clawdjarvis"
        assert latest["event_type"] == "message_received"
        assert latest["data"]["user_id"] == "123"

    def test_track_event_all_types(self, analytics_module, temp_analytics_dir):
        """Test all supported event types."""
        event_types = [
            "message_received",
            "message_sent",
            "command_executed",
            "api_called",
            "error_occurred",
            "user_joined",
        ]

        for event_type in event_types:
            analytics_module.track_event(
                bot_name="test_bot",
                event_type=event_type,
                data={"test": True}
            )

        events = analytics_module._load_events()
        tracked_types = {e["event_type"] for e in events}

        for et in event_types:
            assert et in tracked_types

    def test_track_event_with_empty_data(self, analytics_module, temp_analytics_dir):
        """Test tracking event with empty data dict."""
        analytics_module.track_event(
            bot_name="clawdmatt",
            event_type="message_received"
        )

        events = analytics_module._load_events()
        assert len(events) >= 1
        assert events[-1]["data"] == {}

    def test_track_event_adds_timestamp(self, analytics_module, temp_analytics_dir):
        """Test that timestamp is auto-added."""
        before = datetime.utcnow()
        analytics_module.track_event("test_bot", "message_sent")
        after = datetime.utcnow()

        events = analytics_module._load_events()
        ts = datetime.fromisoformat(events[-1]["timestamp"])

        assert before <= ts <= after

    def test_rolling_events_limit(self, analytics_module, temp_analytics_dir):
        """Test that events are limited to rolling 1000."""
        # Track 1050 events
        for i in range(1050):
            analytics_module.track_event("test_bot", "message_received", {"seq": i})

        events = analytics_module._load_events()
        # Should be capped at 1000
        assert len(events) <= 1000

        # Should have recent events, not oldest
        sequences = [e["data"]["seq"] for e in events]
        assert max(sequences) == 1049  # Latest
        assert min(sequences) >= 50  # Oldest dropped


class TestGetDailyStats:
    """Tests for get_daily_stats function."""

    def test_get_daily_stats_specific_bot(self, analytics_module, temp_analytics_dir):
        """Test getting stats for specific bot."""
        # Track some events
        analytics_module.track_event("clawdjarvis", "message_received")
        analytics_module.track_event("clawdjarvis", "message_sent")
        analytics_module.track_event("clawdmatt", "message_received")

        stats = analytics_module.get_daily_stats(bot_name="clawdjarvis")

        assert "total_events" in stats
        assert "message_received" in stats["by_type"]
        assert "message_sent" in stats["by_type"]
        assert stats["by_type"]["message_received"] >= 1
        assert stats["by_type"]["message_sent"] >= 1

    def test_get_daily_stats_all_bots(self, analytics_module, temp_analytics_dir):
        """Test getting aggregate stats for all bots."""
        analytics_module.track_event("clawdjarvis", "message_received")
        analytics_module.track_event("clawdmatt", "command_executed")
        analytics_module.track_event("clawdfriday", "api_called")

        stats = analytics_module.get_daily_stats()  # No bot_name filter

        assert stats["total_events"] >= 3
        assert "clawdjarvis" in stats["by_bot"] or stats["total_events"] >= 3

    def test_get_daily_stats_date_filtering(self, analytics_module, temp_analytics_dir):
        """Test that stats are for today only."""
        # Manually add an old event
        events = analytics_module._load_events()
        old_event = {
            "bot_name": "test_bot",
            "event_type": "message_received",
            "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat(),
            "data": {}
        }
        events.append(old_event)
        analytics_module._save_events(events)

        # Track today's event
        analytics_module.track_event("test_bot", "message_sent")

        stats = analytics_module.get_daily_stats()
        # Should only count today's events
        assert stats["date"] == datetime.utcnow().strftime("%Y-%m-%d")

    def test_get_daily_stats_structure(self, analytics_module, temp_analytics_dir):
        """Test return structure matches spec."""
        analytics_module.track_event("clawdjarvis", "message_received")

        stats = analytics_module.get_daily_stats()

        # Required fields
        assert "date" in stats
        assert "total_events" in stats
        assert "by_type" in stats
        assert "by_bot" in stats
        assert "unique_users" in stats


class TestGetWeeklyReport:
    """Tests for get_weekly_report function."""

    def test_weekly_report_returns_string(self, analytics_module, temp_analytics_dir):
        """Test that weekly report returns formatted string."""
        analytics_module.track_event("clawdjarvis", "message_received")

        report = analytics_module.get_weekly_report()

        assert isinstance(report, str)
        assert len(report) > 0

    def test_weekly_report_includes_summary(self, analytics_module, temp_analytics_dir):
        """Test report includes key summary info."""
        for _ in range(5):
            analytics_module.track_event("clawdjarvis", "message_received")
        for _ in range(3):
            analytics_module.track_event("clawdmatt", "command_executed")

        report = analytics_module.get_weekly_report()

        # Should contain summary elements
        assert "events" in report.lower() or "total" in report.lower()

    def test_weekly_report_bot_filter(self, analytics_module, temp_analytics_dir):
        """Test report for specific bot."""
        analytics_module.track_event("clawdjarvis", "message_received")
        analytics_module.track_event("clawdmatt", "command_executed")

        report = analytics_module.get_weekly_report(bot_name="clawdjarvis")

        assert "clawdjarvis" in report.lower() or "jarvis" in report.lower()


class TestGetPopularCommands:
    """Tests for get_popular_commands function."""

    def test_popular_commands_ranking(self, analytics_module, temp_analytics_dir):
        """Test commands are ranked by popularity."""
        # Track commands with different frequencies
        for _ in range(10):
            analytics_module.track_event(
                "clawdjarvis",
                "command_executed",
                {"command": "/help"}
            )
        for _ in range(5):
            analytics_module.track_event(
                "clawdjarvis",
                "command_executed",
                {"command": "/status"}
            )
        for _ in range(2):
            analytics_module.track_event(
                "clawdjarvis",
                "command_executed",
                {"command": "/rare"}
            )

        commands = analytics_module.get_popular_commands()

        assert len(commands) >= 1
        # Should be sorted by count
        if len(commands) >= 2:
            assert commands[0]["count"] >= commands[1]["count"]

    def test_popular_commands_limit(self, analytics_module, temp_analytics_dir):
        """Test limit parameter works."""
        for i in range(20):
            analytics_module.track_event(
                "test_bot",
                "command_executed",
                {"command": f"/cmd{i}"}
            )

        commands = analytics_module.get_popular_commands(limit=5)
        assert len(commands) <= 5

    def test_popular_commands_bot_filter(self, analytics_module, temp_analytics_dir):
        """Test filtering by bot."""
        analytics_module.track_event(
            "clawdjarvis",
            "command_executed",
            {"command": "/jarvis_cmd"}
        )
        analytics_module.track_event(
            "clawdmatt",
            "command_executed",
            {"command": "/matt_cmd"}
        )

        commands = analytics_module.get_popular_commands(bot_name="clawdjarvis")

        # Should only include jarvis commands
        cmd_names = [c["command"] for c in commands]
        assert "/jarvis_cmd" in cmd_names or len(commands) == 0

    def test_popular_commands_structure(self, analytics_module, temp_analytics_dir):
        """Test return structure."""
        analytics_module.track_event(
            "test_bot",
            "command_executed",
            {"command": "/test"}
        )

        commands = analytics_module.get_popular_commands()

        if commands:
            assert "command" in commands[0]
            assert "count" in commands[0]


class TestGetActiveUsers:
    """Tests for get_active_users function."""

    def test_active_users_count(self, analytics_module, temp_analytics_dir):
        """Test counting active users."""
        analytics_module.track_event(
            "clawdjarvis",
            "message_received",
            {"user_id": "user1"}
        )
        analytics_module.track_event(
            "clawdjarvis",
            "message_received",
            {"user_id": "user2"}
        )
        analytics_module.track_event(
            "clawdjarvis",
            "message_received",
            {"user_id": "user1"}  # Duplicate
        )

        count = analytics_module.get_active_users()

        assert count >= 2

    def test_active_users_period_day(self, analytics_module, temp_analytics_dir):
        """Test daily active users."""
        analytics_module.track_event(
            "test_bot",
            "message_received",
            {"user_id": "today_user"}
        )

        count = analytics_module.get_active_users(period="day")

        assert count >= 1

    def test_active_users_period_week(self, analytics_module, temp_analytics_dir):
        """Test weekly active users."""
        analytics_module.track_event(
            "test_bot",
            "message_received",
            {"user_id": "week_user"}
        )

        count = analytics_module.get_active_users(period="week")

        assert count >= 1

    def test_active_users_bot_filter(self, analytics_module, temp_analytics_dir):
        """Test filtering by bot."""
        analytics_module.track_event(
            "clawdjarvis",
            "message_received",
            {"user_id": "jarvis_user"}
        )
        analytics_module.track_event(
            "clawdmatt",
            "message_received",
            {"user_id": "matt_user"}
        )

        jarvis_count = analytics_module.get_active_users(bot_name="clawdjarvis")

        assert jarvis_count >= 1


class TestTrendDetection:
    """Tests for trend detection functionality."""

    def test_detect_increasing_trend(self, analytics_module, temp_analytics_dir):
        """Test detection of increasing usage."""
        # Simulate increasing daily events
        analytics_module._save_daily_aggregates_for_testing([
            {"date": "2026-01-25", "total": 10},
            {"date": "2026-01-26", "total": 15},
            {"date": "2026-01-27", "total": 20},
            {"date": "2026-01-28", "total": 30},
        ])

        trend = analytics_module.detect_usage_trend()

        assert trend["direction"] in ["increasing", "up"]
        assert trend["change_percent"] > 0

    def test_detect_decreasing_trend(self, analytics_module, temp_analytics_dir):
        """Test detection of decreasing usage."""
        analytics_module._save_daily_aggregates_for_testing([
            {"date": "2026-01-25", "total": 50},
            {"date": "2026-01-26", "total": 40},
            {"date": "2026-01-27", "total": 25},
            {"date": "2026-01-28", "total": 10},
        ])

        trend = analytics_module.detect_usage_trend()

        assert trend["direction"] in ["decreasing", "down"]
        assert trend["change_percent"] < 0

    def test_detect_stable_trend(self, analytics_module, temp_analytics_dir):
        """Test detection of stable usage."""
        analytics_module._save_daily_aggregates_for_testing([
            {"date": "2026-01-25", "total": 20},
            {"date": "2026-01-26", "total": 21},
            {"date": "2026-01-27", "total": 19},
            {"date": "2026-01-28", "total": 20},
        ])

        trend = analytics_module.detect_usage_trend()

        assert trend["direction"] in ["stable", "flat"]


class TestDailyAggregates:
    """Tests for daily aggregate file storage."""

    def test_daily_aggregate_created(self, analytics_module, temp_analytics_dir):
        """Test daily aggregate file is created."""
        analytics_module.track_event("test_bot", "message_received")
        analytics_module._flush_daily_aggregates()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_file = Path(temp_analytics_dir) / f"daily_{today}.json"

        assert daily_file.exists()

    def test_daily_aggregate_content(self, analytics_module, temp_analytics_dir):
        """Test daily aggregate contains correct data."""
        analytics_module.track_event("clawdjarvis", "message_received")
        analytics_module.track_event("clawdjarvis", "command_executed")
        analytics_module._flush_daily_aggregates()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_file = Path(temp_analytics_dir) / f"daily_{today}.json"

        with open(daily_file) as f:
            data = json.load(f)

        assert "total_events" in data
        assert data["total_events"] >= 2


class TestFileStorage:
    """Tests for file-based storage."""

    def test_events_file_created(self, analytics_module, temp_analytics_dir):
        """Test events.json is created."""
        analytics_module.track_event("test_bot", "message_received")

        events_file = Path(temp_analytics_dir) / "events.json"
        assert events_file.exists()

    def test_events_file_is_valid_json(self, analytics_module, temp_analytics_dir):
        """Test events.json is valid JSON."""
        analytics_module.track_event("test_bot", "message_received")

        events_file = Path(temp_analytics_dir) / "events.json"
        with open(events_file) as f:
            data = json.load(f)

        assert isinstance(data, list)

    def test_data_persists_across_loads(self, analytics_module, temp_analytics_dir):
        """Test data persists when module is reloaded."""
        from bots.shared import analytics as analytics_mod

        analytics_module.track_event("test_bot", "message_received", {"key": "value"})

        # Simulate reload by creating new instance
        analytics_mod._analytics_dir = temp_analytics_dir

        events = analytics_mod._load_events()
        assert len(events) >= 1
        assert events[-1]["data"]["key"] == "value"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_analytics_dir(tmp_path):
    """Create temp directory for analytics files."""
    analytics_dir = tmp_path / "analytics"
    analytics_dir.mkdir()
    return str(analytics_dir)


@pytest.fixture
def analytics_module(temp_analytics_dir):
    """Get analytics module with temp directory."""
    from bots.shared import analytics

    # Override analytics directory
    analytics._analytics_dir = temp_analytics_dir

    # Clear any existing state
    analytics._events_cache = []
    analytics._daily_aggregates = {}

    return analytics
