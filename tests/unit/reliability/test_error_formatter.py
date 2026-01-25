"""Tests for user-friendly error formatting.

These tests verify that errors are formatted appropriately for end users
in Telegram and other interfaces.
"""

import pytest


class TestErrorFormatter:
    """Test error formatting for users."""

    def test_format_quota_exceeded(self):
        """QuotaExceededError should format with wait time."""
        from core.reliability.error_formatter import format_error_for_user
        from core.errors.types import QuotaExceededError

        err = QuotaExceededError("API quota exceeded", retry_after=300)
        msg = format_error_for_user(err)

        assert "quota" in msg.lower() or "limit" in msg.lower()
        assert "5 min" in msg.lower() or "wait" in msg.lower()

    def test_format_transient_error(self):
        """TransientError should suggest retrying."""
        from core.reliability.error_formatter import format_error_for_user
        from core.errors.types import TransientError

        err = TransientError("Connection dropped")
        msg = format_error_for_user(err)

        assert "retry" in msg.lower() or "trying" in msg.lower()

    def test_format_permission_denied(self):
        """PermissionDeniedError should be clear about access."""
        from core.reliability.error_formatter import format_error_for_user
        from core.errors.types import PermissionDeniedError

        err = PermissionDeniedError("Admin only")
        msg = format_error_for_user(err)

        assert "permission" in msg.lower() or "access" in msg.lower()

    def test_format_circuit_open(self):
        """CircuitOpenError should indicate service issue."""
        from core.reliability.error_formatter import format_error_for_user
        from core.errors.types import CircuitOpenError

        err = CircuitOpenError("Jupiter API circuit open", service_name="jupiter")
        msg = format_error_for_user(err)

        assert "service" in msg.lower() or "unavailable" in msg.lower()

    def test_format_unknown_error(self):
        """Unknown errors should have safe fallback."""
        from core.reliability.error_formatter import format_error_for_user

        err = RuntimeError("Internal processing error with sensitive data")
        msg = format_error_for_user(err)

        # Should not leak sensitive details
        assert "sensitive" not in msg.lower()
        assert len(msg) < 200  # Not too verbose

    def test_format_with_emoji(self):
        """Should include appropriate emoji for error type."""
        from core.reliability.error_formatter import format_error_for_user
        from core.errors.types import QuotaExceededError, TransientError

        quota_msg = format_error_for_user(QuotaExceededError("limit"))
        transient_msg = format_error_for_user(TransientError("temp"))

        # Should have some visual indicator
        assert any(c in quota_msg for c in ["!", "warning", "limit"])
        assert any(c in transient_msg for c in ["!", "retry"])


class TestErrorFormatterTelegram:
    """Test Telegram-specific formatting."""

    def test_telegram_markdown_escaping(self):
        """Should escape Markdown special chars for Telegram."""
        from core.reliability.error_formatter import format_for_telegram
        from core.errors.types import TransientError

        err = TransientError("Error with *bold* and _italic_")
        msg = format_for_telegram(err)

        # Telegram MarkdownV2 requires escaping
        assert "*bold*" not in msg or "\\*" in msg

    def test_telegram_max_length(self):
        """Should truncate very long messages."""
        from core.reliability.error_formatter import format_for_telegram

        err = RuntimeError("x" * 5000)
        msg = format_for_telegram(err)

        assert len(msg) <= 4096  # Telegram limit

    def test_telegram_action_buttons_hint(self):
        """Should suggest actions when appropriate."""
        from core.reliability.error_formatter import format_for_telegram
        from core.errors.types import QuotaExceededError

        err = QuotaExceededError("limit", retry_after=60)
        msg = format_for_telegram(err, include_actions=True)

        # Should suggest what user can do
        assert "try again" in msg.lower() or "later" in msg.lower()


class TestErrorFormatterStructured:
    """Test structured error responses for API."""

    def test_structured_response_format(self):
        """Should produce structured JSON-ready dict."""
        from core.reliability.error_formatter import format_structured
        from core.errors.types import TransientError

        err = TransientError("temp failure", context={"endpoint": "/api/trade"})
        response = format_structured(err)

        assert isinstance(response, dict)
        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert "retryable" in response["error"]

    def test_structured_includes_retry_info(self):
        """Should include retry information when applicable."""
        from core.reliability.error_formatter import format_structured
        from core.errors.types import QuotaExceededError

        err = QuotaExceededError("limit", retry_after=120)
        response = format_structured(err)

        assert response["error"]["retry_after"] == 120
        assert response["error"]["retryable"] is True

    def test_structured_hides_sensitive_details(self):
        """Should not expose sensitive information."""
        from core.reliability.error_formatter import format_structured

        err = RuntimeError("Database password 'secret123' invalid")
        response = format_structured(err)

        response_str = str(response)
        assert "secret123" not in response_str
        assert "password" not in response_str.lower() or "***" in response_str


class TestErrorSuggestions:
    """Test error resolution suggestions."""

    def test_suggest_for_rate_limit(self):
        """Should suggest waiting for rate limits."""
        from core.reliability.error_formatter import get_suggestions
        from core.errors.types import QuotaExceededError

        err = QuotaExceededError("Rate limited", retry_after=60)
        suggestions = get_suggestions(err)

        assert any("wait" in s.lower() for s in suggestions)

    def test_suggest_for_connection_error(self):
        """Should suggest checking connection."""
        from core.reliability.error_formatter import get_suggestions
        from core.errors.types import TransientError

        err = TransientError("Connection refused")
        suggestions = get_suggestions(err)

        assert len(suggestions) > 0

    def test_suggest_for_permission_error(self):
        """Should suggest checking permissions."""
        from core.reliability.error_formatter import get_suggestions
        from core.errors.types import PermissionDeniedError

        err = PermissionDeniedError("Admin required")
        suggestions = get_suggestions(err)

        assert any("admin" in s.lower() or "permission" in s.lower() for s in suggestions)
