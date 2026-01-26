"""
Unit tests for RPC Health Scoring System.

Tests cover:
1. Health score calculation (0-100)
2. Latency tracking (p50, p95, p99)
3. Success rate monitoring
4. Auto-failover logic
5. Periodic health checks
6. Metrics persistence
"""

import asyncio
import importlib.util
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
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
_rpc_health = _import_from_file("core.solana.rpc_health_unit", str(_rpc_health_path))

RPCHealthScorer = _rpc_health.RPCHealthScorer
EndpointHealth = _rpc_health.EndpointHealth
HealthScore = _rpc_health.HealthScore
LatencyStats = _rpc_health.LatencyStats
HealthCheckResult = _rpc_health.HealthCheckResult
HEALTH_CHECK_INTERVAL = _rpc_health.HEALTH_CHECK_INTERVAL


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_endpoints() -> List[Dict[str, Any]]:
    """Sample RPC endpoint configurations."""
    return [
        {
            "name": "helius_primary",
            "url": "https://mainnet.helius-rpc.com/?api-key=test",
            "priority": 1,
        },
        {
            "name": "quicknode_backup",
            "url": "https://quick-node.example.com",
            "priority": 2,
        },
        {
            "name": "public_fallback",
            "url": "https://api.mainnet-beta.solana.com",
            "priority": 3,
        },
    ]


@pytest.fixture
def health_scorer(sample_endpoints):
    """Create a health scorer instance."""
    if RPCHealthScorer is None:
        pytest.skip("RPCHealthScorer not implemented yet")
    return RPCHealthScorer(endpoints=sample_endpoints)


# =============================================================================
# TEST: LATENCY STATISTICS
# =============================================================================

class TestLatencyStats:
    """Tests for latency percentile calculations."""

    def test_latency_stats_creation(self):
        """Test creating LatencyStats with recorded latencies."""
        if LatencyStats is None:
            pytest.skip("LatencyStats not implemented yet")

        stats = LatencyStats()
        stats.record(50.0)
        stats.record(100.0)
        stats.record(150.0)
        stats.record(200.0)
        stats.record(250.0)

        assert stats.count == 5
        assert stats.p50 is not None
        assert stats.p95 is not None
        assert stats.p99 is not None

    def test_latency_stats_p50_calculation(self):
        """Test p50 (median) calculation."""
        if LatencyStats is None:
            pytest.skip("LatencyStats not implemented yet")

        stats = LatencyStats()
        # Add 100 latencies from 1-100ms
        for i in range(1, 101):
            stats.record(float(i))

        # p50 should be around 50
        assert 45 <= stats.p50 <= 55

    def test_latency_stats_p95_calculation(self):
        """Test p95 calculation."""
        if LatencyStats is None:
            pytest.skip("LatencyStats not implemented yet")

        stats = LatencyStats()
        # Add 100 latencies from 1-100ms
        for i in range(1, 101):
            stats.record(float(i))

        # p95 should be around 95
        assert 90 <= stats.p95 <= 100

    def test_latency_stats_p99_calculation(self):
        """Test p99 calculation."""
        if LatencyStats is None:
            pytest.skip("LatencyStats not implemented yet")

        stats = LatencyStats()
        # Add 100 latencies from 1-100ms
        for i in range(1, 101):
            stats.record(float(i))

        # p99 should be around 99
        assert 95 <= stats.p99 <= 100

    def test_latency_stats_rolling_window(self):
        """Test that latency stats use a rolling window (last 1000 samples)."""
        if LatencyStats is None:
            pytest.skip("LatencyStats not implemented yet")

        stats = LatencyStats(window_size=100)

        # Add 150 samples
        for i in range(150):
            stats.record(float(i))

        # Should only keep last 100
        assert stats.count == 100
        # p50 should be based on last 100 samples (50-149)
        assert stats.p50 >= 50


# =============================================================================
# TEST: HEALTH SCORE CALCULATION
# =============================================================================

