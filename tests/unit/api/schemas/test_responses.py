"""Tests for API response schemas and helper functions.

Covers:
- ErrorDetail model validation and serialization
- APIResponse model validation, timestamps, and serialization
- ValidationErrorResponse model
- success_response() helper function
- error_response() helper function
- validation_error_response() helper function
- paginated_response() helper function
- ERROR_CODES lookup
- make_error_response() helper function
"""
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pydantic import ValidationError

from api.schemas.responses import (
    ErrorDetail,
    APIResponse,
    ValidationErrorResponse,
    success_response,
    error_response,
    validation_error_response,
    paginated_response,
    ERROR_CODES,
    make_error_response,
)


# =============================================================================
# ErrorDetail Model Tests
# =============================================================================


class TestErrorDetailModel:
    """Test ErrorDetail Pydantic model."""

    def test_error_detail_minimal(self):
        """Test ErrorDetail with only required fields."""
        error = ErrorDetail(code="ERR_001", message="Test error")
        assert error.code == "ERR_001"
        assert error.message == "Test error"
        assert error.field is None
        assert error.details is None

    def test_error_detail_with_field(self):
        """Test ErrorDetail with field specified."""
        error = ErrorDetail(code="VAL_001", message="Field validation failed", field="email")
        assert error.field == "email"

    def test_error_detail_with_details(self):
        """Test ErrorDetail with details dictionary."""
        details = {"expected": "string", "received": "int"}
        error = ErrorDetail(code="TYPE_001", message="Type mismatch", details=details)
        assert error.details == details

    def test_error_detail_full(self):
        """Test ErrorDetail with all fields."""
        error = ErrorDetail(
            code="FULL_001",
            message="Full error",
            field="username",
            details={"min_length": 3, "actual_length": 1}
        )
        assert error.code == "FULL_001"
        assert error.message == "Full error"
        assert error.field == "username"
        assert error.details["min_length"] == 3

    def test_error_detail_serialization(self):
        """Test ErrorDetail serialization to dict."""
        error = ErrorDetail(code="SER_001", message="Serialization test")
        data = error.model_dump()
        assert isinstance(data, dict)
        assert data["code"] == "SER_001"
        assert data["message"] == "Serialization test"

    def test_error_detail_json_serialization(self):
        """Test ErrorDetail JSON serialization."""
        error = ErrorDetail(code="JSON_001", message="JSON test", field="test_field")
        json_str = error.model_dump_json()
        assert isinstance(json_str, str)
        assert "JSON_001" in json_str
        assert "test_field" in json_str

    def test_error_detail_missing_code_fails(self):
        """Test ErrorDetail requires code field."""
        with pytest.raises(ValidationError):
            ErrorDetail(message="Missing code")

    def test_error_detail_missing_message_fails(self):
        """Test ErrorDetail requires message field."""
        with pytest.raises(ValidationError):
            ErrorDetail(code="NO_MSG")

    def test_error_detail_empty_code(self):
        """Test ErrorDetail with empty code."""
        error = ErrorDetail(code="", message="Empty code")
        assert error.code == ""

    def test_error_detail_empty_message(self):
        """Test ErrorDetail with empty message."""
        error = ErrorDetail(code="EMPTY", message="")
        assert error.message == ""

    def test_error_detail_nested_details(self):
        """Test ErrorDetail with nested details dictionary."""
        nested_details = {
            "context": {
                "request_id": "abc123",
                "timestamp": "2026-01-25T10:00:00Z"
            },
            "validation": [
                {"field": "name", "error": "too_short"},
                {"field": "age", "error": "not_integer"}
            ]
        }
        error = ErrorDetail(code="NESTED", message="Nested details", details=nested_details)
        assert error.details["context"]["request_id"] == "abc123"
        assert len(error.details["validation"]) == 2


# =============================================================================
# APIResponse Model Tests
# =============================================================================


