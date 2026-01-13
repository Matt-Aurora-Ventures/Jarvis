"""
Automation Suggestion Engine

Observes user patterns and proactively suggests automations.
Uses lightweight ML (rule-based + frequency analysis) to detect opportunities.

Features:
- Pattern detection from user behavior
- Automation opportunity scoring
- Template-based automation generation
- Learning from accepted/rejected suggestions
"""

import json
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
PATTERNS_FILE = ROOT / "data" / "automation" / "patterns.json"
SUGGESTIONS_FILE = ROOT / "data" / "automation" / "suggestions.json"
HISTORY_FILE = ROOT / "data" / "automation" / "history.jsonl"


@dataclass
class UserAction:
    """A recorded user action."""
    action_type: str  # command, query, click, voice
    content: str
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass
class DetectedPattern:
    """A detected behavioral pattern."""
    pattern_id: str
    pattern_type: str  # repetitive, sequence, time_based, conditional
    description: str
    occurrences: int
    first_seen: float
    last_seen: float
    confidence: float
    actions: List[str] = field(default_factory=list)
    trigger: str = ""  # What triggers this pattern
    frequency_per_day: float = 0.0


@dataclass
class AutomationSuggestion:
    """A suggested automation."""
    suggestion_id: str
    pattern_id: str
    title: str
    description: str
    automation_type: str  # scheduled, triggered, chained
    trigger: str
    actions: List[Dict[str, Any]]
    estimated_time_saved: str
    confidence: float
    status: str = "pending"  # pending, accepted, rejected, implemented
    created_at: str = ""
    user_feedback: str = ""


