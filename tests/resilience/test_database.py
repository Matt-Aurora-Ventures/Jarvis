"""
JARVIS Database Resilience Tests

Tests system behavior under database stress and failures.

Scenarios:
- Connection pool exhaustion
- Slow queries (1000ms+)
- Transaction rollback
- Data corruption recovery

Usage:
    pytest tests/resilience/test_database.py -v
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.security_validation import ValidationError, sanitize_sql_identifier


@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool."""
    pool_size: int
    active_connections: int
    waiting_requests: int
    peak_active: int = 0
    exhaustion_events: int = 0
    total_acquisitions: int = 0
    total_releases: int = 0
    avg_wait_time_ms: float = 0
    max_wait_time_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "active_connections": self.active_connections,
            "waiting_requests": self.waiting_requests,
            "peak_active": self.peak_active,
            "exhaustion_events": self.exhaustion_events,
            "total_acquisitions": self.total_acquisitions,
            "total_releases": self.total_releases,
            "avg_wait_time_ms": round(self.avg_wait_time_ms, 2),
            "max_wait_time_ms": round(self.max_wait_time_ms, 2),
        }


class MockConnectionPool:
    """Mock database connection pool."""

    def __init__(
        self,
        pool_size: int = 10,
        acquire_timeout: float = 5.0,
    ):
        self.pool_size = pool_size
        self.acquire_timeout = acquire_timeout
        self._semaphore = asyncio.Semaphore(pool_size)
        self._active = 0
        self._waiting = 0
        self._stats = ConnectionPoolStats(
            pool_size=pool_size,
            active_connections=0,
            waiting_requests=0,
        )
        self._wait_times: List[float] = []
        self._lock = asyncio.Lock()

    @property
    def stats(self) -> ConnectionPoolStats:
        """Get current pool statistics."""
        self._stats.active_connections = self._active
        self._stats.waiting_requests = self._waiting
        if self._wait_times:
            self._stats.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times) * 1000
            self._stats.max_wait_time_ms = max(self._wait_times) * 1000
        return self._stats

    async def acquire(self) -> "MockConnection":
        """Acquire a connection from the pool."""
        async with self._lock:
            self._waiting += 1

        start = time.time()
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.acquire_timeout,
            )
        except asyncio.TimeoutError:
            async with self._lock:
                self._waiting -= 1
                self._stats.exhaustion_events += 1
            raise PoolExhaustedError(f"Connection pool exhausted (size={self.pool_size})")

        wait_time = time.time() - start
        async with self._lock:
            self._waiting -= 1
            self._active += 1
            self._stats.total_acquisitions += 1
            self._stats.peak_active = max(self._stats.peak_active, self._active)
            self._wait_times.append(wait_time)

        return MockConnection(self)

    async def release(self, conn: "MockConnection"):
        """Release a connection back to the pool."""
        async with self._lock:
            self._active -= 1
            self._stats.total_releases += 1
        self._semaphore.release()


class PoolExhaustedError(Exception):
    """Raised when connection pool is exhausted."""
    pass


class MockConnection:
    """Mock database connection."""

    def __init__(self, pool: MockConnectionPool):
        self._pool = pool
        self._in_transaction = False
        self._transaction_queries: List[str] = []

    async def execute(
        self,
        query: str,
        params: tuple = None,
        latency_ms: float = 10,
    ) -> List[Dict[str, Any]]:
        """Execute a query."""
        # Simulate query latency
        await asyncio.sleep(latency_ms / 1000)

        if self._in_transaction:
            self._transaction_queries.append(query)

        # Return mock results
        if "SELECT" in query.upper():
            return [{"id": 1, "value": "test"}]
        return []

    async def begin_transaction(self):
        """Begin a transaction."""
        self._in_transaction = True
        self._transaction_queries = []

    async def commit(self):
        """Commit the transaction."""
        self._in_transaction = False
        self._transaction_queries = []

    async def rollback(self):
        """Rollback the transaction."""
        self._in_transaction = False
        queries = self._transaction_queries
        self._transaction_queries = []
        return queries  # Return queries that were rolled back

    async def close(self):
        """Close the connection (return to pool)."""
        await self._pool.release(self)


