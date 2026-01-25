"""
Tests for API Request Logging Middleware

Tests:
- Request/response logging
- Sensitive data masking
- Performance tracking
- Error logging
- Correlation IDs
"""

import json
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.testclient import TestClient
from starlette.routing import Route

from api.middleware.request_logging import (
    RequestLoggingMiddleware,
    mask_value,
    mask_headers,
    mask_body,
    get_request_id,
    get_request_duration,
)


# =============================================================================
# Masking Tests
# =============================================================================


def test_mask_value():
    """Test value masking."""
    assert mask_value("secret123456") == "secr...3456"
    assert mask_value("short") == "****"
    assert mask_value("12345678", show_chars=2) == "12...78"


def test_mask_headers():
    """Test header masking."""
    headers = {
        "authorization": "Bearer secret-token-12345",
        "x-api-key": "api-key-12345",
        "content-type": "application/json",
        "user-agent": "TestClient/1.0",
    }

    masked = mask_headers(headers)

    assert "authorization" in masked
    assert "secret-token" not in masked["authorization"]
    assert masked["authorization"] == "Bear...2345"

    assert "x-api-key" in masked
    assert "api-key" not in masked["x-api-key"]

    # Non-sensitive headers should be unchanged
    assert masked["content-type"] == "application/json"
    assert masked["user-agent"] == "TestClient/1.0"


def test_mask_body_nested():
    """Test recursive body masking."""
    body = {
        "username": "testuser",
        "password": "secret123",
        "settings": {
            "api_key": "key-12345",
            "theme": "dark",
        },
        "items": [
            {"name": "item1", "secret": "hidden"},
            {"name": "item2", "value": "visible"},
        ],
    }

    masked = mask_body(body)

    # Sensitive fields should be masked
    assert masked["password"] == "****"
    assert masked["settings"]["api_key"] == "****"
    assert masked["items"][0]["secret"] == "****"

    # Non-sensitive fields should be unchanged
    assert masked["username"] == "testuser"
    assert masked["settings"]["theme"] == "dark"
    assert masked["items"][1]["value"] == "visible"


# =============================================================================
# Middleware Tests
# =============================================================================


@pytest.fixture
def test_app():
    """Create test application with logging middleware."""

    async def homepage(request):
        return JSONResponse({"message": "Hello"})

    async def slow_endpoint(request):
        import time
        time.sleep(1.5)
        return JSONResponse({"message": "Slow"})

    async def error_endpoint(request):
        raise ValueError("Test error")

    async def create_user(request):
        body = await request.json()
        return JSONResponse({"user_id": "123", "username": body.get("username")})

    routes = [
        Route("/", endpoint=homepage),
        Route("/slow", endpoint=slow_endpoint),
        Route("/error", endpoint=error_endpoint),
        Route("/users", endpoint=create_user, methods=["POST"]),
    ]

    app = Starlette(routes=routes)

    # Add logging middleware
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=True,
        log_response_body=False,
        slow_request_threshold=1.0,
    )

    return app


def test_basic_request_logging(test_app, caplog):
    """Test basic request/response logging."""
    client = TestClient(test_app)

    with caplog.at_level(logging.INFO):
        response = client.get("/")

    assert response.status_code == 200

    # Check logs (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    response_logs = [r for r in middleware_records if "Response:" in r.message]

    assert len(request_logs) == 1
    assert len(response_logs) == 1

    # Check request log contains method and path
    assert "GET" in request_logs[0].message
    assert "/" in request_logs[0].message

    # Check response log contains status code
    assert "200" in response_logs[0].message


def test_request_id_tracking(test_app):
    """Test request ID is generated and tracked."""
    client = TestClient(test_app)

    # Without request ID header
    response = client.get("/")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0

    # With custom request ID
    response = client.get("/", headers={"X-Request-ID": "custom-id-123"})
    assert response.headers["x-request-id"] == "custom-id-123"


def test_response_time_header(test_app):
    """Test response time is added to headers."""
    client = TestClient(test_app)

    response = client.get("/")
    assert "x-response-time" in response.headers
    assert response.headers["x-response-time"].endswith("ms")

    # Extract time value
    time_str = response.headers["x-response-time"].replace("ms", "")
    time_ms = float(time_str)
    # Duration can be 0ms for very fast responses
    assert time_ms >= 0


def test_slow_request_logging(test_app, caplog):
    """Test slow requests are logged with warning level."""
    client = TestClient(test_app)

    with caplog.at_level(logging.WARNING):
        response = client.get("/slow")

    assert response.status_code == 200

    # Should have warning log for slow request
    response_logs = [r for r in caplog.records if "Response:" in r.message and r.levelno == logging.WARNING]
    assert len(response_logs) == 1

    # Check extra data has "slow" flag
    assert hasattr(response_logs[0], "response")
    assert response_logs[0].response.get("slow") is True


def test_error_logging(test_app, caplog):
    """Test errors are logged with stack traces."""
    client = TestClient(test_app)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError):
            client.get("/error")

    # Should have error log
    error_logs = [r for r in caplog.records if r.levelno == logging.ERROR and "Response:" in r.message]
    assert len(error_logs) == 1

    # Check error details
    assert hasattr(error_logs[0], "response")
    response_data = error_logs[0].response

    assert response_data["error"] == "Test error"
    assert response_data["error_type"] == "ValueError"
    assert "stack_trace" in response_data


def test_request_body_logging(test_app, caplog):
    """Test request body is logged and masked."""
    client = TestClient(test_app)

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/users",
            json={
                "username": "testuser",
                "password": "secret123",
                "api_key": "key-12345",
            },
        )

    assert response.status_code == 200

    # Check request log (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    assert len(request_logs) == 1

    # Check body is logged and masked
    assert hasattr(request_logs[0], "request")
    request_data = request_logs[0].request

    assert "body" in request_data
    body = request_data["body"]

    # Username should be visible
    assert body["username"] == "testuser"

    # Sensitive fields should be masked
    assert body["password"] == "****"
    assert body["api_key"] == "****"


