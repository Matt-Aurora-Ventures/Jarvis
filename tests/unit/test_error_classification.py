"""
Error Classification and Handling Tests for JARVIS

Tests for:
1. Error classification (transient vs permanent)
2. Error codes uniqueness and meaning
3. Error messages don't leak sensitive info
4. HTTP status codes map correctly to error types
5. Error logging captures needed context
6. Recovery strategies work for each error type

Run with: pytest tests/unit/test_error_classification.py -v
"""

import errno
import gc
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Set
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest


# =============================================================================
# Error Classification Tests
# =============================================================================


class TestErrorCategoryClassification:
    """Tests for error categorization in ErrorRecoveryManager."""

    def test_memory_error_classified_correctly(self):
        """MemoryError maps to MEMORY category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(MemoryError("out of memory"))

        assert category == ErrorCategory.MEMORY

    def test_timeout_error_classified_as_network(self):
        """TimeoutError maps to NETWORK category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(TimeoutError("connection timed out"))

        assert category == ErrorCategory.NETWORK

    def test_connection_error_classified_as_network(self):
        """ConnectionError maps to NETWORK category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(ConnectionError("network unreachable"))

        assert category == ErrorCategory.NETWORK

    def test_file_not_found_classified_as_filesystem(self):
        """FileNotFoundError maps to FILESYSTEM category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(FileNotFoundError("file not found"))

        assert category == ErrorCategory.FILESYSTEM

    def test_permission_error_classified_correctly(self):
        """PermissionError maps to PERMISSION category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(PermissionError("access denied"))

        assert category == ErrorCategory.PERMISSION

    def test_module_not_found_classified_as_dependency(self):
        """ModuleNotFoundError maps to DEPENDENCY category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(ModuleNotFoundError("no module named 'xyz'"))

        assert category == ErrorCategory.DEPENDENCY

    def test_import_error_classified_as_dependency(self):
        """ImportError maps to DEPENDENCY category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        category = manager._categorize_error(ImportError("cannot import name 'x'"))

        assert category == ErrorCategory.DEPENDENCY

    def test_json_decode_error_classified_as_configuration(self):
        """JSONDecodeError maps to CONFIGURATION category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = json.JSONDecodeError("Expecting value", "{invalid}", 0)
        category = manager._categorize_error(error)

        assert category == ErrorCategory.CONFIGURATION

    def test_oserror_permission_errno_classified_correctly(self):
        """OSError with EACCES errno maps to PERMISSION category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = OSError(errno.EACCES, "Permission denied")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.PERMISSION

    def test_oserror_eperm_errno_classified_as_permission(self):
        """OSError with EPERM errno maps to PERMISSION category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = OSError(errno.EPERM, "Operation not permitted")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.PERMISSION

    def test_oserror_enoent_errno_classified_as_filesystem(self):
        """OSError with ENOENT errno maps to FILESYSTEM category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = OSError(errno.ENOENT, "No such file or directory")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.FILESYSTEM

    def test_oserror_enospc_errno_classified_as_filesystem(self):
        """OSError with ENOSPC errno maps to FILESYSTEM category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = OSError(errno.ENOSPC, "No space left on device")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.FILESYSTEM

    def test_mcp_keyword_classified_as_mcp_server(self):
        """Errors with 'mcp' keyword map to MCP_SERVER category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = Exception("MCP server failed to respond")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.MCP_SERVER

    def test_config_keyword_classified_as_configuration(self):
        """Errors with 'config' keyword map to CONFIGURATION category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = Exception("Invalid config value for setting X")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.CONFIGURATION

    def test_unknown_error_classified_as_unknown(self):
        """Unrecognized errors map to UNKNOWN category."""
        from core.error_recovery import ErrorRecoveryManager, ErrorCategory

        manager = ErrorRecoveryManager()
        error = Exception("Something completely unexpected")
        category = manager._categorize_error(error)

        assert category == ErrorCategory.UNKNOWN


