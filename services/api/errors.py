"""
Standardized error responses for Jarvis API.

All API errors should use these functions to ensure consistent response format.
"""

from typing import Any, Dict, Optional
from flask import jsonify
from fastapi.responses import JSONResponse


# Error codes by category
ERROR_CODES = {
    # Voice errors (100-199)
    "VOICE_001": "Voice system not available",
    "VOICE_002": "Microphone not accessible",
    "VOICE_003": "TTS engine failure",
    "VOICE_004": "STT engine failure",
    "VOICE_005": "Wake word detection failed",

    # Trading errors (200-299)
    "TRADE_001": "Trade execution failed",
    "TRADE_002": "Insufficient balance",
    "TRADE_003": "Invalid trading pair",
    "TRADE_004": "Slippage exceeded",
    "TRADE_005": "Position not found",

    # Auth errors (300-399)
    "AUTH_001": "Not authenticated",
    "AUTH_002": "Invalid token",
    "AUTH_003": "Token expired",
    "AUTH_004": "Insufficient permissions",

    # Validation errors (400-499)
    "VAL_001": "Invalid request body",
    "VAL_002": "Missing required field",
    "VAL_003": "Invalid field format",
    "VAL_004": "Value out of range",

    # Provider errors (500-599)
    "PROV_001": "No providers available",
    "PROV_002": "Provider rate limited",
    "PROV_003": "Provider quota exceeded",
    "PROV_004": "Provider timeout",

    # System errors (600-699)
    "SYS_001": "Database connection failed",
    "SYS_002": "Service unavailable",
    "SYS_003": "Internal server error",
    "SYS_004": "Configuration error",
}


def make_error_response(
    error_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    http_status: int = 400
) -> Dict[str, Any]:
    """Create a standardized error response dict.

    Args:
        error_code: Error code from ERROR_CODES
        message: Custom error message (uses default if not provided)
        details: Additional error details
        http_status: HTTP status code (not included in response body)

    Returns:
        Standardized error response dict
    """
    default_message = ERROR_CODES.get(error_code, "Unknown error")

    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message or default_message,
        }
    }

    if details:
        response["error"]["details"] = details

    return response


def flask_error(
    error_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    http_status: int = 400
):
    """Create a Flask JSON error response.

    Example:
        @app.route('/api/voice/start')
        def start_voice():
            if not voice_available:
                return flask_error("VOICE_001", http_status=503)
            return jsonify({"success": True})
    """
    response = make_error_response(error_code, message, details, http_status)
    return jsonify(response), http_status


def fastapi_error(
    error_code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    http_status: int = 400
) -> JSONResponse:
    """Create a FastAPI JSON error response.

    Example:
        @app.get("/api/voice/start")
        async def start_voice():
            if not voice_available:
                return fastapi_error("VOICE_001", http_status=503)
            return {"success": True}
    """
    response = make_error_response(error_code, message, details, http_status)
    return JSONResponse(content=response, status_code=http_status)


def make_success_response(
    data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standardized success response.

    Args:
        data: Response data payload
        message: Optional success message

    Returns:
        Standardized success response dict
    """
    response = {"success": True}

    if data:
        response["data"] = data

    if message:
        response["message"] = message

    return response


def flask_success(
    data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    http_status: int = 200
):
    """Create a Flask JSON success response."""
    return jsonify(make_success_response(data, message)), http_status


def fastapi_success(
    data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    http_status: int = 200
) -> JSONResponse:
    """Create a FastAPI JSON success response."""
    return JSONResponse(
        content=make_success_response(data, message),
        status_code=http_status
    )
