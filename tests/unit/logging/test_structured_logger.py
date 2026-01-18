"""
Tests for StructuredLogger class.
"""

import pytest
import logging
import json
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch, MagicMock
import tempfile
import os


class TestStructuredLogger:
    """Tests for the StructuredLogger class."""

    def test_logger_creation(self):
        """Test creating a structured logger."""
        from core.logging.structured_logger import StructuredLogger

        logger = StructuredLogger("jarvis.test")
        assert logger.name == "jarvis.test"

    def test_set_context(self):
        """Test setting context values."""
        from core.logging.structured_logger import StructuredLogger

        logger = StructuredLogger("jarvis.test")
        logger.set_context("service", "trading_engine")
        logger.set_context("user_id", "tg_123")

        assert logger.context.get("service") == "trading_engine"
        assert logger.context.get("user_id") == "tg_123"

    def test_set_multiple_context(self):
        """Test setting multiple context values at once."""
        from core.logging.structured_logger import StructuredLogger

        logger = StructuredLogger("jarvis.test")
        logger.set_context(
            service="trading_engine",
            user_id="tg_123",
            correlation_id="trade-abc",
        )

        assert logger.context.get("service") == "trading_engine"
        assert logger.context.get("correlation_id") == "trade-abc"

    def test_clear_context(self):
        """Test clearing context."""
        from core.logging.structured_logger import StructuredLogger

        logger = StructuredLogger("jarvis.test")
        logger.set_context("service", "test")
        logger.clear_context()

        assert logger.context.get("service") is None

    def test_log_with_context(self):
        """Test logging with context."""
        from core.logging.structured_logger import StructuredLogger, get_structured_logger

        # Create logger with JSON formatter
        logger = get_structured_logger("jarvis.test.context")
        logger.setLevel(logging.DEBUG)  # Ensure logger level allows messages
        logger.set_context("service", "trading_engine")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            logger.log_with_context(logging.INFO, "Test message", symbol="SOL")
            output = stream.getvalue()

            data = json.loads(output.strip())
            assert data["message"] == "Test message"
            assert data.get("service") == "trading_engine"
            assert data.get("context", {}).get("symbol") == "SOL" or data.get("symbol") == "SOL"
        finally:
            logger.removeHandler(handler)

    def test_log_event(self):
        """Test logging a business event."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.event")
        logger.setLevel(logging.DEBUG)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            logger.log_event(
                "TRADE_EXECUTED",
                symbol="SOL",
                action="BUY",
                amount_usd=100.50,
            )
            output = stream.getvalue()

            data = json.loads(output.strip())
            assert "TRADE_EXECUTED" in data.get("message", "") or data.get("event_name") == "TRADE_EXECUTED"
        finally:
            logger.removeHandler(handler)

    def test_log_with_correlation_id(self):
        """Test logging with correlation ID."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.corr")
        logger.setLevel(logging.DEBUG)
        logger.set_context("correlation_id", "trade-abc123-def456")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            logger.info("Test with correlation")
            output = stream.getvalue()

            data = json.loads(output.strip())
            assert data.get("correlation_id") == "trade-abc123-def456"
        finally:
            logger.removeHandler(handler)

    def test_log_with_active_flags(self):
        """Test logging with active feature flags."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.flags")
        logger.setLevel(logging.DEBUG)
        logger.set_context("active_flags", ["LIVE_TRADING_ENABLED", "DEXTER_ENABLED"])

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            logger.info("Test with flags")
            output = stream.getvalue()

            data = json.loads(output.strip())
            flags = data.get("active_flags", [])
            assert "LIVE_TRADING_ENABLED" in flags
        finally:
            logger.removeHandler(handler)

    def test_log_exception(self):
        """Test logging exceptions."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.exc")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            try:
                raise ValueError("Test error")
            except ValueError:
                logger.exception("An error occurred")

            output = stream.getvalue()
            data = json.loads(output.strip())

            # Should contain exception info
            assert data["level"] == "ERROR"
            has_error_info = (
                "error" in data or
                "stack_trace" in data or
                "exception" in data
            )
            assert has_error_info
        finally:
            logger.removeHandler(handler)

    def test_log_with_duration(self):
        """Test logging with duration tracking."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.duration")
        logger.setLevel(logging.DEBUG)

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        from core.logging.json_formatter import JsonFormatter

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        try:
            logger.log_with_context(logging.INFO, "Slow operation", duration_ms=234.56)
            output = stream.getvalue()

            data = json.loads(output.strip())
            assert data.get("duration_ms") == 234.56
        finally:
            logger.removeHandler(handler)

    def test_context_isolation(self):
        """Test that context is isolated between loggers."""
        from core.logging.structured_logger import get_structured_logger

        logger1 = get_structured_logger("jarvis.test.iso1")
        logger2 = get_structured_logger("jarvis.test.iso2")

        logger1.set_context("service", "service1")
        logger2.set_context("service", "service2")

        assert logger1.context.get("service") == "service1"
        assert logger2.context.get("service") == "service2"

    def test_child_logger_inherits_context(self):
        """Test that child loggers inherit parent context."""
        from core.logging.structured_logger import get_structured_logger

        parent = get_structured_logger("jarvis.trading")
        parent.set_context("service", "trading_engine")

        child = parent.get_child("executor")
        assert child.context.get("service") == "trading_engine"


class TestStructuredLoggerSetup:
    """Tests for structured logger setup and configuration."""

    def test_setup_with_file_handler(self):
        """Test setting up logger with file handler."""
        from core.logging.structured_logger import setup_structured_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "logs", "test.jsonl")

            logger = setup_structured_logger(
                name="jarvis.test.file.setup2",  # Use unique name to avoid cache
                log_file=log_file,
                level=logging.INFO,
                console=False,  # Only file handler for this test
            )

            logger.info("Test message to file")

            # Flush and close handlers to ensure content is written and file released
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)

            # Verify file was created and has content
            assert os.path.exists(log_file)
            with open(log_file) as f:
                content = f.read().strip()
                data = json.loads(content)
                assert data["message"] == "Test message to file"

    def test_setup_with_console_and_file(self):
        """Test setting up logger with both console and file handlers."""
        from core.logging.structured_logger import setup_structured_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.jsonl")

            logger = setup_structured_logger(
                name="jarvis.test.both.setup2",  # Use unique name to avoid cache
                log_file=log_file,
                console=True,
                level=logging.INFO,
            )

            # Should have 2 handlers (file + console)
            assert len(logger.handlers) >= 2

            # Close handlers to release file (Windows compatibility)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


class TestLoggerFactory:
    """Tests for logger factory functions."""

    def test_get_structured_logger(self):
        """Test getting a structured logger."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger("jarvis.test.factory")
        assert logger is not None
        assert hasattr(logger, "set_context")
        assert hasattr(logger, "log_with_context")

    def test_get_structured_logger_same_instance(self):
        """Test that same name returns same logger instance."""
        from core.logging.structured_logger import get_structured_logger

        logger1 = get_structured_logger("jarvis.test.same")
        logger2 = get_structured_logger("jarvis.test.same")

        assert logger1 is logger2

    def test_get_structured_logger_with_initial_context(self):
        """Test getting logger with initial context."""
        from core.logging.structured_logger import get_structured_logger

        logger = get_structured_logger(
            "jarvis.test.initial",
            service="trading_engine",
            user_id="tg_123",
        )

        assert logger.context.get("service") == "trading_engine"
        assert logger.context.get("user_id") == "tg_123"
