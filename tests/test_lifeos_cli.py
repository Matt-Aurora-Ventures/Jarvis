"""
Tests for LifeOS CLI.

Tests cover:
- Argument parsing
- Command handlers
- Jarvis integration
- Error handling
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifeos.cli import LifeOSCLI, create_parser


# =============================================================================
# Test Argument Parsing
# =============================================================================

class TestArgumentParsing:
    """Test CLI argument parsing."""

    def test_parser_creation(self):
        """Should create parser successfully."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "lifeos"

    def test_start_command(self):
        """Should parse start command."""
        parser = create_parser()
        args = parser.parse_args(["start"])
        assert args.command == "start"

    def test_start_with_foreground(self):
        """Should parse start with foreground flag."""
        parser = create_parser()
        args = parser.parse_args(["start", "-f"])
        assert args.command == "start"
        assert args.foreground is True

    def test_status_command(self):
        """Should parse status command."""
        parser = create_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_status_with_verbose(self):
        """Should parse status with verbose flag."""
        parser = create_parser()
        args = parser.parse_args(["status", "-v"])
        assert args.verbose is True

    def test_status_with_json(self):
        """Should parse status with json flag."""
        parser = create_parser()
        args = parser.parse_args(["status", "--json"])
        assert args.json is True

    def test_chat_command(self):
        """Should parse chat command."""
        parser = create_parser()
        args = parser.parse_args(["chat", "Hello"])
        assert args.command == "chat"
        assert args.message == "Hello"

    def test_chat_with_persona(self):
        """Should parse chat with persona."""
        parser = create_parser()
        args = parser.parse_args(["chat", "-p", "casual", "Hi there"])
        assert args.persona == "casual"
        assert args.message == "Hi there"

    def test_plugin_list(self):
        """Should parse plugin list."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "list"])
        assert args.command == "plugin"
        assert args.plugin_command == "list"

    def test_plugin_enable(self):
        """Should parse plugin enable."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "enable", "trading"])
        assert args.plugin_command == "enable"
        assert args.name == "trading"

    def test_config_get(self):
        """Should parse config get."""
        parser = create_parser()
        args = parser.parse_args(["config", "--get", "general.name"])
        assert args.command == "config"
        assert args.get == "general.name"

    def test_config_set(self):
        """Should parse config set."""
        parser = create_parser()
        args = parser.parse_args(["config", "--set", "general.name", "MyJarvis"])
        assert args.set == ["general.name", "MyJarvis"]

    def test_memory_get(self):
        """Should parse memory get."""
        parser = create_parser()
        args = parser.parse_args(["memory", "get", "test_key"])
        assert args.memory_command == "get"
        assert args.key == "test_key"

    def test_persona_list(self):
        """Should parse persona list."""
        parser = create_parser()
        args = parser.parse_args(["persona", "--list"])
        assert args.command == "persona"
        assert args.list is True

    def test_events_stats(self):
        """Should parse events stats."""
        parser = create_parser()
        args = parser.parse_args(["events", "--stats"])
        assert args.command == "events"
        assert args.stats is True


# =============================================================================
# Test CLI Class
# =============================================================================

