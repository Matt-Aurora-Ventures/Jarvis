"""Consensus arena: async fan-out + hybrid response scoring."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
from typing import Any, Dict, List, Mapping, Optional

import requests

from .scoring import score_responses

logger = logging.getLogger(__name__)

PANEL: Dict[str, str] = {
    "claude": "anthropic/claude-opus-4-6",
    "grok": "x-ai/grok-4.1",
    "gemini": "google/gemini-3.1-pro",
    "gpt": "openai/gpt-5.3-codex",
    "o3": "openai/o3-mini",
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
    """Call one model via LiteLLM completion endpoint."""
    try:
        import litellm  # type: ignore

        raw = await asyncio.to_thread(
            litellm.completion,
            model=model_id,
            messages=[{"role": "user", "content": query}],
            temperature=0.2,
            timeout=60,
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


async def _local_ollama_completion(query: str) -> str:
    """Fast-path local response for simple queries."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def _call() -> str:
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": query, "stream": False},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", "")).strip()

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.debug("[arena] local ollama completion failed: %s", exc)
        return ""


async def synthesize_consensus(
    query: str,
    responses: Mapping[str, str],
    scoring: Dict[str, Any],
    *,
    panel: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Use the highest-scored model to merge panel perspectives.
    """
    best_model = str(scoring.get("best_model") or "")
    best_response = str(scoring.get("best_response") or "")
    active_panel = dict(panel or PANEL)
    synth_model_id = active_panel.get(best_model, "")

    if not best_model or not synth_model_id:
        return {
            "model": best_model or None,
            "model_id": synth_model_id or None,
            "content": best_response,
            "agreement_score": scoring.get("agreement_score", 0.0),
            "consensus_tier": scoring.get("consensus_tier", "divergent"),
        }

    ranked = scoring.get("responses", [])
    ranked_context = "\n".join(
        f"- {item.get('model')} (score={item.get('total_score')}): {str(item.get('content', ''))[:1200]}"
        for item in ranked
    )
    prompt = (
        "You are Jarvis Consensus Synthesizer.\n"
        "Merge the perspectives into one coherent answer.\n"
        "Prefer the highest-ranked viewpoints, but preserve key risk/benefit tradeoffs.\n\n"
        f"Query:\n{query}\n\n"
        f"Panel Perspectives:\n{ranked_context}"
    )

    synthesized = best_response
    try:
        import litellm  # type: ignore

        raw = await asyncio.to_thread(
            litellm.completion,
            model=synth_model_id,
            messages=[
                {"role": "system", "content": "Synthesize a single actionable consensus answer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
            timeout=60,
        )
        candidate = _extract_litellm_text(raw)
        if candidate:
            synthesized = candidate
    except Exception as exc:  # pragma: no cover - runtime fallback
        logger.debug("[arena] synthesis call failed (%s); using best response", exc)

    return {
        "model": best_model,
        "model_id": synth_model_id,
        "content": synthesized,
        "agreement_score": scoring.get("agreement_score", 0.0),
        "consensus_tier": scoring.get("consensus_tier", "divergent"),
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

    Simple single-fact queries are routed to local Ollama.
    """
    if is_simple_query(query):
        local_answer = await _local_ollama_completion(query)
        return {
            "route": "local",
            "reason": "simple_query",
            "consensus": {"model": "ollama", "content": local_answer},
            "responses": [],
            "scoring": None,
        }

    responses = await _run_panel_calls(query=query, panel=panel)
    response_map = {
        str(item["model"]): str(item["content"])
        for item in responses
        if item.get("content")
    }
    if not response_map:
        return {
            "route": "arena",
            "reason": "no_successful_responses",
            "consensus": None,
            "responses": responses,
            "scoring": None,
        }

    scoring = score_responses(response_map)
    consensus = await synthesize_consensus(
        query=query,
        responses=response_map,
        scoring=scoring,
        panel=panel,
    )

    payload = {
        "query": query,
        "route": "arena",
        "responses": responses,
        "scoring": scoring,
        "consensus": consensus,
    }
    if scoring.get("consensus_tier") == "divergent":
        payload["perspectives"] = scoring.get("responses", [])

    await _maybe_await(_log_consensus_to_supermemory(payload))
    return payload


__all__ = ["PANEL", "get_consensus", "is_simple_query", "synthesize_consensus"]
