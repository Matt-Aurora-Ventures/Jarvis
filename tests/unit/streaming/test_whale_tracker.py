"""
Tests for whale wallet tracking via Yellowstone Geyser.

Tests cover:
- Whale wallet subscription management
- Token balance change detection
- Trade detection and classification
- Copy trading signals
- Wallet scoring and categorization
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Import the module under test (will fail until implemented)
try:
    from core.streaming.whale_tracker import (
        WhaleTracker,
        WhaleTrackerConfig,
        WalletConfig,
        WalletActivity,
        WhaleEvent,
        WhaleEventType,
        TradeDirection,
        WalletCategory,
        WalletScore,
    )
    from core.streaming.geyser_client import GeyserClient, AccountUpdate
    HAS_WHALE_TRACKER = True
except ImportError:
    HAS_WHALE_TRACKER = False
    WhaleTracker = None
    WhaleTrackerConfig = None
    WalletConfig = None
    WalletActivity = None
    WhaleEvent = None
    WhaleEventType = None
    TradeDirection = None
    WalletCategory = None
    WalletScore = None


pytestmark = pytest.mark.skipif(not HAS_WHALE_TRACKER, reason="whale_tracker not implemented yet")


# Test wallets (example known traders)
KNOWN_WHALE_WALLET = "8PxTkvqXxJfC6HVc5NhNqLb3jfTRr7FJxWGLwwEA9KvF"
KNOWN_SNIPER_WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"


class TestWalletCategory:
    """Tests for wallet category enum."""

    def test_wallet_categories(self):
        """Should have all expected wallet categories."""
        assert WalletCategory.WHALE is not None
        assert WalletCategory.SMART_MONEY is not None
        assert WalletCategory.SNIPER is not None
        assert WalletCategory.MARKET_MAKER is not None
        assert WalletCategory.INSIDER is not None
        assert WalletCategory.UNKNOWN is not None


class TestTradeDirection:
    """Tests for trade direction enum."""

    def test_trade_directions(self):
        """Should have buy and sell directions."""
        assert TradeDirection.BUY is not None
        assert TradeDirection.SELL is not None


class TestWhaleEventType:
    """Tests for whale event types."""

    def test_event_types(self):
        """Should have all expected event types."""
        assert WhaleEventType.LARGE_BUY is not None
        assert WhaleEventType.LARGE_SELL is not None
        assert WhaleEventType.NEW_POSITION is not None
        assert WhaleEventType.POSITION_CLOSED is not None
        assert WhaleEventType.ACCUMULATION is not None
        assert WhaleEventType.DISTRIBUTION is not None
        assert WhaleEventType.TRANSFER_IN is not None
        assert WhaleEventType.TRANSFER_OUT is not None


class TestWalletConfig:
    """Tests for wallet configuration."""

    def test_wallet_config_creation(self):
        """Should create wallet config with required fields."""
        config = WalletConfig(
            address=KNOWN_WHALE_WALLET,
            label="Known Whale",
            category=WalletCategory.WHALE,
        )

        assert config.address == KNOWN_WHALE_WALLET
        assert config.label == "Known Whale"
        assert config.category == WalletCategory.WHALE

    def test_wallet_config_defaults(self):
        """Should have sensible defaults."""
        config = WalletConfig(address=KNOWN_WHALE_WALLET)

        assert config.label is None
        assert config.category == WalletCategory.UNKNOWN
        assert config.min_trade_size_usd == 0
        assert config.enabled is True

    def test_wallet_config_with_thresholds(self):
        """Should support custom thresholds."""
        config = WalletConfig(
            address=KNOWN_WHALE_WALLET,
            min_trade_size_usd=10000,
            track_all_tokens=False,
            tokens_to_track=["Token1...", "Token2..."],
        )

        assert config.min_trade_size_usd == 10000
        assert config.track_all_tokens is False
        assert len(config.tokens_to_track) == 2


class TestWhaleTrackerConfig:
    """Tests for WhaleTrackerConfig."""

    def test_config_defaults(self):
        """Config should have sensible defaults."""
        config = WhaleTrackerConfig()

        assert config.min_trade_size_usd == 5000
        assert config.large_trade_threshold_usd == 50000
        assert config.accumulation_window_hours == 24
        assert config.copy_trade_enabled is False

    def test_config_with_wallets(self):
        """Should accept wallet list."""
        wallets = [
            WalletConfig(address=KNOWN_WHALE_WALLET, label="Whale 1"),
            WalletConfig(address=KNOWN_SNIPER_WALLET, label="Sniper 1"),
        ]
        config = WhaleTrackerConfig(wallets=wallets)

        assert len(config.wallets) == 2

    def test_config_from_file(self):
        """Should load wallets from config file."""
        mock_file_content = """
        wallets:
          - address: "Wallet1..."
            label: "Known Whale"
            category: "whale"
          - address: "Wallet2..."
            label: "Sniper"
            category: "sniper"
        """

        with patch("builtins.open", MagicMock()):
            with patch("yaml.safe_load", return_value={
                "wallets": [
                    {"address": "Wallet1...", "label": "Known Whale", "category": "whale"},
                    {"address": "Wallet2...", "label": "Sniper", "category": "sniper"},
                ]
            }):
                config = WhaleTrackerConfig.from_file("wallets.yaml")
                # Should parse without error


class TestWalletActivity:
    """Tests for WalletActivity dataclass."""

    def test_activity_creation(self):
        """Should create wallet activity record."""
        activity = WalletActivity(
            wallet_address=KNOWN_WHALE_WALLET,
            token_mint="TokenMint...",
            token_symbol="TEST",
            amount_change=1000000,
            direction=TradeDirection.BUY,
            slot=12345678,
            signature="TxSignature...",
            estimated_value_usd=5000.0,
        )

        assert activity.wallet_address == KNOWN_WHALE_WALLET
        assert activity.direction == TradeDirection.BUY
        assert activity.estimated_value_usd == 5000.0

    def test_activity_is_large_trade(self):
        """Should identify large trades."""
        activity = WalletActivity(
            wallet_address=KNOWN_WHALE_WALLET,
            token_mint="TokenMint...",
            token_symbol="TEST",
            amount_change=1000000,
            direction=TradeDirection.BUY,
            slot=12345678,
            signature="TxSignature...",
            estimated_value_usd=100000.0,  # $100k
        )

        assert activity.is_large_trade(threshold_usd=50000) is True
        assert activity.is_large_trade(threshold_usd=200000) is False


class TestWhaleEvent:
    """Tests for WhaleEvent dataclass."""

    def test_whale_event_creation(self):
        """Should create whale event with required fields."""
        event = WhaleEvent(
            event_type=WhaleEventType.LARGE_BUY,
            wallet_address=KNOWN_WHALE_WALLET,
            wallet_label="Known Whale",
            wallet_category=WalletCategory.WHALE,
            token_mint="TokenMint...",
            token_symbol="TEST",
            amount=1000000,
            value_usd=50000.0,
            slot=12345678,
            timestamp=1234567890.0,
        )

        assert event.event_type == WhaleEventType.LARGE_BUY
        assert event.value_usd == 50000.0

    def test_whale_event_to_dict(self):
        """Should serialize to dictionary."""
        event = WhaleEvent(
            event_type=WhaleEventType.LARGE_BUY,
            wallet_address=KNOWN_WHALE_WALLET,
            wallet_label="Known Whale",
            wallet_category=WalletCategory.WHALE,
            token_mint="TokenMint...",
            token_symbol="TEST",
            amount=1000000,
            value_usd=50000.0,
            slot=12345678,
            timestamp=1234567890.0,
        )

        data = event.to_dict()

        assert data["event_type"] == "large_buy"  # Lowercase from enum value
        assert data["wallet_address"] == KNOWN_WHALE_WALLET
        assert data["value_usd"] == 50000.0


class TestWalletScore:
    """Tests for WalletScore dataclass."""

    def test_wallet_score_creation(self):
        """Should create wallet score."""
        score = WalletScore(
            address=KNOWN_WHALE_WALLET,
            total_trades=100,
            win_rate=0.65,
            avg_profit_pct=15.5,
            total_volume_usd=500000.0,
            avg_hold_time_hours=48.0,
            category=WalletCategory.SMART_MONEY,
        )

        assert score.win_rate == 0.65
        assert score.category == WalletCategory.SMART_MONEY

    def test_wallet_score_ranking(self):
        """Should calculate overall ranking score."""
        score = WalletScore(
            address=KNOWN_WHALE_WALLET,
            total_trades=100,
            win_rate=0.65,
            avg_profit_pct=15.5,
            total_volume_usd=500000.0,
            avg_hold_time_hours=48.0,
            category=WalletCategory.SMART_MONEY,
        )

        ranking = score.get_ranking_score()

        assert isinstance(ranking, float)
        assert 0 <= ranking <= 100


class TestWhaleTrackerInit:
    """Tests for WhaleTracker initialization."""

    def test_init_with_geyser_client(self):
        """Should initialize with GeyserClient."""
        mock_client = MagicMock(spec=GeyserClient)
        config = WhaleTrackerConfig()

        tracker = WhaleTracker(mock_client, config)

        assert tracker.geyser_client == mock_client
        assert tracker.config == config

    def test_init_with_wallets(self):
        """Should register configured wallets."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [
            WalletConfig(address=KNOWN_WHALE_WALLET, label="Whale 1"),
            WalletConfig(address=KNOWN_SNIPER_WALLET, label="Sniper 1"),
        ]
        config = WhaleTrackerConfig(wallets=wallets)

        tracker = WhaleTracker(mock_client, config)

        assert len(tracker._tracked_wallets) == 2


