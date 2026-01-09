"""
Proactive Suggestion Engine for Jarvis Self-Improving Core.

The best agents observe context and surface suggestions only when confident
they'll help. Key principles:
- Only suggest if confidence > 70%
- Cooldown between suggestions (don't spam)
- Learn from which suggestions get accepted vs. dismissed
- At most 3 suggestions per day
- Never suggest during focus time

The engine runs on a background loop, observes context, and generates
suggestions when appropriate.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from core.self_improving.memory.store import MemoryStore
from core.self_improving.trust.ladder import TrustManager, TrustLevel

logger = logging.getLogger("jarvis.proactive")


class SuggestionType(Enum):
    """Types of proactive suggestions."""

    REMINDER = "reminder"
    AUTOMATION = "automation"
    INSIGHT = "insight"
    PREPARATION = "preparation"
    OPTIMIZATION = "optimization"
    WARNING = "warning"


@dataclass
class Suggestion:
    """A proactive suggestion from Jarvis."""

    message: str
    suggestion_type: SuggestionType
    confidence: float  # 0.0-1.0
    action_if_approved: Optional[str] = None
    domain: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "type": self.suggestion_type.value,
            "confidence": self.confidence,
            "action_if_approved": self.action_if_approved,
            "domain": self.domain,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def is_expired(self) -> bool:
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False


@dataclass
class SuggestionOutcome:
    """Outcome of a suggestion."""

    suggestion_id: str
    accepted: bool
    dismissed: bool = False
    feedback: Optional[str] = None
    recorded_at: datetime = field(default_factory=datetime.utcnow)


# Prompt for generating suggestions
SUGGESTION_PROMPT = """You are Jarvis, a personal AI assistant. Analyze the current context and decide if you should proactively suggest something.

Current context:
{context}

User's known facts:
{facts}

Past lessons (apply if relevant):
{reflections}

Recent suggestions made (avoid repeating):
{recent_suggestions}

Trust level in this domain: {trust_level}
At this trust level, I can: {allowed_actions}

Rules:
- Only suggest if confidence > 70%
- Don't repeat suggestions within 2 hours
- Don't suggest during focus time (if indicated)
- Better to stay quiet than annoy the user
- Suggestions should be specific and actionable

If you should suggest something, output:
{{
    "suggest": true,
    "message": "Clear, actionable suggestion",
    "type": "reminder|automation|insight|preparation|optimization|warning",
    "confidence": 0.X,
    "action_if_approved": "What happens if user accepts (or null)",
    "domain": "general|calendar|email|tasks|research|trading"
}}

