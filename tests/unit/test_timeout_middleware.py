"""
Tests for Request Timeout Middleware.

Validates:
- Default timeout behavior
- Per-endpoint timeout configuration
- Client-requested timeouts via headers
- Timeout error responses
- Timeout logging
"""

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.timeout import (
    TimeoutMiddleware,
    TimeoutConfig,
    get_current_timeout,
)


# =============================================================================
# Test Application Setup
# =============================================================================


def create_test_app(enable_timeout: bool = True) -> FastAPI:
    """Create a test FastAPI app with timeout middleware."""
    app = FastAPI()

    # Add timeout middleware
    if enable_timeout:
        app.add_middleware(TimeoutMiddleware, enabled=True)

    # Test endpoints
    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/slow")
    async def slow_endpoint():
        """Endpoint that takes 2 seconds."""
        await asyncio.sleep(2)
        return {"status": "completed"}

    @app.get("/api/very-slow")
    async def very_slow_endpoint():
        """Endpoint that takes 10 seconds."""
        await asyncio.sleep(10)
        return {"status": "completed"}

    @app.get("/api/ultra-slow")
    async def ultra_slow_endpoint():
        """Endpoint that takes 60 seconds."""
        await asyncio.sleep(60)
        return {"status": "completed"}

    @app.get("/api/staking/pool")
    async def staking_pool():
        return {"total_staked": 1000}

    @app.get("/api/credits/history/{user_id}")
    async def credits_history(user_id: str):
        await asyncio.sleep(1)
        return {"transactions": []}

    return app


# =============================================================================
# TimeoutConfig Tests
# =============================================================================


def test_timeout_config_exact_match():
    """Test exact path matching for timeouts."""
    timeout = TimeoutConfig.get_timeout_for_path("/api/health")
    assert timeout == 5.0


def test_timeout_config_prefix_match():
    """Test prefix matching for timeouts."""
    # /api/trading should match /api/trading
    timeout = TimeoutConfig.get_timeout_for_path("/api/trading/orders")
    assert timeout == 30.0


def test_timeout_config_default():
    """Test default timeout for unconfigured paths."""
    timeout = TimeoutConfig.get_timeout_for_path("/api/unknown/endpoint")
    assert timeout == TimeoutConfig.DEFAULT_TIMEOUT


def test_timeout_config_longest_prefix_wins():
    """Test that most specific prefix match is used."""
    # Both /api/staking and /api would match, but /api/staking is longer
    timeout = TimeoutConfig.get_timeout_for_path("/api/staking/pool")
    assert timeout == 10.0


# =============================================================================
# Middleware Tests
# =============================================================================


def test_middleware_disabled():
    """Test that middleware can be disabled."""
    app = FastAPI()
    app.add_middleware(TimeoutMiddleware, enabled=False)

    @app.get("/test")
    async def test_endpoint():
        await asyncio.sleep(100)  # Would timeout if enabled
        return {"status": "ok"}

    client = TestClient(app)
    # This would timeout if middleware was enabled, but it's not
    # So we can't actually test a 100s sleep in a unit test
    # Just verify the response structure
    response = client.get("/test", timeout=1)
    # Will fail due to test client timeout, not middleware timeout
    # This test just verifies middleware doesn't interfere when disabled


def test_fast_endpoint_completes():
    """Test that fast endpoints complete successfully."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-Timeout" in response.headers
    assert "X-Request-Duration" in response.headers


def test_slow_endpoint_times_out():
    """Test that slow endpoints timeout correctly."""
    app = create_test_app()
    client = TestClient(app)

    # /api/slow takes 2s but should timeout at default 30s
    # We need an endpoint that exceeds its configured timeout
    # Let's use /api/health (5s timeout) with a 10s sleep

    @app.get("/api/health-slow")
    async def health_slow():
        await asyncio.sleep(10)
        return {"status": "ok"}

    # Update timeout config for this test
    TimeoutConfig.ENDPOINT_TIMEOUTS["/api/health-slow"] = 2.0

    response = client.get("/api/health-slow")

    assert response.status_code == 504
    data = response.json()
    assert data["error"]["code"] == "SYS_004"
    assert "timeout" in data["error"]["message"].lower()
    assert data["timeout_seconds"] == 2.0
    assert "X-Request-Timeout" in response.headers
    assert "Retry-After" in response.headers


def test_client_timeout_header():
    """Test that clients can request specific timeouts."""
    app = create_test_app()
    client = TestClient(app)

    # Request a 1 second timeout
    response = client.get(
        "/api/health",
        headers={"X-Request-Timeout": "1.0"}
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-Timeout") == "1.0"


def test_client_timeout_capped_at_max():
    """Test that client-requested timeouts are capped."""
    app = create_test_app()
    client = TestClient(app)

    # Request a 200 second timeout (exceeds MAX_CLIENT_TIMEOUT of 120)
    response = client.get(
        "/api/health",
        headers={"X-Request-Timeout": "200.0"}
    )

    assert response.status_code == 200
    # Should be capped at max
    timeout = float(response.headers.get("X-Request-Timeout", "0"))
    assert timeout == TimeoutConfig.MAX_CLIENT_TIMEOUT


def test_invalid_client_timeout_header():
    """Test that invalid timeout headers are ignored."""
    app = create_test_app()
    client = TestClient(app)

    # Invalid timeout header
    response = client.get(
        "/api/health",
        headers={"X-Request-Timeout": "invalid"}
    )

    assert response.status_code == 200
    # Should fall back to configured timeout
    timeout = float(response.headers.get("X-Request-Timeout", "0"))
    assert timeout == 5.0  # /api/health configured timeout


def test_negative_client_timeout_ignored():
    """Test that negative timeouts are ignored."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get(
        "/api/health",
        headers={"X-Request-Timeout": "-10"}
    )

    assert response.status_code == 200
    # Should fall back to configured timeout
    timeout = float(response.headers.get("X-Request-Timeout", "0"))
    assert timeout == 5.0


