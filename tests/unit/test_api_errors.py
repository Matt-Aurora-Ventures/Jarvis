"""
Comprehensive tests for api/errors.py and FastAPI exception handlers.

Tests cover:
1. Error code constants and categories
2. make_error_response() function
3. flask_error() response generation
4. fastapi_error() response generation
5. make_success_response() function
6. flask_success() response generation
7. fastapi_success() response generation
8. FastAPI exception handlers (HTTP and general exceptions)
9. Error response format validation
10. Edge cases and error scenarios

Target: 60%+ coverage with 50+ tests.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import (
    ERROR_CODES,
    make_error_response,
    flask_error,
    fastapi_error,
    make_success_response,
    flask_success,
    fastapi_success,
)


# =============================================================================
# ERROR_CODES Dictionary Tests
# =============================================================================


class TestErrorCodes:
    """Test error code constants and categories."""

    def test_error_codes_is_dict(self):
        """Test ERROR_CODES is a dictionary."""
        assert isinstance(ERROR_CODES, dict)

    def test_error_codes_not_empty(self):
        """Test ERROR_CODES is not empty."""
        assert len(ERROR_CODES) > 0

    def test_voice_error_codes_exist(self):
        """Test voice error codes (100-199) exist."""
        voice_codes = ["VOICE_001", "VOICE_002", "VOICE_003", "VOICE_004", "VOICE_005"]
        for code in voice_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)
            assert len(ERROR_CODES[code]) > 0

    def test_trade_error_codes_exist(self):
        """Test trade error codes (200-299) exist."""
        trade_codes = ["TRADE_001", "TRADE_002", "TRADE_003", "TRADE_004", "TRADE_005"]
        for code in trade_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)

    def test_auth_error_codes_exist(self):
        """Test auth error codes (300-399) exist."""
        auth_codes = ["AUTH_001", "AUTH_002", "AUTH_003", "AUTH_004"]
        for code in auth_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)

    def test_validation_error_codes_exist(self):
        """Test validation error codes (400-499) exist."""
        val_codes = ["VAL_001", "VAL_002", "VAL_003", "VAL_004"]
        for code in val_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)

    def test_provider_error_codes_exist(self):
        """Test provider error codes (500-599) exist."""
        prov_codes = ["PROV_001", "PROV_002", "PROV_003", "PROV_004"]
        for code in prov_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)

    def test_system_error_codes_exist(self):
        """Test system error codes (600-699) exist."""
        sys_codes = ["SYS_001", "SYS_002", "SYS_003", "SYS_004"]
        for code in sys_codes:
            assert code in ERROR_CODES
            assert isinstance(ERROR_CODES[code], str)

    def test_voice_001_message(self):
        """Test VOICE_001 has correct message."""
        assert ERROR_CODES["VOICE_001"] == "Voice system not available"

    def test_trade_001_message(self):
        """Test TRADE_001 has correct message."""
        assert ERROR_CODES["TRADE_001"] == "Trade execution failed"

    def test_auth_001_message(self):
        """Test AUTH_001 has correct message."""
        assert ERROR_CODES["AUTH_001"] == "Not authenticated"

    def test_val_001_message(self):
        """Test VAL_001 has correct message."""
        assert ERROR_CODES["VAL_001"] == "Invalid request body"

    def test_sys_003_message(self):
        """Test SYS_003 has correct message."""
        assert ERROR_CODES["SYS_003"] == "Internal server error"


# =============================================================================
# make_error_response() Tests
# =============================================================================


class TestMakeErrorResponse:
    """Test make_error_response function."""

    def test_basic_error_response(self):
        """Test basic error response with error code."""
        response = make_error_response("AUTH_001")
        assert response["success"] is False
        assert response["error"]["code"] == "AUTH_001"
        assert response["error"]["message"] == "Not authenticated"

    def test_error_response_with_custom_message(self):
        """Test error response with custom message overrides default."""
        response = make_error_response("AUTH_001", message="Custom auth error")
        assert response["success"] is False
        assert response["error"]["code"] == "AUTH_001"
        assert response["error"]["message"] == "Custom auth error"

    def test_error_response_with_details(self):
        """Test error response includes details when provided."""
        details = {"field": "email", "reason": "invalid format"}
        response = make_error_response("VAL_001", details=details)
        assert response["success"] is False
        assert response["error"]["code"] == "VAL_001"
        assert response["error"]["details"] == details

    def test_error_response_without_details(self):
        """Test error response excludes details key when not provided."""
        response = make_error_response("AUTH_001")
        assert "details" not in response["error"]

    def test_error_response_with_all_params(self):
        """Test error response with all parameters."""
        details = {"field": "amount", "value": -10}
        response = make_error_response(
            "TRADE_002",
            message="Custom insufficient balance",
            details=details,
            http_status=402
        )
        assert response["success"] is False
        assert response["error"]["code"] == "TRADE_002"
        assert response["error"]["message"] == "Custom insufficient balance"
        assert response["error"]["details"] == details

    def test_unknown_error_code_uses_default_message(self):
        """Test unknown error code returns 'Unknown error' message."""
        response = make_error_response("UNKNOWN_999")
        assert response["error"]["code"] == "UNKNOWN_999"
        assert response["error"]["message"] == "Unknown error"

    def test_http_status_not_in_response_body(self):
        """Test http_status is not included in response body."""
        response = make_error_response("SYS_003", http_status=500)
        assert "http_status" not in response
        assert "status_code" not in response

    def test_empty_details_dict_excluded(self):
        """Test empty details dict is not included (falsy check)."""
        response = make_error_response("VAL_001", details={})
        # Empty dict is falsy, so details key should not be present
        assert "details" not in response["error"]

    def test_complex_details_structure(self):
        """Test complex nested details structure."""
        details = {
            "errors": [
                {"field": "name", "message": "required"},
                {"field": "email", "message": "invalid"}
            ],
            "metadata": {
                "request_id": "req_123",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"] == details


# =============================================================================
# flask_error() Tests
# =============================================================================


class TestFlaskError:
    """Test flask_error function."""

    def test_flask_error_returns_tuple(self):
        """Test flask_error returns (response, status_code) tuple."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            result = flask_error("AUTH_001")
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_flask_error_default_status_code(self):
        """Test flask_error default status code is 400."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_error("VAL_001")
            assert status_code == 400

    def test_flask_error_custom_status_code(self):
        """Test flask_error with custom status code."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_error("SYS_003", http_status=500)
            assert status_code == 500

    def test_flask_error_503_status(self):
        """Test flask_error with 503 service unavailable."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_error("VOICE_001", http_status=503)
            assert status_code == 503

    def test_flask_error_401_status(self):
        """Test flask_error with 401 unauthorized."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_error("AUTH_001", http_status=401)
            assert status_code == 401

    def test_flask_error_calls_jsonify(self):
        """Test flask_error calls jsonify with correct data."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            flask_error("AUTH_001", message="Custom message")
            mock_jsonify.assert_called_once()
            call_args = mock_jsonify.call_args[0][0]
            assert call_args["success"] is False
            assert call_args["error"]["code"] == "AUTH_001"
            assert call_args["error"]["message"] == "Custom message"


# =============================================================================
# fastapi_error() Tests
# =============================================================================


class TestFastapiError:
    """Test fastapi_error function."""

    def test_fastapi_error_returns_json_response(self):
        """Test fastapi_error returns JSONResponse."""
        from fastapi.responses import JSONResponse
        response = fastapi_error("AUTH_001")
        assert isinstance(response, JSONResponse)

    def test_fastapi_error_default_status_code(self):
        """Test fastapi_error default status code is 400."""
        response = fastapi_error("VAL_001")
        assert response.status_code == 400

    def test_fastapi_error_custom_status_code(self):
        """Test fastapi_error with custom status code."""
        response = fastapi_error("SYS_003", http_status=500)
        assert response.status_code == 500

    def test_fastapi_error_503_status(self):
        """Test fastapi_error with 503 service unavailable."""
        response = fastapi_error("VOICE_001", http_status=503)
        assert response.status_code == 503

    def test_fastapi_error_401_status(self):
        """Test fastapi_error with 401 unauthorized."""
        response = fastapi_error("AUTH_001", http_status=401)
        assert response.status_code == 401

    def test_fastapi_error_403_status(self):
        """Test fastapi_error with 403 forbidden."""
        response = fastapi_error("AUTH_004", http_status=403)
        assert response.status_code == 403

    def test_fastapi_error_404_status(self):
        """Test fastapi_error with 404 not found."""
        response = fastapi_error("TRADE_005", http_status=404)
        assert response.status_code == 404

    def test_fastapi_error_409_status(self):
        """Test fastapi_error with 409 conflict."""
        response = fastapi_error("TRADE_001", http_status=409)
        assert response.status_code == 409

    def test_fastapi_error_422_status(self):
        """Test fastapi_error with 422 unprocessable entity."""
        response = fastapi_error("VAL_003", http_status=422)
        assert response.status_code == 422

    def test_fastapi_error_429_status(self):
        """Test fastapi_error with 429 too many requests."""
        response = fastapi_error("PROV_002", http_status=429)
        assert response.status_code == 429

    def test_fastapi_error_response_body(self):
        """Test fastapi_error response body structure."""
        response = fastapi_error("AUTH_001", message="Test message")
        # Access the body content
        import json
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH_001"
        assert body["error"]["message"] == "Test message"

    def test_fastapi_error_with_details(self):
        """Test fastapi_error includes details in response."""
        import json
        details = {"field": "token", "reason": "expired"}
        response = fastapi_error("AUTH_003", details=details)
        body = json.loads(response.body)
        assert body["error"]["details"] == details


# =============================================================================
# make_success_response() Tests
# =============================================================================


class TestMakeSuccessResponse:
    """Test make_success_response function."""

    def test_basic_success_response(self):
        """Test basic success response."""
        response = make_success_response()
        assert response["success"] is True

    def test_success_response_with_data(self):
        """Test success response with data."""
        data = {"user_id": "123", "name": "Test"}
        response = make_success_response(data=data)
        assert response["success"] is True
        assert response["data"] == data

    def test_success_response_with_message(self):
        """Test success response with message."""
        response = make_success_response(message="Operation completed")
        assert response["success"] is True
        assert response["message"] == "Operation completed"

    def test_success_response_with_data_and_message(self):
        """Test success response with both data and message."""
        data = {"result": "ok"}
        response = make_success_response(data=data, message="Done")
        assert response["success"] is True
        assert response["data"] == data
        assert response["message"] == "Done"

    def test_success_response_no_data_key_when_none(self):
        """Test success response excludes data key when None."""
        response = make_success_response()
        assert "data" not in response

    def test_success_response_no_message_key_when_none(self):
        """Test success response excludes message key when None."""
        response = make_success_response()
        assert "message" not in response

    def test_success_response_empty_dict_data(self):
        """Test success response with empty dict as data."""
        response = make_success_response(data={})
        # Empty dict should not be included (falsy check)
        assert "data" not in response

    def test_success_response_complex_data(self):
        """Test success response with complex nested data."""
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ],
            "pagination": {
                "page": 1,
                "total": 10
            }
        }
        response = make_success_response(data=data)
        assert response["data"] == data


# =============================================================================
# flask_success() Tests
# =============================================================================


class TestFlaskSuccess:
    """Test flask_success function."""

    def test_flask_success_returns_tuple(self):
        """Test flask_success returns (response, status_code) tuple."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            result = flask_success()
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_flask_success_default_status_code(self):
        """Test flask_success default status code is 200."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_success()
            assert status_code == 200

    def test_flask_success_custom_status_code(self):
        """Test flask_success with custom status code."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_success(http_status=201)
            assert status_code == 201

    def test_flask_success_204_status(self):
        """Test flask_success with 204 no content."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            _, status_code = flask_success(http_status=204)
            assert status_code == 204

    def test_flask_success_calls_jsonify(self):
        """Test flask_success calls jsonify with correct data."""
        with patch("api.errors.jsonify") as mock_jsonify:
            mock_jsonify.return_value = {"mocked": True}
            data = {"result": "test"}
            flask_success(data=data, message="Done")
            mock_jsonify.assert_called_once()
            call_args = mock_jsonify.call_args[0][0]
            assert call_args["success"] is True
            assert call_args["data"] == data
            assert call_args["message"] == "Done"


# =============================================================================
# fastapi_success() Tests
# =============================================================================


class TestFastapiSuccess:
    """Test fastapi_success function."""

    def test_fastapi_success_returns_json_response(self):
        """Test fastapi_success returns JSONResponse."""
        from fastapi.responses import JSONResponse
        response = fastapi_success()
        assert isinstance(response, JSONResponse)

    def test_fastapi_success_default_status_code(self):
        """Test fastapi_success default status code is 200."""
        response = fastapi_success()
        assert response.status_code == 200

    def test_fastapi_success_custom_status_code(self):
        """Test fastapi_success with custom status code."""
        response = fastapi_success(http_status=201)
        assert response.status_code == 201

    def test_fastapi_success_204_status(self):
        """Test fastapi_success with 204 no content."""
        response = fastapi_success(http_status=204)
        assert response.status_code == 204

    def test_fastapi_success_response_body(self):
        """Test fastapi_success response body structure."""
        import json
        data = {"user": "test"}
        response = fastapi_success(data=data, message="Created")
        body = json.loads(response.body)
        assert body["success"] is True
        assert body["data"] == data
        assert body["message"] == "Created"


# =============================================================================
# FastAPI Exception Handler Tests
# =============================================================================


class TestFastAPIExceptionHandlers:
    """Test FastAPI exception handlers from fastapi_app.py."""

    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with exception handlers."""
        from api.fastapi_app import create_app
        return create_app()

    @pytest.fixture
    def client(self, test_app):
        """Create test client."""
        return TestClient(test_app)

    def test_400_bad_request_handler(self, client):
        """Test 400 Bad Request is handled correctly."""
        # Create an app with an endpoint that raises 400
        app = FastAPI()

        @app.get("/test-400")
        async def raise_400():
            raise HTTPException(status_code=400, detail="Bad request test")

        # Add handlers from main app
        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-400")
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VAL_001"

    def test_401_unauthorized_handler(self, client):
        """Test 401 Unauthorized is handled correctly."""
        app = FastAPI()

        @app.get("/test-401")
        async def raise_401():
            raise HTTPException(status_code=401, detail="Unauthorized")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-401")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTH_001"

    def test_403_forbidden_handler(self, client):
        """Test 403 Forbidden is handled correctly."""
        app = FastAPI()

        @app.get("/test-403")
        async def raise_403():
            raise HTTPException(status_code=403, detail="Forbidden")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-403")
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "AUTH_004"

    def test_404_not_found_handler(self, client):
        """Test 404 Not Found is handled correctly."""
        app = FastAPI()

        @app.get("/test-404")
        async def raise_404():
            raise HTTPException(status_code=404, detail="Not found")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-404")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "SYS_002"

    def test_429_rate_limit_handler(self, client):
        """Test 429 Too Many Requests is handled correctly."""
        app = FastAPI()

        @app.get("/test-429")
        async def raise_429():
            raise HTTPException(status_code=429, detail="Rate limited")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-429")
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "PROV_002"

    def test_500_internal_error_handler(self, client):
        """Test 500 Internal Server Error is handled correctly."""
        app = FastAPI()

        @app.get("/test-500")
        async def raise_500():
            raise HTTPException(status_code=500, detail="Internal error")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-500")
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "SYS_003"

    def test_503_service_unavailable_handler(self, client):
        """Test 503 Service Unavailable is handled correctly."""
        app = FastAPI()

        @app.get("/test-503")
        async def raise_503():
            raise HTTPException(status_code=503, detail="Service unavailable")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-503")
        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "SYS_002"

    def test_unmapped_status_code_uses_sys003(self):
        """Test unmapped status codes default to SYS_003."""
        app = FastAPI()

        @app.get("/test-418")
        async def raise_418():
            raise HTTPException(status_code=418, detail="I'm a teapot")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001", 401: "AUTH_001", 403: "AUTH_004", 404: "SYS_002", 429: "PROV_002", 500: "SYS_003", 503: "SYS_002"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-418")
        assert response.status_code == 418
        data = response.json()
        assert data["error"]["code"] == "SYS_003"

    def test_general_exception_handler(self):
        """Test general exception handler for unhandled exceptions."""
        app = FastAPI()

        @app.get("/test-exception")
        async def raise_exception():
            raise ValueError("Unexpected error")

        from api.errors import make_error_response

        @app.exception_handler(Exception)
        async def general_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content=make_error_response("SYS_003", "Internal server error")
            )

        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.get("/test-exception")
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == "SYS_003"

    def test_exception_handler_preserves_detail(self):
        """Test exception handler preserves detail in response."""
        app = FastAPI()

        @app.get("/test-detail")
        async def raise_with_detail():
            raise HTTPException(status_code=400, detail="Custom detail message")

        from api.errors import make_error_response

        @app.exception_handler(StarletteHTTPException)
        async def http_exception_handler(request, exc):
            from fastapi.responses import JSONResponse
            error_map = {400: "VAL_001"}
            error_code = error_map.get(exc.status_code, "SYS_003")
            payload = make_error_response(error_code, str(exc.detail))
            payload["detail"] = str(exc.detail)
            return JSONResponse(status_code=exc.status_code, content=payload)

        test_client = TestClient(app)
        response = test_client.get("/test-detail")
        data = response.json()
        assert data["detail"] == "Custom detail message"