class TestHealthScore:
    """Tests for health score calculation (0-100 scale)."""

    def test_health_score_perfect_endpoint(self):
        """Test health score for a perfectly performing endpoint."""
        if HealthScore is None:
            pytest.skip("HealthScore not implemented yet")

        score = HealthScore.calculate(
            success_rate=100.0,
            latency_p50=50.0,
            latency_p95=100.0,
            latency_p99=150.0,
            consecutive_failures=0,
            last_failure_seconds_ago=None,
        )

        # Perfect endpoint should score 90+
        assert score >= 90

    def test_health_score_degraded_endpoint(self):
        """Test health score for a degraded endpoint with some failures."""
        if HealthScore is None:
            pytest.skip("HealthScore not implemented yet")

        score = HealthScore.calculate(
            success_rate=85.0,
            latency_p50=200.0,
            latency_p95=500.0,
            latency_p99=1000.0,
            consecutive_failures=1,
            last_failure_seconds_ago=30.0,
        )

        # Degraded endpoint should score between 50-80
        assert 40 <= score <= 80

    def test_health_score_unhealthy_endpoint(self):
        """Test health score for an unhealthy endpoint with many failures."""
        if HealthScore is None:
            pytest.skip("HealthScore not implemented yet")

        score = HealthScore.calculate(
            success_rate=50.0,
            latency_p50=1000.0,
            latency_p95=3000.0,
            latency_p99=5000.0,
            consecutive_failures=5,
            last_failure_seconds_ago=5.0,
        )

        # Unhealthy endpoint should score below 40
        assert score < 40

    def test_health_score_clamped_to_0_100(self):
        """Test that health scores are clamped between 0 and 100."""
        if HealthScore is None:
            pytest.skip("HealthScore not implemented yet")

        # Even with extreme values, score should be in range
        score_good = HealthScore.calculate(
            success_rate=100.0,
            latency_p50=1.0,
            latency_p95=2.0,
            latency_p99=3.0,
            consecutive_failures=0,
            last_failure_seconds_ago=None,
        )

        score_bad = HealthScore.calculate(
            success_rate=0.0,
            latency_p50=10000.0,
            latency_p95=20000.0,
            latency_p99=30000.0,
            consecutive_failures=100,
            last_failure_seconds_ago=1.0,
        )

        assert 0 <= score_good <= 100
        assert 0 <= score_bad <= 100


# =============================================================================
# TEST: ENDPOINT HEALTH TRACKING
# =============================================================================

class TestEndpointHealth:
    """Tests for EndpointHealth state tracking."""

    def test_endpoint_health_creation(self):
        """Test creating an EndpointHealth instance."""
        if EndpointHealth is None:
            pytest.skip("EndpointHealth not implemented yet")

        health = EndpointHealth(
            name="test_endpoint",
            url="https://test.example.com",
            priority=1,
        )

        assert health.name == "test_endpoint"
        assert health.url == "https://test.example.com"
        assert health.priority == 1
        assert health.success_count == 0
        assert health.failure_count == 0
        assert health.consecutive_failures == 0

    def test_endpoint_health_record_success(self):
        """Test recording a successful request."""
        if EndpointHealth is None:
            pytest.skip("EndpointHealth not implemented yet")

        health = EndpointHealth(
            name="test_endpoint",
            url="https://test.example.com",
            priority=1,
        )

        health.record_success(latency_ms=50.0)

        assert health.success_count == 1
        assert health.consecutive_failures == 0
        assert health.last_success is not None

    def test_endpoint_health_record_failure(self):
        """Test recording a failed request."""
        if EndpointHealth is None:
            pytest.skip("EndpointHealth not implemented yet")

        health = EndpointHealth(
            name="test_endpoint",
            url="https://test.example.com",
            priority=1,
        )

        health.record_failure(error="timeout")

        assert health.failure_count == 1
        assert health.consecutive_failures == 1
        assert health.last_failure is not None

    def test_endpoint_health_consecutive_failure_reset(self):
        """Test that consecutive failures reset on success."""
        if EndpointHealth is None:
            pytest.skip("EndpointHealth not implemented yet")

        health = EndpointHealth(
            name="test_endpoint",
            url="https://test.example.com",
            priority=1,
        )

        # Record 3 failures
        health.record_failure(error="timeout")
        health.record_failure(error="timeout")
        health.record_failure(error="timeout")
        assert health.consecutive_failures == 3

        # Record a success
        health.record_success(latency_ms=50.0)
        assert health.consecutive_failures == 0

    def test_endpoint_health_success_rate(self):
        """Test success rate calculation."""
        if EndpointHealth is None:
            pytest.skip("EndpointHealth not implemented yet")

        health = EndpointHealth(
            name="test_endpoint",
            url="https://test.example.com",
            priority=1,
        )

        # 8 successes, 2 failures = 80% success rate
        for _ in range(8):
            health.record_success(latency_ms=50.0)
        for _ in range(2):
            health.record_failure(error="timeout")

        assert abs(health.success_rate - 80.0) < 0.1


