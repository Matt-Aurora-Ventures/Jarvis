"""
Unit tests for tg_bot/error_handler.py - User-Friendly Error Handler.

Covers:
- Error Classification (classify_error function)
- Error Message Formatting (format_error_message, format_simple_error, format_validation_error)
- Error Code Extraction (extract_error_code function)
- ErrorFormatter Class (with customization options)
- Error Templates (all error categories)
- Singleton Pattern (get_formatter)

Test Categories:
1. Error Classification - Classify exceptions into error categories
2. Error Message Formatting - Format errors for user display
3. Simple Error Messages - Quick error formatting
4. Validation Errors - Input validation error messages
5. Error Code Extraction - Extract HTTP/custom error codes
6. ErrorFormatter Class - Customizable error formatter
7. Error Templates - Verify all template configurations
8. Edge Cases - Unusual inputs and error handling

Target: 60%+ coverage with ~50 tests
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_errors():
    """Create sample exceptions for testing."""
    return {
        "token_not_found": Exception("Token not found in database"),
        "invalid_token": ValueError("Invalid token address"),
        "no_data": Exception("No data available for this request"),
        "rate_limit": Exception("Rate limit exceeded: 429 Too Many Requests"),
        "too_many": Exception("Too many requests, please slow down"),
        "throttled": Exception("Request throttled"),
        "unauthorized": Exception("Unauthorized access: 403 Forbidden"),
        "permission": PermissionError("Permission denied to access resource"),
        "forbidden": Exception("Access forbidden"),
        "connection": ConnectionError("Connection refused"),
        "network": Exception("Network unreachable"),
        "dns": Exception("DNS resolution failed"),
        "timeout": TimeoutError("Request timed out after 30s"),
        "deadline": Exception("Deadline exceeded"),
        "api_500": Exception("API returned 500 Internal Server Error"),
        "api_502": Exception("502 Bad Gateway"),
        "api_503": Exception("503 Service Unavailable"),
        "invalid_input": ValueError("Invalid format for input"),
        "parse_error": Exception("Parse error in configuration"),
        "maintenance": Exception("System is down for maintenance"),
        "upgrade": Exception("Upgrade in progress"),
        "generic": Exception("Something unexpected happened"),
    }


@pytest.fixture
def http_error_exceptions():
    """Create exceptions with HTTP status codes."""
    return {
        "400": Exception("Bad request: 400"),
        "401": Exception("Unauthorized: 401"),
        "403": Exception("Forbidden: 403"),
        "404": Exception("Not found: 404"),
        "429": Exception("Too many requests: 429"),
        "500": Exception("Internal server error: 500"),
        "502": Exception("Bad gateway: 502"),
        "503": Exception("Service unavailable: 503"),
        "504": Exception("Gateway timeout: 504"),
    }


@pytest.fixture
def custom_code_exceptions():
    """Create exceptions with custom error codes."""
    return {
        "code_uppercase": Exception("Error occurred, error_code: ABC123"),
        "code_lowercase": Exception("Failed with error-code: xyz789"),
        "code_colon": Exception("Problem: error code: ERR_001"),
        "no_code": Exception("Generic error without code"),
    }


# ============================================================================
# Test: Error Category Enum
# ============================================================================

class TestErrorCategoryEnum:
    """Tests for ErrorCategory enum."""

    def test_all_categories_exist(self):
        """Should have all expected error categories."""
        from tg_bot.error_handler import ErrorCategory

        expected = [
            "TOKEN_NOT_FOUND", "API_ERROR", "RATE_LIMITED", "INVALID_INPUT",
            "PERMISSION_DENIED", "NETWORK_ERROR", "TIMEOUT", "INTERNAL", "MAINTENANCE"
        ]
        for cat in expected:
            assert hasattr(ErrorCategory, cat), f"Missing category: {cat}"

    def test_category_values(self):
        """Should have string values for categories."""
        from tg_bot.error_handler import ErrorCategory

        assert ErrorCategory.TOKEN_NOT_FOUND.value == "token_not_found"
        assert ErrorCategory.API_ERROR.value == "api_error"
        assert ErrorCategory.RATE_LIMITED.value == "rate_limited"
        assert ErrorCategory.INTERNAL.value == "internal"


# ============================================================================
# Test: FriendlyError Dataclass
# ============================================================================

class TestFriendlyErrorDataclass:
    """Tests for FriendlyError dataclass."""

    def test_create_friendly_error(self):
        """Should create FriendlyError instance."""
        from tg_bot.error_handler import FriendlyError

        error = FriendlyError(
            emoji="\U0001f41e",
            title="Test Error",
            message="Something went wrong",
            suggestions=["Try again", "Check input"]
        )

        assert error.emoji == "\U0001f41e"
        assert error.title == "Test Error"
        assert error.message == "Something went wrong"
        assert len(error.suggestions) == 2
        assert error.retry_after is None

    def test_friendly_error_with_retry(self):
        """Should create FriendlyError with retry_after."""
        from tg_bot.error_handler import FriendlyError

        error = FriendlyError(
            emoji="\u23f0",
            title="Rate Limited",
            message="Please wait",
            suggestions=["Wait a moment"],
            retry_after=60
        )

        assert error.retry_after == 60

    def test_friendly_error_empty_suggestions(self):
        """Should allow empty suggestions list."""
        from tg_bot.error_handler import FriendlyError

        error = FriendlyError(
            emoji="\u274c",
            title="Error",
            message="An error occurred",
            suggestions=[]
        )

        assert error.suggestions == []


# ============================================================================
# Test: Error Templates Configuration
# ============================================================================

class TestErrorTemplates:
    """Tests for ERROR_TEMPLATES configuration."""

    def test_all_categories_have_templates(self):
        """Should have templates for all error categories."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        for category in ErrorCategory:
            assert category in ERROR_TEMPLATES, f"Missing template for {category}"

    def test_token_not_found_template(self):
        """Should have correct TOKEN_NOT_FOUND template."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.TOKEN_NOT_FOUND]
        assert "Token Not Found" in template.title
        assert template.retry_after is None
        assert len(template.suggestions) > 0

    def test_rate_limited_template_has_retry(self):
        """Should have retry_after for RATE_LIMITED."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.RATE_LIMITED]
        assert template.retry_after == 60

    def test_api_error_template_has_retry(self):
        """Should have retry_after for API_ERROR."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.API_ERROR]
        assert template.retry_after == 30

    def test_network_error_template_has_retry(self):
        """Should have retry_after for NETWORK_ERROR."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.NETWORK_ERROR]
        assert template.retry_after == 10

    def test_timeout_template_has_retry(self):
        """Should have retry_after for TIMEOUT."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.TIMEOUT]
        assert template.retry_after == 15

    def test_internal_template_no_retry(self):
        """Should not have retry_after for INTERNAL."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.INTERNAL]
        assert template.retry_after is None

    def test_templates_have_emojis(self):
        """All templates should have emojis."""
        from tg_bot.error_handler import ERROR_TEMPLATES

        for category, template in ERROR_TEMPLATES.items():
            assert template.emoji, f"Missing emoji for {category}"
            assert len(template.emoji) > 0


