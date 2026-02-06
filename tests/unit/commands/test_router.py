"""
Unit tests for the CommandRouter system.

Tests the command routing infrastructure including:
- Pattern registration (regex, prefix)
- Route matching and handler resolution
- Command info retrieval
"""

import pytest
import re
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, Optional, Callable


class TestCommandRouterCreation:
    """Test CommandRouter instantiation."""

    def test_router_creation_empty(self):
        """Test creating an empty router."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        assert router is not None
        assert router.get_commands() == []

    def test_router_creation_with_prefix(self):
        """Test creating a router with a custom prefix."""
        from core.commands.router import CommandRouter

        router = CommandRouter(prefix="/")

        assert router.prefix == "/"

    def test_router_creation_default_prefix(self):
        """Test router has default prefix of '/'."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        assert router.prefix == "/"


class TestPatternRegistration:
    """Test pattern registration."""

    def test_register_simple_pattern(self):
        """Test registering a simple command pattern."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("help", handler)

        assert len(router.get_commands()) == 1

    def test_register_regex_pattern(self):
        """Test registering a regex pattern."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register(r"trade\s+(\w+)\s+(\d+)", handler, is_regex=True)

        commands = router.get_commands()
        assert len(commands) == 1
        assert commands[0].is_regex is True

    def test_register_with_description(self):
        """Test registering with metadata."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register(
            "status",
            handler,
            description="Show system status",
            category="core"
        )

        commands = router.get_commands()
        assert commands[0].description == "Show system status"
        assert commands[0].category == "core"

    def test_register_multiple_patterns(self):
        """Test registering multiple patterns."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler1(ctx):
            return "1"

        async def handler2(ctx):
            return "2"

        router.register("help", handler1)
        router.register("status", handler2)

        assert len(router.get_commands()) == 2

    def test_register_with_priority(self):
        """Test pattern priority for ordering."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("low", handler, priority=1)
        router.register("high", handler, priority=10)
        router.register("medium", handler, priority=5)

        commands = router.get_commands()
        # Higher priority should come first
        assert commands[0].pattern == "high"
        assert commands[1].pattern == "medium"
        assert commands[2].pattern == "low"


class TestRouteMatching:
    """Test route matching logic."""

    def test_route_exact_match(self):
        """Test routing with exact prefix match."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "help"

        router.register("help", handler)

        result = router.route("/help")

        assert result is not None
        assert result.handler == handler

    def test_route_with_args(self):
        """Test routing command with arguments."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "trade"

        router.register("trade", handler)

        result = router.route("/trade SOL 10")

        assert result is not None
        assert result.handler == handler

    def test_route_regex_pattern(self):
        """Test routing with regex pattern."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "matched"

        # Pattern to match "buy <token>" or "sell <token>"
        router.register(r"(buy|sell)\s+(\w+)", handler, is_regex=True)

        result = router.route("/buy SOL")
        assert result is not None

        result = router.route("/sell BONK")
        assert result is not None

    def test_route_no_match(self):
        """Test routing returns None when no match."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("help", handler)

        result = router.route("/unknown")

        assert result is None

    def test_route_without_prefix(self):
        """Test routing message without command prefix."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("help", handler)

        result = router.route("help")  # No "/" prefix

        assert result is None

    def test_route_case_insensitive(self):
        """Test routing is case insensitive by default."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("help", handler)

        assert router.route("/HELP") is not None
        assert router.route("/Help") is not None
        assert router.route("/help") is not None

    def test_route_case_sensitive(self):
        """Test routing can be case sensitive."""
        from core.commands.router import CommandRouter

        router = CommandRouter(case_sensitive=True)

        async def handler(ctx):
            return "handled"

        router.register("Help", handler)

        assert router.route("/Help") is not None
        assert router.route("/help") is None
        assert router.route("/HELP") is None

    def test_route_first_match_wins(self):
        """Test that first matching pattern wins."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler1(ctx):
            return "1"

        async def handler2(ctx):
            return "2"

        router.register("trade", handler1, priority=10)
        router.register(r"trade.*", handler2, is_regex=True, priority=5)

        result = router.route("/trade SOL")

        # Higher priority handler should win
        assert result.handler == handler1

    def test_route_with_bot_mention(self):
        """Test routing command with @botname suffix."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("status", handler)

        result = router.route("/status@JarvisBot")

        assert result is not None


class TestRouteResult:
    """Test RouteResult object."""

    def test_route_result_contains_handler(self):
        """Test RouteResult contains the handler."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def my_handler(ctx):
            return "done"

        router.register("test", my_handler)

        result = router.route("/test")

        assert result.handler == my_handler

    def test_route_result_contains_pattern(self):
        """Test RouteResult contains matched pattern."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "done"

        router.register("test", handler)

        result = router.route("/test")

        assert result.pattern == "test"

    def test_route_result_contains_match_groups(self):
        """Test RouteResult contains regex match groups."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "done"

        router.register(r"trade\s+(\w+)\s+(\d+)", handler, is_regex=True)

        result = router.route("/trade SOL 100")

        assert result.groups == ("SOL", "100")

    def test_route_result_contains_raw_message(self):
        """Test RouteResult contains the raw message."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "done"

        router.register("test", handler)

        result = router.route("/test arg1 arg2")

        assert result.raw_message == "/test arg1 arg2"


class TestGetCommands:
    """Test get_commands method."""

    def test_get_commands_returns_all(self):
        """Test get_commands returns all registered commands."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def h1(ctx):
            pass

        async def h2(ctx):
            pass

        router.register("cmd1", h1, description="Command 1")
        router.register("cmd2", h2, description="Command 2")

        commands = router.get_commands()

        assert len(commands) == 2
        patterns = [c.pattern for c in commands]
        assert "cmd1" in patterns
        assert "cmd2" in patterns

    def test_get_commands_filter_by_category(self):
        """Test filtering commands by category."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            pass

        router.register("help", handler, category="core")
        router.register("trade", handler, category="trading")
        router.register("status", handler, category="core")

        core_cmds = router.get_commands(category="core")
        trading_cmds = router.get_commands(category="trading")

        assert len(core_cmds) == 2
        assert len(trading_cmds) == 1

    def test_command_info_contains_metadata(self):
        """Test CommandInfo contains all metadata."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            pass

        router.register(
            "test",
            handler,
            description="Test command",
            category="testing",
            is_regex=False,
            priority=5
        )

        commands = router.get_commands()
        cmd = commands[0]

        assert cmd.pattern == "test"
        assert cmd.description == "Test command"
        assert cmd.category == "testing"
        assert cmd.is_regex is False
        assert cmd.priority == 5


