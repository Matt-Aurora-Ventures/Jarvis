"""
Tests for enhanced API health check endpoints.

Tests comprehensive health monitoring including:
- Database connectivity
- External API availability
- Bot health status
- Cache status
- LLM provider health
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_state():
    """Mock core.state module."""
    with patch("api.routes.health.state") as mock:
        # Mock healthy state
        mock.read_state.return_value = {
            "component_status": {
                "telegram_bot": {"ok": True},
                "twitter_poster": {"ok": True},
                "autonomous_x": {"ok": True},
            }
        }
        yield mock


@pytest.fixture
def mock_birdeye():
    """Mock birdeye module."""
    with patch("api.routes.health.birdeye") as mock:
        # Mock successful price fetch
        mock.get_token_price.return_value = {
            "success": True,
            "data": {"value": 100.0}
        }
        yield mock


@pytest.fixture
def mock_jupiter_requests():
    """Mock requests for Jupiter API."""
    with patch("api.routes.health.requests") as mock:
        # Mock successful Jupiter response
        response = Mock()
        response.status_code = 200
        mock.get.return_value = response
        yield mock


@pytest.fixture
def mock_providers():
    """Mock LLM providers."""
    with patch("api.routes.health.check_provider_health") as mock:
        # Mock healthy provider status
        mock.return_value = {
            "groq": {"available": True, "status": "ok"},
            "openrouter": {"available": True, "status": "ok"},
            "ollama": {"available": False, "status": "not_running"},
        }
        yield mock


@pytest.fixture
def mock_cache():
    """Mock cache system."""
    with patch("api.routes.health.APICache") as mock_class:
        mock_instance = Mock()
        mock_instance.get_stats.return_value = {
            "hits": 100,
            "misses": 20,
            "hit_rate": 0.83
        }
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def client():
    """Create test client."""
    # Import here to avoid circular imports
    from api.fastapi_app import create_app
    app = create_app()
    return TestClient(app)


class TestHealthCheckEndpoint:
    """Test the main health check endpoint."""

    def test_health_check_all_healthy(
        self, client, mock_state, mock_birdeye, mock_jupiter_requests,
        mock_providers, mock_cache
    ):
        """Test health check when all subsystems are healthy."""
        response = client.get("/api/health/")

        assert response.status_code == 200
        data = response.json()

        # Check overall status
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "4.3.0"

        # Check subsystems
        assert "subsystems" in data
        subsystems = data["subsystems"]

        # Database should be healthy
        assert subsystems["database"]["healthy"] is True
        assert subsystems["database"]["status"] == "ok"

        # LLM providers should be healthy (2 available)
        assert subsystems["llm_providers"]["healthy"] is True

        # Check summary
        assert data["summary"]["total_subsystems"] == 8
        assert data["summary"]["healthy_subsystems"] > 0

    def test_health_check_degraded_state(self, client, mock_state, mock_providers):
        """Test health check with some degraded subsystems."""
        # Mock degraded Birdeye
        with patch("api.routes.health.birdeye") as mock_birdeye:
            mock_birdeye.get_token_price.return_value = {"success": False}

            response = client.get("/api/health/")

            assert response.status_code == 200
            data = response.json()

            # Should still be healthy overall (non-critical subsystem degraded)
            # But some subsystems unhealthy
            assert data["summary"]["degraded_subsystems"] > 0

    def test_health_check_database_down(self, client):
        """Test health check when database is down."""
        with patch("api.routes.health.state") as mock:
            mock.read_state.side_effect = Exception("Database connection failed")

            response = client.get("/api/health/")

            assert response.status_code == 200
            data = response.json()

            # Should be unhealthy (critical subsystem down)
            assert data["status"] == "unhealthy"
            assert data["subsystems"]["database"]["healthy"] is False
            assert data["subsystems"]["database"]["status"] == "down"

    def test_health_check_no_providers(self, client, mock_state):
        """Test health check when no LLM providers available."""
        with patch("api.routes.health.check_provider_health") as mock:
            mock.return_value = {
                "groq": {"available": False},
                "openrouter": {"available": False},
            }

            response = client.get("/api/health/")

            assert response.status_code == 200
            data = response.json()

            # Should be unhealthy (critical subsystem down)
            assert data["status"] == "unhealthy"
            assert data["subsystems"]["llm_providers"]["healthy"] is False


class TestQuickHealthCheck:
    """Test the quick health check endpoint."""

    def test_quick_health_ok(self, client, mock_state, mock_providers):
        """Test quick health check returns 200 when healthy."""
        response = client.get("/api/health/quick")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_quick_health_database_down(self, client, mock_providers):
        """Test quick health check returns 503 when database down."""
        with patch("api.routes.health.state") as mock:
            mock.read_state.side_effect = Exception("DB error")

            response = client.get("/api/health/quick")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] in ["unhealthy", "error"]

    def test_quick_health_providers_down(self, client, mock_state):
        """Test quick health check returns 503 when providers down."""
        with patch("api.routes.health.check_provider_health") as mock:
            mock.return_value = {}

            response = client.get("/api/health/quick")

            assert response.status_code == 503


class TestSubsystemHealthChecks:
    """Test individual subsystem health check functions."""

    def test_database_health_check_success(self, mock_state):
        """Test database health check when operational."""
        from api.routes.health import check_database_health

        health = check_database_health()

        assert health.healthy is True
        assert health.status == "ok"
        assert health.latency_ms is not None
        assert health.latency_ms >= 0

    def test_database_health_check_failure(self):
        """Test database health check when down."""
        from api.routes.health import check_database_health

        with patch("api.routes.health.state") as mock:
            mock.read_state.side_effect = Exception("Connection failed")

            health = check_database_health()

            assert health.healthy is False
            assert health.status == "down"
            assert "error" in health.message.lower()

    def test_birdeye_health_check_success(self, mock_birdeye):
        """Test Birdeye API health check when operational."""
        from api.routes.health import check_birdeye_api

        health = check_birdeye_api()

        assert health.healthy is True
        assert health.status == "ok"
        assert health.latency_ms is not None

    def test_birdeye_health_check_failure(self):
        """Test Birdeye health check when API fails."""
        from api.routes.health import check_birdeye_api

        with patch("api.routes.health.birdeye") as mock:
            mock.get_token_price.side_effect = Exception("API error")

            health = check_birdeye_api()

            assert health.healthy is False
            assert health.status == "down"

    def test_jupiter_health_check_success(self, mock_jupiter_requests):
        """Test Jupiter API health check when operational."""
        from api.routes.health import check_jupiter_api

        health = check_jupiter_api()

        assert health.healthy is True
        assert health.status == "ok"

    def test_jupiter_health_check_timeout(self):
        """Test Jupiter health check on timeout."""
        from api.routes.health import check_jupiter_api
        import requests

        with patch("api.routes.health.requests") as mock:
            mock.get.side_effect = requests.Timeout()

            health = check_jupiter_api()

            assert health.healthy is False
            assert health.status == "degraded"
            assert "timeout" in health.message.lower()

    def test_llm_providers_health_check(self, mock_providers):
        """Test LLM providers health check."""
        from api.routes.health import check_llm_providers

        health = check_llm_providers()

        assert health.healthy is True  # 2 providers available
        assert health.status == "ok"
        assert "metadata" in health.model_dump()
        assert "available_providers" in health.metadata

    def test_llm_providers_single_provider(self):
        """Test LLM health with only one provider."""
        from api.routes.health import check_llm_providers

        with patch("api.routes.health.check_provider_health") as mock:
            mock.return_value = {
                "groq": {"available": True},
                "openrouter": {"available": False},
                "ollama": {"available": False},
            }

            health = check_llm_providers()

            assert health.healthy is True
            assert health.status == "degraded"  # Only 1 provider
            assert "1/" in health.message

    def test_telegram_bot_health_running(self, mock_state):
        """Test Telegram bot health when running."""
        from api.routes.health import check_telegram_bot

        health = check_telegram_bot()

        assert health.healthy is True
        assert health.status == "ok"
        assert "running" in health.message.lower()

    def test_telegram_bot_health_error(self):
        """Test Telegram bot health when error state."""
        from api.routes.health import check_telegram_bot

        with patch("api.routes.health.state") as mock:
            mock.read_state.return_value = {
                "component_status": {
                    "telegram_bot": {
                        "ok": False,
                        "error": "Bot crashed"
                    }
                }
            }

            health = check_telegram_bot()

            assert health.healthy is False
            assert health.status == "degraded"
            assert "error" in health.message.lower()

    def test_twitter_bot_health_running(self, mock_state):
        """Test Twitter bot health when running."""
        from api.routes.health import check_twitter_bot

        health = check_twitter_bot()

        assert health.healthy is True
        assert health.status == "ok"

    def test_twitter_bot_health_disabled(self):
        """Test Twitter bot health when disabled."""
        from api.routes.health import check_twitter_bot

        with patch("api.routes.health.os") as mock_os:
            mock_os.getenv.return_value = "false"

            health = check_twitter_bot()

            assert health.healthy is True
            assert health.status == "ok"
            assert "disabled" in health.message.lower()

    def test_cache_health_check(self, mock_cache):
        """Test cache health check."""
        from api.routes.health import check_cache_status

        health = check_cache_status()

        assert health.healthy is True
        assert health.status == "ok"
        assert "hits" in health.metadata

    def test_grok_health_not_configured(self):
        """Test Grok health when not configured."""
        from api.routes.health import check_grok_api

        with patch("api.routes.health.secrets") as mock_secrets:
            mock_secrets.get_grok_key.return_value = None

            health = check_grok_api()

            assert health.healthy is True  # Not configured is OK
            assert health.status == "ok"
            assert "not configured" in health.message.lower()


class TestSubsystemEndpoint:
    """Test the subsystem-specific endpoint."""

    def test_get_subsystem_database(self, client, mock_state):
        """Test getting database subsystem health."""
        response = client.get("/api/health/subsystem/database")

        assert response.status_code == 200
        data = response.json()

        assert data["subsystem"] == "database"
        assert "health" in data
        assert data["health"]["healthy"] is True

    def test_get_subsystem_llm_providers(self, client, mock_providers):
        """Test getting LLM providers subsystem health."""
        response = client.get("/api/health/subsystem/llm_providers")

        assert response.status_code == 200
        data = response.json()

        assert data["subsystem"] == "llm_providers"
        assert data["health"]["healthy"] is True

    def test_get_subsystem_not_found(self, client):
        """Test getting non-existent subsystem."""
        response = client.get("/api/health/subsystem/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_subsystem_birdeye(self, client, mock_birdeye):
        """Test getting Birdeye subsystem health."""
        response = client.get("/api/health/subsystem/birdeye_api")

        assert response.status_code == 200
        data = response.json()

        assert data["subsystem"] == "birdeye_api"

    def test_get_subsystem_jupiter(self, client, mock_jupiter_requests):
        """Test getting Jupiter subsystem health."""
        response = client.get("/api/health/subsystem/jupiter_api")

        assert response.status_code == 200
        data = response.json()

        assert data["subsystem"] == "jupiter_api"


class TestHealthCheckIntegration:
    """Integration tests for health check system."""

    def test_health_check_response_structure(self, client, mock_state, mock_providers):
        """Test complete health check response structure."""
        response = client.get("/api/health/")

        assert response.status_code == 200
        data = response.json()

        # Required top-level fields
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "subsystems" in data
        assert "summary" in data

        # Subsystems should include all expected systems
        subsystems = data["subsystems"]
        expected_subsystems = [
            "database", "birdeye_api", "jupiter_api", "grok_api",
            "llm_providers", "telegram_bot", "twitter_bot", "cache"
        ]
        for subsystem in expected_subsystems:
            assert subsystem in subsystems
            # Each subsystem should have required fields
            assert "healthy" in subsystems[subsystem]
            assert "status" in subsystems[subsystem]
            assert "message" in subsystems[subsystem]

        # Summary should have counts
        summary = data["summary"]
        assert "total_subsystems" in summary
        assert "healthy_subsystems" in summary
        assert "degraded_subsystems" in summary
        assert "down_subsystems" in summary
        assert "check_latency_ms" in summary

    def test_health_check_latency_tracking(self, client, mock_state, mock_providers):
        """Test that latency is tracked for all checks."""
        response = client.get("/api/health/")

        assert response.status_code == 200
        data = response.json()

        # Overall check latency
        assert data["summary"]["check_latency_ms"] >= 0

        # Individual subsystem latencies
        for subsystem_name, subsystem in data["subsystems"].items():
            if subsystem["latency_ms"] is not None:
                assert subsystem["latency_ms"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
