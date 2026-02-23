"""
Debate Integration with Trading Engine

Provides integration between the Bull/Bear debate orchestrator
and the trading engine for high-confidence trade evaluation.
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from .debate_orchestrator import DebateOrchestrator, TradeDecision
from ..reasoning_store import ReasoningStore

logger = logging.getLogger(__name__)


class DebateClient:
    """
    Client adapter for AI models that implements the generate() interface
    expected by the debate orchestrator.

    Supports:
    - Claude (via Anthropic API)
    - Grok (via xAI API)
    - Local models (via Ollama)
    """

    def __init__(self, provider: str = "auto"):
        """
        Initialize debate client.

        Args:
            provider: AI provider ("claude", "grok", "ollama", "auto")
        """
        self.provider = provider
        self._client = None

        # Auto-detect best available provider
        if provider == "auto":
            self.provider = self._detect_provider()

    def _detect_provider(self) -> str:
        """Detect best available AI provider."""
        # Check for Claude
        if os.getenv("ANTHROPIC_API_KEY"):
            return "claude"
        # Check for Grok
        if os.getenv("XAI_API_KEY"):
            return "grok"
        # Default to ollama for local
        return "ollama"

    async def generate(
        self,
        persona: Optional[str],
        context: str,
    ) -> Dict[str, Any]:
        """
        Generate AI response for debate.

        Args:
            persona: Persona name (for context)
            context: Full prompt context

        Returns:
            Dict with "content" and "tokens_used"
        """
        if self.provider == "claude":
            return await self._generate_claude(persona, context)
        elif self.provider == "grok":
            return await self._generate_grok(persona, context)
        elif self.provider == "ollama":
            return await self._generate_ollama(persona, context)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _generate_claude(
        self,
        persona: Optional[str],
        context: str,
    ) -> Dict[str, Any]:
        """Generate using Claude API."""
        try:
            import anthropic
            from core.llm.anthropic_utils import (
                get_anthropic_api_key,
                get_anthropic_base_url,
            )

            client = anthropic.Anthropic(
                api_key=get_anthropic_api_key(),
                base_url=get_anthropic_base_url(),
            )

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                temperature=0.7,
                messages=[{"role": "user", "content": context}],
            )

            return {
                "content": response.content[0].text,
                "tokens_used": response.usage.output_tokens,
            }

        except ImportError:
            logger.warning("Anthropic not available, falling back")
            return {"content": "Analysis unavailable", "tokens_used": 0}
        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            raise

    async def _generate_grok(
        self,
        persona: Optional[str],
        context: str,
    ) -> Dict[str, Any]:
        """Generate using Grok API."""
        try:
            from bots.twitter.grok_client import GrokClient

            client = GrokClient()
            response = await client.generate_tweet(
                prompt=context,
                max_tokens=500,
                temperature=0.7,
            )

            if response.success:
                return {
                    "content": response.content,
                    "tokens_used": response.usage.get("completion_tokens", 50) if response.usage else 50,
                }
            else:
                raise Exception(response.error or "Grok API error")

        except ImportError:
            logger.warning("GrokClient not available, falling back")
            return {"content": "Analysis unavailable", "tokens_used": 0}
        except Exception as e:
            logger.error(f"Grok generation failed: {e}")
            raise

    async def _generate_ollama(
        self,
        persona: Optional[str],
        context: str,
    ) -> Dict[str, Any]:
        """Generate using local Ollama model."""
        try:
            import aiohttp

            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model = os.getenv("OLLAMA_MODEL", "llama3")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": context,
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "content": data.get("response", ""),
                            "tokens_used": len(data.get("response", "")) // 4,  # Estimate
                        }
                    else:
                        raise Exception(f"Ollama error: {resp.status}")

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise


class TradingDebateEvaluator:
    """
    Evaluates trading signals through Bull/Bear debate.

    Integrates with the trading engine to provide explainable
    AI-powered trade evaluation.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_confidence_for_debate: float = 60.0,
        provider: str = "auto",
        store_reasoning: bool = True,
    ):
        """
        Initialize debate evaluator.

        Args:
            enabled: Whether debate evaluation is enabled
            min_confidence_for_debate: Minimum signal confidence to trigger debate
            provider: AI provider for debate
            store_reasoning: Whether to store reasoning chains
        """
        self.enabled = enabled
        self.min_confidence = min_confidence_for_debate

        # Initialize AI client
        self.client = DebateClient(provider=provider) if enabled else None

        # Initialize orchestrator
        self.orchestrator = DebateOrchestrator(
            client=self.client,
            debate_threshold=min_confidence_for_debate,
            parallel=True,
        ) if enabled else None

        # Initialize reasoning store
        self.reasoning_store = ReasoningStore() if store_reasoning else None

    async def evaluate_signal(
        self,
        signal: Dict[str, Any],
        market_data: Dict[str, Any],
        position_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[TradeDecision, bool]:
        """
        Evaluate a trading signal through Bull/Bear debate.

        Args:
            signal: Trading signal with direction and confidence
            market_data: Market data for the token
            position_context: Current position context

        Returns:
            Tuple of (TradeDecision, should_execute)
        """
        if not self.enabled or not self.orchestrator:
            # Pass through without debate
            return TradeDecision(
                recommendation=signal.get("direction", "HOLD"),
                confidence=signal.get("confidence", 50),
                debate_conducted=False,
            ), signal.get("confidence", 50) >= 70

        try:
            # Add position context to market data
            if position_context:
                market_data = {**market_data, "position_context": position_context}

            # Run debate evaluation
            decision = await self.orchestrator.evaluate_trade(
                signal=signal,
                market_data=market_data,
            )

            # Store reasoning chain
            if self.reasoning_store and decision.debate_conducted:
                self.reasoning_store.store({
                    "debate_id": decision.debate_id,
                    "symbol": market_data.get("symbol", "UNKNOWN"),
                    "timestamp": decision.timestamp,
                    "signal": signal,
                    "market_data": market_data,
                    "bull_case": decision.bull_case,
                    "bear_case": decision.bear_case,
                    "synthesis": decision.synthesis,
                    "recommendation": decision.recommendation,
                    "confidence": decision.confidence,
                    "tokens_used": decision.tokens_used,
                })

            # Determine if trade should execute
            should_execute = decision.should_execute(min_confidence=70.0)

            logger.info(
                f"Debate result for {market_data.get('symbol', '?')}: "
                f"{decision.recommendation} @ {decision.confidence:.1f}% "
                f"(execute: {should_execute})"
            )

            return decision, should_execute

        except Exception as e:
            logger.error(f"Debate evaluation failed: {e}")
            # Fall back to original signal
            return TradeDecision(
                recommendation="HOLD",
                confidence=0,
                error=str(e),
            ), False

    async def record_outcome(
        self,
        debate_id: str,
        outcome: Dict[str, Any],
    ) -> bool:
        """
        Record the outcome of a debated trade.

        Args:
            debate_id: The debate ID
            outcome: Outcome data (pnl, was_correct, etc.)

        Returns:
            Success status
        """
        if not self.reasoning_store:
            return False

        result = self.reasoning_store.update_outcome(debate_id, outcome)
        return result.success

    def get_stats(self) -> Dict[str, Any]:
        """Get debate statistics."""
        stats = {}

        if self.orchestrator:
            stats["orchestrator"] = self.orchestrator.get_stats()

        if self.reasoning_store:
            stats["accuracy"] = self.reasoning_store.get_accuracy_stats()

        return stats


# Singleton instance
_evaluator: Optional[TradingDebateEvaluator] = None


def get_debate_evaluator() -> TradingDebateEvaluator:
    """Get or create the singleton debate evaluator."""
    global _evaluator
    if _evaluator is None:
        enabled = os.getenv("DEBATE_ENABLED", "true").lower() in ("1", "true", "yes")
        _evaluator = TradingDebateEvaluator(enabled=enabled)
    return _evaluator


__all__ = [
    "DebateClient",
    "TradingDebateEvaluator",
    "get_debate_evaluator",
]
