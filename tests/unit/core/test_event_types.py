"""
Unit tests for core/events/types.py - Event type definitions.

Tests cover:
- Event base class creation and serialization
- MessageReceived and MessageSent event types
- APICallStarted and APICallCompleted event types
- ErrorOccurred and HealthCheckFailed event types
- BotStarted and BotStopped event types
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add project root to path to avoid core/__init__.py import chain issues
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestEventBaseClass:
    """Tests for Event base class."""

    def test_event_creation_with_type(self):
        """Event should be created with required type field."""
        from core.events.types import Event

        event = Event(type="test.event")

        assert event.type == "test.event"
        assert isinstance(event.timestamp, datetime)
        assert event.data == {}

    def test_event_creation_with_data(self):
        """Event should accept optional data dict."""
        from core.events.types import Event

        event = Event(type="test.event", data={"key": "value"})

        assert event.data["key"] == "value"

    def test_event_creation_with_custom_timestamp(self):
        """Event should accept optional custom timestamp."""
        from core.events.types import Event

        custom_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event = Event(type="test.event", timestamp=custom_time)

        assert event.timestamp == custom_time

    def test_event_has_unique_id(self):
        """Each event should have a unique ID."""
        from core.events.types import Event

        event1 = Event(type="test.event")
        event2 = Event(type="test.event")

        assert event1.id != event2.id
        assert len(event1.id) > 0

    def test_event_to_dict(self):
        """Event should serialize to dictionary."""
        from core.events.types import Event

        event = Event(type="test.event", data={"key": "value"})
        result = event.to_dict()

        assert result["type"] == "test.event"
        assert result["data"] == {"key": "value"}
        assert "timestamp" in result
        assert "id" in result

    def test_event_from_dict(self):
        """Event should deserialize from dictionary."""
        from core.events.types import Event

        data = {
            "id": "test-id-123",
            "type": "test.event",
            "data": {"key": "value"},
            "timestamp": "2026-01-01T12:00:00+00:00"
        }
        event = Event.from_dict(data)

        assert event.id == "test-id-123"
        assert event.type == "test.event"
        assert event.data["key"] == "value"


class TestMessageEvents:
    """Tests for MessageReceived and MessageSent events."""

    def test_message_received_creation(self):
        """MessageReceived should have source and content."""
        from core.events.types import MessageReceived

        event = MessageReceived(
            source="telegram",
            content="Hello world",
            sender_id="user123"
        )

        assert event.type == "message.received"
        assert event.data["source"] == "telegram"
        assert event.data["content"] == "Hello world"
        assert event.data["sender_id"] == "user123"

    def test_message_sent_creation(self):
        """MessageSent should have destination and content."""
        from core.events.types import MessageSent

        event = MessageSent(
            destination="twitter",
            content="Tweet content",
            recipient_id="user456"
        )

        assert event.type == "message.sent"
        assert event.data["destination"] == "twitter"
        assert event.data["content"] == "Tweet content"
        assert event.data["recipient_id"] == "user456"


class TestAPICallEvents:
    """Tests for APICallStarted and APICallCompleted events."""

    def test_api_call_started_creation(self):
        """APICallStarted should have endpoint and method."""
        from core.events.types import APICallStarted

        event = APICallStarted(
            endpoint="/api/v1/users",
            method="GET",
            request_id="req-123"
        )

        assert event.type == "api.call.started"
        assert event.data["endpoint"] == "/api/v1/users"
        assert event.data["method"] == "GET"
        assert event.data["request_id"] == "req-123"

    def test_api_call_completed_creation(self):
        """APICallCompleted should have status and duration."""
        from core.events.types import APICallCompleted

        event = APICallCompleted(
            endpoint="/api/v1/users",
            method="GET",
            request_id="req-123",
            status_code=200,
            duration_ms=150.5
        )

        assert event.type == "api.call.completed"
        assert event.data["status_code"] == 200
        assert event.data["duration_ms"] == 150.5

    def test_api_call_completed_with_error(self):
        """APICallCompleted should capture error info."""
        from core.events.types import APICallCompleted

        event = APICallCompleted(
            endpoint="/api/v1/users",
            method="POST",
            request_id="req-456",
            status_code=500,
            duration_ms=50.0,
            error="Internal Server Error"
        )

        assert event.data["error"] == "Internal Server Error"
        assert event.data["status_code"] == 500


class TestErrorEvents:
    """Tests for ErrorOccurred and HealthCheckFailed events."""

    def test_error_occurred_creation(self):
        """ErrorOccurred should capture error details."""
        from core.events.types import ErrorOccurred

        event = ErrorOccurred(
            error_type="ValueError",
            message="Invalid input",
            component="twitter_bot",
            traceback="Traceback..."
        )

        assert event.type == "error.occurred"
        assert event.data["error_type"] == "ValueError"
        assert event.data["message"] == "Invalid input"
        assert event.data["component"] == "twitter_bot"
        assert event.data["traceback"] == "Traceback..."

    def test_error_occurred_with_context(self):
        """ErrorOccurred should accept additional context."""
        from core.events.types import ErrorOccurred

        event = ErrorOccurred(
            error_type="ConnectionError",
            message="Connection refused",
            component="telegram_bot",
            context={"retry_count": 3, "last_attempt": "2026-01-01"}
        )

        assert event.data["context"]["retry_count"] == 3

    def test_health_check_failed_creation(self):
        """HealthCheckFailed should capture check details."""
        from core.events.types import HealthCheckFailed

        event = HealthCheckFailed(
            component="database",
            check_name="connection_test",
            reason="Connection timeout",
            severity="critical"
        )

        assert event.type == "health.check.failed"
        assert event.data["component"] == "database"
        assert event.data["check_name"] == "connection_test"
        assert event.data["reason"] == "Connection timeout"
        assert event.data["severity"] == "critical"


class TestBotEvents:
    """Tests for BotStarted and BotStopped events."""

    def test_bot_started_creation(self):
        """BotStarted should capture bot startup details."""
        from core.events.types import BotStarted

        event = BotStarted(
            bot_name="twitter_bot",
            bot_id="bot-001",
            version="1.2.3"
        )

        assert event.type == "bot.started"
        assert event.data["bot_name"] == "twitter_bot"
        assert event.data["bot_id"] == "bot-001"
        assert event.data["version"] == "1.2.3"

    def test_bot_started_with_config(self):
        """BotStarted should accept optional config snapshot."""
        from core.events.types import BotStarted

        event = BotStarted(
            bot_name="telegram_bot",
            bot_id="bot-002",
            config={"polling_interval": 60, "max_retries": 3}
        )

        assert event.data["config"]["polling_interval"] == 60

    def test_bot_stopped_creation(self):
        """BotStopped should capture shutdown details."""
        from core.events.types import BotStopped

        event = BotStopped(
            bot_name="twitter_bot",
            bot_id="bot-001",
            reason="manual_shutdown",
            uptime_seconds=3600
        )

        assert event.type == "bot.stopped"
        assert event.data["bot_name"] == "twitter_bot"
        assert event.data["reason"] == "manual_shutdown"
        assert event.data["uptime_seconds"] == 3600

    def test_bot_stopped_with_error(self):
        """BotStopped should capture crash details."""
        from core.events.types import BotStopped

        event = BotStopped(
            bot_name="telegram_bot",
            bot_id="bot-002",
            reason="crash",
            error="Out of memory"
        )

        assert event.data["reason"] == "crash"
        assert event.data["error"] == "Out of memory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
