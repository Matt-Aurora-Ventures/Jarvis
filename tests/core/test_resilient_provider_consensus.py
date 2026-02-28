from core.resilient_provider import ResilientProviderChain


def test_default_providers_include_consensus_and_nosana():
    chain = ResilientProviderChain()
    names = [p.name for p in chain.providers]
    assert "consensus" in names
    assert "nosana" in names


import pytest


@pytest.mark.asyncio
async def test_execute_consensus_passes_gsd_metadata(monkeypatch):
    chain = ResilientProviderChain()
    seen = {}

    async def _fake_execute_builtin(provider_name, prompt, *, models=None, metadata=None):
        seen["provider_name"] = provider_name
        seen["prompt"] = prompt
        seen["metadata"] = metadata
        return {"provider": provider_name, "result": "ok"}

    monkeypatch.setattr(chain, "_execute_builtin_provider", _fake_execute_builtin)
    result = await chain.execute_consensus(
        "Evaluate rollout",
        panel=["m1"],
        gsd_spec_enabled=True,
        gsd_context_ref="docs/operations/2026-02-28-notebooklm-50q-results.md",
    )

    assert result is not None
    assert seen["provider_name"] == "consensus"
    assert seen["metadata"]["gsd_spec_enabled"] is True


@pytest.mark.asyncio
async def test_execute_nosana_uses_payload_prompt_and_metadata(monkeypatch):
    chain = ResilientProviderChain()
    seen = {}

    async def _fake_execute_builtin(provider_name, prompt, *, models=None, metadata=None):
        seen["provider_name"] = provider_name
        seen["prompt"] = prompt
        seen["metadata"] = metadata
        return {"provider": provider_name, "result": "ok"}

    monkeypatch.setattr(chain, "_execute_builtin_provider", _fake_execute_builtin)
    monkeypatch.setenv("NOSANA_API_KEY", "test-key")

    result = await chain.execute_nosana(
        {"prompt": "heavy compute", "name": "test-job", "metadata": {"foo": "bar"}}
    )

    assert result is not None
    assert seen["provider_name"] == "nosana"
    assert seen["prompt"] == "heavy compute"
    assert seen["metadata"]["job_name"] == "test-job"
