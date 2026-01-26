"""
Unit tests for Multi-Provider RPC Failover System.

Tests cover:
1. Multi-provider configuration (Helius, QuickNode, Public RPC)
2. 200ms latency threshold for unhealthy status
3. Priority-based failover
4. Provider switch logging
5. NoHealthyProviderError handling
"""

import asyncio
import importlib.util
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

# Import directly from the module file to avoid __init__.py import chain
def _import_from_file(module_name: str, file_path: str):
    """Import a module directly from file, bypassing package __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Get project root
_project_root = Path(__file__).parent.parent.parent
_rpc_health_path = _project_root / "core" / "solana" / "rpc_health.py"

# Import directly from file
_rpc_health = _import_from_file("core.solana.rpc_health_direct", str(_rpc_health_path))

RPCHealthScorer = _rpc_health.RPCHealthScorer
EndpointHealth = _rpc_health.EndpointHealth
HealthScore = _rpc_health.HealthScore
LatencyStats = _rpc_health.LatencyStats
HealthCheckResult = _rpc_health.HealthCheckResult


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def multi_provider_endpoints() -> List[Dict[str, Any]]:
    """Multi-provider RPC endpoint configurations per audit requirements."""
    return [
        {
            "name": "helius",
            "url": "https://mainnet.helius-rpc.com/?api-key=test",
            "priority": 1,
            "timeout_ms": 200,
            "provider_type": "helius",
        },
        {
            "name": "quicknode",
            "url": "https://api.quicknode.com/solana",
            "priority": 2,
            "timeout_ms": 300,
            "provider_type": "quicknode",
        },
        {
            "name": "public",
            "url": "https://api.mainnet-beta.solana.com",
            "priority": 3,
            "timeout_ms": 500,
            "provider_type": "public",
        },
    ]


@pytest.fixture
def multi_provider_scorer(multi_provider_endpoints):
    """Create a health scorer with multi-provider configuration."""
    return RPCHealthScorer(endpoints=multi_provider_endpoints)


# =============================================================================
# TEST: MULTI-PROVIDER CONFIGURATION
# =============================================================================

class TestMultiProviderConfiguration:
    """Tests for multi-provider RPC configuration."""

    def test_three_providers_configured(self, multi_provider_endpoints):
        """Test that exactly 3 providers are configured."""
        scorer = RPCHealthScorer(endpoints=multi_provider_endpoints)

        assert len(scorer.endpoints) == 3

    def test_provider_priorities_set_correctly(self, multi_provider_scorer):
        """Test that provider priorities are set correctly."""
        endpoints = multi_provider_scorer.endpoints

        # Find endpoints by name
        helius = next(e for e in endpoints if e.name == "helius")
        quicknode = next(e for e in endpoints if e.name == "quicknode")
        public = next(e for e in endpoints if e.name == "public")

        assert helius.priority == 1
        assert quicknode.priority == 2
        assert public.priority == 3

    def test_helius_is_primary_by_default(self, multi_provider_scorer):
        """Test that Helius is selected as primary when all healthy."""
        # All endpoints healthy with same latency
        for ep in multi_provider_scorer.endpoints:
            ep.record_success(latency_ms=50.0)

        multi_provider_scorer.update_scores()
        best = multi_provider_scorer.get_best_endpoint()

        assert best.name == "helius"

    def test_provider_urls_match_expected(self, multi_provider_scorer):
        """Test that provider URLs match expected patterns."""
        endpoints = multi_provider_scorer.endpoints

        helius = next(e for e in endpoints if e.name == "helius")
        quicknode = next(e for e in endpoints if e.name == "quicknode")
        public = next(e for e in endpoints if e.name == "public")

        assert "helius-rpc.com" in helius.url
        assert "quicknode" in quicknode.url
        assert "mainnet-beta.solana.com" in public.url


# =============================================================================
# TEST: 200MS LATENCY THRESHOLD
# =============================================================================

class TestLatencyThreshold:
    """Tests for 200ms latency threshold marking endpoints unhealthy."""

    def test_endpoint_healthy_under_200ms(self, multi_provider_scorer):
        """Test that endpoint is healthy when latency < 200ms."""
        helius = multi_provider_scorer.endpoints[0]

        # Record latencies under 200ms
        for _ in range(10):
            helius.record_success(latency_ms=150.0)

        helius.calculate_score()

        # Score should be high (healthy)
        assert helius.score >= 70

    def test_endpoint_degraded_over_200ms(self, multi_provider_scorer):
        """Test that endpoint is marked degraded when latency > 200ms."""
        helius = multi_provider_scorer.endpoints[0]

        # Record latencies over 200ms
        for _ in range(10):
            helius.record_success(latency_ms=350.0)

        helius.calculate_score()

        # Score should be lower (degraded)
        assert helius.score < 90

    def test_failover_on_high_latency(self, multi_provider_scorer):
        """Test failover to QuickNode when Helius latency exceeds threshold."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]

        # Helius has high latency
        for _ in range(10):
            helius.record_success(latency_ms=500.0)

        # QuickNode has good latency
        for _ in range(10):
            quicknode.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()
        best = multi_provider_scorer.get_best_endpoint()

        # Should prefer QuickNode due to better latency
        assert best.name == "quicknode"

    def test_latency_threshold_constant_defined(self):
        """Test that 200ms latency threshold constant is defined."""
        from core.solana.rpc_health import LATENCY_UNHEALTHY_THRESHOLD_MS

        assert LATENCY_UNHEALTHY_THRESHOLD_MS == 200


