"""
Built-in Middleware - Common middleware implementations.

Provides ready-to-use middleware for:
- LoggingMiddleware: Request/response logging
- AuthMiddleware: Authentication and authorization
- RateLimitMiddleware: Rate limiting
- ErrorMiddleware: Error handling and formatting
- MetricsMiddleware: Timing and metrics tracking
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from core.middleware.base import Middleware, NextHandler
from core.middleware.context import Context, Response, AbortError


logger = logging.getLogger(__name__)


class LoggingMiddleware(Middleware):
    """
    Logs incoming requests and outgoing responses.

    Adds request_id to context for tracking.

    Usage:
        pipeline.add(LoggingMiddleware())

        # Customize logging
        pipeline.add(LoggingMiddleware(
            log_headers=True,
            exclude_paths={"/health", "/metrics"}
        ))
    """

    name = "logging"
    priority = 100  # Run first

    def __init__(
        self,
        log_headers: bool = False,
        log_body: bool = False,
        exclude_paths: Set[str] = None,
    ):
        """
        Initialize logging middleware.

        Args:
            log_headers: Whether to log request headers
            log_body: Whether to log request body
            exclude_paths: Paths to exclude from logging
        """
        self.log_headers = log_headers
        self.log_body = log_body
        self.exclude_paths = exclude_paths or {"/health", "/metrics"}

    async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
        """Log request and response."""
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        ctx.data["request_id"] = request_id

        path = ctx.get_path()
        method = ctx.get_method()

        # Skip logging for excluded paths
        if path not in self.exclude_paths:
            log_msg = f"REQUEST {request_id} | {method} {path}"
            if self.log_headers:
                log_msg += f" | headers={ctx.request.get('headers', {})}"
            logger.info(log_msg)

        start_time = time.time()

        try:
            response = await next_handler(ctx)
            duration_ms = (time.time() - start_time) * 1000

            if path not in self.exclude_paths:
                logger.info(
                    f"RESPONSE {request_id} | {response.status} | {duration_ms:.1f}ms"
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"ERROR {request_id} | {type(e).__name__}: {e} | {duration_ms:.1f}ms"
            )
            raise


class AuthMiddleware(Middleware):
    """
    Authentication and authorization middleware.

    Checks that requests are authenticated and optionally
    verifies required permissions.

    Usage:
        # Basic auth check
        pipeline.add(AuthMiddleware())

        # With permission requirements
        pipeline.add(AuthMiddleware(
            required_permissions=["trade:execute"]
        ))

        # Skip auth for certain paths
        pipeline.add(AuthMiddleware(
            skip_paths={"/auth/login", "/health"}
        ))
    """

    name = "auth"
    priority = 90  # Run early, after logging

    def __init__(
        self,
        required_permissions: List[str] = None,
        skip_paths: Set[str] = None,
    ):
        """
        Initialize auth middleware.

        Args:
            required_permissions: Permissions required for all requests
            skip_paths: Paths that don't require authentication
        """
        self.required_permissions = required_permissions or []
        self.skip_paths = skip_paths or {"/health", "/docs", "/auth/login"}

    async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
        """Verify authentication and authorization."""
        path = ctx.get_path()

        # Skip auth for allowed paths
        if path in self.skip_paths:
            return await next_handler(ctx)

        # Check authentication
        if not ctx.user:
            ctx.abort(401, "Authentication required")

        # Check if user is explicitly marked as not authenticated
        if ctx.user.get("authenticated") is False:
            ctx.abort(401, "Authentication required")

        # Check required permissions
        for permission in self.required_permissions:
            if not ctx.has_permission(permission):
                ctx.abort(403, f"Permission denied: {permission} required")

        return await next_handler(ctx)


@dataclass
class RateLimitState:
    """State for rate limiting a single user."""

    timestamps: List[float]
    last_cleanup: float = 0


class RateLimitMiddleware(Middleware):
    """
    Rate limiting middleware.

    Limits requests per user per time window.

    Usage:
        pipeline.add(RateLimitMiddleware(
            requests_per_minute=60,
            burst_size=10
        ))
    """

    name = "rate_limit"
    priority = 80  # Run after auth

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        key_func: callable = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            requests_per_minute: Max requests per minute
            burst_size: Max burst in 5 seconds
            key_func: Function to extract user key from context
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.key_func = key_func or self._default_key
        self._state: Dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(timestamps=[])
        )
        self._lock = asyncio.Lock()

    @staticmethod
    def _default_key(ctx: Context) -> str:
        """Extract user identifier from context."""
        if ctx.user:
            return str(ctx.user.get("id", "anonymous"))
        return "anonymous"

    async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
        """Check rate limits."""
        async with self._lock:
            key = self.key_func(ctx)
            now = time.time()
            state = self._state[key]

            # Cleanup old timestamps
            cutoff = now - 60  # 1 minute window
            state.timestamps = [t for t in state.timestamps if t > cutoff]

            # Check limits
            minute_count = len(state.timestamps)
            burst_count = len([t for t in state.timestamps if t > now - 5])

            # Store rate limit info in context
            ctx.data["rate_limit"] = {
                "limit": self.requests_per_minute,
                "remaining": max(0, self.requests_per_minute - minute_count),
                "reset": int(now + 60),
            }

            if minute_count >= self.requests_per_minute:
                ctx.abort(
                    429,
                    "Rate limit exceeded",
                    {"retry_after": 60, "limit": self.requests_per_minute},
                )

            if burst_count >= self.burst_size:
                ctx.abort(
                    429,
                    "Burst limit exceeded",
                    {"retry_after": 5, "limit": self.burst_size},
                )

            # Record this request
            state.timestamps.append(now)

        return await next_handler(ctx)


class ErrorMiddleware(Middleware):
    """
    Error handling middleware.

    Catches exceptions and formats them as responses.
    Hides internal error details in production.

    Usage:
        # Development mode (show details)
        pipeline.add(ErrorMiddleware(debug=True))

        # Production mode (hide details)
        pipeline.add(ErrorMiddleware(debug=False))
    """

    name = "error"
    priority = 95  # Run very early to catch all errors

    def __init__(self, debug: bool = False):
        """
        Initialize error middleware.

        Args:
            debug: Whether to include error details in response
        """
        self.debug = debug

    async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
        """Catch and format errors."""
        try:
            return await next_handler(ctx)

        except AbortError as e:
            # Intentional abort - pass through
            return Response.from_abort(e)

        except Exception as e:
            logger.exception(f"Unhandled error: {e}")

            if self.debug:
                return Response.error(
                    500,
                    f"Internal server error: {type(e).__name__}: {e}",
                    {"traceback": str(e)},
                )
            else:
                return Response.error(500, "Internal server error")


class MetricsMiddleware(Middleware):
    """
    Metrics tracking middleware.

    Records timing, status codes, and other metrics.

    Usage:
        metrics = MetricsMiddleware()
        pipeline.add(metrics)

        # Get stats
        stats = metrics.get_stats()
    """

    name = "metrics"
    priority = 99  # Run at the very start

    def __init__(self):
        """Initialize metrics middleware."""
        self._total_requests = 0
        self._total_duration_ms = 0.0
        self._status_counts: Dict[int, int] = defaultdict(int)
        self._path_timings: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
        """Track metrics for request."""
        start_time = time.time()
        path = ctx.get_path()

        try:
            response = await next_handler(ctx)
            duration_ms = (time.time() - start_time) * 1000

            # Store in context
            ctx.data["duration_ms"] = duration_ms
            ctx.data["response_status"] = response.status

            # Update metrics
            async with self._lock:
                self._total_requests += 1
                self._total_duration_ms += duration_ms
                self._status_counts[response.status] += 1
                self._path_timings[path].append(duration_ms)

                # Keep only last 1000 timings per path
                if len(self._path_timings[path]) > 1000:
                    self._path_timings[path] = self._path_timings[path][-1000:]

            return response

        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            ctx.data["duration_ms"] = duration_ms
            raise

    def get_stats(self) -> Dict:
        """
        Get collected metrics.

        Returns:
            Dict with request stats
        """
        avg_duration = (
            self._total_duration_ms / self._total_requests
            if self._total_requests > 0
            else 0
        )

        return {
            "total_requests": self._total_requests,
            "avg_duration_ms": round(avg_duration, 2),
            "status_counts": dict(self._status_counts),
            "paths": {
                path: {
                    "count": len(timings),
                    "avg_ms": round(sum(timings) / len(timings), 2) if timings else 0,
                }
                for path, timings in self._path_timings.items()
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._total_requests = 0
        self._total_duration_ms = 0.0
        self._status_counts.clear()
        self._path_timings.clear()


# Convenience function to create a standard pipeline
def create_standard_pipeline(
    debug: bool = False,
    rate_limit: int = 60,
    required_permissions: List[str] = None,
) -> "Pipeline":
    """
    Create a pipeline with standard middleware.

    Args:
        debug: Enable debug mode for error middleware
        rate_limit: Requests per minute
        required_permissions: Permissions to require

    Returns:
        Configured Pipeline
    """
    from core.middleware.pipeline import Pipeline

    pipeline = Pipeline()
    pipeline.add(MetricsMiddleware())
    pipeline.add(ErrorMiddleware(debug=debug))
    pipeline.add(LoggingMiddleware())
    pipeline.add(AuthMiddleware(required_permissions=required_permissions))
    pipeline.add(RateLimitMiddleware(requests_per_minute=rate_limit))

    return pipeline