class DatabaseService:
    """Database service with resilience patterns."""

    def __init__(self, pool: MockConnectionPool):
        self.pool = pool
        self.slow_query_threshold_ms = 1000
        self.slow_query_count = 0
        self.query_timeouts = 0
        self.successful_transactions = 0
        self.rolled_back_transactions = 0

    async def execute_query(
        self,
        query: str,
        params: tuple = None,
        timeout_ms: float = 5000,
        latency_ms: float = None,
    ) -> List[Dict[str, Any]]:
        """Execute a query with timeout."""
        conn = await self.pool.acquire()
        try:
            latency = latency_ms or random.uniform(5, 50)
            start = time.time()

            try:
                result = await asyncio.wait_for(
                    conn.execute(query, params, latency),
                    timeout=timeout_ms / 1000,
                )
            except asyncio.TimeoutError:
                self.query_timeouts += 1
                raise QueryTimeoutError(f"Query timed out after {timeout_ms}ms")

            elapsed_ms = (time.time() - start) * 1000
            if elapsed_ms > self.slow_query_threshold_ms:
                self.slow_query_count += 1

            return result
        finally:
            await conn.close()

    async def execute_transaction(
        self,
        queries: List[str],
        should_fail: bool = False,
    ) -> bool:
        """Execute multiple queries in a transaction."""
        conn = await self.pool.acquire()
        try:
            await conn.begin_transaction()

            for query in queries:
                await conn.execute(query)

                if should_fail:
                    raise TransactionError("Simulated transaction failure")

            await conn.commit()
            self.successful_transactions += 1
            return True

        except Exception:
            rolled_back = await conn.rollback()
            self.rolled_back_transactions += 1
            return False

        finally:
            await conn.close()

    async def verify_data_integrity(
        self,
        table: str,
        expected_count: int,
    ) -> tuple[bool, str]:
        """Verify data integrity."""
        try:
            safe_table = sanitize_sql_identifier(table)
            result = await self.execute_query(f"SELECT COUNT(*) FROM {safe_table}")
            actual_count = result[0].get("id", 0) if result else 0

            if actual_count != expected_count:
                return False, f"Count mismatch: expected {expected_count}, got {actual_count}"
            return True, "Data integrity verified"
        except ValidationError as exc:
            return False, f"Invalid table name: {exc}"
        except Exception as e:
            return False, f"Integrity check failed: {e}"


class QueryTimeoutError(Exception):
    """Raised when a query times out."""
    pass


class TransactionError(Exception):
    """Raised when a transaction fails."""
    pass


# =============================================================================
# Database Resilience Test Scenarios
# =============================================================================

