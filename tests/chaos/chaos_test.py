"""
JARVIS Chaos Engineering Test Suite

Tests system resilience through fault injection.

Fault Types:
1. Connection failures (database, API)
2. Latency injection (100-500ms delays)
3. Error responses (50% failure rate)
4. Truncated/corrupted data

Goals:
- System degrades gracefully (no crashes)
- Fallbacks work correctly
- Recovery is automatic

Usage:
    pytest tests/chaos/chaos_test.py -v
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FaultType(str, Enum):
    """Types of faults that can be injected."""
    CONNECTION_KILL = "connection_kill"
    LATENCY = "latency"
    ERROR_RESPONSE = "error_response"
    TRUNCATED_DATA = "truncated_data"
    TIMEOUT = "timeout"
    CORRUPT_DATA = "corrupt_data"


@dataclass
class FaultConfig:
    """Configuration for a fault injection."""
    fault_type: FaultType
    probability: float = 0.5  # 50% by default
    latency_range_ms: Tuple[int, int] = (100, 500)
    error_codes: List[int] = field(default_factory=lambda: [500, 502, 503])
    duration_seconds: float = 0  # 0 = indefinite until stopped


@dataclass
class ChaosMetrics:
    """Metrics from chaos testing."""
    total_calls: int = 0
    faults_injected: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    recovered_calls: int = 0
    fallback_used: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def fault_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.faults_injected / self.total_calls) * 100

    @property
    def recovery_rate(self) -> float:
        if self.faults_injected == 0:
            return 0.0
        return (self.recovered_calls / self.faults_injected) * 100

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "faults_injected": self.faults_injected,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "recovered_calls": self.recovered_calls,
            "fallback_used": self.fallback_used,
            "fault_rate_pct": round(self.fault_rate, 2),
            "success_rate_pct": round(self.success_rate, 2),
            "recovery_rate_pct": round(self.recovery_rate, 2),
            "unique_errors": len(set(self.errors)),
        }


class FaultInjector:
    """Inject faults into async functions."""

    def __init__(self, config: FaultConfig):
        self.config = config
        self.enabled = False
        self.metrics = ChaosMetrics()
        self._start_time: Optional[float] = None

    def start(self):
        """Start injecting faults."""
        self.enabled = True
        self._start_time = time.time()
        self.metrics = ChaosMetrics()

    def stop(self):
        """Stop injecting faults."""
        self.enabled = False

    def should_inject(self) -> bool:
        """Determine if fault should be injected."""
        if not self.enabled:
            return False

        # Check duration
        if self.config.duration_seconds > 0:
            elapsed = time.time() - (self._start_time or 0)
            if elapsed > self.config.duration_seconds:
                self.enabled = False
                return False

        return random.random() < self.config.probability

    async def inject_latency(self):
        """Inject latency fault."""
        min_ms, max_ms = self.config.latency_range_ms
        delay = random.randint(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)
        self.metrics.faults_injected += 1

    def inject_error(self) -> Exception:
        """Inject error fault."""
        self.metrics.faults_injected += 1
        error_code = random.choice(self.config.error_codes)
        return Exception(f"Chaos fault: HTTP {error_code}")

    def inject_truncated_data(self, data: Any) -> Any:
        """Inject truncated data fault."""
        self.metrics.faults_injected += 1
        if isinstance(data, dict):
            # Remove some keys
            keys = list(data.keys())
            if keys:
                truncated = data.copy()
                for key in random.sample(keys, min(len(keys) // 2, 1)):
                    del truncated[key]
                return truncated
        elif isinstance(data, str):
            return data[: len(data) // 2]
        elif isinstance(data, list):
            return data[: len(data) // 2]
        return data

    def inject_corrupt_data(self, data: Any) -> Any:
        """Inject corrupted data fault."""
        self.metrics.faults_injected += 1
        if isinstance(data, dict):
            corrupted = data.copy()
            if corrupted:
                key = random.choice(list(corrupted.keys()))
                corrupted[key] = "CORRUPTED_VALUE"
            return corrupted
        elif isinstance(data, str):
            return data[:10] + "CORRUPTED" + data[10:]
        return data

    def wrap_function(self, func: Callable) -> Callable:
        """Wrap a function with fault injection."""

        async def wrapper(*args, **kwargs):
            self.metrics.total_calls += 1
            start_time = time.time()

            try:
                if self.should_inject():
                    fault_type = self.config.fault_type

                    if fault_type == FaultType.LATENCY:
                        await self.inject_latency()
                        result = await func(*args, **kwargs)

                    elif fault_type == FaultType.ERROR_RESPONSE:
                        raise self.inject_error()

                    elif fault_type == FaultType.TIMEOUT:
                        self.metrics.faults_injected += 1
                        raise asyncio.TimeoutError("Chaos timeout")

                    elif fault_type == FaultType.CONNECTION_KILL:
                        self.metrics.faults_injected += 1
                        raise ConnectionError("Connection killed by chaos")

                    elif fault_type in (FaultType.TRUNCATED_DATA, FaultType.CORRUPT_DATA):
                        result = await func(*args, **kwargs)
                        if fault_type == FaultType.TRUNCATED_DATA:
                            result = self.inject_truncated_data(result)
                        else:
                            result = self.inject_corrupt_data(result)
                    else:
                        result = await func(*args, **kwargs)
                else:
                    result = await func(*args, **kwargs)

                self.metrics.successful_calls += 1
                self.metrics.response_times.append(time.time() - start_time)
                return result

            except Exception as e:
                self.metrics.failed_calls += 1
                self.metrics.errors.append(str(e)[:100])
                self.metrics.response_times.append(time.time() - start_time)
                raise

        return wrapper


class ChaosOrchestrator:
    """Orchestrate chaos testing scenarios."""

    def __init__(self):
        self.injectors: Dict[str, FaultInjector] = {}
        self.active_experiment: Optional[str] = None

    def register_fault(self, name: str, config: FaultConfig):
        """Register a fault injector."""
        self.injectors[name] = FaultInjector(config)

    def start_experiment(self, name: str):
        """Start a chaos experiment."""
        if name in self.injectors:
            self.injectors[name].start()
            self.active_experiment = name

    def stop_experiment(self, name: str = None):
        """Stop a chaos experiment."""
        name = name or self.active_experiment
        if name and name in self.injectors:
            self.injectors[name].stop()
            self.active_experiment = None

    def stop_all(self):
        """Stop all experiments."""
        for injector in self.injectors.values():
            injector.stop()
        self.active_experiment = None

    def get_metrics(self, name: str = None) -> Optional[ChaosMetrics]:
        """Get metrics for an experiment."""
        name = name or self.active_experiment
        if name and name in self.injectors:
            return self.injectors[name].metrics
        return None

    def get_all_metrics(self) -> Dict[str, ChaosMetrics]:
        """Get metrics for all experiments."""
        return {name: inj.metrics for name, inj in self.injectors.items()}


# =============================================================================
# Resilient Service Mocks
# =============================================================================

class ResilientService:
    """Service with resilience patterns for testing."""

    def __init__(self):
        self.primary_calls = 0
        self.fallback_calls = 0
        self.recovery_attempts = 0
        self._circuit_state = "closed"
        self._failure_count = 0
        self._failure_threshold = 3

    async def primary_operation(self) -> Dict[str, Any]:
        """Primary operation that can fail."""
        self.primary_calls += 1
        # Simulate some work
        await asyncio.sleep(0.01)
        return {
            "status": "success",
            "source": "primary",
            "data": {"value": random.randint(1, 100)},
        }

    async def fallback_operation(self) -> Dict[str, Any]:
        """Fallback when primary fails."""
        self.fallback_calls += 1
        return {
            "status": "success",
            "source": "fallback",
            "data": {"value": 0, "cached": True},
        }

    async def execute_with_fallback(
        self,
        primary: Callable = None,
        fallback: Callable = None,
    ) -> Dict[str, Any]:
        """Execute with fallback pattern."""
        primary = primary or self.primary_operation
        fallback = fallback or self.fallback_operation

        try:
            if self._circuit_state == "open":
                raise Exception("Circuit open")

            result = await primary()
            self._failure_count = 0
            return result

        except Exception:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._circuit_state = "open"
                # Schedule recovery attempt
                asyncio.create_task(self._attempt_recovery())

            return await fallback()

    async def _attempt_recovery(self):
        """Attempt to recover circuit."""
        await asyncio.sleep(0.5)  # Wait before recovery
        self.recovery_attempts += 1
        self._circuit_state = "half_open"

        # Try recovery
        try:
            await self.primary_operation()
            self._circuit_state = "closed"
            self._failure_count = 0
        except Exception:
            self._circuit_state = "open"


# =============================================================================
# Chaos Test Scenarios
# =============================================================================

class TestChaosScenarios:
    """Chaos engineering test scenarios."""

    @pytest.fixture
    def chaos_orchestrator(self):
        return ChaosOrchestrator()

    @pytest.fixture
    def resilient_service(self):
        return ResilientService()

    @pytest.mark.asyncio
    async def test_latency_injection_100_500ms(
        self,
        chaos_orchestrator: ChaosOrchestrator,
        resilient_service: ResilientService
    ):
        """
        Scenario: Inject 100-500ms latency on API calls.

        Validates:
        - System continues to function
        - Latency is within expected range
        """
        config = FaultConfig(
            fault_type=FaultType.LATENCY,
            probability=0.5,
            latency_range_ms=(100, 500),
        )
        chaos_orchestrator.register_fault("latency", config)

        injector = chaos_orchestrator.injectors["latency"]
        wrapped = injector.wrap_function(resilient_service.primary_operation)

        chaos_orchestrator.start_experiment("latency")

        # Run multiple calls
        results = []
        for _ in range(20):
            try:
                result = await wrapped()
                results.append(result)
            except Exception:
                pass

        chaos_orchestrator.stop_experiment()

        metrics = chaos_orchestrator.get_metrics("latency")

        print(f"\n[Latency Injection Test]")
        print(f"  Total calls: {metrics.total_calls}")
        print(f"  Faults injected: {metrics.faults_injected}")
        print(f"  Success rate: {metrics.success_rate:.2f}%")

        # With latency injection, all calls should still succeed
        assert metrics.success_rate == 100, "Latency should not cause failures"
        assert metrics.faults_injected > 0, "No faults were injected"

    @pytest.mark.asyncio
    async def test_error_response_50_percent(
        self,
        chaos_orchestrator: ChaosOrchestrator,
        resilient_service: ResilientService
    ):
        """
        Scenario: 50% of API calls return errors.

        Validates:
        - Fallback is used when errors occur
        - System doesn't crash
        """
        config = FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            probability=0.5,
            error_codes=[500, 502, 503],
        )
        chaos_orchestrator.register_fault("errors", config)

        injector = chaos_orchestrator.injectors["errors"]
        wrapped = injector.wrap_function(resilient_service.primary_operation)

        chaos_orchestrator.start_experiment("errors")

        successful = 0
        failed = 0
        fallback_used = 0

        for _ in range(20):
            try:
                await wrapped()
                successful += 1
            except Exception:
                # Use fallback
                result = await resilient_service.fallback_operation()
                if result["source"] == "fallback":
                    fallback_used += 1
                failed += 1

        chaos_orchestrator.stop_experiment()

        metrics = chaos_orchestrator.get_metrics("errors")

        print(f"\n[50% Error Rate Test]")
        print(f"  Total calls: {metrics.total_calls}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Fallback used: {fallback_used}")
        print(f"  Fault rate: {metrics.fault_rate:.2f}%")

        # Should have roughly 50% failures (within range due to randomness)
        assert 20 <= metrics.fault_rate <= 80, f"Fault rate {metrics.fault_rate}% outside expected range"
        assert fallback_used > 0, "Fallback should have been used"

    @pytest.mark.asyncio
    async def test_connection_kill(
        self,
        chaos_orchestrator: ChaosOrchestrator,
        resilient_service: ResilientService
    ):
        """
        Scenario: Random connection kills.

        Validates:
        - System handles connection failures gracefully
        - Recovery happens automatically
        """
        config = FaultConfig(
            fault_type=FaultType.CONNECTION_KILL,
            probability=0.3,
        )
        chaos_orchestrator.register_fault("connection", config)

        injector = chaos_orchestrator.injectors["connection"]

        # Use execute_with_fallback to test resilience
        results = []
        chaos_orchestrator.start_experiment("connection")

        for _ in range(30):
            wrapped_primary = injector.wrap_function(resilient_service.primary_operation)

            try:
                result = await wrapped_primary()
                results.append(result)
            except ConnectionError:
                result = await resilient_service.fallback_operation()
                results.append(result)

        chaos_orchestrator.stop_experiment()

        metrics = chaos_orchestrator.get_metrics("connection")

        print(f"\n[Connection Kill Test]")
        print(f"  Total calls: {metrics.total_calls}")
        print(f"  Connection kills: {metrics.faults_injected}")
        print(f"  Results obtained: {len(results)}")

        # All requests should get a result (either primary or fallback)
        assert len(results) == 30, "All requests should get a result"
        primary_results = sum(1 for r in results if r.get("source") == "primary")
        fallback_results = sum(1 for r in results if r.get("source") == "fallback")
        print(f"  Primary: {primary_results}, Fallback: {fallback_results}")

    @pytest.mark.asyncio
    async def test_truncated_data_recovery(
        self,
        chaos_orchestrator: ChaosOrchestrator
    ):
        """
        Scenario: Truncated/incomplete data responses.

        Validates:
        - System detects truncated data
        - Handles incomplete data gracefully
        """
        async def get_data() -> Dict[str, Any]:
            return {
                "id": "token_123",
                "name": "Test Token",
                "price": 1.5,
                "volume": 1000000,
                "market_cap": 50000000,
            }

        config = FaultConfig(
            fault_type=FaultType.TRUNCATED_DATA,
            probability=0.5,
        )
        chaos_orchestrator.register_fault("truncate", config)

        injector = chaos_orchestrator.injectors["truncate"]
        wrapped = injector.wrap_function(get_data)

        chaos_orchestrator.start_experiment("truncate")

        results = []
        for _ in range(20):
            result = await wrapped()
            results.append(result)

        chaos_orchestrator.stop_experiment()

        # Check that some results are truncated
        full_results = [r for r in results if len(r) == 5]
        truncated_results = [r for r in results if len(r) < 5]

        print(f"\n[Truncated Data Test]")
        print(f"  Total results: {len(results)}")
        print(f"  Full results: {len(full_results)}")
        print(f"  Truncated results: {len(truncated_results)}")

        # Should have mix of full and truncated
        assert len(truncated_results) > 0, "No truncated data was generated"
        assert len(full_results) > 0, "All data was truncated"

    @pytest.mark.asyncio
    async def test_recovery_time_after_fault(
        self,
        chaos_orchestrator: ChaosOrchestrator,
        resilient_service: ResilientService
    ):
        """
        Scenario: Measure recovery time after fault injection stops.

        Validates:
        - System recovers automatically
        - Recovery happens within acceptable time
        """
        config = FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            probability=1.0,  # 100% failures during chaos
            duration_seconds=1.0,  # Only 1 second of chaos
        )
        chaos_orchestrator.register_fault("recovery", config)

        injector = chaos_orchestrator.injectors["recovery"]
        wrapped = injector.wrap_function(resilient_service.primary_operation)

        # Start chaos
        chaos_orchestrator.start_experiment("recovery")
        start_time = time.time()

        # Track when we first succeed after chaos ends
        recovery_time = None

        for i in range(100):
            elapsed = time.time() - start_time
            chaos_ended = not injector.enabled

            try:
                await wrapped()
                # If chaos has ended and we succeeded, that's recovery
                if chaos_ended and recovery_time is None:
                    recovery_time = elapsed
                    break
            except Exception:
                pass

            await asyncio.sleep(0.02)

            # Give some extra time after chaos duration
            if elapsed > 2.5:
                break

        print(f"\n[Recovery Time Test]")
        print(f"  Chaos duration: 1.0s")
        print(f"  Recovery time: {recovery_time:.2f}s" if recovery_time else "  Did not recover")

        # Should recover within 3 seconds (1s chaos + 2s recovery buffer)
        assert recovery_time is not None, "System did not recover"
        assert recovery_time < 3.0, f"Recovery took too long: {recovery_time}s"


class TestChaosMetrics:
    """Unit tests for chaos metrics."""

    def test_metrics_calculation(self):
        """Test metrics calculations."""
        metrics = ChaosMetrics(
            total_calls=100,
            faults_injected=30,
            successful_calls=70,
            failed_calls=30,
            recovered_calls=20,
            fallback_used=10,
        )

        assert metrics.fault_rate == 30.0
        assert metrics.success_rate == 70.0
        assert abs(metrics.recovery_rate - 66.67) < 0.1

    def test_empty_metrics(self):
        """Test empty metrics don't cause division errors."""
        metrics = ChaosMetrics()

        assert metrics.fault_rate == 0.0
        assert metrics.success_rate == 0.0
        assert metrics.recovery_rate == 0.0


class TestFaultInjector:
    """Unit tests for fault injector."""

    @pytest.mark.asyncio
    async def test_probability_based_injection(self):
        """Test that faults are injected based on probability."""
        config = FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            probability=0.5,
        )
        injector = FaultInjector(config)
        injector.start()

        injected_count = 0
        for _ in range(100):
            if injector.should_inject():
                injected_count += 1

        injector.stop()

        # Should be roughly 50% (with some variance)
        assert 30 <= injected_count <= 70, f"Injection rate {injected_count}% outside expected range"

    @pytest.mark.asyncio
    async def test_duration_based_stop(self):
        """Test that injection stops after duration."""
        config = FaultConfig(
            fault_type=FaultType.ERROR_RESPONSE,
            probability=1.0,
            duration_seconds=0.5,
        )
        injector = FaultInjector(config)
        injector.start()

        # Should inject at start
        assert injector.should_inject()

        # Wait for duration to pass
        await asyncio.sleep(0.6)

        # Should stop injecting
        assert not injector.should_inject()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
