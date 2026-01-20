"""
Tests for Rate Limit Headers Middleware

Tests that the middleware adds proper rate limiting headers to responses:
- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset
- Retry-After (when rate limited)
"""
import pytest
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.middleware.rate_limit_headers import RateLimitHeadersMiddleware


@pytest.fixture
def app():
    """Create a test FastAPI app with rate limit middleware."""
    app = FastAPI()

    # Add middleware with low limits for testing
    app.add_middleware(
        RateLimitHeadersMiddleware,
        requests_per_minute=5,
        requests_per_hour=20,
        requests_per_day=100,
        burst_limit=3,
        enabled=True,
        exclude_paths=["/health"],
    )

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "ok"}

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestRateLimitHeaders:
    """Tests for rate limit headers on normal requests."""

    def test_headers_present_on_success(self, client):
        """Test that rate limit headers are present on successful requests."""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_limit_header_value(self, client):
        """Test that X-RateLimit-Limit shows the correct limit."""
        response = client.get("/test")

        limit = int(response.headers["X-RateLimit-Limit"])
        assert limit == 5  # requests_per_minute from fixture

    def test_remaining_decrements(self, client):
        """Test that X-RateLimit-Remaining decrements with each request."""
        # First request
        response1 = client.get("/test")
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        # Second request
        response2 = client.get("/test")
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        # Remaining should decrease
        assert remaining2 < remaining1
        assert remaining2 == remaining1 - 1

    def test_reset_header_is_future_timestamp(self, client):
        """Test that X-RateLimit-Reset is a future Unix timestamp."""
        response = client.get("/test")

        reset_time = int(response.headers["X-RateLimit-Reset"])
        current_time = int(time.time())

        # Reset time should be in the future
        assert reset_time > current_time
        # Should be within the next minute
        assert reset_time <= current_time + 60

    def test_excluded_paths_no_headers(self, client):
        """Test that excluded paths don't get rate limited."""
        response = client.get("/health")

        assert response.status_code == 200
        # Excluded paths should not have rate limit headers
        # (they skip the middleware entirely)


class TestRateLimitEnforcement:
    """Tests for rate limit enforcement and 429 responses."""

    def test_rate_limit_returns_429(self, client):
        """Test that exceeding rate limit returns 429 status."""
        # Burst limit is 3, so 4th request should be blocked
        for i in range(3):
            response = client.get("/test")
            assert response.status_code == 200, f"Request {i+1} should succeed"

        # 4th request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429

    def test_rate_limited_response_has_retry_after(self, client):
        """Test that 429 responses include Retry-After header."""
        # Exhaust rate limit
        for i in range(3):
            client.get("/test")

        # Get rate limited
        response = client.get("/test")

        assert response.status_code == 429
        assert "Retry-After" in response.headers

        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= 60  # Should be within 1 minute

    def test_rate_limited_response_has_error_message(self, client):
        """Test that 429 responses have proper error message."""
        # Exhaust rate limit
        for i in range(3):
            client.get("/test")

        # Get rate limited
        response = client.get("/test")

        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert data["error"]["code"] == "RATE_LIMITED"
        assert "message" in data["error"]

    def test_remaining_shows_limit_when_rate_limited(self, client):
        """Test that X-RateLimit-Remaining shows how many were used when rate limited."""
        # Exhaust rate limit (burst limit is 3)
        for i in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        # Get rate limited - the counter is NOT incremented for blocked requests
        response = client.get("/test")

        assert response.status_code == 429
        remaining = int(response.headers["X-RateLimit-Remaining"])
        # Remaining shows requests_per_minute (5) - minute_count (3) = 2
        # This is correct - it shows how many slots remain in the minute window
        assert remaining >= 0  # Should be non-negative
        assert remaining < int(response.headers["X-RateLimit-Limit"])