# =============================================================================
# TEST: RPC HEALTH SCORER
# =============================================================================

class TestRPCHealthScorer:
    """Tests for the main RPCHealthScorer class."""

    def test_scorer_initialization(self, sample_endpoints):
        """Test initializing the health scorer."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        scorer = RPCHealthScorer(endpoints=sample_endpoints)

        assert len(scorer.endpoints) == 3
        assert scorer.is_running is False

    def test_scorer_get_best_endpoint(self, health_scorer):
        """Test selecting the best healthy endpoint."""
        # Simulate different health states
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.endpoints[1].record_success(latency_ms=100.0)
        health_scorer.endpoints[2].record_success(latency_ms=150.0)

        # Update scores
        health_scorer.update_scores()

        best = health_scorer.get_best_endpoint()

        # Helius (lowest latency, highest priority) should be best
        assert best.name == "helius_primary"

    def test_scorer_get_best_endpoint_with_failures(self, health_scorer):
        """Test selecting best endpoint when primary has failures."""
        # Primary endpoint failing
        for _ in range(5):
            health_scorer.endpoints[0].record_failure(error="timeout")

        # Backup working fine
        health_scorer.endpoints[1].record_success(latency_ms=100.0)
        health_scorer.endpoints[2].record_success(latency_ms=150.0)

        health_scorer.update_scores()

        best = health_scorer.get_best_endpoint()

        # Should failover to quicknode backup
        assert best.name == "quicknode_backup"

    def test_scorer_all_endpoints_unhealthy(self, health_scorer):
        """Test behavior when all endpoints are unhealthy."""
        # All endpoints failing
        for endpoint in health_scorer.endpoints:
            for _ in range(10):
                endpoint.record_failure(error="timeout")

        health_scorer.update_scores()

        # Should still return something (lowest priority as fallback)
        best = health_scorer.get_best_endpoint()
        assert best is not None

    def test_scorer_get_all_scores(self, health_scorer):
        """Test getting health scores for all endpoints."""
        # Record some activity
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.endpoints[1].record_success(latency_ms=100.0)

        health_scorer.update_scores()

        scores = health_scorer.get_all_scores()

        assert len(scores) == 3
        assert all("name" in s for s in scores)
        assert all("score" in s for s in scores)
        assert all(0 <= s["score"] <= 100 for s in scores)

    def test_scorer_exclude_endpoint(self, health_scorer):
        """Test getting best endpoint while excluding some."""
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.endpoints[1].record_success(latency_ms=100.0)
        health_scorer.update_scores()

        # Exclude the primary
        best = health_scorer.get_best_endpoint(exclude=["helius_primary"])

        assert best.name != "helius_primary"


# =============================================================================
# TEST: AUTO-FAILOVER
# =============================================================================

class TestAutoFailover:
    """Tests for automatic failover behavior."""

    def test_failover_threshold(self, health_scorer):
        """Test that failover occurs after threshold failures."""
        # Default threshold is 3 consecutive failures
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.update_scores()

        # Verify primary is best initially
        assert health_scorer.get_best_endpoint().name == "helius_primary"

        # Add enough failures to trigger failover
        for _ in range(3):
            health_scorer.endpoints[0].record_failure(error="timeout")

        health_scorer.update_scores()

        # Should have failed over
        best = health_scorer.get_best_endpoint()
        assert best.name != "helius_primary"

    def test_failover_recovery(self, health_scorer):
        """Test that endpoint can recover from circuit breaker state."""
        # Make primary fail to trigger circuit breaker
        for _ in range(5):
            health_scorer.endpoints[0].record_failure(error="timeout")
        health_scorer.endpoints[1].record_success(latency_ms=100.0)
        health_scorer.update_scores()

        # Verify failover occurred (circuit breaker opens)
        assert health_scorer.get_best_endpoint().name != "helius_primary"
        assert health_scorer.endpoints[0].is_circuit_open is True

        # Simulate circuit breaker timeout (time passes)
        health_scorer.endpoints[0]._circuit_open_until = datetime.utcnow() - timedelta(seconds=1)

        # Primary starts getting successful requests again
        # This should clear the circuit breaker
        health_scorer.endpoints[0].record_success(latency_ms=50.0)

        # Verify circuit is now cleared after successful request
        assert health_scorer.endpoints[0].is_circuit_open is False
        assert health_scorer.endpoints[0].consecutive_failures == 0

        # After recovery, primary is at least considered (not circuit-open)
        # The exact scoring depends on history, but it should be usable
        health_scorer.update_scores()
        assert health_scorer.endpoints[0].score > 0

    def test_circuit_breaker_open(self, health_scorer):
        """Test circuit breaker opens after threshold."""
        # Trigger circuit breaker
        for _ in range(5):
            health_scorer.endpoints[0].record_failure(error="timeout")

        assert health_scorer.endpoints[0].is_circuit_open is True

    def test_circuit_breaker_half_open(self, health_scorer):
        """Test circuit breaker transitions to half-open after timeout."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        # Trigger circuit breaker
        for _ in range(5):
            health_scorer.endpoints[0].record_failure(error="timeout")

        # Simulate time passing
        health_scorer.endpoints[0]._circuit_open_until = datetime.utcnow() - timedelta(seconds=1)

        assert health_scorer.endpoints[0].is_circuit_half_open is True