class TestWhaleTrackerSubscription:
    """Tests for WhaleTracker subscription management."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_wallets(self):
        """Should subscribe to wallet token accounts."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.subscribe_accounts = AsyncMock(return_value="sub-id")

        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets)
        tracker = WhaleTracker(mock_client, config)

        await tracker.start()

        mock_client.subscribe_accounts.assert_called()

    @pytest.mark.asyncio
    async def test_add_wallet_dynamically(self):
        """Should allow adding wallets at runtime."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.subscribe_accounts = AsyncMock(return_value="sub-id")

        tracker = WhaleTracker(mock_client, WhaleTrackerConfig())
        tracker._running = True

        await tracker.add_wallet(WalletConfig(
            address=KNOWN_WHALE_WALLET,
            label="New Whale",
        ))

        assert KNOWN_WHALE_WALLET in tracker._tracked_wallets

    @pytest.mark.asyncio
    async def test_remove_wallet(self):
        """Should allow removing wallets."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.unsubscribe = AsyncMock()

        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets)
        tracker = WhaleTracker(mock_client, config)
        tracker._wallet_subscriptions[KNOWN_WHALE_WALLET] = "sub-id"

        await tracker.remove_wallet(KNOWN_WHALE_WALLET)

        assert KNOWN_WHALE_WALLET not in tracker._tracked_wallets

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_all(self):
        """Should unsubscribe from all when stopped."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.unsubscribe = AsyncMock()

        tracker = WhaleTracker(mock_client, WhaleTrackerConfig())
        tracker._wallet_subscriptions = {
            KNOWN_WHALE_WALLET: "sub-1",
            KNOWN_SNIPER_WALLET: "sub-2",
        }

        await tracker.stop()

        assert mock_client.unsubscribe.call_count == 2


class TestWhaleTrackerEventHandling:
    """Tests for WhaleTracker event handling."""

    @pytest.mark.asyncio
    async def test_detects_buy(self):
        """Should emit LARGE_BUY event for significant purchases."""
        mock_client = MagicMock(spec=GeyserClient)

        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET, label="Whale")]
        config = WhaleTrackerConfig(
            wallets=wallets,
            large_trade_threshold_usd=10000,
            min_trade_size_usd=100,  # Low threshold to ensure event is emitted
        )
        tracker = WhaleTracker(mock_client, config)

        events_received = []

        def on_event(event: WhaleEvent):
            events_received.append(event)

        tracker.on_whale_event(on_event)

        # Set up previous balance (small amount, not zero to avoid NEW_POSITION event)
        tracker._wallet_balances[KNOWN_WHALE_WALLET] = {
            "TokenMint...": {"amount": 1, "slot": 100}
        }

        # Simulate token account update showing new balance
        # We want: value_usd = abs(amount_change / 1e9 * price_usd) >= large_trade_threshold (10000)
        # With price = 1.0 and amount_change = 10,000,000,000,000 (10T smallest units = 10000 tokens)
        # value = 10000 tokens * $1 = $10,000 which meets threshold
        with patch.object(tracker, "_get_token_price_usd", new_callable=AsyncMock, return_value=1.0):
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="TokenMint...",
                new_balance=10_000_000_000_001,  # 10000 tokens with 9 decimals + 1 (prev was 1)
                slot=101,
            )

        # $10k trade should trigger large buy
        buy_events = [e for e in events_received if e.event_type == WhaleEventType.LARGE_BUY]
        assert len(buy_events) >= 1

    @pytest.mark.asyncio
    async def test_detects_sell(self):
        """Should emit LARGE_SELL event for significant sales."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET, label="Whale")]
        config = WhaleTrackerConfig(
            wallets=wallets,
            large_trade_threshold_usd=10000,
            min_trade_size_usd=100,
        )
        tracker = WhaleTracker(mock_client, config)

        events_received = []

        def on_event(event: WhaleEvent):
            events_received.append(event)

        tracker.on_whale_event(on_event)

        # Set up previous balance - 10001 tokens at $1 each = $10001
        # (10001 * 1e9 = 10_001_000_000_000 smallest units)
        tracker._wallet_balances[KNOWN_WHALE_WALLET] = {
            "TokenMint...": {"amount": 10_001_000_000_000, "slot": 100}
        }

        # Simulate token account update showing reduced balance (but not zero to avoid POSITION_CLOSED)
        # Selling 10000 tokens at $1 = $10,000 which meets threshold
        with patch.object(tracker, "_get_token_price_usd", new_callable=AsyncMock, return_value=1.0):
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="TokenMint...",
                new_balance=1_000_000_000,  # 1 token left
                slot=101,
            )

        sell_events = [e for e in events_received if e.event_type == WhaleEventType.LARGE_SELL]
        assert len(sell_events) >= 1

    @pytest.mark.asyncio
    async def test_detects_new_position(self):
        """Should emit NEW_POSITION when wallet enters new token."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets, min_trade_size_usd=100)
        tracker = WhaleTracker(mock_client, config)

        events_received = []

        def on_event(event: WhaleEvent):
            events_received.append(event)

        tracker.on_whale_event(on_event)

        # No previous balance for this token (empty dict for this wallet)
        tracker._wallet_balances[KNOWN_WHALE_WALLET] = {}

        # Buy 1000 tokens at $1 = $1000 which is > min_trade_size_usd (100)
        with patch.object(tracker, "_get_token_price_usd", new_callable=AsyncMock, return_value=1.0):
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="NewToken...",
                new_balance=1_000_000_000_000,  # 1000 tokens with 9 decimals
                slot=101,
            )

        new_position_events = [e for e in events_received if e.event_type == WhaleEventType.NEW_POSITION]
        assert len(new_position_events) >= 1

    @pytest.mark.asyncio
    async def test_detects_position_closed(self):
        """Should emit POSITION_CLOSED when balance goes to zero."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets, min_trade_size_usd=100)
        tracker = WhaleTracker(mock_client, config)

        events_received = []

        def on_event(event: WhaleEvent):
            events_received.append(event)

        tracker.on_whale_event(on_event)

        # Previous balance exists - 1000 tokens at $1 = $1000
        tracker._wallet_balances[KNOWN_WHALE_WALLET] = {
            "Token...": {"amount": 1_000_000_000_000, "slot": 100}  # 1000 tokens
        }

        # Sell all tokens - $1000 > min_trade_size (100)
        with patch.object(tracker, "_get_token_price_usd", new_callable=AsyncMock, return_value=1.0):
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                new_balance=0,
                slot=101,
            )

        closed_events = [e for e in events_received if e.event_type == WhaleEventType.POSITION_CLOSED]
        assert len(closed_events) >= 1

    @pytest.mark.asyncio
    async def test_ignores_small_trades(self):
        """Should not emit events for trades below threshold."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets, min_trade_size_usd=1000)
        tracker = WhaleTracker(mock_client, config)

        events_received = []

        def on_event(event: WhaleEvent):
            events_received.append(event)

        tracker.on_whale_event(on_event)

        tracker._wallet_balances[KNOWN_WHALE_WALLET] = {
            "Token...": {"amount": 0, "slot": 100}
        }

        # Small trade ($10)
        with patch.object(tracker, "_get_token_price_usd", return_value=0.0001):
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                new_balance=100000,  # $10 worth
                slot=101,
            )

        # Should not emit large trade events
        large_events = [e for e in events_received if e.event_type in [
            WhaleEventType.LARGE_BUY, WhaleEventType.LARGE_SELL
        ]]
        assert len(large_events) == 0


class TestWhaleTrackerAccumulation:
    """Tests for accumulation/distribution detection."""

    @pytest.mark.asyncio
    async def test_detects_accumulation(self):
        """Should detect accumulation pattern over time."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(wallets=wallets, accumulation_window_hours=24)
        tracker = WhaleTracker(mock_client, config)

        # Simulate multiple buys over time
        tracker._activity_history[KNOWN_WHALE_WALLET] = [
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=100000,
                direction=TradeDirection.BUY,
                slot=100,
                signature="sig1",
                estimated_value_usd=10000,
            ),
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=100000,
                direction=TradeDirection.BUY,
                slot=200,
                signature="sig2",
                estimated_value_usd=10000,
            ),
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=100000,
                direction=TradeDirection.BUY,
                slot=300,
                signature="sig3",
                estimated_value_usd=10000,
            ),
        ]

        is_accumulating = tracker._detect_accumulation(
            wallet_address=KNOWN_WHALE_WALLET,
            token_mint="Token...",
        )

        assert is_accumulating is True

    @pytest.mark.asyncio
    async def test_detects_distribution(self):
        """Should detect distribution pattern over time."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(
            wallets=wallets,
            accumulation_window_hours=24,
            accumulation_trade_count=2,  # Require only 2 trades for test
        )
        tracker = WhaleTracker(mock_client, config)

        # Simulate multiple sells over time (within window)
        current_time = time.time()
        tracker._activity_history[KNOWN_WHALE_WALLET] = [
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=-100000,
                direction=TradeDirection.SELL,
                slot=100,
                signature="sig1",
                estimated_value_usd=10000,
                timestamp=current_time - 3600,  # 1 hour ago
            ),
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=-100000,
                direction=TradeDirection.SELL,
                slot=200,
                signature="sig2",
                estimated_value_usd=10000,
                timestamp=current_time - 1800,  # 30 min ago
            ),
        ]

        is_distributing = tracker._detect_distribution(
            wallet_address=KNOWN_WHALE_WALLET,
            token_mint="Token...",
        )

        assert is_distributing is True


class TestWhaleTrackerCopyTrading:
    """Tests for copy trading functionality."""

    @pytest.mark.asyncio
    async def test_copy_trade_signal_emitted(self):
        """Should emit copy trade signal when enabled."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(
            address=KNOWN_WHALE_WALLET,
            category=WalletCategory.SMART_MONEY,
        )]
        config = WhaleTrackerConfig(
            wallets=wallets,
            copy_trade_enabled=True,
            copy_trade_min_wallet_score=50,
            min_trade_size_usd=100,
        )
        tracker = WhaleTracker(mock_client, config)

        # Set up wallet score (high score to pass threshold)
        # Score = 0.70*40 + (20/50)*30 + (1000000/1000000)*20 + (100/100)*10 = 28 + 12 + 20 + 10 = 70
        tracker._wallet_scores[KNOWN_WHALE_WALLET] = WalletScore(
            address=KNOWN_WHALE_WALLET,
            total_trades=100,
            win_rate=0.70,
            avg_profit_pct=20.0,
            total_volume_usd=1000000,
            avg_hold_time_hours=24,
            category=WalletCategory.SMART_MONEY,
        )

        copy_signals = []

        def on_copy_signal(signal):
            copy_signals.append(signal)

        tracker.on_copy_trade_signal(on_copy_signal)

        # Simulate buy from smart money wallet (new position)
        # 1000 tokens at $1 = $1000 which is > min_trade_size (100)
        with patch.object(tracker, "_get_token_price_usd", new_callable=AsyncMock, return_value=1.0):
            tracker._wallet_balances[KNOWN_WHALE_WALLET] = {}  # No previous balance
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                new_balance=1_000_000_000_000,  # 1000 tokens
                slot=101,
            )

        # Should emit copy trade signal (score 70 > threshold 50)
        assert len(copy_signals) >= 1

    @pytest.mark.asyncio
    async def test_copy_trade_filters_low_score_wallets(self):
        """Should not emit copy signals for low-scoring wallets."""
        mock_client = MagicMock(spec=GeyserClient)
        wallets = [WalletConfig(address=KNOWN_WHALE_WALLET)]
        config = WhaleTrackerConfig(
            wallets=wallets,
            copy_trade_enabled=True,
            copy_trade_min_wallet_score=80,
        )
        tracker = WhaleTracker(mock_client, config)

        # Low scoring wallet
        tracker._wallet_scores[KNOWN_WHALE_WALLET] = WalletScore(
            address=KNOWN_WHALE_WALLET,
            total_trades=10,
            win_rate=0.40,
            avg_profit_pct=5.0,
            total_volume_usd=10000,
            avg_hold_time_hours=24,
            category=WalletCategory.UNKNOWN,
        )

        copy_signals = []

        def on_copy_signal(signal):
            copy_signals.append(signal)

        tracker.on_copy_trade_signal(on_copy_signal)

        with patch.object(tracker, "_get_token_price_usd", return_value=0.10):
            tracker._wallet_balances[KNOWN_WHALE_WALLET] = {}
            await tracker._handle_balance_change(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                new_balance=1000000,
                slot=101,
            )

        # Should NOT emit copy trade signal
        assert len(copy_signals) == 0