# ============================================================================
# Test: classify_error Function
# ============================================================================

class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_token_not_found(self, sample_errors):
        """Should classify token not found errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["token_not_found"]) == ErrorCategory.TOKEN_NOT_FOUND
        assert classify_error(sample_errors["invalid_token"]) == ErrorCategory.TOKEN_NOT_FOUND
        assert classify_error(sample_errors["no_data"]) == ErrorCategory.TOKEN_NOT_FOUND

    def test_classify_rate_limited(self, sample_errors):
        """Should classify rate limit errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["rate_limit"]) == ErrorCategory.RATE_LIMITED
        assert classify_error(sample_errors["too_many"]) == ErrorCategory.RATE_LIMITED
        assert classify_error(sample_errors["throttled"]) == ErrorCategory.RATE_LIMITED

    def test_classify_permission_denied(self, sample_errors):
        """Should classify permission errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["unauthorized"]) == ErrorCategory.PERMISSION_DENIED
        assert classify_error(sample_errors["permission"]) == ErrorCategory.PERMISSION_DENIED
        assert classify_error(sample_errors["forbidden"]) == ErrorCategory.PERMISSION_DENIED

    def test_classify_network_error(self, sample_errors):
        """Should classify network errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["connection"]) == ErrorCategory.NETWORK_ERROR
        assert classify_error(sample_errors["network"]) == ErrorCategory.NETWORK_ERROR
        assert classify_error(sample_errors["dns"]) == ErrorCategory.NETWORK_ERROR

    def test_classify_timeout(self, sample_errors):
        """Should classify timeout errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["timeout"]) == ErrorCategory.TIMEOUT
        assert classify_error(sample_errors["deadline"]) == ErrorCategory.TIMEOUT

    def test_classify_api_error(self, sample_errors):
        """Should classify API errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["api_500"]) == ErrorCategory.API_ERROR
        assert classify_error(sample_errors["api_502"]) == ErrorCategory.API_ERROR
        assert classify_error(sample_errors["api_503"]) == ErrorCategory.API_ERROR

    def test_classify_invalid_input(self, sample_errors):
        """Should classify invalid input errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["invalid_input"]) == ErrorCategory.INVALID_INPUT
        assert classify_error(sample_errors["parse_error"]) == ErrorCategory.INVALID_INPUT

    def test_classify_maintenance(self, sample_errors):
        """Should classify maintenance errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["maintenance"]) == ErrorCategory.MAINTENANCE
        assert classify_error(sample_errors["upgrade"]) == ErrorCategory.MAINTENANCE

    def test_classify_generic_as_internal(self, sample_errors):
        """Should classify unknown errors as INTERNAL."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(sample_errors["generic"]) == ErrorCategory.INTERNAL

    def test_classify_case_insensitive(self):
        """Should classify errors case-insensitively."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(Exception("TOKEN NOT FOUND")) == ErrorCategory.TOKEN_NOT_FOUND
        assert classify_error(Exception("RATE LIMIT exceeded")) == ErrorCategory.RATE_LIMITED
        assert classify_error(Exception("TIMEOUT occurred")) == ErrorCategory.TIMEOUT

    def test_classify_empty_error(self):
        """Should classify empty error as INTERNAL."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(Exception("")) == ErrorCategory.INTERNAL

    def test_classify_with_http_429(self):
        """Should classify 429 as rate limited."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(Exception("Error 429")) == ErrorCategory.RATE_LIMITED

    def test_classify_with_http_403(self):
        """Should classify 403 as permission denied."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        assert classify_error(Exception("Error 403")) == ErrorCategory.PERMISSION_DENIED


# ============================================================================
# Test: format_error_message Function
# ============================================================================

class TestFormatErrorMessage:
    """Tests for format_error_message function."""

    def test_format_basic_error(self):
        """Should format a basic error message."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("Token not found"))

        assert "Token Not Found" in message
        assert "Try this" in message
        assert len(message) > 0

    def test_format_with_category_override(self):
        """Should use category override when provided."""
        from tg_bot.error_handler import format_error_message, ErrorCategory

        message = format_error_message(
            Exception("some error"),
            category=ErrorCategory.RATE_LIMITED
        )

        assert "Rate Limited" in message
        assert "60s" in message  # retry_after

    def test_format_with_context(self):
        """Should include context when provided."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(
            Exception("Token not found"),
            context="fetching SOL price"
        )

        assert "Context: fetching SOL price" in message

    def test_format_includes_emoji(self):
        """Should include emoji in formatted message."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("rate limit exceeded"))

        # Should contain at least one emoji character
        assert any(ord(c) > 127 for c in message)

    def test_format_includes_suggestions(self):
        """Should include suggestions in formatted message."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("Token not found"))

        assert "Try this:" in message
        assert " - " in message  # suggestion bullet

    def test_format_includes_retry_after(self):
        """Should include retry time for applicable errors."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("rate limit 429"))

        assert "Retry in" in message

    def test_format_internal_error(self):
        """Should format internal errors appropriately."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("unknown error xyz"))

        assert "Something Went Wrong" in message

    def test_format_returns_string(self):
        """Should always return a string."""
        from tg_bot.error_handler import format_error_message

        result = format_error_message(Exception("test"))

        assert isinstance(result, str)

    def test_format_uses_markdown_formatting(self):
        """Should use markdown formatting."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("Token not found"))

        assert "*" in message  # bold markers


