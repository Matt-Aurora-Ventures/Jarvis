"""
API Middleware - Request logging, rate limiting, CORS, and security.
"""

import time
import logging
import hashlib
import json
from typing import Optional, Dict, Callable, Set
from functools import wraps
from collections import defaultdict
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)


# === REQUEST LOGGING ===

class RequestLogger:
    """
    Middleware for logging all API requests.
    """

    def __init__(self, log_headers: bool = False, log_body: bool = False,
                 exclude_paths: Set[str] = None):
        self.log_headers = log_headers
        self.log_body = log_body
        self.exclude_paths = exclude_paths or {"/health", "/metrics", "/favicon.ico"}

    def _should_log(self, path: str) -> bool:
        """Check if request should be logged."""
        return path not in self.exclude_paths

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())[:8]

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        if not self._should_log(request.path):
            return await handler(request)

        request_id = self._generate_request_id()
        start_time = time.time()

        # Log request
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "query": dict(request.query),
            "remote": request.remote,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self.log_headers:
            log_data["headers"] = dict(request.headers)

        logger.info(f"REQUEST {request_id} | {request.method} {request.path}")

        try:
            response = await handler(request)
            duration = time.time() - start_time

            logger.info(
                f"RESPONSE {request_id} | {response.status} | {duration:.3f}s"
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"ERROR {request_id} | {type(e).__name__}: {e} | {duration:.3f}s"
            )
            raise


# FastAPI version
def fastapi_request_logger():
    """FastAPI middleware for request logging."""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware

    class LoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request_id = hashlib.md5(
                f"{time.time()}{request.client.host}".encode()
            ).hexdigest()[:8]

            start_time = time.time()

            logger.info(f"REQUEST {request_id} | {request.method} {request.url.path}")

            try:
                response = await call_next(request)
                duration = time.time() - start_time

                logger.info(
                    f"RESPONSE {request_id} | {response.status_code} | {duration:.3f}s"
                )

                response.headers["X-Request-ID"] = request_id
                return response

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"ERROR {request_id} | {type(e).__name__}: {e} | {duration:.3f}s"
                )
                raise

    return LoggingMiddleware


# === RATE LIMITING ===

class APIRateLimiter:
    """
    Token bucket rate limiter for API endpoints.
    """

    def __init__(self, default_limit: int = 100, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

        # Per-endpoint limits
        self.endpoint_limits: Dict[str, int] = {
            "/api/trade": 10,
            "/api/swap": 10,
            "/api/withdraw": 5,
            "/api/sentiment": 30,
        }

    def _get_client_key(self, request) -> str:
        """Get unique client identifier."""
        # Try API key first, then IP
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key}"

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        return f"ip:{request.remote or 'unknown'}"

    def _get_limit(self, path: str) -> int:
        """Get rate limit for endpoint."""
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        return self.default_limit

    async def check_limit(self, request) -> tuple[bool, Dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, info).
        """
        async with self._lock:
            client_key = self._get_client_key(request)
            limit = self._get_limit(request.path)
            now = time.time()

            # Clean old requests
            self.requests[client_key] = [
                t for t in self.requests[client_key]
                if now - t < self.window_seconds
            ]

            current = len(self.requests[client_key])
            remaining = max(0, limit - current)

            info = {
                "limit": limit,
                "remaining": remaining,
                "reset": int(now + self.window_seconds),
            }

            if current >= limit:
                return False, info

            self.requests[client_key].append(now)
            return True, info

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        allowed, info = await self.check_limit(request)

        if not allowed:
            from aiohttp import web
            return web.json_response(
                {"error": "Rate limit exceeded", "retry_after": info["reset"]},
                status=429,
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(self.window_seconds),
                }
            )

        response = await handler(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response


# === CORS MIDDLEWARE ===

class CORSMiddleware:
    """
    CORS middleware with configurable origins.
    """

    def __init__(self, allowed_origins: Set[str] = None,
                 allowed_methods: Set[str] = None,
                 allowed_headers: Set[str] = None,
                 allow_credentials: bool = True,
                 max_age: int = 86400):

        self.allowed_origins = allowed_origins or {
            "http://localhost:3000",
            "http://localhost:5173",
            "https://jarvislife.io",
            "https://www.jarvislife.io",
        }
        self.allowed_methods = allowed_methods or {
            "GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"
        }
        self.allowed_headers = allowed_headers or {
            "Content-Type", "Authorization", "X-API-Key", "X-Request-ID"
        }
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed."""
        if not origin:
            return False
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins

    def _get_cors_headers(self, origin: str) -> Dict[str, str]:
        """Get CORS headers for response."""
        headers = {}

        if self._is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
        else:
            # Don't set header if origin not allowed
            return headers

        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
        headers["Access-Control-Max-Age"] = str(self.max_age)

        return headers

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        origin = request.headers.get("Origin", "")

        # Handle preflight OPTIONS request
        if request.method == "OPTIONS":
            from aiohttp import web
            cors_headers = self._get_cors_headers(origin)
            return web.Response(status=204, headers=cors_headers)

        response = await handler(request)

        # Add CORS headers to response
        cors_headers = self._get_cors_headers(origin)
        for key, value in cors_headers.items():
            response.headers[key] = value

        return response


