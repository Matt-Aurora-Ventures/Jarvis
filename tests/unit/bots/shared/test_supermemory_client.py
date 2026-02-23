"""
Tests for bots/shared/supermemory_client.py hook pipeline helpers.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from bots.shared.supermemory_client import MemoryEntry, MemoryType, SupermemoryClient


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
