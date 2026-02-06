"""
Base plugin architecture for Jarvis.

This module provides the foundational classes for building plugins:
- Plugin: Abstract base class for all plugins
- Command: Dataclass representing a command a plugin can handle
- Handler: Dataclass representing an event handler

Example usage:
    from core.plugins.base import Plugin, Command, Handler

    class MyPlugin(Plugin):
        @property
        def name(self) -> str:
            return "my_plugin"

        @property
        def version(self) -> str:
            return "1.0.0"

        @property
        def description(self) -> str:
            return "A sample plugin"

        async def on_load(self) -> bool:
            # Initialize resources
            return True

        async def on_unload(self) -> bool:
            # Cleanup resources
            return True

        def get_commands(self) -> List[Command]:
            return [
                Command(
                    name="hello",
                    description="Say hello",
                    handler=self._hello_handler,
                )
            ]

        def get_handlers(self) -> List[Handler]:
            return [
                Handler(event_type="message", handler=self._on_message)
            ]
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
)
import logging

logger = logging.getLogger(__name__)


# Type aliases for handler functions
CommandHandler = Callable[[List[str]], Awaitable[str]]
EventHandler = Callable[[Dict[str, Any]], Awaitable[Optional[Any]]]


@dataclass
class Command:
    """
    Represents a command that a plugin can handle.

    Attributes:
        name: The command name (e.g., "help", "status")
        description: Human-readable description of what the command does
        handler: Async function that handles the command
        aliases: Alternative names for the command
        usage: Usage string (e.g., "command <arg1> [arg2]")
        examples: Example usages of the command
    """

    name: str
    description: str
    handler: CommandHandler
    aliases: List[str] = field(default_factory=list)
    usage: Optional[str] = None
    examples: List[str] = field(default_factory=list)


@dataclass
class Handler:
    """
    Represents an event handler that a plugin provides.

    Attributes:
        event_type: Type of event to handle (e.g., "message", "error", "startup")
        handler: Async function that handles the event
        priority: Higher priority handlers are called first (default: 0)
    """

    event_type: str
    handler: EventHandler
    priority: int = 0


class Plugin(ABC):
    """
    Abstract base class for all Jarvis plugins.

    Plugins must implement:
    - name: Unique identifier for the plugin
    - version: Semantic version string
    - description: Human-readable description
    - on_load(): Called when plugin is loaded
    - on_unload(): Called when plugin is unloaded
    - get_commands(): Returns list of commands the plugin handles
    - get_handlers(): Returns list of event handlers

    Lifecycle:
    1. Plugin is instantiated
    2. on_load() is called
    3. Plugin handles commands and events
    4. on_unload() is called when shutting down
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the version string (e.g., '1.0.0')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of the plugin."""
        pass

    @abstractmethod
    async def on_load(self) -> bool:
        """
        Called when the plugin is loaded.

        Use this to initialize resources, connections, etc.

        Returns:
            True if loading was successful, False otherwise.
        """
        pass

    @abstractmethod
    async def on_unload(self) -> bool:
        """
        Called when the plugin is unloaded.

        Use this to cleanup resources, close connections, etc.

        Returns:
            True if unloading was successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_commands(self) -> List[Command]:
        """
        Return the list of commands this plugin handles.

        Returns:
            List of Command objects.
        """
        pass

    @abstractmethod
    def get_handlers(self) -> List[Handler]:
        """
        Return the list of event handlers this plugin provides.

        Returns:
            List of Handler objects.
        """
        pass

    def get_command_names(self) -> List[str]:
        """
        Return all command names including aliases.

        Returns:
            List of command names and aliases.
        """
        names = []
        for cmd in self.get_commands():
            names.append(cmd.name)
            names.extend(cmd.aliases)
        return names

    def get_command(self, name: str) -> Optional[Command]:
        """
        Get a command by name or alias.

        Args:
            name: The command name or alias to look up.

        Returns:
            The Command object if found, None otherwise.
        """
        for cmd in self.get_commands():
            if cmd.name == name or name in cmd.aliases:
                return cmd
        return None

    def get_handler_event_types(self) -> List[str]:
        """
        Return all event types this plugin handles.

        Returns:
            List of event type strings.
        """
        return [h.event_type for h in self.get_handlers()]

    async def handle_command(self, command_name: str, args: List[str]) -> Optional[str]:
        """
        Handle a command by name.

        Args:
            command_name: The name of the command to handle.
            args: Arguments passed to the command.

        Returns:
            The command response, or None if command not found.
        """
        cmd = self.get_command(command_name)
        if cmd is None:
            return None

        try:
            return await cmd.handler(args)
        except Exception as e:
            logger.error(f"Error handling command {command_name} in {self.name}: {e}")
            raise

    async def handle_event(
        self, event_type: str, data: Dict[str, Any]
    ) -> List[Optional[Any]]:
        """
        Handle an event by type.

        Args:
            event_type: The type of event to handle.
            data: Event data.

        Returns:
            List of results from all handlers for this event type.
        """
        results = []
        for handler in self.get_handlers():
            if handler.event_type == event_type:
                try:
                    result = await handler.handler(data)
                    results.append(result)
                except Exception as e:
                    logger.error(
                        f"Error handling event {event_type} in {self.name}: {e}"
                    )
                    results.append(None)
        return results

    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version}>"


# Legacy compatibility - keep old PluginMetadata and PluginManager for backwards compat
@dataclass
class PluginMetadata:
    """
    Legacy metadata class for backwards compatibility.

    New plugins should use the Plugin ABC properties directly.
    """

    name: str
    version: str
    description: str
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)


class PluginManager:
    """
    Legacy plugin manager for backwards compatibility.

    For new code, use PluginRegistry from core.plugins.registry instead.
    """

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self._initialized: set = set()

    def register(self, plugin: Plugin):
        """Register a plugin."""
        name = plugin.name
        if name in self.plugins:
            logger.warning(f"Plugin {name} already registered, replacing")
        self.plugins[name] = plugin
        logger.info(f"Registered plugin: {name} v{plugin.version}")

    def unregister(self, name: str):
        """Unregister a plugin."""
        if name in self.plugins:
            del self.plugins[name]
            self._initialized.discard(name)

    async def initialize_all(self, config: Dict[str, Any] = None):
        """Initialize all registered plugins."""
        config = config or {}

        for name, plugin in self.plugins.items():
            if name in self._initialized:
                continue

            try:
                success = await plugin.on_load()
                if success:
                    self._initialized.add(name)
                    logger.info(f"Initialized plugin: {name}")
                else:
                    logger.error(f"Failed to initialize plugin: {name}")
            except Exception as e:
                logger.error(f"Error initializing plugin {name}: {e}")

    async def shutdown_all(self):
        """Shutdown all plugins."""
        for name, plugin in self.plugins.items():
            if name not in self._initialized:
                continue
            try:
                await plugin.on_unload()
                self._initialized.discard(name)
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")

    def get_all_commands(self) -> Dict[str, List[str]]:
        """Get all commands from all plugins."""
        return {name: plugin.get_command_names() for name, plugin in self.plugins.items()}


# Global plugin manager instance (legacy)
plugin_manager = PluginManager()
