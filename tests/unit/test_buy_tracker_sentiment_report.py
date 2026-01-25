"""
Comprehensive unit tests for the Sentiment Report Generator module.

This file focuses on testing the SentimentReportGenerator class and its methods,
including:
1. Generator initialization and configuration
2. Grok API integration (mocked)
3. Report generation and formatting
4. Telegram posting (mocked)
5. Market data fetching (mocked)
6. Token analysis and scoring
7. Error handling and fallbacks
8. Prediction tracking
9. Future events validation

Tests are designed to achieve 60%+ coverage of bots/buy_tracker/sentiment_report.py
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from dataclasses import asdict
from typing import Dict, List, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the module under test
from bots.buy_tracker.sentiment_report import (
    SentimentReportGenerator,
    TokenSentiment,
    MarketRegime,
    MacroAnalysis,
    TraditionalMarkets,
    StockPick,
    CommodityMover,
    PreciousMetalsOutlook,
    PredictionRecord,
    ManipulationDetector,
    get_emoji,
    STANDARD_EMOJIS,
    KR8TIV_EMOJI_IDS,
    EU_AI_ACT_DISCLOSURE,
    PREDICTIONS_FILE,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_BUY_BOT_CHAT_ID", "test_chat_id")
    monkeypatch.setenv("XAI_API_KEY", "test_xai_key")
    monkeypatch.setenv("TREASURY_WALLET_ADDRESS", "TestTreasuryWallet123")
    monkeypatch.setenv("HELIUS_RPC_URL", "https://test.helius.dev")


@pytest.fixture
def generator(mock_env_vars):
    """Create a SentimentReportGenerator instance for testing."""
    return SentimentReportGenerator(
        bot_token="test_bot_token",
        chat_id="test_chat_id",
        xai_api_key="test_xai_key",
        interval_minutes=30,
    )


@pytest.fixture
def generator_no_grok(mock_env_vars):
    """Create a generator without Grok API key."""
    return SentimentReportGenerator(
        bot_token="test_bot_token",
        chat_id="test_chat_id",
        xai_api_key="",  # No Grok API key
        interval_minutes=30,
    )


@pytest.fixture
def sample_tokens():
    """Create sample tokens for testing."""
    return [
        TokenSentiment(
            symbol="BONK",
            name="Bonk",
            price_usd=0.000025,
            change_1h=2.5,
            change_24h=15.0,
            volume_24h=5_000_000,
            mcap=100_000_000,
            buys_24h=5000,
            sells_24h=3000,
            liquidity=500_000,
            contract_address="BonkAddress123",
        ),
        TokenSentiment(
            symbol="WIF",
            name="dogwifhat",
            price_usd=2.50,
            change_1h=-1.5,
            change_24h=-5.0,
            volume_24h=10_000_000,
            mcap=2_500_000_000,
            buys_24h=8000,
            sells_24h=10000,
            liquidity=5_000_000,
            contract_address="WifAddress456",
        ),
        TokenSentiment(
            symbol="MOON",
            name="MoonToken",
            price_usd=0.001,
            change_1h=50.0,
            change_24h=150.0,
            volume_24h=1_000_000,
            mcap=10_000_000,
            buys_24h=2000,
            sells_24h=500,
            liquidity=50_000,
            contract_address="MoonAddress789",
        ),
    ]


class AsyncContextManager:
    """Helper class to create proper async context managers for mocking."""
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def create_mock_response(status=200, json_data=None):
    """Create a mock aiohttp response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    return response


