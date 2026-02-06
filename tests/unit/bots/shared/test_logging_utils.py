"""
Tests for ClawdBot logging utilities.

TDD Phase 1: Define expected behavior via tests.
"""

import pytest
import json
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_returns_logger(self):
        """setup_logger should return a configured logger instance."""
        from bots.shared.logging_utils import setup_logger

        logger = setup_logger("test_bot")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_bot"

    def test_setup_logger_default_level_info(self):
        """Default log level should be INFO."""
        from bots.shared.logging_utils import setup_logger

        logger = setup_logger("test_bot")
        assert logger.level == logging.INFO

    def test_setup_logger_custom_level(self):
        """setup_logger should accept custom log levels."""
        from bots.shared.logging_utils import setup_logger

        logger = setup_logger("test_bot", log_level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_setup_logger_has_console_handler(self):
        """Logger should have a console (stream) handler."""
        from bots.shared.logging_utils import setup_logger

        logger = setup_logger("test_bot")

        has_stream_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in logger.handlers
        )
        assert has_stream_handler, "Logger should have a StreamHandler for console output"

    def test_setup_logger_has_file_handler_with_rotation(self):
        """Logger should have a rotating file handler."""
        from bots.shared.logging_utils import setup_logger
        from logging.handlers import RotatingFileHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("test_bot")

                has_rotating_handler = any(
                    isinstance(h, RotatingFileHandler)
                    for h in logger.handlers
                )
                assert has_rotating_handler, "Logger should have a RotatingFileHandler"

    def test_setup_logger_file_rotation_config(self):
        """File handler should have correct rotation config (10MB, keep 5)."""
        from bots.shared.logging_utils import setup_logger
        from logging.handlers import RotatingFileHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("test_bot")

                rotating_handler = next(
                    (h for h in logger.handlers if isinstance(h, RotatingFileHandler)),
                    None
                )
                assert rotating_handler is not None
                assert rotating_handler.maxBytes == 10 * 1024 * 1024  # 10MB
                assert rotating_handler.backupCount == 5

    def test_setup_logger_reuses_existing(self):
        """Calling setup_logger twice should return same logger without duplicating handlers."""
        from bots.shared.logging_utils import setup_logger

        logger1 = setup_logger("reuse_test")
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logger("reuse_test")

        assert logger1 is logger2
        assert len(logger2.handlers) == handler_count1


class TestLogApiCall:
    """Tests for log_api_call function."""

    def test_log_api_call_logs_structured_data(self):
        """log_api_call should log structured JSON data."""
        from bots.shared.logging_utils import setup_logger, log_api_call

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("api_test")

                log_api_call(
                    logger,
                    api="telegram",
                    method="sendMessage",
                    latency=0.123,
                    success=True
                )

                # Read log file and verify JSON structure
                log_file = Path(tmpdir) / "api_test.log"
                assert log_file.exists()

                log_content = log_file.read_text()
                # Should contain JSON with the expected fields
                assert "telegram" in log_content
                assert "sendMessage" in log_content
                assert "0.123" in log_content or "123" in log_content

    def test_log_api_call_includes_timestamp(self):
        """log_api_call should include timestamp in log."""
        from bots.shared.logging_utils import setup_logger, log_api_call

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("api_ts_test")

                log_api_call(logger, api="test", method="test", latency=0.1, success=True)

                log_file = Path(tmpdir) / "api_ts_test.log"
                log_content = log_file.read_text()

                # Should have timestamp format
                assert "202" in log_content  # Year 202X

    def test_log_api_call_tracks_failures(self):
        """log_api_call should properly log failures."""
        from bots.shared.logging_utils import setup_logger, log_api_call

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("api_fail_test")

                log_api_call(
                    logger,
                    api="openai",
                    method="chat",
                    latency=5.0,
                    success=False,
                    error="Rate limited"
                )

                log_file = Path(tmpdir) / "api_fail_test.log"
                log_content = log_file.read_text()

                assert "Rate limited" in log_content
                assert "false" in log_content.lower() or "False" in log_content


