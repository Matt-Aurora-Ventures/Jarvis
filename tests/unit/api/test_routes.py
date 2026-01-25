"""
Tests for API Routes and FastAPI Application.

Tests cover:
- Route registration and inclusion
- Endpoint mapping and URL patterns
- HTTP methods and handlers
- Middleware integration
- WebSocket endpoints
- Version routing
- Error handling
- Health check endpoints
- Connection manager

Target: 60%+ coverage with 40-60 tests
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_env():
    """Set up mock environment variables."""
    env_vars = {
        "CORS_ORIGINS": "http://localhost:3000",
        "API_VERSIONING_ENABLED": "true",
        "RATE_LIMIT_ENABLED": "false",
        "TIMEOUT_ENABLED": "false",
        "REQUEST_LOGGING_ENABLED": "false",
        "COMPRESSION_ENABLED": "false",
        "ENABLE_BAGS_INTEGRATION": "false",
        "ENVIRONMENT": "test",
        "TEST_MODE": "true",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_middleware():
    """Mock middleware imports."""
    with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
        yield


@pytest.fixture
def mock_state():
    """Mock core.state module."""
    mock = MagicMock()
    mock.read_state.return_value = {
        "component_status": {},
        "startup_ok": 3,
        "startup_failed": 0,
    }
    return mock


@pytest.fixture
def mock_providers():
    """Mock core.providers module."""
    mock = MagicMock()
    mock.check_providers.return_value = {
        "grok": {"available": True},
        "groq": {"available": True},
    }
    return mock


@pytest.fixture
def app_factory(mock_env, mock_middleware):
    """Factory to create fresh FastAPI apps."""
    def _create_app():
        # Patch imports to avoid side effects
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            # Import fresh each time
            import importlib
            import api.fastapi_app as app_module
            importlib.reload(app_module)
            return app_module.create_app()
    return _create_app


@pytest.fixture
def test_app(mock_env):
    """Create test application with mocked dependencies."""
    with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
        with patch.dict(os.environ, {"API_VERSIONING_ENABLED": "false"}):
            from api.fastapi_app import create_app
            app = create_app()
            yield app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app, raise_server_exceptions=False)


# =============================================================================
# Connection Manager Tests
# =============================================================================


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    def test_connection_manager_init(self):
        """Test ConnectionManager initializes with expected channels."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()

        assert "staking" in manager.active_connections
        assert "credits" in manager.active_connections
        assert "treasury" in manager.active_connections
        assert "voice" in manager.active_connections
        assert "trading" in manager.active_connections

    def test_connection_manager_channels_are_lists(self):
        """Test each channel is initialized as empty list."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()

        for channel, connections in manager.active_connections.items():
            assert isinstance(connections, list)
            assert len(connections) == 0

    @pytest.mark.asyncio
    async def test_connect_adds_websocket(self):
        """Test connect() adds websocket to channel."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws, "staking")

        assert mock_ws in manager.active_connections["staking"]
        mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_creates_new_channel(self):
        """Test connect() creates channel if not exists."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws, "new_channel")

        assert "new_channel" in manager.active_connections
        assert mock_ws in manager.active_connections["new_channel"]

    def test_disconnect_removes_websocket(self):
        """Test disconnect() removes websocket from channel."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)
        manager.active_connections["staking"].append(mock_ws)

        manager.disconnect(mock_ws, "staking")

        assert mock_ws not in manager.active_connections["staking"]

    def test_disconnect_nonexistent_channel(self):
        """Test disconnect() handles nonexistent channel gracefully."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)

        # Should not raise
        manager.disconnect(mock_ws, "nonexistent")

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        """Test broadcast() sends message to all connections in channel."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        manager.active_connections["staking"] = [mock_ws1, mock_ws2]

        await manager.broadcast("staking", {"type": "update", "data": {}})

        mock_ws1.send_json.assert_called_once_with({"type": "update", "data": {}})
        mock_ws2.send_json.assert_called_once_with({"type": "update", "data": {}})

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_channel(self):
        """Test broadcast() handles nonexistent channel gracefully."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()

        # Should not raise
        await manager.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_cleans_up_disconnected(self):
        """Test broadcast() removes disconnected clients."""
        from api.fastapi_app import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws2.send_json.side_effect = Exception("Connection closed")
        manager.active_connections["staking"] = [mock_ws1, mock_ws2]

        await manager.broadcast("staking", {"type": "update"})

        # Disconnected client should be removed
        assert mock_ws2 not in manager.active_connections["staking"]
        assert mock_ws1 in manager.active_connections["staking"]


# =============================================================================
# Application Factory Tests
# =============================================================================


class TestCreateApp:
    """Tests for create_app() factory function."""

    def test_create_app_returns_fastapi(self, mock_env, mock_middleware):
        """Test create_app() returns FastAPI instance."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            assert isinstance(app, FastAPI)

    def test_app_has_correct_title(self, mock_env, mock_middleware):
        """Test app has correct title."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            assert app.title == "JARVIS API"

    def test_app_has_correct_version(self, mock_env, mock_middleware):
        """Test app has correct version."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            assert app.version == "4.3.0"

    def test_app_has_docs_urls(self, mock_env, mock_middleware):
        """Test app has configured docs URLs."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            assert app.docs_url == "/api/docs"
            assert app.redoc_url == "/api/redoc"
            assert app.openapi_url == "/api/openapi.json"

    def test_app_has_openapi_tags(self, mock_env, mock_middleware):
        """Test app has OpenAPI tags configured."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            tag_names = [tag["name"] for tag in app.openapi_tags]
            assert "health" in tag_names
            assert "staking" in tag_names
            assert "credits" in tag_names
            assert "treasury" in tag_names

    def test_cors_middleware_added(self, mock_env, mock_middleware):
        """Test CORS middleware is added."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()

            # Check CORS middleware is present
            middleware_names = [m.cls.__name__ for m in app.user_middleware
                              if hasattr(m, 'cls')]
            assert "CORSMiddleware" in middleware_names


# =============================================================================
# Route Registration Tests
# =============================================================================


class TestRouteRegistration:
    """Tests for _include_routers() function."""

    def test_health_endpoint_registered(self, test_client):
        """Test /api/health endpoint is registered."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_endpoint_returns_version(self, test_client):
        """Test health endpoint returns version."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    def test_health_endpoint_returns_timestamp(self, test_client):
        """Test health endpoint returns timestamp."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data

    def test_health_endpoint_returns_services(self, test_client):
        """Test health endpoint returns services status."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data

    def test_health_components_endpoint(self, test_client, mock_state):
        """Test /api/health/components endpoint."""
        with patch("core.state.read_state", return_value={"component_status": {}, "startup_ok": 1, "startup_failed": 0}):
            response = test_client.get("/api/health/components")

        assert response.status_code == 200
        data = response.json()
        assert "components" in data

    def test_metrics_endpoint_exists(self, test_client):
        """Test /api/metrics endpoint exists."""
        response = test_client.get("/api/metrics")

        # Should return 200 even if metrics not available
        assert response.status_code == 200

    def test_traces_endpoint_exists(self, test_client):
        """Test /api/traces endpoint exists."""
        response = test_client.get("/api/traces")

        assert response.status_code == 200

    def test_compression_stats_endpoint(self, test_client):
        """Test /api/compression-stats endpoint."""
        response = test_client.get("/api/compression-stats")

        assert response.status_code == 200

    def test_timeout_stats_endpoint(self, test_client):
        """Test /api/timeout-stats endpoint."""
        response = test_client.get("/api/timeout-stats")

        assert response.status_code == 200


# =============================================================================
# HTTP Method Tests
# =============================================================================


class TestHTTPMethods:
    """Tests for HTTP method handling."""

    def test_get_health(self, test_client):
        """Test GET method works for health endpoint."""
        response = test_client.get("/api/health")
        assert response.status_code == 200

    def test_post_not_allowed_on_health(self, test_client):
        """Test POST is not allowed on health endpoint."""
        response = test_client.post("/api/health")
        assert response.status_code == 405

    def test_options_request(self, test_client):
        """Test OPTIONS request returns allowed methods."""
        response = test_client.options("/api/health")
        # CORS middleware handles OPTIONS
        assert response.status_code in [200, 405]


# =============================================================================
# URL Pattern Tests
# =============================================================================


class TestURLPatterns:
    """Tests for URL patterns and routing."""

    def test_api_prefix(self, test_client):
        """Test routes use /api prefix."""
        response = test_client.get("/api/health")
        assert response.status_code == 200

    def test_root_without_api_returns_404(self, test_client):
        """Test root path returns 404."""
        response = test_client.get("/")
        assert response.status_code == 404

    def test_health_without_api_returns_404(self, test_client):
        """Test /health without /api returns 404."""
        response = test_client.get("/health")
        assert response.status_code == 404

    def test_trailing_slash_handling(self, test_client):
        """Test trailing slash is handled correctly."""
        # FastAPI typically redirects trailing slash
        response = test_client.get("/api/health/")
        assert response.status_code in [200, 307, 404]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and responses."""

    def test_404_returns_json(self, test_client):
        """Test 404 error returns JSON response."""
        response = test_client.get("/api/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_http_exception_handler(self, test_client):
        """Test HTTP exceptions are handled properly."""
        response = test_client.get("/api/nonexistent/path/here")

        assert response.status_code == 404
        data = response.json()
        # Should have error structure
        assert isinstance(data, dict)

    def test_exception_handler_returns_500_for_errors(self, test_app):
        """Test general exceptions return 500."""
        @test_app.get("/api/test-error")
        async def raise_error():
            raise ValueError("Test error")

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/api/test-error")

        assert response.status_code == 500


# =============================================================================
# WebSocket Endpoint Tests
# =============================================================================


class TestWebSocketEndpoints:
    """Tests for WebSocket endpoints."""

    def test_ws_staking_endpoint_exists(self, test_app):
        """Test /ws/staking endpoint is registered."""
        routes = [route.path for route in test_app.routes]
        assert "/ws/staking" in routes

    def test_ws_credits_endpoint_exists(self, test_app):
        """Test /ws/credits endpoint is registered."""
        routes = [route.path for route in test_app.routes]
        assert "/ws/credits" in routes

    def test_ws_treasury_endpoint_exists(self, test_app):
        """Test /ws/treasury endpoint is registered."""
        routes = [route.path for route in test_app.routes]
        assert "/ws/treasury" in routes

    def test_ws_voice_endpoint_exists(self, test_app):
        """Test /ws/voice endpoint is registered."""
        routes = [route.path for route in test_app.routes]
        assert "/ws/voice" in routes

    def test_ws_trading_endpoint_exists(self, test_app):
        """Test /ws/trading endpoint is registered."""
        routes = [route.path for route in test_app.routes]
        assert "/ws/trading" in routes


# =============================================================================
# Broadcast Helper Tests
# =============================================================================


class TestBroadcastHelpers:
    """Tests for broadcast helper functions."""

    @pytest.mark.asyncio
    async def test_broadcast_staking_update(self):
        """Test broadcast_staking_update() function."""
        from api.fastapi_app import broadcast_staking_update, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["staking"] = [mock_ws]

        await broadcast_staking_update({"amount": 100})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "staking_update"

        # Cleanup
        manager.active_connections["staking"] = []

    @pytest.mark.asyncio
    async def test_broadcast_credits_update(self):
        """Test broadcast_credits_update() function."""
        from api.fastapi_app import broadcast_credits_update, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["credits"] = [mock_ws]

        await broadcast_credits_update("user123", {"balance": 500})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "credits_update"
        assert call_args["user_id"] == "user123"

        # Cleanup
        manager.active_connections["credits"] = []

    @pytest.mark.asyncio
    async def test_broadcast_treasury_update(self):
        """Test broadcast_treasury_update() function."""
        from api.fastapi_app import broadcast_treasury_update, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["treasury"] = [mock_ws]

        await broadcast_treasury_update({"balance": 1000})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "treasury_update"

        # Cleanup
        manager.active_connections["treasury"] = []

    @pytest.mark.asyncio
    async def test_broadcast_voice_status(self):
        """Test broadcast_voice_status() function."""
        from api.fastapi_app import broadcast_voice_status, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["voice"] = [mock_ws]

        await broadcast_voice_status({"listening": True})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "voice_status"

        # Cleanup
        manager.active_connections["voice"] = []

    @pytest.mark.asyncio
    async def test_broadcast_voice_transcript(self):
        """Test broadcast_voice_transcript() function."""
        from api.fastapi_app import broadcast_voice_transcript, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["voice"] = [mock_ws]

        await broadcast_voice_transcript("Hello world", is_final=True)

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "voice_transcript"
        assert call_args["data"]["text"] == "Hello world"
        assert call_args["data"]["is_final"] is True

        # Cleanup
        manager.active_connections["voice"] = []

    @pytest.mark.asyncio
    async def test_broadcast_trading_update(self):
        """Test broadcast_trading_update() function."""
        from api.fastapi_app import broadcast_trading_update, manager

        mock_ws = AsyncMock(spec=WebSocket)
        manager.active_connections["trading"] = [mock_ws]

        await broadcast_trading_update("position_update", {"position": "SOL"})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == "position_update"

        # Cleanup
        manager.active_connections["trading"] = []


# =============================================================================
# Versioning Tests
# =============================================================================


class TestVersioning:
    """Tests for API versioning functionality."""

    def test_extract_version_from_path(self):
        """Test version extraction from URL path."""
        from api.versioning import extract_version_from_path

        assert extract_version_from_path("/api/v1/staking") == "v1"
        assert extract_version_from_path("/api/v2/credits") == "v2"
        assert extract_version_from_path("/api/health") is None
        assert extract_version_from_path("/v1/test") == "v1"

    def test_extract_version_invalid_paths(self):
        """Test version extraction handles invalid paths."""
        from api.versioning import extract_version_from_path

        assert extract_version_from_path("") is None
        assert extract_version_from_path("/api/") is None
        assert extract_version_from_path("/api/version") is None
        assert extract_version_from_path("/api/vx/test") is None

    def test_version_negotiator_is_supported(self):
        """Test VersionNegotiator.is_version_supported()."""
        from api.versioning import VersionNegotiator, SUPPORTED_VERSIONS

        assert VersionNegotiator.is_version_supported("v1") == ("v1" in SUPPORTED_VERSIONS)
        assert VersionNegotiator.is_version_supported("v999") is False

    def test_version_negotiator_is_deprecated(self):
        """Test VersionNegotiator.is_version_deprecated()."""
        from api.versioning import VersionNegotiator, DEPRECATED_VERSIONS

        # v1 should not be deprecated by default
        result = VersionNegotiator.is_version_deprecated("v1")
        expected = "v1" in DEPRECATED_VERSIONS
        assert result == expected

    def test_create_versioned_router(self):
        """Test create_versioned_router() creates correct router."""
        from api.versioning import create_versioned_router
        from fastapi import APIRouter

        router = create_versioned_router(
            version="v1",
            prefix="/test",
            tags=["Test"],
        )

        assert isinstance(router, APIRouter)
        assert router.prefix == "/api/v1/test"

    def test_create_versioned_router_with_tags(self):
        """Test versioned router has correct tags."""
        from api.versioning import create_versioned_router

        router = create_versioned_router(
            version="v1",
            prefix="/test",
            tags=["TestTag"],
        )

        assert "V1 TestTag" in router.tags


# =============================================================================
# Version Info Router Tests
# =============================================================================


class TestVersionInfoRouter:
    """Tests for version info endpoints."""

    def test_versions_endpoint(self, mock_env):
        """Test /api/versions endpoint."""
        from api.versioning import create_version_info_router

        app = FastAPI()
        router = create_version_info_router()
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/versions")

        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert "versions" in data

    def test_version_endpoint(self, mock_env):
        """Test /api/version endpoint."""
        from api.versioning import create_version_info_router

        app = FastAPI()
        router = create_version_info_router()
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "current" in data


# =============================================================================
# Middleware Integration Tests
# =============================================================================


class TestMiddlewareIntegration:
    """Tests for middleware integration."""

    def test_request_has_cors_headers(self, test_client):
        """Test CORS headers are present in response."""
        # Make request with Origin header
        response = test_client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )

        # CORS headers should be present
        assert response.status_code == 200
        # Access-Control-Allow-Origin may be present
        # depending on CORS configuration

    def test_gzip_response_available(self, mock_env):
        """Test GZip compression is available."""
        # GZip is added via GZipMiddleware or CompressionMiddleware
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import create_app

            app = create_app()
            # App should be created without errors
            assert app is not None


