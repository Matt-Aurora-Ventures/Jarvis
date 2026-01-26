"""
Tests for Bull/Bear Debate Orchestrator

These tests verify:
1. Debate orchestration with Bull and Bear personas
2. Market data distribution to both analysts
3. Structured debate format (argument, counter-argument, synthesis)
4. Confidence scoring from debate outcomes
5. Integration with trading signals
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from dataclasses import dataclass


class TestDebateOrchestrator:
    """Test core debate orchestration logic."""

    @pytest.mark.asyncio
    async def test_orchestrator_requires_market_data(self):
        """Debate should require market data for context."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        orchestrator = DebateOrchestrator()

        with pytest.raises(ValueError, match="market_data"):
            await orchestrator.evaluate_trade(signal=None, market_data=None)

    @pytest.mark.asyncio
    async def test_orchestrator_generates_bull_case(self):
        """Orchestrator should generate bull analyst perspective."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        # Mock Claude client
        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "BULL CASE: Strong momentum, high volume, "
                      "sentiment turning positive. Entry at support level.",
            "tokens_used": 100,
        }

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {
            "symbol": "BONK",
            "price": 0.00001234,
            "change_24h": 15.5,
            "volume_24h": 1500000,
        }
        signal = {"direction": "BUY", "confidence": 70}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        assert result.bull_case is not None
        assert len(result.bull_case) > 0

    @pytest.mark.asyncio
    async def test_orchestrator_generates_bear_case(self):
        """Orchestrator should generate bear analyst perspective."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        # Mock Claude client
        mock_client = AsyncMock()
        mock_client.generate.side_effect = [
            {"content": "BULL CASE: Price momentum strong.", "tokens_used": 50},
            {"content": "BEAR CASE: Overbought RSI, potential reversal. "
                       "Volume declining from peak.", "tokens_used": 60},
        ]

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 70}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        assert result.bear_case is not None
        assert len(result.bear_case) > 0

    @pytest.mark.asyncio
    async def test_orchestrator_synthesizes_debate(self):
        """Orchestrator should synthesize both perspectives."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.side_effect = [
            {"content": "BULL: Strong entry", "tokens_used": 30},
            {"content": "BEAR: Risk of reversal", "tokens_used": 30},
            {"content": "SYNTHESIS: Proceed with caution, set tight stop loss. "
                       "Confidence: 65%", "tokens_used": 50},
        ]

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 70}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        assert result.synthesis is not None
        assert result.confidence >= 0 and result.confidence <= 100

    @pytest.mark.asyncio
    async def test_debate_records_reasoning_chain(self):
        """Debate should record full reasoning chain for compliance."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.return_value = {"content": "Analysis", "tokens_used": 50}

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 70}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        assert result.reasoning_chain is not None
        assert isinstance(result.reasoning_chain, list)
        # Should have at least bull, bear, synthesis steps
        assert len(result.reasoning_chain) >= 3


class TestDebateDecision:
    """Test debate decision output."""

    def test_trade_decision_has_required_fields(self):
        """TradeDecision should have all required fields."""
        from core.ai.debate_orchestrator import TradeDecision

        decision = TradeDecision(
            recommendation="BUY",
            confidence=75.0,
            bull_case="Strong momentum",
            bear_case="Risk of reversal",
            synthesis="Proceed with reduced size",
            reasoning_chain=["Step 1", "Step 2"],
        )

        assert decision.recommendation in ["BUY", "SELL", "HOLD"]
        assert 0 <= decision.confidence <= 100
        assert decision.bull_case is not None
        assert decision.bear_case is not None
        assert decision.synthesis is not None

    def test_trade_decision_to_dict(self):
        """TradeDecision should serialize to dict."""
        from core.ai.debate_orchestrator import TradeDecision

        decision = TradeDecision(
            recommendation="BUY",
            confidence=75.0,
            bull_case="Strong momentum",
            bear_case="Risk of reversal",
            synthesis="Proceed with reduced size",
            reasoning_chain=["Step 1"],
        )

        data = decision.to_dict()

        assert data["recommendation"] == "BUY"
        assert data["confidence"] == 75.0
        assert "bull_case" in data
        assert "bear_case" in data

    def test_trade_decision_should_execute(self):
        """Decision should indicate if trade should execute."""
        from core.ai.debate_orchestrator import TradeDecision

        high_confidence = TradeDecision(
            recommendation="BUY",
            confidence=85.0,
            bull_case="",
            bear_case="",
            synthesis="",
        )

        low_confidence = TradeDecision(
            recommendation="BUY",
            confidence=55.0,
            bull_case="",
            bear_case="",
            synthesis="",
        )

        assert high_confidence.should_execute(min_confidence=70) is True
        assert low_confidence.should_execute(min_confidence=70) is False