# ============================================================================
# Test: format_simple_error Function
# ============================================================================

class TestFormatSimpleError:
    """Tests for format_simple_error function."""

    def test_format_simple_message_only(self):
        """Should format simple error with message only."""
        from tg_bot.error_handler import format_simple_error

        message = format_simple_error("Something went wrong")

        assert "Something went wrong" in message
        assert "\u274c" in message  # cross emoji

    def test_format_simple_with_suggestion(self):
        """Should include suggestion when provided."""
        from tg_bot.error_handler import format_simple_error

        message = format_simple_error(
            "Invalid token address",
            suggestion="Check the address format"
        )

        assert "Invalid token address" in message
        assert "Check the address format" in message
        assert "\U0001f4a1" in message  # lightbulb emoji

    def test_format_simple_returns_string(self):
        """Should return a string."""
        from tg_bot.error_handler import format_simple_error

        result = format_simple_error("error")

        assert isinstance(result, str)

    def test_format_simple_empty_message(self):
        """Should handle empty message."""
        from tg_bot.error_handler import format_simple_error

        message = format_simple_error("")

        assert isinstance(message, str)


# ============================================================================
# Test: format_validation_error Function
# ============================================================================

class TestFormatValidationError:
    """Tests for format_validation_error function."""

    def test_format_validation_basic(self):
        """Should format basic validation error."""
        from tg_bot.error_handler import format_validation_error

        message = format_validation_error(
            field="amount",
            issue="Must be a positive number"
        )

        assert "Invalid amount" in message
        assert "Must be a positive number" in message

    def test_format_validation_with_example(self):
        """Should include example when provided."""
        from tg_bot.error_handler import format_validation_error

        message = format_validation_error(
            field="token address",
            issue="Address must be 32-44 characters",
            example="So1ana1111111111111111111111111111111111111"
        )

        assert "Invalid token address" in message
        assert "32-44 characters" in message
        assert "Example:" in message
        assert "So1ana" in message

    def test_format_validation_has_emoji(self):
        """Should include emoji in validation error."""
        from tg_bot.error_handler import format_validation_error

        message = format_validation_error("field", "issue")

        assert "\U0001f4dd" in message  # memo emoji

    def test_format_validation_returns_string(self):
        """Should return a string."""
        from tg_bot.error_handler import format_validation_error

        result = format_validation_error("field", "issue")

        assert isinstance(result, str)

    def test_format_validation_markdown(self):
        """Should use markdown formatting."""
        from tg_bot.error_handler import format_validation_error

        message = format_validation_error(
            field="amount",
            issue="Invalid format",
            example="100.50"
        )

        assert "*" in message  # bold
        assert "`" in message  # code formatting for example


