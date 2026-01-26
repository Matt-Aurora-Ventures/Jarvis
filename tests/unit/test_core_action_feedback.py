"""
Comprehensive Tests for core/action_feedback.py

Tests cover:
1. ActionIntent dataclass creation and defaults
2. ActionOutcome dataclass creation and defaults
3. ActionFeedback dataclass creation and defaults
4. ActionPattern dataclass creation and defaults
5. ActionMetrics dataclass creation and defaults
6. ActionFeedbackLoop - intent recording
7. ActionFeedbackLoop - outcome recording
8. ActionFeedbackLoop - lesson extraction
9. ActionFeedbackLoop - feedback persistence
10. ActionFeedbackLoop - metrics update
11. ActionFeedbackLoop - pattern analysis
12. ActionFeedbackLoop - pattern detection
13. ActionFeedbackLoop - recommendations
14. ActionFeedbackLoop - pattern save/load
15. tracked_action decorator
16. Convenience functions
17. Global instance management

Target: 80%+ coverage for core/action_feedback.py
"""

import json
import time
import pytest
from dataclasses import asdict
from pathlib import Path
from typing import Tuple
from unittest.mock import MagicMock, patch, mock_open, call


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_ensure_dir():
    """Mock the _ensure_dir function to avoid filesystem operations."""
    with patch("core.action_feedback._ensure_dir") as mock:
        yield mock


@pytest.fixture
def mock_patterns_file_not_exists():
    """Mock PATTERNS_FILE to not exist."""
    with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
        mock_file.exists.return_value = False
        yield mock_file


@pytest.fixture
def mock_patterns_file_exists():
    """Mock PATTERNS_FILE to exist with valid data."""
    patterns_data = {
        "patterns": [
            {
                "pattern_type": "failure",
                "action_name": "test_action",
                "description": "Test failure pattern",
                "frequency": 2,
                "last_seen": 1000.0,
                "context_keys": ["key1", "key2"],
            }
        ],
        "updated_at": 1000.0,
    }
    with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
        mock_file.exists.return_value = True
        with patch("builtins.open", mock_open(read_data=json.dumps(patterns_data))):
            yield mock_file


@pytest.fixture
def mock_feedback_log():
    """Mock FEEDBACK_LOG file operations."""
    with patch("core.action_feedback.FEEDBACK_LOG") as mock_file:
        yield mock_file


@pytest.fixture
def mock_metrics_file():
    """Mock METRICS_FILE file operations."""
    with patch("core.action_feedback.METRICS_FILE") as mock_file:
        yield mock_file


@pytest.fixture
def feedback_loop(mock_ensure_dir, mock_patterns_file_not_exists):
    """Create an ActionFeedbackLoop instance with mocked dependencies."""
    from core.action_feedback import ActionFeedbackLoop
    return ActionFeedbackLoop()


@pytest.fixture
def feedback_loop_with_patterns(mock_ensure_dir):
    """Create an ActionFeedbackLoop instance with preloaded patterns."""
    patterns_data = {
        "patterns": [
            {
                "pattern_type": "failure",
                "action_name": "known_action",
                "description": "Known failure: timeout error",
                "frequency": 5,
                "last_seen": 1000.0,
                "context_keys": [],
            }
        ],
        "updated_at": 1000.0,
    }
    with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
        mock_file.exists.return_value = True
        with patch("builtins.open", mock_open(read_data=json.dumps(patterns_data))):
            from core.action_feedback import ActionFeedbackLoop
            return ActionFeedbackLoop()


@pytest.fixture
def sample_intent():
    """Create a sample ActionIntent."""
    from core.action_feedback import ActionIntent
    return ActionIntent(
        action_name="test_action",
        why="Test reasoning",
        expected_outcome="Test succeeds",
        success_criteria=["criterion_1", "criterion_2"],
        context={"key": "value"},
        timestamp=1000.0,
        objective_id="obj_001",
    )


@pytest.fixture
def sample_outcome_success():
    """Create a sample successful ActionOutcome."""
    from core.action_feedback import ActionOutcome
    return ActionOutcome(
        success=True,
        actual_outcome="Test succeeded as expected",
        error="",
        duration_ms=150,
        side_effects=[],
        timestamp=1001.0,
    )


@pytest.fixture
def sample_outcome_failure():
    """Create a sample failed ActionOutcome."""
    from core.action_feedback import ActionOutcome
    return ActionOutcome(
        success=False,
        actual_outcome="Test failed",
        error="Connection timeout",
        duration_ms=5500,
        side_effects=["cache_invalidated"],
        timestamp=1001.0,
    )


# =============================================================================
# 1. ActionIntent Dataclass Tests
# =============================================================================


class TestActionIntent:
    """Test ActionIntent dataclass."""

    def test_action_intent_creation_with_required_fields(self):
        """ActionIntent should be creatable with required fields."""
        from core.action_feedback import ActionIntent

        intent = ActionIntent(
            action_name="open_browser",
            why="User wants to check email",
            expected_outcome="Browser opens to Gmail",
            success_criteria=["browser_launched", "url_loaded"],
        )

        assert intent.action_name == "open_browser"
        assert intent.why == "User wants to check email"
        assert intent.expected_outcome == "Browser opens to Gmail"
        assert intent.success_criteria == ["browser_launched", "url_loaded"]

    def test_action_intent_default_context_is_empty_dict(self):
        """ActionIntent should have empty dict as default context."""
        from core.action_feedback import ActionIntent

        intent = ActionIntent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
        )

        assert intent.context == {}
        assert isinstance(intent.context, dict)

    def test_action_intent_default_timestamp_is_current_time(self):
        """ActionIntent should have current time as default timestamp."""
        from core.action_feedback import ActionIntent

        before = time.time()
        intent = ActionIntent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
        )
        after = time.time()

        assert before <= intent.timestamp <= after

    def test_action_intent_default_objective_id_is_none(self):
        """ActionIntent should have None as default objective_id."""
        from core.action_feedback import ActionIntent

        intent = ActionIntent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
        )

        assert intent.objective_id is None

    def test_action_intent_with_all_fields(self):
        """ActionIntent should support all fields."""
        from core.action_feedback import ActionIntent

        intent = ActionIntent(
            action_name="complex_action",
            why="Complex reasoning",
            expected_outcome="Complex outcome",
            success_criteria=["crit1", "crit2", "crit3"],
            context={"arg1": "val1", "arg2": 42},
            timestamp=1234567890.0,
            objective_id="obj_123",
        )

        assert intent.action_name == "complex_action"
        assert intent.context == {"arg1": "val1", "arg2": 42}
        assert intent.timestamp == 1234567890.0
        assert intent.objective_id == "obj_123"

    def test_action_intent_can_be_converted_to_dict(self):
        """ActionIntent should be convertible to dict via asdict."""
        from core.action_feedback import ActionIntent

        intent = ActionIntent(
            action_name="test",
            why="test reason",
            expected_outcome="expected",
            success_criteria=["c1"],
        )

        d = asdict(intent)
        assert d["action_name"] == "test"
        assert d["why"] == "test reason"
        assert "timestamp" in d


