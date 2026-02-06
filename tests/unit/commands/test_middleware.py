"""
Unit tests for the command middleware system.

Tests the middleware infrastructure including:
- Rate limiting middleware
- Authentication middleware
- Logging middleware
- Chain of responsibility pattern
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional, Callable
import time


class TestMiddlewareBase:
    """Test base middleware functionality."""

    def test_middleware_creation(self):
        """Test creating a middleware."""
        from core.commands.middleware import Middleware

        middleware = Middleware()

        assert middleware is not None
        assert hasattr(middleware, "process")

    @pytest.mark.asyncio
    async def test_middleware_next_chain(self):
        """Test middleware calls next in chain."""
        from core.commands.middleware import Middleware

        class TestMiddleware(Middleware):
            async def process(self, ctx: Dict, next_handler: Callable) -> Any:
                ctx["processed"] = True
                return await next_handler(ctx)

        middleware = TestMiddleware()

        async def final_handler(ctx):
            return ctx

        result = await middleware.process({"data": "test"}, final_handler)

        assert result["processed"] is True
        assert result["data"] == "test"


class TestMiddlewareChain:
    """Test middleware chain of responsibility."""

    def test_chain_creation(self):
        """Test creating a middleware chain."""
        from core.commands.middleware import MiddlewareChain

        chain = MiddlewareChain()

        assert chain is not None

    def test_chain_add_middleware(self):
        """Test adding middleware to chain."""
        from core.commands.middleware import MiddlewareChain, Middleware

        chain = MiddlewareChain()

        class TestMiddleware(Middleware):
            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        chain.add(TestMiddleware())

        assert len(chain.middlewares) == 1

    @pytest.mark.asyncio
    async def test_chain_execution_order(self):
        """Test middlewares execute in order."""
        from core.commands.middleware import MiddlewareChain, Middleware

        execution_order = []

        class FirstMiddleware(Middleware):
            async def process(self, ctx, next_handler):
                execution_order.append("first_before")
                result = await next_handler(ctx)
                execution_order.append("first_after")
                return result

        class SecondMiddleware(Middleware):
            async def process(self, ctx, next_handler):
                execution_order.append("second_before")
                result = await next_handler(ctx)
                execution_order.append("second_after")
                return result

        chain = MiddlewareChain()
        chain.add(FirstMiddleware())
        chain.add(SecondMiddleware())

        async def handler(ctx):
            execution_order.append("handler")
            return "done"

        await chain.execute({}, handler)

        assert execution_order == [
            "first_before",
            "second_before",
            "handler",
            "second_after",
            "first_after"
        ]

    @pytest.mark.asyncio
    async def test_chain_can_short_circuit(self):
        """Test middleware can short-circuit the chain."""
        from core.commands.middleware import MiddlewareChain, Middleware

        class BlockingMiddleware(Middleware):
            async def process(self, ctx, next_handler):
                return {"blocked": True}  # Don't call next_handler

        class NeverReachedMiddleware(Middleware):
            async def process(self, ctx, next_handler):
                ctx["reached"] = True
                return await next_handler(ctx)

        chain = MiddlewareChain()
        chain.add(BlockingMiddleware())
        chain.add(NeverReachedMiddleware())

        async def handler(ctx):
            return ctx

        result = await chain.execute({}, handler)

        assert result == {"blocked": True}

    @pytest.mark.asyncio
    async def test_chain_empty(self):
        """Test empty chain goes directly to handler."""
        from core.commands.middleware import MiddlewareChain

        chain = MiddlewareChain()

        async def handler(ctx):
            return {"handled": True}

        result = await chain.execute({}, handler)

        assert result == {"handled": True}


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""

    def test_rate_limit_middleware_creation(self):
        """Test creating rate limit middleware."""
        from core.commands.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            max_requests=10,
            window_seconds=60
        )

        assert middleware.max_requests == 10
        assert middleware.window_seconds == 60

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        """Test rate limiter allows requests under limit."""
        from core.commands.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(max_requests=5, window_seconds=60)

        async def handler(ctx):
            return {"success": True}

        # Make 5 requests - should all succeed
        for i in range(5):
            ctx = {"user_id": "user123"}
            result = await middleware.process(ctx, handler)
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        """Test rate limiter blocks requests over limit."""
        from core.commands.middleware import RateLimitMiddleware, RateLimitExceeded

        middleware = RateLimitMiddleware(max_requests=3, window_seconds=60)

        async def handler(ctx):
            return {"success": True}

        # Make 3 requests - should succeed
        for i in range(3):
            ctx = {"user_id": "user123"}
            await middleware.process(ctx, handler)

        # 4th request should be blocked
        with pytest.raises(RateLimitExceeded):
            await middleware.process({"user_id": "user123"}, handler)

    @pytest.mark.asyncio
    async def test_rate_limit_per_user(self):
        """Test rate limit is per-user."""
        from core.commands.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(max_requests=2, window_seconds=60)

        async def handler(ctx):
            return {"success": True}

        # User 1 makes 2 requests
        for i in range(2):
            await middleware.process({"user_id": "user1"}, handler)

        # User 2 should still be able to make requests
        result = await middleware.process({"user_id": "user2"}, handler)
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_rate_limit_window_resets(self):
        """Test rate limit window resets after time."""
        from core.commands.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(max_requests=2, window_seconds=1)

        async def handler(ctx):
            return {"success": True}

        # Exhaust limit
        await middleware.process({"user_id": "user1"}, handler)
        await middleware.process({"user_id": "user1"}, handler)

        # Wait for window to reset
        await asyncio.sleep(1.1)

        # Should be able to make request again
        result = await middleware.process({"user_id": "user1"}, handler)
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_rate_limit_returns_retry_after(self):
        """Test rate limit exception includes retry-after."""
        from core.commands.middleware import RateLimitMiddleware, RateLimitExceeded

        middleware = RateLimitMiddleware(max_requests=1, window_seconds=60)

        async def handler(ctx):
            return {"success": True}

        await middleware.process({"user_id": "user1"}, handler)

        try:
            await middleware.process({"user_id": "user1"}, handler)
            assert False, "Should have raised RateLimitExceeded"
        except RateLimitExceeded as e:
            assert e.retry_after > 0
            assert e.retry_after <= 60

    @pytest.mark.asyncio
    async def test_rate_limit_key_function(self):
        """Test custom key function for rate limiting."""
        from core.commands.middleware import RateLimitMiddleware

        # Rate limit by command instead of user
        middleware = RateLimitMiddleware(
            max_requests=2,
            window_seconds=60,
            key_func=lambda ctx: ctx.get("command")
        )

        async def handler(ctx):
            return {"success": True}

        # Different users, same command
        await middleware.process({"user_id": "user1", "command": "help"}, handler)
        await middleware.process({"user_id": "user2", "command": "help"}, handler)

        # Third request to same command should be blocked
        from core.commands.middleware import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await middleware.process({"user_id": "user3", "command": "help"}, handler)


class TestAuthMiddleware:
    """Test authentication middleware."""

    def test_auth_middleware_creation(self):
        """Test creating auth middleware."""
        from core.commands.middleware import AuthMiddleware

        middleware = AuthMiddleware()

        assert middleware is not None

    @pytest.mark.asyncio
    async def test_auth_allows_authenticated(self):
        """Test auth allows authenticated users."""
        from core.commands.middleware import AuthMiddleware

        middleware = AuthMiddleware()

        async def handler(ctx):
            return {"success": True}

        ctx = {"user_id": "user123", "is_authenticated": True}
        result = await middleware.process(ctx, handler)

        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_auth_blocks_unauthenticated(self):
        """Test auth blocks unauthenticated users."""
        from core.commands.middleware import AuthMiddleware, AuthenticationRequired

        middleware = AuthMiddleware()

        async def handler(ctx):
            return {"success": True}

        ctx = {"user_id": "user123", "is_authenticated": False}

        with pytest.raises(AuthenticationRequired):
            await middleware.process(ctx, handler)

    @pytest.mark.asyncio
    async def test_auth_with_required_role(self):
        """Test auth with required role."""
        from core.commands.middleware import AuthMiddleware, InsufficientPermissions

        middleware = AuthMiddleware(required_role="admin")

        async def handler(ctx):
            return {"success": True}

        # User with correct role
        ctx = {"user_id": "admin1", "is_authenticated": True, "role": "admin"}
        result = await middleware.process(ctx, handler)
        assert result.get("success") is True

        # User with wrong role
        ctx = {"user_id": "user1", "is_authenticated": True, "role": "user"}
        with pytest.raises(InsufficientPermissions):
            await middleware.process(ctx, handler)

    @pytest.mark.asyncio
    async def test_auth_with_custom_checker(self):
        """Test auth with custom authentication checker."""
        from core.commands.middleware import AuthMiddleware

        async def custom_checker(ctx):
            # Check custom auth header
            return ctx.get("api_key") == "secret123"

        middleware = AuthMiddleware(auth_checker=custom_checker)

        async def handler(ctx):
            return {"success": True}

        # Valid API key
        ctx = {"api_key": "secret123"}
        result = await middleware.process(ctx, handler)
        assert result.get("success") is True

        # Invalid API key
        from core.commands.middleware import AuthenticationRequired
        ctx = {"api_key": "wrong"}
        with pytest.raises(AuthenticationRequired):
            await middleware.process(ctx, handler)

    @pytest.mark.asyncio
    async def test_auth_enriches_context(self):
        """Test auth middleware can enrich context with user data."""
        from core.commands.middleware import AuthMiddleware

        async def user_loader(ctx):
            if ctx.get("user_id") == "123":
                return {"name": "Test User", "premium": True}
            return None

        middleware = AuthMiddleware(user_loader=user_loader)

        async def handler(ctx):
            return ctx

        ctx = {"user_id": "123", "is_authenticated": True}
        result = await middleware.process(ctx, handler)

        assert result.get("user") is not None
        assert result["user"]["name"] == "Test User"
        assert result["user"]["premium"] is True


class TestLoggingMiddleware:
    """Test logging middleware."""

    def test_logging_middleware_creation(self):
        """Test creating logging middleware."""
        from core.commands.middleware import LoggingMiddleware

        middleware = LoggingMiddleware()

        assert middleware is not None

    @pytest.mark.asyncio
    async def test_logging_logs_request(self):
        """Test logging middleware logs requests."""
        from core.commands.middleware import LoggingMiddleware

        logs = []

        def log_func(level, message, **kwargs):
            logs.append({"level": level, "message": message, "kwargs": kwargs})

        middleware = LoggingMiddleware(logger=log_func)

        async def handler(ctx):
            return {"success": True}

        ctx = {"user_id": "user123", "command": "help"}
        await middleware.process(ctx, handler)

        assert len(logs) >= 1
        assert any("help" in str(l) for l in logs)

    @pytest.mark.asyncio
    async def test_logging_logs_duration(self):
        """Test logging middleware logs request duration."""
        from core.commands.middleware import LoggingMiddleware

        logs = []

        def log_func(level, message, **kwargs):
            logs.append({"level": level, "message": message, "kwargs": kwargs})

        middleware = LoggingMiddleware(logger=log_func)

        async def slow_handler(ctx):
            await asyncio.sleep(0.1)
            return {"success": True}

        await middleware.process({"command": "slow"}, slow_handler)

        # Should log duration
        duration_logs = [l for l in logs if "duration" in l.get("kwargs", {})]
        assert len(duration_logs) > 0
        assert duration_logs[0]["kwargs"]["duration"] >= 0.1

    @pytest.mark.asyncio
    async def test_logging_logs_errors(self):
        """Test logging middleware logs errors."""
        from core.commands.middleware import LoggingMiddleware

        logs = []

        def log_func(level, message, **kwargs):
            logs.append({"level": level, "message": message, "kwargs": kwargs})

        middleware = LoggingMiddleware(logger=log_func)

        async def error_handler(ctx):
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await middleware.process({"command": "error"}, error_handler)

        error_logs = [l for l in logs if l["level"] == "error"]
        assert len(error_logs) > 0

    @pytest.mark.asyncio
    async def test_logging_excludes_sensitive_fields(self):
        """Test logging excludes sensitive fields."""
        from core.commands.middleware import LoggingMiddleware

        logs = []

        def log_func(level, message, **kwargs):
            logs.append({"level": level, "message": message, "kwargs": kwargs})

        middleware = LoggingMiddleware(
            logger=log_func,
            sensitive_fields=["password", "api_key"]
        )

        async def handler(ctx):
            return {"success": True}

        ctx = {"user_id": "user123", "password": "secret", "api_key": "key123"}
        await middleware.process(ctx, handler)

        # Sensitive fields should be redacted
        for log in logs:
            log_str = str(log)
            assert "secret" not in log_str
            assert "key123" not in log_str

    @pytest.mark.asyncio
    async def test_logging_with_custom_formatter(self):
        """Test logging with custom log formatter."""
        from core.commands.middleware import LoggingMiddleware

        logs = []

        def log_func(level, message, **kwargs):
            logs.append(message)

        def custom_formatter(ctx, result, duration):
            return f"CMD:{ctx.get('command')} DUR:{duration:.2f}s"

        middleware = LoggingMiddleware(
            logger=log_func,
            formatter=custom_formatter
        )

        async def handler(ctx):
            return {"success": True}

        await middleware.process({"command": "test"}, handler)

        assert any("CMD:test" in log for log in logs)


class TestMiddlewareFactory:
    """Test middleware factory functions."""

    def test_rate_limit_middleware_factory(self):
        """Test rate_limit_middleware factory function."""
        from core.commands.middleware import rate_limit_middleware

        middleware = rate_limit_middleware(max_requests=10, window_seconds=60)

        assert middleware is not None
        assert middleware.max_requests == 10

    def test_auth_middleware_factory(self):
        """Test auth_middleware factory function."""
        from core.commands.middleware import auth_middleware

        middleware = auth_middleware(required_role="admin")

        assert middleware is not None

    def test_logging_middleware_factory(self):
        """Test logging_middleware factory function."""
        from core.commands.middleware import logging_middleware

        middleware = logging_middleware()

        assert middleware is not None


class TestMiddlewareIntegration:
    """Integration tests for middleware system."""

    @pytest.mark.asyncio
    async def test_full_middleware_chain(self):
        """Test complete middleware chain with all middleware types."""
        from core.commands.middleware import (
            MiddlewareChain,
            RateLimitMiddleware,
            AuthMiddleware,
            LoggingMiddleware
        )

        logs = []

        def log_func(level, message, **kwargs):
            logs.append({"level": level, "message": message})

        chain = MiddlewareChain()
        chain.add(LoggingMiddleware(logger=log_func))
        chain.add(AuthMiddleware())
        chain.add(RateLimitMiddleware(max_requests=10, window_seconds=60))

        async def handler(ctx):
            return {"result": "success", "user": ctx.get("user_id")}

        ctx = {
            "user_id": "user123",
            "is_authenticated": True,
            "command": "test"
        }

        result = await chain.execute(ctx, handler)

        assert result["result"] == "success"
        assert len(logs) > 0

    @pytest.mark.asyncio
    async def test_middleware_chain_with_router(self):
        """Test middleware chain integrated with router."""
        from core.commands.middleware import MiddlewareChain, LoggingMiddleware
        from core.commands.router import CommandRouter

        router = CommandRouter()

        async def help_handler(ctx):
            return "Help text"

        router.register("help", help_handler)

        chain = MiddlewareChain()
        chain.add(LoggingMiddleware())

        # Route and execute with middleware
        route_result = router.route("/help")
        assert route_result is not None

        ctx = {"command": "help", "user_id": "user123"}
        result = await chain.execute(ctx, route_result.handler)

        assert result == "Help text"