class TestAPIResponseModel:
    """Test APIResponse Pydantic model."""

    def test_api_response_success(self):
        """Test successful API response."""
        response = APIResponse(success=True, data={"result": "ok"})
        assert response.success is True
        assert response.data == {"result": "ok"}
        assert response.error is None

    def test_api_response_error(self):
        """Test error API response."""
        error = ErrorDetail(code="ERR", message="Error occurred")
        response = APIResponse(success=False, error=error)
        assert response.success is False
        assert response.error.code == "ERR"

    def test_api_response_auto_timestamp(self):
        """Test APIResponse auto-generates timestamp."""
        before = datetime.utcnow()
        response = APIResponse(success=True)
        after = datetime.utcnow()

        assert response.timestamp is not None
        assert before <= response.timestamp <= after

    def test_api_response_explicit_timestamp(self):
        """Test APIResponse with explicit timestamp."""
        explicit_time = datetime(2026, 1, 15, 12, 0, 0)
        response = APIResponse(success=True, timestamp=explicit_time)
        assert response.timestamp == explicit_time

    def test_api_response_with_meta(self):
        """Test APIResponse with metadata."""
        meta = {"request_id": "req-123", "duration_ms": 42}
        response = APIResponse(success=True, data="result", meta=meta)
        assert response.meta == meta
        assert response.meta["request_id"] == "req-123"

    def test_api_response_serialization(self):
        """Test APIResponse serialization to dict."""
        response = APIResponse(success=True, data={"key": "value"})
        data = response.model_dump()

        assert isinstance(data, dict)
        assert data["success"] is True
        assert data["data"]["key"] == "value"
        assert "timestamp" in data

    def test_api_response_with_list_data(self):
        """Test APIResponse with list data."""
        response = APIResponse(success=True, data=[1, 2, 3, 4, 5])
        assert response.data == [1, 2, 3, 4, 5]

    def test_api_response_with_none_data(self):
        """Test APIResponse with None data (valid for success=True operations)."""
        response = APIResponse(success=True, data=None)
        assert response.data is None

    def test_api_response_with_complex_data(self):
        """Test APIResponse with complex nested data."""
        complex_data = {
            "users": [
                {"id": 1, "name": "Alice", "settings": {"theme": "dark"}},
                {"id": 2, "name": "Bob", "settings": {"theme": "light"}}
            ],
            "pagination": {"page": 1, "total": 100}
        }
        response = APIResponse(success=True, data=complex_data)
        assert response.data["users"][0]["settings"]["theme"] == "dark"

    def test_api_response_missing_success_fails(self):
        """Test APIResponse requires success field."""
        with pytest.raises(ValidationError):
            APIResponse(data="some data")

    def test_api_response_success_with_error(self):
        """Test APIResponse can have success=True with error (unusual but valid)."""
        error = ErrorDetail(code="WARN", message="Warning")
        response = APIResponse(success=True, error=error)
        assert response.success is True
        assert response.error is not None


# =============================================================================
# ValidationErrorResponse Model Tests
# =============================================================================


