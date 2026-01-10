"""
Load Balancer for Multiple Upstream Providers

Distributes requests across providers with health checks and failover.

Prompts #45: API Proxy System - Load Balancing
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class LoadBalancerStrategy(str, Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    LATENCY_BASED = "latency_based"
    FAILOVER = "failover"  # Primary with backup


@dataclass
class ProviderHealth:
    """Health status of a provider"""
    name: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_latency_ms: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    active_connections: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.failed_requests) / self.total_requests

    @property
    def health_score(self) -> float:
        """Calculate health score (0-100)"""
        if not self.is_healthy:
            return 0

        score = 100.0

        # Penalize for failures
        score -= min(50, self.consecutive_failures * 10)

        # Penalize for high latency
        if self.avg_latency_ms > 1000:
            score -= 20
        elif self.avg_latency_ms > 500:
            score -= 10

        # Penalize for low success rate
        score -= (1 - self.success_rate) * 30

        return max(0, score)


@dataclass
class ProviderConfig:
    """Configuration for an upstream provider"""
    name: str
    base_url: str
    weight: int = 100                   # Relative weight for weighted strategy
    priority: int = 0                   # Priority for failover (lower = higher)
    max_connections: int = 100          # Max concurrent connections
    health_check_url: Optional[str] = None
    health_check_interval: int = 30     # Seconds between health checks
    failure_threshold: int = 3          # Failures before marking unhealthy
    recovery_threshold: int = 2         # Successes to mark healthy again
    timeout_seconds: float = 30.0       # Request timeout
    metadata: Dict[str, Any] = field(default_factory=dict)


class LoadBalancer:
    """
    Load balancer for distributing requests across providers.

    Supports multiple strategies and automatic health-based failover.
    """

    def __init__(
        self,
        strategy: LoadBalancerStrategy = LoadBalancerStrategy.ROUND_ROBIN
    ):
        self.strategy = strategy
        self._providers: Dict[str, ProviderConfig] = {}
        self._health: Dict[str, ProviderHealth] = {}
        self._round_robin_index = 0
        self._lock = asyncio.Lock()

    def add_provider(self, config: ProviderConfig):
        """Add a provider to the pool"""
        self._providers[config.name] = config
        self._health[config.name] = ProviderHealth(name=config.name)
        logger.info(f"Added provider: {config.name}")

    def remove_provider(self, name: str):
        """Remove a provider from the pool"""
        self._providers.pop(name, None)
        self._health.pop(name, None)
        logger.info(f"Removed provider: {name}")

    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy provider names"""
        return [
            name for name, health in self._health.items()
            if health.is_healthy
        ]

    async def select_provider(self) -> Optional[str]:
        """Select a provider based on strategy"""
        healthy = self.get_healthy_providers()

        if not healthy:
            logger.warning("No healthy providers available")
            return None

        async with self._lock:
            if self.strategy == LoadBalancerStrategy.ROUND_ROBIN:
                return self._select_round_robin(healthy)

            elif self.strategy == LoadBalancerStrategy.WEIGHTED:
                return self._select_weighted(healthy)

            elif self.strategy == LoadBalancerStrategy.LEAST_CONNECTIONS:
                return self._select_least_connections(healthy)

            elif self.strategy == LoadBalancerStrategy.RANDOM:
                return random.choice(healthy)

            elif self.strategy == LoadBalancerStrategy.LATENCY_BASED:
                return self._select_latency_based(healthy)

            elif self.strategy == LoadBalancerStrategy.FAILOVER:
                return self._select_failover(healthy)

        return healthy[0] if healthy else None

    def _select_round_robin(self, healthy: List[str]) -> str:
        """Round robin selection"""
        self._round_robin_index = (self._round_robin_index + 1) % len(healthy)
        return healthy[self._round_robin_index]

    def _select_weighted(self, healthy: List[str]) -> str:
        """Weighted random selection"""
        weights = [
            self._providers[name].weight
            for name in healthy
        ]
        return random.choices(healthy, weights=weights)[0]

    def _select_least_connections(self, healthy: List[str]) -> str:
        """Select provider with least active connections"""
        return min(
            healthy,
            key=lambda name: self._health[name].active_connections
        )

    def _select_latency_based(self, healthy: List[str]) -> str:
        """Select provider with lowest latency"""
        return min(
            healthy,
            key=lambda name: self._health[name].avg_latency_ms
        )

    def _select_failover(self, healthy: List[str]) -> str:
        """Select highest priority (lowest number) healthy provider"""
        return min(
            healthy,
            key=lambda name: self._providers[name].priority
        )

    async def on_request_start(self, provider_name: str):
        """Called when a request starts"""
        if provider_name in self._health:
            self._health[provider_name].active_connections += 1
            self._health[provider_name].total_requests += 1

    async def on_request_success(
        self,
        provider_name: str,
        latency_ms: float
    ):
        """Called when a request succeeds"""
        if provider_name not in self._health:
            return

        health = self._health[provider_name]
        health.active_connections = max(0, health.active_connections - 1)
        health.consecutive_successes += 1
        health.consecutive_failures = 0

        # Update average latency (exponential moving average)
        alpha = 0.2
        health.avg_latency_ms = (
            alpha * latency_ms + (1 - alpha) * health.avg_latency_ms
        )

        # Check if should mark healthy
        config = self._providers[provider_name]
        if not health.is_healthy:
            if health.consecutive_successes >= config.recovery_threshold:
                health.is_healthy = True
                logger.info(f"Provider {provider_name} recovered")

        health.last_check = datetime.utcnow()

    async def on_request_failure(
        self,
        provider_name: str,
        error: Optional[Exception] = None
    ):
        """Called when a request fails"""
        if provider_name not in self._health:
            return

        health = self._health[provider_name]
        health.active_connections = max(0, health.active_connections - 1)
        health.consecutive_failures += 1
        health.consecutive_successes = 0
        health.failed_requests += 1
        health.last_failure = datetime.utcnow()
        health.last_check = datetime.utcnow()

        # Check if should mark unhealthy
        config = self._providers[provider_name]
        if health.is_healthy:
            if health.consecutive_failures >= config.failure_threshold:
                health.is_healthy = False
                logger.warning(
                    f"Provider {provider_name} marked unhealthy: {error}"
                )

    async def execute_with_failover(
        self,
        func: Callable,
        max_retries: int = 3
    ) -> Any:
        """Execute a function with automatic failover"""
        last_error = None

        for attempt in range(max_retries):
            provider = await self.select_provider()

            if not provider:
                raise NoHealthyProviderError("No healthy providers available")

            config = self._providers[provider]
            await self.on_request_start(provider)
            start_time = time.time()

            try:
                result = await func(config)
                latency_ms = (time.time() - start_time) * 1000
                await self.on_request_success(provider, latency_ms)
                return result

            except Exception as e:
                await self.on_request_failure(provider, e)
                last_error = e
                logger.warning(
                    f"Request to {provider} failed (attempt {attempt + 1}): {e}"
                )

        raise last_error or Exception("All retries failed")

    async def health_check(self, provider_name: str) -> bool:
        """Perform health check on a provider"""
        if provider_name not in self._providers:
            return False

        config = self._providers[provider_name]

        if not config.health_check_url:
            return True  # No health check configured

        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    config.health_check_url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    is_healthy = response.status == 200

            health = self._health[provider_name]
            health.last_check = datetime.utcnow()

            if is_healthy:
                await self.on_request_success(provider_name, 0)
            else:
                await self.on_request_failure(provider_name)

            return is_healthy

        except Exception as e:
            await self.on_request_failure(provider_name, e)
            return False

    async def health_check_all(self) -> Dict[str, bool]:
        """Health check all providers"""
        results = {}
        for name in self._providers:
            results[name] = await self.health_check(name)
        return results

    def get_provider_config(self, name: str) -> Optional[ProviderConfig]:
        """Get provider configuration"""
        return self._providers.get(name)

    def get_provider_health(self, name: str) -> Optional[ProviderHealth]:
        """Get provider health status"""
        return self._health.get(name)

    def to_dict(self) -> Dict[str, Any]:
        """Get load balancer status"""
        return {
            "strategy": self.strategy.value,
            "providers": {
                name: {
                    "config": {
                        "base_url": config.base_url,
                        "weight": config.weight,
                        "priority": config.priority,
                        "max_connections": config.max_connections
                    },
                    "health": {
                        "is_healthy": self._health[name].is_healthy,
                        "health_score": self._health[name].health_score,
                        "success_rate": round(
                            self._health[name].success_rate * 100, 2
                        ),
                        "avg_latency_ms": round(
                            self._health[name].avg_latency_ms, 2
                        ),
                        "active_connections": self._health[name].active_connections,
                        "total_requests": self._health[name].total_requests,
                        "failed_requests": self._health[name].failed_requests
                    }
                }
                for name, config in self._providers.items()
            }
        }


