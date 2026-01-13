"""
JARVIS Response Compression Middleware

Compresses API responses using gzip or brotli:
- Automatic content negotiation
- Configurable minimum size
- Content-type filtering
- Compression level control

Usage:
    from api.middleware.compression import CompressionMiddleware

    app.add_middleware(
        CompressionMiddleware,
        minimum_size=500,
        compression_level=6,
    )
"""

import gzip
import io
import logging
from typing import Callable, List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Try to import brotli for better compression
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    brotli = None


# Content types that benefit from compression
COMPRESSIBLE_TYPES: Set[str] = {
    "application/json",
    "application/javascript",
    "application/xml",
    "application/xhtml+xml",
    "text/html",
    "text/plain",
    "text/css",
    "text/javascript",
    "text/xml",
    "image/svg+xml",
}


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    HTTP compression middleware for FastAPI/Starlette.

    Supports gzip and brotli compression based on Accept-Encoding.
    """

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
        compressible_types: Optional[Set[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ):
        """
        Initialize compression middleware.

        Args:
            app: ASGI application
            minimum_size: Minimum response size to compress (bytes)
            compression_level: Compression level (1-9 for gzip, 0-11 for brotli)
            compressible_types: Content types to compress
            exclude_paths: Paths to exclude from compression
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.compressible_types = compressible_types or COMPRESSIBLE_TYPES
        self.exclude_paths = exclude_paths or []

        # Stats
        self._stats = {
            "total_responses": 0,
            "compressed_responses": 0,
            "bytes_before": 0,
            "bytes_after": 0,
            "gzip_count": 0,
            "brotli_count": 0,
        }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """Process request and compress response if applicable."""
        self._stats["total_responses"] += 1

        # Check if path is excluded
        if self._is_excluded(request.url.path):
            return await call_next(request)

        # Get accepted encodings
        accept_encoding = request.headers.get("accept-encoding", "")
        encoding = self._select_encoding(accept_encoding)

        if not encoding:
            return await call_next(request)

        # Get response
        response = await call_next(request)

        # Check if response should be compressed
        if not self._should_compress(response):
            return response

        # Compress response body
        return await self._compress_response(response, encoding)

    def _is_excluded(self, path: str) -> bool:
        """Check if path is excluded from compression."""
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False

    def _select_encoding(self, accept_encoding: str) -> Optional[str]:
        """Select best encoding based on Accept-Encoding header."""
        accept_encoding = accept_encoding.lower()

        # Prefer brotli if available
        if BROTLI_AVAILABLE and "br" in accept_encoding:
            return "br"

        if "gzip" in accept_encoding:
            return "gzip"

        return None

    def _should_compress(self, response: Response) -> bool:
        """Check if response should be compressed."""
        # Skip if already encoded
        if response.headers.get("content-encoding"):
            return False

        # Check content type
        content_type = response.headers.get("content-type", "")
        base_type = content_type.split(";")[0].strip()

        if base_type not in self.compressible_types:
            return False

        # Check content length if available
        content_length = response.headers.get("content-length")
        if content_length:
            if int(content_length) < self.minimum_size:
                return False

        return True

    async def _compress_response(
        self,
        response: Response,
        encoding: str
    ) -> Response:
        """Compress response body."""
        # Get response body
        if isinstance(response, StreamingResponse):
            # For streaming responses, collect chunks
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)
            body = b"".join(body_parts)
        else:
            body = response.body

        # Check minimum size
        original_size = len(body)
        if original_size < self.minimum_size:
            return response

        self._stats["bytes_before"] += original_size

        # Compress
        if encoding == "br" and BROTLI_AVAILABLE:
            compressed = brotli.compress(
                body,
                quality=min(self.compression_level, 11)
            )
            self._stats["brotli_count"] += 1
        else:
            buffer = io.BytesIO()
            with gzip.GzipFile(
                mode="wb",
                fileobj=buffer,
                compresslevel=self.compression_level
            ) as f:
                f.write(body)
            compressed = buffer.getvalue()
            self._stats["gzip_count"] += 1

        compressed_size = len(compressed)
        self._stats["bytes_after"] += compressed_size
        self._stats["compressed_responses"] += 1

        # Only use compressed if smaller
        if compressed_size >= original_size:
            return response

        # Build new response
        headers = dict(response.headers)
        headers["content-encoding"] = encoding
        headers["content-length"] = str(compressed_size)
        headers["vary"] = "Accept-Encoding"

        # Remove content-length from original headers to avoid mismatch
        if "content-length" in headers:
            del headers["content-length"]
        headers["Content-Length"] = str(compressed_size)

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )

    def get_stats(self) -> dict:
        """Get compression statistics."""
        stats = self._stats.copy()

        if stats["bytes_before"] > 0:
            stats["compression_ratio"] = round(
                1 - (stats["bytes_after"] / stats["bytes_before"]),
                4
            )
            stats["bytes_saved"] = stats["bytes_before"] - stats["bytes_after"]
        else:
            stats["compression_ratio"] = 0
            stats["bytes_saved"] = 0

        return stats


class GzipMiddleware(CompressionMiddleware):
    """Gzip-only compression middleware (for compatibility)."""

    def _select_encoding(self, accept_encoding: str) -> Optional[str]:
        if "gzip" in accept_encoding.lower():
            return "gzip"
        return None


def add_compression_middleware(
    app,
    minimum_size: int = 500,
    compression_level: int = 6,
):
    """
    Helper to add compression middleware to FastAPI app.

    Usage:
        from api.middleware.compression import add_compression_middleware
        add_compression_middleware(app)
    """
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=minimum_size,
        compression_level=compression_level,
    )


if __name__ == "__main__":
    import asyncio
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    print("Compression Middleware Demo")
    print("=" * 50)

    app = FastAPI()

    # Add compression
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=100,
        compression_level=6,
    )

    @app.get("/test")
    async def test_endpoint():
        # Return large JSON response
        return {
            "data": [{"id": i, "name": f"Item {i}", "description": "x" * 100}
                     for i in range(100)]
        }

    @app.get("/small")
    async def small_endpoint():
        return {"status": "ok"}

    # Test with client
    client = TestClient(app)

    # Test with gzip
    print("\n1. Testing gzip compression:")
    response = client.get("/test", headers={"Accept-Encoding": "gzip"})
    print(f"   Status: {response.status_code}")
    print(f"   Content-Encoding: {response.headers.get('content-encoding', 'none')}")
    print(f"   Content-Length: {response.headers.get('content-length', 'unknown')}")

    # Test without compression
    print("\n2. Testing without compression:")
    response = client.get("/test", headers={"Accept-Encoding": ""})
    print(f"   Content-Encoding: {response.headers.get('content-encoding', 'none')}")

    # Test small response
    print("\n3. Testing small response (no compression):")
    response = client.get("/small", headers={"Accept-Encoding": "gzip"})
    print(f"   Content-Encoding: {response.headers.get('content-encoding', 'none')}")

    print(f"\nBrotli available: {BROTLI_AVAILABLE}")
    print("\nDemo complete!")