class PatternDetector:
    """Detects patterns in user behavior."""

    # Minimum occurrences to consider a pattern
    MIN_OCCURRENCES = 3

    # Time patterns (hours)
    MORNING = (6, 12)
    AFTERNOON = (12, 18)
    EVENING = (18, 24)

    def __init__(self):
        self.action_history: List[UserAction] = []
        self.patterns: Dict[str, DetectedPattern] = {}
        self._load_history()

    def _load_history(self):
        """Load action history from disk."""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    for line in f:
                        data = json.loads(line.strip())
                        self.action_history.append(UserAction(**data))
            except Exception:
                pass

    def record_action(self, action: UserAction):
        """Record a user action."""
        self.action_history.append(action)

        # Persist to disk
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'a') as f:
            f.write(json.dumps(asdict(action)) + "\n")

        # Trigger pattern detection
        self._detect_patterns()

    def _detect_patterns(self):
        """Analyze history and detect patterns."""
        if len(self.action_history) < self.MIN_OCCURRENCES:
            return

        # 1. Repetitive command patterns
        self._detect_repetitive_patterns()

        # 2. Sequential patterns (A then B then C)
        self._detect_sequence_patterns()

        # 3. Time-based patterns
        self._detect_time_patterns()

        # 4. Context-triggered patterns
        self._detect_context_patterns()

    def _detect_repetitive_patterns(self):
        """Detect frequently repeated actions."""
        recent = self.action_history[-100:]  # Last 100 actions
        content_counts = Counter(a.content for a in recent)

        for content, count in content_counts.items():
            if count >= self.MIN_OCCURRENCES:
                pattern_id = f"rep_{hash(content) % 10000:04d}"

                if pattern_id not in self.patterns:
                    self.patterns[pattern_id] = DetectedPattern(
                        pattern_id=pattern_id,
                        pattern_type="repetitive",
                        description=f"Frequently runs: {content[:50]}",
                        occurrences=count,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        confidence=min(count / 10, 0.95),
                        actions=[content],
                        trigger="manual",
                    )
                else:
                    self.patterns[pattern_id].occurrences = count
                    self.patterns[pattern_id].last_seen = time.time()
                    self.patterns[pattern_id].confidence = min(count / 10, 0.95)

    def _detect_sequence_patterns(self):
        """Detect common action sequences."""
        recent = self.action_history[-100:]
        sequences = defaultdict(int)

        # Look for 2-3 action sequences
        for i in range(len(recent) - 2):
            seq2 = (recent[i].content, recent[i+1].content)
            seq3 = (recent[i].content, recent[i+1].content, recent[i+2].content)

            # Only count if within 5 minutes
            if recent[i+1].timestamp - recent[i].timestamp < 300:
                sequences[seq2] += 1

            if (recent[i+2].timestamp - recent[i].timestamp < 600):
                sequences[seq3] += 1

        for seq, count in sequences.items():
            if count >= self.MIN_OCCURRENCES:
                pattern_id = f"seq_{hash(seq) % 10000:04d}"
                if pattern_id not in self.patterns:
                    self.patterns[pattern_id] = DetectedPattern(
                        pattern_id=pattern_id,
                        pattern_type="sequence",
                        description=f"Sequence: {' -> '.join(s[:20] for s in seq)}",
                        occurrences=count,
                        first_seen=time.time(),
                        last_seen=time.time(),
                        confidence=min(count / 5, 0.9),
                        actions=list(seq),
                        trigger="first_action",
                    )

    def _detect_time_patterns(self):
        """Detect time-based patterns."""
        recent = self.action_history[-500:]

        # Group by hour and content
        time_actions = defaultdict(lambda: defaultdict(int))
        for action in recent:
            hour = datetime.fromtimestamp(action.timestamp).hour
            time_actions[hour][action.content] += 1

        # Find consistent morning/evening routines
        for hour, actions in time_actions.items():
            for content, count in actions.items():
                if count >= self.MIN_OCCURRENCES:
                    period = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
                    pattern_id = f"time_{hour}_{hash(content) % 1000:03d}"

                    if pattern_id not in self.patterns:
                        self.patterns[pattern_id] = DetectedPattern(
                            pattern_id=pattern_id,
                            pattern_type="time_based",
                            description=f"{period.capitalize()} routine: {content[:30]}",
                            occurrences=count,
                            first_seen=time.time(),
                            last_seen=time.time(),
                            confidence=min(count / 7, 0.85),
                            actions=[content],
                            trigger=f"time:{hour:02d}:00",
                        )

    def _detect_context_patterns(self):
        """Detect context-triggered patterns."""
        # Look for actions that follow specific contexts
        recent = self.action_history[-200:]

        context_actions = defaultdict(lambda: defaultdict(int))
        for i, action in enumerate(recent):
            if action.context:
                for key, value in action.context.items():
                    context_key = f"{key}:{value}"
                    context_actions[context_key][action.content] += 1

        for context, actions in context_actions.items():
            for content, count in actions.items():
                if count >= self.MIN_OCCURRENCES:
                    pattern_id = f"ctx_{hash(context + content) % 10000:04d}"
                    if pattern_id not in self.patterns:
                        self.patterns[pattern_id] = DetectedPattern(
                            pattern_id=pattern_id,
                            pattern_type="conditional",
                            description=f"When {context}: {content[:30]}",
                            occurrences=count,
                            first_seen=time.time(),
                            last_seen=time.time(),
                            confidence=min(count / 5, 0.8),
                            actions=[content],
                            trigger=f"context:{context}",
                        )

    def get_patterns(self, min_confidence: float = 0.5) -> List[DetectedPattern]:
        """Get all patterns above confidence threshold."""
        return [
            p for p in self.patterns.values()
            if p.confidence >= min_confidence
        ]

    def save_patterns(self):
        """Persist patterns to disk."""
        PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PATTERNS_FILE, 'w') as f:
            patterns = [asdict(p) for p in self.patterns.values()]
            json.dump({'patterns': patterns, 'updated': datetime.now().isoformat()}, f, indent=2)