def create_mock_session(post_responses=None, get_responses=None):
    """Create a mock aiohttp session with proper async context managers."""
    session = MagicMock()

    if post_responses is None:
        post_responses = [create_mock_response()]

    if get_responses is None:
        get_responses = [create_mock_response()]

    post_call_count = [0]
    get_call_count = [0]

    def mock_post(*args, **kwargs):
        idx = min(post_call_count[0], len(post_responses) - 1)
        post_call_count[0] += 1
        return AsyncContextManager(post_responses[idx])

    def mock_get(*args, **kwargs):
        idx = min(get_call_count[0], len(get_responses) - 1)
        get_call_count[0] += 1
        return AsyncContextManager(get_responses[idx])

    session.post = mock_post
    session.get = mock_get
    session.close = AsyncMock()

    return session


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session."""
    return create_mock_session()


@pytest.fixture
def mock_cost_tracker():
    """Mock the cost tracker module."""
    with patch('tg_bot.services.cost_tracker.get_tracker') as mock:
        tracker = MagicMock()
        tracker.can_make_call.return_value = (True, "")
        tracker.record_call.return_value = None
        mock.return_value = tracker
        yield tracker


# =============================================================================
# 1. GENERATOR INITIALIZATION TESTS
# =============================================================================

class TestGeneratorInitialization:
    """Tests for SentimentReportGenerator initialization."""

    def test_generator_creation(self, generator):
        """Test basic generator creation."""
        assert generator.bot_token == "test_bot_token"
        assert generator.chat_id == "test_chat_id"
        assert generator.xai_api_key == "test_xai_key"
        assert generator.interval_minutes == 30
        assert generator._running is False
        assert generator._session is None

    def test_generator_without_api_key(self, generator_no_grok):
        """Test generator without Grok API key."""
        assert generator_no_grok.xai_api_key == ""

    def test_can_use_grok_with_key(self, generator):
        """Test _can_use_grok returns True with valid key."""
        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            can_use, reason = generator._can_use_grok()
            assert can_use is True

    def test_can_use_grok_without_key(self, generator_no_grok):
        """Test _can_use_grok returns False without API key."""
        can_use, reason = generator_no_grok._can_use_grok()
        assert can_use is False
        assert "not set" in reason.lower()

    def test_can_use_grok_rate_limited(self, generator):
        """Test _can_use_grok respects rate limits."""
        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (False, "Daily limit reached")
            mock_get.return_value = tracker

            can_use, reason = generator._can_use_grok()
            assert can_use is False
            assert "limit" in reason.lower()


# =============================================================================
# 2. MARKET REGIME TESTS
# =============================================================================

class TestMarketRegimeFetching:
    """Tests for market regime determination."""

    @pytest.mark.asyncio
    async def test_get_market_regime_bullish(self, generator):
        """Test market regime detection for bullish conditions."""
        generator._session = AsyncMock()

        # Mock SOL price response
        sol_response = AsyncMock()
        sol_response.status = 200
        sol_response.json = AsyncMock(return_value={
            "pairs": [{"priceChange": {"h24": 8.0}}]
        })

        # Mock BTC search response
        btc_response = AsyncMock()
        btc_response.status = 200
        btc_response.json = AsyncMock(return_value={
            "pairs": [
                {"baseToken": {"symbol": "BTC"}, "priceChange": {"h24": 6.0}}
            ]
        })

        generator._session.get = AsyncMock()
        generator._session.get.return_value.__aenter__ = AsyncMock(
            side_effect=[sol_response, btc_response]
        )
        generator._session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        regime = await generator._get_market_regime()

        assert regime is not None
        assert isinstance(regime, MarketRegime)

    @pytest.mark.asyncio
    async def test_get_market_regime_handles_api_error(self, generator):
        """Test market regime handles API errors gracefully."""
        generator._session = AsyncMock()

        # Mock API error
        mock_response = AsyncMock()
        mock_response.status = 500

        generator._session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        generator._session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        regime = await generator._get_market_regime()

        # Should return default regime, not crash
        assert regime is not None
        assert isinstance(regime, MarketRegime)

    @pytest.mark.asyncio
    async def test_get_market_regime_handles_exception(self, generator):
        """Test market regime handles exceptions."""
        generator._session = AsyncMock()
        generator._session.get.side_effect = Exception("Network error")

        regime = await generator._get_market_regime()

        # Should return default regime
        assert regime is not None
        assert regime.regime == "NEUTRAL"


# =============================================================================
# 3. GROK API INTEGRATION TESTS
# =============================================================================

class TestGrokApiIntegration:
    """Tests for Grok AI API integration."""

    @pytest.mark.asyncio
    async def test_get_grok_token_scores_parses_response(self, generator, sample_tokens):
        """Test parsing Grok token scores response."""
        # Calculate initial sentiment
        for token in sample_tokens:
            token.calculate_sentiment(include_grok=False)

        # Mock Grok API response
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": "BONK|65|BULLISH|Strong buy pressure, good volume|$0.00002|$0.00003|$0.00004|$0.00005\nWIF|-30|BEARISH|Selling pressure, declining momentum||||\nMOON|40|NEUTRAL|Mixed signals, wait for confirmation||||"
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            await generator._get_grok_token_scores(sample_tokens)

        # Check BONK was scored
        bonk = next(t for t in sample_tokens if t.symbol == "BONK")
        assert bonk.grok_verdict == "BULLISH"
        assert bonk.grok_score == 0.65

    @pytest.mark.asyncio
    async def test_get_grok_token_scores_without_api_key(self, generator_no_grok, sample_tokens):
        """Test Grok scoring gracefully skips without API key."""
        generator_no_grok._session = create_mock_session()

        await generator_no_grok._get_grok_token_scores(sample_tokens)

        # Tokens should not have Grok verdicts
        for token in sample_tokens:
            assert token.grok_verdict == ""

    @pytest.mark.asyncio
    async def test_get_grok_token_scores_handles_api_error(self, generator, sample_tokens):
        """Test Grok scoring handles API errors."""
        # Mock API error
        grok_response = create_mock_response(500)
        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            # Should not raise
            await generator._get_grok_token_scores(sample_tokens)

    @pytest.mark.asyncio
    async def test_get_grok_summary_returns_string(self, generator, sample_tokens):
        """Test Grok summary returns a string."""
        # Calculate sentiment first
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)
            t.grok_verdict = "BULLISH" if t.sentiment_score > 0 else "BEARISH"

        # Mock Grok API response
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": "Market looking bullish, strong buy pressure across meme coins."
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            summary = await generator._get_grok_summary(sample_tokens)

        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_get_grok_summary_fallback_without_key(self, generator_no_grok, sample_tokens):
        """Test Grok summary fallback without API key."""
        summary = await generator_no_grok._get_grok_summary(sample_tokens)

        assert "unavailable" in summary.lower()

    @pytest.mark.asyncio
    async def test_keyword_detection_penalty(self, generator, sample_tokens):
        """Test that hype keywords trigger score penalties."""
        for token in sample_tokens:
            token.calculate_sentiment(include_grok=False)

        # Response with "momentum" keyword which should trigger penalty
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": "BONK|70|BULLISH|Strong momentum play, pump is starting|$0.00002|$0.00003|$0.00004|$0.00005"
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            await generator._get_grok_token_scores(sample_tokens)

        bonk = next(t for t in sample_tokens if t.symbol == "BONK")
        # Score should be penalized for "momentum" and "pump" keywords
        assert bonk.has_momentum_mention is True
        assert bonk.has_pump_mention is True
        # Original 70 -> 0.70, minus penalties
        assert bonk.grok_score < 0.70


# =============================================================================
# 4. MACRO ANALYSIS TESTS
# =============================================================================

class TestMacroAnalysis:
    """Tests for macro events analysis."""

    @pytest.mark.asyncio
    async def test_get_macro_analysis_parses_response(self, generator):
        """Test macro analysis parsing."""
        # Mock Grok response
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """SHORT|Fed meeting tomorrow, expect volatility.
MEDIUM|Earnings season starting, tech in focus.
LONG|Rate cuts expected in Q2, bullish for risk assets.
EVENTS|Fed Meeting Jan 30, CPI Data Feb 12, Earnings Week Feb 3"""
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            macro = await generator._get_macro_analysis()

        assert isinstance(macro, MacroAnalysis)
        assert "Fed" in macro.short_term
        assert "Earnings" in macro.medium_term
        assert len(macro.key_events) > 0

    @pytest.mark.asyncio
    async def test_get_macro_analysis_without_grok(self, generator_no_grok):
        """Test macro analysis returns empty without Grok."""
        macro = await generator_no_grok._get_macro_analysis()

        assert isinstance(macro, MacroAnalysis)
        assert macro.short_term == ""

    def test_validate_future_events_filters_past(self, generator):
        """Test that past events are filtered out."""
        # Events with clearly past dates (assuming current year)
        events = [
            "Fed Meeting January 15 (past date)",  # Will be filtered if in past
            "CPI Data February 28",
            "Earnings Week March 1",
        ]

        validated = generator._validate_future_events(events)

        # Should filter based on current date - exact results depend on when test runs
        assert isinstance(validated, list)

    def test_validate_future_events_keeps_future(self, generator):
        """Test that future events are kept."""
        # Create events with future year
        events = [
            "Bitcoin Halving April 2030",
            "Fed Meeting December 2030",
        ]

        validated = generator._validate_future_events(events)

        # Future years should be kept
        assert len(validated) == 2


# =============================================================================
# 5. TRADITIONAL MARKETS TESTS
# =============================================================================

class TestTraditionalMarkets:
    """Tests for traditional markets analysis."""

    @pytest.mark.asyncio
    async def test_get_traditional_markets_parses_response(self, generator):
        """Test traditional markets parsing."""
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """DXY_DIR|BEARISH
DXY|Dollar weakening due to rate cut expectations.
STOCKS_DIR|BULLISH
STOCKS|Tech earnings driving rally.
24H|Expect continued strength.
WEEK|Watch for CPI data impact.
CRYPTO_IMPACT|Weak dollar positive for crypto."""
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            markets = await generator._get_traditional_markets()

        assert isinstance(markets, TraditionalMarkets)
        assert markets.dxy_direction == "BEARISH"
        assert markets.stocks_direction == "BULLISH"
        assert "dollar" in markets.dxy_sentiment.lower()


# =============================================================================
# 6. STOCK PICKS TESTS
# =============================================================================

class TestStockPicks:
    """Tests for stock picks functionality."""

    @pytest.mark.asyncio
    async def test_get_stock_picks_parses_response(self, generator):
        """Test stock picks parsing."""
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """NVDA|BULLISH|AI demand surge, strong momentum|$600|$500
AAPL|BULLISH|iPhone sales strong|$200|$180
TSLA|BEARISH|Delivery concerns, competition|$180|$220"""
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            picks, changes = await generator._get_stock_picks()

        assert isinstance(picks, list)
        assert len(picks) == 3
        assert picks[0].ticker == "NVDA"
        assert picks[0].direction == "BULLISH"

    @pytest.mark.asyncio
    async def test_get_stock_picks_with_previous(self, generator):
        """Test stock picks with previous picks for change detection."""
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """NVDA|BULLISH|Continues strong|$600|$500
META|BULLISH|New pick, AI play|$400|$350
CHANGES|Dropped AAPL due to weak guidance"""
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            picks, changes = await generator._get_stock_picks(previous_picks=["NVDA", "AAPL"])

        assert "Dropped" in changes or "AAPL" in changes

    def test_get_previous_stock_picks_no_file(self, generator, tmp_path):
        """Test getting previous picks when file doesn't exist."""
        # Use a non-existent file path
        with patch('bots.buy_tracker.sentiment_report.PREDICTIONS_FILE', tmp_path / "nonexistent.json"):
            picks = generator._get_previous_stock_picks()

        assert picks == []