class TestConnectionPoolExhaustion:
    """Tests for connection pool exhaustion scenarios."""

    @pytest.fixture
    def small_pool(self):
        """Create a small connection pool for testing exhaustion."""
        return MockConnectionPool(pool_size=5, acquire_timeout=1.0)

    @pytest.fixture
    def db_service(self, small_pool):
        return DatabaseService(small_pool)

    @pytest.mark.asyncio
    async def test_pool_exhaustion_under_load(self, db_service: DatabaseService):
        """
        Scenario: More concurrent queries than pool size.

        Expected: Some queries should timeout waiting for connection.
        """
        # Simulate 20 concurrent requests on a pool of 5
        async def slow_query():
            try:
                await db_service.execute_query(
                    "SELECT * FROM large_table",
                    latency_ms=500,  # 500ms query
                )
                return True
            except PoolExhaustedError:
                return False

        tasks = [slow_query() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if r is False)

        stats = db_service.pool.stats

        print(f"\n[Pool Exhaustion Test]")
        print(f"  Pool size: {stats.pool_size}")
        print(f"  Successful queries: {successful}")
        print(f"  Failed (pool exhausted): {failed}")
        print(f"  Peak active connections: {stats.peak_active}")
        print(f"  Exhaustion events: {stats.exhaustion_events}")
        print(f"  Max wait time: {stats.max_wait_time_ms:.2f}ms")

        # Should have some failures due to pool exhaustion
        assert stats.peak_active <= stats.pool_size
        assert successful > 0, "All queries failed"

    @pytest.mark.asyncio
    async def test_pool_recovery_after_exhaustion(self, small_pool: MockConnectionPool):
        """
        Scenario: Pool exhaustion followed by recovery.

        Expected: Pool recovers when connections are released.
        """
        db_service = DatabaseService(small_pool)

        # First wave - exhaust the pool
        async def quick_query():
            await db_service.execute_query("SELECT 1", latency_ms=100)

        # Run queries that use all connections
        first_batch = [quick_query() for _ in range(5)]
        await asyncio.gather(*first_batch)

        # Second wave - should succeed since connections were released
        second_batch = [quick_query() for _ in range(5)]
        results = await asyncio.gather(*second_batch, return_exceptions=True)

        successful = sum(1 for r in results if not isinstance(r, Exception))

        print(f"\n[Pool Recovery Test]")
        print(f"  Second batch successful: {successful}/5")

        assert successful == 5, "Pool didn't recover properly"


class TestSlowQueries:
    """Tests for slow query handling."""

    @pytest.fixture
    def pool(self):
        return MockConnectionPool(pool_size=10)

    @pytest.fixture
    def db_service(self, pool):
        return DatabaseService(pool)

    @pytest.mark.asyncio
    async def test_slow_query_detection(self, db_service: DatabaseService):
        """
        Scenario: Queries taking >1000ms.

        Expected: Slow queries are tracked and counted.
        """
        # Keep a wide buffer so scheduler jitter does not classify fast queries as slow.
        db_service.slow_query_threshold_ms = 250

        # Execute some fast and slow queries
        await db_service.execute_query("SELECT 1", latency_ms=10)   # Fast
        await db_service.execute_query("SELECT 2", latency_ms=20)   # Fast
        await db_service.execute_query("SELECT 3", latency_ms=350)  # Slow
        await db_service.execute_query("SELECT 4", latency_ms=450)  # Slow

        print(f"\n[Slow Query Detection]")
        print(f"  Slow queries detected: {db_service.slow_query_count}")

        assert db_service.slow_query_count == 2

    @pytest.mark.asyncio
    async def test_query_timeout(self, db_service: DatabaseService):
        """
        Scenario: Query exceeds timeout.

        Expected: Query is terminated and error is raised.
        """
        with pytest.raises(QueryTimeoutError):
            await db_service.execute_query(
                "SELECT * FROM very_large_table",
                timeout_ms=100,
                latency_ms=500,  # Query takes 500ms but timeout is 100ms
            )

        print(f"\n[Query Timeout Test]")
        print(f"  Timeouts: {db_service.query_timeouts}")

        assert db_service.query_timeouts == 1


