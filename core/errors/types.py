"""Enhanced error type hierarchy for Jarvis.

Provides fine-grained error classification for better error handling,
retry logic, and user-friendly error messages.
"""


class JarvisError(Exception):
    """Base exception for all Jarvis errors."""

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.message = message
        self.context = context


class TransientError(JarvisError):
    """Errors that may resolve on retry (network issues, rate limits, etc)."""

    def __init__(self, message: str, retry_after: int | None = None, **context):
        super().__init__(message, **context)
        self.retry_after = retry_after


class PermanentError(JarvisError):
    """Errors that won't resolve on retry (validation, auth, not found, etc)."""
    pass


class RetryableError(TransientError):
    """Explicitly retryable errors."""
    pass


class ServiceUnavailableError(TransientError):
    """Service temporarily unavailable."""
    pass


class QuotaExceededError(TransientError):
    """API quota or rate limit exceeded."""
    pass


class CircuitOpenError(TransientError):
    """Circuit breaker is open - service is failing."""
    pass


class PermissionDeniedError(PermanentError):
    """Permission or authorization denied."""
    pass
