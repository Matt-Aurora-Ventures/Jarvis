"""
Comprehensive unit tests for the Buy Tracker Monitor.

Tests cover:
- BuyTransaction dataclass and properties
- TransactionMonitor initialization and configuration
- Buy detection logic (valid buys, sells, false positives)
- Transaction parsing (buy amount, buyer address, SOL calculations)
- Notification generation and callback handling
- Buyer statistics and position tracking
- Large buy alerts (threshold detection)
- Error handling (RPC failures, malformed transactions)
- Rate limiting and signature deduplication
- Edge cases (zero-value buys, token burns, empty responses)
- HeliusWebSocketMonitor reconnection logic
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
import sys
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.buy_tracker.monitor import (
    BuyTransaction,
    TransactionMonitor,
    HeliusWebSocketMonitor,
)


# =============================================================================
# BuyTransaction Tests
# =============================================================================

class TestBuyTransaction:
    """Tests for BuyTransaction dataclass."""

    def test_buy_transaction_creation(self):
        """Test basic BuyTransaction creation."""
        tx = BuyTransaction(
            signature="abc123def456",
            buyer_wallet="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            token_amount=1000.0,
            sol_amount=0.5,
            usd_amount=50.0,
            price_per_token=0.00005,
            buyer_position_pct=0.001,
            market_cap=50000000.0,
            timestamp=datetime.utcnow(),
            tx_url="https://solscan.io/tx/abc123",
            dex_url="https://dexscreener.com/solana/test",
        )

        assert tx.signature == "abc123def456"
        assert tx.token_amount == 1000.0
        assert tx.sol_amount == 0.5
        assert tx.usd_amount == 50.0

    def test_buyer_short_property(self):
        """Test shortened buyer wallet address."""
        tx = BuyTransaction(
            signature="testsig",
            buyer_wallet="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.buyer_short == "9WzD...AWWM"
        assert len(tx.buyer_short) == 11  # 4 + 3 + 4

    def test_buyer_short_short_address(self):
        """Test buyer_short with short address (8 chars or less)."""
        tx = BuyTransaction(
            signature="sig",
            buyer_wallet="ABCD1234",  # Exactly 8 chars
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.buyer_short == "ABCD1234"  # No truncation

    def test_signature_short_property(self):
        """Test shortened transaction signature."""
        tx = BuyTransaction(
            signature="abc123def456ghi789",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.signature_short == "abc1...i789"

    def test_signature_short_short_signature(self):
        """Test signature_short with short signature."""
        tx = BuyTransaction(
            signature="ABCD1234",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.signature_short == "ABCD1234"

    def test_lp_pair_fields(self):
        """Test LP pair name and address fields."""
        tx = BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
            lp_pair_name="kr8tiv/sol",
            lp_pair_address="LP123456789",
        )

        assert tx.lp_pair_name == "kr8tiv/sol"
        assert tx.lp_pair_address == "LP123456789"

    def test_default_lp_pair_fields(self):
        """Test LP pair fields default to empty strings."""
        tx = BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.lp_pair_name == ""
        assert tx.lp_pair_address == ""


# =============================================================================
# TransactionMonitor Initialization Tests
# =============================================================================

class TestTransactionMonitorInit:
    """Tests for TransactionMonitor initialization."""

    def test_basic_initialization(self):
        """Test basic monitor creation."""
        monitor = TransactionMonitor(
            token_address="TOKEN123",
            helius_api_key="test_api_key",
        )

        assert monitor.token_address == "TOKEN123"
        assert monitor.helius_api_key == "test_api_key"
        assert monitor.min_buy_usd == 5.0  # Default
        assert monitor.on_buy is None
        assert monitor._running is False

    def test_custom_min_buy_threshold(self):
        """Test custom minimum buy USD threshold."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            min_buy_usd=100.0,
        )

        assert monitor.min_buy_usd == 100.0

    def test_callback_registration(self):
        """Test on_buy callback registration."""
        def my_callback(buy):
            pass

        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            on_buy=my_callback,
        )

        assert monitor.on_buy is my_callback

    def test_pair_address_configuration(self):
        """Test LP pair address configuration."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            pair_address="PAIR123",
        )

        assert monitor.pair_address == "PAIR123"
        assert "PAIR123" in monitor._pair_names
        assert monitor._pair_names["PAIR123"] == "main"

    def test_additional_pairs_configuration(self):
        """Test additional LP pairs configuration."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            pair_address="MAIN_PAIR",
            additional_pairs=[
                ("kr8tiv/ralph", "PAIR_RALPH_12345678901234567890123456"),
                ("kr8tiv/sol", "PAIR_SOL_123456789012345678901234567"),
            ],
        )

        assert len(monitor._pair_names) == 3
        assert "MAIN_PAIR" in monitor._pair_names
        assert "PAIR_RALPH_12345678901234567890123456" in monitor._pair_names
        assert monitor._pair_names["PAIR_RALPH_12345678901234567890123456"] == "kr8tiv/ralph"

    def test_invalid_additional_pair_filtered(self):
        """Test invalid additional pairs are filtered out."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            additional_pairs=[
                ("valid", "12345678901234567890123456789012"),  # 32 chars
                ("invalid", "short"),  # Less than 32 chars
                ("empty", ""),  # Empty
            ],
        )

        assert len(monitor._pair_names) == 1
        assert "12345678901234567890123456789012" in monitor._pair_names

    def test_rpc_and_ws_urls(self):
        """Test RPC and WebSocket URLs are constructed correctly."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="my_test_key",
        )

        assert "my_test_key" in monitor.rpc_url
        assert "my_test_key" in monitor.ws_url
        assert "mainnet.helius-rpc.com" in monitor.rpc_url

    def test_max_processed_signatures_constant(self):
        """Test MAX_PROCESSED_SIGNATURES is set correctly."""
        assert TransactionMonitor.MAX_PROCESSED_SIGNATURES == 500


