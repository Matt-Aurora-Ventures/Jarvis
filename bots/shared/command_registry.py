"""
Command Registry System for ClawdBots.

Provides centralized command registration, execution, and statistics tracking
for all ClawdBot instances (Jarvis, Friday, Matt, etc.).

Features:
- Register commands with descriptions and handlers
- Command aliases support
- Usage statistics tracking with persistence
- Dynamic enable/disable commands
- Help text generation
- Decorator syntax support

Usage:
    from bots.shared.command_registry import CommandRegistry, get_global_registry

    # Create a registry for your bot
    registry = CommandRegistry(bot_name="ClawdJarvis")

    # Register commands
    registry.register_command(
        name="hello",
        handler=hello_handler,
        description="Say hello",
        aliases=["hi", "hey"]
    )

    # Or use decorator syntax
    @registry.command(name="greet", description="Greet user")
    def greet_handler(name):
        return f"Hello, {name}!"

    # Execute commands
    result = registry.execute_command("hello", arg1, arg2)

    # Get help
    help_text = registry.get_help_text()
"""

import json
import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Default stats file location (VPS path)
DEFAULT_STATS_FILE = "/root/clawdbots/command_stats.json"


# =============================================================================
# Exceptions
# =============================================================================


class CommandRegistryError(Exception):
    """Base exception for command registry errors."""
    pass


class CommandNotFoundError(CommandRegistryError):
    """Raised when a command is not found."""
    pass


class CommandDisabledError(CommandRegistryError):
    """Raised when attempting to execute a disabled command."""
    pass


