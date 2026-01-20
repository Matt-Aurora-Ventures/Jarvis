"""
Tests for API versioning support.

Tests:
- Version detection from path
- Version detection from headers
- Version negotiation
- Deprecation warnings
- V1 router creation
"""

import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from api.versioning import (
    extract_version_from_path,
    extract_version_from_header,
    get_request_version,
    APIVersionMiddleware,
    create_versioned_router,
    VersionNegotiator,
    create_version_info_router,
    CURRENT_VERSION,
    SUPPORTED_VERSIONS,
    DEPRECATED_VERSIONS,
)


# =============================================================================
# Version Detection Tests
# =============================================================================

class TestVersionDetection:
    """Test version detection from path and headers."""

    def test_extract_version_from_path(self):
        """Test extracting version from URL path."""
        assert extract_version_from_path("/api/v1/staking") == "v1"
        assert extract_version_from_path("/api/v2/credits") == "v2"
        assert extract_version_from_path("/api/staking") is None
        assert extract_version_from_path("/health") is None

    def test_extract_version_from_header(self):
        """Test extracting version from Accept-Version header."""
        # Mock request with header
        request = Mock()
        request.headers.get.return_value = "v1"
        assert extract_version_from_header(request) == "v1"

        # No header
        request.headers.get.return_value = ""
        assert extract_version_from_header(request) is None

        # Unsupported version
        request.headers.get.return_value = "v99"
        assert extract_version_from_header(request) is None

    def test_get_request_version_priority(self):
        """Test version detection priority (path > header > default)."""
        # Path takes priority
        request = Mock()
        request.url.path = "/api/v1/staking"
        request.headers.get.return_value = "v2"
        assert get_request_version(request) == "v1"

        # Header fallback
        request.url.path = "/api/staking"
        request.headers.get.return_value = "v1"
        assert get_request_version(request) == "v1"

        # Default fallback
        request.url.path = "/api/staking"
        request.headers.get.return_value = ""
        assert get_request_version(request) == CURRENT_VERSION


# =============================================================================
# Middleware Tests
# =============================================================================

class TestAPIVersionMiddleware:
    """Test API version middleware."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with versioning middleware."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_version_header_added(self, client):
        """Test X-API-Version header is added to response."""
        response = client.get("/api/v1/test")
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "v1"

    def test_version_from_accept_header(self, client):
        """Test version detection from Accept-Version header."""
        response = client.get("/api/test", headers={"Accept-Version": "v1"})
        assert response.headers.get("X-API-Version") == "v1"

    @patch.dict(DEPRECATED_VERSIONS, {"v1": "2026-06-01"})
    def test_deprecation_headers(self, client):
        """Test deprecation headers are added for deprecated versions."""
        response = client.get("/api/v1/test")
        assert response.headers.get("Deprecation") == "true"
        assert response.headers.get("Sunset") == "2026-06-01"
        assert "Warning" in response.headers
        assert "deprecated" in response.headers["Warning"].lower()


# =============================================================================
# Router Creation Tests
# =============================================================================

class TestVersionedRouter:
    """Test versioned router creation."""

    def test_create_versioned_router(self):
        """Test creating a versioned router."""
        router = create_versioned_router(
            version="v1",
            prefix="/staking",
            tags=["Staking"],
        )

        assert isinstance(router, APIRouter)
        assert router.prefix == "/api/v1/staking"
        assert "V1 Staking" in router.tags

    def test_deprecated_router(self):
        """Test creating a deprecated router."""
        router = create_versioned_router(
            version="v0",
            prefix="/old",
            tags=["Old"],
            deprecated=True,
            sunset_date="2026-01-01",
        )

        assert router.prefix == "/api/v0/old"
        assert "v0" in DEPRECATED_VERSIONS
        assert DEPRECATED_VERSIONS["v0"] == "2026-01-01"

        # Cleanup
        del DEPRECATED_VERSIONS["v0"]


# =============================================================================
# Version Negotiation Tests
# =============================================================================

class TestVersionNegotiator:
    """Test version negotiation logic."""

    def test_is_version_supported(self):
        """Test checking if version is supported."""
        assert VersionNegotiator.is_version_supported("v1") is True
        assert VersionNegotiator.is_version_supported("v99") is False

    def test_is_version_deprecated(self):
        """Test checking if version is deprecated."""
        with patch.dict(DEPRECATED_VERSIONS, {"v0": "2026-01-01"}):
            assert VersionNegotiator.is_version_deprecated("v0") is True
            assert VersionNegotiator.is_version_deprecated("v1") is False

    def test_get_deprecation_info(self):
        """Test getting deprecation info."""
        with patch.dict(DEPRECATED_VERSIONS, {"v0": "2026-06-01"}):
            info = VersionNegotiator.get_deprecation_info("v0")
            assert info is not None
            assert info["version"] == "v0"
            assert info["deprecated"] is True
            assert info["sunset_date"] == "2026-06-01"
            assert info["current_version"] == CURRENT_VERSION
            assert "days_remaining" in info

    def test_get_deprecation_info_current_version(self):
        """Test getting deprecation info for current version."""
        info = VersionNegotiator.get_deprecation_info(CURRENT_VERSION)
        assert info is None

    def test_validate_version_success(self):
        """Test version validation with supported version."""
        # Should not raise
        VersionNegotiator.validate_version("v1")

    def test_validate_version_failure(self):
        """Test version validation with unsupported version."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            VersionNegotiator.validate_version("v99")

        assert exc_info.value.status_code == 400
        assert "UNSUPPORTED_VERSION" in str(exc_info.value.detail)


