"""
Common command handlers used across platforms.

Provides:
- HelpHandler: /help command
- StartHandler: /start command
- StatusHandler: /status command
- PingHandler: /ping command
- register_common_handlers: Register all common handlers
"""

import logging
import platform
import sys
from datetime import datetime
from typing import Any

from core.handlers.base import CommandHandler, MessageContext, Response

logger = logging.getLogger(__name__)


class HelpHandler(CommandHandler):
    """
    Handler for /help command.

    Shows available commands and their descriptions.
    """

    @property
    def command(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Show available commands and their usage"

    @property
    def usage(self) -> str:
        return "/help [command]"

    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Generate and return help text.

        Args:
            message: The message (may include specific command to get help for)
            context: Execution context

        Returns:
            Response with help text
        """
        from core.handlers.registry import get_handler_registry

        registry = get_handler_registry()
        help_text = registry.generate_help()

        return Response.ok(help_text)

    def can_handle(self, message: Any) -> bool:
        """Check if message is a help command."""
        msg = str(message).lower().strip()
        return msg == "/help" or msg.startswith("/help ")


class StartHandler(CommandHandler):
    """
    Handler for /start command.

    Shows welcome message and basic instructions.
    """

    @property
    def command(self) -> str:
        return "start"

    @property
    def description(self) -> str:
        return "Start the bot and show welcome message"

    @property
    def usage(self) -> str:
        return "/start"

    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Return welcome message.

        Args:
            message: The message
            context: Execution context

        Returns:
            Response with welcome text
        """
        welcome = (
            "Welcome! I'm ready to assist you.\n\n"
            "Use /help to see available commands."
        )

        if context.is_admin:
            welcome += "\n\nAdmin access enabled."

        return Response.ok(welcome, data={"is_admin": context.is_admin})

    def can_handle(self, message: Any) -> bool:
        """Check if message is a start command."""
        msg = str(message).lower().strip()
        return msg == "/start" or msg.startswith("/start ")


class StatusHandler(CommandHandler):
    """
    Handler for /status command.

    Shows current system status and health information.
    """

    @property
    def command(self) -> str:
        return "status"

    @property
    def description(self) -> str:
        return "Show system status and health"

    @property
    def usage(self) -> str:
        return "/status"

    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Return system status.

        Args:
            message: The message
            context: Execution context

        Returns:
            Response with status information
        """
        from core.handlers.registry import get_handler_registry

        registry = get_handler_registry()
        handler_count = len(registry.list_handlers())

        status_data = {
            "status": "online",
            "platform": context.platform,
            "python_version": sys.version.split()[0],
            "os": platform.system(),
            "handlers_registered": handler_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

        status_text = (
            f"Status: Online\n"
            f"Platform: {context.platform}\n"
            f"Python: {status_data['python_version']}\n"
            f"OS: {status_data['os']}\n"
            f"Handlers: {handler_count}\n"
            f"Time: {status_data['timestamp']}"
        )

        return Response.ok(status_text, data=status_data)

    def can_handle(self, message: Any) -> bool:
        """Check if message is a status command."""
        msg = str(message).lower().strip()
        return msg == "/status" or msg.startswith("/status ")


class PingHandler(CommandHandler):
    """
    Handler for /ping command.

    Simple ping-pong to verify bot responsiveness.
    """

    @property
    def command(self) -> str:
        return "ping"

    @property
    def description(self) -> str:
        return "Check if the bot is responsive"

    @property
    def usage(self) -> str:
        return "/ping"

    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Return pong response.

        Args:
            message: The message
            context: Execution context

        Returns:
            Response with pong
        """
        return Response.ok("Pong!", data={"latency_ms": 0})

    def can_handle(self, message: Any) -> bool:
        """Check if message is a ping command."""
        msg = str(message).lower().strip()
        return msg == "/ping" or msg.startswith("/ping ")


def register_common_handlers(registry: "HandlerRegistry") -> None:
    """
    Register all common handlers with the given registry.

    Args:
        registry: The HandlerRegistry to register handlers with
    """
    from core.handlers.registry import HandlerRegistry

    handlers = [
        HelpHandler(),
        StartHandler(),
        StatusHandler(),
        PingHandler(),
    ]

    for handler in handlers:
        registry.register(handler)

    logger.info(f"Registered {len(handlers)} common handlers")