class TestValidationErrorResponseModel:
    """Test ValidationErrorResponse Pydantic model."""

    def test_validation_error_response_basic(self):
        """Test basic ValidationErrorResponse."""
        errors = [ErrorDetail(code="VAL_001", message="Required field")]
        response = ValidationErrorResponse(errors=errors)

        assert response.success is False
        assert len(response.errors) == 1
        assert response.errors[0].code == "VAL_001"

    def test_validation_error_response_multiple_errors(self):
        """Test ValidationErrorResponse with multiple errors."""
        errors = [
            ErrorDetail(code="VAL_001", message="Name required", field="name"),
            ErrorDetail(code="VAL_002", message="Email invalid", field="email"),
            ErrorDetail(code="VAL_003", message="Age must be positive", field="age"),
        ]
        response = ValidationErrorResponse(errors=errors)

        assert len(response.errors) == 3
        assert response.errors[1].field == "email"

    def test_validation_error_response_auto_timestamp(self):
        """Test ValidationErrorResponse auto-generates timestamp."""
        errors = [ErrorDetail(code="VAL_001", message="Test")]
        before = datetime.utcnow()
        response = ValidationErrorResponse(errors=errors)
        after = datetime.utcnow()

        assert response.timestamp is not None
        assert before <= response.timestamp <= after

    def test_validation_error_response_explicit_timestamp(self):
        """Test ValidationErrorResponse with explicit timestamp."""
        errors = [ErrorDetail(code="VAL_001", message="Test")]
        explicit_time = datetime(2026, 1, 20, 15, 30, 0)
        response = ValidationErrorResponse(errors=errors, timestamp=explicit_time)

        assert response.timestamp == explicit_time

    def test_validation_error_response_success_default_false(self):
        """Test ValidationErrorResponse success defaults to False."""
        errors = [ErrorDetail(code="VAL_001", message="Test")]
        response = ValidationErrorResponse(errors=errors)
        assert response.success is False

    def test_validation_error_response_serialization(self):
        """Test ValidationErrorResponse serialization."""
        errors = [
            ErrorDetail(code="VAL_001", message="Error 1", field="field1"),
            ErrorDetail(code="VAL_002", message="Error 2", field="field2")
        ]
        response = ValidationErrorResponse(errors=errors)
        data = response.model_dump()

        assert data["success"] is False
        assert len(data["errors"]) == 2
        assert data["errors"][0]["field"] == "field1"

    def test_validation_error_response_empty_errors_list(self):
        """Test ValidationErrorResponse with empty errors list."""
        response = ValidationErrorResponse(errors=[])
        assert len(response.errors) == 0


# =============================================================================
# success_response() Helper Function Tests
# =============================================================================


class TestSuccessResponseHelper:
    """Test success_response() helper function."""

    def test_success_response_basic(self):
        """Test basic success response."""
        result = success_response(data={"result": "ok"})

        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["data"]["result"] == "ok"

    def test_success_response_no_data(self):
        """Test success response with no data."""
        result = success_response()

        assert result["success"] is True
        assert result["data"] is None

    def test_success_response_with_meta(self):
        """Test success response with metadata."""
        meta = {"duration_ms": 100, "cached": True}
        result = success_response(data="result", meta=meta)

        assert result["meta"]["duration_ms"] == 100
        assert result["meta"]["cached"] is True

    def test_success_response_with_message(self):
        """Test success response with message."""
        result = success_response(data={"id": 123}, message="Created successfully")

        assert result["meta"]["message"] == "Created successfully"
        assert result["data"]["id"] == 123

    def test_success_response_message_adds_to_existing_meta(self):
        """Test message adds to existing meta without overwriting."""
        meta = {"request_id": "xyz"}
        result = success_response(data="data", meta=meta, message="Done")

        assert result["meta"]["message"] == "Done"
        assert result["meta"]["request_id"] == "xyz"

    def test_success_response_with_list_data(self):
        """Test success response with list data."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = success_response(data=items)

        assert len(result["data"]) == 3
        assert result["data"][1]["id"] == 2

    def test_success_response_includes_timestamp(self):
        """Test success response includes timestamp."""
        result = success_response(data="test")

        assert "timestamp" in result
        assert result["timestamp"] is not None

    def test_success_response_with_primitive_data(self):
        """Test success response with primitive data types."""
        assert success_response(data=42)["data"] == 42
        assert success_response(data="string")["data"] == "string"
        assert success_response(data=True)["data"] is True
        assert success_response(data=3.14)["data"] == 3.14


# =============================================================================
# error_response() Helper Function Tests
# =============================================================================


class TestErrorResponseHelper:
    """Test error_response() helper function."""

    def test_error_response_basic(self):
        """Test basic error response."""
        result = error_response(code="ERR_001", message="Something went wrong")

        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["error"]["code"] == "ERR_001"
        assert result["error"]["message"] == "Something went wrong"

    def test_error_response_with_field(self):
        """Test error response with field."""
        result = error_response(code="VAL_001", message="Invalid email", field="email")

        assert result["error"]["field"] == "email"

    def test_error_response_with_details(self):
        """Test error response with details."""
        details = {"expected": "integer", "got": "string"}
        result = error_response(code="TYPE_001", message="Type error", details=details)

        assert result["error"]["details"]["expected"] == "integer"

    def test_error_response_with_status_code(self):
        """Test error response with status code."""
        result = error_response(
            code="AUTH_001",
            message="Unauthorized",
            status_code=401
        )

        assert result["_status_code"] == 401

    def test_error_response_full(self):
        """Test error response with all parameters."""
        result = error_response(
            code="TRADE_001",
            message="Insufficient balance",
            field="amount",
            details={"required": 100, "available": 50},
            status_code=400
        )

        assert result["error"]["code"] == "TRADE_001"
        assert result["error"]["message"] == "Insufficient balance"
        assert result["error"]["field"] == "amount"
        assert result["error"]["details"]["required"] == 100
        assert result["_status_code"] == 400

    def test_error_response_no_status_code(self):
        """Test error response without status code doesn't add _status_code key."""
        result = error_response(code="ERR", message="Error")

        assert "_status_code" not in result

    def test_error_response_includes_timestamp(self):
        """Test error response includes timestamp."""
        result = error_response(code="ERR", message="Error")

        assert "timestamp" in result


