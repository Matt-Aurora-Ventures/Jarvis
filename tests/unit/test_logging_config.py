"""
Tests for Structured Logging Configuration

Validates:
- JSON formatting output
- Correlation ID tracking
- Context propagation
- Log rotation
- Structured data inclusion
"""

import json
import logging
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from core.logging_config import (
    CorrelationContext,
    JSONFormatter,
    StructuredFormatter,
    StructuredLogger,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    set_user_context,
    setup_logging,
    correlation_id_var,
    user_id_var,
    trade_id_var,
)


class TestCorrelationContext:
    """Test correlation context management."""

    def test_auto_generate_correlation_id(self):
        """Test that correlation ID is auto-generated if not provided."""
        with CorrelationContext() as ctx:
            assert ctx.correlation_id is not None
            assert isinstance(ctx.correlation_id, str)
            assert len(ctx.correlation_id) == 36  # UUID format

    def test_explicit_correlation_id(self):
        """Test setting explicit correlation ID."""
        test_id = "test-correlation-123"
        with CorrelationContext(correlation_id=test_id) as ctx:
            assert ctx.correlation_id == test_id
            assert correlation_id_var.get() == test_id

    def test_context_cleanup(self):
        """Test that context is cleaned up after exit."""
        with CorrelationContext(correlation_id="temp-id"):
            assert correlation_id_var.get() == "temp-id"

        assert correlation_id_var.get() is None

    def test_user_context(self):
        """Test user context propagation."""
        with CorrelationContext(user_id="user_123", trade_id="trade_456"):
            assert user_id_var.get() == "user_123"
            assert trade_id_var.get() == "trade_456"

        assert user_id_var.get() is None
        assert trade_id_var.get() is None

    def test_nested_contexts(self):
        """Test nested correlation contexts."""
        with CorrelationContext(correlation_id="outer"):
            assert correlation_id_var.get() == "outer"

            with CorrelationContext(correlation_id="inner"):
                assert correlation_id_var.get() == "inner"

            assert correlation_id_var.get() == "outer"


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_basic_json_format(self):
        """Test basic JSON log formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        log_data = json.loads(output)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["line"] == 42
        assert "timestamp" in log_data
        assert log_data["timestamp"].endswith("Z")  # UTC format

    def test_correlation_id_in_json(self):
        """Test correlation ID appears in JSON output."""
        formatter = JSONFormatter(include_context=True)

        with CorrelationContext(correlation_id="test-corr-123"):
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
            log_data = json.loads(output)

            assert log_data["correlation_id"] == "test-corr-123"

    def test_exception_in_json(self):
        """Test exception formatting in JSON."""
        formatter = JSONFormatter(include_traceback=True)

        try:
            raise ValueError("Test error")
        except Exception:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            output = formatter.format(record)
            log_data = json.loads(output)

            assert "exception" in log_data
            assert log_data["exception"]["type"] == "ValueError"
            assert log_data["exception"]["message"] == "Test error"
            assert isinstance(log_data["exception"]["traceback"], list)

    def test_extra_fields(self):
        """Test extra fields in JSON output."""
        formatter = JSONFormatter(extra_fields={"service": "jarvis", "env": "test"})

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
        log_data = json.loads(output)

        assert log_data["service"] == "jarvis"
        assert log_data["env"] == "test"

    def test_custom_extra_data(self):
        """Test custom extra data in logs."""
        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Trade executed",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"amount": 100.5, "symbol": "SOL"}

        output = formatter.format(record)
        log_data = json.loads(output)

        assert "extra" in log_data
        assert log_data["extra"]["amount"] == 100.5
        assert log_data["extra"]["symbol"] == "SOL"


class TestStructuredFormatter:
    """Test structured console formatting."""

    def test_basic_format(self):
        """Test basic structured format."""
        formatter = StructuredFormatter(use_color=False)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "INFO" in output
        assert "test.logger" in output
        assert "Test message" in output

    def test_correlation_context_in_format(self):
        """Test correlation context appears in formatted output."""
        formatter = StructuredFormatter(use_color=False)

        with CorrelationContext(correlation_id="test-123", user_id="user_456"):
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

            assert "correlation_id=test-123" in output
            assert "user_id=user_456" in output


class TestStructuredLogger:
    """Test StructuredLogger wrapper."""

    def test_log_with_extra_data(self):
        """Test logging with structured extra data."""
        logger = logging.getLogger("test.structured")
        logger.setLevel(logging.DEBUG)

        # Capture log output
        handler = logging.handlers.MemoryHandler(capacity=10)
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        structured_logger = StructuredLogger(logger)
        structured_logger.info("Test message", user_id="123", trade_amount=50.5)

        handler.flush()
        handler.close()

        # Verify extra data was attached
        assert handler.buffer  # Should have captured logs

    def test_exception_logging(self):
        """Test exception logging with traceback."""
        logger = logging.getLogger("test.exception")
        logger.setLevel(logging.ERROR)

        handler = logging.handlers.MemoryHandler(capacity=10)
        logger.addHandler(handler)

        structured_logger = StructuredLogger(logger)

        try:
            raise RuntimeError("Test exception")
        except Exception:
            structured_logger.exception("Failed to process", operation="test")

        handler.flush()
        handler.close()

        assert len(handler.buffer) == 1
        assert handler.buffer[0].exc_info is not None


class TestLogSetup:
    """Test logging setup and configuration."""

    def test_setup_logging_creates_directory(self):
        """Test that log directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"

            logger = setup_logging(
                log_dir=log_dir,
                log_file="test.log",
                level="INFO",
                json_format=True,
                console_output=False,
            )

            assert log_dir.exists()
            assert (log_dir / "test.log").exists()

            # Clean up handlers
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

    def test_setup_logging_levels(self):
        """Test different logging levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                root_logger = setup_logging(
                    log_dir=tmpdir,
                    log_file=f"{level.lower()}.log",
                    level=level,
                    console_output=False,
                )

                assert root_logger.level == getattr(logging, level)

                # Clean up handlers
                for handler in root_logger.handlers[:]:
                    handler.close()
                    root_logger.removeHandler(handler)

    def test_log_rotation_config(self):
        """Test log rotation configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            max_bytes = 1024  # 1KB for testing
            backup_count = 3

            root_logger = setup_logging(
                log_dir=tmpdir,
                log_file="rotate.log",
                level="DEBUG",
                max_bytes=max_bytes,
                backup_count=backup_count,
                console_output=False,
            )

            logger = logging.getLogger()

            # Write enough logs to trigger rotation
            for i in range(100):
                logger.info(f"Log message {i} " + "x" * 100)

            log_files = list(Path(tmpdir).glob("rotate.log*"))
            # Should have main log + backups
            assert len(log_files) > 1

            # Clean up handlers
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)


