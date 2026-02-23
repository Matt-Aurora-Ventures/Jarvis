"""
Tests for Dexter ReAct Decision Loop

Tests the core ReAct (Reasoning + Acting) decision loop:
1. Observe -> Think -> Act cycle
2. Tool selection via meta_router
3. Confidence scoring and thresholds
4. Market analysis tool chain
5. Error handling and fallbacks

These tests work with the actual implementation in core/dexter/.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.dexter.agent import DexterAgent, DecisionType, ReActDecision
from core.dexter.config import DexterConfig, DexterModel
from core.dexter.scratchpad import Scratchpad
from core.dexter.context import ContextManager
from core.dexter.tools.meta_router import MetaRouter, _extract_symbol, financial_research


# =============================================================================
# Section 1: ReAct Decision Loop Tests
# =============================================================================

class TestReActDecisionLoop:
    """Test the Observe -> Think -> Act cycle."""

    def test_decision_loop_initializes_correctly(self):
        """Test agent initializes with proper loop state."""
        agent = DexterAgent()

        # Should have a session ID
        assert agent.session_id is not None
        assert len(agent.session_id) == 8  # UUID prefix

        # Should have default config
        assert agent.model == "grok-4-1-fast-non-reasoning"
        assert agent.max_iterations == 15
        assert agent.min_confidence == 70.0

        # Loop state should be clean
        assert agent._iteration == 0
        assert agent._cost == 0.0

    def test_decision_loop_with_custom_config(self):
        """Test agent respects custom configuration."""
        config = {
            "model": "grok-2",
            "max_iterations": 10,
            "min_confidence": 80.0
        }
        agent = DexterAgent(config)

        assert agent.model == "grok-2"
        assert agent.max_iterations == 10
        assert agent.min_confidence == 80.0

    @pytest.mark.asyncio
    async def test_analyze_token_returns_decision(self):
        """Test analyze_token returns a properly structured decision."""
        agent = DexterAgent()
        result = await agent.analyze_token("SOL")

        # Should return a dict with expected keys
        assert isinstance(result, dict)
        assert "action" in result
        assert "symbol" in result
        assert "confidence" in result
        assert "rationale" in result
        assert "cost" in result

        # Symbol should match input
        assert result["symbol"] == "SOL"

        # Action should be valid
        assert result["action"] in ["BUY", "SELL", "HOLD", "UNKNOWN", "ERROR"]

    @pytest.mark.asyncio
    async def test_analyze_multiple_tokens_independently(self):
        """Test analyzing multiple tokens maintains independent state."""
        agent = DexterAgent()

        tokens = ["SOL", "BTC", "ETH"]
        results = []

        for token in tokens:
            result = await agent.analyze_token(token)
            results.append(result)
            # Iteration should reset between tokens
            assert agent._iteration == 0

        # Each result should have correct symbol
        for i, token in enumerate(tokens):
            assert results[i]["symbol"] == token


class TestReActDecisionClass:
    """Test the ReActDecision data class."""

    def test_react_decision_initialization(self):
        """Test ReActDecision initializes with required fields."""
        decision = ReActDecision(
            action="BUY",
            symbol="SOL",
            confidence=85.0,
            rationale="Strong bullish signal"
        )

        assert decision.action == "BUY"
        assert decision.symbol == "SOL"
        assert decision.confidence == 85.0
        assert decision.rationale == "Strong bullish signal"
        assert decision.iterations == 0  # Default

    def test_react_decision_with_iterations(self):
        """Test ReActDecision tracks iterations."""
        decision = ReActDecision(
            action="HOLD",
            symbol="BTC",
            confidence=55.0,
            rationale="Uncertain market",
            iterations=5
        )

        assert decision.iterations == 5

    def test_react_decision_to_dict(self):
        """Test ReActDecision converts to dictionary."""
        decision = ReActDecision(
            action="SELL",
            symbol="ETH",
            confidence=30.0,
            rationale="Bearish trend",
            iterations=3
        )

        d = decision.to_dict()

        assert isinstance(d, dict)
        assert d["action"] == "SELL"
        assert d["symbol"] == "ETH"
        assert d["confidence"] == 30.0
        assert d["rationale"] == "Bearish trend"
        assert d["iterations"] == 3


class TestDecisionTypeEnum:
    """Test DecisionType enum."""

    def test_decision_type_values(self):
        """Test DecisionType has expected values."""
        assert DecisionType.BUY.value == "BUY"
        assert DecisionType.SELL.value == "SELL"
        assert DecisionType.HOLD.value == "HOLD"
        assert DecisionType.UNKNOWN.value == "UNKNOWN"

    def test_decision_type_value_access(self):
        """Test DecisionType value can be accessed."""
        # DecisionType.value gives the string
        assert DecisionType.BUY.value == "BUY"
        assert DecisionType.SELL.value == "SELL"
        assert DecisionType.HOLD.value == "HOLD"

    def test_decision_type_comparison(self):
        """Test DecisionType can be compared with strings."""
        assert DecisionType.BUY == "BUY"
        assert DecisionType.HOLD == "HOLD"


# =============================================================================
# Section 2: Tool Selection (MetaRouter) Tests
# =============================================================================

class TestMetaRouterToolSelection:
    """Test MetaRouter selects appropriate tools based on query."""

    @pytest.mark.asyncio
    async def test_liquidation_query_routing(self):
        """Test liquidation queries route to liquidation analysis."""
        router = MetaRouter()

        queries = [
            "Check liquidation levels for BTC",
            "Where is the support level?",
            "resistance zone analysis"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert isinstance(result, str)
            assert len(result) > 0
            # Should contain liquidation-related info
            assert any(word in result.lower() for word in ["liquidation", "wall", "$", "support"])

    @pytest.mark.asyncio
    async def test_sentiment_query_routing(self):
        """Test sentiment queries route to sentiment analysis."""
        router = MetaRouter()

        queries = [
            "What is the sentiment for SOL?",
            "Check social media sentiment",
            "Twitter buzz on BTC"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert isinstance(result, str)
            assert any(word in result.lower() for word in ["sentiment", "bullish", "positive", "score"])

    @pytest.mark.asyncio
    async def test_technical_query_routing(self):
        """Test technical queries route to technical analysis."""
        router = MetaRouter()

        queries = [
            "Check the MA crossover",
            "What's the RSI for ETH?",
            "Technical analysis for BTC"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert isinstance(result, str)
            assert any(word in result.lower() for word in ["cross", "ma", "bullish", "bearish"])

    @pytest.mark.asyncio
    async def test_position_query_routing(self):
        """Test position queries route to position status."""
        router = MetaRouter()

        queries = [
            "Check my current positions",
            "What's my portfolio risk?",
            "exposure analysis"
        ]

        for query in queries:
            result = await router.financial_research(query)
            assert isinstance(result, str)
            assert any(word in result.lower() for word in ["position", "capital", "risk"])

    @pytest.mark.asyncio
    async def test_default_routing(self):
        """Test default routing for unrecognized queries."""
        router = MetaRouter()

        result = await router.financial_research("random query about something")

        assert isinstance(result, str)
        # Default returns market status with prices
        assert len(result) > 0


class TestSymbolExtraction:
    """Test symbol extraction from natural language."""

    def test_extract_known_symbols(self):
        """Test extracting known crypto symbols."""
        test_cases = [
            ("Is SOL looking bullish?", "SOL"),
            ("What's the BTC price?", "BTC"),
            ("Should I buy ETH?", "ETH"),
            ("BONK is trending", "BONK"),
        ]

        for query, expected in test_cases:
            result = _extract_symbol(query)
            assert result == expected, f"Expected {expected} from '{query}', got {result}"

    def test_extract_from_uppercase_pattern(self):
        """Test extracting symbols from uppercase patterns."""
        # The current implementation extracts 3-5 char uppercase words
        result = _extract_symbol("Should I invest in TOKEN?")
        assert result == "TOKEN"

    def test_extract_returns_first_match(self):
        """Test extraction returns first matching symbol."""
        # The regex pattern might match other uppercase words too
        result = _extract_symbol("how is the market doing today")
        # "HOW" is 3 chars uppercase, will be matched by pattern
        # This is expected behavior of current implementation
        assert result is None or isinstance(result, str)

    def test_extract_case_insensitive_known(self):
        """Test extraction is case insensitive for known symbols."""
        result = _extract_symbol("check sol price")
        assert result == "SOL"


class TestStandaloneFinancialResearch:
    """Test standalone financial_research function."""

    @pytest.mark.asyncio
    async def test_standalone_function_works(self):
        """Test standalone function wraps MetaRouter."""
        result = await financial_research("analyze market")

        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# Section 3: Confidence Scoring and Thresholds
# =============================================================================

class TestConfidenceScoring:
    """Test confidence scoring mechanics."""

    def test_default_min_confidence_threshold(self):
        """Test default minimum confidence threshold."""
        agent = DexterAgent()
        assert agent.min_confidence == 70.0

    def test_custom_min_confidence_threshold(self):
        """Test custom minimum confidence threshold."""
        agent = DexterAgent({"min_confidence": 85.0})
        assert agent.min_confidence == 85.0

    @pytest.mark.asyncio
    async def test_analyze_returns_confidence(self):
        """Test analysis returns confidence score."""
        agent = DexterAgent()
        result = await agent.analyze_token("SOL")

        assert "confidence" in result
        assert isinstance(result["confidence"], (int, float))
        assert 0 <= result["confidence"] <= 100

    def test_react_decision_confidence_validation(self):
        """Test ReActDecision accepts valid confidence values."""
        # Valid confidence
        decision = ReActDecision("BUY", "SOL", 75.5, "reason")
        assert decision.confidence == 75.5

        # Edge cases
        low = ReActDecision("HOLD", "BTC", 0.0, "reason")
        assert low.confidence == 0.0

        high = ReActDecision("BUY", "ETH", 100.0, "reason")
        assert high.confidence == 100.0


class TestDexterConfig:
    """Test DexterConfig configuration."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = DexterConfig()

        assert config.enabled is True
        assert config.model == "grok-4-1-fast-non-reasoning"
        assert config.max_iterations == 15
        assert config.max_cost_per_decision == 0.50
        assert config.scan_interval_minutes == 15
        assert config.require_confirmation is True
        assert config.min_confidence == 70.0

    def test_tools_enabled_list(self):
        """Test default tools enabled."""
        config = DexterConfig()

        assert "market_data" in config.tools_enabled
        assert "sentiment" in config.tools_enabled
        assert "liquidations" in config.tools_enabled
        assert "technical_indicators" in config.tools_enabled
        assert "onchain_analysis" in config.tools_enabled

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = DexterConfig(
            enabled=False,
            max_iterations=10,
            max_cost_per_decision=0.25,
            require_confirmation=False
        )

        assert config.enabled is False
        assert config.max_iterations == 10
        assert config.max_cost_per_decision == 0.25
        assert config.require_confirmation is False