# =============================================================================
# validation_error_response() Helper Function Tests
# =============================================================================


class TestValidationErrorResponseHelper:
    """Test validation_error_response() helper function."""

    def test_validation_error_response_basic(self):
        """Test basic validation error response."""
        errors = [{"loc": ["body", "name"], "msg": "Field required", "type": "missing"}]
        result = validation_error_response(errors)

        assert result["success"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "VAL_001"
        assert result["errors"][0]["message"] == "Field required"

    def test_validation_error_response_field_path(self):
        """Test validation error response constructs field path."""
        errors = [{"loc": ["body", "user", "email"], "msg": "Invalid", "type": "value_error"}]
        result = validation_error_response(errors)

        assert result["errors"][0]["field"] == "body.user.email"

    def test_validation_error_response_multiple_errors(self):
        """Test validation error response with multiple errors."""
        errors = [
            {"loc": ["name"], "msg": "Too short", "type": "string_too_short"},
            {"loc": ["age"], "msg": "Must be positive", "type": "value_error"},
            {"loc": ["email"], "msg": "Invalid format", "type": "email_error"},
        ]
        result = validation_error_response(errors)

        assert len(result["errors"]) == 3
        assert all(err["code"] == "VAL_001" for err in result["errors"])

    def test_validation_error_response_type_in_details(self):
        """Test validation error response includes type in details."""
        errors = [{"loc": ["field"], "msg": "Error", "type": "string_type"}]
        result = validation_error_response(errors)

        assert result["errors"][0]["details"]["type"] == "string_type"

    def test_validation_error_response_missing_msg(self):
        """Test validation error response with missing msg falls back to default."""
        errors = [{"loc": ["field"], "type": "error_type"}]
        result = validation_error_response(errors)

        assert result["errors"][0]["message"] == "Validation error"

    def test_validation_error_response_missing_loc(self):
        """Test validation error response with missing loc."""
        errors = [{"msg": "Some error", "type": "error_type"}]
        result = validation_error_response(errors)

        assert result["errors"][0]["field"] == ""

    def test_validation_error_response_empty_errors(self):
        """Test validation error response with empty errors list."""
        result = validation_error_response([])

        assert result["success"] is False
        assert len(result["errors"]) == 0

    def test_validation_error_response_includes_timestamp(self):
        """Test validation error response includes timestamp."""
        errors = [{"loc": ["field"], "msg": "Error", "type": "error"}]
        result = validation_error_response(errors)

        assert "timestamp" in result

    def test_validation_error_response_numeric_loc(self):
        """Test validation error response handles numeric loc values (array indices)."""
        errors = [{"loc": ["items", 0, "name"], "msg": "Required", "type": "missing"}]
        result = validation_error_response(errors)

        assert result["errors"][0]["field"] == "items.0.name"


# =============================================================================
# paginated_response() Helper Function Tests
# =============================================================================


class TestPaginatedResponseHelper:
    """Test paginated_response() helper function."""

    def test_paginated_response_basic(self):
        """Test basic paginated response."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = paginated_response(items=items, total=10, page=1, page_size=3)

        assert result["success"] is True
        assert result["data"] == items
        assert result["meta"]["pagination"]["total"] == 10
        assert result["meta"]["pagination"]["page"] == 1
        assert result["meta"]["pagination"]["page_size"] == 3

    def test_paginated_response_total_pages_calculation(self):
        """Test total_pages calculation."""
        result = paginated_response(items=[], total=25, page=1, page_size=10)

        assert result["meta"]["pagination"]["total_pages"] == 3  # ceil(25/10)

    def test_paginated_response_exact_division(self):
        """Test total_pages with exact division."""
        result = paginated_response(items=[], total=20, page=1, page_size=10)

        assert result["meta"]["pagination"]["total_pages"] == 2

    def test_paginated_response_has_next_true(self):
        """Test has_next is true when more pages exist."""
        result = paginated_response(items=[], total=30, page=1, page_size=10)

        assert result["meta"]["pagination"]["has_next"] is True

    def test_paginated_response_has_next_false(self):
        """Test has_next is false on last page."""
        result = paginated_response(items=[], total=30, page=3, page_size=10)

        assert result["meta"]["pagination"]["has_next"] is False

    def test_paginated_response_has_prev_true(self):
        """Test has_prev is true when previous pages exist."""
        result = paginated_response(items=[], total=30, page=2, page_size=10)

        assert result["meta"]["pagination"]["has_prev"] is True

    def test_paginated_response_has_prev_false(self):
        """Test has_prev is false on first page."""
        result = paginated_response(items=[], total=30, page=1, page_size=10)

        assert result["meta"]["pagination"]["has_prev"] is False

    def test_paginated_response_with_meta(self):
        """Test paginated response preserves additional metadata."""
        meta = {"query": "test", "filters": {"active": True}}
        result = paginated_response(items=[], total=10, page=1, page_size=10, meta=meta)

        assert result["meta"]["query"] == "test"
        assert result["meta"]["filters"]["active"] is True
        assert "pagination" in result["meta"]

    def test_paginated_response_zero_page_size(self):
        """Test paginated response handles zero page_size."""
        result = paginated_response(items=[], total=10, page=1, page_size=0)

        assert result["meta"]["pagination"]["total_pages"] == 0

    def test_paginated_response_zero_total(self):
        """Test paginated response with zero total items."""
        result = paginated_response(items=[], total=0, page=1, page_size=10)

        assert result["meta"]["pagination"]["total"] == 0
        assert result["meta"]["pagination"]["total_pages"] == 0
        assert result["meta"]["pagination"]["has_next"] is False

    def test_paginated_response_single_page(self):
        """Test paginated response with single page."""
        items = [1, 2, 3, 4, 5]
        result = paginated_response(items=items, total=5, page=1, page_size=10)

        assert result["meta"]["pagination"]["total_pages"] == 1
        assert result["meta"]["pagination"]["has_next"] is False
        assert result["meta"]["pagination"]["has_prev"] is False


# =============================================================================
# ERROR_CODES Tests
# =============================================================================


class TestErrorCodes:
    """Test ERROR_CODES constant."""

    def test_error_codes_is_dict(self):
        """Test ERROR_CODES is a dictionary."""
        assert isinstance(ERROR_CODES, dict)

    def test_error_codes_validation_errors(self):
        """Test validation error codes exist."""
        assert "VAL_001" in ERROR_CODES
        assert "VAL_002" in ERROR_CODES
        assert ERROR_CODES["VAL_001"][1] == 400  # HTTP 400

    def test_error_codes_auth_errors(self):
        """Test authentication error codes exist."""
        assert "AUTH_001" in ERROR_CODES
        assert "AUTH_002" in ERROR_CODES
        assert "AUTH_003" in ERROR_CODES
        assert "AUTH_004" in ERROR_CODES
        assert ERROR_CODES["AUTH_001"][1] == 401  # HTTP 401
        assert ERROR_CODES["AUTH_004"][1] == 403  # HTTP 403

    def test_error_codes_rate_limit(self):
        """Test rate limit error code exists."""
        assert "RATE_001" in ERROR_CODES
        assert ERROR_CODES["RATE_001"][1] == 429  # HTTP 429

    def test_error_codes_system_errors(self):
        """Test system error codes exist."""
        assert "SYS_001" in ERROR_CODES
        assert "SYS_002" in ERROR_CODES
        assert "SYS_003" in ERROR_CODES
        assert ERROR_CODES["SYS_001"][1] == 500  # HTTP 500
        assert ERROR_CODES["SYS_002"][1] == 503  # HTTP 503
        assert ERROR_CODES["SYS_003"][1] == 404  # HTTP 404

    def test_error_codes_trade_errors(self):
        """Test trade error codes exist."""
        assert "TRADE_001" in ERROR_CODES
        assert "TRADE_002" in ERROR_CODES
        assert "TRADE_003" in ERROR_CODES
        assert ERROR_CODES["TRADE_001"][1] == 400
        assert ERROR_CODES["TRADE_003"][1] == 404

    def test_error_codes_provider_errors(self):
        """Test provider error codes exist."""
        assert "PROV_001" in ERROR_CODES
        assert "PROV_002" in ERROR_CODES
        assert ERROR_CODES["PROV_001"][1] == 502  # HTTP 502
        assert ERROR_CODES["PROV_002"][1] == 429  # HTTP 429

    def test_error_codes_tuple_format(self):
        """Test all error codes have (message, status_code) format."""
        for code, value in ERROR_CODES.items():
            assert isinstance(value, tuple), f"{code} should be tuple"
            assert len(value) == 2, f"{code} should have 2 elements"
            assert isinstance(value[0], str), f"{code} message should be string"
            assert isinstance(value[1], int), f"{code} status should be int"


# =============================================================================
# make_error_response() Helper Function Tests
# =============================================================================


class TestMakeErrorResponseHelper:
    """Test make_error_response() helper function."""

    def test_make_error_response_known_code(self):
        """Test make_error_response with known error code."""
        result = make_error_response("VAL_001")

        assert result["success"] is False
        assert result["error"]["code"] == "VAL_001"
        assert result["error"]["message"] == "Validation error"
        assert result["_status_code"] == 400

    def test_make_error_response_custom_message(self):
        """Test make_error_response with custom message."""
        result = make_error_response("AUTH_001", message="Please login first")

        assert result["error"]["message"] == "Please login first"
        assert result["_status_code"] == 401

    def test_make_error_response_unknown_code(self):
        """Test make_error_response with unknown error code."""
        result = make_error_response("UNKNOWN_999")

        assert result["error"]["code"] == "UNKNOWN_999"
        assert result["error"]["message"] == "Unknown error"
        assert result["_status_code"] == 500

    def test_make_error_response_unknown_code_custom_message(self):
        """Test make_error_response with unknown code and custom message."""
        result = make_error_response("CUSTOM_001", message="Custom error occurred")

        assert result["error"]["code"] == "CUSTOM_001"
        assert result["error"]["message"] == "Custom error occurred"
        assert result["_status_code"] == 500

    def test_make_error_response_all_known_codes(self):
        """Test make_error_response works for all known codes."""
        for code in ERROR_CODES:
            result = make_error_response(code)
            expected_msg, expected_status = ERROR_CODES[code]

            assert result["error"]["code"] == code
            assert result["error"]["message"] == expected_msg
            assert result["_status_code"] == expected_status

    def test_make_error_response_sys_001(self):
        """Test make_error_response for internal server error."""
        result = make_error_response("SYS_001")

        assert result["error"]["message"] == "Internal server error"
        assert result["_status_code"] == 500

    def test_make_error_response_includes_timestamp(self):
        """Test make_error_response includes timestamp."""
        result = make_error_response("VAL_001")

        assert "timestamp" in result


# =============================================================================
# Serialization and Edge Case Tests
# =============================================================================


class TestSerializationEdgeCases:
    """Test serialization edge cases and special scenarios."""

    def test_error_detail_with_special_characters(self):
        """Test ErrorDetail handles special characters in message."""
        error = ErrorDetail(
            code="SPECIAL",
            message="Error with special chars: <>&\"'",
            details={"key": "value with <script>"}
        )
        data = error.model_dump()
        assert "<>&\"'" in data["message"]

    def test_api_response_with_unicode_data(self):
        """Test APIResponse handles unicode data."""
        response = APIResponse(success=True, data={"name": "Test User", "emoji": "Hello!"})
        data = response.model_dump()
        assert data["data"]["emoji"] == "Hello!"

    def test_success_response_with_bytes_like_data(self):
        """Test success response with bytes-like data (base64 encoded)."""
        import base64
        encoded = base64.b64encode(b"binary data").decode()
        result = success_response(data={"binary": encoded})
        assert result["data"]["binary"] == "YmluYXJ5IGRhdGE="

    def test_error_response_with_long_message(self):
        """Test error response with very long message."""
        long_message = "A" * 10000
        result = error_response(code="LONG", message=long_message)
        assert len(result["error"]["message"]) == 10000

    def test_paginated_response_large_dataset(self):
        """Test paginated response with large dataset metadata."""
        result = paginated_response(
            items=list(range(100)),
            total=1_000_000,
            page=5000,
            page_size=100
        )
        assert result["meta"]["pagination"]["total"] == 1_000_000
        assert result["meta"]["pagination"]["page"] == 5000
        assert result["meta"]["pagination"]["total_pages"] == 10000

    def test_validation_error_response_deep_nested_loc(self):
        """Test validation error with deeply nested field location."""
        errors = [{
            "loc": ["body", "data", "items", 5, "metadata", "tags", 2, "value"],
            "msg": "Invalid value",
            "type": "value_error"
        }]
        result = validation_error_response(errors)
        assert result["errors"][0]["field"] == "body.data.items.5.metadata.tags.2.value"


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestResponseIntegration:
    """Integration tests combining multiple response features."""

    def test_error_detail_in_api_response_serialization(self):
        """Test ErrorDetail within APIResponse serializes correctly."""
        error = ErrorDetail(
            code="COMPLEX",
            message="Complex error",
            field="nested.field",
            details={"context": {"request_id": "abc123"}}
        )
        response = APIResponse(success=False, error=error)
        data = response.model_dump()

        assert data["error"]["details"]["context"]["request_id"] == "abc123"

    def test_paginated_response_with_complex_items(self):
        """Test paginated response with complex item structure."""
        items = [
            {
                "id": i,
                "user": {"name": f"User {i}", "roles": ["admin", "user"]},
                "metadata": {"created": "2026-01-25", "tags": ["a", "b"]}
            }
            for i in range(5)
        ]
        result = paginated_response(
            items=items,
            total=100,
            page=1,
            page_size=5,
            meta={"query_time_ms": 15}
        )

        assert result["data"][2]["user"]["name"] == "User 2"
        assert result["meta"]["query_time_ms"] == 15
        assert result["meta"]["pagination"]["total"] == 100

    def test_response_timestamp_consistency(self):
        """Test timestamps are consistent across responses created close together."""
        before = datetime.utcnow()

        success = success_response(data="test")
        error = error_response(code="TEST", message="test")
        val_error = validation_error_response([{"loc": [], "msg": "test", "type": "test"}])

        after = datetime.utcnow()

        # All timestamps should be between before and after
        for response_data in [success, error, val_error]:
            ts = response_data["timestamp"]
            if isinstance(ts, str):
                # Handle string timestamps
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
            assert before <= ts <= after + timedelta(seconds=1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
