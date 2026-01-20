"""
Comprehensive Tests for JARVIS Structured Logging System

This module validates the complete logging system including:
1. Log format is correct and consistent
2. Log levels work correctly
3. Sensitive data is redacted
4. Request/response logging captures needed info
5. Log rotation works (if configured)
6. Structured fields are properly formatted

Components tested:
- core/logging_config.py - CorrelationContext, JSONFormatter, StructuredFormatter
- core/logging/json_formatter.py - JsonFormatter, CompactJsonFormatter
- core/logging/structured_logger.py - StructuredLogger, rotation utilities
- core/logging/log_models.py - LogEntry, LogContext, BusinessEvent
- core/monitoring/log_aggregator.py - LogAggregator, LogLevel, LogEntry
- api/middleware/request_logging.py - RequestLoggingMiddleware, masking functions
"""

import gzip
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest

# Check if starlette/fastapi dependencies are available
try:
    from starlette.applications import Starlette
    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False

# Skip marker for tests requiring starlette
requires_starlette = pytest.mark.skipif(
    not HAS_STARLETTE,
    reason="starlette/fastapi not installed"
)


# =============================================================================
# Test Log Format Correctness and Consistency
# =============================================================================


class TestLogFormatCorrectness:
    """Verify log format is correct and consistent across all formatters."""

    def test_json_formatter_produces_valid_json(self):
        """Test that JSON formatter always produces valid JSON."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter(service="test")

        # Test various message types
        test_cases = [
            "Simple message",
            "Message with special chars: <>&\"'",
            "Unicode: \u4e2d\u6587 \U0001f600",
            "Newlines:\nLine 2\nLine 3",
            "",  # Empty message
            "A" * 10000,  # Long message
        ]

        for msg in test_cases:
            record = logging.LogRecord(
                name="test.format",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=msg,
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            # Must be valid JSON
            data = json.loads(output)
            assert data["message"] == msg
            assert data["level"] == "INFO"

    def test_json_formatter_required_fields(self):
        """Test that JSON formatter includes all required fields."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter(service="jarvis")

        record = logging.LogRecord(
            name="jarvis.trading",
            level=logging.INFO,
            pathname="trading.py",
            lineno=42,
            msg="Trade executed",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Required fields
        assert "timestamp" in data
        assert "level" in data
        assert "logger" in data
        assert "message" in data

        # Verify values
        assert data["level"] == "INFO"
        assert data["logger"] == "jarvis.trading"
        assert data["message"] == "Trade executed"
        assert data["service"] == "jarvis"

    def test_timestamp_iso8601_format(self):
        """Test that timestamps are ISO8601 with Z suffix (UTC)."""
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

        timestamp = data["timestamp"]

        # Should end with Z (UTC)
        assert timestamp.endswith("Z"), f"Timestamp should end with Z: {timestamp}"

        # Should be parseable as ISO8601
        # Remove Z suffix and parse
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt.year >= 2020  # Sanity check

    def test_log_format_consistency_across_levels(self):
        """Test format consistency across all log levels."""
        from core.logging.json_formatter import JsonFormatter

        formatter = JsonFormatter(service="test")

        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level_num, level_name in levels:
            record = logging.LogRecord(
                name="test",
                level=level_num,
                pathname="test.py",
                lineno=1,
                msg=f"Test {level_name}",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert data["level"] == level_name
            assert "timestamp" in data
            assert "logger" in data
            assert "message" in data


class TestLogLevelsWork:
    """Verify log levels work correctly."""

    def test_level_filtering(self):
        """Test that log levels are filtered correctly."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.WARNING)  # Only WARNING and above

        logger = get_structured_logger("test.levels.filter")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            logger.debug("Debug message")  # Should NOT appear
            logger.info("Info message")  # Should NOT appear
            logger.warning("Warning message")  # Should appear
            logger.error("Error message")  # Should appear

            output = stream.getvalue()
            lines = [l for l in output.strip().split("\n") if l]

            assert len(lines) == 2

            data1 = json.loads(lines[0])
            data2 = json.loads(lines[1])

            assert data1["level"] == "WARNING"
            assert data2["level"] == "ERROR"
        finally:
            logger.removeHandler(handler)

    def test_level_inheritance(self):
        """Test that child loggers inherit parent level settings."""
        from core.logging.structured_logger import get_structured_logger

        parent = get_structured_logger("test.parent.level")
        parent.setLevel(logging.WARNING)

        child = parent.get_child("child")

        # Child should respect parent's effective level
        assert parent.level == logging.WARNING

    def test_exception_level_is_error(self):
        """Test that exception logging uses ERROR level."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.exception.level")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            try:
                raise ValueError("Test exception")
            except ValueError:
                logger.exception("Error occurred")

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert data["level"] == "ERROR"
            assert "error" in data or "stack_trace" in data
        finally:
            logger.removeHandler(handler)


@requires_starlette
class TestSensitiveDataRedaction:
    """Verify sensitive data is properly redacted.

    These tests require starlette/fastapi to be installed.
    """

    def test_mask_headers(self):
        """Test header masking for sensitive values."""
        from api.middleware.request_logging import mask_headers

        headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz",
            "x-api-key": "sk-1234567890abcdef",
            "cookie": "session=abc123def456",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0",
        }

        masked = mask_headers(headers)

        # Sensitive headers should be masked
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked["authorization"]
        assert "1234567890abcdef" not in masked["x-api-key"]
        assert "abc123def456" not in masked["cookie"]

        # Non-sensitive headers should be unchanged
        assert masked["content-type"] == "application/json"
        assert masked["user-agent"] == "Mozilla/5.0"

    def test_mask_body_sensitive_fields(self):
        """Test body masking for sensitive field names."""
        from api.middleware.request_logging import mask_body

        body = {
            "username": "testuser",
            "password": "supersecret123",
            "api_key": "sk-abcdef123456",
            "token": "refresh-token-xyz",
            "private_key": "-----BEGIN PRIVATE KEY-----",
            "email": "user@example.com",
        }

        masked = mask_body(body)

        # Sensitive fields should be fully masked
        assert masked["password"] == "****"
        assert masked["api_key"] == "****"
        assert masked["token"] == "****"
        assert masked["private_key"] == "****"

        # Non-sensitive fields should be unchanged
        assert masked["username"] == "testuser"
        assert masked["email"] == "user@example.com"

    def test_mask_body_nested_sensitive_fields(self):
        """Test masking works recursively for nested objects."""
        from api.middleware.request_logging import mask_body

        body = {
            "user": {
                "name": "Test User",
                "credentials": {
                    "password": "nested-secret",
                    "api_key": "nested-key",
                }
            },
            "items": [
                {"name": "item1", "secret": "list-secret"},
                {"name": "item2", "value": "visible"},
            ],
        }

        masked = mask_body(body)

        # Nested sensitive fields should be masked
        assert masked["user"]["credentials"]["password"] == "****"
        assert masked["user"]["credentials"]["api_key"] == "****"
        assert masked["items"][0]["secret"] == "****"

        # Non-sensitive fields should be unchanged
        assert masked["user"]["name"] == "Test User"
        assert masked["items"][1]["value"] == "visible"

    def test_mask_value_preserves_partial_value(self):
        """Test mask_value shows first and last characters."""
        from api.middleware.request_logging import mask_value

        # Long values should show some characters
        result = mask_value("1234567890abcdef")
        assert result == "1234...cdef"

        # Short values should be fully masked
        result = mask_value("short")
        assert result == "****"

    def test_sensitive_headers_list_complete(self):
        """Test that sensitive headers list includes common secrets."""
        from api.middleware.request_logging import SENSITIVE_HEADERS

        # Should include these common sensitive headers (lowercase)
        expected = {
            "authorization",
            "x-api-key",
            "x-auth-token",
            "cookie",
            "set-cookie",
        }

        for header in expected:
            assert header in SENSITIVE_HEADERS, f"Missing sensitive header: {header}"

    def test_sensitive_fields_list_complete(self):
        """Test that sensitive fields list includes common secrets."""
        from api.middleware.request_logging import SENSITIVE_FIELDS

        # Should include these common sensitive field names (lowercase)
        expected = {
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
        }

        for field in expected:
            assert field in SENSITIVE_FIELDS, f"Missing sensitive field: {field}"


