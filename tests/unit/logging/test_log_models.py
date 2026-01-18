"""
Tests for log entry data models.
"""

import pytest
from datetime import datetime, timezone
from dataclasses import asdict
import json


class TestLogEntry:
    """Tests for LogEntry data model."""

    def test_log_entry_creation(self):
        """Test creating a basic log entry."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="jarvis.trading",
            message="Test message",
        )

        assert entry.level == "INFO"
        assert entry.logger == "jarvis.trading"
        assert entry.message == "Test message"

    def test_log_entry_with_context(self):
        """Test log entry with custom context."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="jarvis.trading",
            message="Trade executed",
            service="trading_engine",
            correlation_id="trade-abc123",
            user_id="tg_8527130908",
            context={"symbol": "SOL", "action": "BUY", "amount_usd": 100.50},
        )

        assert entry.service == "trading_engine"
        assert entry.correlation_id == "trade-abc123"
        assert entry.context["symbol"] == "SOL"

    def test_log_entry_with_active_flags(self):
        """Test log entry with active feature flags."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="jarvis.trading",
            message="Flag check",
            active_flags=["LIVE_TRADING_ENABLED", "DEXTER_ENABLED"],
        )

        assert "LIVE_TRADING_ENABLED" in entry.active_flags
        assert len(entry.active_flags) == 2

    def test_log_entry_with_duration(self):
        """Test log entry with duration tracking."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="jarvis.trading",
            message="Slow operation",
            duration_ms=234.56,
        )

        assert entry.duration_ms == 234.56

    def test_log_entry_with_error(self):
        """Test log entry with error information."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="ERROR",
            logger="jarvis.trading",
            message="Trade failed",
            error="ConnectionTimeout",
            stack_trace="Traceback...",
        )

        assert entry.error == "ConnectionTimeout"
        assert entry.stack_trace == "Traceback..."

    def test_log_entry_to_dict(self):
        """Test converting log entry to dictionary."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="test",
            message="Test",
        )

        data = entry.to_dict()
        assert isinstance(data, dict)
        assert "timestamp" in data
        assert "level" in data

    def test_log_entry_to_json(self):
        """Test converting log entry to JSON."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            logger="test",
            message="Test",
            context={"key": "value"},
        )

        json_str = entry.to_json()
        parsed = json.loads(json_str)
        assert parsed["level"] == "INFO"
        assert parsed["context"]["key"] == "value"

    def test_log_entry_timestamp_iso8601(self):
        """Test that timestamp is ISO8601 formatted."""
        from core.logging.log_models import LogEntry

        entry = LogEntry(
            timestamp=datetime(2026, 1, 18, 14, 30, 0, 123456, tzinfo=timezone.utc),
            level="INFO",
            logger="test",
            message="Test",
        )

        data = entry.to_dict()
        # Should be ISO8601 with Z suffix
        assert "2026-01-18" in data["timestamp"]
        assert "Z" in data["timestamp"]


class TestLogContext:
    """Tests for LogContext data model."""

    def test_log_context_creation(self):
        """Test creating a log context."""
        from core.logging.log_models import LogContext

        ctx = LogContext(
            service="trading_engine",
            correlation_id="trade-abc123",
            user_id="tg_8527130908",
        )

        assert ctx.service == "trading_engine"
        assert ctx.correlation_id == "trade-abc123"

    def test_log_context_with_flags(self):
        """Test log context with active flags."""
        from core.logging.log_models import LogContext

        ctx = LogContext(
            service="trading",
            active_flags=["FLAG_A", "FLAG_B"],
        )

        assert len(ctx.active_flags) == 2

    def test_log_context_merge(self):
        """Test merging log contexts."""
        from core.logging.log_models import LogContext

        ctx1 = LogContext(service="trading")
        ctx2 = LogContext(user_id="user123", correlation_id="corr456")

        merged = ctx1.merge(ctx2)
        assert merged.service == "trading"
        assert merged.user_id == "user123"
        assert merged.correlation_id == "corr456"


class TestBusinessEvent:
    """Tests for BusinessEvent model."""

    def test_business_event_creation(self):
        """Test creating a business event."""
        from core.logging.log_models import BusinessEvent

        event = BusinessEvent(
            event_name="TRADE_EXECUTED",
            data={"symbol": "SOL", "amount": 100},
        )

        assert event.event_name == "TRADE_EXECUTED"
        assert event.data["symbol"] == "SOL"

    def test_business_event_to_log_entry(self):
        """Test converting business event to log entry."""
        from core.logging.log_models import BusinessEvent

        event = BusinessEvent(
            event_name="USER_LOGIN",
            data={"user_id": "123", "source": "telegram"},
        )

        entry = event.to_log_entry(logger_name="jarvis.auth")
        assert entry.level == "INFO"
        assert entry.logger == "jarvis.auth"
        assert "USER_LOGIN" in entry.message
