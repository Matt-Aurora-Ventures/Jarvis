from __future__ import annotations

import json

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


def test_history_uses_browser_like_headers(perps_client, monkeypatch):
    client, _ = perps_client
    captured: dict[str, str] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"s":"ok","t":[],"o":[],"h":[],"l":[],"c":[]}'

    def _fake_urlopen(req, timeout=15):
        for key, value in req.header_items():
            captured[key.lower()] = value
        return _FakeResponse()

    monkeypatch.setattr(perps_api.urllib.request, "urlopen", _fake_urlopen)

    response = client.get("/api/perps/history/SOL-USD?resolution=15")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["market"] == "SOL-USD"
    assert isinstance(payload["candles"], list)

    assert captured.get("accept") == "application/json"
    assert captured.get("user-agent")
    assert captured.get("referer") == "https://www.tradingview.com/"
    assert captured.get("origin") == "https://www.tradingview.com"
    assert captured.get("accept-language", "").startswith("en-US")
