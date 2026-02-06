"""
State Machine Tests

Tests for:
- StateMachine creation and state management
- State transitions with triggers
- Callbacks (on_enter, on_exit)
- Invalid transition handling

Run with: pytest tests/unit/state/test_machine.py -v
"""

import pytest
from typing import List
from unittest.mock import MagicMock


class TestStateMachineCreation:
    """Tests for StateMachine initialization."""

    def test_create_empty_state_machine(self):
        """StateMachine can be created without initial states."""
        from core.state.machine import StateMachine

        sm = StateMachine()
        assert sm is not None
        assert sm.get_current_state() is None

    def test_create_with_initial_state(self):
        """StateMachine can be created with an initial state."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        assert sm.get_current_state() == "idle"

    def test_add_state(self):
        """Can add states to state machine."""
        from core.state.machine import StateMachine

        sm = StateMachine()
        sm.add_state("idle")
        sm.add_state("processing")

        assert "idle" in sm.states
        assert "processing" in sm.states


class TestStateCallbacks:
    """Tests for state entry and exit callbacks."""

    def test_on_enter_callback(self):
        """on_enter callback is called when entering a state."""
        from core.state.machine import StateMachine

        enter_calls = []

        def on_enter_processing(context):
            enter_calls.append("entered_processing")

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing", on_enter=on_enter_processing)
        sm.add_transition("idle", "processing", "start")

        sm.trigger("start")

        assert "entered_processing" in enter_calls
        assert sm.get_current_state() == "processing"

    def test_on_exit_callback(self):
        """on_exit callback is called when exiting a state."""
        from core.state.machine import StateMachine

        exit_calls = []

        def on_exit_idle(context):
            exit_calls.append("exited_idle")

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle", on_exit=on_exit_idle)
        sm.add_state("processing")
        sm.add_transition("idle", "processing", "start")

        sm.trigger("start")

        assert "exited_idle" in exit_calls

    def test_callback_order(self):
        """Callbacks are called in order: exit old, enter new."""
        from core.state.machine import StateMachine

        call_order = []

        def on_exit_idle(context):
            call_order.append("exit_idle")

        def on_enter_processing(context):
            call_order.append("enter_processing")

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle", on_exit=on_exit_idle)
        sm.add_state("processing", on_enter=on_enter_processing)
        sm.add_transition("idle", "processing", "start")

        sm.trigger("start")

        assert call_order == ["exit_idle", "enter_processing"]


class TestStateTransitions:
    """Tests for state transition logic."""

    def test_add_transition(self):
        """Can add transitions between states."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_transition("idle", "processing", "start")

        assert sm.has_transition("idle", "start")

    def test_trigger_valid_transition(self):
        """Trigger causes valid state transition."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_state("done")
        sm.add_transition("idle", "processing", "start")
        sm.add_transition("processing", "done", "complete")

        result = sm.trigger("start")
        assert result is True
        assert sm.get_current_state() == "processing"

        result = sm.trigger("complete")
        assert result is True
        assert sm.get_current_state() == "done"

    def test_trigger_invalid_transition(self):
        """Trigger returns False for invalid transition."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_transition("idle", "processing", "start")

        # Try to trigger complete from idle (not valid)
        result = sm.trigger("complete")

        assert result is False
        assert sm.get_current_state() == "idle"

    def test_trigger_from_wrong_state(self):
        """Trigger returns False when in wrong state."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_state("done")
        sm.add_transition("idle", "processing", "start")
        sm.add_transition("processing", "done", "complete")

        # Can't complete from idle
        result = sm.trigger("complete")
        assert result is False
        assert sm.get_current_state() == "idle"

    def test_multiple_triggers_same_source(self):
        """Multiple triggers can be defined from the same state."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_state("error")
        sm.add_transition("idle", "processing", "start")
        sm.add_transition("idle", "error", "fail")

        sm2 = StateMachine(initial_state="idle")
        sm2.add_state("idle")
        sm2.add_state("processing")
        sm2.add_state("error")
        sm2.add_transition("idle", "processing", "start")
        sm2.add_transition("idle", "error", "fail")

        # First machine starts
        sm.trigger("start")
        assert sm.get_current_state() == "processing"

        # Second machine fails
        sm2.trigger("fail")
        assert sm2.get_current_state() == "error"


class TestStateMachineContext:
    """Tests for passing context through transitions."""

    def test_trigger_with_context(self):
        """Context is passed to callbacks during transition."""
        from core.state.machine import StateMachine

        received_context = {}

        def on_enter_processing(context):
            received_context.update(context)

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing", on_enter=on_enter_processing)
        sm.add_transition("idle", "processing", "start")

        sm.trigger("start", context={"user_id": 123, "data": "test"})

        assert received_context["user_id"] == 123
        assert received_context["data"] == "test"

    def test_callback_can_modify_shared_context(self):
        """Callbacks can modify a shared context object."""
        from core.state.machine import StateMachine

        shared_ctx = {"count": 0}

        def on_enter_processing(context):
            context["count"] += 1

        def on_enter_done(context):
            context["count"] += 10

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing", on_enter=on_enter_processing)
        sm.add_state("done", on_enter=on_enter_done)
        sm.add_transition("idle", "processing", "start")
        sm.add_transition("processing", "done", "complete")

        sm.trigger("start", context=shared_ctx)
        sm.trigger("complete", context=shared_ctx)

        assert shared_ctx["count"] == 11


class TestStateMachineReset:
    """Tests for state machine reset functionality."""

    def test_reset_to_initial_state(self):
        """Can reset state machine to initial state."""
        from core.state.machine import StateMachine

        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_state("done")
        sm.add_transition("idle", "processing", "start")
        sm.add_transition("processing", "done", "complete")

        sm.trigger("start")
        sm.trigger("complete")
        assert sm.get_current_state() == "done"

        sm.reset()
        assert sm.get_current_state() == "idle"


class TestStateMachineValidation:
    """Tests for validation and error handling."""

    def test_add_duplicate_state_ignored(self):
        """Adding duplicate state name doesn't cause error."""
        from core.state.machine import StateMachine

        sm = StateMachine()
        sm.add_state("idle")
        sm.add_state("idle")  # Should not raise

        assert len([s for s in sm.states if s == "idle"]) == 1

    def test_transition_to_nonexistent_state_raises(self):
        """Adding transition to nonexistent state raises error."""
        from core.state.machine import StateMachine, StateError

        sm = StateMachine()
        sm.add_state("idle")

        with pytest.raises(StateError):
            sm.add_transition("idle", "nonexistent", "go")

    def test_transition_from_nonexistent_state_raises(self):
        """Adding transition from nonexistent state raises error."""
        from core.state.machine import StateMachine, StateError

        sm = StateMachine()
        sm.add_state("idle")

        with pytest.raises(StateError):
            sm.add_transition("nonexistent", "idle", "go")