class TestLogUserMessage:
    """Tests for log_user_message function."""

    def test_log_user_message_logs_user_id(self):
        """log_user_message should log the user ID."""
        from bots.shared.logging_utils import setup_logger, log_user_message

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("user_msg_test")

                log_user_message(logger, user_id=12345678, message="Hello bot!")

                log_file = Path(tmpdir) / "user_msg_test.log"
                log_content = log_file.read_text()

                assert "12345678" in log_content

    def test_log_user_message_truncates_long_messages(self):
        """log_user_message should truncate very long messages."""
        from bots.shared.logging_utils import setup_logger, log_user_message

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("user_trunc_test")

                long_message = "A" * 10000
                log_user_message(logger, user_id=123, message=long_message)

                log_file = Path(tmpdir) / "user_trunc_test.log"
                log_content = log_file.read_text()

                # Should be truncated to reasonable length
                assert len(log_content) < 5000  # Much less than 10000

    def test_log_user_message_sanitizes_pii(self):
        """log_user_message should not log sensitive data in plain text."""
        from bots.shared.logging_utils import setup_logger, log_user_message

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("user_pii_test")

                # The actual message content should be hashed or truncated
                # to prevent logging of sensitive user data
                log_user_message(
                    logger,
                    user_id=123,
                    message="My password is secret123!"
                )

                log_file = Path(tmpdir) / "user_pii_test.log"
                log_content = log_file.read_text()

                # Full message should not be in logs - just a preview
                assert "secret123" not in log_content


class TestLogBotResponse:
    """Tests for log_bot_response function."""

    def test_log_bot_response_logs_token_count(self):
        """log_bot_response should log the token count."""
        from bots.shared.logging_utils import setup_logger, log_bot_response

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("bot_resp_test")

                log_bot_response(
                    logger,
                    response="Here is my response to you.",
                    tokens=150
                )

                log_file = Path(tmpdir) / "bot_resp_test.log"
                log_content = log_file.read_text()

                assert "150" in log_content

    def test_log_bot_response_logs_response_preview(self):
        """log_bot_response should log a preview of the response."""
        from bots.shared.logging_utils import setup_logger, log_bot_response

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("bot_preview_test")

                log_bot_response(
                    logger,
                    response="This is a test response that is longer than the preview limit.",
                    tokens=50
                )

                log_file = Path(tmpdir) / "bot_preview_test.log"
                log_content = log_file.read_text()

                # Should contain at least part of the response
                assert "test response" in log_content.lower() or "response" in log_content.lower()


class TestGetRecentLogs:
    """Tests for get_recent_logs function."""

    def test_get_recent_logs_returns_list(self):
        """get_recent_logs should return a list."""
        from bots.shared.logging_utils import setup_logger, log_api_call, get_recent_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("recent_test")
                log_api_call(logger, api="test", method="test", latency=0.1, success=True)

                logs = get_recent_logs("recent_test")

                assert isinstance(logs, list)

    def test_get_recent_logs_respects_count(self):
        """get_recent_logs should respect the count parameter."""
        from bots.shared.logging_utils import setup_logger, log_api_call, get_recent_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("count_test")

                # Log multiple entries
                for i in range(10):
                    log_api_call(logger, api=f"api_{i}", method="test", latency=0.1, success=True)

                logs = get_recent_logs("count_test", count=5)

                assert len(logs) <= 5

    def test_get_recent_logs_returns_most_recent_first(self):
        """get_recent_logs should return most recent entries first."""
        from bots.shared.logging_utils import setup_logger, log_api_call, get_recent_logs
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("order_test")

                log_api_call(logger, api="first", method="test", latency=0.1, success=True)
                time.sleep(0.01)  # Small delay to ensure different timestamps
                log_api_call(logger, api="second", method="test", latency=0.1, success=True)

                logs = get_recent_logs("order_test", count=2)

                # Most recent should be first
                assert len(logs) >= 2
                # The last logged item should appear first in results
                assert "second" in str(logs[0])

    def test_get_recent_logs_returns_empty_for_nonexistent_bot(self):
        """get_recent_logs should return empty list for bot with no logs."""
        from bots.shared.logging_utils import get_recent_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logs = get_recent_logs("nonexistent_bot_xyz")

                assert logs == []


