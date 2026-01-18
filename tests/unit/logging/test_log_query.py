"""
Tests for log query CLI tool.
"""

import pytest
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import StringIO
import sys


@pytest.fixture
def sample_logs():
    """Create sample log files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()

        # Create sample log entries
        entries = [
            {
                "timestamp": "2026-01-18T10:00:00.000000Z",
                "level": "INFO",
                "logger": "jarvis.trading",
                "message": "Trade executed",
                "service": "trading_engine",
                "correlation_id": "trade-abc123",
                "user_id": "tg_8527130908",
                "context": {"symbol": "SOL", "action": "BUY", "amount_usd": 100.50},
                "active_flags": ["LIVE_TRADING_ENABLED"],
            },
            {
                "timestamp": "2026-01-18T10:05:00.000000Z",
                "level": "ERROR",
                "logger": "jarvis.trading",
                "message": "Trade failed",
                "service": "trading_engine",
                "correlation_id": "trade-def456",
                "user_id": "tg_8527130908",
                "error": "ConnectionTimeout",
                "context": {"symbol": "ETH"},
            },
            {
                "timestamp": "2026-01-18T10:10:00.000000Z",
                "level": "INFO",
                "logger": "jarvis.telegram",
                "message": "User command",
                "service": "telegram_bot",
                "user_id": "tg_12345",
                "active_flags": ["DEXTER_ENABLED"],
            },
            {
                "timestamp": "2026-01-18T09:00:00.000000Z",
                "level": "WARNING",
                "logger": "jarvis.supervisor",
                "message": "Component restarting",
                "service": "supervisor",
            },
        ]

        log_file = log_dir / "jarvis-2026-01-18.jsonl"
        with open(log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        yield log_dir


class TestLogQueryByLevel:
    """Tests for querying logs by level."""

    def test_query_errors(self, sample_logs):
        """Test querying only ERROR level logs."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, level="ERROR")

        assert len(results) == 1
        assert results[0]["level"] == "ERROR"
        assert "Trade failed" in results[0]["message"]

    def test_query_warnings(self, sample_logs):
        """Test querying WARNING level logs."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, level="WARNING")

        assert len(results) == 1
        assert results[0]["level"] == "WARNING"

    def test_query_info(self, sample_logs):
        """Test querying INFO level logs."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, level="INFO")

        assert len(results) == 2
        for r in results:
            assert r["level"] == "INFO"


class TestLogQueryByService:
    """Tests for querying logs by service."""

    def test_query_by_service(self, sample_logs):
        """Test querying logs by service name."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, service="trading_engine")

        assert len(results) == 2
        for r in results:
            assert r["service"] == "trading_engine"

    def test_query_by_service_no_match(self, sample_logs):
        """Test querying service with no matches."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, service="nonexistent_service")

        assert len(results) == 0


class TestLogQueryByCorrelationId:
    """Tests for querying logs by correlation ID."""

    def test_query_by_correlation_id(self, sample_logs):
        """Test querying logs by correlation ID."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, correlation_id="trade-abc123")

        assert len(results) == 1
        assert results[0]["correlation_id"] == "trade-abc123"

    def test_query_by_partial_correlation_id(self, sample_logs):
        """Test querying logs by partial correlation ID."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, correlation_id="trade-")

        # Should match both trade entries
        assert len(results) >= 2


class TestLogQueryByUser:
    """Tests for querying logs by user ID."""

    def test_query_by_user_id(self, sample_logs):
        """Test querying logs by user ID."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, user_id="tg_8527130908")

        assert len(results) == 2
        for r in results:
            assert r["user_id"] == "tg_8527130908"

    def test_query_by_user_id_numeric(self, sample_logs):
        """Test querying by numeric user ID (without prefix)."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, user_id="8527130908")

        # Should still match
        assert len(results) >= 1


class TestLogQueryByFlag:
    """Tests for querying logs by active flag."""

    def test_query_by_flag(self, sample_logs):
        """Test querying logs by active flag."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, flag="LIVE_TRADING_ENABLED")

        assert len(results) == 1
        assert "LIVE_TRADING_ENABLED" in results[0].get("active_flags", [])

    def test_query_by_dexter_flag(self, sample_logs):
        """Test querying logs by DEXTER_ENABLED flag."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, flag="DEXTER_ENABLED")

        assert len(results) == 1


