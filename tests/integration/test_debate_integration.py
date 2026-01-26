"""
Integration Tests for Bull/Bear Debate Architecture

Tests end-to-end debate evaluation flow including:
- Orchestrator with mock AI client
- Reasoning storage and retrieval
- Telegram UI formatting
"""

import pytest
import tempfile
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime


class TestDebateEndToEnd:
    """Test full debate flow."""

    @pytest.mark.asyncio
    async def test_full_debate_flow(self):
        """Test complete debate evaluation and storage."""
        from core.ai.debate_orchestrator import DebateOrchestrator, TradeDecision
        from core.reasoning_store import ReasoningStore

        # Create mock AI client
        mock_client = AsyncMock()
        call_count = [0]

        async def mock_generate(persona, context):
            call_count[0] += 1
            if "Bull" in str(persona):
                return {
                    "content": "Strong momentum, volume surge, bullish sentiment. "
                              "Entry point at support. RECOMMENDATION: BUY. CONFIDENCE: 78%",
                    "tokens_used": 100,
                }
            elif "Bear" in str(persona):
                return {
                    "content": "RSI overbought, resistance ahead, profit taking likely. "
                              "RECOMMENDATION: HOLD. CONFIDENCE: 65%",
                    "tokens_used": 100,
                }
            else:
                return {
                    "content": "RECOMMENDATION: BUY\nCONFIDENCE: 72%\n"
                              "REASONING: Bull momentum outweighs bear concerns.",
                    "tokens_used": 100,
                }

        mock_client.generate = mock_generate

        # Initialize orchestrator
        orchestrator = DebateOrchestrator(
            client=mock_client,
            debate_threshold=60,
            parallel=False,  # Sequential for predictable test
        )

        # Run debate
        market_data = {
            "symbol": "BONK",
            "price": 0.00001234,
            "change_24h": 15.5,
            "volume_24h": 1500000,
            "sentiment_score": 72,
        }
        signal = {"direction": "BUY", "confidence": 75}

        decision = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Verify debate was conducted
        assert decision.debate_conducted is True
        assert decision.recommendation in ["BUY", "SELL", "HOLD"]
        assert decision.confidence > 0
        assert len(decision.reasoning_chain) >= 3  # Bull, Bear, Synthesis

        # Store reasoning
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ReasoningStore(data_dir=tmpdir)

            result = store.store({
                "debate_id": decision.debate_id,
                "symbol": market_data["symbol"],
                "recommendation": decision.recommendation,
                "confidence": decision.confidence,
                "bull_case": decision.bull_case,
                "bear_case": decision.bear_case,
            })

            assert result.success is True

            # Retrieve and verify
            retrieved = store.get(result.chain_id)
            assert retrieved is not None
            assert retrieved["symbol"] == "BONK"

    @pytest.mark.asyncio
    async def test_debate_integration_with_evaluator(self):
        """Test TradingDebateEvaluator integration."""
        from core.ai.debate_integration import TradingDebateEvaluator

        # Create mock client
        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: BUY\nCONFIDENCE: 75%",
            "tokens_used": 50,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch the reasoning store path
            with patch("core.ai.debate_integration.ReasoningStore") as MockStore:
                mock_store = Mock()
                mock_store.store.return_value = Mock(success=True, chain_id="test123")
                MockStore.return_value = mock_store

                evaluator = TradingDebateEvaluator(
                    enabled=True,
                    min_confidence_for_debate=60,
                    store_reasoning=True,
                )
                evaluator.client = mock_client
                evaluator.orchestrator.client = mock_client

                # Evaluate signal
                signal = {"direction": "BUY", "confidence": 70}
                market_data = {"symbol": "WIF", "price": 2.50}

                decision, should_execute = await evaluator.evaluate_signal(
                    signal=signal,
                    market_data=market_data,
                )

                assert decision is not None
                assert isinstance(should_execute, bool)


class TestDebateTelegramUI:
    """Test Telegram UI formatting."""

    def test_format_debate_summary(self):
        """Test debate summary formatting."""
        from tg_bot.handlers.demo.callbacks.debate import format_debate_summary

        decision = {
            "recommendation": "BUY",
            "confidence": 75.0,
            "bull_case": "Strong momentum and volume surge.",
            "bear_case": "Minor resistance ahead.",
            "synthesis": "Bull case stronger, proceed with position.",
        }

        summary = format_debate_summary(decision)

        assert "BUY" in summary
        assert "75" in summary  # 75.0 rounds to 75%
        assert "momentum" in summary.lower()
        assert "resistance" in summary.lower()


class TestDebateWithRealData:
    """Test debate with realistic market data."""

    @pytest.mark.asyncio
    async def test_debate_with_full_market_context(self):
        """Test debate with comprehensive market data."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        mock_client.generate.return_value = {
            "content": "RECOMMENDATION: HOLD\nCONFIDENCE: 55%\n"
                      "REASONING: Mixed signals, wait for confirmation.",
            "tokens_used": 80,
        }

        orchestrator = DebateOrchestrator(client=mock_client, debate_threshold=50)

        # Comprehensive market data
        market_data = {
            "symbol": "JUP",
            "price": 0.85,
            "change_24h": -3.2,
            "change_1h": 1.5,
            "volume_24h": 25000000,
            "market_cap": 1200000000,
            "fdv": 1500000000,
            "liquidity": 8000000,
            "holder_count": 150000,
            "sentiment_score": 58,
            "sentiment_grade": "B-",
        }

        signal = {
            "direction": "BUY",
            "confidence": 62,
            "rsi": 48,
            "macd": "neutral",
            "volume_surge": False,
        }

        decision = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should result in cautious decision given mixed signals
        assert decision.recommendation in ["BUY", "SELL", "HOLD"]
        assert decision.debate_conducted is True


class TestDebateErrorRecovery:
    """Test debate error recovery."""

    @pytest.mark.asyncio
    async def test_recovers_from_api_timeout(self):
        """Test recovery from API timeout."""
        import asyncio
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()

        async def slow_generate(persona, context):
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError("API timeout")

        mock_client.generate = slow_generate

        orchestrator = DebateOrchestrator(client=mock_client)

        market_data = {"symbol": "TEST", "price": 1.0}
        signal = {"direction": "BUY", "confidence": 75}

        decision = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should return safe HOLD on timeout
        assert decision.recommendation == "HOLD"

    @pytest.mark.asyncio
    async def test_continues_with_partial_data(self):
        """Test continues when one analyst fails."""
        from core.ai.debate_orchestrator import DebateOrchestrator

        mock_client = AsyncMock()
        call_count = [0]

        async def partial_fail(persona, context):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call (bear) fails
                raise Exception("Bear API unavailable")
            return {"content": "Analysis complete", "tokens_used": 50}

        mock_client.generate = partial_fail

        orchestrator = DebateOrchestrator(client=mock_client, parallel=False)

        market_data = {"symbol": "TEST", "price": 1.0}
        signal = {"direction": "BUY", "confidence": 75}

        decision = await orchestrator.evaluate_trade(signal=signal, market_data=market_data)

        # Should still return a decision
        assert decision is not None
        assert decision.recommendation in ["BUY", "SELL", "HOLD"]
