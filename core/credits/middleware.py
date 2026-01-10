"""
API Metering Middleware.

Express-style middleware for credit consumption on API requests.

Features:
- Per-endpoint credit costs
- Balance checking before execution
- Usage logging
- Rate limiting
- Graceful degradation
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional

from core.credits.manager import (
    CreditManager,
    get_credit_manager,
    InsufficientCreditsError,
    UserNotFoundError,
)
from core.credits.models import get_endpoint_cost

logger = logging.getLogger("jarvis.credits.middleware")


@dataclass
class MeteringResult:
    """Result of metering check."""
    allowed: bool
    user_id: str
    endpoint: str
    credits_required: int
    balance_before: int = 0
    balance_after: int = 0
    request_id: str = ""
    error: Optional[str] = None


class CreditMeteringMiddleware:
    """
    Middleware for API credit metering.

    Usage with FastAPI:
        middleware = CreditMeteringMiddleware()

        @app.middleware("http")
        async def metering_middleware(request, call_next):
            return await middleware.process(request, call_next)

    Usage as decorator:
        @metered(cost=5)
        async def expensive_endpoint(user_id: str):
            ...
    """

    def __init__(
        self,
        credit_manager: CreditManager = None,
        bypass_paths: list = None,
        default_cost: int = 1,
        allow_negative: bool = False,
        rate_limit_per_minute: int = 100,
    ):
        """
        Initialize middleware.

        Args:
            credit_manager: CreditManager instance
            bypass_paths: Paths that don't require credits
            default_cost: Default credit cost if not specified
            allow_negative: Allow requests even with insufficient credits
            rate_limit_per_minute: Rate limit per user per minute
        """
        self.credit_manager = credit_manager
        self.bypass_paths = bypass_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/",
            "/credits/packages",
            "/credits/purchase",
        ]
        self.default_cost = default_cost
        self.allow_negative = allow_negative
        self.rate_limit = rate_limit_per_minute

        # Rate limiting state
        self._request_counts: Dict[str, list] = {}

    def _ensure_manager(self):
        """Ensure credit manager is available."""
        if self.credit_manager is None:
            self.credit_manager = get_credit_manager()

    def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit."""
        now = time.time()
        minute_ago = now - 60

        # Get user's request timestamps
        if user_id not in self._request_counts:
            self._request_counts[user_id] = []

        # Clean old timestamps
        self._request_counts[user_id] = [
            ts for ts in self._request_counts[user_id]
            if ts > minute_ago
        ]

        # Check limit
        if len(self._request_counts[user_id]) >= self.rate_limit:
            return False

        # Add current request
        self._request_counts[user_id].append(now)
        return True

    def _is_bypass_path(self, path: str) -> bool:
        """Check if path should bypass metering."""
        for bypass in self.bypass_paths:
            if path.startswith(bypass):
                return True
        return False

    async def check_and_deduct(
        self,
        user_id: str,
        endpoint: str,
        cost: int = None,
    ) -> MeteringResult:
        """
        Check credits and deduct if sufficient.

        Args:
            user_id: User identifier
            endpoint: API endpoint
            cost: Credit cost (uses endpoint default if not specified)

        Returns:
            MeteringResult
        """
        self._ensure_manager()

        request_id = str(uuid.uuid4())[:8]
        cost = cost or get_endpoint_cost(endpoint)

        result = MeteringResult(
            allowed=False,
            user_id=user_id,
            endpoint=endpoint,
            credits_required=cost,
            request_id=request_id,
        )

        try:
            # Check rate limit
            if not self._check_rate_limit(user_id):
                result.error = "Rate limit exceeded"
                return result

            # Get current balance
            balance = self.credit_manager.get_balance(user_id)
            result.balance_before = balance.balance

            # Check if sufficient
            if balance.balance < cost:
                if not self.allow_negative:
                    result.error = f"Insufficient credits: {balance.balance} < {cost}"
                    return result

            # Deduct credits
            success, remaining = self.credit_manager.consume_credits(
                user_id=user_id,
                amount=cost,
                endpoint=endpoint,
                request_id=request_id,
            )

            result.allowed = success
            result.balance_after = remaining

            logger.debug(f"Metering: {user_id} {endpoint} -{cost} credits (remaining: {remaining})")

        except UserNotFoundError:
            result.error = "User not found"
        except InsufficientCreditsError as e:
            result.error = str(e)
        except Exception as e:
            logger.error(f"Metering error: {e}")
            result.error = f"Internal error: {e}"

        return result

    async def process_fastapi(self, request, call_next):
        """
        FastAPI middleware processor.

        Usage:
            @app.middleware("http")
            async def meter(request, call_next):
                return await middleware.process_fastapi(request, call_next)
        """
        from fastapi import Response
        from fastapi.responses import JSONResponse

        # Check bypass paths
        if self._is_bypass_path(request.url.path):
            return await call_next(request)

        # Extract user ID (from header, token, etc.)
        user_id = self._extract_user_id(request)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required"},
            )

        # Check and deduct
        start_time = time.time()
        result = await self.check_and_deduct(user_id, request.url.path)

        if not result.allowed:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment required",
                    "message": result.error,
                    "credits_required": result.credits_required,
                    "current_balance": result.balance_before,
                },
                headers={
                    "X-Credits-Required": str(result.credits_required),
                    "X-Credits-Balance": str(result.balance_before),
                },
            )

        # Process request
        response = await call_next(request)

        # Add credit info to response headers
        response.headers["X-Credits-Consumed"] = str(result.credits_required)
        response.headers["X-Credits-Remaining"] = str(result.balance_after)
        response.headers["X-Request-ID"] = result.request_id

        # Log request duration
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"Request {result.request_id}: {duration_ms}ms")

        return response

    def _extract_user_id(self, request) -> Optional[str]:
        """Extract user ID from request."""
        # Try API key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Would validate and lookup user from API key
            return f"apikey_{api_key[:8]}"

        # Try Authorization header (Bearer token)
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]
            # Would decode JWT and extract user_id
            return f"token_{token[:8]}"

        # Try query param (for testing)
        user_id = request.query_params.get("user_id")
        if user_id:
            return user_id

        return None


