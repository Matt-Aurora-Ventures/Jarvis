"""
Tests for core/handlers/base.py - CommandHandler abstract class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from typing import Any, Dict, Optional


class TestCommandHandler:
    """Tests for CommandHandler abstract base class."""

    def test_command_handler_is_abstract(self):
        """CommandHandler cannot be instantiated directly."""
        from core.handlers.base import CommandHandler

        with pytest.raises(TypeError):
            CommandHandler()

    def test_command_handler_requires_command_property(self):
        """Concrete handlers must implement command property."""
        from core.handlers.base import CommandHandler

        class IncompleteHandler(CommandHandler):
            @property
            def description(self) -> str:
                return "test"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> "Response":
                pass

            def can_handle(self, message: Any) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_command_handler_requires_description_property(self):
        """Concrete handlers must implement description property."""
        from core.handlers.base import CommandHandler

        class IncompleteHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> "Response":
                pass

            def can_handle(self, message: Any) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_command_handler_requires_usage_property(self):
        """Concrete handlers must implement usage property."""
        from core.handlers.base import CommandHandler

        class IncompleteHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "test desc"

            async def handle(self, message: Any, context: Any) -> "Response":
                pass

            def can_handle(self, message: Any) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_command_handler_requires_handle_method(self):
        """Concrete handlers must implement handle method."""
        from core.handlers.base import CommandHandler

        class IncompleteHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "test desc"

            @property
            def usage(self) -> str:
                return "/test"

            def can_handle(self, message: Any) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_command_handler_requires_can_handle_method(self):
        """Concrete handlers must implement can_handle method."""
        from core.handlers.base import CommandHandler

        class IncompleteHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "test desc"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> "Response":
                pass

        with pytest.raises(TypeError):
            IncompleteHandler()

    def test_complete_handler_can_be_instantiated(self):
        """A complete handler implementation can be instantiated."""
        from core.handlers.base import CommandHandler, Response

        class CompleteHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test command"

            @property
            def usage(self) -> str:
                return "/test [arg]"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response(success=True, message="OK")

            def can_handle(self, message: Any) -> bool:
                return True

        handler = CompleteHandler()
        assert handler.command == "test"
        assert handler.description == "Test command"
        assert handler.usage == "/test [arg]"

    @pytest.mark.asyncio
    async def test_handler_handle_method_returns_response(self):
        """Handle method should return a Response object."""
        from core.handlers.base import CommandHandler, Response

        class TestHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response(success=True, message="Success!", data={"key": "value"})

            def can_handle(self, message: Any) -> bool:
                return message == "/test"

        handler = TestHandler()
        response = await handler.handle("/test", {})

        assert isinstance(response, Response)
        assert response.success is True
        assert response.message == "Success!"
        assert response.data == {"key": "value"}

    def test_can_handle_returns_boolean(self):
        """can_handle should return a boolean."""
        from core.handlers.base import CommandHandler, Response

        class TestHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response(success=True, message="OK")

            def can_handle(self, message: Any) -> bool:
                return str(message).startswith("/test")

        handler = TestHandler()
        assert handler.can_handle("/test") is True
        assert handler.can_handle("/test arg1") is True
        assert handler.can_handle("/other") is False
        assert handler.can_handle("test") is False


class TestResponse:
    """Tests for Response dataclass."""

    def test_response_creation(self):
        """Response can be created with required fields."""
        from core.handlers.base import Response

        response = Response(success=True, message="OK")
        assert response.success is True
        assert response.message == "OK"
        assert response.data is None
        assert response.error is None

    def test_response_with_data(self):
        """Response can include optional data."""
        from core.handlers.base import Response

        response = Response(success=True, message="OK", data={"count": 5})
        assert response.data == {"count": 5}

    def test_response_with_error(self):
        """Response can include optional error."""
        from core.handlers.base import Response

        response = Response(success=False, message="Failed", error="Something went wrong")
        assert response.success is False
        assert response.error == "Something went wrong"

    def test_response_ok_factory(self):
        """Response.ok() creates a success response."""
        from core.handlers.base import Response

        response = Response.ok("Done!", data={"result": 42})
        assert response.success is True
        assert response.message == "Done!"
        assert response.data == {"result": 42}

    def test_response_error_factory(self):
        """Response.error() creates an error response."""
        from core.handlers.base import Response

        response = Response.fail("Failed!", error="Invalid input")
        assert response.success is False
        assert response.message == "Failed!"
        assert response.error == "Invalid input"


class TestMessageContext:
    """Tests for MessageContext dataclass."""

    def test_message_context_creation(self):
        """MessageContext can be created with required fields."""
        from core.handlers.base import MessageContext

        ctx = MessageContext(
            user_id=12345,
            chat_id=67890,
            platform="telegram"
        )
        assert ctx.user_id == 12345
        assert ctx.chat_id == 67890
        assert ctx.platform == "telegram"

    def test_message_context_optional_fields(self):
        """MessageContext has optional fields with defaults."""
        from core.handlers.base import MessageContext

        ctx = MessageContext(
            user_id=123,
            chat_id=456,
            platform="discord",
            is_admin=True,
            username="testuser",
            raw_message="test message",
            metadata={"key": "value"}
        )
        assert ctx.is_admin is True
        assert ctx.username == "testuser"
        assert ctx.raw_message == "test message"
        assert ctx.metadata == {"key": "value"}

    def test_message_context_defaults(self):
        """MessageContext has sensible defaults."""
        from core.handlers.base import MessageContext

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        assert ctx.is_admin is False
        assert ctx.username is None
        assert ctx.raw_message is None
        assert ctx.metadata is None
