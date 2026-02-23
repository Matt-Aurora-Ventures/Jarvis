import pytest

from core.consensus.arena import get_consensus, is_simple_query, synthesize_consensus


def test_is_simple_query_classifier():
    assert is_simple_query("SOL price?")
    assert not is_simple_query("Compare staking versus LP on Orca with risk analysis.")


@pytest.mark.asyncio
async def test_get_consensus_routes_simple_queries_locally(monkeypatch):
    async def _should_not_run(*_args, **_kwargs):
        raise AssertionError("fan-out should not run for simple query")

    monkeypatch.setattr("core.consensus.arena._run_panel_calls", _should_not_run)
    result = await get_consensus("SOL price?")
    assert result["route"] == "local"
    assert result["consensus"] is None


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
            "responses": [
                {"model": "claude", "content": responses[0]["content"], "total_score": 0.9},
                {"model": "gpt", "content": responses[1]["content"], "total_score": 0.4},
            ],
            "top_response": {"model": "claude", "content": responses[0]["content"], "total_score": 0.9},
        }

    monkeypatch.setattr("core.consensus.arena.score_responses", _fake_score)
    monkeypatch.setattr("core.consensus.arena._log_consensus_to_supermemory", lambda *_args, **_kwargs: None)

    result = await get_consensus("Compare staking versus LP on Orca with risk analysis.")

    assert result["route"] == "arena"
    assert result["scoring"]["consensus_tier"] == "strong"
    assert result["consensus"]["model"] == "claude"


def test_synthesize_consensus_prefers_top_response():
    scored = {
        "top_response": {"model": "claude", "content": "Use staking with downside controls."},
        "consensus_tier": "moderate",
        "agreement_score": 0.74,
    }
    output = synthesize_consensus(scored)
    assert output["model"] == "claude"
    assert "staking" in output["content"].lower()
