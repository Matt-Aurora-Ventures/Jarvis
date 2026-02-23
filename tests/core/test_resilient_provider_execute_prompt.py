import pytest

from core.resilient_provider import ResilientProviderChain, ProviderConfig


@pytest.mark.asyncio
async def test_execute_prompt_routes_consensus(monkeypatch):
    chain = ResilientProviderChain(
        providers=[ProviderConfig(name="consensus", priority=1, use_for=["complex"])],
    )

    async def fake_builtin(provider_name, prompt, **kwargs):
        return {"provider": provider_name, "result": {"winner": {"provider": "m1", "score": 0.9}}}

    monkeypatch.setattr(chain, "_execute_builtin_provider", fake_builtin)

    out = await chain.execute_prompt("compare these systems", task_type="complex")
    assert out["provider"] == "consensus"
    assert out["result"]["winner"]["provider"] == "m1"


@pytest.mark.asyncio
async def test_execute_prompt_uses_preferred_provider(monkeypatch):
    chain = ResilientProviderChain(
        providers=[
            ProviderConfig(name="consensus", priority=1, use_for=["complex"]),
            ProviderConfig(name="nosana", priority=2, use_for=["complex"]),
        ],
    )

    async def fake_builtin(provider_name, prompt, **kwargs):
        return {"provider": provider_name, "result": {"id": "job-123"}}

    monkeypatch.setattr(chain, "_execute_builtin_provider", fake_builtin)
    out = await chain.execute_prompt(
        "deep analysis",
        task_type="complex",
        metadata={"preferred_provider": "nosana"},
    )
    assert out["provider"] == "nosana"
