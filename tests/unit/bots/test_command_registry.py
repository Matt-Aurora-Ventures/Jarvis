"""
Tests for ClawdBots command registry system.

TDD: Write tests first, then implement.
"""

import pytest
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCommandInfo:
    """Tests for CommandInfo data structure."""

    def test_command_info_has_required_fields(self):
        """CommandInfo should have name, description, aliases, handler, enabled, usage_count."""
        from bots.shared.command_registry import CommandInfo

        handler = Mock()
        info = CommandInfo(
            name="test",
            description="Test command",
            handler=handler,
            aliases=["t", "tst"],
        )

        assert info.name == "test"
        assert info.description == "Test command"
        assert info.handler == handler
        assert info.aliases == ["t", "tst"]
        assert info.enabled is True  # Default enabled
        assert info.usage_count == 0  # Default count

    def test_command_info_default_values(self):
        """CommandInfo should have sensible defaults."""
        from bots.shared.command_registry import CommandInfo

        handler = Mock()
        info = CommandInfo(
            name="minimal",
            description="Minimal command",
            handler=handler,
        )

        assert info.aliases == []  # Default empty list
        assert info.enabled is True
        assert info.usage_count == 0

    def test_command_info_to_dict(self):
        """CommandInfo should be serializable to dict."""
        from bots.shared.command_registry import CommandInfo

        handler = Mock()
        info = CommandInfo(
            name="test",
            description="Test command",
            handler=handler,
            aliases=["t"],
            enabled=True,
            usage_count=5,
        )

        d = info.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "Test command"
        assert d["aliases"] == ["t"]
        assert d["enabled"] is True
        assert d["usage_count"] == 5
        assert "handler" not in d  # Handler is not serializable


class TestCommandRegistry:
    """Tests for CommandRegistry class."""

    def test_registry_initialization(self):
        """CommandRegistry should initialize empty."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        assert len(registry.list_commands()) == 0

    def test_register_command(self):
        """register_command should add command to registry."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock()

        registry.register_command(
            name="hello",
            handler=handler,
            description="Say hello",
            aliases=["hi", "hey"],
        )

        assert "hello" in [c.name for c in registry.list_commands()]

    def test_register_command_with_decorator(self):
        """Registry should support decorator syntax."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()

        @registry.command(name="greet", description="Greet user", aliases=["g"])
        def greet_handler():
            return "Hello!"

        assert "greet" in [c.name for c in registry.list_commands()]

    def test_get_command_by_name(self):
        """get_command should return CommandInfo by name."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock()

        registry.register_command("test", handler, "Test command")

        info = registry.get_command("test")
        assert info is not None
        assert info.name == "test"
        assert info.handler == handler

    def test_get_command_by_alias(self):
        """get_command should resolve aliases to primary command."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock()

        registry.register_command("test", handler, "Test command", aliases=["t", "tst"])

        # Get by alias
        info = registry.get_command("t")
        assert info is not None
        assert info.name == "test"  # Returns primary command

        info2 = registry.get_command("tst")
        assert info2 is not None
        assert info2.name == "test"

    def test_get_command_not_found(self):
        """get_command should return None for unknown commands."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()

        info = registry.get_command("nonexistent")
        assert info is None

    def test_list_commands(self):
        """list_commands should return all registered commands."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()

        registry.register_command("cmd1", Mock(), "Command 1")
        registry.register_command("cmd2", Mock(), "Command 2")
        registry.register_command("cmd3", Mock(), "Command 3")

        commands = registry.list_commands()
        names = [c.name for c in commands]

        assert len(commands) == 3
        assert "cmd1" in names
        assert "cmd2" in names
        assert "cmd3" in names

    def test_list_commands_enabled_only(self):
        """list_commands should optionally filter to enabled only."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()

        registry.register_command("enabled_cmd", Mock(), "Enabled")
        registry.register_command("disabled_cmd", Mock(), "Disabled")
        registry.disable_command("disabled_cmd")

        all_commands = registry.list_commands(enabled_only=False)
        enabled_commands = registry.list_commands(enabled_only=True)

        assert len(all_commands) == 2
        assert len(enabled_commands) == 1
        assert enabled_commands[0].name == "enabled_cmd"


