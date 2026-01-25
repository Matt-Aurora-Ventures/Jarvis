"""
Tests for demo_trading module.

Tests Bags.fm/Jupiter swap execution, wallet management, TP/SL logic.
"""

import os
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from types import SimpleNamespace

from tg_bot.handlers.demo import demo_trading


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_bags_client():
    """Mock Bags.fm client."""
    client = AsyncMock()
    client.api_key = "test_api_key"
    client.partner_key = "test_partner_key"

    # Successful swap result
    swap_result = SimpleNamespace(
        success=True,
        tx_hash="bags_tx_abc123",
        to_amount=1000.0,
        error=None,
    )
    client.swap = AsyncMock(return_value=swap_result)
    return client


@pytest.fixture
def mock_jupiter_client():
    """Mock Jupiter client."""
    client = AsyncMock()

    # Token info
    token_info = SimpleNamespace(decimals=6)
    client.get_token_info = AsyncMock(return_value=token_info)

    # Quote result
    quote = {"quote_data": "test"}
    client.get_quote = AsyncMock(return_value=quote)

    # Successful swap result
    swap_result = SimpleNamespace(
        success=True,
        signature="jupiter_tx_xyz789",
        output_amount=1_000_000,  # 1.0 tokens (6 decimals)
        error=None,
    )
    client.execute_swap = AsyncMock(return_value=swap_result)

    return client


@pytest.fixture
def mock_wallet():
    """Mock SecureWallet."""
    wallet = MagicMock()
    wallet.set_active = MagicMock()
    return wallet


@pytest.fixture
def mock_sentiment_data():
    """Mock sentiment data for token."""
    return {
        "symbol": "TEST",
        "price": 0.50,
        "sentiment": "bullish",
    }


@pytest.fixture(autouse=True)
def reset_jupiter_client():
    """Reset global Jupiter client between tests."""
    demo_trading._JUPITER_CLIENT = None
    yield
    demo_trading._JUPITER_CLIENT = None


# =============================================================================
# Client Initialization Tests
# =============================================================================


class TestClientInitialization:
    """Test lazy-loaded client initialization."""

    def test_get_jupiter_client_creates_instance(self):
        """Test Jupiter client is created on first call."""
        with patch("bots.treasury.jupiter.JupiterClient") as mock_jup_cls:
            mock_instance = MagicMock()
            mock_jup_cls.return_value = mock_instance

            client1 = demo_trading._get_jupiter_client()
            client2 = demo_trading._get_jupiter_client()

            # Should create only once
            assert mock_jup_cls.call_count == 1
            assert client1 is client2
            assert client1 is mock_instance


# =============================================================================
# Wallet Configuration Tests
# =============================================================================


