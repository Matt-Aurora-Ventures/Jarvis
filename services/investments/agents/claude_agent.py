"""Claude Risk Analyst — produces risk analysis reports for the current portfolio."""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

import anthropic

logger = logging.getLogger("investments.agents.claude")


class RiskReport(TypedDict):
    portfolio_risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    concentration_risk: str
    correlation_risk: str
    drawdown_risk: str
    liquidity_risk: str
    recommended_max_position_pct: float
    risk_flags: list[str]
    reasoning: str


class ClaudeRiskAnalyst:
    """Produces risk analysis reports for the current portfolio state."""

    def __init__(
        self, api_key: str, model: str = "claude-sonnet-4-6"
    ) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def analyze(
        self,
        basket_state: dict[str, Any],
        market_data: dict[str, Any],
        calibration_hints: str,
    ) -> RiskReport:
        prompt = f"""You are a risk analyst for an AI-managed crypto portfolio on Base.

CURRENT BASKET STATE:
{self._format_basket(basket_state)}

MARKET DATA (24h):
{self._format_market(market_data)}

CALIBRATION HINTS FROM PAST PERFORMANCE:
{calibration_hints}

Analyze the portfolio for:
1. Concentration risk (no single token should exceed 30% weight)
2. Correlation risk (tokens moving together reduce diversification)
3. Drawdown risk (probability of >10% portfolio loss in next 24h)
4. Liquidity risk (can we exit positions within 1% slippage on Base DEXs)

Output strict JSON matching this schema:
{{
  "portfolio_risk_score": <0.0-1.0>,
  "concentration_risk": "<LOW|MEDIUM|HIGH>",
  "correlation_risk": "<LOW|MEDIUM|HIGH>",
  "drawdown_risk": "<LOW|MEDIUM|HIGH>",
  "liquidity_risk": "<LOW|MEDIUM|HIGH>",
  "recommended_max_position_pct": <float>,
  "risk_flags": ["<flag1>", ...],
  "reasoning": "<1-2 sentences>"
}}"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        # Safely extract text — guard against empty or non-text content blocks
        text_blocks = [b for b in (response.content or []) if getattr(b, "type", "") == "text"]
        if not text_blocks:
            raise ValueError("Claude returned empty or non-text response")
        raw = text_blocks[0].text
        # Strip markdown code fences if Claude wrapped the JSON
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Claude returned non-JSON response: {raw[:200]}") from exc

    def _format_basket(self, state: dict) -> str:
        lines = []
        for token in state.get("tokens", []):
            lines.append(
                f"  {token['symbol']}: {token['weight'] * 100:.1f}% | "
                f"${token.get('value_usd', 0):.2f} | "
                f"24h: {token.get('change_24h', 0):+.1f}%"
            )
        return "\n".join(lines) or "  (empty basket)"

    def _format_market(self, data: dict) -> str:
        return (
            f"  BTC: {data.get('btc_change_24h', 'N/A')}% | "
            f"ETH: {data.get('eth_change_24h', 'N/A')}% | "
            f"Fear/Greed: {data.get('fear_greed', 'N/A')}"
        )

    async def close(self) -> None:
        await self.client.close()
