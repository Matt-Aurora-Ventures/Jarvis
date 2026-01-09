"""
Tests for X Sentiment plugin.

Tests cover:
- Plugin lifecycle
- PAE component registration
- Action functionality
- Provider functionality
- Evaluator functionality
"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import plugin components directly for testing
from plugins.x_sentiment.main import (
    XSentimentPlugin,
    AnalyzeSentimentAction,
    AnalyzeCryptoAction,
    AnalyzeTrendAction,
    SentimentProvider,
    TrendProvider,
    SentimentEvaluator,
)
from lifeos.pae.base import EvaluationResult


# Mock sentiment result for testing
@dataclass
class MockSentimentResult:
    text: str
    sentiment: str
    confidence: float
    key_topics: List[str]
    emotional_tone: str
    market_relevance: Optional[str] = None


@dataclass
class MockTrendAnalysis:
    topic: str
    sentiment: str
    volume: str
    key_drivers: List[str]
    notable_voices: List[str]
    market_impact: Optional[str] = None


# =============================================================================
# Test Actions
# =============================================================================

class TestAnalyzeSentimentAction:
    """Test analyze sentiment action."""

    @pytest.mark.asyncio
    async def test_requires_text(self):
        """Should require text parameter."""
        action = AnalyzeSentimentAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_returns_error_without_analyzer(self):
        """Should return error when analyzer not initialized."""
        action = AnalyzeSentimentAction("test", {})

        result = await action.execute({"text": "Test message"})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyzes_sentiment(self):
        """Should analyze sentiment successfully."""
        action = AnalyzeSentimentAction("test", {"default_focus": "trading"})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_sentiment = MagicMock(return_value=MockSentimentResult(
            text="BTC is mooning!",
            sentiment="positive",
            confidence=0.85,
            key_topics=["bitcoin", "price"],
            emotional_tone="excited",
            market_relevance="bullish",
        ))
        action.set_analyzer(mock_analyzer)

        result = await action.execute({"text": "BTC is mooning!"})

        assert result["success"] is True
        assert result["sentiment"] == "positive"
        assert result["confidence"] == 0.85
        assert "bitcoin" in result["key_topics"]

    @pytest.mark.asyncio
    async def test_handles_none_result(self):
        """Should handle None result from analyzer."""
        action = AnalyzeSentimentAction("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_sentiment = MagicMock(return_value=None)
        action.set_analyzer(mock_analyzer)

        result = await action.execute({"text": "Some text"})

        assert result["success"] is False


class TestAnalyzeCryptoAction:
    """Test analyze crypto action."""

    @pytest.mark.asyncio
    async def test_requires_symbol(self):
        """Should require symbol parameter."""
        action = AnalyzeCryptoAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_analyzes_crypto(self):
        """Should analyze crypto sentiment."""
        action = AnalyzeCryptoAction("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "symbol": "SOL",
            "sentiment": "bullish",
            "sentiment_strength": 75,
        })
        action.set_analyzer(mock_analyzer)

        result = await action.execute({"symbol": "SOL"})

        assert result["success"] is True
        assert result["symbol"] == "SOL"
        assert result["data"]["sentiment"] == "bullish"


class TestAnalyzeTrendAction:
    """Test analyze trend action."""

    @pytest.mark.asyncio
    async def test_requires_topic(self):
        """Should require topic parameter."""
        action = AnalyzeTrendAction("test", {})

        with pytest.raises(ValueError):
            await action.execute({})

    @pytest.mark.asyncio
    async def test_analyzes_trend(self):
        """Should analyze trends."""
        action = AnalyzeTrendAction("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_trend = MagicMock(return_value=MockTrendAnalysis(
            topic="$BTC",
            sentiment="positive",
            volume="high",
            key_drivers=["ETF approval", "institutional buying"],
            notable_voices=["@whale1", "@analyst2"],
            market_impact="bullish breakout expected",
        ))
        action.set_analyzer(mock_analyzer)

        result = await action.execute({"topic": "$BTC"})

        assert result["success"] is True
        assert result["topic"] == "$BTC"
        assert result["volume"] == "high"
        assert "ETF approval" in result["key_drivers"]


# =============================================================================
# Test Providers
# =============================================================================

class TestSentimentProvider:
    """Test sentiment provider."""

    @pytest.mark.asyncio
    async def test_returns_unavailable_without_analyzer(self):
        """Should return unavailable without analyzer."""
        provider = SentimentProvider("test", {})

        result = await provider.provide({"text": "Hello"})

        assert result["available"] is False

    @pytest.mark.asyncio
    async def test_provides_text_sentiment(self):
        """Should provide text sentiment."""
        provider = SentimentProvider("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_sentiment = MagicMock(return_value=MockSentimentResult(
            text="Test",
            sentiment="neutral",
            confidence=0.7,
            key_topics=["test"],
            emotional_tone="calm",
        ))
        provider.set_analyzer(mock_analyzer)

        result = await provider.provide({"text": "Test"})

        assert result["available"] is True
        assert result["text_sentiment"]["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_provides_crypto_sentiment(self):
        """Should provide crypto sentiment."""
        provider = SentimentProvider("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_sentiment = MagicMock(return_value=None)
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "symbol": "ETH",
            "sentiment": "bullish",
        })
        provider.set_analyzer(mock_analyzer)

        result = await provider.provide({"symbol": "ETH"})

        assert result["available"] is True
        assert result["crypto_sentiment"]["sentiment"] == "bullish"


class TestTrendProvider:
    """Test trend provider."""

    @pytest.mark.asyncio
    async def test_requires_topic(self):
        """Should require topic."""
        provider = TrendProvider("test", {})

        result = await provider.provide({})

        assert result["available"] is False
        assert "topic is required" in result["error"]

    @pytest.mark.asyncio
    async def test_provides_trend_data(self):
        """Should provide trend data."""
        provider = TrendProvider("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_trend = MagicMock(return_value=MockTrendAnalysis(
            topic="AI",
            sentiment="positive",
            volume="viral",
            key_drivers=["GPT-5 rumors"],
            notable_voices=["@openai"],
        ))
        provider.set_analyzer(mock_analyzer)

        result = await provider.provide({"topic": "AI"})

        assert result["available"] is True
        assert result["volume"] == "viral"


# =============================================================================
# Test Evaluators
# =============================================================================

class TestSentimentEvaluator:
    """Test sentiment evaluator."""

    @pytest.mark.asyncio
    async def test_requires_symbol(self):
        """Should require symbol."""
        evaluator = SentimentEvaluator("test", {})

        result = await evaluator.evaluate({})

        assert result.decision is False
        assert "No symbol" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluates_bullish_sentiment(self):
        """Should evaluate bullish sentiment correctly."""
        evaluator = SentimentEvaluator("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "sentiment": "bullish",
            "sentiment_strength": 80,
        })
        evaluator.set_analyzer(mock_analyzer)

        result = await evaluator.evaluate({
            "symbol": "SOL",
            "required_sentiment": "bullish",
            "min_confidence": 0.6,
        })

        assert result.decision is True
        assert result.confidence == 0.8
        assert isinstance(result, EvaluationResult)

    @pytest.mark.asyncio
    async def test_rejects_wrong_sentiment(self):
        """Should reject when sentiment doesn't match."""
        evaluator = SentimentEvaluator("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "sentiment": "bearish",
            "sentiment_strength": 70,
        })
        evaluator.set_analyzer(mock_analyzer)

        result = await evaluator.evaluate({
            "symbol": "BTC",
            "required_sentiment": "bullish",
            "min_confidence": 0.5,
        })

        assert result.decision is False

    @pytest.mark.asyncio
    async def test_rejects_low_confidence(self):
        """Should reject when confidence is too low."""
        evaluator = SentimentEvaluator("test", {})

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "sentiment": "bullish",
            "sentiment_strength": 40,  # 40% strength
        })
        evaluator.set_analyzer(mock_analyzer)

        result = await evaluator.evaluate({
            "symbol": "SOL",
            "required_sentiment": "bullish",
            "min_confidence": 0.6,  # Requires 60%
        })

        assert result.decision is False


