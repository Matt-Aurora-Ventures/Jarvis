"""
Built-in decision rules.

These rules cover common scenarios:
- Rate limiting
- Duplicate content detection
- Cost thresholds
- Confidence thresholds
- Materiality checks
- Circuit breakers
"""

import hashlib
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .model import Decision, DecisionContext, DecisionRule


class RateLimitRule(DecisionRule):
    """
    Rate limiting rule - prevents too many actions in a time window.

    Usage:
        rule = RateLimitRule(
            max_per_hour=10,
            max_per_minute=2,
            cooldown_seconds=30,
        )
    """

    name = "rate_limit"
    description = "Prevents excessive action frequency"
    priority = 10  # High priority - check first

    def __init__(
        self,
        max_per_hour: int = 60,
        max_per_minute: int = 5,
        cooldown_seconds: float = 0,
        per_intent: bool = False,
    ):
        self.max_per_hour = max_per_hour
        self.max_per_minute = max_per_minute
        self.cooldown_seconds = cooldown_seconds
        self.per_intent = per_intent

        # Track timestamps of actions
        self._global_history: deque = deque(maxlen=max_per_hour * 2)
        self._intent_history: Dict[str, deque] = {}
        self._last_action_time: float = 0

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        now = time.time()
        what_would_change = []

        # Check cooldown
        if self.cooldown_seconds > 0:
            time_since_last = now - self._last_action_time
            if time_since_last < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_last
                what_would_change.append(f"Wait {remaining:.1f}s for cooldown")
                return (
                    Decision.HOLD,
                    f"Cooldown active ({remaining:.1f}s remaining)",
                    what_would_change,
                )

        # Get history to check
        if self.per_intent:
            if context.intent not in self._intent_history:
                self._intent_history[context.intent] = deque(maxlen=self.max_per_hour * 2)
            history = self._intent_history[context.intent]
        else:
            history = self._global_history

        # Count actions in last minute
        one_minute_ago = now - 60
        actions_in_minute = sum(1 for t in history if t > one_minute_ago)
        if actions_in_minute >= self.max_per_minute:
            what_would_change.append(f"Wait for rate limit ({self.max_per_minute}/min)")
            return (
                Decision.HOLD,
                f"Rate limit: {actions_in_minute}/{self.max_per_minute} per minute",
                what_would_change,
            )

        # Count actions in last hour
        one_hour_ago = now - 3600
        actions_in_hour = sum(1 for t in history if t > one_hour_ago)
        if actions_in_hour >= self.max_per_hour:
            what_would_change.append(f"Wait for hourly limit ({self.max_per_hour}/hr)")
            return (
                Decision.HOLD,
                f"Rate limit: {actions_in_hour}/{self.max_per_hour} per hour",
                what_would_change,
            )

        # Record this action
        history.append(now)
        self._last_action_time = now

        return (Decision.EXECUTE, "Rate limit OK", [])


