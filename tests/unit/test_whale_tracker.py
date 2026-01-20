"""
Tests for Whale Tracker Module.

Tests cover:
- Large transaction monitoring (>$10k threshold)
- Wallet labeling (known whales)
- Movement pattern analysis
- Accumulation/distribution detection
- Alert generation
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any


class TestWhaleTrackerDataClasses:
    """Test data classes for whale tracking."""

    def test_transaction_type_enum(self):
        """Test TransactionType enum values."""
        from core.analysis.whale_tracker import TransactionType

        assert TransactionType.TRANSFER.value == "transfer"
        assert TransactionType.SWAP.value == "swap"
        assert TransactionType.MINT.value == "mint"
        assert TransactionType.BURN.value == "burn"
        assert TransactionType.STAKE.value == "stake"
        assert TransactionType.UNSTAKE.value == "unstake"

    def test_whale_tier_enum(self):
        """Test WhaleTier enum values."""
        from core.analysis.whale_tracker import WhaleTier

        assert WhaleTier.MEGA.value == "mega"
        assert WhaleTier.LARGE.value == "large"
        assert WhaleTier.MEDIUM.value == "medium"
        assert WhaleTier.SMALL.value == "small"

    def test_movement_pattern_enum(self):
        """Test MovementPattern enum values."""
        from core.analysis.whale_tracker import MovementPattern

        assert MovementPattern.ACCUMULATION.value == "accumulation"
        assert MovementPattern.DISTRIBUTION.value == "distribution"
        assert MovementPattern.ROTATION.value == "rotation"
        assert MovementPattern.NEUTRAL.value == "neutral"

    def test_alert_severity_enum(self):
        """Test AlertSeverity enum values."""
        from core.analysis.whale_tracker import AlertSeverity

        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_whale_transaction_creation(self):
        """Test WhaleTransaction dataclass creation."""
        from core.analysis.whale_tracker import WhaleTransaction, TransactionType

        tx = WhaleTransaction(
            signature="abc123",
            timestamp=datetime.now(timezone.utc),
            from_wallet="wallet1",
            to_wallet="wallet2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert tx.signature == "abc123"
        assert tx.from_wallet == "wallet1"
        assert tx.to_wallet == "wallet2"
        assert tx.amount == 100.0
        assert tx.usd_value == 15000.0
        assert tx.transaction_type == TransactionType.TRANSFER

    def test_whale_wallet_creation(self):
        """Test WhaleWallet dataclass creation."""
        from core.analysis.whale_tracker import WhaleWallet, WhaleTier

        wallet = WhaleWallet(
            address="wallet123",
            label="Test Whale",
            tier=WhaleTier.LARGE,
            total_value_usd=500000.0,
        )

        assert wallet.address == "wallet123"
        assert wallet.label == "Test Whale"
        assert wallet.tier == WhaleTier.LARGE
        assert wallet.total_value_usd == 500000.0
        assert wallet.first_seen is not None
        assert wallet.tags == []

    def test_whale_alert_creation(self):
        """Test WhaleAlert dataclass creation."""
        from core.analysis.whale_tracker import WhaleAlert, AlertSeverity

        alert = WhaleAlert(
            id="alert123",
            timestamp=datetime.now(timezone.utc),
            wallet_address="wallet1",
            alert_type="large_transfer",
            severity=AlertSeverity.HIGH,
            message="Large transfer detected",
            usd_value=50000.0,
        )

        assert alert.id == "alert123"
        assert alert.wallet_address == "wallet1"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.usd_value == 50000.0

    def test_movement_analysis_creation(self):
        """Test MovementAnalysis dataclass creation."""
        from core.analysis.whale_tracker import MovementAnalysis, MovementPattern

        analysis = MovementAnalysis(
            wallet_address="wallet1",
            analysis_period_hours=24,
            pattern=MovementPattern.ACCUMULATION,
            confidence=0.85,
            total_inflow_usd=100000.0,
            total_outflow_usd=20000.0,
            net_flow_usd=80000.0,
            transaction_count=15,
        )

        assert analysis.pattern == MovementPattern.ACCUMULATION
        assert analysis.confidence == 0.85
        assert analysis.net_flow_usd == 80000.0


class TestWhaleTrackerCore:
    """Test core WhaleTracker functionality."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker

        return WhaleTracker(
            min_transaction_usd=10000.0,
            alert_threshold_usd=50000.0,
        )

    def test_tracker_initialization(self, tracker):
        """Test tracker initializes correctly."""
        assert tracker.min_transaction_usd == 10000.0
        assert tracker.alert_threshold_usd == 50000.0
        assert tracker._known_wallets == {}
        assert tracker._transactions == []

    def test_tracker_default_thresholds(self):
        """Test tracker uses sensible defaults."""
        from core.analysis.whale_tracker import WhaleTracker

        tracker = WhaleTracker()
        assert tracker.min_transaction_usd == 10000.0
        assert tracker.alert_threshold_usd == 50000.0

    def test_is_whale_transaction_above_threshold(self, tracker):
        """Test detection of whale-sized transactions."""
        # Above threshold
        assert tracker.is_whale_transaction(15000.0) is True
        # Exactly at threshold
        assert tracker.is_whale_transaction(10000.0) is True
        # Below threshold
        assert tracker.is_whale_transaction(9999.99) is False

    def test_classify_whale_tier(self, tracker):
        """Test whale tier classification based on portfolio value."""
        from core.analysis.whale_tracker import WhaleTier

        # Mega whale: >$10M
        assert tracker.classify_whale_tier(15000000.0) == WhaleTier.MEGA
        # Large whale: $1M-$10M
        assert tracker.classify_whale_tier(5000000.0) == WhaleTier.LARGE
        # Medium whale: $100k-$1M
        assert tracker.classify_whale_tier(500000.0) == WhaleTier.MEDIUM
        # Small whale: <$100k but significant
        assert tracker.classify_whale_tier(50000.0) == WhaleTier.SMALL


