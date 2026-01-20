"""
Performance tests for database connection pool.

Validates:
- Connection pooling reduces overhead
- Health checks don't impact performance significantly
- Pool handles concurrent load
- Metrics collection is low-overhead
"""
import pytest
import sqlite3
import tempfile
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.db.pool import DatabaseConfig, ConnectionPool, Database


class TestPoolPerformance:
    """Performance tests for connection pool."""

    def test_pool_vs_no_pool_overhead(self):
        """Pool should reduce connection overhead vs creating new connections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Setup test database
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            for i in range(100):
                conn.execute("INSERT INTO test VALUES (?, ?)", (i, f"value_{i}"))
            conn.commit()
            conn.close()

            # Test without pool (create new connection each time)
            start = time.perf_counter()
            for _ in range(50):
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute("SELECT COUNT(*) FROM test")
                cursor.fetchone()
                conn.close()
            no_pool_time = time.perf_counter() - start

            # Test with pool (reuse connections)
            config = DatabaseConfig(sqlite_path=db_path, pool_size=5)
            pool = ConnectionPool(config)

            start = time.perf_counter()
            for _ in range(50):
                with pool.connection() as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM test")
                    cursor.fetchone()
            pool_time = time.perf_counter() - start

            pool.close()

            # Pool should be faster (or at least not significantly slower)
            print(f"\nNo pool: {no_pool_time:.4f}s, With pool: {pool_time:.4f}s")
            print(f"Speedup: {no_pool_time / pool_time:.2f}x")

            # Pool should provide some benefit (allow some margin for overhead)
            assert pool_time < no_pool_time * 1.5  # At most 50% slower

    def test_health_check_overhead(self):
        """Health checks should have minimal overhead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(
                sqlite_path=db_path,
                pool_size=3,
                health_check_interval=0  # Always check
            )
            pool = ConnectionPool(config)

            # Create test table
            with pool.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

            # Time queries with health checks
            start = time.perf_counter()
            for _ in range(100):
                with pool.connection() as conn:
                    conn.execute("SELECT 1")
            with_health_check_time = time.perf_counter() - start

            pool.close()

            # Recreate without frequent health checks
            config2 = DatabaseConfig(
                sqlite_path=db_path,
                pool_size=3,
                health_check_interval=10000  # Rarely check
            )
            pool2 = ConnectionPool(config2)

            start = time.perf_counter()
            for _ in range(100):
                with pool2.connection() as conn:
                    conn.execute("SELECT 1")
            without_health_check_time = time.perf_counter() - start

            pool2.close()

            print(f"\nWith health checks: {with_health_check_time:.4f}s")
            print(f"Without health checks: {without_health_check_time:.4f}s")
            print(f"Overhead: {(with_health_check_time / without_health_check_time - 1) * 100:.1f}%")

            # Health checks should add minimal overhead (< 50%)
            assert with_health_check_time < without_health_check_time * 1.5

    def test_concurrent_load_handling(self):
        """Pool should handle concurrent requests efficiently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(
                sqlite_path=db_path,
                pool_size=5,
                max_overflow=5
            )
            pool = ConnectionPool(config)

            # Create test table
            with pool.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
                for i in range(100):
                    conn.execute("INSERT INTO test VALUES (?, ?)", (i, f"value_{i}"))

            def query_worker(worker_id):
                """Worker that performs multiple queries."""
                results = []
                for i in range(10):
                    with pool.connection() as conn:
                        cursor = conn.execute(
                            "SELECT value FROM test WHERE id = ?",
                            (worker_id * 10 + i,)
                        )
                        result = cursor.fetchone()
                        results.append(result)
                return results

            # Run concurrent workers
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(query_worker, i) for i in range(10)]
                results = [f.result() for f in as_completed(futures)]

            elapsed = time.perf_counter() - start

            # Verify all queries completed
            assert len(results) == 10

            stats = pool.get_stats()
            print(f"\nConcurrent load test:")
            print(f"  Time: {elapsed:.4f}s")
            print(f"  Total queries: {stats['total_queries']}")
            print(f"  Connections reused: {stats['connections_reused']}")
            print(f"  Pool utilization: {stats['utilization_pct']:.1f}%")

            # Should complete reasonably fast (< 5 seconds for 100 queries)
            assert elapsed < 5.0

            pool.close()

    def test_metrics_collection_overhead(self):
        """Metrics collection should have minimal overhead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(sqlite_path=db_path, pool_size=3)
            pool = ConnectionPool(config)

            with pool.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

            # Time queries without stats collection
            start = time.perf_counter()
            for _ in range(100):
                with pool.connection() as conn:
                    conn.execute("SELECT 1")
            query_time = time.perf_counter() - start

            # Time with frequent stats collection
            start = time.perf_counter()
            for _ in range(100):
                with pool.connection() as conn:
                    conn.execute("SELECT 1")
                pool.get_stats()  # Collect stats each time
            query_with_stats_time = time.perf_counter() - start

            print(f"\nQueries only: {query_time:.4f}s")
            print(f"Queries + stats: {query_with_stats_time:.4f}s")
            print(f"Stats overhead: {(query_with_stats_time / query_time - 1) * 100:.1f}%")

            # Stats collection should be negligible (< 20% overhead)
            assert query_with_stats_time < query_time * 1.2

            pool.close()

    def test_connection_recycling_performance(self):
        """Connection recycling should not significantly impact performance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Pool that recycles frequently
            config = DatabaseConfig(
                sqlite_path=db_path,
                pool_size=3,
                pool_recycle=1  # Recycle after 1 second
            )
            pool = ConnectionPool(config)

            with pool.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

            # Wait for connections to age
            time.sleep(1.1)

            # Execute queries (will trigger recycling)
            start = time.perf_counter()
            for _ in range(50):
                with pool.connection() as conn:
                    conn.execute("SELECT 1")
            elapsed = time.perf_counter() - start

            stats = pool.get_stats()
            print(f"\nRecycling test:")
            print(f"  Time: {elapsed:.4f}s")
            print(f"  Connections recycled: {stats['connections_recycled']}")

            # Should recycle connections
            assert stats["connections_recycled"] > 0

            # Should still complete quickly (< 2 seconds)
            assert elapsed < 2.0

            pool.close()

    def test_overflow_connection_overhead(self):
        """Overflow connections should have minimal overhead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(
                sqlite_path=db_path,
                pool_size=2,
                max_overflow=5
            )
            pool = ConnectionPool(config)

            with pool.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")

            def concurrent_query():
                with pool.connection() as conn:
                    conn.execute("SELECT 1")
                    time.sleep(0.01)  # Small delay to force overflow

            # Force overflow by concurrent requests
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(concurrent_query) for _ in range(20)]
                for f in as_completed(futures):
                    f.result()
            elapsed = time.perf_counter() - start

            stats = pool.get_stats()
            print(f"\nOverflow test:")
            print(f"  Time: {elapsed:.4f}s")
            print(f"  Max overflow used: {stats['overflow_in_use']}")

            # Should complete reasonably (< 1 second)
            assert elapsed < 1.0

            pool.close()