class DuplicateContentRule(DecisionRule):
    """
    Prevents duplicate or near-duplicate content.

    Usage:
        rule = DuplicateContentRule(
            lookback_hours=24,
            similarity_threshold=0.8,
        )
    """

    name = "duplicate_content"
    description = "Prevents posting duplicate content"
    priority = 20

    def __init__(
        self,
        lookback_hours: int = 24,
        similarity_threshold: float = 0.8,
        content_key: str = "content",
    ):
        self.lookback_hours = lookback_hours
        self.similarity_threshold = similarity_threshold
        self.content_key = content_key

        # Store hashes of recent content with timestamps
        self._content_hashes: Dict[str, float] = {}

    def _get_content_hash(self, content: str) -> str:
        """Generate a hash for content comparison."""
        # Normalize content: lowercase, remove extra whitespace
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two pieces of content."""
        # Simple word-based Jaccard similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        now = time.time()
        what_would_change = []

        # Get content to check
        content = context.data.get(self.content_key, "")
        if not content:
            return (Decision.EXECUTE, "No content to check", [])

        content_hash = self._get_content_hash(content)

        # Clean old entries
        cutoff = now - (self.lookback_hours * 3600)
        self._content_hashes = {
            h: t for h, t in self._content_hashes.items() if t > cutoff
        }

        # Check for exact duplicate
        if content_hash in self._content_hashes:
            hours_ago = (now - self._content_hashes[content_hash]) / 3600
            what_would_change.append(f"Use different content (duplicate from {hours_ago:.1f}h ago)")
            return (
                Decision.HOLD,
                f"Exact duplicate content (posted {hours_ago:.1f}h ago)",
                what_would_change,
            )

        # Record this content
        self._content_hashes[content_hash] = now

        return (Decision.EXECUTE, "Content is unique", [])


class CostThresholdRule(DecisionRule):
    """
    Enforces cost limits per action and cumulative.

    Usage:
        rule = CostThresholdRule(
            max_per_action=1.0,
            max_per_hour=10.0,
            max_per_day=50.0,
        )
    """

    name = "cost_threshold"
    description = "Enforces cost limits"
    priority = 15

    def __init__(
        self,
        max_per_action: float = 1.0,
        max_per_hour: float = 10.0,
        max_per_day: float = 100.0,
    ):
        self.max_per_action = max_per_action
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day

        self._hourly_costs: deque = deque(maxlen=1000)
        self._daily_costs: deque = deque(maxlen=10000)

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        now = time.time()
        what_would_change = []
        cost = context.cost_estimate

        # Check per-action limit
        if cost > self.max_per_action:
            what_would_change.append(f"Reduce cost to ${self.max_per_action:.2f}")
            return (
                Decision.ESCALATE,
                f"Cost ${cost:.2f} exceeds per-action limit ${self.max_per_action:.2f}",
                what_would_change,
            )

        # Calculate hourly total
        one_hour_ago = now - 3600
        hourly_total = sum(c for t, c in self._hourly_costs if t > one_hour_ago)
        if hourly_total + cost > self.max_per_hour:
            what_would_change.append(f"Wait for hourly budget reset (${self.max_per_hour:.2f}/hr)")
            return (
                Decision.HOLD,
                f"Hourly cost limit: ${hourly_total:.2f} + ${cost:.2f} > ${self.max_per_hour:.2f}",
                what_would_change,
            )

        # Calculate daily total
        one_day_ago = now - 86400
        daily_total = sum(c for t, c in self._daily_costs if t > one_day_ago)
        if daily_total + cost > self.max_per_day:
            what_would_change.append(f"Wait for daily budget reset (${self.max_per_day:.2f}/day)")
            return (
                Decision.HOLD,
                f"Daily cost limit: ${daily_total:.2f} + ${cost:.2f} > ${self.max_per_day:.2f}",
                what_would_change,
            )

        # Record cost
        self._hourly_costs.append((now, cost))
        self._daily_costs.append((now, cost))

        return (Decision.EXECUTE, f"Cost ${cost:.2f} within limits", [])


class ConfidenceThresholdRule(DecisionRule):
    """
    Requires minimum confidence for execution.

    Usage:
        rule = ConfidenceThresholdRule(
            min_confidence=0.6,
            escalate_below=0.3,
        )
    """

    name = "confidence_threshold"
    description = "Requires minimum confidence"
    priority = 25

    def __init__(
        self,
        min_confidence: float = 0.5,
        escalate_below: float = 0.2,
        confidence_key: str = "confidence",
    ):
        self.min_confidence = min_confidence
        self.escalate_below = escalate_below
        self.confidence_key = confidence_key

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        what_would_change = []

        confidence = context.data.get(self.confidence_key, 1.0)
        if isinstance(confidence, str):
            try:
                confidence = float(confidence)
            except ValueError:
                confidence = 0.5

        # Normalize to 0-1 range if needed
        if confidence > 1.0:
            confidence = confidence / 100.0 if confidence <= 100 else confidence / 10.0

        if confidence < self.escalate_below:
            what_would_change.append(f"Increase confidence above {self.escalate_below:.0%}")
            return (
                Decision.ESCALATE,
                f"Confidence {confidence:.0%} requires human review (below {self.escalate_below:.0%})",
                what_would_change,
            )

        if confidence < self.min_confidence:
            what_would_change.append(f"Increase confidence above {self.min_confidence:.0%}")
            return (
                Decision.HOLD,
                f"Confidence {confidence:.0%} below threshold {self.min_confidence:.0%}",
                what_would_change,
            )

        return (Decision.EXECUTE, f"Confidence {confidence:.0%} OK", [])


class MaterialityRule(DecisionRule):
    """
    Checks if action meets materiality threshold (is it worth doing?).

    Usage:
        rule = MaterialityRule(
            min_benefit=0.1,
            benefit_key="expected_value",
        )
    """

    name = "materiality"
    description = "Checks if action is worth doing"
    priority = 30

    def __init__(
        self,
        min_benefit: float = 0.1,
        benefit_cost_ratio: float = 1.5,
        benefit_key: str = "expected_value",
    ):
        self.min_benefit = min_benefit
        self.benefit_cost_ratio = benefit_cost_ratio
        self.benefit_key = benefit_key

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        what_would_change = []

        benefit = context.data.get(self.benefit_key, 1.0)
        cost = context.cost_estimate or 0.01  # Avoid division by zero

        # Check minimum benefit
        if benefit < self.min_benefit:
            what_would_change.append(f"Action with benefit > {self.min_benefit}")
            return (
                Decision.HOLD,
                f"Benefit {benefit:.2f} below materiality threshold {self.min_benefit:.2f}",
                what_would_change,
            )

        # Check benefit/cost ratio
        ratio = benefit / cost
        if ratio < self.benefit_cost_ratio:
            what_would_change.append(f"Improve benefit/cost ratio to {self.benefit_cost_ratio}:1")
            return (
                Decision.HOLD,
                f"Benefit/cost ratio {ratio:.1f}:1 below threshold {self.benefit_cost_ratio}:1",
                what_would_change,
            )

        return (Decision.EXECUTE, f"Materiality check passed (ratio {ratio:.1f}:1)", [])


class CircuitBreakerRule(DecisionRule):
    """
    Circuit breaker that opens after repeated failures.

    Usage:
        rule = CircuitBreakerRule(
            failure_threshold=5,
            recovery_timeout=300,
        )
    """

    name = "circuit_breaker"
    description = "Prevents cascading failures"
    priority = 5  # Very high priority

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
        half_open_max: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half-open
        self._half_open_attempts = 0

    def record_failure(self) -> None:
        """Record a failure (call after action fails)."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    def record_success(self) -> None:
        """Record a success (call after action succeeds)."""
        if self._state == "half-open":
            self._state = "closed"
            self._failure_count = 0
            self._half_open_attempts = 0

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        now = time.time()
        what_would_change = []

        if self._state == "closed":
            return (Decision.EXECUTE, "Circuit breaker closed", [])

        if self._state == "open":
            # Check if recovery timeout has passed
            if self._last_failure_time:
                time_since_failure = now - self._last_failure_time
                if time_since_failure >= self.recovery_timeout:
                    self._state = "half-open"
                    self._half_open_attempts = 0
                else:
                    remaining = self.recovery_timeout - time_since_failure
                    what_would_change.append(f"Wait {remaining:.0f}s for circuit recovery")
                    return (
                        Decision.HOLD,
                        f"Circuit breaker OPEN ({remaining:.0f}s until recovery)",
                        what_would_change,
                    )

        if self._state == "half-open":
            if self._half_open_attempts >= self.half_open_max:
                what_would_change.append("Wait for half-open test to complete")
                return (
                    Decision.HOLD,
                    "Circuit breaker half-open (max test attempts reached)",
                    what_would_change,
                )
            self._half_open_attempts += 1
            return (Decision.EXECUTE, "Circuit breaker half-open (testing)", [])

        return (Decision.EXECUTE, "Circuit breaker OK", [])