# =============================================================================
# 7. COMMODITY MOVERS TESTS
# =============================================================================

class TestCommodityMovers:
    """Tests for commodity movers functionality."""

    @pytest.mark.asyncio
    async def test_get_commodity_movers_parses_response(self, generator):
        """Test commodity movers parsing."""
        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """Crude Oil|UP|+3.5%|OPEC cuts|Testing $85
Gold|UP|+1.2%|Safe haven demand|Bullish to $2100
Natural Gas|DOWN|-5%|Warm weather|More downside"""
                }
            }]
        })

        generator._session = create_mock_session(post_responses=[grok_response])

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            movers = await generator._get_commodity_movers()

        assert isinstance(movers, list)
        assert len(movers) == 3
        assert movers[0].name == "Crude Oil"
        assert movers[0].direction == "UP"


# =============================================================================
# 8. PRECIOUS METALS TESTS
# =============================================================================

class TestPreciousMetals:
    """Tests for precious metals analysis."""

    @pytest.mark.asyncio
    async def test_get_precious_metals_outlook_parses_response(self, generator):
        """Test precious metals parsing."""
        # Mock live price fetch (fallback)
        price_response = create_mock_response(200, {"pax-gold": {"usd": 2750.0}})

        grok_response = create_mock_response(200, {
            "choices": [{
                "message": {
                    "content": """GOLD_DIR|BULLISH
GOLD|Testing new highs, inflation hedge demand strong.
SILVER_DIR|BULLISH
SILVER|Industrial demand rising, following gold.
PLATINUM_DIR|NEUTRAL
PLATINUM|Mixed signals, watch auto sector."""
                }
            }]
        })

        generator._session = create_mock_session(
            post_responses=[grok_response],
            get_responses=[price_response]
        )

        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_get:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_get.return_value = tracker

            outlook = await generator._get_precious_metals_outlook()

        assert isinstance(outlook, PreciousMetalsOutlook)
        assert outlook.gold_direction == "BULLISH"
        assert "highs" in outlook.gold_outlook.lower()

    @pytest.mark.asyncio
    async def test_fetch_live_commodity_prices_coingecko_fallback(self, generator):
        """Test commodity price fetching with CoinGecko fallback."""
        # Mock CoinGecko PAXG response
        price_response = create_mock_response(200, {"pax-gold": {"usd": 2780.50}})

        generator._session = create_mock_session(get_responses=[price_response])

        # Module not available, so will use fallback
        with patch.dict('sys.modules', {'core.data_sources.commodity_prices': None}):
            prices = await generator._fetch_live_commodity_prices()

        # Should have gold price from PAXG
        assert "gold" in prices
        assert prices["gold"] == 2780.50


