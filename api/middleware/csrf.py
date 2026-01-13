"""CSRF protection middleware."""
import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request, HTTPException


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection for state-changing requests."""
    
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    
    def __init__(self, app, cookie_name: str = "csrf_token", header_name: str = "X-CSRF-Token", 
                 exempt_paths: list = None):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.exempt_paths = exempt_paths or ["/api/health", "/api/docs", "/api/openapi.json"]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            if self.cookie_name not in request.cookies:
                csrf_token = secrets.token_urlsafe(32)
                response.set_cookie(
                    self.cookie_name, 
                    csrf_token, 
                    httponly=True, 
                    samesite="strict",
                    secure=request.url.scheme == "https"
                )
            return response
        
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)
        
        if not cookie_token or not header_token:
            raise HTTPException(status_code=403, detail="CSRF token missing")
        
        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(status_code=403, detail="CSRF token mismatch")
        
        return await call_next(request)
