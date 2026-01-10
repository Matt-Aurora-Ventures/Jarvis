"""
API Metering Middleware.

Credit-based API consumption tracking:
- Extract user from JWT/API key
- Check credit balance
- Deduct based on endpoint cost
- Rate limiting
- Usage logging
"""

import asyncio
import hashlib
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.payments.metering")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class EndpointCost:
    """Cost configuration for an endpoint."""
    path_pattern: str
    credits: int
    description: str


# Endpoint costs
ENDPOINT_COSTS: Dict[str, int] = {
    # Trading endpoints
    "/api/trade/quote": 1,
    "/api/trade/execute": 5,
    "/api/trade/history": 1,

    # Analysis endpoints
    "/api/analyze": 10,
    "/api/analyze/token": 5,
    "/api/analyze/wallet": 10,

    # Backtesting
    "/api/backtest": 50,
    "/api/backtest/run": 100,

    # Data endpoints
    "/api/data/tokens": 1,
    "/api/data/prices": 1,

    # Default for unlisted endpoints
    "__default__": 1,
}


# Rate limits by tier (requests per minute)
RATE_LIMITS: Dict[str, int] = {
    "free": 10,
    "starter": 50,
    "pro": 100,
    "whale": 500,
    "admin": 10000,
}


# =============================================================================
# Credit Balance Cache
# =============================================================================


