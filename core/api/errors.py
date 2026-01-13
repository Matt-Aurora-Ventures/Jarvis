"""
JARVIS API Error Handling

Consistent error responses across all API endpoints:
- Standardized error format
- Error codes for programmatic handling
- Human-readable messages
- Debug info in development

Response format:
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid wallet address",
        "details": {...},
        "request_id": "abc123"
    }
}

Usage:
    from core.api.errors import (
        APIError,
        ValidationError,
        NotFoundError,
        error_handler,
    )

    # In FastAPI
    app.add_exception_handler(APIError, error_handler)

    # Raise errors
    raise ValidationError("Invalid wallet address", field="wallet")
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standard error codes."""
    # Client errors (4xx)
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    UNPROCESSABLE = "UNPROCESSABLE_ENTITY"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

    # Business logic errors
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    TRANSACTION_FAILED = "TRANSACTION_FAILED"
    WALLET_ERROR = "WALLET_ERROR"
    TOKEN_ERROR = "TOKEN_ERROR"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


@dataclass
class ErrorDetail:
    """Structured error detail."""
    field: Optional[str] = None
    message: str = ""
    code: Optional[str] = None


@dataclass
class APIError(Exception):
    """
    Base API error with structured response.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        status_code: HTTP status code
        details: Additional error details
        headers: Custom response headers
    """
    message: str
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500
    details: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    errors: List[ErrorDetail] = field(default_factory=list)

    def __post_init__(self):
        super().__init__(self.message)

    def to_dict(self, include_debug: bool = False) -> Dict[str, Any]:
        """Convert to response dictionary."""
        error_dict = {
            "code": self.code.value,
            "message": self.message,
        }

        if self.details:
            error_dict["details"] = self.details

        if self.errors:
            error_dict["errors"] = [
                {k: v for k, v in {
                    "field": e.field,
                    "message": e.message,
                    "code": e.code,
                }.items() if v}
                for e in self.errors
            ]

        if include_debug:
            error_dict["debug"] = {
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {"error": error_dict}


# Specific error classes

class BadRequestError(APIError):
    """400 Bad Request."""
    def __init__(
        self,
        message: str = "Bad request",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.BAD_REQUEST,
            status_code=400,
            details=details,
        )


class ValidationError(APIError):
    """422 Validation Error."""
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        errors: Optional[List[ErrorDetail]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            details=details,
            errors=errors or [],
        )
        if field:
            self.errors.append(ErrorDetail(field=field, message=message))


class UnauthorizedError(APIError):
    """401 Unauthorized."""
    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            status_code=401,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(APIError):
    """403 Forbidden."""
    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            status_code=403,
            details=details,
        )


class NotFoundError(APIError):
    """404 Not Found."""
    def __init__(
        self,
        message: str = "Resource not found",
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = {}
        if resource:
            details["resource"] = resource
        if resource_id:
            details["id"] = resource_id

        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            status_code=404,
            details=details if details else None,
        )


class ConflictError(APIError):
    """409 Conflict."""
    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT,
            status_code=409,
            details=details,
        )


class RateLimitError(APIError):
    """429 Too Many Requests."""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMITED,
            status_code=429,
            details={"retry_after": retry_after} if retry_after else None,
            headers=headers if headers else None,
        )


class InternalError(APIError):
    """500 Internal Server Error."""
    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            details=details,
        )


class ServiceUnavailableError(APIError):
    """503 Service Unavailable."""
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        retry_after: Optional[int] = None,
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            details={"retry_after": retry_after} if retry_after else None,
            headers=headers if headers else None,
        )


# Business logic errors

class InsufficientFundsError(APIError):
    """Insufficient funds for transaction."""
    def __init__(
        self,
        message: str = "Insufficient funds",
        required: Optional[float] = None,
        available: Optional[float] = None,
    ):
        details = {}
        if required is not None:
            details["required"] = required
        if available is not None:
            details["available"] = available

        super().__init__(
            message=message,
            code=ErrorCode.INSUFFICIENT_FUNDS,
            status_code=400,
            details=details if details else None,
        )


