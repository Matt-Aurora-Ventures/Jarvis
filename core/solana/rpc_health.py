"""
RPC Health Scoring System for Solana Endpoints.

Provides intelligent health monitoring, scoring, and automatic failover
for Solana RPC endpoints. Features:

- Health score calculation (0-100) based on latency, success rate, failures
- Latency percentile tracking (p50, p95, p99)
- Circuit breaker pattern for failing endpoints
- Automatic failover to healthy endpoints
- Periodic health checks (configurable interval)
- Metrics persistence support
- Thread-safe operations
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except ImportError:
    HAS_SOLANA = False
    AsyncClient = None

# Import existing config loader
try:
    from core.solana_execution import load_solana_rpc_endpoints, RpcEndpoint as ConfigRpcEndpoint
    HAS_CONFIG_LOADER = True
except ImportError:
    HAS_CONFIG_LOADER = False
    load_solana_rpc_endpoints = None
    ConfigRpcEndpoint = None

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

HEALTH_CHECK_INTERVAL = 30  # seconds between health checks
DEFAULT_WINDOW_SIZE = 1000  # rolling window for latency stats
CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures to open circuit
CIRCUIT_BREAKER_RECOVERY_SECONDS = 60  # seconds before attempting recovery

# Health score weights
WEIGHT_SUCCESS_RATE = 0.35
WEIGHT_LATENCY = 0.35
WEIGHT_CONSECUTIVE_FAILURES = 0.20
WEIGHT_RECENCY = 0.10

# Latency thresholds (ms)
LATENCY_EXCELLENT = 100
LATENCY_GOOD = 300
LATENCY_DEGRADED = 1000
LATENCY_POOR = 3000


# =============================================================================
# DATABASE PROTOCOL
# =============================================================================

class MetricsDatabase(Protocol):
    """Protocol for metrics persistence."""

    async def save_rpc_metrics(self, metrics: Dict[str, Any]) -> None:
        """Save RPC metrics to database."""
        ...

    async def load_rpc_metrics(self) -> Dict[str, Any]:
        """Load RPC metrics from database."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HealthCheckResult:
    """Result of a health check for an endpoint."""
    healthy: bool
    latency_ms: float
    block_height: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LatencyStats:
    """Tracks latency statistics with rolling window."""
    window_size: int = DEFAULT_WINDOW_SIZE
    _latencies: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, latency_ms: float) -> None:
        """Record a latency measurement."""
        with self._lock:
            self._latencies.append(latency_ms)
            # Maintain rolling window
            if len(self._latencies) > self.window_size:
                self._latencies = self._latencies[-self.window_size:]

    @property
    def count(self) -> int:
        """Number of recorded latencies."""
        with self._lock:
            return len(self._latencies)

    def _percentile(self, p: float) -> Optional[float]:
        """Calculate percentile from recorded latencies."""
        with self._lock:
            if not self._latencies:
                return None
            sorted_latencies = sorted(self._latencies)
            idx = int(len(sorted_latencies) * p / 100)
            idx = min(idx, len(sorted_latencies) - 1)
            return sorted_latencies[idx]

    @property
    def p50(self) -> Optional[float]:
        """Median latency (50th percentile)."""
        return self._percentile(50)

    @property
    def p95(self) -> Optional[float]:
        """95th percentile latency."""
        return self._percentile(95)

    @property
    def p99(self) -> Optional[float]:
        """99th percentile latency."""
        return self._percentile(99)

    @property
    def average(self) -> Optional[float]:
        """Average latency."""
        with self._lock:
            if not self._latencies:
                return None
            return sum(self._latencies) / len(self._latencies)


