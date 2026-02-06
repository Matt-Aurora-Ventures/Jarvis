"""Tests for core/plugins/registry.py - Plugin registry singleton."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPluginRegistry:
    """Tests for the PluginRegistry singleton class."""

    def test_registry_is_singleton(self):
        """PluginRegistry should be a singleton."""
        from core.plugins.registry import PluginRegistry

        registry1 = PluginRegistry.get_instance()
        registry2 = PluginRegistry.get_instance()

        assert registry1 is registry2

    def test_registry_initialization(self):
        """PluginRegistry should initialize with empty state."""
        from core.plugins.registry import PluginRegistry

        # Reset for clean test
        PluginRegistry._instance = None
        registry = PluginRegistry.get_instance()

        assert registry.list_plugins() == []

    @pytest.fixture
    def clean_registry(self):
        """Provide a clean registry for each test."""
        from core.plugins.registry import PluginRegistry

        # Reset singleton
        PluginRegistry._instance = None
        registry = PluginRegistry.get_instance()
        yield registry
        # Cleanup
        PluginRegistry._instance = None

    @pytest.fixture
    def mock_plugin(self):
        """Create a mock plugin."""
        from core.plugins.base import Plugin, Command, Handler

        class MockPlugin(Plugin):
            @property
            def name(self) -> str:
                return "mock_plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Mock plugin for testing"

            async def on_load(self) -> bool:
                return True

            async def on_unload(self) -> bool:
                return True

            def get_commands(self):
                return []

            def get_handlers(self):
                return []

        return MockPlugin()

    def test_register_plugin(self, clean_registry, mock_plugin):
        """register should add a plugin to the registry."""
        clean_registry.register(mock_plugin)

        assert "mock_plugin" in [p.name for p in clean_registry.list_plugins()]

    def test_register_duplicate_plugin(self, clean_registry, mock_plugin):
        """register should handle duplicate plugins."""
        from core.plugins.registry import PluginAlreadyRegisteredError

        clean_registry.register(mock_plugin)

        with pytest.raises(PluginAlreadyRegisteredError):
            clean_registry.register(mock_plugin)

    def test_register_with_replace(self, clean_registry, mock_plugin):
        """register with replace=True should replace existing plugin."""
        clean_registry.register(mock_plugin)

        # Modify and re-register
        mock_plugin._test_marker = "replaced"
        clean_registry.register(mock_plugin, replace=True)

        retrieved = clean_registry.get_plugin("mock_plugin")
        assert hasattr(retrieved, "_test_marker")

    def test_get_plugin(self, clean_registry, mock_plugin):
        """get_plugin should return the plugin by name."""
        clean_registry.register(mock_plugin)

        plugin = clean_registry.get_plugin("mock_plugin")

        assert plugin is not None
        assert plugin.name == "mock_plugin"

    def test_get_plugin_not_found(self, clean_registry):
        """get_plugin should return None for non-existent plugin."""
        plugin = clean_registry.get_plugin("nonexistent")

        assert plugin is None

    def test_list_plugins(self, clean_registry, mock_plugin):
        """list_plugins should return all registered plugins."""
        from core.plugins.registry import PluginInfo

        clean_registry.register(mock_plugin)

        plugins = clean_registry.list_plugins()

        assert len(plugins) == 1
        assert isinstance(plugins[0], PluginInfo)
        assert plugins[0].name == "mock_plugin"
        assert plugins[0].version == "1.0.0"
        assert plugins[0].enabled is True

    def test_enable_plugin(self, clean_registry, mock_plugin):
        """enable should enable a disabled plugin."""
        clean_registry.register(mock_plugin)
        clean_registry.disable("mock_plugin")

        result = clean_registry.enable("mock_plugin")

        assert result is True
        info = clean_registry.list_plugins()[0]
        assert info.enabled is True

    def test_enable_already_enabled(self, clean_registry, mock_plugin):
        """enable should return True for already enabled plugin."""
        clean_registry.register(mock_plugin)

        result = clean_registry.enable("mock_plugin")

        assert result is True

    def test_disable_plugin(self, clean_registry, mock_plugin):
        """disable should disable an enabled plugin."""
        clean_registry.register(mock_plugin)

        result = clean_registry.disable("mock_plugin")

        assert result is True
        info = clean_registry.list_plugins()[0]
        assert info.enabled is False

    def test_disable_already_disabled(self, clean_registry, mock_plugin):
        """disable should return True for already disabled plugin."""
        clean_registry.register(mock_plugin)
        clean_registry.disable("mock_plugin")

        result = clean_registry.disable("mock_plugin")

        assert result is True

    def test_enable_nonexistent_plugin(self, clean_registry):
        """enable should raise error for non-existent plugin."""
        from core.plugins.registry import PluginNotRegisteredError

        with pytest.raises(PluginNotRegisteredError):
            clean_registry.enable("nonexistent")

    def test_disable_nonexistent_plugin(self, clean_registry):
        """disable should raise error for non-existent plugin."""
        from core.plugins.registry import PluginNotRegisteredError

        with pytest.raises(PluginNotRegisteredError):
            clean_registry.disable("nonexistent")

    def test_unregister_plugin(self, clean_registry, mock_plugin):
        """unregister should remove a plugin from the registry."""
        clean_registry.register(mock_plugin)

        result = clean_registry.unregister("mock_plugin")

        assert result is True
        assert clean_registry.get_plugin("mock_plugin") is None

    def test_unregister_nonexistent_plugin(self, clean_registry):
        """unregister should raise error for non-existent plugin."""
        from core.plugins.registry import PluginNotRegisteredError

        with pytest.raises(PluginNotRegisteredError):
            clean_registry.unregister("nonexistent")

    def test_is_enabled(self, clean_registry, mock_plugin):
        """is_enabled should return plugin enabled state."""
        clean_registry.register(mock_plugin)

        assert clean_registry.is_enabled("mock_plugin") is True

        clean_registry.disable("mock_plugin")
        assert clean_registry.is_enabled("mock_plugin") is False

    def test_get_enabled_plugins(self, clean_registry, mock_plugin):
        """get_enabled_plugins should return only enabled plugins."""
        clean_registry.register(mock_plugin)

        # Create another plugin
        class AnotherPlugin:
            @property
            def name(self):
                return "another"

            @property
            def version(self):
                return "1.0.0"

            @property
            def description(self):
                return "Another"

            async def on_load(self):
                return True

            async def on_unload(self):
                return True

            def get_commands(self):
                return []

            def get_handlers(self):
                return []

        another = AnotherPlugin()
        clean_registry.register(another)
        clean_registry.disable("another")

        enabled = clean_registry.get_enabled_plugins()

        assert len(enabled) == 1
        assert enabled[0].name == "mock_plugin"


class TestPluginInfo:
    """Tests for the PluginInfo dataclass."""

    def test_plugin_info_creation(self):
        """PluginInfo should contain plugin metadata."""
        from core.plugins.registry import PluginInfo

        info = PluginInfo(
            name="test",
            version="1.0.0",
            description="Test plugin",
            enabled=True,
            commands=["cmd1", "cmd2"],
            handlers=["message", "error"],
        )

        assert info.name == "test"
        assert info.version == "1.0.0"
        assert info.description == "Test plugin"
        assert info.enabled is True
        assert info.commands == ["cmd1", "cmd2"]
        assert info.handlers == ["message", "error"]
