"""
Tests for per-user rate limiting functionality.

Tests:
- User-based rate limiting (separate limits per user)
- User tier-based limits (free, premium, enterprise)
- Admin override capability
- Internal service bypass
- Fallback to IP-based limiting
"""

import asyncio
import time
from typing import Dict

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from api.middleware.rate_limit_headers import (
    RateLimiter,
    RateLimitConfig,
    UserTierConfig,
    RateLimitHeadersMiddleware,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def rate_limiter():
    """Create a basic rate limiter."""
    config = RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000,
        burst_limit=5,
    )
    return RateLimiter(config)


@pytest.fixture
def tiered_rate_limiter():
    """Create a rate limiter with user tiers."""
    config = RateLimitConfig(
        requests_per_minute=10,  # Free tier
        requests_per_hour=100,
        requests_per_day=1000,
        burst_limit=5,
    )

    tiers = {
        "free": UserTierConfig(
            tier_name="free",
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1000,
            burst_limit=5,
        ),
        "premium": UserTierConfig(
            tier_name="premium",
            requests_per_minute=100,
            requests_per_hour=1000,
            requests_per_day=10000,
            burst_limit=50,
        ),
        "enterprise": UserTierConfig(
            tier_name="enterprise",
            requests_per_minute=1000,
            requests_per_hour=10000,
            requests_per_day=100000,
            burst_limit=500,
        ),
    }

    return RateLimiter(config, user_tiers=tiers)


@pytest.fixture
def app_with_user_rate_limiting():
    """Create test app with user-based rate limiting."""

    async def test_endpoint(request: Request):
        return JSONResponse({"success": True})

    app = Starlette(
        routes=[
            Route("/test", test_endpoint),
            Route("/health", test_endpoint),
        ]
    )

    # Add rate limiting middleware
    tiers = {
        "free": UserTierConfig(
            tier_name="free",
            requests_per_minute=5,
            burst_limit=3,
        ),
        "premium": UserTierConfig(
            tier_name="premium",
            requests_per_minute=50,
            burst_limit=30,
        ),
    }

    app.add_middleware(
        RateLimitHeadersMiddleware,
        requests_per_minute=10,
        burst_limit=5,
        user_tiers=tiers,
        exclude_paths=["/health"],
    )

    return app


# =============================================================================
# TESTS: PER-USER RATE LIMITING
# =============================================================================


@pytest.mark.asyncio
async def test_per_user_rate_limiting(rate_limiter):
    """Test that different users have separate rate limits."""
    user1 = "user123"
    user2 = "user456"
    client_id = "ip:192.168.1.1"

    # User 1 makes requests (burst limit = 5)
    for i in range(5):
        allowed, headers = await rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user1,
        )
        assert allowed, f"User1 request {i+1} should be allowed"

    # User 2 should still have full quota (different user)
    for i in range(5):
        allowed, headers = await rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user2,
        )
        assert allowed, f"User2 request {i+1} should be allowed"

    # User 1 exceeds burst limit (5 requests already made)
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user1,
    )
    assert not allowed, "User1 should be rate limited after 5 requests"
    assert "Retry-After" in headers

    # User 2 exceeds burst limit (5 requests already made)
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user2,
    )
    assert not allowed, "User2 should be rate limited after 5 requests"


@pytest.mark.asyncio
async def test_user_tracking_id_format(rate_limiter):
    """Test that user IDs are tracked with 'user:' prefix."""
    user_id = "test_user"
    client_id = "ip:192.168.1.1"

    # Make request as user
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user_id,
    )
    assert allowed

    # Check stats use correct tracking ID
    stats = rate_limiter.get_client_stats(client_id=client_id, user_id=user_id)
    assert stats["minute_count"] == 1

    # IP stats should be empty (not tracked separately when user_id provided)
    ip_stats = rate_limiter.get_client_stats(client_id=client_id)
    assert ip_stats.get("minute_count", 0) == 0