class HealthScore:
    """Calculates health score (0-100) for an endpoint."""

    @staticmethod
    def calculate(
        success_rate: float,
        latency_p50: Optional[float],
        latency_p95: Optional[float],
        latency_p99: Optional[float],
        consecutive_failures: int,
        last_failure_seconds_ago: Optional[float],
    ) -> float:
        """
        Calculate health score from multiple factors.

        Args:
            success_rate: Percentage of successful requests (0-100)
            latency_p50: Median latency in ms
            latency_p95: 95th percentile latency in ms
            latency_p99: 99th percentile latency in ms
            consecutive_failures: Number of consecutive failures
            last_failure_seconds_ago: Seconds since last failure (None if no failures)

        Returns:
            Health score from 0 to 100
        """
        # Success rate component (0-100)
        success_score = success_rate

        # Latency component (0-100)
        latency_score = HealthScore._latency_score(latency_p50, latency_p95, latency_p99)

        # Consecutive failures component (0-100)
        failure_score = HealthScore._failure_score(consecutive_failures)

        # Recency component (0-100) - penalize recent failures
        recency_score = HealthScore._recency_score(last_failure_seconds_ago)

        # Weighted average
        raw_score = (
            WEIGHT_SUCCESS_RATE * success_score +
            WEIGHT_LATENCY * latency_score +
            WEIGHT_CONSECUTIVE_FAILURES * failure_score +
            WEIGHT_RECENCY * recency_score
        )

        # Clamp to 0-100
        return max(0.0, min(100.0, raw_score))

    @staticmethod
    def _latency_score(p50: Optional[float], p95: Optional[float], p99: Optional[float]) -> float:
        """Score latency (higher is better, lower latency = higher score)."""
        if p50 is None:
            return 50.0  # Neutral score if no data

        # Weight p50 more heavily than p95/p99
        p95 = p95 or p50
        p99 = p99 or p95

        avg_latency = p50 * 0.5 + p95 * 0.3 + p99 * 0.2

        if avg_latency <= LATENCY_EXCELLENT:
            return 100.0
        elif avg_latency <= LATENCY_GOOD:
            return 80.0 + 20.0 * (LATENCY_GOOD - avg_latency) / (LATENCY_GOOD - LATENCY_EXCELLENT)
        elif avg_latency <= LATENCY_DEGRADED:
            return 50.0 + 30.0 * (LATENCY_DEGRADED - avg_latency) / (LATENCY_DEGRADED - LATENCY_GOOD)
        elif avg_latency <= LATENCY_POOR:
            return 20.0 + 30.0 * (LATENCY_POOR - avg_latency) / (LATENCY_POOR - LATENCY_DEGRADED)
        else:
            # Very poor latency
            return max(0.0, 20.0 - (avg_latency - LATENCY_POOR) / 100)

    @staticmethod
    def _failure_score(consecutive_failures: int) -> float:
        """Score based on consecutive failures (higher is better)."""
        if consecutive_failures == 0:
            return 100.0
        elif consecutive_failures == 1:
            return 80.0
        elif consecutive_failures == 2:
            return 60.0
        elif consecutive_failures < 5:
            return 40.0
        else:
            return max(0.0, 20.0 - consecutive_failures * 2)

    @staticmethod
    def _recency_score(last_failure_seconds_ago: Optional[float]) -> float:
        """Score based on recency of last failure (higher is better)."""
        if last_failure_seconds_ago is None:
            return 100.0  # No failures = perfect score

        if last_failure_seconds_ago < 10:
            return 20.0
        elif last_failure_seconds_ago < 30:
            return 40.0
        elif last_failure_seconds_ago < 60:
            return 60.0
        elif last_failure_seconds_ago < 300:
            return 80.0
        else:
            return 100.0


@dataclass
class EndpointHealth:
    """Tracks health state for a single RPC endpoint."""
    name: str
    url: str
    priority: int = 1

    # Counters
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0

    # Timestamps
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    # Circuit breaker
    _circuit_open_until: Optional[datetime] = None

    # Latency tracking
    latency_stats: LatencyStats = field(default_factory=LatencyStats)

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Cached score
    _cached_score: float = 50.0

    def record_success(self, latency_ms: float) -> None:
        """Record a successful request."""
        with self._lock:
            self.success_count += 1
            self.consecutive_failures = 0
            self.last_success = datetime.utcnow()
            self._circuit_open_until = None
        self.latency_stats.record(latency_ms)

    def record_failure(self, error: str) -> None:
        """Record a failed request."""
        with self._lock:
            self.failure_count += 1
            self.consecutive_failures += 1
            self.last_failure = datetime.utcnow()

            # Check circuit breaker threshold
            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                self._circuit_open_until = datetime.utcnow() + timedelta(
                    seconds=CIRCUIT_BREAKER_RECOVERY_SECONDS
                )
                logger.warning(f"Circuit opened for {self.name} after {self.consecutive_failures} failures")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        # Note: Caller should hold lock or this is a snapshot read
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0  # No data = assume healthy
        return (self.success_count / total) * 100.0

    @property
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        # Note: Caller should hold lock or this is a snapshot read
        if self._circuit_open_until is None:
            return False
        return datetime.utcnow() < self._circuit_open_until

    @property
    def is_circuit_half_open(self) -> bool:
        """Check if circuit breaker is in half-open state (recovery attempt)."""
        # Note: Caller should hold lock or this is a snapshot read
        if self._circuit_open_until is None:
            return False
        return datetime.utcnow() >= self._circuit_open_until

    def calculate_score(self) -> float:
        """Calculate current health score."""
        with self._lock:
            last_failure_seconds = None
            if self.last_failure:
                last_failure_seconds = (datetime.utcnow() - self.last_failure).total_seconds()

            # Access internal state directly to avoid lock recursion
            total = self.success_count + self.failure_count
            rate = 100.0 if total == 0 else (self.success_count / total) * 100.0

            self._cached_score = HealthScore.calculate(
                success_rate=rate,
                latency_p50=self.latency_stats.p50,
                latency_p95=self.latency_stats.p95,
                latency_p99=self.latency_stats.p99,
                consecutive_failures=self.consecutive_failures,
                last_failure_seconds_ago=last_failure_seconds,
            )
            return self._cached_score

    @property
    def score(self) -> float:
        """Get cached health score."""
        return self._cached_score

    def to_dict(self) -> Dict[str, Any]:
        """Export endpoint health as dictionary."""
        return {
            "name": self.name,
            "url": self.url,
            "priority": self.priority,
            "score": self._cached_score,
            "success_rate": self.success_rate,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "latency_p50": self.latency_stats.p50,
            "latency_p95": self.latency_stats.p95,
            "latency_p99": self.latency_stats.p99,
            "is_circuit_open": self.is_circuit_open,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
        }


