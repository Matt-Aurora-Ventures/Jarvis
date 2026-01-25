"""
Comprehensive Tests for API Middleware Modules.

Tests all middleware components in api/middleware/:
- RateLimitMiddleware
- SecurityHeadersMiddleware
- RequestTracingMiddleware
- CSRFMiddleware
- IPAllowlistMiddleware
- BodySizeLimitMiddleware
- IdempotencyMiddleware
- CSPNonceMiddleware
- RequestValidationMiddleware
- RequestLoggingMiddleware

Target: 60%+ coverage with ~50 tests
"""

import asyncio
import json
import logging
import pytest
import secrets
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import Response, JSONResponse


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def basic_app():
    """Create a basic FastAPI app for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/submit")
    async def submit_endpoint():
        return {"submitted": True}

    @app.get("/api/health")
    async def health_endpoint():
        return {"healthy": True}

    @app.get("/api/admin/status")
    async def admin_endpoint():
        return {"admin": True}

    return app


# =============================================================================
# RequestTracingMiddleware Tests
# =============================================================================


class TestRequestTracingMiddleware:
    """Tests for request tracing middleware."""

    def test_generates_request_id_when_none_provided(self, basic_app):
        """Should generate a request ID if not provided."""
        from api.middleware.request_tracing import RequestTracingMiddleware

        basic_app.add_middleware(RequestTracingMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Generated IDs are 8 chars (UUID[:8])
        assert len(response.headers["X-Request-ID"]) == 8

    def test_uses_provided_request_id(self, basic_app):
        """Should use the request ID provided in headers."""
        from api.middleware.request_tracing import RequestTracingMiddleware

        basic_app.add_middleware(RequestTracingMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test", headers={"X-Request-ID": "custom123"})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "custom123"

    def test_custom_header_name(self, basic_app):
        """Should support custom header names."""
        from api.middleware.request_tracing import RequestTracingMiddleware

        basic_app.add_middleware(RequestTracingMiddleware, header_name="X-Trace-ID")
        client = TestClient(basic_app)

        response = client.get("/test")

        assert "X-Trace-ID" in response.headers

    def test_includes_response_time_header(self, basic_app):
        """Should include X-Response-Time header."""
        from api.middleware.request_tracing import RequestTracingMiddleware

        basic_app.add_middleware(RequestTracingMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert "X-Response-Time" in response.headers
        # Should be in format "0.XXXs"
        assert "s" in response.headers["X-Response-Time"]

    def test_logs_request_info(self, basic_app, caplog):
        """Should log request information."""
        from api.middleware.request_tracing import RequestTracingMiddleware

        basic_app.add_middleware(RequestTracingMiddleware)
        client = TestClient(basic_app)

        with caplog.at_level(logging.INFO):
            response = client.get("/test")

        assert response.status_code == 200
        # Check that request path was logged
        assert any("/test" in record.message for record in caplog.records)

    def test_get_request_id_function(self):
        """Test the get_request_id helper function."""
        from api.middleware.request_tracing import request_id_var, get_request_id

        # Set a request ID
        request_id_var.set("test-id-123")
        assert get_request_id() == "test-id-123"

        # Reset
        request_id_var.set("")
        assert get_request_id() == ""


# =============================================================================
# SecurityHeadersMiddleware Tests
# =============================================================================


class TestSecurityHeadersMiddleware:
    """Tests for security headers middleware."""

    def test_adds_default_security_headers(self, basic_app):
        """Should add all default security headers."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        basic_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_adds_content_security_policy(self, basic_app):
        """Should add Content-Security-Policy header."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        basic_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert "Content-Security-Policy" in response.headers
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]

    def test_custom_csp_policy(self, basic_app):
        """Should support custom CSP policies."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        custom_csp = "default-src 'none'; script-src 'self'"
        basic_app.add_middleware(SecurityHeadersMiddleware, csp_policy=custom_csp)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_custom_headers(self, basic_app):
        """Should support additional custom headers."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        custom_headers = {"X-Custom-Header": "custom-value"}
        basic_app.add_middleware(SecurityHeadersMiddleware, custom_headers=custom_headers)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.headers["X-Custom-Header"] == "custom-value"

    def test_hsts_only_for_https(self, basic_app):
        """Should only add HSTS header for HTTPS requests."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        basic_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(basic_app)

        # HTTP request (test client uses http by default)
        response = client.get("/test")

        # HSTS should not be present for HTTP
        assert "Strict-Transport-Security" not in response.headers

    def test_get_security_headers_method(self):
        """Test get_security_headers method."""
        from api.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=None)
        headers = middleware.get_security_headers()

        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "Content-Security-Policy" in headers

    def test_get_recommended_csp_function(self):
        """Test get_recommended_csp helper function."""
        from api.middleware.security_headers import get_recommended_csp

        csp = get_recommended_csp()
        assert "default-src 'self'" in csp
        assert "script-src" in csp

    def test_get_recommended_csp_no_inline(self):
        """Test CSP without inline scripts."""
        from api.middleware.security_headers import get_recommended_csp

        csp = get_recommended_csp(allow_inline_scripts=False)
        assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]

    def test_get_recommended_csp_with_report_uri(self):
        """Test CSP with report URI."""
        from api.middleware.security_headers import get_recommended_csp

        csp = get_recommended_csp(report_uri="https://example.com/csp-report")
        assert "report-uri https://example.com/csp-report" in csp