class NoHealthyProviderError(Exception):
    """Raised when no healthy providers are available"""
    pass


# Background health check task
async def health_check_task(
    load_balancer: LoadBalancer,
    interval: int = 30
):
    """Background task for periodic health checks"""
    while True:
        try:
            await asyncio.sleep(interval)
            results = await load_balancer.health_check_all()
            healthy_count = sum(1 for v in results.values() if v)
            logger.debug(
                f"Health check: {healthy_count}/{len(results)} providers healthy"
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Health check error: {e}")


# Testing
if __name__ == "__main__":
    async def test():
        lb = LoadBalancer(LoadBalancerStrategy.ROUND_ROBIN)

        # Add providers
        lb.add_provider(ProviderConfig(
            name="helius",
            base_url="https://api.helius.xyz",
            weight=100,
            priority=1
        ))
        lb.add_provider(ProviderConfig(
            name="triton",
            base_url="https://triton.one",
            weight=80,
            priority=2
        ))
        lb.add_provider(ProviderConfig(
            name="alchemy",
            base_url="https://solana-mainnet.g.alchemy.com",
            weight=60,
            priority=3
        ))

        # Test selection
        print("Testing round robin selection:")
        for i in range(6):
            provider = await lb.select_provider()
            print(f"  Request {i+1}: {provider}")

        # Test failover
        print("\nSimulating failures...")
        for _ in range(4):
            await lb.on_request_failure("helius", Exception("Test failure"))

        print(f"Helius healthy: {lb.get_provider_health('helius').is_healthy}")

        print("\nSelection after failures:")
        for i in range(3):
            provider = await lb.select_provider()
            print(f"  Request {i+1}: {provider}")

        # Test recovery
        print("\nSimulating recovery...")
        for _ in range(3):
            await lb.on_request_success("helius", 100)

        print(f"Helius healthy: {lb.get_provider_health('helius').is_healthy}")

        # Print status
        print(f"\nLoad balancer status: {json.dumps(lb.to_dict(), indent=2)}")

    import json
    asyncio.run(test())