# =============================================================================
# MAIN HEALTH SCORER
# =============================================================================

class RPCHealthScorer:
    """
    Manages health scoring and failover for RPC endpoints.

    Example usage:
        >>> endpoints = [{"name": "primary", "url": "https://...", "priority": 1}]
        >>> scorer = RPCHealthScorer(endpoints=endpoints)
        >>> await scorer.start()  # Start background health checks
        >>> best = scorer.get_best_endpoint()  # Get healthiest endpoint
        >>> await scorer.stop()  # Stop health checks
    """

    def __init__(
        self,
        endpoints: List[Dict[str, Any]],
        health_check_interval: int = HEALTH_CHECK_INTERVAL,
        database: Optional[MetricsDatabase] = None,
    ):
        """
        Initialize the health scorer.

        Args:
            endpoints: List of endpoint configurations with name, url, priority
            health_check_interval: Seconds between health checks
            database: Optional database for metrics persistence

        Raises:
            ValueError: If endpoints list is empty or invalid
        """
        if not endpoints:
            raise ValueError("At least one endpoint required")

        self.endpoints: List[EndpointHealth] = []
        for ep in endpoints:
            if "url" not in ep:
                raise ValueError(f"Endpoint missing required 'url' field: {ep}")
            self.endpoints.append(EndpointHealth(
                name=ep.get("name", "unnamed"),
                url=ep["url"],
                priority=ep.get("priority", 1),
            ))

        self.health_check_interval = health_check_interval
        self._database = database
        self._running = False
        self._health_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, database: Optional[MetricsDatabase] = None) -> "RPCHealthScorer":
        """
        Create a health scorer from the existing RPC config file.

        Returns:
            RPCHealthScorer instance configured from rpc_providers.json
        """
        if not HAS_CONFIG_LOADER or load_solana_rpc_endpoints is None:
            raise RuntimeError("Config loader not available")

        config_endpoints = load_solana_rpc_endpoints()
        endpoints = []
        for i, ep in enumerate(config_endpoints):
            endpoints.append({
                "name": ep.name,
                "url": ep.url,
                "priority": i + 1,
            })

        return cls(endpoints=endpoints, database=database)

    @property
    def is_running(self) -> bool:
        """Check if health check loop is running."""
        return self._running

    def set_database(self, database: MetricsDatabase) -> None:
        """Set the database for metrics persistence."""
        self._database = database

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the background health check loop."""
        if self._running:
            return

        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"RPCHealthScorer started with {len(self.endpoints)} endpoints")

    async def stop(self) -> None:
        """Stop the background health check loop."""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        logger.info("RPCHealthScorer stopped")

    async def _health_check_loop(self) -> None:
        """Background loop that performs periodic health checks."""
        while self._running:
            try:
                await self._run_health_checks()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

            await asyncio.sleep(self.health_check_interval)

    async def _run_health_checks(self) -> None:
        """Run health checks for all endpoints in parallel."""
        tasks = [self._check_endpoint_health(ep) for ep in self.endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for ep, result in zip(self.endpoints, results):
            if isinstance(result, Exception):
                logger.warning(f"Health check exception for {ep.name}: {result}")
                ep.record_failure(str(result))
            elif result.healthy:
                ep.record_success(result.latency_ms)
            else:
                ep.record_failure(result.error or "unhealthy")

        # Update all scores
        self.update_scores()

        # Persist metrics if database configured
        if self._database:
            try:
                await self.persist_metrics()
            except Exception as e:
                logger.warning(f"Failed to persist metrics: {e}")

    async def _check_endpoint_health(self, endpoint: EndpointHealth) -> HealthCheckResult:
        """
        Check health of a single endpoint by calling getHealth RPC method.

        Args:
            endpoint: The endpoint to check

        Returns:
            HealthCheckResult with status and latency
        """
        if not HAS_AIOHTTP:
            return HealthCheckResult(
                healthy=False,
                latency_ms=0,
                error="aiohttp not available",
            )

        payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
        timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout for health checks

        start = time.perf_counter()
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint.url, json=payload) as resp:
                    latency_ms = (time.perf_counter() - start) * 1000

                    if resp.status != 200:
                        return HealthCheckResult(
                            healthy=False,
                            latency_ms=latency_ms,
                            error=f"HTTP {resp.status}",
                        )

                    data = await resp.json()

                    if data.get("result") == "ok":
                        return HealthCheckResult(
                            healthy=True,
                            latency_ms=latency_ms,
                        )
                    else:
                        return HealthCheckResult(
                            healthy=False,
                            latency_ms=latency_ms,
                            error=str(data.get("error", "unhealthy")),
                        )

        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                error="timeout",
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return HealthCheckResult(
                healthy=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    # =========================================================================
    # SCORING & SELECTION
    # =========================================================================

    def update_scores(self) -> None:
        """Recalculate health scores for all endpoints."""
        for endpoint in self.endpoints:
            endpoint.calculate_score()

    def get_best_endpoint(self, exclude: Optional[List[str]] = None) -> EndpointHealth:
        """
        Get the healthiest endpoint, optionally excluding some.

        Args:
            exclude: List of endpoint names to exclude

        Returns:
            The healthiest available endpoint
        """
        exclude = exclude or []
        candidates = [
            ep for ep in self.endpoints
            if ep.name not in exclude and not ep.is_circuit_open
        ]

        if not candidates:
            # If all excluded or circuit-open, fall back to all endpoints
            candidates = [ep for ep in self.endpoints if ep.name not in exclude]

        if not candidates:
            # Absolute fallback - return first endpoint
            return self.endpoints[0]

        # Sort by score (desc) then priority (asc)
        candidates.sort(key=lambda ep: (-ep.score, ep.priority))
        return candidates[0]

    def get_all_scores(self) -> List[Dict[str, Any]]:
        """
        Get health scores for all endpoints.

        Returns:
            List of dicts with name, url, score, and other metrics
        """
        return [
            {
                "name": ep.name,
                "url": ep.url,
                "score": ep.score,
                "success_rate": ep.success_rate,
                "latency_p50": ep.latency_stats.p50,
                "latency_p95": ep.latency_stats.p95,
                "latency_p99": ep.latency_stats.p99,
                "consecutive_failures": ep.consecutive_failures,
                "is_circuit_open": ep.is_circuit_open,
            }
            for ep in self.endpoints
        ]

    # =========================================================================
    # METRICS & PERSISTENCE
    # =========================================================================

    def export_metrics(self) -> Dict[str, Any]:
        """
        Export all metrics in a standard format.

        Returns:
            Dict with timestamp and all endpoint metrics
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoints": [ep.to_dict() for ep in self.endpoints],
        }

    async def persist_metrics(self) -> None:
        """Persist current metrics to database."""
        if self._database is None:
            return

        metrics = self.export_metrics()
        await self._database.save_rpc_metrics(metrics)

    async def load_metrics(self) -> None:
        """Load metrics from database and restore state."""
        if self._database is None:
            return

        try:
            stored = await self._database.load_rpc_metrics()
            if not stored:
                return

            # Restore metrics for matching endpoints
            for ep in self.endpoints:
                if ep.name in stored:
                    ep_data = stored[ep.name]
                    ep.success_count = ep_data.get("success_count", 0)
                    ep.failure_count = ep_data.get("failure_count", 0)

            logger.info(f"Loaded metrics for {len(stored)} endpoints")

        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")

    # =========================================================================
    # CLIENT FACTORY
    # =========================================================================

    def get_client_factory(self) -> Callable[[], Any]:
        """
        Get a factory function that creates AsyncClient for the best endpoint.

        Returns:
            Callable that creates AsyncClient instances

        Example:
            >>> factory = scorer.get_client_factory()
            >>> async with factory() as client:
            ...     resp = await client.get_balance(pubkey)
        """
        if not HAS_SOLANA or AsyncClient is None:
            raise RuntimeError("solana-py not available")

        def factory():
            best = self.get_best_endpoint()
            return AsyncClient(best.url)

        return factory


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "RPCHealthScorer",
    "EndpointHealth",
    "HealthScore",
    "LatencyStats",
    "HealthCheckResult",
    "HEALTH_CHECK_INTERVAL",
]
