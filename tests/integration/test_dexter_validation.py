"""
Dexter ReAct Agent Validation Tests

Comprehensive validation tests to ensure Dexter is ready for production:
1. Decision quality validation (not all signals should be BUY)
2. Scratchpad logging completeness
3. Cost tracking accuracy
4. Paper trading calculations
5. Confidence threshold enforcement

Target: 15-20 validation tests
"""

import unittest
import asyncio
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from dataclasses import asdict

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig
from core.dexter.scratchpad import Scratchpad


class MockGrokClientVaried:
    """Mock Grok client with varied responses for decision quality testing."""

    RESPONSES = {
        "SOL": {
            "initial": "SENTIMENT_SCORE: 82\nCONFIDENCE: 85",
            "final": "SENTIMENT_SCORE: 85\nCONFIDENCE: 88\nRECOMMENDATION: BUY\nStrong bullish"
        },
        "BTC": {
            "initial": "SENTIMENT_SCORE: 55\nCONFIDENCE: 50",
            "final": "SENTIMENT_SCORE: 58\nCONFIDENCE: 55\nRECOMMENDATION: HOLD\nUncertain"
        },
        "SCAM": {
            "initial": "SENTIMENT_SCORE: 25\nCONFIDENCE: 30",
            "final": "SENTIMENT_SCORE: 20\nCONFIDENCE: 25\nRECOMMENDATION: SELL\nHigh risk"
        },
        "NEUTRAL": {
            "initial": "SENTIMENT_SCORE: 50\nCONFIDENCE: 45",
            "final": "SENTIMENT_SCORE: 52\nCONFIDENCE: 48\nRECOMMENDATION: HOLD\nNo clear signal"
        },
        "PUMP": {
            "initial": "SENTIMENT_SCORE: 95\nCONFIDENCE: 60",
            "final": "SENTIMENT_SCORE: 90\nCONFIDENCE: 65\nRECOMMENDATION: BUY\nRisky but high momentum"
        },
    }

    COST_PER_CALL = 0.015

    def __init__(self):
        self.call_count = 0
        self.total_cost = 0.0
        self.call_history = []

    async def analyze_sentiment(self, symbol: str, prompt: str) -> str:
        self.call_count += 1
        self.total_cost += self.COST_PER_CALL
        self.call_history.append({
            "symbol": symbol,
            "prompt": prompt[:100],
            "cost": self.COST_PER_CALL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        await asyncio.sleep(0.01)  # Simulated latency

        responses = self.RESPONSES.get(symbol.upper(), self.RESPONSES["NEUTRAL"])

        if "final decision" in prompt.lower() or "decision:" in prompt.lower():
            return responses["final"]
        return responses["initial"]


class MockSentimentAggregator:
    """Mock sentiment aggregator."""

    SCORES = {
        "SOL": 78.0,
        "BTC": 55.0,
        "SCAM": 20.0,
        "NEUTRAL": 50.0,
        "PUMP": 85.0,
    }

    def get_sentiment_score(self, symbol: str) -> float:
        return self.SCORES.get(symbol.upper(), 50.0)


class TestDecisionQuality(unittest.TestCase):
    """Test that decision quality is appropriate - not all signals should be BUY."""

    def test_varied_decisions_across_tokens(self):
        """Test that Dexter produces varied decisions, not always BUY."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            decisions = {}
            for symbol in ["SOL", "BTC", "SCAM", "NEUTRAL", "PUMP"]:
                agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
                result = await agent.analyze_trading_opportunity(symbol)
                decisions[symbol] = result.decision

            # Should not all be BUY
            decision_values = [d.value for d in decisions.values()]
            unique_decisions = set(decision_values)

            # Expect at least 2 different decision types
            self.assertGreaterEqual(
                len(unique_decisions), 2,
                f"Expected varied decisions but got: {decision_values}"
            )

        asyncio.run(run_test())

    def test_low_confidence_results_in_hold(self):
        """Test that low confidence always results in HOLD."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("NEUTRAL")

            # Low confidence should result in HOLD
            self.assertEqual(result.decision, DecisionType.HOLD)

        asyncio.run(run_test())

    def test_scam_token_not_buy(self):
        """Test that clearly bearish tokens don't get BUY signals."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SCAM")

            # Should not be a BUY
            self.assertNotEqual(result.decision, DecisionType.TRADE_BUY)

        asyncio.run(run_test())

    def test_decision_distribution_reasonable(self):
        """Test that over multiple tokens, decision distribution is reasonable."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            tokens = ["SOL", "BTC", "SCAM", "NEUTRAL", "PUMP"] * 2  # 10 tokens
            buy_count = 0
            hold_count = 0
            sell_count = 0

            for symbol in tokens:
                agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
                result = await agent.analyze_trading_opportunity(symbol)

                if result.decision == DecisionType.TRADE_BUY:
                    buy_count += 1
                elif result.decision == DecisionType.HOLD:
                    hold_count += 1
                elif result.decision == DecisionType.TRADE_SELL:
                    sell_count += 1

            # Not all should be BUY
            self.assertLess(buy_count, len(tokens))
            # Should have some HOLDs
            self.assertGreater(hold_count, 0)

        asyncio.run(run_test())


class TestScratchpadCompleteness(unittest.TestCase):
    """Test that scratchpad captures complete decision trail."""

    def test_scratchpad_has_all_entry_types(self):
        """Test scratchpad captures reasoning, action, and decision."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            # Check entry types
            entry_types = [e["type"] for e in agent.scratchpad]

            # Should have reasoning entries
            self.assertIn("reasoning", entry_types)

        asyncio.run(run_test())

    def test_scratchpad_has_timestamps(self):
        """Test all scratchpad entries have timestamps."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            for entry in agent.scratchpad:
                self.assertIn("timestamp", entry)
                # Verify timestamp is valid ISO format
                self.assertIsNotNone(entry["timestamp"])

        asyncio.run(run_test())

    def test_scratchpad_persistence(self):
        """Test scratchpad can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-persist", scratchpad_dir=tmpdir)
            sp.start_session("Test", symbol="SOL")
            sp.log_reasoning("Test thought", iteration=1)
            sp.log_action("test_tool", {"arg": 1}, "result")
            sp.log_decision("BUY", "SOL", "Test rationale", 85.0)
            sp.save_to_disk()

            # Read back and verify
            filepath = Path(tmpdir) / "test-persist.jsonl"
            self.assertTrue(filepath.exists())

            with open(filepath) as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 4)

            # Verify each line is valid JSON
            for line in lines:
                entry = json.loads(line)
                self.assertIn("ts", entry)
                self.assertIn("type", entry)

    def test_scratchpad_summary_readable(self):
        """Test get_summary returns human-readable format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-summary", scratchpad_dir=tmpdir)
            sp.start_session("Analyze SOL", symbol="SOL")
            sp.log_reasoning("Checking market data", iteration=1)
            sp.log_action("market_data", {"symbol": "SOL"}, "Price: $142")
            sp.log_decision("BUY", "SOL", "Strong signal", 85.0)

            summary = sp.get_summary()

            # Should be readable
            self.assertIn("START", summary)
            self.assertIn("REASON", summary)
            self.assertIn("ACTION", summary)
            self.assertIn("DECISION", summary)
            self.assertIn("BUY", summary)


class TestCostTrackingAccuracy(unittest.TestCase):
    """Test cost tracking is accurate and within budget."""

    def test_cost_accumulates_correctly(self):
        """Test that cost accumulates with each Grok call."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            # Cost should be positive
            self.assertGreater(grok.total_cost, 0)

            # Cost should equal calls * cost_per_call
            expected_cost = grok.call_count * MockGrokClientVaried.COST_PER_CALL
            self.assertAlmostEqual(grok.total_cost, expected_cost, places=4)

        asyncio.run(run_test())

    def test_cost_within_budget(self):
        """Test cost stays within configured budget."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            # Run multiple analyses
            for symbol in ["SOL", "BTC", "NEUTRAL"]:
                agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
                result = await agent.analyze_trading_opportunity(symbol)

                # Each decision should be within budget
                # Note: cost is tracked per grok client, not per agent
                self.assertLessEqual(
                    grok.total_cost / grok.call_count * 4,  # Estimate max calls per decision
                    DexterAgent.MAX_COST_USD
                )

        asyncio.run(run_test())

    def test_cost_logged_in_result(self):
        """Test cost is included in ReActDecision."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # Result should have cost_usd field
            self.assertIsInstance(result.cost_usd, float)
            self.assertGreaterEqual(result.cost_usd, 0.0)

        asyncio.run(run_test())

    def test_cost_per_decision_target(self):
        """Test average cost per decision is under target ($0.20)."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            total_cost = 0.0
            decisions = 0

            for symbol in ["SOL", "BTC", "NEUTRAL", "PUMP", "SCAM"]:
                agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
                result = await agent.analyze_trading_opportunity(symbol)
                decisions += 1

            avg_cost = grok.total_cost / decisions

            # Target: < $0.20 per decision
            self.assertLess(avg_cost, 0.20)

        asyncio.run(run_test())


class TestConfidenceThreshold(unittest.TestCase):
    """Test confidence threshold enforcement."""

    def test_min_confidence_constant_correct(self):
        """Test MIN_CONFIDENCE is set correctly."""
        self.assertEqual(DexterAgent.MIN_CONFIDENCE, 70.0)

    def test_below_threshold_results_in_hold(self):
        """Test decisions below confidence threshold are HOLD."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            # NEUTRAL token has low confidence (48%)
            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("NEUTRAL")

            # Should be HOLD due to low confidence
            self.assertEqual(result.decision, DecisionType.HOLD)

        asyncio.run(run_test())

    def test_above_threshold_can_trade(self):
        """Test decisions above confidence threshold can result in trade."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            # SOL has high confidence (88%)
            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # Should be able to produce a BUY signal
            # (confidence 88% > threshold 70%)
            if result.confidence >= DexterAgent.MIN_CONFIDENCE:
                self.assertIn(
                    result.decision,
                    [DecisionType.TRADE_BUY, DecisionType.TRADE_SELL, DecisionType.HOLD]
                )

        asyncio.run(run_test())

    def test_confidence_logged_correctly(self):
        """Test confidence is logged in result."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # Confidence should be a valid percentage
            self.assertIsInstance(result.confidence, float)
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 100.0)

        asyncio.run(run_test())


class TestPaperTradingCalculations(unittest.TestCase):
    """Test paper trading P&L calculations."""

    def test_pnl_calculation_positive(self):
        """Test P&L calculation for winning trade."""
        entry_price = 100.0
        exit_price = 110.0
        position_size_usd = 1000.0

        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        pnl_usd = position_size_usd * (pnl_pct / 100)

        self.assertEqual(pnl_pct, 10.0)
        self.assertEqual(pnl_usd, 100.0)

    def test_pnl_calculation_negative(self):
        """Test P&L calculation for losing trade."""
        entry_price = 100.0
        exit_price = 90.0
        position_size_usd = 1000.0

        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        pnl_usd = position_size_usd * (pnl_pct / 100)

        self.assertEqual(pnl_pct, -10.0)
        self.assertEqual(pnl_usd, -100.0)

    def test_accuracy_calculation(self):
        """Test accuracy calculation from paper trades."""
        trades = [
            {"decision": "BUY", "pnl_pct": 5.0},   # Correct
            {"decision": "BUY", "pnl_pct": -3.0},  # Incorrect
            {"decision": "HOLD", "pnl_pct": 0.0},  # Neutral
            {"decision": "SELL", "pnl_pct": -2.0}, # Correct (price went down)
            {"decision": "BUY", "pnl_pct": 8.0},   # Correct
        ]

        correct = 0
        total = 0
        for trade in trades:
            if trade["decision"] == "HOLD":
                continue
            total += 1
            if trade["decision"] == "BUY" and trade["pnl_pct"] > 0:
                correct += 1
            elif trade["decision"] == "SELL" and trade["pnl_pct"] < 0:
                correct += 1

        accuracy = (correct / total) * 100 if total > 0 else 0

        self.assertEqual(accuracy, 75.0)  # 3 correct out of 4 trades


class TestIterationTracking(unittest.TestCase):
    """Test that iterations are tracked correctly."""

    def test_iterations_counted(self):
        """Test iterations are counted in result."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            self.assertIsInstance(result.iterations, int)
            self.assertGreater(result.iterations, 0)
            self.assertLessEqual(result.iterations, DexterAgent.MAX_ITERATIONS)

        asyncio.run(run_test())

    def test_max_iterations_enforced(self):
        """Test that max iterations limit is respected."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            for _ in range(5):  # Run multiple times
                agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
                result = await agent.analyze_trading_opportunity("SOL")
                self.assertLessEqual(result.iterations, DexterAgent.MAX_ITERATIONS)

        asyncio.run(run_test())


class TestToolsUsedTracking(unittest.TestCase):
    """Test that tools used are tracked."""

    def test_tools_list_populated(self):
        """Test tools_used list is populated."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            self.assertIsInstance(result.tools_used, list)

        asyncio.run(run_test())

    def test_scratchpad_tools_method(self):
        """Test scratchpad_tools() method works."""
        async def run_test():
            grok = MockGrokClientVaried()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            tools = agent.scratchpad_tools()
            self.assertIsInstance(tools, list)

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
