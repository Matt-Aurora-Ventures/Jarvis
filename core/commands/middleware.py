"""
Command Middleware - Chain of responsibility pattern for command processing.

This module provides middleware infrastructure:
- Middleware base class
- MiddlewareChain for composing middleware
- RateLimitMiddleware for rate limiting
- AuthMiddleware for authentication
- LoggingMiddleware for request logging
"""

import logging
import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class MiddlewareError(Exception):
    """Base exception for middleware errors."""
    pass


class RateLimitExceeded(MiddlewareError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationRequired(MiddlewareError):
    """Raised when authentication is required but not provided."""
    pass


class InsufficientPermissions(MiddlewareError):
    """Raised when user lacks required permissions."""
    pass


# ============================================================================
# Base Middleware
# ============================================================================

class Middleware(ABC):
    """
    Base middleware class.

    Middleware processes requests in a chain, with each middleware able to:
    - Modify the context before passing to the next handler
    - Short-circuit the chain by not calling next_handler
    - Process the result after the handler completes
    """

    @abstractmethod
    async def process(
        self,
        ctx: Dict[str, Any],
        next_handler: Callable
    ) -> Any:
        """
        Process the request.

        Args:
            ctx: Request context
            next_handler: The next handler in the chain

        Returns:
            Result from the handler
        """
        pass


# ============================================================================
# Middleware Chain
# ============================================================================

class MiddlewareChain:
    """
    Chain of middleware that processes requests in order.

    Middleware executes in order, with the first middleware able to
    wrap all subsequent processing.
    """

    def __init__(self):
        self.middlewares: List[Middleware] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """
        Add middleware to the chain.

        Args:
            middleware: The middleware to add

        Returns:
            Self for chaining
        """
        self.middlewares.append(middleware)
        return self

    async def execute(
        self,
        ctx: Dict[str, Any],
        handler: Callable
    ) -> Any:
        """
        Execute the middleware chain.

        Args:
            ctx: Request context
            handler: The final handler

        Returns:
            Result from the handler
        """
        if not self.middlewares:
            return await self._call_handler(handler, ctx)

        # Build the chain from the end
        async def build_chain(index: int):
            if index >= len(self.middlewares):
                return await self._call_handler(handler, ctx)

            middleware = self.middlewares[index]

            async def next_handler(ctx):
                return await build_chain(index + 1)

            return await middleware.process(ctx, next_handler)

        return await build_chain(0)

    async def _call_handler(self, handler: Callable, ctx: Dict[str, Any]) -> Any:
        """Call the handler, handling both sync and async."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(ctx)
        return handler(ctx)


# ============================================================================
# Rate Limit Middleware
# ============================================================================

@dataclass
class RateLimitEntry:
    """Track rate limit for a single key."""
    requests: List[float] = field(default_factory=list)


class RateLimitMiddleware(Middleware):
    """
    Middleware that enforces rate limits.

    Rate limits are tracked per key (default: user_id).
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        key_func: Optional[Callable[[Dict], str]] = None
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            key_func: Function to extract rate limit key from context
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or (lambda ctx: str(ctx.get("user_id", "anonymous")))
        self._limits: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

    async def process(
        self,
        ctx: Dict[str, Any],
        next_handler: Callable
    ) -> Any:
        """Process with rate limiting."""
        key = self.key_func(ctx)
        now = time.time()

        entry = self._limits[key]

        # Remove old requests outside the window
        cutoff = now - self.window_seconds
        entry.requests = [t for t in entry.requests if t > cutoff]

        # Check if limit exceeded
        if len(entry.requests) >= self.max_requests:
            # Calculate retry-after
            oldest = min(entry.requests) if entry.requests else now
            retry_after = self.window_seconds - (now - oldest)

            raise RateLimitExceeded(
                f"Rate limit exceeded. Try again in {retry_after:.1f}s",
                retry_after=max(0, retry_after)
            )

        # Record this request
        entry.requests.append(now)

        return await next_handler(ctx)


# ============================================================================
# Auth Middleware
# ============================================================================

class AuthMiddleware(Middleware):
    """
    Middleware that enforces authentication.

    Can check for basic authentication and required roles.
    """

    def __init__(
        self,
        required_role: Optional[str] = None,
        auth_checker: Optional[Callable] = None,
        user_loader: Optional[Callable] = None
    ):
        """
        Initialize auth middleware.

        Args:
            required_role: Required role for access
            auth_checker: Custom function to check authentication
            user_loader: Function to load user data into context
        """
        self.required_role = required_role
        self.auth_checker = auth_checker
        self.user_loader = user_loader

    async def process(
        self,
        ctx: Dict[str, Any],
        next_handler: Callable
    ) -> Any:
        """Process with authentication check."""
        # Custom auth checker
        if self.auth_checker:
            if asyncio.iscoroutinefunction(self.auth_checker):
                is_authenticated = await self.auth_checker(ctx)
            else:
                is_authenticated = self.auth_checker(ctx)

            if not is_authenticated:
                raise AuthenticationRequired("Authentication required")
        else:
            # Default: check is_authenticated flag
            if not ctx.get("is_authenticated", False):
                raise AuthenticationRequired("Authentication required")

        # Check role if required
        if self.required_role:
            user_role = ctx.get("role")
            if user_role != self.required_role:
                raise InsufficientPermissions(
                    f"Required role: {self.required_role}"
                )

        # Load user data if loader provided
        if self.user_loader:
            if asyncio.iscoroutinefunction(self.user_loader):
                user_data = await self.user_loader(ctx)
            else:
                user_data = self.user_loader(ctx)

            if user_data:
                ctx["user"] = user_data

        return await next_handler(ctx)


# ============================================================================
# Logging Middleware
# ============================================================================

class LoggingMiddleware(Middleware):
    """
    Middleware that logs requests and responses.

    Tracks timing and can filter sensitive fields.
    """

    def __init__(
        self,
        logger: Optional[Callable] = None,
        sensitive_fields: Optional[List[str]] = None,
        formatter: Optional[Callable] = None
    ):
        """
        Initialize logging middleware.

        Args:
            logger: Custom logging function (level, message, **kwargs)
            sensitive_fields: Fields to redact from logs
            formatter: Custom log message formatter
        """
        self._logger = logger or self._default_logger
        self.sensitive_fields = set(sensitive_fields or [])
        self.formatter = formatter

    def _default_logger(self, level: str, message: str, **kwargs):
        """Default logger using Python logging."""
        log_func = getattr(logging.getLogger(__name__), level, logging.info)
        log_func(message, extra=kwargs)

    def _redact_sensitive(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Create a copy of context with sensitive fields redacted."""
        result = {}
        for key, value in ctx.items():
            if key in self.sensitive_fields:
                result[key] = "[REDACTED]"
            else:
                result[key] = value
        return result

    async def process(
        self,
        ctx: Dict[str, Any],
        next_handler: Callable
    ) -> Any:
        """Process with logging."""
        start_time = time.time()
        safe_ctx = self._redact_sensitive(ctx)

        # Log request
        command = ctx.get("command", "unknown")
        user_id = safe_ctx.get("user_id", "unknown")

        self._logger(
            "info",
            f"Command request: {command} from user {user_id}",
            command=command,
            user_id=user_id,
            context=safe_ctx
        )

        try:
            result = await next_handler(ctx)

            duration = time.time() - start_time

            # Log success
            if self.formatter:
                message = self.formatter(ctx, result, duration)
            else:
                message = f"Command completed: {command} in {duration:.3f}s"

            self._logger(
                "info",
                message,
                command=command,
                duration=duration,
                success=True
            )

            return result

        except Exception as e:
            duration = time.time() - start_time

            # Log error
            self._logger(
                "error",
                f"Command failed: {command} - {str(e)}",
                command=command,
                duration=duration,
                error=str(e),
                error_type=type(e).__name__
            )

            raise


# ============================================================================
# Factory Functions
# ============================================================================

def rate_limit_middleware(
    max_requests: int,
    window_seconds: float,
    key_func: Optional[Callable] = None
) -> RateLimitMiddleware:
    """
    Create a rate limit middleware.

    Args:
        max_requests: Maximum requests per window
        window_seconds: Time window in seconds
        key_func: Function to extract rate limit key

    Returns:
        Configured RateLimitMiddleware
    """
    return RateLimitMiddleware(
        max_requests=max_requests,
        window_seconds=window_seconds,
        key_func=key_func
    )


def auth_middleware(
    required_role: Optional[str] = None,
    auth_checker: Optional[Callable] = None,
    user_loader: Optional[Callable] = None
) -> AuthMiddleware:
    """
    Create an auth middleware.

    Args:
        required_role: Required role for access
        auth_checker: Custom authentication checker
        user_loader: Function to load user data

    Returns:
        Configured AuthMiddleware
    """
    return AuthMiddleware(
        required_role=required_role,
        auth_checker=auth_checker,
        user_loader=user_loader
    )


def logging_middleware(
    logger: Optional[Callable] = None,
    sensitive_fields: Optional[List[str]] = None,
    formatter: Optional[Callable] = None
) -> LoggingMiddleware:
    """
    Create a logging middleware.

    Args:
        logger: Custom logging function
        sensitive_fields: Fields to redact
        formatter: Custom message formatter

    Returns:
        Configured LoggingMiddleware
    """
    return LoggingMiddleware(
        logger=logger,
        sensitive_fields=sensitive_fields,
        formatter=formatter
    )