# =============================================================================
# 2. ActionOutcome Dataclass Tests
# =============================================================================


class TestActionOutcome:
    """Test ActionOutcome dataclass."""

    def test_action_outcome_creation_with_required_fields(self):
        """ActionOutcome should be creatable with required fields."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Operation completed successfully",
        )

        assert outcome.success is True
        assert outcome.actual_outcome == "Operation completed successfully"

    def test_action_outcome_default_error_is_empty_string(self):
        """ActionOutcome should have empty string as default error."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(success=True, actual_outcome="ok")
        assert outcome.error == ""

    def test_action_outcome_default_duration_ms_is_zero(self):
        """ActionOutcome should have 0 as default duration_ms."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(success=True, actual_outcome="ok")
        assert outcome.duration_ms == 0

    def test_action_outcome_default_side_effects_is_empty_list(self):
        """ActionOutcome should have empty list as default side_effects."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(success=True, actual_outcome="ok")
        assert outcome.side_effects == []
        assert isinstance(outcome.side_effects, list)

    def test_action_outcome_default_timestamp_is_current_time(self):
        """ActionOutcome should have current time as default timestamp."""
        from core.action_feedback import ActionOutcome

        before = time.time()
        outcome = ActionOutcome(success=True, actual_outcome="ok")
        after = time.time()

        assert before <= outcome.timestamp <= after

    def test_action_outcome_failure_with_error(self):
        """ActionOutcome should capture failure with error details."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=False,
            actual_outcome="Connection failed",
            error="TimeoutError: Server did not respond",
            duration_ms=30000,
            side_effects=["partial_data_received", "retry_queued"],
        )

        assert outcome.success is False
        assert "TimeoutError" in outcome.error
        assert outcome.duration_ms == 30000
        assert len(outcome.side_effects) == 2


# =============================================================================
# 3. ActionFeedback Dataclass Tests
# =============================================================================


class TestActionFeedback:
    """Test ActionFeedback dataclass."""

    def test_action_feedback_creation(self, sample_intent, sample_outcome_success):
        """ActionFeedback should be creatable with intent and outcome."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_action_1234567890",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        assert feedback.id == "test_action_1234567890"
        assert feedback.intent == sample_intent
        assert feedback.outcome == sample_outcome_success

    def test_action_feedback_default_criteria_met_is_empty_dict(
        self, sample_intent, sample_outcome_success
    ):
        """ActionFeedback should have empty dict as default criteria_met."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        assert feedback.criteria_met == {}

    def test_action_feedback_default_gap_analysis_is_empty_string(
        self, sample_intent, sample_outcome_success
    ):
        """ActionFeedback should have empty string as default gap_analysis."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        assert feedback.gap_analysis == ""

    def test_action_feedback_default_lesson_learned_is_empty_string(
        self, sample_intent, sample_outcome_success
    ):
        """ActionFeedback should have empty string as default lesson_learned."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        assert feedback.lesson_learned == ""

    def test_action_feedback_default_should_remember_is_false(
        self, sample_intent, sample_outcome_success
    ):
        """ActionFeedback should have False as default should_remember."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        assert feedback.should_remember is False

    def test_action_feedback_with_all_fields(
        self, sample_intent, sample_outcome_failure
    ):
        """ActionFeedback should support all fields."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="action_failure_123",
            intent=sample_intent,
            outcome=sample_outcome_failure,
            criteria_met={"criterion_1": False, "criterion_2": False},
            gap_analysis="Expected success but got failure",
            lesson_learned="Need to handle timeouts",
            should_remember=True,
        )

        assert feedback.criteria_met == {"criterion_1": False, "criterion_2": False}
        assert feedback.gap_analysis == "Expected success but got failure"
        assert feedback.lesson_learned == "Need to handle timeouts"
        assert feedback.should_remember is True


# =============================================================================
# 4. ActionPattern Dataclass Tests
# =============================================================================


class TestActionPattern:
    """Test ActionPattern dataclass."""

    def test_action_pattern_creation_with_required_fields(self):
        """ActionPattern should be creatable with required fields."""
        from core.action_feedback import ActionPattern

        pattern = ActionPattern(
            pattern_type="failure",
            action_name="api_call",
            description="API fails with rate limit error",
        )

        assert pattern.pattern_type == "failure"
        assert pattern.action_name == "api_call"
        assert pattern.description == "API fails with rate limit error"

    def test_action_pattern_default_frequency_is_one(self):
        """ActionPattern should have 1 as default frequency."""
        from core.action_feedback import ActionPattern

        pattern = ActionPattern(
            pattern_type="success",
            action_name="test",
            description="test",
        )

        assert pattern.frequency == 1

    def test_action_pattern_default_last_seen_is_current_time(self):
        """ActionPattern should have current time as default last_seen."""
        from core.action_feedback import ActionPattern

        before = time.time()
        pattern = ActionPattern(
            pattern_type="success",
            action_name="test",
            description="test",
        )
        after = time.time()

        assert before <= pattern.last_seen <= after

    def test_action_pattern_default_context_keys_is_empty_list(self):
        """ActionPattern should have empty list as default context_keys."""
        from core.action_feedback import ActionPattern

        pattern = ActionPattern(
            pattern_type="success",
            action_name="test",
            description="test",
        )

        assert pattern.context_keys == []

    def test_action_pattern_types(self):
        """ActionPattern should support various pattern types."""
        from core.action_feedback import ActionPattern

        for pattern_type in ["success", "failure", "slow", "side_effect"]:
            pattern = ActionPattern(
                pattern_type=pattern_type,
                action_name="test",
                description="test",
            )
            assert pattern.pattern_type == pattern_type


# =============================================================================
# 5. ActionMetrics Dataclass Tests
# =============================================================================


class TestActionMetrics:
    """Test ActionMetrics dataclass."""

    def test_action_metrics_creation_with_action_name(self):
        """ActionMetrics should be creatable with action_name."""
        from core.action_feedback import ActionMetrics

        metrics = ActionMetrics(action_name="test_action")

        assert metrics.action_name == "test_action"

    def test_action_metrics_default_values(self):
        """ActionMetrics should have correct default values."""
        from core.action_feedback import ActionMetrics

        metrics = ActionMetrics(action_name="test")

        assert metrics.total_calls == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.avg_duration_ms == 0
        assert metrics.success_rate == 0
        assert metrics.common_errors == []
        assert metrics.last_success is None
        assert metrics.last_failure is None

    def test_action_metrics_with_all_fields(self):
        """ActionMetrics should support all fields."""
        from core.action_feedback import ActionMetrics

        metrics = ActionMetrics(
            action_name="api_call",
            total_calls=100,
            success_count=95,
            failure_count=5,
            avg_duration_ms=250.5,
            success_rate=0.95,
            common_errors=["timeout", "rate_limit"],
            last_success=1000.0,
            last_failure=999.0,
        )

        assert metrics.total_calls == 100
        assert metrics.success_count == 95
        assert metrics.failure_count == 5
        assert metrics.avg_duration_ms == 250.5
        assert metrics.success_rate == 0.95
        assert len(metrics.common_errors) == 2


# =============================================================================
# 6. ActionFeedbackLoop - Intent Recording Tests
# =============================================================================


class TestActionFeedbackLoopIntentRecording:
    """Test ActionFeedbackLoop intent recording."""

    def test_record_intent_returns_intent_id(self, feedback_loop):
        """record_intent should return a unique intent_id."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        assert intent_id is not None
        assert "test_action" in intent_id
        assert "_" in intent_id

    def test_record_intent_stores_pending_intent(self, feedback_loop):
        """record_intent should store intent in pending_intents."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        assert intent_id in feedback_loop._pending_intents
        intent = feedback_loop._pending_intents[intent_id]
        assert intent.action_name == "test_action"
        assert intent.why == "Test reasoning"

    def test_record_intent_with_objective_id(self, feedback_loop):
        """record_intent should accept optional objective_id."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
            objective_id="obj_001",
        )

        intent = feedback_loop._pending_intents[intent_id]
        assert intent.objective_id == "obj_001"

    def test_record_intent_with_context(self, feedback_loop):
        """record_intent should accept optional context."""
        context = {"token": "ABC", "amount": 100}
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
            context=context,
        )

        intent = feedback_loop._pending_intents[intent_id]
        assert intent.context == context

    def test_record_intent_generates_unique_ids(self, feedback_loop):
        """record_intent should generate unique IDs for each call."""
        ids = set()
        # Use time.sleep to ensure millisecond differences, or use different action names
        for i in range(10):
            intent_id = feedback_loop.record_intent(
                action_name=f"test_{i}",  # Use different action names to ensure uniqueness
                why="test",
                expected_outcome="test",
                success_criteria=[],
            )
            ids.add(intent_id)

        assert len(ids) == 10  # All IDs should be unique

    def test_record_intent_includes_timestamp_in_id(self, feedback_loop):
        """record_intent ID should include timestamp component."""
        with patch("core.action_feedback.time.time", return_value=1234567.890):
            intent_id = feedback_loop.record_intent(
                action_name="test",
                why="test",
                expected_outcome="test",
                success_criteria=[],
            )

        assert "1234567890" in intent_id


