#!/usr/bin/env python3
"""
Bags Intel Webapp - Supervisor Integration
Connects the intelligence webapp with the JARVIS supervisor and other bots.
"""

import asyncio
import logging
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

logger = logging.getLogger("jarvis.bags_intel.supervisor")


@dataclass
class IntelligenceFeedback:
    """Feedback from trading/actions taken on intelligence."""
    contract_address: str
    token_name: str
    token_symbol: str
    our_score: float
    action_taken: str  # "bought", "passed", "sold"
    action_timestamp: datetime
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    outcome: Optional[str] = None  # "profit", "loss", "pending"
    profit_loss_percent: Optional[float] = None
    notes: str = ""


@dataclass
class IntelligenceSharing:
    """Intelligence shared with other components."""
    contract_address: str
    token_name: str
    symbol: str
    overall_score: float
    risk_level: str
    bonding_score: float
    creator_score: float
    market_score: float
    liquidity_sol: float
    market_cap: float
    holder_count: int
    recommendation: str  # "strong_buy", "buy", "hold", "avoid"
    confidence: float  # 0-1
    reasoning: str  # AI-generated explanation
    timestamp: datetime


class SupervisorBridge:
    """
    Bridge between Bags Intel webapp and JARVIS supervisor.
    Enables cross-component communication and AI-powered learning.
    """

    def __init__(self, shared_state: Optional[Dict[str, Any]] = None):
        self.shared_state = shared_state or {}
        self.feedback_history: List[IntelligenceFeedback] = []
        self.shared_intelligence: List[IntelligenceSharing] = []

        # Stats for self-correction
        self.prediction_accuracy = 0.0
        self.total_predictions = 0
        self.correct_predictions = 0

        # AI client (will be initialized if Ollama is available)
        self.ai_client = None
        self.ollama_available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Check if Ollama is available for AI recommendations."""
        try:
            import anthropic
            # Check if Ollama proxy is configured
            ollama_base_url = os.environ.get("ANTHROPIC_BASE_URL")
            if ollama_base_url:
                logger.info(f"Ollama available at: {ollama_base_url}")
                self.ai_client = anthropic.Anthropic(
                    api_key="ollama",  # Dummy key for local Ollama
                    base_url=ollama_base_url
                )
                return True
            return False
        except ImportError:
            logger.warning("Anthropic library not available")
            return False

    async def share_intelligence(
        self,
        graduation_event: Dict[str, Any],
        ai_reasoning: bool = True
    ) -> IntelligenceSharing:
        """
        Share intelligence about a token graduation with other components.

        Args:
            graduation_event: The raw graduation event data
            ai_reasoning: Whether to generate AI-powered reasoning

        Returns:
            IntelligenceSharing object
        """
        scores = graduation_event.get("scores", {})
        market = graduation_event.get("market_metrics", {})

        # Determine recommendation based on scores
        overall_score = scores.get("overall", 0)
        risk_level = scores.get("risk_level", "medium").lower()

        recommendation, confidence = self._calculate_recommendation(
            overall_score, risk_level, scores, market
        )

        # Generate AI reasoning if enabled and available
        reasoning = ""
        if ai_reasoning and self.ollama_available:
            reasoning = await self._generate_ai_reasoning(
                graduation_event, recommendation, confidence
            )
        else:
            reasoning = self._generate_rule_based_reasoning(
                overall_score, risk_level, scores
            )

        intel = IntelligenceSharing(
            contract_address=graduation_event["contract_address"],
            token_name=graduation_event["token_name"],
            symbol=graduation_event.get("symbol", "UNKNOWN"),
            overall_score=overall_score,
            risk_level=risk_level,
            bonding_score=scores.get("bonding", 0),
            creator_score=scores.get("creator", 0),
            market_score=scores.get("market", 0),
            liquidity_sol=market.get("liquidity_sol", 0),
            market_cap=market.get("market_cap", 0),
            holder_count=graduation_event.get("holder_count", 0),
            recommendation=recommendation,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now()
        )

        self.shared_intelligence.append(intel)

        # Store in shared state for other components
        if "bags_intel" not in self.shared_state:
            self.shared_state["bags_intel"] = {"intelligence": []}

        self.shared_state["bags_intel"]["intelligence"].append(asdict(intel))

        logger.info(
            f"Shared intelligence: {intel.token_name} "
            f"(Score: {intel.overall_score:.1f}, Rec: {recommendation})"
        )

        return intel

    def _calculate_recommendation(
        self,
        overall_score: float,
        risk_level: str,
        scores: Dict[str, Any],
        market: Dict[str, Any]
    ) -> tuple[str, float]:
        """
        Calculate buy recommendation and confidence.

        Returns:
            (recommendation, confidence) tuple
        """
        # Base recommendation on score
        if overall_score >= 80 and risk_level in ["low", "medium"]:
            base_rec = "strong_buy"
            base_confidence = 0.85
        elif overall_score >= 65 and risk_level != "extreme":
            base_rec = "buy"
            base_confidence = 0.70
        elif overall_score >= 50:
            base_rec = "hold"
            base_confidence = 0.55
        else:
            base_rec = "avoid"
            base_confidence = 0.80

        # Adjust confidence based on historical accuracy
        if self.total_predictions > 10:
            accuracy_factor = self.prediction_accuracy
            adjusted_confidence = base_confidence * (0.7 + 0.3 * accuracy_factor)
        else:
            adjusted_confidence = base_confidence * 0.8  # Lower confidence early on

        # Boost/penalize based on specific metrics
        liquidity = market.get("liquidity_sol", 0)
        if liquidity < 10 and base_rec in ["strong_buy", "buy"]:
            adjusted_confidence *= 0.7  # Low liquidity penalty

        bonding_score = scores.get("bonding", 0)
        if bonding_score >= 80 and base_rec in ["strong_buy", "buy"]:
            adjusted_confidence = min(0.95, adjusted_confidence * 1.1)  # Bonding boost

        return base_rec, min(0.95, max(0.3, adjusted_confidence))

    def _generate_rule_based_reasoning(
        self,
        overall_score: float,
        risk_level: str,
        scores: Dict[str, Any]
    ) -> str:
        """Generate reasoning without AI (fallback)."""
        reasons = []

        if overall_score >= 80:
            reasons.append("Exceptional overall score indicates strong fundamentals")
        elif overall_score >= 65:
            reasons.append("Above-average score with solid metrics")
        elif overall_score < 50:
            reasons.append("Below-average score suggests caution")

        if risk_level == "low":
            reasons.append("Low risk profile with verified creator")
        elif risk_level == "extreme":
            reasons.append("Extreme risk - multiple red flags detected")

        bonding = scores.get("bonding", 0)
        if bonding >= 80:
            reasons.append("Strong bonding curve performance")

        creator = scores.get("creator", 0)
        if creator >= 75:
            reasons.append("Reputable creator with proven track record")
        elif creator < 40:
            reasons.append("Unverified or new creator")

        return ". ".join(reasons) + "."

    async def _generate_ai_reasoning(
        self,
        graduation_event: Dict[str, Any],
        recommendation: str,
        confidence: float
    ) -> str:
        """Generate AI-powered reasoning using Ollama/Claude."""
        if not self.ai_client:
            return self._generate_rule_based_reasoning(
                graduation_event["scores"]["overall"],
                graduation_event["scores"]["risk_level"],
                graduation_event["scores"]
            )

        try:
            # Build prompt for AI
            prompt = self._build_ai_prompt(graduation_event, recommendation, confidence)

            # Call Ollama via Anthropic API
            response = await asyncio.to_thread(
                self.ai_client.messages.create,
                model="claude-3-5-sonnet-20241022",  # Routed to Ollama
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            reasoning = response.content[0].text.strip()
            return reasoning

        except Exception as e:
            logger.error(f"AI reasoning generation failed: {e}")
            return self._generate_rule_based_reasoning(
                graduation_event["scores"]["overall"],
                graduation_event["scores"]["risk_level"],
                graduation_event["scores"]
            )

    def _build_ai_prompt(
        self,
        event: Dict[str, Any],
        recommendation: str,
        confidence: float
    ) -> str:
        """Build prompt for AI reasoning generation."""
        scores = event["scores"]
        market = event.get("market_metrics", {})

        return f"""You are analyzing a bags.fm token graduation for investment potential.

