"""Quick boot test — verifies service starts in fallback mode and API responds."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from unittest.mock import MagicMock

from services.investments.config import InvestmentConfig
from services.investments.fallback_runtime import FallbackOrchestrator
from services.investments.api import app, set_dependencies


def test_fallback_boot_and_health():
    from fastapi.testclient import TestClient

    cfg = InvestmentConfig()
    assert cfg.dry_run is True

    orch = FallbackOrchestrator(cfg)
    set_dependencies(orch, None, None)

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "investments"
    assert data["dry_run"] is True
    print("Health endpoint OK:", data)


def test_fallback_trigger_cycle():
    from fastapi.testclient import TestClient

    cfg = InvestmentConfig()
    orch = FallbackOrchestrator(cfg)
    set_dependencies(orch, None, None)

    client = TestClient(app)
    resp = client.post("/api/investments/trigger-cycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["action"] in ("HOLD", "REBALANCE")
    print("Trigger cycle OK:", data)


if __name__ == "__main__":
    test_fallback_boot_and_health()
    test_fallback_trigger_cycle()
    print("\nALL BOOT TESTS PASSED")
