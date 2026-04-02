"""
JARVIS Caching Headers Middleware

Adds HTTP caching headers to responses for improved performance.
"""

from typing import Dict, Optional, Callable, List
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re


@dataclass
class CacheConfig:
    """Cache configuration for a route pattern."""
    pattern: str
    max_age: int = 0  # seconds
    s_maxage: int = 0  # CDN cache seconds
    private: bool = False
    no_cache: bool = False
    no_store: bool = False
    must_revalidate: bool = False
    stale_while_revalidate: int = 0
    stale_if_error: int = 0
    vary: List[str] = None

    def __post_init__(self):
        if self.vary is None:
            self.vary = []


# Default cache configurations for common patterns
DEFAULT_CACHE_CONFIGS = [
    # Health endpoints - no cache
    CacheConfig(
        pattern=r"^/health",
        no_cache=True,
        no_store=True,
    ),
    # API versioning - no cache
    CacheConfig(
        pattern=r"^/api/version",
        no_cache=True,
        must_revalidate=True,
    ),
    # Static assets - long cache
    CacheConfig(
        pattern=r"\.(js|css|png|jpg|jpeg|gif|ico|woff2?)$",
        max_age=31536000,  # 1 year
        s_maxage=31536000,
    ),
    # API documentation - moderate cache
    CacheConfig(
        pattern=r"^/docs",
        max_age=3600,  # 1 hour
        s_maxage=86400,  # 24 hours for CDN
    ),
    # Price data - short cache
    CacheConfig(
        pattern=r"^/api/v1/prices",
        max_age=60,  # 1 minute
        s_maxage=30,
        stale_while_revalidate=60,
    ),
    # Trading endpoints - no cache
    CacheConfig(
        pattern=r"^/api/v1/(trade|order)",
        no_cache=True,
        no_store=True,
        private=True,
    ),
    # User data - private cache
    CacheConfig(
        pattern=r"^/api/v1/(user|profile|settings)",
        private=True,
        max_age=60,
        must_revalidate=True,
    ),
    # Chat endpoints - no cache
    CacheConfig(
        pattern=r"^/api/v1/chat",
        no_cache=True,
        no_store=True,
        private=True,
    ),
    # Default API - short cache
    CacheConfig(
        pattern=r"^/api/",
        max_age=30,
        private=True,
        vary=["Authorization", "Accept"],
    ),
]


def build_cache_control_header(config: CacheConfig) -> str:
    """Build Cache-Control header value from config."""
    directives = []

    if config.no_store:
        directives.append("no-store")
    elif config.no_cache:
        directives.append("no-cache")
    else:
        if config.private:
            directives.append("private")
        else:
            directives.append("public")

        if config.max_age > 0:
            directives.append(f"max-age={config.max_age}")

        if config.s_maxage > 0:
            directives.append(f"s-maxage={config.s_maxage}")

    if config.must_revalidate:
        directives.append("must-revalidate")

    if config.stale_while_revalidate > 0:
        directives.append(f"stale-while-revalidate={config.stale_while_revalidate}")

    if config.stale_if_error > 0:
        directives.append(f"stale-if-error={config.stale_if_error}")

    return ", ".join(directives)


def get_cache_config(path: str, configs: List[CacheConfig] = None) -> Optional[CacheConfig]:
    """Get cache configuration for a given path."""
    if configs is None:
        configs = DEFAULT_CACHE_CONFIGS

    for config in configs:
        if re.match(config.pattern, path):
            return config

    return None


def generate_etag(content: bytes) -> str:
    """Generate ETag for content."""
    return f'"{hashlib.md5(content).hexdigest()}"'


def generate_weak_etag(content: bytes) -> str:
    """Generate weak ETag for content."""
    return f'W/"{hashlib.md5(content).hexdigest()}"'


class CachingHeadersMiddleware:
    """
    Middleware to add caching headers to responses.

    Usage with FastAPI:
        from api.middleware.caching_headers import CachingHeadersMiddleware

        app.add_middleware(CachingHeadersMiddleware)
    """

    def __init__(
        self,
        app,
        configs: List[CacheConfig] = None,
        add_etag: bool = True,
    ):
        self.app = app
        self.configs = configs or DEFAULT_CACHE_CONFIGS
        self.add_etag = add_etag

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        # Only add caching headers for GET and HEAD requests
        if method not in ("GET", "HEAD"):
            await self.app(scope, receive, send)
            return

        config = get_cache_config(path, self.configs)

        response_started = False
        response_body = []

        async def send_wrapper(message):
            nonlocal response_started, response_body

            if message["type"] == "http.response.start":
                response_started = True
                headers = dict(message.get("headers", []))

                # Add Cache-Control if we have a config
                if config:
                    cache_control = build_cache_control_header(config)
                    headers[b"cache-control"] = cache_control.encode()

                    # Add Vary header
                    if config.vary:
                        headers[b"vary"] = ", ".join(config.vary).encode()

                # Convert back to list of tuples
                message = {
                    **message,
                    "headers": list(headers.items()),
                }

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_body.append(body)

                # Add ETag on final body chunk
                if self.add_etag and message.get("more_body", False) is False:
                    full_body = b"".join(response_body)
                    if full_body:
                        etag = generate_etag(full_body)
                        # Note: Would need to modify the start message
                        # This is a simplified version

            await send(message)

        await self.app(scope, receive, send_wrapper)


# FastAPI dependency for manual cache control
def cache_response(
    max_age: int = 60,
    private: bool = False,
    no_cache: bool = False,
    vary: List[str] = None
) -> Dict[str, str]:
    """
    Generate cache headers for a FastAPI response.

    Usage:
        @app.get("/data")
        async def get_data():
            headers = cache_response(max_age=300)
            return JSONResponse({"data": "value"}, headers=headers)
    """
    config = CacheConfig(
        pattern="",
        max_age=max_age,
        private=private,
        no_cache=no_cache,
        vary=vary or [],
    )

    headers = {
        "Cache-Control": build_cache_control_header(config),
    }

    if config.vary:
        headers["Vary"] = ", ".join(config.vary)

    return headers


def no_cache_headers() -> Dict[str, str]:
    """Get headers for no-cache response."""
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }


def immutable_cache_headers(max_age: int = 31536000) -> Dict[str, str]:
    """Get headers for immutable content (versioned assets)."""
    return {
        "Cache-Control": f"public, max-age={max_age}, immutable",
    }