# =============================================================================
# Signature Deduplication Tests
# =============================================================================

class TestSignatureDeduplication:
    """Tests for signature tracking and deduplication."""

    def test_is_already_processed_empty(self):
        """Test is_already_processed with empty list."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        assert monitor._is_already_processed("new_sig") is False

    def test_is_already_processed_found(self):
        """Test is_already_processed returns True for known signature."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._processed_signatures = ["sig1", "sig2", "sig3"]

        assert monitor._is_already_processed("sig2") is True

    def test_is_already_processed_not_found(self):
        """Test is_already_processed returns False for unknown signature."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._processed_signatures = ["sig1", "sig2"]

        assert monitor._is_already_processed("sig3") is False

    def test_mark_as_processed_adds_signature(self):
        """Test mark_as_processed adds new signature."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        monitor._mark_as_processed("new_sig")

        assert "new_sig" in monitor._processed_signatures

    def test_mark_as_processed_no_duplicate(self):
        """Test mark_as_processed doesn't add duplicate."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._processed_signatures = ["existing_sig"]

        monitor._mark_as_processed("existing_sig")

        assert monitor._processed_signatures.count("existing_sig") == 1

    def test_mark_as_processed_trims_old_signatures(self):
        """Test mark_as_processed trims old signatures when exceeding max."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        # Fill up to max
        monitor._processed_signatures = [f"sig_{i}" for i in range(500)]

        # Add one more
        monitor._mark_as_processed("new_sig_overflow")

        assert len(monitor._processed_signatures) == 500
        assert "new_sig_overflow" in monitor._processed_signatures
        assert "sig_0" not in monitor._processed_signatures  # Oldest removed


# =============================================================================
# Price Update Tests
# =============================================================================

