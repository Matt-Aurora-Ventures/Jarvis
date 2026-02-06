"""
Unit tests for metrics API endpoint.
Tests GET /metrics and GET /metrics/json endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestMetricsEndpoint:
    """Test metrics API endpoints."""

    @pytest.fixture
    def mock_bot_metrics(self):
        """Create mock bot metrics."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=100)
        metrics.increment("messages_sent", amount=80)
        metrics.increment("commands_processed", amount=50)
        metrics.increment("errors_total", amount=5)
        metrics.record_timing("handle", 0.5)
        metrics.record_timing("handle", 1.0)

        return metrics

    def test_metrics_endpoint_exists(self, mock_bot_metrics):
        """GET /metrics should exist and return 200."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200

    def test_metrics_endpoint_returns_prometheus_format(self, mock_bot_metrics):
        """GET /metrics should return text/plain with Prometheus format."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics", headers={"X-API-Key": "test-key"})

        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        assert "clawdbot_messages_total" in response.text

    def test_metrics_json_endpoint_exists(self, mock_bot_metrics):
        """GET /metrics/json should exist and return 200."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics/json", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200

    def test_metrics_json_returns_json_format(self, mock_bot_metrics):
        """GET /metrics/json should return application/json."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics/json", headers={"X-API-Key": "test-key"})

        assert "application/json" in response.headers["content-type"]

        data = response.json()
        assert isinstance(data, dict)

    def test_metrics_json_contains_expected_fields(self, mock_bot_metrics):
        """GET /metrics/json should contain expected metric fields."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics/json", headers={"X-API-Key": "test-key"})

        data = response.json()

        assert "bots" in data
        assert "clawdbot" in data["bots"]
        assert "messages_received" in data["bots"]["clawdbot"]
        assert data["bots"]["clawdbot"]["messages_received"] == 100

    def test_metrics_requires_api_key(self, mock_bot_metrics):
        """GET /metrics should require API key authentication."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="secret-key")
        app.include_router(router)

        client = TestClient(app)

        # No API key
        response = client.get("/metrics")
        assert response.status_code == 401

        # Wrong API key
        response = client.get("/metrics", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401

        # Correct API key
        response = client.get("/metrics", headers={"X-API-Key": "secret-key"})
        assert response.status_code == 200

    def test_metrics_json_requires_api_key(self, mock_bot_metrics):
        """GET /metrics/json should require API key authentication."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="secret-key")
        app.include_router(router)

        client = TestClient(app)

        # No API key
        response = client.get("/metrics/json")
        assert response.status_code == 401

    def test_metrics_supports_query_param_auth(self, mock_bot_metrics):
        """GET /metrics should support api_key query parameter."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from fastapi import FastAPI

        aggregator = MetricsAggregator([mock_bot_metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="secret-key")
        app.include_router(router)

        client = TestClient(app)

        # API key via query param
        response = client.get("/metrics?api_key=secret-key")
        assert response.status_code == 200


class TestMetricsEndpointEdgeCases:
    """Test edge cases for metrics endpoint."""

    def test_empty_metrics(self):
        """Endpoint should handle empty metrics gracefully."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.bot_metrics import BotMetrics
        from fastapi import FastAPI

        # Empty bot metrics
        metrics = BotMetrics(bot_name="empty_bot")
        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200
        # Should still have valid Prometheus output (possibly with zero values)
        assert "clawdbot" in response.text or "empty_bot" in response.text or "# " in response.text

    def test_multiple_bots_metrics(self):
        """Endpoint should handle multiple bot metrics."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.bot_metrics import BotMetrics
        from fastapi import FastAPI

        metrics1 = BotMetrics(bot_name="clawdmatt")
        metrics1.increment("messages_received", amount=50)

        metrics2 = BotMetrics(bot_name="clawdjarvis")
        metrics2.increment("messages_received", amount=100)

        metrics3 = BotMetrics(bot_name="clawdfriday")
        metrics3.increment("messages_received", amount=75)

        aggregator = MetricsAggregator([metrics1, metrics2, metrics3])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics/json", headers={"X-API-Key": "test-key"})

        data = response.json()

        assert "clawdmatt" in data["bots"]
        assert "clawdjarvis" in data["bots"]
        assert "clawdfriday" in data["bots"]

    def test_json_includes_aggregates(self):
        """JSON endpoint should include aggregate statistics."""
        from api.metrics import create_metrics_router
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.bot_metrics import BotMetrics
        from fastapi import FastAPI

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=100)
        metrics.record_timing("handle", 0.5)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        app = FastAPI()
        router = create_metrics_router(exporter, api_key="test-key")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/metrics/json", headers={"X-API-Key": "test-key"})

        data = response.json()

        # Should include aggregate totals
        assert "totals" in data
        assert "total_messages_received" in data["totals"]