class TestLogQueryByTime:
    """Tests for querying logs by time range."""

    def test_query_since(self, sample_logs):
        """Test querying logs since a time."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, since="2026-01-18T10:00:00Z")

        assert len(results) >= 3  # All logs at or after 10:00

    def test_query_since_relative(self, sample_logs):
        """Test querying logs with relative time (1 hour ago)."""
        from scripts.log_query import query_logs, parse_relative_time

        # This is a bit tricky since sample logs have fixed dates
        # Let's just test the parse_relative_time function
        result = parse_relative_time("1 hour ago")
        assert result is not None

    def test_query_until(self, sample_logs):
        """Test querying logs until a time."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, until="2026-01-18T10:00:00Z")

        # Should include the 09:00 warning
        assert len(results) >= 1


class TestLogQueryByContext:
    """Tests for querying logs by context fields."""

    def test_query_by_symbol(self, sample_logs):
        """Test querying logs by symbol in context."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, context_key="symbol", context_value="SOL")

        assert len(results) == 1
        assert results[0]["context"]["symbol"] == "SOL"


class TestLogQueryCombined:
    """Tests for combined query filters."""

    def test_combined_level_and_service(self, sample_logs):
        """Test querying with level AND service."""
        from scripts.log_query import query_logs

        results = query_logs(sample_logs, level="INFO", service="trading_engine")

        assert len(results) == 1
        assert results[0]["level"] == "INFO"
        assert results[0]["service"] == "trading_engine"

    def test_combined_user_and_time(self, sample_logs):
        """Test querying with user AND time filters."""
        from scripts.log_query import query_logs

        results = query_logs(
            sample_logs, user_id="tg_8527130908", since="2026-01-18T10:00:00Z"
        )

        assert len(results) == 2


class TestLogQueryOutput:
    """Tests for query output formatting."""

    def test_output_json(self, sample_logs):
        """Test JSON output format."""
        from scripts.log_query import query_logs, format_output

        results = query_logs(sample_logs, level="ERROR")
        output = format_output(results, format="json")

        # Should be valid JSON array
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_output_text(self, sample_logs):
        """Test text/human-readable output format."""
        from scripts.log_query import query_logs, format_output

        results = query_logs(sample_logs, level="ERROR")
        output = format_output(results, format="text")

        assert "ERROR" in output
        assert "Trade failed" in output

    def test_output_count(self, sample_logs):
        """Test count-only output."""
        from scripts.log_query import query_logs, format_output

        results = query_logs(sample_logs, level="INFO")
        output = format_output(results, format="count")

        assert "2" in output


class TestLogQueryCLI:
    """Tests for CLI interface."""

    def test_cli_help(self):
        """Test CLI shows help."""
        from scripts.log_query import create_parser

        parser = create_parser()
        assert parser is not None

    def test_cli_parse_args(self):
        """Test CLI argument parsing."""
        from scripts.log_query import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["--level", "ERROR", "--service", "trading", "--since", "1 hour ago"]
        )

        assert args.level == "ERROR"
        assert args.service == "trading"
        assert args.since == "1 hour ago"


class TestRelativeTimeParsing:
    """Tests for relative time parsing."""

    def test_parse_hours_ago(self):
        """Test parsing 'X hours ago'."""
        from scripts.log_query import parse_relative_time

        result = parse_relative_time("2 hours ago")
        expected = datetime.now(timezone.utc) - timedelta(hours=2)

        # Allow 1 minute tolerance
        assert abs((result - expected).total_seconds()) < 60

    def test_parse_minutes_ago(self):
        """Test parsing 'X minutes ago'."""
        from scripts.log_query import parse_relative_time

        result = parse_relative_time("30 minutes ago")
        expected = datetime.now(timezone.utc) - timedelta(minutes=30)

        assert abs((result - expected).total_seconds()) < 60

    def test_parse_days_ago(self):
        """Test parsing 'X days ago'."""
        from scripts.log_query import parse_relative_time

        result = parse_relative_time("1 day ago")
        expected = datetime.now(timezone.utc) - timedelta(days=1)

        assert abs((result - expected).total_seconds()) < 60

    def test_parse_absolute_datetime(self):
        """Test parsing absolute datetime."""
        from scripts.log_query import parse_relative_time

        result = parse_relative_time("2026-01-18T10:00:00Z")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 18
