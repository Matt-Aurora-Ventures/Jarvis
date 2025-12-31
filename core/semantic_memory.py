"""Lightweight semantic memory search with zero external dependencies."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from core import memory


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _score(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    token_set = set(tokens)
    overlap = sum(1 for token in query_tokens if token in token_set)
    if overlap == 0:
        return 0.0
    return overlap / math.sqrt(len(tokens))


def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    query_tokens = _tokenize(query or "")
    if not query_tokens:
        return []

    entries = memory.get_recent_entries() + memory.get_pending_entries()
    scored: List[Dict[str, Any]] = []

    for entry in entries:
        text = str(entry.get("text", ""))
        score = _score(query_tokens, text)
        if score <= 0:
            continue
        scored.append(
            {
                "text": text,
                "source": entry.get("source", ""),
                "timestamp": entry.get("timestamp", 0),
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda item: (item["score"], item["timestamp"]), reverse=True)
    return scored[: max(1, limit)]