class BalanceCache:
    """
    In-memory balance cache for fast lookups.

    Features:
    - TTL-based expiration
    - Optimistic updates
    - Background sync
    """

    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, Dict] = {}
        self._ttl = ttl_seconds
        self._pending_deductions: Dict[str, int] = defaultdict(int)

    def get(self, user_id: str) -> Optional[Dict]:
        """Get cached balance."""
        entry = self._cache.get(user_id)
        if entry:
            if time.time() < entry["expires_at"]:
                return entry["balance"]
            else:
                del self._cache[user_id]
        return None

    def set(self, user_id: str, balance: Dict):
        """Cache a balance."""
        self._cache[user_id] = {
            "balance": balance,
            "expires_at": time.time() + self._ttl,
        }

    def deduct(self, user_id: str, credits: int) -> bool:
        """Optimistically deduct credits from cache."""
        entry = self._cache.get(user_id)
        if entry and time.time() < entry["expires_at"]:
            current = entry["balance"].get("credits", 0)
            if current >= credits:
                entry["balance"]["credits"] = current - credits
                self._pending_deductions[user_id] += credits
                return True
        return False

    def get_pending(self, user_id: str) -> int:
        """Get pending deductions for batch write."""
        return self._pending_deductions.pop(user_id, 0)

    def invalidate(self, user_id: str):
        """Invalidate cache for user."""
        self._cache.pop(user_id, None)
        self._pending_deductions.pop(user_id, None)


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """
    Sliding window rate limiter.

    Features:
    - Per-user limits based on tier
    - Sliding window algorithm
    - Efficient memory usage
    """

    def __init__(self, window_seconds: int = 60):
        self._window = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def check(self, user_id: str, tier: str) -> Tuple[bool, int]:
        """
        Check if request is allowed.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        limit = RATE_LIMITS.get(tier, RATE_LIMITS["free"])
        now = time.time()
        window_start = now - self._window

        # Clean old requests
        self._requests[user_id] = [
            t for t in self._requests[user_id]
            if t > window_start
        ]

        current_count = len(self._requests[user_id])
        remaining = max(0, limit - current_count)

        if current_count >= limit:
            return False, 0

        return True, remaining

    def record(self, user_id: str):
        """Record a request."""
        self._requests[user_id].append(time.time())

    def get_reset_time(self, user_id: str) -> int:
        """Get seconds until rate limit resets."""
        if not self._requests[user_id]:
            return 0

        oldest = min(self._requests[user_id])
        reset_at = oldest + self._window
        return max(0, int(reset_at - time.time()))


# =============================================================================
# Usage Logger
# =============================================================================


class UsageLogger:
    """
    Logs API usage for analytics and billing.

    Features:
    - Batch writes for efficiency
    - Async flush
    """

    def __init__(self, batch_size: int = 100, flush_interval: int = 30):
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: List[Dict] = []
        self._last_flush = time.time()

    async def log(
        self,
        user_id: str,
        endpoint: str,
        credits: int,
        response_time_ms: float,
        status_code: int,
        metadata: Dict = None,
    ):
        """Log API usage."""
        self._buffer.append({
            "user_id": user_id,
            "endpoint": endpoint,
            "credits": credits,
            "response_time_ms": response_time_ms,
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        })

        # Flush if batch is full or interval elapsed
        if (len(self._buffer) >= self._batch_size or
            time.time() - self._last_flush > self._flush_interval):
            await self.flush()

    async def flush(self):
        """Flush buffer to storage."""
        if not self._buffer:
            return

        batch = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = time.time()

        # In production, write to database
        # await db.api_usage.insert_many(batch)
        logger.debug(f"Flushed {len(batch)} usage records")


# =============================================================================
# Metering Middleware
# =============================================================================


class MeteringMiddleware:
    """
    FastAPI middleware for API credit metering.

    Features:
    - JWT/API key authentication
    - Credit balance checking
    - Rate limiting
    - Usage logging
    """

    def __init__(
        self,
        balance_fetcher: Callable = None,
        balance_deductor: Callable = None,
    ):
        self.cache = BalanceCache()
        self.rate_limiter = RateLimiter()
        self.usage_logger = UsageLogger()

        # Callbacks for balance operations
        self._fetch_balance = balance_fetcher
        self._deduct_balance = balance_deductor

    def get_endpoint_cost(self, path: str, method: str = "GET") -> int:
        """Get credit cost for an endpoint."""
        # Exact match
        if path in ENDPOINT_COSTS:
            return ENDPOINT_COSTS[path]

        # Pattern matching for dynamic routes
        for pattern, cost in ENDPOINT_COSTS.items():
            if pattern.startswith("/") and self._path_matches(pattern, path):
                return cost

        return ENDPOINT_COSTS["__default__"]

    def _path_matches(self, pattern: str, path: str) -> bool:
        """Simple pattern matching for paths."""
        pattern_parts = pattern.split("/")
        path_parts = path.split("/")

        if len(pattern_parts) != len(path_parts):
            return False

        for p, q in zip(pattern_parts, path_parts):
            if p.startswith("{") and p.endswith("}"):
                continue
            if p != q:
                return False

        return True

    async def get_user_balance(self, user_id: str) -> Dict:
        """Get user's credit balance (cached)."""
        cached = self.cache.get(user_id)
        if cached:
            return cached

        # Fetch from source
        if self._fetch_balance:
            balance = await self._fetch_balance(user_id)
        else:
            # Default mock balance
            balance = {
                "credits": 100,
                "tier": "free",
            }

        self.cache.set(user_id, balance)
        return balance

    async def check_and_deduct(
        self,
        user_id: str,
        endpoint: str,
        cost: int,
    ) -> Tuple[bool, Dict]:
        """
        Check balance and deduct credits.

        Returns:
            Tuple of (success, balance_info)
        """
        balance = await self.get_user_balance(user_id)

        if balance.get("credits", 0) < cost:
            return False, {
                "error": "insufficient_credits",
                "required": cost,
                "available": balance.get("credits", 0),
            }

        # Optimistic deduction from cache
        if self.cache.deduct(user_id, cost):
            # Queue background sync
            asyncio.create_task(self._sync_deduction(user_id))

            return True, {
                "credits_used": cost,
                "remaining": balance.get("credits", 0) - cost,
            }

        return False, {"error": "deduction_failed"}

    async def _sync_deduction(self, user_id: str):
        """Sync pending deductions to database."""
        pending = self.cache.get_pending(user_id)
        if pending > 0 and self._deduct_balance:
            try:
                await self._deduct_balance(user_id, pending)
            except Exception as e:
                logger.error(f"Failed to sync deduction for {user_id}: {e}")
                # Invalidate cache on failure
                self.cache.invalidate(user_id)


# =============================================================================
# FastAPI Middleware
# =============================================================================