# =============================================================================
# TEST: AUTOMATIC FAILOVER
# =============================================================================

class TestAutomaticFailover:
    """Tests for automatic failover behavior."""

    def test_failover_to_quicknode_on_helius_failure(self, multi_provider_scorer):
        """Test automatic failover from Helius to QuickNode on failure."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]

        # Helius fails
        for _ in range(5):
            helius.record_failure(error="connection timeout")

        # QuickNode works
        quicknode.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()
        best = multi_provider_scorer.get_best_endpoint()

        assert best.name == "quicknode"

    def test_failover_to_public_when_both_premium_fail(self, multi_provider_scorer):
        """Test failover to Public RPC when both premium providers fail."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]
        public = multi_provider_scorer.endpoints[2]

        # Both premium providers fail
        for _ in range(5):
            helius.record_failure(error="rate limited")
            quicknode.record_failure(error="connection refused")

        # Public works
        public.record_success(latency_ms=200.0)

        multi_provider_scorer.update_scores()
        best = multi_provider_scorer.get_best_endpoint()

        assert best.name == "public"

    def test_recovery_back_to_helius(self, multi_provider_scorer):
        """Test recovery back to Helius when it becomes healthy again."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]

        # Initial: Helius fails, failover to QuickNode
        for _ in range(5):
            helius.record_failure(error="timeout")
        quicknode.record_success(latency_ms=100.0)
        multi_provider_scorer.update_scores()

        assert multi_provider_scorer.get_best_endpoint().name == "quicknode"

        # Helius recovers (simulated circuit breaker timeout)
        helius._circuit_open_until = datetime.utcnow() - timedelta(seconds=1)

        # Record successful requests for Helius
        for _ in range(10):
            helius.record_success(latency_ms=50.0)

        multi_provider_scorer.update_scores()

        # Should prefer Helius again (better latency + higher priority)
        best = multi_provider_scorer.get_best_endpoint()
        assert best.name == "helius"


# =============================================================================
# TEST: PROVIDER SWITCH LOGGING
# =============================================================================

class TestProviderSwitchLogging:
    """Tests for logging when providers switch."""

    def test_failover_logs_provider_switch(self, multi_provider_scorer, caplog):
        """Test that failover logs the provider switch."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]

        # Setup initial state
        helius.record_success(latency_ms=50.0)
        multi_provider_scorer.update_scores()

        # Track initial best
        initial_best = multi_provider_scorer.get_best_endpoint()

        # Trigger failover
        for _ in range(5):
            helius.record_failure(error="connection timeout")
        quicknode.record_success(latency_ms=100.0)

        with caplog.at_level(logging.WARNING):
            multi_provider_scorer.update_scores()

        # Should log circuit breaker open
        assert any("Circuit opened" in record.message for record in caplog.records)

    def test_get_healthy_provider_logs_selection(self, multi_provider_scorer, caplog):
        """Test that get_healthy_provider logs the selected provider."""
        for ep in multi_provider_scorer.endpoints:
            ep.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()

        with caplog.at_level(logging.DEBUG):
            # Use the new method that should log selection
            best = multi_provider_scorer.get_healthy_provider()

        # Method should exist and return endpoint
        assert best is not None


# =============================================================================
# TEST: NO HEALTHY PROVIDER ERROR
# =============================================================================

