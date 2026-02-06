"""
Unit tests for the extended CommandRegistry functionality.

Tests multi-bot command registration and management:
- register_bot_commands
- get_all_commands
- Enhanced help generation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Any


class TestBotCommandRegistration:
    """Test bot-specific command registration."""

    def test_register_bot_commands_single(self):
        """Test registering commands for a single bot."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        commands = [
            Command(
                name="help",
                description="Show help",
                handler=lambda c: None,
                category="core"
            ),
            Command(
                name="status",
                description="Show status",
                handler=lambda c: None,
                category="core"
            )
        ]

        registry.register_bot_commands("jarvis", commands)

        # Commands should be registered
        assert registry.get_command("help") is not None
        assert registry.get_command("status") is not None

    def test_register_bot_commands_multiple_bots(self):
        """Test registering commands for multiple bots."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        jarvis_commands = [
            Command(
                name="portfolio",
                description="Show portfolio",
                handler=lambda c: None,
                category="trading"
            )
        ]

        clawdmatt_commands = [
            Command(
                name="analyze",
                description="Analyze token",
                handler=lambda c: None,
                category="analysis"
            )
        ]

        registry.register_bot_commands("jarvis", jarvis_commands)
        registry.register_bot_commands("clawdmatt", clawdmatt_commands)

        assert registry.get_command("portfolio") is not None
        assert registry.get_command("analyze") is not None

    def test_register_bot_commands_tracks_bot(self):
        """Test that bot name is tracked with commands."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        commands = [
            Command(
                name="trade",
                description="Execute trade",
                handler=lambda c: None,
                category="trading"
            )
        ]

        registry.register_bot_commands("jarvis", commands)

        # Should be able to query by bot
        jarvis_cmds = registry.list_commands(bot_name="jarvis")
        assert len(jarvis_cmds) == 1
        assert jarvis_cmds[0].name == "trade"

    def test_register_bot_commands_with_prefix(self):
        """Test registering bot commands with namespace prefix."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        commands = [
            Command(
                name="help",
                description="Show help",
                handler=lambda c: None,
                category="core"
            )
        ]

        # Register with prefix to avoid conflicts
        registry.register_bot_commands("clawdmatt", commands, prefix="cm_")

        assert registry.get_command("cm_help") is not None
        assert registry.get_command("help") is None


class TestGetAllCommands:
    """Test get_all_commands method."""

    def test_get_all_commands_empty(self):
        """Test get_all_commands on empty registry."""
        from core.commands.registry import CommandRegistry

        registry = CommandRegistry()

        all_cmds = registry.get_all_commands()

        assert all_cmds == {}

    def test_get_all_commands_grouped_by_bot(self):
        """Test get_all_commands returns commands grouped by bot."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core"),
            Command(name="trade", description="Trade", handler=lambda c: None, category="trading")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze", handler=lambda c: None, category="ai")
        ])

        all_cmds = registry.get_all_commands()

        assert "jarvis" in all_cmds
        assert "clawdmatt" in all_cmds
        assert len(all_cmds["jarvis"]) == 2
        assert len(all_cmds["clawdmatt"]) == 1

    def test_get_all_commands_includes_global(self):
        """Test get_all_commands includes global commands."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        # Global command (no bot specified)
        registry.register(Command(
            name="version",
            description="Show version",
            handler=lambda c: None,
            category="core"
        ))

        # Bot-specific command
        registry.register_bot_commands("jarvis", [
            Command(name="trade", description="Trade", handler=lambda c: None, category="trading")
        ])

        all_cmds = registry.get_all_commands()

        assert "_global" in all_cmds or "global" in all_cmds
        assert "jarvis" in all_cmds


class TestEnhancedHelpGeneration:
    """Test enhanced help generation for multi-bot support."""

    def test_generate_help_by_bot(self):
        """Test generating help for specific bot."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Show help", handler=lambda c: None, category="core"),
            Command(name="trade", description="Execute trade", handler=lambda c: None, category="trading")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze token", handler=lambda c: None, category="ai")
        ])

        help_text = registry.generate_help(bot_name="jarvis")

        assert "/help" in help_text
        assert "/trade" in help_text
        assert "/analyze" not in help_text  # Not in jarvis

    def test_generate_help_all_bots(self):
        """Test generating help for all bots."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="trade", description="Execute trade", handler=lambda c: None, category="trading")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze token", handler=lambda c: None, category="ai")
        ])

        help_text = registry.generate_help()

        assert "/trade" in help_text
        assert "/analyze" in help_text
        # Should have bot sections
        assert "jarvis" in help_text.lower() or "Jarvis" in help_text
        assert "clawdmatt" in help_text.lower() or "Clawdmatt" in help_text

    def test_generate_help_formatted(self):
        """Test help generation with formatting options."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(
                name="trade",
                description="Execute trade",
                handler=lambda c: None,
                category="trading",
                usage="/trade <token> <amount>",
                examples=["/trade SOL 10"]
            )
        ])

        # Markdown format
        help_md = registry.generate_help(format="markdown")
        assert "**" in help_md or "#" in help_md  # Has markdown formatting

        # Plain text format
        help_text = registry.generate_help(format="text")
        assert "**" not in help_text

    def test_generate_help_includes_aliases(self):
        """Test help includes command aliases."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register(Command(
            name="trade",
            description="Execute trade",
            handler=lambda c: None,
            category="trading",
            aliases=["t", "buy"]
        ))

        help_text = registry.generate_help()

        # Aliases should be mentioned
        assert "t" in help_text or "/t" in help_text
        assert "buy" in help_text or "/buy" in help_text


class TestCommandConflictHandling:
    """Test handling of command name conflicts."""

    def test_bot_command_conflict_raises(self):
        """Test that conflicting bot commands raise error by default."""
        from core.commands.registry import CommandRegistry, Command, CommandAlreadyExistsError

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Jarvis help", handler=lambda c: None, category="core")
        ])

        with pytest.raises(CommandAlreadyExistsError):
            registry.register_bot_commands("clawdmatt", [
                Command(name="help", description="Clawdmatt help", handler=lambda c: None, category="core")
            ])

    def test_bot_command_conflict_with_override(self):
        """Test that conflicts can be allowed with override flag."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Jarvis help", handler=lambda c: None, category="core")
        ])

        # Allow override
        registry.register_bot_commands("clawdmatt", [
            Command(name="help", description="Clawdmatt help", handler=lambda c: None, category="core")
        ], allow_override=True)

        # Latest registration wins
        cmd = registry.get_command("help")
        assert "Clawdmatt" in cmd.description

    def test_list_command_conflicts(self):
        """Test listing potential command conflicts."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core"),
            Command(name="status", description="Status", handler=lambda c: None, category="core")
        ])

        # Check if new commands would conflict
        potential_conflicts = registry.check_conflicts([
            Command(name="help", description="New help", handler=lambda c: None, category="core"),
            Command(name="new_cmd", description="New cmd", handler=lambda c: None, category="core")
        ])

        assert "help" in potential_conflicts
        assert "new_cmd" not in potential_conflicts


class TestBotMetadata:
    """Test bot metadata tracking."""

    def test_get_registered_bots(self):
        """Test getting list of registered bots."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze", handler=lambda c: None, category="ai")
        ])

        bots = registry.get_registered_bots()

        assert "jarvis" in bots
        assert "clawdmatt" in bots
        assert len(bots) == 2

    def test_get_bot_command_count(self):
        """Test getting command count per bot."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core"),
            Command(name="status", description="Status", handler=lambda c: None, category="core"),
            Command(name="trade", description="Trade", handler=lambda c: None, category="trading")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze", handler=lambda c: None, category="ai")
        ])

        assert registry.get_bot_command_count("jarvis") == 3
        assert registry.get_bot_command_count("clawdmatt") == 1
        assert registry.get_bot_command_count("unknown") == 0

    def test_unregister_bot_commands(self):
        """Test unregistering all commands for a bot."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core"),
            Command(name="trade", description="Trade", handler=lambda c: None, category="trading")
        ])

        assert registry.get_command("help") is not None

        registry.unregister_bot_commands("jarvis")

        assert registry.get_command("help") is None
        assert registry.get_command("trade") is None
        assert "jarvis" not in registry.get_registered_bots()


class TestRegistrySingleton:
    """Test registry singleton behavior with multiple bots."""

    def test_shared_registry_across_bots(self):
        """Test that singleton registry is shared across bots."""
        from core.commands.registry import CommandRegistry, Command

        # Get singleton (or create one for testing)
        registry1 = CommandRegistry()
        registry2 = registry1  # Same instance

        registry1.register_bot_commands("bot1", [
            Command(name="cmd1", description="Cmd 1", handler=lambda c: None, category="core")
        ])

        # Should be visible from registry2
        assert registry2.get_command("cmd1") is not None

    def test_registry_reset_clears_all_bots(self):
        """Test that registry reset clears all bot commands."""
        from core.commands.registry import CommandRegistry, Command

        registry = CommandRegistry()

        registry.register_bot_commands("jarvis", [
            Command(name="help", description="Help", handler=lambda c: None, category="core")
        ])

        registry.register_bot_commands("clawdmatt", [
            Command(name="analyze", description="Analyze", handler=lambda c: None, category="ai")
        ])

        registry.clear()

        assert len(registry.list_commands()) == 0
        assert len(registry.get_registered_bots()) == 0
