"""
PostgreSQL Async Client with Connection Pooling.

Provides async database access with:
- Connection pooling (asyncpg)
- Automatic reconnection on failure
- Health checking
- Transaction support
- Query metrics

Usage:
    from core.database.postgres_client import PostgresClient, get_postgres_client

    client = get_postgres_client()

    # Simple query
    rows = await client.fetch("SELECT * FROM positions WHERE status = $1", "open")

    # Transaction
    async with client.transaction() as conn:
        await conn.execute("INSERT INTO trades ...")
        await conn.execute("UPDATE positions ...")
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Optional asyncpg dependency
try:
    import asyncpg
    from asyncpg import Pool, Connection
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None
    Pool = None
    Connection = None
    logger.warning("asyncpg not available - PostgreSQL async client disabled")


@dataclass
class PoolMetrics:
    """Connection pool metrics for monitoring."""
    pool_size: int = 0
    available_connections: int = 0
    active_connections: int = 0
    total_connections: int = 0
    wait_time_ms: float = 0.0
    queries_executed: int = 0
    errors: int = 0
    last_health_check: Optional[datetime] = None


class ConnectionPoolMonitor:
    """
    Monitor connection pool health and metrics.

    Provides real-time visibility into:
    - Connection utilization
    - Query performance
    - Error rates
    - Health status
    """

    def __init__(self, pool: Optional[Any], metrics: PoolMetrics):
        """
        Initialize pool monitor.

        Args:
            pool: asyncpg Pool instance
            metrics: PoolMetrics instance to track
        """
        self.pool = pool
        self._metrics = metrics
        self._utilization_threshold = 0.8  # Warn at 80% utilization
        self._error_threshold = 10  # Warn after 10 errors

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get current pool metrics.

        Returns:
            Dictionary with all pool statistics
        """
        metrics = {
            "pool_size": self._metrics.pool_size,
            "active_connections": self._metrics.active_connections,
            "idle_connections": self._metrics.pool_size - self._metrics.active_connections,
            "total_connections": self._metrics.total_connections,
            "waiting_requests": 0,  # asyncpg doesn't expose this directly
            "connection_errors": self._metrics.errors,
            "avg_query_time_ms": self._metrics.wait_time_ms,
            "queries_executed": self._metrics.queries_executed,
        }

        # Get pool-level metrics if available
        if self.pool and hasattr(self.pool, 'get_size'):
            actual_size = self.pool.get_size()
            actual_idle = self.pool.get_idle_size()
            metrics["actual_pool_size"] = actual_size
            metrics["actual_idle"] = actual_idle
            metrics["actual_active"] = actual_size - actual_idle

            # Calculate utilization
            if actual_size > 0:
                metrics["utilization"] = (actual_size - actual_idle) / actual_size
            else:
                metrics["utilization"] = 0.0

        if self._metrics.last_health_check:
            metrics["last_health_check"] = self._metrics.last_health_check.isoformat()

        return metrics

    async def check_health(self) -> Tuple[bool, str]:
        """
        Check pool health.

        Returns:
            Tuple of (is_healthy, status_message)
        """
        metrics = await self.get_metrics()

        # Check for connection exhaustion (using actual pool stats if available)
        if "utilization" in metrics:
            if metrics["utilization"] >= 0.9:
                return False, f"Pool near exhaustion ({metrics['utilization']:.0%} utilization)"
            elif metrics["utilization"] >= self._utilization_threshold:
                return True, f"Pool utilization high ({metrics['utilization']:.0%})"
        else:
            # Fallback to basic check
            if metrics["active_connections"] >= metrics["pool_size"] * 0.9:
                return False, "Pool near exhaustion (90% utilization)"

        # Check for high error rate
        if metrics["connection_errors"] > self._error_threshold:
            return False, f"High error rate ({metrics['connection_errors']} errors)"

        # Check if pool is responding
        if not self.pool:
            return False, "Pool not initialized"

        return True, "Pool healthy"

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status for monitoring.

        Returns:
            Dictionary with health status and metrics
        """
        healthy, message = await self.check_health()
        metrics = await self.get_metrics()

        status = "ok" if healthy else "degraded"
        if not self.pool:
            status = "down"

        return {
            "healthy": healthy,
            "status": status,
            "message": message,
            "metrics": metrics,
        }


class PostgresClient:
    """
    Async PostgreSQL client with connection pooling.

    Features:
    - Connection pooling with configurable size
    - Automatic retry on transient failures
    - Health checking
    - Transaction support
    - Query metrics
    """

    def __init__(
        self,
        connection_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_recycle: int = 3600,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        statement_cache_size: int = 100,
    ):
        """
        Initialize PostgreSQL client.

        Args:
            connection_url: PostgreSQL connection URL (or uses DATABASE_URL env var)
            pool_size: Minimum number of connections in pool
            max_overflow: Maximum connections above pool_size
            pool_recycle: Seconds before connection is recycled
            max_retries: Number of connection retry attempts
            retry_delay: Delay between retry attempts
            statement_cache_size: Size of prepared statement cache
        """
        self.connection_url = connection_url or os.getenv("DATABASE_URL", "")
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_recycle = pool_recycle
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.statement_cache_size = statement_cache_size

        self._pool: Optional[Any] = None  # asyncpg.Pool
        self._metrics = PoolMetrics()
        self._connected = False
        self._lock = asyncio.Lock()
        self._monitor: Optional[ConnectionPoolMonitor] = None

    async def connect(self) -> None:
        """
        Create connection pool.

        Raises:
            ConnectionError: If connection fails after all retries
        """
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg is required. Install: pip install asyncpg")

        if not self.connection_url:
            raise ValueError("No connection URL provided. Set DATABASE_URL or pass connection_url")

        async with self._lock:
            if self._connected:
                return

            for attempt in range(self.max_retries):
                try:
                    self._pool = await self._create_pool()
                    self._connected = True
                    self._metrics.pool_size = self.pool_size
                    self._monitor = ConnectionPoolMonitor(self._pool, self._metrics)
                    logger.info(f"PostgreSQL connection pool created (size={self.pool_size})")
                    return
                except Exception as e:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise ConnectionError(f"Failed to connect after {self.max_retries} attempts: {e}")

    async def _create_pool(self) -> Any:
        """Create asyncpg connection pool."""
        return await asyncpg.create_pool(
            self.connection_url,
            min_size=self.pool_size,
            max_size=self.pool_size + self.max_overflow,
            max_inactive_connection_lifetime=self.pool_recycle,
            statement_cache_size=self.statement_cache_size,
        )

    async def close(self) -> None:
        """Close connection pool."""
        async with self._lock:
            if self._pool:
                await self._pool.close()
                self._pool = None
                self._connected = False
                self._monitor = None
                logger.info("PostgreSQL connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Usage:
            async with client.acquire() as conn:
                await conn.execute("SELECT 1")
        """
        if not self._connected:
            await self.connect()

        start_time = time.time()
        async with self._pool.acquire() as conn:
            wait_time = (time.time() - start_time) * 1000
            self._metrics.wait_time_ms = wait_time
            self._metrics.active_connections += 1
            try:
                yield conn
            finally:
                self._metrics.active_connections -= 1

    @asynccontextmanager
    async def transaction(self):
        """
        Start a transaction.

        Usage:
            async with client.transaction() as conn:
                await conn.execute("INSERT INTO ...")
                await conn.execute("UPDATE ...")
        """
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def fetch(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query with $1, $2, etc. placeholders
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            List of result rows as dictionaries
        """
        async with self.acquire() as conn:
            try:
                rows = await conn.fetch(query, *args, timeout=timeout)
                self._metrics.queries_executed += 1
                return [dict(row) for row in rows]
            except Exception as e:
                self._metrics.errors += 1
                logger.error(f"Query failed: {e}")
                raise

    async def fetchrow(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute query and fetch one result.

        Returns:
            Single result row as dictionary, or None
        """
        async with self.acquire() as conn:
            try:
                row = await conn.fetchrow(query, *args, timeout=timeout)
                self._metrics.queries_executed += 1
                return dict(row) if row else None
            except Exception as e:
                self._metrics.errors += 1
                logger.error(f"Query failed: {e}")
                raise

    async def fetchval(
        self,
        query: str,
        *args,
        column: int = 0,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Execute query and fetch single value.

        Returns:
            Single value from result
        """
        async with self.acquire() as conn:
            try:
                value = await conn.fetchval(query, *args, column=column, timeout=timeout)
                self._metrics.queries_executed += 1
                return value
            except Exception as e:
                self._metrics.errors += 1
                logger.error(f"Query failed: {e}")
                raise

    async def execute(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> str:
        """
        Execute a query (INSERT, UPDATE, DELETE).

        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        async with self.acquire() as conn:
            try:
                result = await conn.execute(query, *args, timeout=timeout)
                self._metrics.queries_executed += 1
                return result
            except Exception as e:
                self._metrics.errors += 1
                logger.error(f"Query failed: {e}")
                raise

    async def execute_many(
        self,
        query: str,
        args_list: List[Tuple],
        timeout: Optional[float] = None
    ) -> None:
        """
        Execute query with multiple parameter sets (batch insert).

        Args:
            query: SQL query with $1, $2, etc. placeholders
            args_list: List of parameter tuples
            timeout: Query timeout in seconds
        """
        async with self.acquire() as conn:
            try:
                await conn.executemany(query, args_list, timeout=timeout)
                self._metrics.queries_executed += len(args_list)
            except Exception as e:
                self._metrics.errors += 1
                logger.error(f"Batch query failed: {e}")
                raise

    async def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with self.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                self._metrics.last_health_check = datetime.utcnow()
                return result == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_pool_health(self) -> Dict[str, Any]:
        """
        Get comprehensive pool health status.

        Returns:
            Dictionary with health status and metrics
        """
        if not self._monitor:
            return {
                "healthy": False,
                "status": "down",
                "message": "Pool monitor not initialized",
                "metrics": {},
            }

        return await self._monitor.get_health_status()

    async def check_pool_utilization(self) -> None:
        """
        Check pool utilization and log warnings if needed.

        This should be called periodically by a background task.
        """
        if not self._monitor:
            return

        healthy, message = await self._monitor.check_health()

        if not healthy:
            logger.warning(f"Connection pool health issue: {message}")

        # Log info at high utilization even if still healthy
        metrics = await self._monitor.get_metrics()
        if "utilization" in metrics and metrics["utilization"] >= 0.8:
            logger.info(
                f"Connection pool utilization: {metrics['utilization']:.0%} "
                f"({metrics.get('actual_active', 0)}/{metrics.get('actual_pool_size', 0)} connections)"
            )

    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Get connection pool metrics.

        Returns:
            Dictionary with pool statistics
        """
        metrics = {
            "pool_size": self._metrics.pool_size,
            "available_connections": self._metrics.pool_size - self._metrics.active_connections,
            "active_connections": self._metrics.active_connections,
            "total_connections": self._metrics.total_connections,
            "wait_time_ms": self._metrics.wait_time_ms,
            "queries_executed": self._metrics.queries_executed,
            "errors": self._metrics.errors,
        }

        if self._metrics.last_health_check:
            metrics["last_health_check"] = self._metrics.last_health_check.isoformat()

        # Get pool-level metrics if available
        if self._pool and hasattr(self._pool, 'get_size'):
            metrics["actual_pool_size"] = self._pool.get_size()
            metrics["actual_idle"] = self._pool.get_idle_size()

        return metrics


# Global singleton
_postgres_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
    """
    Get or create global PostgreSQL client.

    Returns:
        Global PostgresClient singleton
    """
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgresClient()
    return _postgres_client


async def init_postgres(connection_url: Optional[str] = None, **kwargs) -> PostgresClient:
    """
    Initialize PostgreSQL client with custom settings.

    Args:
        connection_url: PostgreSQL connection URL
        **kwargs: Additional PostgresClient settings

    Returns:
        Initialized PostgresClient
    """
    global _postgres_client
    _postgres_client = PostgresClient(connection_url=connection_url, **kwargs)
    await _postgres_client.connect()
    return _postgres_client


async def close_postgres() -> None:
    """Close global PostgreSQL client."""
    global _postgres_client
    if _postgres_client:
        await _postgres_client.close()
        _postgres_client = None
