"""Rate limiting middleware for FastAPI."""
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

try:
    from core.rate_limiter import get_rate_limiter
    HAS_RATE_LIMITER = True
except ImportError:
    HAS_RATE_LIMITER = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits on API requests."""
    
    def __init__(self, app, limiter_name: str = "api_global", enabled: bool = True):
        super().__init__(app)
        self.limiter_name = limiter_name
        self.enabled = enabled and HAS_RATE_LIMITER
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        try:
            limiter = get_rate_limiter()
            allowed, wait_time = limiter.acquire(self.limiter_name, scope_key=client_ip)
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Retry after {wait_time:.1f} seconds",
                    headers={"Retry-After": str(int(wait_time) + 1)}
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Rate limiter error: {e}")
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
