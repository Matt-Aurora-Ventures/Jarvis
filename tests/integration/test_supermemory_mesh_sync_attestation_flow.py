import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from bots.shared.supermemory_client import SupermemoryClient
from services.compute.mesh_attestation_service import MeshAttestationService
from services.compute.mesh_sync_service import MeshSyncService
from services.compute.nosana_client import NosanaClient


class _InMemoryTransport:
    def __init__(self, *, fail_publish: bool = False):
        self.fail_publish = fail_publish
        self.published: List[Tuple[str, str]] = []

    async def publish(self, subject: str, payload: str) -> None:
        if self.fail_publish:
            raise RuntimeError("publish_failed")
        self.published.append((subject, payload))

    async def subscribe(self, subject: str, callback):
        return {"subject": subject, "callback": callback}

    async def close(self) -> None:
        return None


class _FakeMemoriesAPI:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def add(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"ok": True}


class _FakeSupermemorySDK:
    def __init__(self):
        self.memories = _FakeMemoriesAPI()


def _read_outbox_statuses(path: Path) -> List[str]:
    if not path.exists():
        return []
    statuses: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        payload = json.loads(raw)
        if isinstance(payload, dict):
            statuses.append(str(payload.get("status", "")))
    return statuses


def _build_client(monkeypatch) -> SupermemoryClient:
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    sdk = _FakeSupermemorySDK()
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    monkeypatch.setattr(client, "_get_async_client", lambda: sdk)
    return client


def _build_attestor(commit_calls: List[str], *, fail_commit: bool = False) -> MeshAttestationService:
    async def _executor(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "commit_state_hash":
            commit_calls.append(str(payload.get("state_hash")))
            if fail_commit:
                return {"ok": False, "error": "solana_rpc_unavailable"}
            return {"ok": True, "signature": "sig-mock", "slot": 7}
        return {"ok": True, "signature": "sig-other", "slot": 7}

    return MeshAttestationService(
        enabled=True,
        program_id="Jarv1sMesh111111111111111111111111111111111",
        keypair_path="dummy.json",
        commit_on_receive=True,
        executor=_executor,
    )


@pytest.mark.asyncio
async def test_supermemory_add_triggers_publish_validate_attest_success(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    shared_key = "11" * 32
    transport = _InMemoryTransport()
    mesh_service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex=shared_key,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )
    commit_calls: List[str] = []
    attestor = _build_attestor(commit_calls)

    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: mesh_service)
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)

    client = _build_client(monkeypatch)
    ok = await client.add(
        "User prefers low-volatility Solana staking over high-risk LP farms.",
        metadata={"conversation_id": "conv-success"},
    )

    assert ok is True
    assert len(transport.published) == 1
    assert len(commit_calls) == 1
    assert all(
        status not in {"pending_publish", "pending_commit", "invalid_envelope"}
        for status in _read_outbox_statuses(outbox_path)
    )


@pytest.mark.asyncio
async def test_publish_failure_queues_pending_publish_but_write_succeeds(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    transport = _InMemoryTransport(fail_publish=True)
    mesh_service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex="22" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )
    commit_calls: List[str] = []
    attestor = _build_attestor(commit_calls)

    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: mesh_service)
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)

    client = _build_client(monkeypatch)
    ok = await client.add("New strategy note: rebalance LP exposure every Friday.")

    assert ok is True
    assert len(commit_calls) == 0
    assert "pending_publish" in _read_outbox_statuses(outbox_path)


@pytest.mark.asyncio
async def test_hash_tamper_blocks_attestation(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    mesh_service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=_InMemoryTransport(),
        shared_key_hex="33" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )
    commit_calls: List[str] = []
    attestor = _build_attestor(commit_calls)

    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: mesh_service)
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)
    monkeypatch.setattr(mesh_service, "validate_envelope", lambda _envelope: (False, "hash_mismatch"))

    client = _build_client(monkeypatch)
    ok = await client.add("Risk policy: never exceed 20% TVL concentration in one LP.")

    assert ok is True
    assert len(commit_calls) == 0
    assert "invalid_envelope" in _read_outbox_statuses(outbox_path)


@pytest.mark.asyncio
async def test_commit_failure_queues_pending_commit(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    mesh_service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=_InMemoryTransport(),
        shared_key_hex="44" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )
    commit_calls: List[str] = []
    attestor = _build_attestor(commit_calls, fail_commit=True)

    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: mesh_service)
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)

    client = _build_client(monkeypatch)
    ok = await client.add("Execution note: spread entry over 3 tranches during high volatility.")

    assert ok is True
    assert len(commit_calls) == 1
    assert "pending_commit" in _read_outbox_statuses(outbox_path)


@pytest.mark.asyncio
async def test_post_response_path_emits_mesh_events_without_recursion(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    transport = _InMemoryTransport()
    mesh_service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex="55" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )
    commit_calls: List[str] = []
    attestor = _build_attestor(commit_calls)

    monkeypatch.setenv("JARVIS_MESH_SYNC_ENABLED", "1")
    monkeypatch.setenv("JARVIS_MESH_ATTESTATION_ENABLED", "1")
    monkeypatch.setattr("services.compute.mesh_sync_service.get_mesh_sync_service", lambda: mesh_service)
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)

    client = _build_client(monkeypatch)
    user_message = (
        "I currently trade only on Solana and prefer lower drawdown strategies with Phantom wallet."
    )
    assistant_response = (
        "Acknowledged. I will focus on lower-risk Solana strategies and avoid high-volatility setups."
    )
    facts = client.extract_candidate_facts(user_message, assistant_response)

    ok = await client.post_response(
        user_message=user_message,
        assistant_response=assistant_response,
        conversation_id="conv-post-response",
    )

    assert ok is True
    assert len(transport.published) == 1 + len(facts)

    published_before = len(transport.published)
    internal_ok = await client.add(
        "Internal mesh telemetry event.",
        metadata={"_mesh_internal": True},
    )
    assert internal_ok is True
    assert len(transport.published) == published_before