# =============================================================================
# 7. ActionFeedbackLoop - Outcome Recording Tests
# =============================================================================


class TestActionFeedbackLoopOutcomeRecording:
    """Test ActionFeedbackLoop outcome recording."""

    def test_record_outcome_returns_feedback_for_valid_intent(self, feedback_loop):
        """record_outcome should return ActionFeedback for valid intent_id."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                )

        assert feedback is not None
        assert feedback.id == intent_id
        assert feedback.outcome.success is True

    def test_record_outcome_returns_none_for_invalid_intent(self, feedback_loop):
        """record_outcome should return None for invalid intent_id."""
        feedback = feedback_loop.record_outcome(
            intent_id="invalid_intent_id",
            success=True,
            actual_outcome="Test succeeded",
        )

        assert feedback is None

    def test_record_outcome_removes_pending_intent(self, feedback_loop):
        """record_outcome should remove intent from pending_intents."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        assert intent_id in feedback_loop._pending_intents

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                )

        assert intent_id not in feedback_loop._pending_intents

    def test_record_outcome_captures_error(self, feedback_loop):
        """record_outcome should capture error details."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=False,
                    actual_outcome="Test failed",
                    error="Connection timeout",
                )

        assert feedback.outcome.error == "Connection timeout"

    def test_record_outcome_captures_duration(self, feedback_loop):
        """record_outcome should capture duration_ms."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                    duration_ms=1500,
                )

        assert feedback.outcome.duration_ms == 1500

    def test_record_outcome_captures_side_effects(self, feedback_loop):
        """record_outcome should capture side_effects."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                    side_effects=["cache_updated", "log_written"],
                )

        assert feedback.outcome.side_effects == ["cache_updated", "log_written"]

    def test_record_outcome_uses_provided_criteria_results(self, feedback_loop):
        """record_outcome should use provided criteria_results."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1", "criterion_2"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                    criteria_results={"criterion_1": True, "criterion_2": False},
                )

        assert feedback.criteria_met == {"criterion_1": True, "criterion_2": False}

    def test_record_outcome_defaults_criteria_to_success_value(self, feedback_loop):
        """record_outcome should default criteria_met based on success."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1", "criterion_2"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Test succeeded",
                )

        assert feedback.criteria_met == {"criterion_1": True, "criterion_2": True}

    def test_record_outcome_creates_gap_analysis_on_failure(self, feedback_loop):
        """record_outcome should create gap_analysis on failure."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Test succeeds",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=False,
                    actual_outcome="Test failed",
                    error="Network error",
                )

        assert "Expected: 'Test succeeds'" in feedback.gap_analysis
        assert "Got: 'Test failed'" in feedback.gap_analysis
        assert "Network error" in feedback.gap_analysis

    def test_record_outcome_creates_gap_analysis_on_mismatch(self, feedback_loop):
        """record_outcome should create gap_analysis when outcome differs."""
        intent_id = feedback_loop.record_intent(
            action_name="test_action",
            why="Test reasoning",
            expected_outcome="Browser opens Gmail",
            success_criteria=["criterion_1"],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Browser opens Yahoo",  # Different!
                )

        assert "Expected: 'Browser opens Gmail'" in feedback.gap_analysis
        assert "Got: 'Browser opens Yahoo'" in feedback.gap_analysis


# =============================================================================
# 8. ActionFeedbackLoop - Lesson Extraction Tests
# =============================================================================


