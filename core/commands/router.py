"""
Command Router - Pattern-based command routing system.

This module provides command routing infrastructure:
- CommandRouter for pattern registration and route matching
- Support for regex patterns and prefix matching
- Priority-based route ordering
- CommandInfo for command metadata
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple, Pattern
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CommandInfo:
    """
    Information about a registered command.

    Attributes:
        pattern: The command pattern (string or regex)
        handler: The async callable that handles this command
        description: Human-readable description
        category: Category for grouping
        is_regex: Whether the pattern is a regex
        priority: Priority for matching (higher = first)
    """
    pattern: str
    handler: Callable
    description: str = ""
    category: str = "default"
    is_regex: bool = False
    priority: int = 0
    _compiled_pattern: Optional[Pattern] = field(default=None, repr=False)


@dataclass
class RouteResult:
    """
    Result of a successful route match.

    Attributes:
        handler: The matched handler
        pattern: The matched pattern string
        groups: Regex capture groups (if any)
        raw_message: The original message
    """
    handler: Callable
    pattern: str
    groups: Tuple[str, ...] = field(default_factory=tuple)
    raw_message: str = ""


class CommandRouter:
    """
    Route messages to command handlers based on pattern matching.

    Features:
    - Register commands with patterns (string or regex)
    - Priority-based matching
    - Case-insensitive matching by default
    - Support for custom command prefix
    """

    def __init__(
        self,
        prefix: str = "/",
        case_sensitive: bool = False
    ):
        """
        Initialize the router.

        Args:
            prefix: Command prefix (default "/")
            case_sensitive: Whether matching is case-sensitive
        """
        self.prefix = prefix
        self.case_sensitive = case_sensitive
        self._commands: List[CommandInfo] = []

    def register(
        self,
        pattern: str,
        handler: Callable,
        description: str = "",
        category: str = "default",
        is_regex: bool = False,
        priority: int = 0
    ) -> None:
        """
        Register a command handler.

        Args:
            pattern: Command pattern (string for prefix match, or regex)
            handler: Async callable to handle the command
            description: Human-readable description
            category: Category for grouping
            is_regex: Whether pattern is a regex
            priority: Priority for matching (higher = first)
        """
        # Compile regex if needed
        compiled_pattern = None
        if is_regex:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            compiled_pattern = re.compile(pattern, flags)

        cmd_info = CommandInfo(
            pattern=pattern,
            handler=handler,
            description=description,
            category=category,
            is_regex=is_regex,
            priority=priority,
            _compiled_pattern=compiled_pattern
        )

        self._commands.append(cmd_info)
        # Re-sort by priority (descending)
        self._commands.sort(key=lambda c: c.priority, reverse=True)

        logger.debug(
            f"Registered command pattern: {pattern} "
            f"(priority: {priority}, regex: {is_regex})"
        )

    def unregister(self, pattern: str) -> bool:
        """
        Unregister a command by pattern.

        Args:
            pattern: The pattern to unregister

        Returns:
            True if found and removed, False otherwise
        """
        for i, cmd in enumerate(self._commands):
            if cmd.pattern == pattern:
                self._commands.pop(i)
                logger.debug(f"Unregistered command pattern: {pattern}")
                return True
        return False

    def route(self, message: str) -> Optional[RouteResult]:
        """
        Route a message to a handler.

        Args:
            message: The message to route

        Returns:
            RouteResult if matched, None otherwise
        """
        if not message:
            return None

        # Strip whitespace
        message = message.strip()

        # Check for prefix
        if not message.startswith(self.prefix):
            return None

        # Remove prefix
        content = message[len(self.prefix):]
        if not content:
            return None

        # Handle @botname suffix (e.g., /status@JarvisBot)
        if "@" in content.split()[0]:
            first_part = content.split()[0]
            command_part = first_part.split("@")[0]
            rest = content[len(first_part):].strip()
            content = command_part + (" " + rest if rest else "")

        # Try each pattern
        for cmd in self._commands:
            if cmd.is_regex:
                match = self._match_regex(cmd, content)
            else:
                match = self._match_prefix(cmd, content)

            if match is not None:
                handler, groups = match
                return RouteResult(
                    handler=handler,
                    pattern=cmd.pattern,
                    groups=groups,
                    raw_message=message
                )

        return None

    def _match_prefix(
        self,
        cmd: CommandInfo,
        content: str
    ) -> Optional[Tuple[Callable, Tuple[str, ...]]]:
        """Match using prefix matching."""
        # Get the command word
        parts = content.split(None, 1)
        if not parts:
            return None

        command_word = parts[0]

        # Compare command
        if self.case_sensitive:
            if command_word == cmd.pattern:
                return (cmd.handler, ())
        else:
            if command_word.lower() == cmd.pattern.lower():
                return (cmd.handler, ())

        return None

    def _match_regex(
        self,
        cmd: CommandInfo,
        content: str
    ) -> Optional[Tuple[Callable, Tuple[str, ...]]]:
        """Match using regex pattern."""
        if cmd._compiled_pattern is None:
            return None

        match = cmd._compiled_pattern.match(content)
        if match:
            return (cmd.handler, match.groups())

        return None

    def get_commands(self, category: str = None) -> List[CommandInfo]:
        """
        Get registered commands.

        Args:
            category: Optional category filter

        Returns:
            List of CommandInfo objects
        """
        commands = self._commands.copy()

        if category:
            commands = [c for c in commands if c.category == category]

        return commands

    def command(
        self,
        pattern: str,
        description: str = "",
        category: str = "default",
        is_regex: bool = False,
        priority: int = 0
    ):
        """
        Decorator to register a command handler.

        Usage:
            @router.command("help", description="Show help")
            async def help_handler(ctx):
                return "Help text..."
        """
        def decorator(func: Callable):
            self.register(
                pattern=pattern,
                handler=func,
                description=description,
                category=category,
                is_regex=is_regex,
                priority=priority
            )

            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return func  # Return original function

        return decorator
