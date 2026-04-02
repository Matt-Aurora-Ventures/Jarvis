"""
Request Timeout Middleware.

Provides configurable timeout handling for API endpoints:
- Per-endpoint timeout configuration
- Graceful timeout responses with 504 Gateway Timeout
- Timeout logging for monitoring
- Client-side timeout header support
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Dict
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("jarvis.api.middleware.timeout")

# Context var to track current request timeout
request_timeout_var: ContextVar[Optional[float]] = ContextVar("request_timeout", default=None)


class TimeoutConfig:
    """Configuration for request timeouts."""

    # Default timeout in seconds (30s)
    DEFAULT_TIMEOUT = 30.0

    # Per-endpoint timeouts (path -> timeout in seconds)
    ENDPOINT_TIMEOUTS: Dict[str, float] = {
        # Health checks - fast
        "/api/health": 5.0,
        "/api/health/components": 10.0,

        # Simple queries - moderate
        "/api/staking/pool": 10.0,
        "/api/staking/user": 10.0,
        "/api/credits/balance": 10.0,
        "/api/credits/packages": 5.0,
        "/api/credits/rewards": 5.0,

        # Transaction building - moderate
        "/api/staking/stake": 15.0,
        "/api/staking/unstake/initiate": 15.0,
        "/api/staking/unstake/complete": 15.0,
        "/api/staking/rewards/claim": 15.0,

        # History/pagination - longer
        "/api/credits/history": 20.0,
        "/api/staking/rewards/history": 20.0,

        # Checkout/payment - longer
        "/api/credits/checkout": 30.0,
        "/api/credits/redeem": 15.0,

        # Webhooks - fast
        "/api/credits/webhook": 10.0,

        # Trading operations - longer
        "/api/trading": 30.0,

        # Market data - moderate
        "/api/market": 15.0,

        # Metrics/monitoring - fast
        "/api/metrics": 10.0,
        "/api/traces": 15.0,
        "/api/compression-stats": 5.0,
    }

    # Max timeout clients can request
    MAX_CLIENT_TIMEOUT = 120.0

    @classmethod
    def get_timeout_for_path(cls, path: str) -> float:
        """
        Get timeout for a given path.

        Supports:
        - Exact matches: /api/health -> 5.0
        - Prefix matches: /api/trading/orders -> 30.0 (from /api/trading)
        """
        # Try exact match first
        if path in cls.ENDPOINT_TIMEOUTS:
            return cls.ENDPOINT_TIMEOUTS[path]

        # Try prefix match (longest prefix wins)
        matching_prefixes = [
            (prefix, timeout)
            for prefix, timeout in cls.ENDPOINT_TIMEOUTS.items()
            if path.startswith(prefix)
        ]

        if matching_prefixes:
            # Sort by prefix length (descending) to get most specific match
            matching_prefixes.sort(key=lambda x: len(x[0]), reverse=True)
            return matching_prefixes[0][1]

        # Default
        return cls.DEFAULT_TIMEOUT


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeouts.

    Features:
    - Configurable per-endpoint timeouts
    - Client can request timeout via X-Request-Timeout header
    - Graceful timeout responses with 504 status
    - Logs timeout occurrences for monitoring
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._timeout_count = 0
        self._total_requests = 0

    async def dispatch(self, request: Request, call_next: Callable):
        """Handle request with timeout."""
        if not self.enabled:
            return await call_next(request)

        self._total_requests += 1

        # Determine timeout
        timeout = self._get_timeout(request)
        request_timeout_var.set(timeout)

        # Track start time
        start_time = time.time()

        try:
            # Execute request with timeout
            response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )

            # Add timeout info to response headers
            elapsed = time.time() - start_time
            response.headers["X-Request-Timeout"] = str(timeout)
            response.headers["X-Request-Duration"] = f"{elapsed:.3f}"

            return response

        except asyncio.TimeoutError:
            # Request timed out
            self._timeout_count += 1
            elapsed = time.time() - start_time

            logger.warning(
                f"Request timeout: {request.method} {request.url.path} "
                f"(timeout={timeout}s, elapsed={elapsed:.2f}s)"
            )

            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "SYS_004",
                        "message": "Request timeout",
                        "details": f"Request exceeded timeout of {timeout}s",
                    },
                    "timeout_seconds": timeout,
                    "elapsed_seconds": round(elapsed, 2),
                },
                headers={
                    "X-Request-Timeout": str(timeout),
                    "X-Request-Duration": f"{elapsed:.3f}",
                    "Retry-After": "60",  # Suggest retry after 60s
                }
            )

    def _get_timeout(self, request: Request) -> float:
        """Determine timeout for this request."""
        # Check if client requested specific timeout
        client_timeout = request.headers.get("X-Request-Timeout")
        if client_timeout:
            try:
                timeout = float(client_timeout)
                # Respect client timeout but cap at maximum
                if 0 < timeout <= TimeoutConfig.MAX_CLIENT_TIMEOUT:
                    return timeout
                elif timeout > TimeoutConfig.MAX_CLIENT_TIMEOUT:
                    logger.debug(
                        f"Client requested timeout {timeout}s exceeds max "
                        f"{TimeoutConfig.MAX_CLIENT_TIMEOUT}s, using max"
                    )
                    return TimeoutConfig.MAX_CLIENT_TIMEOUT
            except (ValueError, TypeError):
                logger.debug(f"Invalid client timeout header: {client_timeout}")

        # Use configured timeout for this endpoint
        path = request.url.path
        return TimeoutConfig.get_timeout_for_path(path)

    def get_stats(self) -> dict:
        """Get timeout statistics."""
        return {
            "total_requests": self._total_requests,
            "timeout_count": self._timeout_count,
            "timeout_rate": self._timeout_count / self._total_requests if self._total_requests > 0 else 0,
        }


def get_current_timeout() -> Optional[float]:
    """Get the timeout for the current request context."""
    return request_timeout_var.get()