# =============================================================================
# Test Plugin Integration
# =============================================================================

class TestXSentimentPluginIntegration:
    """Integration tests for X Sentiment plugin."""

    @pytest.fixture
    def mock_context(self):
        """Create mock plugin context."""
        context = MagicMock()
        context.config = {
            "default_focus": "trading",
        }

        # Mock jarvis with PAE registry
        mock_jarvis = MagicMock()
        mock_jarvis.pae = MagicMock()
        mock_jarvis.pae.register_provider = MagicMock()
        mock_jarvis.pae.register_action = MagicMock()
        mock_jarvis.pae.register_evaluator = MagicMock()

        # Mock event bus
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        mock_event_bus.on = MagicMock(return_value=lambda f: f)

        context.services = {
            "jarvis": mock_jarvis,
            "event_bus": mock_event_bus,
        }

        return context

    @pytest.fixture
    def mock_manifest(self):
        """Create mock plugin manifest."""
        manifest = MagicMock()
        manifest.name = "x_sentiment"
        manifest.version = "1.0.0"
        return manifest

    @pytest.mark.asyncio
    async def test_plugin_loads(self, mock_context, mock_manifest):
        """Should load without errors."""
        plugin = XSentimentPlugin(mock_context, mock_manifest)
        await plugin.on_load()

        # Should register components
        assert mock_context.services["jarvis"].pae.register_action.called
        assert mock_context.services["jarvis"].pae.register_provider.called
        assert mock_context.services["jarvis"].pae.register_evaluator.called

    @pytest.mark.asyncio
    async def test_plugin_enable_disable(self, mock_context, mock_manifest):
        """Should enable and disable cleanly."""
        plugin = XSentimentPlugin(mock_context, mock_manifest)

        await plugin.on_load()
        await plugin.on_enable()

        # Should emit enabled event
        event_bus = mock_context.services["event_bus"]
        assert event_bus.emit.called

        await plugin.on_disable()

        # Should emit disabled event
        calls = [call[0][0] for call in event_bus.emit.call_args_list]
        assert "x_sentiment.disabled" in calls

    @pytest.mark.asyncio
    async def test_plugin_api_methods(self, mock_context, mock_manifest):
        """Should expose API methods."""
        plugin = XSentimentPlugin(mock_context, mock_manifest)

        # Create mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_sentiment = MagicMock(return_value=MockSentimentResult(
            text="Test",
            sentiment="positive",
            confidence=0.8,
            key_topics=["test"],
            emotional_tone="upbeat",
        ))
        mock_analyzer.analyze_crypto_sentiment = MagicMock(return_value={
            "sentiment": "bullish",
        })
        mock_analyzer.analyze_trend = MagicMock(return_value=MockTrendAnalysis(
            topic="crypto",
            sentiment="positive",
            volume="high",
            key_drivers=["adoption"],
            notable_voices=["@expert"],
        ))

        plugin._analyzer = mock_analyzer

        # Test analyze_sentiment
        result = plugin.analyze_sentiment("Test text")
        assert result["sentiment"] == "positive"

        # Test analyze_crypto
        result = plugin.analyze_crypto("SOL")
        assert result["sentiment"] == "bullish"

        # Test analyze_trend
        result = plugin.analyze_trend("crypto")
        assert result["volume"] == "high"

        # Test is_available
        assert plugin.is_available() is True

    @pytest.mark.asyncio
    async def test_plugin_without_analyzer(self, mock_context, mock_manifest):
        """Should handle missing analyzer gracefully."""
        plugin = XSentimentPlugin(mock_context, mock_manifest)
        plugin._analyzer = None

        assert plugin.analyze_sentiment("test") is None
        assert plugin.analyze_crypto("BTC") is None
        assert plugin.analyze_trend("AI") is None
        assert plugin.is_available() is False

    @pytest.mark.asyncio
    async def test_plugin_unload(self, mock_context, mock_manifest):
        """Should clean up on unload."""
        plugin = XSentimentPlugin(mock_context, mock_manifest)

        mock_analyzer = MagicMock()
        plugin._analyzer = mock_analyzer

        await plugin.on_unload()

        assert plugin._analyzer is None
        assert len(plugin._actions) == 0
        assert len(plugin._providers) == 0
        assert len(plugin._evaluators) == 0
