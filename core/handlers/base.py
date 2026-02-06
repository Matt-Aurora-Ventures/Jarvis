"""
Base classes for the command handler system.

Provides:
- CommandHandler: Abstract base class for all command handlers
- Response: Standard response dataclass
- MessageContext: Context information for command execution
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Response:
    """
    Standard response from a command handler.

    Attributes:
        success: Whether the command executed successfully
        message: Human-readable response message
        data: Optional structured data (for programmatic use)
        error: Optional error details (when success=False)
    """

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "Response":
        """
        Factory method for successful responses.

        Args:
            message: Success message
            data: Optional data payload

        Returns:
            A success Response
        """
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, error: Optional[str] = None) -> "Response":
        """
        Factory method for error responses.

        Args:
            message: Error message
            error: Optional detailed error

        Returns:
            A failure Response
        """
        return cls(success=False, message=message, error=error)


@dataclass
class MessageContext:
    """
    Context information for command execution.

    Platform-agnostic context that can be adapted from Telegram, Discord, etc.

    Attributes:
        user_id: Unique user identifier
        chat_id: Unique chat/channel identifier
        platform: Platform name (telegram, discord, slack, etc.)
        is_admin: Whether user has admin privileges
        username: Optional username
        raw_message: Original message text
        metadata: Platform-specific extra data
    """

    user_id: int
    chat_id: int
    platform: str
    is_admin: bool = False
    username: Optional[str] = None
    raw_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CommandHandler(ABC):
    """
    Abstract base class for command handlers.

    All command handlers must implement:
    - command: The command name (without leading /)
    - description: Brief description of the command
    - usage: Usage string showing how to use the command
    - handle(): Async method that executes the command
    - can_handle(): Method to check if handler can process a message

    Example:
        class GreetHandler(CommandHandler):
            @property
            def command(self) -> str:
                return "greet"

            @property
            def description(self) -> str:
                return "Greet a user"

            @property
            def usage(self) -> str:
                return "/greet [name]"

            async def handle(self, message: Any, context: MessageContext) -> Response:
                return Response.ok("Hello!")

            def can_handle(self, message: Any) -> bool:
                return str(message).startswith("/greet")
    """

    @property
    @abstractmethod
    def command(self) -> str:
        """
        The command name (without leading /).

        Returns:
            Command name string
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Brief description of what the command does.

        Returns:
            Description string
        """
        pass

    @property
    @abstractmethod
    def usage(self) -> str:
        """
        Usage string showing how to use the command.

        Returns:
            Usage string (e.g., "/greet [name]")
        """
        pass

    @abstractmethod
    async def handle(self, message: Any, context: MessageContext) -> Response:
        """
        Execute the command.

        Args:
            message: The message/command text
            context: Execution context with user info

        Returns:
            Response object with result
        """
        pass

    @abstractmethod
    def can_handle(self, message: Any) -> bool:
        """
        Check if this handler can process the given message.

        Args:
            message: The message to check

        Returns:
            True if handler can process this message
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} command='{self.command}'>"
