"""
Comprehensive Tests for Telegram Bot State Machine.

Tests all components of tg_bot/state_machine.py:
- State transitions (valid, invalid, guards)
- Context storage (save/load, expiration)
- State lifecycle (enter/exit callbacks, cleanup)
- Timeout handling (idle timeout, state reset)
- Persistence (file-based, database)

Target: 60%+ coverage with ~50 tests
"""

import json
import os
import pytest
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from tg_bot.state_machine import (
    TelegramState,
    TransitionError,
    StateContext,
    StateRecord,
    TransitionHistory,
    ConversationStateMachine,
    get_state_machine,
    reset_state_machine,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton state machine before each test."""
    reset_state_machine()
    yield
    reset_state_machine()


@pytest.fixture
def state_machine():
    """Create a fresh state machine instance."""
    return ConversationStateMachine()


@pytest.fixture
def temp_persistence_dir():
    """Create a temporary directory for file persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def state_machine_with_persistence(temp_persistence_dir):
    """Create a state machine with file persistence enabled."""
    return ConversationStateMachine(persistence_path=temp_persistence_dir)


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    return conn


@pytest.fixture
def sample_user_id():
    """Provide a sample user ID for testing."""
    return 123456789


@pytest.fixture
def sample_chat_id():
    """Provide a sample chat ID for testing."""
    return -1001234567890


# =============================================================================
# TelegramState Enum Tests
# =============================================================================


class TestTelegramStateEnum:
    """Tests for TelegramState enumeration."""

    def test_all_states_defined(self):
        """Should have all expected states defined."""
        expected_states = {
            "IDLE", "GREETING", "AWAITING_INPUT", "AWAITING_TOKEN",
            "AWAITING_AMOUNT", "AWAITING_CONFIRMATION", "AWAITING_SELECTION",
            "PROCESSING", "ANALYZING", "EXECUTING", "TASK_ACTIVE",
            "TASK_WAITING", "TASK_COMPLETE", "ERROR", "TIMEOUT", "CANCELLED"
        }
        actual_states = {s.name for s in TelegramState}
        assert expected_states == actual_states

    def test_states_are_unique(self):
        """Each state should have a unique value."""
        values = [s.value for s in TelegramState]
        assert len(values) == len(set(values))

    def test_state_name_access(self):
        """Should be able to access state by name."""
        assert TelegramState["IDLE"] == TelegramState.IDLE
        assert TelegramState["PROCESSING"] == TelegramState.PROCESSING


# =============================================================================
# StateContext Tests
# =============================================================================


class TestStateContext:
    """Tests for StateContext dataclass."""

    def test_create_context_with_defaults(self, sample_user_id):
        """Should create context with default values."""
        ctx = StateContext(user_id=sample_user_id)
        assert ctx.user_id == sample_user_id
        assert ctx.chat_id == 0
        assert ctx.data == {}
        assert ctx.created_at is not None
        assert ctx.updated_at is not None
        assert ctx.expires_at is None

    def test_create_context_with_values(self, sample_user_id, sample_chat_id):
        """Should create context with provided values."""
        ctx = StateContext(
            user_id=sample_user_id,
            chat_id=sample_chat_id,
            data={"token": "SOL"}
        )
        assert ctx.user_id == sample_user_id
        assert ctx.chat_id == sample_chat_id
        assert ctx.data == {"token": "SOL"}

    def test_get_value(self, sample_user_id):
        """Should get values from context data."""
        ctx = StateContext(user_id=sample_user_id, data={"key": "value"})
        assert ctx.get("key") == "value"
        assert ctx.get("missing") is None
        assert ctx.get("missing", "default") == "default"

    def test_set_value_updates_timestamp(self, sample_user_id):
        """Setting a value should update the updated_at timestamp."""
        ctx = StateContext(user_id=sample_user_id)
        original_updated = ctx.updated_at

        time.sleep(0.01)  # Small delay to ensure timestamp difference
        ctx.set("new_key", "new_value")

        assert ctx.data["new_key"] == "new_value"
        assert ctx.updated_at >= original_updated

    def test_delete_value(self, sample_user_id):
        """Should delete values from context data."""
        ctx = StateContext(user_id=sample_user_id, data={"key": "value"})

        assert ctx.delete("key") is True
        assert "key" not in ctx.data
        assert ctx.delete("missing") is False

    def test_clear_data(self, sample_user_id):
        """Should clear all context data."""
        ctx = StateContext(user_id=sample_user_id, data={"a": 1, "b": 2, "c": 3})
        ctx.clear()
        assert ctx.data == {}

    def test_is_expired_with_no_expiration(self, sample_user_id):
        """Should not be expired when no expiration is set."""
        ctx = StateContext(user_id=sample_user_id)
        assert ctx.is_expired() is False

    def test_is_expired_with_future_expiration(self, sample_user_id):
        """Should not be expired when expiration is in the future."""
        ctx = StateContext(user_id=sample_user_id)
        ctx.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert ctx.is_expired() is False

    def test_is_expired_with_past_expiration(self, sample_user_id):
        """Should be expired when expiration is in the past."""
        ctx = StateContext(user_id=sample_user_id)
        ctx.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert ctx.is_expired() is True

    def test_to_dict_serialization(self, sample_user_id, sample_chat_id):
        """Should serialize context to dictionary."""
        ctx = StateContext(
            user_id=sample_user_id,
            chat_id=sample_chat_id,
            data={"token": "SOL", "amount": 1.5}
        )
        d = ctx.to_dict()

        assert d["user_id"] == sample_user_id
        assert d["chat_id"] == sample_chat_id
        assert d["data"] == {"token": "SOL", "amount": 1.5}
        assert "created_at" in d
        assert "updated_at" in d

    def test_from_dict_deserialization(self, sample_user_id):
        """Should deserialize context from dictionary."""
        now = datetime.now(timezone.utc)
        d = {
            "user_id": sample_user_id,
            "chat_id": 999,
            "data": {"key": "value"},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": None,
        }
        ctx = StateContext.from_dict(d)

        assert ctx.user_id == sample_user_id
        assert ctx.chat_id == 999
        assert ctx.data == {"key": "value"}


# =============================================================================
# StateRecord Tests
# =============================================================================


class TestStateRecord:
    """Tests for StateRecord dataclass."""

    def test_create_record_with_defaults(self, sample_user_id):
        """Should create record with default values."""
        record = StateRecord(user_id=sample_user_id, state=TelegramState.IDLE)
        assert record.user_id == sample_user_id
        assert record.state == TelegramState.IDLE
        assert record.previous_state is None
        assert record.transition_reason == ""
        assert record.metadata == {}

    def test_create_record_with_previous_state(self, sample_user_id):
        """Should create record with previous state."""
        record = StateRecord(
            user_id=sample_user_id,
            state=TelegramState.PROCESSING,
            previous_state=TelegramState.IDLE,
            transition_reason="User sent command"
        )
        assert record.state == TelegramState.PROCESSING
        assert record.previous_state == TelegramState.IDLE
        assert record.transition_reason == "User sent command"

    def test_to_dict_serialization(self, sample_user_id):
        """Should serialize record to dictionary."""
        record = StateRecord(
            user_id=sample_user_id,
            state=TelegramState.AWAITING_INPUT,
            previous_state=TelegramState.GREETING,
            transition_reason="Greeted user",
            metadata={"extra": "data"}
        )
        d = record.to_dict()

        assert d["user_id"] == sample_user_id
        assert d["state"] == "AWAITING_INPUT"
        assert d["previous_state"] == "GREETING"
        assert d["transition_reason"] == "Greeted user"
        assert d["metadata"] == {"extra": "data"}

    def test_from_dict_deserialization(self, sample_user_id):
        """Should deserialize record from dictionary."""
        now = datetime.now(timezone.utc)
        d = {
            "user_id": sample_user_id,
            "state": "PROCESSING",
            "previous_state": "IDLE",
            "entered_at": now.isoformat(),
            "transition_reason": "Command received",
            "metadata": {}
        }
        record = StateRecord.from_dict(d)

        assert record.user_id == sample_user_id
        assert record.state == TelegramState.PROCESSING
        assert record.previous_state == TelegramState.IDLE


# =============================================================================
# TransitionHistory Tests
# =============================================================================


class TestTransitionHistory:
    """Tests for TransitionHistory class."""

    def test_create_empty_history(self, sample_user_id):
        """Should create empty history."""
        history = TransitionHistory(user_id=sample_user_id)
        assert history.user_id == sample_user_id
        assert history.transitions == []

    def test_add_transition(self, sample_user_id):
        """Should add transition to history."""
        history = TransitionHistory(user_id=sample_user_id)
        history.add(TelegramState.IDLE, TelegramState.PROCESSING, "Start processing")

        assert len(history.transitions) == 1
        assert history.transitions[0]["from_state"] == "IDLE"
        assert history.transitions[0]["to_state"] == "PROCESSING"
        assert history.transitions[0]["reason"] == "Start processing"

    def test_add_multiple_transitions(self, sample_user_id):
        """Should track multiple transitions in order."""
        history = TransitionHistory(user_id=sample_user_id)
        history.add(TelegramState.IDLE, TelegramState.GREETING, "User greeted")
        history.add(TelegramState.GREETING, TelegramState.AWAITING_INPUT, "Waiting for input")
        history.add(TelegramState.AWAITING_INPUT, TelegramState.PROCESSING, "Got command")

        assert len(history.transitions) == 3
        assert history.transitions[0]["from_state"] == "IDLE"
        assert history.transitions[2]["to_state"] == "PROCESSING"

    def test_get_last_n_transitions(self, sample_user_id):
        """Should return last n transitions."""
        history = TransitionHistory(user_id=sample_user_id)
        for i in range(10):
            history.add(TelegramState.IDLE, TelegramState.PROCESSING, f"Transition {i}")

        last_5 = history.get_last(5)
        assert len(last_5) == 5
        assert last_5[0]["reason"] == "Transition 5"
        assert last_5[4]["reason"] == "Transition 9"

    def test_history_max_size_limit(self, sample_user_id):
        """Should trim history when exceeding max size."""
        history = TransitionHistory(user_id=sample_user_id, max_size=10)

        for i in range(20):
            history.add(TelegramState.IDLE, TelegramState.PROCESSING, f"Transition {i}")

        assert len(history.transitions) == 10
        assert history.transitions[0]["reason"] == "Transition 10"

    def test_clear_history(self, sample_user_id):
        """Should clear all history."""
        history = TransitionHistory(user_id=sample_user_id)
        history.add(TelegramState.IDLE, TelegramState.PROCESSING, "Test")
        history.clear()
        assert history.transitions == []


# =============================================================================
# State Transition Tests
# =============================================================================


class TestStateTransitions:
    """Tests for state transition logic."""

    def test_initial_state_is_idle(self, state_machine, sample_user_id):
        """New user should start in IDLE state."""
        state = state_machine.get_state(sample_user_id)
        assert state == TelegramState.IDLE

    def test_valid_transition_from_idle(self, state_machine, sample_user_id):
        """Should allow valid transitions from IDLE."""
        state_machine.transition(sample_user_id, TelegramState.GREETING, "User started")
        assert state_machine.get_state(sample_user_id) == TelegramState.GREETING

    def test_valid_transition_chain(self, state_machine, sample_user_id):
        """Should allow valid chain of transitions."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)
        state_machine.transition(sample_user_id, TelegramState.AWAITING_INPUT)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        assert state_machine.get_state(sample_user_id) == TelegramState.PROCESSING

    def test_invalid_transition_raises_error(self, state_machine, sample_user_id):
        """Should raise TransitionError for invalid transitions."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)

        with pytest.raises(TransitionError) as exc_info:
            state_machine.transition(sample_user_id, TelegramState.TASK_COMPLETE)

        assert "Invalid transition" in str(exc_info.value)

    def test_force_invalid_transition(self, state_machine, sample_user_id):
        """Should allow invalid transition when force=True."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)
        state_machine.transition(
            sample_user_id,
            TelegramState.TASK_COMPLETE,
            force=True
        )
        assert state_machine.get_state(sample_user_id) == TelegramState.TASK_COMPLETE

    def test_self_transition_allowed(self, state_machine, sample_user_id):
        """Should allow transitioning to the same state."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        assert state_machine.get_state(sample_user_id) == TelegramState.PROCESSING

    def test_transition_records_previous_state(self, state_machine, sample_user_id):
        """Should record previous state after transition."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        record = state_machine.get_state_record(sample_user_id)
        assert record.state == TelegramState.PROCESSING
        assert record.previous_state == TelegramState.GREETING

    def test_transition_records_reason(self, state_machine, sample_user_id):
        """Should record transition reason."""
        state_machine.transition(
            sample_user_id,
            TelegramState.PROCESSING,
            reason="User sent /analyze command"
        )

        record = state_machine.get_state_record(sample_user_id)
        assert record.transition_reason == "User sent /analyze command"

    def test_transition_records_metadata(self, state_machine, sample_user_id):
        """Should record transition metadata."""
        # First transition to a valid state, then to AWAITING_TOKEN
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        state_machine.transition(
            sample_user_id,
            TelegramState.AWAITING_TOKEN,
            metadata={"command": "buy", "chat_id": 12345}
        )

        record = state_machine.get_state_record(sample_user_id)
        assert record.metadata["command"] == "buy"
        assert record.metadata["chat_id"] == 12345

    def test_can_transition_check_valid(self, state_machine, sample_user_id):
        """can_transition should return True for valid transitions."""
        allowed, reason = state_machine.can_transition(
            sample_user_id,
            TelegramState.GREETING
        )
        assert allowed is True
        assert "allowed" in reason.lower()

    def test_can_transition_check_invalid(self, state_machine, sample_user_id):
        """can_transition should return False for invalid transitions."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)

        allowed, reason = state_machine.can_transition(
            sample_user_id,
            TelegramState.TASK_WAITING
        )
        assert allowed is False
        assert "Invalid transition" in reason

    def test_reset_to_idle(self, state_machine, sample_user_id):
        """Should reset user to IDLE state."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        state_machine.transition(sample_user_id, TelegramState.TASK_ACTIVE)

        state_machine.reset(sample_user_id, "Manual reset")

        assert state_machine.get_state(sample_user_id) == TelegramState.IDLE


# =============================================================================
# Transition Guard Tests
# =============================================================================


class TestTransitionGuards:
    """Tests for transition guard functionality."""

    def test_add_guard(self, state_machine, sample_user_id):
        """Should add a guard function."""
        def my_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            return True, "OK"

        state_machine.add_guard(my_guard)
        assert my_guard in state_machine._transition_guards

    def test_guard_blocks_transition(self, state_machine, sample_user_id):
        """Guard should be able to block transitions."""
        def blocking_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            if to_s == TelegramState.PROCESSING:
                return False, "Processing blocked for testing"
            return True, "OK"

        state_machine.add_guard(blocking_guard)

        with pytest.raises(TransitionError) as exc_info:
            state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        assert "Processing blocked" in str(exc_info.value)

    def test_guard_allows_transition(self, state_machine, sample_user_id):
        """Guard should allow valid transitions."""
        def allowing_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            return True, "Allowed"

        state_machine.add_guard(allowing_guard)
        state_machine.transition(sample_user_id, TelegramState.GREETING)

        assert state_machine.get_state(sample_user_id) == TelegramState.GREETING

    def test_multiple_guards_all_must_pass(self, state_machine, sample_user_id):
        """All guards must pass for transition to succeed."""
        def guard1(uid, from_s, to_s) -> Tuple[bool, str]:
            return True, "Guard 1 OK"

        def guard2(uid, from_s, to_s) -> Tuple[bool, str]:
            return False, "Guard 2 blocks"

        state_machine.add_guard(guard1)
        state_machine.add_guard(guard2)

        with pytest.raises(TransitionError):
            state_machine.transition(sample_user_id, TelegramState.PROCESSING)

    def test_remove_guard(self, state_machine):
        """Should remove a guard function."""
        def my_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            return True, "OK"

        state_machine.add_guard(my_guard)
        result = state_machine.remove_guard(my_guard)

        assert result is True
        assert my_guard not in state_machine._transition_guards

    def test_remove_nonexistent_guard(self, state_machine):
        """Should return False when removing nonexistent guard."""
        def my_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            return True, "OK"

        result = state_machine.remove_guard(my_guard)
        assert result is False

    def test_guard_with_user_specific_logic(self, state_machine):
        """Guard can have user-specific logic."""
        blocked_users = {999, 1000}

        def user_guard(uid, from_s, to_s) -> Tuple[bool, str]:
            if uid in blocked_users:
                return False, f"User {uid} is blocked"
            return True, "OK"

        state_machine.add_guard(user_guard)

        # Allowed user can transition
        state_machine.transition(123, TelegramState.PROCESSING)
        assert state_machine.get_state(123) == TelegramState.PROCESSING

        # Blocked user cannot
        with pytest.raises(TransitionError):
            state_machine.transition(999, TelegramState.PROCESSING)


# =============================================================================
# Context Storage Tests
# =============================================================================


class TestContextStorage:
    """Tests for context storage functionality."""

    def test_get_context_creates_new(self, state_machine, sample_user_id):
        """Should create new context if none exists."""
        ctx = state_machine.get_context(sample_user_id)
        assert ctx is not None
        assert ctx.user_id == sample_user_id

    def test_get_context_returns_same(self, state_machine, sample_user_id):
        """Should return same context on subsequent calls."""
        ctx1 = state_machine.get_context(sample_user_id)
        ctx2 = state_machine.get_context(sample_user_id)
        assert ctx1 is ctx2

    def test_set_context_value(self, state_machine, sample_user_id):
        """Should set value in user's context."""
        state_machine.set_context_value(sample_user_id, "token", "SOL")

        ctx = state_machine.get_context(sample_user_id)
        assert ctx.get("token") == "SOL"

    def test_get_context_value(self, state_machine, sample_user_id):
        """Should get value from user's context."""
        state_machine.set_context_value(sample_user_id, "amount", 1.5)

        value = state_machine.get_context_value(sample_user_id, "amount")
        assert value == 1.5

    def test_get_context_value_default(self, state_machine, sample_user_id):
        """Should return default for missing keys."""
        value = state_machine.get_context_value(sample_user_id, "missing", "default")
        assert value == "default"

    def test_get_context_value_no_context(self, state_machine, sample_user_id):
        """Should return default when no context exists."""
        value = state_machine.get_context_value(sample_user_id, "key", "default")
        assert value == "default"

    def test_clear_context(self, state_machine, sample_user_id):
        """Should clear all context data."""
        state_machine.set_context_value(sample_user_id, "a", 1)
        state_machine.set_context_value(sample_user_id, "b", 2)

        state_machine.clear_context(sample_user_id)

        ctx = state_machine.get_context(sample_user_id)
        assert ctx.data == {}

    def test_delete_context(self, state_machine, sample_user_id):
        """Should delete context entirely."""
        state_machine.set_context_value(sample_user_id, "key", "value")
        state_machine.delete_context(sample_user_id)

        assert sample_user_id not in state_machine._contexts

    def test_set_context_expiration(self, state_machine, sample_user_id):
        """Should set context expiration time."""
        state_machine.get_context(sample_user_id)
        state_machine.set_context_expiration(sample_user_id, 3600)

        ctx = state_machine.get_context(sample_user_id)
        assert ctx.expires_at is not None
        assert ctx.expires_at > datetime.now(timezone.utc)


# =============================================================================
# State Lifecycle Callback Tests
# =============================================================================


class TestStateLifecycleCallbacks:
    """Tests for enter/exit callbacks."""

    def test_on_enter_callback(self, state_machine, sample_user_id):
        """Should call enter callback when entering state."""
        enter_called = []

        def on_enter(uid, state, from_state):
            enter_called.append((uid, state, from_state))

        state_machine.on_enter(TelegramState.PROCESSING, on_enter)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        assert len(enter_called) == 1
        assert enter_called[0][0] == sample_user_id
        assert enter_called[0][1] == TelegramState.PROCESSING
        assert enter_called[0][2] == TelegramState.IDLE

    def test_on_exit_callback(self, state_machine, sample_user_id):
        """Should call exit callback when leaving state."""
        exit_called = []

        def on_exit(uid, state, to_state):
            exit_called.append((uid, state, to_state))

        state_machine.on_exit(TelegramState.IDLE, on_exit)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        assert len(exit_called) == 1
        assert exit_called[0][0] == sample_user_id
        assert exit_called[0][1] == TelegramState.IDLE
        assert exit_called[0][2] == TelegramState.PROCESSING

    def test_multiple_callbacks_same_state(self, state_machine, sample_user_id):
        """Should call all callbacks for a state."""
        calls = []

        state_machine.on_enter(TelegramState.PROCESSING, lambda u, s, f: calls.append("cb1"))
        state_machine.on_enter(TelegramState.PROCESSING, lambda u, s, f: calls.append("cb2"))
        state_machine.on_enter(TelegramState.PROCESSING, lambda u, s, f: calls.append("cb3"))

        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        assert calls == ["cb1", "cb2", "cb3"]

    def test_callback_error_does_not_stop_transition(self, state_machine, sample_user_id):
        """Callback errors should not prevent transition."""
        def failing_callback(uid, state, from_state):
            raise ValueError("Callback error")

        state_machine.on_enter(TelegramState.PROCESSING, failing_callback)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        # Transition should still complete
        assert state_machine.get_state(sample_user_id) == TelegramState.PROCESSING

    def test_enter_callback_receives_none_on_reset(self, state_machine, sample_user_id):
        """Enter callback should receive None for from_state on reset."""
        enter_calls = []

        def on_enter(uid, state, from_state):
            enter_calls.append(from_state)

        state_machine.on_enter(TelegramState.IDLE, on_enter)
        state_machine.reset(sample_user_id)

        assert None in enter_calls


# =============================================================================
# Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout functionality."""

    def test_check_timeout_not_expired(self, sample_user_id):
        """Should not timeout if under idle timeout."""
        sm = ConversationStateMachine(idle_timeout_seconds=300)
        sm.transition(sample_user_id, TelegramState.PROCESSING)

        result = sm.check_timeout(sample_user_id)
        assert result is False
        assert sm.get_state(sample_user_id) == TelegramState.PROCESSING

    def test_check_timeout_expired(self, sample_user_id):
        """Should timeout if over idle timeout."""
        sm = ConversationStateMachine(idle_timeout_seconds=0)  # 0 seconds
        sm.transition(sample_user_id, TelegramState.PROCESSING)

        time.sleep(0.01)  # Small delay

        result = sm.check_timeout(sample_user_id)
        assert result is True
        assert sm.get_state(sample_user_id) == TelegramState.IDLE

    def test_touch_updates_activity(self, sample_user_id):
        """Touch should update last activity time."""
        sm = ConversationStateMachine(idle_timeout_seconds=1)
        sm.transition(sample_user_id, TelegramState.PROCESSING)

        time.sleep(0.5)
        sm.touch(sample_user_id)
        time.sleep(0.5)

        # Should not timeout because we touched
        result = sm.check_timeout(sample_user_id)
        assert result is False

    def test_get_idle_time(self, state_machine, sample_user_id):
        """Should return time since last activity."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        time.sleep(0.1)

        idle_time = state_machine.get_idle_time(sample_user_id)
        assert idle_time >= 0.1
        assert idle_time < 1.0

    def test_get_idle_time_no_activity(self, state_machine, sample_user_id):
        """Should return infinity if no activity recorded."""
        idle_time = state_machine.get_idle_time(sample_user_id)
        assert idle_time == float("inf")

    def test_idle_user_no_timeout(self, sample_user_id):
        """IDLE users should not timeout."""
        sm = ConversationStateMachine(idle_timeout_seconds=0)
        # User starts in IDLE, should not timeout
        result = sm.check_timeout(sample_user_id)
        assert result is False

    def test_cleanup_expired_sessions(self, sample_user_id):
        """cleanup_expired should handle timed-out sessions."""
        sm = ConversationStateMachine(idle_timeout_seconds=0)
        sm.transition(sample_user_id, TelegramState.PROCESSING)
        sm.transition(sample_user_id + 1, TelegramState.AWAITING_INPUT)

        time.sleep(0.01)

        cleaned = sm.cleanup_expired()
        assert cleaned >= 2

    def test_cleanup_expired_contexts(self, sample_user_id):
        """cleanup_expired should remove expired contexts."""
        sm = ConversationStateMachine()
        sm.get_context(sample_user_id)
        sm._contexts[sample_user_id].expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        cleaned = sm.cleanup_expired()
        assert cleaned >= 1
        assert sample_user_id not in sm._contexts


# =============================================================================
# History Tests
# =============================================================================


class TestHistoryTracking:
    """Tests for transition history functionality."""

    def test_get_history(self, state_machine, sample_user_id):
        """Should return transition history."""
        state_machine.transition(sample_user_id, TelegramState.GREETING)
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)

        history = state_machine.get_history(sample_user_id)
        assert len(history) == 2

    def test_get_history_limit(self, state_machine, sample_user_id):
        """Should respect limit parameter."""
        for i in range(10):
            state_machine.transition(
                sample_user_id,
                TelegramState.PROCESSING if i % 2 == 0 else TelegramState.AWAITING_INPUT
            )

        history = state_machine.get_history(sample_user_id, limit=3)
        assert len(history) == 3

    def test_get_history_empty(self, state_machine, sample_user_id):
        """Should return empty list if no history."""
        history = state_machine.get_history(sample_user_id)
        assert history == []

    def test_clear_history(self, state_machine, sample_user_id):
        """Should clear user's history."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING)
        state_machine.clear_history(sample_user_id)

        history = state_machine.get_history(sample_user_id)
        assert history == []


# =============================================================================
# File Persistence Tests
# =============================================================================


class TestFilePersistence:
    """Tests for file-based persistence."""

    def test_save_to_file(self, state_machine_with_persistence, sample_user_id, temp_persistence_dir):
        """Should save state to file."""
        sm = state_machine_with_persistence
        sm.transition(sample_user_id, TelegramState.PROCESSING)
        sm.set_context_value(sample_user_id, "token", "SOL")

        result = sm.save_to_file(sample_user_id)

        assert result is True
        file_path = Path(temp_persistence_dir) / f"state_{sample_user_id}.json"
        assert file_path.exists()

    def test_load_from_file(self, state_machine_with_persistence, sample_user_id, temp_persistence_dir):
        """Should load state from file."""
        sm = state_machine_with_persistence
        sm.transition(sample_user_id, TelegramState.PROCESSING)
        sm.set_context_value(sample_user_id, "token", "SOL")
        sm.save_to_file(sample_user_id)

        # Clear in-memory state
        sm._states.clear()
        sm._contexts.clear()

        result = sm.load_from_file(sample_user_id)

        assert result is True
        assert sm.get_state(sample_user_id) == TelegramState.PROCESSING
        assert sm.get_context_value(sample_user_id, "token") == "SOL"

    def test_load_from_nonexistent_file(self, state_machine_with_persistence, sample_user_id):
        """Should return False for nonexistent file."""
        result = state_machine_with_persistence.load_from_file(999999)
        assert result is False

    def test_save_without_persistence_path(self, state_machine, sample_user_id):
        """Should return False when no persistence path configured."""
        result = state_machine.save_to_file(sample_user_id)
        assert result is False

    def test_cleanup_old_files(self, state_machine_with_persistence, sample_user_id, temp_persistence_dir):
        """Should clean up old state files."""
        sm = state_machine_with_persistence

        # Create old file
        old_file = Path(temp_persistence_dir) / "state_999.json"
        old_file.write_text("{}")
        os.utime(old_file, (0, 0))  # Set mtime to epoch

        cleaned = sm.cleanup_old_files(max_age_seconds=1)
        assert cleaned >= 1
        assert not old_file.exists()


# =============================================================================
# Database Persistence Tests
# =============================================================================


class TestDatabasePersistence:
    """Tests for database persistence."""

    def test_save_to_db(self, mock_db_connection, sample_user_id):
        """Should save state to database."""
        sm = ConversationStateMachine(db_connection=mock_db_connection)
        sm.transition(sample_user_id, TelegramState.PROCESSING)

        result = sm.save_to_db(sample_user_id)

        assert result is True
        assert mock_db_connection.execute.called
        assert mock_db_connection.commit.called

    def test_save_to_db_no_connection(self, state_machine, sample_user_id):
        """Should return False when no db connection."""
        result = state_machine.save_to_db(sample_user_id)
        assert result is False

    def test_load_from_db_no_connection(self, state_machine, sample_user_id):
        """Should return False when no db connection."""
        result = state_machine.load_from_db(sample_user_id)
        assert result is False


# =============================================================================
# Utility Method Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_all_active_users(self, state_machine):
        """Should return list of users not in IDLE state."""
        state_machine.transition(1, TelegramState.PROCESSING)
        state_machine.transition(2, TelegramState.AWAITING_INPUT)
        state_machine.reset(3)  # This one is IDLE

        active = state_machine.get_all_active_users()
        assert 1 in active
        assert 2 in active
        assert 3 not in active

    def test_get_users_in_state(self, state_machine):
        """Should return list of users in specific state."""
        state_machine.transition(1, TelegramState.PROCESSING)
        state_machine.transition(2, TelegramState.PROCESSING)
        state_machine.transition(3, TelegramState.AWAITING_INPUT)

        users = state_machine.get_users_in_state(TelegramState.PROCESSING)
        assert 1 in users
        assert 2 in users
        assert 3 not in users

    def test_get_statistics(self, state_machine):
        """Should return usage statistics."""
        state_machine.transition(1, TelegramState.PROCESSING)
        state_machine.transition(2, TelegramState.AWAITING_INPUT)
        state_machine.get_context(1)
        state_machine.get_context(2)

        stats = state_machine.get_statistics()

        assert stats["total_tracked_users"] == 2
        assert stats["total_contexts"] == 2
        assert stats["active_users"] == 2
        assert "PROCESSING" in stats["state_distribution"]


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_state_machine_returns_singleton(self):
        """Should return same instance."""
        sm1 = get_state_machine()
        sm2 = get_state_machine()
        assert sm1 is sm2

    def test_reset_state_machine(self):
        """Should reset singleton instance."""
        sm1 = get_state_machine()
        reset_state_machine()
        sm2 = get_state_machine()
        assert sm1 is not sm2

    def test_singleton_persists_state(self):
        """State should persist in singleton."""
        sm1 = get_state_machine()
        sm1.transition(123, TelegramState.PROCESSING)

        sm2 = get_state_machine()
        assert sm2.get_state(123) == TelegramState.PROCESSING


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_transition_with_empty_reason(self, state_machine, sample_user_id):
        """Should handle empty reason string."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING, reason="")
        record = state_machine.get_state_record(sample_user_id)
        assert record.transition_reason == ""

    def test_transition_with_none_metadata(self, state_machine, sample_user_id):
        """Should handle None metadata."""
        state_machine.transition(sample_user_id, TelegramState.PROCESSING, metadata=None)
        record = state_machine.get_state_record(sample_user_id)
        assert record.metadata == {}

    def test_large_context_data(self, state_machine, sample_user_id):
        """Should handle large context data."""
        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        for key, value in large_data.items():
            state_machine.set_context_value(sample_user_id, key, value)

        ctx = state_machine.get_context(sample_user_id)
        assert len(ctx.data) == 1000

    def test_unicode_in_context(self, state_machine, sample_user_id):
        """Should handle unicode in context."""
        state_machine.set_context_value(sample_user_id, "emoji", "Hello!")
        state_machine.set_context_value(sample_user_id, "japanese", "Hello")
        state_machine.set_context_value(sample_user_id, "arabic", "Hello")

        ctx = state_machine.get_context(sample_user_id)
        assert ctx.get("emoji") == "Hello!"

    def test_concurrent_state_updates(self, state_machine):
        """Should handle multiple users updating state."""
        for i in range(100):
            state_machine.transition(i, TelegramState.PROCESSING)

        active = state_machine.get_all_active_users()
        assert len(active) == 100

    def test_state_record_without_previous(self, sample_user_id):
        """Should handle state record without previous state."""
        record = StateRecord(user_id=sample_user_id, state=TelegramState.IDLE)
        d = record.to_dict()
        assert d["previous_state"] is None

        # Round-trip
        restored = StateRecord.from_dict(d)
        assert restored.previous_state is None
