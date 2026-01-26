"""
Debate Synthesis Logic

Synthesizes Bull and Bear analyst perspectives into a final recommendation.
Extracts confidence scores, key factors, and generates explainable decisions.
"""

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of debate synthesis."""

    recommendation: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    reasoning: str = ""
    key_factors: List[str] = field(default_factory=list)
    risk_assessment: str = ""
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def extract_confidence(text: str) -> float:
    """
    Extract confidence score from AI response text.

    Supports formats:
    - "75%" or "confidence is 75%"
    - "0.75" or "confidence: 0.75"
    - "CONFIDENCE: 75"

    Args:
        text: AI response text

    Returns:
        Confidence score (0-100), defaults to 50.0 if not found
    """
    if not text:
        return 50.0

    # Try labeled format first: CONFIDENCE: X or Confidence: X%
    labeled_pattern = r'CONFIDENCE[:\s]+(\d+(?:\.\d+)?)\s*%?'
    match = re.search(labeled_pattern, text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        # If it's a decimal like 0.75, convert to percentage
        if value <= 1.0:
            value *= 100
        return min(max(value, 0), 100)

    # Try percentage format: 75%
    pct_pattern = r'(\d+(?:\.\d+)?)\s*%'
    match = re.search(pct_pattern, text)
    if match:
        return min(max(float(match.group(1)), 0), 100)

    # Try decimal format: 0.75
    decimal_pattern = r'\b(0\.\d+)\b'
    match = re.search(decimal_pattern, text)
    if match:
        return min(max(float(match.group(1)) * 100, 0), 100)

    # Default
    return 50.0


def extract_recommendation(text: str) -> str:
    """
    Extract recommendation from AI response text.

    Args:
        text: AI response text

    Returns:
        Recommendation: "BUY", "SELL", or "HOLD"
    """
    if not text:
        return "HOLD"

    text_upper = text.upper()

    # Look for labeled format: RECOMMENDATION: BUY
    rec_pattern = r'RECOMMENDATION[:\s]+(BUY|SELL|HOLD)'
    match = re.search(rec_pattern, text_upper)
    if match:
        return match.group(1)

    # Look for explicit keywords (not in negative context)
    # Check for "should buy" or "recommend buying" patterns
    if re.search(r'\b(SHOULD\s+BUY|RECOMMEND\s+BUY|STRONG\s+BUY)\b', text_upper):
        return "BUY"
    if re.search(r'\b(SHOULD\s+SELL|RECOMMEND\s+SELL|STRONG\s+SELL)\b', text_upper):
        return "SELL"
    if re.search(r'\b(SHOULD\s+HOLD|RECOMMEND\s+HOLD|WAIT)\b', text_upper):
        return "HOLD"

    # Simple keyword detection
    if re.search(r'\bBUY\b', text_upper):
        return "BUY"
    if re.search(r'\bSELL\b', text_upper):
        return "SELL"
    if re.search(r'\bHOLD\b', text_upper):
        return "HOLD"

    # Default to HOLD if unclear
    return "HOLD"


def build_synthesis_prompt(
    bull_case: str,
    bear_case: str,
    signal: Optional[Dict[str, Any]] = None,
    market_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the synthesis prompt for the AI model.

    Args:
        bull_case: Bull analyst's argument
        bear_case: Bear analyst's argument
        signal: Original trading signal
        market_context: Additional market context

    Returns:
        Formatted synthesis prompt
    """
    prompt = """You are a Senior Trading Strategist synthesizing two analyst perspectives.

BULL ANALYST ARGUMENT:
---
{bull_case}
---

BEAR ANALYST ARGUMENT:
---
{bear_case}
---

""".format(bull_case=bull_case, bear_case=bear_case)

    if signal:
        direction = signal.get("direction", "UNKNOWN")
        confidence = signal.get("confidence", 0)
        prompt += f"""
ORIGINAL SIGNAL:
- Direction: {direction}
- Initial Confidence: {confidence}%
"""

    if market_context:
        prompt += f"""
MARKET CONTEXT:
- Regime: {market_context.get('regime', 'unknown')}
- BTC Trend: {market_context.get('btc_trend', 'unknown')}
"""

    prompt += """
YOUR TASK:
Synthesize both perspectives into a final trading decision.

RESPONSE FORMAT (use exactly this structure):
RECOMMENDATION: [BUY/SELL/HOLD]
CONFIDENCE: [0-100]
REASONING: [2-3 sentences explaining your decision]
KEY_FACTORS: [Comma-separated list of decisive factors]
RISK_ASSESSMENT: [Low/Medium/High - brief explanation]

Consider:
1. Which analyst presents stronger evidence?
2. Are the bull and bear concerns complementary or contradictory?
3. What is the risk-reward balance?
4. Would a partial position or waiting be appropriate?
"""

    return prompt


