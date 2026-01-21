"""
Recovery Adapters - Bot-specific adapters for the recovery engine.

Adapters wrap the recovery engine with component-specific logic,
but all core recovery decisions are delegated to the engine.

Usage:
    from core.recovery import XBotAdapter

    adapter = XBotAdapter()

    # Execute with automatic recovery
    tweet_id = await adapter.post_tweet(content)

    # Check status
    if adapter.can_post():
        await adapter.post_tweet(...)
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from .engine import get_recovery_engine, RecoveryEngine
from .config import RecoveryContext, RecoveryOutcome

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseAdapter:
    """Base adapter for recovery integration."""

    component_name: str = "base"

    def __init__(self, engine: Optional[RecoveryEngine] = None):
        self.engine = engine or get_recovery_engine()

    def can_execute(self) -> bool:
        """Check if the component can execute."""
        return self.engine.can_execute(self.component_name)

    def get_status(self) -> dict:
        """Get recovery status for this component."""
        return self.engine.get_circuit_status(self.component_name)

    async def execute(
        self,
        operation: str,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> Optional[T]:
        """Execute an operation with recovery."""
        result, context = await self.engine.execute_with_recovery(
            component=self.component_name,
            operation=operation,
            func=func,
            args=args,
            kwargs=kwargs,
        )
        return result

    def record_success(self, operation: str = "") -> None:
        """Record a successful operation."""
        self.engine.record_success(self.component_name, operation)

    def record_failure(self, operation: str = "", error: str = "") -> None:
        """Record a failed operation."""
        self.engine.record_failure(self.component_name, operation, error)


class TelegramAdapter(BaseAdapter):
    """
    Recovery adapter for Telegram bot operations.

    Handles:
    - Message sending with retry
    - API rate limit handling
    - Flood control recovery
    """

    component_name = "telegram_bot"

    async def send_message(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """Send a Telegram message with recovery."""
        return await self.execute("send_message", func, *args, **kwargs)

    async def edit_message(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """Edit a Telegram message with recovery."""
        return await self.execute("edit_message", func, *args, **kwargs)

    async def callback_query(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """Handle a callback query with recovery."""
        return await self.execute("callback_query", func, *args, **kwargs)


class XBotAdapter(BaseAdapter):
    """
    Recovery adapter for X (Twitter) bot operations.

    Handles:
    - Tweet posting with retry
    - API rate limit handling
    - Circuit breaking after failures
    """

    component_name = "x_bot"

    def can_post(self) -> bool:
        """Check if posting is currently allowed."""
        return self.can_execute()

    async def post_tweet(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[str]:
        """Post a tweet with recovery."""
        return await self.execute("post_tweet", func, *args, **kwargs)

    async def reply_tweet(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[str]:
        """Reply to a tweet with recovery."""
        return await self.execute("reply_tweet", func, *args, **kwargs)

    async def generate_image(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[bytes]:
        """Generate an image with recovery."""
        return await self.execute("generate_image", func, *args, **kwargs)

    async def fetch_mentions(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[list]:
        """Fetch mentions with recovery."""
        return await self.execute("fetch_mentions", func, *args, **kwargs)


class TradingAdapter(BaseAdapter):
    """
    Recovery adapter for trading operations.

    Handles:
    - Trade execution with retry
    - Exchange API failures
    - Always escalates on final failure
    """

    component_name = "trading"

    async def execute_trade(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[dict]:
        """Execute a trade with recovery."""
        return await self.execute("execute_trade", func, *args, **kwargs)

    async def get_price(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[float]:
        """Get a price with recovery."""
        return await self.execute("get_price", func, *args, **kwargs)

    async def get_balance(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[dict]:
        """Get balance with recovery."""
        return await self.execute("get_balance", func, *args, **kwargs)


class ToolAdapter(BaseAdapter):
    """
    Recovery adapter for tool operations.

    Handles:
    - MCP tool calls with retry
    - External API failures
    - LLM API failures
    """

    component_name = "tools"

    async def call_tool(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """Call a tool with recovery."""
        return await self.execute("call_tool", func, *args, **kwargs)

    async def llm_call(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Optional[str]:
        """Make an LLM call with recovery."""
        return await self.execute("llm_call", func, *args, **kwargs)


def with_recovery(
    component: str,
    operation: str = "",
):
    """
    Decorator for adding recovery to any async function.

    Usage:
        @with_recovery("x_bot", "post_tweet")
        async def post_tweet(content: str) -> str:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Optional[T]:
            engine = get_recovery_engine()
            result, context = await engine.execute_with_recovery(
                component=component,
                operation=operation or func.__name__,
                func=func,
                args=args,
                kwargs=kwargs,
            )
            return result
        return wrapper
    return decorator