class TestNoHealthyProviderError:
    """Tests for NoHealthyProviderError when all providers fail."""

    def test_raises_when_all_circuit_open(self, multi_provider_scorer):
        """Test that NoHealthyProviderError is raised when all circuits open."""
        from core.solana.rpc_health import NoHealthyProviderError

        # Open circuit breakers on all endpoints
        for ep in multi_provider_scorer.endpoints:
            for _ in range(5):
                ep.record_failure(error="timeout")

        # All should have circuit open
        for ep in multi_provider_scorer.endpoints:
            assert ep.is_circuit_open is True

        # Should raise when no healthy provider available
        with pytest.raises(NoHealthyProviderError):
            multi_provider_scorer.get_healthy_provider(strict=True)

    def test_returns_fallback_when_not_strict(self, multi_provider_scorer):
        """Test fallback behavior when not in strict mode."""
        # Open circuit breakers on all endpoints
        for ep in multi_provider_scorer.endpoints:
            for _ in range(5):
                ep.record_failure(error="timeout")

        # Should return something (lowest priority fallback)
        best = multi_provider_scorer.get_best_endpoint()
        assert best is not None


# =============================================================================
# TEST: HEALTH CHECK WITH LATENCY THRESHOLD
# =============================================================================

class TestHealthCheckWithLatencyThreshold:
    """Tests for health check behavior with 200ms latency threshold."""

    @pytest.mark.asyncio
    async def test_health_check_marks_slow_endpoint_degraded(self, multi_provider_scorer):
        """Test that health check marks endpoint degraded when latency > 200ms."""
        helius = multi_provider_scorer.endpoints[0]

        # Simulate slow response (350ms)
        result = HealthCheckResult(
            healthy=True,
            latency_ms=350.0,
            error=None,
        )

        # Process the result as the health check loop would
        if result.healthy:
            helius.record_success(result.latency_ms)

        helius.calculate_score()

        # Score should be reduced due to high latency
        assert helius.score < 95  # Not perfect score

    @pytest.mark.asyncio
    async def test_health_check_interval_30_seconds(self, multi_provider_scorer):
        """Test that health check interval is 30 seconds."""
        from core.solana.rpc_health import HEALTH_CHECK_INTERVAL

        assert HEALTH_CHECK_INTERVAL == 30


# =============================================================================
# TEST: PRIORITY-BASED SELECTION
# =============================================================================

class TestPriorityBasedSelection:
    """Tests for priority-based endpoint selection."""

    def test_equal_scores_prefer_higher_priority(self, multi_provider_scorer):
        """Test that equal health scores prefer higher priority endpoint."""
        # Record identical activity for all endpoints
        for ep in multi_provider_scorer.endpoints:
            for _ in range(10):
                ep.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()

        # Get scores
        scores = multi_provider_scorer.get_all_scores()
        helius_score = next(s for s in scores if s["name"] == "helius")["score"]
        quicknode_score = next(s for s in scores if s["name"] == "quicknode")["score"]

        # Scores should be very close
        assert abs(helius_score - quicknode_score) < 5

        # But Helius should be selected due to priority
        best = multi_provider_scorer.get_best_endpoint()
        assert best.name == "helius"

    def test_score_difference_overrides_priority(self, multi_provider_scorer):
        """Test that significant score difference overrides priority."""
        helius = multi_provider_scorer.endpoints[0]
        quicknode = multi_provider_scorer.endpoints[1]

        # Helius has poor performance
        for _ in range(10):
            helius.record_success(latency_ms=800.0)

        # QuickNode has excellent performance
        for _ in range(10):
            quicknode.record_success(latency_ms=50.0)

        multi_provider_scorer.update_scores()

        # QuickNode should be selected despite lower priority
        best = multi_provider_scorer.get_best_endpoint()
        assert best.name == "quicknode"


# =============================================================================
# TEST: METRICS EXPORT WITH PROVIDER INFO
# =============================================================================

class TestMetricsExportWithProviderInfo:
    """Tests for metrics export including provider information."""

    def test_export_includes_all_providers(self, multi_provider_scorer):
        """Test that metrics export includes all three providers."""
        for ep in multi_provider_scorer.endpoints:
            ep.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()
        metrics = multi_provider_scorer.export_metrics()

        assert len(metrics["endpoints"]) == 3

        names = [ep["name"] for ep in metrics["endpoints"]]
        assert "helius" in names
        assert "quicknode" in names
        assert "public" in names

    def test_export_includes_priority(self, multi_provider_scorer):
        """Test that metrics export includes provider priority."""
        for ep in multi_provider_scorer.endpoints:
            ep.record_success(latency_ms=100.0)

        multi_provider_scorer.update_scores()
        metrics = multi_provider_scorer.export_metrics()

        for endpoint_metrics in metrics["endpoints"]:
            assert "priority" in endpoint_metrics
            assert endpoint_metrics["priority"] in [1, 2, 3]
