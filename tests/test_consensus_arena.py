import pytest

from core.consensus.arena import get_consensus, is_simple_query, synthesize_consensus


def test_is_simple_query_classifier():
    assert is_simple_query("SOL price?")
    assert not is_simple_query("Compare staking versus LP on Orca with risk analysis.")


@pytest.mark.asyncio
async def test_get_consensus_routes_simple_queries_locally(monkeypatch):
    async def _should_not_run(*_args, **_kwargs):
        raise AssertionError("fan-out should not run for simple query")

    async def _fake_local(*_args, **_kwargs):
        return "SOL is 192.14"

    monkeypatch.setattr("core.consensus.arena._run_panel_calls", _should_not_run)
    monkeypatch.setattr("core.consensus.arena._local_ollama_completion", _fake_local)
    result = await get_consensus("SOL price?")
    assert result["route"] == "local"
    assert result["consensus"]["model"] == "ollama"
    assert "SOL" in result["consensus"]["content"]


@pytest.mark.asyncio
async def test_get_consensus_runs_arena_and_ranks(monkeypatch):
    async def _fake_panel(*_args, **_kwargs):
        return [
            {"model": "claude", "content": "First evaluate risk and reward. Therefore choose staking."},
            {"model": "gpt", "content": "Maybe LP is fine."},
        ]

    monkeypatch.setattr("core.consensus.arena._run_panel_calls", _fake_panel)

    def _fake_score(responses, **_kwargs):
        return {
            "agreement_score": 0.83,
            "consensus_tier": "strong",
            "best_model": "claude",
            "best_response": responses["claude"],
            "responses": [
                {"model": "claude", "content": responses["claude"], "total_score": 0.9},
                {"model": "gpt", "content": responses["gpt"], "total_score": 0.4},
            ],
            "top_response": {"model": "claude", "content": responses["claude"], "total_score": 0.9},
        }

    monkeypatch.setattr("core.consensus.arena.score_responses", _fake_score)
    monkeypatch.setattr("core.consensus.arena._log_consensus_to_supermemory", lambda *_args, **_kwargs: None)

    result = await get_consensus("Compare staking versus LP on Orca with risk analysis.")

    assert result["route"] == "arena"
    assert result["scoring"]["consensus_tier"] == "strong"
    assert result["consensus"]["model"] == "claude"


@pytest.mark.asyncio
async def test_synthesize_consensus_prefers_top_response_when_llm_unavailable():
    scored = {
        "best_model": "claude",
        "best_response": "Use staking with downside controls.",
        "top_response": {"model": "claude", "content": "Use staking with downside controls."},
        "consensus_tier": "moderate",
        "agreement_score": 0.74,
    }
    output = await synthesize_consensus(
        query="Should I stake SOL or LP?",
        responses={"claude": "Use staking with downside controls."},
        scoring=scored,
    )
    assert output["model"] == "claude"
    assert "staking" in output["content"].lower()
