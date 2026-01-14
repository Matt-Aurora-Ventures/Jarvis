#!/usr/bin/env python3
"""
JARVIS Performance Benchmarks

Comprehensive benchmarks for critical code paths.
Run regularly to detect performance regressions.
"""
import asyncio
import time
import statistics
from typing import List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from pathlib import Path
import json
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    ops_per_second: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time * 1000, 3),
            "avg_time_ms": round(self.avg_time * 1000, 3),
            "min_time_ms": round(self.min_time * 1000, 3),
            "max_time_ms": round(self.max_time * 1000, 3),
            "std_dev_ms": round(self.std_dev * 1000, 3),
            "ops_per_second": round(self.ops_per_second, 2)
        }


class Benchmark:
    """Benchmark runner."""

    def __init__(self, warmup: int = 10, iterations: int = 1000):
        self.warmup = warmup
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []

    def run(
        self,
        name: str,
        fn: Callable[[], Any],
        iterations: int = None
    ) -> BenchmarkResult:
        """
        Run a synchronous benchmark.

        Args:
            name: Benchmark name
            fn: Function to benchmark
            iterations: Override default iterations
        """
        iters = iterations or self.iterations

        # Warmup
        for _ in range(self.warmup):
            fn()

        # Benchmark
        times = []
        for _ in range(iters):
            start = time.perf_counter()
            fn()
            times.append(time.perf_counter() - start)

        result = BenchmarkResult(
            name=name,
            iterations=iters,
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            ops_per_second=iters / sum(times)
        )

        self.results.append(result)
        return result

    async def run_async(
        self,
        name: str,
        fn: Callable[[], Awaitable[Any]],
        iterations: int = None
    ) -> BenchmarkResult:
        """
        Run an async benchmark.

        Args:
            name: Benchmark name
            fn: Async function to benchmark
            iterations: Override default iterations
        """
        iters = iterations or self.iterations

        # Warmup
        for _ in range(self.warmup):
            await fn()

        # Benchmark
        times = []
        for _ in range(iters):
            start = time.perf_counter()
            await fn()
            times.append(time.perf_counter() - start)

        result = BenchmarkResult(
            name=name,
            iterations=iters,
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            ops_per_second=iters / sum(times)
        )

        self.results.append(result)
        return result

    def print_results(self) -> None:
        """Print benchmark results in table format."""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)

        if not self.results:
            print("No results")
            return

        # Header
        print(f"{'Name':<40} {'Avg (ms)':<12} {'Min (ms)':<12} {'Ops/sec':<12}")
        print("-" * 80)

        for r in self.results:
            print(
                f"{r.name:<40} "
                f"{r.avg_time * 1000:<12.3f} "
                f"{r.min_time * 1000:<12.3f} "
                f"{r.ops_per_second:<12.2f}"
            )

        print("=" * 80)

    def save_results(self, path: Path) -> None:
        """Save results to JSON file."""
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": [r.to_dict() for r in self.results]
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        print(f"Results saved to {path}")


# ============================================================================
# Benchmark Suites
# ============================================================================

