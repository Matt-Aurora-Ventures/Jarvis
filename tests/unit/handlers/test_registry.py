"""
Tests for core/handlers/registry.py - HandlerRegistry singleton.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestHandlerRegistry:
    """Tests for HandlerRegistry class."""

    def test_registry_is_singleton(self):
        """HandlerRegistry should return the same instance."""
        from core.handlers.registry import HandlerRegistry

        registry1 = HandlerRegistry.instance()
        registry2 = HandlerRegistry.instance()
        assert registry1 is registry2

    def test_registry_can_be_reset(self):
        """Registry can be reset for testing."""
        from core.handlers.registry import HandlerRegistry

        registry1 = HandlerRegistry.instance()
        HandlerRegistry.reset()
        registry2 = HandlerRegistry.instance()
        assert registry1 is not registry2

    def test_register_handler(self):
        """Handlers can be registered."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class TestHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test command"

            @property
            def usage(self) -> str:
                return "/test"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()
        handler = TestHandler()

        registry.register(handler)
        assert registry.get_handler("test") is handler

    def test_get_handler_returns_none_for_unknown(self):
        """get_handler returns None for unregistered commands."""
        from core.handlers.registry import HandlerRegistry

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        assert registry.get_handler("unknown") is None

    def test_list_handlers(self):
        """list_handlers returns all registered handlers."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class Handler1(CommandHandler):
            @property
            def command(self) -> str:
                return "cmd1"

            @property
            def description(self) -> str:
                return "First"

            @property
            def usage(self) -> str:
                return "/cmd1"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        class Handler2(CommandHandler):
            @property
            def command(self) -> str:
                return "cmd2"

            @property
            def description(self) -> str:
                return "Second"

            @property
            def usage(self) -> str:
                return "/cmd2"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        h1 = Handler1()
        h2 = Handler2()
        registry.register(h1)
        registry.register(h2)

        handlers = registry.list_handlers()
        assert len(handlers) == 2
        assert h1 in handlers
        assert h2 in handlers

    def test_generate_help(self):
        """generate_help returns formatted help text."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class HelpTestHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "greet"

            @property
            def description(self) -> str:
                return "Greet the user"

            @property
            def usage(self) -> str:
                return "/greet [name]"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()
        registry.register(HelpTestHandler())

        help_text = registry.generate_help()

        assert "/greet" in help_text
        assert "Greet the user" in help_text

    def test_register_duplicate_replaces(self):
        """Registering a handler with same command replaces the old one."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class OriginalHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "dup"

            @property
            def description(self) -> str:
                return "Original"

            @property
            def usage(self) -> str:
                return "/dup"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("Original")

            def can_handle(self, message: Any) -> bool:
                return True

        class ReplacementHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "dup"

            @property
            def description(self) -> str:
                return "Replacement"

            @property
            def usage(self) -> str:
                return "/dup"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("Replacement")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        original = OriginalHandler()
        replacement = ReplacementHandler()

        registry.register(original)
        registry.register(replacement)

        handler = registry.get_handler("dup")
        assert handler is replacement
        assert handler.description == "Replacement"

    def test_unregister_handler(self):
        """Handlers can be unregistered."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class TempHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "temp"

            @property
            def description(self) -> str:
                return "Temporary"

            @property
            def usage(self) -> str:
                return "/temp"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        handler = TempHandler()
        registry.register(handler)
        assert registry.get_handler("temp") is handler

        result = registry.unregister("temp")
        assert result is True
        assert registry.get_handler("temp") is None

    def test_unregister_unknown_returns_false(self):
        """Unregistering unknown handler returns False."""
        from core.handlers.registry import HandlerRegistry

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        result = registry.unregister("nonexistent")
        assert result is False

    def test_has_handler(self):
        """has_handler checks if command is registered."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class CheckHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "check"

            @property
            def description(self) -> str:
                return "Check"

            @property
            def usage(self) -> str:
                return "/check"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()
        registry.register(CheckHandler())

        assert registry.has_handler("check") is True
        assert registry.has_handler("nocheck") is False

    def test_get_handler_case_insensitive(self):
        """get_handler should be case-insensitive."""
        from core.handlers.registry import HandlerRegistry
        from core.handlers.base import CommandHandler, Response

        class CaseHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "mycommand"

            @property
            def description(self) -> str:
                return "My Command"

            @property
            def usage(self) -> str:
                return "/mycommand"

            async def handle(self, message: Any, context: Any) -> Response:
                return Response.ok("OK")

            def can_handle(self, message: Any) -> bool:
                return True

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()
        handler = CaseHandler()
        registry.register(handler)

        assert registry.get_handler("mycommand") is handler
        assert registry.get_handler("MyCommand") is handler
        assert registry.get_handler("MYCOMMAND") is handler


class TestGlobalRegistryFunction:
    """Tests for get_handler_registry function."""

    def test_get_handler_registry_returns_instance(self):
        """get_handler_registry returns the singleton instance."""
        from core.handlers.registry import get_handler_registry, HandlerRegistry

        HandlerRegistry.reset()
        registry = get_handler_registry()
        assert isinstance(registry, HandlerRegistry)
        assert registry is HandlerRegistry.instance()
