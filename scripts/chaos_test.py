#!/usr/bin/env python3
"""
JARVIS Chaos Test CLI

Run chaos engineering tests from the command line.

Usage:
    python scripts/chaos_test.py --fault-rate 0.5 --duration 5m
    python scripts/chaos_test.py --fault-type latency --latency-ms 200-500
    python scripts/chaos_test.py --fault-type error --duration 1m
"""

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class FaultType(str, Enum):
    LATENCY = "latency"
    ERROR = "error"
    TIMEOUT = "timeout"
    MIXED = "mixed"


@dataclass
class ChaosConfig:
    """Configuration for chaos test."""
    fault_type: FaultType = FaultType.MIXED
    fault_rate: float = 0.5
    duration_seconds: int = 60
    latency_min_ms: int = 100
    latency_max_ms: int = 500
    iterations: int = 0  # 0 = use duration


@dataclass
class ChaosResult:
    """Result of a chaos test run."""
    config: ChaosConfig
    total_requests: int
    faults_injected: int
    successful_requests: int
    failed_requests: int
    fallback_used: int
    recovered: int
    duration_seconds: float
    timestamp: str

    @property
    def fault_injection_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return (self.faults_injected / self.total_requests) * 100

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def recovery_rate(self) -> float:
        if self.faults_injected == 0:
            return 0
        return (self.recovered / self.faults_injected) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "fault_type": self.config.fault_type.value,
                "fault_rate": self.config.fault_rate,
                "duration_seconds": self.config.duration_seconds,
                "latency_range_ms": f"{self.config.latency_min_ms}-{self.config.latency_max_ms}",
            },
            "results": {
                "total_requests": self.total_requests,
                "faults_injected": self.faults_injected,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "fallback_used": self.fallback_used,
                "recovered": self.recovered,
                "fault_injection_rate_pct": round(self.fault_injection_rate, 2),
                "success_rate_pct": round(self.success_rate, 2),
                "recovery_rate_pct": round(self.recovery_rate, 2),
            },
            "duration_seconds": round(self.duration_seconds, 2),
            "timestamp": self.timestamp,
        }

    def print_summary(self):
        """Print a summary of the results."""
        print("\n" + "=" * 60)
        print("JARVIS Chaos Test Results")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"\nConfiguration:")
        print(f"  Fault type:   {self.config.fault_type.value}")
        print(f"  Fault rate:   {self.config.fault_rate * 100:.0f}%")
        print(f"  Duration:     {self.config.duration_seconds}s")
        if self.config.fault_type in [FaultType.LATENCY, FaultType.MIXED]:
            print(f"  Latency range: {self.config.latency_min_ms}-{self.config.latency_max_ms}ms")
        print(f"\nResults:")
        print(f"  Total requests:     {self.total_requests}")
        print(f"  Faults injected:    {self.faults_injected} ({self.fault_injection_rate:.1f}%)")
        print(f"  Successful:         {self.successful_requests}")
        print(f"  Failed:             {self.failed_requests}")
        print(f"  Fallback used:      {self.fallback_used}")
        print(f"  Recovered:          {self.recovered}")
        print(f"\nRates:")
        print(f"  Success rate:   {self.success_rate:.1f}%")
        print(f"  Recovery rate:  {self.recovery_rate:.1f}%")
        print("=" * 60)

        # Assessment
        if self.success_rate >= 90:
            print("\nStatus: PASS")
            print("  System maintained 90%+ success rate under chaos")
        else:
            print("\nStatus: FAIL")
            print(f"  Success rate {self.success_rate:.1f}% below 90% threshold")