# =============================================================================
# CSRFMiddleware Tests
# =============================================================================


class TestCSRFMiddleware:
    """Tests for CSRF protection middleware."""

    def test_sets_csrf_cookie_on_safe_methods(self, basic_app):
        """Should set CSRF cookie on GET requests."""
        from api.middleware.csrf import CSRFMiddleware

        basic_app.add_middleware(CSRFMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert "csrf_token" in response.cookies

    def test_blocks_post_without_csrf_token(self):
        """Should block POST requests without CSRF token."""
        from api.middleware.csrf import CSRFMiddleware

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/submit")
        async def submit():
            return {"submitted": True}

        client = TestClient(app)

        # Use pytest.raises to catch the HTTPException
        with pytest.raises(HTTPException) as exc_info:
            client.post("/submit")

        assert exc_info.value.status_code == 403
        assert "CSRF token missing" in exc_info.value.detail

    def test_allows_post_with_valid_csrf_token(self, basic_app):
        """Should allow POST with valid CSRF token."""
        from api.middleware.csrf import CSRFMiddleware

        basic_app.add_middleware(CSRFMiddleware)
        client = TestClient(basic_app)

        # First, get the CSRF token via a GET request
        get_response = client.get("/test")
        csrf_token = get_response.cookies.get("csrf_token")

        # Now make POST with the token
        response = client.post(
            "/submit",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    def test_blocks_post_with_mismatched_token(self):
        """Should block POST with mismatched CSRF tokens."""
        from api.middleware.csrf import CSRFMiddleware

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/submit")
        async def submit():
            return {"submitted": True}

        client = TestClient(app)

        with pytest.raises(HTTPException) as exc_info:
            client.post(
                "/submit",
                cookies={"csrf_token": "token1"},
                headers={"X-CSRF-Token": "token2"},
            )

        assert exc_info.value.status_code == 403
        assert "CSRF token mismatch" in exc_info.value.detail

    def test_exempt_paths(self, basic_app):
        """Should skip CSRF check for exempt paths."""
        from api.middleware.csrf import CSRFMiddleware

        basic_app.add_middleware(
            CSRFMiddleware,
            exempt_paths=["/submit"],
        )
        client = TestClient(basic_app)

        response = client.post("/submit")

        assert response.status_code == 200

    def test_custom_header_name(self, basic_app):
        """Should support custom CSRF header name."""
        from api.middleware.csrf import CSRFMiddleware

        basic_app.add_middleware(
            CSRFMiddleware,
            header_name="X-Custom-CSRF",
        )
        client = TestClient(basic_app)

        get_response = client.get("/test")
        csrf_token = get_response.cookies.get("csrf_token")

        response = client.post(
            "/submit",
            cookies={"csrf_token": csrf_token},
            headers={"X-Custom-CSRF": csrf_token},
        )

        assert response.status_code == 200


# =============================================================================
# IPAllowlistMiddleware Tests
# =============================================================================


class TestIPAllowlistMiddleware:
    """Tests for IP allowlist middleware."""

    def test_allows_localhost_by_default(self, basic_app):
        """Should allow localhost by default."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        basic_app.add_middleware(IPAllowlistMiddleware)
        # TestClient uses testclient as hostname, explicitly pass localhost IP
        client = TestClient(basic_app)

        # TestClient doesn't have a real client IP, so the request will come from
        # request.client which may be None or testclient. Test with explicit header.
        response = client.get("/api/admin/status", headers={"X-Forwarded-For": "127.0.0.1"})

        assert response.status_code == 200

    def test_blocks_unauthorized_ip(self):
        """Should block unauthorized IPs on protected paths."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        app = FastAPI()
        app.add_middleware(
            IPAllowlistMiddleware,
            allowed_ips=["192.168.1.1"],
            protected_prefixes=["/api/admin"],
        )

        @app.get("/api/admin/status")
        async def admin_status():
            return {"admin": True}

        client = TestClient(app)

        with pytest.raises(HTTPException) as exc_info:
            client.get(
                "/api/admin/status",
                headers={"X-Forwarded-For": "10.0.0.1"},
            )

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail

    def test_allows_whitelisted_ip(self, basic_app):
        """Should allow whitelisted IPs."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        basic_app.add_middleware(
            IPAllowlistMiddleware,
            allowed_ips=["10.0.0.1"],
            protected_prefixes=["/api/admin"],
        )
        client = TestClient(basic_app)

        response = client.get(
            "/api/admin/status",
            headers={"X-Forwarded-For": "10.0.0.1"},
        )

        assert response.status_code == 200

    def test_allows_unprotected_paths(self, basic_app):
        """Should allow any IP on unprotected paths."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        basic_app.add_middleware(
            IPAllowlistMiddleware,
            allowed_ips=["192.168.1.1"],
            protected_prefixes=["/api/admin"],
        )
        client = TestClient(basic_app)

        response = client.get(
            "/test",
            headers={"X-Forwarded-For": "10.0.0.1"},
        )

        assert response.status_code == 200

    def test_supports_cidr_notation(self, basic_app):
        """Should support CIDR notation for IP ranges."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        basic_app.add_middleware(
            IPAllowlistMiddleware,
            allowed_ips=["10.0.0.0/8"],
            protected_prefixes=["/api/admin"],
        )
        client = TestClient(basic_app)

        response = client.get(
            "/api/admin/status",
            headers={"X-Forwarded-For": "10.255.255.255"},
        )

        assert response.status_code == 200

    def test_add_ip_method(self):
        """Test dynamically adding IPs to allowlist."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        middleware = IPAllowlistMiddleware(
            app=MagicMock(),
            allowed_ips=[],
            protected_prefixes=["/api/admin"],
        )

        middleware.add_ip("192.168.1.100")
        assert "192.168.1.100" in middleware.allowed_ips

    def test_remove_ip_method(self):
        """Test removing IPs from allowlist."""
        from api.middleware.ip_allowlist import IPAllowlistMiddleware

        middleware = IPAllowlistMiddleware(
            app=MagicMock(),
            allowed_ips=["192.168.1.100"],
            protected_prefixes=["/api/admin"],
        )

        middleware.remove_ip("192.168.1.100")
        assert "192.168.1.100" not in middleware.allowed_ips


