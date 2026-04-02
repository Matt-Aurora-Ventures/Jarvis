"""Idempotency key middleware for safe retries."""
import time
import json
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from fastapi import Request
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    status_code: int
    body: bytes
    headers: Dict[str, str]
    timestamp: float


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Handle idempotency keys for safe request retries."""
    
    def __init__(self, app, header_name: str = "Idempotency-Key", ttl_seconds: int = 86400):
        super().__init__(app)
        self.header_name = header_name
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CachedResponse] = {}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)
        
        idempotency_key = request.headers.get(self.header_name)
        if not idempotency_key:
            return await call_next(request)
        
        cache_key = self._make_cache_key(idempotency_key, request)
        
        self._cleanup_expired()
        
        cached = self._cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return Response(
                content=cached.body,
                status_code=cached.status_code,
                headers=cached.headers
            )
        
        response = await call_next(request)
        
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            self._cache[cache_key] = CachedResponse(
                status_code=response.status_code,
                body=body,
                headers=dict(response.headers),
                timestamp=time.time()
            )
            
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        
        return response
    
    def _make_cache_key(self, idempotency_key: str, request: Request) -> str:
        return hashlib.sha256(f"{idempotency_key}:{request.url.path}".encode()).hexdigest()
    
    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v.timestamp > self.ttl_seconds]
        for k in expired:
            del self._cache[k]