# === SECURITY HEADERS ===

class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """

    def __init__(self):
        self.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        response = await handler(request)

        for key, value in self.headers.items():
            response.headers[key] = value

        return response


# === INPUT VALIDATION ===

class InputValidationMiddleware:
    """
    Validate and sanitize input.
    """

    MAX_BODY_SIZE = 1024 * 1024  # 1MB
    MAX_QUERY_LENGTH = 2048

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        from aiohttp import web

        # Check query string length
        if len(str(request.query_string)) > self.MAX_QUERY_LENGTH:
            return web.json_response(
                {"error": "Query string too long"},
                status=400
            )

        # Check content length
        content_length = request.content_length or 0
        if content_length > self.MAX_BODY_SIZE:
            return web.json_response(
                {"error": "Request body too large"},
                status=413
            )

        return await handler(request)


# === CSRF PROTECTION ===

class CSRFMiddleware:
    """
    CSRF protection for state-changing requests.
    """

    def __init__(self, token_header: str = "X-CSRF-Token",
                 safe_methods: Set[str] = None):
        self.token_header = token_header
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS"}
        self._tokens: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        import secrets
        token = secrets.token_urlsafe(32)
        async with self._lock:
            self._tokens[token] = time.time()
        return token

    async def validate_token(self, token: str) -> bool:
        """Validate CSRF token."""
        async with self._lock:
            if token not in self._tokens:
                return False

            # Token expires after 1 hour
            created = self._tokens[token]
            if time.time() - created > 3600:
                del self._tokens[token]
                return False

            return True

    async def __call__(self, request, handler):
        """AIOHTTP middleware handler."""
        from aiohttp import web

        # Safe methods don't need CSRF
        if request.method in self.safe_methods:
            return await handler(request)

        # Check CSRF token
        token = request.headers.get(self.token_header, "")
        if not token or not await self.validate_token(token):
            return web.json_response(
                {"error": "Invalid or missing CSRF token"},
                status=403
            )

        return await handler(request)


# === MIDDLEWARE SETUP ===

def setup_aiohttp_middleware(app, config: Dict = None):
    """
    Setup all middleware for aiohttp app.

    Usage:
        from core.middleware import setup_aiohttp_middleware
        app = web.Application()
        setup_aiohttp_middleware(app)
    """
    config = config or {}

    # Order matters - first added is outermost
    middlewares = [
        SecurityHeadersMiddleware(),
        RequestLogger(
            log_headers=config.get("log_headers", False),
            log_body=config.get("log_body", False)
        ),
        APIRateLimiter(
            default_limit=config.get("rate_limit", 100),
            window_seconds=config.get("rate_window", 60)
        ),
        CORSMiddleware(
            allowed_origins=config.get("cors_origins")
        ),
        InputValidationMiddleware(),
    ]

    for middleware in middlewares:
        app.middlewares.append(middleware)

    logger.info(f"Configured {len(middlewares)} middleware layers")


def setup_fastapi_middleware(app, config: Dict = None):
    """
    Setup all middleware for FastAPI app.

    Usage:
        from core.middleware import setup_fastapi_middleware
        app = FastAPI()
        setup_fastapi_middleware(app)
    """
    from fastapi.middleware.cors import CORSMiddleware as FastAPICORS
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    config = config or {}

    # CORS
    app.add_middleware(
        FastAPICORS,
        allow_origins=list(config.get("cors_origins", [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://jarvislife.io",
        ])),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted hosts
    if config.get("trusted_hosts"):
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=config.get("trusted_hosts")
        )

    # Request logging
    app.add_middleware(fastapi_request_logger())

    logger.info("FastAPI middleware configured")
