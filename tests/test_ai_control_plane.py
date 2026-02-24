import json

from core.ai_control_plane import build_ai_control_plane_snapshot


def test_build_ai_control_plane_snapshot_contains_all_panels(monkeypatch, tmp_path):
    consensus_log = tmp_path / "consensus_arena.jsonl"
    consensus_log.write_text(
        json.dumps(
            {
                "query": "compare staking and lp",
                "scoring": {"consensus_tier": "strong", "best_model": "claude"},
                "consensus": {"model": "claude", "content": "Use staking for lower risk."},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state_file = tmp_path / "model_upgrader_state.json"
    state_file.write_text(
        json.dumps(
            {
                "last_scan_at": "2026-02-24T03:00:00+00:00",
                "last_result": {"action": "skip", "reason": "insufficient_candidate_data"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("JARVIS_CONSENSUS_AUDIT_LOG", str(consensus_log))
    monkeypatch.setenv("JARVIS_RESTART_CMD", "echo restart")
    monkeypatch.setattr(
        "core.ai_control_plane.build_runtime_capability_report",
        lambda: {
            "generated_at": "2026-02-24T10:00:00+00:00",
            "components": {
                "arena": {"status": "ready", "reason": None, "fallback": None},
                "supermemory_hooks": {"status": "ready", "reason": None, "fallback": None},
                "nosana": {"status": "disabled", "reason": "flag_disabled", "fallback": "skip_heavy_compute_route"},
                "mesh_sync": {"status": "disabled", "reason": "flag_disabled", "fallback": "mesh_sync_bypassed"},
                "mesh_attestation": {
                    "status": "disabled",
                    "reason": "flag_disabled",
                    "fallback": "attestation_bypassed",
                },
                "model_upgrader": {
                    "status": "ready",
                    "reason": None,
                    "last_scan_at": "2026-02-24T03:00:00+00:00",
                    "state_file": str(state_file),
                },
            },
        },
    )
    monkeypatch.setattr(
        "core.ai_control_plane.get_provider_health_json",
        lambda: {"routes": {"consensus": {"enabled": True}, "nosana": {"enabled": False}}},
    )
    monkeypatch.setattr(
        "bots.shared.supermemory_client.get_hook_telemetry",
        lambda bot_name=None: {
            "pre_recall": {"static_profile": ["solana"], "dynamic_profile": ["lp vs staking"]},
            "post_response": {"facts_extracted": ["prefer lower risk staking"]},
        },
    )
    monkeypatch.setattr("core.ai_control_plane._active_local_model", lambda: "qwen2.5:7b")

    snapshot = build_ai_control_plane_snapshot()
    assert snapshot["status"] in {"healthy", "degraded"}
    assert set(snapshot["panels"].keys()) == {"consensus", "context", "upgrade", "compute"}
    assert snapshot["panels"]["consensus"]["latest_run"]["consensus"]["model"] == "claude"
    assert snapshot["panels"]["upgrade"]["last_result"]["action"] == "skip"
    assert snapshot["panels"]["context"]["static_profile"] == ["solana"]
    assert "mesh_sync" in snapshot["panels"]["compute"]
    assert "mesh_attestation" in snapshot["panels"]["compute"]


def test_ai_control_plane_endpoint_returns_snapshot(client, monkeypatch):
    monkeypatch.setattr(
        "core.ai_control_plane.build_ai_control_plane_snapshot",
        lambda: {
            "status": "healthy",
            "timestamp": "2026-02-24T10:00:00+00:00",
            "panels": {
                "consensus": {},
                "context": {},
                "upgrade": {},
                "compute": {},
            },
        },
    )

    response = client.get("/api/ai/control-plane")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert set(payload["panels"].keys()) == {"consensus", "context", "upgrade", "compute"}


def test_ai_control_plane_endpoint_degrades_on_error(client, monkeypatch):
    def _raise():
        raise RuntimeError("boom")

    monkeypatch.setattr("core.ai_control_plane.build_ai_control_plane_snapshot", _raise)

    response = client.get("/api/ai/control-plane")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert "boom" in payload["error"]
