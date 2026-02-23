"""Bull/Bear Adversarial Debate — max 3 rounds of structured argument.

Bull (Claude) argues for rebalancing, Bear (ChatGPT) argues for holding.
Position changes require NEW evidence (anti-sycophancy).
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

import anthropic
from openai import AsyncOpenAI

logger = logging.getLogger("investments.consensus.debate")


class DebateThesis(TypedDict):
    position: str  # BULL or BEAR
    thesis: str
    evidence: list[str]
    proposed_action: str  # REBALANCE or HOLD
    proposed_weights: dict[str, float]
    confidence: float
    what_would_change_my_mind: str


class DebateRound(TypedDict):
    round_number: int
    bull_thesis: DebateThesis
    bear_thesis: DebateThesis
    positions_changed: bool


class AdversarialDebate:
    MAX_ROUNDS = 3

    def __init__(self, anthropic_key: str, openai_key: str) -> None:
        self.bull_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        self.bear_client = AsyncOpenAI(api_key=openai_key)

    async def run_debate(
        self,
        analyst_reports: dict[str, Any],
        current_basket: dict[str, Any],
        calibration_hints: str,
    ) -> list[DebateRound]:
        rounds: list[DebateRound] = []
        bull_history = ""
        bear_history = ""

        for round_num in range(1, self.MAX_ROUNDS + 1):
            bull = await self._get_bull_thesis(
                analyst_reports, current_basket, calibration_hints,
                bear_history, round_num,
            )
            bear = await self._get_bear_thesis(
                analyst_reports, current_basket, calibration_hints,
                bull_history, round_num,
            )

            rounds.append(
                DebateRound(
                    round_number=round_num,
                    bull_thesis=bull,
                    bear_thesis=bear,
                    positions_changed=False,
                )
            )

            bull_history += (
                f"\n--- Round {round_num} Bull ---\n"
                f"{bull['thesis']}\nEvidence: {bull['evidence']}"
            )
            bear_history += (
                f"\n--- Round {round_num} Bear ---\n"
                f"{bear['thesis']}\nEvidence: {bear['evidence']}"
            )

            # Early exit if consensus reached
            if abs(bull["confidence"] - bear["confidence"]) < 0.15:
                logger.info(
                    "Debate converged at round %d (spread %.2f)",
                    round_num,
                    abs(bull["confidence"] - bear["confidence"]),
                )
                break

        return rounds

    async def _get_bull_thesis(
        self, reports: dict, basket: dict, hints: str, opponent_history: str,
        round_num: int,
    ) -> DebateThesis:
        new_evidence_clause = (
            "You MUST cite NEW evidence not already presented to change your position."
            if round_num > 1
            else ""
        )
        prompt = f"""You are the BULL researcher. Your job: make the STRONGEST possible case for rebalancing the portfolio.

ANALYST REPORTS: {json.dumps(reports, default=str)[:3000]}
CURRENT BASKET: {json.dumps(basket, default=str)[:1500]}
PAST CALIBRATION: {hints[:500]}
BEAR'S ARGUMENTS SO FAR: {opponent_history[:1500]}

Round {round_num} of {self.MAX_ROUNDS}.
{new_evidence_clause}

Output JSON: {{"position":"BULL","thesis":"...","evidence":["..."],"proposed_action":"REBALANCE","proposed_weights":{{}},"confidence":0.0-1.0,"what_would_change_my_mind":"..."}}"""

        response = await self.bull_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            raw = response.content[0].text
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(stripped)
        except (json.JSONDecodeError, IndexError, AttributeError) as exc:
            logger.error("Bull thesis parse failed: %s", exc)
            return DebateThesis(
                position="BULL", thesis="Parse error", evidence=[],
                proposed_action="HOLD", proposed_weights={},
                confidence=0.0, what_would_change_my_mind="",
            )

    async def _get_bear_thesis(
        self, reports: dict, basket: dict, hints: str, opponent_history: str,
        round_num: int,
    ) -> DebateThesis:
        new_evidence_clause = (
            "You MUST cite NEW evidence not already presented to change your position."
            if round_num > 1
            else ""
        )
        prompt = f"""You are the BEAR researcher. Your job: make the STRONGEST possible case for holding/staying conservative.

ANALYST REPORTS: {json.dumps(reports, default=str)[:3000]}
CURRENT BASKET: {json.dumps(basket, default=str)[:1500]}
PAST CALIBRATION: {hints[:500]}
BULL'S ARGUMENTS SO FAR: {opponent_history[:1500]}

Round {round_num} of {self.MAX_ROUNDS}.
{new_evidence_clause}

Output JSON: {{"position":"BEAR","thesis":"...","evidence":["..."],"proposed_action":"HOLD","proposed_weights":{{}},"confidence":0.0-1.0,"what_would_change_my_mind":"..."}}"""

        response = await self.bear_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        try:
            return json.loads(response.choices[0].message.content)
        except (json.JSONDecodeError, IndexError) as exc:
            logger.error("Bear thesis parse failed: %s", exc)
            return DebateThesis(
                position="BEAR", thesis="Parse error", evidence=[],
                proposed_action="HOLD", proposed_weights={},
                confidence=0.0, what_would_change_my_mind="",
            )