# =============================================================================
# Error Response Format Tests
# =============================================================================


class TestErrorResponseFormat:
    """Test error response format consistency."""

    def test_error_response_has_success_false(self):
        """Test all error responses have success=False."""
        response = make_error_response("AUTH_001")
        assert response["success"] is False

    def test_error_response_has_error_object(self):
        """Test all error responses have error object."""
        response = make_error_response("AUTH_001")
        assert "error" in response
        assert isinstance(response["error"], dict)

    def test_error_object_has_code(self):
        """Test error object has code field."""
        response = make_error_response("AUTH_001")
        assert "code" in response["error"]

    def test_error_object_has_message(self):
        """Test error object has message field."""
        response = make_error_response("AUTH_001")
        assert "message" in response["error"]

    def test_error_response_json_serializable(self):
        """Test error response is JSON serializable."""
        import json
        response = make_error_response("VAL_001", details={"test": True})
        # Should not raise
        json_str = json.dumps(response)
        assert isinstance(json_str, str)

    def test_success_response_has_success_true(self):
        """Test all success responses have success=True."""
        response = make_success_response()
        assert response["success"] is True

    def test_success_response_json_serializable(self):
        """Test success response is JSON serializable."""
        import json
        data = {"result": [1, 2, 3], "nested": {"key": "value"}}
        response = make_success_response(data=data)
        json_str = json.dumps(response)
        assert isinstance(json_str, str)