class TestWhaleTrackerMetrics:
    """Tests for WhaleTracker metrics."""

    def test_get_stats(self):
        """Should return tracking statistics."""
        mock_client = MagicMock(spec=GeyserClient)
        tracker = WhaleTracker(mock_client, WhaleTrackerConfig())

        tracker._tracked_wallets = {KNOWN_WHALE_WALLET: MagicMock()}
        tracker._events_emitted = 50
        tracker._updates_processed = 100

        stats = tracker.get_stats()

        assert stats["wallets_tracked"] == 1
        assert stats["events_emitted"] == 50
        assert stats["updates_processed"] == 100

    def test_get_wallet_activity(self):
        """Should return recent activity for a wallet."""
        mock_client = MagicMock(spec=GeyserClient)
        tracker = WhaleTracker(mock_client, WhaleTrackerConfig())

        tracker._activity_history[KNOWN_WHALE_WALLET] = [
            WalletActivity(
                wallet_address=KNOWN_WHALE_WALLET,
                token_mint="Token...",
                token_symbol="TEST",
                amount_change=100000,
                direction=TradeDirection.BUY,
                slot=100,
                signature="sig1",
                estimated_value_usd=10000,
            ),
        ]

        activity = tracker.get_wallet_activity(KNOWN_WHALE_WALLET)

        assert len(activity) == 1
        assert activity[0].wallet_address == KNOWN_WHALE_WALLET

    def test_get_top_wallets(self):
        """Should return top-scoring wallets."""
        mock_client = MagicMock(spec=GeyserClient)
        tracker = WhaleTracker(mock_client, WhaleTrackerConfig())

        tracker._wallet_scores = {
            "Wallet1": WalletScore(
                address="Wallet1",
                total_trades=100,
                win_rate=0.70,
                avg_profit_pct=20,
                total_volume_usd=1000000,
                avg_hold_time_hours=24,
                category=WalletCategory.SMART_MONEY,
            ),
            "Wallet2": WalletScore(
                address="Wallet2",
                total_trades=50,
                win_rate=0.50,
                avg_profit_pct=10,
                total_volume_usd=100000,
                avg_hold_time_hours=48,
                category=WalletCategory.UNKNOWN,
            ),
        }

        top = tracker.get_top_wallets(n=2)

        assert len(top) == 2
        # Wallet1 should rank higher
        assert top[0].address == "Wallet1"
