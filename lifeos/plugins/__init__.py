"""
Jarvis Plugin System

Provides a robust plugin architecture for extending Jarvis functionality.

Features:
- Plugin manifest schema with validation
- Lifecycle hooks (load, enable, disable, unload)
- Dependency resolution with topological sort
- Permission-based service access
- Hot-reload support for development
- Event-based communication

Usage:
    from lifeos.plugins import PluginManager, Plugin, PluginManifest

    # Create and start manager
    manager = PluginManager()
    manager.add_plugin_dir(Path("plugins"))
    await manager.start()

    # Create a plugin
    class MyPlugin(Plugin):
        async def on_enable(self):
            self.logger.info("Plugin enabled!")

Example plugin directory structure:
    plugins/
        my-plugin/
            manifest.json
            main.py
"""

from lifeos.plugins.manifest import (
    PluginManifest,
    PluginDependency,
    PluginPermission,
    PluginStatus,
    ManifestValidationError,
)
from lifeos.plugins.base import (
    Plugin,
    PluginContext,
    PluginError,
    PluginLoadError,
    PluginDependencyError,
)
from lifeos.plugins.loader import PluginLoader
from lifeos.plugins.manager import (
    PluginManager,
    get_plugin_manager,
    set_plugin_manager,
)

__all__ = [
    # Manifest
    "PluginManifest",
    "PluginDependency",
    "PluginPermission",
    "PluginStatus",
    "ManifestValidationError",
    # Base
    "Plugin",
    "PluginContext",
    "PluginError",
    "PluginLoadError",
    "PluginDependencyError",
    # Loader
    "PluginLoader",
    # Manager
    "PluginManager",
    "get_plugin_manager",
    "set_plugin_manager",
]