If you should NOT suggest, output:
{{"suggest": false, "reason": "why not"}}"""


class ProactiveEngine:
    """
    Engine for generating proactive suggestions.

    Usage:
        engine = ProactiveEngine(memory, trust, llm_client)

        # Check for suggestions periodically
        suggestion = await engine.check_for_suggestion(context)
        if suggestion:
            notify_user(suggestion)

        # Record outcome when user responds
        engine.record_outcome(suggestion.id, accepted=True)
    """

    # Configuration
    MIN_CONFIDENCE = 0.7
    COOLDOWN_HOURS = 2
    MAX_DAILY_SUGGESTIONS = 3
    CHECK_INTERVAL_MINUTES = 15

    def __init__(
        self,
        memory: MemoryStore,
        trust: TrustManager,
        llm_client: Optional[Any] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.memory = memory
        self.trust = trust
        self.llm_client = llm_client
        self.model = model

        # State
        self._recent_suggestions: List[Suggestion] = []
        self._outcomes: List[SuggestionOutcome] = []
        self._last_suggestion_time: Optional[datetime] = None
        self._daily_count = 0
        self._daily_reset = datetime.utcnow().date()

    def set_llm_client(self, client: Any):
        """Set the LLM client."""
        self.llm_client = client

    def _reset_daily_count_if_needed(self):
        """Reset daily count at midnight."""
        today = datetime.utcnow().date()
        if today > self._daily_reset:
            self._daily_count = 0
            self._daily_reset = today

    def _is_in_cooldown(self) -> bool:
        """Check if in suggestion cooldown period."""
        if not self._last_suggestion_time:
            return False
        cooldown_end = self._last_suggestion_time + timedelta(hours=self.COOLDOWN_HOURS)
        return datetime.utcnow() < cooldown_end

    def _get_allowed_actions(self, domain: str) -> str:
        """Get description of allowed actions for trust level."""
        level = self.trust.get_level(domain)
        actions = []

        if level >= TrustLevel.ACQUAINTANCE:
            actions.append("suggest actions")
        if level >= TrustLevel.COLLEAGUE:
            actions.append("draft content for review")
        if level >= TrustLevel.PARTNER:
            actions.append("take action autonomously")
        if level >= TrustLevel.OPERATOR:
            actions.append("fully operate this domain")

        return ", ".join(actions) if actions else "only respond when asked"

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for the prompt."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                lines.append(f"{key}: {json.dumps(value, default=str)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _format_recent_suggestions(self) -> str:
        """Format recent suggestions for the prompt."""
        if not self._recent_suggestions:
            return "None"

        recent = [s for s in self._recent_suggestions[-5:]]
        return "\n".join(
            f"- {s.created_at.strftime('%H:%M')}: {s.message[:100]}"
            for s in recent
        )

    def _parse_suggestion(self, response: str, domain: str) -> Optional[Suggestion]:
        """Parse LLM response into a Suggestion."""
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        try:
            data = json.loads(clean)

            if not data.get("suggest", False):
                logger.debug(f"No suggestion: {data.get('reason', 'unknown')}")
                return None

            confidence = float(data.get("confidence", 0.5))
            if confidence < self.MIN_CONFIDENCE:
                logger.debug(f"Suggestion confidence too low: {confidence}")
                return None

            suggestion_type = SuggestionType(data.get("type", "insight"))

            return Suggestion(
                id=f"sug_{datetime.utcnow().timestamp()}",
                message=data["message"],
                suggestion_type=suggestion_type,
                confidence=confidence,
                action_if_approved=data.get("action_if_approved"),
                domain=domain,
                expires_at=datetime.utcnow() + timedelta(hours=4),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse suggestion: {e}")
            return None

    async def check_for_suggestion(
        self,
        context: Dict[str, Any],
        domain: str = "general",
    ) -> Optional[Suggestion]:
        """
        Check if a proactive suggestion should be made.

        Args:
            context: Current context (time, calendar, tasks, etc.)
            domain: The domain to check suggestions for

        Returns:
            Suggestion if appropriate, None otherwise
        """
        self._reset_daily_count_if_needed()

        # Check rate limits
        if self._daily_count >= self.MAX_DAILY_SUGGESTIONS:
            logger.debug("Daily suggestion limit reached")
            return None

        if self._is_in_cooldown():
            logger.debug("In suggestion cooldown")
            return None

        # Check trust level
        if not self.trust.can_suggest(domain):
            logger.debug(f"Trust too low to suggest in {domain}")
            return None

        if not self.llm_client:
            logger.warning("No LLM client for proactive suggestions")
            return None

        # Gather context
        facts = self.memory.search_facts(context.get("current_focus", ""), limit=10)
        facts_text = "\n".join(f"- {f.entity}: {f.fact}" for f in facts) or "None"

        reflections = self.memory.get_relevant_reflections(str(context), limit=3)
        reflections_text = "\n".join(f"- {r.lesson}" for r in reflections) or "None"

        prompt = SUGGESTION_PROMPT.format(
            context=self._format_context(context),
            facts=facts_text,
            reflections=reflections_text,
            recent_suggestions=self._format_recent_suggestions(),
            trust_level=self.trust.get_level(domain).name,
            allowed_actions=self._get_allowed_actions(domain),
        )

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            suggestion = self._parse_suggestion(response_text, domain)

            if suggestion:
                self._recent_suggestions.append(suggestion)
                self._last_suggestion_time = datetime.utcnow()
                self._daily_count += 1

                logger.info(
                    f"Generated suggestion: {suggestion.message[:50]}... "
                    f"(confidence: {suggestion.confidence:.0%})"
                )

            return suggestion

        except Exception as e:
            logger.error(f"Failed to check for suggestions: {e}")
            return None

    def check_for_suggestion_sync(
        self,
        context: Dict[str, Any],
        domain: str = "general",
    ) -> Optional[Suggestion]:
        """Synchronous version of check_for_suggestion."""
        self._reset_daily_count_if_needed()

        if self._daily_count >= self.MAX_DAILY_SUGGESTIONS:
            return None
        if self._is_in_cooldown():
            return None
        if not self.trust.can_suggest(domain):
            return None
        if not self.llm_client:
            return None

        facts = self.memory.search_facts(context.get("current_focus", ""), limit=10)
        facts_text = "\n".join(f"- {f.entity}: {f.fact}" for f in facts) or "None"

        reflections = self.memory.get_relevant_reflections(str(context), limit=3)
        reflections_text = "\n".join(f"- {r.lesson}" for r in reflections) or "None"

        prompt = SUGGESTION_PROMPT.format(
            context=self._format_context(context),
            facts=facts_text,
            reflections=reflections_text,
            recent_suggestions=self._format_recent_suggestions(),
            trust_level=self.trust.get_level(domain).name,
            allowed_actions=self._get_allowed_actions(domain),
        )

        try:
            response = self.llm_client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            suggestion = self._parse_suggestion(response.content[0].text, domain)

            if suggestion:
                self._recent_suggestions.append(suggestion)
                self._last_suggestion_time = datetime.utcnow()
                self._daily_count += 1

            return suggestion

        except Exception as e:
            logger.error(f"Failed to check for suggestions: {e}")
            return None

    def record_outcome(
        self,
        suggestion_id: str,
        accepted: bool,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Record the outcome of a suggestion.

        Call this when user accepts or dismisses a suggestion.
        This affects trust building.
        """
        # Find the suggestion
        suggestion = next(
            (s for s in self._recent_suggestions if s.id == suggestion_id),
            None,
        )

        if not suggestion:
            logger.warning(f"Suggestion {suggestion_id} not found")
            return False

        outcome = SuggestionOutcome(
            suggestion_id=suggestion_id,
            accepted=accepted,
            dismissed=not accepted,
            feedback=feedback,
        )
        self._outcomes.append(outcome)

        # Update trust
        if accepted:
            self.trust.record_success(suggestion.domain)
            logger.info(f"Suggestion accepted: {suggestion.message[:50]}...")
        else:
            self.trust.record_failure(suggestion.domain)
            logger.info(f"Suggestion dismissed: {suggestion.message[:50]}...")

        # Store as interaction for learning
        from core.self_improving.memory.models import Interaction

        self.memory.store_interaction(
            Interaction(
                user_input=f"[SUGGESTION] {suggestion.message}",
                jarvis_response=f"User {'accepted' if accepted else 'dismissed'}",
                feedback="positive" if accepted else "negative",
                metadata={
                    "suggestion_id": suggestion_id,
                    "suggestion_type": suggestion.suggestion_type.value,
                    "confidence": suggestion.confidence,
                },
            )
        )

        return True

    def get_pending_suggestions(self) -> List[Suggestion]:
        """Get suggestions that haven't been responded to yet."""
        responded_ids = {o.suggestion_id for o in self._outcomes}
        return [
            s
            for s in self._recent_suggestions
            if s.id not in responded_ids and not s.is_expired()
        ]

    def get_acceptance_rate(self, domain: Optional[str] = None) -> float:
        """Get the acceptance rate for suggestions."""
        relevant = self._outcomes
        if domain:
            relevant = [
                o for o in self._outcomes
                if any(
                    s.domain == domain and s.id == o.suggestion_id
                    for s in self._recent_suggestions
                )
            ]

        if not relevant:
            return 0.0

        accepted = sum(1 for o in relevant if o.accepted)
        return accepted / len(relevant)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about proactive suggestions."""
        return {
            "total_suggestions": len(self._recent_suggestions),
            "total_outcomes": len(self._outcomes),
            "acceptance_rate": f"{self.get_acceptance_rate():.0%}",
            "daily_count": self._daily_count,
            "daily_limit": self.MAX_DAILY_SUGGESTIONS,
            "in_cooldown": self._is_in_cooldown(),
            "cooldown_ends": (
                (self._last_suggestion_time + timedelta(hours=self.COOLDOWN_HOURS)).isoformat()
                if self._last_suggestion_time
                else None
            ),
        }

    def clear_cooldown(self):
        """Clear the cooldown (admin function)."""
        self._last_suggestion_time = None
        logger.info("Suggestion cooldown cleared")

    def reset_daily_limit(self):
        """Reset daily limit (admin function)."""
        self._daily_count = 0
        logger.info("Daily suggestion limit reset")
