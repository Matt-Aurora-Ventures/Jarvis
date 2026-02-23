import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.compute.nosana_client import NosanaClient


def test_select_market_prefers_cheapest_gpu_that_fits():
    client = NosanaClient(api_key="test-key")
    markets = [
        {"id": "m1", "price_per_hour": 0.9, "gpu_vram_gb": 24},
        {"id": "m2", "price_per_hour": 0.6, "gpu_vram_gb": 16},
        {"id": "m3", "price_per_hour": 0.4, "gpu_vram_gb": 8},
    ]

    selected = client.select_market(markets, required_vram_gb=12)
    assert selected["id"] == "m2"


def test_build_job_payload_uses_template(tmp_path):
    template_path = tmp_path / "ollama_consensus.json"
    template_path.write_text(
        json.dumps(
            {
                "name": "ollama-consensus",
                "input": {"model": "qwen2.5:1.5b", "prompt": ""},
            }
        ),
        encoding="utf-8",
    )

    client = NosanaClient(api_key="test-key")
    payload = client.build_job_payload(
        template_path=template_path,
        model="llama3.3:70b-q4",
        prompt="compare staking vs lp",
    )

    assert payload["input"]["model"] == "llama3.3:70b-q4"
    assert payload["input"]["prompt"] == "compare staking vs lp"


def test_submit_job_returns_job_metadata(monkeypatch):
    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "job-123", "status": "queued"}

        @staticmethod
        def raise_for_status():
            return None

    def _fake_post(url, json, headers, timeout):
        assert "jobs" in url
        assert headers["Authorization"].startswith("Bearer ")
        return _Resp()

    monkeypatch.setattr("services.compute.nosana_client.requests.post", _fake_post)

    client = NosanaClient(api_key="test-key")
    result = client.submit_job({"template_id": "ollama_consensus", "input": {"prompt": "x"}})
    assert result["id"] == "job-123"
    assert result["status"] == "queued"


def test_submit_ollama_job_selects_market_and_template(tmp_path, monkeypatch):
    template_path = tmp_path / "ollama_consensus.json"
    template_path.write_text(
        json.dumps({"template_id": "ollama_consensus", "input": {"model": "", "prompt": ""}}),
        encoding="utf-8",
    )

    client = NosanaClient(api_key="test-key")
    monkeypatch.setattr(
        client,
        "list_markets",
        lambda: [
            {"id": "cheap-small", "price_per_hour": 0.2, "gpu_vram_gb": 8},
            {"id": "cheap-large", "price_per_hour": 0.3, "gpu_vram_gb": 48},
        ],
    )
    monkeypatch.setattr(client, "submit_job", lambda payload: {"status": "queued", "payload": payload})

    result = client.submit_ollama_job(
        template_path=template_path,
        model="llama3.3:70b-q4",
        prompt="Compare staking vs LP",
    )
    assert result["status"] == "queued"
    assert result["market_id"] == "cheap-large"
    assert result["payload"]["input"]["model"] == "llama3.3:70b-q4"


def test_mesh_sync_envelope_encrypts_and_decrypts_state_delta():
    client = NosanaClient(api_key="test-key")
    shared_key_hex = "11" * 32
    state_delta = {"last_topic": "staking-vs-lp", "updated_at": "2026-02-23T00:00:00Z"}

    envelope = client.build_mesh_sync_envelope(
        state_delta=state_delta,
        node_pubkey="Node111111111111111111111111111111111111",
        shared_key_hex=shared_key_hex,
    )
    assert envelope["channel"] == "jarvis.mesh.sync"
    assert envelope["state_hash"] == client.state_hash(state_delta)

    decrypted = client.decrypt_sync_payload(
        envelope["encrypted_payload"],
        shared_key_hex=shared_key_hex,
    )
    assert decrypted["state_delta"] == state_delta
    assert decrypted["state_hash"] == envelope["state_hash"]
