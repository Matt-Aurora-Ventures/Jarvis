"""
Comprehensive Tests for Dexter Agent Decision Making

Tests the core decision-making logic of the Dexter ReAct agent:
1. Decision types (BUY, SELL, HOLD, UNKNOWN) are correct
2. Confidence thresholds work
3. Cost limits are enforced
4. Reasoning chain is complete
5. Tool selection is appropriate
6. Admin confirmation is required

These tests verify the decision-making system meets trading requirements.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig, DexterModel
from core.dexter.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceThresholds,
    ConfidenceCalibration,
    OutcomeRecord,
    ConfidenceCalibrationStats
)
from core.dexter.cost_tracking import DexterCostTracker, CostEntry, CostStats
from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager
from core.dexter.tools.meta_router import MetaRouter, _extract_symbol


# =============================================================================
# SECTION 1: Decision Types Tests
# =============================================================================

class TestDecisionTypeEnum:
    """Test DecisionType enum is properly defined."""

    def test_decision_type_buy_value(self):
        """Test BUY decision type has correct value."""
        assert DecisionType.BUY.value == "BUY"
        assert DecisionType.BUY == "BUY"

    def test_decision_type_sell_value(self):
        """Test SELL decision type has correct value."""
        assert DecisionType.SELL.value == "SELL"
        assert DecisionType.SELL == "SELL"

    def test_decision_type_hold_value(self):
        """Test HOLD decision type has correct value."""
        assert DecisionType.HOLD.value == "HOLD"
        assert DecisionType.HOLD == "HOLD"

    def test_decision_type_unknown_value(self):
        """Test UNKNOWN decision type has correct value."""
        assert DecisionType.UNKNOWN.value == "UNKNOWN"
        assert DecisionType.UNKNOWN == "UNKNOWN"

    def test_decision_type_is_string_enum(self):
        """Test DecisionType inherits from str and Enum."""
        # DecisionType inherits from str, Enum
        # The .value gives the string value
        assert DecisionType.BUY.value == "BUY"
        # Equality comparison works with strings
        assert DecisionType.BUY == "BUY"
        assert DecisionType.SELL == "SELL"

    def test_all_decision_types_exist(self):
        """Test all expected decision types are defined."""
        expected_types = {"BUY", "SELL", "HOLD", "UNKNOWN"}
        actual_types = {dt.value for dt in DecisionType}
        assert expected_types == actual_types


class TestReActDecisionClass:
    """Test ReActDecision data structure."""

    def test_react_decision_buy(self):
        """Test ReActDecision for BUY action."""
        decision = ReActDecision(
            action="BUY",
            symbol="SOL",
            confidence=85.0,
            rationale="Strong bullish momentum with high volume"
        )
        assert decision.action == "BUY"
        assert decision.symbol == "SOL"
        assert decision.confidence == 85.0
        assert "bullish" in decision.rationale.lower()

    def test_react_decision_sell(self):
        """Test ReActDecision for SELL action."""
        decision = ReActDecision(
            action="SELL",
            symbol="BTC",
            confidence=78.0,
            rationale="Bearish divergence on RSI"
        )
        assert decision.action == "SELL"
        assert decision.symbol == "BTC"
        assert decision.confidence == 78.0
        assert "bearish" in decision.rationale.lower()

    def test_react_decision_hold(self):
        """Test ReActDecision for HOLD action."""
        decision = ReActDecision(
            action="HOLD",
            symbol="ETH",
            confidence=55.0,
            rationale="Uncertain market conditions"
        )
        assert decision.action == "HOLD"
        assert decision.symbol == "ETH"
        assert decision.confidence == 55.0

    def test_react_decision_tracks_iterations(self):
        """Test ReActDecision tracks iteration count."""
        decision = ReActDecision(
            action="BUY",
            symbol="SOL",
            confidence=80.0,
            rationale="Analysis complete",
            iterations=7
        )
        assert decision.iterations == 7

    def test_react_decision_default_iterations(self):
        """Test ReActDecision defaults to 0 iterations."""
        decision = ReActDecision(
            action="HOLD",
            symbol="SOL",
            confidence=50.0,
            rationale="No action"
        )
        assert decision.iterations == 0

    def test_react_decision_to_dict(self):
        """Test ReActDecision serializes to dictionary."""
        decision = ReActDecision(
            action="BUY",
            symbol="SOL",
            confidence=85.0,
            rationale="Strong signal",
            iterations=5
        )
        d = decision.to_dict()

        assert isinstance(d, dict)
        assert d["action"] == "BUY"
        assert d["symbol"] == "SOL"
        assert d["confidence"] == 85.0
        assert d["rationale"] == "Strong signal"
        assert d["iterations"] == 5


class TestDecisionMakingIntegration:
    """Test decision making produces correct decision types."""

    @pytest.mark.asyncio
    async def test_agent_returns_valid_decision_type(self):
        """Test agent analyze_token returns valid action."""
        agent = DexterAgent()
        result = await agent.analyze_token("SOL")

        valid_actions = {"BUY", "SELL", "HOLD", "UNKNOWN", "ERROR"}
        assert result["action"] in valid_actions

    @pytest.mark.asyncio
    async def test_agent_decision_matches_symbol(self):
        """Test agent decision matches input symbol."""
        agent = DexterAgent()
        result = await agent.analyze_token("BTC")

        assert result["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_agent_decision_has_rationale(self):
        """Test agent decision includes rationale."""
        agent = DexterAgent()
        result = await agent.analyze_token("ETH")

        assert "rationale" in result
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 0


# =============================================================================
# SECTION 2: Confidence Thresholds Tests
# =============================================================================

class TestConfidenceThresholdsBasic:
    """Test confidence threshold configuration."""

    def test_default_buy_threshold(self):
        """Test default BUY threshold is 70%."""
        thresholds = ConfidenceThresholds()
        assert thresholds.buy_threshold == 70.0

    def test_default_sell_threshold(self):
        """Test default SELL threshold is 70%."""
        thresholds = ConfidenceThresholds()
        assert thresholds.sell_threshold == 70.0

    def test_default_high_confidence_buy(self):
        """Test high confidence BUY threshold is 85%."""
        thresholds = ConfidenceThresholds()
        assert thresholds.buy_high_confidence == 85.0

    def test_default_high_confidence_sell(self):
        """Test high confidence SELL threshold is 85%."""
        thresholds = ConfidenceThresholds()
        assert thresholds.sell_high_confidence == 85.0

    def test_default_absolute_minimum(self):
        """Test absolute minimum threshold is 60%."""
        thresholds = ConfidenceThresholds()
        assert thresholds.absolute_minimum == 60.0

    def test_custom_thresholds(self):
        """Test custom thresholds are applied."""
        thresholds = ConfidenceThresholds(
            buy_threshold=75.0,
            sell_threshold=80.0,
            buy_high_confidence=90.0,
            sell_high_confidence=92.0,
            absolute_minimum=65.0
        )

        assert thresholds.buy_threshold == 75.0
        assert thresholds.sell_threshold == 80.0
        assert thresholds.buy_high_confidence == 90.0
        assert thresholds.sell_high_confidence == 92.0
        assert thresholds.absolute_minimum == 65.0


class TestConfidenceThresholdsEnforcement:
    """Test confidence thresholds are properly enforced."""

    def test_buy_above_threshold_allowed(self):
        """Test BUY is allowed when confidence exceeds threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 75% confidence > 70% threshold
            result = scorer.should_take_action(75.0, "BUY")
            assert result is True

    def test_buy_at_threshold_allowed(self):
        """Test BUY is allowed at exact threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 70% confidence = 70% threshold
            result = scorer.should_take_action(70.0, "BUY")
            assert result is True

    def test_buy_below_threshold_rejected(self):
        """Test BUY is rejected below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 65% confidence < 70% threshold but > 60% absolute minimum
            result = scorer.should_take_action(65.0, "BUY")
            assert result is False

    def test_sell_above_threshold_allowed(self):
        """Test SELL is allowed when confidence exceeds threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            result = scorer.should_take_action(75.0, "SELL")
            assert result is True

    def test_sell_below_threshold_rejected(self):
        """Test SELL is rejected below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            result = scorer.should_take_action(65.0, "SELL")
            assert result is False

    def test_hold_always_allowed(self):
        """Test HOLD is always allowed regardless of confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # HOLD should be allowed at any confidence level
            assert scorer.should_take_action(0.0, "HOLD") is True
            assert scorer.should_take_action(30.0, "HOLD") is True
            assert scorer.should_take_action(50.0, "HOLD") is True
            assert scorer.should_take_action(70.0, "HOLD") is True
            assert scorer.should_take_action(100.0, "HOLD") is True

    def test_absolute_minimum_blocks_all_trades(self):
        """Test absolute minimum blocks trades below it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 55% is below 60% absolute minimum
            assert scorer.should_take_action(55.0, "BUY") is False
            assert scorer.should_take_action(55.0, "SELL") is False

    def test_high_confidence_detection_buy(self):
        """Test high confidence detection for BUY."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 90% > 85% high confidence threshold
            assert scorer.is_high_confidence(90.0, "BUY") is True

            # 80% < 85% high confidence threshold
            assert scorer.is_high_confidence(80.0, "BUY") is False

    def test_high_confidence_detection_sell(self):
        """Test high confidence detection for SELL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 90% > 85% high confidence threshold
            assert scorer.is_high_confidence(90.0, "SELL") is True

            # 80% < 85% high confidence threshold
            assert scorer.is_high_confidence(80.0, "SELL") is False


