"""
Unit tests for core/events/handlers.py - Event handler implementations.

Tests cover:
- EventHandler abstract base class
- LoggingHandler - logs all events
- MetricsHandler - updates metrics
- AlertHandler - sends alerts on error events
"""

import pytest
import sys
from pathlib import Path
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path to avoid core/__init__.py import chain issues
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestEventHandlerBaseClass:
    """Tests for EventHandler abstract base class."""

    def test_handler_is_abstract(self):
        """EventHandler should be abstract and require handle() implementation."""
        from core.events.handlers import EventHandler

        with pytest.raises(TypeError):
            EventHandler()  # Should not be instantiable

    def test_handler_subclass_must_implement_handle(self):
        """Subclass must implement handle() method."""
        from core.events.handlers import EventHandler

        class IncompleteHandler(EventHandler):
            pass

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_handler_subclass_with_handle(self):
        """Subclass with handle() should be instantiable."""
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class CompleteHandler(EventHandler):
            async def handle(self, event: Event) -> None:
                pass

        handler = CompleteHandler()
        assert handler is not None

    @pytest.mark.asyncio
    async def test_handler_handle_method_signature(self):
        """handle() should accept Event and return None."""
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class TestHandler(EventHandler):
            def __init__(self):
                self.handled_events: List[Event] = []

            async def handle(self, event: Event) -> None:
                self.handled_events.append(event)

        handler = TestHandler()
        event = Event(type="test.event")

        result = await handler.handle(event)

        assert result is None
        assert len(handler.handled_events) == 1


class TestLoggingHandler:
    """Tests for LoggingHandler that logs all events."""

    def test_logging_handler_creation(self):
        """LoggingHandler should be creatable with optional logger."""
        from core.events.handlers import LoggingHandler

        handler = LoggingHandler()
        assert handler is not None

    def test_logging_handler_with_custom_logger(self):
        """LoggingHandler should accept custom logger."""
        from core.events.handlers import LoggingHandler

        custom_logger = logging.getLogger("custom")
        handler = LoggingHandler(logger=custom_logger)

        assert handler.logger is custom_logger

    @pytest.mark.asyncio
    async def test_logging_handler_logs_event(self):
        """LoggingHandler should log event details."""
        from core.events.handlers import LoggingHandler
        from core.events.types import Event

        handler = LoggingHandler()
        event = Event(type="test.event", data={"key": "value"})

        with patch.object(handler.logger, 'info') as mock_log:
            await handler.handle(event)
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_logging_handler_logs_error_events_as_warning(self):
        """LoggingHandler should log error events at warning level."""
        from core.events.handlers import LoggingHandler
        from core.events.types import ErrorOccurred

        handler = LoggingHandler()
        event = ErrorOccurred(
            error_type="TestError",
            message="Test message",
            component="test"
        )

        with patch.object(handler.logger, 'warning') as mock_warning:
            await handler.handle(event)
            mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_logging_handler_includes_event_type(self):
        """Log message should include event type."""
        from core.events.handlers import LoggingHandler
        from core.events.types import Event

        handler = LoggingHandler()
        event = Event(type="custom.event.type")

        with patch.object(handler.logger, 'info') as mock_log:
            await handler.handle(event)
            call_args = str(mock_log.call_args)
            assert "custom.event.type" in call_args


class TestMetricsHandler:
    """Tests for MetricsHandler that updates metrics."""

    def test_metrics_handler_creation(self):
        """MetricsHandler should be creatable."""
        from core.events.handlers import MetricsHandler

        handler = MetricsHandler()
        assert handler is not None

    @pytest.mark.asyncio
    async def test_metrics_handler_counts_events(self):
        """MetricsHandler should count events by type."""
        from core.events.handlers import MetricsHandler
        from core.events.types import Event

        handler = MetricsHandler()

        await handler.handle(Event(type="event.a"))
        await handler.handle(Event(type="event.a"))
        await handler.handle(Event(type="event.b"))

        metrics = handler.get_metrics()

        assert metrics["event.a"]["count"] == 2
        assert metrics["event.b"]["count"] == 1

    @pytest.mark.asyncio
    async def test_metrics_handler_tracks_last_seen(self):
        """MetricsHandler should track last seen time for each event type."""
        from core.events.handlers import MetricsHandler
        from core.events.types import Event

        handler = MetricsHandler()
        event = Event(type="test.event")

        await handler.handle(event)
        metrics = handler.get_metrics()

        assert "last_seen" in metrics["test.event"]
        assert isinstance(metrics["test.event"]["last_seen"], datetime)

    @pytest.mark.asyncio
    async def test_metrics_handler_tracks_total_events(self):
        """MetricsHandler should track total events processed."""
        from core.events.handlers import MetricsHandler
        from core.events.types import Event

        handler = MetricsHandler()

        await handler.handle(Event(type="event.a"))
        await handler.handle(Event(type="event.b"))
        await handler.handle(Event(type="event.c"))

        assert handler.total_events == 3

    def test_metrics_handler_reset(self):
        """MetricsHandler should support resetting metrics."""
        from core.events.handlers import MetricsHandler

        handler = MetricsHandler()
        handler.reset()

        metrics = handler.get_metrics()
        assert metrics == {}
        assert handler.total_events == 0


