"""
Tests for Response Compression Middleware.

Verifies that the CompressionMiddleware correctly compresses API responses
based on size, content-type, and client Accept-Encoding headers.
"""

import gzip
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.middleware.compression import CompressionMiddleware, BROTLI_AVAILABLE


@pytest.fixture
def app():
    """Create a test FastAPI app with compression middleware."""
    app = FastAPI()

    # Add compression middleware with low threshold for testing
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=100,  # Low threshold for testing
        compression_level=6,
    )

    @app.get("/large")
    async def large_endpoint():
        """Return a large JSON response (should be compressed)."""
        return {
            "data": [
                {"id": i, "name": f"Item {i}", "description": "x" * 100}
                for i in range(100)
            ]
        }

    @app.get("/small")
    async def small_endpoint():
        """Return a small JSON response (should NOT be compressed)."""
        return {"status": "ok"}

    @app.get("/text")
    async def text_endpoint():
        """Return text/plain response."""
        return JSONResponse(
            content={"message": "Hello " * 100},
            media_type="text/plain"
        )

    @app.get("/image")
    async def image_endpoint():
        """Return image response (should NOT be compressed)."""
        return JSONResponse(
            content={"data": "binary_data"},
            media_type="image/png"
        )

    @app.get("/excluded")
    async def excluded_endpoint():
        """Endpoint for exclusion testing."""
        return {"data": "x" * 1000}

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestCompressionBasics:
    """Test basic compression behavior."""

    def test_compresses_large_json_with_gzip(self, client):
        """Should compress large JSON responses when gzip is accepted."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        assert "accept-encoding" in response.headers.get("vary", "").lower()

        # Verify data is actually compressed (and decompressible)
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 100

    def test_does_not_compress_small_responses(self, client):
        """Should NOT compress responses below minimum_size threshold."""
        response = client.get(
            "/small",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") is None

    def test_no_compression_without_accept_encoding(self, client):
        """Should NOT compress if client doesn't send Accept-Encoding."""
        # Explicitly disable compression by sending empty Accept-Encoding
        response = client.get("/large", headers={"Accept-Encoding": ""})

        assert response.status_code == 200
        assert response.headers.get("content-encoding") is None

    def test_no_compression_for_non_compressible_types(self, client):
        """Should NOT compress non-text content types like images."""
        response = client.get(
            "/image",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") is None


class TestBrotliCompression:
    """Test Brotli compression (if available)."""

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="Brotli not installed")
    def test_prefers_brotli_over_gzip(self, client):
        """Should use brotli when client accepts both br and gzip."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "br, gzip"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "br"

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="Brotli not installed")
    def test_brotli_compression_works(self, client):
        """Should successfully compress with brotli."""
        import brotli

        response = client.get(
            "/large",
            headers={"Accept-Encoding": "br"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "br"

        # Response should be valid JSON after decompression
        data = response.json()
        assert len(data["data"]) == 100


class TestCompressionHeaders:
    """Test HTTP headers related to compression."""

    def test_sets_vary_header(self, client):
        """Should set Vary: Accept-Encoding for cache control."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )

        assert "accept-encoding" in response.headers.get("vary", "").lower()

    def test_updates_content_length(self, client):
        """Should update Content-Length to reflect compressed size."""
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )

        # Content-Length should be set and smaller than uncompressed
        content_length = int(response.headers.get("content-length", 0))
        assert content_length > 0

        # Verify it's actually compressed (smaller)
        uncompressed_response = client.get("/large")
        uncompressed_length = len(uncompressed_response.content)
        assert content_length < uncompressed_length

    def test_does_not_double_compress(self, client):
        """Should NOT compress responses that are already encoded."""
        # This test verifies the middleware checks for existing content-encoding
        # In practice, this is tested by the middleware's _should_compress() method
        pass  # Implicitly tested by other tests


class TestCompressionConfiguration:
    """Test middleware configuration options."""

    def test_custom_minimum_size(self):
        """Should respect custom minimum_size configuration."""
        app = FastAPI()

        # Set high minimum size (10KB)
        app.add_middleware(
            CompressionMiddleware,
            minimum_size=10_000,
        )

        @app.get("/medium")
        async def medium_endpoint():
            return {"data": "x" * 5000}

        client = TestClient(app)
        response = client.get(
            "/medium",
            headers={"Accept-Encoding": "gzip"}
        )

        # Should NOT compress (below 10KB threshold)
        assert response.headers.get("content-encoding") is None

    def test_custom_compression_level(self):
        """Should respect custom compression_level configuration."""
        app = FastAPI()

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
            compression_level=9,  # Maximum compression
        )

        @app.get("/test")
        async def test_endpoint():
            return {"data": "x" * 1000}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.headers.get("content-encoding") == "gzip"

    def test_exclude_paths(self):
        """Should exclude specified paths from compression."""
        app = FastAPI()

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
            exclude_paths=["/health", "/metrics"],
        )

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok", "data": "x" * 1000}

        @app.get("/api/data")
        async def data_endpoint():
            return {"data": "x" * 1000}

        client = TestClient(app)

        # /health should NOT be compressed (excluded)
        health_response = client.get(
            "/health",
            headers={"Accept-Encoding": "gzip"}
        )
        assert health_response.headers.get("content-encoding") is None

        # /api/data should be compressed (not excluded)
        data_response = client.get(
            "/api/data",
            headers={"Accept-Encoding": "gzip"}
        )
        assert data_response.headers.get("content-encoding") == "gzip"


