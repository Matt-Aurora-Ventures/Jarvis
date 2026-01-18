"""
Unified Decision Matrix: Grok Sentiment + Dexter Fundamentals
Central trading decision engine for Jarvis.

Architecture:
- Grok: Sentiment oracle (weighted 70% for memecoins, 40% for bluechips)
- Dexter: Fundamental analysis (weighted 30% for memecoins, 60% for bluechips)
- Claude: Secondary reasoner for conflict resolution
- Unified scoring: 0-100 (0=strong sell, 100=strong buy, 50=neutral)

Usage:
    from core.decision_matrix import DecisionMatrix

    dm = DecisionMatrix()
    decision = await dm.decide("SOL", "memecoin")
    # Returns: {"action": "BUY", "confidence": 87, "reasoning": "..."}
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AssetClass(Enum):
    """Asset classification for weighting."""
    MEMECOIN = "memecoin"  # 70% Grok, 30% Dexter
    SHITCOIN = "shitcoin"  # 75% Grok, 25% Dexter
    MICRO_CAP = "micro_cap"  # 65% Grok, 35% Dexter
    MID_CAP = "mid_cap"  # 50% Grok, 50% Dexter
    ESTABLISHED = "established"  # 40% Grok, 60% Dexter
    BLUECHIP = "bluechip"  # 30% Grok, 70% Dexter


class DecisionAction(Enum):
    """Trading action from decision matrix."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    SKIP = "SKIP"


@dataclass
class DecisionSignal:
    """Individual signal from an analyzer."""
    name: str
    score: float  # 0-100
    confidence: float  # 0-1
    reasoning: str
    timestamp: str


@dataclass
class DecisionResult:
    """Final trading decision."""
    action: DecisionAction
    confidence: float  # 0-100
    score: float  # 0-100 (0=sell, 50=hold, 100=buy)
    reasoning: str
    grok_score: float
    dexter_score: float
    signals: Dict[str, DecisionSignal]
    risk_level: str  # LOW, MEDIUM, HIGH, EXTREME


class DecisionMatrix:
    """
    Unified trading decision engine.
    Combines Grok sentiment and Dexter fundamentals for trading decisions.
    """

    def __init__(self):
        self._grok_client = None
        self._dexter_agent = None
        self._asset_weights = self._init_asset_weights()

    def _init_asset_weights(self) -> Dict[AssetClass, Dict[str, float]]:
        """Initialize signal weights by asset class."""
        return {
            AssetClass.MEMECOIN: {"grok": 0.70, "dexter": 0.30},
            AssetClass.SHITCOIN: {"grok": 0.75, "dexter": 0.25},
            AssetClass.MICRO_CAP: {"grok": 0.65, "dexter": 0.35},
            AssetClass.MID_CAP: {"grok": 0.50, "dexter": 0.50},
            AssetClass.ESTABLISHED: {"grok": 0.40, "dexter": 0.60},
            AssetClass.BLUECHIP: {"grok": 0.30, "dexter": 0.70},
        }

    async def _get_grok_sentiment(self, symbol: str) -> DecisionSignal:
        """Get Grok sentiment analysis."""
        try:
            if self._grok_client is None:
                from bots.twitter.grok_client import GrokClient
                self._grok_client = GrokClient()

            # Grok sentiment prompt
            prompt = f"""
            Analyze the current market sentiment for ${symbol}.

            Respond with JSON:
            {{
                "score": <0-100>,
                "reasoning": "<brief insight>",
                "confidence": <0-1>
            }}
            """

            # TODO: Implement Grok call with retry logic
            # For now, return placeholder
            return DecisionSignal(
                name="grok_sentiment",
                score=65.0,
                confidence=0.85,
                reasoning="Placeholder Grok sentiment",
                timestamp="2026-01-18T00:00:00Z"
            )

        except Exception as e:
            logger.error(f"Grok sentiment failed: {e}")
            return DecisionSignal(
                name="grok_sentiment",
                score=50.0,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp="2026-01-18T00:00:00Z"
            )

    async def _get_dexter_analysis(self, symbol: str, token_mint: str = None) -> DecisionSignal:
        """Get Dexter fundamental analysis."""
        try:
            if self._dexter_agent is None:
                from core.dexter.agent import DexterAgent
                self._dexter_agent = DexterAgent()

            # Run Dexter ReAct loop
            analysis = await self._dexter_agent.analyze_token(
                symbol=symbol,
                token_mint=token_mint or "",
            )

            return DecisionSignal(
                name="dexter_fundamentals",
                score=analysis.get("score", 50.0),
                confidence=analysis.get("confidence", 0.5),
                reasoning=analysis.get("reasoning", "Placeholder Dexter analysis"),
                timestamp=analysis.get("timestamp", "2026-01-18T00:00:00Z")
            )

        except Exception as e:
            logger.error(f"Dexter analysis failed: {e}")
            return DecisionSignal(
                name="dexter_fundamentals",
                score=50.0,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                timestamp="2026-01-18T00:00:00Z"
            )

    async def decide(
        self,
        symbol: str,
        asset_class: AssetClass = AssetClass.MEMECOIN,
        token_mint: Optional[str] = None,
    ) -> DecisionResult:
        """
        Make unified trading decision.

        Args:
            symbol: Token symbol (e.g., "SOL")
            asset_class: Asset classification for weighting
            token_mint: Token mint address (optional)

        Returns:
            DecisionResult with action and reasoning
        """
        logger.info(f"Deciding on {symbol} ({asset_class.value})")

        # Get signals in parallel
        grok_signal, dexter_signal = await asyncio.gather(
            self._get_grok_sentiment(symbol),
            self._get_dexter_analysis(symbol, token_mint),
        )

        # Get weights for this asset class
        weights = self._asset_weights[asset_class]

        # Calculate weighted score
        weighted_score = (
            (grok_signal.score * weights["grok"]) +
            (dexter_signal.score * weights["dexter"])
        )

        # Determine action based on score
        if weighted_score >= 70:
            action = DecisionAction.BUY
        elif weighted_score >= 55:
            action = DecisionAction.HOLD
        elif weighted_score <= 30:
            action = DecisionAction.SELL
        else:
            action = DecisionAction.SKIP

        # Calculate confidence (weighted average)
        confidence = (
            (grok_signal.confidence * weights["grok"]) +
            (dexter_signal.confidence * weights["dexter"])
        ) * 100

        # Risk assessment
        if asset_class in [AssetClass.SHITCOIN, AssetClass.MEMECOIN]:
            risk_level = "HIGH" if confidence > 80 else "EXTREME"
        elif asset_class == AssetClass.MICRO_CAP:
            risk_level = "HIGH"
        elif asset_class == AssetClass.BLUECHIP:
            risk_level = "LOW" if confidence > 70 else "MEDIUM"
        else:
            risk_level = "MEDIUM"

        # Build reasoning
        reasoning = (
            f"Grok ({grok_signal.score:.0f}/100): {grok_signal.reasoning} | "
            f"Dexter ({dexter_signal.score:.0f}/100): {dexter_signal.reasoning}"
        )

        return DecisionResult(
            action=action,
            confidence=min(confidence, 100),
            score=weighted_score,
            reasoning=reasoning,
            grok_score=grok_signal.score,
            dexter_score=dexter_signal.score,
            signals={
                "grok": grok_signal,
                "dexter": dexter_signal,
            },
            risk_level=risk_level,
        )