class TestHelperFunctions:
    """Test helper functions."""

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        cid = set_correlation_id("test-id-123")
        assert cid == "test-id-123"
        assert get_correlation_id() == "test-id-123"

    def test_auto_generate_correlation_id(self):
        """Test auto-generation of correlation ID."""
        cid = set_correlation_id()
        assert cid is not None
        assert get_correlation_id() == cid

    def test_set_user_context(self):
        """Test setting user context."""
        set_user_context(
            user_id="user_789",
            trade_id="trade_101",
            session_id="session_202",
        )

        assert user_id_var.get() == "user_789"
        assert trade_id_var.get() == "trade_101"


class TestIntegration:
    """Integration tests for structured logging."""

    def test_end_to_end_logging(self):
        """Test complete logging flow with correlation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_logger = setup_logging(
                log_dir=tmpdir,
                log_file="integration.log",
                level="DEBUG",
                json_format=True,
                console_output=False,
                extra_fields={"service": "jarvis"},
            )

            logger = get_logger("integration.test")

            with CorrelationContext(
                correlation_id="int-test-123",
                user_id="user_999",
                trade_id="trade_888",
            ):
                logger.info("Trade started", symbol="SOL", amount=100)
                logger.warning("Low balance", balance=50)
                logger.error("Trade failed", reason="insufficient_funds")

            # Clean up handlers before reading
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)

            # Read and verify log file
            log_file = Path(tmpdir) / "integration.log"
            assert log_file.exists()

            with open(log_file) as f:
                logs = [json.loads(line) for line in f]

            assert len(logs) == 3

            # Verify all logs have correlation context
            for log_entry in logs:
                assert log_entry["correlation_id"] == "int-test-123"
                assert log_entry["user_id"] == "user_999"
                assert log_entry["trade_id"] == "trade_888"
                assert log_entry["service"] == "jarvis"

            # Verify specific log content
            assert logs[0]["message"] == "Trade started"
            assert logs[0]["level"] == "INFO"
            assert logs[1]["level"] == "WARNING"
            assert logs[2]["level"] == "ERROR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
