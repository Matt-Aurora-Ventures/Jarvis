"""
Tests for core/handlers/common.py - Common command handlers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestHelpHandler:
    """Tests for HelpHandler."""

    def test_help_handler_properties(self):
        """HelpHandler has correct properties."""
        from core.handlers.common import HelpHandler

        handler = HelpHandler()
        assert handler.command == "help"
        # Description should mention commands or help
        assert "command" in handler.description.lower() or "help" in handler.description.lower()
        assert "/help" in handler.usage

    def test_help_handler_can_handle(self):
        """HelpHandler.can_handle works correctly."""
        from core.handlers.common import HelpHandler

        handler = HelpHandler()
        assert handler.can_handle("/help") is True
        assert handler.can_handle("/help commands") is True
        assert handler.can_handle("/other") is False
        assert handler.can_handle("help") is False

    @pytest.mark.asyncio
    async def test_help_handler_returns_help_text(self):
        """HelpHandler returns help text from registry."""
        from core.handlers.common import HelpHandler
        from core.handlers.base import MessageContext
        from core.handlers.registry import HandlerRegistry

        HandlerRegistry.reset()
        handler = HelpHandler()

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await handler.handle("/help", ctx)

        assert response.success is True
        assert len(response.message) > 0


class TestStartHandler:
    """Tests for StartHandler."""

    def test_start_handler_properties(self):
        """StartHandler has correct properties."""
        from core.handlers.common import StartHandler

        handler = StartHandler()
        assert handler.command == "start"
        assert "/start" in handler.usage

    def test_start_handler_can_handle(self):
        """StartHandler.can_handle works correctly."""
        from core.handlers.common import StartHandler

        handler = StartHandler()
        assert handler.can_handle("/start") is True
        assert handler.can_handle("/START") is True
        assert handler.can_handle("/other") is False

    @pytest.mark.asyncio
    async def test_start_handler_returns_welcome(self):
        """StartHandler returns welcome message."""
        from core.handlers.common import StartHandler
        from core.handlers.base import MessageContext

        handler = StartHandler()

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await handler.handle("/start", ctx)

        assert response.success is True
        assert len(response.message) > 0


class TestStatusHandler:
    """Tests for StatusHandler."""

    def test_status_handler_properties(self):
        """StatusHandler has correct properties."""
        from core.handlers.common import StatusHandler

        handler = StatusHandler()
        assert handler.command == "status"
        assert "/status" in handler.usage

    def test_status_handler_can_handle(self):
        """StatusHandler.can_handle works correctly."""
        from core.handlers.common import StatusHandler

        handler = StatusHandler()
        assert handler.can_handle("/status") is True
        assert handler.can_handle("/other") is False

    @pytest.mark.asyncio
    async def test_status_handler_returns_status(self):
        """StatusHandler returns system status."""
        from core.handlers.common import StatusHandler
        from core.handlers.base import MessageContext

        handler = StatusHandler()

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await handler.handle("/status", ctx)

        assert response.success is True
        # Status should include some system info
        assert response.data is not None or len(response.message) > 0


class TestPingHandler:
    """Tests for PingHandler."""

    def test_ping_handler_properties(self):
        """PingHandler has correct properties."""
        from core.handlers.common import PingHandler

        handler = PingHandler()
        assert handler.command == "ping"
        assert "/ping" in handler.usage

    def test_ping_handler_can_handle(self):
        """PingHandler.can_handle works correctly."""
        from core.handlers.common import PingHandler

        handler = PingHandler()
        assert handler.can_handle("/ping") is True
        assert handler.can_handle("/pong") is False

    @pytest.mark.asyncio
    async def test_ping_handler_returns_pong(self):
        """PingHandler returns pong response."""
        from core.handlers.common import PingHandler
        from core.handlers.base import MessageContext

        handler = PingHandler()

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await handler.handle("/ping", ctx)

        assert response.success is True
        assert "pong" in response.message.lower()


class TestCommonHandlersRegistration:
    """Tests for registering common handlers."""

    def test_register_common_handlers(self):
        """register_common_handlers adds all common handlers to registry."""
        from core.handlers.common import register_common_handlers
        from core.handlers.registry import HandlerRegistry

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        register_common_handlers(registry)

        assert registry.has_handler("help") is True
        assert registry.has_handler("start") is True
        assert registry.has_handler("status") is True
        assert registry.has_handler("ping") is True

    def test_common_handlers_in_help(self):
        """Common handlers appear in generated help."""
        from core.handlers.common import register_common_handlers
        from core.handlers.registry import HandlerRegistry

        HandlerRegistry.reset()
        registry = HandlerRegistry.instance()

        register_common_handlers(registry)
        help_text = registry.generate_help()

        assert "/help" in help_text
        assert "/start" in help_text
        assert "/status" in help_text
        assert "/ping" in help_text
