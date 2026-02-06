"""
Decorators for creating command handlers.

Provides:
- @command: Create a CommandHandler from an async function
- @admin_only: Restrict handler to admin users
- @rate_limited: Apply rate limiting per user
- @require_args: Require minimum number of arguments
"""

import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.handlers.base import CommandHandler, MessageContext, Response

logger = logging.getLogger(__name__)


# Rate limit tracking: {handler_id: {user_id: [timestamps]}}
_rate_limit_state: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))


class DecoratedHandler(CommandHandler):
    """
    CommandHandler created from a decorated function.

    Wraps an async function with optional middleware (admin check, rate limit, etc.).
    """

    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        usage: Optional[str] = None,
    ):
        """
        Initialize the decorated handler.

        Args:
            func: The async handler function
            name: Command name
            description: Command description
            usage: Usage string (defaults to /name)
        """
        self._func = func
        self._name = name
        self._description = description
        self._usage = usage or f"/{name}"
        self._middleware: List[Callable] = []

    @property
    def command(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def usage(self) -> str:
        return self._usage

    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Execute the command, running through middleware first.

        Args:
            message: The message text
            context: Execution context

        Returns:
            Response from handler or middleware
        """
        # Run middleware in order (they can short-circuit)
        for middleware in self._middleware:
            result = await middleware(message, context, self)
            if result is not None:
                return result

        # Call the actual handler
        return await self._func(message, context)

    def can_handle(self, message: Any) -> bool:
        """
        Check if this handler can process the message.

        Matches if message starts with /command_name.

        Args:
            message: The message to check

        Returns:
            True if message matches this command
        """
        msg_str = str(message).lower().strip()
        cmd = f"/{self._name.lower()}"
        return msg_str == cmd or msg_str.startswith(f"{cmd} ") or msg_str.startswith(f"{cmd}@")

    def add_middleware(self, middleware: Callable) -> None:
        """
        Add middleware to the handler.

        Middleware runs before the handler and can return early.

        Args:
            middleware: Async function(message, context, handler) -> Optional[Response]
        """
        self._middleware.append(middleware)


def command(
    name: str,
    description: str,
    usage: Optional[str] = None,
) -> Callable:
    """
    Decorator to create a CommandHandler from an async function.

    Args:
        name: Command name (without /)
        description: Brief description
        usage: Usage string (defaults to /name)

    Returns:
        Decorator that wraps the function

    Example:
        @command(name="greet", description="Greet someone")
        async def greet(message: str, context: MessageContext) -> Response:
            return Response.ok("Hello!")
    """
    def decorator(func: Callable) -> DecoratedHandler:
        handler = DecoratedHandler(func, name, description, usage)
        return handler
    return decorator


def admin_only(handler_or_func: Any) -> Any:
    """
    Decorator to restrict a handler to admin users only.

    Can be applied to a DecoratedHandler or used with @command.

    Args:
        handler_or_func: DecoratedHandler or async function

    Returns:
        Handler with admin check middleware

    Example:
        @command(name="secret", description="Admin only")
        @admin_only
        async def secret(message, context):
            return Response.ok("Secret data")
    """
    async def admin_middleware(
        message: Any,
        context: MessageContext,
        handler: CommandHandler,
    ) -> Optional[Response]:
        if not context.is_admin:
            return Response.fail(
                "Permission denied. This command requires admin privileges.",
                error="admin_required"
            )
        return None

    if isinstance(handler_or_func, DecoratedHandler):
        handler_or_func.add_middleware(admin_middleware)
        return handler_or_func
    else:
        # If applied to a raw function, wrap it
        @wraps(handler_or_func)
        async def wrapped(message: Any, context: MessageContext) -> Response:
            if not context.is_admin:
                return Response.fail(
                    "Permission denied. This command requires admin privileges.",
                    error="admin_required"
                )
            return await handler_or_func(message, context)
        return wrapped


def rate_limited(calls: int, period: int) -> Callable:
    """
    Decorator to apply rate limiting to a handler.

    Limits the number of calls per user within a time period.

    Args:
        calls: Maximum number of calls allowed
        period: Time period in seconds

    Returns:
        Decorator function

    Example:
        @command(name="api", description="Call API")
        @rate_limited(calls=5, period=60)
        async def api_call(message, context):
            return Response.ok("API result")
    """
    def decorator(handler_or_func: Any) -> Any:
        # Generate unique ID for this handler
        handler_id = f"{id(handler_or_func)}"

        async def rate_middleware(
            message: Any,
            context: MessageContext,
            handler: CommandHandler,
        ) -> Optional[Response]:
            nonlocal handler_id
            user_id = context.user_id
            now = time.time()
            cutoff = now - period

            # Clean old entries
            user_calls = _rate_limit_state[handler_id][user_id]
            _rate_limit_state[handler_id][user_id] = [
                t for t in user_calls if t > cutoff
            ]

            # Check limit
            if len(_rate_limit_state[handler_id][user_id]) >= calls:
                return Response.fail(
                    f"Rate limit exceeded. Maximum {calls} calls per {period} seconds.",
                    error="rate_limited"
                )

            # Record this call
            _rate_limit_state[handler_id][user_id].append(now)
            return None

        if isinstance(handler_or_func, DecoratedHandler):
            handler_or_func.add_middleware(rate_middleware)
            return handler_or_func
        else:
            @wraps(handler_or_func)
            async def wrapped(message: Any, context: MessageContext) -> Response:
                result = await rate_middleware(message, context, None)
                if result is not None:
                    return result
                return await handler_or_func(message, context)
            return wrapped

    return decorator


def require_args(count: int) -> Callable:
    """
    Decorator to require a minimum number of arguments.

    Parses the message and checks for sufficient arguments after the command.

    Args:
        count: Minimum number of required arguments

    Returns:
        Decorator function

    Example:
        @command(name="add", description="Add two numbers")
        @require_args(count=2)
        async def add(message, context):
            args = message.split()[1:]
            return Response.ok(f"Sum: {int(args[0]) + int(args[1])}")
    """
    def decorator(handler_or_func: Any) -> Any:
        def parse_args(message: str) -> List[str]:
            """Parse arguments from a command message."""
            parts = str(message).split()
            # Skip command name (first part starting with /)
            args = [p for p in parts if not p.startswith('/')]
            # If first arg wasn't a command, use all parts except first
            if len(args) == len(parts):
                args = parts[1:] if len(parts) > 1 else []
            return args

        async def args_middleware(
            message: Any,
            context: MessageContext,
            handler: CommandHandler,
        ) -> Optional[Response]:
            args = parse_args(str(message))
            if len(args) < count:
                usage = handler.usage if handler else "command"
                return Response.fail(
                    f"Not enough arguments. Expected {count}, got {len(args)}.\n"
                    f"Usage: {usage}",
                    error="insufficient_arguments"
                )
            return None

        if isinstance(handler_or_func, DecoratedHandler):
            handler_or_func.add_middleware(args_middleware)
            return handler_or_func
        else:
            @wraps(handler_or_func)
            async def wrapped(message: Any, context: MessageContext) -> Response:
                args = parse_args(str(message))
                if len(args) < count:
                    return Response.fail(
                        f"Not enough arguments. Expected {count}, got {len(args)}.",
                        error="insufficient_arguments"
                    )
                return await handler_or_func(message, context)
            return wrapped

    return decorator