class AutomationSuggester:
    """
    Generates automation suggestions from detected patterns.

    Takes patterns and creates actionable automation proposals.
    """

    # Automation templates
    TEMPLATES = {
        'repetitive': {
            'scheduled': "Schedule '{action}' to run automatically",
            'hotkey': "Bind '{action}' to a keyboard shortcut",
            'alias': "Create alias/shortcut for '{action}'",
        },
        'sequence': {
            'chain': "Chain these actions: {actions}",
            'macro': "Create macro for: {actions}",
        },
        'time_based': {
            'scheduled': "Run '{action}' daily at {time}",
            'reminder': "Add reminder for '{action}' at {time}",
        },
        'conditional': {
            'trigger': "Auto-run '{action}' when {condition}",
            'workflow': "Create workflow: IF {condition} THEN {action}",
        },
    }

    def __init__(self):
        self.detector = PatternDetector()
        self.suggestions: Dict[str, AutomationSuggestion] = {}
        self.feedback_history: List[Dict] = []
        self._load_suggestions()

    def _load_suggestions(self):
        """Load existing suggestions."""
        if SUGGESTIONS_FILE.exists():
            try:
                with open(SUGGESTIONS_FILE) as f:
                    data = json.load(f)
                    for sugg_data in data.get('suggestions', []):
                        sugg = AutomationSuggestion(**sugg_data)
                        self.suggestions[sugg.suggestion_id] = sugg
            except Exception:
                pass

    def _save_suggestions(self):
        """Persist suggestions."""
        SUGGESTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SUGGESTIONS_FILE, 'w') as f:
            suggestions = [asdict(s) for s in self.suggestions.values()]
            json.dump({'suggestions': suggestions, 'updated': datetime.now().isoformat()}, f, indent=2)

    def record_action(self, action_type: str, content: str, context: Dict = None):
        """Record user action for pattern detection."""
        action = UserAction(
            action_type=action_type,
            content=content,
            timestamp=time.time(),
            context=context or {},
        )
        self.detector.record_action(action)

    def generate_suggestions(self) -> List[AutomationSuggestion]:
        """Generate suggestions from detected patterns."""
        patterns = self.detector.get_patterns(min_confidence=0.6)
        new_suggestions = []

        for pattern in patterns:
            # Skip if we already have a suggestion for this pattern
            existing = [s for s in self.suggestions.values() if s.pattern_id == pattern.pattern_id]
            if existing and existing[0].status not in ['rejected']:
                continue

            suggestion = self._create_suggestion(pattern)
            if suggestion:
                self.suggestions[suggestion.suggestion_id] = suggestion
                new_suggestions.append(suggestion)

        self._save_suggestions()
        self.detector.save_patterns()

        return new_suggestions

    def _create_suggestion(self, pattern: DetectedPattern) -> Optional[AutomationSuggestion]:
        """Create a suggestion from a pattern."""
        templates = self.TEMPLATES.get(pattern.pattern_type, {})
        if not templates:
            return None

        # Choose best automation type based on pattern
        if pattern.pattern_type == 'repetitive':
            if pattern.occurrences > 10:
                auto_type = 'scheduled'
            else:
                auto_type = 'hotkey'
        elif pattern.pattern_type == 'sequence':
            auto_type = 'chain'
        elif pattern.pattern_type == 'time_based':
            auto_type = 'scheduled'
        else:
            auto_type = 'trigger'

        template = templates.get(auto_type, list(templates.values())[0])

        # Fill template
        title = template.format(
            action=pattern.actions[0][:30] if pattern.actions else "action",
            actions=" -> ".join(a[:20] for a in pattern.actions[:3]),
            time=pattern.trigger.replace("time:", "") if "time:" in pattern.trigger else "scheduled time",
            condition=pattern.trigger.replace("context:", "") if "context:" in pattern.trigger else "condition",
        )

        # Estimate time saved
        time_per_action = 5  # seconds
        daily_occurrences = pattern.frequency_per_day or pattern.occurrences / 7
        time_saved = daily_occurrences * time_per_action * len(pattern.actions)

        if time_saved > 60:
            time_str = f"~{time_saved/60:.0f} min/day"
        else:
            time_str = f"~{time_saved:.0f} sec/day"

        suggestion = AutomationSuggestion(
            suggestion_id=f"sugg_{pattern.pattern_id}_{int(time.time()) % 10000}",
            pattern_id=pattern.pattern_id,
            title=title,
            description=f"Based on {pattern.occurrences} occurrences of this pattern",
            automation_type=auto_type,
            trigger=pattern.trigger,
            actions=[{"type": "run", "content": a} for a in pattern.actions],
            estimated_time_saved=time_str,
            confidence=pattern.confidence,
            created_at=datetime.now().isoformat(),
        )

        return suggestion

    def get_pending_suggestions(self) -> List[AutomationSuggestion]:
        """Get all pending suggestions."""
        return [s for s in self.suggestions.values() if s.status == "pending"]

    def accept_suggestion(self, suggestion_id: str, feedback: str = ""):
        """Accept a suggestion."""
        if suggestion_id in self.suggestions:
            self.suggestions[suggestion_id].status = "accepted"
            self.suggestions[suggestion_id].user_feedback = feedback
            self._save_suggestions()
            self.feedback_history.append({
                'suggestion_id': suggestion_id,
                'action': 'accepted',
                'timestamp': time.time(),
            })
            logger.info(f"Suggestion accepted: {suggestion_id}")

    def reject_suggestion(self, suggestion_id: str, feedback: str = ""):
        """Reject a suggestion."""
        if suggestion_id in self.suggestions:
            self.suggestions[suggestion_id].status = "rejected"
            self.suggestions[suggestion_id].user_feedback = feedback
            self._save_suggestions()
            self.feedback_history.append({
                'suggestion_id': suggestion_id,
                'action': 'rejected',
                'timestamp': time.time(),
            })
            logger.info(f"Suggestion rejected: {suggestion_id}")

    def implement_suggestion(self, suggestion_id: str) -> bool:
        """Actually implement an accepted suggestion."""
        if suggestion_id not in self.suggestions:
            return False

        suggestion = self.suggestions[suggestion_id]
        if suggestion.status != "accepted":
            return False

        # Implementation depends on automation type
        try:
            if suggestion.automation_type == 'scheduled':
                # Add to scheduler
                logger.info(f"Would schedule: {suggestion.actions}")
                # TODO: Integrate with core/scheduler

            elif suggestion.automation_type == 'hotkey':
                # Register hotkey
                logger.info(f"Would bind hotkey for: {suggestion.actions}")
                # TODO: Integrate with core/hotkeys

            elif suggestion.automation_type == 'chain':
                # Create action chain
                logger.info(f"Would create chain: {suggestion.actions}")
                # TODO: Integrate with core/automation/chains

            suggestion.status = "implemented"
            self._save_suggestions()
            return True

        except Exception as e:
            logger.error(f"Failed to implement suggestion: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get suggestion statistics."""
        return {
            'total_patterns': len(self.detector.patterns),
            'total_suggestions': len(self.suggestions),
            'pending': len([s for s in self.suggestions.values() if s.status == "pending"]),
            'accepted': len([s for s in self.suggestions.values() if s.status == "accepted"]),
            'rejected': len([s for s in self.suggestions.values() if s.status == "rejected"]),
            'implemented': len([s for s in self.suggestions.values() if s.status == "implemented"]),
            'actions_recorded': len(self.detector.action_history),
        }


# Singleton instance
_suggester: Optional[AutomationSuggester] = None


def get_suggester() -> AutomationSuggester:
    """Get singleton suggester."""
    global _suggester
    if _suggester is None:
        _suggester = AutomationSuggester()
    return _suggester


def record_user_action(action_type: str, content: str, context: Dict = None):
    """Quick helper to record actions."""
    get_suggester().record_action(action_type, content, context)


def get_suggestions() -> List[AutomationSuggestion]:
    """Get pending automation suggestions."""
    suggester = get_suggester()
    suggester.generate_suggestions()
    return suggester.get_pending_suggestions()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the suggester
    suggester = get_suggester()

    # Simulate some repeated actions
    for _ in range(5):
        suggester.record_action("command", "/sentiment BTC")
        time.sleep(0.1)

    for _ in range(4):
        suggester.record_action("command", "/wallet check")
        time.sleep(0.1)

    # Generate suggestions
    suggestions = suggester.generate_suggestions()
    print(f"\nGenerated {len(suggestions)} suggestions:")
    for s in suggestions:
        print(f"  - {s.title}")
        print(f"    Time saved: {s.estimated_time_saved}")
        print(f"    Confidence: {s.confidence:.0%}")

    print(f"\nStats: {suggester.get_stats()}")