class TestConfidenceCalibration:
    """Test confidence calibration and scoring."""

    def test_confidence_capped_at_95(self):
        """Test confidence is capped at 95% (never 100% certain)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            calibrated, _ = scorer.score_confidence(
                raw_confidence=100.0,
                decision="BUY",
                symbol="SOL",
                iterations=10
            )

            assert calibrated <= 95.0

    def test_confidence_floored_at_0(self):
        """Test confidence is floored at 0%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            calibrated, _ = scorer.score_confidence(
                raw_confidence=-20.0,
                decision="BUY",
                symbol="SOL"
            )

            assert calibrated >= 0.0

    def test_rushed_analysis_penalty(self):
        """Test rushed analysis (low iterations) receives penalty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Low iterations (rushed)
            rushed, rushed_note = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL",
                iterations=1
            )

            # High iterations (thorough)
            thorough, thorough_note = scorer.score_confidence(
                raw_confidence=80.0,
                decision="BUY",
                symbol="SOL",
                iterations=10
            )

            # Rushed should be lower
            assert rushed < thorough
            # Note should mention rush penalty
            assert "rushed" in rushed_note.lower()

    def test_temporal_decay_fresh(self):
        """Test no decay for fresh analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            decayed = scorer.apply_temporal_decay(80.0, 0.1)  # 6 minutes
            assert decayed == 80.0

    def test_temporal_decay_stale(self):
        """Test decay for stale analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # 2 hours old
            decayed = scorer.apply_temporal_decay(80.0, 2.0)
            assert decayed < 80.0

            # 24 hours old - should have significant decay
            very_stale = scorer.apply_temporal_decay(80.0, 24.0)
            assert very_stale < 60.0


class TestConfidenceCalibrationStatus:
    """Test calibration status detection."""

    def test_calibration_status_enum_values(self):
        """Test ConfidenceCalibration enum values."""
        assert ConfidenceCalibration.OVERCAUTIOUS.value == "overcautious"
        assert ConfidenceCalibration.WELL_CALIBRATED.value == "well_calibrated"
        assert ConfidenceCalibration.OVERCONFIDENT.value == "overconfident"

    def test_well_calibrated_detection(self):
        """Test well-calibrated status is detected correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # Create well-calibrated data
            for i in range(10):
                scorer.record_decision(
                    decision_id=f"test{i}",
                    symbol="SOL",
                    decision="BUY",
                    confidence=72.0
                )
                scorer.update_outcome(
                    decision_id=f"test{i}",
                    actual_accuracy_1h=(i < 7)  # 70% accuracy
                )

            stats = scorer.get_calibration_stats()
            # |72 - 70| = 2 < 5, so well-calibrated
            assert stats.calibration_status_1h == ConfidenceCalibration.WELL_CALIBRATED.value


