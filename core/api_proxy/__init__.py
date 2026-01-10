"""
API Proxy & Gateway System

Unified API gateway with circuit breaking, caching, load balancing,
and multi-provider support.

Prompts #45, #61-64: API Proxy Infrastructure
"""

from .openrouter_proxy import (
    OpenRouterProxy,
    UserTier,
    TierConfig,
    UserCredits,
    UsageRecord,
    RateLimitState,
    TIER_CONFIGS,
    MODEL_PRICING,
    create_proxy_endpoints
)

from .gateway import (
    APIGateway,
    UpstreamProvider,
    ProviderStatus,
    CircuitState,
    CacheEntry,
    RequestContext,
    get_api_gateway
)

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState
)

from .cache import (
    RequestCache,
    CacheConfig,
    CacheStats
)

from .load_balancer import (
    LoadBalancer,
    LoadBalancerStrategy,
    ProviderHealth
)

__all__ = [
    # OpenRouter Proxy
    "OpenRouterProxy",
    "UserTier",
    "TierConfig",
    "UserCredits",
    "UsageRecord",
    "RateLimitState",
    "TIER_CONFIGS",
    "MODEL_PRICING",
    "create_proxy_endpoints",

    # Gateway
    "APIGateway",
    "UpstreamProvider",
    "ProviderStatus",
    "CircuitState",
    "CacheEntry",
    "RequestContext",
    "get_api_gateway",

    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerState",

    # Cache
    "RequestCache",
    "CacheConfig",
    "CacheStats",

    # Load Balancer
    "LoadBalancer",
    "LoadBalancerStrategy",
    "ProviderHealth"
]