def create_metering_middleware(app=None):
    """
    Create FastAPI middleware for API metering.

    Usage:
        app = FastAPI()
        middleware = create_metering_middleware(app)
    """
    try:
        from fastapi import Request, Response
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware
    except ImportError:
        return None

    metering = MeteringMiddleware()

    # Endpoints that don't require credits
    FREE_ENDPOINTS = {
        "/api/health",
        "/api/docs",
        "/api/openapi.json",
        "/api/credits/balance",
        "/api/credits/packages",
        "/api/payments/checkout",
        "/api/payments/webhook",
        "/api/staking/pool",
        "/api/consent/options",
    }

    class APIMeteringMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            method = request.method

            # Skip free endpoints
            if path in FREE_ENDPOINTS or path.startswith("/api/docs"):
                return await call_next(request)

            # Skip non-API paths
            if not path.startswith("/api/"):
                return await call_next(request)

            start_time = time.time()

            # Extract user from request
            user_id = await self._extract_user(request)
            if not user_id:
                return JSONResponse(
                    status_code=401,
                    content={"error": "unauthorized", "message": "Missing or invalid authentication"},
                )

            # Get user balance and tier
            try:
                balance = await metering.get_user_balance(user_id)
            except Exception as e:
                logger.error(f"Error fetching balance: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "internal_error"},
                )

            tier = balance.get("tier", "free")

            # Rate limit check
            allowed, remaining = metering.rate_limiter.check(user_id, tier)
            if not allowed:
                reset_time = metering.rate_limiter.get_reset_time(user_id)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "retry_after": reset_time,
                        "limit": RATE_LIMITS.get(tier, 10),
                    },
                    headers={
                        "Retry-After": str(reset_time),
                        "X-RateLimit-Limit": str(RATE_LIMITS.get(tier, 10)),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Get endpoint cost
            cost = metering.get_endpoint_cost(path, method)

            # Check and deduct credits
            success, info = await metering.check_and_deduct(user_id, path, cost)
            if not success:
                return JSONResponse(
                    status_code=402,
                    content={
                        "error": "payment_required",
                        "message": "Insufficient credits",
                        "required": info.get("required", cost),
                        "available": info.get("available", 0),
                        "purchase_url": "/api/credits/packages",
                    },
                )

            # Record rate limit hit
            metering.rate_limiter.record(user_id)

            # Process request
            response = await call_next(request)

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            # Log usage
            await metering.usage_logger.log(
                user_id=user_id,
                endpoint=path,
                credits=cost,
                response_time_ms=response_time,
                status_code=response.status_code,
            )

            # Add headers
            response.headers["X-Credits-Used"] = str(cost)
            response.headers["X-Credits-Remaining"] = str(info.get("remaining", 0))
            response.headers["X-RateLimit-Remaining"] = str(remaining - 1)

            return response

        async def _extract_user(self, request: Request) -> Optional[str]:
            """Extract user ID from request."""
            # Check Authorization header (JWT)
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                return await self._validate_jwt(token)

            # Check API key header
            api_key = request.headers.get("X-API-Key", "")
            if api_key:
                return await self._validate_api_key(api_key)

            # Check query param (for simple testing)
            user_id = request.query_params.get("user_id")
            if user_id and os.getenv("ALLOW_QUERY_AUTH", "false").lower() == "true":
                return user_id

            return None

        async def _validate_jwt(self, token: str) -> Optional[str]:
            """Validate JWT and extract user ID."""
            # In production, use proper JWT validation
            # import jwt
            # try:
            #     payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            #     return payload.get("sub")
            # except jwt.InvalidTokenError:
            #     return None

            # Mock validation for development
            if token.startswith("test_"):
                return token.replace("test_", "user_")
            return None

        async def _validate_api_key(self, api_key: str) -> Optional[str]:
            """Validate API key and return user ID."""
            # In production, look up API key in database
            # key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            # user = await db.api_keys.find_one({"key_hash": key_hash})
            # return user["user_id"] if user else None

            # Mock validation
            if api_key.startswith("jrvs_"):
                return f"user_{api_key[5:13]}"
            return None

    if app:
        app.add_middleware(APIMeteringMiddleware)

    return APIMeteringMiddleware


# =============================================================================
# Decorator for Function-Level Metering
# =============================================================================


def requires_credits(credits: int):
    """
    Decorator for functions that require credits.

    Usage:
        @requires_credits(10)
        async def expensive_operation(user_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id from kwargs or first arg
            user_id = kwargs.get("user_id") or (args[0] if args else None)

            if not user_id:
                raise ValueError("user_id required for credit-gated function")

            metering = MeteringMiddleware()
            success, info = await metering.check_and_deduct(
                user_id, func.__name__, credits
            )

            if not success:
                raise PermissionError(
                    f"Insufficient credits: need {credits}, "
                    f"have {info.get('available', 0)}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
