"""
Metrics Middleware
Automatically records performance metrics for all HTTP requests.
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records request metrics for all endpoints.

    Automatically tracks:
    - Request duration
    - Status codes
    - Error rates
    - Per-endpoint statistics
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics = get_metrics_collector()

    async def dispatch(self, request: Request, call_next):
        """
        Process request and record metrics.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Start timer
        start_time = time.time()

        # Get request details
        method = request.method
        path = request.url.path

        # Initialize variables
        status_code = 500
        error_msg = None

        try:
            # Call next middleware/handler
            response: Response = await call_next(request)
            status_code = response.status_code

            return response

        except Exception as e:
            # Record error
            error_msg = str(e)
            logger.error(f"Request error: {method} {path} - {error_msg}")
            raise

        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Record metric
            self.metrics.record_request(
                endpoint=path,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                error=error_msg
            )

            # Log slow requests (>1 second)
            if duration_ms > 1000:
                logger.warning(f"Slow request: {method} {path} took {duration_ms:.2f}ms")