class DuplicateCommandError(CommandRegistryError):
    """Raised when registering a duplicate command or alias."""
    pass


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class CommandInfo:
    """Information about a registered command."""

    name: str
    description: str
    handler: Callable
    aliases: List[str] = field(default_factory=list)
    enabled: bool = True
    usage_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes non-serializable handler)."""
        return {
            "name": self.name,
            "description": self.description,
            "aliases": self.aliases,
            "enabled": self.enabled,
            "usage_count": self.usage_count,
        }


# =============================================================================
# Command Registry
# =============================================================================


class CommandRegistry:
    """
    Central registry for bot commands.

    Manages command registration, execution, and statistics tracking.
    Each bot instance should have its own registry.
    """

    def __init__(
        self,
        bot_name: Optional[str] = None,
        stats_file: Optional[str] = None,
        auto_save: bool = False,
    ):
        """
        Initialize the command registry.

        Args:
            bot_name: Name of the bot this registry belongs to
            stats_file: Path to JSON file for persisting stats
            auto_save: If True, save stats after each command execution
        """
        self.bot_name = bot_name
        self.stats_file = stats_file or DEFAULT_STATS_FILE
        self.auto_save = auto_save

        # Internal storage
        self._commands: Dict[str, CommandInfo] = {}
        self._aliases: Dict[str, str] = {}  # alias -> primary name

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str,
        aliases: Optional[List[str]] = None,
        force: bool = False,
    ) -> CommandInfo:
        """
        Register a command with the registry.

        Args:
            name: Primary command name
            handler: Function to call when command is executed
            description: Human-readable description
            aliases: Optional list of alternative names
            force: If True, replace existing command with same name

        Returns:
            CommandInfo for the registered command

        Raises:
            DuplicateCommandError: If name or alias already exists (and force=False)
        """
        aliases = aliases or []

        # Check for duplicates (unless forcing)
        if not force:
            if name in self._commands:
                raise DuplicateCommandError(f"Command '{name}' already registered")

            if name in self._aliases:
                raise DuplicateCommandError(f"Name '{name}' conflicts with existing alias")

            for alias in aliases:
                if alias in self._commands:
                    raise DuplicateCommandError(f"Alias '{alias}' conflicts with existing command")
                if alias in self._aliases:
                    raise DuplicateCommandError(f"Alias '{alias}' already registered")

        # If forcing, remove old command and aliases first
        if force and name in self._commands:
            old_info = self._commands[name]
            for old_alias in old_info.aliases:
                self._aliases.pop(old_alias, None)

        # Create command info
        info = CommandInfo(
            name=name,
            description=description,
            handler=handler,
            aliases=aliases,
        )

        # Register command and aliases
        self._commands[name] = info
        for alias in aliases:
            self._aliases[alias] = name

        logger.debug(f"Registered command '{name}' with aliases {aliases}")
        return info

    def command(
        self,
        name: str,
        description: str,
        aliases: Optional[List[str]] = None,
    ) -> Callable:
        """
        Decorator for registering commands.

        Usage:
            @registry.command(name="greet", description="Greet user")
            def greet(name):
                return f"Hello, {name}!"
        """
        def decorator(func: Callable) -> Callable:
            self.register_command(
                name=name,
                handler=func,
                description=description,
                aliases=aliases,
            )
            return func
        return decorator

    def unregister_command(self, name: str) -> None:
        """
        Remove a command from the registry.

        Args:
            name: Command name to remove

        Raises:
            CommandNotFoundError: If command doesn't exist
        """
        if name not in self._commands:
            raise CommandNotFoundError(f"Command '{name}' not found")

        info = self._commands[name]

        # Remove aliases
        for alias in info.aliases:
            self._aliases.pop(alias, None)

        # Remove command
        del self._commands[name]

        logger.debug(f"Unregistered command '{name}'")

    def get_command(self, name: str) -> Optional[CommandInfo]:
        """
        Get command info by name or alias.

        Args:
            name: Command name or alias

        Returns:
            CommandInfo if found, None otherwise
        """
        # Check if it's a direct command name
        if name in self._commands:
            return self._commands[name]

        # Check if it's an alias
        if name in self._aliases:
            primary_name = self._aliases[name]
            return self._commands.get(primary_name)

        return None

    def list_commands(self, enabled_only: bool = False) -> List[CommandInfo]:
        """
        List all registered commands.

        Args:
            enabled_only: If True, only return enabled commands

        Returns:
            List of CommandInfo objects
        """
        commands = list(self._commands.values())

        if enabled_only:
            commands = [c for c in commands if c.enabled]

        return commands

    def execute_command(self, name: str, *args, **kwargs) -> Any:
        """
        Execute a command by name or alias.

        Args:
            name: Command name or alias
            *args: Positional arguments to pass to handler
            **kwargs: Keyword arguments to pass to handler

        Returns:
            Result from the command handler

        Raises:
            CommandNotFoundError: If command doesn't exist
            CommandDisabledError: If command is disabled
        """
        info = self.get_command(name)

        if info is None:
            raise CommandNotFoundError(f"Command '{name}' not found")

        if not info.enabled:
            raise CommandDisabledError(f"Command '{name}' is disabled")

        # Increment usage count
        info.usage_count += 1

        # Execute handler
        result = info.handler(*args, **kwargs)

        # Auto-save if configured
        if self.auto_save:
            self.save_stats()

        return result

    async def execute_command_async(self, name: str, *args, **kwargs) -> Any:
        """
        Execute a command asynchronously.

        Args:
            name: Command name or alias
            *args: Positional arguments to pass to handler
            **kwargs: Keyword arguments to pass to handler

        Returns:
            Result from the command handler

        Raises:
            CommandNotFoundError: If command doesn't exist
            CommandDisabledError: If command is disabled
        """
        info = self.get_command(name)

        if info is None:
            raise CommandNotFoundError(f"Command '{name}' not found")

        if not info.enabled:
            raise CommandDisabledError(f"Command '{name}' is disabled")

        # Increment usage count
        info.usage_count += 1

        # Execute handler (handle both sync and async)
        if asyncio.iscoroutinefunction(info.handler):
            result = await info.handler(*args, **kwargs)
        else:
            result = info.handler(*args, **kwargs)

        # Auto-save if configured
        if self.auto_save:
            self.save_stats()

        return result

    def enable_command(self, name: str) -> None:
        """
        Enable a disabled command.

        Args:
            name: Command name

        Raises:
            CommandNotFoundError: If command doesn't exist
        """
        info = self.get_command(name)

        if info is None:
            raise CommandNotFoundError(f"Command '{name}' not found")

        info.enabled = True
        logger.debug(f"Enabled command '{name}'")

    def disable_command(self, name: str) -> None:
        """
        Disable an enabled command.

        Args:
            name: Command name

        Raises:
            CommandNotFoundError: If command doesn't exist
        """
        info = self.get_command(name)

        if info is None:
            raise CommandNotFoundError(f"Command '{name}' not found")

        info.enabled = False
        logger.debug(f"Disabled command '{name}'")

    def get_command_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get usage statistics for all commands.

        Returns:
            Dictionary mapping command names to their stats
        """
        stats = {}
        for name, info in self._commands.items():
            stats[name] = {
                "usage_count": info.usage_count,
                "enabled": info.enabled,
                "aliases": info.aliases,
            }
        return stats

    def reset_stats(self) -> None:
        """Reset all usage counts to zero."""
        for info in self._commands.values():
            info.usage_count = 0
        logger.debug("Reset all command stats")

    def save_stats(self) -> None:
        """Save command stats to JSON file."""
        stats = {}
        for name, info in self._commands.items():
            stats[name] = {
                "usage_count": info.usage_count,
                "enabled": info.enabled,
            }

        stats_path = Path(self.stats_file)
        stats_path.parent.mkdir(parents=True, exist_ok=True)

        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2)

        logger.debug(f"Saved stats to {self.stats_file}")

    def load_stats(self) -> None:
        """Load command stats from JSON file."""
        stats_path = Path(self.stats_file)

        if not stats_path.exists():
            logger.debug(f"Stats file not found: {self.stats_file}")
            return

        try:
            with open(stats_path) as f:
                stats = json.load(f)

            for name, data in stats.items():
                if name in self._commands:
                    self._commands[name].usage_count = data.get("usage_count", 0)
                    self._commands[name].enabled = data.get("enabled", True)

            logger.debug(f"Loaded stats from {self.stats_file}")

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load stats: {e}")

    def get_help_text(self, include_disabled: bool = False) -> str:
        """
        Generate formatted help text for all commands.

        Args:
            include_disabled: If True, include disabled commands

        Returns:
            Formatted help text string
        """
        lines = []

        if self.bot_name:
            lines.append(f"Commands for {self.bot_name}:")
        else:
            lines.append("Available Commands:")

        lines.append("")

        commands = self.list_commands(enabled_only=not include_disabled)
        commands.sort(key=lambda c: c.name)

        for cmd in commands:
            # Format: /name - Description
            alias_str = ""
            if cmd.aliases:
                alias_str = f" (aliases: {', '.join(cmd.aliases)})"

            status = ""
            if not cmd.enabled:
                status = " [DISABLED]"

            lines.append(f"  /{cmd.name}{alias_str} - {cmd.description}{status}")

        return "\n".join(lines)


# =============================================================================
# Global Registry
# =============================================================================

_global_registry: Optional[CommandRegistry] = None


def get_global_registry() -> Optional[CommandRegistry]:
    """Get the global command registry."""
    return _global_registry


def set_global_registry(registry: CommandRegistry) -> None:
    """Set the global command registry."""
    global _global_registry
    _global_registry = registry


# =============================================================================
# Convenience Functions
# =============================================================================


def create_bot_registry(
    bot_name: str,
    stats_file: Optional[str] = None,
    auto_save: bool = True,
) -> CommandRegistry:
    """
    Create a command registry for a specific bot.

    Args:
        bot_name: Name of the bot (e.g., "ClawdJarvis")
        stats_file: Optional custom stats file path
        auto_save: Whether to auto-save stats after commands

    Returns:
        Configured CommandRegistry instance
    """
    if stats_file is None:
        # Use bot-specific stats file
        safe_name = bot_name.lower().replace(" ", "_")
        stats_file = f"/root/clawdbots/{safe_name}_command_stats.json"

    return CommandRegistry(
        bot_name=bot_name,
        stats_file=stats_file,
        auto_save=auto_save,
    )
