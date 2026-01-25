"""
Jarvis Command System - Clawdbot-style slash commands.

This module provides a centralized command registration and execution system
for all Jarvis interfaces (Telegram, CLI, API).

Usage:
    from core.commands import get_command_registry

    registry = get_command_registry()
    help_text = registry.generate_help()
"""

from core.commands.registry import (
    Command,
    CommandRegistry,
    CommandNotFoundError,
    CommandAlreadyExistsError,
    AliasConflictError,
    PermissionDeniedError,
)

# Global registry singleton
_global_registry: CommandRegistry = None


def get_command_registry() -> CommandRegistry:
    """
    Get the global command registry singleton.

    Returns a fully initialized registry with all standard commands registered.
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = CommandRegistry()
        _initialize_commands(_global_registry)

    return _global_registry


def _initialize_commands(registry: CommandRegistry) -> None:
    """Initialize the registry with all standard commands."""
    from core.commands.core import register_core_commands
    from core.commands.ai import register_ai_commands
    from core.commands.session import register_session_commands
    from core.commands.trading import register_trading_commands

    register_core_commands(registry)
    register_ai_commands(registry)
    register_session_commands(registry)
    register_trading_commands(registry)


def reset_global_registry() -> None:
    """Reset the global registry (for testing)."""
    global _global_registry
    _global_registry = None


__all__ = [
    "Command",
    "CommandRegistry",
    "CommandNotFoundError",
    "CommandAlreadyExistsError",
    "AliasConflictError",
    "PermissionDeniedError",
    "get_command_registry",
    "reset_global_registry",
]