class TestActionFeedbackLoopLessonExtraction:
    """Test ActionFeedbackLoop lesson extraction."""

    def test_extract_lesson_from_failure(self, feedback_loop, sample_intent):
        """_extract_lesson should create lesson from failure."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=False,
            actual_outcome="Operation failed",
            error="Timeout error",
        )
        criteria_met = {}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert "'test_action' failed" in lesson
        assert "Timeout error" in lesson

    def test_extract_lesson_from_unmet_criteria(self, feedback_loop, sample_intent):
        """_extract_lesson should include unmet criteria."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(success=True, actual_outcome="Partial success")
        criteria_met = {"criterion_1": True, "criterion_2": False}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert "Unmet criteria" in lesson
        assert "criterion_2" in lesson

    def test_extract_lesson_from_slow_action(self, feedback_loop, sample_intent):
        """_extract_lesson should note slow actions."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            duration_ms=6000,  # > 5000ms threshold
        )
        criteria_met = {}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert "was slow" in lesson
        assert "6000ms" in lesson

    def test_extract_lesson_from_side_effects(self, feedback_loop, sample_intent):
        """_extract_lesson should note side effects."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            side_effects=["cache_invalidated", "notification_sent"],
        )
        criteria_met = {}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert "Side effects" in lesson
        assert "cache_invalidated" in lesson

    def test_extract_lesson_empty_for_clean_success(self, feedback_loop, sample_intent):
        """_extract_lesson should return empty string for clean success."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            duration_ms=100,  # Fast
        )
        criteria_met = {"criterion_1": True, "criterion_2": True}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert lesson == ""

    def test_extract_lesson_combines_multiple_issues(self, feedback_loop, sample_intent):
        """_extract_lesson should combine multiple issues."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=False,
            actual_outcome="Failed",
            error="Timeout",
            duration_ms=7000,
            side_effects=["data_corrupted"],
        )
        criteria_met = {"criterion_1": False}

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, criteria_met)

        assert "failed" in lesson.lower()
        assert "Unmet criteria" in lesson
        assert "was slow" in lesson
        assert "Side effects" in lesson


# =============================================================================
# 9. ActionFeedbackLoop - Feedback Persistence Tests
# =============================================================================


class TestActionFeedbackLoopPersistence:
    """Test ActionFeedbackLoop feedback persistence."""

    def test_persist_feedback_writes_to_log_file(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_persist_feedback should write to feedback log file."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
            criteria_met={"criterion_1": True},
            gap_analysis="",
            lesson_learned="",
            should_remember=False,
        )

        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            feedback_loop._persist_feedback(feedback)

        mock_file.assert_called_once()
        # Check that JSON was written
        written_data = mock_file().write.call_args[0][0]
        assert "test_id" in written_data
        assert "test_action" in written_data

    def test_persist_feedback_includes_all_fields(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_persist_feedback should include all required fields."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id_123",
            intent=sample_intent,
            outcome=sample_outcome_success,
            criteria_met={"c1": True},
            gap_analysis="Expected A got B",
            lesson_learned="Need to handle X",
            should_remember=True,
        )

        mock_file = mock_open()
        with patch("builtins.open", mock_file):
            feedback_loop._persist_feedback(feedback)

        written_data = mock_file().write.call_args[0][0]
        entry = json.loads(written_data.strip())

        assert entry["id"] == "test_id_123"
        assert entry["action"] == "test_action"
        assert entry["why"] == "Test reasoning"
        assert entry["expected"] == "Test succeeds"
        assert entry["success"] is True
        assert "timestamp" in entry


# =============================================================================
# 10. ActionFeedbackLoop - Metrics Update Tests
# =============================================================================


