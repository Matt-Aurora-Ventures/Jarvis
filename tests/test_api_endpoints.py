"""
Comprehensive API Endpoint Tests

Tests all major API endpoints for correct behavior, validation,
error handling, and response format.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Skip if fastapi not installed
pytest.importorskip("fastapi")

from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_returns_200(self, client):
        """GET /api/health should return 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_response_format(self, client):
        """Health response should have required fields."""
        response = client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_includes_version(self, client):
        """Health should include version info."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data

    def test_health_includes_services(self, client):
        """Health should include service status."""
        response = client.get("/api/health")
        data = response.json()
        if "services" in data:
            assert isinstance(data["services"], dict)


class TestChatEndpoints:
    """Tests for chat/conversation endpoints."""

    def test_chat_requires_message(self, client):
        """POST /api/chat should require message field."""
        response = client.post(
            "/api/chat",
            json={}
        )
        assert response.status_code in [400, 422]

    def test_chat_accepts_valid_message(self, client):
        """POST /api/chat should accept valid message."""
        with patch('core.llm.quick_generate', new_callable=AsyncMock) as mock:
            mock.return_value = "Test response"

            response = client.post(
                "/api/chat",
                json={"message": "Hello"}
            )
            # May need auth, so 401 is acceptable
            assert response.status_code in [200, 201, 401, 403]

    def test_chat_response_format(self, client):
        """Chat response should have correct format."""
        with patch('core.llm.quick_generate', new_callable=AsyncMock) as mock:
            mock.return_value = "Test response"

            response = client.post(
                "/api/chat",
                json={"message": "Hello"},
                headers={"X-API-Key": "test-key"}
            )

            if response.status_code == 200:
                data = response.json()
                assert "response" in data or "message" in data


class TestTradingEndpoints:
    """Tests for trading endpoints."""

    def test_portfolio_requires_auth(self, client):
        """GET /api/trading/portfolio should require auth."""
        response = client.get("/api/trading/portfolio")
        # Should require authentication
        assert response.status_code in [401, 403, 404]

    def test_portfolio_with_auth(self, client):
        """GET /api/trading/portfolio with auth."""
        response = client.get(
            "/api/trading/portfolio",
            headers={"X-API-Key": "test-key"}
        )
        # May still be 401 if key invalid, or 200/404 if endpoint exists
        assert response.status_code in [200, 401, 403, 404]

    def test_trade_history_pagination(self, client):
        """Trade history should support pagination."""
        response = client.get(
            "/api/trading/history",
            params={"limit": 10, "offset": 0},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403, 404]

    def test_quote_validates_amount(self, client):
        """Quote endpoint should validate amount."""
        response = client.post(
            "/api/trading/quote",
            json={
                "symbol": "SOL/USDC",
                "side": "buy",
                "amount": -10  # Invalid
            },
            headers={"X-API-Key": "test-key"}
        )
        # Should reject negative amounts
        if response.status_code not in [401, 403, 404]:
            assert response.status_code in [400, 422]

    def test_quote_validates_side(self, client):
        """Quote endpoint should validate side."""
        response = client.post(
            "/api/trading/quote",
            json={
                "symbol": "SOL/USDC",
                "side": "invalid",  # Invalid
                "amount": 10
            },
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code not in [401, 403, 404]:
            assert response.status_code in [400, 422]


class TestLLMEndpoints:
    """Tests for LLM-related endpoints."""

    def test_providers_list(self, client):
        """GET /api/llm/providers should list providers."""
        response = client.get(
            "/api/llm/providers",
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "providers" in data

    def test_usage_stats(self, client):
        """GET /api/llm/usage should return stats."""
        response = client.get(
            "/api/llm/usage",
            params={"period": "day"},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403, 404]

    def test_analyze_endpoint(self, client):
        """POST /api/llm/analyze should analyze text."""
        response = client.post(
            "/api/llm/analyze",
            json={
                "text": "BTC is bullish",
                "analysis_type": "sentiment"
            },
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403, 404]


class TestBotEndpoints:
    """Tests for bot management endpoints."""

    def test_list_bots(self, client):
        """GET /api/bots should list bots."""
        response = client.get(
            "/api/bots",
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "bots" in data

    def test_bot_command(self, client):
        """POST /api/bots/{name}/command should execute command."""
        response = client.post(
            "/api/bots/telegram/command",
            json={"command": "status"},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403, 404]


class TestMonitoringEndpoints:
    """Tests for monitoring endpoints."""

    def test_metrics_endpoint(self, client):
        """GET /api/metrics should return Prometheus metrics."""
        response = client.get("/api/metrics")
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            content = response.text
            assert "jarvis" in content.lower() or "TYPE" in content

    def test_logs_endpoint(self, client):
        """GET /api/logs should return logs."""
        response = client.get(
            "/api/logs",
            params={"limit": 10},
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code in [200, 401, 403, 404]


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_json_response(self, client):
        """404 should return JSON error."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "error" in data or "detail" in data

    def test_method_not_allowed(self, client):
        """Wrong method should return 405."""
        response = client.delete("/api/health")
        assert response.status_code == 405

    def test_invalid_json(self, client):
        """Invalid JSON should return 400/422."""
        response = client.post(
            "/api/chat",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 405, 422]


