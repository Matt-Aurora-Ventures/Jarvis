"""Unit tests for StructuredLogger.

TDD: These tests define the expected behavior of StructuredLogger.
"""

import json
import logging
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_import_structured_logger(self):
        """StructuredLogger can be imported from tg_bot.logging."""
        from tg_bot.logging import StructuredLogger
        assert StructuredLogger is not None

    def test_log_event_creates_json(self, caplog):
        """log_event produces JSON-formatted log with event type, action, and timestamp."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_event(
                event_type="TEST_EVENT",
                action="test_action",
                context={"key": "value"},
                level="info"
            )

        # Find the log record
        assert len(caplog.records) > 0
        log_message = caplog.records[-1].message

        # Should contain event type
        assert "TEST_EVENT" in log_message

        # Should be valid JSON (part of the message)
        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["event"] == "TEST_EVENT"
        assert parsed["action"] == "test_action"
        assert parsed["key"] == "value"
        assert "timestamp" in parsed

    def test_log_spam_decision_all_fields(self, caplog):
        """log_spam_decision logs all spam decision fields in JSON format."""
        from tg_bot.logging import StructuredLogger

        reputation = {
            "is_trusted": False,
            "clean_messages": 5,
            "reputation_score": -10
        }

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_spam_decision(
                action="ban",
                user_id=12345,
                username="spammer",
                confidence=0.95,
                reason="scam_wallet",
                message_preview="Buy crypto at scam.com/airdrop/claim",
                reputation=reputation
            )

        assert len(caplog.records) > 0
        log_message = caplog.records[-1].message

        assert "SPAM_DECISION" in log_message
        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["action"] == "ban"
        assert parsed["user_id"] == 12345
        assert parsed["username"] == "spammer"
        assert parsed["confidence"] == 0.95
        assert parsed["reason"] == "scam_wallet"
        assert len(parsed["message_preview"]) <= 50  # Truncated
        assert "reputation" in parsed
        assert parsed["reputation"]["is_trusted"] is False
        assert parsed["reputation"]["clean_messages"] == 5
        assert parsed["reputation"]["score"] == -10

    def test_log_spam_decision_without_reputation(self, caplog):
        """log_spam_decision works without reputation data."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_spam_decision(
                action="warn",
                user_id=67890,
                username="newuser",
                confidence=0.55,
                reason="suspicious_pattern",
                message_preview="Message text",
                reputation=None
            )

        assert len(caplog.records) > 0
        json_part = caplog.records[-1].message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert "reputation" not in parsed

    def test_log_ai_routing_with_fallback(self, caplog):
        """log_ai_routing logs AI provider and fallback tier."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_ai_routing(
                provider="dexter",
                user_id=11111,
                message_preview="What's the price of SOL?",
                success=True,
                fallback_tier=1
            )

        assert len(caplog.records) > 0
        log_message = caplog.records[-1].message

        assert "AI_ROUTING" in log_message
        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["provider"] == "dexter"
        assert parsed["user_id"] == 11111
        assert parsed["success"] is True
        assert parsed["fallback_tier"] == 1

    def test_log_ai_routing_without_fallback_tier(self, caplog):
        """log_ai_routing works without fallback_tier parameter."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_ai_routing(
                provider="grok",
                user_id=22222,
                message_preview="Tell me about crypto",
                success=False
            )

        json_part = caplog.records[-1].message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert "fallback_tier" not in parsed

    def test_log_vibe_request_all_fields(self, caplog):
        """log_vibe_request logs vibe coding execution details."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_vibe_request(
                user_id=33333,
                username="admin",
                prompt_preview="jarvis fix the bug in bot_core.py",
                success=True,
                tokens_used=1500,
                duration_sec=12.5,
                sanitized=True
            )

        log_message = caplog.records[-1].message
        assert "VIBE_REQUEST" in log_message

        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["user_id"] == 33333
        assert parsed["username"] == "admin"
        assert len(parsed["prompt_preview"]) <= 100
        assert parsed["success"] is True
        assert parsed["tokens_used"] == 1500
        assert parsed["duration_sec"] == 12.5
        assert parsed["sanitized"] is True

    def test_log_terminal_command_success(self, caplog):
        """log_terminal_command logs terminal command execution."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_terminal_command(
                user_id=44444,
                username="admin",
                command_preview="git status",
                success=True,
                is_admin=True
            )

        log_message = caplog.records[-1].message
        assert "TERMINAL_CMD" in log_message

        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["user_id"] == 44444
        assert parsed["success"] is True
        assert parsed["is_admin"] is True

    def test_log_terminal_command_failure_uses_warning(self, caplog):
        """log_terminal_command uses warning level for failures."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.WARNING):
            StructuredLogger.log_terminal_command(
                user_id=55555,
                username="admin",
                command_preview="invalid command",
                success=False,
                is_admin=True
            )

        assert caplog.records[-1].levelno == logging.WARNING

    def test_log_message_flow(self, caplog):
        """log_message_flow logs message routing decisions."""
        from tg_bot.logging import StructuredLogger

        # Need to set DEBUG level on the specific logger module
        with caplog.at_level(logging.DEBUG, logger="tg_bot.logging.structured_logger"):
            StructuredLogger.log_message_flow(
                user_id=66666,
                message_preview="hello jarvis",
                route="ai_response",
                is_admin=False,
                should_reply=True
            )

        assert len(caplog.records) > 0, "No log records captured at DEBUG level"
        log_message = caplog.records[-1].message
        assert "MESSAGE_FLOW" in log_message

        json_part = log_message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        assert parsed["route"] == "ai_response"
        assert parsed["should_reply"] is True

    def test_timestamp_is_iso_format(self, caplog):
        """All logs include ISO-formatted timestamps."""
        from tg_bot.logging import StructuredLogger

        with caplog.at_level(logging.INFO):
            StructuredLogger.log_event("TEST", "test", {})

        json_part = caplog.records[-1].message.split(": ", 1)[1]
        parsed = json.loads(json_part)

        # Should be parseable as ISO timestamp
        timestamp = parsed["timestamp"]
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed_time is not None