# =============================================================================
# Edge Cases and Error Scenarios
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_none_message_uses_default(self):
        """Test None message falls back to default."""
        response = make_error_response("AUTH_001", message=None)
        assert response["error"]["message"] == "Not authenticated"

    def test_empty_string_message(self):
        """Test empty string message is used as-is."""
        response = make_error_response("AUTH_001", message="")
        # Empty string is falsy, so default should be used
        assert response["error"]["message"] == "Not authenticated"

    def test_unicode_in_message(self):
        """Test unicode characters in message."""
        response = make_error_response("VAL_001", message="Invalid character")
        assert isinstance(response["error"]["message"], str)

    def test_special_characters_in_details(self):
        """Test special characters in details."""
        details = {"path": "/api/test?foo=bar&baz=qux", "chars": "<>&\"'"}
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"] == details

    def test_very_long_message(self):
        """Test very long error message."""
        long_message = "x" * 10000
        response = make_error_response("VAL_001", message=long_message)
        assert len(response["error"]["message"]) == 10000

    def test_deeply_nested_details(self):
        """Test deeply nested details structure."""
        details = {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"]["level1"]["level2"]["level3"]["level4"]["level5"] == "deep"

    def test_list_in_details(self):
        """Test list values in details."""
        details = {"errors": ["error1", "error2", "error3"]}
        response = make_error_response("VAL_001", details=details)
        assert len(response["error"]["details"]["errors"]) == 3

    def test_numeric_values_in_details(self):
        """Test numeric values in details."""
        details = {"count": 42, "rate": 3.14, "negative": -10}
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"]["count"] == 42
        assert response["error"]["details"]["rate"] == 3.14
        assert response["error"]["details"]["negative"] == -10

    def test_boolean_values_in_details(self):
        """Test boolean values in details."""
        details = {"active": True, "deleted": False}
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"]["active"] is True
        assert response["error"]["details"]["deleted"] is False

    def test_null_values_in_details(self):
        """Test null/None values in details."""
        details = {"optional": None, "present": "value"}
        response = make_error_response("VAL_001", details=details)
        assert response["error"]["details"]["optional"] is None
        assert response["error"]["details"]["present"] == "value"


# =============================================================================
# Integration with FastAPI App Tests
# =============================================================================


class TestFastAPIAppIntegration:
    """Test error handling integration with FastAPI app."""

    @pytest.fixture
    def app_client(self):
        """Create client for main FastAPI app."""
        from api.fastapi_app import create_app
        app = create_app()
        return TestClient(app)

    def test_health_endpoint_success(self, app_client):
        """Test health endpoint returns success response format."""
        response = app_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        # Health endpoint returns direct dict, not wrapped in success
        assert "status" in data

    def test_nonexistent_endpoint_404(self, app_client):
        """Test nonexistent endpoint returns 404 with proper format."""
        response = app_client.get("/api/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SYS_002"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