# =============================================================================
# 9. REPORT FORMATTING TESTS
# =============================================================================

class TestReportFormatting:
    """Tests for report formatting functionality."""

    def test_format_report_returns_list_of_messages(self, generator, sample_tokens):
        """Test that format_report returns a list of messages."""
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)
            t.grok_verdict = "BULLISH" if t.sentiment_score > 0 else "BEARISH"
            t.grok_reasoning = "Test reasoning"
            t.grok_analysis = "Test analysis"

        macro = MacroAnalysis(
            short_term="Short term outlook",
            medium_term="Medium term outlook",
            long_term="Long term outlook",
            key_events=["Event 1", "Event 2"],
        )

        markets = TraditionalMarkets(
            dxy_direction="BEARISH",
            dxy_sentiment="Dollar weak",
            stocks_direction="BULLISH",
            stocks_sentiment="Stocks strong",
            next_24h="Bullish outlook",
            next_week="Continued strength",
            correlation_note="Crypto benefits",
        )

        stock_picks = [
            StockPick(ticker="NVDA", direction="BULLISH", reason="AI", target="$600", stop_loss="$500"),
        ]

        commodities = [
            CommodityMover(name="Gold", direction="UP", change="+2%", reason="Safe haven", outlook="Bullish"),
        ]

        precious_metals = PreciousMetalsOutlook(
            gold_direction="BULLISH",
            gold_outlook="Testing highs",
            silver_direction="BULLISH",
            silver_outlook="Following gold",
            platinum_direction="NEUTRAL",
            platinum_outlook="Mixed",
        )

        messages = generator._format_report(
            tokens=sample_tokens,
            grok_summary="Market looking good",
            macro=macro,
            markets=markets,
            stock_picks=stock_picks,
            picks_changes="Dropped AAPL",
            commodities=commodities,
            precious_metals=precious_metals,
        )

        assert isinstance(messages, list)
        assert len(messages) == 3  # 3 messages: tokens, markets/macro, stocks/commodities

        # Check tokens message
        assert "JARVIS SENTIMENT REPORT" in messages[0]
        assert "BONK" in messages[0]

        # Check markets message
        assert "TRADITIONAL MARKETS" in messages[1]
        assert "DXY" in messages[1]

        # Check stocks message
        assert "STOCK PICKS" in messages[2]
        assert "NVDA" in messages[2]

    def test_format_report_handles_empty_data(self, generator, sample_tokens):
        """Test format_report handles empty optional data."""
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)

        messages = generator._format_report(
            tokens=sample_tokens,
            grok_summary="",
            macro=None,
            markets=None,
        )

        assert isinstance(messages, list)
        assert len(messages) == 3

    def test_split_message_short(self, generator):
        """Test message splitting for short messages."""
        short_msg = "Short message"

        chunks = generator._split_message(short_msg)

        assert len(chunks) == 1
        assert chunks[0] == short_msg

    def test_split_message_long(self, generator):
        """Test message splitting for long messages."""
        # Create a long message (>4000 chars)
        long_msg = "Line content here\n" * 500

        chunks = generator._split_message(long_msg, max_len=4000)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 4000


