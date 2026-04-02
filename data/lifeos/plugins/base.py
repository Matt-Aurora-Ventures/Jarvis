"""
Plugin Base Class

Provides the base class for all Jarvis plugins.
Plugins must inherit from this class and implement lifecycle hooks.

Example:
    class MyPlugin(Plugin):
        async def on_load(self):
            self.logger.info("Plugin loaded!")

        async def on_enable(self):
            # Start background tasks, register handlers
            pass

        async def on_disable(self):
            # Stop background tasks, cleanup
            pass
"""

from abc import ABC
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lifeos.plugins.manifest import PluginManifest

logger = logging.getLogger(__name__)


class PluginContext:
    """
    Context object passed to plugins.

    Provides controlled access to host services based on permissions.
    """

    def __init__(
        self,
        plugin_name: str,
        permissions: List[str],
        config: Dict[str, Any],
        services: Dict[str, Any],
    ):
        self._plugin_name = plugin_name
        self._permissions = set(permissions)
        self._config = config
        self._services = services
        self._logger = logging.getLogger(f"plugin.{plugin_name}")

    @property
    def config(self) -> Dict[str, Any]:
        """Plugin configuration."""
        return self._config

    @property
    def logger(self) -> logging.Logger:
        """Plugin-specific logger."""
        return self._logger

    def has_permission(self, permission: str) -> bool:
        """Check if plugin has a permission."""
        return permission in self._permissions

    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service by name.

        Access is controlled by permissions.
        """
        # Map service names to required permissions
        permission_map = {
            "llm": "llm_read",
            "market": "market_read",
            "notifications": "notifications",
            "memory": "memory_read",
        }

        required_perm = permission_map.get(service_name)
        if required_perm and not self.has_permission(required_perm):
            self._logger.warning(
                f"Permission denied: {service_name} requires {required_perm}"
            )
            return None

        return self._services.get(service_name)


class Plugin(ABC):
    """
    Base class for all Jarvis plugins.

    Plugins must inherit from this class and can override
    lifecycle hooks to perform initialization and cleanup.

    Lifecycle:
        1. __init__() - Constructor (don't do heavy init here)
        2. on_load() - Called when plugin is loaded
        3. on_enable() - Called when plugin is enabled
        4. on_disable() - Called when plugin is disabled
        5. on_unload() - Called before plugin is unloaded

    Example:
        class WeatherPlugin(Plugin):
            async def on_load(self):
                self.api_key = self.config.get("api_key")

            async def on_enable(self):
                self.task = asyncio.create_task(self._poll_weather())

            async def on_disable(self):
                self.task.cancel()
    """

    def __init__(self, context: PluginContext, manifest: "PluginManifest"):
        """
        Initialize plugin.

        Args:
            context: Plugin context with services and config
            manifest: Plugin manifest with metadata
        """
        self._context = context
        self._manifest = manifest
        self._enabled = False
        self._tasks: List[asyncio.Task] = []
        self._event_handlers: Dict[str, List[Callable]] = {}

    @property
    def name(self) -> str:
        """Plugin name."""
        return self._manifest.name

    @property
    def version(self) -> str:
        """Plugin version."""
        return self._manifest.version

    @property
    def config(self) -> Dict[str, Any]:
        """Plugin configuration."""
        return self._context.config

    @property
    def logger(self) -> logging.Logger:
        """Plugin logger."""
        return self._context.logger

    @property
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled

    def get_service(self, name: str) -> Optional[Any]:
        """Get a service from the host."""
        return self._context.get_service(name)

    def has_permission(self, permission: str) -> bool:
        """Check if plugin has a permission."""
        return self._context.has_permission(permission)

    # =========================================================================
    # Lifecycle Hooks - Override these in your plugin
    # =========================================================================

    async def on_load(self) -> None:
        """
        Called when the plugin is loaded.

        Use this for one-time initialization that doesn't require
        the plugin to be enabled (e.g., loading config, checking deps).

        This is called ONCE when the plugin is first loaded.
        """
        pass

    async def on_unload(self) -> None:
        """
        Called before the plugin is unloaded.

        Use this for final cleanup before the plugin is removed
        from memory (e.g., closing file handles, saving state).

        This is called ONCE when the plugin is being removed.
        """
        pass

    async def on_enable(self) -> None:
        """
        Called when the plugin is enabled.

        Use this to start background tasks, register event handlers,
        and activate the plugin's functionality.

        This may be called multiple times if the plugin is
        disabled and re-enabled.
        """
        pass

    async def on_disable(self) -> None:
        """
        Called when the plugin is disabled.

        Use this to stop background tasks, unregister handlers,
        and deactivate the plugin's functionality.

        The plugin should be able to be re-enabled after this.
        """
        pass

    async def on_config_change(self, new_config: Dict[str, Any]) -> None:
        """
        Called when plugin configuration changes.

        Override this to handle runtime configuration updates.

        Args:
            new_config: The new configuration dictionary
        """
        pass

    # =========================================================================
    # Task Management
    # =========================================================================

    def create_task(self, coro) -> asyncio.Task:
        """
        Create a managed background task.

        Tasks created this way are automatically cancelled
        when the plugin is disabled.

        Args:
            coro: Coroutine to run

        Returns:
            asyncio.Task instance
        """
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        task.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)
        return task

    async def cancel_all_tasks(self) -> None:
        """Cancel all managed background tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._tasks.clear()

    # =========================================================================
    # Event Handling
    # =========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name to listen for
            handler: Callback function (can be async)
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """
        Unregister event handler(s).

        Args:
            event: Event name
            handler: Specific handler to remove, or None to remove all
        """
        if event not in self._event_handlers:
            return
        if handler is None:
            del self._event_handlers[event]
        else:
            self._event_handlers[event] = [
                h for h in self._event_handlers[event] if h != handler
            ]

    async def emit(self, event: str, *args, **kwargs) -> None:
        """
        Emit an event to registered handlers.

        Args:
            event: Event name
            *args: Positional arguments for handlers
            **kwargs: Keyword arguments for handlers
        """
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.logger.error(f"Error in event handler for {event}: {e}")

    # =========================================================================
    # Internal Methods (called by PluginManager)
    # =========================================================================

    async def _do_enable(self) -> None:
        """Internal enable method."""
        if self._enabled:
            return
        await self.on_enable()
        self._enabled = True

    async def _do_disable(self) -> None:
        """Internal disable method."""
        if not self._enabled:
            return
        self._enabled = False
        await self.cancel_all_tasks()
        await self.on_disable()
        self._event_handlers.clear()


class PluginError(Exception):
    """Base exception for plugin errors."""

    def __init__(self, plugin_name: str, message: str):
        self.plugin_name = plugin_name
        self.message = message
        super().__init__(f"[{plugin_name}] {message}")


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""
    pass


class PluginDependencyError(PluginError):
    """Raised when plugin dependencies cannot be resolved."""
    pass
