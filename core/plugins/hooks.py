"""
Hook system for plugin event handling.

This module provides a hook system that allows plugins to register
callbacks at various hook points in the application lifecycle.

Hook points:
- PRE_MESSAGE: Before processing a message
- POST_MESSAGE: After processing a message
- ON_ERROR: When an error occurs
- ON_STARTUP: When the application starts
- ON_SHUTDOWN: When the application shuts down

Example usage:
    from core.plugins.hooks import HookManager, HookPoint, register_hook

    # Register a hook
    async def my_pre_message_hook(data):
        print(f"Processing message: {data}")
        return data

    register_hook(HookPoint.PRE_MESSAGE, my_pre_message_hook, priority=10)

    # Trigger hooks
    results = await trigger_hooks(HookPoint.PRE_MESSAGE, {"message": "hello"})
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookPoint(Enum):
    """
    Standard hook points in the application lifecycle.
    """

    PRE_MESSAGE = auto()  # Before processing a message
    POST_MESSAGE = auto()  # After processing a message
    ON_ERROR = auto()  # When an error occurs
    ON_STARTUP = auto()  # When the application starts
    ON_SHUTDOWN = auto()  # When the application shuts down
    ON_COMMAND = auto()  # Before executing a command
    POST_COMMAND = auto()  # After executing a command
    ON_PLUGIN_LOAD = auto()  # When a plugin is loaded
    ON_PLUGIN_UNLOAD = auto()  # When a plugin is unloaded


# Type alias for hook callbacks
HookCallback = Callable[[Dict[str, Any]], Awaitable[Any]]


@dataclass
class HookResult:
    """
    Result from a hook callback.

    Attributes:
        consumed: If True, stops further hook processing
        data: Optional data returned by the hook
        error: Optional exception if the hook failed
    """

    consumed: bool = False
    data: Any = None
    error: Optional[Exception] = None


@dataclass
class RegisteredHook:
    """
    A registered hook callback with metadata.

    Attributes:
        callback: The async callback function
        priority: Higher values execute first (default: 0)
        plugin_name: Name of the plugin that registered this hook
    """

    callback: HookCallback
    priority: int = 0
    plugin_name: Optional[str] = None


class HookManager:
    """
    Manages hook registration and execution.

    Hooks are executed in priority order (highest first).
    If a hook returns HookResult(consumed=True), subsequent hooks are skipped.
    """

    def __init__(self):
        """Initialize the hook manager."""
        self._hooks: Dict[HookPoint, List[RegisteredHook]] = {
            point: [] for point in HookPoint
        }

    def register_hook(
        self,
        point: HookPoint,
        callback: HookCallback,
        priority: int = 0,
        plugin_name: Optional[str] = None,
    ) -> None:
        """
        Register a callback at a hook point.

        Args:
            point: The hook point to register at.
            callback: Async callback function.
            priority: Execution priority (higher = first). Default: 0.
            plugin_name: Optional name of the registering plugin.
        """
        hook = RegisteredHook(
            callback=callback,
            priority=priority,
            plugin_name=plugin_name,
        )

        self._hooks[point].append(hook)
        # Sort by priority (descending)
        self._hooks[point].sort(key=lambda h: h.priority, reverse=True)

        callback_name = getattr(callback, "__name__", str(callback))
        logger.debug(
            f"Registered hook at {point.name}: {callback_name} "
            f"(priority={priority}, plugin={plugin_name})"
        )

    def unregister_hook(
        self,
        point: HookPoint,
        callback: HookCallback,
    ) -> bool:
        """
        Unregister a specific callback from a hook point.

        Args:
            point: The hook point.
            callback: The callback to remove.

        Returns:
            True if the callback was found and removed.
        """
        original_count = len(self._hooks[point])
        self._hooks[point] = [
            h for h in self._hooks[point] if h.callback is not callback
        ]
        removed = len(self._hooks[point]) < original_count

        if removed:
            callback_name = getattr(callback, "__name__", str(callback))
            logger.debug(f"Unregistered hook from {point.name}: {callback_name}")

        return removed

    def unregister_hooks_by_plugin(self, plugin_name: str) -> int:
        """
        Unregister all hooks registered by a specific plugin.

        Args:
            plugin_name: Name of the plugin.

        Returns:
            Number of hooks removed.
        """
        removed_count = 0

        for point in HookPoint:
            original_count = len(self._hooks[point])
            self._hooks[point] = [
                h for h in self._hooks[point] if h.plugin_name != plugin_name
            ]
            removed_count += original_count - len(self._hooks[point])

        if removed_count > 0:
            logger.debug(f"Unregistered {removed_count} hooks for plugin: {plugin_name}")

        return removed_count

    def get_hooks(self, point: HookPoint) -> List[RegisteredHook]:
        """
        Get all registered hooks for a point.

        Args:
            point: The hook point.

        Returns:
            List of RegisteredHook objects, sorted by priority (descending).
        """
        return list(self._hooks[point])

    async def trigger_hooks(
        self,
        point: HookPoint,
        data: Dict[str, Any],
        allow_modification: bool = False,
    ) -> List[Any]:
        """
        Trigger all hooks at a point.

        Args:
            point: The hook point to trigger.
            data: Data to pass to hooks.
            allow_modification: If True, hooks can modify data for subsequent hooks.

        Returns:
            List of results from each hook (including errors).
        """
        results = []
        current_data = data.copy() if allow_modification else data

        for hook in self._hooks[point]:
            try:
                result = await hook.callback(current_data)

                # Check if hook consumed the event
                if isinstance(result, HookResult):
                    results.append(result.data)

                    # Update data if hook modified it and modification is allowed
                    if allow_modification and result.data is not None:
                        if isinstance(result.data, dict):
                            current_data.update(result.data)

                    if result.consumed:
                        logger.debug(
                            f"Hook at {point.name} consumed event, stopping chain"
                        )
                        break
                else:
                    results.append(result)

            except Exception as e:
                callback_name = getattr(hook.callback, "__name__", str(hook.callback))
                logger.error(f"Error in hook {callback_name} at {point.name}: {e}")
                results.append(HookResult(error=e))

        return results

    def clear_hooks(self, point: Optional[HookPoint] = None) -> None:
        """
        Clear all hooks at a point, or all hooks if point is None.

        Args:
            point: Optional hook point to clear. If None, clears all.
        """
        if point is not None:
            self._hooks[point] = []
            logger.debug(f"Cleared all hooks at {point.name}")
        else:
            for p in HookPoint:
                self._hooks[p] = []
            logger.debug("Cleared all hooks")

    def get_hook_count(self, point: Optional[HookPoint] = None) -> int:
        """
        Get the number of registered hooks.

        Args:
            point: Optional hook point. If None, returns total count.

        Returns:
            Number of registered hooks.
        """
        if point is not None:
            return len(self._hooks[point])
        return sum(len(hooks) for hooks in self._hooks.values())


# Global hook manager instance
hook_manager = HookManager()


# Convenience functions using the global instance
def register_hook(
    point: HookPoint,
    callback: HookCallback,
    priority: int = 0,
    plugin_name: Optional[str] = None,
) -> None:
    """
    Register a hook using the global hook manager.

    Args:
        point: The hook point to register at.
        callback: Async callback function.
        priority: Execution priority (higher = first). Default: 0.
        plugin_name: Optional name of the registering plugin.
    """
    hook_manager.register_hook(point, callback, priority, plugin_name)


def unregister_hook(point: HookPoint, callback: HookCallback) -> bool:
    """
    Unregister a hook using the global hook manager.

    Args:
        point: The hook point.
        callback: The callback to remove.

    Returns:
        True if the callback was found and removed.
    """
    return hook_manager.unregister_hook(point, callback)


async def trigger_hooks(
    point: HookPoint,
    data: Dict[str, Any],
    allow_modification: bool = False,
) -> List[Any]:
    """
    Trigger hooks using the global hook manager.

    Args:
        point: The hook point to trigger.
        data: Data to pass to hooks.
        allow_modification: If True, hooks can modify data for subsequent hooks.

    Returns:
        List of results from each hook.
    """
    return await hook_manager.trigger_hooks(point, data, allow_modification)
