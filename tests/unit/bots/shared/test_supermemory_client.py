"""
Tests for bots/shared/supermemory_client.py hook pipeline helpers.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from bots.shared.supermemory_client import (
    MemoryEntry,
    MemoryType,
    SupermemoryClient,
    get_hook_telemetry,
)


@pytest.mark.asyncio
async def test_pre_recall_builds_dual_profile_prompt_block():
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    client.search = AsyncMock(
        return_value=[
            MemoryEntry(
                content="User trades only on Solana using Phantom wallet.",
                memory_type=MemoryType.LONG_TERM,
                bot_name="jarvis",
                timestamp="2026-02-23T00:00:00Z",
                metadata={"profile_kind": "static"},
                score=0.92,
            ),
            MemoryEntry(
                content="User is currently comparing staking versus LP yields on Orca.",
                memory_type=MemoryType.MID_TERM,
                bot_name="jarvis",
                timestamp="2026-02-23T00:00:01Z",
                metadata={"profile_kind": "dynamic"},
                score=0.84,
            ),
        ]
    )

    payload = await client.pre_recall("Should I stake SOL or provide liquidity?")

    assert "Static Profile" in payload["prompt_block"]
    assert "Dynamic Profile" in payload["prompt_block"]
    assert "Phantom wallet" in payload["prompt_block"]
    assert "staking versus LP" in payload["prompt_block"]


@pytest.mark.asyncio
async def test_post_response_stores_conversation_and_extracted_facts(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    client.add_with_container_tag = AsyncMock(return_value=True)
    client.add = AsyncMock(return_value=True)

    ok = await client.post_response(
        user_message="I only use Phantom on Solana for trading.",
        assistant_response="Understood. I will keep recommendations scoped to Solana and Phantom.",
    )

    assert ok is True
    client.add_with_container_tag.assert_awaited()
    assert client.add.await_count >= 1


@pytest.mark.asyncio
async def test_add_research_notebook_uses_research_container_tag(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    client.add_with_container_tag = AsyncMock(return_value=True)

    ok = await client.add_research_notebook(
        content="# Solana PoH Notes\n- Research summary",
        metadata={"source": "auto-notebook"},
    )

    assert ok is True
    client.add_with_container_tag.assert_awaited_once()
    call_kwargs = client.add_with_container_tag.await_args.kwargs
    assert call_kwargs["container_tag"] == "research_notebooks"


@pytest.mark.asyncio
async def test_pre_recall_records_hook_telemetry(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    from bots.shared import supermemory_client as sm

    sm._hook_telemetry.clear()
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    client.search = AsyncMock(
        return_value=[
            MemoryEntry(
                content="User prefers Solana-only trading.",
                memory_type=MemoryType.LONG_TERM,
                bot_name="jarvis",
                timestamp="2026-02-23T00:00:00Z",
                metadata={"profile_kind": "static"},
                score=0.95,
            ),
        ]
    )

    await client.pre_recall("What is my current strategy?")
    telemetry = get_hook_telemetry("jarvis")

    assert "pre_recall" in telemetry
    assert telemetry["pre_recall"]["query"] == "What is my current strategy?"
    assert telemetry["pre_recall"]["memory_count"] == 1


@pytest.mark.asyncio
async def test_post_response_records_hook_telemetry(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    from bots.shared import supermemory_client as sm

    sm._hook_telemetry.clear()
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")
    client.add_with_container_tag = AsyncMock(return_value=True)
    client.add = AsyncMock(return_value=True)

    await client.post_response(
        user_message="I only trade Solana with Phantom and focus on LP risk.",
        assistant_response="Understood, I will optimize around Solana LP strategies.",
        conversation_id="conv-1",
    )

    telemetry = get_hook_telemetry("jarvis")
    assert "post_response" in telemetry
    assert telemetry["post_response"]["conversation_id"] == "conv-1"
    assert telemetry["post_response"]["saved_conversation"] is True
    assert telemetry["post_response"]["success"] is True


@pytest.mark.asyncio
async def test_add_skips_mesh_when_internal_metadata_flag_set(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")

    class _Memories:
        async def add(self, **_kwargs):
            return {"ok": True}

    class _SDK:
        memories = _Memories()

    monkeypatch.setattr(client, "_get_async_client", lambda: _SDK())
    mesh_emit = AsyncMock(return_value={"status": "skipped", "reason": "mesh_internal"})
    monkeypatch.setattr(client, "_after_successful_write_emit_mesh", mesh_emit)

    ok = await client.add("internal event", metadata={"_mesh_internal": True})

    assert ok is True
    mesh_emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_keeps_write_success_when_mesh_emit_fails(monkeypatch):
    monkeypatch.setattr("bots.shared.supermemory_client._supermemory_available", True)
    client = SupermemoryClient(bot_name="jarvis", api_key="test-key")

    class _Memories:
        async def add(self, **_kwargs):
            return {"ok": True}

    class _SDK:
        memories = _Memories()

    monkeypatch.setattr(client, "_get_async_client", lambda: _SDK())
    mesh_emit = AsyncMock(side_effect=RuntimeError("mesh path failed"))
    monkeypatch.setattr(client, "_after_successful_write_emit_mesh", mesh_emit)

    ok = await client.add("user preference: solana only", metadata={"hook": "unit-test"})

    assert ok is True
    mesh_emit.assert_awaited_once()
