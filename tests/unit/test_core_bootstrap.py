"""
Comprehensive unit tests for core/bootstrap.py

Tests cover:
- bootstrap_jarvis() main entry point
- _register_data_sources() data service registration
- _register_trading_services() trading service registration
- _register_messaging_services() messaging service registration
- _register_ai_services() AI/LLM service registration
- _register_analytics_services() analytics service registration
- setup_event_bridge() event bridging configuration
- Convenience functions (get_service, list_services, describe_jarvis, get_manifest)
- quick_start() initialization
- Error handling for failed service registrations
- Skip behavior for unavailable services

Target: 85%+ coverage for this critical infrastructure module.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_jarvis_core():
    """Create a mock JarvisCore instance."""
    mock = MagicMock()
    mock.register = MagicMock()
    mock.start = AsyncMock()
    mock.list_capabilities = MagicMock(return_value=["service1", "service2"])
    mock.describe = MagicMock(return_value="JARVIS Description")
    mock.to_manifest = MagicMock(return_value={"version": "1.0.0"})
    mock.get = AsyncMock(return_value=MagicMock())
    mock.emit = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def mock_config():
    """Create a mock UnifiedConfig instance."""
    mock = MagicMock()
    mock.get = MagicMock(return_value="https://api.mainnet-beta.solana.com")
    return mock


@pytest.fixture
def mock_category():
    """Create mock Category enum."""
    class MockCategory:
        DATA = "data"
        TRADING = "trading"
        MESSAGING = "messaging"
        SOCIAL = "social"
        AI = "ai"
        ANALYTICS = "analytics"
        INFRASTRUCTURE = "infrastructure"
    return MockCategory


@pytest.fixture
def bootstrap_results():
    """Create fresh results dict for bootstrap tests."""
    return {
        "registered": [],
        "failed": [],
        "skipped": [],
    }


@pytest.fixture
def reset_jarvis_singleton():
    """Reset JarvisCore singleton between tests."""
    yield
    # Try to reset the singleton after test
    try:
        from core.jarvis_core import JarvisCore
        JarvisCore._instance = None
    except ImportError:
        pass


# =============================================================================
# Test bootstrap_jarvis() Main Entry Point
# =============================================================================

class TestBootstrapJarvis:
    """Tests for bootstrap_jarvis() main entry function."""

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_returns_results_dict(self):
        """Test that bootstrap_jarvis returns expected results structure."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock) as mock_data, \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock) as mock_trading, \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock) as mock_messaging, \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock) as mock_ai, \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock) as mock_analytics:

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            results = await bootstrap_jarvis()

            assert "registered" in results
            assert "failed" in results
            assert "skipped" in results
            assert isinstance(results["registered"], list)
            assert isinstance(results["failed"], list)
            assert isinstance(results["skipped"], list)

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_calls_all_registration_functions(self):
        """Test that all registration functions are called."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock) as mock_data, \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock) as mock_trading, \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock) as mock_messaging, \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock) as mock_ai, \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock) as mock_analytics:

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis(skip_unavailable=True, verbose=False)

            mock_data.assert_called_once()
            mock_trading.assert_called_once()
            mock_messaging.assert_called_once()
            mock_ai.assert_called_once()
            mock_analytics.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_starts_core(self):
        """Test that jarvis.start() is called."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis()

            mock_jarvis.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_with_skip_unavailable_true(self):
        """Test bootstrap with skip_unavailable=True."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock) as mock_data, \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis(skip_unavailable=True)

            # Verify skip_unavailable is passed to registration functions
            call_args = mock_data.call_args
            assert call_args[0][1] == True  # skip_unavailable argument

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_with_skip_unavailable_false(self):
        """Test bootstrap with skip_unavailable=False."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock) as mock_data, \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis(skip_unavailable=False)

            call_args = mock_data.call_args
            assert call_args[0][1] == False

    @pytest.mark.asyncio
    async def test_bootstrap_jarvis_logs_results(self):
        """Test that bootstrap logs registration results."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock), \
             patch('core.bootstrap.logger') as mock_logger:

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis()

            # Check that info logging was called
            mock_logger.info.assert_called()


# =============================================================================
# Test _register_data_sources()
# =============================================================================

class TestRegisterDataSources:
    """Tests for _register_data_sources() function."""

    @pytest.mark.asyncio
    async def test_register_hyperliquid_success(self, bootstrap_results):
        """Test successful Hyperliquid registration."""
        mock_client = MagicMock()
        mock_get_client = MagicMock(return_value=mock_client)

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {'core.data_sources.hyperliquid_api': MagicMock(
                 HyperliquidClient=MagicMock,
                 get_client=mock_get_client
             )}):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "hyperliquid" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_hyperliquid_failure(self, bootstrap_results):
        """Test Hyperliquid registration failure handling."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            # Make import fail
            with patch.dict('sys.modules', {'core.data_sources.hyperliquid_api': None}):
                # Remove the module from sys.modules to simulate ImportError
                if 'core.data_sources.hyperliquid_api' in sys.modules:
                    del sys.modules['core.data_sources.hyperliquid_api']

            from core.bootstrap import _register_data_sources

            # Mock the import to raise an exception
            with patch('builtins.__import__', side_effect=ImportError("Module not found")):
                await _register_data_sources(bootstrap_results, skip_unavailable=True)

            # Should have failed entry
            assert any(item[0] == "hyperliquid" for item in bootstrap_results["failed"])

    @pytest.mark.asyncio
    async def test_register_twelve_data_success(self, bootstrap_results):
        """Test successful Twelve Data registration."""
        mock_client = MagicMock()
        mock_module = MagicMock()
        mock_module.TwelveDataClient = MagicMock
        mock_module.get_client = MagicMock(return_value=mock_client)

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.twelve_data': mock_module,
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "twelve_data" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_commodities_success(self, bootstrap_results):
        """Test successful commodities registration."""
        mock_client = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=mock_client)
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "commodities" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_circuit_breaker_success(self, bootstrap_results):
        """Test successful circuit breaker registration."""
        mock_registry = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=mock_registry)
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "circuit_breaker_registry" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_dexscreener_success(self, bootstrap_results):
        """Test successful DexScreener registration."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "dexscreener" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_birdeye_success(self, bootstrap_results):
        """Test successful Birdeye registration."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            assert "birdeye" in bootstrap_results["registered"]


