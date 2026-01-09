"""
Conversation State Machine for Jarvis.

Tracks conversation state, goals, and multi-turn interactions.

Key concepts:
- State: Current conversation mode (greeting, task, clarification, etc.)
- Goal: What the user is trying to accomplish
- Transition: Movement between states based on user input

Research basis:
- Dialogue state tracking in task-oriented systems
- Goal-oriented conversation management
- Multi-turn context preservation
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.conversation.state")


class ConversationState(Enum):
    """States in the conversation state machine."""

    # Entry states
    IDLE = auto()  # No active conversation
    GREETING = auto()  # User just greeted

    # Active states
    LISTENING = auto()  # Waiting for user input
    PROCESSING = auto()  # Processing a request
    CLARIFYING = auto()  # Asking for clarification
    CONFIRMING = auto()  # Confirming an action

    # Task states
    TASK_ACTIVE = auto()  # Working on a multi-step task
    TASK_WAITING = auto()  # Waiting for task input
    TASK_COMPLETE = auto()  # Task finished

    # Special states
    ERROR_RECOVERY = auto()  # Recovering from an error
    GOODBYE = auto()  # Conversation ending


class GoalStatus(Enum):
    """Status of a conversation goal."""

    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"  # Waiting for something
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class ConversationGoal:
    """A goal the user is trying to accomplish."""

    id: str
    description: str
    status: GoalStatus = GoalStatus.PENDING
    priority: int = 5  # 1-10, higher = more important
    parent_goal_id: Optional[str] = None  # For sub-goals
    blocking_reason: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "parent_goal_id": self.parent_goal_id,
            "blocking_reason": self.blocking_reason,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


@dataclass
class StateTransition:
    """A transition between conversation states."""

    from_state: ConversationState
    to_state: ConversationState
    trigger: str  # What caused the transition
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationFlow:
    """
    Manages conversation state and flow.

    Tracks:
    - Current state
    - Active goals
    - Context slots (entities, values mentioned)
    - Transition history

    Usage:
        flow = ConversationFlow()
        flow.process_input("Hello!")
        print(flow.current_state)  # GREETING
        flow.add_goal("book_flight", "User wants to book a flight")
        flow.process_input("I want to fly to NYC")
        print(flow.get_active_goals())  # [ConversationGoal(...)]
    """

    # State transition rules
    TRANSITIONS = {
        ConversationState.IDLE: {
            "greeting": ConversationState.GREETING,
            "command": ConversationState.PROCESSING,
            "question": ConversationState.PROCESSING,
            "default": ConversationState.LISTENING,
        },
        ConversationState.GREETING: {
            "greeting": ConversationState.GREETING,
            "command": ConversationState.PROCESSING,
            "question": ConversationState.PROCESSING,
            "farewell": ConversationState.GOODBYE,
            "default": ConversationState.LISTENING,
        },
        ConversationState.LISTENING: {
            "command": ConversationState.PROCESSING,
            "question": ConversationState.PROCESSING,
            "clarification": ConversationState.CLARIFYING,
            "farewell": ConversationState.GOODBYE,
            "default": ConversationState.LISTENING,
        },
        ConversationState.PROCESSING: {
            "need_clarification": ConversationState.CLARIFYING,
            "need_confirmation": ConversationState.CONFIRMING,
            "task_started": ConversationState.TASK_ACTIVE,
            "complete": ConversationState.LISTENING,
            "error": ConversationState.ERROR_RECOVERY,
            "default": ConversationState.LISTENING,
        },
        ConversationState.CLARIFYING: {
            "clarified": ConversationState.PROCESSING,
            "abandon": ConversationState.LISTENING,
            "new_topic": ConversationState.PROCESSING,
            "default": ConversationState.CLARIFYING,
        },
        ConversationState.CONFIRMING: {
            "confirmed": ConversationState.PROCESSING,
            "rejected": ConversationState.LISTENING,
            "modified": ConversationState.PROCESSING,
            "default": ConversationState.CONFIRMING,
        },
        ConversationState.TASK_ACTIVE: {
            "task_step": ConversationState.TASK_ACTIVE,
            "task_waiting": ConversationState.TASK_WAITING,
            "task_complete": ConversationState.TASK_COMPLETE,
            "task_error": ConversationState.ERROR_RECOVERY,
            "default": ConversationState.TASK_ACTIVE,
        },
        ConversationState.TASK_WAITING: {
            "input_received": ConversationState.TASK_ACTIVE,
            "timeout": ConversationState.LISTENING,
            "cancel": ConversationState.LISTENING,
            "default": ConversationState.TASK_WAITING,
        },
        ConversationState.TASK_COMPLETE: {
            "acknowledged": ConversationState.LISTENING,
            "new_task": ConversationState.PROCESSING,
            "default": ConversationState.LISTENING,
        },
        ConversationState.ERROR_RECOVERY: {
            "resolved": ConversationState.LISTENING,
            "retry": ConversationState.PROCESSING,
            "escalate": ConversationState.LISTENING,
            "default": ConversationState.LISTENING,
        },
        ConversationState.GOODBYE: {
            "return": ConversationState.GREETING,
            "default": ConversationState.IDLE,
        },
    }

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or f"session_{datetime.now(timezone.utc).timestamp()}"
        self.current_state = ConversationState.IDLE
        self.goals: Dict[str, ConversationGoal] = {}
        self.context_slots: Dict[str, Any] = {}  # Named entity slots
        self.transition_history: List[StateTransition] = []
        self.turn_count = 0
        self._created_at = datetime.now(timezone.utc)

    def transition(self, trigger: str, metadata: Dict[str, Any] = None) -> ConversationState:
        """
        Transition to a new state based on trigger.

        Args:
            trigger: What caused the transition
            metadata: Additional context

        Returns:
            New state after transition
        """
        transitions = self.TRANSITIONS.get(self.current_state, {})
        new_state = transitions.get(trigger, transitions.get("default", self.current_state))

        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            trigger=trigger,
            metadata=metadata or {},
        )
        self.transition_history.append(transition)

        # Keep history bounded
        if len(self.transition_history) > 100:
            self.transition_history = self.transition_history[-100:]

        logger.debug(f"State transition: {self.current_state.name} -> {new_state.name} (trigger: {trigger})")
        self.current_state = new_state

        return new_state

    def process_input(self, user_input: str) -> Tuple[str, ConversationState]:
        """
        Process user input and update state.

        Returns:
            Tuple of (detected_intent, new_state)
        """
        self.turn_count += 1
        lowered = user_input.lower().strip()

        # Detect intent/trigger
        trigger = self._detect_trigger(lowered)

        # Extract entities
        entities = self._extract_entities(user_input)
        for key, value in entities.items():
            self.context_slots[key] = value

        # Transition state
        new_state = self.transition(trigger, {"input": user_input[:200], "entities": entities})

        return trigger, new_state

    def _detect_trigger(self, text: str) -> str:
        """Detect the trigger type from user input."""
        # Greeting patterns
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy"]
        if any(text.startswith(g) or text == g for g in greetings):
            return "greeting"

        # Farewell patterns
        farewells = ["bye", "goodbye", "see you", "later", "good night", "exit", "quit"]
        if any(f in text for f in farewells):
            return "farewell"

        # Confirmation patterns
        if text in ["yes", "yeah", "yep", "sure", "okay", "ok", "go ahead", "do it", "confirmed"]:
            return "confirmed"

        # Rejection patterns
        if text in ["no", "nope", "nah", "cancel", "stop", "nevermind", "never mind"]:
            return "rejected"

        # Question patterns
        if "?" in text or text.startswith(("what", "how", "why", "when", "where", "who", "which", "is", "are", "can", "could")):
            return "question"

        # Command patterns
        command_starters = ["open", "launch", "create", "make", "send", "set", "add", "remove", "delete", "run", "start", "stop"]
        if any(text.startswith(c) for c in command_starters):
            return "command"

        return "default"

    def _extract_entities(self, text: str) -> Dict[str, str]:
        """Extract named entities from text."""
        entities = {}

        # Time expressions
        time_patterns = [
            (r"at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", "time"),
            (r"(tomorrow|today|tonight)", "date"),
            (r"in (\d+)\s*(minutes?|hours?|days?)", "duration"),
        ]
        for pattern, key in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities[key] = match.group(1)

        # Names (capitalized words after certain prepositions)
        name_match = re.search(r"(?:to|from|with|for|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
        if name_match:
            entities["person"] = name_match.group(1)

        # URLs
        url_match = re.search(r"(https?://[^\s]+|www\.[^\s]+|[a-z0-9-]+\.[a-z]{2,})", text, re.IGNORECASE)
        if url_match:
            entities["url"] = url_match.group(1)

        # Numbers
        number_match = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
        if number_match:
            entities["number"] = number_match.group(1)

        return entities

    def add_goal(
        self,
        goal_id: str,
        description: str,
        priority: int = 5,
        parent_goal_id: str = None,
    ) -> ConversationGoal:
        """Add a new goal."""
        goal = ConversationGoal(
            id=goal_id,
            description=description,
            priority=priority,
            parent_goal_id=parent_goal_id,
            status=GoalStatus.ACTIVE,
        )
        self.goals[goal_id] = goal
        logger.info(f"Goal added: {goal_id} - {description}")
        return goal

    def complete_goal(self, goal_id: str) -> bool:
        """Mark a goal as completed."""
        if goal_id in self.goals:
            self.goals[goal_id].status = GoalStatus.COMPLETED
            self.goals[goal_id].completed_at = datetime.now(timezone.utc)
            logger.info(f"Goal completed: {goal_id}")
            return True
        return False

    def block_goal(self, goal_id: str, reason: str) -> bool:
        """Mark a goal as blocked."""
        if goal_id in self.goals:
            self.goals[goal_id].status = GoalStatus.BLOCKED
            self.goals[goal_id].blocking_reason = reason
            logger.info(f"Goal blocked: {goal_id} - {reason}")
            return True
        return False

    def abandon_goal(self, goal_id: str) -> bool:
        """Mark a goal as abandoned."""
        if goal_id in self.goals:
            self.goals[goal_id].status = GoalStatus.ABANDONED
            logger.info(f"Goal abandoned: {goal_id}")
            return True
        return False

    def get_active_goals(self) -> List[ConversationGoal]:
        """Get all active goals, sorted by priority."""
        active = [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
        return sorted(active, key=lambda g: -g.priority)

    def get_blocked_goals(self) -> List[ConversationGoal]:
        """Get all blocked goals."""
        return [g for g in self.goals.values() if g.status == GoalStatus.BLOCKED]

    def set_slot(self, key: str, value: Any) -> None:
        """Set a context slot value."""
        self.context_slots[key] = value

    def get_slot(self, key: str, default: Any = None) -> Any:
        """Get a context slot value."""
        return self.context_slots.get(key, default)

    def clear_slots(self) -> None:
        """Clear all context slots."""
        self.context_slots.clear()

    def get_state_info(self) -> Dict[str, Any]:
        """Get comprehensive state information."""
        return {
            "session_id": self.session_id,
            "current_state": self.current_state.name,
            "turn_count": self.turn_count,
            "active_goals": [g.to_dict() for g in self.get_active_goals()],
            "blocked_goals": [g.to_dict() for g in self.get_blocked_goals()],
            "context_slots": self.context_slots,
            "recent_transitions": [
                {
                    "from": t.from_state.name,
                    "to": t.to_state.name,
                    "trigger": t.trigger,
                }
                for t in self.transition_history[-5:]
            ],
        }

    def format_for_prompt(self) -> str:
        """Format state for injection into prompt."""
        lines = []

        # Current state
        lines.append(f"Conversation state: {self.current_state.name}")

        # Active goals
        active_goals = self.get_active_goals()
        if active_goals:
            goals_str = ", ".join(g.description[:50] for g in active_goals[:3])
            lines.append(f"Active goals: {goals_str}")

        # Blocked goals
        blocked = self.get_blocked_goals()
        if blocked:
            blocked_str = "; ".join(f"{g.description[:30]} (blocked: {g.blocking_reason})" for g in blocked[:2])
            lines.append(f"Blocked: {blocked_str}")

        # Context slots
        if self.context_slots:
            slots_str = ", ".join(f"{k}={v}" for k, v in list(self.context_slots.items())[:5])
            lines.append(f"Context: {slots_str}")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset conversation state to initial."""
        self.current_state = ConversationState.IDLE
        self.goals.clear()
        self.context_slots.clear()
        self.transition_history.clear()
        self.turn_count = 0


# Session management
_active_flows: Dict[str, ConversationFlow] = {}


def get_or_create_flow(session_id: str) -> ConversationFlow:
    """Get existing flow or create new one."""
    if session_id not in _active_flows:
        _active_flows[session_id] = ConversationFlow(session_id)
    return _active_flows[session_id]


def cleanup_old_flows(max_age_hours: int = 24) -> int:
    """Clean up old conversation flows."""
    now = datetime.now(timezone.utc)
    to_remove = []

    for session_id, flow in _active_flows.items():
        age = (now - flow._created_at).total_seconds() / 3600
        if age > max_age_hours:
            to_remove.append(session_id)

    for session_id in to_remove:
        del _active_flows[session_id]

    return len(to_remove)
