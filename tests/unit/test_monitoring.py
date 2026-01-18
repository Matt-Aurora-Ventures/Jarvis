"""
Unit tests for the comprehensive monitoring dashboard system.

Tests cover:
- Dashboard data collection
- Alert rules and routing
- Health check status
- WebSocket updates
- Historical data storage
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for metrics storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_supervisor_status():
    """Mock supervisor component status."""
    return {
        "buy_bot": {
            "status": "running",
            "restart_count": 0,
            "uptime": "12d 5h 30m",
            "last_error": None,
        },
        "sentiment_reporter": {
            "status": "running",
            "restart_count": 0,
            "uptime": "12d 5h 30m",
            "last_error": None,
        },
        "twitter_poster": {
            "status": "running",
            "restart_count": 3,
            "uptime": "1h 20m",
            "last_error": "OAuth token refresh failed",
        },
        "telegram_bot": {
            "status": "running",
            "restart_count": 0,
            "uptime": "12d 5h 30m",
            "last_error": None,
        },
        "autonomous_x": {
            "status": "stopped",
            "restart_count": 5,
            "uptime": None,
            "last_error": "Max restarts reached",
        },
    }


@pytest.fixture
def sample_alert_rules():
    """Sample alert rules configuration."""
    return {
        "rules": [
            {
                "id": "high_error_rate",
                "condition": "errors_per_hour > 10",
                "severity": "warning",
                "actions": ["telegram", "log"],
            },
            {
                "id": "component_down",
                "condition": "component.status == 'crashed'",
                "severity": "critical",
                "actions": ["telegram", "email"],
            },
            {
                "id": "high_drawdown",
                "condition": "portfolio.drawdown < -20",
                "severity": "warning",
                "actions": ["telegram"],
            },
            {
                "id": "api_latency_high",
                "condition": "api_latency_p95 > 1000",
                "severity": "warning",
                "actions": ["log"],
            },
        ]
    }


# =============================================================================
# DASHBOARD DATA COLLECTION TESTS
# =============================================================================

class TestDashboardMetrics:
    """Tests for dashboard metric collection."""

    def test_import_dashboard_module(self):
        """Test that dashboard module can be imported."""
        from core.monitoring.unified_dashboard import DashboardMetrics
        assert DashboardMetrics is not None

    def test_dashboard_metrics_init(self, temp_data_dir):
        """Test DashboardMetrics initialization."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))
        assert metrics is not None
        assert metrics.data_dir == temp_data_dir

    @pytest.mark.asyncio
    async def test_collect_trading_metrics(self, temp_data_dir):
        """Test trading metrics collection."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        # Mock the scorekeeper
        with patch('core.monitoring.unified_dashboard.get_scorekeeper') as mock:
            mock_scorekeeper = MagicMock()
            mock_scorekeeper.get_open_positions.return_value = [
                {"symbol": "SOL", "amount_usd": 1000},
                {"symbol": "RAY", "amount_usd": 500},
            ]
            mock_scorekeeper.get_performance_stats.return_value = {
                "win_rate": 0.65,
                "total_pnl": 1500.50,
                "avg_trade_pnl": 75.25,
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.12,
            }
            mock.return_value = mock_scorekeeper

            trading = await metrics.collect_trading_metrics()

            assert "active_positions" in trading
            assert "win_rate" in trading
            assert "total_pnl_usd" in trading
            assert trading["active_positions"] == 2
            assert trading["total_notional_usd"] == 1500

    @pytest.mark.asyncio
    async def test_collect_bot_metrics(self, temp_data_dir, mock_supervisor_status):
        """Test bot component metrics collection."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = mock_supervisor_status

            bots = await metrics.collect_bot_metrics()

            assert "components" in bots
            assert len(bots["components"]) == 5
            assert bots["components"]["buy_bot"]["status"] == "running"
            assert bots["components"]["autonomous_x"]["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_collect_performance_metrics(self, temp_data_dir):
        """Test performance metrics collection."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        with patch('core.monitoring.unified_dashboard.get_metrics_collector') as mock:
            mock_collector = MagicMock()
            mock_collector.get_latency_percentiles.return_value = MagicMock(
                p50_ms=120.0,
                p95_ms=234.0,
                p99_ms=450.0,
            )
            mock.return_value = mock_collector

            perf = await metrics.collect_performance_metrics()

            assert "api_latency_p95_ms" in perf
            assert "cpu_percent" in perf
            assert "memory_mb" in perf

    @pytest.mark.asyncio
    async def test_collect_log_metrics(self, temp_data_dir):
        """Test log metrics collection."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        with patch('core.monitoring.unified_dashboard.get_log_aggregator') as mock:
            mock_aggregator = MagicMock()
            mock_aggregator.get_stats.return_value = MagicMock(
                total_entries=1000,
                entries_by_level={"ERROR": 5, "WARNING": 23, "INFO": 972},
                error_rate_per_minute=0.2,
                top_errors=[{"pattern": "OAuth failed", "count": 3}],
            )
            mock.return_value = mock_aggregator

            logs = await metrics.collect_log_metrics()

            assert "errors_24h" in logs
            assert "warnings_24h" in logs
            assert "recent_error" in logs

    @pytest.mark.asyncio
    async def test_get_full_dashboard(self, temp_data_dir):
        """Test getting full dashboard data."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        # Use mocks for all data sources
        with patch.multiple(
            'core.monitoring.unified_dashboard',
            get_scorekeeper=MagicMock(return_value=MagicMock(
                get_open_positions=MagicMock(return_value=[]),
                get_performance_stats=MagicMock(return_value={}),
            )),
            get_supervisor_status=MagicMock(return_value={}),
            get_metrics_collector=MagicMock(return_value=MagicMock(
                get_latency_percentiles=MagicMock(return_value=MagicMock(
                    p50_ms=100, p95_ms=200, p99_ms=300
                )),
            )),
            get_log_aggregator=MagicMock(return_value=MagicMock(
                get_stats=MagicMock(return_value=MagicMock(
                    total_entries=0,
                    entries_by_level={},
                    error_rate_per_minute=0,
                    top_errors=[],
                )),
            )),
        ):
            dashboard = await metrics.get_dashboard_data()

            assert "trading" in dashboard
            assert "bots" in dashboard
            assert "performance" in dashboard
            assert "logs" in dashboard
            assert "timestamp" in dashboard


# =============================================================================
# ALERT RULES TESTS
# =============================================================================

class TestAlertRules:
    """Tests for alert rule evaluation."""

    def test_import_rule_engine(self):
        """Test that rule engine can be imported."""
        from core.monitoring.unified_dashboard import AlertRuleEngine
        assert AlertRuleEngine is not None

    def test_load_rules_from_config(self, temp_data_dir, sample_alert_rules):
        """Test loading rules from JSON config."""
        from core.monitoring.unified_dashboard import AlertRuleEngine

        # Write config file
        config_path = temp_data_dir / "alert_rules.json"
        with open(config_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRuleEngine(rules_file=str(config_path))

        assert len(engine.rules) == 4
        assert engine.rules[0]["id"] == "high_error_rate"

    def test_evaluate_error_rate_rule(self, temp_data_dir, sample_alert_rules):
        """Test evaluating error rate rule."""
        from core.monitoring.unified_dashboard import AlertRuleEngine

        config_path = temp_data_dir / "alert_rules.json"
        with open(config_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRuleEngine(rules_file=str(config_path))

        # Context where rule should trigger
        context = {"errors_per_hour": 15}

        triggered = engine.evaluate_rules(context)

        assert any(r["id"] == "high_error_rate" for r in triggered)

    def test_evaluate_component_down_rule(self, temp_data_dir, sample_alert_rules):
        """Test evaluating component down rule."""
        from core.monitoring.unified_dashboard import AlertRuleEngine

        config_path = temp_data_dir / "alert_rules.json"
        with open(config_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRuleEngine(rules_file=str(config_path))

        context = {
            "component": {"status": "crashed"},
        }

        triggered = engine.evaluate_rules(context)

        assert any(r["id"] == "component_down" for r in triggered)

    def test_evaluate_drawdown_rule(self, temp_data_dir, sample_alert_rules):
        """Test evaluating drawdown rule."""
        from core.monitoring.unified_dashboard import AlertRuleEngine

        config_path = temp_data_dir / "alert_rules.json"
        with open(config_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRuleEngine(rules_file=str(config_path))

        context = {
            "portfolio": {"drawdown": -25},
        }

        triggered = engine.evaluate_rules(context)

        assert any(r["id"] == "high_drawdown" for r in triggered)

    def test_no_false_triggers(self, temp_data_dir, sample_alert_rules):
        """Test that rules don't trigger when conditions aren't met."""
        from core.monitoring.unified_dashboard import AlertRuleEngine

        config_path = temp_data_dir / "alert_rules.json"
        with open(config_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRuleEngine(rules_file=str(config_path))

        # All values below thresholds
        context = {
            "errors_per_hour": 5,
            "component": {"status": "running"},
            "portfolio": {"drawdown": -10},
            "api_latency_p95": 500,
        }

        triggered = engine.evaluate_rules(context)

        assert len(triggered) == 0


# =============================================================================
# ALERT ROUTING TESTS
# =============================================================================

class TestAlertRouting:
    """Tests for alert notification routing."""

    def test_import_alert_router(self):
        """Test that alert router can be imported."""
        from core.monitoring.unified_dashboard import AlertRouter
        assert AlertRouter is not None

    @pytest.mark.asyncio
    async def test_route_to_telegram(self, temp_data_dir):
        """Test routing alert to Telegram."""
        from core.monitoring.unified_dashboard import AlertRouter

        router = AlertRouter()

        with patch.object(router, '_send_telegram') as mock_send:
            mock_send.return_value = True

            alert = {
                "id": "test_alert",
                "severity": "warning",
                "message": "Test alert message",
                "actions": ["telegram"],
            }

            result = await router.route_alert(alert)

            mock_send.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_route_to_log(self, temp_data_dir):
        """Test routing alert to log."""
        from core.monitoring.unified_dashboard import AlertRouter

        router = AlertRouter()

        with patch('core.monitoring.unified_dashboard.logger') as mock_logger:
            alert = {
                "id": "test_alert",
                "severity": "warning",
                "message": "Test alert message",
                "actions": ["log"],
            }

            result = await router.route_alert(alert)

            assert result is True
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_route_critical_alert(self, temp_data_dir):
        """Test critical alert routing (all channels)."""
        from core.monitoring.unified_dashboard import AlertRouter

        router = AlertRouter()

        with patch.object(router, '_send_telegram', return_value=True) as mock_tg:
            with patch.object(router, '_send_email', return_value=True) as mock_email:
                alert = {
                    "id": "critical_alert",
                    "severity": "critical",
                    "message": "Critical system failure",
                    "actions": ["telegram", "email"],
                }

                result = await router.route_alert(alert)

                mock_tg.assert_called_once()
                mock_email.assert_called_once()
                assert result is True


# =============================================================================
# HEALTH CHECK STATUS TESTS
# =============================================================================

class TestHealthCheckStatus:
    """Tests for health check status aggregation."""

    def test_import_health_aggregator(self):
        """Test that health aggregator can be imported."""
        from core.monitoring.unified_dashboard import HealthCheckAggregator
        assert HealthCheckAggregator is not None

    @pytest.mark.asyncio
    async def test_check_buy_bot_health(self):
        """Test buy bot health check."""
        from core.monitoring.unified_dashboard import HealthCheckAggregator

        aggregator = HealthCheckAggregator()

        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = {
                "buy_bot": {"status": "running", "restart_count": 0},
            }

            health = await aggregator.check_component("buy_bot")

            assert health["status"] == "healthy"
            assert health["component"] == "buy_bot"

    @pytest.mark.asyncio
    async def test_check_crashed_component(self):
        """Test health check for crashed component."""
        from core.monitoring.unified_dashboard import HealthCheckAggregator

        aggregator = HealthCheckAggregator()

        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = {
                "twitter_poster": {
                    "status": "stopped",
                    "restart_count": 100,
                    "last_error": "Max restarts reached",
                },
            }

            health = await aggregator.check_component("twitter_poster")

            assert health["status"] == "unhealthy"
            assert "Max restarts" in health.get("message", "")

    @pytest.mark.asyncio
    async def test_aggregate_all_health(self):
        """Test aggregating all component health."""
        from core.monitoring.unified_dashboard import HealthCheckAggregator

        aggregator = HealthCheckAggregator()

        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = {
                "buy_bot": {"status": "running", "restart_count": 0},
                "telegram_bot": {"status": "running", "restart_count": 0},
                "twitter_poster": {"status": "stopped", "restart_count": 100},
            }

            overall = await aggregator.get_overall_health()

            assert "status" in overall
            assert "components" in overall
            # One unhealthy component should make overall degraded
            assert overall["status"] in ["degraded", "unhealthy"]


# =============================================================================
# HISTORICAL DATA TESTS
# =============================================================================

class TestHistoricalData:
    """Tests for historical metrics storage."""

    def test_import_metrics_store(self):
        """Test that metrics store can be imported."""
        from core.monitoring.unified_dashboard import MetricsStore
        assert MetricsStore is not None

    def test_store_metric(self, temp_data_dir):
        """Test storing a metric."""
        from core.monitoring.unified_dashboard import MetricsStore

        store = MetricsStore(data_dir=str(temp_data_dir))

        store.record("win_rate", 0.65, {"source": "trading"})

        # Should be stored in memory
        metrics = store.get_recent("win_rate", minutes=5)
        assert len(metrics) == 1
        assert metrics[0]["value"] == 0.65

    def test_store_metric_persistence(self, temp_data_dir):
        """Test metrics persist to file."""
        from core.monitoring.unified_dashboard import MetricsStore

        store = MetricsStore(data_dir=str(temp_data_dir))

        # Record some metrics
        store.record("api_latency", 150.0)
        store.record("api_latency", 200.0)
        store.record("api_latency", 175.0)

        # Force flush
        store.flush()

        # Check file exists
        files = list((temp_data_dir / "metrics").glob("*.jsonl"))
        assert len(files) > 0

    def test_query_historical_data(self, temp_data_dir):
        """Test querying historical data."""
        from core.monitoring.unified_dashboard import MetricsStore

        store = MetricsStore(data_dir=str(temp_data_dir))

        # Record metrics over time
        for i in range(10):
            store.record("error_count", i)

        # Query
        results = store.get_history("error_count", days=1)

        assert len(results) == 10
        assert results[-1]["value"] == 9

    def test_retention_cleanup(self, temp_data_dir):
        """Test old data cleanup based on retention."""
        from core.monitoring.unified_dashboard import MetricsStore

        store = MetricsStore(
            data_dir=str(temp_data_dir),
            retention_days=7,
        )

        # Create old metric file
        old_file = temp_data_dir / "metrics" / "old_metrics.jsonl"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        old_file.write_text('{"metric": "test"}\n')

        # Modify timestamp to be old
        old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
        os.utime(old_file, (old_time, old_time))

        # Cleanup should remove old file
        store.cleanup_old_data()

        assert not old_file.exists()


# =============================================================================
# WEBSOCKET TESTS
# =============================================================================

class TestWebSocketUpdates:
    """Tests for WebSocket real-time updates."""

    def test_import_websocket_manager(self):
        """Test that websocket manager can be imported."""
        from core.monitoring.unified_dashboard import WebSocketManager
        assert WebSocketManager is not None

    @pytest.mark.asyncio
    async def test_broadcast_metrics(self):
        """Test broadcasting metrics to connected clients."""
        from core.monitoring.unified_dashboard import WebSocketManager

        manager = WebSocketManager()

        # Mock WebSocket client
        mock_ws = AsyncMock()
        await manager.connect(mock_ws)

        # Broadcast metrics
        metrics = {"cpu_percent": 12.5, "memory_mb": 456}
        await manager.broadcast(metrics)

        mock_ws.send_json.assert_called_with(metrics)

    @pytest.mark.asyncio
    async def test_client_disconnect(self):
        """Test handling client disconnection."""
        from core.monitoring.unified_dashboard import WebSocketManager

        manager = WebSocketManager()

        mock_ws = AsyncMock()
        await manager.connect(mock_ws)

        assert len(manager.clients) == 1

        await manager.disconnect(mock_ws)

        assert len(manager.clients) == 0


# =============================================================================
# DASHBOARD SERVER TESTS
# =============================================================================

class TestDashboardServer:
    """Tests for the dashboard HTTP server."""

    def test_import_server(self):
        """Test that server module can be imported."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        assert create_dashboard_app is not None

    @pytest.mark.asyncio
    async def test_health_endpoint(self, temp_data_dir):
        """Test /health endpoint."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        app = create_dashboard_app(data_dir=str(temp_data_dir))

        # Mock supervisor to return some components
        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = {
                "buy_bot": {"status": "running", "restart_count": 0},
            }

            async with TestClient(TestServer(app)) as client:
                resp = await client.get("/health")
                # Accept both 200 (healthy/degraded) and 503 (unknown/unhealthy)
                assert resp.status in [200, 503]

                data = await resp.json()
                assert "status" in data

    @pytest.mark.asyncio
    async def test_trading_metrics_endpoint(self, temp_data_dir):
        """Test /metrics/trading endpoint."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        app = create_dashboard_app(data_dir=str(temp_data_dir))

        with patch('core.monitoring.unified_dashboard.get_scorekeeper') as mock:
            mock.return_value = MagicMock(
                get_open_positions=MagicMock(return_value=[]),
                get_performance_stats=MagicMock(return_value={}),
            )

            async with TestClient(TestServer(app)) as client:
                resp = await client.get("/metrics/trading")
                assert resp.status == 200

                data = await resp.json()
                assert "active_positions" in data

    @pytest.mark.asyncio
    async def test_bots_metrics_endpoint(self, temp_data_dir):
        """Test /metrics/bots endpoint."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        app = create_dashboard_app(data_dir=str(temp_data_dir))

        with patch('core.monitoring.unified_dashboard.get_supervisor_status') as mock:
            mock.return_value = {"buy_bot": {"status": "running"}}

            async with TestClient(TestServer(app)) as client:
                resp = await client.get("/metrics/bots")
                assert resp.status == 200

                data = await resp.json()
                assert "components" in data

    @pytest.mark.asyncio
    async def test_alerts_endpoint(self, temp_data_dir, sample_alert_rules):
        """Test /alerts endpoint."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        # Write config
        config_dir = temp_data_dir / "config"
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "alert_rules.json", "w") as f:
            json.dump(sample_alert_rules, f)

        app = create_dashboard_app(
            data_dir=str(temp_data_dir),
            config_dir=str(config_dir),
        )

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/alerts")
            assert resp.status == 200

            data = await resp.json()
            assert "active_alerts" in data
            assert "rules" in data

    @pytest.mark.asyncio
    async def test_history_endpoint(self, temp_data_dir):
        """Test /metrics/history endpoint."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        app = create_dashboard_app(data_dir=str(temp_data_dir))

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/metrics/history?metric=win_rate&days=7")
            assert resp.status == 200

            data = await resp.json()
            assert "metric" in data
            assert "data" in data

    @pytest.mark.asyncio
    async def test_dashboard_html(self, temp_data_dir):
        """Test dashboard HTML page."""
        from core.monitoring.unified_dashboard import create_dashboard_app
        from aiohttp.test_utils import TestClient, TestServer

        app = create_dashboard_app(data_dir=str(temp_data_dir))

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/")
            assert resp.status == 200

            text = await resp.text()
            assert "JARVIS" in text or "Dashboard" in text


# =============================================================================
# SENSITIVE DATA PROTECTION TESTS
# =============================================================================

class TestSensitiveDataProtection:
    """Tests for sensitive data protection."""

    @pytest.mark.asyncio
    async def test_no_api_keys_in_response(self, temp_data_dir):
        """Test that API keys are not exposed."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        # Set some env vars that should be hidden
        os.environ["SOME_API_KEY"] = "secret123"
        os.environ["WALLET_PRIVATE_KEY"] = "super_secret"

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        with patch.multiple(
            'core.monitoring.unified_dashboard',
            get_scorekeeper=MagicMock(return_value=MagicMock(
                get_open_positions=MagicMock(return_value=[]),
                get_performance_stats=MagicMock(return_value={}),
            )),
            get_supervisor_status=MagicMock(return_value={}),
            get_metrics_collector=MagicMock(return_value=MagicMock(
                get_latency_percentiles=MagicMock(return_value=MagicMock(
                    p50_ms=100, p95_ms=200, p99_ms=300
                )),
            )),
            get_log_aggregator=MagicMock(return_value=MagicMock(
                get_stats=MagicMock(return_value=MagicMock(
                    total_entries=0,
                    entries_by_level={},
                    error_rate_per_minute=0,
                    top_errors=[],
                )),
            )),
        ):
            data = await metrics.get_dashboard_data()

            data_str = json.dumps(data)

            # Should not contain sensitive data
            assert "secret123" not in data_str
            assert "super_secret" not in data_str
            assert "WALLET_PRIVATE_KEY" not in data_str

    @pytest.mark.asyncio
    async def test_no_wallet_addresses_in_response(self, temp_data_dir):
        """Test that wallet addresses are masked."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        # Mock with wallet addresses
        with patch.multiple(
            'core.monitoring.unified_dashboard',
            get_scorekeeper=MagicMock(return_value=MagicMock(
                get_open_positions=MagicMock(return_value=[
                    {
                        "symbol": "SOL",
                        "amount_usd": 1000,
                        "wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
                    }
                ]),
                get_performance_stats=MagicMock(return_value={}),
            )),
            get_supervisor_status=MagicMock(return_value={}),
            get_metrics_collector=MagicMock(return_value=MagicMock(
                get_latency_percentiles=MagicMock(return_value=MagicMock(
                    p50_ms=100, p95_ms=200, p99_ms=300
                )),
            )),
            get_log_aggregator=MagicMock(return_value=MagicMock(
                get_stats=MagicMock(return_value=MagicMock(
                    total_entries=0,
                    entries_by_level={},
                    error_rate_per_minute=0,
                    top_errors=[],
                )),
            )),
        ):
            data = await metrics.get_dashboard_data()
            data_str = json.dumps(data)

            # Full wallet address should not appear
            assert "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" not in data_str


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestConfiguration:
    """Tests for monitoring configuration."""

    def test_default_config(self, temp_data_dir):
        """Test default configuration values."""
        from core.monitoring.unified_dashboard import MonitoringConfig

        config = MonitoringConfig()

        assert config.enabled is True
        assert config.port == 8080
        assert config.retention_days == 30
        assert config.metrics_interval_seconds == 5

    def test_load_config_from_file(self, temp_data_dir):
        """Test loading config from JSON file."""
        from core.monitoring.unified_dashboard import MonitoringConfig

        config_data = {
            "enabled": True,
            "port": 9090,
            "retention_days": 60,
            "metrics_interval_seconds": 10,
        }

        config_path = temp_data_dir / "monitoring.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = MonitoringConfig.from_file(str(config_path))

        assert config.port == 9090
        assert config.retention_days == 60

    def test_config_from_env(self, temp_data_dir):
        """Test loading config from environment."""
        from core.monitoring.unified_dashboard import MonitoringConfig

        os.environ["MONITORING_PORT"] = "8081"
        os.environ["MONITORING_RETENTION_DAYS"] = "14"

        config = MonitoringConfig.from_env()

        assert config.port == 8081
        assert config.retention_days == 14

        # Cleanup
        del os.environ["MONITORING_PORT"]
        del os.environ["MONITORING_RETENTION_DAYS"]


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Tests for dashboard performance."""

    @pytest.mark.asyncio
    async def test_dashboard_response_time(self, temp_data_dir):
        """Test that dashboard responds within 500ms."""
        from core.monitoring.unified_dashboard import DashboardMetrics

        metrics = DashboardMetrics(data_dir=str(temp_data_dir))

        with patch.multiple(
            'core.monitoring.unified_dashboard',
            get_scorekeeper=MagicMock(return_value=MagicMock(
                get_open_positions=MagicMock(return_value=[]),
                get_performance_stats=MagicMock(return_value={}),
            )),
            get_supervisor_status=MagicMock(return_value={}),
            get_metrics_collector=MagicMock(return_value=MagicMock(
                get_latency_percentiles=MagicMock(return_value=MagicMock(
                    p50_ms=100, p95_ms=200, p99_ms=300
                )),
            )),
            get_log_aggregator=MagicMock(return_value=MagicMock(
                get_stats=MagicMock(return_value=MagicMock(
                    total_entries=0,
                    entries_by_level={},
                    error_rate_per_minute=0,
                    top_errors=[],
                )),
            )),
        ):
            start = time.time()
            await metrics.get_dashboard_data()
            elapsed = (time.time() - start) * 1000

            assert elapsed < 500, f"Dashboard took {elapsed:.1f}ms (limit: 500ms)"
