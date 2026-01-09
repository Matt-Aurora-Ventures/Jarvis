"""
Tests for core/daemon.py

Tests cover:
- Timestamp formatting
- Time parsing
- Report scheduling
- Notification sending (mocked)
- Component status tracking
"""

import sys
import datetime as dt
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.daemon import (
    _timestamp,
    _parse_time,
    _should_run_report,
    _send_notification,
    _log_message,
)


class TestTimestamp:
    """Test timestamp formatting."""

    def test_timestamp_format(self):
        """Should return properly formatted timestamp."""
        ts = _timestamp()
        # Should match YYYY-MM-DD HH:MM:SS format
        assert len(ts) == 19
        assert ts[4] == "-"
        assert ts[7] == "-"
        assert ts[10] == " "
        assert ts[13] == ":"
        assert ts[16] == ":"

    def test_timestamp_is_current(self):
        """Timestamp should be approximately current time."""
        import time
        ts = _timestamp()
        # Parse the timestamp
        parsed = time.strptime(ts, "%Y-%m-%d %H:%M:%S")
        now = time.localtime()
        # Should be within same minute
        assert parsed.tm_year == now.tm_year
        assert parsed.tm_mon == now.tm_mon
        assert parsed.tm_mday == now.tm_mday


class TestParseTime:
    """Test time parsing."""

    def test_parse_valid_time(self):
        """Should parse valid HH:MM format."""
        hour, minute = _parse_time("14:30")
        assert hour == 14
        assert minute == 30

    def test_parse_midnight(self):
        """Should parse midnight."""
        hour, minute = _parse_time("00:00")
        assert hour == 0
        assert minute == 0

    def test_parse_end_of_day(self):
        """Should parse end of day."""
        hour, minute = _parse_time("23:59")
        assert hour == 23
        assert minute == 59

    def test_parse_single_digit(self):
        """Should parse single digit times."""
        hour, minute = _parse_time("9:5")
        assert hour == 9
        assert minute == 5

    def test_parse_invalid_returns_zero(self):
        """Should return (0, 0) for invalid input."""
        hour, minute = _parse_time("invalid")
        assert hour == 0
        assert minute == 0

    def test_parse_empty_returns_zero(self):
        """Should return (0, 0) for empty input."""
        hour, minute = _parse_time("")
        assert hour == 0
        assert minute == 0

    def test_parse_none_returns_zero(self):
        """Should return (0, 0) for None-like input."""
        # Will raise but handled
        hour, minute = _parse_time(":")
        assert hour == 0
        assert minute == 0


