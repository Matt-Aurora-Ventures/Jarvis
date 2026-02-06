"""Tests for middleware pipeline system.

TDD Phase 1: Tests written FIRST, implementation comes after.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from typing import Optional


class TestMiddlewareContext:
    """Tests for Context class."""

    def test_context_initialization(self):
        """Context should initialize with request data."""
        from core.middleware.context import Context

        ctx = Context(
            request={"method": "POST", "path": "/api/trade"},
            user={"id": "user123", "role": "admin"},
            bot="telegram",
        )

        assert ctx.request["method"] == "POST"
        assert ctx.request["path"] == "/api/trade"
        assert ctx.user["id"] == "user123"
        assert ctx.bot == "telegram"
        assert ctx.response is None
        assert isinstance(ctx.data, dict)

    def test_context_data_storage(self):
        """Context should allow middleware to store data."""
        from core.middleware.context import Context

        ctx = Context(request={})
        ctx.data["auth_verified"] = True
        ctx.data["request_id"] = "abc123"

        assert ctx.data["auth_verified"] is True
        assert ctx.data["request_id"] == "abc123"

    def test_context_abort(self):
        """Context abort should raise AbortError."""
        from core.middleware.context import Context, AbortError

        ctx = Context(request={})

        with pytest.raises(AbortError) as exc_info:
            ctx.abort(403, "Forbidden")

        assert exc_info.value.status == 403
        assert exc_info.value.message == "Forbidden"

    def test_context_abort_with_data(self):
        """Context abort should include extra data."""
        from core.middleware.context import Context, AbortError

        ctx = Context(request={})

        with pytest.raises(AbortError) as exc_info:
            ctx.abort(429, "Rate limited", {"retry_after": 60})

        assert exc_info.value.status == 429
        assert exc_info.value.data["retry_after"] == 60

    def test_context_set_response(self):
        """Context should allow setting response."""
        from core.middleware.context import Context

        ctx = Context(request={})
        ctx.response = {"status": 200, "body": {"ok": True}}

        assert ctx.response["status"] == 200
        assert ctx.response["body"]["ok"] is True


class TestMiddlewareBase:
    """Tests for Middleware abstract base class."""

    def test_middleware_must_have_name(self):
        """Middleware subclass must define name."""
        from core.middleware.base import Middleware

        with pytest.raises(TypeError):
            # Cannot instantiate abstract class
            Middleware()

    def test_middleware_implementation(self):
        """Concrete middleware must implement process method."""
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        class TestMiddleware(Middleware):
            name = "test"
            priority = 100

            async def process(self, ctx: Context, next_handler):
                ctx.data["test_ran"] = True
                return await next_handler(ctx)

        middleware = TestMiddleware()
        assert middleware.name == "test"
        assert middleware.priority == 100

    def test_middleware_default_priority(self):
        """Middleware should have default priority of 50."""
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        class TestMiddleware(Middleware):
            name = "test"

            async def process(self, ctx: Context, next_handler):
                return await next_handler(ctx)

        middleware = TestMiddleware()
        assert middleware.priority == 50

    def test_middleware_comparison_by_priority(self):
        """Middleware should be comparable by priority."""
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        class HighPriority(Middleware):
            name = "high"
            priority = 100

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        class LowPriority(Middleware):
            name = "low"
            priority = 10

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        high = HighPriority()
        low = LowPriority()

        # Higher priority should come first when sorted descending
        assert high.priority > low.priority


class TestMiddlewarePipeline:
    """Tests for Pipeline class."""

    def test_pipeline_initialization(self):
        """Pipeline should initialize empty."""
        from core.middleware.pipeline import Pipeline

        pipeline = Pipeline()
        assert len(pipeline) == 0

    def test_pipeline_add_middleware(self):
        """Pipeline should accept middleware."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        class TestMiddleware(Middleware):
            name = "test"

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        pipeline = Pipeline()
        pipeline.add(TestMiddleware())

        assert len(pipeline) == 1

    def test_pipeline_add_multiple_sorted_by_priority(self):
        """Pipeline should sort middleware by priority (high first)."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware

        class First(Middleware):
            name = "first"
            priority = 100

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        class Second(Middleware):
            name = "second"
            priority = 50

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        class Third(Middleware):
            name = "third"
            priority = 10

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        pipeline = Pipeline()
        pipeline.add(Third())  # Add in wrong order
        pipeline.add(First())
        pipeline.add(Second())

        # Should be sorted by priority descending
        names = [m.name for m in pipeline.middlewares]
        assert names == ["first", "second", "third"]

    def test_pipeline_remove_middleware(self):
        """Pipeline should remove middleware by name."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware

        class TestMiddleware(Middleware):
            name = "to_remove"

            async def process(self, ctx, next_handler):
                return await next_handler(ctx)

        pipeline = Pipeline()
        pipeline.add(TestMiddleware())
        assert len(pipeline) == 1

        pipeline.remove("to_remove")
        assert len(pipeline) == 0

    def test_pipeline_remove_nonexistent(self):
        """Removing nonexistent middleware should not raise."""
        from core.middleware.pipeline import Pipeline

        pipeline = Pipeline()
        # Should not raise
        pipeline.remove("nonexistent")

    @pytest.mark.asyncio
    async def test_pipeline_execute_single_middleware(self):
        """Pipeline should execute single middleware."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        class TestMiddleware(Middleware):
            name = "test"

            async def process(self, ctx: Context, next_handler):
                ctx.data["processed"] = True
                return await next_handler(ctx)

        pipeline = Pipeline()
        pipeline.add(TestMiddleware())

        ctx = Context(request={"path": "/test"})
        response = await pipeline.execute(ctx)

        assert ctx.data["processed"] is True
        assert response is not None

    @pytest.mark.asyncio
    async def test_pipeline_execute_chain_order(self):
        """Pipeline should execute middleware in priority order."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware
        from core.middleware.context import Context

        execution_order = []

        class First(Middleware):
            name = "first"
            priority = 100

            async def process(self, ctx: Context, next_handler):
                execution_order.append("first_before")
                result = await next_handler(ctx)
                execution_order.append("first_after")
                return result

        class Second(Middleware):
            name = "second"
            priority = 50

            async def process(self, ctx: Context, next_handler):
                execution_order.append("second_before")
                result = await next_handler(ctx)
                execution_order.append("second_after")
                return result

        pipeline = Pipeline()
        pipeline.add(Second())
        pipeline.add(First())

        ctx = Context(request={})
        await pipeline.execute(ctx)

        # Chain of responsibility: first -> second -> handler -> second -> first
        assert execution_order == [
            "first_before",
            "second_before",
            "second_after",
            "first_after",
        ]

    @pytest.mark.asyncio
    async def test_pipeline_execute_with_abort(self):
        """Pipeline should stop on abort."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.base import Middleware
        from core.middleware.context import Context, AbortError

        class AbortingMiddleware(Middleware):
            name = "aborter"
            priority = 100

            async def process(self, ctx: Context, next_handler):
                ctx.abort(403, "Not allowed")

        class NeverReached(Middleware):
            name = "never"
            priority = 50

            async def process(self, ctx: Context, next_handler):
                ctx.data["reached"] = True
                return await next_handler(ctx)

        pipeline = Pipeline()
        pipeline.add(AbortingMiddleware())
        pipeline.add(NeverReached())

        ctx = Context(request={})
        response = await pipeline.execute(ctx)

        assert "reached" not in ctx.data
        assert response.status == 403
        assert response.message == "Not allowed"

    @pytest.mark.asyncio
    async def test_pipeline_execute_empty(self):
        """Empty pipeline should return default response."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.context import Context

        pipeline = Pipeline()
        ctx = Context(request={})

        response = await pipeline.execute(ctx)

        assert response is not None
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_pipeline_execute_with_handler(self):
        """Pipeline should call final handler if provided."""
        from core.middleware.pipeline import Pipeline
        from core.middleware.context import Context, Response

        async def final_handler(ctx: Context) -> Response:
            return Response(status=201, body={"created": True})

        pipeline = Pipeline()
        ctx = Context(request={})

        response = await pipeline.execute(ctx, handler=final_handler)

        assert response.status == 201
        assert response.body["created"] is True


class TestBuiltinLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.mark.asyncio
    async def test_logging_middleware_logs_request(self, caplog):
        """LoggingMiddleware should log incoming requests."""
        from core.middleware.builtin import LoggingMiddleware
        from core.middleware.context import Context
        import logging

        caplog.set_level(logging.INFO)

        middleware = LoggingMiddleware()
        ctx = Context(request={"method": "GET", "path": "/api/health"})

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        await middleware.process(ctx, next_handler)

        assert "REQUEST" in caplog.text or "request" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logging_middleware_adds_request_id(self):
        """LoggingMiddleware should add request_id to context."""
        from core.middleware.builtin import LoggingMiddleware
        from core.middleware.context import Context

        middleware = LoggingMiddleware()
        ctx = Context(request={"method": "POST", "path": "/api/trade"})

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        await middleware.process(ctx, next_handler)

        assert "request_id" in ctx.data
        assert len(ctx.data["request_id"]) > 0


class TestBuiltinAuthMiddleware:
    """Tests for AuthMiddleware."""

    @pytest.mark.asyncio
    async def test_auth_middleware_passes_authenticated(self):
        """AuthMiddleware should pass authenticated requests."""
        from core.middleware.builtin import AuthMiddleware
        from core.middleware.context import Context

        middleware = AuthMiddleware()
        ctx = Context(
            request={"headers": {"Authorization": "Bearer valid_token"}},
            user={"id": "user123", "authenticated": True},
        )

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        response = await middleware.process(ctx, next_handler)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_auth_middleware_rejects_unauthenticated(self):
        """AuthMiddleware should reject unauthenticated requests."""
        from core.middleware.builtin import AuthMiddleware
        from core.middleware.context import Context, AbortError

        middleware = AuthMiddleware()
        ctx = Context(
            request={"headers": {}},
            user=None,
        )

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        with pytest.raises(AbortError) as exc_info:
            await middleware.process(ctx, next_handler)

        assert exc_info.value.status == 401

    @pytest.mark.asyncio
    async def test_auth_middleware_checks_permissions(self):
        """AuthMiddleware should check required permissions."""
        from core.middleware.builtin import AuthMiddleware
        from core.middleware.context import Context, AbortError

        middleware = AuthMiddleware(required_permissions=["trade:execute"])
        ctx = Context(
            request={},
            user={"id": "user123", "permissions": ["trade:read"]},
        )

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        with pytest.raises(AbortError) as exc_info:
            await middleware.process(ctx, next_handler)

        assert exc_info.value.status == 403


class TestBuiltinRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_under_limit(self):
        """RateLimitMiddleware should allow requests under limit."""
        from core.middleware.builtin import RateLimitMiddleware
        from core.middleware.context import Context

        middleware = RateLimitMiddleware(requests_per_minute=10)
        ctx = Context(request={}, user={"id": "user123"})

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        response = await middleware.process(ctx, next_handler)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_over_limit(self):
        """RateLimitMiddleware should block requests over limit."""
        from core.middleware.builtin import RateLimitMiddleware
        from core.middleware.context import Context, AbortError

        middleware = RateLimitMiddleware(requests_per_minute=2)

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        # Make requests up to limit
        for i in range(3):
            ctx = Context(request={}, user={"id": "user123"})
            try:
                await middleware.process(ctx, next_handler)
            except AbortError as e:
                # Third request should be blocked
                assert i == 2
                assert e.status == 429
                return

        pytest.fail("Should have raised AbortError on third request")

    @pytest.mark.asyncio
    async def test_rate_limit_adds_headers(self):
        """RateLimitMiddleware should add rate limit headers."""
        from core.middleware.builtin import RateLimitMiddleware
        from core.middleware.context import Context

        middleware = RateLimitMiddleware(requests_per_minute=100)
        ctx = Context(request={}, user={"id": "user123"})

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=200)

        await middleware.process(ctx, next_handler)

        assert "rate_limit" in ctx.data
        assert "remaining" in ctx.data["rate_limit"]


class TestBuiltinErrorMiddleware:
    """Tests for ErrorMiddleware."""

    @pytest.mark.asyncio
    async def test_error_middleware_catches_exceptions(self):
        """ErrorMiddleware should catch and format exceptions."""
        from core.middleware.builtin import ErrorMiddleware
        from core.middleware.context import Context

        middleware = ErrorMiddleware()
        ctx = Context(request={})

        async def failing_handler(ctx):
            raise ValueError("Something went wrong")

        response = await middleware.process(ctx, failing_handler)

        assert response.status == 500
        assert "error" in response.body

    @pytest.mark.asyncio
    async def test_error_middleware_passes_abort_through(self):
        """ErrorMiddleware should pass AbortError through."""
        from core.middleware.builtin import ErrorMiddleware
        from core.middleware.context import Context, AbortError

        middleware = ErrorMiddleware()
        ctx = Context(request={})

        async def aborting_handler(ctx):
            raise AbortError(403, "Forbidden")

        response = await middleware.process(ctx, aborting_handler)

        assert response.status == 403

    @pytest.mark.asyncio
    async def test_error_middleware_hides_details_in_production(self):
        """ErrorMiddleware should hide error details in production."""
        from core.middleware.builtin import ErrorMiddleware
        from core.middleware.context import Context

        middleware = ErrorMiddleware(debug=False)
        ctx = Context(request={})

        async def failing_handler(ctx):
            raise ValueError("Secret database error")

        response = await middleware.process(ctx, failing_handler)

        assert "Secret database error" not in str(response.body)
        assert response.status == 500


class TestBuiltinMetricsMiddleware:
    """Tests for MetricsMiddleware."""

    @pytest.mark.asyncio
    async def test_metrics_middleware_tracks_timing(self):
        """MetricsMiddleware should track request timing."""
        from core.middleware.builtin import MetricsMiddleware
        from core.middleware.context import Context
        import time

        middleware = MetricsMiddleware()
        ctx = Context(request={"path": "/api/test"})

        async def slow_handler(ctx):
            await asyncio.sleep(0.05)  # 50ms delay
            from core.middleware.context import Response
            return Response(status=200)

        await middleware.process(ctx, slow_handler)

        assert "duration_ms" in ctx.data
        assert ctx.data["duration_ms"] >= 40  # Allow some timing variance

    @pytest.mark.asyncio
    async def test_metrics_middleware_records_status(self):
        """MetricsMiddleware should record response status."""
        from core.middleware.builtin import MetricsMiddleware
        from core.middleware.context import Context

        middleware = MetricsMiddleware()
        ctx = Context(request={"path": "/api/test"})

        async def next_handler(ctx):
            from core.middleware.context import Response
            return Response(status=201)

        response = await middleware.process(ctx, next_handler)

        assert ctx.data.get("response_status") == 201

    def test_metrics_middleware_get_stats(self):
        """MetricsMiddleware should provide stats."""
        from core.middleware.builtin import MetricsMiddleware

        middleware = MetricsMiddleware()
        stats = middleware.get_stats()

        assert "total_requests" in stats
        assert "avg_duration_ms" in stats
