"""
Tests for core/handlers/decorators.py - Command decorators.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any
import asyncio


class TestCommandDecorator:
    """Tests for @command decorator."""

    def test_command_decorator_creates_handler(self):
        """@command decorator creates a CommandHandler class."""
        from core.handlers.decorators import command
        from core.handlers.base import CommandHandler, Response

        @command(name="greet", description="Greet someone")
        async def greet_handler(message: Any, context: Any) -> Response:
            return Response.ok("Hello!")

        # The decorator should produce a handler class instance
        assert isinstance(greet_handler, CommandHandler)
        assert greet_handler.command == "greet"
        assert greet_handler.description == "Greet someone"

    def test_command_decorator_with_usage(self):
        """@command decorator accepts usage parameter."""
        from core.handlers.decorators import command
        from core.handlers.base import Response

        @command(name="add", description="Add numbers", usage="/add <a> <b>")
        async def add_handler(message: Any, context: Any) -> Response:
            return Response.ok("Result")

        assert add_handler.usage == "/add <a> <b>"

    def test_command_decorator_default_usage(self):
        """@command decorator generates default usage from name."""
        from core.handlers.decorators import command
        from core.handlers.base import Response

        @command(name="test", description="Test command")
        async def test_handler(message: Any, context: Any) -> Response:
            return Response.ok("OK")

        assert test_handler.usage == "/test"

    @pytest.mark.asyncio
    async def test_command_decorator_preserves_function(self):
        """Decorated function is callable and works correctly."""
        from core.handlers.decorators import command
        from core.handlers.base import Response, MessageContext

        @command(name="echo", description="Echo message")
        async def echo_handler(message: str, context: MessageContext) -> Response:
            return Response.ok(f"Echo: {message}")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await echo_handler.handle("Hello", ctx)

        assert response.success is True
        assert response.message == "Echo: Hello"


class TestAdminOnlyDecorator:
    """Tests for @admin_only decorator."""

    @pytest.mark.asyncio
    async def test_admin_only_allows_admin(self):
        """@admin_only allows admin users."""
        from core.handlers.decorators import command, admin_only
        from core.handlers.base import Response, MessageContext

        @command(name="secret", description="Secret command")
        @admin_only
        async def secret_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("Secret data")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test", is_admin=True)
        response = await secret_handler.handle("secret", ctx)

        assert response.success is True
        assert response.message == "Secret data"

    @pytest.mark.asyncio
    async def test_admin_only_rejects_non_admin(self):
        """@admin_only rejects non-admin users."""
        from core.handlers.decorators import command, admin_only
        from core.handlers.base import Response, MessageContext

        @command(name="restricted", description="Restricted command")
        @admin_only
        async def restricted_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("Restricted data")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test", is_admin=False)
        response = await restricted_handler.handle("restricted", ctx)

        assert response.success is False
        assert "admin" in response.message.lower() or "permission" in response.message.lower()


class TestRateLimitedDecorator:
    """Tests for @rate_limited decorator."""

    @pytest.mark.asyncio
    async def test_rate_limited_allows_within_limit(self):
        """@rate_limited allows calls within the limit."""
        from core.handlers.decorators import command, rate_limited
        from core.handlers.base import Response, MessageContext

        @command(name="frequent", description="Frequent command")
        @rate_limited(calls=5, period=60)
        async def frequent_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("OK")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")

        # First 5 calls should succeed
        for i in range(5):
            response = await frequent_handler.handle("test", ctx)
            assert response.success is True

    @pytest.mark.asyncio
    async def test_rate_limited_rejects_over_limit(self):
        """@rate_limited rejects calls over the limit."""
        from core.handlers.decorators import command, rate_limited
        from core.handlers.base import Response, MessageContext

        # Use a unique handler name to avoid state from other tests
        @command(name="limited_unique", description="Limited command")
        @rate_limited(calls=2, period=60)
        async def limited_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("OK")

        ctx = MessageContext(user_id=999, chat_id=2, platform="test")  # Unique user

        # First 2 calls should succeed
        for i in range(2):
            response = await limited_handler.handle("test", ctx)
            assert response.success is True

        # 3rd call should be rate limited
        response = await limited_handler.handle("test", ctx)
        assert response.success is False
        assert "rate" in response.message.lower() or "limit" in response.message.lower()

    @pytest.mark.asyncio
    async def test_rate_limited_per_user(self):
        """@rate_limited tracks limits per user."""
        from core.handlers.decorators import command, rate_limited
        from core.handlers.base import Response, MessageContext

        @command(name="peruser", description="Per-user limited")
        @rate_limited(calls=1, period=60)
        async def peruser_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("OK")

        ctx1 = MessageContext(user_id=1001, chat_id=2, platform="test")
        ctx2 = MessageContext(user_id=1002, chat_id=2, platform="test")

        # User 1 can make a call
        response1 = await peruser_handler.handle("test", ctx1)
        assert response1.success is True

        # User 2 can also make a call (different user)
        response2 = await peruser_handler.handle("test", ctx2)
        assert response2.success is True

        # User 1's second call should be limited
        response3 = await peruser_handler.handle("test", ctx1)
        assert response3.success is False


class TestRequireArgsDecorator:
    """Tests for @require_args decorator."""

    @pytest.mark.asyncio
    async def test_require_args_with_enough_args(self):
        """@require_args allows when enough args are provided."""
        from core.handlers.decorators import command, require_args
        from core.handlers.base import Response, MessageContext

        @command(name="add", description="Add numbers")
        @require_args(count=2)
        async def add_handler(message: str, context: MessageContext) -> Response:
            parts = message.split()
            # Skip command name if present
            args = [p for p in parts if not p.startswith('/')]
            return Response.ok(f"Sum: {int(args[0]) + int(args[1])}")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await add_handler.handle("/add 5 3", ctx)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_require_args_rejects_insufficient(self):
        """@require_args rejects when not enough args are provided."""
        from core.handlers.decorators import command, require_args
        from core.handlers.base import Response, MessageContext

        @command(name="subtract", description="Subtract numbers")
        @require_args(count=2)
        async def subtract_handler(message: str, context: MessageContext) -> Response:
            return Response.ok("OK")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await subtract_handler.handle("/subtract 5", ctx)  # Only 1 arg

        assert response.success is False
        assert "argument" in response.message.lower() or "usage" in response.message.lower()

    @pytest.mark.asyncio
    async def test_require_args_with_zero(self):
        """@require_args(0) allows commands with no args."""
        from core.handlers.decorators import command, require_args
        from core.handlers.base import Response, MessageContext

        @command(name="noargs", description="No args needed")
        @require_args(count=0)
        async def noargs_handler(message: str, context: MessageContext) -> Response:
            return Response.ok("No args OK")

        ctx = MessageContext(user_id=1, chat_id=2, platform="test")
        response = await noargs_handler.handle("/noargs", ctx)

        assert response.success is True


class TestDecoratorCombinations:
    """Tests for combining multiple decorators."""

    @pytest.mark.asyncio
    async def test_admin_only_and_rate_limited(self):
        """@admin_only and @rate_limited can be combined."""
        from core.handlers.decorators import command, admin_only, rate_limited
        from core.handlers.base import Response, MessageContext

        @command(name="combo", description="Combined decorators")
        @admin_only
        @rate_limited(calls=10, period=60)
        async def combo_handler(message: Any, context: MessageContext) -> Response:
            return Response.ok("Combo OK")

        admin_ctx = MessageContext(user_id=2001, chat_id=2, platform="test", is_admin=True)
        user_ctx = MessageContext(user_id=2002, chat_id=2, platform="test", is_admin=False)

        # Admin should succeed
        response1 = await combo_handler.handle("test", admin_ctx)
        assert response1.success is True

        # Non-admin should fail
        response2 = await combo_handler.handle("test", user_ctx)
        assert response2.success is False

    @pytest.mark.asyncio
    async def test_require_args_and_admin_only(self):
        """@require_args and @admin_only can be combined."""
        from core.handlers.decorators import command, admin_only, require_args
        from core.handlers.base import Response, MessageContext

        @command(name="adminargs", description="Admin with args")
        @admin_only
        @require_args(count=1)
        async def adminargs_handler(message: str, context: MessageContext) -> Response:
            return Response.ok("Admin args OK")

        admin_ctx = MessageContext(user_id=3001, chat_id=2, platform="test", is_admin=True)

        # Admin with args should succeed
        response1 = await adminargs_handler.handle("/adminargs value", admin_ctx)
        assert response1.success is True

        # Admin without args should fail (require_args check)
        response2 = await adminargs_handler.handle("/adminargs", admin_ctx)
        assert response2.success is False