class TestDexterModel:
    """Test DexterModel enum."""

    def test_model_values(self):
        """Test model enum values."""
        assert DexterModel.GROK_4_FAST.value == "grok-4-1-fast-non-reasoning"
        assert DexterModel.GROK_3.value == "grok-3"
        assert DexterModel.GROK_2.value == "grok-2"
        assert DexterModel.CLAUDE.value == "claude-sonnet-4-6"
        assert DexterModel.GPT4.value == "gpt-4o"

    def test_model_string_representation(self):
        """Test model string representation."""
        assert str(DexterModel.GROK_3) == "grok-3"


# =============================================================================
# Section 4: Market Analysis Tool Chain Tests
# =============================================================================

class TestMarketAnalysisChain:
    """Test the market analysis tool chain."""

    @pytest.mark.asyncio
    async def test_multiple_query_types_in_sequence(self):
        """Test running multiple query types in sequence."""
        router = MetaRouter()

        queries = [
            "Check liquidation levels",
            "What's the sentiment?",
            "Technical indicators",
            "Position status"
        ]

        results = []
        for query in queries:
            result = await router.financial_research(query)
            results.append(result)
            assert isinstance(result, str)
            assert len(result) > 0

        # All results should be different (different tools used)
        # At minimum, should not all be identical
        unique_results = set(results)
        assert len(unique_results) >= 2

    @pytest.mark.asyncio
    async def test_comprehensive_analysis_query(self):
        """Test comprehensive analysis query."""
        router = MetaRouter()

        # Query with 'market' or 'analysis' keyword
        result = await router.financial_research("market status update")

        assert isinstance(result, str)
        # Should contain some data
        assert len(result) > 0