async def benchmark_json_serialization(bench: Benchmark) -> None:
    """Benchmark JSON serialization backends."""
    try:
        from core.performance.json_serializer import (
            FastJSONSerializer, benchmark_backends
        )

        print("\n--- JSON Serialization ---")

        test_data = {
            "users": [
                {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"}
                for i in range(100)
            ],
            "metadata": {"total": 100, "page": 1}
        }

        serializer = FastJSONSerializer()
        print(f"Backend: {serializer.backend}")

        bench.run(
            "json_serialize",
            lambda: serializer.dumps(test_data),
            iterations=5000
        )

        bench.run(
            "json_deserialize",
            lambda: serializer.loads(serializer.dumps(test_data)),
            iterations=5000
        )

    except ImportError as e:
        print(f"Skipping JSON benchmark: {e}")


async def benchmark_caching(bench: Benchmark) -> None:
    """Benchmark caching layer."""
    try:
        from core.cache.decorators import cached, async_cached

        print("\n--- Caching ---")

        # Sync cache
        call_count = [0]

        @cached(ttl=60)
        def cached_function(x: int) -> int:
            call_count[0] += 1
            return x * 2

        def cache_hit():
            return cached_function(42)

        # Warm cache
        cached_function(42)
        call_count[0] = 0

        bench.run("cache_hit", cache_hit, iterations=10000)
        print(f"  Actual function calls: {call_count[0]} (should be 0 or 1)")

    except ImportError as e:
        print(f"Skipping cache benchmark: {e}")


async def benchmark_request_coalescing(bench: Benchmark) -> None:
    """Benchmark request coalescing."""
    try:
        from core.performance.request_coalescing import RequestCoalescer

        print("\n--- Request Coalescing ---")

        coalescer = RequestCoalescer(cache_ttl=0)
        fetch_count = [0]

        async def slow_fetch():
            fetch_count[0] += 1
            await asyncio.sleep(0.001)  # 1ms simulated latency
            return {"data": "value"}

        async def coalesced_request():
            return await coalescer.coalesce("test_key", slow_fetch)

        await bench.run_async("coalesced_request", coalesced_request, iterations=100)

    except ImportError as e:
        print(f"Skipping coalescing benchmark: {e}")


async def benchmark_validation(bench: Benchmark) -> None:
    """Benchmark input validation."""
    try:
        from core.validation.validators import (
            validate_solana_address,
            validate_telegram_user_id,
            sanitize_user_input
        )

        print("\n--- Validation ---")

        valid_address = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"

        bench.run(
            "validate_solana_address",
            lambda: validate_solana_address(valid_address),
            iterations=10000
        )

        bench.run(
            "validate_telegram_id",
            lambda: validate_telegram_user_id(123456789),
            iterations=10000
        )

        test_input = "Hello <script>alert('xss')</script> World"
        bench.run(
            "sanitize_input",
            lambda: sanitize_user_input(test_input),
            iterations=10000
        )

    except ImportError as e:
        print(f"Skipping validation benchmark: {e}")


async def benchmark_hashing(bench: Benchmark) -> None:
    """Benchmark hashing operations."""
    import hashlib
    import secrets

    print("\n--- Hashing ---")

    test_data = secrets.token_bytes(1024)  # 1KB of random data

    bench.run(
        "sha256_1kb",
        lambda: hashlib.sha256(test_data).hexdigest(),
        iterations=10000
    )

    bench.run(
        "sha256_hash_chain",
        lambda: hashlib.sha256(
            hashlib.sha256(test_data).digest()
        ).hexdigest(),
        iterations=10000
    )


async def benchmark_rate_limiting(bench: Benchmark) -> None:
    """Benchmark rate limiter."""
    try:
        from core.api.rate_limit import RateLimiter, RateLimitConfig

        print("\n--- Rate Limiting ---")

        limiter = RateLimiter()
        limiter.configure("test", RateLimitConfig(requests=10000, window_seconds=60))

        async def check_limit():
            return await limiter.check("test", "user123")

        await bench.run_async("rate_limit_check", check_limit, iterations=5000)

    except ImportError as e:
        print(f"Skipping rate limit benchmark: {e}")


async def benchmark_lazy_loading(bench: Benchmark) -> None:
    """Benchmark lazy loading patterns."""
    try:
        from core.performance.lazy_loading import LazyValue, AsyncLazyValue

        print("\n--- Lazy Loading ---")

        # Test lazy value access
        call_count = [0]

        def factory():
            call_count[0] += 1
            return {"initialized": True}

        lazy = LazyValue(factory)

        # First access
        _ = lazy.value
        call_count[0] = 0

        # Subsequent accesses should be instant
        bench.run(
            "lazy_value_access",
            lambda: lazy.value,
            iterations=100000
        )

        print(f"  Factory calls: {call_count[0]} (should be 0)")

    except ImportError as e:
        print(f"Skipping lazy loading benchmark: {e}")


async def main():
    """Run all benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="Run JARVIS benchmarks")
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=1000,
        help="Default iterations per benchmark"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--suite",
        choices=["all", "json", "cache", "coalesce", "validate", "hash", "rate", "lazy"],
        default="all",
        help="Which benchmark suite to run"
    )

    args = parser.parse_args()

    bench = Benchmark(warmup=10, iterations=args.iterations)

    print("=" * 80)
    print("JARVIS PERFORMANCE BENCHMARKS")
    print(f"Iterations: {args.iterations}")
    print("=" * 80)

    suites = {
        "json": benchmark_json_serialization,
        "cache": benchmark_caching,
        "coalesce": benchmark_request_coalescing,
        "validate": benchmark_validation,
        "hash": benchmark_hashing,
        "rate": benchmark_rate_limiting,
        "lazy": benchmark_lazy_loading
    }

    if args.suite == "all":
        for name, fn in suites.items():
            await fn(bench)
    else:
        await suites[args.suite](bench)

    bench.print_results()

    if args.output:
        bench.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
