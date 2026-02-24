import json

import pytest

import bots.health_endpoint as health_endpoint
import bots.supervisor as supervisor


@pytest.mark.asyncio
async def test_register_model_upgrader_job_schedules_3am_utc(monkeypatch):
    class DummyScheduler:
        def __init__(self):
            self.cron_expression = None
            self.started = False

        def schedule_cron(self, **kwargs):
            self.cron_expression = kwargs["cron_expression"]
            return "job-123"

        async def start(self):
            self.started = True

    class DummyUpgrader:
        def run_weekly_scan(self, candidates, force=False):
            return {"status": "completed", "candidate_count": len(candidates), "force": force}

    dummy_scheduler = DummyScheduler()
    monkeypatch.setenv("JARVIS_MODEL_UPGRADER_ENABLED", "true")
    monkeypatch.setattr("core.automation.scheduler.get_scheduler", lambda: dummy_scheduler)
    monkeypatch.setattr("jobs.model_upgrader._parse_candidate_specs", lambda _raw: [])
    monkeypatch.setattr("jobs.model_upgrader.ModelUpgrader", lambda: DummyUpgrader())

    await supervisor.register_model_upgrader_job()
    assert dummy_scheduler.cron_expression == "0 3 * * *"
    assert dummy_scheduler.started is True


@pytest.mark.asyncio
async def test_register_mesh_sync_listener_starts_when_enabled(monkeypatch):
    class DummyMeshSyncService:
        def __init__(self):
            self.started = False

        async def start_listener(self, **_kwargs):
            self.started = True
            return {"status": "listening"}

    dummy = DummyMeshSyncService()
    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_SHARED_KEY", "11" * 32)
    monkeypatch.setenv("JARVIS_MESH_NODE_PUBKEY", "Node111111111111111111111111111111111111")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: dummy)

    await supervisor.register_mesh_sync_listener()
    assert dummy.started is True


@pytest.mark.asyncio
async def test_register_mesh_sync_listener_wires_attestation_callback(monkeypatch):
    class DummyMeshSyncService:
        def __init__(self):
            self.kwargs = None

        async def start_listener(self, **kwargs):
            self.kwargs = kwargs
            return {"status": "listening"}

    class DummyAttestationService:
        enabled = True

        async def on_mesh_hash(self, state_hash, envelope, validation):
            return {"status": "committed", "state_hash": state_hash}

    mesh_service = DummyMeshSyncService()
    attestation_service = DummyAttestationService()

    monkeypatch.setattr(
        "services.compute.mesh_sync_service.get_mesh_sync_service",
        lambda: mesh_service,
    )
    monkeypatch.setattr(
        "services.compute.mesh_attestation_service.get_mesh_attestation_service",
        lambda: attestation_service,
    )

    await supervisor.register_mesh_sync_listener()
    assert mesh_service.kwargs is not None
    assert callable(mesh_service.kwargs.get("on_attestation"))


def test_runtime_capability_report_returns_component_matrix(monkeypatch):
    monkeypatch.setattr(
        "core.runtime_capabilities.build_runtime_capability_report",
        lambda: {"components": {"arena": {"status": "ready"}}},
    )
    monkeypatch.setattr(
        "core.runtime_capabilities.collect_degraded_mode_messages",
        lambda _report: [],
    )

    report = supervisor.runtime_capability_report()
    assert "arena" in report["components"]


@pytest.mark.asyncio
async def test_health_runtime_status_handler_returns_runtime_payload(monkeypatch):
    monkeypatch.setattr(
        "bots.health_endpoint._collect_runtime_status",
        lambda: {
            "components": {
                "arena": {"status": "ready"},
                "nosana": {"status": "disabled"},
            }
        },
    )

    response = await health_endpoint.runtime_status_handler(None)
    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["components"]["arena"]["status"] == "ready"


@pytest.mark.asyncio
async def test_health_handler_includes_runtime_matrix(monkeypatch):
    monkeypatch.setattr("bots.health_endpoint._collect_component_health", lambda: {"telegram_bot": {"status": "healthy"}})
    monkeypatch.setattr("bots.health_endpoint._collect_runtime_status", lambda: {"components": {"arena": {"status": "degraded"}}})

    response = await health_endpoint.health_handler(None)
    payload = json.loads(response.text)
    assert "runtime" in payload
    assert payload["runtime"]["components"]["arena"]["status"] == "degraded"