class TransactionError(APIError):
    """Transaction failed."""
    def __init__(
        self,
        message: str = "Transaction failed",
        tx_signature: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        details = {}
        if tx_signature:
            details["signature"] = tx_signature
        if reason:
            details["reason"] = reason

        super().__init__(
            message=message,
            code=ErrorCode.TRANSACTION_FAILED,
            status_code=400,
            details=details if details else None,
        )


class WalletError(APIError):
    """Wallet operation failed."""
    def __init__(
        self,
        message: str = "Wallet error",
        wallet: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        full_details = details or {}
        if wallet:
            full_details["wallet"] = wallet

        super().__init__(
            message=message,
            code=ErrorCode.WALLET_ERROR,
            status_code=400,
            details=full_details if full_details else None,
        )


class CircuitOpenError(APIError):
    """Circuit breaker is open."""
    def __init__(
        self,
        message: str = "Service circuit breaker is open",
        service: Optional[str] = None,
        retry_after: Optional[float] = None,
    ):
        details = {}
        if service:
            details["service"] = service
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code=ErrorCode.CIRCUIT_OPEN,
            status_code=503,
            details=details if details else None,
            headers={"Retry-After": str(int(retry_after))} if retry_after else None,
        )


# Error handler for FastAPI

async def error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    FastAPI exception handler for APIError.

    Usage:
        app.add_exception_handler(APIError, error_handler)
    """
    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)

    # Determine if we should include debug info
    include_debug = getattr(request.app.state, "debug", False)

    # Build response
    response_data = exc.to_dict(include_debug=include_debug)

    if request_id:
        response_data["error"]["request_id"] = request_id

    # Log error
    if exc.status_code >= 500:
        logger.error(
            f"API Error: {exc.code.value} - {exc.message}",
            extra={
                "status_code": exc.status_code,
                "request_id": request_id,
                "path": request.url.path,
            },
            exc_info=True,
        )
    else:
        logger.warning(
            f"API Error: {exc.code.value} - {exc.message}",
            extra={
                "status_code": exc.status_code,
                "request_id": request_id,
                "path": request.url.path,
            },
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=response_data,
        headers=exc.headers,
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unexpected exceptions.

    Usage:
        app.add_exception_handler(Exception, generic_error_handler)
    """
    request_id = getattr(request.state, "request_id", None)
    include_debug = getattr(request.app.state, "debug", False)

    logger.exception(
        f"Unhandled exception: {exc}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
        },
    )

    error = InternalError("An unexpected error occurred")
    response_data = error.to_dict(include_debug=include_debug)

    if request_id:
        response_data["error"]["request_id"] = request_id

    return JSONResponse(
        status_code=500,
        content=response_data,
    )


def setup_error_handlers(app):
    """
    Configure all error handlers for a FastAPI app.

    Usage:
        from core.api.errors import setup_error_handlers
        setup_error_handlers(app)
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(APIError, error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"]),
                message=error["msg"],
                code=error["type"],
            )
            for error in exc.errors()
        ]

        api_error = ValidationError(
            message="Request validation failed",
            errors=errors,
        )
        return await error_handler(request, api_error)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Map Starlette HTTP exceptions to our format
        code_map = {
            400: ErrorCode.BAD_REQUEST,
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.METHOD_NOT_ALLOWED,
            409: ErrorCode.CONFLICT,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMITED,
            500: ErrorCode.INTERNAL_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE,
        }

        api_error = APIError(
            message=str(exc.detail),
            code=code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR),
            status_code=exc.status_code,
        )
        return await error_handler(request, api_error)


if __name__ == "__main__":
    print("API Error Classes Demo")
    print("=" * 50)

    # Test error creation
    errors = [
        BadRequestError("Missing required field"),
        ValidationError("Invalid email format", field="email"),
        NotFoundError("User not found", resource="user", resource_id="123"),
        RateLimitError("Too many requests", retry_after=60),
        InsufficientFundsError(required=1.5, available=0.5),
        TransactionError("Transaction failed", tx_signature="abc123"),
    ]

    for error in errors:
        print(f"\n{error.__class__.__name__}:")
        print(f"  Status: {error.status_code}")
        print(f"  Code: {error.code.value}")
        print(f"  Response: {error.to_dict()}")

    print("\n\nDemo complete!")