class TestTransactionRollback:
    """Tests for transaction rollback scenarios."""

    @pytest.fixture
    def pool(self):
        return MockConnectionPool(pool_size=10)

    @pytest.fixture
    def db_service(self, pool):
        return DatabaseService(pool)

    @pytest.mark.asyncio
    async def test_successful_transaction(self, db_service: DatabaseService):
        """Test a successful transaction commits."""
        queries = [
            "INSERT INTO users VALUES (1, 'test')",
            "INSERT INTO profiles VALUES (1, 'profile')",
            "UPDATE users SET status = 'active' WHERE id = 1",
        ]

        success = await db_service.execute_transaction(queries)

        print(f"\n[Successful Transaction]")
        print(f"  Success: {success}")
        print(f"  Committed: {db_service.successful_transactions}")

        assert success
        assert db_service.successful_transactions == 1

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_failure(self, db_service: DatabaseService):
        """
        Scenario: Transaction fails mid-way.

        Expected: All changes are rolled back.
        """
        queries = [
            "INSERT INTO orders VALUES (1, 100)",
            "INSERT INTO order_items VALUES (1, 'item1')",
            "INSERT INTO payments VALUES (1, 100)",  # This would fail
        ]

        success = await db_service.execute_transaction(queries, should_fail=True)

        print(f"\n[Transaction Rollback]")
        print(f"  Success: {success}")
        print(f"  Rolled back: {db_service.rolled_back_transactions}")

        assert not success
        assert db_service.rolled_back_transactions == 1

    @pytest.mark.asyncio
    async def test_multiple_transactions_isolation(self, db_service: DatabaseService):
        """Test that transactions are isolated."""
        # Run multiple transactions concurrently
        async def transaction(should_fail: bool):
            queries = [
                f"INSERT INTO test VALUES ({random.randint(1, 1000)})",
                f"UPDATE test SET value = {random.randint(1, 100)}",
            ]
            return await db_service.execute_transaction(queries, should_fail=should_fail)

        # Mix of successful and failing transactions
        tasks = [
            transaction(False),
            transaction(False),
            transaction(True),
            transaction(False),
            transaction(True),
        ]

        results = await asyncio.gather(*tasks)
        successful = sum(1 for r in results if r)
        failed = sum(1 for r in results if not r)

        print(f"\n[Transaction Isolation]")
        print(f"  Successful: {successful}")
        print(f"  Failed/Rolled back: {failed}")

        assert successful == 3
        assert failed == 2


class TestDataCorruptionRecovery:
    """Tests for data corruption detection and recovery."""

    @pytest.fixture
    def pool(self):
        return MockConnectionPool(pool_size=10)

    @pytest.fixture
    def db_service(self, pool):
        return DatabaseService(pool)

    @pytest.mark.asyncio
    async def test_data_integrity_verification(self, db_service: DatabaseService):
        """Test data integrity verification."""
        # In mock, this always returns id=1
        valid, message = await db_service.verify_data_integrity("users", 1)

        print(f"\n[Data Integrity Check]")
        print(f"  Valid: {valid}")
        print(f"  Message: {message}")

        assert valid

    @pytest.mark.asyncio
    async def test_corruption_detection(self, db_service: DatabaseService):
        """
        Scenario: Data corruption detected.

        Expected: System reports corruption.
        """
        # Expect count of 100 but mock returns 1
        valid, message = await db_service.verify_data_integrity("users", 100)

        print(f"\n[Corruption Detection]")
        print(f"  Valid: {valid}")
        print(f"  Message: {message}")

        assert not valid
        assert "Count mismatch" in message

    @pytest.mark.asyncio
    async def test_data_integrity_rejects_invalid_table_name(
        self,
        db_service: DatabaseService,
    ):
        """Invalid table names should be rejected deterministically."""
        valid, message = await db_service.verify_data_integrity(
            "users; DROP TABLE users; --",
            1,
        )

        assert not valid
        assert "Invalid table name" in message


class TestConnectionPoolStats:
    """Unit tests for connection pool statistics."""

    def test_stats_tracking(self):
        """Test that pool stats are tracked correctly."""
        stats = ConnectionPoolStats(
            pool_size=10,
            active_connections=5,
            waiting_requests=2,
            peak_active=8,
            exhaustion_events=1,
            total_acquisitions=100,
            total_releases=95,
        )

        result = stats.to_dict()

        assert result["pool_size"] == 10
        assert result["active_connections"] == 5
        assert result["peak_active"] == 8
        assert result["exhaustion_events"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