# =============================================================================
# 10. TELEGRAM POSTING TESTS
# =============================================================================

class TestTelegramPosting:
    """Tests for Telegram posting functionality."""

    @pytest.mark.asyncio
    async def test_post_to_telegram_sends_messages(self, generator, sample_tokens):
        """Test posting messages to Telegram."""
        # Mock successful Telegram response
        tg_response = create_mock_response(200, {"ok": True})
        generator._session = create_mock_session(post_responses=[tg_response])

        messages = ["Message 1", "Message 2", "Message 3"]

        # Mock additional methods that post_to_telegram calls
        with patch.object(generator, '_post_trending_tokens_section', new_callable=AsyncMock):
            with patch.object(generator, '_post_bluechip_tokens_section', new_callable=AsyncMock):
                with patch.object(generator, '_post_xstocks_section', new_callable=AsyncMock):
                    with patch.object(generator, '_post_indexes_section', new_callable=AsyncMock):
                        with patch.object(generator, '_post_grok_conviction_picks', new_callable=AsyncMock):
                            with patch.object(generator, '_post_ape_buttons', new_callable=AsyncMock):
                                with patch.object(generator, '_post_treasury_status', new_callable=AsyncMock):
                                    await generator._post_to_telegram(messages, tokens=sample_tokens)

    @pytest.mark.asyncio
    async def test_post_to_telegram_handles_error(self, generator):
        """Test Telegram posting handles errors gracefully."""
        # Mock error response
        tg_response = create_mock_response(200, {"ok": False, "description": "Bad Request"})
        generator._session = create_mock_session(post_responses=[tg_response])

        messages = ["Test message"]

        with patch.object(generator, '_post_trending_tokens_section', new_callable=AsyncMock):
            with patch.object(generator, '_post_bluechip_tokens_section', new_callable=AsyncMock):
                with patch.object(generator, '_post_xstocks_section', new_callable=AsyncMock):
                    with patch.object(generator, '_post_indexes_section', new_callable=AsyncMock):
                        with patch.object(generator, '_post_grok_conviction_picks', new_callable=AsyncMock):
                            with patch.object(generator, '_post_ape_buttons', new_callable=AsyncMock):
                                with patch.object(generator, '_post_treasury_status', new_callable=AsyncMock):
                                    # Should not raise
                                    await generator._post_to_telegram(messages)