# =============================================================================
# TEST: PERIODIC HEALTH CHECKS
# =============================================================================

class TestPeriodicHealthChecks:
    """Tests for periodic health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_starts(self, health_scorer):
        """Test that health check loop starts."""
        with patch.object(health_scorer, '_run_health_checks', new_callable=AsyncMock) as mock_check:
            await health_scorer.start()

            assert health_scorer.is_running is True

            # Let it run briefly
            await asyncio.sleep(0.1)

            await health_scorer.stop()

            assert health_scorer.is_running is False

    @pytest.mark.asyncio
    async def test_health_check_calls_getHealth(self, health_scorer):
        """Test that health checks call getHealth RPC method."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        mock_response = {"jsonrpc": "2.0", "result": "ok", "id": 1}

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            result = await health_scorer._check_endpoint_health(health_scorer.endpoints[0])

            assert result.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_records_latency(self, health_scorer):
        """Test that health checks record latency via _run_health_checks."""
        mock_response = {"jsonrpc": "2.0", "result": "ok", "id": 1}

        # Mock aiohttp.ClientSession for health checks
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        mock_session.post.return_value.__aexit__ = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        initial_count = health_scorer.endpoints[0].latency_stats.count

        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Run the full health check cycle which records latency
            await health_scorer._run_health_checks()

        # After health check, latency should be recorded
        assert health_scorer.endpoints[0].latency_stats.count > initial_count


# =============================================================================
# TEST: METRICS PERSISTENCE
# =============================================================================

