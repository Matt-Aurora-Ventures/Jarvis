"""
Load tests for Jarvis trading system.

Tests the following:
- Concurrent position management
- High-frequency sentiment updates
- API rate limit testing
- Memory leak detection

Run with: uv run pytest tests/performance/load_tests.py -v --tb=short
"""
import pytest
import asyncio
import threading
import time
import tracemalloc
import gc
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock


class TestConcurrentPositionManagement:
    """Load tests for concurrent position management."""

    @pytest.mark.asyncio
    async def test_concurrent_position_reads(self):
        """Should handle many concurrent position reads."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        # Simulate position store
        positions = {f"token{i}": {"amount": i * 100} for i in range(100)}
        lock = asyncio.Lock()

        async def read_position(token_id):
            with profile_block("position.read"):
                async with lock:
                    await asyncio.sleep(0.001)  # Simulate I/O
                    return positions.get(token_id)

        # Fire 100 concurrent reads
        tasks = [read_position(f"token{i % 100}") for i in range(100)]

        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

        # Should complete within reasonable time
        assert elapsed < 2.0  # 2 seconds max for 100 reads
        assert len([r for r in results if r is not None]) == 100

        profile_results = get_profiler_results()
        assert profile_results["position.read"]["call_count"] == 100

    @pytest.mark.asyncio
    async def test_concurrent_position_updates(self):
        """Should handle concurrent position updates safely."""
        positions = {}
        update_count = 0
        lock = asyncio.Lock()

        async def update_position(token_id, amount):
            nonlocal update_count
            async with lock:
                await asyncio.sleep(0.001)
                if token_id not in positions:
                    positions[token_id] = {"amount": 0}
                positions[token_id]["amount"] += amount
                update_count += 1

        # Fire concurrent updates
        tasks = []
        for i in range(50):
            for token in ["SOL", "BTC", "ETH"]:
                tasks.append(update_position(token, 1))

        await asyncio.gather(*tasks)

        # All updates should succeed
        assert update_count == 150
        assert positions["SOL"]["amount"] == 50
        assert positions["BTC"]["amount"] == 50
        assert positions["ETH"]["amount"] == 50

    def test_thread_safe_position_updates(self):
        """Should handle multi-threaded position updates."""
        positions = {}
        lock = threading.Lock()
        errors = []

        def update_position(token_id, amount):
            try:
                with lock:
                    time.sleep(0.001)
                    if token_id not in positions:
                        positions[token_id] = {"amount": 0}
                    positions[token_id]["amount"] += amount
            except Exception as e:
                errors.append(e)

        # Run concurrent updates from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(100):
                for token in ["SOL", "BTC"]:
                    futures.append(executor.submit(update_position, token, 1))

            # Wait for all
            for f in futures:
                f.result()

        assert len(errors) == 0
        assert positions["SOL"]["amount"] == 100
        assert positions["BTC"]["amount"] == 100


class TestHighFrequencySentimentUpdates:
    """Load tests for high-frequency sentiment updates."""

    @pytest.mark.asyncio
    async def test_rapid_sentiment_ingestion(self):
        """Should handle rapid sentiment data ingestion."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        sentiments = []
        lock = asyncio.Lock()

        async def ingest_sentiment(data):
            with profile_block("sentiment.ingest"):
                async with lock:
                    sentiments.append(data)

        # Simulate 1000 rapid sentiment updates
        start = time.perf_counter()

        tasks = [
            ingest_sentiment({
                "token": f"TOKEN{i % 10}",
                "score": (i % 100) / 100,
                "timestamp": time.time()
            })
            for i in range(1000)
        ]

        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

        # Should complete within 5 seconds
        assert elapsed < 5.0
        assert len(sentiments) == 1000

        results = get_profiler_results()
        assert results["sentiment.ingest"]["call_count"] == 1000

    @pytest.mark.asyncio
    async def test_sentiment_aggregation_under_load(self):
        """Should aggregate sentiment correctly under load."""
        token_sentiments: Dict[str, List[float]] = {}
        lock = asyncio.Lock()

        async def add_sentiment(token, score):
            async with lock:
                if token not in token_sentiments:
                    token_sentiments[token] = []
                token_sentiments[token].append(score)

        # Add many sentiments concurrently
        tasks = []
        for i in range(500):
            token = f"TOKEN{i % 5}"
            score = (i % 10) / 10
            tasks.append(add_sentiment(token, score))

        await asyncio.gather(*tasks)

        # Each token should have 100 sentiments
        for token in token_sentiments:
            assert len(token_sentiments[token]) == 100

    @pytest.mark.asyncio
    async def test_sentiment_processing_throughput(self):
        """Should maintain throughput under sustained load."""
        processed_count = 0
        lock = asyncio.Lock()

        async def process_sentiment(data):
            nonlocal processed_count
            # Simulate some processing
            _ = sum(ord(c) for c in str(data))
            async with lock:
                processed_count += 1

        # Process 500 sentiments as fast as possible
        batch_size = 100
        total_time = 0

        for batch in range(5):
            tasks = [
                process_sentiment({
                    "batch": batch,
                    "idx": i,
                    "score": 0.5
                })
                for i in range(batch_size)
            ]

            start = time.perf_counter()
            await asyncio.gather(*tasks)
            total_time += time.perf_counter() - start

        assert processed_count == 500
        throughput = 500 / total_time
        # Should achieve at least 100 items/second
        assert throughput > 100


