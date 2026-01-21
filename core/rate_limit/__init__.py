"""
Centralized rate limit tracking module.

Provides:
- Central registry for all service rate limits
- Usage tracking and metrics
- Preemptive backoff recommendations
"""

from core.rate_limit.centralized_tracker import (
    CentralizedRateLimitTracker,
    ServiceType,
    ServiceConfig,
    RateLimitState,
    get_rate_limit_tracker,
    track_request,
    wait_if_needed,
)

__all__ = [
    "CentralizedRateLimitTracker",
    "ServiceType",
    "ServiceConfig",
    "RateLimitState",
    "get_rate_limit_tracker",
    "track_request",
    "wait_if_needed",
]