class TestDebateThresholds:
    """Test debate triggering thresholds."""

    @pytest.mark.asyncio
    async def test_debate_triggers_above_confidence_threshold(self):
        """Debate should trigger for high-confidence signals."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.return_value = {"content": "Analysis", "tokens_used": 50}

        orchestrator = DebateOrchestrator(client=mock_client, debate_threshold=60)

        # High confidence signal - should trigger debate
        signal = {"direction": "BUY", "confidence": 75}
        market_data = {"symbol": "BONK", "price": 0.00001234}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Debate should have been conducted
        assert result.debate_conducted is True

    @pytest.mark.asyncio
    async def test_low_confidence_skips_debate(self):
        """Low confidence signals should skip debate and default to HOLD."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        orchestrator = DebateOrchestrator(client=mock_client, debate_threshold=60)

        # Low confidence signal - should skip debate
        signal = {"direction": "BUY", "confidence": 45}
        market_data = {"symbol": "BONK", "price": 0.00001234}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Debate should have been skipped
        assert result.debate_conducted is False
        assert result.recommendation == "HOLD"


class TestDebateWithSignals:
    """Test debate integration with trading signals."""

    @pytest.mark.asyncio
    async def test_debate_includes_technical_signals(self):
        """Debate should incorporate technical indicator signals."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()

        # Track the prompts sent to verify signals are included
        prompts_received = []

        async def capture_generate(persona, context):
            prompts_received.append(context)
            return {"content": "Analysis with signals", "tokens_used": 50}

        mock_client.generate = capture_generate

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signals = {
            "direction": "BUY",
            "confidence": 75,
            "rsi": 32,
            "macd": "bullish_crossover",
            "volume_surge": True,
        }

        await orchestrator.evaluate_trade(signal=signals, market_data=market_data)

        # Verify technical signals were passed to AI
        all_prompts = " ".join(str(p) for p in prompts_received)
        assert "32" in all_prompts or "rsi" in all_prompts.lower()

    @pytest.mark.asyncio
    async def test_debate_includes_sentiment_data(self):
        """Debate should incorporate sentiment data."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        prompts_received = []

        async def capture_generate(persona, context):
            prompts_received.append(context)
            return {"content": "Sentiment analysis", "tokens_used": 50}

        mock_client.generate = capture_generate

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {
            "symbol": "BONK",
            "price": 0.00001234,
            "sentiment_score": 78,
            "sentiment_grade": "A",
        }
        signal = {"direction": "BUY", "confidence": 70}

        await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        all_prompts = " ".join(str(p) for p in prompts_received)
        assert "78" in all_prompts or "sentiment" in all_prompts.lower()


class TestDebateCostTracking:
    """Test debate API cost tracking."""

    @pytest.mark.asyncio
    async def test_tracks_total_tokens_used(self):
        """Orchestrator should track total tokens across debate."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.side_effect = [
            {"content": "Bull", "tokens_used": 100},
            {"content": "Bear", "tokens_used": 150},
            {"content": "Synthesis", "tokens_used": 200},
        ]

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 75}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        assert result.tokens_used == 450  # 100 + 150 + 200

    @pytest.mark.asyncio
    async def test_respects_max_cost_limit(self):
        """Orchestrator should abort if cost exceeds limit."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.return_value = {"content": "Analysis", "tokens_used": 10000}

        orchestrator = DebateOrchestrator(
            client=mock_client,
            max_tokens_per_debate=500  # Low limit
        )

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 75}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should either limit or abort - not exceed
        assert result.tokens_used <= 500 or result.recommendation == "HOLD"


class TestParallelDebate:
    """Test parallel debate generation."""

    @pytest.mark.asyncio
    async def test_bull_bear_generated_in_parallel(self):
        """Bull and Bear cases should be generated concurrently."""
        from core.ai.debate_orchestrator import DebateOrchestrator
        import asyncio

        call_times = []

        async def slow_generate(persona, context):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate API latency
            return {"content": f"{persona} analysis", "tokens_used": 50}

        mock_client = AsyncMock()
        mock_client.generate = slow_generate

        orchestrator = DebateOrchestrator(client=mock_client, parallel=True)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 75}

        start = asyncio.get_event_loop().time()
        await orchestrator.evaluate_trade(signal=signal, market_data=market_data)
        duration = asyncio.get_event_loop().time() - start

        # If parallel, should take ~0.1s (+ synthesis), not ~0.2s+
        # Allow some margin for test environment
        if len(call_times) >= 2:
            time_diff = abs(call_times[1] - call_times[0])
            # If parallel, calls should start within 0.05s of each other
            assert time_diff < 0.05


class TestDebateErrorHandling:
    """Test debate error handling."""

    @pytest.mark.asyncio
    async def test_handles_client_error_gracefully(self):
        """Should return HOLD recommendation on API error."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.side_effect = Exception("API Error")

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 75}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should default to HOLD on error (graceful degradation)
        assert result.recommendation == "HOLD"
        # Errors are captured in the bull/bear cases, synthesis falls back to rule-based
        assert "failed" in result.bull_case.lower() or "error" in result.bull_case.lower()

    @pytest.mark.asyncio
    async def test_handles_partial_failure(self):
        """Should handle partial debate failure gracefully."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        call_count = 0

        async def partial_fail(persona, context):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on bear case
                raise Exception("Bear API failed")
            return {"content": "Analysis", "tokens_used": 50}

        mock_client.generate = partial_fail

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "BONK", "price": 0.00001234}
        signal = {"direction": "BUY", "confidence": 75}

        result = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should still return a result, even if degraded
        assert result is not None
        assert result.recommendation in ["BUY", "SELL", "HOLD"]
