"""
Plugin loader for dynamically loading plugins from files.

This module provides functionality to:
- Load plugins from Python files
- Load all plugins from a directory
- Unload plugins
- Reload plugins

Example usage:
    from core.plugins.loader import PluginLoader

    loader = PluginLoader()

    # Load a single plugin
    plugin = await loader.load_plugin(Path("plugins/my_plugin.py"))

    # Load all plugins from a directory
    plugins = await loader.load_all(Path("plugins/"))

    # Reload a plugin
    plugin = await loader.reload_plugin("my_plugin")

    # Unload a plugin
    await loader.unload_plugin("my_plugin")
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type

from core.plugins.base import Plugin

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""

    def __init__(self, message: str, plugin_path: Optional[Path] = None):
        self.plugin_path = plugin_path
        super().__init__(message)


class PluginNotFoundError(Exception):
    """Raised when a plugin is not found."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        super().__init__(f"Plugin not found: {plugin_name}")


class PluginLoader:
    """
    Loads and manages plugin instances from Python files.

    The loader maintains a mapping of loaded plugins and their source paths,
    enabling reload functionality.
    """

    def __init__(self):
        """Initialize the plugin loader."""
        self.loaded_plugins: Dict[str, Plugin] = {}
        self._plugin_paths: Dict[str, Path] = {}
        self._plugin_modules: Dict[str, str] = {}

    async def load_plugin(self, path: Path) -> Plugin:
        """
        Load a plugin from a Python file.

        The file must contain a class that inherits from Plugin.
        The plugin's on_load() method will be called after instantiation.

        Args:
            path: Path to the plugin Python file.

        Returns:
            The loaded and initialized Plugin instance.

        Raises:
            PluginLoadError: If the plugin cannot be loaded.
        """
        path = Path(path)

        if not path.exists():
            raise PluginLoadError(f"Plugin file not found: {path}", path)

        if not path.is_file() or not path.suffix == ".py":
            raise PluginLoadError(f"Invalid plugin file: {path}", path)

        try:
            # Load the module
            module_name = f"jarvis_plugin_{path.stem}"

            # Remove old module if reloading
            if module_name in sys.modules:
                del sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Cannot create module spec for {path}", path)

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module

            try:
                spec.loader.exec_module(module)
            except SyntaxError as e:
                raise PluginLoadError(f"Syntax error in plugin: {e}", path)
            except ImportError as e:
                raise PluginLoadError(f"Import error in plugin: {e}", path)

            # Find Plugin subclass
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                raise PluginLoadError(
                    f"No Plugin subclass found in {path}", path
                )

            # Instantiate the plugin
            plugin = plugin_class()

            # Call on_load
            success = await plugin.on_load()
            if not success:
                raise PluginLoadError(
                    f"Plugin {plugin.name} on_load() returned False", path
                )

            # Track the loaded plugin
            self.loaded_plugins[plugin.name] = plugin
            self._plugin_paths[plugin.name] = path
            self._plugin_modules[plugin.name] = module_name

            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version} from {path}")
            return plugin

        except PluginLoadError:
            raise
        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin from {path}: {e}", path)

    async def load_all(self, directory: Path) -> List[Plugin]:
        """
        Load all plugins from a directory.

        Scans the directory for .py files and attempts to load each one
        as a plugin. Files starting with underscore are skipped.

        Args:
            directory: Path to the directory containing plugin files.

        Returns:
            List of successfully loaded Plugin instances.
        """
        directory = Path(directory)
        plugins = []

        if not directory.exists():
            logger.warning(f"Plugin directory does not exist: {directory}")
            return plugins

        if not directory.is_dir():
            logger.warning(f"Not a directory: {directory}")
            return plugins

        for plugin_file in directory.glob("*.py"):
            # Skip private files
            if plugin_file.name.startswith("_"):
                continue

            try:
                plugin = await self.load_plugin(plugin_file)
                plugins.append(plugin)
            except PluginLoadError as e:
                logger.warning(f"Skipping {plugin_file}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading {plugin_file}: {e}")

        return plugins

    async def unload_plugin(self, name: str) -> bool:
        """
        Unload a loaded plugin.

        Calls the plugin's on_unload() method and removes it from tracking.

        Args:
            name: Name of the plugin to unload.

        Returns:
            True if unloading was successful.

        Raises:
            PluginNotFoundError: If the plugin is not loaded.
        """
        if name not in self.loaded_plugins:
            raise PluginNotFoundError(name)

        plugin = self.loaded_plugins[name]

        try:
            await plugin.on_unload()
        except Exception as e:
            logger.error(f"Error in on_unload for {name}: {e}")
            # Continue with cleanup even if on_unload fails

        # Clean up module from sys.modules
        module_name = self._plugin_modules.get(name)
        if module_name and module_name in sys.modules:
            del sys.modules[module_name]

        # Remove from tracking
        del self.loaded_plugins[name]
        self._plugin_paths.pop(name, None)
        self._plugin_modules.pop(name, None)

        logger.info(f"Unloaded plugin: {name}")
        return True

    async def reload_plugin(self, name: str) -> Plugin:
        """
        Reload a loaded plugin.

        Unloads the plugin and loads it again from its original path.

        Args:
            name: Name of the plugin to reload.

        Returns:
            The newly loaded Plugin instance.

        Raises:
            PluginNotFoundError: If the plugin is not loaded.
            PluginLoadError: If reloading fails.
        """
        if name not in self.loaded_plugins:
            raise PluginNotFoundError(name)

        # Get the path before unloading
        path = self._plugin_paths[name]

        # Unload the old instance
        await self.unload_plugin(name)

        # Load fresh instance
        return await self.load_plugin(path)

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Get a loaded plugin by name.

        Args:
            name: Name of the plugin.

        Returns:
            The Plugin instance if loaded, None otherwise.
        """
        return self.loaded_plugins.get(name)

    def is_loaded(self, name: str) -> bool:
        """
        Check if a plugin is loaded.

        Args:
            name: Name of the plugin.

        Returns:
            True if the plugin is loaded.
        """
        return name in self.loaded_plugins

    def _find_plugin_class(self, module) -> Optional[Type[Plugin]]:
        """
        Find a Plugin subclass in a module.

        Args:
            module: The module to search.

        Returns:
            The Plugin subclass if found, None otherwise.
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            # Check if it's a class
            if not isinstance(attr, type):
                continue

            # Check if it's a Plugin subclass (but not Plugin itself)
            if issubclass(attr, Plugin) and attr is not Plugin:
                # Make sure it's defined in this module, not imported
                if attr.__module__ == module.__name__:
                    return attr

        return None


# Global loader instance
plugin_loader = PluginLoader()
