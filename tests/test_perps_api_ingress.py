from __future__ import annotations

import json
import urllib.error

import pytest
from flask import Flask

import web.perps_api as perps_api


@pytest.fixture
def perps_client(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(perps_api, "_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(perps_api, "_INTENT_QUEUE", runtime_dir / "intent_queue.jsonl")
    monkeypatch.setattr(perps_api, "_INTENT_AUDIT", runtime_dir / "intent_audit.log")
    monkeypatch.setattr(perps_api, "_POSITIONS_STATE", runtime_dir / "positions_state.json")

    app = Flask(__name__)
    app.register_blueprint(perps_api.perps_bp)
    return app.test_client(), runtime_dir


def test_open_ingress_accepts_legacy_payload_and_writes_canonical_intent(perps_client):
    client, runtime_dir = perps_client
    response = client.post(
        "/api/perps/open",
        json={
            "idempotency_key": "legacy-open-1",
            "market": "SOL-USD",
            "side": "long",
            "collateral_usd": 100.0,
            "leverage": 3.0,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True

    lines = (runtime_dir / "intent_queue.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    queued = json.loads(lines[0])
    assert queued["intent_type"] == "open_position"
    assert queued["collateral_amount_usd"] == 100.0
    assert queued["size_usd"] == 300.0
    assert queued["collateral_mint"] == perps_api._DEFAULT_COLLATERAL_MINT


def test_open_ingress_enforces_idempotency(perps_client):
    client, _ = perps_client
    request = {
        "idempotency_key": "duplicate-key",
        "market": "SOL-USD",
        "side": "short",
        "collateral_amount_usd": 50.0,
        "leverage": 2.0,
    }
    first = client.post("/api/perps/open", json=request)
    second = client.post("/api/perps/open", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json().get("duplicate") is None
    assert second.get_json().get("duplicate") is True


def test_open_ingress_audits_invalid_payload(perps_client):
    client, runtime_dir = perps_client
    response = client.post(
        "/api/perps/open",
        json={"market": "SOL-USD", "side": "long", "collateral_usd": "bad", "leverage": 2},
    )
    assert response.status_code == 400

    audit_lines = (runtime_dir / "intent_audit.log").read_text(encoding="utf-8").splitlines()
    assert audit_lines
    latest = json.loads(audit_lines[-1])
    assert latest["event"] == "ingress_rejected"


def _raise_forbidden(*args, **kwargs):
    raise urllib.error.HTTPError(
        url="https://benchmarks.pyth.network/v1/shims/tradingview/history",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )


def test_history_uses_cached_snapshot_on_upstream_error(perps_client, monkeypatch):
    client, runtime_dir = perps_client
    cache_file = runtime_dir / "history_cache.json"
    monkeypatch.setattr(perps_api, "_HISTORY_CACHE_FILE", cache_file, raising=False)
    cache_file.write_text(
        json.dumps(
            {
                "SOL-USD:5": {
                    "cached_at": 1700000000,
                    "candles": [
                        {"time": 1700000000, "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(perps_api.urllib.request, "urlopen", _raise_forbidden)

    response = client.get("/api/perps/history/SOL-USD?resolution=5")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["market"] == "SOL-USD"
    assert payload["stale"] is True
    assert payload["status"] == 403
    assert payload["reason"] == "Forbidden"
    assert len(payload["candles"]) == 1


def test_ingress_health_exposes_upstream_meta(perps_client, monkeypatch):
    client, _ = perps_client
    monkeypatch.setattr(perps_api.urllib.request, "urlopen", _raise_forbidden)

    response = client.get("/api/perps/ingress-health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["status"] == 403
    assert payload["reason"] == "Forbidden"
