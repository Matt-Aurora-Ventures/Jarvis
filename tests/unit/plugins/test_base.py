"""Tests for core/plugins/base.py - Plugin base classes."""

import pytest
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
from unittest.mock import AsyncMock, MagicMock


class TestPluginBase:
    """Tests for the Plugin abstract base class."""

    def test_plugin_has_required_properties(self):
        """Plugin should have name, version, description properties."""
        from core.plugins.base import Plugin

        # Check abstract properties exist
        assert hasattr(Plugin, "name")
        assert hasattr(Plugin, "version")
        assert hasattr(Plugin, "description")

    def test_plugin_has_lifecycle_methods(self):
        """Plugin should have on_load and on_unload methods."""
        from core.plugins.base import Plugin

        assert hasattr(Plugin, "on_load")
        assert hasattr(Plugin, "on_unload")

    def test_plugin_has_get_commands_method(self):
        """Plugin should have get_commands returning List[Command]."""
        from core.plugins.base import Plugin

        assert hasattr(Plugin, "get_commands")

    def test_plugin_has_get_handlers_method(self):
        """Plugin should have get_handlers returning List[Handler]."""
        from core.plugins.base import Plugin

        assert hasattr(Plugin, "get_handlers")


class TestConcretePlugin:
    """Tests using a concrete plugin implementation."""

    @pytest.fixture
    def sample_plugin(self):
        """Create a sample plugin for testing."""
        from core.plugins.base import Plugin, Command, Handler

        class SamplePlugin(Plugin):
            @property
            def name(self) -> str:
                return "sample_plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "A sample plugin for testing"

            async def on_load(self) -> bool:
                self._loaded = True
                return True

            async def on_unload(self) -> bool:
                self._loaded = False
                return True

            def get_commands(self) -> List[Command]:
                return [
                    Command(
                        name="sample_cmd",
                        description="Sample command",
                        handler=self._handle_sample,
                    )
                ]

            def get_handlers(self) -> List[Handler]:
                return [
                    Handler(
                        event_type="message",
                        handler=self._handle_message,
                    )
                ]

            async def _handle_sample(self, args: List[str]) -> str:
                return f"Sample response: {args}"

            async def _handle_message(self, data: Dict[str, Any]) -> Optional[Any]:
                return {"handled": True}

        return SamplePlugin()

    @pytest.mark.asyncio
    async def test_plugin_on_load(self, sample_plugin):
        """Plugin on_load should be callable and return bool."""
        result = await sample_plugin.on_load()
        assert result is True
        assert sample_plugin._loaded is True

    @pytest.mark.asyncio
    async def test_plugin_on_unload(self, sample_plugin):
        """Plugin on_unload should be callable and return bool."""
        await sample_plugin.on_load()
        result = await sample_plugin.on_unload()
        assert result is True
        assert sample_plugin._loaded is False

    def test_plugin_get_commands_returns_list(self, sample_plugin):
        """get_commands should return list of Command objects."""
        from core.plugins.base import Command

        commands = sample_plugin.get_commands()
        assert isinstance(commands, list)
        assert len(commands) == 1
        assert isinstance(commands[0], Command)
        assert commands[0].name == "sample_cmd"

    def test_plugin_get_handlers_returns_list(self, sample_plugin):
        """get_handlers should return list of Handler objects."""
        from core.plugins.base import Handler

        handlers = sample_plugin.get_handlers()
        assert isinstance(handlers, list)
        assert len(handlers) == 1
        assert isinstance(handlers[0], Handler)
        assert handlers[0].event_type == "message"


class TestCommand:
    """Tests for the Command dataclass."""

    def test_command_creation(self):
        """Command should be creatable with required fields."""
        from core.plugins.base import Command

        async def handler(args):
            return "response"

        cmd = Command(name="test", description="Test command", handler=handler)
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert cmd.handler is handler

    def test_command_optional_fields(self):
        """Command should support optional fields."""
        from core.plugins.base import Command

        async def handler(args):
            return "response"

        cmd = Command(
            name="test",
            description="Test command",
            handler=handler,
            aliases=["t", "tst"],
            usage="test <arg>",
            examples=["test foo", "test bar"],
        )
        assert cmd.aliases == ["t", "tst"]
        assert cmd.usage == "test <arg>"
        assert cmd.examples == ["test foo", "test bar"]


class TestHandler:
    """Tests for the Handler dataclass."""

    def test_handler_creation(self):
        """Handler should be creatable with required fields."""
        from core.plugins.base import Handler

        async def handler(data):
            return {"handled": True}

        h = Handler(event_type="message", handler=handler)
        assert h.event_type == "message"
        assert h.handler is handler

    def test_handler_optional_priority(self):
        """Handler should support optional priority field."""
        from core.plugins.base import Handler

        async def handler(data):
            return None

        h = Handler(event_type="error", handler=handler, priority=10)
        assert h.priority == 10

    def test_handler_default_priority(self):
        """Handler should have default priority of 0."""
        from core.plugins.base import Handler

        async def handler(data):
            return None

        h = Handler(event_type="error", handler=handler)
        assert h.priority == 0
