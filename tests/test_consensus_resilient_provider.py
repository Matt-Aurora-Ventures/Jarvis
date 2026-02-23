import pytest

from core.resilient_provider import ResilientProviderChain


def test_resilient_provider_chain_includes_consensus_route():
    chain = ResilientProviderChain()
    consensus = next((p for p in chain.providers if p.name == "consensus"), None)
    assert consensus is not None
    assert "consensus" in consensus.use_for


def test_resilient_provider_chain_includes_nosana_route():
    chain = ResilientProviderChain()
    nosana = next((p for p in chain.providers if p.name == "nosana"), None)
    assert nosana is not None
    assert "heavy_compute" in nosana.use_for


@pytest.mark.asyncio
async def test_execute_consensus_delegates_to_arena(monkeypatch):
    chain = ResilientProviderChain()

    async def _fake_get_consensus(query, **_kwargs):
        return {"route": "arena", "consensus": {"model": "claude", "content": query}}

    monkeypatch.setattr("core.consensus.arena.get_consensus", _fake_get_consensus)

    result = await chain.execute_consensus("compare staking and lp")
    assert result["route"] == "arena"
    assert result["consensus"]["model"] == "claude"


@pytest.mark.asyncio
async def test_execute_consensus_respects_arena_toggle(monkeypatch):
    chain = ResilientProviderChain()
    monkeypatch.setenv("JARVIS_USE_ARENA", "0")

    result = await chain.execute_consensus("compare staking and lp")
    assert result["route"] == "local"
    assert result["reason"] == "arena_disabled"


@pytest.mark.asyncio
async def test_execute_nosana_delegates_to_client(monkeypatch):
    chain = ResilientProviderChain()

    class _DummyNosanaClient:
        is_configured = True

        async def run_heavy_workload(self, payload):
            return {"provider": "nosana", "status": "queued", "payload": payload}

    monkeypatch.setattr(
        "core.resilient_provider.get_nosana_client",
        lambda: _DummyNosanaClient(),
    )

    result = await chain.execute_nosana({"task": "consensus", "prompt": "compare routes"})
    assert result["provider"] == "nosana"
    assert result["status"] == "queued"
