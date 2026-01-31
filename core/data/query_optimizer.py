"""
Query Optimization Module

Provides performance optimizations for data access:
- Batch price lookups with request coalescing
- API call reduction through caching
- Connection pooling for database
- Async query batching
- Request deduplication

Usage:
    from core.data.query_optimizer import (
        BatchPriceLookup,
        RequestDeduplicator,
        ConnectionPool,
        OptimizedPriceService
    )

    # Batch price lookups
    lookup = BatchPriceLookup(fetcher=api_fetch)
    price = await lookup.get_price("SOL")

    # Connection pooling
    pool = ConnectionPool("data/jarvis.db")
    with pool.get_connection() as conn:
        conn.execute("SELECT * FROM positions")
"""

import asyncio
import queue
import sqlite3
import threading
import time
import logging
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from core.security_validation import sanitize_sql_identifier

logger = logging.getLogger(__name__)


# =============================================================================
# Batch Price Lookup
# =============================================================================

class BatchPriceLookup:
    """
    Batch multiple price lookup requests into single API calls.

    Collects requests within a time window and executes them as a batch,
    reducing the number of API calls significantly.

    Usage:
        lookup = BatchPriceLookup(
            batch_fetcher=fetch_prices,
            batch_window_ms=50,
            max_batch_size=10
        )

        # These concurrent requests will be batched
        price1 = await lookup.get_price("SOL")
        price2 = await lookup.get_price("BTC")
    """

    def __init__(
        self,
        batch_fetcher: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        batch_window_ms: int = 50,
        max_batch_size: int = 50,
        cache_ttl_seconds: int = 60
    ):
        """
        Args:
            batch_fetcher: Async function that fetches prices for a list of tokens
            batch_window_ms: Time window to collect requests before batching
            max_batch_size: Maximum batch size before forced execution
            cache_ttl_seconds: How long to cache results (0 to disable)
        """
        self.batch_fetcher = batch_fetcher
        self.batch_window_ms = batch_window_ms
        self.max_batch_size = max_batch_size
        self.cache_ttl_seconds = cache_ttl_seconds

        self._pending: Dict[str, asyncio.Future] = {}
        self._batch: List[str] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None

        # Simple cache
        self._cache: Dict[str, tuple] = {}  # key -> (value, expires_at)

    async def get_price(self, token: str) -> Any:
        """Get price for a token, batching with other requests."""
        # Check cache first
        if self.cache_ttl_seconds > 0 and token in self._cache:
            value, expires_at = self._cache[token]
            if time.time() < expires_at:
                return value
            del self._cache[token]

        async with self._batch_lock:
            # Check if already pending
            if token in self._pending:
                return await self._pending[token]

            # Create future for this request
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._pending[token] = future

            # Add to batch
            self._batch.append(token)

            # Start batch timer if first in batch
            if len(self._batch) == 1:
                self._batch_task = asyncio.create_task(self._execute_after_delay())

            # Execute immediately if batch is full
            if len(self._batch) >= self.max_batch_size:
                if self._batch_task:
                    self._batch_task.cancel()
                await self._execute_batch()

        return await future

    async def _execute_after_delay(self):
        """Execute batch after window delay."""
        await asyncio.sleep(self.batch_window_ms / 1000)
        async with self._batch_lock:
            if self._batch:
                await self._execute_batch()

    async def _execute_batch(self):
        """Execute the current batch."""
        if not self._batch:
            return

        tokens = self._batch.copy()
        futures = {t: self._pending[t] for t in tokens}
        self._batch.clear()

        try:
            results = await self.batch_fetcher(tokens)

            # Cache and resolve futures
            expires_at = time.time() + self.cache_ttl_seconds

            for token in tokens:
                value = results.get(token)

                # Cache if enabled
                if self.cache_ttl_seconds > 0 and value is not None:
                    self._cache[token] = (value, expires_at)

                # Resolve future
                if token in futures and not futures[token].done():
                    futures[token].set_result(value)

        except Exception as e:
            # Reject all pending futures
            for token, future in futures.items():
                if not future.done():
                    future.set_exception(e)

        finally:
            # Clean up pending
            for token in tokens:
                self._pending.pop(token, None)


# =============================================================================
# Request Deduplication
# =============================================================================

class RequestDeduplicator:
    """
    Deduplicate concurrent requests for the same key.

    If multiple requests for the same key arrive while one is pending,
    they all share the same result instead of making duplicate calls.

    Usage:
        dedup = RequestDeduplicator()

        # These will share one actual fetch
        result1 = await dedup.get_or_fetch("key", fetch_func)
        result2 = await dedup.get_or_fetch("key", fetch_func)
    """

    def __init__(self):
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(
        self,
        key: str,
        fetcher: Callable[[], Awaitable[Any]]
    ) -> Any:
        """
        Get result, deduplicating concurrent requests.

        Args:
            key: Unique key for this request
            fetcher: Async function to fetch the value (no args)

        Returns:
            Fetched value
        """
        async with self._lock:
            # Check if already pending
            if key in self._pending:
                return await self._pending[key]

            # Create future
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._pending[key] = future

        try:
            result = await fetcher()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._pending.pop(key, None)


