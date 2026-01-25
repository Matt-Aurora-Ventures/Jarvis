"""
Telegram Bot Conversation State Machine.

Manages conversation state, transitions, context storage, and persistence
for the Telegram bot interface.

Key Features:
- State transitions with guards
- Context storage per user/chat
- Timeout handling with auto-reset
- Database persistence for state recovery
- Enter/exit callbacks for state lifecycle

Usage:
    from tg_bot.state_machine import ConversationStateMachine, TelegramState

    sm = ConversationStateMachine()
    sm.transition(user_id, TelegramState.AWAITING_INPUT, "User started command")

    ctx = sm.get_context(user_id)
    sm.set_context(user_id, "token_address", "So11111111111111111111111111111111111111112")
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TelegramState(Enum):
    """States for Telegram bot conversations."""

    # Initial states
    IDLE = auto()  # No active conversation
    GREETING = auto()  # User just started/greeted

    # Input states
    AWAITING_INPUT = auto()  # Waiting for user input
    AWAITING_TOKEN = auto()  # Waiting for token address
    AWAITING_AMOUNT = auto()  # Waiting for amount
    AWAITING_CONFIRMATION = auto()  # Waiting for yes/no confirmation
    AWAITING_SELECTION = auto()  # Waiting for menu selection

    # Processing states
    PROCESSING = auto()  # Processing a request
    ANALYZING = auto()  # Running analysis
    EXECUTING = auto()  # Executing an action

    # Task states
    TASK_ACTIVE = auto()  # Multi-step task in progress
    TASK_WAITING = auto()  # Waiting for task input
    TASK_COMPLETE = auto()  # Task finished

    # Special states
    ERROR = auto()  # Error occurred
    TIMEOUT = auto()  # Session timed out
    CANCELLED = auto()  # User cancelled


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


@dataclass
class StateContext:
    """Context storage for a conversation state."""

    user_id: int
    chat_id: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context data."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in context data."""
        self.data[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def delete(self, key: str) -> bool:
        """Delete a key from context data."""
        if key in self.data:
            del self.data[key]
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False

    def clear(self) -> None:
        """Clear all context data."""
        self.data.clear()
        self.updated_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if context has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateContext":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            chat_id=data.get("chat_id", 0),
            data=data.get("data", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )


@dataclass
class StateRecord:
    """Record of a user's current state."""

    user_id: int
    state: TelegramState
    previous_state: Optional[TelegramState] = None
    entered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transition_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "state": self.state.name,
            "previous_state": self.previous_state.name if self.previous_state else None,
            "entered_at": self.entered_at.isoformat(),
            "transition_reason": self.transition_reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateRecord":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            state=TelegramState[data["state"]],
            previous_state=TelegramState[data["previous_state"]] if data.get("previous_state") else None,
            entered_at=datetime.fromisoformat(data["entered_at"]) if data.get("entered_at") else datetime.now(timezone.utc),
            transition_reason=data.get("transition_reason", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TransitionHistory:
    """History of state transitions for a user."""

    user_id: int
    transitions: List[Dict[str, Any]] = field(default_factory=list)
    max_size: int = 100

    def add(
        self,
        from_state: TelegramState,
        to_state: TelegramState,
        reason: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a transition to history."""
        self.transitions.append({
            "from_state": from_state.name,
            "to_state": to_state.name,
            "reason": reason,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Trim if over max size
        if len(self.transitions) > self.max_size:
            self.transitions = self.transitions[-self.max_size:]

    def get_last(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the last n transitions."""
        return self.transitions[-n:]

    def clear(self) -> None:
        """Clear transition history."""
        self.transitions.clear()


# Type alias for state callbacks
StateCallback = Callable[[int, TelegramState, Optional[TelegramState]], None]
TransitionGuard = Callable[[int, TelegramState, TelegramState], Tuple[bool, str]]


class ConversationStateMachine:
    """
    Manages conversation state for Telegram bot users.

    Features:
    - State transitions with validation
    - Guard conditions for transitions
    - Enter/exit callbacks
    - Context storage per user
    - Timeout handling
    - Persistence to database/file
    """

    # Valid state transitions
    VALID_TRANSITIONS: Dict[TelegramState, Set[TelegramState]] = {
        TelegramState.IDLE: {
            TelegramState.GREETING,
            TelegramState.AWAITING_INPUT,
            TelegramState.PROCESSING,
            TelegramState.TASK_ACTIVE,
        },
        TelegramState.GREETING: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
            TelegramState.PROCESSING,
        },
        TelegramState.AWAITING_INPUT: {
            TelegramState.IDLE,
            TelegramState.PROCESSING,
            TelegramState.AWAITING_TOKEN,
            TelegramState.AWAITING_AMOUNT,
            TelegramState.AWAITING_CONFIRMATION,
            TelegramState.AWAITING_SELECTION,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
        },
        TelegramState.AWAITING_TOKEN: {
            TelegramState.IDLE,
            TelegramState.PROCESSING,
            TelegramState.ANALYZING,
            TelegramState.AWAITING_INPUT,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
            TelegramState.ERROR,
        },
        TelegramState.AWAITING_AMOUNT: {
            TelegramState.IDLE,
            TelegramState.PROCESSING,
            TelegramState.AWAITING_CONFIRMATION,
            TelegramState.AWAITING_INPUT,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
            TelegramState.ERROR,
        },
        TelegramState.AWAITING_CONFIRMATION: {
            TelegramState.IDLE,
            TelegramState.EXECUTING,
            TelegramState.AWAITING_INPUT,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
        },
        TelegramState.AWAITING_SELECTION: {
            TelegramState.IDLE,
            TelegramState.PROCESSING,
            TelegramState.AWAITING_INPUT,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
        },
        TelegramState.PROCESSING: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
            TelegramState.AWAITING_TOKEN,
            TelegramState.AWAITING_AMOUNT,
            TelegramState.AWAITING_CONFIRMATION,
            TelegramState.AWAITING_SELECTION,
            TelegramState.ANALYZING,
            TelegramState.EXECUTING,
            TelegramState.TASK_ACTIVE,
            TelegramState.ERROR,
        },
        TelegramState.ANALYZING: {
            TelegramState.IDLE,
            TelegramState.PROCESSING,
            TelegramState.AWAITING_INPUT,
            TelegramState.TASK_COMPLETE,
            TelegramState.ERROR,
        },
        TelegramState.EXECUTING: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
            TelegramState.TASK_COMPLETE,
            TelegramState.ERROR,
        },
        TelegramState.TASK_ACTIVE: {
            TelegramState.IDLE,
            TelegramState.TASK_WAITING,
            TelegramState.TASK_COMPLETE,
            TelegramState.ERROR,
            TelegramState.CANCELLED,
        },
        TelegramState.TASK_WAITING: {
            TelegramState.TASK_ACTIVE,
            TelegramState.TASK_COMPLETE,
            TelegramState.TIMEOUT,
            TelegramState.CANCELLED,
        },
        TelegramState.TASK_COMPLETE: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
            TelegramState.TASK_ACTIVE,
        },
        TelegramState.ERROR: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
        },
        TelegramState.TIMEOUT: {
            TelegramState.IDLE,
        },
        TelegramState.CANCELLED: {
            TelegramState.IDLE,
            TelegramState.AWAITING_INPUT,
        },
    }

    def __init__(
        self,
        idle_timeout_seconds: int = 300,
        persistence_path: Optional[str] = None,
        db_connection: Any = None,
    ):
        """
        Initialize the state machine.

        Args:
            idle_timeout_seconds: Seconds before an idle session times out (default 5 min)
            persistence_path: Path for file-based persistence (optional)
            db_connection: Database connection for persistence (optional)
        """
        self.idle_timeout_seconds = idle_timeout_seconds
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self.db_connection = db_connection

        # In-memory state
        self._states: Dict[int, StateRecord] = {}
        self._contexts: Dict[int, StateContext] = {}
        self._history: Dict[int, TransitionHistory] = {}
        self._last_activity: Dict[int, float] = {}

        # Callbacks
        self._enter_callbacks: Dict[TelegramState, List[StateCallback]] = {}
        self._exit_callbacks: Dict[TelegramState, List[StateCallback]] = {}
        self._transition_guards: List[TransitionGuard] = []

        # Ensure persistence directory exists
        if self.persistence_path:
            self.persistence_path.mkdir(parents=True, exist_ok=True)

    def get_state(self, user_id: int) -> TelegramState:
        """Get current state for a user."""
        if user_id in self._states:
            return self._states[user_id].state
        return TelegramState.IDLE

    def get_state_record(self, user_id: int) -> Optional[StateRecord]:
        """Get full state record for a user."""
        return self._states.get(user_id)

    def transition(
        self,
        user_id: int,
        to_state: TelegramState,
        reason: str = "",
        metadata: Dict[str, Any] = None,
        force: bool = False,
    ) -> bool:
        """
        Transition a user to a new state.

        Args:
            user_id: User to transition
            to_state: Target state
            reason: Reason for transition
            metadata: Additional transition metadata
            force: Force transition even if invalid

        Returns:
            True if transition succeeded, False otherwise

        Raises:
            TransitionError: If transition is invalid and force=False
        """
        current_state = self.get_state(user_id)

        # Check if transition is valid
        if not force:
            if not self._is_valid_transition(current_state, to_state):
                raise TransitionError(
                    f"Invalid transition from {current_state.name} to {to_state.name}"
                )

            # Check guards
            for guard in self._transition_guards:
                allowed, guard_reason = guard(user_id, current_state, to_state)
                if not allowed:
                    raise TransitionError(f"Transition blocked by guard: {guard_reason}")

        # Execute exit callbacks for current state
        self._run_exit_callbacks(user_id, current_state, to_state)

        # Update state
        old_record = self._states.get(user_id)
        self._states[user_id] = StateRecord(
            user_id=user_id,
            state=to_state,
            previous_state=current_state,
            transition_reason=reason,
            metadata=metadata or {},
        )

        # Record in history
        if user_id not in self._history:
            self._history[user_id] = TransitionHistory(user_id=user_id)
        self._history[user_id].add(current_state, to_state, reason, metadata)

        # Update last activity
        self._last_activity[user_id] = time.time()

        # Execute enter callbacks for new state
        self._run_enter_callbacks(user_id, to_state, current_state)

        logger.debug(f"User {user_id}: {current_state.name} -> {to_state.name} ({reason})")

        return True

    def _is_valid_transition(self, from_state: TelegramState, to_state: TelegramState) -> bool:
        """Check if a transition is valid."""
        if from_state == to_state:
            return True  # Self-transitions are always valid

        valid_targets = self.VALID_TRANSITIONS.get(from_state, set())
        return to_state in valid_targets

    def can_transition(self, user_id: int, to_state: TelegramState) -> Tuple[bool, str]:
        """
        Check if a transition is allowed.

        Returns:
            Tuple of (allowed, reason)
        """
        current_state = self.get_state(user_id)

        if not self._is_valid_transition(current_state, to_state):
            return False, f"Invalid transition from {current_state.name} to {to_state.name}"

        for guard in self._transition_guards:
            allowed, reason = guard(user_id, current_state, to_state)
            if not allowed:
                return False, reason

        return True, "Transition allowed"

    def reset(self, user_id: int, reason: str = "Reset") -> None:
        """Reset a user's state to IDLE."""
        if user_id in self._states:
            current_state = self._states[user_id].state
            self._run_exit_callbacks(user_id, current_state, TelegramState.IDLE)

        self._states[user_id] = StateRecord(
            user_id=user_id,
            state=TelegramState.IDLE,
            transition_reason=reason,
        )
        self._last_activity[user_id] = time.time()

        self._run_enter_callbacks(user_id, TelegramState.IDLE, None)

    # =========================================================================
    # Context Management
    # =========================================================================

    def get_context(self, user_id: int, chat_id: int = 0) -> StateContext:
        """Get or create context for a user."""
        if user_id not in self._contexts:
            self._contexts[user_id] = StateContext(user_id=user_id, chat_id=chat_id)
        return self._contexts[user_id]

    def set_context_value(self, user_id: int, key: str, value: Any) -> None:
        """Set a value in user's context."""
        ctx = self.get_context(user_id)
        ctx.set(key, value)
        self._last_activity[user_id] = time.time()

    def get_context_value(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get a value from user's context."""
        if user_id not in self._contexts:
            return default
        return self._contexts[user_id].get(key, default)

    def clear_context(self, user_id: int) -> None:
        """Clear a user's context."""
        if user_id in self._contexts:
            self._contexts[user_id].clear()

    def delete_context(self, user_id: int) -> None:
        """Delete a user's context entirely."""
        if user_id in self._contexts:
            del self._contexts[user_id]

    def set_context_expiration(self, user_id: int, expires_in_seconds: int) -> None:
        """Set when a user's context should expire."""
        ctx = self.get_context(user_id)
        ctx.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_enter(self, state: TelegramState, callback: StateCallback) -> None:
        """Register a callback for when a state is entered."""
        if state not in self._enter_callbacks:
            self._enter_callbacks[state] = []
        self._enter_callbacks[state].append(callback)

    def on_exit(self, state: TelegramState, callback: StateCallback) -> None:
        """Register a callback for when a state is exited."""
        if state not in self._exit_callbacks:
            self._exit_callbacks[state] = []
        self._exit_callbacks[state].append(callback)

    def add_guard(self, guard: TransitionGuard) -> None:
        """Add a transition guard function."""
        self._transition_guards.append(guard)

    def remove_guard(self, guard: TransitionGuard) -> bool:
        """Remove a transition guard function."""
        try:
            self._transition_guards.remove(guard)
            return True
        except ValueError:
            return False

    def _run_enter_callbacks(
        self,
        user_id: int,
        state: TelegramState,
        from_state: Optional[TelegramState]
    ) -> None:
        """Run enter callbacks for a state."""
        callbacks = self._enter_callbacks.get(state, [])
        for callback in callbacks:
            try:
                callback(user_id, state, from_state)
            except Exception as e:
                logger.error(f"Error in enter callback for {state.name}: {e}")

    def _run_exit_callbacks(
        self,
        user_id: int,
        state: TelegramState,
        to_state: TelegramState
    ) -> None:
        """Run exit callbacks for a state."""
        callbacks = self._exit_callbacks.get(state, [])
        for callback in callbacks:
            try:
                callback(user_id, state, to_state)
            except Exception as e:
                logger.error(f"Error in exit callback for {state.name}: {e}")

    # =========================================================================
    # Timeout Handling
    # =========================================================================

    def check_timeout(self, user_id: int) -> bool:
        """
        Check if a user's session has timed out.

        Returns:
            True if timed out and state was reset
        """
        if user_id not in self._last_activity:
            return False

        last_active = self._last_activity[user_id]
        if time.time() - last_active > self.idle_timeout_seconds:
            current_state = self.get_state(user_id)

            if current_state != TelegramState.IDLE:
                # Transition to TIMEOUT, then IDLE
                try:
                    self.transition(user_id, TelegramState.TIMEOUT, "Session timeout")
                    self.transition(user_id, TelegramState.IDLE, "Timeout cleanup")
                except TransitionError:
                    # Force reset if normal transition fails
                    self.reset(user_id, "Timeout forced reset")

                return True

        return False

    def touch(self, user_id: int) -> None:
        """Update last activity time for a user."""
        self._last_activity[user_id] = time.time()

    def get_idle_time(self, user_id: int) -> float:
        """Get seconds since last activity for a user."""
        if user_id not in self._last_activity:
            return float("inf")
        return time.time() - self._last_activity[user_id]

    def cleanup_expired(self) -> int:
        """
        Clean up expired contexts and timed-out sessions.

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        now = time.time()

        # Check timeouts
        for user_id in list(self._last_activity.keys()):
            if self.check_timeout(user_id):
                cleaned += 1

        # Clean expired contexts
        for user_id in list(self._contexts.keys()):
            ctx = self._contexts[user_id]
            if ctx.is_expired():
                self.delete_context(user_id)
                cleaned += 1

        return cleaned

    # =========================================================================
    # History
    # =========================================================================

    def get_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get transition history for a user."""
        if user_id not in self._history:
            return []
        return self._history[user_id].get_last(limit)

    def clear_history(self, user_id: int) -> None:
        """Clear transition history for a user."""
        if user_id in self._history:
            self._history[user_id].clear()

    # =========================================================================
    # Persistence
    # =========================================================================

    def save_to_db(self, user_id: int) -> bool:
        """Save user's state to database."""
        if self.db_connection is None:
            return False

        try:
            state_record = self._states.get(user_id)
            context = self._contexts.get(user_id)

            if state_record:
                self.db_connection.execute(
                    """
                    INSERT OR REPLACE INTO telegram_state (user_id, state, previous_state,
                        entered_at, transition_reason, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        state_record.state.name,
                        state_record.previous_state.name if state_record.previous_state else None,
                        state_record.entered_at.isoformat(),
                        state_record.transition_reason,
                        json.dumps(state_record.metadata),
                    )
                )

            if context:
                self.db_connection.execute(
                    """
                    INSERT OR REPLACE INTO telegram_context (user_id, chat_id, data,
                        created_at, updated_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        context.chat_id,
                        json.dumps(context.data),
                        context.created_at.isoformat(),
                        context.updated_at.isoformat(),
                        context.expires_at.isoformat() if context.expires_at else None,
                    )
                )

            self.db_connection.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to save state for user {user_id}: {e}")
            return False

    def load_from_db(self, user_id: int) -> bool:
        """Load user's state from database."""
        if self.db_connection is None:
            return False

        try:
            # Load state
            cursor = self.db_connection.execute(
                "SELECT * FROM telegram_state WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                self._states[user_id] = StateRecord(
                    user_id=row["user_id"],
                    state=TelegramState[row["state"]],
                    previous_state=TelegramState[row["previous_state"]] if row["previous_state"] else None,
                    entered_at=datetime.fromisoformat(row["entered_at"]),
                    transition_reason=row["transition_reason"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )

            # Load context
            cursor = self.db_connection.execute(
                "SELECT * FROM telegram_context WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                self._contexts[user_id] = StateContext(
                    user_id=row["user_id"],
                    chat_id=row["chat_id"],
                    data=json.loads(row["data"]) if row["data"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                )

            return True

        except Exception as e:
            logger.error(f"Failed to load state for user {user_id}: {e}")
            return False

    def save_to_file(self, user_id: int) -> bool:
        """Save user's state to file."""
        if self.persistence_path is None:
            return False

        try:
            file_path = self.persistence_path / f"state_{user_id}.json"

            data = {
                "state": self._states[user_id].to_dict() if user_id in self._states else None,
                "context": self._contexts[user_id].to_dict() if user_id in self._contexts else None,
                "last_activity": self._last_activity.get(user_id),
            }

            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save state file for user {user_id}: {e}")
            return False

    def load_from_file(self, user_id: int) -> bool:
        """Load user's state from file."""
        if self.persistence_path is None:
            return False

        try:
            file_path = self.persistence_path / f"state_{user_id}.json"

            if not file_path.exists():
                return False

            with open(file_path, "r") as f:
                data = json.load(f)

            if data.get("state"):
                self._states[user_id] = StateRecord.from_dict(data["state"])

            if data.get("context"):
                self._contexts[user_id] = StateContext.from_dict(data["context"])

            if data.get("last_activity"):
                self._last_activity[user_id] = data["last_activity"]

            return True

        except Exception as e:
            logger.error(f"Failed to load state file for user {user_id}: {e}")
            return False

    def cleanup_old_files(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up old state files.

        Args:
            max_age_seconds: Max age in seconds (default 24 hours)

        Returns:
            Number of files cleaned up
        """
        if self.persistence_path is None:
            return 0

        cleaned = 0
        now = time.time()

        for file_path in self.persistence_path.glob("state_*.json"):
            try:
                if now - file_path.stat().st_mtime > max_age_seconds:
                    file_path.unlink()
                    cleaned += 1
            except OSError as e:
                logger.warning(f"Failed to delete old state file {file_path}: {e}")

        return cleaned

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_all_active_users(self) -> List[int]:
        """Get list of all users with active states."""
        return [
            uid for uid, record in self._states.items()
            if record.state != TelegramState.IDLE
        ]

    def get_users_in_state(self, state: TelegramState) -> List[int]:
        """Get list of users in a specific state."""
        return [
            uid for uid, record in self._states.items()
            if record.state == state
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about current state machine usage."""
        state_counts = {}
        for state in TelegramState:
            count = len(self.get_users_in_state(state))
            if count > 0:
                state_counts[state.name] = count

        return {
            "total_tracked_users": len(self._states),
            "total_contexts": len(self._contexts),
            "active_users": len(self.get_all_active_users()),
            "state_distribution": state_counts,
        }


# Singleton instance
_state_machine: Optional[ConversationStateMachine] = None


def get_state_machine() -> ConversationStateMachine:
    """Get or create the singleton state machine instance."""
    global _state_machine
    if _state_machine is None:
        _state_machine = ConversationStateMachine()
    return _state_machine


def reset_state_machine() -> None:
    """Reset the singleton instance (for testing)."""
    global _state_machine
    _state_machine = None


__all__ = [
    "TelegramState",
    "TransitionError",
    "StateContext",
    "StateRecord",
    "TransitionHistory",
    "ConversationStateMachine",
    "get_state_machine",
    "reset_state_machine",
]
