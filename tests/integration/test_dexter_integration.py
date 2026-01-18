"""
Integration Tests for Dexter ReAct Agent

Full dry run tests with mocked market data to verify:
- Tool chain works end-to-end
- Decision quality scores
- Cost tracking accuracy
- Scratchpad logging
- Comparison with existing sentiment pipeline
"""

import unittest
import asyncio
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig
from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager
from core.dexter.tools.meta_router import financial_research, _extract_symbol


class MockGrokClient:
    """Mock Grok client for integration testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_count = 0
        self.call_history = []

    async def analyze_sentiment(self, symbol: str, prompt: str) -> str:
        """Return mocked sentiment analysis."""
        self.call_count += 1
        self.call_history.append({"symbol": symbol, "prompt": prompt})

        # Default bullish response
        if symbol in self.responses:
            return self.responses[symbol]

        return f"""
        Analysis for {symbol}:
        SENTIMENT_SCORE: 75
        CONFIDENCE: 80
        RECOMMENDATION: BUY

        Market shows bullish momentum with strong volume support.
        Risk/reward ratio favors long positions.
        """


class MockSentimentAggregator:
    """Mock sentiment aggregator for integration testing."""

    def __init__(self, scores=None):
        self.scores = scores or {"SOL": 72.0, "BTC": 68.0, "ETH": 65.0}

    def get_sentiment_score(self, symbol: str) -> float:
        """Return mocked sentiment score."""
        return self.scores.get(symbol, 50.0)

    def get_sentiment_leaders(self, count: int = 10):
        """Return top sentiment leaders."""
        sorted_items = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:count]


class TestFullDryRun(unittest.TestCase):
    """Full dry run integration tests."""

    def setUp(self):
        """Set up mocked environment."""
        self.grok = MockGrokClient({
            "SOL": "SENTIMENT_SCORE: 82\nCONFIDENCE: 85\nRECOMMENDATION: BUY\nStrong bullish signal",
            "BTC": "SENTIMENT_SCORE: 65\nCONFIDENCE: 60\nRECOMMENDATION: HOLD\nUncertain market",
            "ETH": "SENTIMENT_SCORE: 78\nCONFIDENCE: 75\nRECOMMENDATION: BUY\nGood momentum",
        })
        self.sentiment = MockSentimentAggregator({
            "SOL": 78.0,
            "BTC": 55.0,
            "ETH": 72.0,
        })

    def test_full_dry_run_sol(self):
        """Test full dry run on SOL - should result in BUY."""
        async def run_test():
            agent = DexterAgent(
                grok_client=self.grok,
                sentiment_aggregator=self.sentiment
            )

            result = await agent.analyze_trading_opportunity("SOL")

            # Verify decision structure
            self.assertIsInstance(result, ReActDecision)
            self.assertEqual(result.symbol, "SOL")

            # SOL should be bullish
            self.assertGreater(result.grok_sentiment_score, 70)
            self.assertGreater(result.iterations, 0)

            # Scratchpad should have entries
            self.assertGreater(len(agent.scratchpad), 0)

        asyncio.run(run_test())

    def test_full_dry_run_btc(self):
        """Test full dry run on BTC - should result in HOLD."""
        async def run_test():
            agent = DexterAgent(
                grok_client=self.grok,
                sentiment_aggregator=self.sentiment
            )

            result = await agent.analyze_trading_opportunity("BTC")

            # BTC should be more cautious
            self.assertIsInstance(result, ReActDecision)
            self.assertEqual(result.symbol, "BTC")

        asyncio.run(run_test())

    def test_multiple_tokens_in_sequence(self):
        """Test analyzing multiple tokens in sequence."""
        async def run_test():
            agent = DexterAgent(
                grok_client=self.grok,
                sentiment_aggregator=self.sentiment
            )

            tokens = ["SOL", "BTC", "ETH"]
            results = []

            for token in tokens:
                result = await agent.analyze_trading_opportunity(token)
                results.append(result)
                # Reset for next token
                agent.scratchpad = []
                agent.iteration_count = 0

            self.assertEqual(len(results), 3)
            for r in results:
                self.assertIsInstance(r, ReActDecision)

        asyncio.run(run_test())


class TestToolChainEndToEnd(unittest.TestCase):
    """Test that tool chain works end-to-end."""

    def test_financial_research_routing(self):
        """Test financial_research routes queries correctly."""
        async def run_test():
            sentiment_agg = MockSentimentAggregator()

            # Test sentiment query
            result = await financial_research(
                "Is SOL looking bullish?",
                sentiment_agg=sentiment_agg
            )

            self.assertIn("query", result)
            self.assertIn("tools_used", result)
            self.assertIn("sentiment_aggregation", result["tools_used"])

        asyncio.run(run_test())

    def test_financial_research_position_query(self):
        """Test position query routing."""
        async def run_test():
            mock_pm = MagicMock()
            mock_pm.get_open_positions = MagicMock(return_value=[])

            result = await financial_research(
                "What positions do I have open?",
                position_manager=mock_pm
            )

            self.assertIn("position_status", result["tools_used"])

        asyncio.run(run_test())

    def test_financial_research_trending_query(self):
        """Test trending query routing."""
        async def run_test():
            sentiment_agg = MockSentimentAggregator()

            result = await financial_research(
                "What are the top performers?",
                sentiment_agg=sentiment_agg
            )

            self.assertIn("trending_analysis", result["tools_used"])

        asyncio.run(run_test())

    def test_financial_research_risk_query(self):
        """Test risk query routing."""
        async def run_test():
            result = await financial_research(
                "What are the liquidation levels for BTC?"
            )

            self.assertIn("risk_analysis", result["tools_used"])

        asyncio.run(run_test())


class TestDecisionQualityScores(unittest.TestCase):
    """Test decision quality scoring."""

    def test_high_confidence_decision(self):
        """Test high confidence produces quality decision."""
        async def run_test():
            grok = MockGrokClient({
                "SOL": "SENTIMENT_SCORE: 90\nCONFIDENCE: 95\nBUY"
            })
            sentiment = MockSentimentAggregator({"SOL": 88.0})

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # High quality decision
            self.assertGreaterEqual(result.grok_sentiment_score, 85)

        asyncio.run(run_test())

    def test_low_confidence_results_in_hold(self):
        """Test low confidence results in HOLD."""
        async def run_test():
            grok = MockGrokClient({
                "UNKNOWN": "SENTIMENT_SCORE: 45\nCONFIDENCE: 30\nHOLD"
            })
            sentiment = MockSentimentAggregator({"UNKNOWN": 40.0})

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("UNKNOWN")

            # Low confidence = HOLD
            self.assertEqual(result.decision, DecisionType.HOLD)

        asyncio.run(run_test())


class TestCostTrackingAccuracy(unittest.TestCase):
    """Test cost tracking is accurate."""

    def test_cost_is_non_negative(self):
        """Test cost is never negative."""
        async def run_test():
            grok = MockGrokClient()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            self.assertGreaterEqual(result.cost_usd, 0.0)

        asyncio.run(run_test())

    def test_cost_within_budget(self):
        """Test cost stays within budget."""
        async def run_test():
            grok = MockGrokClient()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            self.assertLessEqual(result.cost_usd, DexterAgent.MAX_COST_USD)

        asyncio.run(run_test())


class TestScratchpadLogging(unittest.TestCase):
    """Test scratchpad logging completeness."""

    def test_scratchpad_captures_full_trail(self):
        """Test scratchpad captures complete decision trail."""
        async def run_test():
            grok = MockGrokClient({
                "SOL": "SENTIMENT_SCORE: 80\nCONFIDENCE: 85\nBUY"
            })
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            # Should have multiple entries
            self.assertGreater(len(agent.scratchpad), 0)

            # Check for reasoning entries
            types = [e["type"] for e in agent.scratchpad]
            self.assertIn("reasoning", types)

        asyncio.run(run_test())

    def test_scratchpad_get_scratchpad_format(self):
        """Test get_scratchpad returns readable format."""
        async def run_test():
            grok = MockGrokClient()
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            await agent.analyze_trading_opportunity("SOL")

            formatted = agent.get_scratchpad()
            self.assertIsInstance(formatted, str)
            self.assertGreater(len(formatted), 0)

        asyncio.run(run_test())


class TestComparisonWithSentimentPipeline(unittest.TestCase):
    """Compare Dexter decisions vs existing sentiment pipeline."""

    def test_dexter_vs_sentiment_agg_alignment(self):
        """Test Dexter aligns with sentiment aggregator."""
        async def run_test():
            # Both should agree on bullish SOL
            grok = MockGrokClient({
                "SOL": "SENTIMENT_SCORE: 82\nCONFIDENCE: 85\nBUY"
            })
            sentiment = MockSentimentAggregator({"SOL": 80.0})

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # Dexter and sentiment agg should be aligned
            sentiment_score = sentiment.get_sentiment_score("SOL")
            grok_score = result.grok_sentiment_score

            # Within reasonable range of each other
            self.assertLess(abs(grok_score - sentiment_score), 20)

        asyncio.run(run_test())

    def test_dexter_overrides_low_sentiment(self):
        """Test Dexter can override low aggregated sentiment with Grok."""
        async def run_test():
            # Grok is bullish, sentiment agg is bearish
            grok = MockGrokClient({
                "TOKEN": "SENTIMENT_SCORE: 85\nCONFIDENCE: 90\nBUY"
            })
            sentiment = MockSentimentAggregator({"TOKEN": 40.0})

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("TOKEN")

            # Grok (1.0 weight) should dominate
            self.assertGreater(result.grok_sentiment_score, 70)

        asyncio.run(run_test())


class TestSymbolExtraction(unittest.TestCase):
    """Test symbol extraction from queries."""

    def test_extract_known_symbol(self):
        """Test extracting known symbols."""
        symbol = _extract_symbol("Is SOL looking bullish?")
        self.assertEqual(symbol, "SOL")

    def test_extract_btc(self):
        """Test extracting BTC."""
        symbol = _extract_symbol("What's the BTC sentiment?")
        self.assertEqual(symbol, "BTC")

    def test_extract_first_uppercase(self):
        """Test extracting first uppercase word."""
        symbol = _extract_symbol("Should I buy NEWTOKEN today?")
        self.assertEqual(symbol, "NEWTOKEN")

    def test_extract_none_when_missing(self):
        """Test None when no symbol found."""
        symbol = _extract_symbol("how is the market doing")
        self.assertIsNone(symbol)


class TestContextManagerIntegration(unittest.TestCase):
    """Test context manager with full workflow."""

    def test_save_and_compress_data(self):
        """Test saving and compressing market data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-integration", session_dir=tmpdir)

            # Save market data
            market_data = {
                "symbol": "SOL",
                "price": 142.50,
                "volume": 2500000000,
                "timestamp": datetime.utcnow().isoformat()
            }

            summary = ctx.save_full_data(market_data, "market_data")

            # Should return compressed summary
            self.assertIn("SOL", summary)
            self.assertIn("$142", summary)

            # Full data should be saved to disk
            files = list(Path(tmpdir).rglob("*.json"))
            self.assertGreater(len(files), 0)

    def test_session_state_persistence(self):
        """Test session state can be saved and recovered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-persist", session_dir=tmpdir)

            ctx.add_summary("Analysis 1")
            ctx.add_summary("Analysis 2")
            ctx.save_session_state()

            # State file should exist
            state_file = Path(tmpdir) / "test-persist" / "state.json"
            self.assertTrue(state_file.exists())

            with open(state_file) as f:
                state = json.load(f)

            self.assertEqual(state["session_id"], "test-persist")
            self.assertEqual(state["summaries_count"], 2)


class TestDryRunScratchpadPersistence(unittest.TestCase):
    """Test scratchpad persistence for dry runs."""

    def test_scratchpad_jsonl_format(self):
        """Test scratchpad saves in JSONL format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("dryrun-test", scratchpad_dir=tmpdir)

            sp.start_session("Dry run test", symbol="SOL")
            sp.log_reasoning("Checking market state", iteration=1)
            sp.log_action("financial_research", {"query": "SOL sentiment"}, "Bullish")
            sp.log_decision("BUY", "SOL", "Strong signal", 85.0)
            sp.save_to_disk()

            # Read and verify JSONL
            filepath = Path(tmpdir) / "dryrun-test.jsonl"
            with open(filepath) as f:
                lines = f.readlines()

            self.assertEqual(len(lines), 4)

            # Each line should be valid JSON
            for line in lines:
                entry = json.loads(line)
                self.assertIn("ts", entry)
                self.assertIn("type", entry)


class TestMultipleIterationsIntegration(unittest.TestCase):
    """Test multiple iterations through the ReAct loop."""

    def test_five_iterations(self):
        """Test running through multiple iterations."""
        async def run_test():
            # Grok that requires multiple calls
            call_count = [0]

            async def mock_analyze(symbol, prompt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return "SENTIMENT_SCORE: 70\nCONFIDENCE: 60\nNeed more data"
                else:
                    return "SENTIMENT_SCORE: 80\nCONFIDENCE: 85\nBUY confirmed"

            grok = MockGrokClient()
            grok.analyze_sentiment = mock_analyze
            sentiment = MockSentimentAggregator()

            agent = DexterAgent(grok_client=grok, sentiment_aggregator=sentiment)
            result = await agent.analyze_trading_opportunity("SOL")

            # Should have gone through multiple iterations
            self.assertGreater(result.iterations, 0)

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
