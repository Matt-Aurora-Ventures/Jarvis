import asyncio
import json

import pytest

from services.compute.mesh_sync_service import MeshSyncService
from services.compute.mesh_attestation_service import MeshAttestationService
from services.compute.nosana_client import NosanaClient


class _InMemoryTransport:
    def __init__(self):
        self.subscribers = []
        self.published = []

    async def publish(self, subject: str, payload: str) -> None:
        self.published.append((subject, payload))
        for sub_subject, callback in list(self.subscribers):
            if sub_subject == subject:
                await callback(payload)

    async def subscribe(self, subject: str, callback):
        self.subscribers.append((subject, callback))
        return len(self.subscribers)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_publish_state_delta_builds_and_publishes_envelope():
    transport = _InMemoryTransport()
    service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex="11" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
    )

    result = await service.publish_state_delta({"topic": "staking-vs-lp"})
    assert result["published"] is True
    assert transport.published

    subject, payload = transport.published[0]
    decoded = json.loads(payload)
    assert subject == "jarvis.mesh.sync"
    assert decoded["state_hash"] == result["state_hash"]


@pytest.mark.asyncio
async def test_start_listener_validates_envelope_and_applies_delta():
    transport = _InMemoryTransport()
    shared_key_hex = "22" * 32

    received = []

    async def _on_delta(delta, metadata):
        received.append((delta, metadata))

    receiver = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex=shared_key_hex,
        node_pubkey="NodeReceiver11111111111111111111111111111111",
        enabled=True,
    )
    await receiver.start_listener(on_state_delta=_on_delta)

    sender = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex=shared_key_hex,
        node_pubkey="NodeSender111111111111111111111111111111111",
        enabled=True,
    )
    await sender.publish_state_delta({"focus": "liquidity", "risk": "medium"})

    assert len(received) == 1
    assert received[0][0]["focus"] == "liquidity"
    status = receiver.get_status()
    assert status["metrics"]["validated_messages"] == 1


@pytest.mark.asyncio
async def test_start_listener_rejects_invalid_envelope():
    transport = _InMemoryTransport()
    service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex="33" * 32,
        node_pubkey="NodeReceiver11111111111111111111111111111111",
        enabled=True,
    )

    called = False

    async def _on_delta(_delta, _metadata):
        nonlocal called
        called = True

    await service.start_listener(on_state_delta=_on_delta)
    await transport.publish("jarvis.mesh.sync", json.dumps({"invalid": "payload"}))

    assert called is False
    status = service.get_status()
    assert status["metrics"]["invalid_messages"] == 1


def test_validate_envelope_returns_reason_for_valid_and_invalid_packets(tmp_path):
    service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=_InMemoryTransport(),
        shared_key_hex="44" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=tmp_path / "mesh_outbox.jsonl",
    )

    envelope = service.nosana_client.build_mesh_sync_envelope(
        state_delta={"focus": "solana", "priority": "safety"},
        node_pubkey=service.node_pubkey,
        shared_key_hex=service.shared_key_hex,
        message_id="evt-validate",
    )

    ok, reason = service.validate_envelope(envelope)
    assert ok is True
    assert reason == "ok"

    envelope["state_hash"] = "00" * 32
    envelope["message_id"] = "evt-validate-tampered"
    ok, reason = service.validate_envelope(envelope)
    assert ok is False
    assert reason == "hash_mismatch"


@pytest.mark.asyncio
async def test_retry_pending_mesh_events_replays_publish_and_commit(monkeypatch, tmp_path):
    outbox_path = tmp_path / "mesh_outbox.jsonl"
    transport = _InMemoryTransport()
    service = MeshSyncService(
        nosana_client=NosanaClient(api_key="test-key"),
        transport=transport,
        shared_key_hex="55" * 32,
        node_pubkey="NodePublisher11111111111111111111111111111111",
        enabled=True,
        outbox_path=outbox_path,
    )

    pending_publish_envelope = service.nosana_client.build_mesh_sync_envelope(
        state_delta={"kind": "pending_publish", "sequence": 1},
        node_pubkey=service.node_pubkey,
        shared_key_hex=service.shared_key_hex,
        message_id="evt-publish-retry",
    )
    pending_commit_hash = "ab" * 32
    service.record_outbox_event(
        event_id="evt-publish-retry",
        status="pending_publish",
        state_hash=str(pending_publish_envelope["state_hash"]),
        state_delta={"kind": "pending_publish", "sequence": 1},
        envelope=pending_publish_envelope,
        reason="transport_unavailable",
    )
    service.record_outbox_event(
        event_id="evt-commit-retry",
        status="pending_commit",
        state_hash=pending_commit_hash,
        state_delta={"kind": "pending_commit", "sequence": 2},
        reason="solana_rpc_unavailable",
    )

    committed_hashes = []

    async def _executor(action, payload):
        if action == "commit_state_hash":
            committed_hashes.append(str(payload.get("state_hash")))
        return {"ok": True, "signature": "sig-retry", "slot": 123}

    attestor = MeshAttestationService(
        enabled=True,
        program_id="Jarv1sMesh111111111111111111111111111111111",
        keypair_path="dummy.json",
        executor=_executor,
    )
    monkeypatch.setattr("services.compute.mesh_attestation_service.get_mesh_attestation_service", lambda: attestor)

    summary = await service.retry_pending_mesh_events(limit=10)

    assert summary["retried"] == 2
    assert summary["published"] >= 1
    assert summary["committed"] == 2
    assert any(message_id == "evt-publish-retry" for _subject, message_id in summary["published_event_ids"])
    assert pending_commit_hash in committed_hashes