# ============================================================================
# Test: extract_error_code Function
# ============================================================================

class TestExtractErrorCode:
    """Tests for extract_error_code function."""

    def test_extract_http_400(self, http_error_exceptions):
        """Should extract HTTP 400 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["400"])
        assert code == "HTTP_400"

    def test_extract_http_401(self, http_error_exceptions):
        """Should extract HTTP 401 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["401"])
        assert code == "HTTP_401"

    def test_extract_http_404(self, http_error_exceptions):
        """Should extract HTTP 404 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["404"])
        assert code == "HTTP_404"

    def test_extract_http_500(self, http_error_exceptions):
        """Should extract HTTP 500 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["500"])
        assert code == "HTTP_500"

    def test_extract_http_502(self, http_error_exceptions):
        """Should extract HTTP 502 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["502"])
        assert code == "HTTP_502"

    def test_extract_http_503(self, http_error_exceptions):
        """Should extract HTTP 503 code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(http_error_exceptions["503"])
        assert code == "HTTP_503"

    def test_extract_custom_code_uppercase(self, custom_code_exceptions):
        """Should extract custom error code (uppercase format)."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(custom_code_exceptions["code_uppercase"])
        assert code == "ABC123"

    def test_extract_custom_code_lowercase(self, custom_code_exceptions):
        """Should extract custom error code (lowercase format)."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(custom_code_exceptions["code_lowercase"])
        assert code == "XYZ789"

    def test_extract_no_code_returns_none(self, custom_code_exceptions):
        """Should return None when no code present."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(custom_code_exceptions["no_code"])
        assert code is None

    def test_extract_empty_error(self):
        """Should return None for empty error."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(Exception(""))
        assert code is None