# =============================================================================
# Connection Pool
# =============================================================================

class ConnectionPool:
    """
    SQLite connection pool for efficient database access.

    Maintains a pool of connections to avoid the overhead of
    creating new connections for each query.

    Usage:
        pool = ConnectionPool("data/jarvis.db", max_connections=5)

        with pool.get_connection() as conn:
            conn.execute("SELECT * FROM positions")
    """

    def __init__(self, db_path: str, max_connections: int = 5):
        """
        Args:
            db_path: Path to SQLite database
            max_connections: Maximum connections to maintain
        """
        self.db_path = db_path
        self.max_connections = max_connections

        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = threading.Lock()

        # Stats
        self._acquired = 0
        self._released = 0
        self._created = 0

        # Ensure database exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = self._acquire()
        try:
            yield conn
        finally:
            self._release(conn)

    def _acquire(self) -> sqlite3.Connection:
        """Acquire a connection from pool or create new."""
        # Try to get from pool
        try:
            conn = self._pool.get_nowait()
            self._acquired += 1
            return conn
        except queue.Empty:
            pass

        # Create new if under limit
        with self._lock:
            if self._active_connections < self.max_connections:
                conn = self._create_connection()
                self._active_connections += 1
                self._created += 1
                self._acquired += 1
                return conn

        # Wait for one to be returned
        conn = self._pool.get(timeout=5.0)
        self._acquired += 1
        return conn

    def _release(self, conn: sqlite3.Connection):
        """Return connection to pool."""
        try:
            self._pool.put_nowait(conn)
            self._released += 1
        except queue.Full:
            # Pool is full, close connection
            conn.close()
            with self._lock:
                self._active_connections -= 1

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "max_connections": self.max_connections,
            "active_connections": self._active_connections,
            "pool_size": self._pool.qsize(),
            "acquired": self._acquired,
            "released": self._released,
            "created": self._created
        }

    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break

        with self._lock:
            self._active_connections = 0


# =============================================================================
# Async Query Batcher
# =============================================================================