class TestWalletConfiguration:
    """Test wallet password and directory resolution."""

    def test_wallet_password_precedence_demo_treasury_first(self, monkeypatch):
        """Test DEMO_TREASURY_WALLET_PASSWORD is checked first."""
        monkeypatch.setenv("DEMO_TREASURY_WALLET_PASSWORD", "demo_treasury_pwd")
        monkeypatch.setenv("TREASURY_WALLET_PASSWORD", "treasury_pwd")
        monkeypatch.setenv("WALLET_PASSWORD", "generic_pwd")

        result = demo_trading._get_demo_wallet_password()

        assert result == "demo_treasury_pwd"

    def test_wallet_password_precedence_fallback_to_treasury(self, monkeypatch):
        """Test fallback to TREASURY_WALLET_PASSWORD."""
        monkeypatch.delenv("DEMO_TREASURY_WALLET_PASSWORD", raising=False)
        monkeypatch.delenv("DEMO_WALLET_PASSWORD", raising=False)
        monkeypatch.delenv("DEMO_JARVIS_WALLET_PASSWORD", raising=False)
        monkeypatch.setenv("TREASURY_WALLET_PASSWORD", "treasury_pwd")

        result = demo_trading._get_demo_wallet_password()

        assert result == "treasury_pwd"

    def test_wallet_password_none_when_missing(self, monkeypatch):
        """Test returns None when no password env vars set."""
        for key in [
            "DEMO_TREASURY_WALLET_PASSWORD",
            "DEMO_WALLET_PASSWORD",
            "DEMO_JARVIS_WALLET_PASSWORD",
            "TREASURY_WALLET_PASSWORD",
            "JARVIS_WALLET_PASSWORD",
            "WALLET_PASSWORD",
        ]:
            monkeypatch.delenv(key, raising=False)

        result = demo_trading._get_demo_wallet_password()

        assert result is None

    def test_wallet_dir_from_env(self, monkeypatch):
        """Test wallet directory from DEMO_WALLET_DIR."""
        monkeypatch.setenv("DEMO_WALLET_DIR", "/custom/wallet/dir")

        result = demo_trading._get_demo_wallet_dir()

        assert result == Path("/custom/wallet/dir")

    def test_wallet_dir_default_path(self, monkeypatch):
        """Test default wallet directory path."""
        monkeypatch.delenv("DEMO_WALLET_DIR", raising=False)

        result = demo_trading._get_demo_wallet_dir()

        # Should be relative to project root (handle Windows backslashes)
        assert ".wallets-demo" in str(result)
        assert "treasury" in str(result)

    def test_load_demo_wallet_success(self, monkeypatch, mock_wallet):
        """Test successful wallet loading."""
        monkeypatch.setenv("DEMO_TREASURY_WALLET_PASSWORD", "test_pwd")

        with patch("bots.treasury.wallet.SecureWallet") as mock_wallet_cls:
            mock_wallet_cls.return_value = mock_wallet

            wallet = demo_trading._load_demo_wallet("test_address_123")

            assert wallet is mock_wallet
            mock_wallet.set_active.assert_called_once_with("test_address_123")

    def test_load_demo_wallet_no_password(self, monkeypatch):
        """Test wallet loading returns None without password."""
        for key in [
            "DEMO_TREASURY_WALLET_PASSWORD",
            "DEMO_WALLET_PASSWORD",
            "DEMO_JARVIS_WALLET_PASSWORD",
            "TREASURY_WALLET_PASSWORD",
            "JARVIS_WALLET_PASSWORD",
            "WALLET_PASSWORD",
        ]:
            monkeypatch.delenv(key, raising=False)

        wallet = demo_trading._load_demo_wallet()

        assert wallet is None

    def test_load_demo_wallet_set_active_failure_ignored(self, monkeypatch, mock_wallet):
        """Test set_active failure is ignored gracefully."""
        monkeypatch.setenv("DEMO_TREASURY_WALLET_PASSWORD", "test_pwd")
        mock_wallet.set_active.side_effect = Exception("Address not found")

        with patch("bots.treasury.wallet.SecureWallet") as mock_wallet_cls:
            mock_wallet_cls.return_value = mock_wallet

            wallet = demo_trading._load_demo_wallet("invalid_address")

            # Should still return wallet despite set_active failure
            assert wallet is mock_wallet


# =============================================================================
# Slippage Configuration Tests
# =============================================================================


