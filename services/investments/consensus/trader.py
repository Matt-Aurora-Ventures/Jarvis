"""Trader Agent — Grok-based final allocation decision maker."""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

import httpx

logger = logging.getLogger("investments.consensus.trader")


class TradeDecision(TypedDict):
    action: str  # REBALANCE | HOLD | EMERGENCY_EXIT
    final_weights: dict[str, float]
    reasoning: str
    confidence: float
    estimated_gas_cost_usd: float
    estimated_slippage_pct: float


class TraderAgent:
    """Grok-based trader that makes the FINAL allocation decision.

    Receives: bull thesis, bear thesis, risk assessment, analyst reports, memory.
    Outputs: final trade decision within allowed action space.
    """

    def __init__(
        self, api_key: str, model: str = "grok-4-1-fast-non-reasoning"
    ) -> None:
        self.client = httpx.AsyncClient(
            base_url="https://api.x.ai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self.model = model

    async def decide(
        self,
        bull_thesis: dict[str, Any],
        bear_thesis: dict[str, Any],
        risk_assessment: dict[str, Any],
        analyst_reports: dict[str, Any],
        current_weights: dict[str, float],
        basket_nav_usd: float,
        calibration_hints: str,
        decision_history: list[dict],
    ) -> TradeDecision:
        risk_approved = risk_assessment.get("approved", False)
        prompt = f"""You are the TRADER making the final portfolio allocation decision.

BULL CASE (confidence {bull_thesis.get('confidence', 0):.0%}):
{bull_thesis.get('thesis', '')}

BEAR CASE (confidence {bear_thesis.get('confidence', 0):.0%}):
{bear_thesis.get('thesis', '')}

RISK OFFICER ASSESSMENT:
Approved: {risk_approved}
Violations: {risk_assessment.get('risk_violations', [])}
Max allowed change: {risk_assessment.get('max_allowed_change_pct', 0):.0%}

ANALYST REPORTS SUMMARY:
{self._summarize_reports(analyst_reports)}

CURRENT PORTFOLIO:
{json.dumps(current_weights)}
NAV: ${basket_nav_usd:.2f}

CALIBRATION (from past decisions):
{calibration_hints[:500]}

RECENT DECISIONS (last 5):
{json.dumps(decision_history[-5:], default=str)[:800] if decision_history else 'No history yet'}

CONSTRAINTS:
- Risk officer has {"APPROVED" if risk_approved else "VETOED"} this rebalance
- If vetoed, you MUST output HOLD
- Max single-rebalance change: 25% of basket value
- No single token > 30%
- Basket must include ALVA at >= 5% weight
- Consider gas costs (~$0.50-2 on Base) relative to basket size ${basket_nav_usd:.2f}

Output JSON: {{"action":"REBALANCE|HOLD|EMERGENCY_EXIT","final_weights":{{}},"reasoning":"...","confidence":0.0-1.0,"estimated_gas_cost_usd":float,"estimated_slippage_pct":float}}"""

        response = await self.client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 1500,
            },
        )
        response.raise_for_status()
        data = response.json()
        try:
            return json.loads(data["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("Trader parse failed: %s", exc)
            return TradeDecision(
                action="HOLD",
                final_weights=current_weights,
                reasoning=f"Parse error, defaulting to HOLD: {exc}",
                confidence=0.0,
                estimated_gas_cost_usd=0.0,
                estimated_slippage_pct=0.0,
            )

    async def close(self) -> None:
        await self.client.aclose()

    def _summarize_reports(self, reports: dict) -> str:
        lines = []
        for agent, report in reports.items():
            if isinstance(report, dict):
                conf = report.get("confidence", "N/A")
                key = report.get(
                    "reasoning",
                    report.get("thesis", report.get("trend", "N/A")),
                )
                if isinstance(key, str):
                    key = key[:100]
                lines.append(f"  {agent}: confidence={conf}, key={key}")
        return "\n".join(lines) or "  (no reports)"