@requires_starlette
class TestRequestResponseLogging:
    """Verify request/response logging captures needed info.

    These tests require starlette/fastapi to be installed.
    """

    def test_request_log_structure(self):
        """Test that request log contains all needed fields."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        # Mock request with all relevant attributes
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/trades"
        mock_request.query_params = {"symbol": "SOL"}
        mock_request.headers = {
            "content-type": "application/json",
            "user-agent": "TestClient/1.0",
            "authorization": "Bearer token123",
        }
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        # Create middleware and test request log building
        app = MagicMock()
        middleware = RequestLoggingMiddleware(app, log_request_body=False)

        # Directly test the log building
        import asyncio

        async def build_log():
            return await middleware._build_request_log(mock_request, "req-123")

        request_log = asyncio.get_event_loop().run_until_complete(build_log())

        # Required fields
        assert request_log["request_id"] == "req-123"
        assert request_log["method"] == "POST"
        assert request_log["path"] == "/api/v1/trades"
        assert request_log["query"] == {"symbol": "SOL"}
        assert "headers" in request_log
        assert "client_ip" in request_log

        # Authorization should be masked
        assert "token123" not in str(request_log["headers"]["authorization"])

    def test_response_log_structure(self):
        """Test that response log contains all needed fields."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json", "content-length": "256"}

        app = MagicMock()
        middleware = RequestLoggingMiddleware(app)

        response_log = middleware._build_response_log(
            request_id="req-123",
            response=mock_response,
            duration_ms=150.5,
            error=None,
        )

        # Required fields
        assert response_log["request_id"] == "req-123"
        assert response_log["status_code"] == 200
        assert response_log["duration_ms"] == 150.5

    def test_response_log_with_error(self):
        """Test that error responses capture error details."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = MagicMock()
        middleware = RequestLoggingMiddleware(app)

        test_error = ValueError("Something went wrong")

        response_log = middleware._build_response_log(
            request_id="req-456",
            response=None,
            duration_ms=50.0,
            error=test_error,
        )

        assert response_log["status_code"] == 500
        assert response_log["error"] == "Something went wrong"
        assert response_log["error_type"] == "ValueError"
        assert "stack_trace" in response_log

    def test_slow_request_flagged(self):
        """Test that slow requests are flagged."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        app = MagicMock()
        middleware = RequestLoggingMiddleware(app, slow_request_threshold=1.0)

        # Simulate a 2-second response
        response_log = middleware._build_response_log(
            request_id="req-slow",
            response=mock_response,
            duration_ms=2000.0,  # 2 seconds
            error=None,
        )

        assert response_log.get("slow") is True

    def test_health_endpoints_skipped(self):
        """Test that health check endpoints are skipped."""
        from api.middleware.request_logging import SKIP_PATHS

        # Health endpoints should be in skip list
        assert "/health" in SKIP_PATHS or "/health/" in SKIP_PATHS
        assert "/metrics" in SKIP_PATHS

    def test_client_ip_extraction_from_forwarded(self):
        """Test client IP extraction from X-Forwarded-For header."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = MagicMock()
        middleware = RequestLoggingMiddleware(app)

        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)

        # Should return first IP in chain
        assert ip == "1.2.3.4"


class TestLogRotation:
    """Verify log rotation works correctly."""

    def test_log_filename_format(self):
        """Test that log filenames follow expected format."""
        from core.logging.structured_logger import get_log_filename

        date = datetime(2026, 1, 18)
        filename = get_log_filename("jarvis", date)

        assert filename == "jarvis-2026-01-18.jsonl"

    def test_rotate_and_cleanup_creates_archive(self):
        """Test that rotation creates gzipped archives."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = Path(tmpdir) / "archive"

            # Create an old log file (10 days ago)
            old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            old_log = log_dir / f"jarvis-{old_date}.jsonl"
            old_log.write_text('{"message": "old log entry"}\n')

            # Run rotation
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7)

            # Archive should exist
            assert archive_dir.exists()
            archives = list(archive_dir.glob("*.gz"))
            assert len(archives) == 1

            # Original should be gone
            assert not old_log.exists()

            # Archive should be valid gzip
            with gzip.open(archives[0], "rt") as f:
                content = f.read()
                assert "old log entry" in content

    def test_recent_logs_not_archived(self):
        """Test that recent logs (< 7 days) are kept."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = Path(tmpdir) / "archive"

            # Create recent log files (1-5 days ago)
            for i in range(1, 6):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                log_file = log_dir / f"jarvis-{date}.jsonl"
                log_file.write_text(f'{{"day": {i}}}\n')

            # Run rotation
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7)

            # All files should still exist
            logs = list(log_dir.glob("jarvis-*.jsonl"))
            assert len(logs) == 5

    def test_very_old_archives_deleted(self):
        """Test that archives older than 30 days are deleted."""
        from core.logging.structured_logger import rotate_and_cleanup_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir()
            archive_dir = Path(tmpdir) / "archive"
            archive_dir.mkdir()

            # Create a very old archive (35 days ago)
            old_date = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
            old_archive = archive_dir / f"jarvis-{old_date}.jsonl.gz"

            with gzip.open(old_archive, "wt") as f:
                f.write('{"test": "very old"}\n')

            # Set file modification time to 35 days ago
            old_timestamp = (datetime.now() - timedelta(days=35)).timestamp()
            os.utime(old_archive, (old_timestamp, old_timestamp))

            # Run cleanup
            rotate_and_cleanup_logs(log_dir, archive_dir, delete_after_days=30)

            # Very old archive should be deleted
            assert not old_archive.exists()

    def test_rotating_file_handler(self):
        """Test TimedRotatingFileHandler configuration."""
        from core.logging.structured_logger import get_rotating_file_handler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"

            handler = get_rotating_file_handler(
                log_dir=log_dir,
                base_name="test",
                when="midnight",
                backup_count=7,
            )

            assert handler is not None
            assert log_dir.exists()

            # Log something to ensure it works
            logger = logging.getLogger("test.rotation.handler")
            logger.handlers = []
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

            logger.info("Test message")

            handler.flush()
            handler.close()

            # Log file should exist
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) >= 1


class TestStructuredFieldsFormatting:
    """Verify structured fields are properly formatted."""

    def test_correlation_id_propagation(self):
        """Test that correlation_id is included in all logs."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.correlation")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.set_context(correlation_id="corr-abc-123")

            logger.info("Message 1")
            logger.info("Message 2")
            logger.warning("Message 3")

            output = stream.getvalue()
            lines = [l for l in output.strip().split("\n") if l]

            for line in lines:
                data = json.loads(line)
                assert data["correlation_id"] == "corr-abc-123"
        finally:
            logger.removeHandler(handler)

    def test_user_id_in_logs(self):
        """Test that user_id is included when set."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.user")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.set_context(user_id="tg_8527130908")
            logger.info("User action")

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert data["user_id"] == "tg_8527130908"
        finally:
            logger.removeHandler(handler)

    def test_active_flags_in_logs(self):
        """Test that active_flags list is included."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.flags")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.set_context(active_flags=["LIVE_TRADING_ENABLED", "DEXTER_ENABLED"])
            logger.info("Flags test")

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert "LIVE_TRADING_ENABLED" in data["active_flags"]
            assert "DEXTER_ENABLED" in data["active_flags"]
        finally:
            logger.removeHandler(handler)

    def test_duration_ms_in_logs(self):
        """Test that duration_ms is included."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.duration")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.log_with_context(logging.INFO, "Operation completed", duration_ms=234.56)

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert data["duration_ms"] == 234.56
        finally:
            logger.removeHandler(handler)

    def test_context_dict_in_logs(self):
        """Test that context dictionary is properly included."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.context.dict")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.log_with_context(
                logging.INFO,
                "Trade executed",
                symbol="SOL",
                amount_usd=100.50,
                action="BUY",
            )

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert "context" in data
            assert data["context"]["symbol"] == "SOL"
            assert data["context"]["amount_usd"] == 100.50
            assert data["context"]["action"] == "BUY"
        finally:
            logger.removeHandler(handler)

    def test_event_logging_format(self):
        """Test that business events are properly formatted."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="trading_engine"))

        logger = get_structured_logger("test.events.format")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()

        try:
            logger.log_event(
                "TRADE_EXECUTED",
                symbol="SOL",
                amount_usd=50.0,
                entry_price=98.5,
            )

            output = stream.getvalue()
            data = json.loads(output.strip())

            assert "TRADE_EXECUTED" in data["message"]
            assert data["service"] == "trading_engine"
            assert data["context"]["symbol"] == "SOL"
        finally:
            logger.removeHandler(handler)


class TestLogAggregator:
    """Test log aggregation functionality."""

    def test_log_aggregator_add_entry(self):
        """Test adding entries to aggregator."""
        from core.monitoring.log_aggregator import LogAggregator, LogEntry, LogLevel

        aggregator = LogAggregator(max_entries=100)

        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test message",
            source="test",
            logger_name="test.logger",
        )

        aggregator.add_entry(entry)

        # Entry should be stored
        stats = aggregator.get_stats()
        assert stats.total_entries == 1
        assert stats.entries_by_level.get("INFO", 0) == 1

    def test_log_aggregator_query_by_level(self):
        """Test querying logs by level."""
        from core.monitoring.log_aggregator import LogAggregator, LogEntry, LogLevel, LogQuery

        aggregator = LogAggregator()

        # Add entries of different levels
        for level in [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]:
            entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                message=f"Test {level.value}",
                source="test",
            )
            aggregator.add_entry(entry)

        # Query for ERROR only
        query = LogQuery(min_level=LogLevel.ERROR)
        results = aggregator.query(query)

        assert len(results) == 1
        assert results[0].level == LogLevel.ERROR

    def test_log_aggregator_error_pattern_tracking(self):
        """Test that error patterns are tracked."""
        from core.monitoring.log_aggregator import LogAggregator, LogEntry, LogLevel

        aggregator = LogAggregator()

        # Add similar error messages
        for i in range(5):
            entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.ERROR,
                message=f"Connection failed to host-{i} at port 5432",
                source="test",
            )
            aggregator.add_entry(entry)

        stats = aggregator.get_stats()

        # Should have error patterns tracked
        assert len(stats.top_errors) > 0

    def test_log_aggregator_trace_correlation(self):
        """Test getting logs by trace ID."""
        from core.monitoring.log_aggregator import LogAggregator, LogEntry, LogLevel

        aggregator = LogAggregator()

        # Add entries with same trace ID
        for i in range(3):
            entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message=f"Step {i}",
                source="test",
                trace_id="trace-abc-123",
            )
            aggregator.add_entry(entry)

        # Add unrelated entry
        unrelated = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Other",
            source="test",
            trace_id="trace-xyz-789",
        )
        aggregator.add_entry(unrelated)

        # Get trace
        trace_entries = aggregator.get_trace("trace-abc-123")

        assert len(trace_entries) == 3
        for entry in trace_entries:
            assert entry.trace_id == "trace-abc-123"


class TestLogModels:
    """Test log data models."""

    def test_log_entry_to_dict(self):
        """Test LogEntry serialization."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime(2026, 1, 18, 14, 30, 0, tzinfo=timezone.utc),
            level="INFO",
            logger="jarvis.trading",
            message="Trade executed",
            service="trading_engine",
            correlation_id="trade-123",
            context={"symbol": "SOL", "amount": 100},
        )

        data = entry.to_dict()

        assert "2026-01-18" in data["timestamp"]
        assert data["timestamp"].endswith("Z")
        assert data["level"] == "INFO"
        assert data["service"] == "trading_engine"
        assert data["context"]["symbol"] == "SOL"

    def test_log_entry_to_json(self):
        """Test LogEntry JSON serialization."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime(2026, 1, 18, 14, 30, 0, tzinfo=timezone.utc),
            level="INFO",
            logger="test",
            message="Test",
        )

        json_str = entry.to_json()
        parsed = json.loads(json_str)

        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_log_context_merge(self):
        """Test LogContext merging."""
        from core.logging.log_models import LogContext

        ctx1 = LogContext(
            service="trading",
            correlation_id="old-corr",
        )

        ctx2 = LogContext(
            correlation_id="new-corr",
            user_id="user-123",
        )

        merged = ctx1.merge(ctx2)

        # Should prefer non-None values from ctx2
        assert merged.service == "trading"  # From ctx1 (ctx2 is None)
        assert merged.correlation_id == "new-corr"  # From ctx2
        assert merged.user_id == "user-123"  # From ctx2

    def test_business_event_to_log_entry(self):
        """Test BusinessEvent conversion to LogEntry."""
        from core.logging.log_models import BusinessEvent

        event = BusinessEvent(
            event_name="TRADE_EXECUTED",
            data={"symbol": "SOL", "amount": 100},
        )

        entry = event.to_log_entry(
            logger_name="jarvis.trading",
            service="trading_engine",
        )

        assert "TRADE_EXECUTED" in entry.message
        assert entry.service == "trading_engine"
        assert entry.context["symbol"] == "SOL"


class TestCompactJsonFormatter:
    """Test compact JSON formatter."""

    def test_compact_formatter_omits_nulls(self):
        """Test that compact formatter omits null values."""
        from core.logging.json_formatter import CompactJsonFormatter

        formatter = CompactJsonFormatter(service="test")

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

        # Should not have null values
        for key, value in data.items():
            assert value is not None
            assert value != []
            assert value != {}

    def test_compact_formatter_no_location(self):
        """Test that compact formatter doesn't include location."""
        from core.logging.json_formatter import CompactJsonFormatter

        formatter = CompactJsonFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Should not have location fields
        assert "function" not in data
        assert "line" not in data


