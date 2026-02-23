"""Consensus arena: async fan-out + hybrid response scoring."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional

from .scoring import score_responses

logger = logging.getLogger(__name__)

PANEL: Dict[str, str] = {
    "claude": "anthropic/claude-opus-4.1",
    "grok": "x-ai/grok-4",
    "gemini": "google/gemini-2.5-pro",
    "gpt": "openai/gpt-5.3-codex",
    "o3": "openai/o3",
}

_COMPLEX_QUERY_MARKERS = (
    "compare",
    "versus",
    "vs",
    "analyze",
    "risk",
    "benefit",
    "tradeoff",
    "architecture",
    "design",
    "code",
    "implement",
    "strategy",
    "should i",
    "explain",
)


def is_simple_query(query: str) -> bool:
    """Classify short single-fact lookups for local model routing."""
    text = (query or "").strip().lower()
    words = len(re.findall(r"\w+", text))
    if words == 0:
        return True
    has_complex_marker = any(marker in text for marker in _COMPLEX_QUERY_MARKERS)
    return words <= 8 and not has_complex_marker


def _extract_litellm_text(response: Any) -> str:
    try:
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        if message and getattr(message, "content", None):
            return str(message.content).strip()
        delta = getattr(choice, "delta", None)
        if delta and getattr(delta, "content", None):
            return str(delta.content).strip()
    except Exception:
        pass
    return ""


async def _call_model(model_alias: str, model_id: str, query: str) -> Dict[str, Any]:
    """Call one model via LiteLLM."""
    try:
        import litellm  # type: ignore

        messages = [
            {
                "role": "system",
                "content": (
                    "You are part of a consensus arena. Return concise, evidence-aware reasoning. "
                    "State risks and benefits."
                ),
            },
            {"role": "user", "content": query},
        ]

        if hasattr(litellm, "acompletion"):
            raw = await litellm.acompletion(model=model_id, messages=messages, timeout=45)
        else:  # pragma: no cover - sync fallback
            raw = await asyncio.to_thread(
                litellm.completion, model=model_id, messages=messages, timeout=45
            )
        content = _extract_litellm_text(raw)
        return {"model": model_alias, "model_id": model_id, "content": content}
    except Exception as exc:  # pragma: no cover - network/provider runtime
        logger.warning("[arena] %s failed: %s", model_alias, exc)
        return {"model": model_alias, "model_id": model_id, "content": "", "error": str(exc)}


async def _run_panel_calls(
    query: str,
    panel: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    active_panel = dict(panel or PANEL)
    tasks = [
        _call_model(model_alias=alias, model_id=model_id, query=query)
        for alias, model_id in active_panel.items()
    ]
    return await asyncio.gather(*tasks)


def synthesize_consensus(scored: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesize final consensus output.

    Current strategy uses the highest-scored response as the lead answer.
    """
    top = scored.get("top_response") or {}
    return {
        "model": top.get("model"),
        "content": top.get("content", ""),
        "agreement_score": scored.get("agreement_score", 0.0),
        "consensus_tier": scored.get("consensus_tier", "divergent"),
    }


async def _log_consensus_to_supermemory(payload: Dict[str, Any]) -> None:
    try:
        from bots.shared.supermemory_client import get_memory_client

        memory = get_memory_client("consensus_arena")
        if not memory.is_available:
            return

        await memory.add_shared_learning(
            content=json.dumps(payload, ensure_ascii=True),
            category="consensus_arena",
            metadata={"source": "core.consensus.arena"},
        )
    except Exception as exc:  # pragma: no cover - optional dependency/runtime
        logger.debug("[arena] supermemory logging skipped: %s", exc)


async def _maybe_await(result: Any) -> None:
    if inspect.isawaitable(result):
        await result


async def get_consensus(
    query: str,
    *,
    panel: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Run consensus arena for complex queries.

    Simple single-fact queries are routed to local model path.
    """
    if is_simple_query(query):
        return {
            "route": "local",
            "reason": "simple_query",
            "consensus": None,
            "responses": [],
            "scoring": None,
        }

    responses = await _run_panel_calls(query=query, panel=panel)
    successful = [r for r in responses if r.get("content")]
    if not successful:
        return {
            "route": "arena",
            "reason": "no_successful_responses",
            "consensus": None,
            "responses": responses,
            "scoring": None,
        }

    scoring = score_responses(successful)
    consensus = synthesize_consensus(scoring)

    payload = {
        "query": query,
        "route": "arena",
        "responses": responses,
        "scoring": scoring,
        "consensus": consensus,
    }
    await _maybe_await(_log_consensus_to_supermemory(payload))

    return payload


__all__ = ["PANEL", "get_consensus", "is_simple_query", "synthesize_consensus"]