class TestActionFeedbackLoopMetricsUpdate:
    """Test ActionFeedbackLoop metrics update."""

    def test_update_metrics_creates_new_metrics_for_new_action(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_update_metrics should create new metrics for unknown action."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        feedback_loop._update_metrics(feedback)

        assert "test_action" in feedback_loop._metrics_cache
        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.total_calls == 1
        assert metrics.success_count == 1

    def test_update_metrics_increments_success_count(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_update_metrics should increment success_count on success."""
        from core.action_feedback import ActionFeedback

        for i in range(3):
            feedback = ActionFeedback(
                id=f"test_id_{i}",
                intent=sample_intent,
                outcome=sample_outcome_success,
            )
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.total_calls == 3
        assert metrics.success_count == 3
        assert metrics.failure_count == 0

    def test_update_metrics_increments_failure_count(
        self, feedback_loop, sample_intent, sample_outcome_failure
    ):
        """_update_metrics should increment failure_count on failure."""
        from core.action_feedback import ActionFeedback

        for i in range(2):
            feedback = ActionFeedback(
                id=f"test_id_{i}",
                intent=sample_intent,
                outcome=sample_outcome_failure,
            )
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.total_calls == 2
        assert metrics.success_count == 0
        assert metrics.failure_count == 2

    def test_update_metrics_updates_last_success_timestamp(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_update_metrics should update last_success timestamp."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_success,
        )

        with patch("core.action_feedback.time.time", return_value=12345.0):
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.last_success == 12345.0

    def test_update_metrics_updates_last_failure_timestamp(
        self, feedback_loop, sample_intent, sample_outcome_failure
    ):
        """_update_metrics should update last_failure timestamp."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_failure,
        )

        with patch("core.action_feedback.time.time", return_value=12345.0):
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.last_failure == 12345.0

    def test_update_metrics_tracks_common_errors(
        self, feedback_loop, sample_intent
    ):
        """_update_metrics should track common errors."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        errors = ["Error A", "Error B", "Error C"]
        for i, error in enumerate(errors):
            outcome = ActionOutcome(
                success=False,
                actual_outcome="Failed",
                error=error,
            )
            feedback = ActionFeedback(
                id=f"test_id_{i}",
                intent=sample_intent,
                outcome=outcome,
            )
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert "Error A" in metrics.common_errors
        assert "Error B" in metrics.common_errors
        assert "Error C" in metrics.common_errors

    def test_update_metrics_limits_common_errors_to_five(
        self, feedback_loop, sample_intent
    ):
        """_update_metrics should keep only last 5 errors."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        with patch.object(feedback_loop, "_save_metrics"):  # Avoid file I/O
            for i in range(10):
                outcome = ActionOutcome(
                    success=False,
                    actual_outcome="Failed",
                    error=f"Error_{i}",
                )
                feedback = ActionFeedback(
                    id=f"test_id_{i}",
                    intent=sample_intent,
                    outcome=outcome,
                )
                feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert len(metrics.common_errors) <= 5
        # Should have most recent errors
        assert "Error_9" in metrics.common_errors
        assert "Error_8" in metrics.common_errors

    def test_update_metrics_calculates_success_rate(
        self, feedback_loop, sample_intent, sample_outcome_success, sample_outcome_failure
    ):
        """_update_metrics should calculate success_rate."""
        from core.action_feedback import ActionFeedback

        # 2 successes
        for i in range(2):
            feedback = ActionFeedback(
                id=f"success_{i}",
                intent=sample_intent,
                outcome=sample_outcome_success,
            )
            feedback_loop._update_metrics(feedback)

        # 2 failures
        for i in range(2):
            feedback = ActionFeedback(
                id=f"failure_{i}",
                intent=sample_intent,
                outcome=sample_outcome_failure,
            )
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.success_rate == 0.5  # 2/4

    def test_update_metrics_calculates_avg_duration(
        self, feedback_loop, sample_intent
    ):
        """_update_metrics should calculate avg_duration_ms."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        durations = [100, 200, 300]
        for i, duration in enumerate(durations):
            outcome = ActionOutcome(
                success=True,
                actual_outcome="Success",
                duration_ms=duration,
            )
            feedback = ActionFeedback(
                id=f"test_id_{i}",
                intent=sample_intent,
                outcome=outcome,
            )
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert metrics.avg_duration_ms == 200.0  # (100+200+300)/3

    def test_update_metrics_saves_periodically(
        self, feedback_loop, sample_intent, sample_outcome_success
    ):
        """_update_metrics should save every 10 calls."""
        from core.action_feedback import ActionFeedback

        with patch.object(feedback_loop, "_save_metrics") as mock_save:
            for i in range(25):
                feedback = ActionFeedback(
                    id=f"test_id_{i}",
                    intent=sample_intent,
                    outcome=sample_outcome_success,
                )
                feedback_loop._update_metrics(feedback)

            # Should be called at 10 and 20
            assert mock_save.call_count == 2


# =============================================================================
# 11. ActionFeedbackLoop - Pattern Analysis Tests
# =============================================================================


class TestActionFeedbackLoopPatternAnalysis:
    """Test ActionFeedbackLoop pattern analysis."""

    def test_analyze_feedback_detects_failure_pattern(
        self, feedback_loop, sample_intent, sample_outcome_failure
    ):
        """analyze_feedback should detect failure patterns."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_failure,
        )

        with patch.object(feedback_loop, "_add_pattern") as mock_add:
            pattern = feedback_loop.analyze_feedback(feedback)

        assert pattern is not None
        assert pattern.pattern_type == "failure"
        mock_add.assert_called_once()

    def test_analyze_feedback_detects_slow_pattern(
        self, feedback_loop, sample_intent
    ):
        """analyze_feedback should detect slow action patterns."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            duration_ms=6000,  # > 5000ms threshold
        )
        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=outcome,
        )

        with patch.object(feedback_loop, "_add_pattern") as mock_add:
            pattern = feedback_loop.analyze_feedback(feedback)

        assert pattern is not None
        assert pattern.pattern_type == "slow"
        assert "6000ms" in pattern.description

    def test_analyze_feedback_detects_side_effect_pattern(
        self, feedback_loop, sample_intent
    ):
        """analyze_feedback should detect side effect patterns."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            side_effects=["database_updated", "email_sent"],
        )
        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=outcome,
        )

        with patch.object(feedback_loop, "_add_pattern") as mock_add:
            pattern = feedback_loop.analyze_feedback(feedback)

        assert pattern is not None
        assert pattern.pattern_type == "side_effect"
        assert "database_updated" in pattern.description

    def test_analyze_feedback_returns_none_for_clean_success(
        self, feedback_loop, sample_intent
    ):
        """analyze_feedback should return None for clean success."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        outcome = ActionOutcome(
            success=True,
            actual_outcome="Success",
            duration_ms=100,  # Fast
        )
        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=outcome,
        )

        pattern = feedback_loop.analyze_feedback(feedback)

        assert pattern is None


# =============================================================================
# 12. ActionFeedbackLoop - Pattern Detection Tests
# =============================================================================


class TestActionFeedbackLoopPatternDetection:
    """Test ActionFeedbackLoop pattern detection."""

    def test_detect_failure_pattern_creates_new_pattern(
        self, feedback_loop, sample_intent, sample_outcome_failure
    ):
        """_detect_failure_pattern should create new pattern."""
        from core.action_feedback import ActionFeedback

        feedback = ActionFeedback(
            id="test_id",
            intent=sample_intent,
            outcome=sample_outcome_failure,
        )

        pattern = feedback_loop._detect_failure_pattern(feedback)

        assert pattern is not None
        assert pattern.pattern_type == "failure"
        assert pattern.action_name == "test_action"
        assert "Connection timeout" in pattern.description

    def test_detect_failure_pattern_increments_existing_pattern(
        self, feedback_loop_with_patterns
    ):
        """_detect_failure_pattern should increment frequency of existing pattern."""
        from core.action_feedback import ActionIntent, ActionOutcome, ActionFeedback

        intent = ActionIntent(
            action_name="known_action",
            why="Test",
            expected_outcome="Success",
            success_criteria=[],
        )
        outcome = ActionOutcome(
            success=False,
            actual_outcome="Failed",
            error="timeout error",  # Matches existing pattern
        )
        feedback = ActionFeedback(
            id="test_id",
            intent=intent,
            outcome=outcome,
        )

        initial_frequency = feedback_loop_with_patterns._patterns[0].frequency

        with patch.object(feedback_loop_with_patterns, "_save_patterns"):
            pattern = feedback_loop_with_patterns._detect_failure_pattern(feedback)

        assert pattern.frequency == initial_frequency + 1

    def test_add_pattern_stores_new_pattern(self, feedback_loop):
        """_add_pattern should add new pattern to list."""
        from core.action_feedback import ActionPattern

        pattern = ActionPattern(
            pattern_type="failure",
            action_name="new_action",
            description="New failure pattern",
        )

        with patch.object(feedback_loop, "_save_patterns"):
            with patch("core.action_feedback.memory") as mock_memory:
                feedback_loop._add_pattern(pattern)

        assert len(feedback_loop._patterns) == 1
        assert feedback_loop._patterns[0].action_name == "new_action"

    def test_add_pattern_increments_existing_pattern_frequency(self, feedback_loop):
        """_add_pattern should increment frequency of similar pattern."""
        from core.action_feedback import ActionPattern

        pattern1 = ActionPattern(
            pattern_type="failure",
            action_name="test_action",
            description="Test failure",
        )
        pattern2 = ActionPattern(
            pattern_type="failure",
            action_name="test_action",
            description="Another description",  # Same type/action
        )

        with patch.object(feedback_loop, "_save_patterns"):
            with patch("core.action_feedback.memory"):
                feedback_loop._add_pattern(pattern1)
                feedback_loop._add_pattern(pattern2)

        assert len(feedback_loop._patterns) == 1
        assert feedback_loop._patterns[0].frequency == 2

    def test_add_pattern_stores_in_memory_when_significant(self, feedback_loop):
        """_add_pattern should store in memory for significant patterns."""
        from core.action_feedback import ActionPattern

        # Failure patterns are always stored
        pattern = ActionPattern(
            pattern_type="failure",
            action_name="critical_action",
            description="Critical failure",
        )

        # The import is: from core import memory, so we patch the whole memory module
        with patch.object(feedback_loop, "_save_patterns"):
            with patch("core.action_feedback.memory") as mock_memory_module:
                mock_memory_module.append_entry = MagicMock()
                with patch("core.action_feedback.safety.SafetyContext"):
                    feedback_loop._add_pattern(pattern)

        mock_memory_module.append_entry.assert_called_once()


# =============================================================================
# 13. ActionFeedbackLoop - Recommendations Tests
# =============================================================================


class TestActionFeedbackLoopRecommendations:
    """Test ActionFeedbackLoop recommendations."""

    def test_get_recommendations_for_low_success_rate(self, feedback_loop):
        """get_recommendations should warn about low success rate."""
        from core.action_feedback import ActionMetrics

        feedback_loop._metrics_cache["test_action"] = ActionMetrics(
            action_name="test_action",
            total_calls=10,
            success_count=3,
            failure_count=7,
            success_rate=0.3,  # < 0.5
            common_errors=["timeout", "network_error"],
        )

        recs = feedback_loop.get_recommendations("test_action")

        assert len(recs) > 0
        assert any("low success rate" in r.lower() for r in recs)
        assert any("30%" in r for r in recs)

    def test_get_recommendations_for_slow_action(self, feedback_loop):
        """get_recommendations should warn about slow actions."""
        from core.action_feedback import ActionMetrics

        feedback_loop._metrics_cache["test_action"] = ActionMetrics(
            action_name="test_action",
            avg_duration_ms=5000,  # > 3000ms threshold
            success_rate=0.9,
        )

        recs = feedback_loop.get_recommendations("test_action")

        assert len(recs) > 0
        assert any("slow" in r.lower() for r in recs)
        assert any("async" in r.lower() for r in recs)

    def test_get_recommendations_for_frequent_failure_pattern(self, feedback_loop):
        """get_recommendations should include frequent failure patterns."""
        from core.action_feedback import ActionPattern

        feedback_loop._patterns.append(
            ActionPattern(
                pattern_type="failure",
                action_name="test_action",
                description="Always fails on Mondays",
                frequency=5,  # >= 3 threshold
            )
        )

        recs = feedback_loop.get_recommendations("test_action")

        assert len(recs) > 0
        assert any("Known issue" in r for r in recs)

    def test_get_recommendations_for_side_effect_pattern(self, feedback_loop):
        """get_recommendations should include side effect warnings."""
        from core.action_feedback import ActionPattern

        feedback_loop._patterns.append(
            ActionPattern(
                pattern_type="side_effect",
                action_name="test_action",
                description="Causes cache invalidation",
            )
        )

        recs = feedback_loop.get_recommendations("test_action")

        assert len(recs) > 0
        assert any("Watch for" in r for r in recs)

    def test_get_recommendations_empty_for_unknown_action(self, feedback_loop):
        """get_recommendations should return empty list for unknown action."""
        recs = feedback_loop.get_recommendations("unknown_action")

        assert recs == []

    def test_get_recommendations_empty_for_healthy_action(self, feedback_loop):
        """get_recommendations should return empty for healthy action."""
        from core.action_feedback import ActionMetrics

        feedback_loop._metrics_cache["test_action"] = ActionMetrics(
            action_name="test_action",
            total_calls=100,
            success_count=95,
            failure_count=5,
            success_rate=0.95,  # > 0.5
            avg_duration_ms=100,  # < 3000ms
        )

        recs = feedback_loop.get_recommendations("test_action")

        assert recs == []


# =============================================================================
# 14. ActionFeedbackLoop - Pattern Save/Load Tests
# =============================================================================


class TestActionFeedbackLoopPatternIO:
    """Test ActionFeedbackLoop pattern save/load."""

    def test_load_patterns_from_file(self, mock_ensure_dir):
        """_load_patterns should load patterns from file."""
        patterns_data = {
            "patterns": [
                {
                    "pattern_type": "failure",
                    "action_name": "loaded_action",
                    "description": "Loaded pattern",
                    "frequency": 10,
                    "last_seen": 2000.0,
                    "context_keys": ["key1"],
                }
            ],
            "updated_at": 2000.0,
        }

        with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(patterns_data))):
                from core.action_feedback import ActionFeedbackLoop
                loop = ActionFeedbackLoop()

        assert len(loop._patterns) == 1
        assert loop._patterns[0].action_name == "loaded_action"
        assert loop._patterns[0].frequency == 10

    def test_load_patterns_handles_missing_file(self, mock_ensure_dir):
        """_load_patterns should handle missing file gracefully."""
        with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
            mock_file.exists.return_value = False
            from core.action_feedback import ActionFeedbackLoop
            loop = ActionFeedbackLoop()

        assert loop._patterns == []

    def test_load_patterns_handles_invalid_json(self, mock_ensure_dir):
        """_load_patterns should handle invalid JSON gracefully."""
        with patch("core.action_feedback.PATTERNS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data="not valid json")):
                from core.action_feedback import ActionFeedbackLoop
                loop = ActionFeedbackLoop()

        assert loop._patterns == []

    def test_save_patterns_writes_to_file(self, feedback_loop, tmp_path):
        """_save_patterns should write patterns to file."""
        from core.action_feedback import ActionPattern
        import core.action_feedback as af

        feedback_loop._patterns = [
            ActionPattern(
                pattern_type="failure",
                action_name="test_action",
                description="Test pattern",
            )
        ]

        # Use tmp_path for actual file I/O test
        test_file = tmp_path / "patterns.json"
        with patch.object(af, "PATTERNS_FILE", test_file):
            feedback_loop._save_patterns()

        assert test_file.exists()
        data = json.loads(test_file.read_text())
        assert "patterns" in data
        assert len(data["patterns"]) == 1

    def test_save_metrics_writes_to_file(self, feedback_loop, tmp_path):
        """_save_metrics should write metrics to file."""
        from core.action_feedback import ActionMetrics
        import core.action_feedback as af

        feedback_loop._metrics_cache["test_action"] = ActionMetrics(
            action_name="test_action",
            total_calls=50,
        )

        # Use tmp_path for actual file I/O test
        test_file = tmp_path / "metrics.json"
        with patch.object(af, "METRICS_FILE", test_file):
            feedback_loop._save_metrics()

        assert test_file.exists()
        data = json.loads(test_file.read_text())
        assert "metrics" in data
        assert "test_action" in data["metrics"]


# =============================================================================
# 15. ActionFeedbackLoop - Get Methods Tests
# =============================================================================


class TestActionFeedbackLoopGetMethods:
    """Test ActionFeedbackLoop get methods."""

    def test_get_metrics_returns_all_metrics(self, feedback_loop):
        """get_metrics should return all metrics when no action specified."""
        from core.action_feedback import ActionMetrics

        feedback_loop._metrics_cache["action1"] = ActionMetrics(
            action_name="action1", total_calls=10
        )
        feedback_loop._metrics_cache["action2"] = ActionMetrics(
            action_name="action2", total_calls=20
        )

        metrics = feedback_loop.get_metrics()

        assert len(metrics) == 2
        assert "action1" in metrics
        assert "action2" in metrics

    def test_get_metrics_returns_single_action_metrics(self, feedback_loop):
        """get_metrics should return metrics for specified action."""
        from core.action_feedback import ActionMetrics

        feedback_loop._metrics_cache["action1"] = ActionMetrics(
            action_name="action1", total_calls=10
        )

        metrics = feedback_loop.get_metrics("action1")

        assert metrics["action_name"] == "action1"
        assert metrics["total_calls"] == 10

    def test_get_metrics_returns_empty_for_unknown_action(self, feedback_loop):
        """get_metrics should return empty dict for unknown action."""
        metrics = feedback_loop.get_metrics("unknown_action")

        assert metrics == {}

    def test_get_patterns_returns_all_patterns(self, feedback_loop):
        """get_patterns should return all patterns when no action specified."""
        from core.action_feedback import ActionPattern

        feedback_loop._patterns = [
            ActionPattern(pattern_type="failure", action_name="action1", description="p1"),
            ActionPattern(pattern_type="slow", action_name="action2", description="p2"),
        ]

        patterns = feedback_loop.get_patterns()

        assert len(patterns) == 2

    def test_get_patterns_filters_by_action(self, feedback_loop):
        """get_patterns should filter by action_name."""
        from core.action_feedback import ActionPattern

        feedback_loop._patterns = [
            ActionPattern(pattern_type="failure", action_name="action1", description="p1"),
            ActionPattern(pattern_type="slow", action_name="action2", description="p2"),
            ActionPattern(pattern_type="side_effect", action_name="action1", description="p3"),
        ]

        patterns = feedback_loop.get_patterns("action1")

        assert len(patterns) == 2
        assert all(p["action_name"] == "action1" for p in patterns)


# =============================================================================
# 16. tracked_action Decorator Tests
# =============================================================================


class TestTrackedActionDecorator:
    """Test tracked_action decorator."""

    def test_tracked_action_wraps_function(self, feedback_loop):
        """tracked_action should wrap function and return result."""
        from core.action_feedback import tracked_action

        @tracked_action(
            why="Test function",
            expected="Returns tuple",
            criteria=["completed"],
        )
        def test_func(x: int) -> Tuple[bool, str]:
            return True, f"Result: {x}"

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "_persist_feedback"):
                with patch.object(feedback_loop, "_update_metrics"):
                    success, output = test_func(42)

        assert success is True
        assert output == "Result: 42"

    def test_tracked_action_records_intent_and_outcome(self, feedback_loop):
        """tracked_action should record intent and outcome."""
        from core.action_feedback import tracked_action

        @tracked_action(
            why="Test function",
            expected="Returns success",
            criteria=["completed"],
        )
        def test_func() -> Tuple[bool, str]:
            return True, "Done"

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent") as mock_intent:
                with patch.object(feedback_loop, "record_outcome") as mock_outcome:
                    mock_intent.return_value = "intent_123"
                    test_func()

        mock_intent.assert_called_once()
        mock_outcome.assert_called_once()
        assert mock_outcome.call_args[1]["intent_id"] == "intent_123"

    def test_tracked_action_captures_exception(self, feedback_loop):
        """tracked_action should capture exception and record failure."""
        from core.action_feedback import tracked_action

        @tracked_action(
            why="Test function",
            expected="Returns success",
            criteria=["completed"],
        )
        def failing_func() -> Tuple[bool, str]:
            raise ValueError("Test error")

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent", return_value="intent_123"):
                with patch.object(feedback_loop, "record_outcome") as mock_outcome:
                    with pytest.raises(ValueError):
                        failing_func()

        mock_outcome.assert_called_once()
        assert mock_outcome.call_args[1]["success"] is False
        assert "Test error" in mock_outcome.call_args[1]["error"]

    def test_tracked_action_measures_duration(self, feedback_loop):
        """tracked_action should measure function duration."""
        from core.action_feedback import tracked_action
        import time as real_time

        @tracked_action(
            why="Test function",
            expected="Returns success",
        )
        def slow_func() -> Tuple[bool, str]:
            real_time.sleep(0.1)
            return True, "Done"

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent", return_value="intent_123"):
                with patch.object(feedback_loop, "record_outcome") as mock_outcome:
                    slow_func()

        duration = mock_outcome.call_args[1]["duration_ms"]
        assert duration >= 100  # At least 100ms

    def test_tracked_action_uses_default_criteria(self, feedback_loop):
        """tracked_action should use default criteria if not provided."""
        from core.action_feedback import tracked_action

        @tracked_action(
            why="Test function",
            expected="Returns success",
        )
        def test_func() -> Tuple[bool, str]:
            return True, "Done"

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent") as mock_intent:
                with patch.object(feedback_loop, "record_outcome"):
                    mock_intent.return_value = "intent_123"
                    test_func()

        assert mock_intent.call_args[1]["success_criteria"] == ["action_completed"]


# =============================================================================
# 17. Convenience Functions Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_feedback_loop_returns_singleton(self):
        """get_feedback_loop should return singleton instance."""
        # Reset global
        import core.action_feedback as af
        af._feedback_loop = None

        with patch.object(af.ActionFeedbackLoop, "__init__", return_value=None):
            loop1 = af.get_feedback_loop()
            loop2 = af.get_feedback_loop()

        assert loop1 is loop2

    def test_record_action_intent_delegates_to_loop(self, feedback_loop):
        """record_action_intent should delegate to loop."""
        from core.action_feedback import record_action_intent

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent", return_value="intent_id"):
                result = record_action_intent(
                    action_name="test",
                    why="test reason",
                    expected_outcome="test outcome",
                )

        assert result == "intent_id"

    def test_record_action_intent_uses_default_criteria(self, feedback_loop):
        """record_action_intent should use default criteria if not provided."""
        from core.action_feedback import record_action_intent

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_intent") as mock_intent:
                mock_intent.return_value = "intent_id"
                record_action_intent(
                    action_name="test",
                    why="test reason",
                    expected_outcome="test outcome",
                )

        assert mock_intent.call_args[1]["success_criteria"] == ["action_completed"]

    def test_record_action_outcome_delegates_to_loop(self, feedback_loop):
        """record_action_outcome should delegate to loop."""
        from core.action_feedback import record_action_outcome, ActionFeedback

        mock_feedback = MagicMock(spec=ActionFeedback)

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(feedback_loop, "record_outcome", return_value=mock_feedback):
                result = record_action_outcome(
                    intent_id="intent_123",
                    success=True,
                    actual_outcome="Done",
                )

        assert result is mock_feedback

    def test_get_action_recommendations_delegates_to_loop(self, feedback_loop):
        """get_action_recommendations should delegate to loop."""
        from core.action_feedback import get_action_recommendations

        with patch("core.action_feedback.get_feedback_loop", return_value=feedback_loop):
            with patch.object(
                feedback_loop, "get_recommendations", return_value=["rec1", "rec2"]
            ):
                result = get_action_recommendations("test_action")

        assert result == ["rec1", "rec2"]


# =============================================================================
# 18. Module-Level Constants and Functions Tests
# =============================================================================


class TestModuleLevelFunctions:
    """Test module-level constants and utility functions."""

    def test_feedback_dir_is_path(self):
        """FEEDBACK_DIR should be a Path object."""
        from core.action_feedback import FEEDBACK_DIR

        assert isinstance(FEEDBACK_DIR, Path)

    def test_feedback_log_is_path(self):
        """FEEDBACK_LOG should be a Path object."""
        from core.action_feedback import FEEDBACK_LOG

        assert isinstance(FEEDBACK_LOG, Path)

    def test_patterns_file_is_path(self):
        """PATTERNS_FILE should be a Path object."""
        from core.action_feedback import PATTERNS_FILE

        assert isinstance(PATTERNS_FILE, Path)

    def test_metrics_file_is_path(self):
        """METRICS_FILE should be a Path object."""
        from core.action_feedback import METRICS_FILE

        assert isinstance(METRICS_FILE, Path)

    def test_ensure_dir_creates_directory(self, tmp_path):
        """_ensure_dir should create directory if it doesn't exist."""
        import core.action_feedback as af

        # Use tmp_path to test actual directory creation
        test_dir = tmp_path / "test_feedback_dir"

        with patch.object(af, "FEEDBACK_DIR", test_dir):
            af._ensure_dir()

        assert test_dir.exists()
        assert test_dir.is_dir()