@pytest.mark.asyncio
async def test_fallback_to_ip_when_no_user_id(rate_limiter):
    """Test that system falls back to IP-based limiting when no user_id."""
    client_id = "ip:192.168.1.1"

    # Make requests without user_id (should use IP)
    for _ in range(5):
        allowed, headers = await rate_limiter.check_rate_limit(client_id=client_id)
        assert allowed

    # Exceed burst limit
    allowed, headers = await rate_limiter.check_rate_limit(client_id=client_id)
    assert not allowed


# =============================================================================
# TESTS: USER TIER-BASED LIMITS
# =============================================================================


@pytest.mark.asyncio
async def test_user_tier_free(tiered_rate_limiter):
    """Test free tier has lower limits."""
    user_id = "free_user"
    client_id = "ip:192.168.1.1"

    # Free tier: 10 requests/minute, burst 5
    for i in range(5):
        allowed, headers = await tiered_rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id,
            user_tier="free",
        )
        assert allowed, f"Request {i+1} should be allowed"
        assert headers["X-RateLimit-Tier"] == "free"

    # 6th request should be blocked (burst limit = 5)
    allowed, headers = await tiered_rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user_id,
        user_tier="free",
    )
    assert not allowed


@pytest.mark.asyncio
async def test_user_tier_premium(tiered_rate_limiter):
    """Test premium tier has higher limits."""
    user_id = "premium_user"
    client_id = "ip:192.168.1.1"

    # Premium tier: 100 requests/minute, burst 50
    for i in range(50):
        allowed, headers = await tiered_rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id,
            user_tier="premium",
        )
        assert allowed, f"Request {i+1} should be allowed"
        assert headers["X-RateLimit-Tier"] == "premium"

    # 51st request should be blocked (burst limit = 50)
    allowed, headers = await tiered_rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user_id,
        user_tier="premium",
    )
    assert not allowed


@pytest.mark.asyncio
async def test_user_tier_enterprise(tiered_rate_limiter):
    """Test enterprise tier has very high limits."""
    user_id = "enterprise_user"
    client_id = "ip:192.168.1.1"

    # Enterprise tier: 1000 requests/minute, burst 500
    for i in range(100):
        allowed, headers = await tiered_rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id,
            user_tier="enterprise",
        )
        assert allowed, f"Request {i+1} should be allowed"
        assert headers["X-RateLimit-Tier"] == "enterprise"


@pytest.mark.asyncio
async def test_tier_not_configured_uses_default(tiered_rate_limiter):
    """Test that unconfigured tier uses default config."""
    user_id = "unknown_tier_user"
    client_id = "ip:192.168.1.1"

    # Unknown tier should use default (10/min, burst 5)
    for i in range(5):
        allowed, headers = await tiered_rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id,
            user_tier="super_secret_tier",
        )
        assert allowed

    # 6th request blocked
    allowed, headers = await tiered_rate_limiter.check_rate_limit(
        client_id=client_id,
        user_id=user_id,
        user_tier="super_secret_tier",
    )
    assert not allowed


@pytest.mark.asyncio
async def test_add_user_tier_dynamically(rate_limiter):
    """Test adding user tiers dynamically."""
    # Add custom tier
    custom_tier = UserTierConfig(
        tier_name="custom",
        requests_per_minute=25,
        burst_limit=15,
    )
    rate_limiter.add_user_tier("custom", custom_tier)

    # Use custom tier
    for i in range(15):
        allowed, headers = await rate_limiter.check_rate_limit(
            client_id="ip:1.1.1.1",
            user_id="custom_user",
            user_tier="custom",
        )
        assert allowed

    # 16th blocked
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id="ip:1.1.1.1",
        user_id="custom_user",
        user_tier="custom",
    )
    assert not allowed


# =============================================================================
# TESTS: ADMIN OVERRIDE
# =============================================================================


@pytest.mark.asyncio
async def test_admin_user_bypass(rate_limiter):
    """Test that admin users bypass rate limits."""
    admin_user = "admin123"
    rate_limiter.add_admin_user(admin_user)

    # Admin can make unlimited requests
    for _ in range(1000):
        allowed, headers = await rate_limiter.check_rate_limit(
            client_id="ip:192.168.1.1",
            user_id=admin_user,
        )
        assert allowed
        assert headers.get("X-RateLimit-Admin") == "true"


