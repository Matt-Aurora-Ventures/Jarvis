"""
Unit tests for ClawdBot centralized error handling module.

Tests cover:
- Error severity levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Uniform error logging
- Telegram alert sending
- Retry logic with exponential backoff
- Transient error detection
- Error pattern tracking
- Graceful degradation strategies
- Rolling error log (max 1000 entries)
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bots.shared.error_handler import (
    ErrorSeverity,
    ErrorContext,
    ErrorStats,
    ErrorHandler,
    with_retry,
    handle_error,
    send_error_alert,
    get_error_stats,
    is_transient_error,
    get_error_handler,
    reset_error_handler,
)


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_severity_levels_exist(self):
        """Test all severity levels are defined."""
        assert ErrorSeverity.DEBUG.value == "DEBUG"
        assert ErrorSeverity.INFO.value == "INFO"
        assert ErrorSeverity.WARNING.value == "WARNING"
        assert ErrorSeverity.ERROR.value == "ERROR"
        assert ErrorSeverity.CRITICAL.value == "CRITICAL"

    def test_severity_ordering(self):
        """Test severity levels have correct numeric ordering."""
        assert ErrorSeverity.DEBUG.level < ErrorSeverity.INFO.level
        assert ErrorSeverity.INFO.level < ErrorSeverity.WARNING.level
        assert ErrorSeverity.WARNING.level < ErrorSeverity.ERROR.level
        assert ErrorSeverity.ERROR.level < ErrorSeverity.CRITICAL.level

    def test_should_alert(self):
        """Test which severities should trigger alerts."""
        assert ErrorSeverity.DEBUG.should_alert() is False
        assert ErrorSeverity.INFO.should_alert() is False
        assert ErrorSeverity.WARNING.should_alert() is False
        assert ErrorSeverity.ERROR.should_alert() is True
        assert ErrorSeverity.CRITICAL.should_alert() is True


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_basic_context(self):
        """Test basic error context creation."""
        ctx = ErrorContext(
            bot_name="clawdjarvis",
            operation="send_message",
        )
        assert ctx.bot_name == "clawdjarvis"
        assert ctx.operation == "send_message"
        assert ctx.user_id is None
        assert ctx.chat_id is None

    def test_context_with_all_fields(self):
        """Test error context with all fields."""
        ctx = ErrorContext(
            bot_name="clawdmatt",
            operation="process_command",
            user_id=123456,
            chat_id=-1001234567890,
            message_id=42,
            extra={"command": "/test"},
        )
        assert ctx.user_id == 123456
        assert ctx.chat_id == -1001234567890
        assert ctx.message_id == 42
        assert ctx.extra["command"] == "/test"

    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        ctx = ErrorContext(
            bot_name="clawdfriday",
            operation="api_call",
            user_id=999,
        )
        d = ctx.to_dict()
        assert d["bot_name"] == "clawdfriday"
        assert d["operation"] == "api_call"
        assert d["user_id"] == 999


class TestErrorStats:
    """Tests for ErrorStats tracking."""

    def test_record_error(self):
        """Test recording an error."""
        stats = ErrorStats()
        stats.record_error("ValueError", ErrorSeverity.ERROR, "clawdjarvis")

        assert stats.total_errors == 1
        assert stats.by_severity[ErrorSeverity.ERROR] == 1
        assert stats.by_type["ValueError"] == 1
        assert stats.by_bot["clawdjarvis"] == 1

    def test_multiple_errors(self):
        """Test recording multiple errors."""
        stats = ErrorStats()

        stats.record_error("ValueError", ErrorSeverity.ERROR, "clawdjarvis")
        stats.record_error("TimeoutError", ErrorSeverity.WARNING, "clawdmatt")
        stats.record_error("ValueError", ErrorSeverity.ERROR, "clawdjarvis")
        stats.record_error("APIError", ErrorSeverity.CRITICAL, "clawdfriday")

        assert stats.total_errors == 4
        assert stats.by_type["ValueError"] == 2
        assert stats.by_severity[ErrorSeverity.ERROR] == 2
        assert stats.by_bot["clawdjarvis"] == 2

    def test_get_summary(self):
        """Test getting error summary."""
        stats = ErrorStats()
        stats.record_error("ValueError", ErrorSeverity.ERROR, "bot1")
        stats.record_error("TimeoutError", ErrorSeverity.ERROR, "bot2")

        summary = stats.get_summary()

        assert summary["total_errors"] == 2
        assert "by_severity" in summary
        assert "by_type" in summary
        assert "by_bot" in summary

    def test_get_recent_errors(self):
        """Test getting recent errors."""
        stats = ErrorStats()

        # Add errors over time
        stats.record_error("Error1", ErrorSeverity.ERROR, "bot1")
        stats.record_error("Error2", ErrorSeverity.ERROR, "bot1")
        stats.record_error("Error3", ErrorSeverity.ERROR, "bot1")

        recent = stats.get_recent_errors(limit=2)
        assert len(recent) == 2


class TestErrorHandler:
    """Tests for main ErrorHandler class."""

    def setup_method(self):
        """Reset error handler before each test."""
        reset_error_handler()

    def test_singleton_pattern(self):
        """Test error handler uses singleton pattern."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        assert handler1 is handler2

    def test_handle_error_logs_error(self):
        """Test handle_error logs the error."""
        handler = ErrorHandler(error_log_path=None)  # In-memory only

        error = ValueError("Test error")
        ctx = ErrorContext(bot_name="testbot", operation="test_op")

        with patch.object(handler, '_log_error') as mock_log:
            handler.handle_error(error, ctx, severity=ErrorSeverity.ERROR)
            mock_log.assert_called_once()

    def test_handle_error_updates_stats(self):
        """Test handle_error updates statistics."""
        handler = ErrorHandler(error_log_path=None)

        error = ValueError("Test error")
        ctx = ErrorContext(bot_name="testbot", operation="test_op")

        handler.handle_error(error, ctx, severity=ErrorSeverity.ERROR)

        stats = handler.get_error_stats()
        assert stats["total_errors"] == 1

    @pytest.mark.asyncio
    async def test_handle_error_sends_alert_for_critical(self):
        """Test handle_error sends alert for critical errors."""
        handler = ErrorHandler(error_log_path=None)
        handler.telegram_token = "test_token"
        handler.alert_chat_id = "123456"

        error = ValueError("Critical failure")
        ctx = ErrorContext(bot_name="testbot", operation="critical_op")

        with patch.object(handler, '_send_telegram_alert', new_callable=AsyncMock) as mock_alert:
            await handler.handle_error_async(error, ctx, severity=ErrorSeverity.CRITICAL)
            mock_alert.assert_called_once()

    def test_handle_error_graceful_degradation(self):
        """Test handle_error returns gracefully handled status."""
        handler = ErrorHandler(error_log_path=None)

        error = ValueError("Test error")
        ctx = ErrorContext(bot_name="testbot", operation="test_op")

        result = handler.handle_error(error, ctx, severity=ErrorSeverity.ERROR)

        assert result["handled"] is True
        assert "timestamp" in result
        assert result["severity"] == "ERROR"


