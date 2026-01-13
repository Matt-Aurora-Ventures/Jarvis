"""Request tracing middleware for distributed tracing."""
import uuid
import time
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str] = ContextVar('request_id', default='')
request_start_time: ContextVar[float] = ContextVar('request_start_time', default=0.0)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Add request ID tracing to all requests."""
    
    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())[:8]
        request_id_var.set(request_id)
        request_start_time.set(time.time())
        
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
        except Exception as e:
            duration = time.time() - request_start_time.get()
            logger.error(f"[{request_id}] {request.method} {request.url.path} failed after {duration:.3f}s: {e}")
            raise
        
        duration = time.time() - request_start_time.get()
        response.headers[self.header_name] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        logger.info(f"[{request_id}] {request.method} {request.url.path} {response.status_code} {duration:.3f}s")
        
        return response


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_var.get()
