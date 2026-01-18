"""
Unit Tests for Dexter ReAct Agent

Tests the core ReAct loop logic, tool invocation, context compaction,
exit conditions, cost tracking, and max iteration enforcement.

Uses mocked Grok responses for deterministic testing.
"""

import unittest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig, DexterModel
from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager


class TestReActLoopIteration(unittest.TestCase):
    """Test ReAct loop iteration logic."""

    def setUp(self):
        """Set up mock clients for testing."""
        self.mock_grok = AsyncMock()
        self.mock_sentiment_agg = MagicMock()
        self.agent = DexterAgent(
            grok_client=self.mock_grok,
            sentiment_aggregator=self.mock_sentiment_agg
        )

    def test_agent_initialization(self):
        """Test agent initializes with correct defaults."""
        agent = DexterAgent()
        self.assertEqual(agent.iteration_count, 0)
        self.assertEqual(agent.total_cost, 0.0)
        self.assertEqual(agent.scratchpad, [])

    def test_max_iterations_constant(self):
        """Test MAX_ITERATIONS is enforced."""
        self.assertEqual(DexterAgent.MAX_ITERATIONS, 15)

    def test_max_cost_constant(self):
        """Test MAX_COST_USD is enforced."""
        self.assertEqual(DexterAgent.MAX_COST_USD, 0.50)

    def test_min_confidence_constant(self):
        """Test MIN_CONFIDENCE threshold."""
        self.assertEqual(DexterAgent.MIN_CONFIDENCE, 70.0)

    def test_iteration_count_increments(self):
        """Test that iteration count increments during analysis."""
        async def run_test():
            # Mock Grok to return bullish sentiment
            self.mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 75\nCONFIDENCE: 80\nRECOMMENDATION: BUY"
            )
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=72.0)

            result = await self.agent.analyze_trading_opportunity("SOL")

            # Should have completed at least one iteration
            self.assertGreater(self.agent.iteration_count, 0)
            self.assertGreater(result.iterations, 0)

        asyncio.run(run_test())


class TestToolInvocation(unittest.TestCase):
    """Test tool invocation and result handling."""

    def setUp(self):
        """Set up mock clients."""
        self.mock_grok = AsyncMock()
        self.mock_sentiment_agg = MagicMock()
        self.agent = DexterAgent(
            grok_client=self.mock_grok,
            sentiment_aggregator=self.mock_sentiment_agg
        )

    def test_tools_used_tracking(self):
        """Test that tools used are tracked in the decision."""
        async def run_test():
            self.mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 80\nCONFIDENCE: 85\nRECOMMENDATION: BUY"
            )
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=75.0)

            result = await self.agent.analyze_trading_opportunity("SOL")

            # Should track tools used
            self.assertIsInstance(result.tools_used, list)

        asyncio.run(run_test())

    def test_scratchpad_logs_actions(self):
        """Test that scratchpad logs all actions."""
        async def run_test():
            self.mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 70\nCONFIDENCE: 75\nRECOMMENDATION: BUY"
            )
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=68.0)

            await self.agent.analyze_trading_opportunity("SOL")

            # Scratchpad should have entries
            self.assertGreater(len(self.agent.scratchpad), 0)

            # Check scratchpad structure
            for entry in self.agent.scratchpad:
                self.assertIn("type", entry)
                self.assertIn("timestamp", entry)

        asyncio.run(run_test())

    def test_log_reasoning_adds_entry(self):
        """Test _log_reasoning adds correct entry."""
        self.agent._log_reasoning("Test thought")

        self.assertEqual(len(self.agent.scratchpad), 1)
        self.assertEqual(self.agent.scratchpad[0]["type"], "reasoning")
        self.assertEqual(self.agent.scratchpad[0]["thought"], "Test thought")

    def test_log_action_adds_entry(self):
        """Test _log_action adds correct entry."""
        self.agent._log_action("test_tool", {"arg": "value"}, "result")

        self.assertEqual(len(self.agent.scratchpad), 1)
        self.assertEqual(self.agent.scratchpad[0]["type"], "action")
        self.assertEqual(self.agent.scratchpad[0]["tool"], "test_tool")
        self.assertEqual(self.agent.scratchpad[0]["args"], {"arg": "value"})
        self.assertEqual(self.agent.scratchpad[0]["result"], "result")