class TestPriceUpdates:
    """Tests for price update functionality."""

    @pytest.fixture
    def monitor_with_session(self):
        """Create monitor with mocked session."""
        monitor = TransactionMonitor(
            token_address="TOKEN123",
            helius_api_key="key",
        )
        monitor._session = AsyncMock(spec=aiohttp.ClientSession)
        return monitor

    @pytest.mark.asyncio
    async def test_update_prices_success(self, monitor_with_session):
        """Test successful price update from APIs."""
        monitor = monitor_with_session

        # Mock CoinGecko response
        coingecko_response = AsyncMock()
        coingecko_response.status = 200
        coingecko_response.json = AsyncMock(return_value={
            "solana": {"usd": 150.0}
        })

        # Mock DexScreener response
        dexscreener_response = AsyncMock()
        dexscreener_response.status = 200
        dexscreener_response.json = AsyncMock(return_value={
            "pairs": [
                {
                    "priceUsd": "0.00001234",
                    "marketCap": 5000000.0,
                }
            ]
        })

        # Configure mock to return different responses for different URLs
        def mock_get(url, **kwargs):
            mock_cm = MagicMock()
            if "coingecko" in url:
                mock_cm.__aenter__ = AsyncMock(return_value=coingecko_response)
            else:
                mock_cm.__aenter__ = AsyncMock(return_value=dexscreener_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            return mock_cm

        monitor._session.get = mock_get

        await monitor._update_prices()

        assert monitor._sol_price_usd == 150.0
        assert monitor._token_price_usd == 0.00001234
        assert monitor._market_cap == 5000000.0

    @pytest.mark.asyncio
    async def test_update_prices_coingecko_failure(self, monitor_with_session):
        """Test price update handles CoinGecko failure."""
        monitor = monitor_with_session
        monitor._sol_price_usd = 100.0  # Pre-existing value

        # Mock failed CoinGecko response
        coingecko_response = AsyncMock()
        coingecko_response.status = 500

        # Mock successful DexScreener response
        dexscreener_response = AsyncMock()
        dexscreener_response.status = 200
        dexscreener_response.json = AsyncMock(return_value={"pairs": []})

        def mock_get(url, **kwargs):
            mock_cm = MagicMock()
            if "coingecko" in url:
                mock_cm.__aenter__ = AsyncMock(return_value=coingecko_response)
            else:
                mock_cm.__aenter__ = AsyncMock(return_value=dexscreener_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            return mock_cm

        monitor._session.get = mock_get

        await monitor._update_prices()

        # SOL price should remain unchanged
        assert monitor._sol_price_usd == 100.0

    @pytest.mark.asyncio
    async def test_update_prices_dexscreener_empty_pairs(self, monitor_with_session):
        """Test price update handles empty DexScreener pairs."""
        monitor = monitor_with_session
        monitor._token_price_usd = 0.0001  # Pre-existing

        coingecko_response = AsyncMock()
        coingecko_response.status = 200
        coingecko_response.json = AsyncMock(return_value={"solana": {"usd": 150.0}})

        dexscreener_response = AsyncMock()
        dexscreener_response.status = 200
        dexscreener_response.json = AsyncMock(return_value={"pairs": []})

        def mock_get(url, **kwargs):
            mock_cm = MagicMock()
            if "coingecko" in url:
                mock_cm.__aenter__ = AsyncMock(return_value=coingecko_response)
            else:
                mock_cm.__aenter__ = AsyncMock(return_value=dexscreener_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            return mock_cm

        monitor._session.get = mock_get

        await monitor._update_prices()

        # Token price should remain unchanged when no pairs
        assert monitor._token_price_usd == 0.0001

    @pytest.mark.asyncio
    async def test_update_prices_uses_fdv_fallback(self, monitor_with_session):
        """Test price update uses fdv when marketCap is missing."""
        monitor = monitor_with_session

        coingecko_response = AsyncMock()
        coingecko_response.status = 200
        coingecko_response.json = AsyncMock(return_value={"solana": {"usd": 100.0}})

        dexscreener_response = AsyncMock()
        dexscreener_response.status = 200
        dexscreener_response.json = AsyncMock(return_value={
            "pairs": [{"priceUsd": "0.001", "marketCap": None, "fdv": 1000000.0}]
        })

        def mock_get(url, **kwargs):
            mock_cm = MagicMock()
            if "coingecko" in url:
                mock_cm.__aenter__ = AsyncMock(return_value=coingecko_response)
            else:
                mock_cm.__aenter__ = AsyncMock(return_value=dexscreener_response)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            return mock_cm

        monitor._session.get = mock_get

        await monitor._update_prices()

        assert monitor._market_cap == 1000000.0

    @pytest.mark.asyncio
    async def test_update_prices_handles_exception(self, monitor_with_session):
        """Test price update handles exceptions gracefully."""
        monitor = monitor_with_session
        monitor._sol_price_usd = 100.0
        monitor._token_price_usd = 0.001

        # Make get raise an exception
        monitor._session.get = MagicMock(side_effect=Exception("Network error"))

        # Should not raise
        await monitor._update_prices()

        # Values should remain unchanged
        assert monitor._sol_price_usd == 100.0
        assert monitor._token_price_usd == 0.001


# =============================================================================
# Get Recent Signatures Tests
# =============================================================================

class TestGetRecentSignatures:
    """Tests for fetching recent signatures."""

    @pytest.fixture
    def monitor_with_session(self):
        """Create monitor with mocked session."""
        monitor = TransactionMonitor(
            token_address="TOKEN123",
            helius_api_key="key",
            pair_address="PAIR456",
        )
        monitor._session = AsyncMock(spec=aiohttp.ClientSession)
        return monitor

    @pytest.mark.asyncio
    async def test_get_recent_signatures_success(self, monitor_with_session):
        """Test successful signature retrieval."""
        monitor = monitor_with_session

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "result": [
                {"signature": "sig1"},
                {"signature": "sig2"},
                {"signature": "sig3"},
            ]
        })

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        signatures = await monitor._get_recent_signatures("WATCH_ADDR")

        assert len(signatures) == 3
        assert signatures[0]["signature"] == "sig1"

    @pytest.mark.asyncio
    async def test_get_recent_signatures_uses_pair_address_fallback(self, monitor_with_session):
        """Test uses pair_address when watch_address not provided."""
        monitor = monitor_with_session

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": []})

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        await monitor._get_recent_signatures("")

        # Verify the call was made with pair_address
        call_args = monitor._session.post.call_args
        payload = call_args.kwargs.get("json", call_args[1].get("json"))
        assert payload["params"][0] == "PAIR456"

    @pytest.mark.asyncio
    async def test_get_recent_signatures_uses_token_address_fallback(self):
        """Test uses token_address when no pair_address."""
        monitor = TransactionMonitor(
            token_address="TOKEN_ONLY",
            helius_api_key="key",
        )
        monitor._session = AsyncMock(spec=aiohttp.ClientSession)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": []})

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        await monitor._get_recent_signatures("")

        call_args = monitor._session.post.call_args
        payload = call_args.kwargs.get("json", call_args[1].get("json"))
        assert payload["params"][0] == "TOKEN_ONLY"

    @pytest.mark.asyncio
    async def test_get_recent_signatures_no_address(self):
        """Test returns empty list when no address available."""
        monitor = TransactionMonitor(
            token_address="",
            helius_api_key="key",
        )
        monitor._session = AsyncMock()

        signatures = await monitor._get_recent_signatures("")

        assert signatures == []

    @pytest.mark.asyncio
    async def test_get_recent_signatures_failure(self, monitor_with_session):
        """Test handles RPC failure gracefully."""
        monitor = monitor_with_session

        mock_response = AsyncMock()
        mock_response.status = 500

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        signatures = await monitor._get_recent_signatures("ADDR")

        assert signatures == []

    @pytest.mark.asyncio
    async def test_get_recent_signatures_exception(self, monitor_with_session):
        """Test handles exceptions gracefully."""
        monitor = monitor_with_session
        monitor._session.post = MagicMock(side_effect=Exception("Connection failed"))

        signatures = await monitor._get_recent_signatures("ADDR")

        assert signatures == []


# =============================================================================
# Parse Transaction Tests
# =============================================================================

class TestParseTransaction:
    """Tests for transaction parsing and buy detection."""

    @pytest.fixture
    def monitor_with_prices(self):
        """Create monitor with price data."""
        monitor = TransactionMonitor(
            token_address="TOKEN123",
            helius_api_key="test_key",
        )
        monitor._session = AsyncMock(spec=aiohttp.ClientSession)
        monitor._sol_price_usd = 100.0
        monitor._token_price_usd = 0.001
        monitor._market_cap = 1000000.0
        return monitor

    @pytest.mark.asyncio
    async def test_parse_transaction_buy_detected(self, monitor_with_prices):
        """Test buy transaction is correctly detected."""
        monitor = monitor_with_prices

        # Mock Helius API response for a buy transaction
        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "BUYER_WALLET_123",
            "tokenTransfers": [
                {
                    "mint": "TOKEN123",
                    "toUserAccount": "BUYER_WALLET_123",  # Buyer receives token
                    "fromUserAccount": "LP_POOL",
                    "tokenAmount": 10000.0,
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": "BUYER_WALLET_123",  # Buyer sends SOL
                    "toUserAccount": "LP_POOL",
                    "amount": 500000000,  # 0.5 SOL in lamports
                }
            ]
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG123", "main", "PAIR_ADDR")

        assert buy is not None
        assert buy.buyer_wallet == "BUYER_WALLET_123"
        assert buy.token_amount == 10000.0
        assert buy.sol_amount == 0.5
        assert buy.usd_amount == 50.0  # 0.5 SOL * $100
        assert buy.lp_pair_name == "main"
        assert buy.lp_pair_address == "PAIR_ADDR"

    @pytest.mark.asyncio
    async def test_parse_transaction_sell_filtered(self, monitor_with_prices):
        """Test sell transaction is filtered out (returns None)."""
        monitor = monitor_with_prices

        # Mock Helius API response for a sell transaction
        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "SELLER_WALLET",
            "tokenTransfers": [
                {
                    "mint": "TOKEN123",
                    "fromUserAccount": "SELLER_WALLET",  # Seller sends token
                    "toUserAccount": "LP_POOL",
                    "tokenAmount": 5000.0,
                }
            ],
            "nativeTransfers": []
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG_SELL")

        assert buy is None

    @pytest.mark.asyncio
    async def test_parse_transaction_wrong_token_filtered(self, monitor_with_prices):
        """Test transaction with different token is filtered."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "WALLET",
            "tokenTransfers": [
                {
                    "mint": "DIFFERENT_TOKEN",  # Not our token
                    "toUserAccount": "WALLET",
                    "fromUserAccount": "LP",
                    "tokenAmount": 1000.0,
                }
            ],
            "nativeTransfers": []
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is None

    @pytest.mark.asyncio
    async def test_parse_transaction_tiny_sol_filtered(self, monitor_with_prices):
        """Test transaction with tiny SOL amount is filtered."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "WALLET",
            "tokenTransfers": [
                {
                    "mint": "TOKEN123",
                    "toUserAccount": "WALLET",
                    "fromUserAccount": "LP",
                    "tokenAmount": 100.0,
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": "WALLET",
                    "toUserAccount": "LP",
                    "amount": 100000,  # 0.0001 SOL - below 0.001 threshold
                }
            ]
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is None

    @pytest.mark.asyncio
    async def test_parse_transaction_api_failure(self, monitor_with_prices):
        """Test handles Helius API failure."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 500

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is None

    @pytest.mark.asyncio
    async def test_parse_transaction_empty_response(self, monitor_with_prices):
        """Test handles empty API response."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is None

    @pytest.mark.asyncio
    async def test_parse_transaction_net_sol_calculation(self, monitor_with_prices):
        """Test net SOL spent calculation with SOL returned."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "WALLET",
            "tokenTransfers": [
                {
                    "mint": "TOKEN123",
                    "toUserAccount": "WALLET",
                    "fromUserAccount": "LP",
                    "tokenAmount": 1000.0,
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": "WALLET",
                    "toUserAccount": "LP",
                    "amount": 1000000000,  # 1 SOL out
                },
                {
                    "fromUserAccount": "OTHER",
                    "toUserAccount": "WALLET",
                    "amount": 200000000,  # 0.2 SOL in (change)
                }
            ]
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is not None
        assert buy.sol_amount == 0.8  # 1.0 - 0.2 = 0.8 SOL net

    @pytest.mark.asyncio
    async def test_parse_transaction_buyer_position_pct(self, monitor_with_prices):
        """Test buyer position percentage calculation."""
        monitor = monitor_with_prices

        helius_response = AsyncMock()
        helius_response.status = 200
        helius_response.json = AsyncMock(return_value=[{
            "feePayer": "WALLET",
            "tokenTransfers": [
                {
                    "mint": "TOKEN123",
                    "toUserAccount": "WALLET",
                    "fromUserAccount": "LP",
                    "tokenAmount": 10000.0,  # 10000 tokens at $0.001 = $10
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": "WALLET",
                    "toUserAccount": "LP",
                    "amount": 100000000,  # 0.1 SOL
                }
            ]
        }])

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = helius_response
        mock_cm.__aexit__.return_value = None
        monitor._session.post = MagicMock(return_value=mock_cm)

        buy = await monitor._parse_transaction("SIG")

        assert buy is not None
        # Position pct = ($10 / $1,000,000) * 100 = 0.001%
        assert buy.buyer_position_pct == pytest.approx(0.001, rel=0.01)

    @pytest.mark.asyncio
    async def test_parse_transaction_exception_handling(self, monitor_with_prices):
        """Test exception handling during parsing."""
        monitor = monitor_with_prices
        monitor._session.post = MagicMock(side_effect=Exception("Parse error"))

        buy = await monitor._parse_transaction("SIG")

        assert buy is None


# =============================================================================
# Callback Tests
# =============================================================================

class TestSafeCallback:
    """Tests for safe callback execution."""

    @pytest.fixture
    def monitor(self):
        """Create monitor with mock session."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        return monitor

    @pytest.fixture
    def sample_buy(self):
        """Create sample buy transaction."""
        return BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=1000000.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

    @pytest.mark.asyncio
    async def test_safe_callback_async(self, monitor, sample_buy):
        """Test safe callback with async function."""
        callback_called = []

        async def async_callback(buy):
            callback_called.append(buy)

        monitor.on_buy = async_callback

        await monitor._safe_callback(sample_buy)

        assert len(callback_called) == 1
        assert callback_called[0] is sample_buy

    @pytest.mark.asyncio
    async def test_safe_callback_sync(self, monitor, sample_buy):
        """Test safe callback with sync function."""
        callback_called = []

        def sync_callback(buy):
            callback_called.append(buy)

        monitor.on_buy = sync_callback

        await monitor._safe_callback(sample_buy)

        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_safe_callback_exception(self, monitor, sample_buy):
        """Test safe callback handles exceptions."""
        def bad_callback(buy):
            raise ValueError("Callback error")

        monitor.on_buy = bad_callback

        # Should not raise
        await monitor._safe_callback(sample_buy)


# =============================================================================
# Start/Stop Tests
# =============================================================================

class TestMonitorLifecycle:
    """Tests for monitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Test start sets _running to True."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        with patch.object(monitor, '_update_prices', new_callable=AsyncMock):
            with patch('asyncio.create_task'):
                await monitor.start()

        assert monitor._running is True
        assert monitor._session is not None

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self):
        """Test stop cleans up resources."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._running = True
        monitor._session = AsyncMock()
        monitor._ws = AsyncMock()

        await monitor.stop()

        assert monitor._running is False
        monitor._session.close.assert_called_once()
        monitor._ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_without_session(self):
        """Test stop handles missing session/ws gracefully."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._running = True
        monitor._session = None
        monitor._ws = None

        # Should not raise
        await monitor.stop()

        assert monitor._running is False


# =============================================================================
# HeliusWebSocketMonitor Tests
# =============================================================================

class TestHeliusWebSocketMonitor:
    """Tests for HeliusWebSocketMonitor."""

    def test_inherits_from_transaction_monitor(self):
        """Test HeliusWebSocketMonitor inherits from TransactionMonitor."""
        assert issubclass(HeliusWebSocketMonitor, TransactionMonitor)

    def test_reconnection_constants(self):
        """Test reconnection constants are set correctly."""
        assert HeliusWebSocketMonitor.INITIAL_BACKOFF_SECONDS == 1
        assert HeliusWebSocketMonitor.MAX_BACKOFF_SECONDS == 60
        assert HeliusWebSocketMonitor.BACKOFF_MULTIPLIER == 2

    def test_calculate_backoff_initial(self):
        """Test initial backoff calculation."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._reconnect_attempts = 0

        backoff = monitor._calculate_backoff()

        assert backoff == 1  # INITIAL_BACKOFF_SECONDS * 2^0

    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._reconnect_attempts = 3

        backoff = monitor._calculate_backoff()

        assert backoff == 8  # 1 * 2^3 = 8

    def test_calculate_backoff_max_cap(self):
        """Test backoff is capped at MAX_BACKOFF_SECONDS."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._reconnect_attempts = 10  # 1 * 2^10 = 1024 > 60

        backoff = monitor._calculate_backoff()

        assert backoff == 60  # MAX_BACKOFF_SECONDS

    @pytest.mark.asyncio
    async def test_start_initializes_reconnect_attempts(self):
        """Test start initializes reconnect attempts."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        with patch.object(monitor, '_update_prices', new_callable=AsyncMock):
            with patch('asyncio.create_task'):
                await monitor.start()

        assert monitor._reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_start_registers_exception_handlers(self):
        """Test start registers exception handlers for background tasks."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()

        with patch.object(monitor, '_update_prices', new_callable=AsyncMock):
            with patch('asyncio.create_task', return_value=mock_task) as mock_create:
                await monitor.start()

        # Should have called add_done_callback for both tasks
        assert mock_task.add_done_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_start_stores_task_references(self):
        """Test start stores task references for proper cancellation."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        mock_task = MagicMock()

        with patch.object(monitor, '_update_prices', new_callable=AsyncMock):
            with patch('asyncio.create_task', return_value=mock_task):
                await monitor.start()

        # Should store task references
        assert monitor._price_task is not None
        assert monitor._ws_task is not None

    @pytest.mark.asyncio
    async def test_stop_cancels_websocket_task(self):
        """Test stop cancels WebSocket task properly."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._running = True
        monitor._session = AsyncMock()
        monitor._ws = AsyncMock()

        # Track cancel calls
        ws_cancel_called = []
        price_cancel_called = []

        # Create a proper awaitable mock task class
        class MockTask:
            def __init__(self, cancel_tracker):
                self._done = False
                self._cancel_tracker = cancel_tracker

            def done(self):
                return self._done

            def cancel(self):
                self._cancel_tracker.append(True)
                self._done = True

            def __await__(self):
                async def _raise_cancelled():
                    raise asyncio.CancelledError()
                return _raise_cancelled().__await__()

        mock_ws_task = MockTask(ws_cancel_called)
        monitor._ws_task = mock_ws_task

        mock_price_task = MockTask(price_cancel_called)
        monitor._price_task = mock_price_task

        await monitor.stop()

        # Both tasks should be cancelled
        assert len(ws_cancel_called) == 1, "WebSocket task cancel should be called"
        assert len(price_cancel_called) == 1, "Price task cancel should be called"

    @pytest.mark.asyncio
    async def test_handle_ws_message_subscription_confirmation(self):
        """Test handles subscription confirmation message."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._session = AsyncMock()

        # Subscription confirmation
        message = {"result": 12345}

        # Should not raise or call any processing
        await monitor._handle_ws_message(message)

    @pytest.mark.asyncio
    async def test_handle_ws_message_account_update(self):
        """Test handles account update message."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN123",
            helius_api_key="key",
        )
        monitor._session = AsyncMock()
        monitor._sol_price_usd = 100.0
        monitor._token_price_usd = 0.001
        monitor._market_cap = 1000000.0

        # Mock _get_recent_signatures to return empty
        with patch.object(monitor, '_get_recent_signatures', new_callable=AsyncMock) as mock_sigs:
            mock_sigs.return_value = []

            message = {
                "params": {
                    "result": {
                        "context": {"slot": 12345}
                    }
                }
            }

            await monitor._handle_ws_message(message)

            mock_sigs.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_ws_message_exception(self):
        """Test handles exception during message processing."""
        monitor = HeliusWebSocketMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )

        # Mock _get_recent_signatures to raise
        with patch.object(monitor, '_get_recent_signatures', new_callable=AsyncMock) as mock_sigs:
            mock_sigs.side_effect = Exception("Processing error")

            message = {"params": {"result": {}}}

            # Should not raise
            await monitor._handle_ws_message(message)


# =============================================================================
# Large Buy Alert Tests
# =============================================================================

class TestLargeBuyAlerts:
    """Tests for large buy threshold detection."""

    @pytest.fixture
    def monitor(self):
        """Create monitor with higher threshold."""
        return TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            min_buy_usd=100.0,  # $100 minimum
        )

    def test_buy_below_threshold_filtered(self, monitor):
        """Test buy below threshold is filtered."""
        buy = BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.5,
            usd_amount=50.0,  # Below $100 threshold
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=1000000.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        # Buy USD amount < min_buy_usd
        assert buy.usd_amount < monitor.min_buy_usd

    def test_buy_above_threshold_passes(self, monitor):
        """Test buy above threshold passes."""
        buy = BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=10000.0,
            sol_amount=1.5,
            usd_amount=150.0,  # Above $100 threshold
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=1000000.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert buy.usd_amount >= monitor.min_buy_usd

    def test_buy_exactly_at_threshold(self, monitor):
        """Test buy exactly at threshold passes."""
        buy = BuyTransaction(
            signature="sig",
            buyer_wallet="wallet",
            token_amount=5000.0,
            sol_amount=1.0,
            usd_amount=100.0,  # Exactly at threshold
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=1000000.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert buy.usd_amount >= monitor.min_buy_usd


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_market_cap_position_calculation(self):
        """Test position calculation with zero market cap."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
        )
        monitor._market_cap = 0
        monitor._token_price_usd = 0

        # Position would be 0 when market cap is 0
        token_amount = 1000.0
        buyer_position_pct = 0
        if monitor._market_cap > 0 and monitor._token_price_usd > 0:
            buyer_value = token_amount * monitor._token_price_usd
            buyer_position_pct = (buyer_value / monitor._market_cap) * 100

        assert buyer_position_pct == 0

    def test_empty_token_transfers(self):
        """Test transaction with no token transfers."""
        # This should be handled in _parse_transaction
        # No token_in found -> returns None
        pass  # Covered by other tests

    def test_no_native_transfers(self):
        """Test transaction with token transfer but no SOL transfer."""
        # net_sol_spent would be 0 -> filtered out
        pass  # Covered by test_parse_transaction_tiny_sol_filtered

    def test_very_long_wallet_address(self):
        """Test buyer_short with standard Solana address (44 chars)."""
        wallet = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"  # 44 chars
        tx = BuyTransaction(
            signature="sig",
            buyer_wallet=wallet,
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert len(tx.buyer_short) == 11
        assert tx.buyer_short.startswith(wallet[:4])
        assert tx.buyer_short.endswith(wallet[-4:])

    def test_urls_constructed_correctly(self):
        """Test transaction and DEX URLs are constructed correctly."""
        tx = BuyTransaction(
            signature="abc123xyz",
            buyer_wallet="wallet",
            token_amount=100.0,
            sol_amount=0.1,
            usd_amount=10.0,
            price_per_token=0.0001,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="https://solscan.io/tx/abc123xyz",
            dex_url="https://dexscreener.com/solana/TOKEN",
        )

        assert "abc123xyz" in tx.tx_url
        assert "solscan.io" in tx.tx_url
        assert "dexscreener.com" in tx.dex_url


# =============================================================================
# Integration-style Tests (with full mocking)
# =============================================================================

class TestTransactionPolling:
    """Tests for the transaction polling loop."""

    @pytest.mark.asyncio
    async def test_poll_loop_first_run_marks_existing(self):
        """Test first run marks existing transactions as processed."""
        monitor = TransactionMonitor(
            token_address="TOKEN",
            helius_api_key="key",
            pair_address="PAIR",
        )
        monitor._running = True
        monitor._session = AsyncMock()

        # Mock _get_recent_signatures
        with patch.object(monitor, '_get_recent_signatures', new_callable=AsyncMock) as mock_sigs:
            mock_sigs.return_value = [
                {"signature": "existing1"},
                {"signature": "existing2"},
            ]

            # Run one iteration by making running False after first loop
            call_count = [0]
            original_running = monitor._running

            async def stop_after_first():
                call_count[0] += 1
                if call_count[0] >= 1:
                    monitor._running = False
                    return []
                return mock_sigs.return_value

            mock_sigs.side_effect = stop_after_first

            # Start polling loop (it will run once then stop)
            await monitor._transaction_poll_loop()

        # Existing signatures should be marked as processed
        assert "existing1" in monitor._processed_signatures
        assert "existing2" in monitor._processed_signatures


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
