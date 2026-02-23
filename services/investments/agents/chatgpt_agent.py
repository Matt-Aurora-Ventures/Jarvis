"""ChatGPT Macro Analyst — produces macro/technical analysis reports."""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from openai import AsyncOpenAI

logger = logging.getLogger("investments.agents.chatgpt")


class MacroReport(TypedDict):
    market_regime: str  # RISK_ON | RISK_OFF | TRANSITIONING | UNCERTAIN
    key_macro_factors: list[str]
    technical_signals: dict  # per-token technical indicators
    recommended_sector_weights: dict  # e.g. {"defi": 0.3, "l1": 0.4}
    reasoning: str
    confidence: float


class ChatGPTMacroAnalyst:
    """Produces macro/technical analysis reports."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def analyze(
        self,
        basket_state: dict[str, Any],
        market_data: dict[str, Any],
        calibration_hints: str,
    ) -> MacroReport:
        prompt = f"""You are a macro and technical analyst for an AI-managed crypto portfolio.

BASKET STATE:
{json.dumps(basket_state, default=str, indent=2)}

MARKET DATA:
{json.dumps(market_data, default=str, indent=2)}

CALIBRATION FROM PAST:
{calibration_hints}

Provide:
1. Current market regime assessment
2. Key macro factors affecting crypto (rates, regulatory, flows)
3. Technical signals for each basket token (RSI direction, momentum, support/resistance)
4. Recommended sector weight adjustments

Output strict JSON:
{{
  "market_regime": "RISK_ON|RISK_OFF|TRANSITIONING|UNCERTAIN",
  "key_macro_factors": ["factor1", ...],
  "technical_signals": {{"TOKEN": {{"rsi_direction": "...", "momentum": "..."}}}},
  "recommended_sector_weights": {{"defi": 0.3, "l1": 0.4, ...}},
  "reasoning": "...",
  "confidence": 0.0-1.0
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        return json.loads(response.choices[0].message.content)

    async def close(self) -> None:
        await self.client.close()
