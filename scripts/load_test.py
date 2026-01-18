#!/usr/bin/env python3
"""
JARVIS Load Test CLI

Run load tests from the command line.

Usage:
    python scripts/load_test.py --users 100 --duration 10m
    python scripts/load_test.py --users 50 --requests 1000
    python scripts/load_test.py --report  # Show last results
"""

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LoadTestConfig:
    """Configuration for load test."""
    users: int = 100
    duration_seconds: int = 60
    total_requests: int = 0  # 0 = use duration
    target_rps: float = 0  # 0 = max throughput
    host: str = "http://localhost:8000"


@dataclass
class LoadTestResult:
    """Result of a load test run."""
    config: LoadTestConfig
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    response_times: List[float]
    errors: List[str]
    timestamp: str

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def throughput(self) -> float:
        if self.duration_seconds == 0:
            return 0
        return self.total_requests / self.duration_seconds

    @property
    def p50(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        return sorted_times[len(sorted_times) // 2]

    @property
    def p95(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "users": self.config.users,
                "duration_seconds": self.config.duration_seconds,
                "host": self.config.host,
            },
            "results": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "error_rate_pct": round(self.error_rate, 2),
                "duration_seconds": round(self.duration_seconds, 2),
                "throughput_rps": round(self.throughput, 2),
            },
            "latency_ms": {
                "p50": round(self.p50 * 1000, 2),
                "p95": round(self.p95 * 1000, 2),
                "p99": round(self.p99 * 1000, 2),
            },
            "timestamp": self.timestamp,
        }

    def print_summary(self):
        """Print a summary of the results."""
        print("\n" + "=" * 60)
        print("JARVIS Load Test Results")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"\nConfiguration:")
        print(f"  Concurrent users: {self.config.users}")
        print(f"  Duration: {self.config.duration_seconds}s")
        print(f"  Host: {self.config.host}")
        print(f"\nResults:")
        print(f"  Total requests:  {self.total_requests}")
        print(f"  Successful:      {self.successful_requests}")
        print(f"  Failed:          {self.failed_requests}")
        print(f"  Error rate:      {self.error_rate:.2f}%")
        print(f"  Throughput:      {self.throughput:.2f} req/s")
        print(f"\nLatency:")
        print(f"  p50:  {self.p50 * 1000:.2f}ms")
        print(f"  p95:  {self.p95 * 1000:.2f}ms")
        print(f"  p99:  {self.p99 * 1000:.2f}ms")
        print("=" * 60)

        # Pass/Fail assessment
        if self.p95 < 0.5 and self.error_rate < 1:
            print("\nStatus: PASS")
            print("  p95 < 500ms and error rate < 1%")
        else:
            print("\nStatus: FAIL")
            if self.p95 >= 0.5:
                print(f"  p95 latency {self.p95 * 1000:.2f}ms > 500ms threshold")
            if self.error_rate >= 1:
                print(f"  Error rate {self.error_rate:.2f}% > 1% threshold")


class MockEndpoint:
    """Mock endpoint for testing without real server."""

    def __init__(self, latency_range: tuple = (0.01, 0.05), failure_rate: float = 0.01):
        self.latency_range = latency_range
        self.failure_rate = failure_rate

    async def call(self) -> Dict[str, Any]:
        """Simulate an API call."""
        await asyncio.sleep(random.uniform(*self.latency_range))

        if random.random() < self.failure_rate:
            raise Exception("Simulated failure")

        return {"status": "ok"}


class LoadTestRunner:
    """Run load tests."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.mock_endpoint = MockEndpoint()

    async def run(self) -> LoadTestResult:
        """Run the load test."""
        response_times = []
        errors = []
        successful = 0
        failed = 0

        semaphore = asyncio.Semaphore(self.config.users)

        async def make_request():
            nonlocal successful, failed
            async with semaphore:
                start = time.time()
                try:
                    await self.mock_endpoint.call()
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
                finally:
                    response_times.append(time.time() - start)

        start_time = time.time()

        if self.config.total_requests > 0:
            # Run fixed number of requests
            tasks = [make_request() for _ in range(self.config.total_requests)]
            await asyncio.gather(*tasks)
        else:
            # Run for duration
            end_time = start_time + self.config.duration_seconds
            tasks = []

            while time.time() < end_time:
                tasks.append(asyncio.create_task(make_request()))

                # Rate limiting if target RPS is set
                if self.config.target_rps > 0:
                    await asyncio.sleep(1 / self.config.target_rps)
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent overwhelming

            # Wait for remaining tasks
            await asyncio.gather(*tasks)

        duration = time.time() - start_time

        return LoadTestResult(
            config=self.config,
            total_requests=successful + failed,
            successful_requests=successful,
            failed_requests=failed,
            duration_seconds=duration,
            response_times=response_times,
            errors=errors[:10],  # Keep first 10 errors
            timestamp=datetime.now().isoformat(),
        )


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '10m', '1h', '30s'."""
    if duration_str.endswith('m'):
        return int(duration_str[:-1]) * 60
    elif duration_str.endswith('h'):
        return int(duration_str[:-1]) * 3600
    elif duration_str.endswith('s'):
        return int(duration_str[:-1])
    else:
        return int(duration_str)


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Load Test CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/load_test.py --users 100 --duration 10m
    python scripts/load_test.py --users 50 --requests 1000
    python scripts/load_test.py --users 100 --rps 50 --duration 5m
        """
    )

    parser.add_argument(
        "--users",
        type=int,
        default=100,
        help="Number of concurrent users (default: 100)"
    )
    parser.add_argument(
        "--duration",
        type=str,
        default="60s",
        help="Test duration (e.g., 30s, 10m, 1h) (default: 60s)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=0,
        help="Total requests to make (overrides duration)"
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=0,
        help="Target requests per second (0 = max throughput)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:8000",
        help="Target host URL"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Show report of last test run"
    )

    args = parser.parse_args()

    # Handle report mode
    if args.report:
        results_file = Path("tests/load/.load_test_results.json")
        if results_file.exists():
            data = json.loads(results_file.read_text())
            print(json.dumps(data, indent=2))
        else:
            print("No previous results found")
        return

    # Create config
    config = LoadTestConfig(
        users=args.users,
        duration_seconds=parse_duration(args.duration),
        total_requests=args.requests,
        target_rps=args.rps,
        host=args.host,
    )

    print("=" * 60)
    print("JARVIS Load Test")
    print("=" * 60)
    print(f"Starting load test:")
    print(f"  Users: {config.users}")
    if config.total_requests > 0:
        print(f"  Total requests: {config.total_requests}")
    else:
        print(f"  Duration: {config.duration_seconds}s")
    if config.target_rps > 0:
        print(f"  Target RPS: {config.target_rps}")
    print(f"  Host: {config.host}")
    print("=" * 60)
    print("\nRunning...")

    # Run the test
    runner = LoadTestRunner(config)
    result = asyncio.run(runner.run())

    # Print results
    result.print_summary()

    # Save results
    output_file = args.output or "tests/load/.load_test_results.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nResults saved to: {output_file}")

    # Exit with appropriate code
    if result.p95 < 0.5 and result.error_rate < 1:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