# =============================================================================
# Version Info Endpoints Tests
# =============================================================================

class TestVersionInfoEndpoints:
    """Test version info endpoints."""

    @pytest.fixture
    def app(self):
        """Create test app with version info routes."""
        app = FastAPI()
        version_router = create_version_info_router()
        app.include_router(version_router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_list_versions(self, client):
        """Test /api/versions endpoint."""
        response = client.get("/api/versions")
        assert response.status_code == 200

        data = response.json()
        assert "current_version" in data
        assert data["current_version"] == CURRENT_VERSION
        assert "versions" in data
        assert len(data["versions"]) > 0

        # Check version info structure
        v1_info = next(v for v in data["versions"] if v["version"] == "v1")
        assert "deprecated" in v1_info
        assert "current" in v1_info

    def test_get_version_info(self, client):
        """Test /api/version endpoint."""
        response = client.get("/api/version")
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert data["version"] == CURRENT_VERSION
        assert "current" in data
        assert "deprecated" in data

    def test_get_version_info_with_header(self, client):
        """Test /api/version with Accept-Version header."""
        response = client.get("/api/version", headers={"Accept-Version": "v1"})
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "v1"

    @patch.dict(DEPRECATED_VERSIONS, {"v1": "2026-06-01"})
    def test_deprecated_version_info(self, client):
        """Test version info includes deprecation details."""
        response = client.get("/api/versions")
        data = response.json()

        v1_info = next(v for v in data["versions"] if v["version"] == "v1")
        assert v1_info["deprecated"] is True
        assert "sunset_date" in v1_info


# =============================================================================
# V1 Router Tests
# =============================================================================

class TestV1Routers:
    """Test V1 router creation."""

    def test_create_v1_routers(self):
        """Test creating v1 routers."""
        from api.routes.v1 import create_v1_routers

        routers = create_v1_routers()

        # Should have routers for available modules
        assert isinstance(routers, list)
        assert len(routers) > 0

        # All should be APIRouter instances
        for router in routers:
            assert isinstance(router, APIRouter)

        # Check prefixes
        prefixes = [r.prefix for r in routers]
        # Should have v1 prefixes
        assert any("/api/v1/" in p for p in prefixes)


# =============================================================================
# Integration Tests
# =============================================================================

class TestVersioningIntegration:
    """Integration tests for complete versioning flow."""

    @pytest.fixture
    def app(self):
        """Create app with versioning enabled."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        # Version info
        version_router = create_version_info_router()
        app.include_router(version_router)

        # V1 routes
        v1_router = create_versioned_router("v1", "/test", ["Test"])

        @v1_router.get("/endpoint")
        async def test_endpoint():
            return {"message": "Hello from v1"}

        app.include_router(v1_router)

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_versioned_endpoint_access(self, client):
        """Test accessing versioned endpoint."""
        response = client.get("/api/v1/test/endpoint")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello from v1"}
        assert response.headers["X-API-Version"] == "v1"

    def test_version_discovery(self, client):
        """Test discovering available versions."""
        response = client.get("/api/versions")
        assert response.status_code == 200

        data = response.json()
        assert data["current_version"] == CURRENT_VERSION
        assert len(data["versions"]) > 0

    def test_accept_version_header(self, client):
        """Test Accept-Version header support."""
        response = client.get("/api/version", headers={"Accept-Version": "v1"})
        assert response.status_code == 200
        assert response.json()["version"] == "v1"

    @patch.dict(DEPRECATED_VERSIONS, {"v1": "2026-12-31"})
    def test_deprecated_version_warning(self, client):
        """Test deprecation warnings on deprecated versions."""
        response = client.get("/api/v1/test/endpoint")
        assert response.status_code == 200
        assert response.headers.get("Deprecation") == "true"
        assert response.headers.get("Sunset") == "2026-12-31"
        assert "deprecated" in response.headers.get("Warning", "").lower()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_version_format(self):
        """Test handling invalid version format."""
        assert extract_version_from_path("/api/vX/test") is None
        assert extract_version_from_path("/api/1/test") is None

    def test_empty_version_header(self):
        """Test handling empty version header."""
        request = Mock()
        request.headers.get.return_value = "   "
        assert extract_version_from_header(request) is None

    def test_multiple_versions_in_path(self):
        """Test path with multiple version-like segments."""
        # Should return first match
        result = extract_version_from_path("/api/v1/v2/test")
        assert result == "v1"

    def test_version_case_sensitivity(self):
        """Test version detection is case-sensitive."""
        assert extract_version_from_path("/api/V1/test") is None
        assert extract_version_from_path("/api/v1/test") == "v1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
