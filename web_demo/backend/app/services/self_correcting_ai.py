"""
Self-Correcting AI Service
Integrates with Jarvis supervisor and uses Ollama+Claude for continuous improvement.

Based on supervisor_integration.py pattern with enhancements:
- Anthropic Messages API routing to Ollama
- Feedback loop for learning from trading outcomes
- Cross-component communication via shared state
- Prediction accuracy tracking and self-adjustment
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Feedback from actual trading outcomes."""
    token_address: str
    token_symbol: str
    action: Literal["buy", "sell", "hold", "skip"]
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    outcome: Optional[Literal["profit", "loss", "pending"]] = None
    timestamp: datetime = None
    notes: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AIRecommendation:
    """AI-generated trading recommendation."""
    token_address: str
    token_symbol: str
    action: Literal["strong_buy", "buy", "hold", "avoid"]
    confidence: float  # 0.0 to 1.0
    reasoning: str
    score: float  # Overall score
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SelfCorrectingAI:
    """
    Self-correcting AI service that learns from trading outcomes.

    Features:
    - Routes to Ollama (local, fast, free) or Claude (cloud, powerful)
    - Learns from trading feedback to improve accuracy
    - Shares insights across Jarvis components
    - Adjusts confidence based on historical performance
    """

    def __init__(self, shared_state: Optional[Dict[str, Any]] = None):
        self.shared_state = shared_state or {}

        # Learning state
        self.recommendations: List[AIRecommendation] = []
        self.outcomes: List[TradeOutcome] = []
        self.total_predictions = 0
        self.correct_predictions = 0
        self.prediction_accuracy = 0.0

        # AI clients
        self.claude_client: Optional[anthropic.Anthropic] = None
        self.ollama_client: Optional[anthropic.Anthropic] = None
        self.preferred_model = "ollama"  # Start with free local model

        self._initialize_ai_clients()

    def _initialize_ai_clients(self):
        """Initialize Anthropic clients for Claude and Ollama."""
        if not ANTHROPIC_AVAILABLE:
            logger.warning("Anthropic library not installed - AI features disabled")
            return

        # Claude (cloud)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
            logger.info("Claude AI client initialized")

        # Ollama (local via Anthropic Messages API proxy)
        ollama_base_url = os.getenv("OLLAMA_ANTHROPIC_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
        if ollama_base_url:
            self.ollama_client = anthropic.Anthropic(
                api_key="ollama",  # Dummy key for local proxy
                base_url=ollama_base_url
            )
            logger.info(f"Ollama AI client initialized (proxy: {ollama_base_url})")

        # Determine which client to use
        if self.ollama_client:
            self.preferred_model = "ollama"
            logger.info("Using Ollama as primary AI (cost-effective)")
        elif self.claude_client:
            self.preferred_model = "claude"
            logger.info("Using Claude as primary AI (no Ollama available)")
        else:
            logger.warning("No AI clients available - falling back to rule-based")

    async def analyze_token(
        self,
        token_data: Dict[str, Any],
        use_ai: bool = True
    ) -> AIRecommendation:
        """
        Analyze a token and generate recommendation.

        Args:
            token_data: Token information (address, symbol, price, metrics, etc.)
            use_ai: Whether to use AI (falls back to rules if False or unavailable)

        Returns:
            AIRecommendation with action, confidence, and reasoning
        """
        # Extract key metrics
        token_address = token_data.get("address", "unknown")
        token_symbol = token_data.get("symbol", "UNKNOWN")

        # Calculate base score from metrics
        score = self._calculate_base_score(token_data)

        # Generate recommendation
        if use_ai and (self.ollama_client or self.claude_client):
            recommendation = await self._ai_recommendation(token_data, score)
        else:
            recommendation = self._rule_based_recommendation(token_data, score)

        # Adjust confidence based on historical accuracy
        adjusted_confidence = self._adjust_confidence(recommendation.confidence)
        recommendation.confidence = adjusted_confidence

        # Store recommendation
        self.recommendations.append(recommendation)

        # Share with other components
        self._share_intelligence(recommendation)

        return recommendation

    def _calculate_base_score(self, token_data: Dict[str, Any]) -> float:
        """Calculate base score from token metrics (0-100)."""
        scores = []
        weights = []

        # Liquidity score (25%)
        liquidity = token_data.get("liquidity_usd", 0)
        if liquidity > 1_000_000:
            scores.append(100)
        elif liquidity > 500_000:
            scores.append(80)
        elif liquidity > 100_000:
            scores.append(60)
        elif liquidity > 10_000:
            scores.append(40)
        else:
            scores.append(20)
        weights.append(0.25)

        # Volume score (20%)
        volume_24h = token_data.get("volume_24h", 0)
        if volume_24h > 500_000:
            scores.append(90)
        elif volume_24h > 100_000:
            scores.append(70)
        elif volume_24h > 10_000:
            scores.append(50)
        else:
            scores.append(30)
        weights.append(0.20)

        # Holder count score (15%)
        holders = token_data.get("holder_count", 0)
        if holders > 10_000:
            scores.append(100)
        elif holders > 1_000:
            scores.append(75)
        elif holders > 100:
            scores.append(50)
        else:
            scores.append(25)
        weights.append(0.15)

        # Age score (10%)
        age_days = token_data.get("age_days", 0)
        if age_days > 365:
            scores.append(90)
        elif age_days > 90:
            scores.append(70)
        elif age_days > 30:
            scores.append(50)
        elif age_days > 7:
            scores.append(40)
        else:
            scores.append(20)
        weights.append(0.10)

        # Social score (10%)
        has_twitter = token_data.get("has_twitter", False)
        has_website = token_data.get("has_website", False)
        has_telegram = token_data.get("has_telegram", False)
        social_score = (has_twitter * 40 + has_website * 35 + has_telegram * 25)
        scores.append(social_score)
        weights.append(0.10)

        # Price stability score (20%)
        price_change_24h = abs(token_data.get("price_change_24h_pct", 0))
        if price_change_24h < 5:
            scores.append(90)
        elif price_change_24h < 15:
            scores.append(70)
        elif price_change_24h < 30:
            scores.append(50)
        else:
            scores.append(20)
        weights.append(0.20)

        # Weighted average
        weighted_score = sum(s * w for s, w in zip(scores, weights))
        return round(weighted_score, 1)

    async def _ai_recommendation(
        self,
        token_data: Dict[str, Any],
        base_score: float
    ) -> AIRecommendation:
        """Generate AI-powered recommendation using Ollama or Claude."""
        client = self.ollama_client if self.preferred_model == "ollama" else self.claude_client

        if not client:
            return self._rule_based_recommendation(token_data, base_score)

        # Build prompt
        prompt = self._build_analysis_prompt(token_data, base_score)

        try:
            # Call AI (Ollama or Claude via Anthropic Messages API)
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-sonnet-20241022",  # Routed to Ollama if using ollama_client
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            ai_text = response.content[0].text.strip()
            action, confidence, reasoning = self._parse_ai_response(ai_text, base_score)

            return AIRecommendation(
                token_address=token_data.get("address", "unknown"),
                token_symbol=token_data.get("symbol", "UNKNOWN"),
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                score=base_score
            )

        except Exception as e:
            logger.error(f"AI recommendation failed: {e}")
            return self._rule_based_recommendation(token_data, base_score)

    def _build_analysis_prompt(self, token_data: Dict[str, Any], score: float) -> str:
        """Build analysis prompt for AI."""
        return f"""Analyze this Solana token for trading potential:

Token: {token_data.get('symbol', 'UNKNOWN')}
Base Score: {score:.1f}/100

Metrics:
- Liquidity: ${token_data.get('liquidity_usd', 0):,.0f}
- 24h Volume: ${token_data.get('volume_24h', 0):,.0f}
- Holder Count: {token_data.get('holder_count', 0):,}
- Age: {token_data.get('age_days', 0)} days
- Price Change 24h: {token_data.get('price_change_24h_pct', 0):.1f}%
- Has Twitter: {token_data.get('has_twitter', False)}
- Has Website: {token_data.get('has_website', False)}

Historical Context:
- Your Accuracy: {self.prediction_accuracy:.1%} (based on {self.total_predictions} predictions)
- Recent Performance: {'improving' if self.prediction_accuracy > 0.6 else 'needs adjustment'}

Provide your recommendation in this EXACT format:
ACTION: [strong_buy|buy|hold|avoid]
CONFIDENCE: [0.0-1.0]
REASONING: [2-3 sentences explaining why]

Focus on risk-adjusted returns. Consider liquidity, volume trends, and holder distribution."""

    def _parse_ai_response(
        self,
        ai_text: str,
        fallback_score: float
    ) -> tuple[str, float, str]:
        """Parse AI response into action, confidence, reasoning."""
        lines = ai_text.strip().split('\n')

        action = "hold"
        confidence = 0.5
        reasoning = "Unable to generate detailed analysis."

        for line in lines:
            line = line.strip()
            if line.startswith("ACTION:"):
                action_str = line.split(":", 1)[1].strip().lower()
                if action_str in ["strong_buy", "buy", "hold", "avoid"]:
                    action = action_str
            elif line.startswith("CONFIDENCE:"):
                try:
                    conf_str = line.split(":", 1)[1].strip()
                    confidence = float(conf_str)
                    confidence = max(0.0, min(1.0, confidence))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        return action, confidence, reasoning

    def _rule_based_recommendation(
        self,
        token_data: Dict[str, Any],
        score: float
    ) -> AIRecommendation:
        """Fallback rule-based recommendation when AI is unavailable."""
        token_address = token_data.get("address", "unknown")
        token_symbol = token_data.get("symbol", "UNKNOWN")

        # Determine action based on score
        if score >= 80:
            action = "strong_buy"
            confidence = 0.75
            reasoning = "Exceptional metrics across all categories. Strong fundamentals indicate high potential."
        elif score >= 65:
            action = "buy"
            confidence = 0.65
            reasoning = "Above-average score with solid liquidity and holder base. Good entry opportunity."
        elif score >= 45:
            action = "hold"
            confidence = 0.55
            reasoning = "Moderate metrics. Wait for stronger signals before entering."
        else:
            action = "avoid"
            confidence = 0.70
            reasoning = "Below-average fundamentals. High risk with limited upside potential."

        # Add specific warnings
        liquidity = token_data.get("liquidity_usd", 0)
        if liquidity < 50_000 and action in ["strong_buy", "buy"]:
            reasoning += " Note: Low liquidity may cause slippage."
            confidence *= 0.85

        age_days = token_data.get("age_days", 0)
        if age_days < 7:
            reasoning += " Warning: Very new token - proceed with caution."
            confidence *= 0.80

        return AIRecommendation(
            token_address=token_address,
            token_symbol=token_symbol,
            action=action,
            confidence=min(0.95, max(0.3, confidence)),
            reasoning=reasoning,
            score=score
        )

    def _adjust_confidence(self, base_confidence: float) -> float:
        """Adjust confidence based on historical accuracy."""
        if self.total_predictions < 10:
            # Low confidence early on
            return base_confidence * 0.75

        # Adjust based on accuracy
        accuracy_factor = self.prediction_accuracy
        adjusted = base_confidence * (0.6 + 0.4 * accuracy_factor)

        return min(0.95, max(0.25, adjusted))

    def _share_intelligence(self, recommendation: AIRecommendation):
        """Share intelligence with other Jarvis components via shared state."""
        if "ai_recommendations" not in self.shared_state:
            self.shared_state["ai_recommendations"] = []

        self.shared_state["ai_recommendations"].append({
            "token_address": recommendation.token_address,
            "token_symbol": recommendation.token_symbol,
            "action": recommendation.action,
            "confidence": recommendation.confidence,
            "reasoning": recommendation.reasoning,
            "score": recommendation.score,
            "timestamp": recommendation.timestamp.isoformat(),
            "accuracy": self.prediction_accuracy
        })

        # Keep only last 100 recommendations in shared state
        if len(self.shared_state["ai_recommendations"]) > 100:
            self.shared_state["ai_recommendations"] = self.shared_state["ai_recommendations"][-100:]

    async def record_outcome(self, outcome: TradeOutcome):
        """
        Record actual trading outcome for learning.

        This is the feedback loop that enables self-correction.
        """
        self.outcomes.append(outcome)

        # Find original recommendation
        original_rec = next(
            (r for r in self.recommendations if r.token_address == outcome.token_address),
            None
        )

        if not original_rec:
            logger.warning(f"No recommendation found for {outcome.token_symbol}")
            return

        # Evaluate if prediction was correct
        if outcome.outcome in ["profit", "loss"]:
            self.total_predictions += 1
            was_correct = self._evaluate_prediction(original_rec, outcome)

            if was_correct:
                self.correct_predictions += 1

            # Update accuracy
            self.prediction_accuracy = self.correct_predictions / self.total_predictions

            logger.info(
                f"Outcome recorded: {outcome.token_symbol} - {outcome.outcome} "
                f"(Predicted: {original_rec.action}, Correct: {was_correct}) "
                f"Accuracy: {self.prediction_accuracy:.1%}"
            )

            # Use AI to learn from this outcome
            if self.ollama_client or self.claude_client:
                await self._learn_from_outcome(original_rec, outcome)

    def _evaluate_prediction(
        self,
        recommendation: AIRecommendation,
        outcome: TradeOutcome
    ) -> bool:
        """Check if prediction was correct."""
        if outcome.outcome == "profit":
            # Profit is good if we recommended buy
            return recommendation.action in ["buy", "strong_buy"]
        elif outcome.outcome == "loss":
            # Loss means we should have avoided
            return recommendation.action in ["hold", "avoid"]
        return False

    async def _learn_from_outcome(
        self,
        recommendation: AIRecommendation,
        outcome: TradeOutcome
    ):
        """Use AI to extract learnings from outcome."""
        client = self.ollama_client if self.preferred_model == "ollama" else self.claude_client

        if not client:
            return

        try:
            # Build learning prompt
            prompt = f"""Learn from this trading outcome to improve future recommendations:

PREDICTION:
Token: {recommendation.token_symbol}
Score: {recommendation.score:.1f}/100
Action: {recommendation.action}
Confidence: {recommendation.confidence:.0%}
Reasoning: {recommendation.reasoning}

ACTUAL OUTCOME:
Entry Price: ${outcome.entry_price or 0:.6f}
Exit Price: ${outcome.exit_price or 0:.6f}
P/L: {outcome.profit_loss_pct or 0:.1f}%
Result: {outcome.outcome}
Notes: {outcome.notes}

Current Accuracy: {self.prediction_accuracy:.1%}

What specific lesson should we learn to improve future predictions? Provide 1-2 actionable insights."""

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            learning = response.content[0].text.strip()
            logger.info(f"🧠 AI Learning: {learning}")

            # Store learning
            if "learnings" not in self.shared_state:
                self.shared_state["learnings"] = []

            self.shared_state["learnings"].append({
                "timestamp": datetime.now().isoformat(),
                "insight": learning,
                "accuracy": self.prediction_accuracy,
                "token": recommendation.token_symbol
            })

        except Exception as e:
            logger.error(f"Learning extraction failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get AI system stats for monitoring."""
        return {
            "total_recommendations": len(self.recommendations),
            "total_outcomes": len(self.outcomes),
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "prediction_accuracy": self.prediction_accuracy,
            "preferred_model": self.preferred_model,
            "ollama_available": self.ollama_client is not None,
            "claude_available": self.claude_client is not None,
            "learnings_count": len(self.shared_state.get("learnings", [])),
            "last_recommendation": (
                asdict(self.recommendations[-1])
                if self.recommendations else None
            )
        }


# Global instance
_ai_service: Optional[SelfCorrectingAI] = None


def get_ai_service(shared_state: Optional[Dict[str, Any]] = None) -> SelfCorrectingAI:
    """Get or create global AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = SelfCorrectingAI(shared_state)
    return _ai_service