Token: {event['token_name']} ({event.get('symbol', 'N/A')})
Overall Score: {scores['overall']:.1f}/100
Risk Level: {scores['risk_level']}

Component Scores:
- Bonding: {scores.get('bonding', 0):.1f}/100
- Creator: {scores.get('creator', 0):.1f}/100
- Social: {scores.get('social', 0):.1f}/100
- Market: {scores.get('market', 0):.1f}/100
- Distribution: {scores.get('distribution', 0):.1f}/100

Market Metrics:
- Liquidity: {market.get('liquidity_sol', 0):.1f} SOL
- Market Cap: ${market.get('market_cap', 0):,.0f}
- 24h Volume: ${market.get('volume_24h', 0):,.0f}

Recommendation: {recommendation.upper()}
Confidence: {confidence:.0%}

Your Accuracy: {self.prediction_accuracy:.1%} (based on {self.total_predictions} past predictions)

Provide a concise 2-3 sentence explanation of WHY this recommendation makes sense given the data. Focus on the most important factors."""

    async def receive_feedback(self, feedback: IntelligenceFeedback):
        """
        Receive feedback from treasury bot or other components about outcomes.
        This enables self-correction and learning.
        """
        self.feedback_history.append(feedback)

        # Update prediction accuracy
        if feedback.outcome in ["profit", "loss"]:
            self.total_predictions += 1

            # Find the original intelligence shared for this token
            original_intel = next(
                (i for i in self.shared_intelligence
                 if i.contract_address == feedback.contract_address),
                None
            )

            if original_intel:
                # Check if prediction was correct
                was_correct = self._evaluate_prediction(original_intel, feedback)
                if was_correct:
                    self.correct_predictions += 1

                self.prediction_accuracy = (
                    self.correct_predictions / self.total_predictions
                )

                logger.info(
                    f"Feedback processed: {feedback.token_name} "
                    f"({feedback.outcome}) - Accuracy: {self.prediction_accuracy:.1%}"
                )

                # If AI is available, learn from this feedback
                if self.ollama_available:
                    await self._ai_learning_update(original_intel, feedback)

    def _evaluate_prediction(
        self,
        intel: IntelligenceSharing,
        feedback: IntelligenceFeedback
    ) -> bool:
        """Evaluate if our recommendation was correct based on outcome."""
        rec = intel.recommendation

        if feedback.outcome == "profit":
            # Profit is good if we recommended buy/strong_buy
            return rec in ["buy", "strong_buy"]
        elif feedback.outcome == "loss":
            # Loss means we should have recommended hold/avoid
            return rec in ["hold", "avoid"]

        return False  # Can't evaluate if outcome is "pending"

    async def _ai_learning_update(
        self,
        intel: IntelligenceSharing,
        feedback: IntelligenceFeedback
    ):
        """Use AI to learn from feedback and adjust future recommendations."""
        if not self.ai_client:
            return

        try:
            # Build learning prompt
            prompt = f"""You are learning from past trading outcomes to improve future recommendations.