class TestSlippageConfiguration:
    """Test slippage resolution from environment."""

    def test_slippage_from_bps_env(self, monkeypatch):
        """Test slippage from DEMO_SWAP_SLIPPAGE_BPS."""
        monkeypatch.setenv("DEMO_SWAP_SLIPPAGE_BPS", "250")

        result = demo_trading._get_demo_slippage_bps()

        assert result == 250

    def test_slippage_from_pct_env(self, monkeypatch):
        """Test slippage from DEMO_SWAP_SLIPPAGE_PCT."""
        monkeypatch.delenv("DEMO_SWAP_SLIPPAGE_BPS", raising=False)
        monkeypatch.setenv("DEMO_SWAP_SLIPPAGE_PCT", "2.5")

        result = demo_trading._get_demo_slippage_bps()

        assert result == 250  # 2.5% = 250 bps

    def test_slippage_default_when_missing(self, monkeypatch):
        """Test default slippage when env vars missing."""
        monkeypatch.delenv("DEMO_SWAP_SLIPPAGE_BPS", raising=False)
        monkeypatch.delenv("DEMO_SWAP_SLIPPAGE_PCT", raising=False)

        result = demo_trading._get_demo_slippage_bps()

        assert result == 100  # 1% default

    def test_slippage_minimum_one_bps(self, monkeypatch):
        """Test slippage is clamped to minimum 1 bps."""
        monkeypatch.setenv("DEMO_SWAP_SLIPPAGE_BPS", "0")

        result = demo_trading._get_demo_slippage_bps()

        assert result == 1

    def test_slippage_invalid_bps_value(self, monkeypatch):
        """Test invalid BPS value falls back to default."""
        monkeypatch.setenv("DEMO_SWAP_SLIPPAGE_BPS", "not_a_number")

        result = demo_trading._get_demo_slippage_bps()

        assert result == 100


# =============================================================================
# Token Utility Tests
# =============================================================================


class TestTokenUtilities:
    """Test token decimals and conversion utilities."""

    @pytest.mark.asyncio
    async def test_get_token_decimals_sol(self, mock_jupiter_client):
        """Test SOL always returns 9 decimals."""
        sol_mint = "So11111111111111111111111111111111111111112"

        decimals = await demo_trading._get_token_decimals(sol_mint, mock_jupiter_client)

        assert decimals == 9
        # Should not call get_token_info for SOL
        mock_jupiter_client.get_token_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_token_decimals_from_jupiter(self, mock_jupiter_client):
        """Test fetching decimals from Jupiter."""
        token_mint = "TokenMintAddress123"

        decimals = await demo_trading._get_token_decimals(token_mint, mock_jupiter_client)

        assert decimals == 6
        mock_jupiter_client.get_token_info.assert_called_once_with(token_mint)

    @pytest.mark.asyncio
    async def test_get_token_decimals_default_on_error(self, mock_jupiter_client):
        """Test default 6 decimals on error."""
        mock_jupiter_client.get_token_info = AsyncMock(side_effect=Exception("API error"))

        decimals = await demo_trading._get_token_decimals("bad_mint", mock_jupiter_client)

        assert decimals == 6

    @pytest.mark.asyncio
    async def test_to_base_units_conversion(self, mock_jupiter_client):
        """Test human-readable to base units conversion."""
        token_mint = "TestToken"

        base_units = await demo_trading._to_base_units(token_mint, 1.5, mock_jupiter_client)

        # 1.5 tokens * 10^6 = 1,500,000
        assert base_units == 1_500_000

    @pytest.mark.asyncio
    async def test_from_base_units_conversion(self, mock_jupiter_client):
        """Test base units to human-readable conversion."""
        token_mint = "TestToken"

        human_amount = await demo_trading._from_base_units(token_mint, 1_500_000, mock_jupiter_client)

        assert human_amount == 1.5


# =============================================================================
# Swap Execution Tests
# =============================================================================


