from core.consensus.scoring import (
    ConsensusThresholds,
    extract_confidence,
    reasoning_heuristic,
    score_candidates,
    semantic_similarity,
)


def test_similarity_and_reasoning_scores():
    assert semantic_similarity("alpha beta", "alpha gamma") > 0
    assert reasoning_heuristic("Because we have evidence. Therefore risk is lower.") > 0


def test_confidence_extraction():
    assert extract_confidence("confidence: 0.9") == 0.9
    assert extract_confidence("81% confidence") == 0.81


def test_score_candidates_respects_priors():
    thresholds = ConsensusThresholds(priors={"model-a": 1.2, "model-b": 0.9})
    scored = score_candidates(
        [
            {"provider": "model-a", "response": "confidence: 0.8 because therefore evidence"},
            {"provider": "model-b", "response": "confidence: 0.8 because therefore evidence"},
        ],
        thresholds=thresholds,
    )
    assert scored[0]["provider"] == "model-a"