class TestWalletLabeling:
    """Test wallet labeling and management."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker

        return WhaleTracker()

    def test_register_known_wallet(self, tracker):
        """Test registering a known whale wallet."""
        from core.analysis.whale_tracker import WhaleTier

        tracker.register_wallet(
            address="wallet123",
            label="Alameda Research",
            tier=WhaleTier.MEGA,
            tags=["exchange", "market_maker"],
        )

        wallet = tracker.get_wallet("wallet123")
        assert wallet is not None
        assert wallet.label == "Alameda Research"
        assert wallet.tier == WhaleTier.MEGA
        assert "exchange" in wallet.tags

    def test_get_unknown_wallet_returns_none(self, tracker):
        """Test getting unknown wallet returns None."""
        wallet = tracker.get_wallet("unknown_wallet")
        assert wallet is None

    def test_update_wallet_value(self, tracker):
        """Test updating a wallet's total value."""
        from core.analysis.whale_tracker import WhaleTier

        tracker.register_wallet(
            address="wallet123",
            label="Test Whale",
            tier=WhaleTier.MEDIUM,
        )

        tracker.update_wallet_value("wallet123", 5000000.0)
        wallet = tracker.get_wallet("wallet123")

        # Tier should be updated based on new value
        assert wallet.total_value_usd == 5000000.0
        assert wallet.tier == WhaleTier.LARGE

    def test_list_known_wallets(self, tracker):
        """Test listing all known wallets."""
        from core.analysis.whale_tracker import WhaleTier

        tracker.register_wallet("w1", "Whale 1", WhaleTier.MEGA)
        tracker.register_wallet("w2", "Whale 2", WhaleTier.LARGE)
        tracker.register_wallet("w3", "Whale 3", WhaleTier.MEDIUM)

        wallets = tracker.list_wallets()
        assert len(wallets) == 3

    def test_list_wallets_by_tier(self, tracker):
        """Test filtering wallets by tier."""
        from core.analysis.whale_tracker import WhaleTier

        tracker.register_wallet("w1", "Mega 1", WhaleTier.MEGA)
        tracker.register_wallet("w2", "Large 1", WhaleTier.LARGE)
        tracker.register_wallet("w3", "Mega 2", WhaleTier.MEGA)

        mega_wallets = tracker.list_wallets(tier=WhaleTier.MEGA)
        assert len(mega_wallets) == 2


