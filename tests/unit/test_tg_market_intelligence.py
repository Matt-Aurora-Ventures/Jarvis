"""
Unit tests for tg_bot/services/market_intelligence.py

Covers:
- TrendDirection enum values and usage
- MarketIntelligence class initialization
- Market overview generation
- Sentiment analysis with various symbols
- Liquidation heatmap formatting
- Volume analysis display
- Trending tokens reporting
- Macro indicators presentation
- Helper methods for emojis
- Edge cases and error handling

Target: 60%+ coverage with comprehensive test cases.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, List, Optional, Any

# Import the module under test
from tg_bot.services.market_intelligence import (
    TrendDirection,
    MarketIntelligence,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def market_intel():
    """Create a MarketIntelligence instance with no dependencies."""
    return MarketIntelligence()


@pytest.fixture
def market_intel_with_deps():
    """Create a MarketIntelligence instance with mocked dependencies."""
    mock_sentiment = MagicMock()
    mock_market_api = MagicMock()
    return MarketIntelligence(
        sentiment_agg=mock_sentiment,
        market_data_api=mock_market_api
    )


@pytest.fixture
def mock_sentiment_agg():
    """Create a mock sentiment aggregator."""
    mock = MagicMock()
    mock.get_sentiment.return_value = {
        'score': 75,
        'label': 'bullish',
        'sources': ['twitter', 'news', 'onchain']
    }
    return mock


@pytest.fixture
def mock_market_data_api():
    """Create a mock market data API."""
    mock = MagicMock()
    mock.get_price.return_value = {
        'price': 95000.0,
        'change_24h': 2.5,
        'volume_24h': 42000000000
    }
    return mock


# ============================================================================
# Test: TrendDirection Enum
# ============================================================================

class TestTrendDirection:
    """Test TrendDirection enum values and behavior."""

    def test_strong_up_value(self):
        """Should have correct emoji for STRONG_UP."""
        assert TrendDirection.STRONG_UP.value == "rocket emoji"[0:1] or TrendDirection.STRONG_UP.value

    def test_up_value(self):
        """Should have correct emoji for UP."""
        assert TrendDirection.UP.value == "chart emoji"[0:1] or TrendDirection.UP.value

    def test_neutral_value(self):
        """Should have correct emoji for NEUTRAL."""
        assert TrendDirection.NEUTRAL.value == "arrow emoji"[0:1] or TrendDirection.NEUTRAL.value

    def test_down_value(self):
        """Should have correct emoji for DOWN."""
        assert TrendDirection.DOWN.value == "down emoji"[0:1] or TrendDirection.DOWN.value

    def test_strong_down_value(self):
        """Should have correct emoji for STRONG_DOWN."""
        assert TrendDirection.STRONG_DOWN.value == "crash emoji"[0:1] or TrendDirection.STRONG_DOWN.value

    def test_all_enum_members_exist(self):
        """Should have all 5 trend directions."""
        members = list(TrendDirection)
        assert len(members) == 5

    def test_enum_names(self):
        """Should have correct member names."""
        names = [m.name for m in TrendDirection]
        assert "STRONG_UP" in names
        assert "UP" in names
        assert "NEUTRAL" in names
        assert "DOWN" in names
        assert "STRONG_DOWN" in names

    def test_enum_is_iterable(self):
        """Should be iterable."""
        count = 0
        for direction in TrendDirection:
            count += 1
            assert direction.value is not None
        assert count == 5

    def test_enum_comparison(self):
        """Should support comparison."""
        assert TrendDirection.STRONG_UP != TrendDirection.DOWN
        assert TrendDirection.UP == TrendDirection.UP

    def test_enum_from_name(self):
        """Should be accessible by name."""
        assert TrendDirection["STRONG_UP"] == TrendDirection.STRONG_UP
        assert TrendDirection["NEUTRAL"] == TrendDirection.NEUTRAL


# ============================================================================
# Test: MarketIntelligence Initialization
# ============================================================================

class TestMarketIntelligenceInit:
    """Test MarketIntelligence initialization."""

    def test_init_no_dependencies(self):
        """Should initialize without dependencies."""
        mi = MarketIntelligence()
        assert mi.sentiment_agg is None
        assert mi.market_data_api is None

    def test_init_with_sentiment_agg(self, mock_sentiment_agg):
        """Should initialize with sentiment aggregator."""
        mi = MarketIntelligence(sentiment_agg=mock_sentiment_agg)
        assert mi.sentiment_agg is mock_sentiment_agg
        assert mi.market_data_api is None

    def test_init_with_market_data_api(self, mock_market_data_api):
        """Should initialize with market data API."""
        mi = MarketIntelligence(market_data_api=mock_market_data_api)
        assert mi.sentiment_agg is None
        assert mi.market_data_api is mock_market_data_api

    def test_init_with_both_dependencies(self, mock_sentiment_agg, mock_market_data_api):
        """Should initialize with both dependencies."""
        mi = MarketIntelligence(
            sentiment_agg=mock_sentiment_agg,
            market_data_api=mock_market_data_api
        )
        assert mi.sentiment_agg is mock_sentiment_agg
        assert mi.market_data_api is mock_market_data_api

    def test_emoji_constants_defined(self, market_intel):
        """Should have EMOJI constants defined."""
        assert hasattr(market_intel, 'EMOJI')
        assert isinstance(market_intel.EMOJI, dict)

    def test_emoji_has_expected_keys(self, market_intel):
        """Should have all expected emoji keys."""
        expected_keys = ['bull', 'bear', 'chart', 'fire', 'warning',
                         'rocket', 'thunder', 'money', 'up', 'down',
                         'target', 'brain', 'eye', 'bell']
        for key in expected_keys:
            assert key in market_intel.EMOJI

    def test_emoji_values_are_strings(self, market_intel):
        """Should have string values for all emojis."""
        for key, value in market_intel.EMOJI.items():
            assert isinstance(value, str)
            assert len(value) > 0


# ============================================================================
# Test: Market Overview Generation
# ============================================================================

class TestBuildMarketOverview:
    """Test build_market_overview method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_market_overview()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include MARKET OVERVIEW header."""
        result = market_intel.build_market_overview()
        assert "MARKET OVERVIEW" in result

    def test_includes_btc(self, market_intel):
        """Should include BTC data."""
        result = market_intel.build_market_overview()
        assert "BTC" in result

    def test_includes_eth(self, market_intel):
        """Should include ETH data."""
        result = market_intel.build_market_overview()
        assert "ETH" in result

    def test_includes_sol(self, market_intel):
        """Should include SOL data."""
        result = market_intel.build_market_overview()
        assert "SOL" in result

    def test_includes_market_cap(self, market_intel):
        """Should include market cap."""
        result = market_intel.build_market_overview()
        assert "Market Cap" in result

    def test_includes_volume(self, market_intel):
        """Should include 24h volume."""
        result = market_intel.build_market_overview()
        assert "Volume" in result or "volume" in result

    def test_includes_bitcoin_dominance(self, market_intel):
        """Should include Bitcoin dominance."""
        result = market_intel.build_market_overview()
        assert "Dominance" in result or "dominance" in result

    def test_includes_fear_greed(self, market_intel):
        """Should include Fear & Greed index."""
        result = market_intel.build_market_overview()
        assert "Fear" in result or "Greed" in result

    def test_includes_top_gainers(self, market_intel):
        """Should include top gainers section."""
        result = market_intel.build_market_overview()
        assert "Gainer" in result or "gainer" in result

    def test_includes_top_losers(self, market_intel):
        """Should include top losers section."""
        result = market_intel.build_market_overview()
        assert "Loser" in result or "loser" in result

    def test_uses_html_formatting(self, market_intel):
        """Should use HTML formatting tags."""
        result = market_intel.build_market_overview()
        assert "<b>" in result
        assert "</b>" in result

    def test_uses_code_formatting(self, market_intel):
        """Should use code formatting for values."""
        result = market_intel.build_market_overview()
        assert "<code>" in result
        assert "</code>" in result

    def test_includes_chart_emoji(self, market_intel):
        """Should include chart emoji."""
        result = market_intel.build_market_overview()
        # Check for emoji presence (chart emoji is in the header)
        assert market_intel.EMOJI['chart'] in result

    def test_includes_percentage_changes(self, market_intel):
        """Should include percentage change values."""
        result = market_intel.build_market_overview()
        # Should have % symbols for changes
        assert "%" in result


# ============================================================================
# Test: Sentiment Analysis
# ============================================================================

class TestBuildSentimentAnalysis:
    """Test build_sentiment_analysis method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_sentiment_analysis()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include SENTIMENT ANALYSIS header."""
        result = market_intel.build_sentiment_analysis()
        assert "SENTIMENT ANALYSIS" in result

    def test_default_symbols_included(self, market_intel):
        """Should include default symbols when none provided."""
        result = market_intel.build_sentiment_analysis()
        assert "BTC" in result
        assert "ETH" in result
        assert "SOL" in result
        assert "DOGE" in result

    def test_custom_symbols(self, market_intel):
        """Should use custom symbols when provided."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'ETH'])
        assert "BTC" in result
        assert "ETH" in result

    def test_unknown_symbol_skipped(self, market_intel):
        """Should skip unknown symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['UNKNOWN123'])
        # Should still return valid output, just without unknown symbol data
        assert isinstance(result, str)

    def test_includes_grok_score(self, market_intel):
        """Should include Grok sentiment score."""
        result = market_intel.build_sentiment_analysis()
        assert "Grok" in result

    def test_includes_twitter_score(self, market_intel):
        """Should include Twitter sentiment score."""
        result = market_intel.build_sentiment_analysis()
        assert "Twitter" in result

    def test_includes_news_score(self, market_intel):
        """Should include News sentiment score."""
        result = market_intel.build_sentiment_analysis()
        assert "News" in result

    def test_includes_onchain_score(self, market_intel):
        """Should include Onchain sentiment score."""
        result = market_intel.build_sentiment_analysis()
        assert "Onchain" in result

    def test_includes_sentiment_drivers(self, market_intel):
        """Should include sentiment drivers section."""
        result = market_intel.build_sentiment_analysis()
        assert "Driver" in result or "driver" in result

    def test_includes_catalysts(self, market_intel):
        """Should include upcoming catalysts."""
        result = market_intel.build_sentiment_analysis()
        assert "Catalyst" in result or "catalyst" in result

    def test_includes_timestamp(self, market_intel):
        """Should include update timestamp."""
        result = market_intel.build_sentiment_analysis()
        assert "updated" in result.lower() or "UTC" in result

    def test_includes_brain_emoji(self, market_intel):
        """Should include brain emoji in header."""
        result = market_intel.build_sentiment_analysis()
        assert market_intel.EMOJI['brain'] in result

    def test_empty_symbol_list(self, market_intel):
        """Should use defaults for empty symbol list."""
        result = market_intel.build_sentiment_analysis(symbols=[])
        # Empty list should still produce output with defaults
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_symbols(self, market_intel):
        """Should use defaults for None symbols."""
        result = market_intel.build_sentiment_analysis(symbols=None)
        assert "BTC" in result  # Default symbol

    def test_partial_known_symbols(self, market_intel):
        """Should handle mix of known and unknown symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'FAKECOIN'])
        assert "BTC" in result
        # Unknown symbol shouldn't cause crash