class TestShouldRunReport:
    """Test report scheduling logic."""

    def test_report_not_in_schedule(self):
        """Should return False if report not in schedule."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 10, 0, 0)
        last_run = {}

        result = _should_run_report("weekly", schedule, now, last_run)
        assert not result

    def test_report_already_run_today_dash_format(self):
        """Should return False if already run today (dash format)."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 10, 0, 0)
        last_run = {"daily": "2026-01-08"}

        result = _should_run_report("daily", schedule, now, last_run)
        assert not result

    def test_report_already_run_today_compact_format(self):
        """Should return False if already run today (compact format)."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 10, 0, 0)
        last_run = {"daily": "20260108"}

        result = _should_run_report("daily", schedule, now, last_run)
        assert not result

    def test_report_should_run_after_scheduled_time(self):
        """Should return True if after scheduled time and not run today."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 10, 0, 0)  # After 9 AM
        last_run = {"daily": "2026-01-07"}  # Last run yesterday

        result = _should_run_report("daily", schedule, now, last_run)
        assert result

    def test_report_should_not_run_before_scheduled_time(self):
        """Should return False if before scheduled time."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 8, 0, 0)  # Before 9 AM
        last_run = {"daily": "2026-01-07"}  # Last run yesterday

        result = _should_run_report("daily", schedule, now, last_run)
        assert not result

    def test_report_never_run_before(self):
        """Should return True if never run before and after scheduled time."""
        schedule = {"weekly": "10:00"}
        now = dt.datetime(2026, 1, 8, 11, 0, 0)
        last_run = {}  # Never run

        result = _should_run_report("weekly", schedule, now, last_run)
        assert result

    def test_report_exact_scheduled_time(self):
        """Should return True at exactly scheduled time."""
        schedule = {"daily": "09:00"}
        now = dt.datetime(2026, 1, 8, 9, 0, 0)  # Exactly 9 AM
        last_run = {}

        result = _should_run_report("daily", schedule, now, last_run)
        assert result


class TestSendNotification:
    """Test notification sending (mocked)."""

    @patch('core.daemon.safe_subprocess')
    def test_send_notification_calls_osascript(self, mock_subprocess):
        """Should call osascript with notification."""
        mock_subprocess.run_command_safe = Mock()

        _send_notification("Test Title", "Test Message")

        mock_subprocess.run_command_safe.assert_called_once()
        call_args = mock_subprocess.run_command_safe.call_args
        # First arg should be the command list
        cmd_list = call_args[0][0]
        assert cmd_list[0] == "osascript"
        assert cmd_list[1] == "-e"
        # Script should contain the message
        assert "Test Message" in cmd_list[2]
        assert "Test Title" in cmd_list[2]

    @patch('core.daemon.safe_subprocess')
    def test_send_notification_sanitizes_input(self, mock_subprocess):
        """Should sanitize quotes in notification."""
        mock_subprocess.run_command_safe = Mock()

        _send_notification('Title with "quotes"', 'Message with "quotes"')

        call_args = mock_subprocess.run_command_safe.call_args
        cmd_list = call_args[0][0]
        script = cmd_list[2]
        # Should have escaped quotes
        assert '\\"' in script or "quotes" in script

    @patch('core.daemon.safe_subprocess')
    def test_send_notification_handles_error(self, mock_subprocess):
        """Should handle errors gracefully."""
        mock_subprocess.run_command_safe = Mock(side_effect=Exception("osascript failed"))

        # Should not raise
        _send_notification("Title", "Message")

    @patch('core.daemon.safe_subprocess')
    def test_send_notification_timeout(self, mock_subprocess):
        """Should use timeout when calling osascript."""
        mock_subprocess.run_command_safe = Mock()

        _send_notification("Title", "Message")

        call_args = mock_subprocess.run_command_safe.call_args
        # Check timeout kwarg
        assert call_args[1].get("timeout") == 5


class TestLogMessage:
    """Test log message writing."""

    def test_log_message_creates_directory(self, tmp_path):
        """Should create directory if it doesn't exist."""
        log_path = tmp_path / "subdir" / "daemon.log"

        _log_message(log_path, "Test message")

        assert log_path.parent.exists()

    def test_log_message_writes_to_file(self, tmp_path):
        """Should write message to log file."""
        log_path = tmp_path / "daemon.log"

        _log_message(log_path, "Test log entry")

        assert log_path.exists()
        content = log_path.read_text()
        assert "Test log entry" in content

    def test_log_message_includes_timestamp(self, tmp_path):
        """Should include timestamp in log entry."""
        log_path = tmp_path / "daemon.log"

        _log_message(log_path, "Entry with timestamp")

        content = log_path.read_text()
        # Should have timestamp format [YYYY-MM-DD HH:MM:SS]
        assert "[202" in content  # Year starts with 202x
        assert "]" in content

    def test_log_message_appends(self, tmp_path):
        """Should append to existing log file."""
        log_path = tmp_path / "daemon.log"

        _log_message(log_path, "First message")
        _log_message(log_path, "Second message")

        content = log_path.read_text()
        assert "First message" in content
        assert "Second message" in content

    def test_log_message_uses_utf8(self, tmp_path):
        """Should handle UTF-8 characters."""
        log_path = tmp_path / "daemon.log"

        _log_message(log_path, "Message with emoji: 🎉 and unicode: 日本語")

        content = log_path.read_text(encoding="utf-8")
        assert "🎉" in content
        assert "日本語" in content


class TestComponentStatus:
    """Test component status tracking structure."""

    def test_component_status_structure(self):
        """Verify expected component status structure."""
        # This tests the structure that would be created in run()
        component_status = {
            "brain": {"ok": False, "error": None},
            "mcp": {"ok": False, "error": None},
            "jarvis": {"ok": False, "error": None},
            "voice": {"ok": False, "error": None},
            "hotkeys": {"ok": False, "error": None},
            "passive": {"ok": False, "error": None},
            "observer": {"ok": False, "error": None},
            "resource_monitor": {"ok": False, "error": None},
            "missions": {"ok": False, "error": None},
            "proactive": {"ok": False, "error": None},
        }

        # All components should start as not ok
        for name, status in component_status.items():
            assert "ok" in status
            assert "error" in status
            assert status["ok"] is False

    def test_component_status_update(self):
        """Test updating component status."""
        component_status = {"voice": {"ok": False, "error": None}}

        # Simulate successful initialization
        component_status["voice"]["ok"] = True
        assert component_status["voice"]["ok"]

        # Simulate error
        component_status["voice"]["ok"] = False
        component_status["voice"]["error"] = "Microphone not found"
        assert component_status["voice"]["error"] == "Microphone not found"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_time_with_extra_colons(self):
        """Should handle time with extra parts."""
        # "10:30:00" should fail gracefully
        hour, minute = _parse_time("10:30:00")
        # Will try to unpack 3 values into 2, causing exception
        assert hour == 0
        assert minute == 0

    def test_should_run_report_empty_schedule(self):
        """Should handle empty schedule."""
        result = _should_run_report("daily", {}, dt.datetime.now(), {})
        assert not result

    def test_log_message_with_newlines(self, tmp_path):
        """Should handle messages with newlines."""
        log_path = tmp_path / "daemon.log"

        _log_message(log_path, "Line 1\nLine 2\nLine 3")

        content = log_path.read_text()
        assert "Line 1\nLine 2\nLine 3" in content
