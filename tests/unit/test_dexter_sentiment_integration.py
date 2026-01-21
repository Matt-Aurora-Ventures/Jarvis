"""
Tests for Dexter (Claude CLI) integration with JARVIS sentiment analysis.

Tests cover:
- Querying sentiment data via CLI
- Triggering sentiment analysis via CLI
- Context engine timing controls
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class TestDexterSentimentQuery:
    """Tests for querying sentiment data via Dexter CLI."""

    @pytest.fixture
    def mock_sentiment_service(self):
        """Create a mock sentiment service."""
        service = MagicMock()
        service.get_latest_report = MagicMock(return_value={
            "tokens": [
                {"symbol": "BONK", "sentiment": "bullish", "score": 0.75},
                {"symbol": "WIF", "sentiment": "neutral", "score": 0.5},
            ],
            "generated_at": "2026-01-21T10:00:00",
            "market_regime": "BULL"
        })
        service.get_token_sentiment = MagicMock(return_value={
            "symbol": "BONK",
            "sentiment": "bullish",
            "score": 0.75,
            "change_24h": 15.5,
            "volume_24h": 1000000
        })
        return service

    def test_query_latest_sentiment_report(self, mock_sentiment_service):
        """Test querying the latest sentiment report."""
        from core.dexter_sentiment import DexterSentimentBridge

        # Ensure get_cached_report returns None so get_latest_report is used
        mock_sentiment_service.get_cached_report = MagicMock(return_value=None)

        bridge = DexterSentimentBridge(sentiment_service=mock_sentiment_service)
        result = bridge.get_latest_report()

        assert result is not None
        assert "tokens" in result
        assert len(result["tokens"]) == 2
        assert result["market_regime"] == "BULL"

    def test_query_token_sentiment(self, mock_sentiment_service):
        """Test querying sentiment for a specific token."""
        from core.dexter_sentiment import DexterSentimentBridge

        bridge = DexterSentimentBridge(sentiment_service=mock_sentiment_service)
        result = bridge.get_token_sentiment("BONK")

        assert result is not None
        assert result["symbol"] == "BONK"
        assert result["sentiment"] == "bullish"
        assert result["score"] == 0.75

    def test_query_nonexistent_token(self, mock_sentiment_service):
        """Test querying sentiment for a nonexistent token."""
        mock_sentiment_service.get_token_sentiment = MagicMock(return_value=None)

        from core.dexter_sentiment import DexterSentimentBridge

        bridge = DexterSentimentBridge(sentiment_service=mock_sentiment_service)
        result = bridge.get_token_sentiment("NONEXISTENT")

        assert result is None


class TestDexterSentimentTrigger:
    """Tests for triggering sentiment analysis via Dexter CLI."""

    @pytest.fixture
    def mock_context_engine(self):
        """Create a mock context engine."""
        engine = MagicMock()
        engine.can_run_sentiment = MagicMock(return_value=True)
        engine.record_sentiment_run = MagicMock()
        return engine

    @pytest.fixture
    def mock_sentiment_generator(self):
        """Create a mock sentiment generator."""
        generator = AsyncMock()
        generator.generate_and_post_report = AsyncMock(return_value=True)
        return generator

    @pytest.mark.asyncio
    async def test_trigger_sentiment_when_allowed(self, mock_context_engine, mock_sentiment_generator):
        """Test triggering sentiment analysis when context allows."""
        from core.dexter_sentiment import DexterSentimentBridge

        bridge = DexterSentimentBridge(
            context_engine=mock_context_engine,
            sentiment_generator=mock_sentiment_generator
        )

        success, message = await bridge.trigger_sentiment_analysis()

        assert success is True
        assert "triggered" in message.lower() or "started" in message.lower()
        mock_context_engine.can_run_sentiment.assert_called_once()
        mock_sentiment_generator.generate_and_post_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_sentiment_blocked_by_timing(self, mock_context_engine, mock_sentiment_generator):
        """Test that sentiment analysis is blocked when timing doesn't allow."""
        mock_context_engine.can_run_sentiment = MagicMock(return_value=False)

        from core.dexter_sentiment import DexterSentimentBridge

        bridge = DexterSentimentBridge(
            context_engine=mock_context_engine,
            sentiment_generator=mock_sentiment_generator
        )

        success, message = await bridge.trigger_sentiment_analysis()

        assert success is False
        assert "blocked" in message.lower() or "wait" in message.lower() or "timing" in message.lower()
        mock_sentiment_generator.generate_and_post_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_sentiment_force_override(self, mock_context_engine, mock_sentiment_generator):
        """Test forcing sentiment analysis even when timing blocks."""
        mock_context_engine.can_run_sentiment = MagicMock(return_value=False)

        from core.dexter_sentiment import DexterSentimentBridge

        bridge = DexterSentimentBridge(
            context_engine=mock_context_engine,
            sentiment_generator=mock_sentiment_generator
        )

        success, message = await bridge.trigger_sentiment_analysis(force=True)

        assert success is True
        mock_sentiment_generator.generate_and_post_report.assert_called_once()


