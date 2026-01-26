"""
Unified API Gateway

Combines circuit breaking, caching, load balancing, and request routing
into a single cohesive gateway.

Prompts #45: API Proxy System - Gateway
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import aiohttp
from aiohttp import ClientTimeout
import json

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError
)
from .cache import RequestCache, CacheConfig
from .load_balancer import (
    LoadBalancer,
    LoadBalancerStrategy,
    ProviderConfig,
    NoHealthyProviderError
)

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    """Status of an upstream provider"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class CircuitState(str, Enum):
    """Circuit breaker states (re-export)"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class UpstreamProvider:
    """Configuration for an upstream API provider"""
    name: str
    base_url: str
    api_key: Optional[str] = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    cache_ttl: int = 300  # Default cache TTL
    weight: int = 100     # For load balancing
    priority: int = 0     # For failover
    headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestContext:
    """Context for a proxied request"""
    request_id: str
    user_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    provider: Optional[str] = None
    attempts: int = 0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000


@dataclass
class GatewayStats:
    """Gateway statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    circuit_breaks: int = 0
    total_latency_ms: float = 0.0
    requests_by_provider: Dict[str, int] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests


class APIGateway:
    """
    Unified API Gateway with circuit breaking, caching, and load balancing.

    Features:
    - Multi-provider support with automatic failover
    - Request/response caching with TTL
    - Circuit breaking for failing upstreams
    - Load balancing across providers
    - Request transformation and middleware
    - Retry with exponential backoff
    """

    def __init__(
        self,
        default_cache_ttl: int = 300,
        load_balancer_strategy: LoadBalancerStrategy = LoadBalancerStrategy.WEIGHTED
    ):
        self._providers: Dict[str, UpstreamProvider] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._load_balancer = LoadBalancer(load_balancer_strategy)
        self._cache = RequestCache(CacheConfig(default_ttl=default_cache_ttl))
        self._stats = GatewayStats()
        self._session: Optional[aiohttp.ClientSession] = None
        self._middleware: List[Callable] = []
        self._lock = asyncio.Lock()

    async def start(self):
        """Initialize the gateway"""
        # Configure timeouts: 60s total, 30s connect (safety net - per-request timeouts take precedence)
        timeout = ClientTimeout(total=60, connect=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        logger.info("API Gateway started")

    async def stop(self):
        """Shutdown the gateway"""
        if self._session:
            await self._session.close()
        logger.info("API Gateway stopped")

    # =========================================================================
    # PROVIDER MANAGEMENT
    # =========================================================================

    def register_provider(self, provider: UpstreamProvider):
        """Register an upstream provider"""
        self._providers[provider.name] = provider

        # Create circuit breaker
        self._circuit_breakers[provider.name] = CircuitBreaker(
            name=f"gateway_{provider.name}",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                success_threshold=3
            )
        )

        # Add to load balancer
        self._load_balancer.add_provider(ProviderConfig(
            name=provider.name,
            base_url=provider.base_url,
            weight=provider.weight,
            priority=provider.priority,
            timeout_seconds=provider.timeout_seconds
        ))

        logger.info(f"Registered provider: {provider.name}")

    def unregister_provider(self, name: str):
        """Unregister a provider"""
        self._providers.pop(name, None)
        self._circuit_breakers.pop(name, None)
        self._load_balancer.remove_provider(name)
        logger.info(f"Unregistered provider: {name}")

    def get_provider(self, name: str) -> Optional[UpstreamProvider]:
        """Get a provider by name"""
        return self._providers.get(name)

    def get_provider_status(self, name: str) -> ProviderStatus:
        """Get status of a provider"""
        if name not in self._providers:
            return ProviderStatus.DISABLED

        provider = self._providers[name]
        if not provider.enabled:
            return ProviderStatus.DISABLED

        health = self._load_balancer.get_provider_health(name)
        if not health or not health.is_healthy:
            return ProviderStatus.UNHEALTHY

        if health.health_score < 70:
            return ProviderStatus.DEGRADED

        return ProviderStatus.HEALTHY

    # =========================================================================
    # MIDDLEWARE
    # =========================================================================

    def add_middleware(self, middleware: Callable):
        """Add request/response middleware"""
        self._middleware.append(middleware)

    async def _apply_middleware(
        self,
        ctx: RequestContext,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply middleware to request"""
        for mw in self._middleware:
            if asyncio.iscoroutinefunction(mw):
                request = await mw(ctx, request)
            else:
                request = mw(ctx, request)
        return request

    # =========================================================================
    # REQUEST HANDLING
    # =========================================================================

    async def request(
        self,
        method: str,
        path: str,
        provider_name: Optional[str] = None,
        params: Optional[Dict] = None,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        cache_ttl: Optional[int] = None,
        skip_cache: bool = False,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a proxied request to upstream.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path
            provider_name: Specific provider or None for load balancer
            params: Query parameters
            body: Request body
            headers: Additional headers
            cache_ttl: Cache TTL override
            skip_cache: Skip cache lookup
            user_id: User making request
            metadata: Additional context

        Returns:
            Response data
        """
        ctx = RequestContext(
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            metadata=metadata or {}
        )

        self._stats.total_requests += 1

        try:
            # Check cache for GET requests
            if method.upper() == "GET" and not skip_cache:
                cache_key = self._cache._generate_key(method, path, params, body)
                cached = await self._cache.get(cache_key)
                if cached is not None:
                    self._stats.cache_hits += 1
                    ctx.cached = True
                    return {
                        "data": cached,
                        "cached": True,
                        "request_id": ctx.request_id
                    }
                self._stats.cache_misses += 1

            # Select provider
            if provider_name:
                provider = self._providers.get(provider_name)
                if not provider:
                    raise ValueError(f"Unknown provider: {provider_name}")
            else:
                selected = await self._load_balancer.select_provider()
                if not selected:
                    raise NoHealthyProviderError("No healthy providers")
                provider = self._providers[selected]

            ctx.provider = provider.name

            # Build request
            request = {
                "method": method,
                "url": f"{provider.base_url}{path}",
                "params": params,
                "json": body if body else None,
                "headers": {
                    **(provider.headers or {}),
                    **(headers or {})
                },
                "timeout": aiohttp.ClientTimeout(total=provider.timeout_seconds)
            }

            # Add API key if configured
            if provider.api_key:
                key_value = f"{provider.api_key_prefix}{provider.api_key}"
                request["headers"][provider.api_key_header] = key_value

            # Apply middleware
            request = await self._apply_middleware(ctx, request)

            # Execute with circuit breaker and retry
            result = await self._execute_with_retry(ctx, provider, request)

            # Cache successful GET responses
            if method.upper() == "GET" and result.get("status") == 200:
                ttl = cache_ttl or provider.cache_ttl
                await self._cache.set(cache_key, result.get("data"), ttl)

            self._stats.successful_requests += 1
            return result

        except CircuitOpenError as e:
            self._stats.circuit_breaks += 1
            self._stats.failed_requests += 1
            raise

        except Exception as e:
            self._stats.failed_requests += 1
            error_type = type(e).__name__
            self._stats.errors_by_type[error_type] = (
                self._stats.errors_by_type.get(error_type, 0) + 1
            )
            raise

        finally:
            self._stats.total_latency_ms += ctx.elapsed_ms

    async def _execute_with_retry(
        self,
        ctx: RequestContext,
        provider: UpstreamProvider,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute request with retry and circuit breaker"""
        cb = self._circuit_breakers.get(provider.name)
        last_error = None

        for attempt in range(provider.retry_attempts):
            ctx.attempts = attempt + 1

            try:
                # Check circuit breaker
                if cb and not cb.can_execute():
                    raise CircuitOpenError(f"Circuit open for {provider.name}")

                # Track request start
                await self._load_balancer.on_request_start(provider.name)

                # Make request
                result = await self._make_request(request)

                # Track success
                latency = ctx.elapsed_ms
                await self._load_balancer.on_request_success(provider.name, latency)
                if cb:
                    await cb._on_success()

                # Track by provider
                self._stats.requests_by_provider[provider.name] = (
                    self._stats.requests_by_provider.get(provider.name, 0) + 1
                )

                return result

            except Exception as e:
                last_error = e

                # Track failure
                await self._load_balancer.on_request_failure(provider.name, e)
                if cb:
                    await cb._on_failure(e)

                # Log and maybe retry
                logger.warning(
                    f"Request to {provider.name} failed "
                    f"(attempt {attempt + 1}/{provider.retry_attempts}): {e}"
                )

                if attempt < provider.retry_attempts - 1:
                    # Exponential backoff
                    delay = provider.retry_delay_seconds * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise last_error or Exception("All retry attempts failed")

    async def _make_request(
        self,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the actual HTTP request"""
        if not self._session:
            raise RuntimeError("Gateway not started")

        method = request.pop("method")
        url = request.pop("url")

        async with self._session.request(method, url, **request) as response:
            try:
                data = await response.json()
            except Exception:
                data = await response.text()

            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=str(data)
                )

            return {
                "status": response.status,
                "data": data,
                "headers": dict(response.headers)
            }

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    async def get(
        self,
        path: str,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """GET request"""
        return await self.request("GET", path, provider_name, **kwargs)

    async def post(
        self,
        path: str,
        body: Any,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """POST request"""
        return await self.request("POST", path, provider_name, body=body, **kwargs)

    async def put(
        self,
        path: str,
        body: Any,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """PUT request"""
        return await self.request("PUT", path, provider_name, body=body, **kwargs)

    async def delete(
        self,
        path: str,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """DELETE request"""
        return await self.request("DELETE", path, provider_name, **kwargs)

    # =========================================================================
    # STATUS & METRICS
    # =========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all providers"""
        results = await self._load_balancer.health_check_all()
        return {
            "healthy_providers": sum(1 for v in results.values() if v),
            "total_providers": len(results),
            "providers": results
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics"""
        return {
            "total_requests": self._stats.total_requests,
            "successful_requests": self._stats.successful_requests,
            "failed_requests": self._stats.failed_requests,
            "success_rate": round(self._stats.success_rate * 100, 2),
            "avg_latency_ms": round(self._stats.avg_latency_ms, 2),
            "cache": {
                "hits": self._stats.cache_hits,
                "misses": self._stats.cache_misses,
                "hit_rate": round(
                    self._stats.cache_hits / max(1, self._stats.cache_hits + self._stats.cache_misses) * 100,
                    2
                )
            },
            "circuit_breaks": self._stats.circuit_breaks,
            "requests_by_provider": self._stats.requests_by_provider,
            "errors_by_type": self._stats.errors_by_type
        }

    def to_dict(self) -> Dict[str, Any]:
        """Get full gateway status"""
        return {
            "stats": self.get_stats(),
            "cache": self._cache.to_dict(),
            "load_balancer": self._load_balancer.to_dict(),
            "circuit_breakers": {
                name: cb.to_dict()
                for name, cb in self._circuit_breakers.items()
            },
            "providers": {
                name: {
                    "base_url": p.base_url,
                    "enabled": p.enabled,
                    "status": self.get_provider_status(name).value,
                    "weight": p.weight,
                    "priority": p.priority
                }
                for name, p in self._providers.items()
            }
        }


# Global gateway instance
_gateway: Optional[APIGateway] = None


def get_api_gateway() -> APIGateway:
    """Get or create global API gateway"""
    global _gateway
    if _gateway is None:
        _gateway = APIGateway()
    return _gateway


async def setup_default_providers(gateway: APIGateway, config: Dict[str, str]):
    """Setup default providers from config"""
    # Helius (Solana RPC)
    if config.get("helius_api_key"):
        gateway.register_provider(UpstreamProvider(
            name="helius",
            base_url="https://api.helius.xyz",
            api_key=config["helius_api_key"],
            api_key_header="Authorization",
            api_key_prefix="Bearer ",
            weight=100,
            priority=1,
            cache_ttl=60
        ))

    # BirdEye (Token data)
    if config.get("birdeye_api_key"):
        gateway.register_provider(UpstreamProvider(
            name="birdeye",
            base_url="https://public-api.birdeye.so",
            api_key=config["birdeye_api_key"],
            api_key_header="X-API-KEY",
            api_key_prefix="",
            weight=100,
            priority=1,
            cache_ttl=300
        ))

    # DexScreener
    gateway.register_provider(UpstreamProvider(
        name="dexscreener",
        base_url="https://api.dexscreener.com/latest",
        weight=80,
        priority=2,
        cache_ttl=60
    ))

    # GeckoTerminal
    gateway.register_provider(UpstreamProvider(
        name="geckoterminal",
        base_url="https://api.geckoterminal.com/api/v2",
        weight=70,
        priority=3,
        cache_ttl=120
    ))


# Testing
if __name__ == "__main__":
    async def test():
        gateway = APIGateway()
        await gateway.start()

        # Register test providers
        gateway.register_provider(UpstreamProvider(
            name="dexscreener",
            base_url="https://api.dexscreener.com/latest",
            cache_ttl=60
        ))

        # Test request
        try:
            result = await gateway.get(
                "/dex/tokens/So11111111111111111111111111111111111111112",
                provider_name="dexscreener"
            )
            print(f"Response status: {result.get('status')}")
            print(f"Data type: {type(result.get('data'))}")
        except Exception as e:
            print(f"Request failed: {e}")

        # Test cached request
        result2 = await gateway.get(
            "/dex/tokens/So11111111111111111111111111111111111111112",
            provider_name="dexscreener"
        )
        print(f"Cached: {result2.get('cached', False)}")

        # Print stats
        print(f"\nGateway stats: {json.dumps(gateway.get_stats(), indent=2)}")

        await gateway.stop()

    asyncio.run(test())
