"""
Performance Benchmark Tests for JARVIS Critical Paths

Benchmarks for:
- API endpoint response times
- Cache hit/miss performance
- Database query execution time
- WebSocket message throughput
- Market data processing latency

Run with:
    uv run pytest tests/performance/test_benchmarks.py -v --tb=short
    uv run pytest tests/performance/test_benchmarks.py -v -k "cache" --tb=short

For detailed timings:
    uv run pytest tests/performance/test_benchmarks.py -v -s
"""

import asyncio
import json
import statistics
import time
import tempfile
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# BENCHMARK INFRASTRUCTURE
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    times_ms: List[float]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0

    @property
    def median_ms(self) -> float:
        return statistics.median(self.times_ms) if self.times_ms else 0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0

    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0

    @property
    def p95_ms(self) -> float:
        if not self.times_ms:
            return 0
        sorted_times = sorted(self.times_ms)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99_ms(self) -> float:
        if not self.times_ms:
            return 0
        sorted_times = sorted(self.times_ms)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def stddev_ms(self) -> float:
        if len(self.times_ms) < 2:
            return 0
        return statistics.stdev(self.times_ms)

    @property
    def throughput_ops(self) -> float:
        """Operations per second."""
        if self.mean_ms == 0:
            return 0
        return 1000 / self.mean_ms

    def summary(self) -> str:
        return (
            f"{self.name}: "
            f"mean={self.mean_ms:.3f}ms, "
            f"median={self.median_ms:.3f}ms, "
            f"p95={self.p95_ms:.3f}ms, "
            f"min={self.min_ms:.3f}ms, "
            f"max={self.max_ms:.3f}ms, "
            f"throughput={self.throughput_ops:.0f} ops/s"
        )


class Benchmark:
    """Benchmark runner for sync and async functions."""

    def __init__(self, iterations: int = 100, warmup: int = 10):
        self.iterations = iterations
        self.warmup = warmup

    def run(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
    ) -> BenchmarkResult:
        """Run a synchronous benchmark."""
        kwargs = kwargs or {}
        times_ms = []

        # Warmup
        for _ in range(self.warmup):
            func(*args, **kwargs)

        # Benchmark
        for _ in range(self.iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed)

        return BenchmarkResult(name=name, iterations=self.iterations, times_ms=times_ms)

    async def run_async(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
    ) -> BenchmarkResult:
        """Run an async benchmark."""
        kwargs = kwargs or {}
        times_ms = []

        # Warmup
        for _ in range(self.warmup):
            await func(*args, **kwargs)

        # Benchmark
        for _ in range(self.iterations):
            start = time.perf_counter()
            await func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed)

        return BenchmarkResult(name=name, iterations=self.iterations, times_ms=times_ms)


# =============================================================================
# PERFORMANCE BASELINES (thresholds in milliseconds)
# =============================================================================

PERFORMANCE_BASELINES = {
    # Cache operations should be very fast (< 1ms)
    "cache_get": 1.0,
    "cache_set": 1.0,
    "cache_hit": 0.5,
    "cache_miss": 0.5,

    # Database operations (with mock)
    "db_connection_acquire": 5.0,
    "db_query_simple": 10.0,
    "db_query_batch": 50.0,

    # WebSocket operations
    "ws_message_serialize": 1.0,
    "ws_message_compress": 5.0,
    "ws_batch_create": 2.0,

    # Market data processing
    "market_data_parse": 5.0,
    "price_lookup_cached": 1.0,
    "price_batch_lookup": 10.0,

    # API response
    "api_json_serialize": 2.0,
    "api_json_deserialize": 2.0,
}


# =============================================================================
# CACHE PERFORMANCE BENCHMARKS
# =============================================================================