class TestCommandExecution:
    """Tests for command execution."""

    def test_execute_command_sync(self):
        """execute_command should call sync handler."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock(return_value="result")

        registry.register_command("test", handler, "Test")

        result = registry.execute_command("test", "arg1", kwarg1="value1")

        handler.assert_called_once_with("arg1", kwarg1="value1")
        assert result == "result"

    @pytest.mark.asyncio
    async def test_execute_command_async(self):
        """execute_command should handle async handlers."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = AsyncMock(return_value="async result")

        registry.register_command("async_test", handler, "Async Test")

        result = await registry.execute_command_async("async_test", "arg1")

        handler.assert_called_once_with("arg1")
        assert result == "async result"

    def test_execute_command_increments_usage(self):
        """execute_command should increment usage_count."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock()

        registry.register_command("counter", handler, "Counter test")

        assert registry.get_command("counter").usage_count == 0

        registry.execute_command("counter")
        assert registry.get_command("counter").usage_count == 1

        registry.execute_command("counter")
        registry.execute_command("counter")
        assert registry.get_command("counter").usage_count == 3

    def test_execute_command_via_alias(self):
        """execute_command should work with aliases."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler = Mock(return_value="aliased")

        registry.register_command("full_name", handler, "Full command", aliases=["fn", "f"])

        result = registry.execute_command("fn")

        handler.assert_called_once()
        assert result == "aliased"

    def test_execute_disabled_command_raises(self):
        """execute_command should raise for disabled commands."""
        from bots.shared.command_registry import CommandRegistry, CommandDisabledError

        registry = CommandRegistry()
        registry.register_command("disabled", Mock(), "Disabled command")
        registry.disable_command("disabled")

        with pytest.raises(CommandDisabledError):
            registry.execute_command("disabled")

    def test_execute_unknown_command_raises(self):
        """execute_command should raise for unknown commands."""
        from bots.shared.command_registry import CommandRegistry, CommandNotFoundError

        registry = CommandRegistry()

        with pytest.raises(CommandNotFoundError):
            registry.execute_command("unknown")


class TestCommandEnableDisable:
    """Tests for command enable/disable functionality."""

    def test_enable_command(self):
        """enable_command should enable a disabled command."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("toggle", Mock(), "Toggle test")
        registry.disable_command("toggle")

        assert registry.get_command("toggle").enabled is False

        registry.enable_command("toggle")

        assert registry.get_command("toggle").enabled is True

    def test_disable_command(self):
        """disable_command should disable an enabled command."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("toggle", Mock(), "Toggle test")

        assert registry.get_command("toggle").enabled is True

        registry.disable_command("toggle")

        assert registry.get_command("toggle").enabled is False

    def test_enable_unknown_command_raises(self):
        """enable_command should raise for unknown commands."""
        from bots.shared.command_registry import CommandRegistry, CommandNotFoundError

        registry = CommandRegistry()

        with pytest.raises(CommandNotFoundError):
            registry.enable_command("unknown")

    def test_disable_unknown_command_raises(self):
        """disable_command should raise for unknown commands."""
        from bots.shared.command_registry import CommandRegistry, CommandNotFoundError

        registry = CommandRegistry()

        with pytest.raises(CommandNotFoundError):
            registry.disable_command("unknown")