class TestContextCompaction(unittest.TestCase):
    """Test context compaction to prevent token overflow."""

    def test_context_manager_initialization(self):
        """Test ContextManager initializes correctly."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", session_dir=tmpdir)
            self.assertEqual(ctx.session_id, "test-session")
            self.assertEqual(ctx.context_max_tokens, 100000)

    def test_check_context_overflow_empty(self):
        """Test overflow check with empty context."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", session_dir=tmpdir)
            self.assertFalse(ctx.check_context_overflow())

    def test_add_summary(self):
        """Test adding summary to context."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", session_dir=tmpdir)
            ctx.add_summary("Test summary 1")
            ctx.add_summary("Test summary 2")

            self.assertEqual(len(ctx.summaries), 2)

    def test_compact_context_removes_old(self):
        """Test context compaction removes old summaries."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", session_dir=tmpdir, context_max_tokens=1)

            # Add many summaries to trigger compaction
            for i in range(10):
                ctx.add_summary(f"Summary {i} " * 100)

            ctx.compact_context()

            # Should have reduced summaries
            self.assertLess(len(ctx.summaries), 10)

    def test_get_summary_format(self):
        """Test get_summary returns formatted string."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", session_dir=tmpdir)
            ctx.add_summary("Test summary")

            summary = ctx.get_summary()
            self.assertIn("Context Summary", summary)
            self.assertIn("Test summary", summary)


class TestExitConditions(unittest.TestCase):
    """Test exit conditions: TRADE, HOLD, ERROR."""

    def setUp(self):
        """Set up mock clients."""
        self.mock_grok = AsyncMock()
        self.mock_sentiment_agg = MagicMock()

    def test_decision_type_enum(self):
        """Test DecisionType enum values."""
        self.assertEqual(DecisionType.TRADE_BUY.value, "TRADE_BUY")
        self.assertEqual(DecisionType.TRADE_SELL.value, "TRADE_SELL")
        self.assertEqual(DecisionType.HOLD.value, "HOLD")
        self.assertEqual(DecisionType.ERROR.value, "ERROR")

    def test_buy_decision_on_high_confidence(self):
        """Test BUY decision when confidence is high."""
        async def run_test():
            self.mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 85\nCONFIDENCE: 90\nRECOMMENDATION: BUY strong signal"
            )
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=80.0)

            agent = DexterAgent(
                grok_client=self.mock_grok,
                sentiment_aggregator=self.mock_sentiment_agg
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # High confidence + BUY recommendation = TRADE_BUY
            if result.confidence >= agent.MIN_CONFIDENCE:
                self.assertEqual(result.decision, DecisionType.TRADE_BUY)

        asyncio.run(run_test())

    def test_hold_decision_on_low_confidence(self):
        """Test HOLD decision when confidence is low."""
        async def run_test():
            self.mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 55\nCONFIDENCE: 50\nRECOMMENDATION: HOLD uncertain"
            )
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=52.0)

            agent = DexterAgent(
                grok_client=self.mock_grok,
                sentiment_aggregator=self.mock_sentiment_agg
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # Low confidence = HOLD
            self.assertEqual(result.decision, DecisionType.HOLD)

        asyncio.run(run_test())

    def test_error_decision_on_exception(self):
        """Test ERROR decision when exception occurs."""
        async def run_test():
            self.mock_grok.analyze_sentiment = AsyncMock(
                side_effect=Exception("API Error")
            )

            agent = DexterAgent(
                grok_client=self.mock_grok,
                sentiment_aggregator=self.mock_sentiment_agg
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # Exception = ERROR
            self.assertEqual(result.decision, DecisionType.ERROR)

        asyncio.run(run_test())

    def test_fallback_decision_without_grok(self):
        """Test fallback decision when Grok is unavailable."""
        async def run_test():
            self.mock_sentiment_agg.get_sentiment_score = MagicMock(return_value=75.0)

            agent = DexterAgent(
                grok_client=None,  # No Grok
                sentiment_aggregator=self.mock_sentiment_agg
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # Should return fallback decision, not error
            self.assertIn(result.decision, [DecisionType.HOLD, DecisionType.TRADE_BUY])

        asyncio.run(run_test())


class TestCostTracking(unittest.TestCase):
    """Test cost tracking functionality."""

    def test_react_decision_has_cost(self):
        """Test ReActDecision includes cost field."""
        decision = ReActDecision(decision=DecisionType.HOLD)
        self.assertEqual(decision.cost_usd, 0.0)

    def test_cost_tracked_in_result(self):
        """Test cost is tracked in result."""
        async def run_test():
            mock_grok = AsyncMock()
            mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 70\nCONFIDENCE: 75\nBUY"
            )
            mock_sentiment = MagicMock()
            mock_sentiment.get_sentiment_score = MagicMock(return_value=70.0)

            agent = DexterAgent(
                grok_client=mock_grok,
                sentiment_aggregator=mock_sentiment
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # Cost should be tracked (even if 0 for mock)
            self.assertIsInstance(result.cost_usd, float)
            self.assertGreaterEqual(result.cost_usd, 0.0)

        asyncio.run(run_test())


class TestMaxIterationEnforcement(unittest.TestCase):
    """Test max iteration enforcement."""

    def test_max_iterations_limit(self):
        """Test that iterations don't exceed MAX_ITERATIONS."""
        async def run_test():
            mock_grok = AsyncMock()
            mock_grok.analyze_sentiment = AsyncMock(
                return_value="SENTIMENT_SCORE: 65\nCONFIDENCE: 60\nHOLD"
            )
            mock_sentiment = MagicMock()
            mock_sentiment.get_sentiment_score = MagicMock(return_value=60.0)

            agent = DexterAgent(
                grok_client=mock_grok,
                sentiment_aggregator=mock_sentiment
            )
            result = await agent.analyze_trading_opportunity("SOL")

            # Iterations should not exceed MAX_ITERATIONS
            self.assertLessEqual(result.iterations, DexterAgent.MAX_ITERATIONS)

        asyncio.run(run_test())