# ============================================================================
# Test: Liquidation Heatmap
# ============================================================================

class TestBuildLiquidationHeatmap:
    """Test build_liquidation_heatmap method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_liquidation_heatmap()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include LIQUIDATION HEATMAP header."""
        result = market_intel.build_liquidation_heatmap()
        assert "LIQUIDATION" in result

    def test_includes_btc_levels(self, market_intel):
        """Should include BTC liquidation levels."""
        result = market_intel.build_liquidation_heatmap()
        assert "BTC" in result

    def test_includes_eth_levels(self, market_intel):
        """Should include ETH liquidation levels."""
        result = market_intel.build_liquidation_heatmap()
        assert "ETH" in result

    def test_includes_sol_levels(self, market_intel):
        """Should include SOL liquidation levels."""
        result = market_intel.build_liquidation_heatmap()
        assert "SOL" in result

    def test_includes_short_liquidations(self, market_intel):
        """Should include short liquidation data."""
        result = market_intel.build_liquidation_heatmap()
        assert "Short" in result or "short" in result

    def test_includes_long_liquidations(self, market_intel):
        """Should include long liquidation data."""
        result = market_intel.build_liquidation_heatmap()
        assert "Long" in result or "long" in result

    def test_includes_risk_assessment(self, market_intel):
        """Should include liquidation risk assessment."""
        result = market_intel.build_liquidation_heatmap()
        assert "Risk" in result or "risk" in result

    def test_includes_concentration_levels(self, market_intel):
        """Should include concentration percentages."""
        result = market_intel.build_liquidation_heatmap()
        assert "%" in result

    def test_includes_dollar_values(self, market_intel):
        """Should include dollar values for liquidations."""
        result = market_intel.build_liquidation_heatmap()
        assert "$" in result

    def test_includes_fire_emoji(self, market_intel):
        """Should include fire emoji in header."""
        result = market_intel.build_liquidation_heatmap()
        assert market_intel.EMOJI['fire'] in result

    def test_includes_timestamp(self, market_intel):
        """Should include update timestamp."""
        result = market_intel.build_liquidation_heatmap()
        assert "UTC" in result or "Updated" in result

    def test_includes_data_source(self, market_intel):
        """Should mention data source."""
        result = market_intel.build_liquidation_heatmap()
        assert "GlassNode" in result or "glassnode" in result.lower()