@pytest.mark.asyncio
async def test_remove_admin_user(rate_limiter):
    """Test removing admin status."""
    user_id = "temp_admin"

    # Add as admin
    rate_limiter.add_admin_user(user_id)
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id="ip:1.1.1.1",
        user_id=user_id,
    )
    assert headers.get("X-RateLimit-Admin") == "true"

    # Remove admin status
    rate_limiter.remove_admin_user(user_id)

    # Now subject to normal limits
    for _ in range(5):
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id="ip:1.1.1.1",
            user_id=user_id,
        )
        assert allowed

    # Exceeds burst limit
    allowed, headers = await rate_limiter.check_rate_limit(
        client_id="ip:1.1.1.1",
        user_id=user_id,
    )
    assert not allowed
    assert "X-RateLimit-Admin" not in headers


# =============================================================================
# TESTS: INTERNAL SERVICE BYPASS
# =============================================================================


@pytest.mark.asyncio
async def test_internal_service_bypass(rate_limiter):
    """Test that internal services bypass rate limits."""
    service_id = "internal_service_123"
    rate_limiter.add_internal_service(service_id)

    # Internal service can make unlimited requests
    for _ in range(1000):
        allowed, headers = await rate_limiter.check_rate_limit(
            client_id=service_id,
        )
        assert allowed
        assert headers.get("X-RateLimit-Internal") == "true"


@pytest.mark.asyncio
async def test_remove_internal_service(rate_limiter):
    """Test removing internal service status."""
    service_id = "temp_service"

    # Add as internal
    rate_limiter.add_internal_service(service_id)
    allowed, headers = await rate_limiter.check_rate_limit(client_id=service_id)
    assert headers.get("X-RateLimit-Internal") == "true"

    # Remove internal status
    rate_limiter.remove_internal_service(service_id)

    # Now subject to normal limits
    for _ in range(5):
        allowed, _ = await rate_limiter.check_rate_limit(client_id=service_id)
        assert allowed

    # Exceeds burst limit
    allowed, headers = await rate_limiter.check_rate_limit(client_id=service_id)
    assert not allowed
    assert "X-RateLimit-Internal" not in headers


# =============================================================================
# TESTS: MIDDLEWARE INTEGRATION
# =============================================================================


def test_middleware_user_id_from_header(app_with_user_rate_limiting):
    """Test middleware extracts user ID from header."""
    client = TestClient(app_with_user_rate_limiting)

    # Make requests with user ID header (no tier = uses default 10/min)
    for i in range(3):
        response = client.get("/test", headers={"X-User-ID": "user123"})
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        assert remaining == 10 - (i + 1)  # Default tier = 10/min


def test_middleware_user_tier_from_header(app_with_user_rate_limiting):
    """Test middleware applies tier-based limits."""
    client = TestClient(app_with_user_rate_limiting)

    # Free tier user (5 requests/min)
    for i in range(3):
        response = client.get(
            "/test",
            headers={"X-User-ID": "free_user", "X-User-Tier": "free"}
        )
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Tier") == "free"

    # Premium tier user (50 requests/min)
    for i in range(10):
        response = client.get(
            "/test",
            headers={"X-User-ID": "premium_user", "X-User-Tier": "premium"}
        )
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-Tier") == "premium"


def test_middleware_rate_limit_response_includes_user_info(app_with_user_rate_limiting):
    """Test that 429 response includes user info."""
    client = TestClient(app_with_user_rate_limiting)

    # Exceed free tier burst limit (3)
    headers = {"X-User-ID": "rate_limited_user", "X-User-Tier": "free"}

    for _ in range(3):
        response = client.get("/test", headers=headers)
        assert response.status_code == 200

    # 4th request should be rate limited
    response = client.get("/test", headers=headers)
    assert response.status_code == 429

    data = response.json()
    assert data["error"]["code"] == "RATE_LIMITED"
    assert data["error"]["user_id"] == "rate_limited_user"
    assert data["error"]["tier"] == "free"
    assert "Retry-After" in response.headers