class TestTransactionTracking:
    """Test transaction tracking and recording."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker

        return WhaleTracker(min_transaction_usd=10000.0)

    @pytest.mark.asyncio
    async def test_record_transaction(self, tracker):
        """Test recording a whale transaction."""
        from core.analysis.whale_tracker import TransactionType

        tx = await tracker.record_transaction(
            signature="sig123",
            from_wallet="wallet1",
            to_wallet="wallet2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert tx.signature == "sig123"
        assert len(tracker._transactions) == 1

    @pytest.mark.asyncio
    async def test_record_below_threshold_ignored(self, tracker):
        """Test that transactions below threshold are ignored."""
        from core.analysis.whale_tracker import TransactionType

        tx = await tracker.record_transaction(
            signature="sig123",
            from_wallet="wallet1",
            to_wallet="wallet2",
            token_mint="SOL",
            amount=10.0,
            usd_value=5000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert tx is None
        assert len(tracker._transactions) == 0

    @pytest.mark.asyncio
    async def test_get_recent_transactions(self, tracker):
        """Test getting recent transactions."""
        from core.analysis.whale_tracker import TransactionType

        # Record several transactions
        for i in range(5):
            await tracker.record_transaction(
                signature=f"sig{i}",
                from_wallet=f"wallet{i}",
                to_wallet="wallet_dest",
                token_mint="SOL",
                amount=100.0,
                usd_value=15000.0 + (i * 1000),
                transaction_type=TransactionType.TRANSFER,
            )

        recent = tracker.get_recent_transactions(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_get_transactions_by_wallet(self, tracker):
        """Test filtering transactions by wallet address."""
        from core.analysis.whale_tracker import TransactionType

        # Record transactions from different wallets
        await tracker.record_transaction(
            signature="sig1",
            from_wallet="wallet_a",
            to_wallet="wallet_b",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )
        await tracker.record_transaction(
            signature="sig2",
            from_wallet="wallet_b",
            to_wallet="wallet_c",
            token_mint="SOL",
            amount=200.0,
            usd_value=25000.0,
            transaction_type=TransactionType.TRANSFER,
        )
        await tracker.record_transaction(
            signature="sig3",
            from_wallet="wallet_a",
            to_wallet="wallet_d",
            token_mint="SOL",
            amount=300.0,
            usd_value=35000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        wallet_a_txs = tracker.get_transactions_by_wallet("wallet_a")
        assert len(wallet_a_txs) == 2  # Two transactions from wallet_a

        wallet_b_txs = tracker.get_transactions_by_wallet("wallet_b")
        assert len(wallet_b_txs) == 2  # One from, one to wallet_b


class TestMovementPatternAnalysis:
    """Test movement pattern detection and analysis."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance with test data."""
        from core.analysis.whale_tracker import WhaleTracker, WhaleTier

        tracker = WhaleTracker(min_transaction_usd=10000.0)
        tracker.register_wallet("whale1", "Test Whale", WhaleTier.LARGE)
        return tracker

    @pytest.mark.asyncio
    async def test_detect_accumulation_pattern(self, tracker):
        """Test detecting accumulation pattern (more inflows than outflows)."""
        from core.analysis.whale_tracker import TransactionType, MovementPattern

        # Simulate accumulation: whale receiving more than sending
        for i in range(5):
            await tracker.record_transaction(
                signature=f"in_{i}",
                from_wallet="other_wallet",
                to_wallet="whale1",
                token_mint="SOL",
                amount=100.0,
                usd_value=20000.0,  # 5 * 20k = 100k inflow
                transaction_type=TransactionType.TRANSFER,
            )

        # Small outflow
        await tracker.record_transaction(
            signature="out_1",
            from_wallet="whale1",
            to_wallet="other_wallet",
            token_mint="SOL",
            amount=50.0,
            usd_value=10000.0,  # 10k outflow
            transaction_type=TransactionType.TRANSFER,
        )

        analysis = await tracker.analyze_movement_pattern(
            wallet_address="whale1",
            hours=24,
        )

        assert analysis.pattern == MovementPattern.ACCUMULATION
        assert analysis.net_flow_usd > 0
        assert analysis.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_detect_distribution_pattern(self, tracker):
        """Test detecting distribution pattern (more outflows than inflows)."""
        from core.analysis.whale_tracker import TransactionType, MovementPattern

        # Simulate distribution: whale sending more than receiving
        for i in range(5):
            await tracker.record_transaction(
                signature=f"out_{i}",
                from_wallet="whale1",
                to_wallet="other_wallet",
                token_mint="SOL",
                amount=100.0,
                usd_value=20000.0,  # 5 * 20k = 100k outflow
                transaction_type=TransactionType.TRANSFER,
            )

        # Small inflow
        await tracker.record_transaction(
            signature="in_1",
            from_wallet="other_wallet",
            to_wallet="whale1",
            token_mint="SOL",
            amount=50.0,
            usd_value=10000.0,  # 10k inflow
            transaction_type=TransactionType.TRANSFER,
        )

        analysis = await tracker.analyze_movement_pattern(
            wallet_address="whale1",
            hours=24,
        )

        assert analysis.pattern == MovementPattern.DISTRIBUTION
        assert analysis.net_flow_usd < 0
        assert analysis.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_detect_rotation_pattern(self, tracker):
        """Test detecting rotation pattern (similar in/out, different tokens)."""
        from core.analysis.whale_tracker import TransactionType, MovementPattern

        # Simulate rotation: selling one token, buying another
        await tracker.record_transaction(
            signature="out_sol",
            from_wallet="whale1",
            to_wallet="dex",
            token_mint="SOL",
            amount=1000.0,
            usd_value=100000.0,
            transaction_type=TransactionType.SWAP,
        )

        await tracker.record_transaction(
            signature="in_eth",
            from_wallet="dex",
            to_wallet="whale1",
            token_mint="ETH",
            amount=50.0,
            usd_value=95000.0,
            transaction_type=TransactionType.SWAP,
        )

        analysis = await tracker.analyze_movement_pattern(
            wallet_address="whale1",
            hours=24,
        )

        # With balanced in/out and swaps, this should be detected as rotation
        assert analysis.pattern == MovementPattern.ROTATION

    @pytest.mark.asyncio
    async def test_detect_neutral_pattern(self, tracker):
        """Test detecting neutral pattern (no significant activity)."""
        from core.analysis.whale_tracker import MovementPattern

        # No transactions
        analysis = await tracker.analyze_movement_pattern(
            wallet_address="whale1",
            hours=24,
        )

        assert analysis.pattern == MovementPattern.NEUTRAL
        assert analysis.transaction_count == 0


