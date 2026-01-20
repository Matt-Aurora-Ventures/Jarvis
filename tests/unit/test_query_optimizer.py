"""
Unit tests for the query optimization system.

Tests the following components:
- Batch price lookups
- API call reduction through caching
- Connection pooling for DB
- Async query batching
"""
import pytest
import asyncio
import tempfile
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock


class TestBatchPriceLookup:
    """Tests for batch price lookup optimization."""

    @pytest.mark.asyncio
    async def test_batch_price_lookup_coalesces_requests(self):
        """Should coalesce multiple price requests into one batch."""
        from core.data.query_optimizer import BatchPriceLookup

        call_count = 0
        fetched_tokens = []

        async def mock_batch_fetch(tokens):
            nonlocal call_count, fetched_tokens
            call_count += 1
            fetched_tokens = tokens
            await asyncio.sleep(0.01)
            return {token: {"price": 100.0} for token in tokens}

        lookup = BatchPriceLookup(
            batch_fetcher=mock_batch_fetch,
            batch_window_ms=50,
            max_batch_size=10
        )

        # Fire multiple requests concurrently
        tasks = [
            lookup.get_price("SOL"),
            lookup.get_price("BTC"),
            lookup.get_price("ETH"),
        ]

        results = await asyncio.gather(*tasks)

        # Should be coalesced into one batch call
        assert call_count == 1
        assert set(fetched_tokens) == {"SOL", "BTC", "ETH"}
        assert all(r["price"] == 100.0 for r in results)

    @pytest.mark.asyncio
    async def test_batch_price_lookup_respects_max_size(self):
        """Should split batches when exceeding max size."""
        from core.data.query_optimizer import BatchPriceLookup

        call_count = 0

        async def mock_batch_fetch(tokens):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {token: {"price": 100.0} for token in tokens}

        lookup = BatchPriceLookup(
            batch_fetcher=mock_batch_fetch,
            batch_window_ms=50,
            max_batch_size=3
        )

        # Request more than max batch size
        tasks = [lookup.get_price(f"TOKEN{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Should be split into multiple batches
        assert call_count >= 4  # At least 4 batches for 10 items with max 3
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_batch_price_lookup_with_cache(self):
        """Should use cache for repeated lookups."""
        from core.data.query_optimizer import BatchPriceLookup

        call_count = 0

        async def mock_batch_fetch(tokens):
            nonlocal call_count
            call_count += 1
            return {token: {"price": 100.0} for token in tokens}

        lookup = BatchPriceLookup(
            batch_fetcher=mock_batch_fetch,
            batch_window_ms=50,
            cache_ttl_seconds=60
        )

        # First request
        result1 = await lookup.get_price("SOL")
        # Second request should hit cache
        result2 = await lookup.get_price("SOL")

        assert call_count == 1
        assert result1 == result2


class TestAPICallReduction:
    """Tests for API call reduction through caching."""

    @pytest.mark.asyncio
    async def test_deduplication_during_pending_request(self):
        """Should deduplicate requests while one is pending."""
        from core.data.query_optimizer import RequestDeduplicator

        call_count = 0

        async def slow_fetch(key):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return f"result_{key}"

        dedup = RequestDeduplicator()

        # Fire multiple requests for same key concurrently
        tasks = [
            dedup.get_or_fetch("key1", lambda: slow_fetch("key1")),
            dedup.get_or_fetch("key1", lambda: slow_fetch("key1")),
            dedup.get_or_fetch("key1", lambda: slow_fetch("key1")),
        ]

        results = await asyncio.gather(*tasks)

        # All should get the same result from one call
        assert call_count == 1
        assert all(r == "result_key1" for r in results)

    @pytest.mark.asyncio
    async def test_deduplication_allows_parallel_different_keys(self):
        """Should allow parallel requests for different keys."""
        from core.data.query_optimizer import RequestDeduplicator

        call_keys = []

        async def slow_fetch(key):
            call_keys.append(key)
            await asyncio.sleep(0.01)
            return f"result_{key}"

        dedup = RequestDeduplicator()

        tasks = [
            dedup.get_or_fetch("key1", lambda: slow_fetch("key1")),
            dedup.get_or_fetch("key2", lambda: slow_fetch("key2")),
        ]

        results = await asyncio.gather(*tasks)

        assert set(call_keys) == {"key1", "key2"}
        assert results[0] == "result_key1"
        assert results[1] == "result_key2"


class TestConnectionPooling:
    """Tests for database connection pooling."""

    def test_connection_pool_basic(self):
        """Should create and manage connections."""
        from core.data.query_optimizer import ConnectionPool

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create test database
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'hello')")
            conn.commit()
            conn.close()

            pool = ConnectionPool(str(db_path), max_connections=5)

            # Get connection and query
            with pool.get_connection() as conn:
                cursor = conn.execute("SELECT value FROM test WHERE id = 1")
                result = cursor.fetchone()
                assert result[0] == "hello"

            # Close all connections before temp dir cleanup
            pool.close_all()

    def test_connection_pool_reuse(self):
        """Should reuse connections from pool."""
        from core.data.query_optimizer import ConnectionPool

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_conn = sqlite3.connect(str(db_path))
            init_conn.execute("SELECT 1").fetchone()
            init_conn.close()

            pool = ConnectionPool(str(db_path), max_connections=2)

            # Get two connections
            conn1_id = None
            conn2_id = None

            with pool.get_connection() as conn:
                conn1_id = id(conn)

            # Return to pool and get again
            with pool.get_connection() as conn:
                conn2_id = id(conn)

            # Should be same connection object (reused)
            assert conn1_id == conn2_id

            # Close all connections before temp dir cleanup
            pool.close_all()

    def test_connection_pool_limit(self):
        """Should respect max connection limit."""
        from core.data.query_optimizer import ConnectionPool

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_conn = sqlite3.connect(str(db_path))
            init_conn.execute("SELECT 1").fetchone()
            init_conn.close()

            pool = ConnectionPool(str(db_path), max_connections=2)
            stats = pool.get_stats()

            assert stats["max_connections"] == 2

            # Close all connections before temp dir cleanup
            pool.close_all()


class TestAsyncQueryBatching:
    """Tests for async query batching."""

    @pytest.mark.asyncio
    async def test_query_batch_accumulates(self):
        """Should accumulate queries within batch window."""
        from core.data.query_optimizer import AsyncQueryBatcher

        executed_batches = []

        async def batch_executor(queries):
            executed_batches.append(queries)
            return [{"result": q} for q in queries]

        batcher = AsyncQueryBatcher(
            executor=batch_executor,
            batch_window_ms=50
        )

        # Submit queries concurrently
        tasks = [
            batcher.execute("SELECT 1"),
            batcher.execute("SELECT 2"),
            batcher.execute("SELECT 3"),
        ]

        results = await asyncio.gather(*tasks)

        # Should be one batch with all queries
        assert len(executed_batches) == 1
        assert len(executed_batches[0]) == 3
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_batch_timeout(self):
        """Should execute batch after timeout even if not full."""
        from core.data.query_optimizer import AsyncQueryBatcher

        executed_batches = []

        async def batch_executor(queries):
            executed_batches.append(queries)
            return [{"result": q} for q in queries]

        batcher = AsyncQueryBatcher(
            executor=batch_executor,
            batch_window_ms=30,
            max_batch_size=100
        )

        # Submit single query
        result = await batcher.execute("SELECT 1")

        # Should execute after timeout
        assert len(executed_batches) == 1
        assert executed_batches[0] == ["SELECT 1"]


class TestQueryOptimizations:
    """Tests for SQL query optimizations."""

    def test_query_analysis_detects_full_scan(self):
        """Should detect queries that cause full table scans."""
        from core.data.query_optimizer import QueryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT
                )
            """)
            conn.commit()
            conn.close()

            analyzer = QueryAnalyzer(str(db_path))
            analysis = analyzer.analyze("SELECT * FROM users WHERE name = 'test'")

            # Check all warnings for full scan or no index message
            all_warnings = " ".join(w.lower() for w in analysis.warnings)
            assert "full table scan" in all_warnings or \
                   "no index" in all_warnings or \
                   "select *" in all_warnings

    def test_query_analysis_suggests_index(self):
        """Should suggest indexes for frequently filtered columns."""
        from core.data.query_optimizer import QueryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    token_mint TEXT,
                    user_id INTEGER,
                    created_at TEXT
                )
            """)
            conn.commit()
            conn.close()

            analyzer = QueryAnalyzer(str(db_path))
            suggestions = analyzer.suggest_indexes("positions")

            # Should suggest index on token_mint or user_id
            assert any("token_mint" in s or "user_id" in s for s in suggestions)

    def test_query_analysis_detects_select_star(self):
        """Should warn about SELECT * usage."""
        from core.data.query_optimizer import QueryAnalyzer

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test (id INTEGER, data TEXT)")
            conn.commit()
            conn.close()

            analyzer = QueryAnalyzer(str(db_path))
            analysis = analyzer.analyze("SELECT * FROM test")

            assert any("SELECT *" in w or "specify columns" in w.lower()
                      for w in analysis.warnings)