class DebateSynthesizer:
    """
    Synthesizes Bull and Bear debate into final recommendation.
    """

    def __init__(self, client: Optional[Any] = None):
        """
        Initialize synthesizer.

        Args:
            client: AI client with generate() method
        """
        self.client = client

    async def synthesize(
        self,
        bull_case: str,
        bear_case: str,
        signal: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        weight_by_evidence: bool = False,
    ) -> SynthesisResult:
        """
        Synthesize bull and bear perspectives into final recommendation.

        Args:
            bull_case: Bull analyst's argument
            bear_case: Bear analyst's argument
            signal: Original trading signal
            market_context: Additional market context
            weight_by_evidence: Whether to weight by evidence strength

        Returns:
            SynthesisResult with recommendation and reasoning

        Raises:
            ValueError: If bull_case or bear_case is missing
        """
        if not bull_case:
            raise ValueError("bull_case is required for synthesis")
        if not bear_case:
            raise ValueError("bear_case is required for synthesis")

        # Build synthesis prompt
        prompt = build_synthesis_prompt(
            bull_case=bull_case,
            bear_case=bear_case,
            signal=signal,
            market_context=market_context,
        )

        # If no client, return rule-based synthesis
        if not self.client:
            return self._rule_based_synthesis(bull_case, bear_case, signal)

        try:
            response = await self.client.generate(
                persona=None,
                context=prompt,
            )

            content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)

            # Parse response
            recommendation = extract_recommendation(content)
            confidence = extract_confidence(content)

            # Extract reasoning
            reasoning_match = re.search(
                r'REASONING[:\s]+(.+?)(?=KEY_FACTORS|RISK_ASSESSMENT|$)',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            reasoning = reasoning_match.group(1).strip() if reasoning_match else content[:200]

            # Extract key factors
            factors_match = re.search(
                r'KEY_FACTORS[:\s]+(.+?)(?=RISK_ASSESSMENT|$)',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            key_factors = []
            if factors_match:
                factors_text = factors_match.group(1).strip()
                key_factors = [f.strip() for f in factors_text.split(",")]

            # Extract risk assessment
            risk_match = re.search(
                r'RISK_ASSESSMENT[:\s]+(.+?)$',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            risk_assessment = risk_match.group(1).strip() if risk_match else "Unknown"

            return SynthesisResult(
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                key_factors=key_factors,
                risk_assessment=risk_assessment,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return self._rule_based_synthesis(bull_case, bear_case, signal)

    def _rule_based_synthesis(
        self,
        bull_case: str,
        bear_case: str,
        signal: Optional[Dict[str, Any]] = None,
    ) -> SynthesisResult:
        """
        Fallback rule-based synthesis without AI.

        Args:
            bull_case: Bull argument
            bear_case: Bear argument
            signal: Original signal

        Returns:
            SynthesisResult based on simple heuristics
        """
        # Simple heuristic: count positive vs negative words
        bull_score = self._score_argument(bull_case, positive=True)
        bear_score = self._score_argument(bear_case, positive=False)

        # Use signal as tie-breaker
        signal_direction = signal.get("direction", "HOLD") if signal else "HOLD"
        signal_confidence = signal.get("confidence", 50) if signal else 50

        if bull_score > bear_score + 2:
            recommendation = "BUY"
            confidence = min(65 + bull_score * 2, 80)
        elif bear_score > bull_score + 2:
            recommendation = "SELL"
            confidence = min(65 + bear_score * 2, 80)
        else:
            recommendation = "HOLD"
            confidence = 50

        return SynthesisResult(
            recommendation=recommendation,
            confidence=confidence,
            reasoning=f"Rule-based synthesis: Bull score {bull_score}, Bear score {bear_score}",
            key_factors=["Automated analysis"],
            risk_assessment="Medium",
        )

    def _score_argument(self, text: str, positive: bool) -> int:
        """Score an argument based on keyword presence."""
        if positive:
            keywords = [
                "strong", "momentum", "growth", "breakout", "bullish",
                "support", "oversold", "accumulation", "volume",
            ]
        else:
            keywords = [
                "risk", "overbought", "resistance", "weak", "declining",
                "bearish", "reversal", "distribution", "warning",
            ]

        text_lower = text.lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        return score


__all__ = [
    "SynthesisResult",
    "DebateSynthesizer",
    "extract_confidence",
    "extract_recommendation",
    "build_synthesis_prompt",
]
