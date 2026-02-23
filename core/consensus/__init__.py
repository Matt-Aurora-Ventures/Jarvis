"""Consensus arena package for multi-model scoring and synthesis."""

from .scoring import (
    MODEL_PRIOR_WEIGHTS,
    MODERATE_CONSENSUS_THRESHOLD,
    STRONG_CONSENSUS_THRESHOLD,
    classify_consensus_tier,
    compute_semantic_agreement,
    extract_confidence_score,
    reasoning_quality_score,
    score_responses,
)
from .arena import PANEL, get_consensus, is_simple_query, synthesize_consensus

__all__ = [
    "PANEL",
    "get_consensus",
    "is_simple_query",
    "synthesize_consensus",
    "MODEL_PRIOR_WEIGHTS",
    "MODERATE_CONSENSUS_THRESHOLD",
    "STRONG_CONSENSUS_THRESHOLD",
    "classify_consensus_tier",
    "compute_semantic_agreement",
    "extract_confidence_score",
    "reasoning_quality_score",
    "score_responses",
]