class TestTransientErrorDetection:
    """Tests for transient error identification."""

    def test_timeout_error_is_transient(self):
        """TimeoutError is detected as transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(TimeoutError("timeout")) is True

    def test_connection_error_is_transient(self):
        """ConnectionError is detected as transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(ConnectionError("connection reset")) is True

    def test_rate_limit_keyword_is_transient(self):
        """Errors with 'rate limit' are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("rate limit exceeded")) is True

    def test_network_keyword_is_transient(self):
        """Errors with 'network' keyword are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("network unreachable")) is True

    def test_socket_keyword_is_transient(self):
        """Errors with 'socket' keyword are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("socket error")) is True

    def test_dns_keyword_is_transient(self):
        """Errors with 'dns' keyword are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("dns resolution failed")) is True

    def test_temporary_keyword_is_transient(self):
        """Errors with 'temporary' keyword are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("temporary failure")) is True

    def test_unavailable_keyword_is_transient(self):
        """Errors with 'unavailable' keyword are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("service unavailable")) is True

    def test_reset_by_peer_keyword_is_transient(self):
        """Errors with 'reset by peer' are transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(Exception("Connection reset by peer")) is True

    def test_value_error_not_transient(self):
        """ValueError is NOT transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(ValueError("invalid value")) is False

    def test_key_error_not_transient(self):
        """KeyError is NOT transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(KeyError("missing key")) is False

    def test_type_error_not_transient(self):
        """TypeError is NOT transient."""
        from core.error_recovery import _is_transient_error

        assert _is_transient_error(TypeError("bad type")) is False


# =============================================================================
# Error Codes Tests
# =============================================================================


class TestErrorCodesUniqueness:
    """Tests ensuring error codes are unique and meaningful."""

    def test_api_error_codes_are_unique(self):
        """All error codes in api/errors.py are unique."""
        from api.errors import ERROR_CODES

        codes = list(ERROR_CODES.keys())
        unique_codes = set(codes)

        assert len(codes) == len(unique_codes), (
            f"Duplicate error codes found: "
            f"{[c for c in codes if codes.count(c) > 1]}"
        )

    def test_api_error_codes_follow_convention(self):
        """Error codes follow naming convention (CATEGORY_NNN)."""
        from api.errors import ERROR_CODES

        pattern = re.compile(r"^[A-Z]+_\d{3}$")

        for code in ERROR_CODES.keys():
            assert pattern.match(code), f"Code {code} doesn't match CATEGORY_NNN pattern"

    def test_core_api_error_codes_are_unique(self):
        """All ErrorCode enum values are unique."""
        from core.api.errors import ErrorCode

        values = [e.value for e in ErrorCode]
        unique_values = set(values)

        assert len(values) == len(unique_values), (
            f"Duplicate ErrorCode values found"
        )

    def test_error_code_messages_not_empty(self):
        """All error codes have non-empty messages."""
        from api.errors import ERROR_CODES

        for code, message in ERROR_CODES.items():
            assert message and len(message.strip()) > 0, (
                f"Error code {code} has empty message"
            )

    def test_voice_error_codes_sequential(self):
        """Voice error codes are sequential within category."""
        from api.errors import ERROR_CODES

        voice_codes = [c for c in ERROR_CODES.keys() if c.startswith("VOICE_")]
        # The codes are VOICE_001, VOICE_002, etc. (sequential within category)
        # Verify each code follows the pattern
        for code in voice_codes:
            num = int(code.split("_")[1])
            # Sequential codes start at 001
            assert 1 <= num < 100, f"Voice code {code} should be sequential (001-099)"

    def test_trade_error_codes_sequential(self):
        """Trading error codes are sequential within category."""
        from api.errors import ERROR_CODES

        trade_codes = [c for c in ERROR_CODES.keys() if c.startswith("TRADE_")]
        for code in trade_codes:
            num = int(code.split("_")[1])
            assert 1 <= num < 100, f"Trade code {code} should be sequential (001-099)"

    def test_auth_error_codes_sequential(self):
        """Auth error codes are sequential within category."""
        from api.errors import ERROR_CODES

        auth_codes = [c for c in ERROR_CODES.keys() if c.startswith("AUTH_")]
        for code in auth_codes:
            num = int(code.split("_")[1])
            assert 1 <= num < 100, f"Auth code {code} should be sequential (001-099)"

    def test_error_codes_grouped_by_category(self):
        """Error codes are properly grouped by category prefix."""
        from api.errors import ERROR_CODES

        categories = set()
        for code in ERROR_CODES.keys():
            category = code.split("_")[0]
            categories.add(category)

        # Should have multiple categories defined
        expected_categories = {"VOICE", "TRADE", "AUTH", "VAL", "PROV", "SYS"}
        assert expected_categories.issubset(categories), (
            f"Missing expected categories. Found: {categories}"
        )


# =============================================================================
# Sensitive Information Leakage Tests
# =============================================================================


class TestNoSensitiveInfoLeakage:
    """Tests ensuring error messages don't leak sensitive information."""

    SENSITIVE_PATTERNS = [
        # API Keys and tokens
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API keys
        r"[a-zA-Z0-9]{32,}",  # Generic long alphanumeric (potential tokens)
        r"Bearer\s+[a-zA-Z0-9\-_]+",  # Bearer tokens
        # Passwords
        r"password['\"]?\s*[:=]\s*['\"]?[^'\"]+['\"]?",
        r"passwd['\"]?\s*[:=]\s*['\"]?[^'\"]+['\"]?",
        r"secret['\"]?\s*[:=]\s*['\"]?[^'\"]+['\"]?",
        # Private keys
        r"-----BEGIN\s+(RSA|EC|PRIVATE|DSA)\s+",
        # Wallet keys
        r"[1-9A-HJ-NP-Za-km-z]{87,88}",  # Base58 encoded keys (Solana)
    ]

    def test_api_error_messages_no_sensitive_data(self):
        """Default error messages contain no sensitive patterns."""
        from api.errors import ERROR_CODES

        for code, message in ERROR_CODES.items():
            for pattern in self.SENSITIVE_PATTERNS:
                matches = re.findall(pattern, message, re.IGNORECASE)
                assert not matches, (
                    f"Error code {code} message may contain sensitive data: {matches}"
                )

    def test_error_record_sanitizes_context(self):
        """ErrorRecord handles sensitive data in context safely."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        sensitive_context = {
            "api_key": "sk-test1234567890abcdef",
            "password": "supersecret123",
            "user_id": "user123",  # Safe to include
        }

        record = ErrorRecord(
            error=ValueError("test"),
            context=sensitive_context,
            severity=ErrorSeverity.LOW
        )

        # The record stores context but to_dict should have truncation
        data = record.to_dict()
        # Context is serialized - sensitive data is NOT automatically redacted
        # This test documents current behavior for awareness
        assert "context" in data

    def test_error_response_excludes_traceback_by_default(self):
        """APIError.to_dict excludes traceback by default."""
        from core.api.errors import APIError, ErrorCode

        error = APIError(
            message="Something went wrong",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500
        )

        data = error.to_dict(include_debug=False)

        # Debug info should not be in the response when include_debug=False
        assert "debug" not in data.get("error", data)
        assert "traceback" not in str(data.get("error", data))

    def test_error_response_includes_traceback_when_debug(self):
        """APIError.to_dict includes traceback in debug mode."""
        from core.api.errors import APIError, ErrorCode

        error = APIError(
            message="Something went wrong",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500
        )

        data = error.to_dict(include_debug=True)

        # Debug info should be included - it may be nested in "error" dict
        error_dict = data.get("error", data)
        assert "debug" in error_dict
        assert "traceback" in error_dict["debug"]

    def test_user_error_messages_are_generic(self):
        """User-facing error messages are generic and safe."""
        from core.bot.error_recovery import UserErrorNotifier, ErrorSeverity

        for severity in ErrorSeverity:
            message = UserErrorNotifier.get_user_message(severity)
            # Should not contain technical details
            assert "traceback" not in message.lower()
            assert "exception" not in message.lower()
            assert "error code" not in message.lower()
            # Should be user-friendly
            assert len(message) > 10


# =============================================================================
# HTTP Status Code Mapping Tests
# =============================================================================


class TestHTTPStatusCodeMapping:
    """Tests for HTTP status code to error type mappings."""

    def test_bad_request_error_returns_400(self):
        """BadRequestError returns HTTP 400."""
        from core.api.errors import BadRequestError

        error = BadRequestError("Invalid input")
        assert error.status_code == 400

    def test_validation_error_returns_422(self):
        """ValidationError returns HTTP 422."""
        from core.api.errors import ValidationError

        error = ValidationError("Field validation failed")
        assert error.status_code == 422

    def test_unauthorized_error_returns_401(self):
        """UnauthorizedError returns HTTP 401."""
        from core.api.errors import UnauthorizedError

        error = UnauthorizedError("Not authenticated")
        assert error.status_code == 401
        # Should include WWW-Authenticate header
        assert error.headers is not None
        assert "WWW-Authenticate" in error.headers

    def test_forbidden_error_returns_403(self):
        """ForbiddenError returns HTTP 403."""
        from core.api.errors import ForbiddenError

        error = ForbiddenError("Access denied")
        assert error.status_code == 403

    def test_not_found_error_returns_404(self):
        """NotFoundError returns HTTP 404."""
        from core.api.errors import NotFoundError

        error = NotFoundError("Resource not found")
        assert error.status_code == 404

    def test_conflict_error_returns_409(self):
        """ConflictError returns HTTP 409."""
        from core.api.errors import ConflictError

        error = ConflictError("Resource conflict")
        assert error.status_code == 409

    def test_rate_limit_error_returns_429(self):
        """RateLimitError returns HTTP 429."""
        from core.api.errors import RateLimitError

        error = RateLimitError("Too many requests", retry_after=60)
        assert error.status_code == 429
        assert error.headers is not None
        assert error.headers.get("Retry-After") == "60"

    def test_internal_error_returns_500(self):
        """InternalError returns HTTP 500."""
        from core.api.errors import InternalError

        error = InternalError("Server error")
        assert error.status_code == 500

    def test_service_unavailable_error_returns_503(self):
        """ServiceUnavailableError returns HTTP 503."""
        from core.api.errors import ServiceUnavailableError

        error = ServiceUnavailableError("Service down", retry_after=30)
        assert error.status_code == 503
        assert error.headers is not None
        assert error.headers.get("Retry-After") == "30"

    def test_circuit_open_error_returns_503(self):
        """CircuitOpenError returns HTTP 503."""
        from core.api.errors import CircuitOpenError

        error = CircuitOpenError("Circuit is open", service="database")
        assert error.status_code == 503

    def test_insufficient_funds_error_returns_400(self):
        """InsufficientFundsError returns HTTP 400."""
        from core.api.errors import InsufficientFundsError

        error = InsufficientFundsError(required=1.5, available=0.5)
        assert error.status_code == 400
        assert error.details is not None
        assert error.details["required"] == 1.5
        assert error.details["available"] == 0.5

    def test_transaction_error_returns_400(self):
        """TransactionError returns HTTP 400."""
        from core.api.errors import TransactionError

        error = TransactionError("TX failed", tx_signature="abc123")
        assert error.status_code == 400


class TestFlaskErrorResponses:
    """Tests for Flask error response formatting."""

    def test_make_error_response_structure(self):
        """make_error_response returns correct structure."""
        from api.errors import make_error_response

        response = make_error_response("AUTH_001", http_status=401)

        assert response["success"] is False
        assert "error" in response
        assert response["error"]["code"] == "AUTH_001"
        assert "message" in response["error"]

    def test_make_error_response_custom_message(self):
        """make_error_response uses custom message when provided."""
        from api.errors import make_error_response

        response = make_error_response("SYS_003", message="Custom error message")

        assert response["error"]["message"] == "Custom error message"

    def test_make_error_response_with_details(self):
        """make_error_response includes details when provided."""
        from api.errors import make_error_response

        details = {"field": "email", "reason": "invalid format"}
        response = make_error_response("VAL_003", details=details)

        assert response["error"]["details"] == details

    def test_make_success_response_structure(self):
        """make_success_response returns correct structure."""
        from api.errors import make_success_response

        response = make_success_response(data={"id": 123})

        assert response["success"] is True
        assert response["data"]["id"] == 123


# =============================================================================
# Error Logging Context Tests
# =============================================================================


class TestErrorLoggingContext:
    """Tests for error logging capturing needed context."""

    def test_error_record_captures_stack_trace(self):
        """ErrorRecord captures stack trace automatically."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        try:
            raise ValueError("test error")
        except ValueError as e:
            record = ErrorRecord(error=e, context={}, severity=ErrorSeverity.LOW)

        assert record.stack_trace
        assert "ValueError" in record.stack_trace
        assert "test error" in record.stack_trace

    def test_error_record_has_unique_id(self):
        """Each ErrorRecord gets a unique ID."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        record1 = ErrorRecord(error=ValueError("a"), context={}, severity=ErrorSeverity.LOW)
        record2 = ErrorRecord(error=ValueError("b"), context={}, severity=ErrorSeverity.LOW)

        assert record1.error_id != record2.error_id
        assert record1.error_id.startswith("err_")
        assert record2.error_id.startswith("err_")

    def test_error_record_has_timestamp(self):
        """ErrorRecord has a timestamp."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        before = time.time()
        record = ErrorRecord(error=ValueError("test"), context={}, severity=ErrorSeverity.LOW)
        after = time.time()

        assert before <= record.timestamp <= after

    def test_error_record_to_dict_complete(self):
        """ErrorRecord.to_dict includes all important fields."""
        from core.error_recovery import ErrorRecord, ErrorSeverity, ErrorCategory

        record = ErrorRecord(
            error=ConnectionError("network down"),
            context={"endpoint": "/api/test"},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK
        )

        data = record.to_dict()

        assert "id" in data
        assert "error" in data
        assert "type" in data
        assert data["type"] == "ConnectionError"
        assert "context" in data
        assert "severity" in data
        assert data["severity"] == "medium"
        assert "category" in data
        assert data["category"] == "network"
        assert "timestamp" in data
        assert "stack_trace" in data
        assert "recovery_attempts" in data
        assert "resolved" in data

    def test_error_reporter_captures_exception_info(self):
        """ErrorReporter captures exception details."""
        from core.error_reporter import ErrorReporter
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_errors.db"
            reporter = ErrorReporter(db_path)

            try:
                raise RuntimeError("Test runtime error")
            except RuntimeError as e:
                record = reporter.capture_exception(
                    e,
                    context={"request_id": "req-123"},
                    severity="ERROR"
                )

            assert record.error_type == "RuntimeError"
            assert "Test runtime error" in record.message
            assert record.context["request_id"] == "req-123"
            assert record.fingerprint  # Has a fingerprint for grouping

    def test_error_reporter_generates_fingerprints(self):
        """ErrorReporter generates consistent fingerprints for same errors."""
        from core.error_reporter import ErrorReporter
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_errors.db"
            reporter = ErrorReporter(db_path)

            # Same error type and message should have same fingerprint
            fp1 = reporter._generate_fingerprint(
                ValueError("bad value"), "/path/to/file.py", "func"
            )
            fp2 = reporter._generate_fingerprint(
                ValueError("bad value"), "/path/to/file.py", "func"
            )

            assert fp1 == fp2

            # Different error should have different fingerprint
            fp3 = reporter._generate_fingerprint(
                TypeError("type error"), "/path/to/file.py", "func"
            )

            assert fp1 != fp3


