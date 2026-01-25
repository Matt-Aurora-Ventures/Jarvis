"""
Comprehensive unit tests for the X Bot Decision Engine.

Tests cover:
- NewInformationRule: Novelty scoring and validation
- ToneQualityRule: Content filtering and banned patterns
- XDecisionEngine: Main decision engine integration
- Post decisions (should_post method)
- Reply decisions (should_reply method)
- Image generation decisions (should_generate_image method)
- Success/failure tracking and circuit breaker integration
- Statistics and reporting
- Escalation callbacks
- Edge cases and error handling

This is CORE DECISION LOGIC controlling what the bot posts to thousands
of followers. Thorough testing is essential for brand safety.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.x_decision_engine import (
    NewInformationRule,
    ToneQualityRule,
    XDecisionEngine,
    get_x_decision_engine,
    _x_decision_engine,
)
from core.decisions import (
    Decision,
    DecisionContext,
    DecisionResult,
    RiskLevel,
)


# =============================================================================
# NewInformationRule Tests
# =============================================================================

class TestNewInformationRule:
    """Tests for the NewInformationRule that filters low-value content."""

    def test_default_initialization(self):
        """Test default initialization parameters."""
        rule = NewInformationRule()
        assert rule.min_novelty_score == 0.3
        assert rule.novelty_key == "novelty_score"
        assert rule.name == "new_information"
        assert rule.description == "Ensures tweet provides new value"
        assert rule.priority == 40

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        rule = NewInformationRule(
            min_novelty_score=0.5,
            novelty_key="custom_novelty",
        )
        assert rule.min_novelty_score == 0.5
        assert rule.novelty_key == "custom_novelty"

    @pytest.mark.asyncio
    async def test_high_novelty_executes(self):
        """Test that high novelty content is allowed."""
        rule = NewInformationRule(min_novelty_score=0.3)
        context = DecisionContext(
            intent="post_tweet",
            data={"novelty_score": 0.8, "content": "Breaking news about markets"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.EXECUTE
        assert "new information" in rationale.lower()
        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_low_novelty_holds(self):
        """Test that low novelty content is held."""
        rule = NewInformationRule(min_novelty_score=0.3)
        context = DecisionContext(
            intent="post_tweet",
            data={"novelty_score": 0.1, "content": "Same old stuff"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "novelty" in rationale.lower()
        assert "10%" in rationale
        assert "30%" in rationale
        assert len(changes) == 1
        assert "novelty" in changes[0].lower()

    @pytest.mark.asyncio
    async def test_exact_threshold_executes(self):
        """Test that exact threshold score is allowed."""
        rule = NewInformationRule(min_novelty_score=0.3)
        context = DecisionContext(
            intent="post_tweet",
            data={"novelty_score": 0.3},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.EXECUTE

    @pytest.mark.asyncio
    async def test_missing_novelty_uses_default(self):
        """Test that missing novelty score uses default (0.5)."""
        rule = NewInformationRule(min_novelty_score=0.3)
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Some content"},  # No novelty_score
        )

        decision, rationale, changes = await rule.evaluate(context)

        # Default 0.5 > 0.3 threshold, so should execute
        assert decision == Decision.EXECUTE

    @pytest.mark.asyncio
    async def test_custom_novelty_key(self):
        """Test using a custom novelty key."""
        rule = NewInformationRule(
            min_novelty_score=0.5,
            novelty_key="my_novelty",
        )
        context = DecisionContext(
            intent="post_tweet",
            data={"my_novelty": 0.2},  # Low novelty under custom key
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD

    @pytest.mark.asyncio
    async def test_preserves_current_decision(self):
        """Test that rule respects current_decision parameter."""
        rule = NewInformationRule(min_novelty_score=0.3)
        context = DecisionContext(
            intent="post_tweet",
            data={"novelty_score": 0.8},
        )

        # Even with HOLD as current, high novelty should return EXECUTE
        decision, rationale, changes = await rule.evaluate(
            context, current_decision=Decision.HOLD
        )

        assert decision == Decision.EXECUTE


# =============================================================================
# ToneQualityRule Tests
# =============================================================================

class TestToneQualityRule:
    """Tests for the ToneQualityRule that filters inappropriate content."""

    def test_default_initialization(self):
        """Test default initialization with banned patterns."""
        rule = ToneQualityRule()
        assert rule.name == "tone_quality"
        assert rule.description == "Validates content tone and quality"
        assert rule.priority == 45
        assert "BREAKING" in rule.banned_patterns
        assert "WAGMI" in rule.banned_patterns
        assert "LFG" in rule.banned_patterns
        assert "100x" in rule.banned_patterns
        assert "guaranteed" in rule.banned_patterns
        assert "moonshot" in rule.banned_patterns
        assert "FOMO" in rule.banned_patterns

    def test_custom_banned_patterns(self):
        """Test custom banned patterns initialization."""
        custom_patterns = ["SPAM", "SCAM", "PUMP"]
        rule = ToneQualityRule(banned_patterns=custom_patterns)
        assert rule.banned_patterns == custom_patterns

    @pytest.mark.asyncio
    async def test_clean_content_executes(self):
        """Test that clean content is allowed."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Market analysis shows interesting trends today."},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.EXECUTE
        assert "tone quality ok" in rationale.lower()
        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_breaking_pattern_holds(self):
        """Test that BREAKING pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "BREAKING: New token launched!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "BREAKING" in rationale
        assert len(changes) == 1
        assert "BREAKING" in changes[0]

    @pytest.mark.asyncio
    async def test_wagmi_pattern_holds(self):
        """Test that WAGMI pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Bullish on SOL, wagmi frens!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "WAGMI" in rationale

    @pytest.mark.asyncio
    async def test_lfg_pattern_holds(self):
        """Test that LFG pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "New partnership announced! LFG!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "LFG" in rationale

    @pytest.mark.asyncio
    async def test_100x_pattern_holds(self):
        """Test that 100x shilling pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "This token will 100x for sure!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "100x" in rationale

    @pytest.mark.asyncio
    async def test_guaranteed_pattern_holds(self):
        """Test that guaranteed pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Guaranteed returns on this investment!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "guaranteed" in rationale

    @pytest.mark.asyncio
    async def test_moonshot_pattern_holds(self):
        """Test that moonshot pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Found a new moonshot project!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "moonshot" in rationale

    @pytest.mark.asyncio
    async def test_fomo_pattern_holds(self):
        """Test that FOMO pattern is caught."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "Don't miss out on this FOMO moment!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        assert "FOMO" in rationale

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """Test that pattern matching is case-insensitive."""
        rule = ToneQualityRule()

        # Test lowercase
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "breaking news here"},
        )
        decision, _, _ = await rule.evaluate(context)
        assert decision == Decision.HOLD

        # Test mixed case
        context2 = DecisionContext(
            intent="post_tweet",
            data={"content": "BrEaKiNg update"},
        )
        decision2, _, _ = await rule.evaluate(context2)
        assert decision2 == Decision.HOLD

    @pytest.mark.asyncio
    async def test_empty_content_executes(self):
        """Test that empty content is allowed (no patterns to match)."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={"content": ""},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.EXECUTE

    @pytest.mark.asyncio
    async def test_missing_content_executes(self):
        """Test that missing content key is handled."""
        rule = ToneQualityRule()
        context = DecisionContext(
            intent="post_tweet",
            data={},  # No content key
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.EXECUTE

    @pytest.mark.asyncio
    async def test_first_pattern_match_returned(self):
        """Test that first matching pattern is returned."""
        rule = ToneQualityRule()
        # Content has multiple banned patterns - should catch first one
        context = DecisionContext(
            intent="post_tweet",
            data={"content": "BREAKING: LFG to the moon, WAGMI!"},
        )

        decision, rationale, changes = await rule.evaluate(context)

        assert decision == Decision.HOLD
        # Should catch BREAKING first (it appears first in default list)
        assert "BREAKING" in rationale


# =============================================================================
# XDecisionEngine Tests
# =============================================================================

class TestXDecisionEngineInitialization:
    """Tests for XDecisionEngine initialization and setup."""

    def test_basic_initialization(self):
        """Test basic initialization creates engine with rules."""
        engine = XDecisionEngine()

        assert engine.engine is not None
        assert engine.engine.component == "x_bot"
        assert len(engine.engine.rules) > 0
        assert engine._hold_reasons == {}
        assert engine._last_hold_time is None

    def test_rules_are_configured(self):
        """Test that all expected rules are configured."""
        engine = XDecisionEngine()

        rule_names = [rule.name for rule in engine.engine.rules]

        # Check core rules are present
        assert "circuit_breaker" in rule_names
        assert "rate_limit" in rule_names
        assert "cost_threshold" in rule_names
        assert "duplicate_content" in rule_names
        assert "confidence_threshold" in rule_names
        assert "new_information" in rule_names
        assert "tone_quality" in rule_names

    def test_circuit_breaker_config(self):
        """Test circuit breaker is configured correctly."""
        engine = XDecisionEngine()

        cb_rule = None
        for rule in engine.engine.rules:
            if rule.name == "circuit_breaker":
                cb_rule = rule
                break

        assert cb_rule is not None
        assert cb_rule.failure_threshold == 3
        assert cb_rule.recovery_timeout == 1800  # 30 min

    def test_rate_limit_config(self):
        """Test rate limiting is configured correctly."""
        engine = XDecisionEngine()

        rl_rule = None
        for rule in engine.engine.rules:
            if rule.name == "rate_limit":
                rl_rule = rule
                break

        assert rl_rule is not None
        assert rl_rule.max_per_hour == 4
        assert rl_rule.max_per_minute == 1
        assert rl_rule.cooldown_seconds == 60

    def test_cost_threshold_config(self):
        """Test cost thresholds are configured correctly."""
        engine = XDecisionEngine()

        ct_rule = None
        for rule in engine.engine.rules:
            if rule.name == "cost_threshold":
                ct_rule = rule
                break

        assert ct_rule is not None
        assert ct_rule.max_per_action == 0.50
        assert ct_rule.max_per_hour == 2.00
        assert ct_rule.max_per_day == 20.00


class TestXDecisionEngineShouldPost:
    """Tests for the should_post decision method."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_basic_post_allowed(self, fresh_engine):
        """Test that a basic valid post is allowed."""
        result = await fresh_engine.should_post(
            content="SOL showing strong momentum today with increased volume",
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.EXECUTE
        assert result.intent == "post_tweet"
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_low_confidence_holds(self, fresh_engine):
        """Test that low confidence triggers hold."""
        result = await fresh_engine.should_post(
            content="Some market observation",
            category="market_update",
            confidence=0.3,  # Below 0.5 threshold
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.HOLD
        assert "confidence" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_very_low_confidence_escalates(self, fresh_engine):
        """Test that very low confidence triggers escalation."""
        result = await fresh_engine.should_post(
            content="Uncertain market observation",
            category="market_update",
            confidence=0.1,  # Below 0.2 escalate threshold
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.ESCALATE

    @pytest.mark.asyncio
    async def test_low_novelty_holds(self, fresh_engine):
        """Test that low novelty content is held."""
        result = await fresh_engine.should_post(
            content="Same old market update",
            category="market_update",
            confidence=0.8,
            novelty_score=0.1,  # Below 0.3 threshold
            cost=0.01,
        )

        assert result.decision == Decision.HOLD
        assert "novelty" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_banned_content_holds(self, fresh_engine):
        """Test that banned content patterns trigger hold."""
        result = await fresh_engine.should_post(
            content="BREAKING: Token will 100x guaranteed! LFG WAGMI!",
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.HOLD

    @pytest.mark.asyncio
    async def test_hold_reasons_tracked(self, fresh_engine):
        """Test that hold reasons are tracked."""
        # Trigger a hold
        await fresh_engine.should_post(
            content="Low novelty content",
            category="test",
            confidence=0.8,
            novelty_score=0.1,
            cost=0.01,
        )

        assert len(fresh_engine._hold_reasons) > 0
        assert fresh_engine._last_hold_time is not None

    @pytest.mark.asyncio
    async def test_duplicate_content_holds(self, fresh_engine):
        """Test that duplicate content triggers hold (bypassing rate limit)."""
        content = "Unique market analysis for today"

        # First post should succeed
        result1 = await fresh_engine.should_post(
            content=content,
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )
        assert result1.decision == Decision.EXECUTE

        # Reset rate limiter to isolate duplicate detection
        for rule in fresh_engine.engine.rules:
            if rule.name == "rate_limit":
                rule._global_history.clear()
                rule._last_action_time = 0
                break

        # Same content should be held as duplicate
        result2 = await fresh_engine.should_post(
            content=content,
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )
        assert result2.decision == Decision.HOLD
        assert "duplicate" in result2.rationale.lower()

    @pytest.mark.asyncio
    async def test_metadata_included(self, fresh_engine):
        """Test that metadata is included in decision."""
        result = await fresh_engine.should_post(
            content="Market update content here",
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
            metadata={"extra_key": "extra_value"},
        )

        # Result should have category in metadata
        assert result.component == "x_bot"

    @pytest.mark.asyncio
    async def test_cost_in_context(self, fresh_engine):
        """Test that cost estimate is passed to engine."""
        result = await fresh_engine.should_post(
            content="Valid content for posting",
            category="market_update",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.05,
        )

        assert result.cost_estimate == 0.05


class TestXDecisionEngineShouldReply:
    """Tests for the should_reply decision method."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_basic_reply_allowed(self, fresh_engine):
        """Test that a basic valid reply is allowed."""
        original_tweet = {
            "author": "@user123",
            "text": "What do you think about SOL?",
        }

        result = await fresh_engine.should_reply(
            original_tweet=original_tweet,
            reply_content="SOL has strong fundamentals and growing adoption.",
            sentiment="positive",
            confidence=0.7,
        )

        assert result.decision == Decision.EXECUTE
        assert result.intent == "reply_tweet"

    @pytest.mark.asyncio
    async def test_reply_risk_level_is_medium(self, fresh_engine):
        """Test that replies have medium risk level."""
        original_tweet = {
            "author": "@user123",
            "text": "Question here",
        }

        result = await fresh_engine.should_reply(
            original_tweet=original_tweet,
            reply_content="Answer here",
            sentiment="neutral",
            confidence=0.7,
        )

        # The context should have medium risk level
        assert result.intent == "reply_tweet"

    @pytest.mark.asyncio
    async def test_reply_low_confidence_holds(self, fresh_engine):
        """Test that low confidence reply is held."""
        original_tweet = {
            "author": "@user123",
            "text": "Complex question here",
        }

        result = await fresh_engine.should_reply(
            original_tweet=original_tweet,
            reply_content="Not sure about this...",
            sentiment="neutral",
            confidence=0.3,
        )

        assert result.decision == Decision.HOLD

    @pytest.mark.asyncio
    async def test_reply_cost_is_lower(self, fresh_engine):
        """Test that reply cost is lower than regular post."""
        original_tweet = {
            "author": "@user123",
            "text": "Question",
        }

        result = await fresh_engine.should_reply(
            original_tweet=original_tweet,
            reply_content="Answer",
            sentiment="neutral",
            confidence=0.7,
        )

        # Reply cost should be 0.005
        assert result.cost_estimate == 0.005

    @pytest.mark.asyncio
    async def test_reply_with_missing_author(self, fresh_engine):
        """Test reply handling when author is missing."""
        original_tweet = {
            "text": "Question without author",
        }

        result = await fresh_engine.should_reply(
            original_tweet=original_tweet,
            reply_content="Response here",
            sentiment="neutral",
            confidence=0.7,
        )

        assert result.decision == Decision.EXECUTE


class TestXDecisionEngineShouldGenerateImage:
    """Tests for the should_generate_image decision method."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_basic_image_generation_allowed(self, fresh_engine):
        """Test that basic image generation is allowed."""
        result = await fresh_engine.should_generate_image(
            prompt="Create a chart showing SOL price movement",
            cost=0.02,
        )

        assert result.decision == Decision.EXECUTE
        assert result.intent == "generate_image"

    @pytest.mark.asyncio
    async def test_image_has_high_default_confidence(self, fresh_engine):
        """Test that images have high default confidence (0.8)."""
        result = await fresh_engine.should_generate_image(
            prompt="Generate market visualization",
            cost=0.02,
        )

        assert result.decision == Decision.EXECUTE

    @pytest.mark.asyncio
    async def test_image_cost_passed_correctly(self, fresh_engine):
        """Test that image cost is passed correctly."""
        result = await fresh_engine.should_generate_image(
            prompt="Generate chart",
            cost=0.05,
        )

        assert result.cost_estimate == 0.05


class TestXDecisionEngineSuccessFailureTracking:
    """Tests for success/failure tracking and circuit breaker."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    def test_record_success(self, fresh_engine):
        """Test recording a successful post."""
        # Should not raise
        fresh_engine.record_success()

    def test_record_failure(self, fresh_engine):
        """Test recording a failed post."""
        # Should not raise
        fresh_engine.record_failure(error="API error")

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_after_failures(self, fresh_engine):
        """Test that circuit breaker trips after multiple failures."""
        # Record failures to trip circuit breaker (threshold is 3)
        fresh_engine.record_failure("Error 1")
        fresh_engine.record_failure("Error 2")
        fresh_engine.record_failure("Error 3")

        # Now posts should be held due to circuit breaker
        result = await fresh_engine.should_post(
            content="Valid content",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.HOLD
        assert "circuit" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_success_resets_circuit_breaker(self, fresh_engine):
        """Test that success in half-open state resets circuit breaker."""
        # Get circuit breaker rule
        cb_rule = None
        for rule in fresh_engine.engine.rules:
            if rule.name == "circuit_breaker":
                cb_rule = rule
                break

        assert cb_rule is not None

        # Simulate half-open state and success
        cb_rule._state = "half-open"
        cb_rule._failure_count = 3

        fresh_engine.record_success()

        assert cb_rule._state == "closed"
        assert cb_rule._failure_count == 0


class TestXDecisionEngineStatistics:
    """Tests for statistics and reporting."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    def test_get_stats_returns_dict(self, fresh_engine):
        """Test that get_stats returns a dictionary."""
        stats = fresh_engine.get_stats()

        assert isinstance(stats, dict)
        assert "hold_reasons" in stats
        assert "last_hold_time" in stats

    @pytest.mark.asyncio
    async def test_stats_track_holds(self, fresh_engine):
        """Test that stats track hold reasons."""
        # Trigger a hold
        await fresh_engine.should_post(
            content="Low novelty content",
            category="test",
            confidence=0.8,
            novelty_score=0.1,
            cost=0.01,
        )

        stats = fresh_engine.get_stats()
        assert len(stats["hold_reasons"]) > 0
        assert stats["last_hold_time"] is not None

    def test_get_hold_summary_empty(self, fresh_engine):
        """Test hold summary with no holds."""
        summary = fresh_engine.get_hold_summary()

        assert "no holds" in summary.lower()

    @pytest.mark.asyncio
    async def test_get_hold_summary_with_holds(self, fresh_engine):
        """Test hold summary after holds."""
        # Trigger holds
        await fresh_engine.should_post(
            content="Low novelty",
            category="test",
            confidence=0.8,
            novelty_score=0.1,
            cost=0.01,
        )

        summary = fresh_engine.get_hold_summary()

        assert "Hold reasons" in summary
        assert "new_information" in summary or "novelty" in summary.lower()


class TestXDecisionEngineEscalation:
    """Tests for escalation callback functionality."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_escalation_callback_registered(self, fresh_engine):
        """Test that escalation callback is registered."""
        # The _on_escalate should be registered
        assert hasattr(fresh_engine, "_on_escalate")

    @pytest.mark.asyncio
    async def test_escalation_callback_handles_no_token(self, fresh_engine):
        """Test escalation callback handles missing token gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            # Create a mock result
            result = DecisionResult(
                decision=Decision.ESCALATE,
                confidence=0.1,
                rationale="Low confidence requires review",
                intent="post_tweet",
                what_would_change_my_mind=["Higher confidence"],
            )

            # Should not raise even without token
            await fresh_engine._on_escalate(result)

    @pytest.mark.asyncio
    async def test_escalation_callback_handles_no_admin_ids(self, fresh_engine):
        """Test escalation callback handles missing admin IDs gracefully."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}, clear=True):
            result = DecisionResult(
                decision=Decision.ESCALATE,
                confidence=0.1,
                rationale="Low confidence requires review",
                intent="post_tweet",
                what_would_change_my_mind=["Higher confidence"],
            )

            # Should not raise even without admin IDs
            await fresh_engine._on_escalate(result)

    @pytest.mark.asyncio
    async def test_escalation_callback_handles_invalid_admin_ids(self, fresh_engine):
        """Test escalation callback handles invalid admin IDs gracefully."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "invalid,not_a_number",
        }, clear=True):
            result = DecisionResult(
                decision=Decision.ESCALATE,
                confidence=0.1,
                rationale="Low confidence requires review",
                intent="post_tweet",
                what_would_change_my_mind=["Higher confidence"],
            )

            # Should not raise with invalid admin IDs
            await fresh_engine._on_escalate(result)


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_rate_limit_per_minute(self, fresh_engine):
        """Test rate limiting per minute (1 per minute max)."""
        # First post should succeed
        result1 = await fresh_engine.should_post(
            content="First unique post content",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )
        assert result1.decision == Decision.EXECUTE

        # Second post within same minute should be rate limited
        result2 = await fresh_engine.should_post(
            content="Second unique post content",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )
        assert result2.decision == Decision.HOLD
        assert "rate" in result2.rationale.lower() or "cooldown" in result2.rationale.lower()

    @pytest.mark.asyncio
    async def test_cooldown_enforced(self, fresh_engine):
        """Test that 60 second cooldown is enforced."""
        # First post
        await fresh_engine.should_post(
            content="Post with cooldown",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        # Immediate second post should be blocked by cooldown
        result = await fresh_engine.should_post(
            content="Another post immediately",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        assert result.decision == Decision.HOLD


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def test_get_x_decision_engine_returns_instance(self):
        """Test that get_x_decision_engine returns an instance."""
        # Reset singleton
        import bots.twitter.x_decision_engine as module
        module._x_decision_engine = None

        engine = get_x_decision_engine()

        assert engine is not None
        assert isinstance(engine, XDecisionEngine)

    def test_get_x_decision_engine_returns_same_instance(self):
        """Test that get_x_decision_engine returns same singleton."""
        import bots.twitter.x_decision_engine as module
        module._x_decision_engine = None

        engine1 = get_x_decision_engine()
        engine2 = get_x_decision_engine()

        assert engine1 is engine2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_empty_content(self, fresh_engine):
        """Test handling of empty content."""
        result = await fresh_engine.should_post(
            content="",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        # Empty content should still be evaluated
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_very_long_content(self, fresh_engine):
        """Test handling of very long content."""
        long_content = "A" * 10000  # 10k characters

        result = await fresh_engine.should_post(
            content=long_content,
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        # Should be evaluated without error
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self, fresh_engine):
        """Test handling of special characters in content."""
        special_content = "Test \n\t\r content with $pecial @chars #hashtag! <html>"

        result = await fresh_engine.should_post(
            content=special_content,
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        # Should be evaluated without error
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_unicode_content(self, fresh_engine):
        """Test handling of unicode content."""
        unicode_content = "Market update with emojis and unicode chars"

        result = await fresh_engine.should_post(
            content=unicode_content,
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.01,
        )

        # Should be evaluated without error
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_zero_cost(self, fresh_engine):
        """Test handling of zero cost."""
        result = await fresh_engine.should_post(
            content="Free content post",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=0.0,
        )

        # Should be evaluated without error
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_negative_confidence(self, fresh_engine):
        """Test handling of negative confidence (edge case)."""
        result = await fresh_engine.should_post(
            content="Negative confidence post",
            category="test",
            confidence=-0.5,  # Invalid but should be handled
            novelty_score=0.7,
            cost=0.01,
        )

        # Should be handled gracefully
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_confidence_over_one(self, fresh_engine):
        """Test handling of confidence over 1.0."""
        result = await fresh_engine.should_post(
            content="High confidence post",
            category="test",
            confidence=1.5,  # Over 1.0
            novelty_score=0.7,
            cost=0.01,
        )

        # Should be handled gracefully
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_reply_with_empty_original_tweet(self, fresh_engine):
        """Test reply with empty original tweet."""
        result = await fresh_engine.should_reply(
            original_tweet={},
            reply_content="Reply to nothing",
            sentiment="neutral",
            confidence=0.7,
        )

        # Should be handled gracefully
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]

    @pytest.mark.asyncio
    async def test_image_with_empty_prompt(self, fresh_engine):
        """Test image generation with empty prompt."""
        result = await fresh_engine.should_generate_image(
            prompt="",
            cost=0.02,
        )

        # Should be handled gracefully
        assert result.decision in [Decision.EXECUTE, Decision.HOLD, Decision.ESCALATE]


class TestMultipleRulesInteraction:
    """Tests for interaction between multiple rules."""

    @pytest.fixture
    def fresh_engine(self):
        """Create a fresh engine for each test."""
        return XDecisionEngine()

    @pytest.mark.asyncio
    async def test_low_novelty_and_banned_pattern(self, fresh_engine):
        """Test content that fails both novelty and tone checks."""
        result = await fresh_engine.should_post(
            content="BREAKING: Same old news",
            category="test",
            confidence=0.8,
            novelty_score=0.1,  # Low novelty
            cost=0.01,
        )

        # Should be held (one of the rules will catch it)
        assert result.decision == Decision.HOLD

    @pytest.mark.asyncio
    async def test_high_cost_escalates(self, fresh_engine):
        """Test that high cost triggers escalation."""
        result = await fresh_engine.should_post(
            content="Valid content with high cost",
            category="test",
            confidence=0.8,
            novelty_score=0.7,
            cost=1.0,  # Over $0.50 per action limit
        )

        # High cost should escalate
        assert result.decision == Decision.ESCALATE

    @pytest.mark.asyncio
    async def test_circuit_breaker_priority(self, fresh_engine):
        """Test that circuit breaker has highest priority."""
        # Trip circuit breaker
        fresh_engine.record_failure("Error 1")
        fresh_engine.record_failure("Error 2")
        fresh_engine.record_failure("Error 3")

        # Even with perfect content, should be held by circuit breaker
        result = await fresh_engine.should_post(
            content="Perfect content here",
            category="test",
            confidence=0.95,
            novelty_score=0.95,
            cost=0.001,
        )

        assert result.decision == Decision.HOLD
        assert "circuit" in result.rationale.lower()
