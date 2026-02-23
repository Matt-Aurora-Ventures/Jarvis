import pytest

from bots.shared.supermemory_client import SupermemoryClient


@pytest.mark.asyncio
async def test_pre_recall_and_post_response_hooks(monkeypatch):
    client = SupermemoryClient(bot_name="jarvis", api_key="x", primary_profile="trading", secondary_profile="research")

    async def fake_search(*args, **kwargs):
        return []

    async def fake_add(*args, **kwargs):
        return True

    monkeypatch.setattr(client, "search", fake_search)
    monkeypatch.setattr(client, "add", fake_add)

    pre = await client.pre_recall("query", context={"session": "abc"})
    assert pre["profiles"]["primary"] == "trading"

    ok = await client.post_response("query", "response", context={"session": "abc"})
    assert ok is True
