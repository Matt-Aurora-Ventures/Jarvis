"""
Plugin Manager

High-level interface for managing plugins.
Orchestrates loading, enabling, and lifecycle management.

Usage:
    manager = PluginManager()
    manager.add_plugin_dir(Path("plugins"))
    await manager.start()

    # Enable/disable plugins
    await manager.enable("my-plugin")
    await manager.disable("my-plugin")

    # Hot reload during development
    await manager.reload("my-plugin")
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from lifeos.plugins.manifest import PluginManifest, PluginStatus
from lifeos.plugins.base import Plugin, PluginError
from lifeos.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)


class PluginManager:
    """
    High-level plugin management.

    Provides a simple interface for:
    - Starting/stopping the plugin system
    - Enabling/disabling individual plugins
    - Hot-reloading plugins during development
    - Querying plugin status
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[Path]] = None,
        services: Optional[Dict[str, Any]] = None,
        auto_enable: bool = True,
    ):
        """
        Initialize plugin manager.

        Args:
            plugin_dirs: Directories to search for plugins
            services: Services to expose to plugins
            auto_enable: Whether to auto-enable plugins after loading
        """
        self._loader = PluginLoader(plugin_dirs, services)
        self._auto_enable = auto_enable
        self._started = False
        self._event_handlers: Dict[str, List[Callable]] = {}

    def add_plugin_dir(self, path: Path) -> None:
        """Add a plugin directory."""
        self._loader.add_plugin_dir(path)

    def set_services(self, services: Dict[str, Any]) -> None:
        """Set services available to plugins."""
        self._loader.set_services(services)

    def configure_plugin(self, name: str, config: Dict[str, Any]) -> None:
        """Set configuration for a plugin."""
        self._loader.set_plugin_config(name, config)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """
        Start the plugin system.

        Discovers, loads, and optionally enables all plugins.
        """
        if self._started:
            return

        logger.info("Starting plugin system...")
        self._started = True

        # Load all plugins
        await self._loader.load_all()

        # Auto-enable plugins that request it
        if self._auto_enable:
            for name, plugin in self._loader.get_all_plugins().items():
                manifest = self._loader.get_manifest(name)
                if manifest and manifest.auto_enable:
                    try:
                        await self.enable(name)
                    except PluginError as e:
                        logger.error(f"Failed to auto-enable {name}: {e}")

        await self._emit("system.started")
        logger.info(
            f"Plugin system started. "
            f"{len(self._loader.get_all_plugins())} plugins loaded."
        )

    async def stop(self) -> None:
        """
        Stop the plugin system.

        Disables and unloads all plugins.
        """
        if not self._started:
            return

        logger.info("Stopping plugin system...")

        # Disable all enabled plugins
        for name, plugin in list(self._loader.get_all_plugins().items()):
            if plugin.is_enabled:
                try:
                    await self.disable(name)
                except PluginError as e:
                    logger.error(f"Error disabling {name}: {e}")

        # Unload all plugins
        await self._loader.unload_all()

        self._started = False
        await self._emit("system.stopped")
        logger.info("Plugin system stopped.")

    # =========================================================================
    # Plugin Control
    # =========================================================================

    async def enable(self, name: str) -> None:
        """
        Enable a plugin.

        Args:
            name: Plugin name

        Raises:
            PluginError: If plugin cannot be enabled
        """
        plugin = self._loader.get_plugin(name)
        if not plugin:
            raise PluginError(name, "Plugin not loaded")

        if plugin.is_enabled:
            return

        manifest = self._loader.get_manifest(name)
        logger.info(f"Enabling plugin: {name}")

        try:
            await plugin._do_enable()
            if manifest:
                manifest.status = PluginStatus.ENABLED
            await self._emit("plugin.enabled", name)
            logger.info(f"Enabled plugin: {name}")
        except Exception as e:
            if manifest:
                manifest.status = PluginStatus.ERROR
                manifest.error_message = str(e)
            raise PluginError(name, f"Failed to enable: {e}")

    async def disable(self, name: str) -> None:
        """
        Disable a plugin.

        Args:
            name: Plugin name

        Raises:
            PluginError: If plugin cannot be disabled
        """
        plugin = self._loader.get_plugin(name)
        if not plugin:
            raise PluginError(name, "Plugin not loaded")

        if not plugin.is_enabled:
            return

        manifest = self._loader.get_manifest(name)
        logger.info(f"Disabling plugin: {name}")

        try:
            await plugin._do_disable()
            if manifest:
                manifest.status = PluginStatus.DISABLED
            await self._emit("plugin.disabled", name)
            logger.info(f"Disabled plugin: {name}")
        except Exception as e:
            if manifest:
                manifest.status = PluginStatus.ERROR
                manifest.error_message = str(e)
            raise PluginError(name, f"Failed to disable: {e}")

    async def reload(self, name: str) -> Plugin:
        """
        Hot-reload a plugin.

        Args:
            name: Plugin name

        Returns:
            Reloaded plugin instance
        """
        logger.info(f"Reloading plugin: {name}")
        plugin = await self._loader.reload(name)
        await self._emit("plugin.reloaded", name)
        return plugin

    async def load(self, manifest: PluginManifest) -> Plugin:
        """
        Load a single plugin from manifest.

        Args:
            manifest: Plugin manifest

        Returns:
            Loaded plugin
        """
        plugin = await self._loader.load(manifest)
        await self._emit("plugin.loaded", manifest.name)
        return plugin

    async def unload(self, name: str) -> None:
        """
        Unload a plugin.

        Args:
            name: Plugin name
        """
        await self._loader.unload(name)
        await self._emit("plugin.unloaded", name)

    # =========================================================================
    # Query
    # =========================================================================

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin."""
        return self._loader.get_plugin(name)

    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """Get a plugin manifest."""
        return self._loader.get_manifest(name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all known plugins with status.

        Returns:
            List of plugin info dictionaries
        """
        result = []
        for name, manifest in self._loader.get_all_manifests().items():
            plugin = self._loader.get_plugin(name)
            result.append({
                "name": name,
                "version": manifest.version,
                "status": manifest.status.value,
                "enabled": plugin.is_enabled if plugin else False,
                "description": manifest.description,
                "error": manifest.error_message,
            })
        return result

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return self._loader.get_plugin(name) is not None

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        plugin = self._loader.get_plugin(name)
        return plugin is not None and plugin.is_enabled

    # =========================================================================
    # Events
    # =========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """Unregister an event handler."""
        if event not in self._event_handlers:
            return
        if handler is None:
            del self._event_handlers[event]
        else:
            self._event_handlers[event] = [
                h for h in self._event_handlers[event] if h != handler
            ]

    async def _emit(self, event: str, *args) -> None:
        """Emit an event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                result = handler(*args)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}")


# Global manager instance
_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get or create the global plugin manager."""
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager


def set_plugin_manager(manager: PluginManager) -> None:
    """Set the global plugin manager."""
    global _manager
    _manager = manager
