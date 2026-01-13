"""
JARVIS Proactive Suggestion System

Monitors context and proactively offers helpful suggestions:
- Time-based triggers (morning briefing, market hours)
- Event-based triggers (price alerts, news)
- Pattern-based triggers (detected habits)
- Context-based triggers (current activity)

Dependencies: None (uses standard library)
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import hashlib

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "proactive"


class TriggerType(Enum):
    """Types of suggestion triggers."""
    TIME = "time"           # Time-based (morning, evening, market hours)
    EVENT = "event"         # Event-based (price alert, news)
    PATTERN = "pattern"     # Pattern detection (user habits)
    CONTEXT = "context"     # Current context (activity, location)
    SCHEDULE = "schedule"   # Scheduled recurring
    THRESHOLD = "threshold" # Value threshold crossed


class SuggestionCategory(Enum):
    """Categories of suggestions."""
    BRIEFING = "briefing"       # Information summaries
    ALERT = "alert"             # Important notifications
    ACTION = "action"           # Suggested actions
    RESEARCH = "research"       # Research opportunities
    AUTOMATION = "automation"   # Automation suggestions
    REMINDER = "reminder"       # Reminders
    INSIGHT = "insight"         # AI-generated insights


class Priority(Enum):
    """Suggestion priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Suggestion:
    """A proactive suggestion."""
    id: str
    category: SuggestionCategory
    priority: Priority
    title: str
    content: str
    trigger_type: TriggerType
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acted_upon: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "content": self.content,
            "trigger_type": self.trigger_type.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "actions": self.actions,
            "metadata": self.metadata,
            "acknowledged": self.acknowledged,
            "acted_upon": self.acted_upon,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Suggestion':
        return cls(
            id=data["id"],
            category=SuggestionCategory(data["category"]),
            priority=Priority(data["priority"]),
            title=data["title"],
            content=data["content"],
            trigger_type=TriggerType(data["trigger_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            actions=data.get("actions", []),
            metadata=data.get("metadata", {}),
            acknowledged=data.get("acknowledged", False),
            acted_upon=data.get("acted_upon", False),
        )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class SuggestionTrigger(ABC):
    """Base class for suggestion triggers."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.last_triggered: Optional[datetime] = None
        self.cooldown: timedelta = timedelta(minutes=30)

    @abstractmethod
    async def check(self, context: Dict[str, Any]) -> Optional[Suggestion]:
        """Check if trigger condition is met."""
        pass

    def can_trigger(self) -> bool:
        """Check if trigger is off cooldown."""
        if not self.enabled:
            return False
        if self.last_triggered is None:
            return True
        return datetime.now() - self.last_triggered > self.cooldown

    def mark_triggered(self):
        """Mark trigger as fired."""
        self.last_triggered = datetime.now()


class TimeBasedTrigger(SuggestionTrigger):
    """Trigger based on time of day."""

    def __init__(
        self,
        name: str,
        trigger_times: List[time],
        suggestion_factory: Callable[[], Suggestion],
        days: Optional[List[int]] = None,  # 0=Monday, 6=Sunday
    ):
        super().__init__(name)
        self.trigger_times = trigger_times
        self.suggestion_factory = suggestion_factory
        self.days = days  # None = all days
        self.cooldown = timedelta(hours=12)  # Don't repeat same day

    async def check(self, context: Dict[str, Any]) -> Optional[Suggestion]:
        if not self.can_trigger():
            return None

        now = datetime.now()

        # Check day of week
        if self.days is not None and now.weekday() not in self.days:
            return None

        # Check if within 5 minutes of a trigger time
        current_time = now.time()
        for trigger_time in self.trigger_times:
            trigger_dt = datetime.combine(now.date(), trigger_time)
            diff = abs((now - trigger_dt).total_seconds())
            if diff < 300:  # Within 5 minutes
                self.mark_triggered()
                return self.suggestion_factory()

        return None


class ThresholdTrigger(SuggestionTrigger):
    """Trigger when a value crosses a threshold."""

    def __init__(
        self,
        name: str,
        value_key: str,
        threshold: float,
        direction: str = "above",  # "above" or "below"
        suggestion_factory: Callable[[float], Suggestion] = None,
    ):
        super().__init__(name)
        self.value_key = value_key
        self.threshold = threshold
        self.direction = direction
        self.suggestion_factory = suggestion_factory
        self.cooldown = timedelta(hours=1)
        self._last_value: Optional[float] = None

    async def check(self, context: Dict[str, Any]) -> Optional[Suggestion]:
        if not self.can_trigger():
            return None

        value = context.get(self.value_key)
        if value is None:
            return None

        crossed = False
        if self.direction == "above":
            if self._last_value is not None:
                crossed = self._last_value <= self.threshold < value
        else:  # below
            if self._last_value is not None:
                crossed = self._last_value >= self.threshold > value

        self._last_value = value

        if crossed and self.suggestion_factory:
            self.mark_triggered()
            return self.suggestion_factory(value)

        return None


class PatternTrigger(SuggestionTrigger):
    """Trigger based on detected patterns."""

    def __init__(
        self,
        name: str,
        pattern_type: str,
        suggestion_factory: Callable[[Dict], Suggestion],
    ):
        super().__init__(name)
        self.pattern_type = pattern_type
        self.suggestion_factory = suggestion_factory
        self.cooldown = timedelta(hours=4)

    async def check(self, context: Dict[str, Any]) -> Optional[Suggestion]:
        if not self.can_trigger():
            return None

        patterns = context.get("detected_patterns", [])
        for pattern in patterns:
            if pattern.get("type") == self.pattern_type:
                self.mark_triggered()
                return self.suggestion_factory(pattern)

        return None


class ProactiveSuggestionEngine:
    """
    Main engine for proactive suggestions.

    Features:
    - Multiple trigger types
    - Priority queue
    - Persistence
    - Learning from feedback
    - Debouncing
    """

    def __init__(self):
        self.triggers: List[SuggestionTrigger] = []
        self.pending_suggestions: List[Suggestion] = []
        self.suggestion_history: List[Suggestion] = []
        self._running = False
        self._callbacks: List[Callable[[Suggestion], None]] = []
        self._context: Dict[str, Any] = {}

        # Feedback tracking
        self._feedback_file = DATA_DIR / "feedback.json"
        self._feedback: Dict[str, Dict] = {}

        self._load_state()
        self._setup_default_triggers()

    def _load_state(self):
        """Load persisted state."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load feedback
        if self._feedback_file.exists():
            try:
                with open(self._feedback_file) as f:
                    self._feedback = json.load(f)
            except Exception:
                self._feedback = {}

    def _save_state(self):
        """Persist state."""
        with open(self._feedback_file, 'w') as f:
            json.dump(self._feedback, f, indent=2)

    def _setup_default_triggers(self):
        """Set up default suggestion triggers."""

        # Morning briefing (8 AM weekdays)
        def morning_briefing():
            return Suggestion(
                id=f"morning_{datetime.now().strftime('%Y%m%d')}",
                category=SuggestionCategory.BRIEFING,
                priority=Priority.MEDIUM,
                title="Good morning! Here's your daily briefing",
                content="Ready to provide your morning market update and task summary.",
                trigger_type=TriggerType.TIME,
                expires_at=datetime.now() + timedelta(hours=4),
                actions=[
                    {"type": "command", "label": "Show Briefing", "command": "/briefing"},
                    {"type": "dismiss", "label": "Dismiss"},
                ],
            )

        self.add_trigger(TimeBasedTrigger(
            name="morning_briefing",
            trigger_times=[time(8, 0)],
            suggestion_factory=morning_briefing,
            days=[0, 1, 2, 3, 4],  # Weekdays
        ))

        # Market open alert (9:30 AM ET on weekdays)
        def market_open():
            return Suggestion(
                id=f"market_open_{datetime.now().strftime('%Y%m%d')}",
                category=SuggestionCategory.ALERT,
                priority=Priority.HIGH,
                title="US Markets Opening",
                content="US stock markets are opening. Check your watchlist?",
                trigger_type=TriggerType.TIME,
                expires_at=datetime.now() + timedelta(hours=1),
                actions=[
                    {"type": "command", "label": "Check Watchlist", "command": "/watchlist"},
                ],
            )

        self.add_trigger(TimeBasedTrigger(
            name="market_open",
            trigger_times=[time(9, 30)],
            suggestion_factory=market_open,
            days=[0, 1, 2, 3, 4],
        ))

        # Evening summary (6 PM)
        def evening_summary():
            return Suggestion(
                id=f"evening_{datetime.now().strftime('%Y%m%d')}",
                category=SuggestionCategory.BRIEFING,
                priority=Priority.LOW,
                title="Daily Summary Available",
                content="Ready to provide your end-of-day summary.",
                trigger_type=TriggerType.TIME,
                expires_at=datetime.now() + timedelta(hours=4),
                actions=[
                    {"type": "command", "label": "Show Summary", "command": "/summary"},
                ],
            )

        self.add_trigger(TimeBasedTrigger(
            name="evening_summary",
            trigger_times=[time(18, 0)],
            suggestion_factory=evening_summary,
        ))

    def add_trigger(self, trigger: SuggestionTrigger):
        """Add a suggestion trigger."""
        self.triggers.append(trigger)

    def remove_trigger(self, name: str):
        """Remove a trigger by name."""
        self.triggers = [t for t in self.triggers if t.name != name]

    def on_suggestion(self, callback: Callable[[Suggestion], None]):
        """Register callback for new suggestions."""
        self._callbacks.append(callback)

    def update_context(self, key: str, value: Any):
        """Update context used by triggers."""
        self._context[key] = value

    def set_context(self, context: Dict[str, Any]):
        """Set full context."""
        self._context = context

    async def check_triggers(self) -> List[Suggestion]:
        """Check all triggers and return new suggestions."""
        new_suggestions = []

        for trigger in self.triggers:
            try:
                suggestion = await trigger.check(self._context)
                if suggestion and not self._is_duplicate(suggestion):
                    new_suggestions.append(suggestion)
                    self.pending_suggestions.append(suggestion)
                    self._notify(suggestion)
            except Exception as e:
                logger.error(f"Trigger {trigger.name} failed: {e}")

        return new_suggestions

    def _is_duplicate(self, suggestion: Suggestion) -> bool:
        """Check if suggestion is a duplicate."""
        for existing in self.pending_suggestions:
            if existing.id == suggestion.id:
                return True
        return False

    def _notify(self, suggestion: Suggestion):
        """Notify callbacks of new suggestion."""
        for callback in self._callbacks:
            try:
                callback(suggestion)
            except Exception as e:
                logger.error(f"Suggestion callback failed: {e}")

    def get_pending(self, category: Optional[SuggestionCategory] = None) -> List[Suggestion]:
        """Get pending suggestions, optionally filtered by category."""
        # Remove expired
        self.pending_suggestions = [s for s in self.pending_suggestions if not s.is_expired()]

        if category:
            return [s for s in self.pending_suggestions if s.category == category]
        return sorted(self.pending_suggestions, key=lambda s: s.priority.value, reverse=True)

    def acknowledge(self, suggestion_id: str, acted_upon: bool = False):
        """Mark suggestion as acknowledged."""
        for suggestion in self.pending_suggestions:
            if suggestion.id == suggestion_id:
                suggestion.acknowledged = True
                suggestion.acted_upon = acted_upon
                self.suggestion_history.append(suggestion)
                self.pending_suggestions.remove(suggestion)

                # Track feedback
                self._record_feedback(suggestion, acted_upon)
                break

    def dismiss(self, suggestion_id: str):
        """Dismiss a suggestion without acting."""
        self.acknowledge(suggestion_id, acted_upon=False)

    def _record_feedback(self, suggestion: Suggestion, acted_upon: bool):
        """Record feedback for learning."""
        trigger_key = suggestion.metadata.get("trigger_name", "unknown")

        if trigger_key not in self._feedback:
            self._feedback[trigger_key] = {
                "total": 0,
                "acted": 0,
                "dismissed": 0,
            }

        self._feedback[trigger_key]["total"] += 1
        if acted_upon:
            self._feedback[trigger_key]["acted"] += 1
        else:
            self._feedback[trigger_key]["dismissed"] += 1

        self._save_state()

    def get_trigger_effectiveness(self, trigger_name: str) -> float:
        """Get effectiveness ratio for a trigger."""
        if trigger_name not in self._feedback:
            return 0.5  # Default

        stats = self._feedback[trigger_name]
        if stats["total"] == 0:
            return 0.5

        return stats["acted"] / stats["total"]

    async def start(self, check_interval: int = 60):
        """Start the suggestion engine loop."""
        self._running = True
        logger.info("Proactive suggestion engine started")

        while self._running:
            try:
                await self.check_triggers()
            except Exception as e:
                logger.error(f"Suggestion engine error: {e}")

            await asyncio.sleep(check_interval)

    def stop(self):
        """Stop the suggestion engine."""
        self._running = False
        self._save_state()

    # Convenience methods for adding common triggers

    def add_price_alert(
        self,
        asset: str,
        threshold: float,
        direction: str = "above",
    ):
        """Add a price threshold alert."""
        def make_suggestion(current_price: float) -> Suggestion:
            return Suggestion(
                id=f"price_{asset}_{direction}_{threshold}_{datetime.now().timestamp()}",
                category=SuggestionCategory.ALERT,
                priority=Priority.HIGH,
                title=f"{asset} Price Alert",
                content=f"{asset} has {'risen above' if direction == 'above' else 'dropped below'} ${threshold:.2f} (Current: ${current_price:.2f})",
                trigger_type=TriggerType.THRESHOLD,
                expires_at=datetime.now() + timedelta(hours=1),
                actions=[
                    {"type": "command", "label": "View Chart", "command": f"/chart {asset}"},
                    {"type": "command", "label": "Trade", "command": f"/trade {asset}"},
                ],
                metadata={"asset": asset, "threshold": threshold, "direction": direction},
            )

        self.add_trigger(ThresholdTrigger(
            name=f"price_{asset}_{direction}_{threshold}",
            value_key=f"price_{asset}",
            threshold=threshold,
            direction=direction,
            suggestion_factory=make_suggestion,
        ))

    def add_scheduled_reminder(
        self,
        name: str,
        message: str,
        times: List[time],
        days: Optional[List[int]] = None,
    ):
        """Add a scheduled reminder."""
        def make_reminder() -> Suggestion:
            return Suggestion(
                id=f"reminder_{name}_{datetime.now().strftime('%Y%m%d%H%M')}",
                category=SuggestionCategory.REMINDER,
                priority=Priority.MEDIUM,
                title=name,
                content=message,
                trigger_type=TriggerType.SCHEDULE,
                expires_at=datetime.now() + timedelta(hours=2),
                metadata={"reminder_name": name},
            )

        self.add_trigger(TimeBasedTrigger(
            name=f"reminder_{name}",
            trigger_times=times,
            suggestion_factory=make_reminder,
            days=days,
        ))


# Singleton instance
_engine: Optional[ProactiveSuggestionEngine] = None


def get_suggestion_engine() -> ProactiveSuggestionEngine:
    """Get singleton suggestion engine."""
    global _engine
    if _engine is None:
        _engine = ProactiveSuggestionEngine()
    return _engine


async def start_suggestion_engine():
    """Start the suggestion engine in background."""
    engine = get_suggestion_engine()
    await engine.start()


# Helper for quick suggestions
def suggest(
    title: str,
    content: str,
    category: SuggestionCategory = SuggestionCategory.INSIGHT,
    priority: Priority = Priority.MEDIUM,
    actions: List[Dict] = None,
) -> Suggestion:
    """Create and queue a suggestion."""
    suggestion = Suggestion(
        id=hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:12],
        category=category,
        priority=priority,
        title=title,
        content=content,
        trigger_type=TriggerType.EVENT,
        actions=actions or [],
    )
    engine = get_suggestion_engine()
    engine.pending_suggestions.append(suggestion)
    engine._notify(suggestion)
    return suggestion