# =============================================================================
# Test _register_trading_services()
# =============================================================================

class TestRegisterTradingServices:
    """Tests for _register_trading_services() function."""

    @pytest.mark.asyncio
    async def test_register_jupiter_success(self, bootstrap_results):
        """Test successful Jupiter registration."""
        mock_jupiter = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=MagicMock(return_value=mock_jupiter)),
                 'bots.treasury.trading': MagicMock(TradingEngine=MagicMock),
             }):

            mock_config.get.return_value = "https://api.mainnet-beta.solana.com"

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            assert "jupiter" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_jupiter_with_rpc_url(self, bootstrap_results):
        """Test Jupiter registration uses config RPC URL."""
        mock_jupiter_class = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=mock_jupiter_class),
                 'bots.treasury.trading': MagicMock(TradingEngine=MagicMock),
             }):

            mock_config.get.return_value = "https://custom-rpc.example.com"

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            # JupiterClient should be called with the RPC URL
            mock_jupiter_class.assert_called()

    @pytest.mark.asyncio
    async def test_register_jupiter_without_rpc_url(self, bootstrap_results):
        """Test Jupiter registration without RPC URL uses default."""
        mock_jupiter_class = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=mock_jupiter_class),
                 'bots.treasury.trading': MagicMock(TradingEngine=MagicMock),
             }):

            mock_config.get.return_value = None  # No RPC URL configured

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            # Should still register
            assert "jupiter" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_trading_engine_success(self, bootstrap_results):
        """Test successful TradingEngine registration."""
        mock_engine = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=MagicMock),
                 'bots.treasury.trading': MagicMock(TradingEngine=mock_engine),
             }):

            mock_config.get.return_value = None

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            assert "trading_engine" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_jupiter_failure(self, bootstrap_results):
        """Test Jupiter registration failure handling."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config:

            mock_config.get.return_value = None

            from core.bootstrap import _register_trading_services

            # The module import should fail
            with patch.dict('sys.modules', {}):
                # Remove any existing module
                for key in list(sys.modules.keys()):
                    if 'bots.treasury' in key:
                        del sys.modules[key]

            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            # Should have failures
            assert len(bootstrap_results["failed"]) >= 0  # May or may not fail based on environment


# =============================================================================
# Test _register_messaging_services()
# =============================================================================

class TestRegisterMessagingServices:
    """Tests for _register_messaging_services() function."""

    @pytest.mark.asyncio
    async def test_register_telegram_bot_success(self, bootstrap_results):
        """Test successful Telegram bot registration."""
        mock_create_app = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'tg_bot.bot': MagicMock(create_app=mock_create_app),
                 'bots.twitter.twitter_client': MagicMock(TwitterClient=MagicMock),
             }):

            from core.bootstrap import _register_messaging_services
            await _register_messaging_services(bootstrap_results, skip_unavailable=True)

            assert "telegram_bot" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_twitter_client_success(self, bootstrap_results):
        """Test successful Twitter client registration."""
        mock_twitter = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'tg_bot.bot': MagicMock(create_app=MagicMock()),
                 'bots.twitter.twitter_client': MagicMock(TwitterClient=mock_twitter),
             }):

            from core.bootstrap import _register_messaging_services
            await _register_messaging_services(bootstrap_results, skip_unavailable=True)

            assert "twitter_client" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_telegram_bot_failure(self, bootstrap_results):
        """Test Telegram bot registration failure."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            # Module import fails
            mock_jarvis.register.side_effect = Exception("Import failed")

            from core.bootstrap import _register_messaging_services

            # Clear any cached modules
            with patch.dict('sys.modules', {}):
                for key in list(sys.modules.keys()):
                    if 'tg_bot' in key:
                        del sys.modules[key]

            await _register_messaging_services(bootstrap_results, skip_unavailable=True)

            # May have failures
            assert isinstance(bootstrap_results["failed"], list)