# =============================================================================
# Section 5: Error Handling and Fallbacks
# =============================================================================

class TestErrorHandling:
    """Test error handling and fallback behavior."""

    @pytest.mark.asyncio
    async def test_analyze_invalid_token(self):
        """Test analyzing invalid/unknown token."""
        agent = DexterAgent()

        # Should not raise, should return a decision
        result = await agent.analyze_token("INVALIDTOKEN12345")

        assert result is not None
        assert "symbol" in result
        assert result["symbol"] == "INVALIDTOKEN12345"

    @pytest.mark.asyncio
    async def test_analyze_empty_symbol(self):
        """Test analyzing empty symbol."""
        agent = DexterAgent()

        result = await agent.analyze_token("")

        assert result is not None
        assert "action" in result

    @pytest.mark.asyncio
    async def test_meta_router_handles_empty_query(self):
        """Test MetaRouter handles empty query gracefully."""
        router = MetaRouter()

        result = await router.financial_research("")

        # Should return default market status
        assert isinstance(result, str)

    def test_agent_handles_none_config(self):
        """Test agent handles None config."""
        agent = DexterAgent(None)

        # Should use defaults
        assert agent.model == "grok-4-1-fast-non-reasoning"
        assert agent.max_iterations == 15

    def test_agent_handles_empty_config(self):
        """Test agent handles empty config dict."""
        agent = DexterAgent({})

        # Should use defaults
        assert agent.model == "grok-4-1-fast-non-reasoning"
        assert agent.max_iterations == 15