class TestCommandStats:
    """Tests for command usage statistics."""

    def test_get_command_stats(self):
        """get_command_stats should return usage statistics."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("popular", Mock(), "Popular command")
        registry.register_command("rare", Mock(), "Rare command")

        # Execute commands
        for _ in range(10):
            registry.execute_command("popular")
        registry.execute_command("rare")

        stats = registry.get_command_stats()

        assert stats["popular"]["usage_count"] == 10
        assert stats["rare"]["usage_count"] == 1
        assert stats["popular"]["enabled"] is True

    def test_stats_include_all_commands(self):
        """get_command_stats should include disabled commands."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("enabled", Mock(), "Enabled")
        registry.register_command("disabled", Mock(), "Disabled")
        registry.disable_command("disabled")

        stats = registry.get_command_stats()

        assert "enabled" in stats
        assert "disabled" in stats
        assert stats["disabled"]["enabled"] is False

    def test_reset_stats(self):
        """reset_stats should clear all usage counts."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("cmd", Mock(), "Command")

        registry.execute_command("cmd")
        registry.execute_command("cmd")
        assert registry.get_command("cmd").usage_count == 2

        registry.reset_stats()

        assert registry.get_command("cmd").usage_count == 0


class TestStatsPersistence:
    """Tests for stats persistence to JSON file."""

    def test_save_stats(self, tmp_path):
        """save_stats should write stats to JSON file."""
        from bots.shared.command_registry import CommandRegistry

        stats_file = tmp_path / "command_stats.json"
        registry = CommandRegistry(stats_file=str(stats_file))

        registry.register_command("cmd1", Mock(), "Command 1")
        registry.execute_command("cmd1")
        registry.execute_command("cmd1")

        registry.save_stats()

        assert stats_file.exists()

        with open(stats_file) as f:
            saved = json.load(f)

        assert "cmd1" in saved
        assert saved["cmd1"]["usage_count"] == 2

    def test_load_stats(self, tmp_path):
        """load_stats should restore stats from JSON file."""
        from bots.shared.command_registry import CommandRegistry

        stats_file = tmp_path / "command_stats.json"

        # Pre-create stats file
        with open(stats_file, "w") as f:
            json.dump({
                "cmd1": {"usage_count": 5, "enabled": True},
                "cmd2": {"usage_count": 10, "enabled": False},
            }, f)

        registry = CommandRegistry(stats_file=str(stats_file))
        registry.register_command("cmd1", Mock(), "Command 1")
        registry.register_command("cmd2", Mock(), "Command 2")

        registry.load_stats()

        assert registry.get_command("cmd1").usage_count == 5
        assert registry.get_command("cmd2").usage_count == 10
        assert registry.get_command("cmd2").enabled is False

    def test_auto_save_on_execute(self, tmp_path):
        """Stats should auto-save after command execution if configured."""
        from bots.shared.command_registry import CommandRegistry

        stats_file = tmp_path / "command_stats.json"
        registry = CommandRegistry(stats_file=str(stats_file), auto_save=True)

        registry.register_command("auto", Mock(), "Auto save test")
        registry.execute_command("auto")

        # Stats should be saved
        assert stats_file.exists()

        with open(stats_file) as f:
            saved = json.load(f)

        assert saved["auto"]["usage_count"] == 1


class TestHelpGeneration:
    """Tests for help/command listing generation."""

    def test_get_help_text(self):
        """get_help_text should return formatted help."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("hello", Mock(), "Say hello", aliases=["hi"])
        registry.register_command("bye", Mock(), "Say goodbye", aliases=["b", "goodbye"])

        help_text = registry.get_help_text()

        assert "hello" in help_text
        assert "Say hello" in help_text
        assert "hi" in help_text
        assert "bye" in help_text
        assert "Say goodbye" in help_text

    def test_get_help_text_excludes_disabled(self):
        """get_help_text should exclude disabled commands by default."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("enabled", Mock(), "Enabled command")
        registry.register_command("disabled", Mock(), "Disabled command")
        registry.disable_command("disabled")

        help_text = registry.get_help_text()

        assert "enabled" in help_text
        assert "disabled" not in help_text

    def test_get_help_text_include_disabled(self):
        """get_help_text should optionally include disabled commands."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("enabled", Mock(), "Enabled command")
        registry.register_command("disabled", Mock(), "Disabled command")
        registry.disable_command("disabled")

        help_text = registry.get_help_text(include_disabled=True)

        assert "enabled" in help_text
        assert "disabled" in help_text