class TestAPICachePerformance:
    """Benchmark API cache operations."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=1000, warmup=100)

    def test_cache_get_performance(self, bench):
        """Cache get should be < 1ms."""
        from core.cache.api_cache import APICache

        cache = APICache()
        # Pre-populate cache
        for i in range(100):
            cache.set("jupiter", f"key_{i}", {"value": i, "data": "x" * 100})

        result = bench.run(
            "cache_get",
            cache.get,
            args=("jupiter", "key_50")
        )

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["cache_get"], \
            f"Cache get too slow: {result.mean_ms:.3f}ms > {PERFORMANCE_BASELINES['cache_get']}ms"

    def test_cache_set_performance(self, bench):
        """Cache set should be < 1ms."""
        from core.cache.api_cache import APICache

        cache = APICache()
        counter = [0]

        def cache_set():
            counter[0] += 1
            cache.set("jupiter", f"key_{counter[0]}", {"value": counter[0]})

        result = bench.run("cache_set", cache_set)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["cache_set"], \
            f"Cache set too slow: {result.mean_ms:.3f}ms > {PERFORMANCE_BASELINES['cache_set']}ms"

    def test_cache_hit_vs_miss_performance(self, bench):
        """Compare cache hit vs miss performance."""
        from core.cache.api_cache import APICache

        cache = APICache()
        cache.set("jupiter", "existing_key", {"value": 1})

        # Benchmark hits
        hit_result = bench.run(
            "cache_hit",
            cache.get,
            args=("jupiter", "existing_key")
        )

        # Benchmark misses
        miss_counter = [0]
        def cache_miss():
            miss_counter[0] += 1
            return cache.get("jupiter", f"missing_key_{miss_counter[0]}")

        miss_result = bench.run("cache_miss", cache_miss)

        print(f"\nCache Hit: {hit_result.summary()}")
        print(f"Cache Miss: {miss_result.summary()}")

        assert hit_result.mean_ms < PERFORMANCE_BASELINES["cache_hit"]
        assert miss_result.mean_ms < PERFORMANCE_BASELINES["cache_miss"]

    def test_cache_stats_performance(self, bench):
        """Cache stats retrieval should be fast."""
        from core.cache.api_cache import APICache

        cache = APICache()
        # Populate cache with some data
        for i in range(50):
            cache.set("jupiter", f"key_{i}", {"value": i})
            cache.get("jupiter", f"key_{i}")

        result = bench.run("cache_stats", cache.get_stats)

        print(f"\n{result.summary()}")
        # Stats should complete in < 5ms even with data
        assert result.mean_ms < 5.0

    def test_cache_invalidation_performance(self, bench):
        """Cache invalidation should be fast."""
        from core.cache.api_cache import APICache

        cache = APICache()

        def setup_and_invalidate():
            # Setup
            for i in range(10):
                cache.set("jupiter", f"key_{i}", {"value": i})
            # Invalidate
            cache.invalidate_api("jupiter")

        result = bench.run("cache_invalidation", setup_and_invalidate)

        print(f"\n{result.summary()}")
        assert result.mean_ms < 2.0


class TestMemoryCachePerformance:
    """Benchmark LRU memory cache operations."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=1000, warmup=100)

    def test_lru_cache_get_set(self, bench):
        """LRU cache operations should be very fast."""
        from core.cache.memory_cache import LRUCache

        cache = LRUCache(maxsize=1000, ttl=60)

        # Pre-populate
        for i in range(500):
            cache.set(f"key_{i}", {"value": i})

        result = bench.run(
            "lru_cache_get",
            cache.get,
            args=("key_250",)
        )

        print(f"\n{result.summary()}")
        assert result.mean_ms < 0.5  # Should be very fast

    def test_lru_cache_eviction_performance(self, bench):
        """LRU eviction should not significantly impact performance."""
        from core.cache.memory_cache import LRUCache

        cache = LRUCache(maxsize=100, ttl=60)
        counter = [0]

        def insert_with_eviction():
            counter[0] += 1
            cache.set(f"key_{counter[0]}", {"value": counter[0]})

        # This will trigger evictions after 100 inserts
        result = bench.run("lru_eviction", insert_with_eviction)

        print(f"\n{result.summary()}")
        assert result.mean_ms < 1.0


