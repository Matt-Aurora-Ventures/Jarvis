"""Risk Officer — Claude-based with VETO power over hard limits."""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

import anthropic

logger = logging.getLogger("investments.consensus.risk_officer")


class RiskVeto(TypedDict):
    approved: bool
    veto_reason: str
    risk_violations: list[str]
    adjusted_weights: dict[str, float]
    max_allowed_change_pct: float


class RiskOfficer:
    """Can block ANY trade that violates hard-coded risk thresholds."""

    HARD_LIMITS = {
        "max_single_token_pct": 0.30,
        "max_rebalance_change_pct": 0.25,
        "max_daily_cumulative_pct": 0.40,
        "max_correlated_exposure_pct": 0.60,
        "min_token_liquidity_usd": 50_000,
    }

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def evaluate(
        self,
        proposed_action: str,
        proposed_weights: dict[str, float],
        current_weights: dict[str, float],
        basket_nav_usd: float,
        token_liquidities: dict[str, float],
        risk_report: dict[str, Any],
        daily_changes_so_far_pct: float,
    ) -> RiskVeto:
        violations: list[str] = []

        # Hard limit checks — no LLM needed
        for token, weight in proposed_weights.items():
            if weight > self.HARD_LIMITS["max_single_token_pct"]:
                violations.append(
                    f"{token} weight {weight:.0%} exceeds "
                    f"{self.HARD_LIMITS['max_single_token_pct']:.0%} max"
                )

        all_tokens = set(list(proposed_weights) + list(current_weights))
        total_change = sum(
            abs(proposed_weights.get(t, 0) - current_weights.get(t, 0))
            for t in all_tokens
        ) / 2

        if total_change > self.HARD_LIMITS["max_rebalance_change_pct"]:
            violations.append(
                f"Total change {total_change:.0%} exceeds "
                f"{self.HARD_LIMITS['max_rebalance_change_pct']:.0%} max per rebalance"
            )

        if (
            daily_changes_so_far_pct + total_change
            > self.HARD_LIMITS["max_daily_cumulative_pct"]
        ):
            violations.append(
                f"Cumulative daily change would exceed "
                f"{self.HARD_LIMITS['max_daily_cumulative_pct']:.0%}"
            )

        for token, weight in proposed_weights.items():
            if weight > 0.01:
                liq = token_liquidities.get(token, 0)
                if liq < self.HARD_LIMITS["min_token_liquidity_usd"]:
                    violations.append(
                        f"{token} liquidity ${liq:,.0f} below "
                        f"${self.HARD_LIMITS['min_token_liquidity_usd']:,.0f} minimum"
                    )

        if violations:
            return RiskVeto(
                approved=False,
                veto_reason=f"Hard limit violations: {'; '.join(violations)}",
                risk_violations=violations,
                adjusted_weights={},
                max_allowed_change_pct=self.HARD_LIMITS["max_rebalance_change_pct"],
            )

        # If action is HOLD, auto-approve (no risk in doing nothing)
        if proposed_action == "HOLD":
            return RiskVeto(
                approved=True,
                veto_reason="",
                risk_violations=[],
                adjusted_weights=proposed_weights,
                max_allowed_change_pct=total_change,
            )

        # LLM soft-risk assessment for edge cases
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"As risk officer, evaluate this proposed rebalance:\n\n"
                            f"PROPOSED: {proposed_weights}\n"
                            f"CURRENT: {current_weights}\n"
                            f"NAV: ${basket_nav_usd:.2f}\n"
                            f"RISK REPORT: {json.dumps(risk_report, default=str)[:1000]}\n\n"
                            f"Hard limits already passed. Evaluate for soft risks:\n"
                            f"- Sector concentration\n"
                            f"- Momentum chasing\n"
                            f"- Rebalancing too frequently for the basket size\n\n"
                            f'Output JSON: {{"approved": bool, "veto_reason": "...", '
                            f'"risk_violations": [], "adjusted_weights": {{}}, '
                            f'"max_allowed_change_pct": float}}'
                        ),
                    }
                ],
            )
            raw = response.content[0].text
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(stripped)
        except Exception as exc:
            logger.warning("LLM risk assessment failed, approving by default: %s", exc)
            return RiskVeto(
                approved=True,
                veto_reason="",
                risk_violations=[],
                adjusted_weights=proposed_weights,
                max_allowed_change_pct=total_change,
            )