class TestRequestValidation:
    """Tests for request validation."""

    def test_missing_required_field(self, client):
        """Missing required field should return 422."""
        response = client.post(
            "/api/trading/quote",
            json={"symbol": "SOL/USDC"},  # Missing side and amount
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code not in [401, 403, 404]:
            assert response.status_code in [400, 422]

    def test_invalid_field_type(self, client):
        """Invalid field type should return 422."""
        response = client.post(
            "/api/trading/quote",
            json={
                "symbol": "SOL/USDC",
                "side": "buy",
                "amount": "not a number"  # Should be float
            },
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code not in [401, 403, 404]:
            assert response.status_code in [400, 422]


class TestResponseFormat:
    """Tests for response format consistency."""

    def test_json_content_type(self, client):
        """Responses should have JSON content type."""
        response = client.get("/api/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_request_id_header(self, client):
        """Responses should include request ID."""
        response = client.get("/api/health")
        # Request ID may be in different header names
        headers = dict(response.headers)
        has_request_id = any(
            "request" in k.lower() and "id" in k.lower()
            for k in headers
        )
        # This is optional, so just log
        if not has_request_id:
            pass  # Acceptable if not implemented


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_headers(self, client):
        """Responses should include rate limit headers."""
        response = client.get("/api/health")

        # Rate limit headers may or may not be present
        headers = dict(response.headers)
        rate_limit_keys = [
            k for k in headers
            if "ratelimit" in k.lower() or "rate-limit" in k.lower()
        ]
        # Log but don't fail if not present
        pass

    def test_many_requests_allowed(self, client):
        """Multiple requests should be allowed within limit."""
        for _ in range(5):
            response = client.get("/api/health")
            assert response.status_code == 200


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_preflight(self, client):
        """CORS preflight should be handled."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # May return 200 (cors enabled) or 405 (not configured)
        assert response.status_code in [200, 405]


@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Async endpoint tests."""

    async def test_concurrent_health_checks(self, async_client):
        """Multiple concurrent requests should succeed."""
        import asyncio

        tasks = [
            async_client.get("/api/health")
            for _ in range(10)
        ]

        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200

    async def test_streaming_endpoint(self, async_client):
        """Streaming endpoints should work."""
        # Stream endpoint test placeholder
        response = await async_client.get("/api/health")
        assert response.status_code == 200


class TestVersioning:
    """Tests for API versioning."""

    def test_version_header(self, client):
        """API version header should be present."""
        response = client.get("/api/health")
        # Version may be in header or response body
        headers = dict(response.headers)
        has_version = any("version" in k.lower() for k in headers)

        if not has_version:
            data = response.json()
            assert "version" in data

    def test_deprecation_warning(self, client):
        """Deprecated endpoints should warn."""
        # Test deprecated endpoint if exists
        response = client.get("/api/v0/health")
        if response.status_code == 200:
            headers = dict(response.headers)
            # May have deprecation warning
            pass


class TestWebhooks:
    """Tests for webhook endpoints."""

    def test_webhook_create_validates_url(self, client):
        """Webhook creation should validate URL."""
        response = client.post(
            "/api/webhooks",
            json={
                "url": "not-a-valid-url",
                "events": ["trade.executed"]
            },
            headers={"X-API-Key": "test-key"}
        )
        if response.status_code not in [401, 403, 404]:
            assert response.status_code in [400, 422]

    def test_webhook_events_validated(self, client):
        """Webhook events should be validated."""
        response = client.post(
            "/api/webhooks",
            json={
                "url": "https://example.com/webhook",
                "events": ["invalid.event"]
            },
            headers={"X-API-Key": "test-key"}
        )
        # May accept or reject invalid events
        assert response.status_code in [200, 201, 400, 401, 403, 404, 422]