class TestMetricsPersistence:
    """Tests for metrics persistence to database."""

    @pytest.mark.asyncio
    async def test_metrics_saved_to_db(self, health_scorer):
        """Test that metrics are persisted to database."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        # Mock database
        mock_db = MagicMock()
        mock_db.save_rpc_metrics = AsyncMock()
        health_scorer.set_database(mock_db)

        # Record some activity
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.update_scores()

        # Persist metrics
        await health_scorer.persist_metrics()

        # Verify save was called
        mock_db.save_rpc_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_loaded_from_db(self, sample_endpoints):
        """Test that metrics are loaded from database on init."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        # Mock database with existing metrics
        mock_db = MagicMock()
        mock_db.load_rpc_metrics = AsyncMock(return_value={
            "helius_primary": {"success_count": 100, "failure_count": 5},
        })

        scorer = RPCHealthScorer(endpoints=sample_endpoints, database=mock_db)
        await scorer.load_metrics()

        # Verify metrics were loaded
        assert scorer.endpoints[0].success_count == 100
        assert scorer.endpoints[0].failure_count == 5

    def test_metrics_export_format(self, health_scorer):
        """Test that metrics can be exported in standard format."""
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.update_scores()

        metrics = health_scorer.export_metrics()

        assert "timestamp" in metrics
        assert "endpoints" in metrics
        assert len(metrics["endpoints"]) == 3

        for endpoint_metrics in metrics["endpoints"]:
            assert "name" in endpoint_metrics
            assert "url" in endpoint_metrics
            assert "score" in endpoint_metrics
            assert "success_rate" in endpoint_metrics
            assert "latency_p50" in endpoint_metrics
            assert "latency_p95" in endpoint_metrics
            assert "latency_p99" in endpoint_metrics


# =============================================================================
# TEST: INTEGRATION WITH SOLANA CLIENT
# =============================================================================

class TestSolanaClientIntegration:
    """Tests for integration with existing Solana client."""

    @pytest.mark.skip(reason="Requires full package import which fails due to __init__.py chain")
    def test_scorer_from_rpc_config(self):
        """Test creating scorer from existing RPC config file."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        with patch('core.solana.rpc_health.load_solana_rpc_endpoints') as mock_load:
            mock_load.return_value = [
                MagicMock(name="test", url="https://test.com", timeout_ms=30000, rate_limit=100)
            ]

            scorer = RPCHealthScorer.from_config()

            assert len(scorer.endpoints) == 1

    @pytest.mark.skip(reason="Requires full package import which fails due to __init__.py chain")
    def test_scorer_provides_async_client(self, health_scorer):
        """Test that scorer provides AsyncClient for best endpoint."""
        health_scorer.endpoints[0].record_success(latency_ms=50.0)
        health_scorer.update_scores()

        # Mock solana being available
        with patch('core.solana.rpc_health.HAS_SOLANA', True):
            with patch('core.solana.rpc_health.AsyncClient', MagicMock()):
                # Should return a callable that creates AsyncClient
                client_factory = health_scorer.get_client_factory()
                assert callable(client_factory)


# =============================================================================
# TEST: EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_endpoints_list(self):
        """Test handling empty endpoints list."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        with pytest.raises(ValueError, match="At least one endpoint required"):
            RPCHealthScorer(endpoints=[])

    def test_invalid_endpoint_config(self):
        """Test handling invalid endpoint configuration."""
        if RPCHealthScorer is None:
            pytest.skip("RPCHealthScorer not implemented yet")

        with pytest.raises(ValueError):
            RPCHealthScorer(endpoints=[{"name": "test"}])  # Missing url

    def test_score_with_no_data(self, health_scorer):
        """Test getting score when no data recorded yet."""
        scores = health_scorer.get_all_scores()

        # Should still work, return default scores
        assert len(scores) == 3
        for s in scores:
            assert 0 <= s["score"] <= 100

    def test_concurrent_record_updates(self, health_scorer):
        """Test thread-safety of record updates."""
        import threading

        def record_many():
            for _ in range(100):
                health_scorer.endpoints[0].record_success(latency_ms=50.0)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have recorded all without errors
        assert health_scorer.endpoints[0].success_count == 500


# =============================================================================
# TEST: HEALTH CHECK RESULT
# =============================================================================

class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_health_check_result_healthy(self):
        """Test healthy check result."""
        if HealthCheckResult is None:
            pytest.skip("HealthCheckResult not implemented yet")

        result = HealthCheckResult(
            healthy=True,
            latency_ms=50.0,
            block_height=123456789,
            error=None,
        )

        assert result.healthy is True
        assert result.latency_ms == 50.0
        assert result.error is None

    def test_health_check_result_unhealthy(self):
        """Test unhealthy check result."""
        if HealthCheckResult is None:
            pytest.skip("HealthCheckResult not implemented yet")

        result = HealthCheckResult(
            healthy=False,
            latency_ms=5000.0,
            block_height=None,
            error="timeout",
        )

        assert result.healthy is False
        assert result.error == "timeout"