class TestSwapExecution:
    """Test _execute_swap_with_fallback logic."""

    @pytest.mark.asyncio
    async def test_swap_bags_success(self, mock_bags_client):
        """Test successful swap via Bags.fm."""
        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client):
            result = await demo_trading._execute_swap_with_fallback(
                from_token="SOL",
                to_token="TOKEN",
                amount=1.0,
                wallet_address="wallet123",
                slippage_bps=100,
            )

        assert result["success"] is True
        assert result["source"] == "bags_fm"
        assert result["tx_hash"] == "bags_tx_abc123"
        assert result["amount_out"] == 1000.0

    @pytest.mark.asyncio
    async def test_swap_bags_failure_jupiter_fallback(self, mock_bags_client, mock_jupiter_client, mock_wallet):
        """Test Bags.fm failure triggers Jupiter fallback."""
        # Bags fails
        bags_fail_result = SimpleNamespace(success=False, error="Bags API error")
        mock_bags_client.swap = AsyncMock(return_value=bags_fail_result)

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter_client), \
             patch("tg_bot.handlers.demo.demo_trading._load_demo_wallet", return_value=mock_wallet):

            result = await demo_trading._execute_swap_with_fallback(
                from_token="SOL",
                to_token="TOKEN",
                amount=1.0,
                wallet_address="wallet123",
                slippage_bps=100,
            )

        assert result["success"] is True
        assert result["source"] == "jupiter"
        assert result["tx_hash"] == "jupiter_tx_xyz789"
        mock_jupiter_client.execute_swap.assert_called_once()

    @pytest.mark.asyncio
    async def test_swap_jupiter_fallback_no_wallet(self, mock_bags_client):
        """Test Jupiter fallback fails without wallet."""
        bags_fail_result = SimpleNamespace(success=False, error="Bags error")
        mock_bags_client.swap = AsyncMock(return_value=bags_fail_result)

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_trading._load_demo_wallet", return_value=None):

            result = await demo_trading._execute_swap_with_fallback(
                from_token="SOL",
                to_token="TOKEN",
                amount=1.0,
                wallet_address="wallet123",
                slippage_bps=100,
            )

        assert result["success"] is False
        # Error should mention wallet issue (last_error from Bags is propagated)
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_swap_jupiter_quote_failure(self, mock_bags_client, mock_jupiter_client, mock_wallet):
        """Test Jupiter fallback fails on quote error."""
        bags_fail_result = SimpleNamespace(success=False, error="Bags error")
        mock_bags_client.swap = AsyncMock(return_value=bags_fail_result)
        mock_jupiter_client.get_quote = AsyncMock(return_value=None)

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_trading._get_jupiter_client", return_value=mock_jupiter_client), \
             patch("tg_bot.handlers.demo.demo_trading._load_demo_wallet", return_value=mock_wallet):

            result = await demo_trading._execute_swap_with_fallback(
                from_token="SOL",
                to_token="TOKEN",
                amount=1.0,
                wallet_address="wallet123",
                slippage_bps=100,
            )

        assert result["success"] is False
        # Error from Jupiter quote failure
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_swap_bags_skipped_without_keys(self):
        """Test Bags.fm is skipped without API keys."""
        mock_bags_no_keys = AsyncMock()
        mock_bags_no_keys.api_key = None
        mock_bags_no_keys.partner_key = None

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_no_keys), \
             patch("tg_bot.handlers.demo.demo_trading._load_demo_wallet", return_value=None):

            result = await demo_trading._execute_swap_with_fallback(
                from_token="SOL",
                to_token="TOKEN",
                amount=1.0,
                wallet_address="wallet123",
                slippage_bps=100,
            )

        # Should skip Bags and fail on wallet (Jupiter fallback)
        assert result["success"] is False
        mock_bags_no_keys.swap.assert_not_called()


# =============================================================================
# Buy with TP/SL Tests
# =============================================================================