# =============================================================================
# Decorator for manual metering
# =============================================================================


def metered(cost: int = None, endpoint: str = None):
    """
    Decorator for metered API endpoints.

    Usage:
        @metered(cost=5)
        async def expensive_operation(user_id: str, ...):
            ...

        @metered(endpoint="/api/trade/execute")
        def trade(user_id: str, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract user_id from kwargs or first arg
            user_id = kwargs.get("user_id")
            if user_id is None and args:
                user_id = args[0]

            if user_id is None:
                raise ValueError("user_id required for metered endpoint")

            middleware = CreditMeteringMiddleware()
            ep = endpoint or f"/{func.__module__}.{func.__name__}"
            c = cost or get_endpoint_cost(ep)

            result = await middleware.check_and_deduct(user_id, ep, c)

            if not result.allowed:
                raise InsufficientCreditsError(result.error)

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.get_event_loop().run_until_complete(
                async_wrapper(*args, **kwargs)
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Flask/Express-style middleware
# =============================================================================


class ExpressStyleMiddleware:
    """
    Express-style middleware for non-FastAPI frameworks.

    Usage:
        middleware = ExpressStyleMiddleware()

        # Before request
        result = middleware.before_request(user_id, endpoint)
        if not result.allowed:
            return error_response(402, result.error)

        # After request
        middleware.after_request(result)
    """

    def __init__(self):
        self._middleware = CreditMeteringMiddleware()
        self._pending_requests: Dict[str, MeteringResult] = {}

    async def before_request(
        self,
        user_id: str,
        endpoint: str,
        cost: int = None,
    ) -> MeteringResult:
        """Call before processing request."""
        result = await self._middleware.check_and_deduct(user_id, endpoint, cost)
        self._pending_requests[result.request_id] = result
        return result

    def after_request(
        self,
        request_id: str,
        success: bool = True,
        refund_on_error: bool = False,
    ):
        """Call after processing request."""
        result = self._pending_requests.pop(request_id, None)

        if result and not success and refund_on_error:
            # Refund credits on error
            self._middleware.credit_manager.add_credits(
                user_id=result.user_id,
                amount=result.credits_required,
                description=f"Refund for failed request {request_id}",
            )

        return result