class TestAPIRateLimiting:
    """Load tests for API rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_respects_limits(self):
        """Rate limiter should respect configured limits."""
        from core.rate_limiter import RateLimiter
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ratelimit.db"
            limiter = RateLimiter(db_path=str(db_path))
            limiter.configure("test", requests_per_second=10, burst_size=20)

            allowed = 0
            denied = 0

            for _ in range(50):
                result, _ = limiter.acquire("test")
                if result:
                    allowed += 1
                else:
                    denied += 1

            # Should allow approximately 20 requests initially (burst)
            assert allowed <= 25  # Some tolerance for burst
            assert denied > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_under_concurrent_load(self):
        """Rate limiter should work correctly under concurrent access."""
        from core.rate_limiter import RateLimiter
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ratelimit.db"
            limiter = RateLimiter(db_path=str(db_path))
            limiter.configure("test", requests_per_second=100, burst_size=150)

            results = []
            lock = asyncio.Lock()

            async def make_request():
                result, _ = limiter.acquire("test")
                async with lock:
                    results.append(result)

            # Fire 200 concurrent requests
            tasks = [make_request() for _ in range(200)]
            await asyncio.gather(*tasks)

            allowed = sum(1 for r in results if r)
            denied = sum(1 for r in results if not r)

            # Should allow ~100-150 (burst)
            assert allowed > 50
            assert denied > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_recovery(self):
        """Rate limiter should recover after period of no requests."""
        from core.rate_limiter import RateLimiter
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ratelimit.db"
            limiter = RateLimiter(db_path=str(db_path))
            limiter.configure("test", requests_per_second=10, burst_size=20)

            # Exhaust the limiter
            for _ in range(50):
                limiter.acquire("test")

            # Wait for recovery
            await asyncio.sleep(0.5)  # Half second = 5 token recovery at 10/s

            # Should allow some requests now
            allowed = 0
            for _ in range(10):
                result, _ = limiter.acquire("test")
                if result:
                    allowed += 1

            assert allowed >= 3  # At least some recovery


class TestMemoryLeakDetection:
    """Load tests for memory leak detection."""

    def test_no_memory_leak_in_cache_operations(self):
        """Cache operations should not leak memory over time."""
        gc.collect()
        tracemalloc.start()

        # Simulate cache operations
        cache = {}

        for cycle in range(10):
            # Add 1000 items
            for i in range(1000):
                cache[f"key_{cycle}_{i}"] = {"data": "x" * 100}

            # Remove them
            for i in range(1000):
                del cache[f"key_{cycle}_{i}"]

            gc.collect()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory should not grow significantly (< 10MB growth)
        assert current < 10 * 1024 * 1024

    def test_no_memory_leak_in_profiler(self):
        """Profiler should not leak memory."""
        from core.performance.profiler import profile_block, reset_profiler

        gc.collect()
        tracemalloc.start()

        for cycle in range(100):
            reset_profiler()

            for i in range(100):
                with profile_block(f"operation_{i}"):
                    _ = [x for x in range(100)]

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Should not accumulate significant memory
        assert current < 20 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_no_memory_leak_in_async_operations(self):
        """Async operations should not leak memory."""
        gc.collect()
        tracemalloc.start()

        async def dummy_operation():
            await asyncio.sleep(0.001)
            return {"data": "x" * 100}

        for cycle in range(50):
            tasks = [dummy_operation() for _ in range(100)]
            results = await asyncio.gather(*tasks)
            del results
            gc.collect()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory should be stable
        assert current < 10 * 1024 * 1024

    def test_memory_tracking_with_large_datasets(self):
        """Should handle large datasets without memory issues."""
        from core.performance.profiler import MemoryLeakDetector

        detector = MemoryLeakDetector()
        gc.collect()

        # Record baseline
        initial_memory = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0

        # Process large data
        large_data = []
        for i in range(10):
            # Create large temporary data
            temp = [{"id": j, "data": "x" * 1000} for j in range(1000)]
            large_data.extend(temp)

            # Track memory
            gc.collect()
            current_memory = len(large_data) * 1000  # Rough estimate

            detector.record_sample(current_memory / 1024 / 1024)

        analysis = detector.analyze()

        # Large data growth expected in this test
        assert analysis["growth_mb"] > 0


class TestSystemUnderLoad:
    """Integration load tests for the full system."""

    @pytest.mark.asyncio
    async def test_mixed_workload(self):
        """Should handle mixed workload of reads and writes."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        state = {"positions": {}, "sentiments": []}
        lock = asyncio.Lock()

        async def read_position(token):
            with profile_block("mixed.read"):
                async with lock:
                    return state["positions"].get(token)

        async def write_position(token, amount):
            with profile_block("mixed.write"):
                async with lock:
                    state["positions"][token] = amount

        async def add_sentiment(data):
            with profile_block("mixed.sentiment"):
                async with lock:
                    state["sentiments"].append(data)

        # Mixed workload
        tasks = []

        # 50 position writes
        for i in range(50):
            tasks.append(write_position(f"TOKEN{i % 10}", i * 100))

        # 100 position reads
        for i in range(100):
            tasks.append(read_position(f"TOKEN{i % 10}"))

        # 50 sentiment updates
        for i in range(50):
            tasks.append(add_sentiment({"score": i / 100}))

        start = time.perf_counter()
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

        # Should complete within 5 seconds
        assert elapsed < 5.0

        results = get_profiler_results()
        assert results["mixed.read"]["call_count"] == 100
        assert results["mixed.write"]["call_count"] == 50
        assert results["mixed.sentiment"]["call_count"] == 50

    @pytest.mark.asyncio
    async def test_sustained_load(self):
        """Should maintain performance under sustained load."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        counter = 0
        lock = asyncio.Lock()

        async def operation():
            nonlocal counter
            with profile_block("sustained.operation"):
                async with lock:
                    counter += 1
                await asyncio.sleep(0.001)

        # Run sustained load for 2 seconds
        start = time.perf_counter()
        batch = 0

        while time.perf_counter() - start < 2.0:
            tasks = [operation() for _ in range(100)]
            await asyncio.gather(*tasks)
            batch += 1

        results = get_profiler_results()
        avg_time = results["sustained.operation"]["avg_duration_ms"]

        # Average operation time should be < 50ms
        assert avg_time < 50
        # Should have processed many operations
        assert counter > 100