class TestAlertHandler:
    """Tests for AlertHandler that sends alerts on error events."""

    def test_alert_handler_creation(self):
        """AlertHandler should be creatable with alert callback."""
        from core.events.handlers import AlertHandler

        async def alert_callback(event, message):
            pass

        handler = AlertHandler(alert_callback=alert_callback)
        assert handler is not None

    def test_alert_handler_requires_callback(self):
        """AlertHandler should require an alert callback."""
        from core.events.handlers import AlertHandler

        with pytest.raises(TypeError):
            AlertHandler()

    @pytest.mark.asyncio
    async def test_alert_handler_triggers_on_error(self):
        """AlertHandler should trigger alert on ErrorOccurred events."""
        from core.events.handlers import AlertHandler
        from core.events.types import ErrorOccurred

        alerts_received = []

        async def capture_alert(event, message):
            alerts_received.append((event, message))

        handler = AlertHandler(alert_callback=capture_alert)
        event = ErrorOccurred(
            error_type="CriticalError",
            message="System failure",
            component="main"
        )

        await handler.handle(event)

        assert len(alerts_received) == 1
        assert "CriticalError" in alerts_received[0][1]

    @pytest.mark.asyncio
    async def test_alert_handler_triggers_on_health_check_failed(self):
        """AlertHandler should trigger alert on HealthCheckFailed events."""
        from core.events.handlers import AlertHandler
        from core.events.types import HealthCheckFailed

        alerts_received = []

        async def capture_alert(event, message):
            alerts_received.append((event, message))

        handler = AlertHandler(alert_callback=capture_alert)
        event = HealthCheckFailed(
            component="database",
            check_name="ping",
            reason="Timeout",
            severity="critical"
        )

        await handler.handle(event)

        assert len(alerts_received) == 1

    @pytest.mark.asyncio
    async def test_alert_handler_ignores_normal_events(self):
        """AlertHandler should not trigger on normal events."""
        from core.events.handlers import AlertHandler
        from core.events.types import MessageReceived

        alerts_received = []

        async def capture_alert(event, message):
            alerts_received.append((event, message))

        handler = AlertHandler(alert_callback=capture_alert)
        event = MessageReceived(
            source="telegram",
            content="Hello",
            sender_id="user123"
        )

        await handler.handle(event)

        assert len(alerts_received) == 0

    @pytest.mark.asyncio
    async def test_alert_handler_severity_filter(self):
        """AlertHandler should support severity filtering."""
        from core.events.handlers import AlertHandler
        from core.events.types import HealthCheckFailed

        alerts_received = []

        async def capture_alert(event, message):
            alerts_received.append((event, message))

        handler = AlertHandler(
            alert_callback=capture_alert,
            min_severity="critical"
        )

        # This should not trigger (severity = warning)
        await handler.handle(HealthCheckFailed(
            component="cache",
            check_name="size",
            reason="Cache size high",
            severity="warning"
        ))

        # This should trigger (severity = critical)
        await handler.handle(HealthCheckFailed(
            component="database",
            check_name="connection",
            reason="Connection lost",
            severity="critical"
        ))

        assert len(alerts_received) == 1


class TestHandlerChaining:
    """Tests for chaining multiple handlers."""

    @pytest.mark.asyncio
    async def test_multiple_handlers_process_same_event(self):
        """Multiple handlers should process the same event."""
        from core.events.handlers import EventHandler
        from core.events.types import Event

        class CountingHandler(EventHandler):
            def __init__(self):
                self.count = 0

            async def handle(self, event: Event) -> None:
                self.count += 1

        handler1 = CountingHandler()
        handler2 = CountingHandler()

        event = Event(type="test.event")

        await handler1.handle(event)
        await handler2.handle(event)

        assert handler1.count == 1
        assert handler2.count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