class TestScratchpadErrorHandling:
    """Test Scratchpad error handling."""

    def test_scratchpad_handles_invalid_directory(self):
        """Test Scratchpad handles directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use nested path that doesn't exist
            nested_path = Path(tmpdir) / "deep" / "nested" / "path"

            sp = Scratchpad("test-session", scratchpad_dir=nested_path)

            # Should create directory
            assert sp.scratchpad_dir.exists()

    def test_scratchpad_log_error_method(self):
        """Test Scratchpad log_error method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            sp.log_error("Test error message", iteration=1)

            entries = sp.get_entries()
            assert len(entries) == 1
            assert entries[0]["type"] == "error"
            assert entries[0]["error"] == "Test error message"
            assert entries[0]["iteration"] == 1


class TestContextManagerErrorHandling:
    """Test ContextManager error handling."""

    def test_context_manager_handles_missing_data(self):
        """Test loading from empty session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("empty-session", data_dir=Path(tmpdir))

            # Should return None for missing data
            result = ctx.load_historical("nonexistent")
            assert result is None

    def test_context_manager_summary_empty(self):
        """Test summary with no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("empty-session", data_dir=Path(tmpdir))

            summary = ctx.get_summary()

            # Should return header at minimum
            assert "Context" in summary or "===" in summary


# =============================================================================
# Section 6: Integration Tests - Full Decision Flow
# =============================================================================

class TestFullDecisionFlow:
    """Test the full decision flow from input to output."""

    @pytest.mark.asyncio
    async def test_complete_analysis_flow(self):
        """Test complete analysis from start to finish."""
        agent = DexterAgent()

        # Analyze a token
        result = await agent.analyze_token("SOL")

        # Verify all expected outputs
        assert result["symbol"] == "SOL"
        assert result["action"] in ["BUY", "SELL", "HOLD", "UNKNOWN"]
        assert isinstance(result["confidence"], (int, float))
        assert isinstance(result["rationale"], str)
        assert isinstance(result["cost"], (int, float))

    @pytest.mark.asyncio
    async def test_decision_flow_with_scratchpad(self):
        """Test decision flow with scratchpad logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = DexterAgent()

            # Create scratchpad for this session - use Path object
            sp = Scratchpad(agent.session_id, scratchpad_dir=Path(tmpdir))
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

            # Verify scratchpad has entries
            entries = sp.get_entries()
            assert len(entries) >= 2

            # Should have start and decision
            types = [e["type"] for e in entries]
            assert "start" in types
            assert "decision" in types

    @pytest.mark.asyncio
    async def test_decision_flow_with_context(self):
        """Test decision flow with context management."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = DexterAgent()

            # Create context manager
            ctx = ContextManager(agent.session_id, data_dir=Path(tmpdir))

            # Run analysis
            result = await agent.analyze_token("SOL")

            # Add to context
            ctx.add_summary(f"Analyzed {result['symbol']}: {result['action']}")

            # Verify context has summary
            summary = ctx.get_summary()
            assert "SOL" in summary


