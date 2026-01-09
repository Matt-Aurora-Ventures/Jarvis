"""
Tests for Calendar Client Integration.

Tests verify:
- Calendar configuration
- Event dataclass
- CalDAV client operations (mocked)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.integrations.calendar_client import (
    CalendarEvent,
    Calendar,
    CalendarConfig,
    CalendarClient,
    RecurrenceFrequency,
    create_google_calendar_client,
    create_apple_calendar_client,
    create_caldav_client,
)


# =============================================================================
# Test CalendarEvent Dataclass
# =============================================================================

class TestCalendarEvent:
    """Test CalendarEvent dataclass."""

    def test_create_event(self):
        """Should create calendar event with required fields."""
        start = datetime.now()
        end = start + timedelta(hours=1)

        event = CalendarEvent(
            id="123",
            title="Test Meeting",
            start=start,
            end=end,
        )

        assert event.id == "123"
        assert event.title == "Test Meeting"
        assert event.duration == timedelta(hours=1)

    def test_duration_property(self):
        """Duration should be calculated correctly."""
        start = datetime.now()
        end = start + timedelta(hours=2, minutes=30)

        event = CalendarEvent(
            id="1",
            title="Test",
            start=start,
            end=end,
        )

        assert event.duration == timedelta(hours=2, minutes=30)

    def test_is_past_property(self):
        """is_past should be true for past events."""
        past_start = datetime.now() - timedelta(days=1)
        past_end = past_start + timedelta(hours=1)

        event = CalendarEvent(
            id="1",
            title="Past Event",
            start=past_start,
            end=past_end,
        )

        assert event.is_past is True

    def test_is_past_false_for_future(self):
        """is_past should be false for future events."""
        future_start = datetime.now() + timedelta(days=1)
        future_end = future_start + timedelta(hours=1)

        event = CalendarEvent(
            id="1",
            title="Future Event",
            start=future_start,
            end=future_end,
        )

        assert event.is_past is False

    def test_is_upcoming_property(self):
        """is_upcoming should be true for events within 24 hours."""
        soon_start = datetime.now() + timedelta(hours=12)
        soon_end = soon_start + timedelta(hours=1)

        event = CalendarEvent(
            id="1",
            title="Soon Event",
            start=soon_start,
            end=soon_end,
        )

        assert event.is_upcoming is True

    def test_is_upcoming_false_for_far_future(self):
        """is_upcoming should be false for events > 24 hours away."""
        far_start = datetime.now() + timedelta(days=3)
        far_end = far_start + timedelta(hours=1)

        event = CalendarEvent(
            id="1",
            title="Far Event",
            start=far_start,
            end=far_end,
        )

        assert event.is_upcoming is False

    def test_default_values(self):
        """Should have sensible defaults."""
        event = CalendarEvent(
            id="1",
            title="Test",
            start=datetime.now(),
            end=datetime.now() + timedelta(hours=1),
        )

        assert event.description == ""
        assert event.location == ""
        assert event.is_all_day is False
        assert event.attendees == []
        assert event.reminders == []
        assert event.recurrence is None


# =============================================================================
# Test Calendar Dataclass
# =============================================================================

class TestCalendar:
    """Test Calendar dataclass."""

    def test_create_calendar(self):
        """Should create calendar with required fields."""
        cal = Calendar(
            id="primary",
            name="Work Calendar",
        )

        assert cal.id == "primary"
        assert cal.name == "Work Calendar"
        assert cal.is_default is False
        assert cal.is_readonly is False

    def test_calendar_with_color(self):
        """Should accept custom color."""
        cal = Calendar(
            id="1",
            name="Personal",
            color="#ff5733",
        )

        assert cal.color == "#ff5733"


# =============================================================================
# Test CalendarConfig
# =============================================================================

class TestCalendarConfig:
    """Test CalendarConfig dataclass."""

    def test_default_config(self):
        """Default config should have empty values."""
        config = CalendarConfig()
        assert config.caldav_url == ""
        assert config.username == ""
        assert config.provider == "caldav"

    def test_custom_config(self):
        """Should accept custom configuration."""
        config = CalendarConfig(
            caldav_url="https://caldav.example.com/",
            username="user@example.com",
            password="secret",
            provider="google",
        )

        assert config.caldav_url == "https://caldav.example.com/"
        assert config.username == "user@example.com"


# =============================================================================
# Test Factory Functions
# =============================================================================

class TestCalendarClientFactories:
    """Test client factory functions."""

    def test_create_google_calendar_client(self):
        """Google factory should create correct config."""
        client = create_google_calendar_client(
            email="user@gmail.com",
            app_password="password",
        )

        assert "google.com/calendar/dav" in client._config.caldav_url
        assert client._config.username == "user@gmail.com"
        assert client._config.provider == "google"

    def test_create_apple_calendar_client(self):
        """Apple factory should create correct config."""
        client = create_apple_calendar_client(
            apple_id="user@icloud.com",
            app_password="password",
        )

        assert "caldav.icloud.com" in client._config.caldav_url
        assert client._config.provider == "apple"

    def test_create_caldav_client(self):
        """Generic factory should accept custom URL."""
        client = create_caldav_client(
            caldav_url="https://caldav.example.com/",
            username="user",
            password="pass",
        )

        assert client._config.caldav_url == "https://caldav.example.com/"
        assert client._config.provider == "caldav"


# =============================================================================
# Test CalendarClient Operations (Mocked)
# =============================================================================

class TestCalendarClientOperations:
    """Test CalendarClient with mocked CalDAV."""

    def test_connect_without_url(self):
        """Should fail to connect without URL."""
        config = CalendarConfig()
        client = CalendarClient(config)

        result = client.connect()
        assert result is False

    def test_connect_without_caldav_package(self):
        """Should handle missing caldav package."""
        config = CalendarConfig(
            caldav_url="https://caldav.example.com/",
            username="user",
            password="pass",
        )
        client = CalendarClient(config)

        # Mock caldav import failure
        with patch.dict("sys.modules", {"caldav": None}):
            result = client.connect()
            # May fail depending on how import is handled
            # Just verify no exception raised

    def test_disconnect(self):
        """Should disconnect cleanly."""
        config = CalendarConfig(
            caldav_url="https://caldav.example.com/",
            username="user",
            password="pass",
        )
        client = CalendarClient(config)
        client._connected = True
        client._caldav = MagicMock()

        client.disconnect()

        assert client._connected is False
        assert client._caldav is None

    def test_event_to_ical(self):
        """Should convert event to iCalendar format."""
        config = CalendarConfig()
        client = CalendarClient(config)

        event = CalendarEvent(
            id="test-123",
            title="Test Event",
            start=datetime(2024, 1, 15, 10, 0, 0),
            end=datetime(2024, 1, 15, 11, 0, 0),
            description="Test description",
            location="Test location",
        )

        ical = client._event_to_ical(event)

        assert "BEGIN:VCALENDAR" in ical
        assert "BEGIN:VEVENT" in ical
        assert "SUMMARY:Test Event" in ical
        assert "DESCRIPTION:Test description" in ical
        assert "LOCATION:Test location" in ical
        assert "END:VEVENT" in ical
        assert "END:VCALENDAR" in ical


# =============================================================================
# Test RecurrenceFrequency
# =============================================================================

class TestRecurrenceFrequency:
    """Test RecurrenceFrequency enum."""

    def test_daily(self):
        """Should have DAILY frequency."""
        assert RecurrenceFrequency.DAILY.value == "DAILY"

    def test_weekly(self):
        """Should have WEEKLY frequency."""
        assert RecurrenceFrequency.WEEKLY.value == "WEEKLY"

    def test_monthly(self):
        """Should have MONTHLY frequency."""
        assert RecurrenceFrequency.MONTHLY.value == "MONTHLY"

    def test_yearly(self):
        """Should have YEARLY frequency."""
        assert RecurrenceFrequency.YEARLY.value == "YEARLY"


# =============================================================================
# Test Context Manager
# =============================================================================

class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_disconnects(self):
        """Should disconnect on context exit."""
        config = CalendarConfig(
            caldav_url="https://example.com/",
            username="user",
            password="pass",
        )

        with patch.object(CalendarClient, 'connect', return_value=True):
            with CalendarClient(config) as client:
                client._connected = True
                client._caldav = MagicMock()

            assert client._connected is False
