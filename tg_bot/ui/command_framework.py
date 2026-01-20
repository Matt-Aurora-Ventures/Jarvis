"""
Command Framework for Telegram UI.

Provides:
- Structured command parsing
- Permission-based command access
- Command history/favorites
- Autocomplete for commands
"""

import logging
import re
import shlex
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ParsedCommand:
    """Result of parsing a command message."""
    command: str
    args: List[str]
    raw: str

    def get_arg(self, index: int, default: str = "") -> str:
        """Get argument at index or default."""
        if 0 <= index < len(self.args):
            return self.args[index]
        return default


class PermissionLevel(Enum):
    """Permission levels for command access."""
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a command."""
    max_calls: int
    window_seconds: int


@dataclass
class CommandUsage:
    """Record of a command usage."""
    command: str
    args: List[str]
    timestamp: datetime


# =============================================================================
# Command Parser
# =============================================================================


class CommandParser:
    """
    Parse Telegram command messages into structured data.

    Handles:
    - Basic commands: /help
    - Commands with args: /analyze SOL
    - Quoted args: /note "my note with spaces"
    - Bot mentions: /help@BotName
    """

    def __init__(self):
        self._command_pattern = re.compile(r'^/([a-zA-Z0-9_]+)(@[a-zA-Z0-9_]+)?(.*)$', re.DOTALL)

    def parse(self, text: str) -> Optional[ParsedCommand]:
        """
        Parse a message into a command.

        Args:
            text: Message text

        Returns:
            ParsedCommand or None if not a command
        """
        if not text or not text.strip():
            return None

        text = text.strip()

        if not text.startswith('/'):
            return None

        match = self._command_pattern.match(text)
        if not match:
            return None

        command = match.group(1).lower()
        args_text = match.group(3).strip() if match.group(3) else ""

        # Parse arguments (handle quoted strings)
        try:
            args = shlex.split(args_text) if args_text else []
        except ValueError:
            # Fallback for malformed quotes
            args = args_text.split() if args_text else []

        return ParsedCommand(command=command, args=args, raw=text)


# =============================================================================
# Command Permissions
# =============================================================================


class CommandPermissions:
    """
    Manage command permissions and access control.

    Features:
    - Admin/superadmin levels
    - Rate limiting
    - User-specific permissions
    """

    def __init__(
        self,
        admin_ids: Optional[Set[int]] = None,
        superadmin_ids: Optional[Set[int]] = None,
    ):
        """
        Initialize CommandPermissions.

        Args:
            admin_ids: Set of admin user IDs
            superadmin_ids: Set of superadmin user IDs
        """
        self.admin_ids = admin_ids or set()
        self.superadmin_ids = superadmin_ids or set()
        self._command_levels: Dict[str, PermissionLevel] = {}
        self._rate_limits: Dict[str, RateLimitConfig] = {}
        self._rate_limit_calls: Dict[str, List[datetime]] = defaultdict(list)

    def register_admin_command(self, command: str) -> None:
        """Register a command as admin-only."""
        self._command_levels[command] = PermissionLevel.ADMIN

    def register_command(self, command: str, level: PermissionLevel) -> None:
        """Register a command with a specific permission level."""
        self._command_levels[command] = level

    def requires_admin(self, command: str) -> bool:
        """Check if command requires admin."""
        level = self._command_levels.get(command, PermissionLevel.USER)
        return level in (PermissionLevel.ADMIN, PermissionLevel.SUPERADMIN)

    def can_execute(self, user_id: int, command: str) -> bool:
        """
        Check if user can execute command.

        Args:
            user_id: User ID to check
            command: Command name

        Returns:
            True if user can execute
        """
        level = self._command_levels.get(command, PermissionLevel.USER)

        if level == PermissionLevel.USER:
            return True

        if level == PermissionLevel.ADMIN:
            return user_id in self.admin_ids or user_id in self.superadmin_ids

        if level == PermissionLevel.SUPERADMIN:
            return user_id in self.superadmin_ids

        return False

    def set_rate_limit(
        self,
        command: str,
        max_calls: int,
        window_seconds: int,
    ) -> None:
        """
        Set rate limit for a command.

        Args:
            command: Command name
            max_calls: Maximum calls allowed
            window_seconds: Time window in seconds
        """
        self._rate_limits[command] = RateLimitConfig(
            max_calls=max_calls,
            window_seconds=window_seconds,
        )

    def check_rate_limit(self, user_id: int, command: str) -> bool:
        """
        Check if user is within rate limit.

        Args:
            user_id: User ID
            command: Command name

        Returns:
            True if within limit, False if rate limited
        """
        if command not in self._rate_limits:
            return True

        config = self._rate_limits[command]
        key = f"{user_id}:{command}"
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=config.window_seconds)

        # Clean old entries
        self._rate_limit_calls[key] = [
            t for t in self._rate_limit_calls[key]
            if t > cutoff
        ]

        # Check limit
        if len(self._rate_limit_calls[key]) >= config.max_calls:
            return False

        # Record this call
        self._rate_limit_calls[key].append(now)
        return True


# =============================================================================
# Command History
# =============================================================================


class CommandHistory:
    """
    Track command history and favorites per user.

    Features:
    - Recent command history
    - Favorite commands
    - Usage statistics
    """

    MAX_HISTORY = 100
    MAX_FAVORITES = 20

    def __init__(self):
        self._history: Dict[int, List[CommandUsage]] = defaultdict(list)
        self._favorites: Dict[int, List[str]] = defaultdict(list)

    def record(
        self,
        user_id: int,
        command: str,
        args: Optional[List[str]] = None,
    ) -> None:
        """
        Record a command execution.

        Args:
            user_id: User ID
            command: Command name
            args: Command arguments
        """
        usage = CommandUsage(
            command=command,
            args=args or [],
            timestamp=datetime.utcnow(),
        )

        history = self._history[user_id]
        history.append(usage)

        # Trim if too long
        if len(history) > self.MAX_HISTORY:
            self._history[user_id] = history[-self.MAX_HISTORY:]

    def get_recent(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent command history.

        Args:
            user_id: User ID
            limit: Maximum entries to return

        Returns:
            List of command usage dicts
        """
        history = self._history.get(user_id, [])
        recent = list(reversed(history[-limit:]))
        return [
            {
                "command": u.command,
                "args": u.args,
                "timestamp": u.timestamp.isoformat(),
            }
            for u in recent
        ]

    def add_favorite(self, user_id: int, command_str: str) -> bool:
        """
        Add a command to favorites.

        Args:
            user_id: User ID
            command_str: Full command string

        Returns:
            True if added
        """
        favorites = self._favorites[user_id]

        if command_str in favorites:
            return False

        favorites.append(command_str)

        # Trim if too many
        if len(favorites) > self.MAX_FAVORITES:
            self._favorites[user_id] = favorites[-self.MAX_FAVORITES:]

        return True

    def remove_favorite(self, user_id: int, command_str: str) -> bool:
        """
        Remove a command from favorites.

        Args:
            user_id: User ID
            command_str: Full command string

        Returns:
            True if removed
        """
        favorites = self._favorites[user_id]

        if command_str not in favorites:
            return False

        favorites.remove(command_str)
        return True

    def get_favorites(self, user_id: int) -> List[str]:
        """
        Get user's favorite commands.

        Args:
            user_id: User ID

        Returns:
            List of favorite command strings
        """
        return self._favorites.get(user_id, []).copy()

    def get_most_used(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get most frequently used commands.

        Args:
            user_id: User ID
            limit: Maximum entries to return

        Returns:
            List of {command, count} dicts
        """
        history = self._history.get(user_id, [])

        # Count commands
        counts: Dict[str, int] = defaultdict(int)
        for usage in history:
            counts[usage.command] += 1

        # Sort by count
        sorted_commands = sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {"command": cmd, "count": count}
            for cmd, count in sorted_commands[:limit]
        ]


# =============================================================================
# Command Autocomplete
# =============================================================================


class CommandAutocomplete:
    """
    Provide command autocomplete suggestions.

    Features:
    - Command name completion
    - Argument suggestions
    - Fuzzy matching
    """

    # Default popular commands
    DEFAULT_COMMANDS = [
        "/help", "/trending", "/status", "/analyze", "/positions",
        "/balance", "/watchlist", "/dashboard", "/report", "/digest",
        "/signals", "/chart", "/sentiment", "/calibrate",
    ]

    def __init__(self, commands: Optional[List[str]] = None):
        """
        Initialize CommandAutocomplete.

        Args:
            commands: List of available commands
        """
        self._commands = commands or self.DEFAULT_COMMANDS.copy()
        self._arg_suggestions: Dict[str, List[str]] = {}

    def register_arg_suggestions(self, command: str, suggestions: List[str]) -> None:
        """
        Register argument suggestions for a command.

        Args:
            command: Command name (without /)
            suggestions: List of suggested arguments
        """
        self._arg_suggestions[command] = suggestions

    def suggest(
        self,
        partial: str,
        limit: int = 10,
    ) -> List[str]:
        """
        Get autocomplete suggestions.

        Args:
            partial: Partial input text
            limit: Maximum suggestions

        Returns:
            List of suggestions
        """
        partial = partial.strip()
        partial_lower = partial.lower()

        # Empty input - return popular commands
        if not partial:
            return self._commands[:limit]

        # Check if completing arguments (has space after command)
        if partial.startswith('/') and ' ' in partial:
            parts = partial.split(' ', 1)
            command = parts[0][1:].lower()  # Remove / and lowercase

            if command in self._arg_suggestions:
                arg_partial = parts[1].lower() if len(parts) > 1 else ""
                suggestions = [
                    f"/{command} {arg}"
                    for arg in self._arg_suggestions[command]
                    if arg_partial == "" or arg.lower().startswith(arg_partial)
                ]
                return suggestions[:limit]

        # Completing command name
        search_term = partial_lower[1:] if partial_lower.startswith('/') else partial_lower

        matches = [
            cmd for cmd in self._commands
            if cmd[1:].lower().startswith(search_term)  # Skip leading /
        ]

        return matches[:limit]


# =============================================================================
# Command Executor
# =============================================================================


class CommandExecutor:
    """
    Execute commands with middleware support.

    Features:
    - Handler registration
    - Middleware pipeline
    - Error handling
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []

    def register(self, command: str, handler: Callable) -> None:
        """
        Register a command handler.

        Args:
            command: Command name
            handler: Async handler function
        """
        self._handlers[command] = handler

    def add_middleware(self, middleware: Callable) -> None:
        """
        Add middleware to the execution pipeline.

        Args:
            middleware: Async middleware function
        """
        self._middleware.append(middleware)

    async def execute(
        self,
        command: str,
        args: List[str],
        update: Any,
        context: Any,
    ) -> str:
        """
        Execute a command.

        Args:
            command: Command name
            args: Command arguments
            update: Telegram update
            context: Telegram context

        Returns:
            Result message
        """
        if command not in self._handlers:
            return f"Unknown command: /{command}"

        handler = self._handlers[command]

        # Build middleware chain
        async def run_handler():
            return await handler(update, context, args)

        # Run through middleware
        next_fn = run_handler
        for middleware in reversed(self._middleware):
            current_next = next_fn

            async def wrapped_next(mw=middleware, nxt=current_next):
                return await mw(update, context, command, args, nxt)

            next_fn = wrapped_next

        # Execute
        try:
            return await next_fn()
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return f"Error executing /{command}: {str(e)[:100]}"


# =============================================================================
# Singleton Instances
# =============================================================================

_parser: Optional[CommandParser] = None
_permissions: Optional[CommandPermissions] = None
_history: Optional[CommandHistory] = None
_autocomplete: Optional[CommandAutocomplete] = None


def get_command_parser() -> CommandParser:
    """Get the global CommandParser instance."""
    global _parser
    if _parser is None:
        _parser = CommandParser()
    return _parser


def get_command_permissions() -> CommandPermissions:
    """Get the global CommandPermissions instance."""
    global _permissions
    if _permissions is None:
        _permissions = CommandPermissions()
    return _permissions


def get_command_history() -> CommandHistory:
    """Get the global CommandHistory instance."""
    global _history
    if _history is None:
        _history = CommandHistory()
    return _history


def get_command_autocomplete() -> CommandAutocomplete:
    """Get the global CommandAutocomplete instance."""
    global _autocomplete
    if _autocomplete is None:
        _autocomplete = CommandAutocomplete()
    return _autocomplete


__all__ = [
    "ParsedCommand",
    "PermissionLevel",
    "CommandParser",
    "CommandPermissions",
    "CommandHistory",
    "CommandAutocomplete",
    "CommandExecutor",
    "get_command_parser",
    "get_command_permissions",
    "get_command_history",
    "get_command_autocomplete",
]
