"""
Unit tests for the Command Registry system.

Tests the core command infrastructure including:
- Command registration and lookup
- Alias resolution
- Category grouping
- Help text generation
- Context-based execution
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Any


class TestCommandDataclass:
    """Test the Command dataclass."""

    def test_command_creation_minimal(self):
        """Test creating a command with minimal required fields."""
        from core.commands.registry import Command

        cmd = Command(
            name="test",
            description="A test command",
            handler=lambda ctx: None,
            category="core"
        )

        assert cmd.name == "test"
        assert cmd.description == "A test command"
        assert cmd.category == "core"
        assert cmd.aliases == []
        assert cmd.admin_only is False
        assert cmd.args_schema is None
        assert cmd.usage == ""
        assert cmd.examples == []

    def test_command_creation_full(self):
        """Test creating a command with all fields."""
        from core.commands.registry import Command

        async def handler(ctx):
            return "result"

        cmd = Command(
            name="full",
            description="Full command",
            handler=handler,
            category="trading",
            aliases=["f", "fu"],
            admin_only=True,
            args_schema={"token": str, "amount": float},
            usage="/full <token> <amount>",
            examples=["/full SOL 10", "/f BONK 100"]
        )

        assert cmd.name == "full"
        assert cmd.aliases == ["f", "fu"]
        assert cmd.admin_only is True
        assert cmd.args_schema == {"token": str, "amount": float}
        assert cmd.usage == "/full <token> <amount>"
        assert len(cmd.examples) == 2


class TestCommandRegistry:
    """Test the CommandRegistry class."""

    def test_registry_creation(self):
        """Test creating an empty registry."""
        from core.commands.registry import CommandRegistry

        registry = CommandRegistry()

        assert len(registry.list_commands()) == 0
        assert registry.get_command("nonexistent") is None

    def test_register_command(self):
        """Test registering a single command."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()
        cmd = Command(
            name="help",
            description="Show help",
            handler=lambda ctx: "help",
            category="core"
        )

        registry.register(cmd)

        assert registry.get_command("help") is not None
        assert registry.get_command("help").name == "help"
        assert len(registry.list_commands()) == 1

    def test_register_with_aliases(self):
        """Test registering a command with aliases."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()
        cmd = Command(
            name="status",
            description="Show status",
            handler=lambda ctx: "status",
            category="core",
            aliases=["s", "st", "stat"]
        )

        registry.register(cmd)

        # All should resolve to the same command
        assert registry.get_command("status") is not None
        assert registry.get_command("s") is not None
        assert registry.get_command("st") is not None
        assert registry.get_command("stat") is not None

        # Should all return the same command object
        assert registry.get_command("s").name == "status"
        assert registry.get_command("st").name == "status"

    def test_alias_resolution(self):
        """Test alias resolution returns correct command name."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()
        cmd = Command(
            name="portfolio",
            description="Show portfolio",
            handler=lambda ctx: "portfolio",
            category="trading",
            aliases=["p", "port"]
        )

        registry.register(cmd)

        assert registry.resolve_alias("p") == "portfolio"
        assert registry.resolve_alias("port") == "portfolio"
        assert registry.resolve_alias("portfolio") == "portfolio"
        assert registry.resolve_alias("unknown") == "unknown"  # Returns as-is

    def test_list_commands(self):
        """Test listing all commands."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        for i in range(5):
            registry.register(Command(
                name=f"cmd{i}",
                description=f"Command {i}",
                handler=lambda ctx: None,
                category="core"
            ))

        commands = registry.list_commands()
        assert len(commands) == 5
        assert all(cmd.name.startswith("cmd") for cmd in commands)

    def test_list_commands_by_category(self):
        """Test filtering commands by category."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        # Register commands in different categories
        registry.register(Command(
            name="help", description="Help", handler=lambda c: None, category="core"
        ))
        registry.register(Command(
            name="status", description="Status", handler=lambda c: None, category="core"
        ))
        registry.register(Command(
            name="trade", description="Trade", handler=lambda c: None, category="trading"
        ))
        registry.register(Command(
            name="positions", description="Positions", handler=lambda c: None, category="trading"
        ))
        registry.register(Command(
            name="model", description="Model", handler=lambda c: None, category="ai"
        ))

        core_cmds = registry.list_commands(category="core")
        trading_cmds = registry.list_commands(category="trading")
        ai_cmds = registry.list_commands(category="ai")

        assert len(core_cmds) == 2
        assert len(trading_cmds) == 2
        assert len(ai_cmds) == 1

    def test_get_categories(self):
        """Test getting list of all categories."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register(Command(
            name="help", description="Help", handler=lambda c: None, category="core"
        ))
        registry.register(Command(
            name="trade", description="Trade", handler=lambda c: None, category="trading"
        ))
        registry.register(Command(
            name="model", description="Model", handler=lambda c: None, category="ai"
        ))

        categories = registry.get_categories()

        assert "core" in categories
        assert "trading" in categories
        assert "ai" in categories
        assert len(categories) == 3

    def test_duplicate_command_raises_error(self):
        """Test that registering duplicate command raises error."""
        from core.commands.registry import CommandRegistry, Command, CommandAlreadyExistsError

        registry = CommandRegistry()
        cmd1 = Command(name="test", description="Test 1", handler=lambda c: None, category="core")
        cmd2 = Command(name="test", description="Test 2", handler=lambda c: None, category="core")

        registry.register(cmd1)

        with pytest.raises(CommandAlreadyExistsError):
            registry.register(cmd2)

    def test_duplicate_alias_raises_error(self):
        """Test that registering duplicate alias raises error."""
        from core.commands.registry import CommandRegistry, Command, AliasConflictError

        registry = CommandRegistry()
        cmd1 = Command(
            name="help", description="Help", handler=lambda c: None,
            category="core", aliases=["h"]
        )
        cmd2 = Command(
            name="history", description="History", handler=lambda c: None,
            category="core", aliases=["h"]  # Conflict!
        )

        registry.register(cmd1)

        with pytest.raises(AliasConflictError):
            registry.register(cmd2)


class TestCommandExecution:
    """Test command execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """Test executing a simple command."""
        from core.commands.registry import CommandRegistry, Command

        executed = []

        async def handler(ctx):
            executed.append(ctx)
            return "done"

        registry = CommandRegistry()
        registry.register(Command(
            name="test",
            description="Test",
            handler=handler,
            category="core"
        ))

        context = {"user_id": 123, "args": []}
        result = await registry.execute("test", context)

        assert result == "done"
        assert len(executed) == 1
        assert executed[0]["user_id"] == 123

    @pytest.mark.asyncio
    async def test_execute_with_alias(self):
        """Test executing a command via alias."""
        from core.commands.registry import CommandRegistry, Command

        executed = []

        async def handler(ctx):
            executed.append(ctx["command_name"])
            return "done"

        registry = CommandRegistry()
        registry.register(Command(
            name="status",
            description="Status",
            handler=handler,
            category="core",
            aliases=["s", "st"]
        ))

        await registry.execute("s", {"user_id": 123})
        await registry.execute("st", {"user_id": 123})

        assert executed == ["status", "status"]

    @pytest.mark.asyncio
    async def test_execute_nonexistent_command(self):
        """Test executing a nonexistent command raises error."""
        from core.commands.registry import CommandRegistry, CommandNotFoundError

        registry = CommandRegistry()

        with pytest.raises(CommandNotFoundError):
            await registry.execute("nonexistent", {})

    @pytest.mark.asyncio
    async def test_execute_admin_only_command(self):
        """Test that admin-only commands check permissions."""
        from core.commands.registry import CommandRegistry, Command, PermissionDeniedError

        async def handler(ctx):
            return "admin action"

        registry = CommandRegistry()
        registry.register(Command(
            name="admin",
            description="Admin",
            handler=handler,
            category="admin",
            admin_only=True
        ))

        # Non-admin should be denied
        with pytest.raises(PermissionDeniedError):
            await registry.execute("admin", {"user_id": 123, "is_admin": False})

        # Admin should succeed
        result = await registry.execute("admin", {"user_id": 456, "is_admin": True})
        assert result == "admin action"

    @pytest.mark.asyncio
    async def test_execute_with_args(self):
        """Test executing command with arguments."""
        from core.commands.registry import CommandRegistry, Command

        captured_args = []

        async def handler(ctx):
            captured_args.append(ctx.get("args", []))
            return "done"

        registry = CommandRegistry()
        registry.register(Command(
            name="trade",
            description="Trade",
            handler=handler,
            category="trading"
        ))

        await registry.execute("trade", {
            "user_id": 123,
            "args": ["SOL", "10"]
        })

        assert captured_args == [["SOL", "10"]]