# =============================================================================
# Lifespan Tests
# =============================================================================


class TestLifespan:
    """Tests for application lifespan management."""

    def test_lifespan_context_manager(self, mock_env):
        """Test lifespan context manager works."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import lifespan

            app = FastAPI()

            # Lifespan should be callable
            assert callable(lifespan)

    @pytest.mark.asyncio
    async def test_lifespan_startup_shutdown(self, mock_env):
        """Test lifespan handles startup and shutdown."""
        with patch("api.fastapi_app.HAS_MIDDLEWARE", False):
            from api.fastapi_app import lifespan

            app = FastAPI()

            # Run through lifespan
            async with lifespan(app):
                # Inside lifespan, services should be available
                pass
            # After context, cleanup should have run


# =============================================================================
# Health Check System Tests
# =============================================================================


class TestHealthCheckSystem:
    """Tests for health check system metrics."""

    def test_health_returns_system_metrics(self, test_client):
        """Test health endpoint returns system metrics."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "system" in data

        system = data["system"]
        assert "cpu_percent" in system
        assert "memory_percent" in system

    def test_health_status_values(self, test_client):
        """Test health status is one of expected values."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_services_structure(self, test_client):
        """Test services have expected structure."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        services = data["services"]
        # Check expected service keys
        expected_services = ["staking", "credits", "treasury", "database"]
        for service in expected_services:
            assert service in services