class TestRequestIdTracking:
    """Tests for request ID tracking."""

    def test_request_id_in_log_context(self):
        """Logs should include request ID for tracing."""
        from bots.shared.logging_utils import setup_logger, log_api_call, set_request_id

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("reqid_test")

                # Set a request ID for this context
                set_request_id("req-12345-abcde")

                log_api_call(logger, api="test", method="test", latency=0.1, success=True)

                log_file = Path(tmpdir) / "reqid_test.log"
                log_content = log_file.read_text()

                assert "req-12345-abcde" in log_content


class TestJSONFormatting:
    """Tests for JSON structured logging."""

    def test_file_output_is_json(self):
        """File log output should be valid JSON lines."""
        from bots.shared.logging_utils import setup_logger, log_api_call

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("json_test")

                log_api_call(logger, api="test", method="test", latency=0.1, success=True)

                log_file = Path(tmpdir) / "json_test.log"
                log_content = log_file.read_text().strip()

                # Each line should be valid JSON
                for line in log_content.split("\n"):
                    if line.strip():
                        parsed = json.loads(line)
                        assert isinstance(parsed, dict)

    def test_json_contains_required_fields(self):
        """JSON log entries should contain required fields."""
        from bots.shared.logging_utils import setup_logger, log_api_call

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("json_fields_test")

                log_api_call(logger, api="telegram", method="send", latency=0.5, success=True)

                log_file = Path(tmpdir) / "json_fields_test.log"
                log_content = log_file.read_text().strip()

                # Parse last line
                parsed = json.loads(log_content.split("\n")[-1])

                # Required fields
                assert "timestamp" in parsed
                assert "level" in parsed
                assert "bot_name" in parsed
                assert "message" in parsed


class TestColoredConsoleOutput:
    """Tests for colored console output."""

    def test_console_handler_uses_color_formatter(self):
        """Console handler should use a color-aware formatter."""
        from bots.shared.logging_utils import setup_logger, ColoredFormatter

        logger = setup_logger("color_test")

        stream_handler = next(
            (h for h in logger.handlers
             if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)),
            None
        )

        assert stream_handler is not None
        assert isinstance(stream_handler.formatter, ColoredFormatter)


class TestLogAggregation:
    """Tests for log aggregation support."""

    def test_logs_include_bot_name_for_aggregation(self):
        """All logs should include bot_name for aggregation."""
        from bots.shared.logging_utils import setup_logger, log_api_call, log_user_message, log_bot_response

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("aggregation_test")

                log_api_call(logger, api="test", method="test", latency=0.1, success=True)
                log_user_message(logger, user_id=123, message="test")
                log_bot_response(logger, response="test", tokens=10)

                log_file = Path(tmpdir) / "aggregation_test.log"
                log_content = log_file.read_text()

                # Every line should contain the bot name
                for line in log_content.strip().split("\n"):
                    if line.strip():
                        parsed = json.loads(line)
                        assert parsed.get("bot_name") == "aggregation_test"

    def test_logs_include_log_type_for_filtering(self):
        """Logs should include log_type field for filtering."""
        from bots.shared.logging_utils import setup_logger, log_api_call, log_user_message, log_bot_response

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CLAWDBOT_LOG_DIR": tmpdir}):
                logger = setup_logger("type_test")

                log_api_call(logger, api="test", method="test", latency=0.1, success=True)

                log_file = Path(tmpdir) / "type_test.log"
                log_content = log_file.read_text().strip()

                parsed = json.loads(log_content.split("\n")[-1])
                assert "log_type" in parsed
                assert parsed["log_type"] == "api_call"
