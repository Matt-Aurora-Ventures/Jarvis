"""
X Bot Decision Engine - Integrates the decision framework with X posting.

This module wraps the autonomous X posting logic with institution-grade
decision making, making HOLD a first-class intelligent choice.

Key Features:
1. Pre-Post Validation: Checks content before posting
2. Decision Logging: Full audit trail of all decisions
3. Circuit Breaker: Automatic cooldown on failures
4. Rate Limiting: Intelligent throttling
5. Content Quality: Prevents duplicate/low-value posts
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from core.decisions import (
    DecisionEngine,
    DecisionContext,
    DecisionResult,
    Decision,
    RiskLevel,
    RateLimitRule,
    DuplicateContentRule,
    CostThresholdRule,
    ConfidenceThresholdRule,
    CircuitBreakerRule,
)
from core.decisions.rules import TimeWindowRule

logger = logging.getLogger(__name__)

# Singleton instance
_x_decision_engine: Optional["XDecisionEngine"] = None


class NewInformationRule:
    """
    Checks if the tweet contains new/valuable information.

    Inspired by Prism's "Bold Hold" - don't post just to post.
    """

    name = "new_information"
    description = "Ensures tweet provides new value"
    priority = 40

    def __init__(
        self,
        min_novelty_score: float = 0.3,
        novelty_key: str = "novelty_score",
    ):
        self.min_novelty_score = min_novelty_score
        self.novelty_key = novelty_key
        self._recent_topics: List[tuple] = []  # (topic_hash, timestamp)
        self._max_topics = 100

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> tuple[Decision, str, List[str]]:
        what_would_change = []

        # Get novelty score if provided
        novelty = context.data.get(self.novelty_key, 0.5)

        if novelty < self.min_novelty_score:
            what_would_change.append("Content with higher novelty/information value")
            return (
                Decision.HOLD,
                f"Content novelty {novelty:.0%} below threshold {self.min_novelty_score:.0%} - not worth posting",
                what_would_change,
            )

        return (Decision.EXECUTE, "Content provides new information", [])


class ToneQualityRule:
    """
    Ensures tweet tone matches brand guidelines.
    """

    name = "tone_quality"
    description = "Validates content tone and quality"
    priority = 45

    def __init__(self, banned_patterns: Optional[List[str]] = None):
        self.banned_patterns = banned_patterns or [
            "BREAKING",  # Overused
            "WAGMI",     # Too degen
            "LFG",       # Too degen
            "100x",      # Shilling
            "guaranteed",
            "moonshot",
            "FOMO",
        ]

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> tuple[Decision, str, List[str]]:
        content = context.data.get("content", "")
        content_upper = content.upper()

        for pattern in self.banned_patterns:
            if pattern.upper() in content_upper:
                return (
                    Decision.HOLD,
                    f"Content contains banned pattern '{pattern}'",
                    [f"Remove '{pattern}' from content"],
                )

        return (Decision.EXECUTE, "Tone quality OK", [])


class XDecisionEngine:
    """
    Decision engine specialized for X/Twitter posting.

    Wraps the generic DecisionEngine with X-specific rules and callbacks.
    """

    def __init__(self):
        self.engine = DecisionEngine(
            component="x_bot",
            default_confidence_threshold=0.5,
            default_cost_threshold=0.10,  # $0.10 per tweet (API cost)
            enable_logging=True,
            enable_audit=True,
        )

        # Configure rules
        self._setup_rules()

        # Track decision history for reporting
        self._hold_reasons: Dict[str, int] = {}
        self._last_hold_time: Optional[float] = None

        # Register callbacks
        self.engine.on_escalate(self._on_escalate)

    def _setup_rules(self):
        """Configure decision rules for X posting."""
        # Circuit breaker - highest priority
        self.engine.add_rule(
            CircuitBreakerRule(
                failure_threshold=3,
                recovery_timeout=1800,  # 30 min cooldown
                half_open_max=1,
            )
        )

        # Rate limiting
        self.engine.add_rule(
            RateLimitRule(
                max_per_hour=4,        # Max 4 tweets/hour
                max_per_minute=1,      # Max 1 tweet/minute
                cooldown_seconds=60,   # 60s minimum between posts
                per_intent=False,
            )
        )

        # Cost threshold
        self.engine.add_rule(
            CostThresholdRule(
                max_per_action=0.50,   # $0.50 max per tweet (including image)
                max_per_hour=2.00,     # $2/hour max
                max_per_day=20.00,     # $20/day max
            )
        )

        # Duplicate content
        self.engine.add_rule(
            DuplicateContentRule(
                lookback_hours=48,
                similarity_threshold=0.4,
                content_key="content",
            )
        )

        # Confidence threshold
        self.engine.add_rule(
            ConfidenceThresholdRule(
                min_confidence=0.5,
                escalate_below=0.2,
                confidence_key="confidence",
            )
        )

        # New information check
        self.engine.add_rule(NewInformationRule(min_novelty_score=0.3))

        # Tone quality
        self.engine.add_rule(ToneQualityRule())

    async def _on_escalate(self, result: DecisionResult):
        """Handle escalation decisions - notify admin."""
        try:
            import aiohttp
            import os

            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            admin_ids = os.environ.get("TELEGRAM_ADMIN_IDS", "")

            if not token or not admin_ids:
                return

            admin_list = [x.strip() for x in admin_ids.split(",") if x.strip().isdigit()]
            if not admin_list:
                return

            message = (
                f"⚠️ <b>X Bot Decision Escalation</b>\n\n"
                f"<b>Intent:</b> {result.intent}\n"
                f"<b>Decision:</b> ESCALATE\n"
                f"<b>Confidence:</b> {result.confidence:.0%}\n"
                f"<b>Rationale:</b> {result.rationale[:200]}\n"
                f"<b>What would change:</b>\n"
                + "\n".join(f"  • {w}" for w in result.what_would_change_my_mind[:3])
            )

            async with aiohttp.ClientSession() as session:
                for admin_id in admin_list[:2]:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    await session.post(url, json={
                        "chat_id": admin_id,
                        "text": message,
                        "parse_mode": "HTML",
                    })
        except Exception as e:
            logger.debug(f"Escalation notification failed: {e}")

    async def should_post(
        self,
        content: str,
        category: str,
        confidence: float = 0.7,
        novelty_score: float = 0.5,
        cost: float = 0.01,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """
        Decide whether to post a tweet.

        This is the main entry point for X posting decisions.
        Returns a full DecisionResult with EXECUTE/HOLD/ESCALATE.
        """
        context = DecisionContext(
            intent="post_tweet",
            data={
                "content": content,
                "category": category,
                "confidence": confidence,
                "novelty_score": novelty_score,
                **(metadata or {}),
            },
            cost_estimate=cost,
            risk_level=RiskLevel.LOW,
            metadata={
                "category": category,
                "content_length": len(content),
            },
        )

        result = await self.engine.decide(context)

        # Track hold reasons for reporting
        if result.decision == Decision.HOLD:
            for rule in result.rules_failed:
                self._hold_reasons[rule] = self._hold_reasons.get(rule, 0) + 1
            self._last_hold_time = time.time()

        return result

    async def should_reply(
        self,
        original_tweet: Dict[str, Any],
        reply_content: str,
        sentiment: str = "neutral",
        confidence: float = 0.6,
    ) -> DecisionResult:
        """Decide whether to reply to a tweet."""
        context = DecisionContext(
            intent="reply_tweet",
            data={
                "content": reply_content,
                "original_author": original_tweet.get("author", ""),
                "original_content": original_tweet.get("text", "")[:100],
                "sentiment": sentiment,
                "confidence": confidence,
            },
            cost_estimate=0.005,  # Replies are cheaper
            risk_level=RiskLevel.MEDIUM,  # Replies have brand risk
        )

        return await self.engine.decide(context)

    async def should_generate_image(
        self,
        prompt: str,
        cost: float = 0.02,
    ) -> DecisionResult:
        """Decide whether to generate an image for a tweet."""
        context = DecisionContext(
            intent="generate_image",
            data={
                "prompt": prompt,
                "confidence": 0.8,  # Images are usually intentional
            },
            cost_estimate=cost,
            risk_level=RiskLevel.LOW,
        )

        return await self.engine.decide(context)

    def record_success(self):
        """Record a successful post (resets circuit breaker)."""
        for rule in self.engine.rules:
            if hasattr(rule, "record_success"):
                rule.record_success()

    def record_failure(self, error: str = ""):
        """Record a failed post (trips circuit breaker after threshold)."""
        for rule in self.engine.rules:
            if hasattr(rule, "record_failure"):
                rule.record_failure()
        logger.warning(f"X Bot failure recorded: {error}")

    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics."""
        stats = self.engine.get_stats()
        stats["hold_reasons"] = dict(self._hold_reasons)
        stats["last_hold_time"] = self._last_hold_time
        return stats

    def get_hold_summary(self) -> str:
        """Get a human-readable summary of hold decisions."""
        if not self._hold_reasons:
            return "No holds recorded this session"

        lines = ["Hold reasons this session:"]
        for reason, count in sorted(
            self._hold_reasons.items(), key=lambda x: x[1], reverse=True
        ):
            lines.append(f"  • {reason}: {count}")

        stats = self.engine.get_stats()
        hold_rate = stats.get("hold_rate", 0)
        lines.append(f"\nOverall hold rate: {hold_rate:.0%}")

        return "\n".join(lines)


def get_x_decision_engine() -> XDecisionEngine:
    """Get or create the singleton X decision engine."""
    global _x_decision_engine
    if _x_decision_engine is None:
        _x_decision_engine = XDecisionEngine()
    return _x_decision_engine