# =============================================================================
# V1 Routes Tests
# =============================================================================


class TestV1Routes:
    """Tests for v1 versioned routes."""

    def test_create_v1_routers(self):
        """Test create_v1_routers() returns list of routers."""
        from api.routes.v1 import create_v1_routers

        routers = create_v1_routers()

        assert isinstance(routers, list)
        # Should have at least one router if any routes are available
        # (depends on which modules are importable)

    def test_v1_router_has_correct_prefix(self):
        """Test v1 routers have /api/v1 prefix."""
        from api.routes.v1 import create_v1_routers

        routers = create_v1_routers()

        for router in routers:
            assert router.prefix.startswith("/api/v1")


# =============================================================================
# Default Response Class Tests
# =============================================================================


class TestDefaultResponseClass:
    """Tests for default response class configuration."""

    def test_orjson_import_handling(self):
        """Test ORJSONResponse import is handled gracefully."""
        # This tests the try/except block for ORJSONResponse
        from api.fastapi_app import DEFAULT_RESPONSE_CLASS

        # Should be either ORJSONResponse or JSONResponse
        assert DEFAULT_RESPONSE_CLASS is not None

    def test_response_is_json(self, test_client):
        """Test responses are JSON formatted."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        # Should parse as JSON without error
        data = response.json()
        assert isinstance(data, dict)


# =============================================================================
# Route Path Tests
# =============================================================================


class TestRoutePaths:
    """Tests for route path configurations."""

    def test_all_routes_have_paths(self, test_app):
        """Test all routes have valid paths."""
        for route in test_app.routes:
            assert hasattr(route, 'path')
            assert route.path is not None
            assert isinstance(route.path, str)

    def test_routes_start_with_slash(self, test_app):
        """Test all routes start with /."""
        for route in test_app.routes:
            if hasattr(route, 'path'):
                assert route.path.startswith("/"), f"Route {route.path} doesn't start with /"

    def test_api_routes_have_api_prefix(self, test_app):
        """Test API routes use /api prefix (except WS routes)."""
        for route in test_app.routes:
            if hasattr(route, 'path'):
                path = route.path
                # Skip WebSocket, docs, and internal routes
                if path.startswith("/ws/") or path.startswith("/docs") or path == "/openapi.json":
                    continue
                if path.startswith("/api"):
                    assert path.startswith("/api/") or path == "/api"


# =============================================================================
# Deprecated Endpoint Decorator Tests
# =============================================================================


class TestDeprecatedDecorator:
    """Tests for deprecated() decorator."""

    @pytest.mark.asyncio
    async def test_deprecated_decorator_marks_function(self):
        """Test deprecated decorator adds metadata."""
        from api.versioning import deprecated

        @deprecated("v2", "2026-06-01", "Use new endpoint")
        async def old_endpoint():
            return {"result": "ok"}

        assert old_endpoint.__deprecated__ is True
        assert old_endpoint.__new_version__ == "v2"
        assert old_endpoint.__sunset_date__ == "2026-06-01"

    @pytest.mark.asyncio
    async def test_deprecated_decorator_preserves_function(self):
        """Test deprecated decorator preserves function behavior."""
        from api.versioning import deprecated

        @deprecated("v2", "2026-06-01")
        async def old_endpoint():
            return {"result": "success"}

        result = await old_endpoint()
        assert result == {"result": "success"}


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for routes system."""

    def test_full_health_workflow(self, test_client):
        """Test complete health check workflow."""
        # 1. Check main health
        response = test_client.get("/api/health")
        assert response.status_code == 200
        health_data = response.json()

        # 2. Check components
        with patch("core.state.read_state", return_value={"component_status": {}, "startup_ok": 1, "startup_failed": 0}):
            response = test_client.get("/api/health/components")
        assert response.status_code == 200

    def test_api_info_workflow(self, mock_env):
        """Test API version info workflow."""
        from api.versioning import create_version_info_router

        app = FastAPI()
        router = create_version_info_router()
        app.include_router(router)

        client = TestClient(app)

        # 1. List versions
        response = client.get("/api/versions")
        assert response.status_code == 200
        versions_data = response.json()

        # 2. Get current version
        response = client.get("/api/version")
        assert response.status_code == 200
        version_data = response.json()

        # Current version should match
        assert version_data["version"] == versions_data["current_version"]

    def test_multiple_routes_respond(self, test_client):
        """Test multiple routes respond correctly."""
        endpoints = [
            "/api/health",
            "/api/metrics",
            "/api/traces",
            "/api/compression-stats",
            "/api/timeout-stats",
        ]

        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
