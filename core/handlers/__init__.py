"""
Command Handler System.

Provides a standardized, platform-agnostic command handling framework.

Components:
- base: CommandHandler abstract class, Response, MessageContext
- registry: HandlerRegistry singleton for managing handlers
- decorators: @command, @admin_only, @rate_limited, @require_args
- common: Standard handlers (help, start, status, ping)

Usage:
    from core.handlers import CommandHandler, Response, MessageContext
    from core.handlers import get_handler_registry
    from core.handlers.decorators import command, admin_only

    @command(name="greet", description="Greet a user")
    async def greet(message: str, context: MessageContext) -> Response:
        return Response.ok("Hello!")
"""

from core.handlers.base import CommandHandler, Response, MessageContext
from core.handlers.registry import HandlerRegistry, get_handler_registry
from core.handlers.decorators import command, admin_only, rate_limited, require_args
from core.handlers.common import (
    HelpHandler,
    StartHandler,
    StatusHandler,
    PingHandler,
    register_common_handlers,
)

__all__ = [
    # Base classes
    "CommandHandler",
    "Response",
    "MessageContext",
    # Registry
    "HandlerRegistry",
    "get_handler_registry",
    # Decorators
    "command",
    "admin_only",
    "rate_limited",
    "require_args",
    # Common handlers
    "HelpHandler",
    "StartHandler",
    "StatusHandler",
    "PingHandler",
    "register_common_handlers",
]
