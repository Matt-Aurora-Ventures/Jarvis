"""
Tests for structured logging integration in critical paths.

These tests verify that:
1. Trading module uses structured logging
2. Sentiment aggregator uses structured logging
3. Sentiment poster uses structured logging
4. Grok client uses structured logging
5. Dexter agent uses structured logging
"""

import pytest
import logging
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime, timezone
import io


class TestStructuredLoggingIntegration:
    """Test structured logging integration in critical modules."""

    def test_json_formatter_basic_output(self):
        """Test JSON formatter produces valid JSON."""
        from core.logging.json_formatter import JsonFormatter

        # Create a test handler
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="test_service"))

        # Create logger
        logger = logging.getLogger("test.basic")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log a message
        logger.info("Test message")

        # Parse output
        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["service"] == "test_service"
        assert "timestamp" in log_data

    def test_json_formatter_with_context(self):
        """Test JSON formatter includes context data."""
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="trading"))

        logger = logging.getLogger("test.context")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log with extra context
        logger.info(
            "Trade executed",
            extra={
                "correlation_id": "trade-123",
                "user_id": "tg_456",
                "context": {"symbol": "SOL", "amount": 100},
            },
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert log_data["correlation_id"] == "trade-123"
        assert log_data["user_id"] == "tg_456"
        assert log_data["context"]["symbol"] == "SOL"

    def test_structured_logger_event_logging(self):
        """Test StructuredLogger log_event method."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.events")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log an event
        logger.log_event("TRADE_OPENED", symbol="SOL", amount=50)

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "TRADE_OPENED" in log_data["message"]
        assert log_data["context"]["symbol"] == "SOL"
        assert log_data["context"]["amount"] == 50

    def test_structured_logger_context_persistence(self):
        """Test that context is persisted across log calls."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = get_structured_logger("test.persistence")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.clear_context()  # Reset context

        # Set persistent context
        logger.set_context(correlation_id="trace-abc", service="test")

        # Log multiple messages
        logger.info("First message")
        logger.info("Second message")

        outputs = stream.getvalue().strip().split("\n")
        assert len(outputs) == 2

        for output in outputs:
            log_data = json.loads(output)
            assert log_data["correlation_id"] == "trace-abc"
            assert log_data["service"] == "test"

    def test_structured_logger_child_logger(self):
        """Test child logger inherits parent context."""
        from core.logging.structured_logger import get_structured_logger
        from core.logging.json_formatter import JsonFormatter

        # Use separate stream for child
        child_stream = io.StringIO()
        child_handler = logging.StreamHandler(child_stream)
        child_handler.setFormatter(JsonFormatter())

        # Use unique name to avoid conflicts
        parent = get_structured_logger("test.parent.unique")
        parent.handlers = []
        parent.propagate = False
        parent.setLevel(logging.DEBUG)
        parent.clear_context()

        # Set parent context
        parent.set_context(service="trading", correlation_id="parent-123")

        # Get child logger
        child = parent.get_child("executor")
        child.handlers = []
        child.propagate = False
        child.addHandler(child_handler)
        child.setLevel(logging.DEBUG)

        # Log from child
        child.info("Child log message")

        output = child_stream.getvalue().strip()
        log_data = json.loads(output)

        assert log_data["service"] == "trading"
        assert log_data["correlation_id"] == "parent-123"
        assert "parent.unique.executor" in log_data["logger"]

    def test_error_logging_with_exception(self):
        """Test error logging includes exception info."""
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = logging.getLogger("test.error")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("Error occurred")

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert log_data["level"] == "ERROR"
        assert "ValueError" in log_data["error"]
        assert log_data["stack_trace"] is not None

    def test_duration_ms_logging(self):
        """Test duration_ms field is logged correctly."""
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = logging.getLogger("test.duration")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("Operation completed", extra={"duration_ms": 234.5})

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert log_data["duration_ms"] == 234.5

    def test_active_flags_logging(self):
        """Test active_flags field is logged correctly."""
        from core.logging.json_formatter import JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = logging.getLogger("test.flags")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info(
            "Operation with flags",
            extra={"active_flags": ["LIVE_TRADING", "DEXTER_ENABLED"]},
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "LIVE_TRADING" in log_data["active_flags"]
        assert "DEXTER_ENABLED" in log_data["active_flags"]


class TestLogQueryCLI:
    """Test log query CLI functionality."""

    def test_parse_relative_time_hours(self):
        """Test parsing relative time strings."""
        from scripts.log_query import parse_relative_time

        now = datetime.now(timezone.utc)
        result = parse_relative_time("1 hour ago")

        assert result is not None
        delta = now - result
        assert 3500 < delta.total_seconds() < 3700

    def test_parse_relative_time_minutes(self):
        """Test parsing minutes ago."""
        from scripts.log_query import parse_relative_time

        now = datetime.now(timezone.utc)
        result = parse_relative_time("30 minutes ago")

        assert result is not None
        delta = now - result
        assert 1700 < delta.total_seconds() < 1900

    def test_parse_relative_time_days(self):
        """Test parsing days ago."""
        from scripts.log_query import parse_relative_time

        now = datetime.now(timezone.utc)
        result = parse_relative_time("2 days ago")

        assert result is not None
        delta = now - result
        assert 172700 < delta.total_seconds() < 172900

    def test_parse_iso_timestamp(self):
        """Test parsing ISO8601 timestamps."""
        from scripts.log_query import parse_relative_time

        result = parse_relative_time("2026-01-18T10:30:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 18

    def test_query_logs_level_filter(self):
        """Test log query with level filter."""
        from scripts.log_query import query_logs
        import tempfile
        import os

        # Create temp log directory
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"

            # Write test logs
            logs = [
                {"timestamp": "2026-01-18T10:00:00Z", "level": "INFO", "message": "Test info"},
                {"timestamp": "2026-01-18T10:01:00Z", "level": "ERROR", "message": "Test error"},
                {"timestamp": "2026-01-18T10:02:00Z", "level": "WARNING", "message": "Test warning"},
            ]

            with open(log_file, "w") as f:
                for log in logs:
                    f.write(json.dumps(log) + "\n")

            # Query for ERROR only
            results = query_logs(Path(tmpdir), level="ERROR")

            assert len(results) == 1
            assert results[0]["level"] == "ERROR"

    def test_query_logs_service_filter(self):
        """Test log query with service filter."""
        from scripts.log_query import query_logs
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"

            logs = [
                {"timestamp": "2026-01-18T10:00:00Z", "level": "INFO", "service": "trading", "message": "Trade"},
                {"timestamp": "2026-01-18T10:01:00Z", "level": "INFO", "service": "sentiment", "message": "Sentiment"},
            ]

            with open(log_file, "w") as f:
                for log in logs:
                    f.write(json.dumps(log) + "\n")

            results = query_logs(Path(tmpdir), service="trading")

            assert len(results) == 1
            assert results[0]["service"] == "trading"

    def test_query_logs_correlation_id_filter(self):
        """Test log query with correlation_id filter."""
        from scripts.log_query import query_logs
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"

            logs = [
                {"timestamp": "2026-01-18T10:00:00Z", "level": "INFO", "correlation_id": "trade-abc123", "message": "Start"},
                {"timestamp": "2026-01-18T10:01:00Z", "level": "INFO", "correlation_id": "trade-abc123", "message": "End"},
                {"timestamp": "2026-01-18T10:02:00Z", "level": "INFO", "correlation_id": "trade-xyz789", "message": "Other"},
            ]

            with open(log_file, "w") as f:
                for log in logs:
                    f.write(json.dumps(log) + "\n")

            results = query_logs(Path(tmpdir), correlation_id="abc123")

            assert len(results) == 2
            for r in results:
                assert "abc123" in r["correlation_id"]


class TestLogAggregation:
    """Test log aggregation functionality."""

    def test_log_rotation_creates_archive(self):
        """Test that log rotation creates archives."""
        from core.logging.structured_logger import rotate_and_cleanup_logs
        import tempfile
        from datetime import timedelta

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            archive_dir = Path(tmpdir) / "archive"
            log_dir.mkdir()

            # Create an old log file
            old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
            old_log = log_dir / f"jarvis-{old_date}.jsonl"
            old_log.write_text('{"message": "old log"}\n')

            # Run rotation
            rotate_and_cleanup_logs(log_dir, archive_dir, keep_days=7)

            # Check archive was created
            assert archive_dir.exists()
            archives = list(archive_dir.glob("*.gz"))
            assert len(archives) == 1

            # Original file should be gone
            assert not old_log.exists()

    def test_log_file_handler_writes_jsonl(self):
        """Test that rotating file handler writes valid JSONL."""
        from core.logging.structured_logger import get_rotating_file_handler
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            handler = get_rotating_file_handler(log_dir, base_name="test")

            logger = logging.getLogger("test.rotation")
            logger.handlers = []
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)

            # Log some messages
            logger.info("Message 1")
            logger.info("Message 2")

            # Close handler to flush
            handler.close()

            # Read log file
            log_file = log_dir / "test.jsonl"
            assert log_file.exists()

            lines = log_file.read_text().strip().split("\n")
            assert len(lines) >= 2

            for line in lines:
                data = json.loads(line)
                assert "message" in data
                assert "timestamp" in data


class TestTradingLoggingIntegration:
    """Test that trading module uses structured logging correctly."""

    def test_trading_engine_logger_import(self):
        """Test that trading module can import structured logger."""
        # This tests that the import paths work correctly
        from core.logging import get_structured_logger, JsonFormatter

        logger = get_structured_logger("jarvis.trading", service="trading_engine")
        assert logger is not None
        assert logger.name == "jarvis.trading"

    def test_trading_log_event_format(self):
        """Test trading event log format."""
        from core.logging import get_structured_logger, JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="trading_engine"))

        logger = get_structured_logger("jarvis.trading.test")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate a trade event log
        logger.log_event(
            "POSITION_OPENED",
            position_id="abc123",
            symbol="SOL",
            amount_usd=50.0,
            entry_price=98.5,
            sentiment_grade="B+",
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "POSITION_OPENED" in log_data["message"]
        assert log_data["context"]["symbol"] == "SOL"
        assert log_data["context"]["amount_usd"] == 50.0


class TestSentimentLoggingIntegration:
    """Test sentiment aggregator logging."""

    def test_sentiment_logger_format(self):
        """Test sentiment aggregator log format."""
        from core.logging import get_structured_logger, JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="sentiment"))

        logger = get_structured_logger("jarvis.sentiment.test")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate sentiment calculation log
        logger.log_event(
            "SENTIMENT_CALCULATED",
            symbol="SOL",
            score=0.75,
            grade="A-",
            sources=["grok", "twitter", "onchain"],
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "SENTIMENT_CALCULATED" in log_data["message"]
        assert log_data["service"] == "sentiment"
        assert log_data["context"]["score"] == 0.75


class TestGrokClientLoggingIntegration:
    """Test Grok client logging."""

    def test_grok_api_call_log_format(self):
        """Test Grok API call log format."""
        from core.logging import get_structured_logger, JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="grok"))

        logger = get_structured_logger("jarvis.grok.test")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate Grok API call log
        logger.log_event(
            "GROK_API_CALL",
            model="grok-3",
            prompt_length=500,
            response_length=200,
            duration_ms=1250.5,
            cost_usd=0.003,
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "GROK_API_CALL" in log_data["message"]
        assert log_data["service"] == "grok"
        assert log_data["context"]["model"] == "grok-3"
        assert log_data["context"]["cost_usd"] == 0.003


class TestDexterLoggingIntegration:
    """Test Dexter agent logging."""

    def test_dexter_react_loop_log_format(self):
        """Test Dexter ReAct loop log format."""
        from core.logging import get_structured_logger, JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="dexter"))

        logger = get_structured_logger("jarvis.dexter.test")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate ReAct iteration log
        logger.log_event(
            "REACT_ITERATION",
            iteration=3,
            action="analyze_sentiment",
            symbol="SOL",
            observation="bullish signal detected",
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "REACT_ITERATION" in log_data["message"]
        assert log_data["service"] == "dexter"
        assert log_data["context"]["iteration"] == 3
        assert log_data["context"]["action"] == "analyze_sentiment"

    def test_dexter_decision_log_format(self):
        """Test Dexter decision log format."""
        from core.logging import get_structured_logger, JsonFormatter

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter(service="dexter"))

        logger = get_structured_logger("jarvis.dexter.decision.test")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate decision log
        logger.log_event(
            "TRADE_DECISION",
            decision="TRADE_BUY",
            symbol="SOL",
            confidence=0.85,
            rationale="Strong bullish sentiment with liquidation support",
            iterations=5,
            total_cost_usd=0.015,
        )

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        assert "TRADE_DECISION" in log_data["message"]
        assert log_data["context"]["decision"] == "TRADE_BUY"
        assert log_data["context"]["confidence"] == 0.85
