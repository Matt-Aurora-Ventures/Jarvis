"""
Calendar Integration Client

Provides a unified interface for calendar operations:
- CalDAV (generic, works with most providers)
- Google Calendar (via CalDAV)
- Apple Calendar (via CalDAV)
- Microsoft 365 (future)

Features:
- List calendars
- Create/read/update/delete events
- Search events by date range
- Recurring events support
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RecurrenceFrequency(Enum):
    """Event recurrence frequency."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: str
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    is_all_day: bool = False
    calendar_id: str = ""
    attendees: List[str] = field(default_factory=list)
    reminders: List[int] = field(default_factory=list)  # Minutes before event
    recurrence: Optional[RecurrenceFrequency] = None
    recurrence_until: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> timedelta:
        """Get event duration."""
        return self.end - self.start

    @property
    def is_past(self) -> bool:
        """Check if event is in the past."""
        return self.end < datetime.now()

    @property
    def is_upcoming(self) -> bool:
        """Check if event starts within 24 hours."""
        now = datetime.now()
        return now <= self.start <= now + timedelta(hours=24)


@dataclass
class Calendar:
    """Represents a calendar."""
    id: str
    name: str
    color: str = "#3788d8"
    is_default: bool = False
    is_readonly: bool = False
    owner: str = ""


@dataclass
class CalendarConfig:
    """Calendar client configuration."""
    caldav_url: str = ""
    username: str = ""
    password: str = ""
    provider: str = "caldav"  # caldav, google, apple