# =============================================================================
# SECTION 3: Cost Limits Tests
# =============================================================================

class TestCostLimitsConfiguration:
    """Test cost limit configuration."""

    def test_default_max_cost_per_decision(self):
        """Test default max cost per decision is $0.50."""
        config = DexterConfig()
        assert config.max_cost_per_decision == 0.50

    def test_custom_max_cost_per_decision(self):
        """Test custom max cost per decision."""
        config = DexterConfig(max_cost_per_decision=0.25)
        assert config.max_cost_per_decision == 0.25

    def test_cost_tracker_default_budget(self):
        """Test cost tracker default budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir)
            assert tracker.budget_per_decision == 0.20


class TestCostTracking:
    """Test cost tracking functionality."""

    def test_record_cost_calculates_correctly(self):
        """Test cost calculation from tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir)

            entry = tracker.record_cost(
                symbol="SOL",
                decision="BUY",
                input_tokens=1000,
                output_tokens=500,
                iterations=5,
                model="grok-3"
            )

            # Verify cost is calculated
            assert entry.cost_usd >= 0.0
            assert entry.input_tokens == 1000
            assert entry.output_tokens == 500
            assert entry.symbol == "SOL"
            assert entry.decision == "BUY"

    def test_cost_budget_tracking(self):
        """Test budget tracking for costs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir, budget_per_decision=0.10)

            # Record cost under budget
            entry1 = tracker.record_cost(
                symbol="SOL",
                decision="BUY",
                input_tokens=500,
                output_tokens=200
            )

            # Check budget status
            status = tracker.check_budget()
            assert "status" in status
            assert "avg_cost" in status
            assert "budget" in status

    def test_cost_persists_to_file(self):
        """Test cost entries are persisted to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir)

            tracker.record_cost(
                symbol="SOL",
                decision="BUY",
                input_tokens=1000,
                output_tokens=500
            )

            # Check file exists
            costs_file = Path(tmpdir) / "costs.jsonl"
            assert costs_file.exists()

            with open(costs_file) as f:
                lines = f.readlines()
                assert len(lines) == 1

    def test_cost_stats_calculation(self):
        """Test cost statistics calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir)

            # Record multiple entries
            for i in range(5):
                tracker.record_cost(
                    symbol="SOL",
                    decision="BUY",
                    input_tokens=1000 + i * 100,
                    output_tokens=500
                )

            stats = tracker.get_stats()

            assert stats.total_decisions == 5
            assert stats.total_cost_usd > 0
            assert stats.avg_cost_per_decision > 0

    def test_agent_tracks_cost(self):
        """Test agent tracks cost in result."""
        agent = DexterAgent()

        @pytest.mark.asyncio
        async def run():
            result = await agent.analyze_token("SOL")
            assert "cost" in result
            assert isinstance(result["cost"], (int, float))

        import asyncio
        asyncio.run(run())


class TestCostLimitsEnforcement:
    """Test cost limits are enforced."""

    def test_over_budget_alert(self):
        """Test alert is generated when over budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir, budget_per_decision=0.001)

            # Record cost that exceeds budget
            tracker.record_cost(
                symbol="SOL",
                decision="BUY",
                input_tokens=10000,
                output_tokens=5000
            )

            status = tracker.check_budget()

            # Should have alerts for over-budget
            assert len(status.get("alerts", [])) > 0 or status["status"] == "OVER_BUDGET"

    def test_cost_percentile_calculation(self):
        """Test cost percentile calculation (P50, P95, P99)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DexterCostTracker(data_dir=tmpdir)

            # Record varied costs
            for i in range(10):
                tracker.record_cost(
                    symbol="SOL",
                    decision="BUY",
                    input_tokens=500 + i * 500,
                    output_tokens=200 + i * 100
                )

            stats = tracker.get_stats()

            assert stats.p50_cost >= 0
            assert stats.p95_cost >= stats.p50_cost
            assert stats.p99_cost >= stats.p95_cost
            assert stats.max_cost >= stats.p99_cost


# =============================================================================
# SECTION 4: Reasoning Chain Tests
# =============================================================================

class TestReasoningChainLogging:
    """Test reasoning chain is properly logged."""

    def test_scratchpad_logs_start(self):
        """Test scratchpad logs session start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Analyze SOL for trading", symbol="SOL")

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "start"
            assert entries[0]["goal"] == "Analyze SOL for trading"
            assert entries[0]["symbol"] == "SOL"

    def test_scratchpad_logs_reasoning(self):
        """Test scratchpad logs reasoning steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_reasoning("Checking market sentiment", iteration=1)
            sp.log_reasoning("Analyzing technical indicators", iteration=2)
            sp.log_reasoning("Evaluating risk/reward", iteration=3)

            entries = sp.get_entries()
            assert len(entries) == 3

            for i, entry in enumerate(entries, 1):
                assert entry["type"] == "reasoning"
                assert entry["iteration"] == i

    def test_scratchpad_logs_actions(self):
        """Test scratchpad logs tool actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_action(
                "market_data",
                {"symbol": "SOL", "timeframe": "1h"},
                "Price: $148, Volume: $2.5B"
            )

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "action"
            assert entries[0]["tool"] == "market_data"
            assert entries[0]["args"]["symbol"] == "SOL"

    def test_scratchpad_logs_decision(self):
        """Test scratchpad logs final decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_decision(
                action="BUY",
                symbol="SOL",
                rationale="Strong bullish momentum with high volume",
                confidence=85.0
            )

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "decision"
            assert entries[0]["action"] == "BUY"
            assert entries[0]["symbol"] == "SOL"
            assert entries[0]["confidence"] == 85.0

    def test_scratchpad_logs_errors(self):
        """Test scratchpad logs errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_error("API connection timeout", iteration=2)

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "error"
            assert entries[0]["error"] == "API connection timeout"
            assert entries[0]["iteration"] == 2