class TimeWindowRule(DecisionRule):
    """
    Only allow actions during specific time windows.

    Usage:
        rule = TimeWindowRule(
            allowed_hours=(9, 17),  # 9am to 5pm
            allowed_days=(0, 4),    # Monday to Friday
        )
    """

    name = "time_window"
    description = "Restricts actions to specific times"
    priority = 35

    def __init__(
        self,
        allowed_hours: Optional[Tuple[int, int]] = None,
        allowed_days: Optional[Tuple[int, int]] = None,
        timezone_offset: int = 0,
    ):
        self.allowed_hours = allowed_hours  # (start_hour, end_hour)
        self.allowed_days = allowed_days    # (start_day, end_day) 0=Monday
        self.timezone_offset = timezone_offset

    async def evaluate(
        self,
        context: DecisionContext,
        current_decision: Decision = Decision.EXECUTE,
    ) -> Tuple[Decision, str, List[str]]:
        now = datetime.utcnow() + timedelta(hours=self.timezone_offset)
        what_would_change = []

        # Check day of week
        if self.allowed_days:
            start_day, end_day = self.allowed_days
            if not (start_day <= now.weekday() <= end_day):
                what_would_change.append(f"Wait for allowed day (weekday {start_day}-{end_day})")
                return (
                    Decision.HOLD,
                    f"Outside allowed days (current: {now.strftime('%A')})",
                    what_would_change,
                )

        # Check hour
        if self.allowed_hours:
            start_hour, end_hour = self.allowed_hours
            if not (start_hour <= now.hour < end_hour):
                what_would_change.append(f"Wait for allowed hours ({start_hour}:00-{end_hour}:00)")
                return (
                    Decision.HOLD,
                    f"Outside allowed hours (current: {now.hour}:00)",
                    what_would_change,
                )

        return (Decision.EXECUTE, "Within allowed time window", [])