# =============================================================================
# DATABASE QUERY PERFORMANCE BENCHMARKS
# =============================================================================

class TestDatabasePerformance:
    """Benchmark database operations using the query optimizer."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=100, warmup=10)

    @pytest.fixture
    def db_pool(self, tmp_path):
        """Create a connection pool with a temporary database."""
        from core.data.query_optimizer import ConnectionPool

        db_path = tmp_path / "test.db"
        pool = ConnectionPool(str(db_path), max_connections=5)

        # Initialize schema
        with pool.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY,
                    token_mint TEXT NOT NULL,
                    amount REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_mint)")

            # Insert test data
            for i in range(1000):
                conn.execute(
                    "INSERT INTO positions (token_mint, amount, entry_price, created_at) VALUES (?, ?, ?, ?)",
                    (f"TOKEN{i % 50}", float(i * 100), float(i * 0.01), datetime.now().isoformat())
                )
            conn.commit()

        yield pool
        pool.close_all()

    def test_connection_pool_acquire_release(self, bench, db_pool):
        """Connection pool acquire/release should be fast."""
        def acquire_release():
            with db_pool.get_connection() as conn:
                pass

        result = bench.run("db_connection_acquire", acquire_release)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["db_connection_acquire"]

    def test_simple_query_performance(self, bench, db_pool):
        """Simple SELECT query should be fast."""
        def simple_query():
            with db_pool.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM positions WHERE token_mint = ? LIMIT 10",
                    ("TOKEN0",)
                )
                return cursor.fetchall()

        result = bench.run("db_query_simple", simple_query)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["db_query_simple"]

    def test_batch_query_performance(self, bench, db_pool):
        """Batch query should complete in reasonable time."""
        def batch_query():
            results = []
            with db_pool.get_connection() as conn:
                for i in range(10):
                    cursor = conn.execute(
                        "SELECT * FROM positions WHERE token_mint = ? LIMIT 5",
                        (f"TOKEN{i}",)
                    )
                    results.extend(cursor.fetchall())
            return results

        result = bench.run("db_query_batch", batch_query)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["db_query_batch"]

    def test_connection_pool_concurrent_access(self, db_pool):
        """Test connection pool under concurrent access."""
        results = []
        errors = []
        lock = threading.Lock()

        def concurrent_query(thread_id):
            try:
                start = time.perf_counter()
                with db_pool.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM positions WHERE token_mint = ?",
                        (f"TOKEN{thread_id % 50}",)
                    )
                    cursor.fetchone()
                elapsed = (time.perf_counter() - start) * 1000
                with lock:
                    results.append(elapsed)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Run concurrent queries
        threads = []
        for i in range(20):
            t = threading.Thread(target=concurrent_query, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        assert len(results) == 20

        avg_time = statistics.mean(results)
        print(f"\nConcurrent access: mean={avg_time:.3f}ms, max={max(results):.3f}ms")
        assert avg_time < 50.0  # Should complete within 50ms on average


# =============================================================================
# WEBSOCKET MESSAGE THROUGHPUT BENCHMARKS
# =============================================================================

class TestWebSocketPerformance:
    """Benchmark WebSocket operations."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=1000, warmup=100)

    def test_message_serialization(self, bench):
        """JSON message serialization should be fast."""
        message = {
            "type": "price.updated",
            "data": {
                "token": "SOL",
                "price": 150.25,
                "change_24h": 5.5,
                "volume": 1000000000,
                "timestamp": datetime.now().isoformat()
            },
            "channel": "prices",
            "timestamp": datetime.now().isoformat()
        }

        def serialize():
            return json.dumps(message)

        result = bench.run("ws_message_serialize", serialize)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["ws_message_serialize"]

    def test_message_compression(self, bench):
        """Message compression should be reasonably fast."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer(compression_threshold=100)

        # Create a message larger than compression threshold
        large_message = json.dumps({
            "type": "batch",
            "data": [{"id": i, "value": "x" * 50} for i in range(10)]
        }).encode()

        def compress():
            return optimizer.compress(large_message)

        result = bench.run("ws_message_compress", compress)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["ws_message_compress"]

    def test_batch_creation_performance(self, bench):
        """Batch message creation should be fast."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer(batch_size=10, batch_delay_ms=50)

        def create_batch():
            for i in range(10):
                result = optimizer.add_to_batch("prices", {
                    "type": "price",
                    "token": f"TOKEN{i}",
                    "price": i * 100
                })
            return result

        result = bench.run("ws_batch_create", create_batch)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["ws_batch_create"]

    def test_deduplication_performance(self, bench):
        """Message deduplication should be fast."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()
        counter = [0]

        def check_duplicate():
            counter[0] += 1
            # Alternate between new and duplicate
            msg_id = f"msg_{counter[0] % 50}"
            return optimizer.is_duplicate(msg_id)

        result = bench.run("ws_deduplication", check_duplicate)

        print(f"\n{result.summary()}")
        assert result.mean_ms < 0.5

    def test_subscription_management_performance(self, bench):
        """Subscription management should be fast."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()

        # Pre-populate subscriptions
        for i in range(100):
            for j in range(10):
                optimizer.subscribe(f"client_{i}", f"channel_{j}")

        def get_subscribers():
            return optimizer.get_subscribers("channel_5")

        result = bench.run("ws_get_subscribers", get_subscribers)

        print(f"\n{result.summary()}")
        assert result.mean_ms < 0.5


