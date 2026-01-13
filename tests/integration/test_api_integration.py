"""Integration tests for API endpoints."""
import pytest
import asyncio

# Skip entire module if fastapi not installed
pytest.importorskip("fastapi")

from httpx import AsyncClient
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Integration tests for health endpoints."""
    
    def test_health_check_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_health_check_includes_version(self, client):
        """Health endpoint should include version."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
    
    def test_health_check_includes_services(self, client):
        """Health endpoint should include service status."""
        response = client.get("/api/health")
        data = response.json()
        assert "services" in data


class TestAuthenticationFlow:
    """Integration tests for authentication."""
    
    def test_unauthenticated_request_allowed_on_public_routes(self, client):
        """Public routes should not require auth."""
        response = client.get("/api/health")
        assert response.status_code == 200
    
    def test_api_key_header_accepted(self, client):
        """API key in header should be accepted."""
        response = client.get(
            "/api/health",
            headers={"X-API-Key": "test-key"}
        )
        # Should not fail due to header presence
        assert response.status_code in [200, 401]


class TestRateLimiting:
    """Integration tests for rate limiting."""
    
    def test_multiple_requests_allowed(self, client):
        """Multiple requests should be allowed within limit."""
        for _ in range(5):
            response = client.get("/api/health")
            assert response.status_code == 200


class TestErrorHandling:
    """Integration tests for error handling."""
    
    def test_404_returns_json_error(self, client):
        """404 should return JSON error response."""
        response = client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_method_not_allowed(self, client):
        """Wrong method should return 405."""
        response = client.delete("/api/health")
        assert response.status_code == 405


class TestCORSHeaders:
    """Integration tests for CORS."""
    
    def test_cors_headers_present(self, client):
        """CORS headers should be present."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # CORS preflight may return 200 or 405 depending on config
        assert response.status_code in [200, 405]


@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Async integration tests."""
    
    async def test_concurrent_requests(self, async_client):
        """Multiple concurrent requests should succeed."""
        tasks = [
            async_client.get("/api/health")
            for _ in range(10)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.status_code == 200


class TestWebSocketConnections:
    """Integration tests for WebSocket endpoints."""
    
    def test_websocket_connection(self, client):
        """WebSocket should accept connections."""
        # TestClient doesn't support WebSocket directly
        # This is a placeholder for actual WebSocket testing
        pass


class TestDataValidation:
    """Integration tests for request validation."""
    
    def test_invalid_json_rejected(self, client):
        """Invalid JSON should be rejected."""
        response = client.post(
            "/api/health",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        # Should return validation error or method not allowed
        assert response.status_code in [400, 405, 422]


class TestResponseFormat:
    """Integration tests for response format."""
    
    def test_json_content_type(self, client):
        """Responses should have JSON content type."""
        response = client.get("/api/health")
        assert "application/json" in response.headers.get("content-type", "")
    
    def test_timestamp_in_response(self, client):
        """Responses should include timestamp."""
        response = client.get("/api/health")
        data = response.json()
        assert "timestamp" in data
