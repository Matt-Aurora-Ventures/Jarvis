"""Tests for investment API endpoints using FastAPI TestClient."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.investments.api import _adapt_reflection, app, set_dependencies


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.cfg = MagicMock()
    orch.cfg.dry_run = True
    orch.cfg.basket_id = "alpha"
    orch.cfg.admin_key = "test-admin-key"
    orch.safety = AsyncMock()
    orch._get_basket_state = AsyncMock(return_value={
        "tokens": {
            "ALVA": {"weight": 0.10, "price_usd": 0.50, "liquidity_usd": 200_000},
            "WETH": {"weight": 0.25, "price_usd": 3200.0, "liquidity_usd": 5_000_000},
            "USDC": {"weight": 0.65, "price_usd": 1.0, "liquidity_usd": 50_000_000},
        },
        "nav_usd": 200.0,
    })
    orch.run_cycle = AsyncMock(return_value={
        "status": "completed",
        "action": "HOLD",
        "confidence": 0.85,
    })
    return orch


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_redis():
    rds = AsyncMock()
    return rds


@pytest.fixture
def client(mock_orchestrator, mock_db, mock_redis):
    """Create a FastAPI test client with mocked dependencies."""
    from fastapi.testclient import TestClient
    set_dependencies(mock_orchestrator, mock_db, mock_redis)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "investments"
        assert data["dry_run"] is True


class TestBasketEndpoint:
    def test_get_basket(self, client):
        resp = client.get("/api/investments/basket")
        assert resp.status_code == 200
        data = resp.json()
        assert "tokens" in data
        assert "total_nav" in data
        assert data["total_nav"] == 200.0
        assert len(data["tokens"]) == 3
        # Verify adapter transforms tokens dict → array with frontend field names
        token = data["tokens"][0]
        assert "symbol" in token
        assert "mint" in token
        assert "weight" in token
        assert "usd_value" in token
        assert "price" in token


class TestDecisionsEndpoint:
    def test_get_decisions_empty(self, client):
        resp = client.get("/api/investments/decisions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestReflectionAdapter:
    def test_derives_dashboard_fields_from_runtime_reflection_payload(self):
        adapted = _adapt_reflection(
            {
                "id": 7,
                "ts": "2026-03-05T00:00:00+00:00",
                "calibration_hint": "Bias slightly toward HOLD after weak rebalance follow-through.",
                "data": {
                    "predicted_action": "REBALANCE",
                    "nav_change_pct": -0.021,
                    "agent_accuracy_scores": {
                        "grok_sentiment": 0.8,
                        "claude_risk": 0.6,
                    },
                },
            }
        )

        assert adapted["accuracy_pct"] == 70.0
        assert adapted["lessons"]
        assert adapted["adjustments"] == [
            "Bias slightly toward HOLD after weak rebalance follow-through."
        ]


class TestKillSwitchEndpoints:
    def test_get_kill_switch(self, client, mock_orchestrator):
        mock_orchestrator.safety.is_killed.return_value = False
        resp = client.get("/api/investments/kill-switch")
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_activate_requires_auth(self, client):
        resp = client.post("/api/investments/kill-switch/activate")
        assert resp.status_code == 401

    def test_activate_wrong_key(self, client):
        resp = client.post(
            "/api/investments/kill-switch/activate",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 403

    def test_activate_correct_key(self, client):
        resp = client.post(
            "/api/investments/kill-switch/activate",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    def test_deactivate_correct_key(self, client):
        resp = client.post(
            "/api/investments/kill-switch/deactivate",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False


class TestTriggerCycleEndpoint:
    def test_trigger_requires_auth(self, client):
        resp = client.post("/api/investments/trigger-cycle")
        assert resp.status_code == 401

    def test_trigger_with_auth(self, client):
        resp = client.post(
            "/api/investments/trigger-cycle",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"


class TestAuthOpenAccess:
    def test_no_admin_key_allows_all(self, mock_orchestrator, mock_db, mock_redis):
        """When admin_key is empty, all endpoints are open (dev mode)."""
        from fastapi.testclient import TestClient
        mock_orchestrator.cfg.admin_key = ""
        set_dependencies(mock_orchestrator, mock_db, mock_redis)
        client = TestClient(app)

        resp = client.post("/api/investments/kill-switch/activate")
        assert resp.status_code == 200

    def test_no_admin_key_blocks_live_writes(self, mock_orchestrator, mock_db, mock_redis):
        """Live mode must fail closed when admin auth is not configured."""
        from fastapi.testclient import TestClient
        mock_orchestrator.cfg.admin_key = ""
        mock_orchestrator.cfg.dry_run = False
        set_dependencies(mock_orchestrator, mock_db, mock_redis)
        client = TestClient(app)

        resp = client.post("/api/investments/trigger-cycle")
        assert resp.status_code == 503
