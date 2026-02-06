"""
Rate limiting exceptions.

Provides custom exceptions for rate limit violations.
"""

from typing import Optional


class RateLimitExceeded(Exception):
    """
    Exception raised when a rate limit is exceeded.

    Attributes:
        key: The rate limit key that was exceeded
        limit: The limit that was exceeded
        window: The time window in seconds
        retry_after: Seconds until the request can be retried
    """

    def __init__(
        self,
        key: str,
        limit: int,
        window: float,
        retry_after: float,
        message: Optional[str] = None
    ):
        self.key = key
        self.limit = limit
        self.window = window
        self.retry_after = retry_after

        if message is None:
            message = (
                f"Rate limit exceeded for '{key}': "
                f"{limit} requests per {window}s. "
                f"Retry after {retry_after:.1f}s"
            )

        super().__init__(message)


class RateLimitConfigError(Exception):
    """Exception raised for invalid rate limit configuration."""
    pass
