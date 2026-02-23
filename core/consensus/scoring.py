"""Consensus scoring helpers for multi-model arena synthesis."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


_REASONING_MARKERS = (
    "because",
    "therefore",
    "however",
    "if",
    "then",
    "risk",
    "assumption",
    "evidence",
)


@dataclass(frozen=True)
class ConsensusThresholds:
    """Thresholds and priors used by consensus scoring."""

    semantic_min: float = 0.58
    reasoning_min: float = 0.25
    confidence_min: float = 0.45
    priors: Dict[str, float] | None = None

    def prior_for(self, provider: str) -> float:
        if not self.priors:
            return 1.0
        return float(self.priors.get(provider, 1.0))


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def semantic_similarity(a: str, b: str) -> float:
    """Lightweight Jaccard token overlap."""
    at = set(tokenize(a))
    bt = set(tokenize(b))
    if not at or not bt:
        return 0.0
    return len(at & bt) / len(at | bt)


def reasoning_heuristic(text: str) -> float:
    """Heuristic score based on logical structure markers and sentence depth."""
    lowered = text.lower()
    marker_hits = sum(1 for marker in _REASONING_MARKERS if marker in lowered)
    sentence_count = max(1, len(re.findall(r"[.!?]", text)))
    length_factor = min(len(tokenize(text)) / 120.0, 1.0)
    return min(1.0, (marker_hits / len(_REASONING_MARKERS)) * 0.6 + length_factor * 0.4) / math.sqrt(sentence_count / 2)


def extract_confidence(text: str) -> float:
    """Extract confidence from text using common formats.

    Supports:
    - "confidence: 0.81"
    - "81% confidence"
    - falls back to neutral 0.5
    """
    lowered = text.lower()
    decimal_match = re.search(r"confidence\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?)", lowered)
    if decimal_match:
        return float(decimal_match.group(1))

    pct_match = re.search(r"(\d{1,3})\s*%\s*confidence", lowered)
    if pct_match:
        pct = max(0, min(100, int(pct_match.group(1))))
        return pct / 100.0

    if "high confidence" in lowered:
        return 0.8
    if "low confidence" in lowered:
        return 0.3
    return 0.5


def score_candidates(candidates: Sequence[Dict[str, str]], thresholds: ConsensusThresholds | None = None) -> List[Dict[str, float | str | bool]]:
    """Score model outputs and mark candidates that pass the consensus floor."""
    thresholds = thresholds or ConsensusThresholds()
    if not candidates:
        return []

    texts = [c.get("response", "") for c in candidates]
    scored: List[Dict[str, float | str | bool]] = []

    for idx, candidate in enumerate(candidates):
        provider = candidate.get("provider", "unknown")
        current = texts[idx]
        similarities = [semantic_similarity(current, other) for i, other in enumerate(texts) if i != idx]
        semantic = sum(similarities) / len(similarities) if similarities else 0.0
        reasoning = reasoning_heuristic(current)
        confidence = extract_confidence(current)
        prior = thresholds.prior_for(provider)

        blended = (semantic * 0.45 + reasoning * 0.35 + confidence * 0.20) * prior
        passes = semantic >= thresholds.semantic_min and reasoning >= thresholds.reasoning_min and confidence >= thresholds.confidence_min

        scored.append(
            {
                "provider": provider,
                "semantic": semantic,
                "reasoning": reasoning,
                "confidence": confidence,
                "prior": prior,
                "score": blended,
                "passes_threshold": passes,
            }
        )

    return sorted(scored, key=lambda item: float(item["score"]), reverse=True)