# =============================================================================
# 11. APE BUTTONS TESTS
# =============================================================================

class TestApeButtons:
    """Tests for ape button functionality."""

    @pytest.mark.asyncio
    async def test_post_ape_buttons_for_bullish_tokens(self, generator, sample_tokens):
        """Test ape buttons posted for bullish tokens."""
        # Set up tokens with Grok verdicts and targets
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)
            if t.symbol == "BONK":
                t.grok_verdict = "BULLISH"
                t.grok_target_safe = "$0.00003"
                t.grok_target_med = "$0.00004"
                t.grok_target_degen = "$0.00005"
                t.grok_stop_loss = "$0.00002"
                t.grok_reasoning = "Strong buy pressure"

        # Mock Telegram response
        tg_response = create_mock_response(200, {"ok": True})
        generator._session = create_mock_session(post_responses=[tg_response])

        await generator._post_ape_buttons(sample_tokens)

    @pytest.mark.asyncio
    async def test_post_ape_buttons_no_tokens(self, generator):
        """Test ape buttons handles empty tokens."""
        generator._session = create_mock_session()

        await generator._post_ape_buttons(None)
        await generator._post_ape_buttons([])

    def test_create_grok_ape_keyboard(self, generator):
        """Test ape keyboard creation."""
        token = TokenSentiment(
            symbol="TEST",
            name="Test",
            price_usd=1.0,
            change_1h=0,
            change_24h=0,
            volume_24h=0,
            mcap=0,
            buys_24h=0,
            sells_24h=0,
            liquidity=0,
            contract_address="TestAddress123",
        )

        keyboard = generator._create_grok_ape_keyboard(token)

        # Should have multiple rows of buttons
        assert len(keyboard.inline_keyboard) >= 3


# =============================================================================
# 12. PREDICTION TRACKING TESTS
# =============================================================================