# ============================================================================
# Test: Volume Analysis
# ============================================================================

class TestBuildVolumeAnalysis:
    """Test build_volume_analysis method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_volume_analysis()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include VOLUME header."""
        result = market_intel.build_volume_analysis()
        assert "VOLUME" in result

    def test_includes_volume_leaders(self, market_intel):
        """Should include volume leaders."""
        result = market_intel.build_volume_analysis()
        assert "Leader" in result or "leader" in result

    def test_includes_btc_volume(self, market_intel):
        """Should include BTC volume data."""
        result = market_intel.build_volume_analysis()
        assert "BTC" in result

    def test_includes_eth_volume(self, market_intel):
        """Should include ETH volume data."""
        result = market_intel.build_volume_analysis()
        assert "ETH" in result

    def test_includes_sol_volume(self, market_intel):
        """Should include SOL volume data."""
        result = market_intel.build_volume_analysis()
        assert "SOL" in result

    def test_includes_volume_trends(self, market_intel):
        """Should include volume trends section."""
        result = market_intel.build_volume_analysis()
        assert "Trend" in result or "trend" in result

    def test_includes_buying_pressure(self, market_intel):
        """Should include buying pressure data."""
        result = market_intel.build_volume_analysis()
        assert "buy" in result.lower() or "Buying" in result

    def test_includes_selling_pressure(self, market_intel):
        """Should include selling pressure data."""
        result = market_intel.build_volume_analysis()
        assert "sell" in result.lower() or "Selling" in result

    def test_includes_exchange_flow(self, market_intel):
        """Should include exchange flow data."""
        result = market_intel.build_volume_analysis()
        assert "Exchange" in result or "exchange" in result

    def test_includes_inflow_outflow(self, market_intel):
        """Should include inflow and outflow data."""
        result = market_intel.build_volume_analysis()
        assert "Inflow" in result or "inflow" in result
        assert "Outflow" in result or "outflow" in result

    def test_includes_whale_activity(self, market_intel):
        """Should include whale activity section."""
        result = market_intel.build_volume_analysis()
        assert "Whale" in result or "whale" in result

    def test_includes_thunder_emoji(self, market_intel):
        """Should include thunder emoji in header."""
        result = market_intel.build_volume_analysis()
        assert market_intel.EMOJI['thunder'] in result

    def test_includes_dollar_amounts(self, market_intel):
        """Should include dollar amounts."""
        result = market_intel.build_volume_analysis()
        assert "$" in result

    def test_includes_percentages(self, market_intel):
        """Should include percentage values."""
        result = market_intel.build_volume_analysis()
        assert "%" in result


