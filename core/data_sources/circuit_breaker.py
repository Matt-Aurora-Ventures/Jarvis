"""
DEPRECATED: Use core.resilience.circuit_breaker instead.

This module redirects to the unified circuit breaker implementation.
"""

import warnings

warnings.warn(
    "core.data_sources.circuit_breaker is deprecated. Use core.resilience.circuit_breaker instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the unified module
from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerState,
    CircuitOpenError,
    CircuitState,
    CircuitStats,
    API_CONFIGS,
    APICircuitBreaker,
    circuit_breaker,
    get_all_circuits,
    get_api_breaker,
    get_breaker,
    get_circuit_breaker,
    get_registry,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitBreakerState",
    "CircuitOpenError",
    "CircuitState",
    "CircuitStats",
    "API_CONFIGS",
    "APICircuitBreaker",
    "circuit_breaker",
    "get_all_circuits",
    "get_api_breaker",
    "get_breaker",
    "get_circuit_breaker",
    "get_registry",
]
