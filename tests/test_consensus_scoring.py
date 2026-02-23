import math

import pytest

from core.consensus.scoring import (
    MODEL_PRIOR_WEIGHTS,
    MODERATE_CONSENSUS_THRESHOLD,
    STRONG_CONSENSUS_THRESHOLD,
    classify_consensus_tier,
    compute_semantic_agreement,
    extract_confidence_score,
    reasoning_quality_score,
    score_responses,
)


class _FakeEmbedder:
    def __init__(self, vectors):
        self._vectors = vectors

    def encode(self, _responses, **_kwargs):
        return self._vectors


def test_model_prior_weights_are_expected():
    assert MODEL_PRIOR_WEIGHTS["claude"] == 1.18
    assert MODEL_PRIOR_WEIGHTS["grok"] == 1.12
    assert MODEL_PRIOR_WEIGHTS["gemini"] == 1.08
    assert MODEL_PRIOR_WEIGHTS["gpt"] == 1.00
    assert MODEL_PRIOR_WEIGHTS["o3"] == 1.15


def test_consensus_thresholds_and_tiers():
    assert STRONG_CONSENSUS_THRESHOLD == pytest.approx(0.82)
    assert MODERATE_CONSENSUS_THRESHOLD == pytest.approx(0.65)
    assert classify_consensus_tier(0.82) == "strong"
    assert classify_consensus_tier(0.80) == "moderate"
    assert classify_consensus_tier(0.60) == "divergent"


def test_compute_semantic_agreement_from_embeddings():
    # Two very similar vectors and one opposite vector -> moderate agreement.
    vectors = [
        [1.0, 0.0],
        [0.9, 0.1],
        [-1.0, 0.0],
    ]
    score = compute_semantic_agreement(
        ["A", "B", "C"],
        embedder=_FakeEmbedder(vectors),
    )
    assert 0.20 < score < 0.55


def test_confidence_scoring_penalizes_hedging():
    high = extract_confidence_score("This is definitely the best approach and will work.")
    low = extract_confidence_score("This might work, maybe, but it is uncertain.")
    assert high > low
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0


def test_reasoning_quality_rewards_structure_and_risk_benefit():
    weak = reasoning_quality_score("Do this.")
    strong = reasoning_quality_score(
        "First, evaluate risk and benefit. Therefore choose staking because fees are lower. "
        "However monitor downside and rebalance if needed."
    )
    assert strong > weak
    assert 0.0 <= weak <= 1.0
    assert 0.0 <= strong <= 1.0


def test_score_responses_returns_ranked_payload(monkeypatch):
    monkeypatch.setattr("core.consensus.scoring.compute_semantic_agreement", lambda *_args, **_kwargs: 0.84)

    responses = [
        {"model": "gpt-5.3", "content": "Maybe do A."},
        {"model": "claude-opus", "content": "First evaluate risks and benefits. Therefore do B confidently."},
    ]

    result = score_responses(responses)
    assert result["agreement_score"] == pytest.approx(0.84)
    assert result["consensus_tier"] == "strong"
    assert len(result["responses"]) == 2
    assert result["responses"][0]["total_score"] >= result["responses"][1]["total_score"]
    assert result["top_response"]["model"] in {"gpt-5.3", "claude-opus"}