class AsyncQueryBatcher:
    """
    Batch multiple async queries for efficient execution.

    Collects queries within a time window and executes them together,
    reducing round-trips and improving throughput.

    Usage:
        batcher = AsyncQueryBatcher(executor=batch_execute)

        # These will be batched
        result1 = await batcher.execute("SELECT 1")
        result2 = await batcher.execute("SELECT 2")
    """

    def __init__(
        self,
        executor: Callable[[List[str]], Awaitable[List[Any]]],
        batch_window_ms: int = 20,
        max_batch_size: int = 100
    ):
        """
        Args:
            executor: Function that executes a batch of queries
            batch_window_ms: Time window to collect queries
            max_batch_size: Max queries per batch
        """
        self.executor = executor
        self.batch_window_ms = batch_window_ms
        self.max_batch_size = max_batch_size

        self._queries: List[str] = []
        self._futures: List[asyncio.Future] = []
        self._lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None

    async def execute(self, query: str) -> Any:
        """Add query to batch and wait for result."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        async with self._lock:
            self._queries.append(query)
            self._futures.append(future)

            # Start timer on first query
            if len(self._queries) == 1:
                self._batch_task = asyncio.create_task(self._execute_after_delay())

            # Execute immediately if batch is full
            if len(self._queries) >= self.max_batch_size:
                if self._batch_task:
                    self._batch_task.cancel()
                await self._execute_batch()

        return await future

    async def _execute_after_delay(self):
        """Execute batch after window."""
        await asyncio.sleep(self.batch_window_ms / 1000)
        async with self._lock:
            if self._queries:
                await self._execute_batch()

    async def _execute_batch(self):
        """Execute the current batch."""
        if not self._queries:
            return

        queries = self._queries.copy()
        futures = self._futures.copy()
        self._queries.clear()
        self._futures.clear()

        try:
            results = await self.executor(queries)

            # Resolve futures
            for i, future in enumerate(futures):
                if i < len(results):
                    future.set_result(results[i])
                else:
                    future.set_result(None)

        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)


# =============================================================================
# Query Analyzer
# =============================================================================

@dataclass
class QueryAnalysis:
    """Result of query analysis."""
    query: str
    execution_time_ms: float
    rows_affected: int
    uses_index: bool
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    explain_plan: List[Dict[str, Any]] = field(default_factory=list)


class QueryAnalyzer:
    """
    Analyze SQL queries for optimization opportunities.

    Provides insights into:
    - Index usage
    - Full table scans
    - Query patterns to avoid
    - Index suggestions
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def analyze(self, query: str, params: tuple = None) -> QueryAnalysis:
        """Analyze a query and provide optimization recommendations.

        Note: Only SELECT queries are allowed for security reasons.
        Other query types will be analyzed for patterns but not executed.
        """
        warnings = []
        suggestions = []
        uses_index = False
        rows_affected = 0

        # Security: Only allow SELECT queries to be analyzed/executed
        query_stripped = query.strip()
        query_upper = query_stripped.upper()
        is_select = query_upper.startswith("SELECT")

        if not is_select:
            warnings.append("Only SELECT queries can be fully analyzed for security reasons")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            # Get EXPLAIN QUERY PLAN - only for SELECT queries
            explain_results = []
            if is_select:
                try:
                    cursor = conn.execute(f"EXPLAIN QUERY PLAN {query_stripped}")
                    explain_results = [dict(row) for row in cursor.fetchall()]
                except sqlite3.Error:
                    pass

            # Check for index usage
            explain_str = str(explain_results)
            uses_index = "USING INDEX" in explain_str
            has_scan = "SCAN TABLE" in explain_str

            if has_scan and not uses_index:
                warnings.append("Query performs full table scan - no index used")

            # Analyze query pattern (query_upper already set above)
            if "SELECT *" in query_upper:
                warnings.append("Avoid SELECT * - specify only needed columns")

            if "WHERE" not in query_upper and "LIMIT" not in query_upper:
                warnings.append("No WHERE clause or LIMIT - may return excessive rows")

            if query_upper.count("JOIN") > 2:
                warnings.append("Multiple JOINs may impact performance")

            if "LIKE '%" in query or "LIKE '%'" in query_upper:
                warnings.append("Leading wildcard in LIKE prevents index usage")

            # Execute and time - only for SELECT queries
            start = time.perf_counter()
            if is_select:
                try:
                    if params:
                        cursor = conn.execute(query_stripped, params)
                    else:
                        cursor = conn.execute(query_stripped)
                    rows = cursor.fetchall()
                    rows_affected = len(rows)
                except sqlite3.Error as e:
                    warnings.append(f"Query error: {e}")
                    rows_affected = 0

            execution_time = (time.perf_counter() - start) * 1000

            if execution_time > 100:
                warnings.append(f"Slow query: {execution_time:.0f}ms")

            return QueryAnalysis(
                query=query,
                execution_time_ms=execution_time,
                rows_affected=rows_affected,
                uses_index=uses_index,
                warnings=warnings,
                suggestions=suggestions,
                explain_plan=explain_results
            )

        finally:
            conn.close()

    def suggest_indexes(self, table: str) -> List[str]:
        """Suggest indexes for a table."""
        suggestions = []

        # Sanitize table name to prevent SQL injection
        safe_table = sanitize_sql_identifier(table)

        conn = sqlite3.connect(self.db_path)
        try:
            # Get existing indexes
            cursor = conn.execute(f"PRAGMA index_list({safe_table})")
            existing = {row[1] for row in cursor.fetchall()}

            # Get columns
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")
            columns = [row[1] for row in cursor.fetchall()]

            # Common patterns to index
            for col in columns:
                if col.endswith("_id") or col.endswith("_at") or col in ["status", "type", "symbol", "token_mint", "user_id"]:
                    index_name = f"idx_{table}_{col}"
                    if index_name not in existing:
                        suggestions.append(f"CREATE INDEX {index_name} ON {table}({col});")

            return suggestions

        finally:
            conn.close()


# =============================================================================
# Optimized Price Service
# =============================================================================

class OptimizedPriceService:
    """
    Optimized service for fetching token prices.

    Combines batching, caching, and deduplication for maximum efficiency.

    Usage:
        service = OptimizedPriceService(fetcher=api_call)
        prices = await service.get_prices(["SOL", "BTC", "ETH"])
    """

    def __init__(
        self,
        fetcher: Callable[[List[str]], Awaitable[Dict[str, Any]]],
        cache_ttl_seconds: int = 60,
        batch_window_ms: int = 50
    ):
        self.fetcher = fetcher
        self.cache_ttl_seconds = cache_ttl_seconds

        self._batch_lookup = BatchPriceLookup(
            batch_fetcher=fetcher,
            batch_window_ms=batch_window_ms,
            cache_ttl_seconds=cache_ttl_seconds
        )

        self._dedup = RequestDeduplicator()

        # Metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_requests = 0
        self._lock = threading.Lock()

    async def get_price(self, token: str) -> Any:
        """Get single token price."""
        with self._lock:
            self._total_requests += 1

        # Check batch lookup's cache
        if token in self._batch_lookup._cache:
            value, expires_at = self._batch_lookup._cache[token]
            if time.time() < expires_at:
                with self._lock:
                    self._cache_hits += 1
                return value

        with self._lock:
            self._cache_misses += 1

        return await self._batch_lookup.get_price(token)

    async def get_prices(self, tokens: List[str]) -> Dict[str, Any]:
        """Get multiple token prices."""
        results = {}

        for token in tokens:
            results[token] = await self.get_price(token)

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        with self._lock:
            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "total_requests": self._total_requests,
                "hit_rate": self._cache_hits / self._total_requests if self._total_requests > 0 else 0.0
            }

    def clear_cache(self):
        """Clear the price cache."""
        self._batch_lookup._cache.clear()