# =============================================================================
# MARKET DATA PROCESSING BENCHMARKS
# =============================================================================

class TestMarketDataPerformance:
    """Benchmark market data processing."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=500, warmup=50)

    def test_price_data_parsing(self, bench):
        """Price data parsing should be fast."""
        raw_data = json.dumps({
            "symbol": "SOLUSDT",
            "lastPrice": "150.25",
            "priceChangePercent": "5.5",
            "prevClosePrice": "142.50",
            "volume": "1000000000",
            "quoteVolume": "150000000000"
        })

        def parse_price():
            data = json.loads(raw_data)
            return {
                "price": float(data["lastPrice"]),
                "change_pct": float(data["priceChangePercent"]),
                "volume": float(data["volume"])
            }

        result = bench.run("market_data_parse", parse_price)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["market_data_parse"]

    @pytest.mark.asyncio
    async def test_batch_price_lookup_sequential(self, bench):
        """Sequential batch price lookups should use cache effectively."""
        from core.data.query_optimizer import BatchPriceLookup

        call_count = 0

        # Mock fetcher that tracks calls
        async def mock_fetcher(tokens: List[str]) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {token: {"price": 100.0, "change": 5.0} for token in tokens}

        lookup = BatchPriceLookup(
            batch_fetcher=mock_fetcher,
            batch_window_ms=5,
            max_batch_size=50,
            cache_ttl_seconds=60
        )

        # Sequential lookups - first one fetches, rest come from cache
        times_ms = []
        for i in range(10):
            start = time.perf_counter()
            # Use same token to test cache hit performance
            result = await lookup.get_price("SOL")
            elapsed = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed)

        avg_time = statistics.mean(times_ms)
        print(f"\nSequential price lookup: mean={avg_time:.3f}ms, calls={call_count}")

        # Should only call fetcher once (rest from cache)
        assert call_count == 1, f"Expected 1 fetch call but got {call_count}"
        # Average should be fast since most are cache hits
        assert avg_time < 10.0

    @pytest.mark.asyncio
    async def test_cached_price_lookup_performance(self, bench):
        """Cached price lookup should be very fast."""
        from core.data.query_optimizer import BatchPriceLookup

        async def mock_fetcher(tokens: List[str]) -> Dict[str, Any]:
            return {token: {"price": 100.0} for token in tokens}

        lookup = BatchPriceLookup(
            batch_fetcher=mock_fetcher,
            batch_window_ms=10,
            cache_ttl_seconds=60
        )

        # Prime the cache
        await lookup.get_price("SOL")

        async def get_cached_price():
            return await lookup.get_price("SOL")

        result = await bench.run_async("price_lookup_cached", get_cached_price)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["price_lookup_cached"]

    @pytest.mark.asyncio
    async def test_request_deduplication_correctness(self):
        """Test that concurrent requests for the same key are deduplicated correctly."""
        from core.data.query_optimizer import RequestDeduplicator

        dedup = RequestDeduplicator()
        call_count = 0

        async def slow_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)  # 20ms simulated work
            return {"result": "data", "call_id": call_count}

        # Test 1: All requests for the SAME key should share one fetch
        start = time.perf_counter()

        # Launch 20 concurrent requests for THE SAME key
        tasks = [dedup.get_or_fetch("same_key", slow_fetch) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        elapsed = (time.perf_counter() - start) * 1000

        print(f"\nSingle-key deduplication: {call_count} call(s) for 20 requests")
        print(f"Time: {elapsed:.1f}ms (expected ~20ms for single fetch)")

        # Critical assertion: Only 1 actual call should be made
        assert call_count == 1, f"Expected 1 call but got {call_count} - deduplication not working"

        # All results should be the same object (shared)
        first_result = results[0]
        for r in results[1:]:
            assert r == first_result, "Results should be shared across deduplicated requests"

        # Time should be close to single fetch time (20ms + overhead), not 20 * 20ms
        assert elapsed < 100, f"Too slow: {elapsed:.1f}ms - requests not sharing result"

    @pytest.mark.asyncio
    async def test_request_deduplication_multiple_keys(self):
        """Test deduplication behavior with multiple distinct keys."""
        from core.data.query_optimizer import RequestDeduplicator

        dedup = RequestDeduplicator()
        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # 10ms
            return {"call_id": call_count}

        # 5 unique keys, each with 10 concurrent requests = 50 total requests
        # Should result in 5 actual fetches (one per unique key)
        tasks = [
            dedup.get_or_fetch(f"key_{i // 10}", fetch)
            for i in range(50)
        ]
        results = await asyncio.gather(*tasks)

        print(f"\nMulti-key deduplication: {call_count} calls for 50 requests across 5 keys")

        # Should have exactly 5 actual fetch calls (one per unique key)
        assert call_count == 5, f"Expected 5 calls but got {call_count}"


# =============================================================================
# API RESPONSE PERFORMANCE BENCHMARKS
# =============================================================================

class TestAPIResponsePerformance:
    """Benchmark API response handling."""

    @pytest.fixture
    def bench(self):
        return Benchmark(iterations=1000, warmup=100)

    def test_json_serialization_performance(self, bench):
        """JSON serialization should be fast."""
        response_data = {
            "status": "success",
            "data": {
                "positions": [
                    {"token": f"TOKEN{i}", "amount": 1000, "value": 10000}
                    for i in range(20)
                ],
                "total_value": 200000,
                "timestamp": datetime.now().isoformat()
            },
            "meta": {
                "page": 1,
                "per_page": 20,
                "total": 100
            }
        }

        def serialize():
            return json.dumps(response_data)

        result = bench.run("api_json_serialize", serialize)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["api_json_serialize"]

    def test_json_deserialization_performance(self, bench):
        """JSON deserialization should be fast."""
        json_str = json.dumps({
            "status": "success",
            "data": {
                "positions": [
                    {"token": f"TOKEN{i}", "amount": 1000, "value": 10000}
                    for i in range(20)
                ]
            }
        })

        def deserialize():
            return json.loads(json_str)

        result = bench.run("api_json_deserialize", deserialize)

        print(f"\n{result.summary()}")
        assert result.mean_ms < PERFORMANCE_BASELINES["api_json_deserialize"]

    def test_fast_json_performance(self, bench):
        """Fast JSON (orjson/msgspec) should be faster than stdlib."""
        from core.performance.fast_json import dumps, loads, HAS_ORJSON, HAS_MSGSPEC

        data = {
            "positions": [
                {"token": f"TOKEN{i}", "amount": 1000.0, "value": 10000.0}
                for i in range(20)
            ]
        }

        def fast_serialize():
            return dumps(data)

        def fast_deserialize():
            return loads(dumps(data))

        serialize_result = bench.run("fast_json_serialize", fast_serialize)
        deserialize_result = bench.run("fast_json_deserialize", fast_deserialize)

        backend = "orjson" if HAS_ORJSON else ("msgspec" if HAS_MSGSPEC else "stdlib")
        print(f"\nUsing: {backend}")
        print(f"Serialize: {serialize_result.summary()}")
        print(f"Deserialize: {deserialize_result.summary()}")

        # Fast JSON should be faster than stdlib
        if HAS_ORJSON or HAS_MSGSPEC:
            assert serialize_result.mean_ms < 1.0


# =============================================================================
# CONCURRENT PERFORMANCE BENCHMARKS
# =============================================================================

class TestConcurrentPerformance:
    """Benchmark concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Cache should handle concurrent access efficiently."""
        from core.cache.api_cache import APICache

        cache = APICache()
        results = []
        lock = asyncio.Lock()

        async def concurrent_operation(task_id):
            start = time.perf_counter()

            # Mixed read/write operations
            cache.set("jupiter", f"key_{task_id}", {"value": task_id})
            _ = cache.get("jupiter", f"key_{task_id % 10}")
            _ = cache.get_stats()

            elapsed = (time.perf_counter() - start) * 1000
            async with lock:
                results.append(elapsed)

        # Run 100 concurrent operations
        tasks = [concurrent_operation(i) for i in range(100)]
        await asyncio.gather(*tasks)

        avg_time = statistics.mean(results)
        p95_time = sorted(results)[int(len(results) * 0.95)]

        print(f"\nConcurrent cache access: mean={avg_time:.3f}ms, p95={p95_time:.3f}ms")
        assert avg_time < 5.0
        assert p95_time < 10.0

    @pytest.mark.asyncio
    async def test_concurrent_deduplication(self):
        """RequestDeduplicator should handle concurrent requests efficiently."""
        from core.data.query_optimizer import RequestDeduplicator

        dedup = RequestDeduplicator()
        results = []
        call_count = 0
        lock = asyncio.Lock()

        async def mock_fetch():
            nonlocal call_count
            async with lock:
                call_count += 1
            await asyncio.sleep(0.005)  # 5ms
            return {"data": "result"}

        start = time.perf_counter()

        # 50 concurrent requests for same key
        tasks = [dedup.get_or_fetch("shared_key", mock_fetch) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        elapsed = (time.perf_counter() - start) * 1000

        print(f"\n50 concurrent dedup requests: {elapsed:.1f}ms, actual fetches: {call_count}")

        # Should deduplicate to single call
        assert call_count == 1
        assert len(results) == 50
        assert elapsed < 100  # Should complete quickly


# =============================================================================
# THROUGHPUT BENCHMARKS
# =============================================================================

class TestThroughputBenchmarks:
    """Test throughput under sustained load."""

    @pytest.mark.asyncio
    async def test_cache_throughput(self):
        """Measure cache operations per second."""
        from core.cache.api_cache import APICache

        cache = APICache()

        # Pre-populate
        for i in range(100):
            cache.set("jupiter", f"key_{i}", {"value": i})

        operations = 0
        duration = 1.0  # 1 second test

        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            for i in range(100):
                cache.get("jupiter", f"key_{i % 100}")
                cache.set("jupiter", f"new_key_{operations}", {"value": operations})
                operations += 2

        elapsed = time.perf_counter() - start
        ops_per_second = operations / elapsed

        print(f"\nCache throughput: {ops_per_second:,.0f} ops/second")
        assert ops_per_second > 10000  # Should achieve at least 10K ops/sec

    @pytest.mark.asyncio
    async def test_websocket_message_throughput(self):
        """Measure WebSocket message processing throughput."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer(batch_size=10, batch_delay_ms=10)

        messages_processed = 0
        duration = 1.0

        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            for i in range(100):
                optimizer.add_to_batch("prices", {
                    "type": "price",
                    "token": f"TOKEN{i}",
                    "price": i * 100
                })
                messages_processed += 1

        elapsed = time.perf_counter() - start
        msgs_per_second = messages_processed / elapsed

        print(f"\nWebSocket message throughput: {msgs_per_second:,.0f} msgs/second")
        assert msgs_per_second > 50000  # Should achieve at least 50K msgs/sec


