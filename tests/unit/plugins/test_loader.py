"""Tests for core/plugins/loader.py - Plugin loading functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestPluginLoader:
    """Tests for the PluginLoader class."""

    @pytest.fixture
    def plugin_dir(self, tmp_path):
        """Create a temporary directory with sample plugins."""
        # Create a valid plugin file
        plugin_code = '''
"""Sample plugin for testing."""
from core.plugins.base import Plugin, Command, Handler
from typing import List, Dict, Any, Optional


class TestPlugin(Plugin):
    @property
    def name(self) -> str:
        return "test_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "A test plugin"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> bool:
        return True

    def get_commands(self) -> List[Command]:
        return []

    def get_handlers(self) -> List[Handler]:
        return []
'''
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(plugin_code)

        # Create another plugin
        plugin2_code = '''
"""Another sample plugin."""
from core.plugins.base import Plugin, Command, Handler
from typing import List


class AnotherPlugin(Plugin):
    @property
    def name(self) -> str:
        return "another_plugin"

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def description(self) -> str:
        return "Another test plugin"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> bool:
        return True

    def get_commands(self) -> List[Command]:
        return []

    def get_handlers(self) -> List[Handler]:
        return []
'''
        plugin2_file = tmp_path / "another_plugin.py"
        plugin2_file.write_text(plugin2_code)

        return tmp_path

    def test_loader_initialization(self):
        """PluginLoader should initialize with empty state."""
        from core.plugins.loader import PluginLoader

        loader = PluginLoader()
        assert loader is not None
        assert loader.loaded_plugins == {}

    @pytest.mark.asyncio
    async def test_load_plugin_from_path(self, plugin_dir):
        """load_plugin should load a plugin from file path."""
        from core.plugins.loader import PluginLoader
        from core.plugins.base import Plugin

        loader = PluginLoader()
        plugin_path = plugin_dir / "test_plugin.py"

        plugin = await loader.load_plugin(plugin_path)

        assert plugin is not None
        assert isinstance(plugin, Plugin)
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_load_plugin_calls_on_load(self, plugin_dir):
        """load_plugin should call the plugin's on_load method."""
        from core.plugins.loader import PluginLoader

        loader = PluginLoader()
        plugin_path = plugin_dir / "test_plugin.py"

        plugin = await loader.load_plugin(plugin_path)

        # The plugin should be loaded (on_load was called)
        assert plugin.name in loader.loaded_plugins

    @pytest.mark.asyncio
    async def test_load_plugin_invalid_path(self):
        """load_plugin should raise error for invalid path."""
        from core.plugins.loader import PluginLoader, PluginLoadError

        loader = PluginLoader()

        with pytest.raises(PluginLoadError):
            await loader.load_plugin(Path("/nonexistent/path/plugin.py"))

    @pytest.mark.asyncio
    async def test_load_all_plugins(self, plugin_dir):
        """load_all should load all plugins from a directory."""
        from core.plugins.loader import PluginLoader

        loader = PluginLoader()
        plugins = await loader.load_all(plugin_dir)

        assert len(plugins) == 2
        plugin_names = {p.name for p in plugins}
        assert "test_plugin" in plugin_names
        assert "another_plugin" in plugin_names

    @pytest.mark.asyncio
    async def test_load_all_skips_invalid_files(self, tmp_path):
        """load_all should skip files that aren't valid plugins."""
        from core.plugins.loader import PluginLoader

        # Create an invalid Python file
        invalid_file = tmp_path / "invalid.py"
        invalid_file.write_text("# Not a valid plugin\nx = 1")

        loader = PluginLoader()
        plugins = await loader.load_all(tmp_path)

        assert len(plugins) == 0

    @pytest.mark.asyncio
    async def test_unload_plugin(self, plugin_dir):
        """unload_plugin should unload a loaded plugin."""
        from core.plugins.loader import PluginLoader

        loader = PluginLoader()
        plugin_path = plugin_dir / "test_plugin.py"
        await loader.load_plugin(plugin_path)

        assert "test_plugin" in loader.loaded_plugins

        result = await loader.unload_plugin("test_plugin")

        assert result is True
        assert "test_plugin" not in loader.loaded_plugins

    @pytest.mark.asyncio
    async def test_unload_plugin_not_loaded(self):
        """unload_plugin should handle unloading a non-loaded plugin."""
        from core.plugins.loader import PluginLoader, PluginNotFoundError

        loader = PluginLoader()

        with pytest.raises(PluginNotFoundError):
            await loader.unload_plugin("nonexistent_plugin")

    @pytest.mark.asyncio
    async def test_reload_plugin(self, plugin_dir):
        """reload_plugin should unload and reload a plugin."""
        from core.plugins.loader import PluginLoader

        loader = PluginLoader()
        plugin_path = plugin_dir / "test_plugin.py"
        original_plugin = await loader.load_plugin(plugin_path)

        reloaded_plugin = await loader.reload_plugin("test_plugin")

        assert reloaded_plugin is not None
        assert reloaded_plugin.name == "test_plugin"
        # Should be a new instance
        assert reloaded_plugin is not original_plugin

    @pytest.mark.asyncio
    async def test_reload_plugin_not_loaded(self):
        """reload_plugin should raise error for non-loaded plugin."""
        from core.plugins.loader import PluginLoader, PluginNotFoundError

        loader = PluginLoader()

        with pytest.raises(PluginNotFoundError):
            await loader.reload_plugin("nonexistent_plugin")


class TestPluginLoaderErrors:
    """Tests for PluginLoader error handling."""

    def test_plugin_load_error_exists(self):
        """PluginLoadError should be importable."""
        from core.plugins.loader import PluginLoadError

        error = PluginLoadError("Test error")
        assert str(error) == "Test error"

    def test_plugin_not_found_error_exists(self):
        """PluginNotFoundError should be importable."""
        from core.plugins.loader import PluginNotFoundError

        error = PluginNotFoundError("plugin_name")
        assert "plugin_name" in str(error)

    @pytest.mark.asyncio
    async def test_load_plugin_with_syntax_error(self, tmp_path):
        """load_plugin should handle plugins with syntax errors."""
        from core.plugins.loader import PluginLoader, PluginLoadError

        # Create a file with syntax error
        bad_plugin = tmp_path / "bad_plugin.py"
        bad_plugin.write_text("def broken(:\n    pass")

        loader = PluginLoader()

        with pytest.raises(PluginLoadError):
            await loader.load_plugin(bad_plugin)

    @pytest.mark.asyncio
    async def test_load_plugin_with_import_error(self, tmp_path):
        """load_plugin should handle plugins with import errors."""
        from core.plugins.loader import PluginLoader, PluginLoadError

        # Create a file with import error
        bad_plugin = tmp_path / "import_error.py"
        bad_plugin.write_text("import nonexistent_module_12345")

        loader = PluginLoader()

        with pytest.raises(PluginLoadError):
            await loader.load_plugin(bad_plugin)
