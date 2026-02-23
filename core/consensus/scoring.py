"""Hybrid response scoring for the consensus arena."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

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
    r"(highly|very|extremely|almost certain|strong evidence|clearly|definitely|99%|confident)",
    re.IGNORECASE,
)
_HEDGED_RE = re.compile(
    r"(not sure|maybe|possibly|uncertain|low confidence|could be|might)",
    re.IGNORECASE,
)

_LOGICAL_SIGNALS = (
    "1.",
    "2.",
    "3.",
    "firstly",
    "secondly",
    "therefore",
    "because",
    "however",
    "evidence",
    "data shows",
    "according to",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_numpy(matrix: Any) -> np.ndarray:
    if hasattr(matrix, "detach"):
        matrix = matrix.detach()
    if hasattr(matrix, "cpu"):
        matrix = matrix.cpu()
    return np.asarray(matrix, dtype=np.float32)


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe = np.where(norms == 0.0, 1.0, norms)
    return vectors / safe


def _lexical_similarity_matrix(texts: Sequence[str]) -> np.ndarray:
    size = len(texts)
    matrix = np.eye(size, dtype=np.float32)
    for i in range(size):
        for j in range(i + 1, size):
            score = float(SequenceMatcher(None, texts[i], texts[j]).ratio())
            matrix[i, j] = score
            matrix[j, i] = score
    return matrix


def _get_embedder() -> Optional[Any]:
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER

    try:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(BGE_MODEL_NAME)
        return _EMBEDDER
    except Exception as exc:  # pragma: no cover - optional dependency/runtime
        logger.warning("Embedding model unavailable; falling back to lexical similarity: %s", exc)
        return None


def _semantic_similarity_matrix(
    texts: Sequence[str],
    *,
    embedder: Optional[Any] = None,
) -> np.ndarray:
    if len(texts) < 2:
        return np.eye(len(texts), dtype=np.float32)

    model = embedder or _get_embedder()
    if model is None:
        return _lexical_similarity_matrix(texts)

    try:
        embeddings = model.encode(
            list(texts),
            convert_to_tensor=True,
            normalize_embeddings=True,
        )
    except TypeError:
        embeddings = model.encode(list(texts))
    except Exception as exc:  # pragma: no cover - optional runtime fallback
        logger.warning("Embedding encode failed; using lexical fallback: %s", exc)
        return _lexical_similarity_matrix(texts)

    matrix: Optional[np.ndarray] = None
    try:
        from sentence_transformers import util

        matrix = _to_numpy(util.cos_sim(embeddings, embeddings))
    except Exception:
        matrix = None

    if matrix is None or matrix.ndim != 2:
        vectors = _to_numpy(embeddings)
        if vectors.ndim != 2:
            return _lexical_similarity_matrix(texts)
        normalized = _normalize_vectors(vectors)
        matrix = normalized @ normalized.T

    if matrix.shape[0] != matrix.shape[1]:
        return _lexical_similarity_matrix(texts)

    return matrix


def _coerce_response_map(
    responses: Mapping[str, str] | Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    if isinstance(responses, Mapping):
        return {str(model): str(content or "") for model, content in responses.items()}

    output: Dict[str, str] = {}
    for idx, item in enumerate(responses):
        model = str(item.get("model", f"model_{idx}")) if isinstance(item, Mapping) else f"model_{idx}"
        content = str(item.get("content", "") or "") if isinstance(item, Mapping) else str(item or "")
        output[model] = content
    return output


def compute_semantic_agreement(
    responses: Mapping[str, str] | Sequence[str],
    *,
    embedder: Optional[Any] = None,
) -> float:
    """
    Compute average pairwise cosine similarity for responses.

    Returns the mean of the upper-triangle similarity values.
    """
    if isinstance(responses, Mapping):
        texts = [str(v or "") for v in responses.values()]
    else:
        texts = [str(v or "") for v in responses]

    if len(texts) < 2:
        return 1.0

    sim_matrix = _semantic_similarity_matrix(texts, embedder=embedder)
    if sim_matrix.size == 0:
        return 1.0

    mask = np.triu(np.ones_like(sim_matrix, dtype=bool), k=1)
    if not np.any(mask):
        return 1.0
    agreement = float(sim_matrix[mask].mean())
    return float(max(-1.0, min(1.0, agreement)))


def reasoning_quality_score(text: str) -> float:
    """0.0-1.0 structural depth heuristic for reasoning quality."""
    score = 0.0
    lowered = text.lower()
    word_count = len(lowered.split())

    if word_count > 450:
        score += 0.35
    elif word_count > 280:
        score += 0.25
    elif word_count > 150:
        score += 0.15

    if any(signal in lowered for signal in _LOGICAL_SIGNALS):
        score += 0.30

    if "risk" in lowered and ("mitigate" in lowered or "downside" in lowered or "upside" in lowered):
        score += 0.15

    return _clamp(score)


def extract_confidence_score(text: str) -> float:
    """Explicit confidence language score."""
    lowered = text.lower()
    high = len(_CONFIDENT_RE.findall(lowered))
    low = len(_HEDGED_RE.findall(lowered))

    if high >= 2 and low == 0:
        return 0.95
    if high >= 1:
        return 0.80
    if low >= 2:
        return 0.35
    return 0.60


def classify_consensus_tier(agreement_score: float) -> str:
    if agreement_score >= STRONG_CONSENSUS_THRESHOLD:
        return "strong"
    if agreement_score >= MODERATE_CONSENSUS_THRESHOLD:
        return "moderate"
    return "divergent"


def _similarity_to_others(
    models: Sequence[str],
    matrix: np.ndarray,
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if matrix.ndim != 2 or matrix.shape[0] != len(models):
        return {model: 1.0 for model in models}

    for idx, model in enumerate(models):
        row = np.delete(matrix[idx], idx)
        out[model] = float(row.mean()) if row.size else 1.0
    return out


def _model_prior(model_name: str, model_weights: Mapping[str, float]) -> float:
    lowered = model_name.lower()
    for key, weight in model_weights.items():
        if key in lowered:
            return float(weight)
    return 1.0


def score_responses(
    responses: Mapping[str, str] | Sequence[Dict[str, Any]],
    *,
    model_weights: Optional[Mapping[str, float]] = None,
    embedder: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Score model responses using semantic agreement + quality + confidence + priors.

    Final per-model score:
    0.55 * semantic_similarity_to_others
    + 0.25 * reasoning_quality
    + 0.12 * confidence
    + 0.08 * model_prior
    """
    response_map = _coerce_response_map(responses)
    model_names = list(response_map.keys())
    contents = list(response_map.values())
    if not contents:
        return {
            "agreement_score": 0.0,
            "consensus_tier": "divergent",
            "thresholds": {
                "strong": STRONG_CONSENSUS_THRESHOLD,
                "moderate": MODERATE_CONSENSUS_THRESHOLD,
            },
            "individual_scores": {},
            "best_model": None,
            "best_response": "",
            "raw_responses": {},
            "responses": [],
            "top_response": None,
        }

    weights = dict(model_weights or MODEL_PRIOR_WEIGHTS)
    matrix = _semantic_similarity_matrix(contents, embedder=embedder)
    agreement = compute_semantic_agreement(contents, embedder=embedder)
    tier = classify_consensus_tier(agreement)
    sim_to_others = _similarity_to_others(model_names, matrix)

    individual_scores: Dict[str, float] = {}
    ranked: List[Dict[str, Any]] = []
    for model_name in model_names:
        content = response_map[model_name]
        semantic_score = sim_to_others.get(model_name, agreement)
        reasoning = reasoning_quality_score(content)
        confidence = extract_confidence_score(content)
        prior = _model_prior(model_name, weights)

        final_score = (
            0.55 * semantic_score
            + 0.25 * reasoning
            + 0.12 * confidence
            + 0.08 * prior
        )
        bounded_score = _clamp(final_score)
        individual_scores[model_name] = round(bounded_score, 4)

        ranked.append(
            {
                "model": model_name,
                "content": content,
                "similarity_to_others": round(semantic_score, 4),
                "reasoning_score": round(reasoning, 4),
                "confidence_score": round(confidence, 4),
                "model_prior_weight": round(prior, 4),
                "total_score": round(bounded_score, 4),
            }
        )

    ranked.sort(key=lambda item: item["total_score"], reverse=True)
    best_model = ranked[0]["model"] if ranked else None
    best_response = response_map.get(best_model, "") if best_model else ""

    return {
        "agreement_score": round(agreement, 4),
        "consensus_tier": tier,
        "thresholds": {
            "strong": STRONG_CONSENSUS_THRESHOLD,
            "moderate": MODERATE_CONSENSUS_THRESHOLD,
        },
        "individual_scores": individual_scores,
        "best_model": best_model,
        "best_response": best_response,
        "raw_responses": response_map,
        "responses": ranked,
        "top_response": ranked[0] if ranked else None,
    }