PAST PREDICTION:
Token: {intel.token_name}
Score: {intel.overall_score:.1f}
Recommendation: {intel.recommendation}
Confidence: {intel.confidence:.0%}
Reasoning: {intel.reasoning}

ACTUAL OUTCOME:
Action: {feedback.action_taken}
Entry: ${feedback.entry_price or 0:.6f}
Exit: ${feedback.exit_price or 0:.6f}
P/L: {feedback.profit_loss_percent or 0:.1f}%
Result: {feedback.outcome}

What should we learn from this outcome to improve future recommendations? Provide 1-2 specific insights."""

            response = await asyncio.to_thread(
                self.ai_client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}]
            )

            learning = response.content[0].text.strip()
            logger.info(f"AI Learning: {learning}")

            # Store learning for future reference
            if "learnings" not in self.shared_state:
                self.shared_state["learnings"] = []
            self.shared_state["learnings"].append({
                "timestamp": datetime.now().isoformat(),
                "insight": learning,
                "accuracy": self.prediction_accuracy
            })

        except Exception as e:
            logger.error(f"AI learning update failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get intelligence system stats for monitoring."""
        return {
            "total_intelligence_shared": len(self.shared_intelligence),
            "feedback_received": len(self.feedback_history),
            "prediction_accuracy": self.prediction_accuracy,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "ollama_available": self.ollama_available,
            "last_intelligence": (
                asdict(self.shared_intelligence[-1])
                if self.shared_intelligence else None
            )
        }


# Global instance
_supervisor_bridge = None


def get_supervisor_bridge(shared_state: Optional[Dict[str, Any]] = None) -> SupervisorBridge:
    """Get or create the global supervisor bridge instance."""
    global _supervisor_bridge
    if _supervisor_bridge is None:
        _supervisor_bridge = SupervisorBridge(shared_state)
    return _supervisor_bridge
