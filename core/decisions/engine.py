"""
Decision Engine - Orchestrates rules to make decisions.

The engine:
1. Accepts a context describing a potential action
2. Runs it through configured rules
3. Returns a complete DecisionResult with full audit trail
4. Logs all decisions for accountability
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .model import (
    Decision,
    DecisionResult,
    DecisionContext,
    DecisionRule,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Global engine registry
_engines: Dict[str, "DecisionEngine"] = {}


@dataclass
class DecisionStats:
    """Track decision statistics for a component."""
    total_decisions: int = 0
    executes: int = 0
    holds: int = 0
    escalates: int = 0
    total_cost_approved: float = 0.0
    total_cost_prevented: float = 0.0
    avg_confidence: float = 0.0
    last_decision_at: Optional[datetime] = None


class DecisionEngine:
    """
    Core decision engine for a component.

    Usage:
        engine = DecisionEngine(component="x_bot")
        engine.add_rule(RateLimitRule(max_per_hour=10))
        engine.add_rule(ConfidenceThresholdRule(min_confidence=0.6))

        result = await engine.decide(context)
        if result.decision == Decision.EXECUTE:
            # proceed
    """

    def __init__(
        self,
        component: str,
        default_confidence_threshold: float = 0.5,
        default_cost_threshold: float = 10.0,
        enable_logging: bool = True,
        enable_audit: bool = True,
    ):
        self.component = component
        self.default_confidence_threshold = default_confidence_threshold
        self.default_cost_threshold = default_cost_threshold
        self.enable_logging = enable_logging
        self.enable_audit = enable_audit

        self.rules: List[DecisionRule] = []
        self.stats = DecisionStats()
        self._decision_history: List[DecisionResult] = []
        self._max_history = 1000

        # Callbacks for external integrations
        self._on_decision_callbacks: List[callable] = []
        self._on_escalate_callbacks: List[callable] = []

    def add_rule(self, rule: DecisionRule) -> "DecisionEngine":
        """Add a rule to the engine. Returns self for chaining."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
        return self

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        return len(self.rules) < before

    def on_decision(self, callback: callable) -> None:
        """Register callback for all decisions."""
        self._on_decision_callbacks.append(callback)

    def on_escalate(self, callback: callable) -> None:
        """Register callback for escalation decisions."""
        self._on_escalate_callbacks.append(callback)

    async def decide(
        self,
        context: DecisionContext,
        override_rules: Optional[List[DecisionRule]] = None,
    ) -> DecisionResult:
        """
        Make a decision based on context and rules.

        This is the core method that implements the decision framework.
        """
        start_time = datetime.utcnow()
        rules_to_apply = override_rules if override_rules else self.rules

        # Start with EXECUTE and let rules demote if needed
        current_decision = Decision.EXECUTE
        rationale_parts: List[str] = []
        rules_applied: List[str] = []
        rules_passed: List[str] = []
        rules_failed: List[str] = []
        what_would_change: List[str] = []
        confidence = 1.0

        # Apply each rule in priority order
        for rule in rules_to_apply:
            try:
                decision, rule_rationale, changes = await rule.evaluate(
                    context, current_decision
                )
                rules_applied.append(rule.name)

                if decision == Decision.HOLD:
                    # Rule says HOLD - this overrides EXECUTE
                    if current_decision == Decision.EXECUTE:
                        current_decision = Decision.HOLD
                        rationale_parts.append(f"[{rule.name}] {rule_rationale}")
                        rules_failed.append(rule.name)
                        confidence *= 0.8  # Reduce confidence on holds
                    what_would_change.extend(changes)

                elif decision == Decision.ESCALATE:
                    # Escalation takes priority over everything
                    current_decision = Decision.ESCALATE
                    rationale_parts.append(f"[{rule.name}] ESCALATE: {rule_rationale}")
                    rules_failed.append(rule.name)
                    what_would_change.extend(changes)

                else:
                    # Rule passed
                    rules_passed.append(rule.name)

            except Exception as e:
                logger.error(f"Rule {rule.name} failed: {e}")
                # On rule error, escalate for safety
                current_decision = Decision.ESCALATE
                rationale_parts.append(f"[{rule.name}] Rule error: {e}")
                rules_failed.append(rule.name)
                what_would_change.append(f"Fix rule error in {rule.name}")

        # Build final rationale
        if current_decision == Decision.EXECUTE:
            rationale = f"All {len(rules_passed)} rules passed"
        elif not rationale_parts:
            rationale = "No rules configured"
        else:
            rationale = "; ".join(rationale_parts)

        # Calculate cost-benefit
        benefit_estimate = self._estimate_benefit(context)
        materiality_threshold = self._get_materiality_threshold(context)
        materiality_checked = context.cost_estimate <= materiality_threshold

        # Check if cost exceeds threshold - potential HOLD
        if (
            context.cost_estimate > self.default_cost_threshold
            and current_decision == Decision.EXECUTE
        ):
            current_decision = Decision.ESCALATE
            rationale = f"Cost ${context.cost_estimate:.2f} exceeds threshold ${self.default_cost_threshold:.2f}"
            what_would_change.append(f"Lower cost below ${self.default_cost_threshold:.2f}")

        # Create result
        result = DecisionResult(
            decision=current_decision,
            confidence=max(0.0, min(1.0, confidence)),
            rationale=rationale,
            rules_applied=rules_applied,
            rules_passed=rules_passed,
            rules_failed=rules_failed,
            intent=context.intent,
            context_hash=context.content_hash(),
            cost_estimate=context.cost_estimate,
            benefit_estimate=benefit_estimate,
            materiality_checked=materiality_checked,
            materiality_threshold=materiality_threshold,
            what_would_change_my_mind=what_would_change,
            decided_at=start_time,
            component=self.component,
        )

        # Update stats
        self._update_stats(result)

        # Log decision
        if self.enable_logging:
            self._log_decision(result)

        # Store in history
        self._decision_history.append(result)
        if len(self._decision_history) > self._max_history:
            self._decision_history = self._decision_history[-self._max_history:]

        # Fire callbacks
        await self._fire_callbacks(result)

        return result

    async def quick_decide(
        self,
        intent: str,
        data: Optional[Dict[str, Any]] = None,
        cost: float = 0.0,
        risk: RiskLevel = RiskLevel.LOW,
    ) -> DecisionResult:
        """Convenience method for quick decisions."""
        context = DecisionContext(
            intent=intent,
            data=data or {},
            cost_estimate=cost,
            risk_level=risk,
        )
        return await self.decide(context)

    def _estimate_benefit(self, context: DecisionContext) -> float:
        """Estimate the benefit of executing the action."""
        # Default implementation - override in subclasses
        base_benefit = 1.0

        # Higher urgency = higher benefit
        if context.urgency > 0.5:
            base_benefit *= 1.5

        # Lower risk = higher benefit
        risk_multipliers = {
            RiskLevel.NONE: 2.0,
            RiskLevel.LOW: 1.5,
            RiskLevel.MEDIUM: 1.0,
            RiskLevel.HIGH: 0.5,
            RiskLevel.CRITICAL: 0.1,
        }
        base_benefit *= risk_multipliers.get(context.risk_level, 1.0)

        return base_benefit

    def _get_materiality_threshold(self, context: DecisionContext) -> float:
        """Get the materiality threshold based on risk level."""
        thresholds = {
            RiskLevel.NONE: 100.0,
            RiskLevel.LOW: 50.0,
            RiskLevel.MEDIUM: 10.0,
            RiskLevel.HIGH: 1.0,
            RiskLevel.CRITICAL: 0.1,
        }
        return thresholds.get(context.risk_level, self.default_cost_threshold)

    def _update_stats(self, result: DecisionResult) -> None:
        """Update decision statistics."""
        self.stats.total_decisions += 1
        self.stats.last_decision_at = result.decided_at

        if result.decision == Decision.EXECUTE:
            self.stats.executes += 1
            self.stats.total_cost_approved += result.cost_estimate
        elif result.decision == Decision.HOLD:
            self.stats.holds += 1
            self.stats.total_cost_prevented += result.cost_estimate
        elif result.decision == Decision.ESCALATE:
            self.stats.escalates += 1

        # Update running average confidence
        n = self.stats.total_decisions
        self.stats.avg_confidence = (
            (self.stats.avg_confidence * (n - 1) + result.confidence) / n
        )

    def _log_decision(self, result: DecisionResult) -> None:
        """Log the decision for audit trail."""
        level = {
            Decision.EXECUTE: logging.INFO,
            Decision.HOLD: logging.INFO,
            Decision.ESCALATE: logging.WARNING,
        }.get(result.decision, logging.INFO)

        logger.log(
            level,
            f"DECISION [{self.component}] {result.summary()}"
        )

        if self.enable_audit:
            # Also log to audit logger if available
            try:
                from core.audit_logger import audit_log
                audit_log(
                    event="decision",
                    component=self.component,
                    data=result.to_dict(),
                )
            except ImportError:
                pass

    async def _fire_callbacks(self, result: DecisionResult) -> None:
        """Fire registered callbacks."""
        for callback in self._on_decision_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")

        if result.decision == Decision.ESCALATE:
            for callback in self._on_escalate_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(result)
                    else:
                        callback(result)
                except Exception as e:
                    logger.error(f"Escalation callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics."""
        return {
            "component": self.component,
            "total_decisions": self.stats.total_decisions,
            "executes": self.stats.executes,
            "holds": self.stats.holds,
            "escalates": self.stats.escalates,
            "hold_rate": (
                self.stats.holds / self.stats.total_decisions
                if self.stats.total_decisions > 0
                else 0.0
            ),
            "total_cost_approved": self.stats.total_cost_approved,
            "total_cost_prevented": self.stats.total_cost_prevented,
            "avg_confidence": self.stats.avg_confidence,
            "rules_count": len(self.rules),
            "last_decision_at": (
                self.stats.last_decision_at.isoformat()
                if self.stats.last_decision_at
                else None
            ),
        }

    def get_recent_decisions(
        self,
        limit: int = 10,
        decision_type: Optional[Decision] = None,
    ) -> List[DecisionResult]:
        """Get recent decisions, optionally filtered by type."""
        history = self._decision_history
        if decision_type:
            history = [d for d in history if d.decision == decision_type]
        return history[-limit:]


def get_decision_engine(
    component: str,
    create_if_missing: bool = True,
    **kwargs,
) -> Optional[DecisionEngine]:
    """
    Get or create a decision engine for a component.

    This provides a singleton-per-component pattern for easy access.
    """
    if component not in _engines and create_if_missing:
        _engines[component] = DecisionEngine(component=component, **kwargs)
    return _engines.get(component)


def get_all_engines() -> Dict[str, DecisionEngine]:
    """Get all registered decision engines."""
    return _engines.copy()