# =============================================================================
# 19. Integration Tests
# =============================================================================


class TestActionFeedbackIntegration:
    """Integration tests for action feedback system."""

    def test_full_feedback_cycle(self, feedback_loop):
        """Test complete feedback cycle from intent to analysis."""
        # Record intent
        intent_id = feedback_loop.record_intent(
            action_name="integration_test",
            why="Testing full cycle",
            expected_outcome="All steps pass",
            success_criteria=["step1", "step2"],
        )

        assert intent_id is not None

        # Record outcome
        with patch.object(feedback_loop, "_persist_feedback"):
            feedback = feedback_loop.record_outcome(
                intent_id=intent_id,
                success=False,
                actual_outcome="Step 2 failed",
                error="Validation error",
                duration_ms=2500,
            )

        assert feedback is not None
        assert feedback.outcome.success is False

        # Analyze feedback
        with patch.object(feedback_loop, "_add_pattern"):
            pattern = feedback_loop.analyze_feedback(feedback)

        assert pattern is not None
        assert pattern.pattern_type == "failure"

    def test_multiple_actions_tracked_independently(self, feedback_loop):
        """Test that multiple actions are tracked independently."""
        # Track action1
        intent1 = feedback_loop.record_intent(
            action_name="action1",
            why="Test action 1",
            expected_outcome="Success",
            success_criteria=["done"],
        )

        # Track action2
        intent2 = feedback_loop.record_intent(
            action_name="action2",
            why="Test action 2",
            expected_outcome="Success",
            success_criteria=["done"],
        )

        # Record outcomes
        with patch.object(feedback_loop, "_persist_feedback"):
            feedback1 = feedback_loop.record_outcome(
                intent_id=intent1,
                success=True,
                actual_outcome="Action 1 done",
            )
            feedback2 = feedback_loop.record_outcome(
                intent_id=intent2,
                success=False,
                actual_outcome="Action 2 failed",
                error="Timeout",
            )

        assert feedback1.intent.action_name == "action1"
        assert feedback2.intent.action_name == "action2"
        assert feedback1.outcome.success is True
        assert feedback2.outcome.success is False

    def test_metrics_accumulate_over_time(self, feedback_loop):
        """Test that metrics accumulate correctly over time."""
        from core.action_feedback import ActionFeedback, ActionIntent, ActionOutcome

        intent = ActionIntent(
            action_name="repeated_action",
            why="Test",
            expected_outcome="Success",
            success_criteria=[],
        )

        # 5 successes
        for i in range(5):
            outcome = ActionOutcome(success=True, actual_outcome="OK", duration_ms=100)
            feedback = ActionFeedback(id=f"s{i}", intent=intent, outcome=outcome)
            feedback_loop._update_metrics(feedback)

        # 3 failures
        for i in range(3):
            outcome = ActionOutcome(
                success=False, actual_outcome="Fail", error=f"Error{i}", duration_ms=200
            )
            feedback = ActionFeedback(id=f"f{i}", intent=intent, outcome=outcome)
            feedback_loop._update_metrics(feedback)

        metrics = feedback_loop.get_metrics("repeated_action")

        assert metrics["total_calls"] == 8
        assert metrics["success_count"] == 5
        assert metrics["failure_count"] == 3
        assert metrics["success_rate"] == 5 / 8
        assert len(metrics["common_errors"]) == 3