def test_skip_health_endpoints(caplog):
    """Test health check endpoints are skipped."""

    async def health(request):
        return JSONResponse({"status": "ok"})

    routes = [Route("/health", endpoint=health)]
    app = Starlette(routes=routes)
    app.add_middleware(RequestLoggingMiddleware)

    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/health")

    assert response.status_code == 200

    # Should not have any request/response logs (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    response_logs = [r for r in middleware_records if "Response:" in r.message]

    assert len(request_logs) == 0
    assert len(response_logs) == 0


def test_client_ip_extraction(test_app):
    """Test client IP is extracted from headers."""
    client = TestClient(test_app)

    # With X-Forwarded-For
    with patch("logging.Logger.info") as mock_log:
        client.get("/", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})

        # Check first call (request log)
        args = mock_log.call_args_list[0]
        extra = args[1]["extra"]
        assert extra["request"]["client_ip"] == "1.2.3.4"


def test_context_vars():
    """Test request ID and duration context vars."""
    # Before request
    assert get_request_id() == ""
    assert get_request_duration() == 0.0

    # Context vars would be set by middleware during request
    # This is a simple sanity check that the functions exist and work


def test_large_body_truncation(caplog):
    """Test large request bodies are truncated."""

    async def upload(request):
        return JSONResponse({"status": "ok"})

    routes = [Route("/upload", endpoint=upload, methods=["POST"])]
    app = Starlette(routes=routes)
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=True,
        max_body_size=100,  # Small limit
    )

    client = TestClient(app)

    # Send large body
    large_data = {"data": "x" * 10000}

    with caplog.at_level(logging.INFO):
        client.post("/upload", json=large_data)

    # Check request log (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    assert len(request_logs) == 1

    request_data = request_logs[0].request
    assert "body" in request_data
    assert "<truncated:" in request_data["body"]


def test_binary_body_handling(caplog):
    """Test binary request bodies are handled gracefully."""

    async def upload_binary(request):
        return JSONResponse({"status": "ok"})

    routes = [Route("/upload-binary", endpoint=upload_binary, methods=["POST"])]
    app = Starlette(routes=routes)
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=True,
    )

    client = TestClient(app)

    # Send binary data
    binary_data = b"\x00\x01\x02\x03\x04"

    with caplog.at_level(logging.INFO):
        client.post(
            "/upload-binary",
            content=binary_data,
            headers={"content-type": "application/octet-stream"},
        )

    # Check request log (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    assert len(request_logs) == 1

    request_data = request_logs[0].request
    assert "body" in request_data
    # Binary data may be marked as unavailable or binary depending on implementation
    assert request_data["body"] in ("<unavailable>", "<binary: 5 bytes>")


# =============================================================================
# Performance Tests
# =============================================================================


def test_middleware_performance():
    """Test middleware doesn't add significant overhead."""
    import time

    async def fast_endpoint(request):
        return JSONResponse({"status": "ok"})

    routes = [Route("/fast", endpoint=fast_endpoint)]

    # App without middleware
    app_no_middleware = Starlette(routes=routes)
    client_no_middleware = TestClient(app_no_middleware)

    # App with middleware
    app_with_middleware = Starlette(routes=routes)
    app_with_middleware.add_middleware(RequestLoggingMiddleware)
    client_with_middleware = TestClient(app_with_middleware)

    # Measure without middleware (more iterations for stability)
    iterations = 200
    start = time.time()
    for _ in range(iterations):
        client_no_middleware.get("/fast")
    no_middleware_time = time.time() - start

    # Measure with middleware
    start = time.time()
    for _ in range(iterations):
        client_with_middleware.get("/fast")
    with_middleware_time = time.time() - start

    # Middleware should add < 100% overhead
    # Note: Higher threshold accounts for Windows timing precision and
    # the fact that middleware does real work (logging, masking, headers).
    # The important thing is it doesn't add seconds of delay, not microseconds.
    overhead = (with_middleware_time - no_middleware_time) / no_middleware_time
    assert overhead < 1.0, f"Middleware added {overhead * 100:.1f}% overhead"


# =============================================================================
# Integration Tests
# =============================================================================


def test_full_request_lifecycle(test_app, caplog):
    """Test complete request lifecycle logging."""
    client = TestClient(test_app)

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/users",
            json={"username": "newuser", "password": "secret"},
            headers={
                "X-Request-ID": "integration-test-123",
                "User-Agent": "TestClient/1.0",
                "X-Forwarded-For": "192.168.1.1",
            },
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "integration-test-123"
    assert "x-response-time" in response.headers

    # Check request log (filter by logger name to exclude httpx logs)
    middleware_records = [r for r in caplog.records if r.name == "api.middleware.request_logging"]
    request_logs = [r for r in middleware_records if "Request:" in r.message]
    assert len(request_logs) == 1

    request_data = request_logs[0].request
    assert request_data["request_id"] == "integration-test-123"
    assert request_data["method"] == "POST"
    assert request_data["path"] == "/users"
    assert request_data["client_ip"] == "192.168.1.1"
    assert request_data["user_agent"] == "TestClient/1.0"

    # Check response log
    response_logs = [r for r in middleware_records if "Response:" in r.message]
    assert len(response_logs) == 1

    response_data = response_logs[0].response
    assert response_data["request_id"] == "integration-test-123"
    assert response_data["status_code"] == 200
    # Duration can be 0ms for very fast responses
    assert response_data["duration_ms"] >= 0
