"""
Middleware Pipeline - Manages and executes middleware chain.

The Pipeline class orchestrates middleware execution using the
chain of responsibility pattern. Middleware is sorted by priority
(higher priority runs first).
"""

import logging
from typing import Callable, Awaitable, List, Optional

from core.middleware.context import Context, Response, AbortError
from core.middleware.base import Middleware, NextHandler


logger = logging.getLogger(__name__)


class Pipeline:
    """
    Middleware pipeline for composable request processing.

    Manages a collection of middleware and executes them in
    priority order (highest first).

    Usage:
        pipeline = Pipeline()
        pipeline.add(LoggingMiddleware())
        pipeline.add(AuthMiddleware())
        pipeline.add(RateLimitMiddleware())

        ctx = Context(request={"method": "POST", "path": "/api/trade"})
        response = await pipeline.execute(ctx)

        # Remove middleware
        pipeline.remove("logging")
    """

    def __init__(self):
        """Initialize empty pipeline."""
        self._middlewares: List[Middleware] = []

    @property
    def middlewares(self) -> List[Middleware]:
        """Get sorted list of middlewares."""
        return self._middlewares

    def __len__(self) -> int:
        """Number of middlewares in pipeline."""
        return len(self._middlewares)

    def add(self, middleware: Middleware) -> "Pipeline":
        """
        Add middleware to the pipeline.

        Middleware is automatically sorted by priority (descending).
        Higher priority middleware runs first.

        Args:
            middleware: The middleware to add

        Returns:
            Self for chaining
        """
        self._middlewares.append(middleware)
        # Sort by priority descending (higher runs first)
        self._middlewares.sort(key=lambda m: m.priority, reverse=True)
        logger.debug(f"Added middleware: {middleware.name} (priority={middleware.priority})")
        return self

    def remove(self, name: str) -> "Pipeline":
        """
        Remove middleware by name.

        Args:
            name: Name of middleware to remove

        Returns:
            Self for chaining
        """
        self._middlewares = [m for m in self._middlewares if m.name != name]
        logger.debug(f"Removed middleware: {name}")
        return self

    def get(self, name: str) -> Optional[Middleware]:
        """
        Get middleware by name.

        Args:
            name: Name of middleware

        Returns:
            Middleware if found, None otherwise
        """
        for middleware in self._middlewares:
            if middleware.name == name:
                return middleware
        return None

    def clear(self) -> "Pipeline":
        """
        Remove all middleware.

        Returns:
            Self for chaining
        """
        self._middlewares.clear()
        return self

    async def execute(
        self,
        ctx: Context,
        handler: Optional[Callable[[Context], Awaitable[Response]]] = None,
    ) -> Response:
        """
        Execute the middleware pipeline.

        Processes the context through all middleware in priority order,
        then calls the final handler (or returns default response).

        Args:
            ctx: The context to process
            handler: Optional final handler to call after all middleware

        Returns:
            Response from the pipeline
        """
        # Build the chain from inside out
        # Start with the innermost handler (final handler or default)
        async def default_handler(ctx: Context) -> Response:
            """Default handler that returns OK response."""
            if ctx.response:
                return Response(
                    status=ctx.response.get("status", 200),
                    body=ctx.response.get("body", {}),
                )
            return Response.ok()

        final_handler = handler or default_handler

        # Build chain in reverse order (lowest priority first)
        # So when we execute, highest priority runs first
        chain = final_handler

        for middleware in reversed(self._middlewares):
            # Capture middleware in closure
            chain = self._wrap_middleware(middleware, chain)

        # Execute the chain
        try:
            return await chain(ctx)
        except AbortError as e:
            logger.debug(f"Pipeline aborted: {e.status} {e.message}")
            return Response.from_abort(e)
        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            return Response.error(500, f"Internal error: {type(e).__name__}")

    def _wrap_middleware(
        self,
        middleware: Middleware,
        next_handler: NextHandler,
    ) -> NextHandler:
        """
        Wrap middleware to create a chain link.

        Args:
            middleware: The middleware to wrap
            next_handler: The next handler in the chain

        Returns:
            A handler that calls this middleware then next
        """
        async def wrapped(ctx: Context) -> Response:
            return await middleware.process(ctx, next_handler)

        return wrapped

    def __repr__(self) -> str:
        """String representation."""
        names = [m.name for m in self._middlewares]
        return f"<Pipeline middlewares={names}>"