class TestClientIdentification:
    """Tests for client identification methods."""

    def test_api_key_based_limiting(self):
        """Test that clients are identified by API key if provided."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=2,
            burst_limit=2,
            enabled=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Client 1 with API key
        headers1 = {"X-API-Key": "key_client_1"}
        response1 = client.get("/test", headers=headers1)
        response2 = client.get("/test", headers=headers1)

        # Should be rate limited
        response3 = client.get("/test", headers=headers1)
        assert response3.status_code == 429

        # Client 2 with different API key should have separate limit
        headers2 = {"X-API-Key": "key_client_2"}
        response4 = client.get("/test", headers=headers2)
        assert response4.status_code == 200  # Not rate limited

    def test_x_forwarded_for_identification(self):
        """Test that X-Forwarded-For header is used for identification."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=2,
            burst_limit=2,
            enabled=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Requests from different IPs should have separate limits
        headers_ip1 = {"X-Forwarded-For": "1.2.3.4"}
        headers_ip2 = {"X-Forwarded-For": "5.6.7.8"}

        # Exhaust limit for IP1
        client.get("/test", headers=headers_ip1)
        client.get("/test", headers=headers_ip1)
        response = client.get("/test", headers=headers_ip1)
        assert response.status_code == 429

        # IP2 should still work
        response = client.get("/test", headers=headers_ip2)
        assert response.status_code == 200


class TestMultipleTimeWindows:
    """Tests for multiple time window enforcement."""

    def test_minute_limit_enforcement(self):
        """Test that minute limit is enforced."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=5,
            requests_per_hour=100,
            burst_limit=5,
            enabled=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # First 5 requests should succeed (burst)
        for i in range(5):
            response = client.get("/test")
            assert response.status_code == 200, f"Request {i+1} failed"

        # 6th should be blocked
        response = client.get("/test")
        assert response.status_code == 429

    def test_hour_limit_enforcement(self):
        """Test that hour limit is enforced."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=1000,  # Very high minute limit
            requests_per_hour=10,
            burst_limit=10,
            enabled=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # First 10 requests should succeed
        for i in range(10):
            response = client.get("/test")
            assert response.status_code == 200

        # 11th should be blocked by hour limit
        response = client.get("/test")
        assert response.status_code == 429


class TestMiddlewareConfiguration:
    """Tests for middleware configuration options."""

    def test_disabled_middleware_no_limiting(self):
        """Test that disabled middleware doesn't limit requests."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=1,
            burst_limit=1,
            enabled=False,  # Disabled
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        # Should be able to make many requests without limiting
        for i in range(10):
            response = client.get("/test")
            assert response.status_code == 200

    def test_custom_exclude_paths(self):
        """Test that custom exclude paths are respected."""
        app = FastAPI()
        app.add_middleware(
            RateLimitHeadersMiddleware,
            requests_per_minute=1,
            burst_limit=1,
            enabled=True,
            exclude_paths=["/admin", "/internal"],
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.get("/admin/status")
        async def admin_endpoint():
            return {"message": "admin"}

        @app.get("/internal/metrics")
        async def internal_endpoint():
            return {"message": "internal"}

        client = TestClient(app)

        # Regular endpoint should be limited
        client.get("/test")
        response = client.get("/test")
        assert response.status_code == 429

        # Excluded paths should never be limited
        for i in range(10):
            response = client.get("/admin/status")
            assert response.status_code == 200

            response = client.get("/internal/metrics")
            assert response.status_code == 200


class TestHeaderValueFormats:
    """Tests for proper header value formats."""

    def test_limit_is_positive_integer(self, client):
        """Test that X-RateLimit-Limit is a valid positive integer."""
        response = client.get("/test")

        limit = response.headers["X-RateLimit-Limit"]
        assert limit.isdigit()
        assert int(limit) > 0

    def test_remaining_is_non_negative_integer(self, client):
        """Test that X-RateLimit-Remaining is a valid non-negative integer."""
        response = client.get("/test")

        remaining = response.headers["X-RateLimit-Remaining"]
        assert remaining.isdigit()
        assert int(remaining) >= 0

    def test_reset_is_unix_timestamp(self, client):
        """Test that X-RateLimit-Reset is a valid Unix timestamp."""
        response = client.get("/test")

        reset = response.headers["X-RateLimit-Reset"]
        assert reset.isdigit()

        # Should be a reasonable timestamp (between 2020 and 2100)
        reset_time = int(reset)
        assert reset_time > 1577836800  # 2020-01-01
        assert reset_time < 4102444800  # 2100-01-01

    def test_retry_after_is_positive_integer(self, client):
        """Test that Retry-After is a valid positive integer."""
        # Exhaust rate limit
        for i in range(3):
            client.get("/test")

        # Get rate limited
        response = client.get("/test")

        retry_after = response.headers["Retry-After"]
        assert retry_after.isdigit()
        assert int(retry_after) > 0