class TestScratchpadClass(unittest.TestCase):
    """Test Scratchpad class functionality."""

    def test_scratchpad_initialization(self):
        """Test scratchpad initializes correctly."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            self.assertEqual(sp.session_id, "test-session")
            self.assertEqual(len(sp.entries), 0)

    def test_start_session(self):
        """Test start_session logs correctly."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.start_session("Analyze SOL", symbol="SOL")

            self.assertEqual(len(sp.entries), 1)
            self.assertEqual(sp.entries[0]["type"], "start")
            self.assertEqual(sp.entries[0]["symbol"], "SOL")

    def test_log_reasoning(self):
        """Test log_reasoning adds entry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.log_reasoning("I need to check market data", iteration=1)

            self.assertEqual(len(sp.entries), 1)
            self.assertEqual(sp.entries[0]["type"], "reasoning")
            self.assertEqual(sp.entries[0]["iteration"], 1)

    def test_log_action(self):
        """Test log_action adds entry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.log_action("market_data", {"symbol": "SOL"}, "Price: $142")

            self.assertEqual(len(sp.entries), 1)
            self.assertEqual(sp.entries[0]["type"], "action")
            self.assertEqual(sp.entries[0]["tool"], "market_data")

    def test_log_decision(self):
        """Test log_decision adds entry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.log_decision("BUY", "SOL", "Strong bullish signal", 85.0)

            self.assertEqual(len(sp.entries), 1)
            self.assertEqual(sp.entries[0]["type"], "decision")
            self.assertEqual(sp.entries[0]["confidence"], 85.0)

    def test_log_error(self):
        """Test log_error adds entry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.log_error("API_ERROR", "Connection timeout")

            self.assertEqual(len(sp.entries), 1)
            self.assertEqual(sp.entries[0]["type"], "error")
            self.assertEqual(sp.entries[0]["error_type"], "API_ERROR")

    def test_get_summary(self):
        """Test get_summary returns formatted string."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.start_session("Analyze SOL", symbol="SOL")
            sp.log_reasoning("Check sentiment", iteration=1)
            sp.log_decision("BUY", "SOL", "Bullish", 80.0)

            summary = sp.get_summary()
            self.assertIn("START", summary)
            self.assertIn("REASON", summary)
            self.assertIn("DECISION", summary)

    def test_save_to_disk(self):
        """Test save_to_disk writes JSONL file."""
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=tmpdir)
            sp.log_reasoning("Test thought", iteration=1)
            sp.save_to_disk()

            # Check file exists and has content
            filepath = Path(tmpdir) / "test-session.jsonl"
            self.assertTrue(filepath.exists())

            with open(filepath) as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)
                entry = json.loads(lines[0])
                self.assertEqual(entry["type"], "reasoning")


class TestSentimentExtraction(unittest.TestCase):
    """Test sentiment extraction from Grok responses."""

    def setUp(self):
        self.agent = DexterAgent()

    def test_extract_sentiment_score(self):
        """Test sentiment score extraction."""
        response = "Analysis complete. SENTIMENT_SCORE: 75 based on market data."
        score = self.agent._extract_sentiment_score(response)
        self.assertEqual(score, 75.0)

    def test_extract_sentiment_score_with_colon(self):
        """Test sentiment extraction with colon format."""
        response = "SENTIMENT: 82"
        score = self.agent._extract_sentiment_score(response)
        self.assertEqual(score, 82.0)

    def test_extract_sentiment_score_default(self):
        """Test default sentiment when not found."""
        response = "No clear sentiment in this response."
        score = self.agent._extract_sentiment_score(response)
        self.assertEqual(score, 50.0)  # Neutral default

    def test_extract_confidence(self):
        """Test confidence extraction."""
        response = "CONFIDENCE: 88 based on multiple sources."
        confidence = self.agent._extract_confidence(response)
        self.assertEqual(confidence, 88.0)

    def test_extract_confidence_default(self):
        """Test default confidence when not found."""
        response = "No confidence mentioned."
        confidence = self.agent._extract_confidence(response)
        self.assertEqual(confidence, 50.0)

    def test_parse_recommendation_buy(self):
        """Test BUY recommendation parsing."""
        response = "Strong BUY signal detected."
        rec = self.agent._parse_recommendation(response)
        self.assertEqual(rec, DecisionType.TRADE_BUY)

    def test_parse_recommendation_sell(self):
        """Test SELL recommendation parsing."""
        response = "Consider SELL at current levels."
        rec = self.agent._parse_recommendation(response)
        self.assertEqual(rec, DecisionType.TRADE_SELL)

    def test_parse_recommendation_hold(self):
        """Test HOLD recommendation parsing."""
        response = "Market is uncertain, HOLD for now."
        rec = self.agent._parse_recommendation(response)
        self.assertEqual(rec, DecisionType.HOLD)

    def test_parse_recommendation_default(self):
        """Test default recommendation when unclear."""
        response = "Market is neutral."
        rec = self.agent._parse_recommendation(response)
        self.assertEqual(rec, DecisionType.HOLD)


class TestDexterConfig(unittest.TestCase):
    """Test DexterConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DexterConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.model, DexterModel.GROK_3)
        self.assertEqual(config.max_iterations, 15)
        self.assertEqual(config.max_cost_per_decision, 0.50)
        self.assertEqual(config.min_confidence, 70.0)
        self.assertTrue(config.require_confirmation)
        self.assertTrue(config.save_scratchpad)

    def test_tools_enabled_default(self):
        """Test default enabled tools."""
        config = DexterConfig()
        self.assertIn("financial_research", config.tools_enabled)
        self.assertIn("sentiment_analyze", config.tools_enabled)
        self.assertIn("market_data", config.tools_enabled)

    def test_config_to_dict(self):
        """Test config serialization."""
        config = DexterConfig()
        d = config.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["enabled"], True)
        self.assertEqual(d["model"], "grok-3")

    def test_config_custom_values(self):
        """Test config with custom values."""
        config = DexterConfig(
            enabled=False,
            max_iterations=10,
            max_cost_per_decision=0.25,
            require_confirmation=False
        )
        self.assertFalse(config.enabled)
        self.assertEqual(config.max_iterations, 10)
        self.assertEqual(config.max_cost_per_decision, 0.25)
        self.assertFalse(config.require_confirmation)


if __name__ == '__main__':
    unittest.main()
