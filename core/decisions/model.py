"""
Core decision model types.

This module defines the fundamental types for the decision framework:
- Decision: The three possible outcomes (EXECUTE, HOLD, ESCALATE)
- DecisionResult: Complete decision with rationale and metadata
- DecisionContext: Input context for making decisions
- DecisionRule: Base class for decision rules
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import hashlib
import json


class Decision(Enum):
    """
    The three fundamental decision outcomes.

    EXECUTE: Proceed with the action
    HOLD: Do not act - this is an intelligent choice, not inaction
    ESCALATE: Requires human review or higher-level decision
    """
    EXECUTE = "execute"
    HOLD = "hold"
    ESCALATE = "escalate"


class RiskLevel(Enum):
    """Risk classification for actions."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DecisionContext:
    """
    Input context for making a decision.

    Attributes:
        intent: What action is being considered (e.g., "post_tweet", "execute_trade")
        data: Relevant data for the decision
        cost_estimate: Estimated cost of the action (money, API calls, etc.)
        risk_level: Classification of risk
        urgency: How time-sensitive is this (0-1, higher = more urgent)
        metadata: Additional context for logging/debugging
    """
    intent: str
    data: Dict[str, Any] = field(default_factory=dict)
    cost_estimate: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    urgency: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        """Generate a hash of the content for deduplication."""
        content = json.dumps(self.data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class DecisionResult:
    """
    Complete decision outcome with audit trail.

    This is the core output that makes "HOLD" a first-class decision.
    Every field is designed for transparency and accountability.
    """
    # Core decision
    decision: Decision
    confidence: float  # 0.0 to 1.0

    # Rationale - the "why"
    rationale: str
    rules_applied: List[str] = field(default_factory=list)
    rules_passed: List[str] = field(default_factory=list)
    rules_failed: List[str] = field(default_factory=list)

    # Context preservation
    intent: str = ""
    context_hash: str = ""

    # Cost-benefit analysis
    cost_estimate: float = 0.0
    benefit_estimate: float = 0.0
    materiality_checked: bool = False
    materiality_threshold: Optional[float] = None

    # What would change the decision
    what_would_change_my_mind: List[str] = field(default_factory=list)

    # Timing
    decided_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # Audit metadata
    component: str = ""
    decision_id: str = ""

    def __post_init__(self):
        """Generate decision ID if not provided."""
        if not self.decision_id:
            timestamp = self.decided_at.strftime("%Y%m%d%H%M%S%f")
            self.decision_id = f"{self.component}_{self.intent}_{timestamp}"[:64]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "rules_applied": self.rules_applied,
            "rules_passed": self.rules_passed,
            "rules_failed": self.rules_failed,
            "intent": self.intent,
            "context_hash": self.context_hash,
            "cost_estimate": self.cost_estimate,
            "benefit_estimate": self.benefit_estimate,
            "materiality_checked": self.materiality_checked,
            "materiality_threshold": self.materiality_threshold,
            "what_would_change_my_mind": self.what_would_change_my_mind,
            "decided_at": self.decided_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "component": self.component,
            "decision_id": self.decision_id,
        }

    def is_actionable(self) -> bool:
        """Check if the decision allows action."""
        return self.decision == Decision.EXECUTE

    def should_escalate(self) -> bool:
        """Check if the decision requires human review."""
        return self.decision == Decision.ESCALATE

    def summary(self) -> str:
        """Human-readable summary."""
        emoji = {
            Decision.EXECUTE: "✅",
            Decision.HOLD: "⏸️",
            Decision.ESCALATE: "⚠️",
        }.get(self.decision, "❓")

        return (
            f"{emoji} {self.decision.value.upper()} "
            f"[{self.intent}] "
            f"(confidence: {self.confidence:.0%}) - "
            f"{self.rationale}"
        )


class DecisionRule(ABC):
    """
    Base class for decision rules.

    Rules evaluate a context and return whether to allow/deny the action,
    along with rationale for the decision.
    """
    name: str = "base_rule"
    description: str = "Base decision rule"
    priority: int = 100  # Lower = evaluated first

    @abstractmethod
    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> tuple[Decision, str, List[str]]:
        """
        Evaluate the rule against the context.

        Args:
            context: The decision context
            current_decision: The current decision state (from prior rules)

        Returns:
            Tuple of (decision, rationale, what_would_change)
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} priority={self.priority}>"
