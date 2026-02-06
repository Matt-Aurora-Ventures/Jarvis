"""
State Handlers

Base classes and utilities for handling messages in specific conversation states.

Example:
    class TokenInputHandler(StateHandler):
        def handle(self, context, message):
            context.data["token"] = message.upper()
            return Response(text=f"Selected: {message}", next_state="amount_input")

        def get_next_state(self, context):
            return "amount_input"

    registry = HandlerRegistry()
    registry.register("token_input", TokenInputHandler())
    response = registry.dispatch(context, "SOL")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.state.context import ConversationContext


@dataclass
class Response:
    """
    Response from a state handler.

    Attributes:
        text: The response text to send to the user
        data: Additional data associated with the response
        next_state: Suggested next state (None to stay in current)
        error: Whether this is an error response
        error_message: Error description if error=True
    """

    text: str
    data: Dict[str, Any] = field(default_factory=dict)
    next_state: Optional[str] = None
    error: bool = False
    error_message: Optional[str] = None


class StateHandler(ABC):
    """
    Abstract base class for state-specific message handlers.

    Subclass this to implement handling logic for each state
    in your conversation flow.
    """

    @abstractmethod
    def handle(
        self,
        context: ConversationContext,
        message: str,
    ) -> Response:
        """
        Handle a message in this state.

        Args:
            context: The conversation context
            message: The user's message

        Returns:
            Response object with text and optional next state
        """
        pass

    @abstractmethod
    def get_next_state(
        self,
        context: ConversationContext,
    ) -> Optional[str]:
        """
        Get the default next state after handling.

        This is used when the handler doesn't explicitly set
        next_state in the Response.

        Args:
            context: The conversation context

        Returns:
            Next state name or None to stay in current state
        """
        pass


class HandlerRegistry:
    """
    Registry for state handlers.

    Maps state names to their handlers and provides dispatch logic.

    Example:
        registry = HandlerRegistry()
        registry.register("idle", IdleHandler())
        registry.register("input", InputHandler())
        registry.set_default(FallbackHandler())

        response = registry.dispatch(context, message)
    """

    def __init__(self):
        self._handlers: Dict[str, StateHandler] = {}
        self._default: Optional[StateHandler] = None

    def register(self, state: str, handler: StateHandler) -> None:
        """
        Register a handler for a state.

        Args:
            state: State name
            handler: Handler instance
        """
        self._handlers[state] = handler

    def set_default(self, handler: StateHandler) -> None:
        """
        Set a default handler for unregistered states.

        Args:
            handler: Default handler instance
        """
        self._default = handler

    def has_handler(self, state: str) -> bool:
        """
        Check if a handler is registered for a state.

        Args:
            state: State name

        Returns:
            True if handler exists
        """
        return state in self._handlers

    def get_handler(self, state: str) -> Optional[StateHandler]:
        """
        Get the handler for a state.

        Args:
            state: State name

        Returns:
            Handler instance or None
        """
        return self._handlers.get(state)

    def dispatch(
        self,
        context: ConversationContext,
        message: str,
    ) -> Response:
        """
        Dispatch a message to the appropriate handler.

        Args:
            context: Conversation context (must have state set)
            message: User message

        Returns:
            Response from the handler
        """
        state = context.state

        # Try to get handler for current state
        handler = self._handlers.get(state) if state else None

        # Fall back to default handler
        if handler is None:
            handler = self._default

        # No handler available
        if handler is None:
            return Response(
                text="No handler available for this state",
                error=True,
                error_message=f"No handler registered for state: {state}",
            )

        return handler.handle(context, message)
