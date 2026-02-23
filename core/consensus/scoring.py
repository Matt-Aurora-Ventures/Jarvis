"""Hybrid response scoring for the consensus arena."""

from __future__ import annotations

import logging
import math
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

BGE_MODEL_NAME = "BAAI/bge-large-en-v1.5"
STRONG_CONSENSUS_THRESHOLD = 0.82
MODERATE_CONSENSUS_THRESHOLD = 0.65

MODEL_PRIOR_WEIGHTS: Dict[str, float] = {
    "claude": 1.18,
    "grok": 1.12,
    "gemini": 1.08,
    "gpt": 1.00,
    "o3": 1.15,
}

_EMBEDDER: Optional[Any] = None

_CONFIDENT_RE = re.compile(
    r"\b(definitely|certainly|clearly|must|strongly|high confidence|will)\b",
    re.IGNORECASE,
)
_HEDGED_RE = re.compile(
    r"\b(maybe|might|could|uncertain|possibly|perhaps|unsure)\b",
    re.IGNORECASE,
)

_LOGICAL_SIGNALS = (
    "because",
    "therefore",
    "however",
    "if ",
    "then ",
    "first",
    "second",
    "finally",
)
_RISK_TERMS = ("risk", "downside", "exposure", "loss", "volatility")
_BENEFIT_TERMS = ("benefit", "upside", "advantage", "gain", "reward")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


def _lexical_agreement(responses: Sequence[str]) -> float:
    if len(responses) < 2:
        return 1.0
    scores: List[float] = []
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            scores.append(SequenceMatcher(None, responses[i], responses[j]).ratio())
    return float(sum(scores) / max(len(scores), 1))


def _get_embedder() -> Optional[Any]:
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    try:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(BGE_MODEL_NAME)
        return _EMBEDDER
    except Exception as exc:  # pragma: no cover - dependency/runtime fallback
        logger.warning("Embedding model unavailable, using lexical similarity fallback: %s", exc)
        return None


def compute_semantic_agreement(
    responses: Sequence[str],
    *,
    embedder: Optional[Any] = None,
) -> float:
    """Compute average pairwise semantic agreement in [0, 1]."""
    if len(responses) < 2:
        return 1.0

    model = embedder or _get_embedder()
    if model is None:
        return _lexical_agreement(responses)

    try:
        embeddings = model.encode(
            list(responses),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except TypeError:
        embeddings = model.encode(list(responses))
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.warning("Embedding encode failed, using lexical fallback: %s", exc)
        return _lexical_agreement(responses)

    vectors = np.asarray(embeddings, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] < 2:
        return _lexical_agreement(responses)

    pairwise: List[float] = []
    for i in range(vectors.shape[0]):
        for j in range(i + 1, vectors.shape[0]):
            pairwise.append(_cosine_similarity(vectors[i], vectors[j]))
    if not pairwise:
        return 1.0

    # Cosine range [-1, 1] -> normalized [0, 1].
    avg_cos = float(sum(pairwise) / len(pairwise))
    return _clamp((avg_cos + 1.0) / 2.0)


def reasoning_quality_score(text: str) -> float:
    """Heuristic reasoning score in [0, 1]."""
    text_l = text.lower()
    words = max(len(re.findall(r"\w+", text_l)), 1)

    length_score = min(words / 180.0, 1.0)
    logical_hits = sum(text_l.count(signal.strip()) for signal in _LOGICAL_SIGNALS)
    logical_score = min(logical_hits / 5.0, 1.0)

    structure_hits = (
        text.count("\n-")
        + text.count("\n1.")
        + text_l.count("first")
        + text_l.count("second")
        + text_l.count("finally")
    )
    structure_score = min(structure_hits / 3.0, 1.0)

    has_risk = any(term in text_l for term in _RISK_TERMS)
    has_benefit = any(term in text_l for term in _BENEFIT_TERMS)
    risk_benefit_score = 1.0 if (has_risk and has_benefit) else 0.0

    total = (
        0.35 * length_score
        + 0.30 * logical_score
        + 0.20 * structure_score
        + 0.15 * risk_benefit_score
    )
    return _clamp(total)


def extract_confidence_score(text: str) -> float:
    """Extract confidence from certainty/hedging language in [0, 1]."""
    high_hits = len(_CONFIDENT_RE.findall(text))
    hedge_hits = len(_HEDGED_RE.findall(text))

    score = 0.5 + min(high_hits * 0.12, 0.35) - min(hedge_hits * 0.10, 0.35)
    return _clamp(score)


def classify_consensus_tier(agreement_score: float) -> str:
    if agreement_score >= STRONG_CONSENSUS_THRESHOLD:
        return "strong"
    if agreement_score >= MODERATE_CONSENSUS_THRESHOLD:
        return "moderate"
    return "divergent"


def get_model_prior_weight(model_name: str) -> float:
    model_l = model_name.lower()
    for key, weight in MODEL_PRIOR_WEIGHTS.items():
        if key in model_l:
            return weight
    return 1.0


def score_responses(
    responses: Sequence[Dict[str, Any]],
    *,
    embedder: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Score and rank model responses for consensus synthesis.

    Input item format:
    {"model": "...", "content": "..."}
    """
    contents = [str(r.get("content", "") or "") for r in responses]
    agreement = compute_semantic_agreement(contents, embedder=embedder) if contents else 0.0
    tier = classify_consensus_tier(agreement)

    max_prior = max(MODEL_PRIOR_WEIGHTS.values())
    scored: List[Dict[str, Any]] = []
    for item in responses:
        model = str(item.get("model", "unknown"))
        content = str(item.get("content", "") or "")
        reasoning = reasoning_quality_score(content)
        confidence = extract_confidence_score(content)
        prior = get_model_prior_weight(model)
        prior_norm = prior / max_prior if max_prior > 0 else 1.0

        total = _clamp(
            (0.45 * reasoning)
            + (0.25 * confidence)
            + (0.20 * prior_norm)
            + (0.10 * agreement)
        )

        scored.append(
            {
                "model": model,
                "content": content,
                "agreement_score": round(agreement, 4),
                "reasoning_score": round(reasoning, 4),
                "confidence_score": round(confidence, 4),
                "model_prior_weight": round(prior, 4),
                "total_score": round(total, 6),
            }
        )

    scored.sort(key=lambda r: r["total_score"], reverse=True)

    return {
        "agreement_score": round(agreement, 4),
        "consensus_tier": tier,
        "thresholds": {
            "strong": STRONG_CONSENSUS_THRESHOLD,
            "moderate": MODERATE_CONSENSUS_THRESHOLD,
        },
        "responses": scored,
        "top_response": scored[0] if scored else None,
    }