class TestLifeOSCLI:
    """Test LifeOS CLI class."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance."""
        return LifeOSCLI()

    @pytest.fixture
    def mock_jarvis(self):
        """Create mock Jarvis instance."""
        jarvis = MagicMock()
        jarvis.is_running = True
        jarvis.start = AsyncMock()
        jarvis.stop = AsyncMock()
        jarvis.chat = AsyncMock(return_value="Hello! How can I help?")
        jarvis.get_stats = MagicMock(return_value={
            "running": True,
            "uptime_seconds": 100,
            "memory": {"entry_count": 5, "namespace_count": 2},
            "events": {"events_emitted": 10, "events_handled": 8, "pattern_count": 3},
            "pae": {"providers": 2, "actions": 3, "evaluators": 1},
        })
        jarvis.list_plugins = MagicMock(return_value=["trading", "telegram"])
        jarvis.list_personas = MagicMock(return_value=["jarvis", "casual", "analyst"])
        jarvis.set_persona = MagicMock(return_value=True)
        jarvis.get_greeting = MagicMock(return_value="Hello, how may I assist you?")
        jarvis.enable_plugin = AsyncMock(return_value=True)
        jarvis.disable_plugin = AsyncMock(return_value=True)
        jarvis.remember = AsyncMock()
        jarvis.recall = AsyncMock(return_value="test_value")
        jarvis.forget = AsyncMock(return_value=True)
        jarvis.event_bus = MagicMock()
        jarvis.event_bus.get_stats = MagicMock(return_value={
            "events_emitted": 10,
            "events_handled": 8,
            "handlers_failed": 0,
            "pattern_count": 3,
            "history_size": 50,
        })
        jarvis.event_bus.get_history = MagicMock(return_value=[])

        mock_persona = MagicMock()
        mock_persona.name = "jarvis"
        mock_persona.description = "AI Assistant"
        mock_persona.voice_description = "Calm and measured"
        mock_persona.traits = set()

        jarvis.persona_manager = MagicMock()
        jarvis.persona_manager.get_active_name = MagicMock(return_value="jarvis")
        jarvis.persona_manager.get_persona = MagicMock(return_value=mock_persona)

        return jarvis

    @pytest.mark.asyncio
    async def test_cmd_start(self, cli, mock_jarvis):
        """Should start LifeOS."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.foreground = False
        args.verbose = False

        result = await cli.cmd_start(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_stop(self, cli, mock_jarvis):
        """Should stop LifeOS."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        result = await cli.cmd_stop(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_status(self, cli, mock_jarvis):
        """Should show status."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.verbose = False
        args.json = False

        result = await cli.cmd_status(args)
        assert result == 0
        mock_jarvis.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_chat_single_message(self, cli, mock_jarvis):
        """Should handle single chat message."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.message = "Hello"
        args.persona = None

        result = await cli.cmd_chat(args)
        assert result == 0
        mock_jarvis.chat.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_cmd_chat_with_persona(self, cli, mock_jarvis):
        """Should use specified persona."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.message = "Hello"
        args.persona = "casual"

        await cli.cmd_chat(args)
        mock_jarvis.set_persona.assert_called_once_with("casual")

    @pytest.mark.asyncio
    async def test_cmd_plugin_list(self, cli, mock_jarvis):
        """Should list plugins."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.plugin_command = "list"

        result = await cli.cmd_plugin(args)
        assert result == 0
        mock_jarvis.list_plugins.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_plugin_enable(self, cli, mock_jarvis):
        """Should enable plugin."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.plugin_command = "enable"
        args.name = "trading"

        result = await cli.cmd_plugin(args)
        assert result == 0
        mock_jarvis.enable_plugin.assert_called_once_with("trading")

    @pytest.mark.asyncio
    async def test_cmd_plugin_disable(self, cli, mock_jarvis):
        """Should disable plugin."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.plugin_command = "disable"
        args.name = "trading"

        result = await cli.cmd_plugin(args)
        assert result == 0
        mock_jarvis.disable_plugin.assert_called_once_with("trading")

    @pytest.mark.asyncio
    async def test_cmd_memory_get(self, cli, mock_jarvis):
        """Should get memory value."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.memory_command = "get"
        args.key = "test_key"

        result = await cli.cmd_memory(args)
        assert result == 0
        mock_jarvis.recall.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cmd_memory_set(self, cli, mock_jarvis):
        """Should set memory value."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.memory_command = "set"
        args.key = "test_key"
        args.value = "test_value"

        result = await cli.cmd_memory(args)
        assert result == 0
        mock_jarvis.remember.assert_called_once_with("test_key", "test_value")

    @pytest.mark.asyncio
    async def test_cmd_memory_forget(self, cli, mock_jarvis):
        """Should forget memory key."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.memory_command = "forget"
        args.key = "test_key"

        result = await cli.cmd_memory(args)
        assert result == 0
        mock_jarvis.forget.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cmd_persona_list(self, cli, mock_jarvis):
        """Should list personas."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.list = True
        args.set = None
        args.info = None

        result = await cli.cmd_persona(args)
        assert result == 0
        mock_jarvis.list_personas.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_persona_set(self, cli, mock_jarvis):
        """Should set persona."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.list = False
        args.set = "casual"
        args.info = None

        result = await cli.cmd_persona(args)
        assert result == 0
        mock_jarvis.set_persona.assert_called_with("casual")

    @pytest.mark.asyncio
    async def test_cmd_events_stats(self, cli, mock_jarvis):
        """Should show event stats."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.stats = True
        args.history = False
        args.pattern = None

        result = await cli.cmd_events(args)
        assert result == 0
        mock_jarvis.event_bus.get_stats.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_events_history(self, cli, mock_jarvis):
        """Should show event history."""
        cli.jarvis = mock_jarvis

        args = MagicMock()
        args.stats = False
        args.history = True
        args.pattern = None

        result = await cli.cmd_events(args)
        assert result == 0
        mock_jarvis.event_bus.get_history.assert_called()

    def test_cmd_version(self, cli):
        """Should show version."""
        args = MagicMock()
        result = cli.cmd_version(args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_run_no_command(self, cli):
        """Should show help when no command."""
        result = await cli.run([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_run_version(self, cli):
        """Should run version command."""
        result = await cli.run(["version"])
        assert result == 0


# =============================================================================
# Test Config Command
# =============================================================================

class TestConfigCommand:
    """Test config command."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance."""
        return LifeOSCLI()

    @pytest.mark.asyncio
    async def test_config_list(self, cli):
        """Should list config."""
        args = MagicMock()
        args.get = None
        args.set = None
        args.list = True

        with patch("lifeos.cli.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.to_dict = MagicMock(return_value={
                "general": {"name": "Jarvis"},
            })
            mock_get_config.return_value = mock_config

            result = await cli.cmd_config(args)
            assert result == 0

    @pytest.mark.asyncio
    async def test_config_get(self, cli):
        """Should get config value."""
        args = MagicMock()
        args.get = "general.name"
        args.set = None
        args.list = False

        with patch("lifeos.cli.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.get = MagicMock(return_value="Jarvis")
            mock_get_config.return_value = mock_config

            result = await cli.cmd_config(args)
            assert result == 0
            mock_config.get.assert_called_with("general.name")

    @pytest.mark.asyncio
    async def test_config_set(self, cli):
        """Should set config value."""
        args = MagicMock()
        args.get = None
        args.set = ["general.name", "MyJarvis"]
        args.list = False

        with patch("lifeos.cli.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            result = await cli.cmd_config(args)
            assert result == 0
            mock_config.set.assert_called_with("general.name", "MyJarvis")