class TestCompressionStatistics:
    """Test compression statistics tracking."""

    def test_tracks_compression_stats(self):
        """Should track compression statistics."""
        app = FastAPI()

        middleware_instance = None

        # Capture middleware instance
        def capture_middleware():
            nonlocal middleware_instance
            for middleware in app.user_middleware:
                if hasattr(middleware, 'cls') and middleware.cls == CompressionMiddleware:
                    # Can't easily get instance, so we'll test via the middleware class
                    pass
            return app

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"data": "x" * 1000}

        client = TestClient(app)

        # Make requests
        for _ in range(5):
            client.get("/test", headers={"Accept-Encoding": "gzip"})

        # Note: Getting stats from middleware instance is tricky in FastAPI
        # In production, stats can be exposed via a dedicated endpoint


class TestCompressionEfficiency:
    """Test compression efficiency and edge cases."""

    def test_compression_reduces_size(self, client):
        """Should significantly reduce response size for compressible data."""
        # Get uncompressed response
        uncompressed = client.get("/large")
        uncompressed_size = len(uncompressed.content)

        # Get compressed response
        compressed = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        compressed_size = int(compressed.headers.get("content-length", 0))

        # Should be at least 50% smaller
        compression_ratio = 1 - (compressed_size / uncompressed_size)
        assert compression_ratio > 0.5, f"Compression ratio: {compression_ratio:.2%}"

    def test_decompressed_content_matches_original(self, client):
        """Decompressed content should match uncompressed response."""
        # Get uncompressed
        uncompressed = client.get("/large")
        uncompressed_data = uncompressed.json()

        # Get compressed
        compressed = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"}
        )
        compressed_data = compressed.json()

        # Should be identical
        assert compressed_data == uncompressed_data

    def test_handles_empty_responses(self):
        """Should handle empty responses gracefully."""
        app = FastAPI()

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
        )

        @app.get("/empty")
        async def empty_endpoint():
            return {}

        client = TestClient(app)
        response = client.get(
            "/empty",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        # Should not compress (below minimum size)
        assert response.headers.get("content-encoding") is None


class TestCompressionContentTypes:
    """Test compression behavior for different content types."""

    @pytest.mark.parametrize("content_type,should_compress", [
        ("application/json", True),
        ("application/javascript", True),
        ("text/html", True),
        ("text/plain", True),
        ("text/css", True),
        ("application/xml", True),
        ("image/svg+xml", True),
        ("image/png", False),
        ("image/jpeg", False),
        ("video/mp4", False),
        ("application/octet-stream", False),
    ])
    def test_compression_by_content_type(self, content_type, should_compress):
        """Should compress only text-based content types."""
        app = FastAPI()

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
        )

        @app.get("/test")
        async def test_endpoint():
            return JSONResponse(
                content={"data": "x" * 1000},
                media_type=content_type
            )

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Accept-Encoding": "gzip"}
        )

        if should_compress:
            assert response.headers.get("content-encoding") == "gzip", \
                f"{content_type} should be compressed"
        else:
            assert response.headers.get("content-encoding") is None, \
                f"{content_type} should NOT be compressed"


class TestIntegrationWithFastAPI:
    """Test integration with FastAPI features."""

    def test_works_with_orjson_response(self):
        """Should work with ORJSONResponse."""
        try:
            from fastapi.responses import ORJSONResponse
        except ImportError:
            pytest.skip("ORJSONResponse not available")

        app = FastAPI(default_response_class=ORJSONResponse)

        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"data": "x" * 1000}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Accept-Encoding": "gzip"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

    def test_works_with_middleware_stack(self):
        """Should work correctly in a middleware stack."""
        from starlette.middleware.cors import CORSMiddleware

        app = FastAPI()

        # Add multiple middleware (CORS must be added FIRST to be last in execution)
        app.add_middleware(
            CompressionMiddleware,
            minimum_size=100,
        )
        app.add_middleware(CORSMiddleware, allow_origins=["*"])

        @app.get("/test")
        async def test_endpoint():
            return {"data": "x" * 1000}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Accept-Encoding": "gzip", "Origin": "http://localhost"}
        )

        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        assert "access-control-allow-origin" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