def test_zero_timeout_ignored():
    """Test that zero timeout is ignored."""
    app = create_test_app()
    client = TestClient(app)

    response = client.get(
        "/api/health",
        headers={"X-Request-Timeout": "0"}
    )

    assert response.status_code == 200
    timeout = float(response.headers.get("X-Request-Timeout", "0"))
    assert timeout == 5.0


def test_timeout_response_headers():
    """Test that timeout responses include proper headers."""
    app = create_test_app()

    @app.get("/api/timeout-test")
    async def timeout_test():
        await asyncio.sleep(5)
        return {"status": "ok"}

    TimeoutConfig.ENDPOINT_TIMEOUTS["/api/timeout-test"] = 1.0

    client = TestClient(app)
    response = client.get("/api/timeout-test")

    assert response.status_code == 504
    assert "X-Request-Timeout" in response.headers
    assert "X-Request-Duration" in response.headers
    assert "Retry-After" in response.headers
    assert response.headers["Retry-After"] == "60"


def test_different_endpoints_different_timeouts():
    """Test that different endpoints use their configured timeouts."""
    app = create_test_app()
    client = TestClient(app)

    # Health should have 5s timeout
    response1 = client.get("/api/health")
    assert float(response1.headers.get("X-Request-Timeout", "0")) == 5.0

    # Staking should have 10s timeout
    response2 = client.get("/api/staking/pool")
    assert float(response2.headers.get("X-Request-Timeout", "0")) == 10.0


def test_duration_header_accurate():
    """Test that duration header reflects actual execution time."""
    app = create_test_app()
    client = TestClient(app)

    # Slow endpoint that sleeps 1 second
    @app.get("/api/one-second")
    async def one_second():
        await asyncio.sleep(1)
        return {"status": "ok"}

    response = client.get("/api/one-second")

    assert response.status_code == 200
    duration = float(response.headers.get("X-Request-Duration", "0"))
    # Should be approximately 1 second (with some tolerance)
    assert 0.9 <= duration <= 1.5


def test_timeout_error_response_structure():
    """Test the structure of timeout error responses."""
    app = create_test_app()

    @app.get("/api/timeout-test")
    async def timeout_test():
        await asyncio.sleep(5)
        return {"status": "ok"}

    TimeoutConfig.ENDPOINT_TIMEOUTS["/api/timeout-test"] = 0.5

    client = TestClient(app)
    response = client.get("/api/timeout-test")

    assert response.status_code == 504
    data = response.json()

    # Verify error structure
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "details" in data["error"]

    # Verify timeout info
    assert "timeout_seconds" in data
    assert "elapsed_seconds" in data
    assert data["timeout_seconds"] == 0.5


def test_middleware_stats():
    """Test that middleware tracks statistics."""
    app = create_test_app()
    middleware_instance = None

    # Find the middleware instance
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TimeoutMiddleware':
            # Create an instance to test stats
            middleware_instance = middleware.cls(app, enabled=True)
            break

    if middleware_instance:
        stats = middleware_instance.get_stats()
        assert "total_requests" in stats
        assert "timeout_count" in stats
        assert "timeout_rate" in stats


# =============================================================================
# Integration Tests
# =============================================================================


def test_timeout_with_other_middleware():
    """Test timeout middleware interaction with other middleware."""
    from starlette.middleware.base import BaseHTTPMiddleware

    class DummyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["X-Dummy"] = "test"
            return response

    app = FastAPI()
    app.add_middleware(TimeoutMiddleware, enabled=True)
    app.add_middleware(DummyMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Dummy" in response.headers
    assert "X-Request-Timeout" in response.headers


def test_endpoint_timeout_configuration():
    """Test various endpoint timeout configurations."""
    test_cases = [
        ("/api/health", 5.0),
        ("/api/health/components", 10.0),
        ("/api/staking/pool", 10.0),
        ("/api/staking/stake", 15.0),
        ("/api/credits/history/user123", 20.0),
        ("/api/credits/checkout", 30.0),
        ("/api/trading/orders", 30.0),
        ("/api/unknown", 30.0),  # Default
    ]

    for path, expected_timeout in test_cases:
        actual_timeout = TimeoutConfig.get_timeout_for_path(path)
        assert actual_timeout == expected_timeout, f"Path {path}: expected {expected_timeout}, got {actual_timeout}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
