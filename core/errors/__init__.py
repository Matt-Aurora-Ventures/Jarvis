"""Error handling and exception classes."""
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