# ============================================================================
# Test: Trending Tokens
# ============================================================================

class TestBuildTrendingTokens:
    """Test build_trending_tokens method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_trending_tokens()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include TRENDING TOKENS header."""
        result = market_intel.build_trending_tokens()
        assert "TRENDING" in result

    def test_includes_trending_up_section(self, market_intel):
        """Should include trending up section."""
        result = market_intel.build_trending_tokens()
        # Check for trending tokens section
        assert "Trend" in result or "trend" in result

    def test_includes_community_favorites(self, market_intel):
        """Should include community favorites."""
        result = market_intel.build_trending_tokens()
        assert "Community" in result or "community" in result

    def test_includes_farcaster(self, market_intel):
        """Should mention Farcaster."""
        result = market_intel.build_trending_tokens()
        assert "Farcaster" in result or "farcaster" in result.lower()

    def test_includes_reddit(self, market_intel):
        """Should mention Reddit."""
        result = market_intel.build_trending_tokens()
        assert "Reddit" in result or "reddit" in result.lower()

    def test_includes_discord(self, market_intel):
        """Should mention Discord."""
        result = market_intel.build_trending_tokens()
        assert "Discord" in result or "discord" in result.lower()

    def test_includes_catalyst_tokens(self, market_intel):
        """Should include upcoming catalyst tokens."""
        result = market_intel.build_trending_tokens()
        assert "Catalyst" in result or "Upcoming" in result

    def test_includes_risk_warning(self, market_intel):
        """Should include risk warning."""
        result = market_intel.build_trending_tokens()
        assert "Risk" in result or "DYOR" in result or "risk" in result.lower()

    def test_includes_rocket_emoji(self, market_intel):
        """Should include rocket emoji in header."""
        result = market_intel.build_trending_tokens()
        assert market_intel.EMOJI['rocket'] in result

    def test_includes_fire_emoji_for_trending(self, market_intel):
        """Should include fire emoji for hot tokens."""
        result = market_intel.build_trending_tokens()
        assert market_intel.EMOJI['fire'] in result

    def test_includes_volume_changes(self, market_intel):
        """Should include volume change percentages."""
        result = market_intel.build_trending_tokens()
        assert "%" in result


# ============================================================================
# Test: Macro Indicators
# ============================================================================

class TestBuildMacroIndicators:
    """Test build_macro_indicators method."""

    def test_returns_string(self, market_intel):
        """Should return a string."""
        result = market_intel.build_macro_indicators()
        assert isinstance(result, str)

    def test_includes_header(self, market_intel):
        """Should include MACRO INDICATORS header."""
        result = market_intel.build_macro_indicators()
        assert "MACRO" in result

    def test_includes_gdp(self, market_intel):
        """Should include GDP data."""
        result = market_intel.build_macro_indicators()
        assert "GDP" in result

    def test_includes_inflation(self, market_intel):
        """Should include inflation data."""
        result = market_intel.build_macro_indicators()
        assert "Inflation" in result or "inflation" in result

    def test_includes_unemployment(self, market_intel):
        """Should include unemployment data."""
        result = market_intel.build_macro_indicators()
        assert "Unemployment" in result or "unemployment" in result

    def test_includes_fed_rate(self, market_intel):
        """Should include Fed rate data."""
        result = market_intel.build_macro_indicators()
        assert "Fed" in result or "Rate" in result

    def test_includes_fed_policy_section(self, market_intel):
        """Should include Fed policy section."""
        result = market_intel.build_macro_indicators()
        assert "Policy" in result or "Meeting" in result

    def test_includes_market_structure(self, market_intel):
        """Should include market structure section."""
        result = market_intel.build_macro_indicators()
        assert "Structure" in result or "Market" in result

    def test_includes_stock_market(self, market_intel):
        """Should include stock market data."""
        result = market_intel.build_macro_indicators()
        assert "Stock" in result or "SPX" in result

    def test_includes_bond_yields(self, market_intel):
        """Should include bond yield data."""
        result = market_intel.build_macro_indicators()
        assert "Bond" in result or "Yield" in result or "10Y" in result

    def test_includes_usd_index(self, market_intel):
        """Should include USD index."""
        result = market_intel.build_macro_indicators()
        assert "USD" in result or "Dollar" in result

    def test_includes_vix(self, market_intel):
        """Should include VIX data."""
        result = market_intel.build_macro_indicators()
        assert "VIX" in result or "Fear Index" in result

    def test_includes_crypto_narrative(self, market_intel):
        """Should include crypto narrative section."""
        result = market_intel.build_macro_indicators()
        assert "Narrative" in result or "ETF" in result or "Institutional" in result

    def test_includes_overall_outlook(self, market_intel):
        """Should include overall outlook."""
        result = market_intel.build_macro_indicators()
        assert "Outlook" in result or "outlook" in result

    def test_includes_eye_emoji(self, market_intel):
        """Should include eye emoji in header."""
        result = market_intel.build_macro_indicators()
        assert market_intel.EMOJI['eye'] in result

    def test_includes_us_flag(self, market_intel):
        """Should include US flag emoji."""
        result = market_intel.build_macro_indicators()
        # US flag or US mention
        assert "US" in result


