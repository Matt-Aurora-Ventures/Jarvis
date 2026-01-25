"""Tests for enhanced error types.

These tests verify the error type hierarchy for proper error classification,
retry behavior, and user-friendly formatting.
"""

import pytest
from core.errors.types import (
    JarvisError,
    TransientError,
    PermanentError,
    QuotaExceededError,
    PermissionDeniedError,
    CircuitOpenError,
    RetryableError,
    ServiceUnavailableError,
)


class TestJarvisErrorHierarchy:
    """Test error class hierarchy."""

    def test_transient_error_is_jarvis_error(self):
        """TransientError should inherit from JarvisError."""
        err = TransientError("Temporary failure")
        assert isinstance(err, JarvisError)
        assert err.is_retryable is True

    def test_permanent_error_is_not_retryable(self):
        """PermanentError should not be retryable."""
        err = PermanentError("Configuration invalid")
        assert isinstance(err, JarvisError)
        assert err.is_retryable is False

    def test_quota_exceeded_has_retry_after(self):
        """QuotaExceededError should have retry_after attribute."""
        err = QuotaExceededError("API quota exceeded", retry_after=300)
        assert isinstance(err, JarvisError)
        assert err.retry_after == 300
        assert err.is_retryable is True

    def test_permission_denied_is_permanent(self):
        """PermissionDeniedError should be permanent."""
        err = PermissionDeniedError("Access denied")
        assert isinstance(err, JarvisError)
        assert err.is_retryable is False

    def test_circuit_open_error(self):
        """CircuitOpenError should indicate service unavailable."""
        err = CircuitOpenError("Service X circuit is open")
        assert isinstance(err, JarvisError)
        assert err.service_name is not None or "circuit" in str(err).lower()

    def test_retryable_error_interface(self):
        """RetryableError should have suggested_delay."""
        err = RetryableError("Network hiccup", suggested_delay=5.0)
        assert err.suggested_delay == 5.0
        assert err.is_retryable is True

    def test_service_unavailable_error(self):
        """ServiceUnavailableError for external service failures."""
        err = ServiceUnavailableError("Jupiter API down", service="jupiter")
        assert err.service == "jupiter"
        assert err.is_retryable is True


class TestErrorSerialization:
    """Test error serialization for logging and API responses."""

    def test_error_to_dict(self):
        """Errors should serialize to dict."""
        err = TransientError("Temp fail", details={"attempt": 3})
        data = err.to_dict()
        assert "code" in data
        assert "message" in data
        assert data["message"] == "Temp fail"
        assert data.get("details", {}).get("attempt") == 3

    def test_error_from_dict(self):
        """Errors should deserialize from dict."""
        data = {
            "code": "TRANS_001",
            "message": "Network timeout",
            "type": "TransientError",
            "is_retryable": True
        }
        # This tests the from_dict class method
        err = JarvisError.from_dict(data)
        assert err.message == "Network timeout"

    def test_error_code_format(self):
        """Error codes should follow pattern: CATEGORY_NNN."""
        import re
        err = QuotaExceededError("Quota hit")
        assert re.match(r"^[A-Z]+_\d{3}$", err.code)


class TestErrorContext:
    """Test error context and chaining."""

    def test_error_with_cause(self):
        """Errors should preserve original exception."""
        original = ValueError("invalid data")
        err = TransientError("Processing failed", cause=original)
        assert err.__cause__ == original or err.cause == original

    def test_error_chain_preserves_stack(self):
        """Error chain should preserve full stack."""
        try:
            try:
                raise ConnectionError("Socket closed")
            except ConnectionError as e:
                raise TransientError("Network error") from e
        except TransientError as te:
            assert te.__cause__ is not None
            assert isinstance(te.__cause__, ConnectionError)

    def test_error_context_metadata(self):
        """Errors should support arbitrary context."""
        err = TransientError(
            "API call failed",
            context={
                "endpoint": "/api/v1/tokens",
                "method": "GET",
                "status_code": 503
            }
        )
        assert err.context["endpoint"] == "/api/v1/tokens"
        assert err.context["status_code"] == 503