def test_middleware_different_users_separate_limits(app_with_user_rate_limiting):
    """Test that different users have separate rate limits in middleware."""
    client = TestClient(app_with_user_rate_limiting)

    # User 1 uses quota
    for _ in range(3):
        response = client.get("/test", headers={"X-User-ID": "user1"})
        assert response.status_code == 200

    # User 2 should have full quota
    for _ in range(3):
        response = client.get("/test", headers={"X-User-ID": "user2"})
        assert response.status_code == 200


def test_middleware_excluded_paths_not_rate_limited(app_with_user_rate_limiting):
    """Test that excluded paths bypass rate limiting."""
    client = TestClient(app_with_user_rate_limiting)

    # Health endpoint should not be rate limited
    for _ in range(100):
        response = client.get("/health")
        assert response.status_code == 200
        # No rate limit headers on excluded paths
        assert "X-RateLimit-Limit" not in response.headers


# =============================================================================
# TESTS: RESET FUNCTIONALITY
# =============================================================================


@pytest.mark.asyncio
async def test_reset_user_rate_limit(rate_limiter):
    """Test resetting rate limit for a specific user."""
    user_id = "user123"
    client_id = "ip:192.168.1.1"

    # Use up quota
    for _ in range(5):
        await rate_limiter.check_rate_limit(client_id=client_id, user_id=user_id)

    # Should be rate limited
    allowed, _ = await rate_limiter.check_rate_limit(client_id=client_id, user_id=user_id)
    assert not allowed

    # Reset user
    rate_limiter.reset_client(client_id=client_id, user_id=user_id)

    # Can make requests again
    allowed, _ = await rate_limiter.check_rate_limit(client_id=client_id, user_id=user_id)
    assert allowed


@pytest.mark.asyncio
async def test_reset_ip_rate_limit(rate_limiter):
    """Test resetting rate limit for an IP."""
    client_id = "ip:192.168.1.1"

    # Use up quota
    for _ in range(5):
        await rate_limiter.check_rate_limit(client_id=client_id)

    # Should be rate limited
    allowed, _ = await rate_limiter.check_rate_limit(client_id=client_id)
    assert not allowed

    # Reset IP
    rate_limiter.reset_client(client_id=client_id)

    # Can make requests again
    allowed, _ = await rate_limiter.check_rate_limit(client_id=client_id)
    assert allowed


# =============================================================================
# TESTS: EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_same_user_different_ips(rate_limiter):
    """Test that same user from different IPs shares quota."""
    user_id = "mobile_user"

    # Request from IP 1
    for _ in range(3):
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id="ip:192.168.1.1",
            user_id=user_id,
        )
        assert allowed

    # Request from IP 2 (same user)
    for _ in range(2):
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id="ip:10.0.0.1",
            user_id=user_id,
        )
        assert allowed

    # 6th request blocked (burst limit = 5, user has 5 total)
    allowed, _ = await rate_limiter.check_rate_limit(
        client_id="ip:10.0.0.1",
        user_id=user_id,
    )
    assert not allowed


@pytest.mark.asyncio
async def test_empty_user_id_uses_ip(rate_limiter):
    """Test that empty string user_id falls back to IP."""
    client_id = "ip:192.168.1.1"

    # Empty user_id should use IP tracking
    for _ in range(5):
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id="",
        )
        assert allowed

    # Should be tracked by IP
    stats = rate_limiter.get_client_stats(client_id=client_id)
    assert stats["minute_count"] == 5


@pytest.mark.asyncio
async def test_none_user_id_uses_ip(rate_limiter):
    """Test that None user_id falls back to IP."""
    client_id = "ip:192.168.1.1"

    # None user_id should use IP tracking
    for _ in range(5):
        allowed, _ = await rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=None,
        )
        assert allowed

    # Should be tracked by IP
    stats = rate_limiter.get_client_stats(client_id=client_id)
    assert stats["minute_count"] == 5
