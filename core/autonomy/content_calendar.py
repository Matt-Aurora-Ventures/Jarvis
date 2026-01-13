"""
Content Calendar
Event awareness and optimal posting timing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "calendar"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CryptoEvent:
    """A crypto event to be aware of"""
    name: str
    event_type: str  # unlock, upgrade, launch, conference, earnings
    date: str  # ISO format
    tokens: List[str] = field(default_factory=list)
    importance: str = "medium"  # low, medium, high
    description: str = ""
    content_generated: bool = False


@dataclass
class ScheduledContent:
    """Content scheduled for posting"""
    content_type: str
    scheduled_for: str  # ISO format
    topic: str = ""
    prompt: str = ""
    generated_content: str = ""
    posted: bool = False
    tweet_id: str = ""


class ContentCalendar:
    """
    Manage content calendar and posting schedule.
    Aware of crypto events, optimal times.
    """
    
    # Optimal posting hours (UTC)
    OPTIMAL_HOURS = [14, 15, 16, 17, 18, 19, 20, 21]  # 2PM-9PM UTC (morning-afternoon US)
    
    # Content type weights by time of day
    CONTENT_BY_HOUR = {
        "morning": ["market_update", "daily_outlook"],  # 12-16 UTC
        "afternoon": ["engagement", "alpha", "trending"],  # 16-20 UTC
        "evening": ["reflection", "agentic", "grok_chat"],  # 20-24 UTC
        "night": ["sentiment", "overnight"],  # 0-12 UTC
    }
    
    def __init__(self):
        self.events_file = DATA_DIR / "events.json"
        self.schedule_file = DATA_DIR / "schedule.json"
        
        self.events: List[CryptoEvent] = []
        self.scheduled: List[ScheduledContent] = []
        
        self._load_data()
        self._init_default_events()
    
    def _load_data(self):
        """Load calendar data"""
        try:
            if self.events_file.exists():
                data = json.loads(self.events_file.read_text())
                self.events = [CryptoEvent(**e) for e in data]
            
            if self.schedule_file.exists():
                data = json.loads(self.schedule_file.read_text())
                self.scheduled = [ScheduledContent(**s) for s in data]
        except Exception as e:
            logger.error(f"Error loading calendar: {e}")
    
    def _save_data(self):
        """Save calendar data"""
        try:
            self.events_file.write_text(json.dumps(
                [asdict(e) for e in self.events],
                indent=2
            ))
            self.schedule_file.write_text(json.dumps(
                [asdict(s) for s in self.scheduled[-100:]],  # Keep last 100
                indent=2
            ))
        except Exception as e:
            logger.error(f"Error saving calendar: {e}")
    
    def _init_default_events(self):
        """Initialize with known recurring events"""
        # Only add if empty
        if self.events:
            return
        
        # Add some known patterns
        default_events = [
            CryptoEvent(
                name="Weekly Options Expiry",
                event_type="options",
                date="recurring:friday",
                importance="medium",
                description="BTC/ETH options expire, expect volatility"
            ),
            CryptoEvent(
                name="Monthly Close",
                event_type="market",
                date="recurring:last_day",
                importance="high",
                description="Monthly candle close, significant for technicals"
            ),
        ]
        self.events.extend(default_events)
        self._save_data()
    
    def add_event(
        self,
        name: str,
        event_type: str,
        date: str,
        tokens: List[str] = None,
        importance: str = "medium",
        description: str = ""
    ):
        """Add a crypto event"""
        event = CryptoEvent(
            name=name,
            event_type=event_type,
            date=date,
            tokens=tokens or [],
            importance=importance,
            description=description
        )
        self.events.append(event)
        self._save_data()
        logger.info(f"Added event: {name}")
    
    def get_upcoming_events(self, days: int = 7) -> List[CryptoEvent]:
        """Get events in the next N days"""
        now = datetime.utcnow()
        cutoff = now + timedelta(days=days)
        
        upcoming = []
        for event in self.events:
            if event.date.startswith("recurring:"):
                # Handle recurring events
                upcoming.append(event)
            else:
                try:
                    event_date = datetime.fromisoformat(event.date)
                    if now <= event_date <= cutoff:
                        upcoming.append(event)
                except Exception:
                    pass
        
        return upcoming
    
    def get_todays_events(self) -> List[CryptoEvent]:
        """Get events happening today"""
        today = datetime.utcnow().date()
        todays = []
        
        for event in self.events:
            if event.date.startswith("recurring:"):
                pattern = event.date.split(":")[1]
                if pattern == "friday" and today.weekday() == 4:
                    todays.append(event)
                elif pattern == "last_day" and (today + timedelta(days=1)).month != today.month:
                    todays.append(event)
            else:
                try:
                    event_date = datetime.fromisoformat(event.date).date()
                    if event_date == today:
                        todays.append(event)
                except Exception:
                    pass
        
        return todays
    
    def get_time_period(self, hour: int = None) -> str:
        """Get current time period"""
        if hour is None:
            hour = datetime.utcnow().hour
        
        if 12 <= hour < 16:
            return "morning"
        elif 16 <= hour < 20:
            return "afternoon"
        elif 20 <= hour < 24:
            return "evening"
        else:
            return "night"
    
    def get_recommended_content_types(self) -> List[str]:
        """Get recommended content types for current time"""
        period = self.get_time_period()
        return self.CONTENT_BY_HOUR.get(period, ["market_update"])
    
    def is_optimal_time(self) -> bool:
        """Check if now is an optimal posting time"""
        return datetime.utcnow().hour in self.OPTIMAL_HOURS
    
    def get_next_optimal_time(self) -> datetime:
        """Get the next optimal posting time"""
        now = datetime.utcnow()
        current_hour = now.hour
        
        # Find next optimal hour
        for h in self.OPTIMAL_HOURS:
            if h > current_hour:
                return now.replace(hour=h, minute=0, second=0, microsecond=0)
        
        # Next day
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=self.OPTIMAL_HOURS[0], minute=0, second=0, microsecond=0)
    
    def schedule_content(
        self,
        content_type: str,
        scheduled_for: datetime,
        topic: str = "",
        prompt: str = ""
    ):
        """Schedule content for posting"""
        scheduled = ScheduledContent(
            content_type=content_type,
            scheduled_for=scheduled_for.isoformat(),
            topic=topic,
            prompt=prompt
        )
        self.scheduled.append(scheduled)
        self._save_data()
    
    def get_due_content(self) -> List[ScheduledContent]:
        """Get content that's due for posting"""
        now = datetime.utcnow()
        due = []
        
        for content in self.scheduled:
            if content.posted:
                continue
            try:
                scheduled_time = datetime.fromisoformat(content.scheduled_for)
                if scheduled_time <= now:
                    due.append(content)
            except Exception:
                pass
        
        return due
    
    def mark_content_posted(self, content: ScheduledContent, tweet_id: str):
        """Mark scheduled content as posted"""
        content.posted = True
        content.tweet_id = tweet_id
        self._save_data()
    
    def get_content_suggestions(self) -> List[Dict[str, Any]]:
        """Get content suggestions based on calendar"""
        suggestions = []
        
        # Check today's events
        for event in self.get_todays_events():
            if not event.content_generated:
                suggestions.append({
                    "type": "event_commentary",
                    "event": event.name,
                    "tokens": event.tokens,
                    "importance": event.importance,
                    "prompt": f"Comment on {event.name}: {event.description}"
                })
        
        # Check upcoming events
        for event in self.get_upcoming_events(3):
            if event.importance == "high" and not event.content_generated:
                suggestions.append({
                    "type": "event_preview",
                    "event": event.name,
                    "date": event.date,
                    "prompt": f"Preview upcoming event: {event.name}"
                })
        
        # Add time-appropriate content
        for content_type in self.get_recommended_content_types():
            suggestions.append({
                "type": content_type,
                "reason": f"Good for {self.get_time_period()} posting"
            })
        
        return suggestions[:5]


# Singleton
_calendar: Optional[ContentCalendar] = None

def get_content_calendar() -> ContentCalendar:
    global _calendar
    if _calendar is None:
        _calendar = ContentCalendar()
    return _calendar