class TestAlertGeneration:
    """Test alert generation for significant whale movements."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker, WhaleTier

        tracker = WhaleTracker(
            min_transaction_usd=10000.0,
            alert_threshold_usd=50000.0,
        )
        tracker.register_wallet("mega_whale", "Mega Whale", WhaleTier.MEGA)
        return tracker

    @pytest.mark.asyncio
    async def test_alert_on_large_transfer(self, tracker):
        """Test alert generation for large transfers."""
        from core.analysis.whale_tracker import TransactionType, AlertSeverity

        alerts = []
        tracker.on_alert(lambda alert: alerts.append(alert))

        await tracker.record_transaction(
            signature="big_tx",
            from_wallet="mega_whale",
            to_wallet="unknown_wallet",
            token_mint="SOL",
            amount=5000.0,
            usd_value=500000.0,  # $500k - well above alert threshold
            transaction_type=TransactionType.TRANSFER,
        )

        assert len(alerts) == 1
        assert alerts[0].severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        assert alerts[0].usd_value == 500000.0

    @pytest.mark.asyncio
    async def test_alert_severity_scaling(self, tracker):
        """Test that alert severity scales with transaction size."""
        from core.analysis.whale_tracker import TransactionType, AlertSeverity

        alerts = []
        tracker.on_alert(lambda alert: alerts.append(alert))

        # Medium-sized whale transaction
        await tracker.record_transaction(
            signature="medium_tx",
            from_wallet="mega_whale",
            to_wallet="unknown",
            token_mint="SOL",
            amount=500.0,
            usd_value=75000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        # Very large whale transaction
        await tracker.record_transaction(
            signature="huge_tx",
            from_wallet="mega_whale",
            to_wallet="unknown",
            token_mint="SOL",
            amount=10000.0,
            usd_value=1000000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert len(alerts) == 2
        # Second alert should be higher severity
        assert alerts[1].severity.value >= alerts[0].severity.value

    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self, tracker):
        """Test no alert for transactions below alert threshold."""
        from core.analysis.whale_tracker import TransactionType

        alerts = []
        tracker.on_alert(lambda alert: alerts.append(alert))

        await tracker.record_transaction(
            signature="small_tx",
            from_wallet="mega_whale",
            to_wallet="unknown",
            token_mint="SOL",
            amount=50.0,
            usd_value=25000.0,  # Below 50k alert threshold
            transaction_type=TransactionType.TRANSFER,
        )

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_alert_includes_wallet_label(self, tracker):
        """Test that alerts include known wallet labels."""
        from core.analysis.whale_tracker import TransactionType

        alerts = []
        tracker.on_alert(lambda alert: alerts.append(alert))

        await tracker.record_transaction(
            signature="labeled_tx",
            from_wallet="mega_whale",
            to_wallet="unknown",
            token_mint="SOL",
            amount=1000.0,
            usd_value=100000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert len(alerts) == 1
        assert "Mega Whale" in alerts[0].message or alerts[0].wallet_label == "Mega Whale"

    @pytest.mark.asyncio
    async def test_get_recent_alerts(self, tracker):
        """Test retrieving recent alerts."""
        from core.analysis.whale_tracker import TransactionType

        tracker.on_alert(lambda alert: None)  # Register handler

        for i in range(5):
            await tracker.record_transaction(
                signature=f"tx_{i}",
                from_wallet="mega_whale",
                to_wallet="unknown",
                token_mint="SOL",
                amount=1000.0,
                usd_value=100000.0,
                transaction_type=TransactionType.TRANSFER,
            )

        recent_alerts = tracker.get_recent_alerts(limit=3)
        assert len(recent_alerts) == 3


class TestTokenSpecificTracking:
    """Test token-specific whale tracking."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker

        return WhaleTracker(min_transaction_usd=10000.0)

    @pytest.mark.asyncio
    async def test_track_specific_token(self, tracker):
        """Test tracking transactions for a specific token."""
        from core.analysis.whale_tracker import TransactionType

        # Record transactions for different tokens
        await tracker.record_transaction(
            signature="sol_tx",
            from_wallet="w1",
            to_wallet="w2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )
        await tracker.record_transaction(
            signature="eth_tx",
            from_wallet="w1",
            to_wallet="w2",
            token_mint="ETH",
            amount=10.0,
            usd_value=20000.0,
            transaction_type=TransactionType.TRANSFER,
        )
        await tracker.record_transaction(
            signature="sol_tx2",
            from_wallet="w3",
            to_wallet="w4",
            token_mint="SOL",
            amount=200.0,
            usd_value=30000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        sol_txs = tracker.get_transactions_by_token("SOL")
        assert len(sol_txs) == 2

        eth_txs = tracker.get_transactions_by_token("ETH")
        assert len(eth_txs) == 1

    @pytest.mark.asyncio
    async def test_get_token_flow_summary(self, tracker):
        """Test getting token flow summary."""
        from core.analysis.whale_tracker import TransactionType

        await tracker.record_transaction(
            signature="tx1",
            from_wallet="w1",
            to_wallet="w2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )
        await tracker.record_transaction(
            signature="tx2",
            from_wallet="w2",
            to_wallet="w3",
            token_mint="SOL",
            amount=50.0,
            usd_value=7500.0,
            transaction_type=TransactionType.TRANSFER,
        )

        summary = tracker.get_token_flow_summary("SOL", hours=24)

        assert summary["token_mint"] == "SOL"
        assert summary["total_volume_usd"] > 0
        assert summary["transaction_count"] == 2


class TestStatisticsAndMetrics:
    """Test statistical analysis and metrics."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker with test data."""
        from core.analysis.whale_tracker import WhaleTracker, WhaleTier

        tracker = WhaleTracker(min_transaction_usd=10000.0)
        tracker.register_wallet("w1", "Whale 1", WhaleTier.MEGA)
        tracker.register_wallet("w2", "Whale 2", WhaleTier.LARGE)
        return tracker

    @pytest.mark.asyncio
    async def test_get_whale_activity_stats(self, tracker):
        """Test getting overall whale activity statistics."""
        from core.analysis.whale_tracker import TransactionType

        for i in range(10):
            await tracker.record_transaction(
                signature=f"tx_{i}",
                from_wallet="w1",
                to_wallet="w2",
                token_mint="SOL",
                amount=100.0 + i * 10,
                usd_value=15000.0 + i * 1000,
                transaction_type=TransactionType.TRANSFER,
            )

        stats = tracker.get_activity_stats(hours=24)

        assert stats["total_transactions"] == 10
        assert stats["total_volume_usd"] > 0
        assert stats["unique_wallets"] >= 2
        assert "average_transaction_usd" in stats

    @pytest.mark.asyncio
    async def test_get_top_movers(self, tracker):
        """Test getting wallets with most activity."""
        from core.analysis.whale_tracker import TransactionType

        # w1 makes more transactions
        for i in range(5):
            await tracker.record_transaction(
                signature=f"tx_w1_{i}",
                from_wallet="w1",
                to_wallet="w2",
                token_mint="SOL",
                amount=100.0,
                usd_value=15000.0,
                transaction_type=TransactionType.TRANSFER,
            )

        # w2 makes fewer
        await tracker.record_transaction(
            signature="tx_w2_1",
            from_wallet="w2",
            to_wallet="w1",
            token_mint="SOL",
            amount=50.0,
            usd_value=10000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        top_movers = tracker.get_top_movers(limit=5, hours=24)

        assert len(top_movers) >= 1
        assert top_movers[0]["wallet_address"] == "w1"


class TestPersistence:
    """Test data persistence capabilities."""

    @pytest.fixture
    def temp_tracker(self, tmp_path):
        """Create a tracker with temporary storage."""
        from core.analysis.whale_tracker import WhaleTracker

        storage_path = tmp_path / "whale_data.json"
        return WhaleTracker(
            min_transaction_usd=10000.0,
            storage_path=storage_path,
        )

    @pytest.mark.asyncio
    async def test_save_and_load_wallets(self, temp_tracker, tmp_path):
        """Test saving and loading wallet data."""
        from core.analysis.whale_tracker import WhaleTracker, WhaleTier

        # Add some wallets
        temp_tracker.register_wallet("w1", "Whale 1", WhaleTier.MEGA)
        temp_tracker.register_wallet("w2", "Whale 2", WhaleTier.LARGE)

        # Save
        await temp_tracker.save()

        # Create new tracker and load
        storage_path = tmp_path / "whale_data.json"
        new_tracker = WhaleTracker(storage_path=storage_path)
        await new_tracker.load()

        assert new_tracker.get_wallet("w1") is not None
        assert new_tracker.get_wallet("w1").label == "Whale 1"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def tracker(self):
        """Create a WhaleTracker instance."""
        from core.analysis.whale_tracker import WhaleTracker

        return WhaleTracker()

    @pytest.mark.asyncio
    async def test_duplicate_transaction_handling(self, tracker):
        """Test that duplicate transactions are handled."""
        from core.analysis.whale_tracker import TransactionType

        await tracker.record_transaction(
            signature="dup_sig",
            from_wallet="w1",
            to_wallet="w2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        # Try to record same transaction again
        result = await tracker.record_transaction(
            signature="dup_sig",
            from_wallet="w1",
            to_wallet="w2",
            token_mint="SOL",
            amount=100.0,
            usd_value=15000.0,
            transaction_type=TransactionType.TRANSFER,
        )

        assert result is None  # Should be ignored
        assert len(tracker._transactions) == 1

    def test_invalid_wallet_address(self, tracker):
        """Test handling of invalid wallet addresses."""
        from core.analysis.whale_tracker import WhaleTier

        # Empty address should be rejected
        with pytest.raises(ValueError):
            tracker.register_wallet("", "Invalid", WhaleTier.LARGE)

    def test_negative_usd_value_rejected(self, tracker):
        """Test that negative USD values are rejected."""
        assert tracker.is_whale_transaction(-10000.0) is False

    @pytest.mark.asyncio
    async def test_empty_analysis_period(self, tracker):
        """Test analysis with no transactions in period."""
        from core.analysis.whale_tracker import MovementPattern

        analysis = await tracker.analyze_movement_pattern(
            wallet_address="unknown",
            hours=24,
        )

        assert analysis.pattern == MovementPattern.NEUTRAL
        assert analysis.transaction_count == 0
        assert analysis.confidence == 0.0