# =============================================================================
# BENCHMARK REPORT GENERATION
# =============================================================================

class TestBenchmarkReport:
    """Generate comprehensive benchmark report."""

    @pytest.mark.asyncio
    async def test_generate_benchmark_summary(self, tmp_path):
        """Generate a benchmark summary report."""
        from core.cache.api_cache import APICache
        from core.performance.websocket_optimizer import WebSocketOptimizer

        bench = Benchmark(iterations=100, warmup=10)
        results = []

        # Cache benchmarks
        cache = APICache()
        for i in range(50):
            cache.set("jupiter", f"key_{i}", {"value": i})

        results.append(bench.run("cache_get", cache.get, args=("jupiter", "key_25")))

        counter = [0]
        def cache_set():
            counter[0] += 1
            cache.set("jupiter", f"bench_key_{counter[0]}", {"value": counter[0]})
        results.append(bench.run("cache_set", cache_set))

        # WebSocket benchmarks
        optimizer = WebSocketOptimizer()
        results.append(bench.run(
            "ws_serialize",
            json.dumps,
            args=({"type": "test", "data": {"value": 123}},)
        ))

        # Generate report
        report_lines = [
            "# JARVIS Performance Benchmark Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Results Summary",
            "",
            "| Benchmark | Mean (ms) | P95 (ms) | Throughput (ops/s) | Status |",
            "|-----------|-----------|----------|-------------------|--------|",
        ]

        for r in results:
            baseline = PERFORMANCE_BASELINES.get(r.name.replace("bench_", ""), 10.0)
            status = "PASS" if r.mean_ms < baseline else "FAIL"
            report_lines.append(
                f"| {r.name} | {r.mean_ms:.3f} | {r.p95_ms:.3f} | {r.throughput_ops:.0f} | {status} |"
            )

        report_lines.extend([
            "",
            "## Detailed Results",
            ""
        ])

        for r in results:
            report_lines.append(f"### {r.name}")
            report_lines.append(f"- Iterations: {r.iterations}")
            report_lines.append(f"- Mean: {r.mean_ms:.3f}ms")
            report_lines.append(f"- Median: {r.median_ms:.3f}ms")
            report_lines.append(f"- P95: {r.p95_ms:.3f}ms")
            report_lines.append(f"- P99: {r.p99_ms:.3f}ms")
            report_lines.append(f"- Min: {r.min_ms:.3f}ms")
            report_lines.append(f"- Max: {r.max_ms:.3f}ms")
            report_lines.append(f"- Std Dev: {r.stddev_ms:.3f}ms")
            report_lines.append("")

        report = "\n".join(report_lines)

        # Write report
        report_path = tmp_path / "benchmark_report.md"
        report_path.write_text(report)

        print(f"\n{report}")
        print(f"\nReport written to: {report_path}")

        # All benchmarks should pass
        for r in results:
            baseline = PERFORMANCE_BASELINES.get(r.name, 10.0)
            assert r.mean_ms < baseline * 2, f"{r.name} exceeded baseline by more than 2x"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