class TestRouterDecorator:
    """Test decorator-based registration."""

    def test_register_via_decorator(self):
        """Test registering handler via decorator."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        @router.command("greet", description="Greet user")
        async def greet_handler(ctx):
            return "Hello!"

        assert len(router.get_commands()) == 1
        assert router.route("/greet") is not None

    def test_decorator_preserves_function(self):
        """Test decorator preserves original function."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        @router.command("test")
        async def test_handler(ctx):
            """Original docstring."""
            return "test"

        assert test_handler.__doc__ == "Original docstring."
        assert test_handler.__name__ == "test_handler"


class TestRouterIntegration:
    """Integration tests for router."""

    @pytest.mark.asyncio
    async def test_full_routing_workflow(self):
        """Test complete routing workflow."""
        from core.commands.router import CommandRouter

        router = CommandRouter()
        executed = []

        async def help_handler(ctx):
            executed.append(("help", ctx))
            return "Help text"

        async def trade_handler(ctx):
            executed.append(("trade", ctx))
            return "Trade executed"

        router.register("help", help_handler)
        router.register("trade", trade_handler)

        # Route and execute help
        result = router.route("/help")
        assert result is not None
        response = await result.handler({})
        assert response == "Help text"

        # Route and execute trade
        result = router.route("/trade SOL 10")
        assert result is not None
        response = await result.handler({})
        assert response == "Trade executed"

        assert len(executed) == 2

    def test_router_with_custom_prefix(self):
        """Test router with custom command prefix."""
        from core.commands.router import CommandRouter

        router = CommandRouter(prefix="!")

        async def handler(ctx):
            return "handled"

        router.register("help", handler)

        assert router.route("!help") is not None
        assert router.route("/help") is None

    def test_router_unregister(self):
        """Test unregistering a command."""
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def handler(ctx):
            return "handled"

        router.register("test", handler)
        assert router.route("/test") is not None

        router.unregister("test")
        assert router.route("/test") is None
        assert len(router.get_commands()) == 0