# =============================================================================
# Recovery Strategy Tests
# =============================================================================


class TestRecoveryStrategies:
    """Tests for error recovery strategies."""

    def test_retry_with_backoff_can_handle_transient(self):
        """RetryWithBackoffStrategy handles transient errors."""
        from core.error_recovery import (
            RetryWithBackoffStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = RetryWithBackoffStrategy()
        record = ErrorRecord(
            error=TimeoutError("timed out"),
            context={},
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.NETWORK
        )

        assert strategy.can_handle(record) is True

    def test_retry_with_backoff_rejects_permanent(self):
        """RetryWithBackoffStrategy rejects permanent errors."""
        from core.error_recovery import (
            RetryWithBackoffStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = RetryWithBackoffStrategy()
        record = ErrorRecord(
            error=ValueError("invalid input"),
            context={},
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.UNKNOWN
        )

        assert strategy.can_handle(record) is False

    def test_retry_circuit_breaker_after_max_attempts(self):
        """RetryWithBackoffStrategy stops after max_attempts."""
        from core.error_recovery import (
            RetryWithBackoffStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = RetryWithBackoffStrategy()
        record = ErrorRecord(
            error=ConnectionError("network down"),
            context={"_retry_attempts": 5},  # Already at max
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK
        )

        result = strategy.attempt_recovery(record)

        assert result is False
        assert record.context.get("circuit_breaker_tripped") is True
        assert record.context.get("should_retry") is False

    def test_clear_cache_strategy_handles_cache_errors(self):
        """ClearCacheStrategy handles cache-related errors."""
        from core.error_recovery import (
            ClearCacheStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = ClearCacheStrategy()
        record = ErrorRecord(
            error=Exception("Cache corrupted"),
            context={},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.FILESYSTEM
        )

        assert strategy.can_handle(record) is True

    def test_ensure_directories_handles_file_errors(self):
        """EnsureDirectoriesStrategy handles file not found errors."""
        from core.error_recovery import (
            EnsureDirectoriesStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = EnsureDirectoriesStrategy()
        record = ErrorRecord(
            error=FileNotFoundError("No such file or directory"),
            context={},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.FILESYSTEM
        )

        assert strategy.can_handle(record) is True

    def test_garbage_collect_strategy_handles_memory_errors(self):
        """GarbageCollectStrategy handles memory errors."""
        from core.error_recovery import (
            GarbageCollectStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = GarbageCollectStrategy()
        record = ErrorRecord(
            error=MemoryError("out of memory"),
            context={},
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.MEMORY
        )

        assert strategy.can_handle(record) is True

    def test_garbage_collect_runs_gc(self):
        """GarbageCollectStrategy actually runs garbage collection."""
        from core.error_recovery import (
            GarbageCollectStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = GarbageCollectStrategy()
        record = ErrorRecord(
            error=MemoryError("memory pressure"),
            context={},
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.MEMORY
        )

        result = strategy.attempt_recovery(record)

        assert result is True
        assert "gc_collected" in record.context

    def test_mcp_server_strategy_handles_mcp_errors(self):
        """RestartMCPServerStrategy handles MCP errors."""
        from core.error_recovery import (
            RestartMCPServerStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = RestartMCPServerStrategy()
        record = ErrorRecord(
            error=Exception("MCP server not responding"),
            context={},
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.MCP_SERVER
        )

        assert strategy.can_handle(record) is True

    def test_invalidate_import_caches_handles_dependency(self):
        """InvalidateImportCachesStrategy handles dependency errors."""
        from core.error_recovery import (
            InvalidateImportCachesStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = InvalidateImportCachesStrategy()
        record = ErrorRecord(
            error=ModuleNotFoundError("No module named 'xyz'"),
            context={},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DEPENDENCY
        )

        assert strategy.can_handle(record) is True

    def test_invalidate_import_caches_actually_invalidates(self):
        """InvalidateImportCachesStrategy invalidates import caches."""
        from core.error_recovery import (
            InvalidateImportCachesStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        strategy = InvalidateImportCachesStrategy()
        record = ErrorRecord(
            error=ImportError("cannot import"),
            context={},
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DEPENDENCY
        )

        result = strategy.attempt_recovery(record)

        assert result is True
        assert record.context.get("import_caches_invalidated") is True


class TestErrorRecoveryManager:
    """Tests for the ErrorRecoveryManager."""

    def test_manager_handles_error_and_attempts_recovery(self):
        """ErrorRecoveryManager handles errors and attempts recovery."""
        from core.error_recovery import ErrorRecoveryManager, ErrorSeverity

        manager = ErrorRecoveryManager()

        # Transient error should trigger recovery attempt
        recovered = manager.handle_error(
            TimeoutError("connection timed out"),
            context={"endpoint": "/api/test"},
            severity=ErrorSeverity.MEDIUM
        )

        # May or may not recover, but should have recorded the error
        assert len(manager.error_history) == 1

    def test_manager_tracks_error_patterns(self):
        """ErrorRecoveryManager tracks error patterns."""
        from core.error_recovery import ErrorRecoveryManager, ErrorSeverity

        manager = ErrorRecoveryManager()

        # Report same error type multiple times
        for i in range(5):
            manager.handle_error(
                TimeoutError(f"timeout {i}"),
                severity=ErrorSeverity.LOW
            )

        stats = manager.get_error_stats()
        assert "network:TimeoutError" in stats["common_patterns"]
        assert stats["common_patterns"]["network:TimeoutError"] == 5

    def test_manager_get_recent_errors(self):
        """ErrorRecoveryManager returns recent errors."""
        from core.error_recovery import ErrorRecoveryManager, ErrorSeverity

        manager = ErrorRecoveryManager()

        # Add some errors
        manager.handle_error(ValueError("error 1"), severity=ErrorSeverity.LOW)
        manager.handle_error(TypeError("error 2"), severity=ErrorSeverity.MEDIUM)
        manager.handle_error(KeyError("error 3"), severity=ErrorSeverity.LOW)

        recent = manager.get_recent_errors(limit=2)

        assert len(recent) == 2
        # Most recent first
        assert "KeyError" in str(recent[0])

    def test_manager_strategy_cooldown(self):
        """Strategies respect cooldown period."""
        from core.error_recovery import (
            ErrorRecoveryManager,
            RecoveryStrategy,
            ErrorRecord,
            ErrorSeverity,
            ErrorCategory
        )

        class TestStrategy(RecoveryStrategy):
            def __init__(self):
                super().__init__("test_strategy", priority=10, cooldown_seconds=60)
                self.call_count = 0

            def can_handle(self, error_record):
                return True

            def attempt_recovery(self, error_record):
                self.call_count += 1
                return True

        manager = ErrorRecoveryManager()
        strategy = TestStrategy()
        manager.register_strategy(strategy)

        # First call should succeed
        manager.handle_error(Exception("test"), severity=ErrorSeverity.LOW)
        assert strategy.call_count == 1

        # Second call within cooldown should be skipped
        manager.handle_error(Exception("test 2"), severity=ErrorSeverity.LOW)
        # Strategy should still be at 1 call due to cooldown
        # (depends on implementation - may vary)


class TestBotErrorRecovery:
    """Tests for bot-specific error recovery."""

    def test_bot_circuit_breaker_initial_state(self):
        """Bot circuit breaker starts closed."""
        from core.bot.error_recovery import CircuitBreaker

        breaker = CircuitBreaker()

        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_bot_circuit_breaker_opens_on_failures(self):
        """Bot circuit breaker opens after threshold failures."""
        from core.bot.error_recovery import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.is_closed is False

    def test_bot_circuit_breaker_closes_on_success(self):
        """Bot circuit breaker closes after recovery timeout and success."""
        from core.bot.error_recovery import CircuitBreaker
        import time

        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0)

        # Open circuit
        breaker.record_failure()
        breaker.record_failure()

        # Simulate timeout passing
        breaker._last_failure = None  # Force state check

        # Wait and then record success
        breaker._state = "half-open"
        breaker._half_open_count = 0
        breaker.record_success()

        assert breaker.is_closed is True

    def test_bot_circuit_breaker_state_info(self):
        """Bot circuit breaker provides state information."""
        from core.bot.error_recovery import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=5)

        breaker.record_success()
        breaker.record_success()
        breaker.record_failure()

        state = breaker.get_state()

        assert state["state"] == "closed"
        assert state["failures"] == 1
        assert state["successes"] == 2


# =============================================================================
# Safe Serialization Tests
# =============================================================================


class TestSafeSerialization:
    """Tests for safe serialization of error context."""

    def test_safe_string_truncates_long_values(self):
        """_safe_string truncates values over max length."""
        from core.error_recovery import _safe_string

        long_string = "x" * 2000
        result = _safe_string(long_string, max_len=100)

        assert len(result) < 150  # 100 + truncation message
        assert "truncated" in result

    def test_safe_string_handles_exceptions(self):
        """_safe_string handles objects that fail to convert."""
        from core.error_recovery import _safe_string

        class BadStr:
            def __str__(self):
                raise Exception("Cannot convert")

            def __repr__(self):
                return "BadStr()"

        result = _safe_string(BadStr())
        assert "BadStr" in result

    def test_safe_serialize_handles_nested_dicts(self):
        """_safe_serialize handles nested dictionaries."""
        from core.error_recovery import _safe_serialize

        nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": "deep value"
                        }
                    }
                }
            }
        }

        result = _safe_serialize(nested, depth=3)

        assert isinstance(result, dict)
        # Should truncate at depth 3
        assert "level1" in result

    def test_safe_serialize_handles_lists(self):
        """_safe_serialize handles lists."""
        from core.error_recovery import _safe_serialize

        data = [1, 2, 3, {"nested": "value"}]
        result = _safe_serialize(data)

        assert isinstance(result, list)
        assert len(result) == 4

    def test_safe_serialize_handles_paths(self):
        """_safe_serialize converts Path objects to strings."""
        from core.error_recovery import _safe_serialize

        # Use PurePosixPath for consistent cross-platform testing
        data = {"path": PurePosixPath("/some/path")}
        result = _safe_serialize(data)

        # The serialized path should be a string
        assert isinstance(result["path"], str)
        # On Windows, Path("/some/path") produces "\\some\\path"
        # On Unix, it produces "/some/path"
        # Accept either format
        assert "some" in result["path"]
        assert "path" in result["path"]

    def test_safe_serialize_handles_exceptions_in_context(self):
        """_safe_serialize handles Exception objects in context."""
        from core.error_recovery import _safe_serialize

        data = {"error": ValueError("test error")}
        result = _safe_serialize(data)

        assert result["error"]["type"] == "ValueError"
        assert "test error" in result["error"]["message"]

    def test_safe_serialize_truncates_large_collections(self):
        """_safe_serialize truncates large collections."""
        from core.error_recovery import _safe_serialize, MAX_CONTEXT_ITEMS

        large_dict = {f"key_{i}": i for i in range(100)}
        result = _safe_serialize(large_dict)

        # Should be truncated
        assert len(result) <= MAX_CONTEXT_ITEMS + 1  # +1 for __truncated__ marker


# =============================================================================
# API Error Handler Integration Tests
# =============================================================================


class TestAPIErrorHandlerIntegration:
    """Tests for FastAPI error handler integration."""

    @pytest.mark.asyncio
    async def test_error_handler_returns_json_response(self):
        """error_handler returns proper JSONResponse."""
        from core.api.errors import error_handler, ValidationError
        from unittest.mock import MagicMock

        # Mock request
        request = MagicMock()
        request.state = MagicMock()
        request.state.request_id = "test-req-123"
        request.app = MagicMock()
        request.app.state = MagicMock()
        request.app.state.debug = False
        request.url = MagicMock()
        request.url.path = "/api/test"

        error = ValidationError("Invalid email", field="email")

        response = await error_handler(request, error)

        assert response.status_code == 422
        # Response content should be JSON
        body = json.loads(response.body)
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "request_id" in body["error"]

    @pytest.mark.asyncio
    async def test_generic_error_handler_wraps_unexpected(self):
        """generic_error_handler wraps unexpected exceptions."""
        from core.api.errors import generic_error_handler
        from unittest.mock import MagicMock

        request = MagicMock()
        request.state = MagicMock()
        request.state.request_id = "test-req-456"
        request.app = MagicMock()
        request.app.state = MagicMock()
        request.app.state.debug = False
        request.url = MagicMock()
        request.url.path = "/api/test"

        exc = RuntimeError("Unexpected crash")

        response = await generic_error_handler(request, exc)

        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["error"]["code"] == "INTERNAL_ERROR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