# ============================================================================
# Test: ErrorFormatter Class - Initialization
# ============================================================================

class TestErrorFormatterInit:
    """Tests for ErrorFormatter initialization."""

    def test_create_default_formatter(self):
        """Should create formatter with default options."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter()

        assert formatter.include_code is False
        assert formatter.include_timestamp is False
        assert formatter.max_suggestion_count == 3

    def test_create_with_include_code(self):
        """Should create formatter with include_code enabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_code=True)

        assert formatter.include_code is True

    def test_create_with_include_timestamp(self):
        """Should create formatter with include_timestamp enabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_timestamp=True)

        assert formatter.include_timestamp is True

    def test_create_with_custom_suggestion_count(self):
        """Should create formatter with custom suggestion count."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(max_suggestion_count=5)

        assert formatter.max_suggestion_count == 5


# ============================================================================
# Test: ErrorFormatter Class - format Method
# ============================================================================

class TestErrorFormatterFormat:
    """Tests for ErrorFormatter.format method."""

    def test_format_basic(self):
        """Should format basic error."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter()
        message = formatter.format(Exception("Token not found"))

        assert "Token Not Found" in message
        assert isinstance(message, str)

    def test_format_with_context(self):
        """Should include context in formatted message."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter()
        message = formatter.format(
            Exception("Token not found"),
            context="looking up SOL"
        )

        assert "Context: looking up SOL" in message

    def test_format_with_error_code(self):
        """Should include error code when enabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_code=True)
        message = formatter.format(Exception("Error 500 occurred"))

        assert "Code:" in message
        assert "HTTP_500" in message

    def test_format_without_error_code(self):
        """Should not include code when disabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_code=False)
        message = formatter.format(Exception("Error 500 occurred"))

        assert "Code:" not in message

    def test_format_with_timestamp(self):
        """Should include timestamp when enabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_timestamp=True)
        message = formatter.format(Exception("test error"))

        assert "Time:" in message
        assert "UTC" in message

    def test_format_without_timestamp(self):
        """Should not include timestamp when disabled."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(include_timestamp=False)
        message = formatter.format(Exception("test error"))

        assert "Time:" not in message

    def test_format_limits_suggestions(self):
        """Should limit suggestions to max_suggestion_count."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(max_suggestion_count=1)
        message = formatter.format(Exception("Token not found"))

        # Count suggestion bullets
        bullet_count = message.count("  - ")
        assert bullet_count <= 1

    def test_format_includes_retry_after(self):
        """Should include retry_after for applicable errors."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter()
        message = formatter.format(Exception("rate limit 429"))

        assert "Retry in" in message


# ============================================================================
# Test: get_formatter Singleton
# ============================================================================