class TestReasoningChainCompleteness:
    """Test reasoning chain is complete."""

    def test_complete_reasoning_chain(self):
        """Test a complete reasoning chain has all components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            # Log complete chain
            sp.log_start("Analyze SOL opportunity", symbol="SOL")
            sp.log_reasoning("Step 1: Check market conditions", iteration=1)
            sp.log_action("market_data", {"symbol": "SOL"}, "Price: $148")
            sp.log_reasoning("Step 2: Evaluate sentiment", iteration=2)
            sp.log_action("sentiment", {"symbol": "SOL"}, "Bullish 75/100")
            sp.log_reasoning("Step 3: Make decision", iteration=3)
            sp.log_decision("BUY", "SOL", "Strong signal", 85.0)

            entries = sp.get_entries()
            types = [e["type"] for e in entries]

            # Verify all required components
            assert "start" in types
            assert "reasoning" in types
            assert "action" in types
            assert "decision" in types

            # Verify order (start first, decision last)
            assert types[0] == "start"
            assert types[-1] == "decision"

    def test_reasoning_chain_summary(self):
        """Test reasoning chain produces readable summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Analyze SOL", symbol="SOL")
            sp.log_reasoning("Checking data", iteration=1)
            sp.log_decision("BUY", "SOL", "Strong signal", 80.0)

            summary = sp.get_summary()

            # Summary should contain key information
            assert "SOL" in summary
            assert "BUY" in summary
            assert "80" in summary

    def test_reasoning_chain_persists(self):
        """Test reasoning chain persists to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_start("Analyze SOL", symbol="SOL")
            sp.log_decision("BUY", "SOL", "Test", 80.0)

            # Check file exists
            filepath = Path(tmpdir) / "test-session.jsonl"
            assert filepath.exists()

            # Check file contains entries
            with open(filepath) as f:
                lines = f.readlines()
                assert len(lines) == 2


class TestReasoningChainWithContext:
    """Test reasoning chain with context management."""

    def test_context_manager_stores_data(self):
        """Test context manager stores analysis data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            data = {
                "symbol": "SOL",
                "price": 148.50,
                "volume": 2500000000
            }
            ctx.save_full_data(data, "market_data")

            # Verify data is saved
            session_dir = Path(tmpdir) / "test-session"
            files = list(session_dir.glob("market_data_*.json"))
            assert len(files) >= 1

    def test_context_manager_adds_summaries(self):
        """Test context manager adds analysis summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            ctx.add_summary("SOL price: $148.50, Volume: $2.5B")
            ctx.add_summary("Sentiment: Bullish 75/100")

            summary = ctx.get_summary()
            assert "SOL" in summary

    def test_context_token_estimation(self):
        """Test context token estimation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            initial = ctx.get_token_estimate()
            ctx.add_summary("This is a test summary with several words")
            after = ctx.get_token_estimate()

            assert after > initial