class TestBotIntegration:
    """Tests for bot-specific registry integration."""

    def test_registry_with_bot_name(self):
        """Registry should support bot-specific naming."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry(bot_name="ClawdJarvis")

        assert registry.bot_name == "ClawdJarvis"

    def test_multiple_registries(self):
        """Multiple registries should be independent."""
        from bots.shared.command_registry import CommandRegistry

        jarvis_registry = CommandRegistry(bot_name="Jarvis")
        friday_registry = CommandRegistry(bot_name="Friday")

        jarvis_registry.register_command("jarvis_cmd", Mock(), "Jarvis command")
        friday_registry.register_command("friday_cmd", Mock(), "Friday command")

        assert "jarvis_cmd" in [c.name for c in jarvis_registry.list_commands()]
        assert "friday_cmd" not in [c.name for c in jarvis_registry.list_commands()]

        assert "friday_cmd" in [c.name for c in friday_registry.list_commands()]
        assert "jarvis_cmd" not in [c.name for c in friday_registry.list_commands()]

    def test_global_registry(self):
        """There should be a global registry accessor."""
        from bots.shared.command_registry import get_global_registry, set_global_registry, CommandRegistry

        registry = CommandRegistry(bot_name="Global")
        set_global_registry(registry)

        retrieved = get_global_registry()
        assert retrieved is registry
        assert retrieved.bot_name == "Global"


class TestDuplicateHandling:
    """Tests for handling duplicate command registration."""

    def test_duplicate_name_raises(self):
        """Registering same name twice should raise."""
        from bots.shared.command_registry import CommandRegistry, DuplicateCommandError

        registry = CommandRegistry()
        registry.register_command("dupe", Mock(), "First")

        with pytest.raises(DuplicateCommandError):
            registry.register_command("dupe", Mock(), "Second")

    def test_duplicate_alias_raises(self):
        """Registering conflicting alias should raise."""
        from bots.shared.command_registry import CommandRegistry, DuplicateCommandError

        registry = CommandRegistry()
        registry.register_command("first", Mock(), "First", aliases=["f"])

        with pytest.raises(DuplicateCommandError):
            registry.register_command("second", Mock(), "Second", aliases=["f"])

    def test_alias_conflicts_with_name_raises(self):
        """Alias conflicting with existing name should raise."""
        from bots.shared.command_registry import CommandRegistry, DuplicateCommandError

        registry = CommandRegistry()
        registry.register_command("existing", Mock(), "Existing")

        with pytest.raises(DuplicateCommandError):
            registry.register_command("new", Mock(), "New", aliases=["existing"])

    def test_force_replace(self):
        """force=True should allow replacing commands."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        handler1 = Mock()
        handler2 = Mock()

        registry.register_command("replaceable", handler1, "First")
        registry.register_command("replaceable", handler2, "Second", force=True)

        assert registry.get_command("replaceable").handler == handler2
        assert registry.get_command("replaceable").description == "Second"


class TestUnregister:
    """Tests for unregistering commands."""

    def test_unregister_command(self):
        """unregister_command should remove command from registry."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("removable", Mock(), "Removable")

        assert registry.get_command("removable") is not None

        registry.unregister_command("removable")

        assert registry.get_command("removable") is None

    def test_unregister_removes_aliases(self):
        """unregister_command should also remove aliases."""
        from bots.shared.command_registry import CommandRegistry

        registry = CommandRegistry()
        registry.register_command("cmd", Mock(), "Command", aliases=["c", "command"])

        registry.unregister_command("cmd")

        assert registry.get_command("c") is None
        assert registry.get_command("command") is None

    def test_unregister_unknown_raises(self):
        """unregister_command should raise for unknown commands."""
        from bots.shared.command_registry import CommandRegistry, CommandNotFoundError

        registry = CommandRegistry()

        with pytest.raises(CommandNotFoundError):
            registry.unregister_command("unknown")
