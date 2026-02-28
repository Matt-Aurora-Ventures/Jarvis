"""Async consensus arena with LiteLLM fan-out and supermemory logging."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional

from core.consensus.scoring import ConsensusThresholds, score_candidates

logger = logging.getLogger(__name__)

try:
    from litellm import acompletion
except Exception:  # pragma: no cover - dependency optional in tests
    acompletion = None

try:
    from bots.shared.supermemory_client import get_memory_client, MemoryType
except Exception:  # pragma: no cover
    get_memory_client = None
    MemoryType = None


class ConsensusArena:
    """Runs prompts across multiple models/providers and synthesizes best answer."""

    def __init__(
        self,
        models: Iterable[str],
        thresholds: Optional[ConsensusThresholds] = None,
        timeout_s: float = 45.0,
        memory_bot: str = "jarvis",
    ):
        self.models = list(models)
        self.thresholds = thresholds or ConsensusThresholds()
        self.timeout_s = timeout_s
        self.memory_bot = memory_bot

    async def _call_model(self, model: str, prompt: str) -> Dict[str, str]:
        if acompletion is None:
            raise RuntimeError("litellm is not installed")

        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=self.timeout_s,
        )
        content = response.choices[0].message.content
        return {"provider": model, "response": content or ""}

    async def fanout(self, prompt: str) -> List[Dict[str, str]]:
        tasks = [self._call_model(model, prompt) for model in self.models]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[Dict[str, str]] = []
        for model, item in zip(self.models, raw):
            if isinstance(item, Exception):
                logger.warning("Arena call failed for %s: %s", model, item)
                results.append({"provider": model, "response": f"ERROR: {item}"})
            else:
                results.append(item)
        return results

    def _prompt_with_gsd_context(
        self,
        prompt: str,
        *,
        gsd_spec_enabled: bool,
        gsd_context_ref: str | None,
    ) -> str:
        if not gsd_spec_enabled:
            return prompt
        lines = [
            "GSD Spec-Driven Evaluation:",
            "- Apply spec -> plan -> execute -> verify gates in the recommendation.",
            "- Explicitly call out blocking gates and next action.",
        ]
        if gsd_context_ref:
            lines.append(f"- Context reference: {gsd_context_ref}")
        lines.extend(["", prompt])
        return "\n".join(lines)

    async def run(
        self,
        prompt: str,
        *,
        gsd_spec_enabled: bool = False,
        gsd_context_ref: str | None = None,
    ) -> Dict[str, Any]:
        effective_prompt = self._prompt_with_gsd_context(
            prompt,
            gsd_spec_enabled=gsd_spec_enabled,
            gsd_context_ref=gsd_context_ref,
        )
        candidates = await self.fanout(effective_prompt)
        ranked = score_candidates(candidates, thresholds=self.thresholds)
        winner = ranked[0] if ranked else None

        synthesis = {
            "prompt": prompt,
            "effective_prompt": effective_prompt,
            "winner": winner,
            "ranked": ranked,
            "candidates": candidates,
            "consensus_reached": bool(winner and winner.get("passes_threshold")),
            "gsd_spec_enabled": gsd_spec_enabled,
            "gsd_context_ref": gsd_context_ref,
        }

        await self._log_to_supermemory(synthesis)
        return synthesis

    async def _log_to_supermemory(self, synthesis: Dict[str, Any]) -> None:
        if get_memory_client is None or MemoryType is None:
            return
        try:
            client = get_memory_client(self.memory_bot)
            winner = synthesis.get("winner") or {}
            ranked = synthesis.get("ranked") or []
            summary = (
                f"Consensus run winner={winner.get('provider')} score={winner.get('score')} "
                f"consensus={synthesis.get('consensus_reached')} candidates={len(ranked)}"
            )
            await client.add(summary, memory_type=MemoryType.MID_TERM, metadata={"source": "consensus_arena"})
        except Exception as exc:
            logger.debug("Failed to log consensus synthesis: %s", exc)