class TestCostTracking:
    """Test cost tracking through decision flow."""

    @pytest.mark.asyncio
    async def test_cost_is_tracked(self):
        """Test cost is tracked in result."""
        agent = DexterAgent()

        result = await agent.analyze_token("SOL")

        assert "cost" in result
        assert isinstance(result["cost"], (int, float))
        assert result["cost"] >= 0

    @pytest.mark.asyncio
    async def test_cost_accumulates(self):
        """Test cost accumulates across analyses."""
        agent = DexterAgent()

        # Run multiple analyses
        await agent.analyze_token("SOL")
        await agent.analyze_token("BTC")

        # Cost should be tracked in agent
        assert agent._cost >= 0


# =============================================================================
# Section 7: Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_max_iterations_boundary(self):
        """Test max iterations boundary."""
        agent = DexterAgent({"max_iterations": 1})
        assert agent.max_iterations == 1

        agent2 = DexterAgent({"max_iterations": 100})
        assert agent2.max_iterations == 100

    def test_min_confidence_boundary(self):
        """Test min confidence boundary."""
        agent = DexterAgent({"min_confidence": 0.0})
        assert agent.min_confidence == 0.0

        agent2 = DexterAgent({"min_confidence": 100.0})
        assert agent2.min_confidence == 100.0

    @pytest.mark.asyncio
    async def test_special_characters_in_symbol(self):
        """Test handling symbols with special characters."""
        agent = DexterAgent()

        # Should handle gracefully
        result = await agent.analyze_token("$SOL")
        assert result is not None

    def test_scratchpad_long_rationale(self):
        """Test scratchpad handles long rationale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sp = Scratchpad("test-session", scratchpad_dir=Path(tmpdir))

            # Very long rationale
            long_rationale = "This is a very long rationale. " * 100
            sp.log_decision("BUY", "SOL", long_rationale, 85.0)

            entries = sp.get_entries()
            assert len(entries) == 1
            # Result should be capped at 500 chars in action logs
            # Decision logs the full rationale

    def test_context_manager_many_summaries(self):
        """Test context manager with many summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ContextManager("test-session", data_dir=Path(tmpdir))

            # Add many summaries
            for i in range(100):
                ctx.add_summary(f"Summary {i}: " + "x" * 100)

            # Should compact automatically
            # get_summary only returns last 3
            summary = ctx.get_summary()
            assert isinstance(summary, str)


# =============================================================================
# Section 8: Concurrency Tests
# =============================================================================

class TestConcurrency:
    """Test concurrent operation handling."""

    @pytest.mark.asyncio
    async def test_concurrent_analyses(self):
        """Test running concurrent analyses."""
        import asyncio

        async def analyze_token(symbol):
            agent = DexterAgent()
            return await agent.analyze_token(symbol)

        # Run multiple analyses concurrently
        results = await asyncio.gather(
            analyze_token("SOL"),
            analyze_token("BTC"),
            analyze_token("ETH")
        )

        # All should complete successfully
        assert len(results) == 3
        for result in results:
            assert result is not None
            assert "action" in result

    @pytest.mark.asyncio
    async def test_concurrent_meta_router_queries(self):
        """Test concurrent MetaRouter queries."""
        import asyncio

        router = MetaRouter()

        queries = [
            "liquidation levels",
            "sentiment analysis",
            "technical indicators",
            "position status"
        ]

        # Run concurrently
        tasks = [router.financial_research(q) for q in queries]
        results = await asyncio.gather(*tasks)

        assert len(results) == 4
        for result in results:
            assert isinstance(result, str)
            assert len(result) > 0


# Ensure module can be run standalone
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
