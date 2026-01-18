"""
Tests for JSON log formatter.
"""

import pytest
import logging
import json
from datetime import datetime, timezone
from io import StringIO


class TestJsonFormatter:
    """Tests for the JSON formatter."""

    def test_formatter_basic_output(self):
        """Test basic JSON output format."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        logger = logging.getLogger("test.formatter.basic")
        logger.setLevel(logging.INFO)

        # Create a handler with string buffer
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        try:
            logger.info("Test message")
            output = stream.getvalue()

            # Parse the JSON output
            data = json.loads(output.strip())
            assert data["level"] == "INFO"
            assert data["message"] == "Test message"
            assert "timestamp" in data
        finally:
            logger.removeHandler(handler)

    def test_formatter_timestamp_format(self):
        """Test that timestamps are ISO8601 with Z suffix."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Should end with Z (UTC)
        assert data["timestamp"].endswith("Z")
        # Should be valid ISO8601
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_formatter_includes_logger_name(self):
        """Test that logger name is included."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="jarvis.trading.engine",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data["logger"] == "jarvis.trading.engine"

    def test_formatter_includes_location(self):
        """Test that file location info is included."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter(include_location=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/module.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"

        output = formatter.format(record)
        data = json.loads(output)

        assert "location" in data or ("function" in data and "line" in data)

    def test_formatter_exception_handling(self):
        """Test that exceptions are captured properly."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        # Should have error info
        assert "error" in data or "stack_trace" in data or "exception" in data

    def test_formatter_with_extra_fields(self):
        """Test that extra fields are included."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Trade executed",
            args=(),
            exc_info=None,
        )
        record.context = {"symbol": "SOL", "amount": 100}

        output = formatter.format(record)
        data = json.loads(output)

        # Context should be included
        assert "context" in data or "symbol" in data

    def test_formatter_handles_unicode(self):
        """Test that unicode is handled properly."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User message: \u4e2d\u6587\u6d4b\u8bd5 \U0001f600",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert "\u4e2d\u6587" in data["message"]

    def test_formatter_handles_non_serializable(self):
        """Test that non-serializable objects are handled."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"date": datetime.now(), "bytes": b"data"}

        # Should not raise an exception
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"

    def test_formatter_all_log_levels(self):
        """Test all log levels are formatted correctly."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level, level_name in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg=f"{level_name} message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            data = json.loads(output)
            assert data["level"] == level_name

    def test_formatter_with_service_context(self):
        """Test formatter with service context."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter(
            service="trading_engine",
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data.get("service") == "trading_engine"

    def test_formatter_with_correlation_id(self):
        """Test formatter captures correlation IDs."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "trade-abc123-def456"

        output = formatter.format(record)
        data = json.loads(output)
        assert data.get("correlation_id") == "trade-abc123-def456"

    def test_formatter_with_active_flags(self):
        """Test formatter includes active feature flags."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.active_flags = ["LIVE_TRADING_ENABLED", "DEXTER_ENABLED"]

        output = formatter.format(record)
        data = json.loads(output)
        assert "active_flags" in data
        assert "LIVE_TRADING_ENABLED" in data["active_flags"]

    def test_formatter_with_duration(self):
        """Test formatter includes duration tracking."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Operation completed",
            args=(),
            exc_info=None,
        )
        record.duration_ms = 234.56

        output = formatter.format(record)
        data = json.loads(output)
        assert data.get("duration_ms") == 234.56
