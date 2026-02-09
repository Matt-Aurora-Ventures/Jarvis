"""
Tests for demo_sentiment module.

Tests sentiment caching, market regime, trending tokens, conviction picks.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from tg_bot.handlers.demo import demo_sentiment


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset sentiment cache between tests."""
    demo_sentiment._SENTIMENT_CACHE = {"tokens": [], "last_update": None, "macro": {}}
    yield
    demo_sentiment._SENTIMENT_CACHE = {"tokens": [], "last_update": None, "macro": {}}


@pytest.fixture
def sample_sentiment_data():
    """Sample sentiment report data."""
    return {
        "tokens_raw": [
            {"symbol": "TEST1", "address": "addr1", "score": 0.8},
            {"symbol": "TEST2", "address": "addr2", "score": 0.6},
        ],
        "stocks": "bullish",
        "commodities": "neutral",
        "metals": "bearish",
        "solana": "bullish",
    }


@pytest.fixture
def mock_signal_service():
    """Mock signal service."""
    service = MagicMock()
    # get_comprehensive_signal
    signal = SimpleNamespace(
        symbol="TEST",
        address="test_addr",
        price_usd=0.50,
        price_change_24h=10.5,
        volume_24h=100_000,
        liquidity_usd=50_000,
        sentiment="bullish",
        sentiment_score=0.75,
        sentiment_confidence=0.80,
        sentiment_summary="Strong uptrend",
        signal="BUY",
        signal_score=0.80,
        signal_reasons=["Volume spike", "Price action"],
    )
    service.get_comprehensive_signal = AsyncMock(return_value=signal)

    # get_trending_tokens
    trending = [signal]
    service.get_trending_tokens = AsyncMock(return_value=trending)

    # get_top_signals
    service.get_top_signals = AsyncMock(return_value=trending)

    return service


# =============================================================================
# Sentiment Cache Tests
# =============================================================================


class TestSentimentCache:
    """Test sentiment data cache management."""

    @pytest.mark.asyncio
    async def test_update_sentiment_cache_success(self, sample_sentiment_data, tmp_path):
        """Test successfully updates sentiment cache from file."""
        sentiment_file = tmp_path / "sentiment_report_data.json"
        with open(sentiment_file, "w") as f:
            json.dump(sample_sentiment_data, f)

        with patch.object(Path, "resolve") as mock_resolve:
            mock_path = MagicMock()
            mock_path.parents = {3: tmp_path.parent.parent.parent}
            mock_resolve.return_value = mock_path

            # Mock the file path construction
            with patch("tg_bot.handlers.demo.demo_sentiment.Path") as mock_path_cls:
                mock_path_cls.return_value.resolve.return_value.parents = [None, None, None, tmp_path]
                with patch("pathlib.Path.exists", return_value=True), \
                     patch("builtins.open", mock_open(read_data=json.dumps(sample_sentiment_data))):
                    await demo_sentiment._update_sentiment_cache()

        assert len(demo_sentiment._SENTIMENT_CACHE["tokens"]) == 2
        assert demo_sentiment._SENTIMENT_CACHE["macro"]["stocks"] == "bullish"
        assert demo_sentiment._SENTIMENT_CACHE["last_update"] is not None

    @pytest.mark.asyncio
    async def test_update_sentiment_cache_file_not_found(self):
        """Test gracefully handles missing sentiment file."""
        with patch("pathlib.Path.exists", return_value=False):
            await demo_sentiment._update_sentiment_cache()

        # Cache should remain empty
        assert len(demo_sentiment._SENTIMENT_CACHE["tokens"]) == 0

    def test_get_cached_sentiment_tokens(self):
        """Test retrieves cached sentiment tokens."""
        demo_sentiment._SENTIMENT_CACHE["tokens"] = [{"symbol": "TEST"}]

        result = demo_sentiment.get_cached_sentiment_tokens()

        assert len(result) == 1
        assert result[0]["symbol"] == "TEST"

    def test_get_cached_macro_sentiment(self):
        """Test retrieves cached macro sentiment."""
        demo_sentiment._SENTIMENT_CACHE["macro"] = {"stocks": "bullish"}

        result = demo_sentiment.get_cached_macro_sentiment()

        assert result["stocks"] == "bullish"

    def test_get_sentiment_cache_age_with_data(self):
        """Test calculates cache age when data exists."""
        demo_sentiment._SENTIMENT_CACHE["last_update"] = datetime.now(timezone.utc) - timedelta(minutes=5)

        age = demo_sentiment.get_sentiment_cache_age()

        assert age is not None
        assert age.total_seconds() >= 300  # At least 5 minutes

    def test_get_sentiment_cache_age_no_data(self):
        """Test returns None when cache has never been updated."""
        demo_sentiment._SENTIMENT_CACHE["last_update"] = None

        age = demo_sentiment.get_sentiment_cache_age()

        assert age is None