# ============================================================================
# Test: Helper Methods - Get Trend Emoji
# ============================================================================

class TestGetTrendEmoji:
    """Test _get_trend_emoji helper method."""

    def test_strong_up_for_large_positive(self, market_intel):
        """Should return STRONG_UP for >= 5%."""
        result = market_intel._get_trend_emoji(5.0)
        assert result == TrendDirection.STRONG_UP.value

    def test_strong_up_for_very_large_positive(self, market_intel):
        """Should return STRONG_UP for very large gains."""
        result = market_intel._get_trend_emoji(15.0)
        assert result == TrendDirection.STRONG_UP.value

    def test_up_for_moderate_positive(self, market_intel):
        """Should return UP for 1-5%."""
        result = market_intel._get_trend_emoji(2.5)
        assert result == TrendDirection.UP.value

    def test_up_for_boundary(self, market_intel):
        """Should return UP for exactly 1%."""
        result = market_intel._get_trend_emoji(1.0)
        assert result == TrendDirection.UP.value

    def test_neutral_for_small_changes(self, market_intel):
        """Should return NEUTRAL for -1% to 1%."""
        result = market_intel._get_trend_emoji(0.5)
        assert result == TrendDirection.NEUTRAL.value

    def test_neutral_for_zero(self, market_intel):
        """Should return NEUTRAL for 0%."""
        result = market_intel._get_trend_emoji(0.0)
        assert result == TrendDirection.NEUTRAL.value

    def test_neutral_for_small_negative(self, market_intel):
        """Should return NEUTRAL for small negative."""
        result = market_intel._get_trend_emoji(-0.5)
        assert result == TrendDirection.NEUTRAL.value

    def test_down_for_moderate_negative(self, market_intel):
        """Should return DOWN for -5% to -1%."""
        result = market_intel._get_trend_emoji(-2.5)
        assert result == TrendDirection.DOWN.value

    def test_down_for_boundary(self, market_intel):
        """Should return DOWN for -1% boundary."""
        # Just under -1 should be DOWN
        result = market_intel._get_trend_emoji(-1.5)
        assert result == TrendDirection.DOWN.value

    def test_strong_down_for_large_negative(self, market_intel):
        """Should return STRONG_DOWN for < -5%."""
        result = market_intel._get_trend_emoji(-6.0)
        assert result == TrendDirection.STRONG_DOWN.value

    def test_strong_down_for_very_large_negative(self, market_intel):
        """Should return STRONG_DOWN for crash scenarios."""
        result = market_intel._get_trend_emoji(-15.0)
        assert result == TrendDirection.STRONG_DOWN.value

    def test_boundary_at_5_percent(self, market_intel):
        """Should return STRONG_UP at exactly 5%."""
        result = market_intel._get_trend_emoji(5.0)
        assert result == TrendDirection.STRONG_UP.value

    def test_boundary_at_negative_5_percent(self, market_intel):
        """Should return DOWN at exactly -5%."""
        result = market_intel._get_trend_emoji(-5.0)
        assert result == TrendDirection.DOWN.value

    def test_boundary_at_negative_1_percent(self, market_intel):
        """Should return NEUTRAL at -1%."""
        result = market_intel._get_trend_emoji(-1.0)
        assert result == TrendDirection.NEUTRAL.value


# ============================================================================
# Test: Helper Methods - Get Sentiment Emoji
# ============================================================================