class FaultInjector:
    """Inject faults into operations."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self.faults_injected = 0

    def should_inject(self) -> bool:
        """Determine if a fault should be injected."""
        return random.random() < self.config.fault_rate

    async def inject_latency(self):
        """Inject latency fault."""
        delay_ms = random.randint(self.config.latency_min_ms, self.config.latency_max_ms)
        await asyncio.sleep(delay_ms / 1000)
        self.faults_injected += 1

    def inject_error(self):
        """Inject error fault."""
        self.faults_injected += 1
        raise Exception("Chaos error injection")

    async def inject_timeout(self):
        """Inject timeout fault."""
        self.faults_injected += 1
        await asyncio.sleep(5)  # Long delay to simulate timeout
        raise asyncio.TimeoutError("Chaos timeout injection")

    async def inject_fault(self, fault_type: FaultType = None):
        """Inject a fault of the specified type."""
        fault_type = fault_type or self.config.fault_type

        if fault_type == FaultType.MIXED:
            fault_type = random.choice([FaultType.LATENCY, FaultType.ERROR])

        if fault_type == FaultType.LATENCY:
            await self.inject_latency()
        elif fault_type == FaultType.ERROR:
            self.inject_error()
        elif fault_type == FaultType.TIMEOUT:
            await self.inject_timeout()


class MockService:
    """Mock service with fallback."""

    def __init__(self):
        self.call_count = 0
        self.fallback_count = 0

    async def primary_operation(self) -> Dict[str, Any]:
        """Primary operation."""
        self.call_count += 1
        await asyncio.sleep(0.01)  # 10ms base latency
        return {"status": "ok", "source": "primary"}

    async def fallback_operation(self) -> Dict[str, Any]:
        """Fallback operation."""
        self.fallback_count += 1
        return {"status": "ok", "source": "fallback"}


class ChaosTestRunner:
    """Run chaos tests."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self.injector = FaultInjector(config)
        self.service = MockService()

    async def run(self) -> ChaosResult:
        """Run the chaos test."""
        successful = 0
        failed = 0
        fallback_used = 0
        recovered = 0

        start_time = time.time()

        if self.config.iterations > 0:
            iterations = self.config.iterations
        else:
            # Estimate iterations based on duration
            iterations = self.config.duration_seconds * 100  # ~100 ops/sec

        for i in range(iterations):
            # Check duration limit
            if self.config.iterations == 0 and time.time() - start_time > self.config.duration_seconds:
                break

            try:
                # Decide whether to inject fault
                if self.injector.should_inject():
                    if self.config.fault_type in [FaultType.ERROR, FaultType.TIMEOUT]:
                        await self.injector.inject_fault()
                    else:
                        # For latency, inject then continue
                        await self.injector.inject_fault()
                        await self.service.primary_operation()
                        successful += 1
                        continue

                # Normal operation
                await self.service.primary_operation()
                successful += 1

            except Exception:
                failed += 1
                # Try fallback
                try:
                    await self.service.fallback_operation()
                    fallback_used += 1
                    recovered += 1
                except Exception:
                    pass

            await asyncio.sleep(0.01)  # Pacing

        duration = time.time() - start_time

        return ChaosResult(
            config=self.config,
            total_requests=successful + failed,
            faults_injected=self.injector.faults_injected,
            successful_requests=successful,
            failed_requests=failed,
            fallback_used=fallback_used,
            recovered=recovered,
            duration_seconds=duration,
            timestamp=datetime.now().isoformat(),
        )


def parse_latency_range(range_str: str) -> tuple:
    """Parse latency range like '100-500'."""
    parts = range_str.split('-')
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return 100, 500


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
        description="JARVIS Chaos Test CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/chaos_test.py --fault-rate 0.5 --duration 5m
    python scripts/chaos_test.py --fault-type latency --latency-ms 200-500
    python scripts/chaos_test.py --fault-type error --duration 1m
    python scripts/chaos_test.py --fault-type mixed --fault-rate 0.3
        """
    )

    parser.add_argument(
        "--fault-type",
        type=str,
        choices=["latency", "error", "timeout", "mixed"],
        default="mixed",
        help="Type of fault to inject (default: mixed)"
    )
    parser.add_argument(
        "--fault-rate",
        type=float,
        default=0.5,
        help="Probability of fault injection (0.0-1.0, default: 0.5)"
    )
    parser.add_argument(
        "--duration",
        type=str,
        default="60s",
        help="Test duration (e.g., 30s, 10m, 1h) (default: 60s)"
    )
    parser.add_argument(
        "--latency-ms",
        type=str,
        default="100-500",
        help="Latency range in ms (e.g., 100-500) (default: 100-500)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="Fixed number of iterations (0 = use duration)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    # Parse latency range
    latency_min, latency_max = parse_latency_range(args.latency_ms)

    # Create config
    config = ChaosConfig(
        fault_type=FaultType(args.fault_type),
        fault_rate=args.fault_rate,
        duration_seconds=parse_duration(args.duration),
        latency_min_ms=latency_min,
        latency_max_ms=latency_max,
        iterations=args.iterations,
    )

    print("=" * 60)
    print("JARVIS Chaos Test")
    print("=" * 60)
    print(f"Starting chaos test:")
    print(f"  Fault type:   {config.fault_type.value}")
    print(f"  Fault rate:   {config.fault_rate * 100:.0f}%")
    print(f"  Duration:     {config.duration_seconds}s")
    if config.fault_type in [FaultType.LATENCY, FaultType.MIXED]:
        print(f"  Latency:      {config.latency_min_ms}-{config.latency_max_ms}ms")
    print("=" * 60)
    print("\nRunning...")

    # Run the test
    runner = ChaosTestRunner(config)
    result = asyncio.run(runner.run())

    # Print results
    result.print_summary()

    # Save results
    output_file = args.output or "tests/chaos/.chaos_test_results.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nResults saved to: {output_file}")

    # Exit with appropriate code
    if result.success_rate >= 90:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
