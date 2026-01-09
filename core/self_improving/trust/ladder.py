"""
Trust Ladder for Jarvis Self-Improving Core.

Trust is earned, not given. The system uses gradual autonomy:
- Start by observing
- Progress to suggesting
- Eventually act autonomously (in approved domains)

Trust Levels:
- Level 0 (STRANGER): Only respond when asked
- Level 1 (ACQUAINTANCE): Can suggest, needs approval
- Level 2 (COLLEAGUE): Can draft, needs review
- Level 3 (PARTNER): Can act, reports after
- Level 4 (OPERATOR): Full autonomy in domain

Trust is earned through:
- Accurate predictions that come true
- Suggestions that get accepted
- Zero false positives that waste user attention
- Graceful handling of mistakes
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from core.self_improving.memory.store import MemoryStore

logger = logging.getLogger("jarvis.trust")


class TrustLevel(IntEnum):
    """Trust levels with increasing autonomy."""

    STRANGER = 0  # Only respond when asked
    ACQUAINTANCE = 1  # Can suggest, needs approval
    COLLEAGUE = 2  # Can draft, needs review
    PARTNER = 3  # Can act, reports after
    OPERATOR = 4  # Full autonomy in domain

    @property
    def name_description(self) -> str:
        descriptions = {
            0: "Stranger - Only responds when asked",
            1: "Acquaintance - Can suggest, needs approval",
            2: "Colleague - Can draft, needs review",
            3: "Partner - Can act, reports after",
            4: "Operator - Full autonomy",
        }
        return descriptions.get(self.value, "Unknown")


# Thresholds for trust progression
TRUST_THRESHOLDS = {
    # level: (required_successes, max_failures, required_accuracy)
    1: (5, 2, 0.6),  # 5 successes, max 2 failures, 60% accuracy
    2: (15, 3, 0.7),  # 15 successes, max 3 failures, 70% accuracy
    3: (30, 5, 0.8),  # 30 successes, max 5 failures, 80% accuracy
    4: (50, 5, 0.9),  # 50 successes, max 5 failures, 90% accuracy
}


@dataclass
class TrustState:
    """Current trust state for a domain."""

    domain: str
    level: TrustLevel
    successes: int = 0
    failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    accuracy: float = 0.0
    consecutive_successes: int = 0
    consecutive_failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "level": self.level.value,
            "level_name": self.level.name,
            "successes": self.successes,
            "failures": self.failures,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "accuracy": self.accuracy,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class Permission:
    """A specific permission check result."""

    allowed: bool
    reason: str
    required_level: TrustLevel
    current_level: TrustLevel
    domain: str

    def __bool__(self) -> bool:
        return self.allowed


class TrustManager:
    """
    Manages trust levels and permissions for Jarvis.

    Usage:
        trust = TrustManager(memory)

        # Check if action is allowed
        if trust.can_suggest("calendar"):
            suggest_calendar_action()

        # Record outcomes
        trust.record_success("calendar")  # Suggestion was accepted

        # Get current state
        state = trust.get_state("calendar")
    """

    # Default domains
    DOMAINS = [
        "general",
        "calendar",
        "email",
        "tasks",
        "research",
        "trading",
        "communication",
        "files",
    ]

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self._state_cache: Dict[str, TrustState] = {}
        self._load_all_states()

    def _load_all_states(self):
        """Load trust states from memory."""
        all_trust = self.memory.get_all_trust_levels()
        for domain, data in all_trust.items():
            self._state_cache[domain] = TrustState(
                domain=domain,
                level=TrustLevel(data.get("level", 0)),
                successes=data.get("successes", 0),
                failures=data.get("failures", 0),
                last_success=datetime.fromisoformat(data["last_success"])
                if data.get("last_success")
                else None,
                last_failure=datetime.fromisoformat(data["last_failure"])
                if data.get("last_failure")
                else None,
            )

    def _get_state(self, domain: str) -> TrustState:
        """Get trust state for a domain, creating if needed."""
        if domain not in self._state_cache:
            self._state_cache[domain] = TrustState(
                domain=domain,
                level=TrustLevel.STRANGER,
            )
        return self._state_cache[domain]

    def _update_accuracy(self, state: TrustState):
        """Update accuracy calculation for a state."""
        total = state.successes + state.failures
        state.accuracy = state.successes / total if total > 0 else 0.0

    def _check_promotion(self, state: TrustState) -> bool:
        """Check if state qualifies for promotion."""
        next_level = state.level + 1
        if next_level > TrustLevel.OPERATOR:
            return False

        threshold = TRUST_THRESHOLDS.get(next_level)
        if not threshold:
            return False

        req_successes, max_failures, req_accuracy = threshold

        # Check all conditions
        if state.successes < req_successes:
            return False
        if state.failures > max_failures:
            return False
        if state.accuracy < req_accuracy:
            return False
        if state.consecutive_successes < 3:  # Need some momentum
            return False

        return True

    def _check_demotion(self, state: TrustState) -> bool:
        """Check if state should be demoted."""
        if state.level == TrustLevel.STRANGER:
            return False

        # Demote on 3 consecutive failures
        if state.consecutive_failures >= 3:
            return True

        # Demote if accuracy drops significantly below threshold
        current_threshold = TRUST_THRESHOLDS.get(state.level, (0, 0, 0.5))
        if state.accuracy < current_threshold[2] - 0.15:  # 15% below threshold
            return True

        return False

    # =========================================================================
    # PUBLIC API - Permission Checks
    # =========================================================================

    def get_level(self, domain: str = "general") -> TrustLevel:
        """Get current trust level for a domain."""
        return self._get_state(domain).level

    def get_state(self, domain: str = "general") -> TrustState:
        """Get full trust state for a domain."""
        state = self._get_state(domain)
        self._update_accuracy(state)
        return state

    def can_observe(self, domain: str = "general") -> Permission:
        """Check if can observe (always allowed at any level)."""
        state = self._get_state(domain)
        return Permission(
            allowed=True,
            reason="Observation is always allowed",
            required_level=TrustLevel.STRANGER,
            current_level=state.level,
            domain=domain,
        )

    def can_suggest(self, domain: str = "general") -> Permission:
        """Check if can proactively suggest (level 1+)."""
        state = self._get_state(domain)
        allowed = state.level >= TrustLevel.ACQUAINTANCE
        return Permission(
            allowed=allowed,
            reason="Can suggest" if allowed else "Need ACQUAINTANCE level to suggest",
            required_level=TrustLevel.ACQUAINTANCE,
            current_level=state.level,
            domain=domain,
        )

    def can_draft(self, domain: str = "general") -> Permission:
        """Check if can draft (emails, documents) for review (level 2+)."""
        state = self._get_state(domain)
        allowed = state.level >= TrustLevel.COLLEAGUE
        return Permission(
            allowed=allowed,
            reason="Can draft" if allowed else "Need COLLEAGUE level to draft",
            required_level=TrustLevel.COLLEAGUE,
            current_level=state.level,
            domain=domain,
        )

    def can_act(self, domain: str = "general") -> Permission:
        """Check if can take action autonomously (level 3+)."""
        state = self._get_state(domain)
        allowed = state.level >= TrustLevel.PARTNER
        return Permission(
            allowed=allowed,
            reason="Can act" if allowed else "Need PARTNER level to act autonomously",
            required_level=TrustLevel.PARTNER,
            current_level=state.level,
            domain=domain,
        )

    def can_operate(self, domain: str = "general") -> Permission:
        """Check if can fully operate domain (level 4)."""
        state = self._get_state(domain)
        allowed = state.level >= TrustLevel.OPERATOR
        return Permission(
            allowed=allowed,
            reason="Full operator access" if allowed else "Need OPERATOR level",
            required_level=TrustLevel.OPERATOR,
            current_level=state.level,
            domain=domain,
        )

    def check_permission(
        self,
        action: str,
        domain: str = "general",
    ) -> Permission:
        """
        Check if an action type is allowed.

        Actions: observe, suggest, draft, act, operate
        """
        checks = {
            "observe": self.can_observe,
            "suggest": self.can_suggest,
            "draft": self.can_draft,
            "act": self.can_act,
            "operate": self.can_operate,
        }

        check_func = checks.get(action.lower())
        if not check_func:
            return Permission(
                allowed=False,
                reason=f"Unknown action type: {action}",
                required_level=TrustLevel.OPERATOR,
                current_level=self._get_state(domain).level,
                domain=domain,
            )

        return check_func(domain)

    # =========================================================================
    # PUBLIC API - Trust Building
    # =========================================================================

    def record_success(self, domain: str = "general") -> TrustState:
        """
        Record a successful interaction.

        Call this when:
        - A suggestion is accepted
        - A prediction comes true
        - An action succeeds
        - User gives positive feedback
        """
        state = self._get_state(domain)
        state.successes += 1
        state.consecutive_successes += 1
        state.consecutive_failures = 0
        state.last_success = datetime.utcnow()
        self._update_accuracy(state)

        # Check for promotion
        if self._check_promotion(state):
            self._promote(state)

        # Persist
        self.memory.record_trust_success(domain)
        self.memory.set_trust_level(domain, state.level)

        logger.info(
            f"Trust success in {domain}: level={state.level.name}, "
            f"successes={state.successes}, accuracy={state.accuracy:.0%}"
        )

        return state

    def record_failure(
        self,
        domain: str = "general",
        major: bool = False,
    ) -> TrustState:
        """
        Record a failed interaction.

        Call this when:
        - A suggestion is rejected
        - A prediction is wrong
        - An action fails
        - User gives negative feedback

        Args:
            domain: The domain of the failure
            major: If True, immediately demote (for serious failures)
        """
        state = self._get_state(domain)
        state.failures += 1
        state.consecutive_failures += 1
        state.consecutive_successes = 0
        state.last_failure = datetime.utcnow()
        self._update_accuracy(state)

        # Major failure = immediate demotion
        if major:
            self._demote(state)
        elif self._check_demotion(state):
            self._demote(state)

        # Persist
        self.memory.record_trust_failure(domain)
        self.memory.set_trust_level(domain, state.level)

        logger.warning(
            f"Trust failure in {domain}: level={state.level.name}, "
            f"failures={state.failures}, accuracy={state.accuracy:.0%}"
        )

        return state

    def _promote(self, state: TrustState):
        """Promote trust level."""
        old_level = state.level
        state.level = TrustLevel(min(state.level + 1, TrustLevel.OPERATOR))
        logger.info(f"Trust promoted in {state.domain}: {old_level.name} -> {state.level.name}")

    def _demote(self, state: TrustState):
        """Demote trust level."""
        old_level = state.level
        state.level = TrustLevel(max(state.level - 1, TrustLevel.STRANGER))
        state.consecutive_failures = 0  # Reset after demotion
        logger.warning(f"Trust demoted in {state.domain}: {old_level.name} -> {state.level.name}")

    def set_level(self, domain: str, level: int) -> TrustState:
        """
        Manually set trust level (admin override).

        Use sparingly - trust should usually be earned.
        """
        state = self._get_state(domain)
        state.level = TrustLevel(max(0, min(4, level)))
        self.memory.set_trust_level(domain, state.level)

        logger.info(f"Trust level manually set for {domain}: {state.level.name}")
        return state

    def reset_domain(self, domain: str) -> TrustState:
        """Reset trust for a domain to initial state."""
        state = TrustState(domain=domain, level=TrustLevel.STRANGER)
        self._state_cache[domain] = state
        self.memory.set_trust_level(domain, 0)

        logger.info(f"Trust reset for {domain}")
        return state

    # =========================================================================
    # PUBLIC API - Status and Reporting
    # =========================================================================

    def get_all_states(self) -> Dict[str, TrustState]:
        """Get trust states for all domains."""
        for domain in self.DOMAINS:
            if domain not in self._state_cache:
                self._get_state(domain)
        return self._state_cache

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of trust across all domains."""
        states = self.get_all_states()
        return {
            "domains": {
                domain: {
                    "level": state.level.name,
                    "level_value": state.level.value,
                    "accuracy": f"{state.accuracy:.0%}",
                    "can_suggest": state.level >= TrustLevel.ACQUAINTANCE,
                    "can_draft": state.level >= TrustLevel.COLLEAGUE,
                    "can_act": state.level >= TrustLevel.PARTNER,
                }
                for domain, state in states.items()
            },
            "highest_trust": max(
                states.values(),
                key=lambda s: s.level,
                default=TrustState("none", TrustLevel.STRANGER),
            ).domain,
            "total_successes": sum(s.successes for s in states.values()),
            "total_failures": sum(s.failures for s in states.values()),
        }

    def get_progress_to_next_level(self, domain: str = "general") -> Dict[str, Any]:
        """Get progress toward next trust level."""
        state = self._get_state(domain)
        next_level = state.level + 1

        if next_level > TrustLevel.OPERATOR:
            return {
                "domain": domain,
                "current_level": state.level.name,
                "next_level": None,
                "message": "Already at maximum trust level",
            }

        threshold = TRUST_THRESHOLDS.get(next_level, (0, 0, 0))
        req_successes, max_failures, req_accuracy = threshold

        return {
            "domain": domain,
            "current_level": state.level.name,
            "next_level": TrustLevel(next_level).name,
            "progress": {
                "successes": f"{state.successes}/{req_successes}",
                "failures": f"{state.failures}/{max_failures}",
                "accuracy": f"{state.accuracy:.0%}/{req_accuracy:.0%}",
                "consecutive_successes": state.consecutive_successes,
            },
            "needs": {
                "more_successes": max(0, req_successes - state.successes),
                "accuracy_gap": max(0, req_accuracy - state.accuracy),
            },
        }

    def explain_denial(self, permission: Permission) -> str:
        """Generate user-friendly explanation for permission denial."""
        if permission.allowed:
            return "Action is allowed"

        state = self._get_state(permission.domain)
        progress = self.get_progress_to_next_level(permission.domain)

        return (
            f"I can't {permission.required_level.name.lower()} in {permission.domain} yet. "
            f"Current trust level: {state.level.name}. "
            f"Need: {permission.required_level.name}. "
            f"Progress: {progress['progress']['successes']} successes, "
            f"{progress['progress']['accuracy']} accuracy."
        )