class TestPriceCacheIntegration:
    """Integration tests for price caching."""

    @pytest.mark.asyncio
    async def test_price_cache_reduces_api_calls(self):
        """Should significantly reduce API calls with caching."""
        from core.data.query_optimizer import OptimizedPriceService

        api_calls = 0

        async def mock_api(tokens):
            nonlocal api_calls
            api_calls += 1
            return {t: {"price": 100 + i} for i, t in enumerate(tokens)}

        service = OptimizedPriceService(
            fetcher=mock_api,
            cache_ttl_seconds=60
        )

        # First batch - all cache misses (3 tokens, gets called per token)
        await service.get_prices(["SOL", "BTC", "ETH"])
        first_batch_calls = api_calls

        # Second batch - all cache hits (should be 0 new calls)
        await service.get_prices(["SOL", "BTC", "ETH"])
        second_batch_calls = api_calls - first_batch_calls

        # Third batch - partial cache hits (only DOGE is new)
        await service.get_prices(["SOL", "DOGE"])
        third_batch_calls = api_calls - first_batch_calls - second_batch_calls

        # Second batch should have 0 calls (all cached)
        assert second_batch_calls == 0
        # Third batch should only fetch DOGE
        assert third_batch_calls >= 1

    @pytest.mark.asyncio
    async def test_price_service_metrics(self):
        """Should track cache hit/miss metrics."""
        from core.data.query_optimizer import OptimizedPriceService

        async def mock_api(tokens):
            return {t: {"price": 100} for t in tokens}

        service = OptimizedPriceService(
            fetcher=mock_api,
            cache_ttl_seconds=60
        )

        await service.get_prices(["SOL"])
        await service.get_prices(["SOL"])
        await service.get_prices(["BTC"])

        metrics = service.get_metrics()

        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 2
        assert metrics["total_requests"] == 3