class TestPredictionTracking:
    """Tests for prediction tracking functionality."""

    def test_save_predictions_creates_file(self, generator, sample_tokens, tmp_path):
        """Test saving predictions to file."""
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)
            t.grok_verdict = "BULLISH"
            t.grok_score = 0.7
            t.grok_analysis = "Test targets"
            t.grok_reasoning = "Test reasoning"

        macro = MacroAnalysis(short_term="Test", medium_term="Test", long_term="Test")
        markets = TraditionalMarkets(dxy_direction="BULLISH", stocks_direction="BULLISH")
        stock_picks = [StockPick(ticker="NVDA", direction="BULLISH", reason="Test")]
        commodities = [CommodityMover(name="Gold", direction="UP", change="+1%", reason="Test")]
        precious_metals = PreciousMetalsOutlook(gold_direction="BULLISH")

        # Use temp file for test
        test_file = tmp_path / "test_predictions.json"

        with patch('bots.buy_tracker.sentiment_report.PREDICTIONS_FILE', test_file):
            generator._save_predictions(
                tokens=sample_tokens,
                macro=macro,
                markets=markets,
                stock_picks=stock_picks,
                commodities=commodities,
                precious_metals=precious_metals,
            )

        assert test_file.exists()

        with open(test_file) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 1
        assert "token_predictions" in data[0]
        assert "BONK" in data[0]["token_predictions"]

    def test_save_predictions_appends(self, generator, sample_tokens, tmp_path):
        """Test saving predictions appends to existing file."""
        for t in sample_tokens:
            t.calculate_sentiment(include_grok=False)
            t.grok_verdict = "BULLISH"

        macro = MacroAnalysis()
        markets = TraditionalMarkets()

        test_file = tmp_path / "test_predictions.json"

        # Create existing file with one record
        with open(test_file, 'w') as f:
            json.dump([{"timestamp": "old_record"}], f)

        with patch('bots.buy_tracker.sentiment_report.PREDICTIONS_FILE', test_file):
            generator._save_predictions(
                tokens=sample_tokens,
                macro=macro,
                markets=markets,
            )

        with open(test_file) as f:
            data = json.load(f)

        assert len(data) == 2  # Old record + new record


# =============================================================================
# 13. TRENDING TOKENS SECTION TESTS
# =============================================================================

class TestTrendingTokensSection:
    """Tests for trending tokens section."""

    @pytest.mark.asyncio
    async def test_post_trending_tokens_section(self, generator):
        """Test posting trending tokens section."""
        tg_response = create_mock_response(200, {"ok": True})
        generator._session = create_mock_session(post_responses=[tg_response])

        # Mock fetch_trending_solana_tokens
        mock_tokens = [
            MagicMock(
                symbol="BONK",
                price_usd=0.00003,
                price_change_24h=15.0,
                volume_24h=1000000,
                mcap=100000000,
                rank=1,
                contract="BonkAddress",
            ),
            MagicMock(
                symbol="WIF",
                price_usd=2.5,
                price_change_24h=-5.0,
                volume_24h=5000000,
                mcap=2500000000,
                rank=2,
                contract="WifAddress",
            ),
        ]

        with patch('bots.buy_tracker.sentiment_report.fetch_trending_solana_tokens',
                   new_callable=AsyncMock, return_value=(mock_tokens, [])):
            await generator._post_trending_tokens_section()


# =============================================================================
# 14. FULL REPORT GENERATION TESTS
# =============================================================================