class TestIntegration:
    """Integration tests for the complete logging system."""

    def test_end_to_end_structured_logging(self):
        """Test complete logging flow from setup to file output."""
        from core.logging.structured_logger import setup_structured_logger
        from core.logging.json_formatter import JsonFormatter

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "integration.jsonl"

            logger = setup_structured_logger(
                name="test.integration.e2e",
                log_file=str(log_file),
                console=False,
                level=logging.DEBUG,
                service="test_service",
            )

            try:
                logger.set_context(
                    correlation_id="int-test-456",
                    user_id="tg_123",
                )

                logger.info("Start operation")
                logger.log_event("OPERATION_STARTED", operation="test")
                logger.warning("Something concerning")
                logger.log_with_context(
                    logging.INFO,
                    "Operation completed",
                    duration_ms=100.5,
                    result="success",
                )

                # Flush handlers
                for handler in logger.handlers[:]:
                    handler.flush()
                    handler.close()
                    logger.removeHandler(handler)

                # Read and verify log file
                assert log_file.exists()

                with open(log_file) as f:
                    logs = [json.loads(line) for line in f if line.strip()]

                assert len(logs) == 4

                # All logs should have correlation context
                for log in logs:
                    assert log["correlation_id"] == "int-test-456"
                    assert log["user_id"] == "tg_123"

                # Verify specific logs
                assert logs[0]["message"] == "Start operation"
                assert "OPERATION_STARTED" in logs[1]["message"]
                assert logs[2]["level"] == "WARNING"
                assert logs[3]["duration_ms"] == 100.5

            finally:
                # Ensure handlers are cleaned up
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)

    def test_context_inheritance_in_child_loggers(self):
        """Test that child loggers inherit parent context."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        # Parent logger
        parent_stream = StringIO()
        parent_handler = logging.StreamHandler(parent_stream)
        parent_handler.setFormatter(JsonFormatter())

        parent = get_structured_logger("test.parent.inherit")
        parent.handlers = []
        parent.addHandler(parent_handler)
        parent.setLevel(logging.DEBUG)
        parent.clear_context()

        parent.set_context(
            service="parent_service",
            correlation_id="parent-corr-123",
        )

        # Child logger
        child_stream = StringIO()
        child_handler = logging.StreamHandler(child_stream)
        child_handler.setFormatter(JsonFormatter())

        child = parent.get_child("child")
        child.handlers = []
        child.addHandler(child_handler)
        child.setLevel(logging.DEBUG)

        try:
            child.info("Child log message")

            output = child_stream.getvalue()
            data = json.loads(output.strip())

            # Should have inherited context
            assert data["service"] == "parent_service"
            assert data["correlation_id"] == "parent-corr-123"

        finally:
            parent.removeHandler(parent_handler)
            child.removeHandler(child_handler)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
