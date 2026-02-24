import json

from core import runtime_capabilities as rc


def test_build_runtime_capability_report_flags_degraded_arena_when_litellm_missing(monkeypatch):
    monkeypatch.setenv("JARVIS_USE_ARENA", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("core.runtime_capabilities.module_available", lambda name: name != "litellm")

    report = rc.build_runtime_capability_report()
    arena = report["components"]["arena"]
    assert arena["status"] == "degraded"
    assert arena["reason"] == "litellm_missing"
    assert arena["fallback"] == "local_ollama"


def test_build_runtime_capability_report_marks_nosana_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_USE_NOSANA", raising=False)

    report = rc.build_runtime_capability_report()
    nosana = report["components"]["nosana"]
    assert nosana["status"] == "disabled"
    assert nosana["reason"] == "flag_disabled"


def test_build_runtime_capability_report_marks_mesh_sync_degraded_when_key_missing(monkeypatch):
    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.delenv("JARVIS_MESH_SHARED_KEY", raising=False)
    monkeypatch.setenv("JARVIS_MESH_NODE_PUBKEY", "Node111111111111111111111111111111111111")

    report = rc.build_runtime_capability_report()
    mesh_sync = report["components"]["mesh_sync"]
    assert mesh_sync["status"] == "degraded"
    assert mesh_sync["reason"] == "mesh_shared_key_missing"


def test_build_runtime_capability_report_marks_attestation_degraded_when_program_missing(monkeypatch):
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.delenv("JARVIS_MESH_PROGRAM_ID", raising=False)
    monkeypatch.setenv("JARVIS_MESH_KEYPAIR_PATH", "data/mesh_keypair.json")
    monkeypatch.setattr("core.runtime_capabilities.module_available", lambda name: True)

    report = rc.build_runtime_capability_report()
    attestation = report["components"]["mesh_attestation"]
    assert attestation["status"] == "degraded"
    assert attestation["reason"] == "mesh_program_id_missing"


def test_model_upgrader_status_reads_last_scan(monkeypatch, tmp_path):
    state_path = tmp_path / "model_upgrader_state.json"
    state_path.write_text(
        json.dumps({"last_scan_at": "2026-02-23T03:00:00+00:00"}),
        encoding="utf-8",
    )

    status = rc._model_upgrader_status(state_path)
    assert status["status"] == "ready"
    assert status["last_scan_at"] == "2026-02-23T03:00:00+00:00"


def test_collect_degraded_mode_messages_lists_fallbacks():
    report = {
        "components": {
            "arena": {
                "status": "degraded",
                "reason": "litellm_missing",
                "fallback": "local_ollama",
            },
            "nosana": {
                "status": "disabled",
                "reason": "flag_disabled",
                "fallback": "skip_heavy_compute_route",
            },
        }
    }

    messages = rc.collect_degraded_mode_messages(report)
    assert "arena: degraded (litellm_missing) -> fallback=local_ollama" in messages
    assert "nosana: disabled (flag_disabled) -> fallback=skip_heavy_compute_route" in messages