class TestHelpGeneration:
    """Test auto-help generation."""

    def test_generate_help_all_commands(self):
        """Test generating help for all commands."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register(Command(
            name="help", description="Show help", handler=lambda c: None,
            category="core", aliases=["h", "?"]
        ))
        registry.register(Command(
            name="status", description="Show status", handler=lambda c: None,
            category="core"
        ))
        registry.register(Command(
            name="trade", description="Execute trade", handler=lambda c: None,
            category="trading"
        ))

        help_text = registry.generate_help()

        # Should have category headers
        assert "Core" in help_text or "core" in help_text.lower()
        assert "Trading" in help_text or "trading" in help_text.lower()

        # Should have command names
        assert "/help" in help_text
        assert "/status" in help_text
        assert "/trade" in help_text

        # Should have descriptions
        assert "Show help" in help_text
        assert "Show status" in help_text

    def test_generate_help_single_command(self):
        """Test generating help for a single command."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register(Command(
            name="trade",
            description="Execute a trade",
            handler=lambda c: None,
            category="trading",
            aliases=["t", "buy"],
            usage="/trade <token> <amount>",
            examples=["/trade SOL 10", "/t BONK 1000"]
        ))

        help_text = registry.generate_help("trade")

        assert "/trade" in help_text
        assert "Execute a trade" in help_text
        assert "/t" in help_text or "t" in help_text
        assert "/buy" in help_text or "buy" in help_text
        assert "/trade <token> <amount>" in help_text
        assert "/trade SOL 10" in help_text

    def test_generate_help_unknown_command(self):
        """Test generating help for unknown command."""
        from core.commands.registry import CommandRegistry

        registry = CommandRegistry()

        help_text = registry.generate_help("unknown")

        assert "unknown" in help_text.lower() or "not found" in help_text.lower()

    def test_help_shows_admin_marker(self):
        """Test that admin-only commands are marked."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register(Command(
            name="config",
            description="Change config",
            handler=lambda c: None,
            category="admin",
            admin_only=True
        ))

        help_text = registry.generate_help()

        # Should indicate admin-only somehow
        assert "admin" in help_text.lower() or "[A]" in help_text or "(admin)" in help_text


class TestDecoratorRegistration:
    """Test the decorator-based registration."""

    def test_decorator_registration(self):
        """Test registering commands via decorator."""
        from core.commands.registry import CommandRegistry

        registry = CommandRegistry()

        @registry.command(
            name="decorated",
            description="A decorated command",
            category="core",
            aliases=["dec"]
        )
        async def decorated_handler(ctx):
            return "decorated result"

        # Command should be registered
        assert registry.get_command("decorated") is not None
        assert registry.get_command("dec") is not None

        # Handler should be the actual function
        assert registry.get_command("decorated").handler == decorated_handler

    def test_decorator_preserves_function(self):
        """Test that decorator preserves the original function."""
        from core.commands.registry import CommandRegistry

        registry = CommandRegistry()

        @registry.command(name="test", description="Test", category="core")
        async def test_func(ctx):
            """Original docstring."""
            return "test"

        # Function should still be callable directly
        assert test_func.__doc__ == "Original docstring."
        assert test_func.__name__ == "test_func"


class TestCommandContext:
    """Test command execution context."""

    @pytest.mark.asyncio
    async def test_context_contains_command_info(self):
        """Test that context is enriched with command info."""
        from core.commands.registry import CommandRegistry, Command

        captured_ctx = None

        async def handler(ctx):
            nonlocal captured_ctx
            captured_ctx = ctx
            return "done"

        registry = CommandRegistry()
        registry.register(Command(
            name="info",
            description="Info",
            handler=handler,
            category="core",
            aliases=["i"]
        ))

        await registry.execute("i", {"user_id": 123})

        # Context should have command info
        assert captured_ctx is not None
        assert captured_ctx.get("command_name") == "info"
        assert captured_ctx.get("invoked_as") == "i"
        assert captured_ctx.get("user_id") == 123


class TestCoreCommands:
    """Test built-in core commands."""

    def test_core_commands_module_exists(self):
        """Test that core commands module exists."""
        from core.commands import core as core_commands

        assert hasattr(core_commands, "register_core_commands")

    def test_core_commands_registration(self):
        """Test registering core commands."""
        from core.commands.registry import CommandRegistry
        from core.commands.core import register_core_commands

        registry = CommandRegistry()
        register_core_commands(registry)

        # Core commands should be registered
        assert registry.get_command("help") is not None
        assert registry.get_command("commands") is not None
        assert registry.get_command("status") is not None
        assert registry.get_command("whoami") is not None


class TestAICommands:
    """Test AI-related commands."""

    def test_ai_commands_module_exists(self):
        """Test that AI commands module exists."""
        from core.commands import ai as ai_commands

        assert hasattr(ai_commands, "register_ai_commands")

    def test_ai_commands_registration(self):
        """Test registering AI commands."""
        from core.commands.registry import CommandRegistry
        from core.commands.ai import register_ai_commands

        registry = CommandRegistry()
        register_ai_commands(registry)

        # AI commands should be registered
        assert registry.get_command("skill") is not None
        assert registry.get_command("model") is not None
        assert registry.get_command("models") is not None
        assert registry.get_command("think") is not None


class TestSessionCommands:
    """Test session management commands."""

    def test_session_commands_module_exists(self):
        """Test that session commands module exists."""
        from core.commands import session as session_commands

        assert hasattr(session_commands, "register_session_commands")

    def test_session_commands_registration(self):
        """Test registering session commands."""
        from core.commands.registry import CommandRegistry
        from core.commands.session import register_session_commands

        registry = CommandRegistry()
        register_session_commands(registry)

        # Session commands should be registered
        assert registry.get_command("compact") is not None
        assert registry.get_command("reset") is not None
        assert registry.get_command("new") is not None


class TestTradingCommands:
    """Test trading-related commands."""

    def test_trading_commands_module_exists(self):
        """Test that trading commands module exists."""
        from core.commands import trading as trading_commands

        assert hasattr(trading_commands, "register_trading_commands")

    def test_trading_commands_registration(self):
        """Test registering trading commands."""
        from core.commands.registry import CommandRegistry
        from core.commands.trading import register_trading_commands

        registry = CommandRegistry()
        register_trading_commands(registry)

        # Trading commands should be registered
        assert registry.get_command("demo") is not None
        assert registry.get_command("trade") is not None
        assert registry.get_command("positions") is not None


class TestCommandRouter:
    """Test the Telegram command router."""

    def test_router_module_exists(self):
        """Test that command router module exists."""
        from tg_bot import command_router

        assert hasattr(command_router, "CommandRouter")

    def test_router_parse_command(self):
        """Test parsing command from message text."""
        from tg_bot.command_router import CommandRouter

        router = CommandRouter()

        # Simple command
        cmd, args = router.parse_message("/help")
        assert cmd == "help"
        assert args == []

        # Command with args
        cmd, args = router.parse_message("/trade SOL 10")
        assert cmd == "trade"
        assert args == ["SOL", "10"]

        # Command with @botname suffix
        cmd, args = router.parse_message("/status@JarvisBot")
        assert cmd == "status"
        assert args == []

        # Non-command message
        cmd, args = router.parse_message("Hello world")
        assert cmd is None
        assert args == []

    @pytest.mark.asyncio
    async def test_router_routes_to_registry(self):
        """Test that router correctly routes to registry."""
        from tg_bot.command_router import CommandRouter
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()
        executed = []

        async def handler(ctx):
            executed.append(ctx)
            return "done"

        registry.register(Command(
            name="test",
            description="Test",
            handler=handler,
            category="core"
        ))

        router = CommandRouter(registry=registry)

        # Create mock update
        mock_update = MagicMock()
        mock_update.message.text = "/test arg1 arg2"
        mock_update.effective_user.id = 123
        mock_update.effective_user.username = "testuser"
        mock_update.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        await router.handle_command(mock_update, mock_context)

        assert len(executed) == 1
        assert executed[0]["args"] == ["arg1", "arg2"]
        assert executed[0]["user_id"] == 123


class TestGlobalRegistry:
    """Test the global registry singleton."""

    def test_get_global_registry(self):
        """Test getting the global registry."""
        from core.commands import get_command_registry

        registry1 = get_command_registry()
        registry2 = get_command_registry()

        # Should return the same instance
        assert registry1 is registry2

    def test_global_registry_has_commands(self):
        """Test that global registry has core commands registered."""
        from core.commands import get_command_registry

        registry = get_command_registry()

        # Should have some core commands
        assert registry.get_command("help") is not None
        assert registry.get_command("status") is not None
