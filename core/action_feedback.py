"""
Action Feedback System.

Post-action learning loop that:
1. Records every action with explicit "why" and expected outcome
2. Compares expected vs actual results
3. Extracts patterns from successes and failures
4. Updates knowledge for future decisions

This closes the feedback loop that makes Jarvis learn from experience.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import config, memory, safety


ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_DIR = ROOT / "data" / "action_feedback"
FEEDBACK_LOG = FEEDBACK_DIR / "feedback.jsonl"
PATTERNS_FILE = FEEDBACK_DIR / "patterns.json"
METRICS_FILE = FEEDBACK_DIR / "metrics.json"


def _ensure_dir() -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ActionIntent:
    """Records the intent before an action is executed."""
    action_name: str
    why: str  # Explicit reasoning for taking this action
    expected_outcome: str
    success_criteria: List[str]
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    objective_id: Optional[str] = None


@dataclass
class ActionOutcome:
    """Records what actually happened after an action."""
    success: bool
    actual_outcome: str
    error: str = ""
    duration_ms: int = 0
    side_effects: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActionFeedback:
    """Complete feedback record for an action."""
    id: str
    intent: ActionIntent
    outcome: ActionOutcome
    criteria_met: Dict[str, bool] = field(default_factory=dict)
    gap_analysis: str = ""
    lesson_learned: str = ""
    should_remember: bool = False


@dataclass
class ActionPattern:
    """A learned pattern from action feedback."""
    pattern_type: str  # "success", "failure", "slow", "side_effect"
    action_name: str
    description: str
    frequency: int = 1
    last_seen: float = field(default_factory=time.time)
    context_keys: List[str] = field(default_factory=list)


@dataclass
class ActionMetrics:
    """Aggregate metrics for action performance."""
    action_name: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0
    success_rate: float = 0
    common_errors: List[str] = field(default_factory=list)
    last_success: Optional[float] = None
    last_failure: Optional[float] = None


class ActionFeedbackLoop:
    """
    Manages the action feedback loop.

    Usage:
        loop = ActionFeedbackLoop()

        # Before action
        intent = loop.record_intent(
            action_name="open_browser",
            why="User wants to check email",
            expected_outcome="Browser opens to Gmail",
            success_criteria=["browser_launched", "url_loaded"]
        )

        # Execute action...

        # After action
        feedback = loop.record_outcome(
            intent_id=intent.id,
            success=True,
            actual_outcome="Browser opened to Gmail",
        )

        # Learn from feedback
        loop.analyze_feedback(feedback)
    """

    def __init__(self):
        _ensure_dir()
        self._pending_intents: Dict[str, ActionIntent] = {}
        self._metrics_cache: Dict[str, ActionMetrics] = {}
        self._patterns: List[ActionPattern] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load learned patterns from disk."""
        if PATTERNS_FILE.exists():
            try:
                with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._patterns = [
                        ActionPattern(**p) for p in data.get("patterns", [])
                    ]
            except Exception:
                self._patterns = []

    def _save_patterns(self) -> None:
        """Persist learned patterns."""
        _ensure_dir()
        with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "patterns": [asdict(p) for p in self._patterns],
                "updated_at": time.time(),
            }, f, indent=2)

    def record_intent(
        self,
        action_name: str,
        why: str,
        expected_outcome: str,
        success_criteria: List[str],
        objective_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record intent before executing an action.

        Returns an intent_id to correlate with outcome.
        """
        intent_id = f"{action_name}_{int(time.time() * 1000)}"

        intent = ActionIntent(
            action_name=action_name,
            why=why,
            expected_outcome=expected_outcome,
            success_criteria=success_criteria,
            objective_id=objective_id,
            context=context or {},
        )

        self._pending_intents[intent_id] = intent

        # Log intent
        self._log_feedback_event("intent_recorded", {
            "intent_id": intent_id,
            "action": action_name,
            "why": why,
            "expected": expected_outcome,
        })

        return intent_id

    def record_outcome(
        self,
        intent_id: str,
        success: bool,
        actual_outcome: str,
        error: str = "",
        duration_ms: int = 0,
        side_effects: Optional[List[str]] = None,
        criteria_results: Optional[Dict[str, bool]] = None,
    ) -> Optional[ActionFeedback]:
        """
        Record outcome after executing an action.

        Returns the complete feedback record.
        """
        intent = self._pending_intents.pop(intent_id, None)
        if not intent:
            return None

        outcome = ActionOutcome(
            success=success,
            actual_outcome=actual_outcome,
            error=error,
            duration_ms=duration_ms,
            side_effects=side_effects or [],
        )

        # Evaluate criteria
        criteria_met = criteria_results or {}
        if not criteria_met:
            # Default: all criteria met if success
            criteria_met = {c: success for c in intent.success_criteria}

        # Gap analysis
        gap = ""
        if not success or intent.expected_outcome != actual_outcome:
            gap = f"Expected: '{intent.expected_outcome}' | Got: '{actual_outcome}'"
            if error:
                gap += f" | Error: {error}"

        # Determine lesson
        lesson = self._extract_lesson(intent, outcome, criteria_met)
        should_remember = bool(lesson) or not success

        feedback = ActionFeedback(
            id=intent_id,
            intent=intent,
            outcome=outcome,
            criteria_met=criteria_met,
            gap_analysis=gap,
            lesson_learned=lesson,
            should_remember=should_remember,
        )

        # Persist feedback
        self._persist_feedback(feedback)

        # Update metrics
        self._update_metrics(feedback)

        return feedback

    def _extract_lesson(
        self,
        intent: ActionIntent,
        outcome: ActionOutcome,
        criteria_met: Dict[str, bool],
    ) -> str:
        """Extract a lesson from the feedback."""
        lessons = []

        if not outcome.success:
            lessons.append(
                f"'{intent.action_name}' failed: {outcome.error or outcome.actual_outcome}"
            )

        failed_criteria = [c for c, met in criteria_met.items() if not met]
        if failed_criteria:
            lessons.append(f"Unmet criteria: {', '.join(failed_criteria)}")

        if outcome.duration_ms > 5000:
            lessons.append(f"'{intent.action_name}' was slow ({outcome.duration_ms}ms)")

        if outcome.side_effects:
            lessons.append(f"Side effects: {', '.join(outcome.side_effects)}")

        return " | ".join(lessons) if lessons else ""

    def _persist_feedback(self, feedback: ActionFeedback) -> None:
        """Write feedback to disk."""
        _ensure_dir()
        entry = {
            "id": feedback.id,
            "timestamp": time.time(),
            "action": feedback.intent.action_name,
            "why": feedback.intent.why,
            "expected": feedback.intent.expected_outcome,
            "actual": feedback.outcome.actual_outcome,
            "success": feedback.outcome.success,
            "error": feedback.outcome.error,
            "duration_ms": feedback.outcome.duration_ms,
            "criteria_met": feedback.criteria_met,
            "gap": feedback.gap_analysis,
            "lesson": feedback.lesson_learned,
            "objective_id": feedback.intent.objective_id,
        }
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _update_metrics(self, feedback: ActionFeedback) -> None:
        """Update aggregate metrics for the action."""
        action = feedback.intent.action_name

        if action not in self._metrics_cache:
            self._metrics_cache[action] = ActionMetrics(action_name=action)

        m = self._metrics_cache[action]
        m.total_calls += 1

        if feedback.outcome.success:
            m.success_count += 1
            m.last_success = time.time()
        else:
            m.failure_count += 1
            m.last_failure = time.time()
            if feedback.outcome.error and feedback.outcome.error not in m.common_errors:
                m.common_errors.append(feedback.outcome.error[:100])
                m.common_errors = m.common_errors[-5:]  # Keep last 5

        # Update averages
        m.success_rate = m.success_count / max(1, m.total_calls)
        prev_total = m.total_calls - 1
        if prev_total > 0:
            m.avg_duration_ms = (
                (m.avg_duration_ms * prev_total + feedback.outcome.duration_ms)
                / m.total_calls
            )
        else:
            m.avg_duration_ms = float(feedback.outcome.duration_ms)

        # Persist metrics periodically
        if m.total_calls % 10 == 0:
            self._save_metrics()

    def _save_metrics(self) -> None:
        """Persist metrics to disk."""
        _ensure_dir()
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "metrics": {k: asdict(v) for k, v in self._metrics_cache.items()},
                "updated_at": time.time(),
            }, f, indent=2)

    def analyze_feedback(self, feedback: ActionFeedback) -> Optional[ActionPattern]:
        """
        Analyze feedback to extract patterns.

        Returns a new pattern if one is detected.
        """
        # Look for failure patterns
        if not feedback.outcome.success:
            pattern = self._detect_failure_pattern(feedback)
            if pattern:
                self._add_pattern(pattern)
                return pattern

        # Look for slow action patterns
        if feedback.outcome.duration_ms > 5000:
            pattern = ActionPattern(
                pattern_type="slow",
                action_name=feedback.intent.action_name,
                description=f"Action typically takes {feedback.outcome.duration_ms}ms",
                context_keys=list(feedback.intent.context.keys()),
            )
            self._add_pattern(pattern)
            return pattern

        # Look for side effect patterns
        if feedback.outcome.side_effects:
            pattern = ActionPattern(
                pattern_type="side_effect",
                action_name=feedback.intent.action_name,
                description=f"Causes: {', '.join(feedback.outcome.side_effects)}",
            )
            self._add_pattern(pattern)
            return pattern

        return None

    def _detect_failure_pattern(self, feedback: ActionFeedback) -> Optional[ActionPattern]:
        """Detect if this failure matches an existing pattern."""
        action = feedback.intent.action_name
        error = feedback.outcome.error

        # Check if we've seen this before
        for pattern in self._patterns:
            if (
                pattern.pattern_type == "failure"
                and pattern.action_name == action
                and error in pattern.description
            ):
                pattern.frequency += 1
                pattern.last_seen = time.time()
                self._save_patterns()
                return pattern

        # New failure pattern
        return ActionPattern(
            pattern_type="failure",
            action_name=action,
            description=f"Fails with: {error or feedback.gap_analysis}",
            context_keys=list(feedback.intent.context.keys()),
        )

    def _add_pattern(self, pattern: ActionPattern) -> None:
        """Add or update a pattern."""
        # Check for existing similar pattern
        for i, existing in enumerate(self._patterns):
            if (
                existing.pattern_type == pattern.pattern_type
                and existing.action_name == pattern.action_name
            ):
                existing.frequency += 1
                existing.last_seen = time.time()
                self._save_patterns()
                return

        # Add new pattern
        self._patterns.append(pattern)
        self._save_patterns()

        # Store significant patterns in memory
        if pattern.frequency >= 3 or pattern.pattern_type == "failure":
            ctx = safety.SafetyContext(apply=True, dry_run=False)
            memory.append_entry(
                text=f"[PATTERN] {pattern.action_name}: {pattern.description}",
                source="action_feedback",
                context=ctx,
            )

    def get_metrics(self, action_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for one or all actions."""
        if action_name:
            m = self._metrics_cache.get(action_name)
            return asdict(m) if m else {}

        return {k: asdict(v) for k, v in self._metrics_cache.items()}

    def get_patterns(self, action_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get learned patterns for an action."""
        patterns = self._patterns
        if action_name:
            patterns = [p for p in patterns if p.action_name == action_name]
        return [asdict(p) for p in patterns]

    def get_recommendations(self, action_name: str) -> List[str]:
        """Get recommendations based on learned patterns."""
        recs = []
        metrics = self._metrics_cache.get(action_name)
        patterns = [p for p in self._patterns if p.action_name == action_name]

        if metrics:
            if metrics.success_rate < 0.5:
                recs.append(
                    f"'{action_name}' has low success rate ({metrics.success_rate:.0%}). "
                    f"Common errors: {', '.join(metrics.common_errors[:2])}"
                )
            if metrics.avg_duration_ms > 3000:
                recs.append(
                    f"'{action_name}' is slow (avg {metrics.avg_duration_ms:.0f}ms). "
                    "Consider async execution."
                )

        for p in patterns:
            if p.pattern_type == "failure" and p.frequency >= 3:
                recs.append(f"Known issue: {p.description}")
            elif p.pattern_type == "side_effect":
                recs.append(f"Watch for: {p.description}")

        return recs

    def _log_feedback_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log a feedback event."""
        # Could be extended to use a separate event log
        pass


# Global instance
_feedback_loop: Optional[ActionFeedbackLoop] = None


def get_feedback_loop() -> ActionFeedbackLoop:
    """Get the global ActionFeedbackLoop instance."""
    global _feedback_loop
    if _feedback_loop is None:
        _feedback_loop = ActionFeedbackLoop()
    return _feedback_loop


# Convenience decorator for action functions
def tracked_action(
    why: str,
    expected: str,
    criteria: Optional[List[str]] = None,
):
    """
    Decorator to automatically track actions.

    Usage:
        @tracked_action(
            why="Open browser for user",
            expected="Browser window opens",
            criteria=["browser_launched"]
        )
        def open_browser(url: str) -> Tuple[bool, str]:
            ...
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs) -> Tuple[bool, str]:
            loop = get_feedback_loop()

            # Record intent
            intent_id = loop.record_intent(
                action_name=func.__name__,
                why=why,
                expected_outcome=expected,
                success_criteria=criteria or ["action_completed"],
                context={"args": str(args)[:100], "kwargs": str(kwargs)[:100]},
            )

            # Execute
            start = time.time()
            try:
                success, output = func(*args, **kwargs)
                duration = int((time.time() - start) * 1000)

                # Record outcome
                loop.record_outcome(
                    intent_id=intent_id,
                    success=success,
                    actual_outcome=output,
                    duration_ms=duration,
                )

                return success, output

            except Exception as e:
                duration = int((time.time() - start) * 1000)
                loop.record_outcome(
                    intent_id=intent_id,
                    success=False,
                    actual_outcome="",
                    error=str(e)[:200],
                    duration_ms=duration,
                )
                raise

        return wrapper
    return decorator


# Convenience functions
def record_action_intent(
    action_name: str,
    why: str,
    expected_outcome: str,
    success_criteria: Optional[List[str]] = None,
    **kwargs,
) -> str:
    """Record intent before an action."""
    return get_feedback_loop().record_intent(
        action_name=action_name,
        why=why,
        expected_outcome=expected_outcome,
        success_criteria=success_criteria or ["action_completed"],
        **kwargs,
    )


def record_action_outcome(
    intent_id: str,
    success: bool,
    actual_outcome: str,
    **kwargs,
) -> Optional[ActionFeedback]:
    """Record outcome after an action."""
    return get_feedback_loop().record_outcome(
        intent_id=intent_id,
        success=success,
        actual_outcome=actual_outcome,
        **kwargs,
    )


def get_action_recommendations(action_name: str) -> List[str]:
    """Get recommendations for an action."""
    return get_feedback_loop().get_recommendations(action_name)