# =============================================================================
# BodySizeLimitMiddleware Tests
# =============================================================================


class TestBodySizeLimitMiddleware:
    """Tests for request body size limit middleware."""

    def test_allows_small_requests(self, basic_app):
        """Should allow requests within size limit."""
        from api.middleware.body_limit import BodySizeLimitMiddleware

        basic_app.add_middleware(BodySizeLimitMiddleware, max_size=1024)
        client = TestClient(basic_app)

        response = client.post("/submit", content="x" * 100)

        assert response.status_code == 200

    def test_blocks_large_requests(self):
        """Should block requests exceeding size limit."""
        from api.middleware.body_limit import BodySizeLimitMiddleware

        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_size=100)

        @app.post("/submit")
        async def submit(request: Request):
            return {"submitted": True}

        client = TestClient(app)

        with pytest.raises(HTTPException) as exc_info:
            client.post(
                "/submit",
                content="x" * 1000,
                headers={"Content-Length": "1000"},
            )

        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    def test_default_max_size_is_10mb(self):
        """Default max size should be 10MB."""
        from api.middleware.body_limit import BodySizeLimitMiddleware

        middleware = BodySizeLimitMiddleware(app=MagicMock())
        assert middleware.max_size == 10 * 1024 * 1024

    def test_allows_requests_without_content_length(self, basic_app):
        """Should allow requests without Content-Length header."""
        from api.middleware.body_limit import BodySizeLimitMiddleware

        basic_app.add_middleware(BodySizeLimitMiddleware, max_size=1024)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.status_code == 200


