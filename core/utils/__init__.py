"""
Core Utilities - Reusable helpers.

This package keeps optional dependencies lazy/soft so minimal runtime profiles
(like isolated execution hosts) can import focused modules without pulling in
extras such as aiohttp.
"""

__all__: list[str] = []


def _export(module_names: list[str], module_globals: dict) -> None:
    for name in module_names:
        if name in module_globals:
            __all__.append(name)


from core.utils.rate_limiter import (  # noqa: E402
    MultiRateLimiter,
    RateLimiter,
    RateLimitConfig,
    SlidingWindow,
    TokenBucket,
    get_rate_limiter,
    rate_limited,
)

_export(
    [
        "RateLimiter",
        "MultiRateLimiter",
        "RateLimitConfig",
        "TokenBucket",
        "SlidingWindow",
        "get_rate_limiter",
        "rate_limited",
    ],
    globals(),
)

try:
    from core.utils.connection_pool import (  # noqa: E402
        ConnectionPool,
        PoolConfig,
        close_all_sessions,
        get_connection_pool,
        get_session,
    )

    _export(
        [
            "ConnectionPool",
            "PoolConfig",
            "get_connection_pool",
            "get_session",
            "close_all_sessions",
        ],
        globals(),
    )
except Exception:  # noqa: BLE001
    pass

from core.utils.timeout import (  # noqa: E402
    TimeoutError,
    race,
    retry_with_timeout,
    timeout,
    with_timeout,
    with_timeout_default,
)

_export(
    [
        "TimeoutError",
        "with_timeout",
        "with_timeout_default",
        "timeout",
        "race",
        "retry_with_timeout",
    ],
    globals(),
)

from core.utils.decorators import (  # noqa: E402
    deprecated,
    log_calls,
    measure_time,
    memoize,
    retry,
    singleton,
)

_export(
    [
        "retry",
        "log_calls",
        "memoize",
        "singleton",
        "deprecated",
        "measure_time",
    ],
    globals(),
)