class TestDatabasePerformance:
    """Performance tests for Database high-level API."""

    def test_bulk_insert_performance(self):
        """Bulk inserts should be efficient."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(sqlite_path=db_path, pool_size=1)
            db = Database(config)

            with db.connection() as conn:
                conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")

            # Insert 1000 records
            start = time.perf_counter()
            for i in range(1000):
                db.insert("test", {"value": f"value_{i}"})
            elapsed = time.perf_counter() - start

            print(f"\nBulk insert test:")
            print(f"  1000 inserts: {elapsed:.4f}s")
            print(f"  Rate: {1000 / elapsed:.0f} inserts/sec")

            # Should insert at reasonable rate (> 100/sec)
            assert 1000 / elapsed > 100

            db.disconnect()

    def test_query_performance_with_pool(self):
        """Pool should enable efficient querying."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            config = DatabaseConfig(sqlite_path=db_path, pool_size=5)
            db = Database(config)

            # Setup test data
            with db.connection() as conn:
                conn.executescript("""
                    CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT);
                    CREATE INDEX idx_value ON test(value);
                """)
                for i in range(1000):
                    conn.execute("INSERT INTO test VALUES (?, ?)", (i, f"value_{i % 10}"))

            # Run queries
            start = time.perf_counter()
            for i in range(100):
                results = db.fetchall(
                    "SELECT * FROM test WHERE value = ?",
                    (f"value_{i % 10}",)
                )
            elapsed = time.perf_counter() - start

            stats = db.get_stats()
            print(f"\nQuery performance:")
            print(f"  100 queries: {elapsed:.4f}s")
            print(f"  Rate: {100 / elapsed:.0f} queries/sec")
            print(f"  Pool utilization: {stats['utilization_pct']:.1f}%")

            # Should query efficiently (> 50 queries/sec)
            assert 100 / elapsed > 50

            db.disconnect()
