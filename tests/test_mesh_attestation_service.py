import pytest

from services.compute.mesh_attestation_service import MeshAttestationService


@pytest.mark.asyncio
async def test_commit_state_hash_uses_executor_when_enabled():
    calls = []

    async def _executor(action, payload):
        calls.append((action, payload))
        return {"ok": True, "signature": "sig-123", "slot": 99}

    service = MeshAttestationService(
        enabled=True,
        program_id="Jarv1sMesh111111111111111111111111111111111",
        keypair_path="dummy.json",
        executor=_executor,
    )

    result = await service.commit_state_hash("ab" * 32)
    assert result["status"] == "committed"
    assert result["signature"] == "sig-123"
    assert calls and calls[0][0] == "commit_state_hash"


@pytest.mark.asyncio
async def test_commit_state_hash_returns_disabled_when_flag_off():
    service = MeshAttestationService(enabled=False)
    result = await service.commit_state_hash("ab" * 32)
    assert result["status"] == "disabled"
    assert result["reason"] == "mesh_attestation_disabled"


@pytest.mark.asyncio
async def test_on_mesh_hash_commits_when_callback_enabled():
    calls = []

    async def _executor(action, payload):
        calls.append((action, payload))
        return {"ok": True, "signature": "sig-abc"}

    service = MeshAttestationService(
        enabled=True,
        program_id="Jarv1sMesh111111111111111111111111111111111",
        keypair_path="dummy.json",
        commit_on_receive=True,
        executor=_executor,
    )

    result = await service.on_mesh_hash(
        "cd" * 32,
        {"message_id": "m1"},
        {"reason": "ok", "state_hash": "cd" * 32},
    )
    assert result["status"] == "committed"
    assert calls and calls[0][0] == "commit_state_hash"
    status = service.get_status()
    assert status["metrics"]["commit_success"] == 1


@pytest.mark.asyncio
async def test_register_node_uses_executor():
    calls = []

    async def _executor(action, payload):
        calls.append((action, payload))
        return {"ok": True, "signature": "sig-register"}

    service = MeshAttestationService(
        enabled=True,
        program_id="Jarv1sMesh111111111111111111111111111111111",
        keypair_path="dummy.json",
        node_endpoint="nats://mesh-node:4222",
        executor=_executor,
    )
    result = await service.register_node()
    assert result["status"] == "registered"
    assert calls and calls[0][0] == "register_node"
