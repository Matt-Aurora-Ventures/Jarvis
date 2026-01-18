#!/usr/bin/env python3
"""
JARVIS Stress Test CLI

Run stress tests from the command line.

Usage:
    python scripts/stress_test.py --ramp-up 1m --peak 100 --hold 5m
    python scripts/stress_test.py --spike --multiplier 10
    python scripts/stress_test.py --sustained --users 50 --duration 30m
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class StressPattern(str, Enum):
    RAMP = "ramp"
    SPIKE = "spike"
    SUSTAINED = "sustained"


@dataclass
class StressConfig:
    """Configuration for stress test."""
    pattern: StressPattern = StressPattern.RAMP
    start_users: int = 10
    peak_users: int = 100
    ramp_up_seconds: int = 60
    hold_seconds: int = 300
    spike_multiplier: int = 10


@dataclass
class StressBucket:
    """Metrics for a time bucket."""
    timestamp: float
    users: int
    requests: int
    errors: int
    avg_latency_ms: float
    throughput_rps: float


@dataclass
class StressResult:
    """Result of a stress test run."""
    config: StressConfig
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    buckets: List[StressBucket]
    degradation_point: Optional[Tuple[int, float]]
    breaking_point: Optional[Tuple[int, float]]
    peak_throughput: float
    timestamp: str

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return (self.failed_requests / self.total_requests) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "pattern": self.config.pattern.value,
                "start_users": self.config.start_users,
                "peak_users": self.config.peak_users,
                "ramp_up_seconds": self.config.ramp_up_seconds,
                "hold_seconds": self.config.hold_seconds,
            },
            "results": {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "error_rate_pct": round(self.error_rate, 2),
                "duration_seconds": round(self.duration_seconds, 2),
                "peak_throughput_rps": round(self.peak_throughput, 2),
            },
            "analysis": {
                "degradation_point": {
                    "users": self.degradation_point[0] if self.degradation_point else None,
                    "latency_ms": self.degradation_point[1] if self.degradation_point else None,
                },
                "breaking_point": {
                    "users": self.breaking_point[0] if self.breaking_point else None,
                    "error_rate_pct": self.breaking_point[1] if self.breaking_point else None,
                },
            },
            "buckets": [
                {
                    "timestamp": b.timestamp,
                    "users": b.users,
                    "requests": b.requests,
                    "errors": b.errors,
                    "avg_latency_ms": round(b.avg_latency_ms, 2),
                    "throughput_rps": round(b.throughput_rps, 2),
                }
                for b in self.buckets
            ],
            "timestamp": self.timestamp,
        }

    def print_summary(self):
        """Print a summary of the results."""
        print("\n" + "=" * 60)
        print("JARVIS Stress Test Results")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"\nConfiguration:")
        print(f"  Pattern:      {self.config.pattern.value}")
        print(f"  Start users:  {self.config.start_users}")
        print(f"  Peak users:   {self.config.peak_users}")
        print(f"  Ramp-up:      {self.config.ramp_up_seconds}s")
        print(f"  Hold:         {self.config.hold_seconds}s")
        print(f"\nResults:")
        print(f"  Total requests:   {self.total_requests}")
        print(f"  Successful:       {self.successful_requests}")
        print(f"  Failed:           {self.failed_requests}")
        print(f"  Error rate:       {self.error_rate:.2f}%")
        print(f"  Peak throughput:  {self.peak_throughput:.2f} req/s")
        print(f"\nAnalysis:")
        if self.degradation_point:
            print(f"  Degradation at:  {self.degradation_point[0]} users "
                  f"(latency: {self.degradation_point[1]:.2f}ms)")
        else:
            print(f"  Degradation:     Not detected")
        if self.breaking_point:
            print(f"  Breaking at:     {self.breaking_point[0]} users "
                  f"(error rate: {self.breaking_point[1]:.2f}%)")
        else:
            print(f"  Breaking point:  Not detected")

        # Print bucket summary
        print(f"\nTime Series (every {len(self.buckets)} buckets):")
        for i, bucket in enumerate(self.buckets[::max(1, len(self.buckets) // 5)]):
            print(f"  t={bucket.timestamp:5.0f}s | users={bucket.users:3d} | "
                  f"rps={bucket.throughput_rps:6.1f} | latency={bucket.avg_latency_ms:6.1f}ms | "
                  f"errors={bucket.errors}")

        print("=" * 60)


class MockService:
    """Mock service with degradation under load."""

    def __init__(self, degradation_threshold: int = 50):
        self.degradation_threshold = degradation_threshold
        self._active = 0

    async def process(self) -> Dict[str, Any]:
        """Process a request with load-dependent behavior."""
        self._active += 1
        try:
            # Latency increases with load
            load_factor = max(1.0, self._active / self.degradation_threshold)
            latency = 0.01 * load_factor  # Base 10ms

            await asyncio.sleep(latency)

            # Error rate increases with load
            if load_factor > 2 and random.random() < (load_factor - 2) * 0.1:
                raise Exception("Overloaded")

            return {"status": "ok", "latency": latency}
        finally:
            self._active -= 1


class StressTestRunner:
    """Run stress tests."""

    def __init__(self, config: StressConfig):
        self.config = config
        self.service = MockService(degradation_threshold=50)
        self.buckets: List[StressBucket] = []

    async def _run_bucket(
        self,
        users: int,
        duration: float,
        bucket_start: float,
    ) -> StressBucket:
        """Run requests for a single time bucket."""
        semaphore = asyncio.Semaphore(users)
        response_times = []
        errors = 0
        successful = 0

        async def make_request():
            nonlocal successful, errors
            async with semaphore:
                start = time.time()
                try:
                    await self.service.process()
                    successful += 1
                except Exception:
                    errors += 1
                response_times.append(time.time() - start)

        start_time = time.time()
        tasks = []

        while time.time() - start_time < duration:
            tasks.append(asyncio.create_task(make_request()))
            await asyncio.sleep(0.01)

        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time

        return StressBucket(
            timestamp=bucket_start,
            users=users,
            requests=successful + errors,
            errors=errors,
            avg_latency_ms=statistics.mean(response_times) * 1000 if response_times else 0,
            throughput_rps=(successful + errors) / elapsed if elapsed > 0 else 0,
        )

    async def run_ramp(self) -> StressResult:
        """Run ramp-up stress test."""
        start_time = time.time()
        total_successful = 0
        total_failed = 0

        # Calculate user steps
        steps = 10
        user_step = (self.config.peak_users - self.config.start_users) // steps
        step_duration = self.config.ramp_up_seconds / steps

        # Ramp up phase
        print("\n[Ramp-up Phase]")
        for i in range(steps + 1):
            users = self.config.start_users + (i * user_step)
            bucket = await self._run_bucket(
                users=users,
                duration=step_duration,
                bucket_start=time.time() - start_time,
            )
            self.buckets.append(bucket)
            total_successful += bucket.requests - bucket.errors
            total_failed += bucket.errors
            print(f"  Step {i+1}/{steps+1}: {users} users, {bucket.throughput_rps:.1f} rps")

        # Hold phase
        print("\n[Hold Phase]")
        hold_buckets = max(1, self.config.hold_seconds // 10)
        for i in range(hold_buckets):
            bucket = await self._run_bucket(
                users=self.config.peak_users,
                duration=min(10, self.config.hold_seconds),
                bucket_start=time.time() - start_time,
            )
            self.buckets.append(bucket)
            total_successful += bucket.requests - bucket.errors
            total_failed += bucket.errors

        duration = time.time() - start_time

        return self._create_result(
            total_successful=total_successful,
            total_failed=total_failed,
            duration=duration,
        )

    async def run_spike(self) -> StressResult:
        """Run spike stress test."""
        start_time = time.time()
        total_successful = 0
        total_failed = 0

        # Pre-spike
        print("\n[Pre-Spike Phase]")
        bucket = await self._run_bucket(
            users=self.config.start_users,
            duration=10,
            bucket_start=0,
        )
        self.buckets.append(bucket)
        total_successful += bucket.requests - bucket.errors
        total_failed += bucket.errors

        # Spike
        print("\n[Spike Phase]")
        spike_users = self.config.start_users * self.config.spike_multiplier
        bucket = await self._run_bucket(
            users=spike_users,
            duration=30,
            bucket_start=time.time() - start_time,
        )
        self.buckets.append(bucket)
        total_successful += bucket.requests - bucket.errors
        total_failed += bucket.errors
        print(f"  Spike: {spike_users} users, {bucket.throughput_rps:.1f} rps")

        # Recovery
        print("\n[Recovery Phase]")
        bucket = await self._run_bucket(
            users=self.config.start_users,
            duration=10,
            bucket_start=time.time() - start_time,
        )
        self.buckets.append(bucket)
        total_successful += bucket.requests - bucket.errors
        total_failed += bucket.errors

        duration = time.time() - start_time

        return self._create_result(
            total_successful=total_successful,
            total_failed=total_failed,
            duration=duration,
        )

    async def run_sustained(self) -> StressResult:
        """Run sustained load test."""
        start_time = time.time()
        total_successful = 0
        total_failed = 0

        print(f"\n[Sustained Load: {self.config.peak_users} users]")
        bucket_count = max(1, self.config.hold_seconds // 10)

        for i in range(bucket_count):
            bucket = await self._run_bucket(
                users=self.config.peak_users,
                duration=10,
                bucket_start=time.time() - start_time,
            )
            self.buckets.append(bucket)
            total_successful += bucket.requests - bucket.errors
            total_failed += bucket.errors

            if (i + 1) % 6 == 0:
                print(f"  Minute {(i + 1) // 6}: {bucket.throughput_rps:.1f} rps, "
                      f"{bucket.avg_latency_ms:.1f}ms latency")

        duration = time.time() - start_time

        return self._create_result(
            total_successful=total_successful,
            total_failed=total_failed,
            duration=duration,
        )

    def _create_result(
        self,
        total_successful: int,
        total_failed: int,
        duration: float,
    ) -> StressResult:
        """Create result from collected data."""
        # Find degradation point (latency > 100ms)
        degradation = None
        for bucket in self.buckets:
            if bucket.avg_latency_ms > 100:
                degradation = (bucket.users, bucket.avg_latency_ms)
                break

        # Find breaking point (error rate > 5%)
        breaking = None
        for bucket in self.buckets:
            error_rate = (bucket.errors / bucket.requests * 100) if bucket.requests > 0 else 0
            if error_rate > 5:
                breaking = (bucket.users, error_rate)
                break

        return StressResult(
            config=self.config,
            total_requests=total_successful + total_failed,
            successful_requests=total_successful,
            failed_requests=total_failed,
            duration_seconds=duration,
            buckets=self.buckets,
            degradation_point=degradation,
            breaking_point=breaking,
            peak_throughput=max(b.throughput_rps for b in self.buckets) if self.buckets else 0,
            timestamp=datetime.now().isoformat(),
        )

    async def run(self) -> StressResult:
        """Run the configured stress test."""
        if self.config.pattern == StressPattern.RAMP:
            return await self.run_ramp()
        elif self.config.pattern == StressPattern.SPIKE:
            return await self.run_spike()
        else:
            return await self.run_sustained()


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
        description="JARVIS Stress Test CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/stress_test.py --ramp-up 1m --peak 100 --hold 5m
    python scripts/stress_test.py --spike --multiplier 10
    python scripts/stress_test.py --sustained --users 50 --duration 30m
        """
    )

    # Pattern selection
    pattern_group = parser.add_mutually_exclusive_group()
    pattern_group.add_argument(
        "--ramp",
        action="store_true",
        help="Run ramp-up test (default)"
    )
    pattern_group.add_argument(
        "--spike",
        action="store_true",
        help="Run spike test"
    )
    pattern_group.add_argument(
        "--sustained",
        action="store_true",
        help="Run sustained load test"
    )

    # Common parameters
    parser.add_argument(
        "--start-users",
        type=int,
        default=10,
        help="Starting number of users (default: 10)"
    )
    parser.add_argument(
        "--peak",
        type=int,
        default=100,
        help="Peak number of users (default: 100)"
    )
    parser.add_argument(
        "--ramp-up",
        type=str,
        default="60s",
        help="Ramp-up duration (default: 60s)"
    )
    parser.add_argument(
        "--hold",
        type=str,
        default="60s",
        help="Hold duration at peak (default: 60s)"
    )
    parser.add_argument(
        "--multiplier",
        type=int,
        default=10,
        help="Spike multiplier (for --spike mode)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    # Determine pattern
    if args.spike:
        pattern = StressPattern.SPIKE
    elif args.sustained:
        pattern = StressPattern.SUSTAINED
    else:
        pattern = StressPattern.RAMP

    # Create config
    config = StressConfig(
        pattern=pattern,
        start_users=args.start_users,
        peak_users=args.peak,
        ramp_up_seconds=parse_duration(args.ramp_up),
        hold_seconds=parse_duration(args.hold),
        spike_multiplier=args.multiplier,
    )

    print("=" * 60)
    print("JARVIS Stress Test")
    print("=" * 60)
    print(f"Pattern:     {config.pattern.value}")
    print(f"Start users: {config.start_users}")
    print(f"Peak users:  {config.peak_users}")
    if config.pattern == StressPattern.RAMP:
        print(f"Ramp-up:     {config.ramp_up_seconds}s")
    if config.pattern == StressPattern.SPIKE:
        print(f"Multiplier:  {config.spike_multiplier}x")
    print(f"Hold:        {config.hold_seconds}s")
    print("=" * 60)

    # Run the test
    runner = StressTestRunner(config)
    result = asyncio.run(runner.run())

    # Print results
    result.print_summary()

    # Save results
    output_file = args.output or "tests/stress/.stress_test_results.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nResults saved to: {output_file}")

    # Exit code based on results
    if result.breaking_point is None and result.error_rate < 10:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
