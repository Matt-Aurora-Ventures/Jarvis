"""
Middleware Base Class - Abstract base for all middleware.

Implements chain of responsibility pattern where each middleware
can process the request, call the next middleware, and process the response.
"""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.middleware.context import Context, Response


# Type alias for next handler
NextHandler = Callable[["Context"], Awaitable["Response"]]


class Middleware(ABC):
    """
    Abstract base class for middleware.

    Middleware processes requests in a chain. Each middleware:
    1. Receives the context and next handler
    2. Can modify context before calling next
    3. Calls next to continue the chain
    4. Can modify response after next returns

    Attributes:
        name: Unique identifier for the middleware
        priority: Execution order (higher = runs first, default 50)

    Usage:
        class MyMiddleware(Middleware):
            name = "my_middleware"
            priority = 100  # Runs early

            async def process(self, ctx: Context, next_handler: NextHandler) -> Response:
                # Before processing
                ctx.data["my_data"] = "value"

                # Call next middleware in chain
                response = await next_handler(ctx)

                # After processing
                response.headers["X-My-Header"] = "value"

                return response
    """

    # Subclasses must define name
    name: str = ""

    # Priority for execution order (higher = runs first)
    priority: int = 50

    @abstractmethod
    async def process(self, ctx: "Context", next_handler: NextHandler) -> "Response":
        """
        Process the request.

        Args:
            ctx: The middleware context
            next_handler: Callable to invoke next middleware in chain

        Returns:
            Response from the middleware chain
        """
        pass

    def __lt__(self, other: "Middleware") -> bool:
        """Compare middleware by priority (for sorting)."""
        return self.priority < other.priority

    def __eq__(self, other: object) -> bool:
        """Check equality by name."""
        if not isinstance(other, Middleware):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        """Hash by name."""
        return hash(self.name)

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__} name={self.name!r} priority={self.priority}>"