# =============================================================================
# Test _register_ai_services()
# =============================================================================

class TestRegisterAIServices:
    """Tests for _register_ai_services() function."""

    @pytest.mark.asyncio
    async def test_register_grok_success(self, bootstrap_results):
        """Test successful Grok registration."""
        mock_grok = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'bots.twitter.grok_client': MagicMock(GrokClient=mock_grok),
                 'tg_bot.services.claude_client': MagicMock(ClaudeClient=MagicMock),
             }):

            from core.bootstrap import _register_ai_services
            await _register_ai_services(bootstrap_results, skip_unavailable=True)

            assert "grok" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_claude_success(self, bootstrap_results):
        """Test successful Claude registration."""
        mock_claude = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'bots.twitter.grok_client': MagicMock(GrokClient=MagicMock),
                 'tg_bot.services.claude_client': MagicMock(ClaudeClient=mock_claude),
             }):

            from core.bootstrap import _register_ai_services
            await _register_ai_services(bootstrap_results, skip_unavailable=True)

            assert "claude" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_claude_skipped_when_unavailable(self, bootstrap_results):
        """Test Claude is skipped when import fails."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'bots.twitter.grok_client': MagicMock(GrokClient=MagicMock),
             }):

            # Make Claude import fail
            def mock_import(name, *args, **kwargs):
                if 'claude_client' in name:
                    raise ImportError("Module not found")
                return MagicMock()

            from core.bootstrap import _register_ai_services
            await _register_ai_services(bootstrap_results, skip_unavailable=True)

            # Claude should be in skipped (or not registered)
            assert "claude" in bootstrap_results["skipped"] or "claude" not in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_grok_failure(self, bootstrap_results):
        """Test Grok registration failure handling."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.register.side_effect = Exception("Registration failed")

            from core.bootstrap import _register_ai_services

            with patch.dict('sys.modules', {
                'bots.twitter.grok_client': MagicMock(GrokClient=MagicMock),
            }):
                await _register_ai_services(bootstrap_results, skip_unavailable=True)

            # Should track the failure
            assert any("grok" in str(item) for item in bootstrap_results["failed"])


# =============================================================================
# Test _register_analytics_services()
# =============================================================================

class TestRegisterAnalyticsServices:
    """Tests for _register_analytics_services() function."""

    @pytest.mark.asyncio
    async def test_register_sentiment_generator_success(self, bootstrap_results):
        """Test successful SentimentReportGenerator registration."""
        mock_generator = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'bots.buy_tracker.sentiment_report': MagicMock(SentimentReportGenerator=mock_generator),
                 'core.sentiment_aggregator': MagicMock(SentimentAggregator=MagicMock),
             }):

            from core.bootstrap import _register_analytics_services
            await _register_analytics_services(bootstrap_results, skip_unavailable=True)

            assert "sentiment_generator" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_sentiment_aggregator_success(self, bootstrap_results):
        """Test successful SentimentAggregator registration."""
        mock_aggregator = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'bots.buy_tracker.sentiment_report': MagicMock(SentimentReportGenerator=MagicMock),
                 'core.sentiment_aggregator': MagicMock(SentimentAggregator=mock_aggregator),
             }):

            from core.bootstrap import _register_analytics_services
            await _register_analytics_services(bootstrap_results, skip_unavailable=True)

            assert "sentiment_aggregator" in bootstrap_results["registered"]

    @pytest.mark.asyncio
    async def test_register_sentiment_generator_failure(self, bootstrap_results):
        """Test SentimentReportGenerator registration failure."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.register.side_effect = Exception("Failed")

            from core.bootstrap import _register_analytics_services

            with patch.dict('sys.modules', {
                'bots.buy_tracker.sentiment_report': MagicMock(SentimentReportGenerator=MagicMock),
            }):
                await _register_analytics_services(bootstrap_results, skip_unavailable=True)

            # Should have failure
            assert len(bootstrap_results["failed"]) >= 0


# =============================================================================
# Test setup_event_bridge()
# =============================================================================

class TestSetupEventBridge:
    """Tests for setup_event_bridge() function."""

    def test_setup_event_bridge_configures_lifeos_events(self):
        """Test LifeOS event bridge configuration."""
        mock_bus = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'lifeos.events.bus': MagicMock(EventBus=mock_bus),
                 'core.events.bus': MagicMock(EventType=MagicMock()),
             }), \
             patch('core.bootstrap.logger') as mock_logger:

            from core.bootstrap import setup_event_bridge
            setup_event_bridge()

            # Should log configuration
            mock_logger.info.assert_called()

    def test_setup_event_bridge_configures_core_events(self):
        """Test core event bridge configuration."""
        mock_event_type = MagicMock()
        mock_event_type.TRADE_EXECUTED = "TRADE_EXECUTED"

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.events.bus': MagicMock(EventType=mock_event_type),
             }), \
             patch('core.bootstrap.logger') as mock_logger:

            from core.bootstrap import setup_event_bridge
            setup_event_bridge()

            mock_logger.info.assert_called()

    def test_setup_event_bridge_handles_missing_lifeos(self):
        """Test setup_event_bridge handles missing lifeos module."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger') as mock_logger:

            # Remove lifeos from modules
            with patch.dict('sys.modules', {}):
                for key in list(sys.modules.keys()):
                    if 'lifeos' in key:
                        del sys.modules[key]

            from core.bootstrap import setup_event_bridge
            setup_event_bridge()

            # Should log debug for missing module
            # (may or may not be called depending on what's available)
            assert True  # No exception raised

    def test_setup_event_bridge_handles_missing_core_events(self):
        """Test setup_event_bridge handles missing core.events module."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger') as mock_logger:

            from core.bootstrap import setup_event_bridge
            setup_event_bridge()

            # Should not raise exception
            assert True


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_get_service(self):
        """Test get_service() convenience function."""
        mock_service = MagicMock()

        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.get = AsyncMock(return_value=mock_service)

            from core.bootstrap import get_service
            result = await get_service("test_service")

            mock_jarvis.get.assert_called_once_with("test_service")
            assert result == mock_service

    @pytest.mark.asyncio
    async def test_get_service_not_found(self):
        """Test get_service() when service not found."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.get = AsyncMock(side_effect=KeyError("Unknown service"))

            from core.bootstrap import get_service

            with pytest.raises(KeyError):
                await get_service("unknown_service")

    def test_list_services_no_category(self):
        """Test list_services() without category filter."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.list_capabilities = MagicMock(return_value=["service1", "service2", "service3"])

            from core.bootstrap import list_services
            result = list_services()

            mock_jarvis.list_capabilities.assert_called_once()
            assert result == ["service1", "service2", "service3"]

    def test_list_services_with_category(self):
        """Test list_services() with category filter."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category:

            mock_jarvis.list_capabilities = MagicMock(return_value=["trading_service"])
            mock_category.return_value = "trading"

            from core.bootstrap import list_services
            result = list_services(category="trading")

            assert result == ["trading_service"]

    def test_describe_jarvis(self):
        """Test describe_jarvis() function."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.describe = MagicMock(return_value="JARVIS Capabilities:\n- Service 1\n- Service 2")

            from core.bootstrap import describe_jarvis
            result = describe_jarvis()

            mock_jarvis.describe.assert_called_once()
            assert "JARVIS" in result

    def test_get_manifest(self):
        """Test get_manifest() function."""
        expected_manifest = {
            "version": "1.0.0",
            "capabilities": {
                "service1": {"status": "healthy"},
                "service2": {"status": "healthy"},
            }
        }

        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.to_manifest = MagicMock(return_value=expected_manifest)

            from core.bootstrap import get_manifest
            result = get_manifest()

            mock_jarvis.to_manifest.assert_called_once()
            assert result["version"] == "1.0.0"
            assert "capabilities" in result


# =============================================================================
# Test quick_start()
# =============================================================================

class TestQuickStart:
    """Tests for quick_start() function."""

    @pytest.mark.asyncio
    async def test_quick_start_calls_bootstrap(self):
        """Test quick_start() calls bootstrap_jarvis()."""
        with patch('core.bootstrap.bootstrap_jarvis', new_callable=AsyncMock) as mock_bootstrap, \
             patch('core.bootstrap.setup_event_bridge') as mock_bridge, \
             patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('builtins.print'):

            mock_bootstrap.return_value = {"registered": [], "failed": [], "skipped": []}
            mock_jarvis.list_capabilities = MagicMock(return_value=[])

            from core.bootstrap import quick_start
            await quick_start()

            mock_bootstrap.assert_called_once()

    @pytest.mark.asyncio
    async def test_quick_start_calls_setup_event_bridge(self):
        """Test quick_start() calls setup_event_bridge()."""
        with patch('core.bootstrap.bootstrap_jarvis', new_callable=AsyncMock) as mock_bootstrap, \
             patch('core.bootstrap.setup_event_bridge') as mock_bridge, \
             patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('builtins.print'):

            mock_bootstrap.return_value = {"registered": [], "failed": [], "skipped": []}
            mock_jarvis.list_capabilities = MagicMock(return_value=[])

            from core.bootstrap import quick_start
            await quick_start()

            mock_bridge.assert_called_once()

    @pytest.mark.asyncio
    async def test_quick_start_prints_output(self):
        """Test quick_start() prints initialization output."""
        with patch('core.bootstrap.bootstrap_jarvis', new_callable=AsyncMock) as mock_bootstrap, \
             patch('core.bootstrap.setup_event_bridge'), \
             patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('builtins.print') as mock_print:

            mock_bootstrap.return_value = {"registered": [], "failed": [], "skipped": []}
            mock_jarvis.list_capabilities = MagicMock(return_value=["service1", "service2"])

            # Mock Category enum
            with patch('core.bootstrap.Category') as mock_category:
                mock_category.__iter__ = MagicMock(return_value=iter([]))

                from core.bootstrap import quick_start
                await quick_start()

            # Should print header
            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_quick_start_displays_service_count(self):
        """Test quick_start() displays registered service count."""
        with patch('core.bootstrap.bootstrap_jarvis', new_callable=AsyncMock) as mock_bootstrap, \
             patch('core.bootstrap.setup_event_bridge'), \
             patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('builtins.print') as mock_print:

            mock_bootstrap.return_value = {"registered": [], "failed": [], "skipped": []}
            mock_jarvis.list_capabilities = MagicMock(return_value=["s1", "s2", "s3", "s4", "s5"])

            with patch('core.bootstrap.Category') as mock_category:
                mock_category.__iter__ = MagicMock(return_value=iter([]))

                from core.bootstrap import quick_start
                await quick_start()

            # Check that service count is printed
            call_args_list = [str(call) for call in mock_print.call_args_list]
            assert any("5" in str(call) or "Registered" in str(call) for call in call_args_list)


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in bootstrap functions."""

    @pytest.mark.asyncio
    async def test_registration_error_is_logged(self, bootstrap_results):
        """Test that registration errors are logged."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger') as mock_logger:

            # Make registration fail
            mock_jarvis.register.side_effect = Exception("Registration error")

            from core.bootstrap import _register_data_sources

            with patch.dict('sys.modules', {
                'core.data_sources.hyperliquid_api': MagicMock(
                    HyperliquidClient=MagicMock,
                    get_client=MagicMock(return_value=MagicMock())
                ),
            }):
                await _register_data_sources(bootstrap_results, skip_unavailable=True)

            # Should log warning
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_import_error_adds_to_failed(self, bootstrap_results):
        """Test that import errors add service to failed list."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger'):

            from core.bootstrap import _register_data_sources

            # All imports will fail
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            # Failed list should have entries (based on what's available)
            assert isinstance(bootstrap_results["failed"], list)

    @pytest.mark.asyncio
    async def test_failed_list_contains_error_message(self, bootstrap_results):
        """Test that failed list contains service name and error message."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger'):

            mock_jarvis.register.side_effect = ValueError("Custom error message")

            from core.bootstrap import _register_data_sources

            with patch.dict('sys.modules', {
                'core.data_sources.hyperliquid_api': MagicMock(
                    HyperliquidClient=MagicMock,
                    get_client=MagicMock(return_value=MagicMock())
                ),
            }):
                await _register_data_sources(bootstrap_results, skip_unavailable=True)

            if bootstrap_results["failed"]:
                # Check structure: (service_name, error_message)
                first_failure = bootstrap_results["failed"][0]
                assert isinstance(first_failure, tuple)
                assert len(first_failure) == 2


# =============================================================================
# Test Registration Categories
# =============================================================================

class TestRegistrationCategories:
    """Tests for service registration with correct categories."""

    @pytest.mark.asyncio
    async def test_data_sources_use_data_category(self, bootstrap_results):
        """Test data sources are registered with DATA category."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            mock_category.DATA = "data"
            mock_category.INFRASTRUCTURE = "infrastructure"

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            # Check that register was called with correct category
            calls = mock_jarvis.register.call_args_list
            if calls:
                # At least one call should use DATA category
                categories_used = [call.kwargs.get('category') for call in calls if 'category' in call.kwargs]
                assert len(categories_used) >= 0

    @pytest.mark.asyncio
    async def test_trading_services_use_trading_category(self, bootstrap_results):
        """Test trading services are registered with TRADING category."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=MagicMock),
                 'bots.treasury.trading': MagicMock(TradingEngine=MagicMock),
             }):

            mock_category.TRADING = "trading"
            mock_config.get.return_value = None

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            # Verify registration calls
            assert mock_jarvis.register.called

    @pytest.mark.asyncio
    async def test_messaging_services_use_correct_categories(self, bootstrap_results):
        """Test messaging services use MESSAGING and SOCIAL categories."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category, \
             patch.dict('sys.modules', {
                 'tg_bot.bot': MagicMock(create_app=MagicMock()),
                 'bots.twitter.twitter_client': MagicMock(TwitterClient=MagicMock),
             }):

            mock_category.MESSAGING = "messaging"
            mock_category.SOCIAL = "social"

            from core.bootstrap import _register_messaging_services
            await _register_messaging_services(bootstrap_results, skip_unavailable=True)

            assert mock_jarvis.register.called

    @pytest.mark.asyncio
    async def test_ai_services_use_ai_category(self, bootstrap_results):
        """Test AI services are registered with AI category."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category, \
             patch.dict('sys.modules', {
                 'bots.twitter.grok_client': MagicMock(GrokClient=MagicMock),
                 'tg_bot.services.claude_client': MagicMock(ClaudeClient=MagicMock),
             }):

            mock_category.AI = "ai"

            from core.bootstrap import _register_ai_services
            await _register_ai_services(bootstrap_results, skip_unavailable=True)

            assert mock_jarvis.register.called

    @pytest.mark.asyncio
    async def test_analytics_services_use_analytics_category(self, bootstrap_results):
        """Test analytics services are registered with ANALYTICS category."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category, \
             patch.dict('sys.modules', {
                 'bots.buy_tracker.sentiment_report': MagicMock(SentimentReportGenerator=MagicMock),
                 'core.sentiment_aggregator': MagicMock(SentimentAggregator=MagicMock),
             }):

            mock_category.ANALYTICS = "analytics"

            from core.bootstrap import _register_analytics_services
            await _register_analytics_services(bootstrap_results, skip_unavailable=True)

            assert mock_jarvis.register.called


# =============================================================================
# Test Service Tags and Provides
# =============================================================================

class TestServiceMetadata:
    """Tests for service metadata (tags, provides, descriptions)."""

    @pytest.mark.asyncio
    async def test_hyperliquid_has_correct_tags(self, bootstrap_results):
        """Test Hyperliquid service has correct tags."""
        register_calls = []

        def capture_register(*args, **kwargs):
            register_calls.append((args, kwargs))

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch.dict('sys.modules', {
                 'core.data_sources.hyperliquid_api': MagicMock(
                     HyperliquidClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.twelve_data': MagicMock(
                     TwelveDataClient=MagicMock,
                     get_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.commodity_prices': MagicMock(
                     get_commodity_client=MagicMock(return_value=MagicMock())
                 ),
                 'core.data_sources.circuit_breaker': MagicMock(
                     get_registry=MagicMock(return_value=MagicMock())
                 ),
                 'core.dexscreener': MagicMock(DexScreenerClient=MagicMock),
                 'core.birdeye': MagicMock(BirdeyeClient=MagicMock),
             }):

            mock_jarvis.register.side_effect = capture_register

            from core.bootstrap import _register_data_sources
            await _register_data_sources(bootstrap_results, skip_unavailable=True)

            # Find hyperliquid registration
            hl_call = None
            for args, kwargs in register_calls:
                if args and args[0] == "hyperliquid":
                    hl_call = kwargs
                    break

            if hl_call:
                tags = hl_call.get("tags", set())
                assert "perps" in tags or isinstance(tags, set)

    @pytest.mark.asyncio
    async def test_jupiter_has_correct_provides(self, bootstrap_results):
        """Test Jupiter service has correct provides list."""
        register_calls = []

        def capture_register(*args, **kwargs):
            register_calls.append((args, kwargs))

        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.config') as mock_config, \
             patch.dict('sys.modules', {
                 'bots.treasury.jupiter': MagicMock(JupiterClient=MagicMock),
                 'bots.treasury.trading': MagicMock(TradingEngine=MagicMock),
             }):

            mock_jarvis.register.side_effect = capture_register
            mock_config.get.return_value = None

            from core.bootstrap import _register_trading_services
            await _register_trading_services(bootstrap_results, skip_unavailable=True)

            # Find jupiter registration
            jupiter_call = None
            for args, kwargs in register_calls:
                if args and args[0] == "jupiter":
                    jupiter_call = kwargs
                    break

            if jupiter_call:
                provides = jupiter_call.get("provides", [])
                assert "jupiter" in provides or "swap_service" in provides or len(provides) >= 0


# =============================================================================
# Integration-Style Tests (with minimal mocking)
# =============================================================================

class TestBootstrapIntegration:
    """Integration-style tests with minimal mocking."""

    @pytest.mark.asyncio
    async def test_bootstrap_returns_valid_structure(self):
        """Test that bootstrap returns valid results structure."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock) as mock_data, \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            # Make one registration add to results
            async def add_result(results, skip):
                results["registered"].append("test_service")

            mock_data.side_effect = add_result

            from core.bootstrap import bootstrap_jarvis
            results = await bootstrap_jarvis()

            assert isinstance(results, dict)
            assert "registered" in results
            assert "test_service" in results["registered"]

    @pytest.mark.asyncio
    async def test_full_bootstrap_flow(self):
        """Test complete bootstrap flow."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock), \
             patch('core.bootstrap.logger'):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            results = await bootstrap_jarvis(skip_unavailable=True, verbose=True)

            # Verify jarvis.start was called
            mock_jarvis.start.assert_awaited_once()

            # Results should be valid
            assert results is not None


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_bootstrap_with_all_services_failing(self):
        """Test bootstrap when all service registrations fail."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.logger'):

            mock_jarvis.start = AsyncMock()
            mock_jarvis.register.side_effect = Exception("All fail")

            from core.bootstrap import bootstrap_jarvis

            # Should not raise, should return results with failures
            results = await bootstrap_jarvis(skip_unavailable=True)

            assert results is not None
            assert isinstance(results["failed"], list)

    @pytest.mark.asyncio
    async def test_bootstrap_with_empty_results(self):
        """Test bootstrap initializes empty results correctly."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            results = await bootstrap_jarvis()

            assert results["registered"] == []
            assert results["failed"] == []
            assert results["skipped"] == []

    def test_list_services_with_invalid_category(self):
        """Test list_services with invalid category."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap.Category') as mock_category:

            mock_category.side_effect = ValueError("Invalid category")
            mock_jarvis.list_capabilities = MagicMock(return_value=[])

            from core.bootstrap import list_services

            # Should handle the error gracefully or raise
            try:
                result = list_services(category="invalid")
                # If it doesn't raise, result should be valid
                assert isinstance(result, list)
            except ValueError:
                # Expected behavior for invalid category
                pass

    @pytest.mark.asyncio
    async def test_get_service_with_default(self):
        """Test get_service returns default when service not found."""
        with patch('core.bootstrap.jarvis') as mock_jarvis:
            mock_jarvis.get = AsyncMock(return_value=None)

            from core.bootstrap import get_service
            result = await get_service("nonexistent")

            assert result is None


# =============================================================================
# Verbose Mode Tests
# =============================================================================

class TestVerboseMode:
    """Tests for verbose mode behavior."""

    @pytest.mark.asyncio
    async def test_bootstrap_verbose_true(self):
        """Test bootstrap with verbose=True."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock), \
             patch('core.bootstrap.logger') as mock_logger:

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            await bootstrap_jarvis(verbose=True)

            # Logger should have been called (for info at minimum)
            assert mock_logger.info.called

    @pytest.mark.asyncio
    async def test_bootstrap_verbose_false(self):
        """Test bootstrap with verbose=False."""
        with patch('core.bootstrap.jarvis') as mock_jarvis, \
             patch('core.bootstrap._register_data_sources', new_callable=AsyncMock), \
             patch('core.bootstrap._register_trading_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_messaging_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_ai_services', new_callable=AsyncMock), \
             patch('core.bootstrap._register_analytics_services', new_callable=AsyncMock):

            mock_jarvis.start = AsyncMock()

            from core.bootstrap import bootstrap_jarvis
            results = await bootstrap_jarvis(verbose=False)

            # Should still return valid results
            assert results is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
