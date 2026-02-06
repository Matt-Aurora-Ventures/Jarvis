"""
State Machine Implementation

Provides a flexible state machine for managing conversation flows
and multi-step processes.

Example:
    sm = StateMachine(initial_state="idle")
    sm.add_state("idle", on_enter=greet)
    sm.add_state("input", on_exit=validate)
    sm.add_transition("idle", "input", "begin")
    sm.trigger("begin", context={"user": user})
"""

from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field


class StateError(Exception):
    """Raised when a state machine operation fails."""

    pass


@dataclass
class State:
    """Represents a state in the state machine."""

    name: str
    on_enter: Optional[Callable[[Dict[str, Any]], None]] = None
    on_exit: Optional[Callable[[Dict[str, Any]], None]] = None


@dataclass
class Transition:
    """Represents a transition between states."""

    from_state: str
    to_state: str
    trigger: str


class StateMachine:
    """
    A finite state machine for managing conversation flows.

    Features:
    - State definitions with on_enter/on_exit callbacks
    - Named transitions with triggers
    - Context passing through transitions
    - Reset to initial state

    Example:
        sm = StateMachine(initial_state="idle")
        sm.add_state("idle")
        sm.add_state("processing")
        sm.add_transition("idle", "processing", "start")
        sm.trigger("start")
    """

    def __init__(self, initial_state: Optional[str] = None):
        """
        Initialize the state machine.

        Args:
            initial_state: Optional name of the initial state
        """
        self._states: Dict[str, State] = {}
        self._transitions: Dict[str, List[Transition]] = {}  # from_state -> transitions
        self._initial_state = initial_state
        self._current_state = initial_state

    @property
    def states(self) -> Set[str]:
        """Return set of state names."""
        return set(self._states.keys())

    def get_current_state(self) -> Optional[str]:
        """
        Get the current state name.

        Returns:
            Current state name or None if no state is set
        """
        return self._current_state

    def add_state(
        self,
        name: str,
        on_enter: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_exit: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> "StateMachine":
        """
        Add a state to the state machine.

        Args:
            name: State name
            on_enter: Callback called when entering this state
            on_exit: Callback called when exiting this state

        Returns:
            Self for method chaining
        """
        if name not in self._states:
            self._states[name] = State(name=name, on_enter=on_enter, on_exit=on_exit)
            self._transitions[name] = []
        return self

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        trigger: str,
    ) -> "StateMachine":
        """
        Add a transition between states.

        Args:
            from_state: Source state name
            to_state: Destination state name
            trigger: Trigger name that causes this transition

        Returns:
            Self for method chaining

        Raises:
            StateError: If from_state or to_state doesn't exist
        """
        if from_state not in self._states:
            raise StateError(f"Source state '{from_state}' does not exist")
        if to_state not in self._states:
            raise StateError(f"Target state '{to_state}' does not exist")

        transition = Transition(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
        )
        self._transitions[from_state].append(transition)
        return self

    def has_transition(self, from_state: str, trigger: str) -> bool:
        """
        Check if a transition exists from a state with a trigger.

        Args:
            from_state: Source state name
            trigger: Trigger name

        Returns:
            True if transition exists, False otherwise
        """
        if from_state not in self._transitions:
            return False
        return any(t.trigger == trigger for t in self._transitions[from_state])

    def trigger(
        self,
        event: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Trigger a transition.

        Args:
            event: Trigger name
            context: Optional context to pass to callbacks

        Returns:
            True if transition occurred, False otherwise
        """
        if context is None:
            context = {}

        if self._current_state is None:
            return False

        if self._current_state not in self._transitions:
            return False

        # Find matching transition
        matching = None
        for transition in self._transitions[self._current_state]:
            if transition.trigger == event:
                matching = transition
                break

        if matching is None:
            return False

        # Execute transition
        old_state = self._states.get(self._current_state)
        new_state = self._states.get(matching.to_state)

        # Call on_exit callback
        if old_state and old_state.on_exit:
            old_state.on_exit(context)

        # Update current state
        self._current_state = matching.to_state

        # Call on_enter callback
        if new_state and new_state.on_enter:
            new_state.on_enter(context)

        return True

    def reset(self) -> None:
        """Reset the state machine to its initial state."""
        self._current_state = self._initial_state
