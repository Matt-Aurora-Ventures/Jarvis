"""
JARVIS API Utilities

Provides API helpers:
- Versioning
- Response formatting
- Pagination
- Error handling
"""

from core.api.versioning import (
    APIVersion,
    VersionStatus,
    VersionRegistry,
    VersionedAPI,
    api_version,
    versioned_response,
    paginated_response,
    get_version_registry,
    create_versioned_router,
    version_header_middleware,
)

from core.api.errors import (
    APIError,
    ErrorCode,
    ErrorDetail,
    BadRequestError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    RateLimitError,
    InternalError,
    ServiceUnavailableError,
    InsufficientFundsError,
    TransactionError,
    WalletError,
    CircuitOpenError,
    error_handler,
    generic_error_handler,
    setup_error_handlers,
)

__all__ = [
    # Versioning
    "APIVersion",
    "VersionStatus",
    "VersionRegistry",
    "VersionedAPI",
    "api_version",
    "versioned_response",
    "paginated_response",
    "get_version_registry",
    "create_versioned_router",
    "version_header_middleware",
    # Errors
    "APIError",
    "ErrorCode",
    "ErrorDetail",
    "BadRequestError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "InternalError",
    "ServiceUnavailableError",
    "InsufficientFundsError",
    "TransactionError",
    "WalletError",
    "CircuitOpenError",
    "error_handler",
    "generic_error_handler",
    "setup_error_handlers",
]