# =============================================================================
# 20. Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_record_outcome_with_empty_side_effects(self, feedback_loop):
        """record_outcome should handle None side_effects."""
        intent_id = feedback_loop.record_intent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="Done",
                    side_effects=None,
                )

        assert feedback.outcome.side_effects == []

    def test_record_outcome_with_long_error_message(self, feedback_loop, sample_intent):
        """_update_metrics should truncate long error messages."""
        from core.action_feedback import ActionFeedback, ActionOutcome

        long_error = "E" * 200
        outcome = ActionOutcome(success=False, actual_outcome="Fail", error=long_error)
        feedback = ActionFeedback(id="test", intent=sample_intent, outcome=outcome)

        feedback_loop._update_metrics(feedback)

        metrics = feedback_loop._metrics_cache["test_action"]
        assert len(metrics.common_errors[0]) <= 100

    def test_record_intent_with_none_context(self, feedback_loop):
        """record_intent should handle None context."""
        intent_id = feedback_loop.record_intent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
            context=None,
        )

        intent = feedback_loop._pending_intents[intent_id]
        assert intent.context == {}

    def test_gap_analysis_without_error(self, feedback_loop):
        """Gap analysis should work without error message."""
        intent_id = feedback_loop.record_intent(
            action_name="test",
            why="test",
            expected_outcome="Expected A",
            success_criteria=[],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=False,
                    actual_outcome="Got B",
                    error="",
                )

        assert "Expected: 'Expected A'" in feedback.gap_analysis
        assert "Got: 'Got B'" in feedback.gap_analysis
        assert "Error:" not in feedback.gap_analysis

    def test_empty_success_criteria(self, feedback_loop):
        """Should handle empty success criteria list."""
        intent_id = feedback_loop.record_intent(
            action_name="test",
            why="test",
            expected_outcome="test",
            success_criteria=[],
        )

        with patch.object(feedback_loop, "_persist_feedback"):
            with patch.object(feedback_loop, "_update_metrics"):
                feedback = feedback_loop.record_outcome(
                    intent_id=intent_id,
                    success=True,
                    actual_outcome="test",
                )

        assert feedback.criteria_met == {}

    def test_failure_with_actual_outcome_only(self, feedback_loop, sample_intent):
        """_extract_lesson should use actual_outcome when error is empty."""
        from core.action_feedback import ActionOutcome

        outcome = ActionOutcome(
            success=False,
            actual_outcome="Network unreachable",
            error="",
        )

        lesson = feedback_loop._extract_lesson(sample_intent, outcome, {})

        assert "test_action" in lesson
        assert "failed" in lesson.lower()
        assert "Network unreachable" in lesson