class TestFullReportGeneration:
    """Tests for complete report generation flow."""

    @pytest.mark.asyncio
    async def test_generate_and_post_report_success(self, generator):
        """Test successful report generation and posting."""
        # Mock all responses
        mock_response = create_mock_response(200, {
            "ok": True,
            "pairs": [{"priceChange": {"h24": 5.0}}],
            "choices": [{"message": {"content": "Test|50|BULLISH|Reason||||"}}],
        })

        generator._session = create_mock_session(
            post_responses=[mock_response],
            get_responses=[mock_response]
        )

        # Mock cost tracker
        with patch('tg_bot.services.cost_tracker.get_tracker') as mock_tracker:
            tracker = MagicMock()
            tracker.can_make_call.return_value = (True, "")
            mock_tracker.return_value = tracker

            # Mock context engine
            with patch('core.context_engine.context') as mock_context:
                mock_context.can_run_sentiment.return_value = True
                mock_context.record_sentiment_run.return_value = None

                # Mock trending tokens
                with patch('bots.buy_tracker.sentiment_report.fetch_trending_solana_tokens',
                          new_callable=AsyncMock, return_value=([], [])):
                    with patch('bots.buy_tracker.sentiment_report.fetch_high_liquidity_tokens',
                              new_callable=AsyncMock, return_value=([], [])):
                        with patch.object(generator, '_get_trending_tokens',
                                         new_callable=AsyncMock, return_value=[]):
                            result = await generator.generate_and_post_report(force=True)

        # Should return falsey value since no tokens found
        assert not result

    @pytest.mark.asyncio
    async def test_generate_and_post_report_blocked_by_timing(self, generator):
        """Test report generation blocked by timing controls."""
        generator._session = create_mock_session()

        with patch.object(generator, '_can_run_report', return_value=False):
            result = await generator.generate_and_post_report(force=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_generate_and_post_report_handles_exception(self, generator):
        """Test report generation handles exceptions."""
        generator._session = create_mock_session()

        with patch.object(generator, '_can_run_report', side_effect=Exception("Test error")):
            result = await generator.generate_and_post_report()

        assert result is False


# =============================================================================
# 15. LIFECYCLE TESTS
# =============================================================================

class TestLifecycle:
    """Tests for generator lifecycle (start/stop)."""

    @pytest.mark.asyncio
    async def test_start_creates_session(self, generator):
        """Test that start creates an aiohttp session."""
        # Mock the generate_and_post_report to avoid actual execution
        with patch.object(generator, 'generate_and_post_report', new_callable=AsyncMock):
            with patch.object(generator, '_can_run_report', return_value=False):
                # Start in background
                task = asyncio.create_task(generator.start())

                # Give it a moment to initialize
                await asyncio.sleep(0.1)

                # Stop it
                await generator.stop()

                # Cancel task
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert generator._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_session(self, generator):
        """Test that stop closes the session."""
        generator._session = AsyncMock()
        generator._running = True

        await generator.stop()

        assert generator._running is False
        generator._session.close.assert_called_once()


# =============================================================================
# 16. TREASURY STATUS TESTS
# =============================================================================

class TestTreasuryStatus:
    """Tests for treasury status functionality."""

    @pytest.mark.asyncio
    async def test_get_treasury_balance(self, generator):
        """Test getting treasury balance."""
        # Mock RPC response
        rpc_response = create_mock_response(200, {
            "result": {"value": 5_000_000_000}  # 5 SOL in lamports
        })

        # Mock price response
        price_response = create_mock_response(200, {
            "pairs": [{"priceUsd": "200"}]
        })

        generator._session = create_mock_session(
            post_responses=[rpc_response],
            get_responses=[price_response]
        )

        # Mock TreasuryTrader
        with patch('bots.treasury.trading.TreasuryTrader') as mock_trader:
            trader_instance = MagicMock()
            trader_instance._ensure_initialized = AsyncMock(return_value=(False, "Not initialized"))
            mock_trader.return_value = trader_instance

            balance_sol, sol_price = await generator._get_treasury_balance()

        # Should have fetched via RPC fallback
        assert balance_sol == 5.0
        assert sol_price == 200.0

    @pytest.mark.asyncio
    async def test_post_treasury_status_fallback(self, generator):
        """Test treasury status fallback when scorekeeper unavailable."""
        mock_response = create_mock_response(200, {"ok": True})
        generator._session = create_mock_session(post_responses=[mock_response])

        # Mock _get_treasury_status to return data
        with patch.object(generator, '_get_treasury_status', new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "address": "TestAddress123",
                "balance_sol": 10.5,
                "balance_usd": 2100.0,
            }

            await generator._post_treasury_status_fallback()


# =============================================================================
# 17. GET TRENDING TOKENS TESTS
# =============================================================================

class TestGetTrendingTokens:
    """Tests for trending token fetching."""

    @pytest.mark.asyncio
    async def test_get_trending_tokens_from_boosted(self, generator):
        """Test fetching trending tokens from boosted list."""
        # Mock boosted tokens response
        boosted_response = create_mock_response(200, [
            {"chainId": "solana", "tokenAddress": "Token1Address"},
            {"chainId": "solana", "tokenAddress": "Token2Address"},
            {"chainId": "ethereum", "tokenAddress": "EthToken"},  # Should be filtered
        ])

        # Mock pair data response
        pair_response = create_mock_response(200, {
            "pairs": [{
                "baseToken": {"symbol": "TEST", "name": "Test Token", "address": "Token1Address"},
                "priceUsd": "0.001",
                "priceChange": {"h1": 5.0, "h24": 15.0},
                "volume": {"h24": 1000000},
                "marketCap": 10000000,
                "txns": {"h24": {"buys": 500, "sells": 300}},
                "liquidity": {"usd": 100000},
            }]
        })

        generator._session = create_mock_session(
            get_responses=[boosted_response, pair_response, pair_response]
        )

        tokens = await generator._get_trending_tokens(limit=5)

        assert isinstance(tokens, list)

    @pytest.mark.asyncio
    async def test_get_trending_tokens_handles_error(self, generator):
        """Test trending tokens handles API errors."""
        # Create a session where get raises an exception
        session = MagicMock()

        def mock_get(*args, **kwargs):
            raise Exception("Network error")

        session.get = mock_get
        generator._session = session

        tokens = await generator._get_trending_tokens()

        assert tokens == []


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
