"""
Middleware Context - Request/Response container for middleware chain.

The Context object flows through each middleware, allowing them to:
- Read/modify request data
- Set response data
- Store middleware-specific data
- Abort processing with errors
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class AbortError(Exception):
    """
    Exception raised to abort middleware processing.

    Usage:
        ctx.abort(403, "Forbidden")
        # or
        raise AbortError(403, "Forbidden", {"retry_after": 60})
    """

    def __init__(self, status: int, message: str, data: Dict[str, Any] = None):
        """
        Initialize abort error.

        Args:
            status: HTTP status code
            message: Error message
            data: Additional error data
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data or {}


@dataclass
class Response:
    """
    Middleware response object.

    Represents the final response from middleware chain processing.
    """

    status: int = 200
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    message: str = ""

    @classmethod
    def ok(cls, body: Dict[str, Any] = None) -> "Response":
        """Create successful response."""
        return cls(status=200, body=body or {})

    @classmethod
    def error(cls, status: int, message: str, data: Dict[str, Any] = None) -> "Response":
        """Create error response."""
        return cls(
            status=status,
            message=message,
            body={"error": message, **(data or {})}
        )

    @classmethod
    def from_abort(cls, abort: AbortError) -> "Response":
        """Create response from AbortError."""
        return cls.error(abort.status, abort.message, abort.data)


@dataclass
class Context:
    """
    Middleware context - flows through the middleware chain.

    Attributes:
        request: The incoming request data
        response: The outgoing response (set by middlewares or handler)
        user: User information (set by auth middleware)
        bot: Bot identifier (telegram, discord, etc.)
        data: Middleware-specific storage

    Usage:
        ctx = Context(
            request={"method": "POST", "path": "/api/trade"},
            user={"id": "user123"},
            bot="telegram"
        )

        # Middleware can store data
        ctx.data["request_id"] = "abc123"
        ctx.data["authenticated"] = True

        # Middleware can abort processing
        if not authorized:
            ctx.abort(403, "Forbidden")
    """

    request: Dict[str, Any] = field(default_factory=dict)
    response: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    bot: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def abort(self, status: int, message: str, data: Dict[str, Any] = None) -> None:
        """
        Abort middleware processing with an error.

        Args:
            status: HTTP status code
            message: Error message
            data: Additional error data

        Raises:
            AbortError: Always raised to stop processing
        """
        raise AbortError(status, message, data)

    def get_header(self, name: str, default: str = None) -> Optional[str]:
        """Get a header from the request."""
        headers = self.request.get("headers", {})
        return headers.get(name, default)

    def get_path(self) -> str:
        """Get the request path."""
        return self.request.get("path", "/")

    def get_method(self) -> str:
        """Get the request method."""
        return self.request.get("method", "GET")

    def is_authenticated(self) -> bool:
        """Check if the user is authenticated."""
        if self.user is None:
            return False
        return self.user.get("authenticated", True) if self.user else False

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if not self.user:
            return False
        permissions = self.user.get("permissions", [])
        return permission in permissions