class CalendarClient:
    """
    Unified calendar client supporting CalDAV.

    For Google Calendar: Use CalDAV URL format
    https://www.googleapis.com/caldav/v2/calendars/{calendar_id}/events

    For Apple Calendar (iCloud):
    https://caldav.icloud.com/{user_id}/calendars/

    For generic CalDAV:
    Use your provider's CalDAV endpoint
    """

    def __init__(self, config: CalendarConfig):
        self._config = config
        self._connected = False
        self._calendars: Dict[str, Calendar] = {}
        self._caldav = None

    def connect(self) -> bool:
        """Connect to CalDAV server."""
        if not self._config.caldav_url:
            logger.warning("CalDAV URL not configured")
            return False

        try:
            import caldav
            self._caldav = caldav.DAVClient(
                url=self._config.caldav_url,
                username=self._config.username,
                password=self._config.password,
            )
            # Test connection
            principal = self._caldav.principal()
            self._connected = True
            logger.info(f"Connected to CalDAV at {self._config.caldav_url}")
            return True

        except ImportError:
            logger.warning("caldav package not installed (pip install caldav)")
            return False
        except Exception as e:
            logger.error(f"CalDAV connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from server."""
        self._caldav = None
        self._connected = False
        self._calendars.clear()

    def list_calendars(self) -> List[Calendar]:
        """List all calendars."""
        if not self._ensure_connected():
            return []

        try:
            principal = self._caldav.principal()
            calendars = principal.calendars()

            result = []
            for cal in calendars:
                calendar = Calendar(
                    id=str(cal.url),
                    name=cal.name or "Untitled",
                    is_default=False,
                )
                self._calendars[calendar.id] = calendar
                result.append(calendar)

            return result

        except Exception as e:
            logger.error(f"Failed to list calendars: {e}")
            return []

    def get_events(
        self,
        calendar_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[CalendarEvent]:
        """
        Get events from a calendar.

        Args:
            calendar_id: Calendar ID
            start: Start of date range (default: now)
            end: End of date range (default: 30 days from now)
            limit: Maximum number of events

        Returns:
            List of calendar events
        """
        if not self._ensure_connected():
            return []

        start = start or datetime.now()
        end = end or start + timedelta(days=30)

        try:
            principal = self._caldav.principal()
            calendars = principal.calendars()

            # Find the calendar
            calendar = None
            for cal in calendars:
                if str(cal.url) == calendar_id or cal.name == calendar_id:
                    calendar = cal
                    break

            if not calendar:
                logger.warning(f"Calendar not found: {calendar_id}")
                return []

            # Search for events
            events = calendar.date_search(
                start=start,
                end=end,
                expand=True,
            )

            result = []
            for event in events[:limit]:
                parsed = self._parse_event(event, calendar_id)
                if parsed:
                    result.append(parsed)

            # Sort by start time
            result.sort(key=lambda e: e.start)
            return result

        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def get_upcoming_events(
        self,
        days: int = 7,
        calendar_id: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """
        Get upcoming events across all calendars or a specific one.

        Args:
            days: Number of days ahead to look
            calendar_id: Optional specific calendar

        Returns:
            List of upcoming events, sorted by start time
        """
        start = datetime.now()
        end = start + timedelta(days=days)

        if calendar_id:
            return self.get_events(calendar_id, start, end)

        # Get from all calendars
        calendars = self.list_calendars()
        all_events = []

        for cal in calendars:
            events = self.get_events(cal.id, start, end)
            all_events.extend(events)

        # Sort by start time
        all_events.sort(key=lambda e: e.start)
        return all_events

    def create_event(
        self,
        calendar_id: str,
        event: CalendarEvent,
    ) -> Optional[str]:
        """
        Create a new event.

        Args:
            calendar_id: Calendar ID
            event: Event to create

        Returns:
            Event ID if successful, None otherwise
        """
        if not self._ensure_connected():
            return None

        try:
            principal = self._caldav.principal()
            calendars = principal.calendars()

            # Find the calendar
            calendar = None
            for cal in calendars:
                if str(cal.url) == calendar_id or cal.name == calendar_id:
                    calendar = cal
                    break

            if not calendar:
                logger.warning(f"Calendar not found: {calendar_id}")
                return None

            # Build iCalendar data
            ical_data = self._event_to_ical(event)

            # Create event
            new_event = calendar.add_event(ical_data)
            event_id = str(new_event.url) if new_event else None

            logger.info(f"Created event: {event.title}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None

    def update_event(
        self,
        calendar_id: str,
        event: CalendarEvent,
    ) -> bool:
        """
        Update an existing event.

        Args:
            calendar_id: Calendar ID
            event: Event with updated data (must have id)

        Returns:
            True if successful
        """
        if not self._ensure_connected():
            return False

        if not event.id:
            logger.error("Event ID required for update")
            return False

        try:
            # Delete and recreate (simplest approach)
            self.delete_event(calendar_id, event.id)
            new_id = self.create_event(calendar_id, event)
            return new_id is not None

        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return False

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """
        Delete an event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID

        Returns:
            True if successful
        """
        if not self._ensure_connected():
            return False

        try:
            principal = self._caldav.principal()
            calendars = principal.calendars()

            # Find the calendar
            calendar = None
            for cal in calendars:
                if str(cal.url) == calendar_id or cal.name == calendar_id:
                    calendar = cal
                    break

            if not calendar:
                return False

            # Find and delete the event
            events = calendar.events()
            for event in events:
                if str(event.url) == event_id:
                    event.delete()
                    logger.info(f"Deleted event: {event_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    def _parse_event(
        self,
        caldav_event: Any,
        calendar_id: str,
    ) -> Optional[CalendarEvent]:
        """Parse a CalDAV event to CalendarEvent."""
        try:
            import icalendar

            ical = icalendar.Calendar.from_ical(caldav_event.data)

            for component in ical.walk():
                if component.name == "VEVENT":
                    # Get start/end
                    dtstart = component.get("dtstart")
                    dtend = component.get("dtend")

                    if not dtstart:
                        continue

                    start = dtstart.dt
                    if dtend:
                        end = dtend.dt
                    else:
                        end = start + timedelta(hours=1)

                    # Handle all-day events (date vs datetime)
                    is_all_day = not hasattr(start, "hour")
                    if is_all_day:
                        start = datetime.combine(start, datetime.min.time())
                        end = datetime.combine(end, datetime.min.time())

                    return CalendarEvent(
                        id=str(caldav_event.url),
                        title=str(component.get("summary", "Untitled")),
                        start=start,
                        end=end,
                        description=str(component.get("description", "")),
                        location=str(component.get("location", "")),
                        is_all_day=is_all_day,
                        calendar_id=calendar_id,
                    )

            return None

        except ImportError:
            logger.warning("icalendar package not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None

    def _event_to_ical(self, event: CalendarEvent) -> str:
        """Convert CalendarEvent to iCalendar format."""
        import uuid

        uid = event.id or str(uuid.uuid4())
        dtformat = "%Y%m%dT%H%M%SZ" if not event.is_all_day else "%Y%m%d"

        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Jarvis//Calendar//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime(dtformat)}
DTSTART:{event.start.strftime(dtformat)}
DTEND:{event.end.strftime(dtformat)}
SUMMARY:{event.title}
DESCRIPTION:{event.description}
LOCATION:{event.location}
END:VEVENT
END:VCALENDAR"""

        return ical

    def _ensure_connected(self) -> bool:
        """Ensure connection is active."""
        if not self._connected or not self._caldav:
            return self.connect()
        return True

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


# Factory functions

def create_google_calendar_client(
    email: str,
    app_password: str,
) -> CalendarClient:
    """
    Create a Google Calendar client via CalDAV.

    Requires an App Password for authentication.
    """
    config = CalendarConfig(
        caldav_url=f"https://www.google.com/calendar/dav/{email}/events/",
        username=email,
        password=app_password,
        provider="google",
    )
    return CalendarClient(config)


def create_apple_calendar_client(
    apple_id: str,
    app_password: str,
) -> CalendarClient:
    """
    Create an Apple Calendar client via CalDAV.

    Requires an App-Specific Password from appleid.apple.com
    """
    config = CalendarConfig(
        caldav_url="https://caldav.icloud.com/",
        username=apple_id,
        password=app_password,
        provider="apple",
    )
    return CalendarClient(config)


def create_caldav_client(
    caldav_url: str,
    username: str,
    password: str,
) -> CalendarClient:
    """Create a generic CalDAV client."""
    config = CalendarConfig(
        caldav_url=caldav_url,
        username=username,
        password=password,
        provider="caldav",
    )
    return CalendarClient(config)
