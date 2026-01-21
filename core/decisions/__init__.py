"""
JARVIS Decision Model - Institution-grade decision framework.

Every action-producing component should use this module to:
1. Make explicit EXECUTE / HOLD / ESCALATE decisions
2. Log decisions with rationale for audit trails
3. Track confidence and cost-benefit analysis
4. Enable "do nothing" as a first-class intelligent choice

Usage:
    from core.decisions import DecisionEngine, Decision, DecisionContext

    engine = DecisionEngine(component="x_bot")

    result = await engine.decide(
        context=DecisionContext(
            intent="post_tweet",
            data={"content": "...", "sentiment": 0.7},
            cost_estimate=0.01,  # API cost
            risk_level="low",
        )
    )

    if result.decision == Decision.EXECUTE:
        await post_tweet(...)
    elif result.decision == Decision.HOLD:
        logger.info(f"Holding: {result.rationale}")
    elif result.decision == Decision.ESCALATE:
        await notify_admin(result)
"""

from .model import (
    Decision,
    DecisionResult,
    DecisionContext,
    DecisionRule,
    RiskLevel,
)
from .engine import DecisionEngine, get_decision_engine
from .rules import (
    RateLimitRule,
    DuplicateContentRule,
    CostThresholdRule,
    ConfidenceThresholdRule,
    MaterialityRule,
    CircuitBreakerRule,
)

__all__ = [
    # Core types
    "Decision",
    "DecisionResult",
    "DecisionContext",
    "DecisionRule",
    "RiskLevel",
    # Engine
    "DecisionEngine",
    "get_decision_engine",
    # Built-in rules
    "RateLimitRule",
    "DuplicateContentRule",
    "CostThresholdRule",
    "ConfidenceThresholdRule",
    "MaterialityRule",
    "CircuitBreakerRule",
]
