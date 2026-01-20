"""
JARVIS Request/Response Logging Middleware

Comprehensive HTTP logging with:
- Request details (method, path, headers, body)
- Response details (status, headers, timing)
- Structured JSON output
- Sensitive data masking
- Performance metrics

Usage:
    from api.middleware.request_logging import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context vars for request tracking
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
request_start_ctx: ContextVar[float] = ContextVar("request_start", default=0.0)

# Headers to mask (case-insensitive)
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "x-auth-token",
    "cookie",
    "set-cookie",
    "x-csrf-token",
}

# Body fields to mask
SENSITIVE_FIELDS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credit_card",
    "ssn",
}

# Paths to skip logging
SKIP_PATHS = {
    "/health",
    "/health/",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/favicon.ico",
}


def mask_value(value: str, show_chars: int = 4) -> str:
    """Mask a sensitive value."""
    if len(value) <= show_chars * 2:
        return "****"
    return f"{value[:show_chars]}...{value[-show_chars:]}"


def mask_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Mask sensitive headers."""
    masked = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            masked[key] = mask_value(value)
        else:
            masked[key] = value
    return masked


def mask_body(data: Any) -> Any:
    """Recursively mask sensitive fields in body."""
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS:
                masked[key] = "****"
            else:
                masked[key] = mask_body(value)
        return masked
    elif isinstance(data, list):
        return [mask_body(item) for item in data]
    return data


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive request/response logging middleware.

    Logs:
    - Request method, path, query params
    - Request headers (masked)
    - Request body (masked, if applicable)
    - Response status code
    - Response time
    - Response size
    """

    def __init__(
        self,
        app,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 10000,
        skip_paths: Set[str] = None,
        slow_request_threshold: float = 1.0,
    ):
        """
        Initialize middleware.

        Args:
            app: ASGI application
            log_request_body: Log request body content
            log_response_body: Log response body content
            max_body_size: Max body size to log (bytes)
            skip_paths: Paths to skip logging
            slow_request_threshold: Seconds to consider request slow
        """
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.skip_paths = skip_paths or SKIP_PATHS
        self.slow_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        request_id_ctx.set(request_id)

        # Start timing
        start_time = time.time()
        request_start_ctx.set(start_time)

        # Build request log
        request_log = await self._build_request_log(request, request_id)

        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={"request": request_log}
        )

        # Process request
        response = None
        error = None

        try:
            response = await call_next(request)
        except Exception as e:
            error = e
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time
            duration_ms = duration * 1000

            # Build response log
            response_log = self._build_response_log(
                request_id=request_id,
                response=response,
                duration_ms=duration_ms,
                error=error,
            )

            # Determine log level
            log_level = logging.INFO
            if error:
                log_level = logging.ERROR
            elif response and response.status_code >= 500:
                log_level = logging.ERROR
            elif response and response.status_code >= 400:
                log_level = logging.WARNING
            elif duration > self.slow_threshold:
                log_level = logging.WARNING

            # Log response
            status = response.status_code if response else "ERROR"
            logger.log(
                log_level,
                f"Response: {request.method} {request.url.path} {status} ({duration_ms:.0f}ms)",
                extra={"response": response_log}
            )

        # Add headers to response
        if response:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"

        return response

    async def _build_request_log(
        self,
        request: Request,
        request_id: str,
    ) -> Dict[str, Any]:
        """Build structured request log."""
        log = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
        }

        # Add masked headers
        log["headers"] = mask_headers(dict(request.headers))

        # Add body if enabled
        if self.log_request_body and request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if len(body) <= self.max_body_size:
                    try:
                        body_json = json.loads(body)
                        log["body"] = mask_body(body_json)
                    except json.JSONDecodeError:
                        log["body"] = f"<binary: {len(body)} bytes>"
                else:
                    log["body"] = f"<truncated: {len(body)} bytes>"
            except Exception:
                log["body"] = "<unavailable>"

        return log

    def _build_response_log(
        self,
        request_id: str,
        response: Optional[Response],
        duration_ms: float,
        error: Optional[Exception],
    ) -> Dict[str, Any]:
        """Build structured response log."""
        log = {
            "request_id": request_id,
            "duration_ms": round(duration_ms, 2),
        }

        if error:
            log["error"] = str(error)
            log["error_type"] = type(error).__name__
            log["status_code"] = 500

            # Add stack trace for 500 errors (truncated)
            import traceback
            stack = traceback.format_exc()
            log["stack_trace"] = stack[:1000] if len(stack) > 1000 else stack
        elif response:
            log["status_code"] = response.status_code
            log["headers"] = mask_headers(dict(response.headers))

            # Content length
            content_length = response.headers.get("content-length")
            if content_length:
                log["content_length"] = int(content_length)

        # Mark slow requests
        if duration_ms > self.slow_threshold * 1000:
            log["slow"] = True

        return log

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        # Check forwarded headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"


def get_request_id() -> str:
    """Get current request ID."""
    return request_id_ctx.get()


def get_request_duration() -> float:
    """Get current request duration in seconds."""
    start = request_start_ctx.get()
    if start:
        return time.time() - start
    return 0.0