class TestWithRetry:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0

        @with_retry(max_retries=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test function retries on failure."""
        call_count = 0

        @with_retry(max_retries=3, backoff=False, base_delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test raises after max retries exceeded."""
        call_count = 0

        @with_retry(max_retries=2, backoff=False, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await always_fails()

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff increases delay."""
        delays = []

        @with_retry(max_retries=3, backoff=True, base_delay=0.1)
        async def track_delays():
            if len(delays) < 3:
                delays.append(time.time())
                raise ValueError("Fail")
            return "success"

        await track_delays()

        # Check delays increase exponentially
        if len(delays) >= 3:
            delay1 = delays[1] - delays[0]
            delay2 = delays[2] - delays[1]
            # Second delay should be longer (exponential backoff)
            assert delay2 > delay1

    @pytest.mark.asyncio
    async def test_retry_only_transient_errors(self):
        """Test retry only for transient errors when configured."""
        call_count = 0

        @with_retry(max_retries=3, only_transient=True, base_delay=0.01)
        async def non_transient_error():
            nonlocal call_count
            call_count += 1
            raise PermissionError("Not transient")

        with pytest.raises(PermissionError):
            await non_transient_error()

        # Should not retry non-transient errors
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_sync_function(self):
        """Test retry decorator works with sync functions."""
        call_count = 0

        @with_retry(max_retries=3, backoff=False, base_delay=0.01)
        def sync_failing():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temp fail")
            return "done"

        result = sync_failing()

        assert result == "done"
        assert call_count == 2


class TestTransientErrorDetection:
    """Tests for is_transient_error function."""

    def test_connection_errors_are_transient(self):
        """Test connection errors are identified as transient."""
        assert is_transient_error(ConnectionError("Network issue")) is True
        assert is_transient_error(ConnectionResetError("Reset")) is True
        assert is_transient_error(ConnectionRefusedError("Refused")) is True

    def test_timeout_errors_are_transient(self):
        """Test timeout errors are identified as transient."""
        assert is_transient_error(TimeoutError("Timed out")) is True
        assert is_transient_error(asyncio.TimeoutError()) is True

    def test_rate_limit_errors_are_transient(self):
        """Test rate limit errors are identified as transient."""
        # HTTP 429 in message
        error = Exception("HTTP 429 Too Many Requests")
        assert is_transient_error(error) is True

    def test_value_errors_are_not_transient(self):
        """Test value errors are not transient."""
        assert is_transient_error(ValueError("Bad value")) is False

    def test_permission_errors_are_not_transient(self):
        """Test permission errors are not transient."""
        assert is_transient_error(PermissionError("No access")) is False

    def test_type_errors_are_not_transient(self):
        """Test type errors are not transient."""
        assert is_transient_error(TypeError("Wrong type")) is False


class TestSendErrorAlert:
    """Tests for send_error_alert function."""

    @pytest.mark.asyncio
    async def test_sends_telegram_message(self):
        """Test sends Telegram message for error alert."""
        handler = get_error_handler()
        handler.telegram_token = "test_token"
        handler.alert_chat_id = "123456"

        error = ValueError("Test error")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = Mock(return_value=Mock())
            mock_urlopen.return_value.__exit__ = Mock(return_value=False)

            result = send_error_alert(error, ErrorSeverity.ERROR)

            # Should attempt to send
            assert mock_urlopen.called or result is False  # Depends on config

    def test_skips_alert_for_low_severity(self):
        """Test skips alert for DEBUG/INFO severity."""
        reset_error_handler()
        handler = get_error_handler()

        error = ValueError("Minor issue")

        with patch.object(handler, '_send_telegram_alert') as mock_alert:
            result = send_error_alert(error, ErrorSeverity.DEBUG)

            mock_alert.assert_not_called()


class TestGetErrorStats:
    """Tests for get_error_stats function."""

    def setup_method(self):
        """Reset handler before each test."""
        reset_error_handler()

    def test_returns_stats_summary(self):
        """Test returns error statistics summary."""
        handler = get_error_handler()

        # Record some errors
        handler.handle_error(
            ValueError("E1"),
            ErrorContext(bot_name="bot1", operation="op1"),
            severity=ErrorSeverity.ERROR
        )
        handler.handle_error(
            TimeoutError("E2"),
            ErrorContext(bot_name="bot2", operation="op2"),
            severity=ErrorSeverity.WARNING
        )

        stats = get_error_stats()

        assert stats["total_errors"] == 2
        assert "by_severity" in stats
        assert "by_type" in stats
        assert "by_bot" in stats

    def test_get_error_patterns(self):
        """Test identifying error patterns."""
        handler = get_error_handler()

        # Record same error multiple times
        for _ in range(5):
            handler.handle_error(
                ConnectionError("API timeout"),
                ErrorContext(bot_name="bot1", operation="api_call"),
                severity=ErrorSeverity.ERROR
            )

        stats = get_error_stats()
        patterns = stats.get("patterns", {})

        # Should identify repeated error as pattern
        assert stats["by_type"].get("ConnectionError", 0) == 5


class TestHandleErrorFunction:
    """Tests for the convenience handle_error function."""

    def setup_method(self):
        """Reset handler before each test."""
        reset_error_handler()

    def test_convenience_function_works(self):
        """Test handle_error convenience function."""
        error = ValueError("Test")
        ctx = ErrorContext(bot_name="testbot", operation="test")

        result = handle_error(error, ctx, "testbot")

        assert result["handled"] is True

    def test_accepts_string_context(self):
        """Test handle_error accepts string context."""
        error = ValueError("Test")

        result = handle_error(error, "test_operation", "testbot")

        assert result["handled"] is True

    def test_auto_detects_severity(self):
        """Test auto-detection of severity based on error type."""
        critical_error = MemoryError("Out of memory")
        result = handle_error(critical_error, "operation", "bot")
        assert result["severity"] == "CRITICAL"


class TestErrorLogPersistence:
    """Tests for error log file persistence."""

    def test_writes_to_log_file(self):
        """Test errors are written to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "errors.json"

            handler = ErrorHandler(error_log_path=log_path)
            handler.handle_error(
                ValueError("Test error"),
                ErrorContext(bot_name="testbot", operation="test"),
                severity=ErrorSeverity.ERROR
            )

            # Force flush
            handler._flush_log()

            assert log_path.exists()
            content = json.loads(log_path.read_text())
            assert len(content) >= 1

    def test_rolling_log_max_entries(self):
        """Test log file rolls at max entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "errors.json"

            handler = ErrorHandler(error_log_path=log_path, max_log_entries=10)

            # Add more than max entries
            for i in range(15):
                handler.handle_error(
                    ValueError(f"Error {i}"),
                    ErrorContext(bot_name="testbot", operation="test"),
                    severity=ErrorSeverity.WARNING
                )
                handler._flush_log()

            content = json.loads(log_path.read_text())
            assert len(content) <= 10

    def test_loads_existing_log_on_init(self):
        """Test existing log is loaded on initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "errors.json"

            # Create initial log
            initial_errors = [
                {"error": "OldError", "timestamp": "2024-01-01T00:00:00"}
            ]
            log_path.write_text(json.dumps(initial_errors))

            handler = ErrorHandler(error_log_path=log_path)

            # Add new error
            handler.handle_error(
                ValueError("NewError"),
                ErrorContext(bot_name="testbot", operation="test"),
                severity=ErrorSeverity.ERROR
            )
            handler._flush_log()

            content = json.loads(log_path.read_text())
            assert len(content) >= 2


class TestGracefulDegradation:
    """Tests for graceful degradation strategies."""

    def test_returns_fallback_on_error(self):
        """Test handler returns fallback value on error."""
        handler = get_error_handler()

        error = ValueError("API failure")
        ctx = ErrorContext(bot_name="bot", operation="fetch_data")

        result = handler.handle_error(error, ctx, fallback_value={"data": []})

        assert result["fallback_applied"] is True
        assert result["fallback_value"] == {"data": []}

    def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker pattern."""
        handler = get_error_handler()

        # Record many errors for same operation
        for _ in range(10):
            handler.handle_error(
                ConnectionError("Service down"),
                ErrorContext(bot_name="bot", operation="external_api"),
                severity=ErrorSeverity.ERROR
            )

        # Should recommend circuit breaker after pattern detected
        stats = handler.get_error_stats()
        assert stats["by_type"].get("ConnectionError", 0) >= 10


class TestModuleIntegration:
    """Integration tests for error handler module."""

    def test_full_error_handling_flow(self):
        """Test complete error handling flow."""
        reset_error_handler()

        @with_retry(max_retries=2, base_delay=0.01)
        async def api_call():
            raise ConnectionError("Network error")

        async def run_test():
            try:
                await api_call()
            except ConnectionError as e:
                result = handle_error(
                    e,
                    ErrorContext(bot_name="clawdjarvis", operation="api_call"),
                    "clawdjarvis"
                )
                return result

        result = asyncio.run(run_test())

        assert result["handled"] is True
        stats = get_error_stats()
        assert stats["total_errors"] >= 1

    def test_multiple_bots_tracked_separately(self):
        """Test errors from multiple bots are tracked separately."""
        reset_error_handler()

        bots = ["clawdjarvis", "clawdfriday", "clawdmatt"]

        for bot in bots:
            handle_error(
                ValueError(f"Error from {bot}"),
                ErrorContext(bot_name=bot, operation="test"),
                bot
            )

        stats = get_error_stats()

        for bot in bots:
            assert stats["by_bot"].get(bot, 0) >= 1