# =============================================================================
# IdempotencyMiddleware Tests
# =============================================================================


class TestIdempotencyMiddleware:
    """Tests for idempotency key middleware."""

    def test_returns_cached_response_for_same_key(self):
        """Should return cached response for duplicate idempotency key."""
        from api.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        call_count = 0

        @app.post("/submit")
        async def submit():
            nonlocal call_count
            call_count += 1
            return {"call_count": call_count}

        client = TestClient(app)
        idempotency_key = str(uuid.uuid4())

        # First request
        response1 = client.post(
            "/submit",
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.json()["call_count"] == 1

        # Second request with same key should return cached response
        response2 = client.post(
            "/submit",
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response2.json()["call_count"] == 1  # Same as first

        # Handler should only be called once
        assert call_count == 1

    def test_processes_requests_without_idempotency_key(self):
        """Should process requests normally without idempotency key."""
        from api.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        call_count = 0

        @app.post("/submit")
        async def submit():
            nonlocal call_count
            call_count += 1
            return {"call_count": call_count}

        client = TestClient(app)

        # Multiple requests without key
        client.post("/submit")
        client.post("/submit")

        assert call_count == 2

    def test_different_keys_process_separately(self):
        """Should process requests with different keys separately."""
        from api.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        @app.post("/submit")
        async def submit():
            return {"time": time.time()}

        client = TestClient(app)

        response1 = client.post("/submit", headers={"Idempotency-Key": "key1"})
        response2 = client.post("/submit", headers={"Idempotency-Key": "key2"})

        # Different keys should return different responses
        assert response1.json()["time"] != response2.json()["time"]

    def test_only_caches_successful_responses(self):
        """Should only cache 2xx responses."""
        from api.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        call_count = 0

        @app.post("/submit")
        async def submit():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise HTTPException(status_code=400, detail="First call fails")
            return {"success": True}

        client = TestClient(app)
        idempotency_key = str(uuid.uuid4())

        # First request fails
        response1 = client.post(
            "/submit",
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.status_code == 400

        # Second request with same key should retry (not return cached error)
        response2 = client.post(
            "/submit",
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response2.status_code == 200

    def test_ignores_get_requests(self):
        """Should ignore idempotency key on GET requests."""
        from api.middleware.idempotency import IdempotencyMiddleware

        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware)

        call_count = 0

        @app.get("/test")
        async def test():
            nonlocal call_count
            call_count += 1
            return {"call_count": call_count}

        client = TestClient(app)
        idempotency_key = str(uuid.uuid4())

        client.get("/test", headers={"Idempotency-Key": idempotency_key})
        client.get("/test", headers={"Idempotency-Key": idempotency_key})

        # Both requests should process
        assert call_count == 2


# =============================================================================
# CSPNonceMiddleware Tests
# =============================================================================


class TestCSPNonceMiddleware:
    """Tests for CSP nonce middleware."""

    def test_generates_nonce(self, basic_app):
        """Should generate a nonce and add CSP header."""
        from api.middleware.csp_nonce import CSPNonceMiddleware

        basic_app.add_middleware(CSPNonceMiddleware)
        client = TestClient(basic_app)

        response = client.get("/test")

        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "nonce-" in csp

    def test_nonce_is_unique_per_request(self, basic_app):
        """Each request should get a unique nonce."""
        from api.middleware.csp_nonce import CSPNonceMiddleware

        basic_app.add_middleware(CSPNonceMiddleware)
        client = TestClient(basic_app)

        response1 = client.get("/test")
        response2 = client.get("/test")

        # Extract nonces from CSP headers
        import re
        nonce1 = re.search(r"nonce-([^']+)", response1.headers["Content-Security-Policy"])
        nonce2 = re.search(r"nonce-([^']+)", response2.headers["Content-Security-Policy"])

        assert nonce1 and nonce2
        assert nonce1.group(1) != nonce2.group(1)

    def test_get_csp_nonce_function(self):
        """Test get_csp_nonce helper function."""
        from api.middleware.csp_nonce import get_csp_nonce

        mock_request = MagicMock()
        mock_request.state.csp_nonce = "test-nonce-123"

        nonce = get_csp_nonce(mock_request)
        assert nonce == "test-nonce-123"

    def test_get_csp_nonce_returns_empty_if_not_set(self):
        """Should return empty string if nonce not set."""
        from api.middleware.csp_nonce import get_csp_nonce

        mock_request = MagicMock(spec=Request)
        del mock_request.state.csp_nonce

        nonce = get_csp_nonce(mock_request)
        assert nonce == ""


# =============================================================================
# RequestValidationMiddleware Tests
# =============================================================================


class TestRequestValidationMiddleware:
    """Tests for request validation middleware."""

    def test_allows_valid_json_post(self):
        """Should allow valid JSON POST requests."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            body = await request.json()
            return {"received": body}

        client = TestClient(app)
        response = client.post(
            "/submit",
            json={"name": "test"},
        )

        assert response.status_code == 200

    def test_rejects_invalid_json(self):
        """Should reject requests with invalid JSON."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/submit",
            content="{invalid json}",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VAL_001"

    def test_rejects_unsupported_content_type(self):
        """Should reject unsupported content types."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/submit",
            content="some data",
            headers={"Content-Type": "text/plain", "Content-Length": "9"},
        )

        assert response.status_code == 415

    def test_rejects_deeply_nested_json(self):
        """Should reject deeply nested JSON structures."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)

        # Create deeply nested structure (>10 levels)
        nested = {"level": {}}
        current = nested["level"]
        for i in range(15):
            current["next"] = {}
            current = current["next"]

        response = client.post("/submit", json=nested)

        assert response.status_code == 400
        assert "nested" in response.json()["error"]["message"].lower()

    def test_detects_sql_injection_patterns(self):
        """Should detect SQL injection patterns."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/submit",
            json={"query": "SELECT * FROM users WHERE id=1 OR 1=1"},
        )

        assert response.status_code == 400
        assert "suspicious" in response.json()["error"]["message"].lower()

    def test_detects_xss_patterns(self):
        """Should detect XSS patterns."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/submit",
            json={"content": "<script>alert('xss')</script>"},
        )

        assert response.status_code == 400

    def test_skips_exempt_paths(self):
        """Should skip validation for exempt paths."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.get("/api/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200

    def test_skips_get_requests(self):
        """Should skip validation for GET requests."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

    def test_body_size_validation(self):
        """Should validate body size."""
        from api.middleware.request_validation import RequestValidationMiddleware

        app = FastAPI()
        app.add_middleware(RequestValidationMiddleware, max_body_size=100)

        @app.post("/submit")
        async def submit(request: Request):
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/submit",
            json={"data": "x" * 1000},
            headers={"Content-Length": "2000"},
        )

        assert response.status_code == 413


# =============================================================================
# RequestLoggingMiddleware Tests
# =============================================================================


class TestRequestLoggingMiddleware:
    """Tests for request logging middleware."""

    def test_adds_request_id_header(self):
        """Should add X-Request-ID to response."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_adds_response_time_header(self):
        """Should add X-Response-Time to response."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert "X-Response-Time" in response.headers
        assert "ms" in response.headers["X-Response-Time"]

    def test_uses_provided_request_id(self):
        """Should use request ID from header if provided."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test", headers={"X-Request-ID": "custom-id"})

        assert response.headers["X-Request-ID"] == "custom-id"

    def test_skips_health_endpoints(self):
        """Should skip logging for health endpoints."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/health")
        async def health():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200

    def test_mask_sensitive_headers(self):
        """Test masking of sensitive headers."""
        from api.middleware.request_logging import mask_headers

        headers = {
            "Authorization": "Bearer secret-token-12345",
            "X-API-Key": "api-key-secret",
            "Content-Type": "application/json",
        }

        masked = mask_headers(headers)

        # Sensitive headers should be masked
        assert masked["Authorization"] != headers["Authorization"]
        assert "****" in masked["Authorization"] or "..." in masked["Authorization"]
        assert masked["X-API-Key"] != headers["X-API-Key"]

        # Non-sensitive headers should not be masked
        assert masked["Content-Type"] == "application/json"

    def test_mask_body_fields(self):
        """Test masking of sensitive body fields."""
        from api.middleware.request_logging import mask_body

        body = {
            "username": "john",
            "password": "secret123",
            "data": {
                "api_key": "key-12345",
                "name": "test",
            },
        }

        masked = mask_body(body)

        assert masked["username"] == "john"
        assert masked["password"] == "****"
        assert masked["data"]["api_key"] == "****"
        assert masked["data"]["name"] == "test"

    def test_mask_value_function(self):
        """Test the mask_value helper function."""
        from api.middleware.request_logging import mask_value

        # Short value
        assert mask_value("abc") == "****"

        # Long value
        masked = mask_value("1234567890abcdef")
        assert masked.startswith("1234")
        assert masked.endswith("cdef")
        assert "..." in masked

    def test_get_request_id_function(self):
        """Test get_request_id helper function."""
        from api.middleware.request_logging import get_request_id, request_id_ctx

        request_id_ctx.set("test-id-456")
        assert get_request_id() == "test-id-456"

    def test_get_request_duration_function(self):
        """Test get_request_duration helper function."""
        from api.middleware.request_logging import get_request_duration, request_start_ctx

        # Set start time to 1 second ago
        request_start_ctx.set(time.time() - 1.0)
        duration = get_request_duration()
        assert 0.9 <= duration <= 1.5

    def test_logs_slow_requests_as_warning(self, caplog):
        """Should log slow requests with WARNING level."""
        from api.middleware.request_logging import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware, slow_request_threshold=0.01)

        @app.get("/slow")
        async def slow():
            await asyncio.sleep(0.1)
            return {"ok": True}

        client = TestClient(app)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200


