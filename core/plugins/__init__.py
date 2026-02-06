"""
Plugin system for Jarvis.

This package provides a complete plugin architecture including:
- Base classes for creating plugins (Plugin, Command, Handler)
- Dynamic plugin loading (PluginLoader)
- Plugin registration and management (PluginRegistry)
- Hook system for event handling (HookManager, HookPoint)

Example creating a plugin:
    from core.plugins import Plugin, Command, Handler

    class MyPlugin(Plugin):
        @property
        def name(self) -> str:
            return "my_plugin"

        @property
        def version(self) -> str:
            return "1.0.0"

        @property
        def description(self) -> str:
            return "My awesome plugin"

        async def on_load(self) -> bool:
            return True

        async def on_unload(self) -> bool:
            return True

        def get_commands(self) -> List[Command]:
            return []

        def get_handlers(self) -> List[Handler]:
            return []

Example using the registry:
    from core.plugins import PluginRegistry

    registry = PluginRegistry.get_instance()
    registry.register(my_plugin)
    registry.enable("my_plugin")

Example using hooks:
    from core.plugins import HookPoint, register_hook

    async def my_hook(data):
        print(f"Got: {data}")
        return data

    register_hook(HookPoint.PRE_MESSAGE, my_hook, priority=10)
"""

# Base classes
from core.plugins.base import (
    Plugin,
    Command,
    Handler,
    PluginMetadata,  # Legacy
    PluginManager,  # Legacy
    plugin_manager,  # Legacy global instance
)

# Loader
from core.plugins.loader import (
    PluginLoader,
    PluginLoadError,
    PluginNotFoundError,
    plugin_loader,
)

# Registry
from core.plugins.registry import (
    PluginRegistry,
    PluginInfo,
    PluginAlreadyRegisteredError,
    PluginNotRegisteredError,
    get_registry,
)

# Hooks
from core.plugins.hooks import (
    HookManager,
    HookPoint,
    HookResult,
    RegisteredHook,
    hook_manager,
    register_hook,
    unregister_hook,
    trigger_hooks,
)

__all__ = [
    # Base
    "Plugin",
    "Command",
    "Handler",
    "PluginMetadata",
    "PluginManager",
    "plugin_manager",
    # Loader
    "PluginLoader",
    "PluginLoadError",
    "PluginNotFoundError",
    "plugin_loader",
    # Registry
    "PluginRegistry",
    "PluginInfo",
    "PluginAlreadyRegisteredError",
    "PluginNotRegisteredError",
    "get_registry",
    # Hooks
    "HookManager",
    "HookPoint",
    "HookResult",
    "RegisteredHook",
    "hook_manager",
    "register_hook",
    "unregister_hook",
    "trigger_hooks",
]
