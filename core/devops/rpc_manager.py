"""
RPC Management System
Prompts #57-58: RPC load balancing, failover, and health monitoring
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import random
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Health check interval
HEALTH_CHECK_INTERVAL = 30  # seconds

# Timeout settings
DEFAULT_TIMEOUT = 10  # seconds
SLOW_THRESHOLD_MS = 500  # Considered slow if > 500ms

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5

# Circuit breaker settings
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 60  # seconds


# =============================================================================
# MODELS
# =============================================================================

class RPCProvider(str, Enum):
    HELIUS = "helius"
    QUICKNODE = "quicknode"
    ALCHEMY = "alchemy"
    TRITON = "triton"
    GETBLOCK = "getblock"
    PUBLIC = "public"


class EndpointStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class LoadBalanceStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    WEIGHTED = "weighted"
    RANDOM = "random"


@dataclass
class RPCEndpoint:
    """An RPC endpoint configuration"""
    url: str
    provider: RPCProvider
    api_key: Optional[str] = None
    weight: int = 1
    priority: int = 1  # Lower = higher priority
    max_requests_per_second: int = 100
    is_websocket: bool = False

    # Runtime state
    status: EndpointStatus = EndpointStatus.HEALTHY
    latency_ms: float = 0
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    circuit_open_until: Optional[datetime] = None

    # Rate limiting
    requests_this_second: int = 0
    current_second: int = 0


@dataclass
class RPCRequest:
    """An RPC request"""
    method: str
    params: List[Any] = field(default_factory=list)
    id: int = 1
    jsonrpc: str = "2.0"


@dataclass
class RPCResponse:
    """An RPC response"""
    result: Any
    latency_ms: float
    endpoint: str
    success: bool
    error: Optional[str] = None


@dataclass
class HealthMetrics:
    """Health metrics for an endpoint"""
    endpoint: str
    status: EndpointStatus
    latency_ms: float
    success_rate: float
    requests_per_minute: int
    last_check: datetime
    block_height: Optional[int] = None
    behind_by_blocks: int = 0


# =============================================================================
# RPC MANAGER
# =============================================================================

class RPCManager:
    """Manages RPC endpoints with load balancing, failover, and health monitoring"""

    def __init__(
        self,
        endpoints: List[RPCEndpoint],
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_LATENCY
    ):
        self.endpoints = endpoints
        self.strategy = strategy
        self.current_index = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self._health_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.request_latencies: List[float] = []

    async def start(self):
        """Start the RPC manager"""
        # Configure timeouts: 60s total, 30s connect (safety net - per-request timeouts take precedence)
        timeout = ClientTimeout(total=60, connect=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"RPC Manager started with {len(self.endpoints)} endpoints")

    async def stop(self):
        """Stop the RPC manager"""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
        if self.session:
            await self.session.close()
        logger.info("RPC Manager stopped")

    # =========================================================================
    # REQUEST HANDLING
    # =========================================================================

    async def call(
        self,
        method: str,
        params: List[Any] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> RPCResponse:
        """Make an RPC call with automatic failover"""
        params = params or []
        request = RPCRequest(method=method, params=params)

        last_error = None
        tried_endpoints = set()

        for attempt in range(MAX_RETRIES):
            endpoint = self._select_endpoint(tried_endpoints)
            if not endpoint:
                break

            tried_endpoints.add(endpoint.url)

            try:
                response = await self._make_request(endpoint, request, timeout)
                if response.success:
                    return response
                last_error = response.error
            except Exception as e:
                last_error = str(e)
                await self._record_failure(endpoint, str(e))

            # Backoff before retry
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BACKOFF_BASE ** attempt)

        self.total_failures += 1
        return RPCResponse(
            result=None,
            latency_ms=0,
            endpoint="none",
            success=False,
            error=f"All endpoints failed: {last_error}"
        )

    async def call_batch(
        self,
        requests: List[Tuple[str, List[Any]]],
        timeout: int = DEFAULT_TIMEOUT
    ) -> List[RPCResponse]:
        """Make multiple RPC calls in batch"""
        endpoint = self._select_endpoint()
        if not endpoint:
            return [RPCResponse(
                result=None,
                latency_ms=0,
                endpoint="none",
                success=False,
                error="No healthy endpoints"
            ) for _ in requests]

        batch = [
            {"jsonrpc": "2.0", "id": i, "method": method, "params": params}
            for i, (method, params) in enumerate(requests)
        ]

        start = time.time()
        try:
            async with self.session.post(
                endpoint.url,
                json=batch,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                latency_ms = (time.time() - start) * 1000
                data = await resp.json()

                await self._record_success(endpoint, latency_ms)

                results = []
                for item in data:
                    if "error" in item:
                        results.append(RPCResponse(
                            result=None,
                            latency_ms=latency_ms,
                            endpoint=endpoint.url,
                            success=False,
                            error=item["error"].get("message", "Unknown error")
                        ))
                    else:
                        results.append(RPCResponse(
                            result=item.get("result"),
                            latency_ms=latency_ms,
                            endpoint=endpoint.url,
                            success=True
                        ))
                return results

        except Exception as e:
            await self._record_failure(endpoint, str(e))
            return [RPCResponse(
                result=None,
                latency_ms=0,
                endpoint=endpoint.url,
                success=False,
                error=str(e)
            ) for _ in requests]

    async def _make_request(
        self,
        endpoint: RPCEndpoint,
        request: RPCRequest,
        timeout: int
    ) -> RPCResponse:
        """Make a single RPC request"""
        self.total_requests += 1

        # Check rate limit
        current_second = int(time.time())
        if endpoint.current_second != current_second:
            endpoint.current_second = current_second
            endpoint.requests_this_second = 0

        if endpoint.requests_this_second >= endpoint.max_requests_per_second:
            return RPCResponse(
                result=None,
                latency_ms=0,
                endpoint=endpoint.url,
                success=False,
                error="Rate limited"
            )

        endpoint.requests_this_second += 1

        payload = {
            "jsonrpc": request.jsonrpc,
            "id": request.id,
            "method": request.method,
            "params": request.params
        }

        start = time.time()
        async with self.session.post(
            endpoint.url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            latency_ms = (time.time() - start) * 1000
            data = await resp.json()

            if "error" in data:
                await self._record_failure(endpoint, data["error"].get("message"))
                return RPCResponse(
                    result=None,
                    latency_ms=latency_ms,
                    endpoint=endpoint.url,
                    success=False,
                    error=data["error"].get("message", "Unknown error")
                )

            await self._record_success(endpoint, latency_ms)
            return RPCResponse(
                result=data.get("result"),
                latency_ms=latency_ms,
                endpoint=endpoint.url,
                success=True
            )

    # =========================================================================
    # ENDPOINT SELECTION
    # =========================================================================

    def _select_endpoint(
        self,
        exclude: set = None
    ) -> Optional[RPCEndpoint]:
        """Select an endpoint based on strategy"""
        exclude = exclude or set()
        healthy = [
            e for e in self.endpoints
            if e.status in [EndpointStatus.HEALTHY, EndpointStatus.DEGRADED]
            and e.url not in exclude
            and (not e.circuit_open_until or datetime.utcnow() > e.circuit_open_until)
        ]

        if not healthy:
            return None

        if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin_select(healthy)
        elif self.strategy == LoadBalanceStrategy.LEAST_LATENCY:
            return self._least_latency_select(healthy)
        elif self.strategy == LoadBalanceStrategy.WEIGHTED:
            return self._weighted_select(healthy)
        else:  # RANDOM
            return random.choice(healthy)

    def _round_robin_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Round-robin selection"""
        endpoint = endpoints[self.current_index % len(endpoints)]
        self.current_index += 1
        return endpoint

    def _least_latency_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Select endpoint with lowest latency"""
        # Prefer endpoints with known latency
        with_latency = [e for e in endpoints if e.latency_ms > 0]
        if with_latency:
            return min(with_latency, key=lambda e: e.latency_ms)
        return endpoints[0]

    def _weighted_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Weighted random selection"""
        total_weight = sum(e.weight for e in endpoints)
        r = random.uniform(0, total_weight)
        current = 0
        for endpoint in endpoints:
            current += endpoint.weight
            if current >= r:
                return endpoint
        return endpoints[-1]

    # =========================================================================
    # HEALTH & METRICS
    # =========================================================================

    async def _health_check_loop(self):
        """Background health check loop"""
        while self._running:
            try:
                await self._check_all_endpoints()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def _check_all_endpoints(self):
        """Check health of all endpoints"""
        tasks = [self._check_endpoint(e) for e in self.endpoints]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_endpoint(self, endpoint: RPCEndpoint):
        """Check health of a single endpoint"""
        try:
            response = await self._make_request(
                endpoint,
                RPCRequest(method="getHealth"),
                timeout=5
            )

            if response.success:
                if response.latency_ms > SLOW_THRESHOLD_MS:
                    endpoint.status = EndpointStatus.DEGRADED
                else:
                    endpoint.status = EndpointStatus.HEALTHY
            else:
                endpoint.status = EndpointStatus.UNHEALTHY

        except Exception as e:
            endpoint.status = EndpointStatus.UNHEALTHY
            logger.warning(f"Health check failed for {endpoint.provider}: {e}")

    async def _record_success(self, endpoint: RPCEndpoint, latency_ms: float):
        """Record a successful request"""
        endpoint.success_count += 1
        endpoint.last_success = datetime.utcnow()
        endpoint.consecutive_failures = 0
        endpoint.latency_ms = (endpoint.latency_ms * 0.8) + (latency_ms * 0.2)  # EMA
        self.request_latencies.append(latency_ms)

        # Limit stored latencies
        if len(self.request_latencies) > 1000:
            self.request_latencies = self.request_latencies[-1000:]

    async def _record_failure(self, endpoint: RPCEndpoint, error: str):
        """Record a failed request"""
        endpoint.failure_count += 1
        endpoint.last_failure = datetime.utcnow()
        endpoint.consecutive_failures += 1

        # Check circuit breaker
        if endpoint.consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
            endpoint.status = EndpointStatus.CIRCUIT_OPEN
            endpoint.circuit_open_until = datetime.utcnow() + timedelta(
                seconds=CIRCUIT_RECOVERY_TIMEOUT
            )
            logger.warning(f"Circuit opened for {endpoint.provider}: {error}")

    def get_health_metrics(self) -> List[HealthMetrics]:
        """Get health metrics for all endpoints"""
        return [
            HealthMetrics(
                endpoint=e.url,
                status=e.status,
                latency_ms=e.latency_ms,
                success_rate=(
                    e.success_count / (e.success_count + e.failure_count) * 100
                    if (e.success_count + e.failure_count) > 0 else 100
                ),
                requests_per_minute=e.success_count + e.failure_count,
                last_check=e.last_success or datetime.utcnow()
            )
            for e in self.endpoints
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get overall RPC stats"""
        avg_latency = (
            sum(self.request_latencies) / len(self.request_latencies)
            if self.request_latencies else 0
        )

        return {
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "success_rate": (
                (self.total_requests - self.total_failures) / self.total_requests * 100
                if self.total_requests > 0 else 100
            ),
            "average_latency_ms": avg_latency,
            "p99_latency_ms": (
                sorted(self.request_latencies)[int(len(self.request_latencies) * 0.99)]
                if len(self.request_latencies) >= 100 else avg_latency
            ),
            "healthy_endpoints": len([
                e for e in self.endpoints if e.status == EndpointStatus.HEALTHY
            ]),
            "total_endpoints": len(self.endpoints)
        }


# =============================================================================
# BACKUP SYSTEM
# =============================================================================

@dataclass
class BackupConfig:
    """Backup configuration"""
    backup_dir: str
    retention_days: int = 30
    max_backups: int = 100
    compress: bool = True
    encrypt: bool = True
    encryption_key: Optional[str] = None


class BackupManager:
    """Manages data backups and recovery"""

    def __init__(self, config: BackupConfig):
        self.config = config
        self.backups: List[Dict[str, Any]] = []

    async def create_backup(
        self,
        data_type: str,
        data: Any,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a backup"""
        import json
        import gzip
        import hashlib

        backup_id = f"{data_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Serialize data
        serialized = json.dumps(data, default=str).encode()

        # Compress if enabled
        if self.config.compress:
            serialized = gzip.compress(serialized)

        # Calculate checksum
        checksum = hashlib.sha256(serialized).hexdigest()

        backup_info = {
            "id": backup_id,
            "data_type": data_type,
            "created_at": datetime.utcnow().isoformat(),
            "size_bytes": len(serialized),
            "compressed": self.config.compress,
            "encrypted": self.config.encrypt,
            "checksum": checksum,
            "metadata": metadata or {}
        }

        # In production, write to storage
        self.backups.append(backup_info)

        logger.info(f"Created backup: {backup_id} ({len(serialized)} bytes)")
        return backup_info

    async def restore_backup(self, backup_id: str) -> Any:
        """Restore from a backup"""
        backup = next((b for b in self.backups if b["id"] == backup_id), None)
        if not backup:
            raise ValueError(f"Backup not found: {backup_id}")

        # In production, read from storage and decompress/decrypt
        logger.info(f"Restored backup: {backup_id}")
        return {"restored": True, "backup_id": backup_id}

    async def list_backups(
        self,
        data_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = self.backups
        if data_type:
            backups = [b for b in backups if b["data_type"] == data_type]
        return sorted(backups, key=lambda b: b["created_at"], reverse=True)[:limit]

    async def cleanup_old_backups(self):
        """Remove backups older than retention period"""
        cutoff = datetime.utcnow() - timedelta(days=self.config.retention_days)

        removed = 0
        self.backups = [
            b for b in self.backups
            if datetime.fromisoformat(b["created_at"]) > cutoff
        ]

        logger.info(f"Cleaned up {removed} old backups")
        return removed


# =============================================================================
# LOGGING SYSTEM
# =============================================================================

class StructuredLogger:
    """Structured logging with context and metrics"""

    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name
        self.log_level = log_level
        self.context: Dict[str, Any] = {}
        self.metrics: Dict[str, int] = {}

    def with_context(self, **kwargs) -> "StructuredLogger":
        """Create a new logger with additional context"""
        new_logger = StructuredLogger(self.service_name, self.log_level)
        new_logger.context = {**self.context, **kwargs}
        return new_logger

    def _format_log(
        self,
        level: str,
        message: str,
        extra: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Format a structured log entry"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "service": self.service_name,
            "message": message,
            "context": {**self.context, **(extra or {})}
        }

    def info(self, message: str, **kwargs):
        """Log info message"""
        entry = self._format_log("INFO", message, kwargs)
        logger.info(f"[{self.service_name}] {message}", extra=entry)
        self._increment_metric("log_info")

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        entry = self._format_log("WARNING", message, kwargs)
        logger.warning(f"[{self.service_name}] {message}", extra=entry)
        self._increment_metric("log_warning")

    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message"""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
        entry = self._format_log("ERROR", message, kwargs)
        logger.error(f"[{self.service_name}] {message}", extra=entry)
        self._increment_metric("log_error")

    def audit(self, action: str, actor: str, resource: str, **kwargs):
        """Log audit event"""
        entry = self._format_log("AUDIT", action, {
            "actor": actor,
            "resource": resource,
            **kwargs
        })
        logger.info(f"[AUDIT] {action} by {actor} on {resource}", extra=entry)
        self._increment_metric("audit_events")

    def metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Log a metric"""
        entry = self._format_log("METRIC", name, {
            "value": value,
            "tags": tags or {}
        })
        logger.debug(f"[METRIC] {name}={value}", extra=entry)

    def _increment_metric(self, name: str):
        """Increment an internal metric counter"""
        self.metrics[name] = self.metrics.get(name, 0) + 1


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

@dataclass
class PerformanceMetric:
    """A performance metric"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


class PerformanceMonitor:
    """Monitors system performance"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics: List[PerformanceMetric] = []
        self.timers: Dict[str, float] = {}
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}

    def start_timer(self, name: str):
        """Start a timer"""
        self.timers[name] = time.time()

    def stop_timer(self, name: str, tags: Dict[str, str] = None) -> float:
        """Stop a timer and record the duration"""
        if name not in self.timers:
            return 0

        duration = (time.time() - self.timers[name]) * 1000  # ms
        del self.timers[name]

        self.metrics.append(PerformanceMetric(
            name=f"{name}_duration_ms",
            value=duration,
            unit="ms",
            tags=tags or {}
        ))

        return duration

    def increment(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter"""
        key = f"{name}_{str(tags)}" if tags else name
        self.counters[key] = self.counters.get(key, 0) + value

        self.metrics.append(PerformanceMetric(
            name=name,
            value=self.counters[key],
            unit="count",
            tags=tags or {}
        ))

    def gauge(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Set a gauge value"""
        self.gauges[name] = value

        self.metrics.append(PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        ))

    def histogram(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a histogram value"""
        self.metrics.append(PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        ))

    def get_summary(self, name: str, window_minutes: int = 5) -> Dict[str, float]:
        """Get summary statistics for a metric"""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        values = [
            m.value for m in self.metrics
            if m.name == name and m.timestamp > cutoff
        ]

        if not values:
            return {}

        sorted_values = sorted(values)
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": sorted_values[len(sorted_values) // 2],
            "p95": sorted_values[int(len(sorted_values) * 0.95)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)]
        }

    def get_all_metrics(self, window_minutes: int = 5) -> Dict[str, Any]:
        """Get all metrics summary"""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = [m for m in self.metrics if m.timestamp > cutoff]

        # Group by name
        by_name = {}
        for m in recent:
            if m.name not in by_name:
                by_name[m.name] = []
            by_name[m.name].append(m.value)

        return {
            name: {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values)
            }
            for name, values in by_name.items()
        }


# =============================================================================
# CONTEXT MANAGER FOR TIMING
# =============================================================================

class Timer:
    """Context manager for timing operations"""

    def __init__(self, monitor: PerformanceMonitor, name: str, tags: Dict[str, str] = None):
        self.monitor = monitor
        self.name = name
        self.tags = tags or {}
        self.duration = 0

    async def __aenter__(self):
        self.monitor.start_timer(self.name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.duration = self.monitor.stop_timer(self.name, self.tags)
        if exc_type:
            self.monitor.increment(f"{self.name}_errors", tags=self.tags)
        return False


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_devops_endpoints(
    rpc_manager: RPCManager,
    backup_manager: BackupManager,
    performance_monitor: PerformanceMonitor
):
    """Create DevOps API endpoints"""
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/devops", tags=["DevOps"])

    @router.get("/rpc/health")
    async def get_rpc_health():
        """Get RPC endpoint health"""
        return {
            "endpoints": [
                {
                    "endpoint": m.endpoint,
                    "status": m.status.value,
                    "latency_ms": m.latency_ms,
                    "success_rate": m.success_rate
                }
                for m in rpc_manager.get_health_metrics()
            ],
            "stats": rpc_manager.get_stats()
        }

    @router.get("/backups")
    async def list_backups(data_type: Optional[str] = None, limit: int = 50):
        """List available backups"""
        return await backup_manager.list_backups(data_type, limit)

    @router.post("/backups/{backup_id}/restore")
    async def restore_backup(backup_id: str):
        """Restore from a backup"""
        try:
            result = await backup_manager.restore_backup(backup_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/metrics")
    async def get_metrics(window_minutes: int = 5):
        """Get performance metrics"""
        return performance_monitor.get_all_metrics(window_minutes)

    @router.get("/metrics/{name}")
    async def get_metric_summary(name: str, window_minutes: int = 5):
        """Get summary for a specific metric"""
        return performance_monitor.get_summary(name, window_minutes)

    return router