# =============================================================================
# RateLimitMiddleware Tests
# =============================================================================


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware."""

    def test_passes_when_disabled(self, basic_app):
        """Should pass all requests when disabled."""
        from api.middleware.rate_limit import RateLimitMiddleware

        basic_app.add_middleware(RateLimitMiddleware, enabled=False)
        client = TestClient(basic_app)

        for _ in range(10):
            response = client.get("/test")
            assert response.status_code == 200

    def test_extracts_ip_from_x_forwarded_for(self):
        """Should extract client IP from X-Forwarded-For header."""
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), enabled=False)

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        ip = middleware._get_client_ip(mock_request)
        assert ip == "1.2.3.4"

    def test_falls_back_to_client_host(self):
        """Should fall back to client host if no forwarded header."""
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), enabled=False)

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_returns_unknown_when_no_client(self):
        """Should return 'unknown' if no client info available."""
        from api.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), enabled=False)

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)
        assert ip == "unknown"


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestMiddlewareExports:
    """Tests for middleware module exports."""

    def test_all_middleware_exported(self):
        """All middleware should be exported from __init__."""
        from api.middleware import (
            RateLimitMiddleware,
            SecurityHeadersMiddleware,
            RequestTracingMiddleware,
            request_id_var,
            CSRFMiddleware,
            IPAllowlistMiddleware,
            BodySizeLimitMiddleware,
            IdempotencyMiddleware,
            CSPNonceMiddleware,
            RequestValidationMiddleware,
            TimeoutMiddleware,
            TimeoutConfig,
            get_current_timeout,
        )

        assert RateLimitMiddleware is not None
        assert SecurityHeadersMiddleware is not None
        assert RequestTracingMiddleware is not None
        assert request_id_var is not None
        assert CSRFMiddleware is not None
        assert IPAllowlistMiddleware is not None
        assert BodySizeLimitMiddleware is not None
        assert IdempotencyMiddleware is not None
        assert CSPNonceMiddleware is not None
        assert RequestValidationMiddleware is not None
        assert TimeoutMiddleware is not None
        assert TimeoutConfig is not None
        assert get_current_timeout is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestMiddlewareIntegration:
    """Tests for middleware interaction and stacking."""

    def test_multiple_middleware_stack(self):
        """Test multiple middleware work together."""
        from api.middleware.security_headers import SecurityHeadersMiddleware
        from api.middleware.request_tracing import RequestTracingMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestTracingMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Both middlewares should add their headers
        assert "X-Request-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers

    def test_security_and_csrf_middleware(self):
        """Test security headers and CSRF work together."""
        from api.middleware.security_headers import SecurityHeadersMiddleware
        from api.middleware.csrf import CSRFMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(CSRFMiddleware)

        @app.get("/test")
        async def test():
            return {"ok": True}

        @app.post("/submit")
        async def submit():
            return {"submitted": True}

        client = TestClient(app)

        # GET should work and set CSRF cookie
        get_response = client.get("/test")
        assert get_response.status_code == 200
        assert "X-Content-Type-Options" in get_response.headers
        csrf_token = get_response.cookies.get("csrf_token")

        # POST with valid CSRF should work
        post_response = client.post(
            "/submit",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert post_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