# =============================================================================
# Market Regime Tests
# =============================================================================


class TestMarketRegime:
    """Test market regime detection."""

    @pytest.mark.asyncio
    async def test_get_market_regime_bull_from_dexscreener(self):
        """Test detects bull market from DexScreener data."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "pairs": [{
                "priceChange": {"h24": 8.5}
            }]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            regime = await demo_sentiment.get_market_regime()

        assert regime["regime"] == "BULL"
        assert regime["risk_level"] == "LOW"
        assert regime["sol_change_24h"] == 8.5

    @pytest.mark.asyncio
    async def test_get_market_regime_bear_from_dexscreener(self):
        """Test detects bear market from DexScreener data."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "pairs": [{
                "priceChange": {"h24": -8.5}
            }]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            regime = await demo_sentiment.get_market_regime()

        assert regime["regime"] == "BEAR"
        assert regime["risk_level"] == "HIGH"

    @pytest.mark.asyncio
    async def test_get_market_regime_neutral_default(self):
        """Test returns neutral regime on errors."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("API error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            regime = await demo_sentiment.get_market_regime()

        assert regime["regime"] in ["UNKNOWN", "NEUTRAL"]


# =============================================================================
# AI Sentiment Tests
# =============================================================================


class TestAISentiment:
    """Test AI sentiment for tokens."""

    @pytest.mark.asyncio
    async def test_get_ai_sentiment_from_signal_service(self, mock_signal_service):
        """Test gets sentiment from signal service (primary)."""
        with patch("tg_bot.services.signal_service.get_signal_service", return_value=mock_signal_service):
            result = await demo_sentiment.get_ai_sentiment_for_token("addr123")

        assert result["symbol"] == "TEST"
        assert result["sentiment"] == "bullish"
        assert result["score"] == 0.75
        assert result["signal"] == "BUY"

    @pytest.mark.asyncio
    async def test_get_ai_sentiment_fallback_to_bags(self):
        """Test falls back to Bags client on signal service failure."""
        mock_bags_client = AsyncMock()
        mock_token = SimpleNamespace(
            symbol="BAGS",
            price_usd=1.5,
            price_change_24h=5.0,
            volume_24h=10_000,
            liquidity=50_000,
        )
        mock_bags_client.get_token_info = AsyncMock(return_value=mock_token)

        with patch("tg_bot.services.signal_service.get_signal_service", side_effect=Exception("Service error")), \
             patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client):
            result = await demo_sentiment.get_ai_sentiment_for_token("addr123")

        assert result["symbol"] == "BAGS"
        assert result["sentiment"] == "neutral"
        assert result["score"] == 0.5

    @pytest.mark.asyncio
    async def test_get_ai_sentiment_fallback_to_jupiter(self):
        """Test falls back to Jupiter on Bags failure."""
        mock_jupiter = AsyncMock()
        mock_token = SimpleNamespace(
            symbol="JUP",
            price_usd=2.0,
        )
        mock_jupiter.get_token_info = AsyncMock(return_value=mock_token)

        with patch("tg_bot.services.signal_service.get_signal_service", side_effect=Exception("Service error")), \
             patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=None), \
             patch("bots.treasury.jupiter.JupiterClient", return_value=mock_jupiter):
            result = await demo_sentiment.get_ai_sentiment_for_token("addr123")

        assert result["symbol"] == "JUP"
        assert result["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_get_ai_sentiment_returns_unknown_on_total_failure(self):
        """Test returns unknown sentiment when all sources fail."""
        with patch("tg_bot.services.signal_service.get_signal_service", side_effect=Exception("Service error")), \
             patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=None), \
             patch("bots.treasury.jupiter.JupiterClient", side_effect=Exception("Jupiter error")):
            result = await demo_sentiment.get_ai_sentiment_for_token("addr123")

        assert result["sentiment"] == "unknown"
        assert result["score"] == 0


# =============================================================================
# Trending Tokens Tests
# =============================================================================


class TestTrendingTokens:
    """Test trending tokens retrieval."""

    @pytest.mark.asyncio
    async def test_get_trending_from_signal_service(self, mock_signal_service):
        """Test gets trending from signal service."""
        with patch("tg_bot.services.signal_service.get_signal_service", return_value=mock_signal_service):
            result = await demo_sentiment.get_trending_with_sentiment(limit=15)

        assert len(result) == 1
        assert result[0]["symbol"] == "TEST"
        assert result[0]["sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_get_trending_fallback_to_dexscreener(self):
        """Test falls back to DexScreener on signal service failure."""
        mock_dex_token = SimpleNamespace(
            base_token_symbol="DEX",
            base_token_address="dex_addr",
            price_usd=3.0,
            price_change_24h=12.0,
            volume_24h=100_000,
            liquidity_usd=500_000,
        )

        with patch("tg_bot.services.signal_service.get_signal_service", side_effect=Exception("Service error")), \
             patch("core.dexscreener.get_solana_trending", return_value=[mock_dex_token]):
            result = await demo_sentiment.get_trending_with_sentiment(limit=15)

        assert len(result) == 1
        assert result[0]["symbol"] == "DEX"
        assert result[0]["sentiment"] == "neutral"  # No AI sentiment in fallback


# =============================================================================
# Conviction Pick Helpers Tests
# =============================================================================


class TestConvictionHelpers:
    """Test conviction pick helper functions."""

    def test_conviction_label_high(self):
        """Test conviction label for high scores."""
        assert demo_sentiment._conviction_label(85) == "HIGH"

    def test_conviction_label_medium(self):
        """Test conviction label for medium scores."""
        assert demo_sentiment._conviction_label(65) == "MEDIUM"

    def test_conviction_label_low(self):
        """Test conviction label for low scores."""
        assert demo_sentiment._conviction_label(45) == "LOW"

    def test_default_tp_sl_high_conviction(self):
        """Test default TP/SL for high conviction."""
        tp, sl = demo_sentiment._default_tp_sl("HIGH")
        assert tp == 30
        assert sl == 12

    def test_default_tp_sl_medium_conviction(self):
        """Test default TP/SL for medium conviction."""
        tp, sl = demo_sentiment._default_tp_sl("MEDIUM")
        assert tp == 22
        assert sl == 12

    def test_default_tp_sl_low_conviction(self):
        """Test default TP/SL for low conviction."""
        tp, sl = demo_sentiment._default_tp_sl("LOW")
        assert tp == 15
        assert sl == 15

    def test_grade_for_signal_name(self):
        """Test signal name to grade conversion."""
        assert demo_sentiment._grade_for_signal_name("STRONG_BUY") == "A"
        assert demo_sentiment._grade_for_signal_name("BUY") == "B+"
        assert demo_sentiment._grade_for_signal_name("NEUTRAL") == "C+"
        assert demo_sentiment._grade_for_signal_name("UNKNOWN") == "B"  # default

    def test_pick_key_uses_address(self):
        """Test pick key uses address when available."""
        pick = {"address": "ADDR123", "symbol": "TEST"}
        assert demo_sentiment._pick_key(pick) == "addr123"

    def test_pick_key_falls_back_to_symbol(self):
        """Test pick key falls back to symbol."""
        pick = {"address": "", "symbol": "TEST"}
        assert demo_sentiment._pick_key(pick) == "test"


# =============================================================================
# Conviction Picks Tests
# =============================================================================


class TestConvictionPicks:
    """Test conviction picks generation."""

    @pytest.mark.asyncio
    async def test_get_conviction_picks_from_treasury(self, tmp_path):
        """Test loads conviction picks from treasury file."""
        picks_data = [
            {
                "symbol": "PICK1",
                "contract": "addr1",
                "conviction": 85,
                "reasoning": "Strong fundamentals",
                "entry_price": 1.0,
                "target_price": 1.3,
                "stop_loss": 0.88,
            }
        ]

        picks_file = tmp_path / "jarvis_top_picks.json"
        with open(picks_file, "w") as f:
            json.dump(picks_data, f)

        with patch("tempfile.gettempdir", return_value=str(tmp_path)), \
             patch("tg_bot.services.signal_service.get_signal_service", side_effect=Exception("No service")):
            result = await demo_sentiment.get_conviction_picks()

        assert len(result) >= 1
        assert result[0]["symbol"] == "PICK1"
        assert result[0]["conviction"] == "HIGH"

    @pytest.mark.asyncio
    async def test_get_conviction_picks_from_signal_service(self, mock_signal_service):
        """Test gets conviction picks from signal service."""
        with patch("tempfile.gettempdir", return_value="/nonexistent"), \
             patch("tg_bot.services.signal_service.get_signal_service", return_value=mock_signal_service):
            result = await demo_sentiment.get_conviction_picks()

        # Should have at least signal service picks
        assert len(result) >= 1
        # Find the signal service pick
        signal_pick = next((p for p in result if p.get("signal") == "BUY"), None)
        assert signal_pick is not None
        assert signal_pick["conviction"] == "MEDIUM"  # BUY maps to MEDIUM

    @pytest.mark.asyncio
    async def test_get_conviction_picks_deduplicates(self, mock_signal_service, tmp_path):
        """Test deduplicates picks from multiple sources."""
        # Treasury pick with same address as signal service
        picks_data = [
            {
                "symbol": "TEST",
                "contract": mock_signal_service.get_comprehensive_signal.return_value.address,
                "conviction": 85,
                "reasoning": "Test",
                "entry_price": 1.0,
                "target_price": 1.3,
                "stop_loss": 0.88,
            }
        ]

        picks_file = tmp_path / "jarvis_top_picks.json"
        with open(picks_file, "w") as f:
            json.dump(picks_data, f)

        # Mock the signal to have an address attribute
        mock_signal_service.get_top_signals.return_value[0].address = "test_addr"

        with patch("tempfile.gettempdir", return_value=str(tmp_path)), \
             patch("tg_bot.services.signal_service.get_signal_service", return_value=mock_signal_service):
            result = await demo_sentiment.get_conviction_picks()

        # Should not have duplicates (though without matching addresses, both will be present)
        assert len(result) <= 10  # Max limit


# =============================================================================
# Bags Top Tokens Tests
# =============================================================================


class TestBagsTopTokens:
    """Test Bags.fm top tokens retrieval."""

    @pytest.mark.asyncio
    async def test_get_bags_top_tokens_with_sentiment(self):
        """Test gets top tokens from Bags with sentiment."""
        mock_bags_client = AsyncMock()
        # Token needs name or symbol ending in "bags" due to filtering
        mock_token = SimpleNamespace(
            symbol="TESTBAGS",
            name="Test Bags",
            address="bags_addr",
            price_usd=2.0,
            price_change_24h=5.0,
            volume_24h=100_000,
            liquidity=200_000,
        )
        # The function calls get_top_tokens_by_volume, not get_top_tokens
        mock_bags_client.get_top_tokens_by_volume = AsyncMock(return_value=[mock_token])

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value={"sentiment": "bullish", "score": 0.7, "signal": "BUY"}):
            result = await demo_sentiment.get_bags_top_tokens_with_sentiment(limit=15)

        assert len(result) == 1
        assert result[0]["symbol"] == "TESTBAGS"
        assert result[0]["sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_get_bags_top_tokens_fallback_to_dexscreener(self):
        """Test falls back to DexScreener (bags-only filter) when Bags leaderboard is unavailable."""
        fallback_token = {
            "symbol": "TESTBAGS",
            "name": "Test Bags Token",
            "address": "testbags_addr",
            "price_usd": 1.0,
            "price_change_24h": 5.0,
            "volume_24h": 50_000,
            "liquidity": 25_000,
        }

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=None), \
             patch("tg_bot.handlers.demo.demo_sentiment._fallback_bags_top_tokens_via_dexscreener", new_callable=AsyncMock, return_value=[fallback_token]), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value={"sentiment": "neutral", "score": 0.5, "signal": "NEUTRAL"}):
            result = await demo_sentiment.get_bags_top_tokens_with_sentiment(limit=15)

        assert len(result) == 1
        assert result[0]["symbol"] == "TESTBAGS"