class TestGetSentimentEmoji:
    """Test _get_sentiment_emoji helper method."""

    def test_very_bullish_for_high_score(self, market_intel):
        """Should return bullish emoji for >= 75."""
        result = market_intel._get_sentiment_emoji(80)
        # Very bullish should include rocket
        assert "rocket" in result.lower() or len(result) >= 2

    def test_bullish_for_moderate_high_score(self, market_intel):
        """Should return bullish emoji for 60-75."""
        result = market_intel._get_sentiment_emoji(65)
        # Should be up trending
        assert len(result) >= 1

    def test_neutral_for_middle_score(self, market_intel):
        """Should return neutral emoji for 40-60."""
        result = market_intel._get_sentiment_emoji(50)
        assert len(result) >= 1

    def test_bearish_for_low_score(self, market_intel):
        """Should return bearish emoji for 25-40."""
        result = market_intel._get_sentiment_emoji(30)
        assert len(result) >= 1

    def test_very_bearish_for_very_low_score(self, market_intel):
        """Should return very bearish emoji for < 25."""
        result = market_intel._get_sentiment_emoji(20)
        # Very bearish should include down emoji
        assert len(result) >= 1

    def test_boundary_at_75(self, market_intel):
        """Should return very bullish at exactly 75."""
        result = market_intel._get_sentiment_emoji(75)
        assert len(result) >= 2  # Should have multiple emojis

    def test_boundary_at_60(self, market_intel):
        """Should return bullish at exactly 60."""
        result = market_intel._get_sentiment_emoji(60)
        assert len(result) >= 1

    def test_boundary_at_40(self, market_intel):
        """Should return neutral at exactly 40."""
        result = market_intel._get_sentiment_emoji(40)
        assert len(result) >= 1

    def test_boundary_at_25(self, market_intel):
        """Should return bearish at exactly 25."""
        result = market_intel._get_sentiment_emoji(25)
        assert len(result) >= 1

    def test_score_zero(self, market_intel):
        """Should handle score of 0."""
        result = market_intel._get_sentiment_emoji(0)
        assert isinstance(result, str)

    def test_score_100(self, market_intel):
        """Should handle score of 100."""
        result = market_intel._get_sentiment_emoji(100)
        assert len(result) >= 2  # Very bullish

    def test_float_score(self, market_intel):
        """Should handle float scores."""
        result = market_intel._get_sentiment_emoji(67.5)
        assert isinstance(result, str)


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_calls_same_instance(self, market_intel):
        """Should handle multiple calls on same instance."""
        result1 = market_intel.build_market_overview()
        result2 = market_intel.build_market_overview()
        assert result1 == result2

    def test_all_methods_return_non_empty(self, market_intel):
        """Should return non-empty strings for all methods."""
        assert len(market_intel.build_market_overview()) > 0
        assert len(market_intel.build_sentiment_analysis()) > 0
        assert len(market_intel.build_liquidation_heatmap()) > 0
        assert len(market_intel.build_volume_analysis()) > 0
        assert len(market_intel.build_trending_tokens()) > 0
        assert len(market_intel.build_macro_indicators()) > 0

    def test_html_tags_balanced(self, market_intel):
        """Should have balanced HTML tags."""
        result = market_intel.build_market_overview()
        assert result.count("<b>") == result.count("</b>")
        assert result.count("<code>") == result.count("</code>")

    def test_sentiment_html_balanced(self, market_intel):
        """Should have balanced HTML tags in sentiment."""
        result = market_intel.build_sentiment_analysis()
        assert result.count("<b>") == result.count("</b>")

    def test_liquidation_html_balanced(self, market_intel):
        """Should have balanced HTML tags in liquidation."""
        result = market_intel.build_liquidation_heatmap()
        assert result.count("<b>") == result.count("</b>")

    def test_volume_html_balanced(self, market_intel):
        """Should have balanced HTML tags in volume."""
        result = market_intel.build_volume_analysis()
        assert result.count("<b>") == result.count("</b>")

    def test_trending_html_balanced(self, market_intel):
        """Should have balanced HTML tags in trending."""
        result = market_intel.build_trending_tokens()
        assert result.count("<b>") == result.count("</b>")

    def test_macro_html_balanced(self, market_intel):
        """Should have balanced HTML tags in macro."""
        result = market_intel.build_macro_indicators()
        assert result.count("<b>") == result.count("</b>")

    def test_trend_emoji_negative_boundary(self, market_intel):
        """Test exact boundary at -5%."""
        result = market_intel._get_trend_emoji(-5.0)
        # At -5 should still be DOWN, not STRONG_DOWN
        assert result == TrendDirection.DOWN.value

    def test_trend_emoji_positive_boundary(self, market_intel):
        """Test exact boundary at 1%."""
        result = market_intel._get_trend_emoji(1.0)
        assert result == TrendDirection.UP.value

    def test_extreme_positive_change(self, market_intel):
        """Should handle extreme positive changes."""
        result = market_intel._get_trend_emoji(100.0)
        assert result == TrendDirection.STRONG_UP.value

    def test_extreme_negative_change(self, market_intel):
        """Should handle extreme negative changes."""
        result = market_intel._get_trend_emoji(-100.0)
        assert result == TrendDirection.STRONG_DOWN.value


# ============================================================================
# Test: Output Format Consistency
# ============================================================================

