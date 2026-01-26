"""
Bull/Bear Debate Orchestrator

Orchestrates debates between Bull and Bear analyst personas to produce
explainable, well-reasoned trading decisions. Based on the TradingAgents
framework used by institutional hedge funds (UCLA/MIT research).

Features:
- Parallel generation of Bull and Bear perspectives
- Structured synthesis of opposing viewpoints
- Confidence scoring with calibration
- Full reasoning chain recording for compliance
- Cost tracking and limits
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from .personas import BullPersona, BearPersona, PersonaFactory
from .synthesis import DebateSynthesizer, extract_confidence, extract_recommendation

logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """
    Result of a Bull/Bear debate evaluation.

    Contains the full reasoning chain for compliance and explainability.
    """

    recommendation: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    bull_case: str = ""
    bear_case: str = ""
    synthesis: str = ""
    reasoning_chain: List[Dict[str, Any]] = field(default_factory=list)
    debate_conducted: bool = True
    tokens_used: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None
    debate_id: str = ""
    timestamp: str = ""

    def __post_init__(self):
        """Initialize defaults."""
        if not self.debate_id:
            self.debate_id = str(uuid.uuid4())[:12]
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def should_execute(self, min_confidence: float = 70.0) -> bool:
        """
        Determine if trade should be executed based on confidence.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            True if trade should execute
        """
        if self.error:
            return False
        if self.recommendation == "HOLD":
            return False
        return self.confidence >= min_confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class DebateOrchestrator:
    """
    Orchestrates Bull/Bear debates for trading decisions.

    Creates opposing analyst perspectives, synthesizes them into a
    final recommendation, and records the full reasoning chain.
    """

    # Cost per 1K tokens (configurable, defaults to Claude pricing)
    COST_PER_1K_TOKENS = 0.003

    def __init__(
        self,
        client: Optional[Any] = None,
        debate_threshold: float = 60.0,
        max_tokens_per_debate: int = 2000,
        parallel: bool = True,
    ):
        """
        Initialize debate orchestrator.

        Args:
            client: AI client with generate(persona, context) method
            debate_threshold: Minimum signal confidence to trigger debate
            max_tokens_per_debate: Maximum tokens allowed per debate
            parallel: Whether to generate bull/bear in parallel
        """
        self.client = client
        self.debate_threshold = debate_threshold
        self.max_tokens_per_debate = max_tokens_per_debate
        self.parallel = parallel

        # Initialize personas
        self.bull_persona = BullPersona()
        self.bear_persona = BearPersona()

        # Initialize synthesizer
        self.synthesizer = DebateSynthesizer(client=client)

        # Track total usage
        self._total_debates = 0
        self._total_tokens = 0
        self._total_cost = 0.0

    async def evaluate_trade(
        self,
        signal: Optional[Dict[str, Any]],
        market_data: Optional[Dict[str, Any]],
    ) -> TradeDecision:
        """
        Evaluate a trading signal through Bull/Bear debate.

        Args:
            signal: Trading signal with direction and confidence
            market_data: Market data for the token

        Returns:
            TradeDecision with recommendation and reasoning chain

        Raises:
            ValueError: If market_data is None
        """
        if market_data is None:
            raise ValueError("market_data is required for debate evaluation")

        # Generate unique debate ID
        debate_id = str(uuid.uuid4())[:12]
        timestamp = datetime.now(timezone.utc).isoformat()
        reasoning_chain: List[Dict[str, Any]] = []
        tokens_used = 0

        # Check if debate should be conducted
        signal_confidence = signal.get("confidence", 0) if signal else 0

        if signal_confidence < self.debate_threshold:
            # Skip debate for low-confidence signals
            logger.info(
                f"Skipping debate: signal confidence {signal_confidence}% "
                f"below threshold {self.debate_threshold}%"
            )
            return TradeDecision(
                recommendation="HOLD",
                confidence=signal_confidence,
                debate_conducted=False,
                reasoning_chain=[{
                    "step": "threshold_check",
                    "result": f"Signal confidence {signal_confidence}% below threshold",
                }],
                debate_id=debate_id,
                timestamp=timestamp,
            )

        try:
            # Step 1: Generate Bull case
            reasoning_chain.append({
                "step": "bull_analysis",
                "persona": self.bull_persona.name,
                "started_at": datetime.now(timezone.utc).isoformat(),
            })

            # Step 2: Generate Bear case (in parallel if enabled)
            reasoning_chain.append({
                "step": "bear_analysis",
                "persona": self.bear_persona.name,
                "started_at": datetime.now(timezone.utc).isoformat(),
            })

            if self.parallel and self.client:
                bull_case, bear_case, parallel_tokens = await self._generate_parallel(
                    market_data, signal
                )
                tokens_used += parallel_tokens
            else:
                bull_case, bull_tokens = await self._generate_case(
                    self.bull_persona, market_data, signal
                )
                tokens_used += bull_tokens

                # Check token limit
                if tokens_used >= self.max_tokens_per_debate:
                    logger.warning(f"Token limit reached after bull case")
                    return TradeDecision(
                        recommendation="HOLD",
                        confidence=50,
                        bull_case=bull_case,
                        bear_case="Token limit reached",
                        debate_conducted=True,
                        tokens_used=tokens_used,
                        reasoning_chain=reasoning_chain,
                        debate_id=debate_id,
                        timestamp=timestamp,
                    )

                bear_case, bear_tokens = await self._generate_case(
                    self.bear_persona, market_data, signal
                )
                tokens_used += bear_tokens

            # Update reasoning chain with results
            reasoning_chain[0]["result"] = bull_case[:200] + "..."
            reasoning_chain[0]["tokens"] = tokens_used // 2
            reasoning_chain[1]["result"] = bear_case[:200] + "..."
            reasoning_chain[1]["tokens"] = tokens_used // 2

            # Step 3: Synthesize debate
            reasoning_chain.append({
                "step": "synthesis",
                "started_at": datetime.now(timezone.utc).isoformat(),
            })

            synthesis_result = await self.synthesizer.synthesize(
                bull_case=bull_case,
                bear_case=bear_case,
                signal=signal,
                market_context=market_data,
            )
            tokens_used += synthesis_result.tokens_used

            reasoning_chain[2]["result"] = synthesis_result.reasoning
            reasoning_chain[2]["tokens"] = synthesis_result.tokens_used

            # Update tracking
            self._total_debates += 1
            self._total_tokens += tokens_used
            self._total_cost += (tokens_used / 1000) * self.COST_PER_1K_TOKENS

            return TradeDecision(
                recommendation=synthesis_result.recommendation,
                confidence=synthesis_result.confidence,
                bull_case=bull_case,
                bear_case=bear_case,
                synthesis=synthesis_result.reasoning,
                reasoning_chain=reasoning_chain,
                debate_conducted=True,
                tokens_used=tokens_used,
                cost_usd=(tokens_used / 1000) * self.COST_PER_1K_TOKENS,
                debate_id=debate_id,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Debate evaluation failed: {e}")
            reasoning_chain.append({
                "step": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            return TradeDecision(
                recommendation="HOLD",
                confidence=0,
                reasoning_chain=reasoning_chain,
                debate_conducted=True,
                tokens_used=tokens_used,
                error=str(e),
                debate_id=debate_id,
                timestamp=timestamp,
            )

    async def _generate_case(
        self,
        persona: Any,
        market_data: Dict[str, Any],
        signal: Optional[Dict[str, Any]],
    ) -> Tuple[str, int]:
        """
        Generate an analyst case using the AI client.

        Args:
            persona: The analyst persona
            market_data: Market data for analysis
            signal: Trading signal context

        Returns:
            Tuple of (analysis_text, tokens_used)
        """
        if not self.client:
            return f"{persona.name}: No AI client available", 0

        try:
            # Build context from market data and signal
            context = persona.generate_analysis_prompt(market_data, signals=signal)

            response = await self.client.generate(
                persona=persona.name,
                context=context,
            )

            content = response.get("content", "")
            tokens = response.get("tokens_used", 50)

            return content, tokens

        except Exception as e:
            logger.error(f"Failed to generate {persona.name} case: {e}")
            raise

    async def _generate_parallel(
        self,
        market_data: Dict[str, Any],
        signal: Optional[Dict[str, Any]],
    ) -> Tuple[str, str, int]:
        """
        Generate Bull and Bear cases in parallel.

        Args:
            market_data: Market data for analysis
            signal: Trading signal context

        Returns:
            Tuple of (bull_case, bear_case, total_tokens)
        """
        bull_task = asyncio.create_task(
            self._generate_case(self.bull_persona, market_data, signal)
        )
        bear_task = asyncio.create_task(
            self._generate_case(self.bear_persona, market_data, signal)
        )

        results = await asyncio.gather(bull_task, bear_task, return_exceptions=True)

        bull_result = results[0]
        bear_result = results[1]

        # Handle exceptions
        if isinstance(bull_result, Exception):
            bull_case = f"Bull analysis failed: {bull_result}"
            bull_tokens = 0
        else:
            bull_case, bull_tokens = bull_result

        if isinstance(bear_result, Exception):
            bear_case = f"Bear analysis failed: {bear_result}"
            bear_tokens = 0
        else:
            bear_case, bear_tokens = bear_result

        return bull_case, bear_case, bull_tokens + bear_tokens

    def get_stats(self) -> Dict[str, Any]:
        """Get debate statistics."""
        return {
            "total_debates": self._total_debates,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "avg_tokens_per_debate": (
                self._total_tokens / self._total_debates
                if self._total_debates > 0
                else 0
            ),
        }


__all__ = [
    "DebateOrchestrator",
    "TradeDecision",
]
