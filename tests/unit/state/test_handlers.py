"""
State Handler Tests

Tests for:
- StateHandler base class
- Handler registration and dispatch
- Handler response types

Run with: pytest tests/unit/state/test_handlers.py -v
"""

import pytest
from dataclasses import dataclass
from typing import Optional


class TestStateHandlerBase:
    """Tests for StateHandler base class."""

    def test_handler_is_abstract(self):
        """StateHandler is an abstract base class."""
        from core.state.handlers import StateHandler

        with pytest.raises(TypeError):
            StateHandler()  # Cannot instantiate abstract class

    def test_custom_handler_implementation(self):
        """Can create custom handler implementation."""
        from core.state.handlers import StateHandler, Response
        from core.state.context import ConversationContext

        class MyHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(text="Hello!")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return "next_state"

        handler = MyHandler()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")

        response = handler.handle(ctx, "test")
        next_state = handler.get_next_state(ctx)

        assert response.text == "Hello!"
        assert next_state == "next_state"


class TestResponse:
    """Tests for Response dataclass."""

    def test_create_text_response(self):
        """Can create response with text."""
        from core.state.handlers import Response

        response = Response(text="Hello, world!")

        assert response.text == "Hello, world!"

    def test_response_with_data(self):
        """Response can include additional data."""
        from core.state.handlers import Response

        response = Response(
            text="Processing...",
            data={"status": "pending", "id": 123},
        )

        assert response.data["status"] == "pending"
        assert response.data["id"] == 123

    def test_response_with_next_state(self):
        """Response can suggest next state."""
        from core.state.handlers import Response

        response = Response(
            text="Done!",
            next_state="completed",
        )

        assert response.next_state == "completed"

    def test_response_with_error(self):
        """Response can indicate error."""
        from core.state.handlers import Response

        response = Response(
            text="Error occurred",
            error=True,
            error_message="Invalid input",
        )

        assert response.error is True
        assert response.error_message == "Invalid input"

    def test_response_defaults(self):
        """Response has sensible defaults."""
        from core.state.handlers import Response

        response = Response(text="Test")

        assert response.data == {}
        assert response.next_state is None
        assert response.error is False
        assert response.error_message is None


class TestHandlerRegistry:
    """Tests for handler registration and dispatch."""

    def test_register_handler(self):
        """Can register handler for a state."""
        from core.state.handlers import HandlerRegistry, StateHandler, Response
        from core.state.context import ConversationContext

        class IdleHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(text="Idle response")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return None

        registry = HandlerRegistry()
        registry.register("idle", IdleHandler())

        assert registry.has_handler("idle")

    def test_get_handler(self):
        """Can get registered handler."""
        from core.state.handlers import HandlerRegistry, StateHandler, Response
        from core.state.context import ConversationContext

        class TestHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(text="Test")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return None

        registry = HandlerRegistry()
        handler = TestHandler()
        registry.register("test_state", handler)

        retrieved = registry.get_handler("test_state")

        assert retrieved is handler

    def test_get_nonexistent_handler_returns_none(self):
        """Getting nonexistent handler returns None."""
        from core.state.handlers import HandlerRegistry

        registry = HandlerRegistry()
        handler = registry.get_handler("nonexistent")

        assert handler is None

    def test_dispatch_to_handler(self):
        """Can dispatch message to appropriate handler."""
        from core.state.handlers import HandlerRegistry, StateHandler, Response
        from core.state.context import ConversationContext

        class GreetingHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(text=f"Hello, {message}!")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return "next"

        registry = HandlerRegistry()
        registry.register("greeting", GreetingHandler())

        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "greeting"

        response = registry.dispatch(ctx, "World")

        assert response.text == "Hello, World!"

    def test_dispatch_with_no_handler_returns_error(self):
        """Dispatch with no handler returns error response."""
        from core.state.handlers import HandlerRegistry
        from core.state.context import ConversationContext

        registry = HandlerRegistry()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "unknown_state"

        response = registry.dispatch(ctx, "test")

        assert response.error is True

    def test_default_handler(self):
        """Can set and use a default handler."""
        from core.state.handlers import HandlerRegistry, StateHandler, Response
        from core.state.context import ConversationContext

        class DefaultHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(text="Default response")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return None

        registry = HandlerRegistry()
        registry.set_default(DefaultHandler())

        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "any_unregistered_state"

        response = registry.dispatch(ctx, "test")

        assert response.text == "Default response"


class TestHandlerChaining:
    """Tests for handler chaining and state progression."""

    def test_handler_can_trigger_state_change(self):
        """Handler can trigger state change via response."""
        from core.state.handlers import StateHandler, Response
        from core.state.context import ConversationContext

        class StartHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                return Response(
                    text="Starting process...",
                    next_state="processing",
                )

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return "processing"

        handler = StartHandler()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "idle"

        response = handler.handle(ctx, "start")

        assert response.next_state == "processing"

    def test_handler_can_stay_in_same_state(self):
        """Handler can indicate staying in same state."""
        from core.state.handlers import StateHandler, Response
        from core.state.context import ConversationContext

        class WaitingHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                if message != "confirm":
                    return Response(
                        text="Please type 'confirm' to continue",
                        next_state=None,  # Stay in current state
                    )
                return Response(text="Confirmed!", next_state="done")

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return None

        handler = WaitingHandler()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")
        ctx.state = "waiting"

        # Wrong input
        response1 = handler.handle(ctx, "wrong")
        assert response1.next_state is None

        # Correct input
        response2 = handler.handle(ctx, "confirm")
        assert response2.next_state == "done"

    def test_handler_with_context_data(self):
        """Handler can read and write context data."""
        from core.state.handlers import StateHandler, Response
        from core.state.context import ConversationContext

        class TokenInputHandler(StateHandler):
            def handle(self, context: ConversationContext, message: str) -> Response:
                # Store the token in context
                context.data["selected_token"] = message.upper()
                return Response(
                    text=f"Selected token: {message.upper()}",
                    next_state="amount_input",
                )

            def get_next_state(self, context: ConversationContext) -> Optional[str]:
                return "amount_input"

        handler = TokenInputHandler()
        ctx = ConversationContext(user_id="user1", chat_id="chat1")

        handler.handle(ctx, "sol")

        assert ctx.data["selected_token"] == "SOL"
