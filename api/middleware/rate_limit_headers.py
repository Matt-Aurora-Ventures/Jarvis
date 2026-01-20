"""
JARVIS Rate Limit Headers Middleware

Adds rate limit information to response headers:
- X-RateLimit-Limit: Maximum requests allowed
- X-RateLimit-Remaining: Requests remaining in window
- X-RateLimit-Reset: Time until limit resets (Unix timestamp)
- Retry-After: Seconds until client can retry (when rate limited)

Usage:
    from api.middleware.rate_limit_headers import RateLimitHeadersMiddleware

    app.add_middleware(RateLimitHeadersMiddleware)
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger("jarvis.api.rate_limit")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10  # Max requests in 1 second
    enabled: bool = True


@dataclass
class UserTierConfig:
    """Per-user tier rate limit configuration"""
    tier_name: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10


@dataclass
class RateLimitState:
    """Current rate limit state for a client"""
    minute_count: int = 0
    minute_start: float = 0.0
    hour_count: int = 0
    hour_start: float = 0.0
    day_count: int = 0
    day_start: float = 0.0
    burst_count: int = 0
    burst_start: float = 0.0


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    In-memory rate limiter with sliding window.

    Tracks requests per minute, hour, and day for each client.
    Supports per-user tier-based limits.
    """

    def __init__(
        self,
        config: RateLimitConfig = None,
        user_tiers: Optional[Dict[str, UserTierConfig]] = None
    ):
        self.config = config or RateLimitConfig()
        self._states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._user_tiers = user_tiers or {}
        self._admin_users: Set[str] = set()
        self._internal_services: Set[str] = set()
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        client_id: str,
        user_id: Optional[str] = None,
        user_tier: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is within rate limits.

        Args:
            client_id: Unique identifier for the client (IP or API key)
            user_id: Optional user ID for per-user limits
            user_tier: Optional user tier for tier-based limits

        Returns:
            Tuple of (allowed, headers_dict)
        """
        if not self.config.enabled:
            return True, {}

        # Admin override
        if user_id and user_id in self._admin_users:
            return True, {"X-RateLimit-Admin": "true"}

        # Internal service bypass
        if client_id in self._internal_services:
            return True, {"X-RateLimit-Internal": "true"}

        # Determine effective config
        effective_config = self._get_effective_config(user_tier)

        async with self._lock:
            now = time.time()

            # Use user_id if available for per-user tracking, otherwise client_id
            tracking_id = f"user:{user_id}" if user_id else client_id
            state = self._states[tracking_id]

            # Reset windows if expired
            self._reset_windows(state, now)

            # Check limits
            headers = {}
            allowed = True
            retry_after = 0

            # Check burst limit (1 second window)
            if state.burst_count >= effective_config.burst_limit:
                allowed = False
                retry_after = max(retry_after, 1)

            # Check minute limit
            if state.minute_count >= effective_config.requests_per_minute:
                allowed = False
                retry_after = max(retry_after, int(60 - (now - state.minute_start)))

            # Check hour limit
            if state.hour_count >= effective_config.requests_per_hour:
                allowed = False
                retry_after = max(retry_after, int(3600 - (now - state.hour_start)))

            # Check day limit
            if state.day_count >= effective_config.requests_per_day:
                allowed = False
                retry_after = max(retry_after, int(86400 - (now - state.day_start)))

            # Update counters if allowed
            if allowed:
                state.burst_count += 1
                state.minute_count += 1
                state.hour_count += 1
                state.day_count += 1

            # Build headers
            headers = {
                "X-RateLimit-Limit": str(effective_config.requests_per_minute),
                "X-RateLimit-Remaining": str(max(0, effective_config.requests_per_minute - state.minute_count)),
                "X-RateLimit-Reset": str(int(state.minute_start + 60)),
            }

            if user_tier:
                headers["X-RateLimit-Tier"] = user_tier

            if not allowed:
                headers["Retry-After"] = str(retry_after)

            return allowed, headers

    def _get_effective_config(self, user_tier: Optional[str]) -> RateLimitConfig:
        """Get effective rate limit config based on user tier."""
        if user_tier and user_tier in self._user_tiers:
            tier_config = self._user_tiers[user_tier]
            return RateLimitConfig(
                requests_per_minute=tier_config.requests_per_minute,
                requests_per_hour=tier_config.requests_per_hour,
                requests_per_day=tier_config.requests_per_day,
                burst_limit=tier_config.burst_limit,
                enabled=self.config.enabled,
            )
        return self.config

    def add_user_tier(self, tier_name: str, tier_config: UserTierConfig):
        """Add or update a user tier configuration."""
        self._user_tiers[tier_name] = tier_config

    def add_admin_user(self, user_id: str):
        """Add user to admin list (bypass rate limits)."""
        self._admin_users.add(user_id)

    def remove_admin_user(self, user_id: str):
        """Remove user from admin list."""
        self._admin_users.discard(user_id)

    def add_internal_service(self, service_id: str):
        """Add service to internal list (bypass rate limits)."""
        self._internal_services.add(service_id)

    def remove_internal_service(self, service_id: str):
        """Remove service from internal list."""
        self._internal_services.discard(service_id)

    def _reset_windows(self, state: RateLimitState, now: float):
        """Reset expired time windows"""
        # Burst window (1 second)
        if now - state.burst_start >= 1:
            state.burst_count = 0
            state.burst_start = now

        # Minute window
        if now - state.minute_start >= 60:
            state.minute_count = 0
            state.minute_start = now

        # Hour window
        if now - state.hour_start >= 3600:
            state.hour_count = 0
            state.hour_start = now

        # Day window
        if now - state.day_start >= 86400:
            state.day_count = 0
            state.day_start = now

    def get_client_stats(self, client_id: str, user_id: Optional[str] = None) -> Dict[str, int]:
        """Get current stats for a client or user"""
        tracking_id = f"user:{user_id}" if user_id else client_id
        state = self._states.get(tracking_id)
        if not state:
            return {}

        return {
            "minute_count": state.minute_count,
            "minute_remaining": max(0, self.config.requests_per_minute - state.minute_count),
            "hour_count": state.hour_count,
            "hour_remaining": max(0, self.config.requests_per_hour - state.hour_count),
            "day_count": state.day_count,
            "day_remaining": max(0, self.config.requests_per_day - state.day_count),
        }

    def reset_client(self, client_id: str, user_id: Optional[str] = None):
        """Reset rate limit for a client or user"""
        tracking_id = f"user:{user_id}" if user_id else client_id
        if tracking_id in self._states:
            del self._states[tracking_id]


# =============================================================================
# MIDDLEWARE
# =============================================================================

class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limit headers to responses.

    Features:
    - Per-IP rate limiting
    - Per-user rate limiting
    - User tier-based limits
    - Admin override capability
    - Internal service bypass
    - Multiple time windows (burst/minute/hour/day)
    - Standard rate limit headers
    - Automatic 429 responses when limited
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        burst_limit: int = 10,
        enabled: bool = True,
        exclude_paths: list = None,
        custom_key_func: Callable[[Request], str] = None,
        user_id_header: str = "X-User-ID",
        user_tier_header: str = "X-User-Tier",
        user_tiers: Optional[Dict[str, UserTierConfig]] = None,
    ):
        super().__init__(app)

        self.config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            requests_per_day=requests_per_day,
            burst_limit=burst_limit,
            enabled=enabled,
        )
        self.limiter = RateLimiter(self.config, user_tiers=user_tiers)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
        self.custom_key_func = custom_key_func
        self.user_id_header = user_id_header
        self.user_tier_header = user_tier_header

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request with rate limiting"""
        # Check if path is excluded
        if self._is_excluded(request.url.path):
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Get user ID and tier from headers (if available)
        user_id = request.headers.get(self.user_id_header)
        user_tier = request.headers.get(self.user_tier_header)

        # Check rate limit (per-user if user_id available, otherwise per-IP)
        allowed, headers = await self.limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id,
            user_tier=user_tier,
        )

        if not allowed:
            # Return 429 Too Many Requests
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please slow down.",
                        "user_id": user_id,
                        "tier": user_tier,
                    }
                }
            )
            for key, value in headers.items():
                response.headers[key] = value
            return response

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response

    def _is_excluded(self, path: str) -> bool:
        """Check if path is excluded from rate limiting"""
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False

    def _get_client_id(self, request: Request) -> str:
        """Get unique identifier for the client"""
        if self.custom_key_func:
            return self.custom_key_func(request)

        # Try to get API key first
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if api_key:
            return f"key:{api_key[:20]}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def add_rate_limit_middleware(
    app,
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    **kwargs,
):
    """
    Helper to add rate limit middleware to FastAPI app.

    Usage:
        from api.middleware.rate_limit_headers import add_rate_limit_middleware
        add_rate_limit_middleware(app, requests_per_minute=100)
    """
    app.add_middleware(
        RateLimitHeadersMiddleware,
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        **kwargs,
    )


# =============================================================================
# DECORATOR FOR ROUTE-SPECIFIC LIMITS
# =============================================================================

_route_limiters: Dict[str, RateLimiter] = {}


def rate_limit(
    requests_per_minute: int = 10,
    requests_per_hour: int = 100,
    key: str = None,
):
    """
    Decorator to apply rate limiting to specific routes.

    Usage:
        @app.get("/expensive-operation")
        @rate_limit(requests_per_minute=5)
        async def expensive_operation():
            ...
    """
    def decorator(func):
        limiter_key = key or func.__name__

        if limiter_key not in _route_limiters:
            _route_limiters[limiter_key] = RateLimiter(RateLimitConfig(
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
            ))

        async def wrapper(request: Request, *args, **kwargs):
            limiter = _route_limiters[limiter_key]

            # Get client ID from request
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_id = forwarded.split(",")[0].strip()
            else:
                client_id = request.client.host if request.client else "unknown"

            allowed, headers = await limiter.check_rate_limit(client_id)

            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded for this endpoint"},
                    headers=headers,
                )

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator
