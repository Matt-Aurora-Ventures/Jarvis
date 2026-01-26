"""
Comprehensive unit tests for bots/bags_intel/intel_service.py

Tests cover:
- Service initialization and configuration
- Start/stop lifecycle management
- Graduation event handling and deduplication
- Rate limiting and cooldowns
- Data gathering from DexScreener and Twitter
- Score calculation integration
- Telegram report delivery
- Memory hooks integration (fire-and-forget)
- Error handling and edge cases
- Threshold filtering (min mcap, min score)

Coverage target: 80%+
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.bags_intel.intel_service import BagsIntelService, create_bags_intel_service
from bots.bags_intel.config import BagsIntelConfig
from bots.bags_intel.models import (
    TokenMetadata,
    CreatorProfile,
    BondingMetrics,
    MarketMetrics,
    IntelScore,
    GraduationEvent,
    LaunchQuality,
    RiskLevel,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def config():
    """Create a fully configured BagsIntelConfig for testing."""
    return BagsIntelConfig(
        bitquery_api_key="test-bitquery-key",
        bitquery_ws_url="wss://test.bitquery.io/graphql",
        telegram_bot_token="test-telegram-token",
        telegram_chat_id="test-chat-id",
        twitter_bearer_token="test-twitter-token",
        xai_api_key="test-xai-key",
        helius_api_key="test-helius-key",
        min_graduation_mcap=10000.0,
        min_score_to_report=30.0,
        report_cooldown_seconds=60,
    )


@pytest.fixture
def config_minimal():
    """Create a minimally configured BagsIntelConfig."""
    return BagsIntelConfig(
        bitquery_api_key="test-bitquery-key",
        telegram_bot_token="test-telegram-token",
        telegram_chat_id="test-chat-id",
    )


@pytest.fixture
def config_no_bitquery():
    """Create config without Bitquery API key (fallback mode)."""
    return BagsIntelConfig(
        telegram_bot_token="test-telegram-token",
        telegram_chat_id="test-chat-id",
    )


@pytest.fixture
def config_no_telegram():
    """Create config without Telegram."""
    return BagsIntelConfig(
        bitquery_api_key="test-bitquery-key",
    )


@pytest.fixture
def service(config):
    """Create a BagsIntelService with full config."""
    return BagsIntelService(config=config)


@pytest.fixture
def service_minimal(config_minimal):
    """Create a BagsIntelService with minimal config."""
    return BagsIntelService(config=config_minimal)


@pytest.fixture
def sample_graduation_event():
    """Create a sample graduation event dict."""
    return {
        "mint_address": "TestMint11111111111111111111111111111111111",
        "signature": "5abc123def456TestSignature",
        "creator": "CreatorWallet111111111111111111111111111111",
        "timestamp": "2026-01-25T12:00:00Z",
    }


@pytest.fixture
def sample_dexscreener_token_response():
    """Create a sample DexScreener token API response."""
    return {
        "pairs": [
            {
                "baseToken": {
                    "name": "Test Token",
                    "symbol": "TEST",
                },
                "info": {
                    "websites": [{"url": "https://testtoken.com"}],
                    "socials": [
                        {"type": "twitter", "url": "https://twitter.com/testtoken"},
                        {"type": "telegram", "url": "https://t.me/testtoken"},
                    ],
                },
                "priceUsd": "0.001",
                "priceNative": "0.00001",
                "marketCap": "100000",
                "liquidity": {"usd": "15000"},
                "volume": {"h24": "50000"},
                "priceChange": {"h1": "10"},
                "txns": {"h1": {"buys": 100, "sells": 50}},
            }
        ]
    }


@pytest.fixture
def sample_twitter_profile_response():
    """Create a sample Twitter API profile response."""
    return {
        "data": {
            "id": "123456789",
            "username": "testtoken",
            "created_at": "2024-01-01T00:00:00Z",
            "public_metrics": {
                "followers_count": 5000,
                "following_count": 100,
                "tweet_count": 500,
            },
        }
    }


@pytest.fixture
def sample_intel_score():
    """Create a sample IntelScore."""
    return IntelScore(
        overall_score=75.0,
        launch_quality=LaunchQuality.STRONG,
        risk_level=RiskLevel.LOW,
        bonding_score=80.0,
        creator_score=70.0,
        social_score=75.0,
        market_score=80.0,
        distribution_score=70.0,
        green_flags=["Strong liquidity", "Many buyers"],
        red_flags=[],
        warnings=["Quick graduation"],
    )


@pytest.fixture
def sample_graduation_model(sample_intel_score):
    """Create a sample GraduationEvent model."""
    return GraduationEvent(
        token=TokenMetadata(
            mint_address="TestMint11111111111111111111111111111111111",
            name="Test Token",
            symbol="TEST",
            website="https://testtoken.com",
            twitter="https://twitter.com/testtoken",
        ),
        creator=CreatorProfile(
            wallet_address="CreatorWallet111",
            twitter_handle="testcreator",
            twitter_followers=1000,
        ),
        bonding=BondingMetrics(
            duration_seconds=600,
            total_volume_sol=50.0,
            unique_buyers=100,
            unique_sellers=30,
            buy_sell_ratio=3.3,
            graduation_mcap_usd=100000.0,
        ),
        market=MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        ),
        score=sample_intel_score,
        timestamp=datetime.utcnow(),
        tx_signature="TestSignature123",
    )


# =============================================================================
# Initialization Tests
# =============================================================================

class TestServiceInitialization:
    """Tests for BagsIntelService initialization."""

    def test_init_with_config(self, config):
        """Test initialization with provided config."""
        service = BagsIntelService(config=config)

        assert service.config == config
        assert service._monitor is None
        assert service._fallback is None
        assert service._scorer is None
        assert service._bot is None
        assert service._http is None
        assert service._running is False
        assert len(service._processed) == 0
        assert len(service._last_report_time) == 0
        assert service._report_count == 0

    def test_init_without_config_loads_default(self):
        """Test that initialization without config calls load_config."""
        with patch("bots.bags_intel.intel_service.load_config") as mock_load:
            mock_load.return_value = BagsIntelConfig()
            service = BagsIntelService()
            mock_load.assert_called_once()

    def test_init_preserves_empty_sets(self, config):
        """Test that internal sets are initialized empty."""
        service = BagsIntelService(config=config)

        assert isinstance(service._processed, set)
        assert isinstance(service._last_report_time, dict)
        assert service._report_count == 0


# =============================================================================
# Start/Stop Lifecycle Tests
# =============================================================================

class TestServiceLifecycle:
    """Tests for service start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_initializes_http_session(self, service):
        """Test that start() creates aiohttp session."""
        with patch.object(service, "_monitor", None), \
             patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.IntelScorer"), \
             patch("telegram.Bot"):

            mock_monitor_instance = AsyncMock()
            mock_monitor_instance.run = AsyncMock()
            mock_monitor.return_value = mock_monitor_instance

            # Start briefly then stop
            async def stop_soon():
                await asyncio.sleep(0.01)
                service._running = False

            asyncio.create_task(stop_soon())

            # Start will block on monitor.run(), so we mock it
            mock_monitor_instance.run.side_effect = lambda: asyncio.sleep(0.05)

            await service.start()

            assert service._http is not None
            await service._http.close()

    @pytest.mark.asyncio
    async def test_start_initializes_scorer(self, service):
        """Test that start() creates IntelScorer with config."""
        with patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.IntelScorer") as mock_scorer, \
             patch("telegram.Bot"):

            mock_monitor_instance = AsyncMock()
            mock_monitor_instance.run = AsyncMock(side_effect=lambda: asyncio.sleep(0.01))
            mock_monitor.return_value = mock_monitor_instance

            async def stop_soon():
                await asyncio.sleep(0.005)
                service._running = False

            asyncio.create_task(stop_soon())

            await service.start()

            mock_scorer.assert_called_once_with(xai_api_key=service.config.xai_api_key)
            await service._http.close()

    @pytest.mark.asyncio
    async def test_start_initializes_telegram_bot(self, service):
        """Test that start() creates Telegram bot when configured."""
        with patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.IntelScorer"), \
             patch("bots.bags_intel.intel_service.Bot") as mock_bot:

            mock_monitor_instance = AsyncMock()
            mock_monitor_instance.run = AsyncMock(side_effect=lambda: asyncio.sleep(0.01))
            mock_monitor.return_value = mock_monitor_instance

            async def stop_soon():
                await asyncio.sleep(0.005)
                service._running = False

            asyncio.create_task(stop_soon())

            await service.start()

            mock_bot.assert_called_once_with(token=service.config.telegram_bot_token)
            await service._http.close()

    @pytest.mark.asyncio
    async def test_start_no_telegram_without_config(self, config_no_telegram):
        """Test that Telegram bot is not created without token."""
        service = BagsIntelService(config=config_no_telegram)

        with patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.IntelScorer"), \
             patch("bots.bags_intel.intel_service.Bot") as mock_bot:

            mock_monitor_instance = AsyncMock()
            mock_monitor_instance.run = AsyncMock(side_effect=lambda: asyncio.sleep(0.01))
            mock_monitor.return_value = mock_monitor_instance

            async def stop_soon():
                await asyncio.sleep(0.005)
                service._running = False

            asyncio.create_task(stop_soon())

            await service.start()

            mock_bot.assert_not_called()
            assert service._bot is None
            await service._http.close()

    @pytest.mark.asyncio
    async def test_start_uses_websocket_with_bitquery_key(self, service):
        """Test that WebSocket monitor is used when Bitquery key is present."""
        with patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.PollingFallback") as mock_fallback, \
             patch("bots.bags_intel.intel_service.IntelScorer"), \
             patch("telegram.Bot"):

            mock_monitor_instance = AsyncMock()
            mock_monitor_instance.run = AsyncMock(side_effect=lambda: asyncio.sleep(0.01))
            mock_monitor.return_value = mock_monitor_instance

            async def stop_soon():
                await asyncio.sleep(0.005)
                service._running = False

            asyncio.create_task(stop_soon())

            await service.start()

            mock_monitor.assert_called_once()
            mock_fallback.assert_not_called()
            await service._http.close()

    @pytest.mark.asyncio
    async def test_start_uses_polling_without_bitquery_key(self, config_no_bitquery):
        """Test that polling fallback is used without Bitquery key."""
        service = BagsIntelService(config=config_no_bitquery)

        with patch("bots.bags_intel.intel_service.GraduationMonitor") as mock_monitor, \
             patch("bots.bags_intel.intel_service.PollingFallback") as mock_fallback, \
             patch("bots.bags_intel.intel_service.IntelScorer"), \
             patch("telegram.Bot"):

            mock_fallback_instance = AsyncMock()
            mock_fallback_instance.run = AsyncMock(side_effect=lambda: asyncio.sleep(0.01))
            mock_fallback.return_value = mock_fallback_instance

            async def stop_soon():
                await asyncio.sleep(0.005)
                service._running = False

            asyncio.create_task(stop_soon())

            await service.start()

            mock_fallback.assert_called_once()
            mock_monitor.assert_not_called()
            await service._http.close()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, service):
        """Test that stop() sets _running to False."""
        service._running = True

        await service.stop()

        assert service._running is False

    @pytest.mark.asyncio
    async def test_stop_stops_monitor(self, service):
        """Test that stop() stops the monitor."""
        mock_monitor = AsyncMock()
        service._monitor = mock_monitor
        service._running = True

        await service.stop()

        mock_monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stops_fallback(self, service):
        """Test that stop() stops the fallback poller."""
        mock_fallback = AsyncMock()
        service._fallback = mock_fallback
        service._running = True

        await service.stop()

        mock_fallback.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_closes_http_session(self, service):
        """Test that stop() closes the HTTP session."""
        mock_http = AsyncMock()
        service._http = mock_http
        service._running = True

        await service.stop()

        mock_http.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_logs_report_count(self, service):
        """Test that stop() logs the report count."""
        service._running = True
        service._report_count = 5

        with patch("bots.bags_intel.intel_service.logger") as mock_logger:
            await service.stop()

            # Check that info was called with report count
            calls = [str(c) for c in mock_logger.info.call_args_list]
            assert any("5" in str(c) for c in calls)


# =============================================================================
# Graduation Event Handling Tests
# =============================================================================

class TestHandleGraduation:
    """Tests for _handle_graduation method."""

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_no_mint(self, service):
        """Test that events without mint_address are skipped."""
        event = {"signature": "test", "creator": "wallet"}

        await service._handle_graduation(event)

        assert len(service._processed) == 0

    @pytest.mark.asyncio
    async def test_handle_graduation_deduplicates(self, service, sample_graduation_event):
        """Test that duplicate mints are skipped."""
        mint = sample_graduation_event["mint_address"]
        service._processed.add(mint)

        with patch.object(service, "_gather_data") as mock_gather:
            await service._handle_graduation(sample_graduation_event)

            mock_gather.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_rate_limits(self, service, sample_graduation_event):
        """Test rate limiting by cooldown."""
        mint = sample_graduation_event["mint_address"]
        # Set last report time to recent (within cooldown)
        service._last_report_time[mint] = datetime.utcnow()
        service.config.report_cooldown_seconds = 60

        with patch.object(service, "_gather_data") as mock_gather:
            await service._handle_graduation(sample_graduation_event)

            mock_gather.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_allows_after_cooldown(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that events are processed after cooldown expires."""
        mint = sample_graduation_event["mint_address"]
        # Set last report time to past cooldown
        service._last_report_time[mint] = datetime.utcnow() - timedelta(seconds=120)
        service.config.report_cooldown_seconds = 60
        # Clear processed set so it's not deduped
        service._processed.clear()

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock):

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            mock_gather.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_graduation_adds_to_processed(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that mint is added to processed set."""
        mint = sample_graduation_event["mint_address"]

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock):

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            assert mint in service._processed

    @pytest.mark.asyncio
    async def test_handle_graduation_updates_last_report_time(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that last report time is updated."""
        mint = sample_graduation_event["mint_address"]
        before = datetime.utcnow()

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock):

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            assert mint in service._last_report_time
            assert service._last_report_time[mint] >= before

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_failed_data_gather(
        self, service, sample_graduation_event
    ):
        """Test that report is not sent if data gathering fails."""
        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock) as mock_send:

            mock_gather.return_value = None  # Simulate failure

            await service._handle_graduation(sample_graduation_event)

            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_below_mcap_threshold(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that low mcap graduations are skipped."""
        sample_graduation_model.market.market_cap_usd = 5000  # Below threshold
        service.config.min_graduation_mcap = 10000

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock) as mock_send:

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_below_score_threshold(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that low score graduations are skipped."""
        sample_graduation_model.score.overall_score = 20  # Below threshold
        service.config.min_score_to_report = 30

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock) as mock_send:

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_sends_report_when_thresholds_met(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that report is sent when thresholds are met."""
        sample_graduation_model.market.market_cap_usd = 100000
        sample_graduation_model.score.overall_score = 75

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock) as mock_send:

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            mock_send.assert_called_once_with(sample_graduation_model)

    @pytest.mark.asyncio
    async def test_handle_graduation_increments_report_count(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that report count is incremented."""
        initial_count = service._report_count

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock):

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            assert service._report_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_handle_graduation_fires_memory_hook(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that memory hook is triggered (fire-and-forget)."""
        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock), \
             patch("bots.bags_intel.intel_service.fire_and_forget") as mock_fire:

            mock_gather.return_value = sample_graduation_model

            await service._handle_graduation(sample_graduation_event)

            mock_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_graduation_memory_hook_failure_silent(
        self, service, sample_graduation_event, sample_graduation_model
    ):
        """Test that memory hook failure doesn't break graduation handling."""
        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock) as mock_send, \
             patch("bots.bags_intel.intel_service.fire_and_forget") as mock_fire:

            mock_gather.return_value = sample_graduation_model
            # Make fire_and_forget raise - should be caught
            mock_fire.side_effect = Exception("Memory hook failed")

            # Should not raise
            await service._handle_graduation(sample_graduation_event)

            # Report should still be sent
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_graduation_exception_handling(
        self, service, sample_graduation_event
    ):
        """Test that exceptions during handling are caught."""
        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather:
            mock_gather.side_effect = Exception("Data gathering failed")

            # Should not raise
            await service._handle_graduation(sample_graduation_event)


# =============================================================================
# Data Gathering Tests
# =============================================================================

class TestGatherData:
    """Tests for _gather_data method."""

    @pytest.mark.asyncio
    async def test_gather_data_fetches_parallel(self, service):
        """Test that token and market data are fetched in parallel."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(
            mint_address="TestMint",
            name="Test",
            symbol="TST",
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet="CreatorWallet",
                tx_signature="TxSig123",
                timestamp="2026-01-25T12:00:00Z",
            )

            mock_token.assert_called_once_with("TestMint")
            mock_market.assert_called_once_with("TestMint")
            assert result is not None

    @pytest.mark.asyncio
    async def test_gather_data_returns_none_on_token_failure(self, service):
        """Test that None is returned if token fetch fails."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.side_effect = Exception("Token fetch failed")
            mock_market.return_value = MagicMock()

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet="CreatorWallet",
                tx_signature="TxSig123",
                timestamp=None,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_gather_data_returns_none_on_market_failure(self, service):
        """Test that None is returned if market fetch fails."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = MagicMock()
            mock_market.side_effect = Exception("Market fetch failed")

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet="CreatorWallet",
                tx_signature="TxSig123",
                timestamp=None,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_gather_data_creates_creator_profile(self, service):
        """Test that CreatorProfile is created correctly."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(
            mint_address="TestMint",
            name="Test",
            symbol="TST",
            twitter="@testcreator",
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet="CreatorWallet123",
                tx_signature="TxSig123",
                timestamp=None,
            )

            assert result.creator.wallet_address == "CreatorWallet123"

    @pytest.mark.asyncio
    async def test_gather_data_calls_scorer(self, service):
        """Test that scorer is called with gathered data."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        mock_score = IntelScore(
            overall_score=80.0,
            launch_quality=LaunchQuality.EXCEPTIONAL,
            risk_level=RiskLevel.LOW,
            bonding_score=85.0,
            creator_score=80.0,
            social_score=75.0,
            market_score=85.0,
            distribution_score=75.0,
        )
        service._scorer.calculate_score = AsyncMock(return_value=mock_score)

        token_meta = TokenMetadata(
            mint_address="TestMint",
            name="Test",
            symbol="TST",
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet="CreatorWallet",
                tx_signature="TxSig123",
                timestamp="2026-01-25T12:00:00Z",
            )

            service._scorer.calculate_score.assert_called_once()
            assert result.score == mock_score

    @pytest.mark.asyncio
    async def test_gather_data_handles_unknown_creator_wallet(self, service):
        """Test handling of missing creator wallet."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(
            mint_address="TestMint",
            name="Test",
            symbol="TST",
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="TestMint",
                creator_wallet=None,  # Missing
                tx_signature="TxSig123",
                timestamp=None,
            )

            assert result.creator.wallet_address == "unknown"


# =============================================================================
# Token Metadata Fetch Tests
# =============================================================================

class TestFetchTokenMetadata:
    """Tests for _fetch_token_metadata method."""

    @pytest.mark.asyncio
    async def test_fetch_token_metadata_success(self, service, sample_dexscreener_token_response):
        """Test successful token metadata fetch."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_dexscreener_token_response)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_token_metadata("TestMint123")

        assert result.name == "Test Token"
        assert result.symbol == "TEST"
        assert result.website == "https://testtoken.com"
        assert result.twitter == "https://twitter.com/testtoken"
        assert result.telegram == "https://t.me/testtoken"

    @pytest.mark.asyncio
    async def test_fetch_token_metadata_non_200_raises(self, service):
        """Test that non-200 status raises exception."""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        with pytest.raises(Exception, match="DexScreener error"):
            await service._fetch_token_metadata("TestMint123")

    @pytest.mark.asyncio
    async def test_fetch_token_metadata_no_pairs_returns_default(self, service):
        """Test that empty pairs returns default metadata."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"pairs": []})

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_token_metadata("TestMint123")

        assert result.mint_address == "TestMint123"
        assert result.name == "Unknown"
        assert result.symbol == "???"

    @pytest.mark.asyncio
    async def test_fetch_token_metadata_missing_socials(self, service):
        """Test handling of missing social links."""
        response_data = {
            "pairs": [
                {
                    "baseToken": {"name": "No Socials", "symbol": "NOSOC"},
                    "info": {},
                }
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response_data)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_token_metadata("TestMint123")

        assert result.name == "No Socials"
        assert result.twitter is None
        assert result.website is None


# =============================================================================
# Market Data Fetch Tests
# =============================================================================

class TestFetchMarketData:
    """Tests for _fetch_market_data method."""

    @pytest.mark.asyncio
    async def test_fetch_market_data_success(self, service, sample_dexscreener_token_response):
        """Test successful market data fetch."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_dexscreener_token_response)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_market_data("TestMint123")

        assert result.price_usd == 0.001
        assert result.market_cap_usd == 100000.0
        assert result.liquidity_usd == 15000.0
        assert result.volume_24h_usd == 50000.0
        assert result.buys_1h == 100
        assert result.sells_1h == 50

    @pytest.mark.asyncio
    async def test_fetch_market_data_non_200_raises(self, service):
        """Test that non-200 status raises exception."""
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        with pytest.raises(Exception, match="DexScreener error"):
            await service._fetch_market_data("TestMint123")

    @pytest.mark.asyncio
    async def test_fetch_market_data_no_pairs_raises(self, service):
        """Test that empty pairs raises exception."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"pairs": []})

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        with pytest.raises(Exception, match="No pairs found"):
            await service._fetch_market_data("TestMint123")

    @pytest.mark.asyncio
    async def test_fetch_market_data_selects_highest_liquidity(self, service):
        """Test that highest liquidity pair is selected."""
        response_data = {
            "pairs": [
                {
                    "priceUsd": "0.001",
                    "priceNative": "0.00001",
                    "marketCap": "50000",
                    "liquidity": {"usd": "5000"},  # Lower liquidity
                    "volume": {"h24": "10000"},
                    "priceChange": {"h1": "5"},
                    "txns": {"h1": {"buys": 30, "sells": 20}},
                },
                {
                    "priceUsd": "0.002",
                    "priceNative": "0.00002",
                    "marketCap": "100000",
                    "liquidity": {"usd": "25000"},  # Higher liquidity - should be selected
                    "volume": {"h24": "50000"},
                    "priceChange": {"h1": "10"},
                    "txns": {"h1": {"buys": 100, "sells": 50}},
                },
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response_data)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_market_data("TestMint123")

        assert result.liquidity_usd == 25000.0
        assert result.market_cap_usd == 100000.0

    @pytest.mark.asyncio
    async def test_fetch_market_data_handles_null_values(self, service):
        """Test handling of null/missing values in response."""
        response_data = {
            "pairs": [
                {
                    "priceUsd": None,
                    "priceNative": None,
                    "marketCap": None,
                    "liquidity": {"usd": None},
                    "volume": {"h24": None},
                    "priceChange": {"h1": None},
                    "txns": {"h1": {"buys": None, "sells": None}},
                },
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response_data)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        result = await service._fetch_market_data("TestMint123")

        assert result.price_usd == 0.0
        assert result.market_cap_usd == 0.0
        assert result.liquidity_usd == 0.0


# =============================================================================
# Twitter Profile Fetch Tests
# =============================================================================

class TestFetchTwitterProfile:
    """Tests for _fetch_twitter_profile method."""

    @pytest.mark.asyncio
    async def test_fetch_twitter_profile_success(self, service, sample_twitter_profile_response):
        """Test successful Twitter profile fetch."""
        service.config.twitter_bearer_token = "test-bearer-token"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_twitter_profile_response)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        creator = CreatorProfile(
            wallet_address="TestWallet",
            twitter_handle="testtoken",
        )

        result = await service._fetch_twitter_profile(creator)

        assert result.twitter_followers == 5000
        assert result.twitter_account_age_days is not None

    @pytest.mark.asyncio
    async def test_fetch_twitter_profile_no_handle_returns_unchanged(self, service):
        """Test that creator without Twitter handle is returned unchanged."""
        creator = CreatorProfile(
            wallet_address="TestWallet",
            twitter_handle=None,
        )

        result = await service._fetch_twitter_profile(creator)

        assert result == creator

    @pytest.mark.asyncio
    async def test_fetch_twitter_profile_failure_graceful(self, service):
        """Test that Twitter fetch failure is handled gracefully."""
        service.config.twitter_bearer_token = "test-bearer-token"

        mock_http = MagicMock()
        mock_http.get = MagicMock(side_effect=Exception("Twitter API error"))
        service._http = mock_http

        creator = CreatorProfile(
            wallet_address="TestWallet",
            twitter_handle="testtoken",
        )

        # Should not raise
        result = await service._fetch_twitter_profile(creator)

        # Creator returned (possibly unchanged)
        assert result.twitter_handle == "testtoken"

    @pytest.mark.asyncio
    async def test_fetch_twitter_profile_non_200_ignored(self, service):
        """Test that non-200 Twitter response is ignored."""
        service.config.twitter_bearer_token = "test-bearer-token"

        mock_response = AsyncMock()
        mock_response.status = 429  # Rate limited

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        creator = CreatorProfile(
            wallet_address="TestWallet",
            twitter_handle="testtoken",
        )

        result = await service._fetch_twitter_profile(creator)

        # Followers should not be set
        assert result.twitter_followers is None


# =============================================================================
# Report Sending Tests
# =============================================================================

class TestSendReport:
    """Tests for _send_report method."""

    @pytest.mark.asyncio
    async def test_send_report_success(self, service, sample_graduation_model):
        """Test successful report sending."""
        mock_bot = AsyncMock()
        service._bot = mock_bot
        service.config.telegram_chat_id = "test-chat-id"

        await service._send_report(sample_graduation_model)

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == "test-chat-id"

    @pytest.mark.asyncio
    async def test_send_report_no_bot_skips(self, service, sample_graduation_model):
        """Test that report is skipped when no bot configured."""
        service._bot = None

        # Should not raise
        await service._send_report(sample_graduation_model)

    @pytest.mark.asyncio
    async def test_send_report_no_chat_id_skips(self, service, sample_graduation_model):
        """Test that report is skipped when no chat ID configured."""
        service._bot = AsyncMock()
        service.config.telegram_chat_id = ""

        # Should not raise
        await service._send_report(sample_graduation_model)

        service._bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_report_formats_html(self, service, sample_graduation_model):
        """Test that report is formatted as HTML."""
        from telegram.constants import ParseMode

        mock_bot = AsyncMock()
        service._bot = mock_bot
        service.config.telegram_chat_id = "test-chat-id"

        await service._send_report(sample_graduation_model)

        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["parse_mode"] == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_send_report_disables_preview(self, service, sample_graduation_model):
        """Test that web preview is disabled."""
        mock_bot = AsyncMock()
        service._bot = mock_bot
        service.config.telegram_chat_id = "test-chat-id"

        await service._send_report(sample_graduation_model)

        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["disable_web_page_preview"] is True

    @pytest.mark.asyncio
    async def test_send_report_telegram_error_handled(self, service, sample_graduation_model):
        """Test that Telegram errors are handled gracefully."""
        from telegram.error import TelegramError

        mock_bot = AsyncMock()
        mock_bot.send_message.side_effect = TelegramError("Send failed")
        service._bot = mock_bot
        service.config.telegram_chat_id = "test-chat-id"

        # Should not raise
        await service._send_report(sample_graduation_model)


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunction:
    """Tests for create_bags_intel_service factory function."""

    @pytest.mark.asyncio
    async def test_create_bags_intel_service_with_bitquery(self):
        """Test factory function with Bitquery configured."""
        with patch("bots.bags_intel.intel_service.load_config") as mock_load, \
             patch("bots.bags_intel.intel_service.BagsIntelService") as mock_service:

            mock_config = BagsIntelConfig(
                bitquery_api_key="test-key",
                telegram_bot_token="test-token",
            )
            mock_load.return_value = mock_config

            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance

            await create_bags_intel_service()

            mock_service.assert_called_once_with(mock_config)
            mock_instance.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bags_intel_service_missing_config_skips(self):
        """Test factory function without required config."""
        with patch("bots.bags_intel.intel_service.load_config") as mock_load, \
             patch("bots.bags_intel.intel_service.BagsIntelService") as mock_service, \
             patch("bots.bags_intel.intel_service.logger") as mock_logger:

            mock_config = BagsIntelConfig(
                bitquery_api_key="",
                telegram_bot_token="",
            )
            mock_load.return_value = mock_config

            await create_bags_intel_service()

            mock_service.assert_not_called()
            mock_logger.warning.assert_called()


# =============================================================================
# Bonding Metrics Estimation Tests
# =============================================================================

class TestBondingMetricsEstimation:
    """Tests for bonding metrics estimation in _gather_data."""

    @pytest.mark.asyncio
    async def test_bonding_metrics_volume_estimation(self, service):
        """Test volume estimation from market data."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(mint_address="Test", name="Test", symbol="TST")
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=40000.0,  # Should become 200 SOL estimate
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            # Volume estimation: 40000 / 200 = 200 SOL
            assert result.bonding.total_volume_sol == 200.0

    @pytest.mark.asyncio
    async def test_bonding_metrics_buyers_estimation(self, service):
        """Test buyer count estimation from market data."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(mint_address="Test", name="Test", symbol="TST")
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=50,  # Should become 100 unique buyers estimate
            sells_1h=25,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            # Buyers estimation: buys_1h * 2 = 100
            assert result.bonding.unique_buyers == 100
            assert result.bonding.unique_sellers == 50

    @pytest.mark.asyncio
    async def test_bonding_metrics_buy_sell_ratio_zero_sells(self, service):
        """Test buy/sell ratio when sells is zero."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(mint_address="Test", name="Test", symbol="TST")
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=0,  # Zero sells
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            # Default ratio when sells is 0
            assert result.bonding.buy_sell_ratio == 2.0


# =============================================================================
# Timestamp Parsing Tests
# =============================================================================

class TestTimestampParsing:
    """Tests for timestamp parsing in _gather_data."""

    @pytest.mark.asyncio
    async def test_gather_data_parses_iso_timestamp(self, service):
        """Test ISO timestamp parsing."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(mint_address="Test", name="Test", symbol="TST")
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp="2026-01-25T12:30:45Z",
            )

            assert result.timestamp.year == 2026
            assert result.timestamp.month == 1
            assert result.timestamp.day == 25

    @pytest.mark.asyncio
    async def test_gather_data_uses_utcnow_for_none_timestamp(self, service):
        """Test that utcnow is used when timestamp is None."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(mint_address="Test", name="Test", symbol="TST")
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        before = datetime.utcnow()

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            after = datetime.utcnow()
            assert before <= result.timestamp <= after


# =============================================================================
# Twitter Handle Extraction Tests
# =============================================================================

class TestTwitterHandleExtraction:
    """Tests for Twitter handle extraction in _gather_data."""

    @pytest.mark.asyncio
    async def test_gather_data_extracts_twitter_handle_from_token(self, service):
        """Test Twitter handle extraction strips @ prefix."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))

        token_meta = TokenMetadata(
            mint_address="Test",
            name="Test",
            symbol="TST",
            twitter="@testhandle",  # With @ prefix
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            # @ should be stripped
            assert result.creator.twitter_handle == "testhandle"

    @pytest.mark.asyncio
    async def test_gather_data_fetches_twitter_profile_when_configured(self, service):
        """Test that Twitter profile is fetched when bearer token is configured."""
        service._http = AsyncMock()
        service._scorer = AsyncMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=75.0,
            launch_quality=LaunchQuality.STRONG,
            risk_level=RiskLevel.LOW,
            bonding_score=75.0,
            creator_score=70.0,
            social_score=75.0,
            market_score=80.0,
            distribution_score=70.0,
        ))
        service.config.twitter_bearer_token = "test-bearer-token"

        token_meta = TokenMetadata(
            mint_address="Test",
            name="Test",
            symbol="TST",
            twitter="@testhandle",
        )
        market_data = MarketMetrics(
            price_usd=0.001,
            price_sol=0.00001,
            market_cap_usd=100000.0,
            liquidity_usd=15000.0,
            volume_24h_usd=50000.0,
            price_change_1h=10.0,
            buys_1h=100,
            sells_1h=50,
        )

        with patch.object(service, "_fetch_token_metadata", new_callable=AsyncMock) as mock_token, \
             patch.object(service, "_fetch_market_data", new_callable=AsyncMock) as mock_market, \
             patch.object(service, "_fetch_twitter_profile", new_callable=AsyncMock) as mock_twitter:

            mock_token.return_value = token_meta
            mock_market.return_value = market_data
            enhanced_creator = CreatorProfile(
                wallet_address="Creator",
                twitter_handle="testhandle",
                twitter_followers=5000,
            )
            mock_twitter.return_value = enhanced_creator

            result = await service._gather_data(
                mint_address="Test",
                creator_wallet="Creator",
                tx_signature="TxSig",
                timestamp=None,
            )

            mock_twitter.assert_called_once()
            assert result.creator.twitter_followers == 5000


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handle_graduation_short_mint_address_logged(self, service):
        """Test that short mint addresses are handled gracefully."""
        event = {"mint_address": "short"}

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = None

            # Should not raise even with short address
            await service._handle_graduation(event)

    @pytest.mark.asyncio
    async def test_service_handles_concurrent_graduations(self, service, sample_graduation_model):
        """Test handling of multiple concurrent graduation events."""
        events = [
            {"mint_address": f"Mint{i}", "signature": f"Sig{i}", "creator": "Creator"}
            for i in range(5)
        ]

        with patch.object(service, "_gather_data", new_callable=AsyncMock) as mock_gather, \
             patch.object(service, "_send_report", new_callable=AsyncMock):

            mock_gather.return_value = sample_graduation_model

            # Process all events concurrently
            await asyncio.gather(*[service._handle_graduation(e) for e in events])

            # All should be processed (minus deduplication)
            assert mock_gather.call_count >= 1

    def test_config_is_configured_property(self, config):
        """Test is_configured property."""
        assert config.is_configured is True

        no_bitquery = BagsIntelConfig(telegram_bot_token="token")
        assert no_bitquery.is_configured is False

        no_telegram = BagsIntelConfig(bitquery_api_key="key")
        assert no_telegram.is_configured is False


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestIntegration:
    """Integration-style tests for complete flows."""

    @pytest.mark.asyncio
    async def test_full_graduation_flow(self, service, sample_dexscreener_token_response):
        """Test complete graduation processing flow."""
        event = {
            "mint_address": "IntegrationTestMint111111111111111111111111",
            "signature": "IntegrationTestSig",
            "creator": "IntegrationCreator",
            "timestamp": "2026-01-25T12:00:00Z",
        }

        # Setup mocks
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_dexscreener_token_response)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        service._scorer = MagicMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=80.0,
            launch_quality=LaunchQuality.EXCEPTIONAL,
            risk_level=RiskLevel.LOW,
            bonding_score=85.0,
            creator_score=80.0,
            social_score=75.0,
            market_score=85.0,
            distribution_score=75.0,
            green_flags=["Strong liquidity"],
            red_flags=[],
            warnings=[],
        ))

        mock_bot = AsyncMock()
        service._bot = mock_bot

        # Set thresholds
        service.config.min_graduation_mcap = 10000
        service.config.min_score_to_report = 30

        # Execute
        await service._handle_graduation(event)

        # Verify
        assert event["mint_address"] in service._processed
        mock_bot.send_message.assert_called_once()
        assert service._report_count == 1

    @pytest.mark.asyncio
    async def test_full_graduation_flow_below_threshold(
        self, service, sample_dexscreener_token_response
    ):
        """Test graduation flow when below threshold."""
        event = {
            "mint_address": "LowScoreTestMint111111111111111111111111111",
            "signature": "TestSig",
            "creator": "Creator",
            "timestamp": "2026-01-25T12:00:00Z",
        }

        # Setup mocks
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_dexscreener_token_response)

        mock_http = MagicMock()
        mock_http.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))
        service._http = mock_http

        service._scorer = MagicMock()
        service._scorer.calculate_score = AsyncMock(return_value=IntelScore(
            overall_score=20.0,  # Below threshold
            launch_quality=LaunchQuality.POOR,
            risk_level=RiskLevel.HIGH,
            bonding_score=15.0,
            creator_score=20.0,
            social_score=25.0,
            market_score=20.0,
            distribution_score=15.0,
            red_flags=["Low score"],
        ))

        mock_bot = AsyncMock()
        service._bot = mock_bot

        # Set thresholds
        service.config.min_graduation_mcap = 10000
        service.config.min_score_to_report = 30

        # Execute
        await service._handle_graduation(event)

        # Verify - no report sent
        mock_bot.send_message.assert_not_called()
        assert service._report_count == 0
