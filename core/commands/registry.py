"""
Command Registry - Central command registration and execution.

This module provides the core command infrastructure:
- Command dataclass for defining commands
- CommandRegistry for registration, lookup, and execution
- Auto-help generation
- Decorator-based registration
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from functools import wraps
import inspect

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class CommandError(Exception):
    """Base exception for command system errors."""
    pass


class CommandNotFoundError(CommandError):
    """Raised when a command is not found."""
    pass


class CommandAlreadyExistsError(CommandError):
    """Raised when attempting to register a duplicate command."""
    pass


class AliasConflictError(CommandError):
    """Raised when an alias conflicts with an existing command or alias."""
    pass


class PermissionDeniedError(CommandError):
    """Raised when user lacks permission to execute a command."""
    pass


# ============================================================================
# Command Dataclass
# ============================================================================

@dataclass
class Command:
    """
    A command definition.

    Attributes:
        name: The primary command name (e.g., "help")
        description: Human-readable description
        handler: Async callable that executes the command
        category: Category for grouping (e.g., "core", "trading", "ai")
        aliases: Alternative names for the command (e.g., ["h", "?"])
        admin_only: Whether this command requires admin privileges
        args_schema: Optional schema for argument validation
        usage: Usage string (e.g., "/trade <token> <amount>")
        examples: Example usages
    """
    name: str
    description: str
    handler: Callable
    category: str
    aliases: List[str] = field(default_factory=list)
    admin_only: bool = False
    args_schema: Optional[Dict] = None
    usage: str = ""
    examples: List[str] = field(default_factory=list)


# ============================================================================
# Command Registry
# ============================================================================

class CommandRegistry:
    """
    Central registry for command registration and execution.

    Features:
    - Register commands with aliases
    - Look up commands by name or alias
    - Execute commands with context
    - Generate help text
    - Filter by category
    """

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name

    def register(self, cmd: Command) -> None:
        """
        Register a command.

        Args:
            cmd: The Command to register

        Raises:
            CommandAlreadyExistsError: If command name already exists
            AliasConflictError: If an alias conflicts with existing command/alias
        """
        # Check for duplicate command name
        if cmd.name in self._commands:
            raise CommandAlreadyExistsError(
                f"Command '{cmd.name}' is already registered"
            )

        # Check for alias conflicts
        if cmd.name in self._aliases:
            raise AliasConflictError(
                f"Command name '{cmd.name}' conflicts with existing alias"
            )

        for alias in cmd.aliases:
            if alias in self._commands:
                raise AliasConflictError(
                    f"Alias '{alias}' conflicts with existing command"
                )
            if alias in self._aliases:
                raise AliasConflictError(
                    f"Alias '{alias}' is already registered for command "
                    f"'{self._aliases[alias]}'"
                )

        # Register the command
        self._commands[cmd.name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name
            logger.debug(f"Registered alias '{alias}' -> '{cmd.name}'")

        logger.info(
            f"Registered command: /{cmd.name} "
            f"(aliases: {cmd.aliases}, category: {cmd.category})"
        )

    def get_command(self, name: str) -> Optional[Command]:
        """
        Get a command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            The Command if found, None otherwise
        """
        # Direct match
        if name in self._commands:
            return self._commands[name]

        # Alias match
        if name in self._aliases:
            return self._commands[self._aliases[name]]

        return None

    def resolve_alias(self, name: str) -> str:
        """
        Resolve an alias to its command name.

        Args:
            name: Command name or alias

        Returns:
            The canonical command name (or input if not an alias)
        """
        return self._aliases.get(name, name)

    def list_commands(self, category: str = None) -> List[Command]:
        """
        List all registered commands.

        Args:
            category: Optional category filter

        Returns:
            List of Command objects
        """
        commands = list(self._commands.values())

        if category:
            commands = [c for c in commands if c.category == category]

        return commands

    def get_categories(self) -> List[str]:
        """
        Get list of all categories.

        Returns:
            List of unique category names
        """
        categories: Set[str] = set()
        for cmd in self._commands.values():
            categories.add(cmd.category)
        return sorted(list(categories))

    async def execute(self, command_name: str, context: Dict[str, Any]) -> Any:
        """
        Execute a command.

        Args:
            command_name: Command name or alias
            context: Execution context containing:
                - user_id: User identifier
                - is_admin: Whether user is admin (optional)
                - args: Command arguments (optional)
                - Additional context as needed

        Returns:
            The result from the command handler

        Raises:
            CommandNotFoundError: If command doesn't exist
            PermissionDeniedError: If user lacks permission
        """
        cmd = self.get_command(command_name)

        if cmd is None:
            raise CommandNotFoundError(f"Command '{command_name}' not found")

        # Check admin permission
        if cmd.admin_only:
            is_admin = context.get("is_admin", False)
            if not is_admin:
                raise PermissionDeniedError(
                    f"Command '/{cmd.name}' requires admin privileges"
                )

        # Enrich context with command info
        enriched_context = {
            **context,
            "command_name": cmd.name,
            "invoked_as": command_name,
        }

        # Execute the handler
        if inspect.iscoroutinefunction(cmd.handler):
            result = await cmd.handler(enriched_context)
        else:
            result = cmd.handler(enriched_context)

        return result

    def generate_help(self, command_name: str = None) -> str:
        """
        Generate help text.

        Args:
            command_name: Optional specific command to get help for

        Returns:
            Formatted help text
        """
        if command_name:
            return self._generate_command_help(command_name)
        return self._generate_all_help()

    def _generate_command_help(self, command_name: str) -> str:
        """Generate help for a specific command."""
        cmd = self.get_command(command_name)

        if cmd is None:
            return f"Unknown command: {command_name}"

        lines = [f"/{cmd.name} - {cmd.description}"]

        if cmd.aliases:
            alias_str = ", ".join(f"/{a}" for a in cmd.aliases)
            lines.append(f"Aliases: {alias_str}")

        if cmd.usage:
            lines.append(f"Usage: {cmd.usage}")

        if cmd.examples:
            lines.append("Examples:")
            for ex in cmd.examples:
                lines.append(f"  {ex}")

        if cmd.admin_only:
            lines.append("(Admin only)")

        return "\n".join(lines)

    def _generate_all_help(self) -> str:
        """Generate help for all commands."""
        lines = ["Available Commands", ""]

        # Group by category
        categories = self.get_categories()

        # Define display order (core first, then alphabetical)
        category_order = ["core", "ai", "session", "trading", "admin"]
        ordered_categories = []
        for cat in category_order:
            if cat in categories:
                ordered_categories.append(cat)
        for cat in categories:
            if cat not in ordered_categories:
                ordered_categories.append(cat)

        for category in ordered_categories:
            commands = self.list_commands(category=category)
            if not commands:
                continue

            # Category header
            lines.append(f"**{category.title()}**")

            for cmd in sorted(commands, key=lambda c: c.name):
                admin_marker = " (admin)" if cmd.admin_only else ""
                lines.append(f"  /{cmd.name} - {cmd.description}{admin_marker}")

            lines.append("")

        lines.append("Use /help <command> for detailed help")

        return "\n".join(lines)

    def command(
        self,
        name: str,
        description: str,
        category: str,
        aliases: List[str] = None,
        admin_only: bool = False,
        args_schema: Dict = None,
        usage: str = "",
        examples: List[str] = None
    ):
        """
        Decorator to register a command handler.

        Usage:
            @registry.command(
                name="help",
                description="Show help",
                category="core",
                aliases=["h", "?"]
            )
            async def help_handler(ctx):
                return "Help text..."
        """
        def decorator(func: Callable):
            cmd = Command(
                name=name,
                description=description or func.__doc__ or "",
                handler=func,
                category=category,
                aliases=aliases or [],
                admin_only=admin_only,
                args_schema=args_schema,
                usage=usage,
                examples=examples or []
            )
            self.register(cmd)

            @wraps(func)
            async def wrapper(*args, **kwargs):
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            return func  # Return original function, not wrapper

        return decorator
