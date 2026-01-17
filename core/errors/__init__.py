"""
Error handling and exception classes.

NOTE: There are two error hierarchies in this codebase:
1. core.errors (this module) - Internal errors with JarvisError as root
2. core.api.errors - HTTP/API errors with APIError as root (for FastAPI responses)

These are intentionally separate:
- Use JarvisError for internal business logic
- Use APIError for HTTP endpoint error responses

Example usage:
    from core.errors import ValidationError  # Internal validation
    from core.api.errors import ValidationError as APIValidationError  # HTTP 422

Do NOT mix these hierarchies.
"""

from core.errors.exceptions import (
    JarvisError, ValidationError, AuthenticationError, AuthorizationError,
    NotFoundError, RateLimitError, ProviderError, TradingError
)
from core.errors.classification import classify_error, ErrorCategory, ClassifiedError
from core.errors.recovery import RecoveryStrategy, with_recovery

__all__ = [
    "JarvisError", "ValidationError", "AuthenticationError", "AuthorizationError",
    "NotFoundError", "RateLimitError", "ProviderError", "TradingError",
    "classify_error", "ErrorCategory", "ClassifiedError",
    "RecoveryStrategy", "with_recovery"
]
