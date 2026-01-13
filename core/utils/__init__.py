"""
Core Utilities - Reusable utilities for robustness and performance.
"""

from core.utils.rate_limiter import (
    RateLimiter,
    MultiRateLimiter,
    RateLimitConfig,
    TokenBucket,
    SlidingWindow,
    get_rate_limiter,
    rate_limited,
)

from core.utils.connection_pool import (
    ConnectionPool,
    PoolConfig,
    get_connection_pool,
    get_session,
    close_all_sessions,
)

from core.utils.timeout import (
    TimeoutError,
    with_timeout,
    with_timeout_default,
    timeout,
    race,
    retry_with_timeout,
)

from core.utils.decorators import (
    retry,
    log_calls,
    memoize,
    singleton,
    deprecated,
    measure_time,
)

__all__ = [
    # Rate limiting
    "RateLimiter",
    "MultiRateLimiter",
    "RateLimitConfig",
    "TokenBucket",
    "SlidingWindow",
    "get_rate_limiter",
    "rate_limited",
    # Connection pool
    "ConnectionPool",
    "PoolConfig",
    "get_connection_pool",
    "get_session",
    "close_all_sessions",
    # Timeout utilities
    "TimeoutError",
    "with_timeout",
    "with_timeout_default",
    "timeout",
    "race",
    "retry_with_timeout",
    # Decorators
    "retry",
    "log_calls",
    "memoize",
    "singleton",
    "deprecated",
    "measure_time",
]
