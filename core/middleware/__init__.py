"""
Middleware Pipeline System.

Composable request processing with chain of responsibility pattern.

Usage:
    from core.middleware import Pipeline, Context
    from core.middleware.builtin import LoggingMiddleware, AuthMiddleware

    pipeline = Pipeline()
    pipeline.add(LoggingMiddleware())
    pipeline.add(AuthMiddleware())

    ctx = Context(request={"method": "POST", "path": "/api/trade"})
    response = await pipeline.execute(ctx)
"""

from core.middleware.context import Context, Response, AbortError
from core.middleware.base import Middleware
from core.middleware.pipeline import Pipeline

__all__ = [
    "Context",
    "Response",
    "AbortError",
    "Middleware",
    "Pipeline",
]
