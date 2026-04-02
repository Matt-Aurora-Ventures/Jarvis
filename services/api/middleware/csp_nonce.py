"""CSP nonce middleware for inline script security."""
import secrets
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request


class CSPNonceMiddleware(BaseHTTPMiddleware):
    """Generate CSP nonces for inline scripts."""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        
        response = await call_next(request)
        
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: https:; "
            f"font-src 'self'; "
            f"connect-src 'self' wss: ws:; "
            f"frame-ancestors 'none'"
        )
        response.headers["Content-Security-Policy"] = csp
        
        return response


def get_csp_nonce(request: Request) -> str:
    """Get CSP nonce from request state."""
    return getattr(request.state, 'csp_nonce', '')
