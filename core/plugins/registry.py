"""
Plugin registry singleton for managing plugin registration and state.

This module provides:
- PluginRegistry: Singleton for registering and managing plugins
- PluginInfo: Dataclass with plugin metadata
- Enable/disable functionality for plugins

Example usage:
    from core.plugins.registry import PluginRegistry, PluginInfo

    registry = PluginRegistry.get_instance()

    # Register a plugin
    registry.register(my_plugin)

    # Get plugin info
    info = registry.list_plugins()

    # Enable/disable
    registry.disable("my_plugin")
    registry.enable("my_plugin")

    # Get only enabled plugins
    enabled = registry.get_enabled_plugins()
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.plugins.base import Plugin

logger = logging.getLogger(__name__)


class PluginAlreadyRegisteredError(Exception):
    """Raised when attempting to register a plugin that's already registered."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        super().__init__(f"Plugin already registered: {plugin_name}")


class PluginNotRegisteredError(Exception):
    """Raised when attempting to access a plugin that's not registered."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        super().__init__(f"Plugin not registered: {plugin_name}")


@dataclass
class PluginInfo:
    """
    Information about a registered plugin.

    Attributes:
        name: Unique plugin identifier
        version: Plugin version string
        description: Human-readable description
        enabled: Whether the plugin is enabled
        commands: List of command names the plugin handles
        handlers: List of event types the plugin handles
    """

    name: str
    version: str
    description: str
    enabled: bool = True
    commands: List[str] = field(default_factory=list)
    handlers: List[str] = field(default_factory=list)


class PluginRegistry:
    """
    Singleton registry for managing plugins.

    Provides centralized plugin registration, lookup, and enable/disable
    functionality. Thread-safe for concurrent access.
    """

    _instance: Optional["PluginRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the registry (only runs once)."""
        if self._initialized:
            return

        self._plugins: Dict[str, Plugin] = {}
        self._enabled: Dict[str, bool] = {}
        self._lock = threading.RLock()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "PluginRegistry":
        """
        Get the singleton registry instance.

        Returns:
            The PluginRegistry singleton.
        """
        return cls()

    @classmethod
    def reset_instance(cls):
        """
        Reset the singleton instance (mainly for testing).

        Warning: This will clear all registered plugins.
        """
        with cls._lock:
            cls._instance = None

    def register(self, plugin: Plugin, replace: bool = False) -> None:
        """
        Register a plugin with the registry.

        Args:
            plugin: The Plugin instance to register.
            replace: If True, replace existing plugin with same name.

        Raises:
            PluginAlreadyRegisteredError: If plugin exists and replace=False.
        """
        with self._lock:
            name = plugin.name

            if name in self._plugins and not replace:
                raise PluginAlreadyRegisteredError(name)

            self._plugins[name] = plugin
            self._enabled[name] = True

            logger.info(f"Registered plugin: {name} v{plugin.version}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a plugin from the registry.

        Args:
            name: Name of the plugin to unregister.

        Returns:
            True if unregistration was successful.

        Raises:
            PluginNotRegisteredError: If plugin is not registered.
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotRegisteredError(name)

            del self._plugins[name]
            del self._enabled[name]

            logger.info(f"Unregistered plugin: {name}")
            return True

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Get a plugin by name.

        Args:
            name: Name of the plugin.

        Returns:
            The Plugin instance if registered, None otherwise.
        """
        with self._lock:
            return self._plugins.get(name)

    def list_plugins(self) -> List[PluginInfo]:
        """
        List all registered plugins with their info.

        Returns:
            List of PluginInfo for all registered plugins.
        """
        with self._lock:
            result = []
            for name, plugin in self._plugins.items():
                info = PluginInfo(
                    name=plugin.name,
                    version=plugin.version,
                    description=plugin.description,
                    enabled=self._enabled.get(name, True),
                    commands=plugin.get_command_names(),
                    handlers=plugin.get_handler_event_types(),
                )
                result.append(info)
            return result

    def enable(self, name: str) -> bool:
        """
        Enable a disabled plugin.

        Args:
            name: Name of the plugin to enable.

        Returns:
            True if operation was successful.

        Raises:
            PluginNotRegisteredError: If plugin is not registered.
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotRegisteredError(name)

            self._enabled[name] = True
            logger.info(f"Enabled plugin: {name}")
            return True

    def disable(self, name: str) -> bool:
        """
        Disable an enabled plugin.

        Disabled plugins remain registered but won't handle commands/events.

        Args:
            name: Name of the plugin to disable.

        Returns:
            True if operation was successful.

        Raises:
            PluginNotRegisteredError: If plugin is not registered.
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotRegisteredError(name)

            self._enabled[name] = False
            logger.info(f"Disabled plugin: {name}")
            return True

    def is_enabled(self, name: str) -> bool:
        """
        Check if a plugin is enabled.

        Args:
            name: Name of the plugin.

        Returns:
            True if the plugin is enabled, False if disabled.

        Raises:
            PluginNotRegisteredError: If plugin is not registered.
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotRegisteredError(name)
            return self._enabled.get(name, True)

    def get_enabled_plugins(self) -> List[Plugin]:
        """
        Get all enabled plugins.

        Returns:
            List of enabled Plugin instances.
        """
        with self._lock:
            return [
                plugin
                for name, plugin in self._plugins.items()
                if self._enabled.get(name, True)
            ]

    def get_disabled_plugins(self) -> List[Plugin]:
        """
        Get all disabled plugins.

        Returns:
            List of disabled Plugin instances.
        """
        with self._lock:
            return [
                plugin
                for name, plugin in self._plugins.items()
                if not self._enabled.get(name, True)
            ]

    def get_plugin_count(self) -> int:
        """
        Get the total number of registered plugins.

        Returns:
            Number of registered plugins.
        """
        with self._lock:
            return len(self._plugins)

    def clear(self) -> None:
        """
        Clear all registered plugins.

        Warning: This removes all plugins without calling on_unload.
        """
        with self._lock:
            self._plugins.clear()
            self._enabled.clear()
            logger.info("Cleared all plugins from registry")


# Global registry instance accessor
def get_registry() -> PluginRegistry:
    """Get the global plugin registry instance."""
    return PluginRegistry.get_instance()
