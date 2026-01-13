"""
JARVIS Resilience Patterns

Provides fault tolerance and reliability:
- Retry with exponential backoff
- Circuit breaker pattern
- Bulkhead isolation
- Timeout handling
"""

from core.resilience.retry import (
    RetryPolicy,
    RetryExhausted,
    RetryStats,
    RetryContext,
    retry,
    retry_async,
    retry_sync,
    AGGRESSIVE_RETRY,
    CONSERVATIVE_RETRY,
    API_RETRY,
    RPC_RETRY,
)

from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitStats,
    CircuitOpenError,
    circuit_breaker,
    get_circuit_breaker,
    get_all_circuits,
)

__all__ = [
    # Retry
    "RetryPolicy",
    "RetryExhausted",
    "RetryStats",
    "RetryContext",
    "retry",
    "retry_async",
    "retry_sync",
    "AGGRESSIVE_RETRY",
    "CONSERVATIVE_RETRY",
    "API_RETRY",
    "RPC_RETRY",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitStats",
    "CircuitOpenError",
    "circuit_breaker",
    "get_circuit_breaker",
    "get_all_circuits",
]