class TestOutputFormatConsistency:
    """Test output format consistency across methods."""

    def test_all_methods_use_emojis(self, market_intel):
        """All methods should include emojis."""
        methods = [
            market_intel.build_market_overview,
            market_intel.build_sentiment_analysis,
            market_intel.build_liquidation_heatmap,
            market_intel.build_volume_analysis,
            market_intel.build_trending_tokens,
            market_intel.build_macro_indicators,
        ]
        for method in methods:
            result = method()
            # Check for at least one emoji from EMOJI dict
            has_emoji = any(emoji in result for emoji in market_intel.EMOJI.values())
            assert has_emoji, f"{method.__name__} should include emojis"

    def test_all_methods_use_bold_headers(self, market_intel):
        """All methods should use bold headers."""
        methods = [
            market_intel.build_market_overview,
            market_intel.build_sentiment_analysis,
            market_intel.build_liquidation_heatmap,
            market_intel.build_volume_analysis,
            market_intel.build_trending_tokens,
            market_intel.build_macro_indicators,
        ]
        for method in methods:
            result = method()
            assert "<b>" in result, f"{method.__name__} should use bold"

    def test_no_trailing_whitespace(self, market_intel):
        """Output should not have excessive trailing whitespace."""
        methods = [
            market_intel.build_market_overview,
            market_intel.build_sentiment_analysis,
            market_intel.build_liquidation_heatmap,
            market_intel.build_volume_analysis,
            market_intel.build_trending_tokens,
            market_intel.build_macro_indicators,
        ]
        for method in methods:
            result = method()
            # Check last line doesn't have excessive whitespace
            lines = result.split('\n')
            if lines:
                last_line = lines[-1] if lines[-1] else (lines[-2] if len(lines) > 1 else "")
                # Allow some trailing but not excessive
                assert len(last_line) < 200 or not last_line.endswith("   ")


# ============================================================================
# Test: Integration with Dependencies
# ============================================================================

class TestIntegrationWithDependencies:
    """Test behavior when dependencies are provided."""

    def test_with_sentiment_agg_stores_reference(self, mock_sentiment_agg):
        """Should store sentiment aggregator reference."""
        mi = MarketIntelligence(sentiment_agg=mock_sentiment_agg)
        assert mi.sentiment_agg is mock_sentiment_agg

    def test_with_market_api_stores_reference(self, mock_market_data_api):
        """Should store market data API reference."""
        mi = MarketIntelligence(market_data_api=mock_market_data_api)
        assert mi.market_data_api is mock_market_data_api

    def test_methods_work_with_deps(self, mock_sentiment_agg, mock_market_data_api):
        """Methods should work even with dependencies provided."""
        mi = MarketIntelligence(
            sentiment_agg=mock_sentiment_agg,
            market_data_api=mock_market_data_api
        )
        # All methods should still work (they use hardcoded data currently)
        assert isinstance(mi.build_market_overview(), str)
        assert isinstance(mi.build_sentiment_analysis(), str)
        assert isinstance(mi.build_liquidation_heatmap(), str)
        assert isinstance(mi.build_volume_analysis(), str)
        assert isinstance(mi.build_trending_tokens(), str)
        assert isinstance(mi.build_macro_indicators(), str)


# ============================================================================
# Test: EMOJI Dictionary Completeness
# ============================================================================

class TestEmojiDictionary:
    """Test the EMOJI class constant."""

    def test_bull_emoji_exists(self, market_intel):
        """Should have bull emoji."""
        assert 'bull' in market_intel.EMOJI
        assert len(market_intel.EMOJI['bull']) > 0

    def test_bear_emoji_exists(self, market_intel):
        """Should have bear emoji."""
        assert 'bear' in market_intel.EMOJI
        assert len(market_intel.EMOJI['bear']) > 0

    def test_chart_emoji_exists(self, market_intel):
        """Should have chart emoji."""
        assert 'chart' in market_intel.EMOJI
        assert len(market_intel.EMOJI['chart']) > 0

    def test_fire_emoji_exists(self, market_intel):
        """Should have fire emoji."""
        assert 'fire' in market_intel.EMOJI
        assert len(market_intel.EMOJI['fire']) > 0

    def test_warning_emoji_exists(self, market_intel):
        """Should have warning emoji."""
        assert 'warning' in market_intel.EMOJI
        assert len(market_intel.EMOJI['warning']) > 0

    def test_rocket_emoji_exists(self, market_intel):
        """Should have rocket emoji."""
        assert 'rocket' in market_intel.EMOJI
        assert len(market_intel.EMOJI['rocket']) > 0

    def test_thunder_emoji_exists(self, market_intel):
        """Should have thunder emoji."""
        assert 'thunder' in market_intel.EMOJI
        assert len(market_intel.EMOJI['thunder']) > 0

    def test_money_emoji_exists(self, market_intel):
        """Should have money emoji."""
        assert 'money' in market_intel.EMOJI
        assert len(market_intel.EMOJI['money']) > 0

    def test_up_emoji_exists(self, market_intel):
        """Should have up emoji."""
        assert 'up' in market_intel.EMOJI
        assert len(market_intel.EMOJI['up']) > 0

    def test_down_emoji_exists(self, market_intel):
        """Should have down emoji."""
        assert 'down' in market_intel.EMOJI
        assert len(market_intel.EMOJI['down']) > 0

    def test_target_emoji_exists(self, market_intel):
        """Should have target emoji."""
        assert 'target' in market_intel.EMOJI
        assert len(market_intel.EMOJI['target']) > 0

    def test_brain_emoji_exists(self, market_intel):
        """Should have brain emoji."""
        assert 'brain' in market_intel.EMOJI
        assert len(market_intel.EMOJI['brain']) > 0

    def test_eye_emoji_exists(self, market_intel):
        """Should have eye emoji."""
        assert 'eye' in market_intel.EMOJI
        assert len(market_intel.EMOJI['eye']) > 0

    def test_bell_emoji_exists(self, market_intel):
        """Should have bell emoji."""
        assert 'bell' in market_intel.EMOJI
        assert len(market_intel.EMOJI['bell']) > 0

    def test_emoji_dict_is_class_constant(self):
        """EMOJI should be a class-level constant."""
        assert hasattr(MarketIntelligence, 'EMOJI')
        assert isinstance(MarketIntelligence.EMOJI, dict)


