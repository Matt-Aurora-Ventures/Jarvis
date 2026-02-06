"""
Handler Registry for managing command handlers.

Provides:
- HandlerRegistry: Singleton registry for command handlers
- get_handler_registry: Function to get the global registry instance
"""

import logging
from typing import Dict, List, Optional

from core.handlers.base import CommandHandler

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """
    Singleton registry for command handlers.

    Manages registration, lookup, and help generation for handlers.

    Usage:
        registry = HandlerRegistry.instance()
        registry.register(MyHandler())
        handler = registry.get_handler("mycommand")
    """

    _instance: Optional["HandlerRegistry"] = None

    def __init__(self):
        """Initialize the registry with an empty handler dict."""
        self._handlers: Dict[str, CommandHandler] = {}

    @classmethod
    def instance(cls) -> "HandlerRegistry":
        """
        Get the singleton instance.

        Returns:
            The global HandlerRegistry instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing. Creates a fresh registry.
        """
        cls._instance = None

    def register(self, handler: CommandHandler) -> None:
        """
        Register a command handler.

        If a handler with the same command already exists, it will be replaced.

        Args:
            handler: The CommandHandler to register
        """
        command = handler.command.lower()
        if command in self._handlers:
            logger.warning(f"Replacing existing handler for command: {command}")
        self._handlers[command] = handler
        logger.debug(f"Registered handler: /{command}")

    def unregister(self, command: str) -> bool:
        """
        Unregister a command handler.

        Args:
            command: The command name to unregister

        Returns:
            True if handler was removed, False if not found
        """
        command = command.lower()
        if command in self._handlers:
            del self._handlers[command]
            logger.debug(f"Unregistered handler: /{command}")
            return True
        return False

    def get_handler(self, command: str) -> Optional[CommandHandler]:
        """
        Get a handler by command name.

        Args:
            command: The command name (case-insensitive)

        Returns:
            The CommandHandler or None if not found
        """
        return self._handlers.get(command.lower())

    def has_handler(self, command: str) -> bool:
        """
        Check if a handler is registered for a command.

        Args:
            command: The command name

        Returns:
            True if handler exists
        """
        return command.lower() in self._handlers

    def list_handlers(self) -> List[CommandHandler]:
        """
        Get all registered handlers.

        Returns:
            List of all CommandHandler instances
        """
        return list(self._handlers.values())

    def generate_help(self) -> str:
        """
        Generate help text for all registered commands.

        Returns:
            Formatted help text string
        """
        if not self._handlers:
            return "No commands registered."

        lines = ["Available Commands:", ""]

        # Sort handlers alphabetically by command name
        sorted_handlers = sorted(self._handlers.values(), key=lambda h: h.command)

        for handler in sorted_handlers:
            lines.append(f"/{handler.command} - {handler.description}")
            if handler.usage != f"/{handler.command}":
                lines.append(f"  Usage: {handler.usage}")
            lines.append("")

        return "\n".join(lines).strip()


def get_handler_registry() -> HandlerRegistry:
    """
    Get the global handler registry instance.

    Convenience function for accessing the singleton.

    Returns:
        The global HandlerRegistry instance
    """
    return HandlerRegistry.instance()