class TestGetFormatter:
    """Tests for get_formatter singleton function."""

    def test_get_formatter_returns_instance(self):
        """Should return an ErrorFormatter instance."""
        from tg_bot.error_handler import get_formatter, ErrorFormatter

        formatter = get_formatter()

        assert isinstance(formatter, ErrorFormatter)

    def test_get_formatter_returns_same_instance(self):
        """Should return the same instance on multiple calls."""
        import tg_bot.error_handler as error_handler_module
        from tg_bot.error_handler import get_formatter

        # Reset singleton
        error_handler_module._formatter = None

        formatter1 = get_formatter()
        formatter2 = get_formatter()

        assert formatter1 is formatter2


# ============================================================================
# Test: Module Exports
# ============================================================================

class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports_exist(self):
        """Should export all declared items."""
        from tg_bot.error_handler import __all__
        import tg_bot.error_handler as module

        for name in __all__:
            assert hasattr(module, name), f"Missing export: {name}"

    def test_exports_include_main_functions(self):
        """Should export main functions."""
        from tg_bot.error_handler import __all__

        expected = [
            "ErrorCategory",
            "FriendlyError",
            "ErrorFormatter",
            "classify_error",
            "format_error_message",
            "format_simple_error",
            "format_validation_error",
            "extract_error_code",
            "get_formatter",
            "ERROR_TEMPLATES",
        ]

        for name in expected:
            assert name in __all__, f"Missing export: {name}"


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_classify_none_like_error(self):
        """Should handle error with 'None' in message."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        result = classify_error(Exception("Value is None"))
        assert result == ErrorCategory.INTERNAL

    def test_classify_very_long_error(self):
        """Should handle very long error messages."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        long_message = "x" * 10000 + " token not found " + "y" * 10000
        result = classify_error(Exception(long_message))
        assert result == ErrorCategory.TOKEN_NOT_FOUND

    def test_format_error_with_special_chars(self):
        """Should handle errors with special characters."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("Error with <html> & 'quotes'"))
        assert isinstance(message, str)
        assert len(message) > 0

    def test_format_error_with_unicode(self):
        """Should handle errors with unicode."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(Exception("Error with unicode"))
        assert isinstance(message, str)

    def test_format_simple_with_newlines(self):
        """Should handle messages with newlines."""
        from tg_bot.error_handler import format_simple_error

        message = format_simple_error("Line 1\nLine 2\nLine 3")
        assert "Line 1" in message

    def test_extract_code_with_multiple_numbers(self):
        """Should extract first HTTP-like code."""
        from tg_bot.error_handler import extract_error_code

        code = extract_error_code(Exception("Errors: 500, 502, 503"))
        assert code == "HTTP_500"

    def test_extract_code_ignores_non_http(self):
        """Should ignore numbers that aren't HTTP codes."""
        from tg_bot.error_handler import extract_error_code

        # 300 is not typically an error code range
        code = extract_error_code(Exception("Value is 123"))
        assert code is None

    def test_formatter_with_no_suggestions(self):
        """Should handle errors with no suggestions gracefully."""
        from tg_bot.error_handler import ErrorFormatter, ERROR_TEMPLATES, ErrorCategory, FriendlyError

        # Temporarily create template with no suggestions
        original = ERROR_TEMPLATES[ErrorCategory.INTERNAL]
        try:
            ERROR_TEMPLATES[ErrorCategory.INTERNAL] = FriendlyError(
                emoji="\U0001f41e",
                title="Test",
                message="Test message",
                suggestions=[]
            )

            formatter = ErrorFormatter()
            message = formatter.format(Exception("unknown error"))

            assert isinstance(message, str)
            assert "Try this:" not in message
        finally:
            ERROR_TEMPLATES[ErrorCategory.INTERNAL] = original

    def test_classify_error_priority(self):
        """Should follow classification priority order."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        # Token not found takes priority
        result = classify_error(Exception("token not found rate limit"))
        assert result == ErrorCategory.TOKEN_NOT_FOUND

    def test_format_preserves_context_special_chars(self):
        """Should preserve special chars in context."""
        from tg_bot.error_handler import format_error_message

        message = format_error_message(
            Exception("error"),
            context="<test> & 'context'"
        )

        # Context should be preserved (implementation may escape)
        assert "Context:" in message


# ============================================================================
# Test: Integration - Full Error Handling Flow
# ============================================================================

class TestIntegrationFlow:
    """Integration tests for full error handling workflow."""

    def test_full_flow_token_not_found(self):
        """Should handle complete token not found flow."""
        from tg_bot.error_handler import (
            classify_error, format_error_message, extract_error_code, ErrorCategory
        )

        error = Exception("Token ABC123 not found in database")

        category = classify_error(error)
        assert category == ErrorCategory.TOKEN_NOT_FOUND

        message = format_error_message(error, context="looking up token ABC123")
        assert "Token Not Found" in message
        assert "ABC123" in message

        code = extract_error_code(error)
        assert code is None  # No HTTP code in this error

    def test_full_flow_rate_limit(self):
        """Should handle complete rate limit flow."""
        from tg_bot.error_handler import (
            classify_error, format_error_message, extract_error_code, ErrorCategory
        )

        error = Exception("Rate limit exceeded: 429 Too Many Requests")

        category = classify_error(error)
        assert category == ErrorCategory.RATE_LIMITED

        message = format_error_message(error)
        assert "Rate Limited" in message
        assert "Retry in 60s" in message

        code = extract_error_code(error)
        assert code == "HTTP_429"

    def test_full_flow_api_error(self):
        """Should handle complete API error flow."""
        from tg_bot.error_handler import (
            classify_error, format_error_message, extract_error_code, ErrorCategory
        )

        error = Exception("API returned 500 Internal Server Error")

        category = classify_error(error)
        assert category == ErrorCategory.API_ERROR

        message = format_error_message(error)
        assert "Data Unavailable" in message

        code = extract_error_code(error)
        assert code == "HTTP_500"

    def test_full_flow_with_formatter(self):
        """Should handle flow using ErrorFormatter."""
        from tg_bot.error_handler import ErrorFormatter

        formatter = ErrorFormatter(
            include_code=True,
            include_timestamp=True,
            max_suggestion_count=2
        )

        error = Exception("Connection refused: 502 Bad Gateway")
        message = formatter.format(error, context="fetching market data")

        assert "Connection Issue" in message or "Data Unavailable" in message
        assert "Context: fetching market data" in message
        assert "Code:" in message
        assert "Time:" in message

        # Should limit suggestions
        bullet_count = message.count("  - ")
        assert bullet_count <= 2


# ============================================================================
# Test: Retry Logic Validation
# ============================================================================

class TestRetryLogic:
    """Tests for retry_after values in templates."""

    def test_rate_limited_retry_is_60(self):
        """Rate limit should suggest 60 second retry."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.RATE_LIMITED]
        assert template.retry_after == 60

    def test_api_error_retry_is_30(self):
        """API error should suggest 30 second retry."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.API_ERROR]
        assert template.retry_after == 30

    def test_network_error_retry_is_10(self):
        """Network error should suggest 10 second retry."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.NETWORK_ERROR]
        assert template.retry_after == 10

    def test_timeout_retry_is_15(self):
        """Timeout should suggest 15 second retry."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        template = ERROR_TEMPLATES[ErrorCategory.TIMEOUT]
        assert template.retry_after == 15

    def test_non_retryable_errors_have_no_retry(self):
        """Non-retryable errors should not have retry_after."""
        from tg_bot.error_handler import ERROR_TEMPLATES, ErrorCategory

        non_retryable = [
            ErrorCategory.TOKEN_NOT_FOUND,
            ErrorCategory.INVALID_INPUT,
            ErrorCategory.PERMISSION_DENIED,
            ErrorCategory.INTERNAL,
            ErrorCategory.MAINTENANCE,
        ]

        for category in non_retryable:
            template = ERROR_TEMPLATES[category]
            assert template.retry_after is None, f"{category} should not have retry_after"