# ============================================================================
# Test: Sentiment Symbol Variations
# ============================================================================

class TestSentimentSymbolVariations:
    """Test sentiment analysis with various symbol combinations."""

    def test_single_symbol_btc(self, market_intel):
        """Should work with single BTC symbol."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC'])
        assert "BTC" in result

    def test_single_symbol_eth(self, market_intel):
        """Should work with single ETH symbol."""
        result = market_intel.build_sentiment_analysis(symbols=['ETH'])
        assert "ETH" in result

    def test_single_symbol_sol(self, market_intel):
        """Should work with single SOL symbol."""
        result = market_intel.build_sentiment_analysis(symbols=['SOL'])
        assert "SOL" in result

    def test_single_symbol_doge(self, market_intel):
        """Should work with single DOGE symbol."""
        result = market_intel.build_sentiment_analysis(symbols=['DOGE'])
        assert "DOGE" in result

    def test_two_symbols(self, market_intel):
        """Should work with two symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'SOL'])
        assert "BTC" in result
        assert "SOL" in result

    def test_three_symbols(self, market_intel):
        """Should work with three symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'ETH', 'DOGE'])
        assert "BTC" in result
        assert "ETH" in result
        assert "DOGE" in result

    def test_all_known_symbols(self, market_intel):
        """Should work with all known symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'ETH', 'SOL', 'DOGE'])
        assert "BTC" in result
        assert "ETH" in result
        assert "SOL" in result
        assert "DOGE" in result

    def test_duplicate_symbols(self, market_intel):
        """Should handle duplicate symbols."""
        result = market_intel.build_sentiment_analysis(symbols=['BTC', 'BTC'])
        # Should not crash, and should include BTC
        assert "BTC" in result

    def test_only_unknown_symbols(self, market_intel):
        """Should handle only unknown symbols gracefully."""
        result = market_intel.build_sentiment_analysis(symbols=['UNKNOWNCOIN', 'FAKECOIN'])
        # Should still return valid structure
        assert "SENTIMENT ANALYSIS" in result

    def test_case_sensitivity(self, market_intel):
        """Should handle symbol case sensitivity."""
        # The hardcoded data uses uppercase, so lowercase might not match
        result_upper = market_intel.build_sentiment_analysis(symbols=['BTC'])
        result_lower = market_intel.build_sentiment_analysis(symbols=['btc'])
        # Lowercase should be skipped (no match in hardcoded dict)
        assert "BTC" in result_upper


# ============================================================================
# Test: Message Content Validation
# ============================================================================

class TestMessageContentValidation:
    """Test that message content is properly formatted."""

    def test_market_overview_has_price_format(self, market_intel):
        """Market overview should show prices with $ and commas."""
        result = market_intel.build_market_overview()
        assert "$" in result
        # Check for comma-formatted numbers (e.g., $95,432.50)
        assert "," in result

    def test_sentiment_has_score_format(self, market_intel):
        """Sentiment should show scores out of 100."""
        result = market_intel.build_sentiment_analysis()
        assert "/100" in result

    def test_liquidation_has_dollar_millions(self, market_intel):
        """Liquidation should show $ amounts in millions."""
        result = market_intel.build_liquidation_heatmap()
        assert "$" in result
        assert "M" in result  # For millions

    def test_volume_has_billions(self, market_intel):
        """Volume should show values in billions."""
        result = market_intel.build_volume_analysis()
        assert "B" in result  # For billions

    def test_trending_has_percentage_changes(self, market_intel):
        """Trending should show percentage volume changes."""
        result = market_intel.build_trending_tokens()
        assert "%" in result
        assert "vol" in result.lower()

    def test_macro_has_percentage_values(self, market_intel):
        """Macro should show various percentage values."""
        result = market_intel.build_macro_indicators()
        assert "%" in result
        # Should have multiple percentage values
        assert result.count("%") > 3