# =============================================================================
# SECTION 5: Tool Selection Tests
# =============================================================================

class TestToolSelectionRouting:
    """Test MetaRouter selects appropriate tools."""

    @pytest.mark.asyncio
    async def test_liquidation_routing(self):
        """Test liquidation queries route correctly."""
        router = MetaRouter()

        queries = [
            "Check liquidation levels",
            "Where is support?",
            "Resistance zones"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert any(word in result.lower() for word in [
                "liquidation", "wall", "support", "$"
            ])

    @pytest.mark.asyncio
    async def test_sentiment_routing(self):
        """Test sentiment queries route correctly."""
        router = MetaRouter()

        queries = [
            "What's the sentiment?",
            "Social media buzz",
            "Twitter analysis"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert any(word in result.lower() for word in [
                "sentiment", "bullish", "score", "positive"
            ])

    @pytest.mark.asyncio
    async def test_technical_routing(self):
        """Test technical queries route correctly."""
        router = MetaRouter()

        queries = [
            "Check MA crossover",
            "RSI analysis",
            "Technical indicators"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert any(word in result.lower() for word in [
                "cross", "ma", "bullish", "bearish", "day"
            ])

    @pytest.mark.asyncio
    async def test_position_routing(self):
        """Test position queries route correctly."""
        router = MetaRouter()

        queries = [
            "Check my positions",
            "Portfolio risk",
            "Exposure analysis"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert any(word in result.lower() for word in [
                "position", "risk", "capital", "open"
            ])


class TestSymbolExtraction:
    """Test symbol extraction from queries."""

    def test_extract_known_symbols(self):
        """Test extraction of known crypto symbols."""
        test_cases = [
            ("Is SOL bullish?", "SOL"),
            ("BTC analysis please", "BTC"),
            ("Check ETH price", "ETH"),
            ("BONK is trending", "BONK"),
        ]

        for query, expected in test_cases:
            result = _extract_symbol(query)
            assert result == expected

    def test_extract_case_insensitive(self):
        """Test extraction is case insensitive."""
        result = _extract_symbol("check sol price")
        assert result == "SOL"

    def test_extract_returns_none_for_empty(self):
        """Test extraction returns None for empty query."""
        result = _extract_symbol("")
        assert result is None


class TestToolSelectionComprehensive:
    """Test comprehensive tool selection scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_tools_sequence(self):
        """Test using multiple tools in sequence."""
        router = MetaRouter()

        # Run a sequence of different query types
        liquidation = await router.financial_research("liquidation levels")
        sentiment = await router.financial_research("sentiment score")
        technical = await router.financial_research("MA analysis")
        position = await router.financial_research("check positions")

        # Each should return different results
        results = {liquidation, sentiment, technical, position}
        assert len(results) >= 3  # At least 3 unique results

    @pytest.mark.asyncio
    async def test_default_routing_fallback(self):
        """Test default routing for unrecognized queries."""
        router = MetaRouter()

        result = await router.financial_research("random query about something")

        # Should return some market data
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_router_handles_edge_cases(self):
        """Test router handles edge cases gracefully."""
        router = MetaRouter()

        # Empty query
        result1 = await router.financial_research("")
        assert isinstance(result1, str)

        # Whitespace only
        result2 = await router.financial_research("   ")
        assert isinstance(result2, str)

        # Special characters
        result3 = await router.financial_research("@#$%^&*()")
        assert isinstance(result3, str)


# =============================================================================
# SECTION 6: Admin Confirmation Tests
# =============================================================================

class TestAdminConfirmationConfig:
    """Test admin confirmation configuration."""

    def test_require_confirmation_default_true(self):
        """Test require_confirmation defaults to True."""
        config = DexterConfig()
        assert config.require_confirmation is True

    def test_require_confirmation_can_be_disabled(self):
        """Test require_confirmation can be disabled."""
        config = DexterConfig(require_confirmation=False)
        assert config.require_confirmation is False

    def test_config_serialization_includes_confirmation(self):
        """Test config serialization includes require_confirmation."""
        config = DexterConfig(require_confirmation=True)

        # Note: DexterConfig from config.py is a dataclass
        # so we convert it to dict using asdict
        d = asdict(config)
        assert "require_confirmation" in d
        assert d["require_confirmation"] is True


class TestAdminConfirmationBehavior:
    """Test admin confirmation behavior."""

    def test_config_require_confirmation_is_accessible(self):
        """Test require_confirmation is accessible on config."""
        config = DexterConfig()
        assert hasattr(config, "require_confirmation")
        assert isinstance(config.require_confirmation, bool)

    def test_agent_respects_config(self):
        """Test agent uses config values."""
        custom_config = {
            "max_iterations": 10,
            "min_confidence": 75.0
        }
        agent = DexterAgent(config=custom_config)

        assert agent.max_iterations == 10
        assert agent.min_confidence == 75.0


class TestDecisionOutputForConfirmation:
    """Test decision output provides info needed for confirmation."""

    @pytest.mark.asyncio
    async def test_decision_has_required_fields_for_confirmation(self):
        """Test decision output has all fields needed for admin review."""
        agent = DexterAgent()
        result = await agent.analyze_token("SOL")

        # Fields needed for admin confirmation
        required_fields = ["action", "symbol", "confidence", "rationale", "cost"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_react_decision_has_confirmation_info(self):
        """Test ReActDecision has all info for confirmation display."""
        decision = ReActDecision(
            action="BUY",
            symbol="SOL",
            confidence=85.0,
            rationale="Strong bullish signal with volume confirmation",
            iterations=7
        )

        d = decision.to_dict()

        # All fields needed for confirmation dialog
        assert d["action"] in {"BUY", "SELL", "HOLD", "UNKNOWN"}
        assert len(d["symbol"]) > 0
        assert 0 <= d["confidence"] <= 100
        assert len(d["rationale"]) > 0
        assert d["iterations"] >= 0


# =============================================================================
# SECTION 7: Integration Tests
# =============================================================================

class TestDecisionMakingIntegrationFlow:
    """Integration tests for complete decision-making flow."""

    @pytest.mark.asyncio
    async def test_full_decision_flow(self):
        """Test complete decision flow from input to output."""
        agent = DexterAgent()

        result = await agent.analyze_token("SOL")

        # Verify complete result structure
        assert result["symbol"] == "SOL"
        assert result["action"] in {"BUY", "SELL", "HOLD", "UNKNOWN", "ERROR"}
        assert isinstance(result["confidence"], (int, float))
        assert isinstance(result["rationale"], str)
        assert isinstance(result["cost"], (int, float))

    @pytest.mark.asyncio
    async def test_multiple_tokens_independent(self):
        """Test analyzing multiple tokens maintains independence."""
        agent = DexterAgent()

        results = {}
        for token in ["SOL", "BTC", "ETH"]:
            result = await agent.analyze_token(token)
            results[token] = result
            assert result["symbol"] == token

    @pytest.mark.asyncio
    async def test_decision_with_scratchpad_logging(self):
        """Test decision flow with complete scratchpad logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = DexterAgent()
            sp = Scratchpad(agent.session_id, scratchpad_dir=Path(tmpdir))

            # Log start
            sp.log_start("Analyze SOL", symbol="SOL")

            # Run analysis
            result = await agent.analyze_token("SOL")

            # Log decision
            sp.log_decision(
                result["action"],
                result["symbol"],
                result["rationale"],
                result["confidence"]
            )

            # Verify logging
            entries = sp.get_entries()
            assert len(entries) >= 2

            types = [e["type"] for e in entries]
            assert "start" in types
            assert "decision" in types


class TestDecisionConsistency:
    """Test decision-making consistency."""

    @pytest.mark.asyncio
    async def test_same_input_consistent_structure(self):
        """Test same input produces consistent output structure."""
        agent = DexterAgent()

        results = []
        for _ in range(3):
            result = await agent.analyze_token("SOL")
            results.append(result)

        # All results should have same keys
        keys = set(results[0].keys())
        for r in results[1:]:
            assert set(r.keys()) == keys

    def test_confidence_scorer_consistent(self):
        """Test confidence scorer produces consistent results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            results = []
            for _ in range(3):
                calibrated, note = scorer.score_confidence(
                    raw_confidence=80.0,
                    decision="BUY",
                    symbol="SOL",
                    iterations=5
                )
                results.append(calibrated)

            # All results should be identical
            assert all(r == results[0] for r in results)


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_symbol(self):
        """Test handling empty symbol."""
        agent = DexterAgent()
        result = await agent.analyze_token("")

        assert result is not None
        assert "action" in result

    @pytest.mark.asyncio
    async def test_special_character_symbol(self):
        """Test handling symbol with special characters."""
        agent = DexterAgent()
        result = await agent.analyze_token("$SOL")

        assert result is not None

    def test_confidence_at_boundaries(self):
        """Test confidence at boundary values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorer = ConfidenceScorer(data_dir=tmpdir)

            # At threshold
            assert scorer.should_take_action(70.0, "BUY") is True

            # Just below threshold
            assert scorer.should_take_action(69.9, "BUY") is False

            # At absolute minimum
            assert scorer.should_take_action(60.0, "BUY") is False

            # Just below absolute minimum
            assert scorer.should_take_action(59.9, "BUY") is False

    def test_max_iterations_config(self):
        """Test max iterations configuration."""
        agent = DexterAgent({"max_iterations": 1})
        assert agent.max_iterations == 1

        agent2 = DexterAgent({"max_iterations": 100})
        assert agent2.max_iterations == 100


# =============================================================================
# SECTION 8: Concurrent Operations Tests
# =============================================================================

class TestConcurrentOperations:
    """Test concurrent decision operations."""

    @pytest.mark.asyncio
    async def test_concurrent_token_analysis(self):
        """Test concurrent token analyses."""
        import asyncio

        async def analyze(symbol):
            agent = DexterAgent()
            return await agent.analyze_token(symbol)

        results = await asyncio.gather(
            analyze("SOL"),
            analyze("BTC"),
            analyze("ETH")
        )

        assert len(results) == 3
        for result in results:
            assert result is not None
            assert "action" in result

    @pytest.mark.asyncio
    async def test_concurrent_meta_router(self):
        """Test concurrent MetaRouter queries."""
        import asyncio

        router = MetaRouter()

        queries = [
            "liquidation levels",
            "sentiment analysis",
            "technical indicators",
            "position status"
        ]

        tasks = [router.financial_research(q) for q in queries]
        results = await asyncio.gather(*tasks)

        assert len(results) == 4
        for result in results:
            assert isinstance(result, str)
            assert len(result) > 0


# Run tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