class TestContextEngineIntegration:
    """Tests for context engine timing controls."""

    def test_context_engine_can_run_sentiment_fresh(self):
        """Test that sentiment can run when no previous run exists."""
        from core.context_engine import ContextEngine

        # Create fresh engine with clean state
        with patch('core.context_engine.os.path.exists', return_value=False):
            engine = ContextEngine.__new__(ContextEngine)
            engine._initialized = False
            engine.__init__()

        assert engine.can_run_sentiment() is True

    def test_context_engine_blocks_recent_run(self):
        """Test that sentiment is blocked after recent run."""
        from core.context_engine import ContextEngine

        mock_state = {
            "last_sentiment_report": datetime.now().isoformat(),
            "sentiment_cache_valid": True
        }

        with patch('core.context_engine.os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock()):
                with patch('json.load', return_value=mock_state):
                    engine = ContextEngine.__new__(ContextEngine)
                    engine._initialized = False
                    engine.__init__()

        assert engine.can_run_sentiment(min_interval_hours=4) is False

    def test_context_engine_allows_after_interval(self):
        """Test that sentiment is allowed after the interval passes."""
        from core.context_engine import ContextEngine

        old_time = (datetime.now() - timedelta(hours=5)).isoformat()
        mock_state = {
            "last_sentiment_report": old_time,
            "sentiment_cache_valid": True
        }

        with patch('core.context_engine.os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock()):
                with patch('json.load', return_value=mock_state):
                    engine = ContextEngine.__new__(ContextEngine)
                    engine._initialized = False
                    engine.__init__()

        assert engine.can_run_sentiment(min_interval_hours=4) is True


class TestCLICommandHandling:
    """Tests for CLI command handling of sentiment commands."""

    @pytest.fixture
    def mock_cli_handler(self):
        """Create a mock CLI handler."""
        from bots.twitter.x_claude_cli_handler import XClaudeCLIHandler

        handler = MagicMock(spec=XClaudeCLIHandler)
        handler.execute_command = AsyncMock()
        return handler

    def test_sentiment_command_detection(self):
        """Test that sentiment-related commands are detected."""
        from core.dexter_sentiment import is_sentiment_command

        assert is_sentiment_command("get sentiment report") is True
        assert is_sentiment_command("show me the sentiment") is True
        assert is_sentiment_command("run sentiment analysis") is True
        assert is_sentiment_command("trigger sentiment") is True
        assert is_sentiment_command("what's the market sentiment") is True

        # Should not match non-sentiment commands
        assert is_sentiment_command("check my balance") is False
        assert is_sentiment_command("buy some tokens") is False

    @pytest.mark.asyncio
    async def test_sentiment_command_routing(self):
        """Test that sentiment commands are routed to the bridge."""
        from core.dexter_sentiment import DexterSentimentBridge, handle_sentiment_command

        mock_bridge = MagicMock()
        mock_bridge.get_latest_report = MagicMock(return_value={"tokens": []})

        result = await handle_sentiment_command("get sentiment report", bridge=mock_bridge)

        assert result is not None
        mock_bridge.get_latest_report.assert_called_once()


class TestSentimentDataFormatting:
    """Tests for formatting sentiment data for CLI output."""

    def test_format_sentiment_report_for_cli(self):
        """Test formatting a sentiment report for CLI display."""
        from core.dexter_sentiment import format_sentiment_for_cli

        report = {
            "tokens": [
                {"symbol": "BONK", "sentiment": "bullish", "score": 0.75, "change_24h": 15.5},
                {"symbol": "WIF", "sentiment": "bearish", "score": 0.25, "change_24h": -8.2},
            ],
            "market_regime": "BULL",
            "generated_at": "2026-01-21T10:00:00"
        }

        formatted = format_sentiment_for_cli(report)

        assert "BONK" in formatted
        assert "bullish" in formatted.lower()
        assert "WIF" in formatted
        assert "bearish" in formatted.lower()
        assert "BULL" in formatted

    def test_format_token_sentiment_for_cli(self):
        """Test formatting a single token's sentiment for CLI display."""
        from core.dexter_sentiment import format_token_sentiment_for_cli

        token_data = {
            "symbol": "BONK",
            "sentiment": "bullish",
            "score": 0.75,
            "change_24h": 15.5,
            "volume_24h": 1000000
        }

        formatted = format_token_sentiment_for_cli(token_data)

        assert "BONK" in formatted
        assert "bullish" in formatted.lower()
        assert "0.75" in formatted or "75" in formatted


class TestSentimentCaching:
    """Tests for sentiment caching behavior."""

    def test_cached_sentiment_returned_when_valid(self):
        """Test that cached sentiment is returned when still valid."""
        from core.dexter_sentiment import DexterSentimentBridge

        mock_service = MagicMock()
        cached_report = {"tokens": [], "cached": True, "generated_at": datetime.now().isoformat()}
        mock_service.get_cached_report = MagicMock(return_value=cached_report)

        bridge = DexterSentimentBridge(sentiment_service=mock_service)
        result = bridge.get_latest_report(use_cache=True)

        assert result is not None
        assert result.get("cached") is True

    def test_fresh_sentiment_when_cache_invalid(self):
        """Test that fresh sentiment is fetched when cache is invalid."""
        from core.dexter_sentiment import DexterSentimentBridge

        mock_service = MagicMock()
        mock_service.get_cached_report = MagicMock(return_value=None)
        fresh_report = {"tokens": [], "cached": False, "generated_at": datetime.now().isoformat()}
        mock_service.get_latest_report = MagicMock(return_value=fresh_report)

        bridge = DexterSentimentBridge(sentiment_service=mock_service)
        result = bridge.get_latest_report(use_cache=True)

        assert result is not None
        assert result.get("cached") is False