class TestBuyWithTPSL:
    """Test execute_buy_with_tpsl function."""

    @pytest.mark.asyncio
    async def test_buy_with_tpsl_success(self, mock_bags_client, mock_sentiment_data):
        """Test successful buy with TP/SL creation."""
        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value=mock_sentiment_data):

            result = await demo_trading.execute_buy_with_tpsl(
                token_address="TokenMint123",
                amount_sol=1.0,
                wallet_address="wallet123",
                tp_percent=50.0,
                sl_percent=20.0,
            )

        assert result["success"] is True
        assert "position" in result

        position = result["position"]
        assert position["symbol"] == "TEST"
        assert position["amount_sol"] == 1.0
        assert position["entry_price"] == 0.50
        assert position["tp_percent"] == 50.0
        assert position["sl_percent"] == 20.0
        assert position["tp_price"] == 0.75  # 0.50 * 1.5
        assert position["sl_price"] == 0.40  # 0.50 * 0.8
        assert position["source"] == "bags_fm"
        assert "id" in position

    @pytest.mark.asyncio
    async def test_buy_with_tpsl_swap_failure(self, mock_bags_client, mock_sentiment_data):
        """Test buy fails when swap fails."""
        swap_fail_result = SimpleNamespace(success=False, error="Swap error")
        mock_bags_client.swap = AsyncMock(return_value=swap_fail_result)

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value=mock_sentiment_data), \
             patch("tg_bot.handlers.demo.demo_trading._load_demo_wallet", return_value=None):

            result = await demo_trading.execute_buy_with_tpsl(
                token_address="TokenMint123",
                amount_sol=1.0,
                wallet_address="wallet123",
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_buy_with_tpsl_sentiment_failure_fallback(self, mock_bags_client):
        """Test buy continues with UNKNOWN symbol on sentiment failure."""
        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, side_effect=Exception("Sentiment error")):

            result = await demo_trading.execute_buy_with_tpsl(
                token_address="TokenMint123",
                amount_sol=1.0,
                wallet_address="wallet123",
            )

        assert result["success"] is True
        position = result["position"]
        assert position["symbol"] == "UNKNOWN"
        assert position["entry_price"] == 0.0

    @pytest.mark.asyncio
    async def test_buy_with_tpsl_custom_slippage(self, mock_bags_client, mock_sentiment_data):
        """Test buy with custom slippage parameter."""
        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value=mock_sentiment_data):

            result = await demo_trading.execute_buy_with_tpsl(
                token_address="TokenMint123",
                amount_sol=1.0,
                wallet_address="wallet123",
                slippage_bps=500,
            )

        assert result["success"] is True
        # Verify slippage was passed to swap
        mock_bags_client.swap.assert_called_once()
        call_kwargs = mock_bags_client.swap.call_args.kwargs
        assert call_kwargs["slippage_bps"] == 500

    @pytest.mark.asyncio
    async def test_buy_with_tpsl_tokens_estimation(self, mock_bags_client, mock_sentiment_data):
        """Test tokens received estimation when not returned."""
        # Swap result without amount_out
        swap_result_no_amount = SimpleNamespace(
            success=True,
            tx_hash="tx123",
            to_amount=None,  # Not provided
            error=None,
        )
        mock_bags_client.swap = AsyncMock(return_value=swap_result_no_amount)

        with patch("tg_bot.handlers.demo.demo_trading.get_bags_client", return_value=mock_bags_client), \
             patch("tg_bot.handlers.demo.demo_sentiment.get_ai_sentiment_for_token", new_callable=AsyncMock, return_value=mock_sentiment_data):

            result = await demo_trading.execute_buy_with_tpsl(
                token_address="TokenMint123",
                amount_sol=1.0,
                wallet_address="wallet123",
            )

        assert result["success"] is True
        position = result["position"]
        # Should estimate: 1.0 SOL * $225 / $0.50 = 450 tokens
        assert position["amount"] == 450.0


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Test input validation functions."""

    def test_validate_buy_amount_valid(self):
        """Test valid buy amounts pass."""
        valid, error = demo_trading.validate_buy_amount(1.0)

        assert valid is True
        assert error == ""

    def test_validate_buy_amount_below_minimum(self):
        """Test buy amount below 0.01 SOL fails."""
        valid, error = demo_trading.validate_buy_amount(0.005)

        assert valid is False
        assert "Minimum" in error

    def test_validate_buy_amount_above_maximum(self):
        """Test buy amount above 50 SOL fails."""
        valid, error = demo_trading.validate_buy_amount(51.0)

        assert valid is False
        assert "Maximum" in error

    def test_validate_buy_amount_edge_minimum(self):
        """Test exactly 0.01 SOL passes."""
        valid, error = demo_trading.validate_buy_amount(0.01)

        assert valid is True

    def test_validate_buy_amount_edge_maximum(self):
        """Test exactly 50 SOL passes."""
        valid, error = demo_trading.validate_buy_amount(50.0)

        assert valid is True
