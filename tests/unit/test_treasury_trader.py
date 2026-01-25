"""
Unit tests for treasury_trader.py

Tests cover:
- _SimpleWallet class (balance, signing, treasury info)
- TreasuryTrader singleton pattern
- Environment variable resolution with profile prefixes
- Wallet initialization and keypair decryption
- Trade execution with TP/SL
- Token mint resolution
- Position health monitoring
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime
from typing import Tuple

from bots.treasury.trading.treasury_trader import _SimpleWallet, TreasuryTrader
from bots.treasury.trading.types import Position, TradeDirection, TradeStatus


# Mock classes to avoid import dependencies
class MockKeypair:
    """Mock Solana keypair."""
    def __init__(self, pubkey_str="test_pubkey_12345"):
        self._pubkey = pubkey_str

    def pubkey(self):
        return self._pubkey

    def sign_message(self, message):
        return b"mock_signature_bytes"


class MockWalletInfo:
    """Mock WalletInfo."""
    def __init__(self, address, created_at="", label="", is_treasury=False):
        self.address = address
        self.created_at = created_at
        self.label = label
        self.is_treasury = is_treasury


@pytest.fixture
def mock_keypair():
    """Create mock keypair."""
    return MockKeypair("test_treasury_address_12345")


@pytest.fixture
def simple_wallet(mock_keypair):
    """Create _SimpleWallet instance for testing."""
    with patch('bots.treasury.trading.treasury_trader.WalletInfo', MockWalletInfo):
        wallet = _SimpleWallet(mock_keypair, str(mock_keypair.pubkey()))
        return wallet


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for RPC calls."""
    # Create async context manager for response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "result": {"value": 5_000_000_000}  # 5 SOL in lamports
    })
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # Create async context manager for session
    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


@pytest.fixture
def treasury_trader_instance(monkeypatch):
    """Create TreasuryTrader instance with mocked dependencies."""
    # Clear singleton instances
    TreasuryTrader._instances = {}

    # Set environment variables
    monkeypatch.setenv("JARVIS_WALLET_PASSWORD", "test_password")
    monkeypatch.setenv("TREASURY_LIVE_MODE", "false")
    monkeypatch.setenv("TREASURY_ADMIN_IDS", "12345,67890")

    trader = TreasuryTrader(profile="treasury")
    return trader


class TestSimpleWallet:
    """Tests for _SimpleWallet class."""

    def test_init_creates_wallet_info(self, simple_wallet, mock_keypair):
        """Test wallet initialization creates WalletInfo."""
        assert simple_wallet._address == str(mock_keypair.pubkey())
        assert simple_wallet._keypair == mock_keypair
        assert simple_wallet._treasury_info is not None
        assert simple_wallet._treasury_info.is_treasury is True

    def test_get_treasury_returns_wallet_info(self, simple_wallet):
        """Test get_treasury returns WalletInfo."""
        treasury = simple_wallet.get_treasury()
        assert treasury is not None
        assert treasury.is_treasury is True
        assert treasury.label == "Treasury"

    @pytest.mark.asyncio
    async def test_get_balance_success(self, simple_wallet):
        """Test successful balance retrieval."""
        # Create async context manager for CoinGecko response
        coingecko_response = AsyncMock()
        coingecko_response.status = 200
        coingecko_response.json = AsyncMock(return_value={
            "solana": {"usd": 100.0}
        })
        coingecko_response.__aenter__ = AsyncMock(return_value=coingecko_response)
        coingecko_response.__aexit__ = AsyncMock(return_value=None)

        # Create async context manager for RPC response
        rpc_response = AsyncMock()
        rpc_response.status = 200
        rpc_response.json = AsyncMock(return_value={
            "result": {"value": 5_000_000_000}  # 5 SOL in lamports
        })
        rpc_response.__aenter__ = AsyncMock(return_value=rpc_response)
        rpc_response.__aexit__ = AsyncMock(return_value=None)

        # Create session that returns different responses for post vs get
        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=rpc_response)
        mock_session.get = MagicMock(return_value=coingecko_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            sol_balance, usd_value = await simple_wallet.get_balance()

            assert sol_balance == 5.0  # 5_000_000_000 lamports / 1e9
            assert usd_value == 500.0  # 5 SOL * $100

    @pytest.mark.asyncio
    async def test_get_balance_rpc_failure(self, simple_wallet):
        """Test balance retrieval when RPC fails."""
        mock_response = AsyncMock()
        mock_response.status = 500

        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            sol_balance, usd_value = await simple_wallet.get_balance()

            assert sol_balance == 0.0
            assert usd_value == 0.0

    @pytest.mark.asyncio
    async def test_get_balance_with_custom_address(self, simple_wallet, mock_aiohttp_session):
        """Test balance retrieval for custom address."""
        with patch('aiohttp.ClientSession', return_value=mock_aiohttp_session):
            sol_balance, _ = await simple_wallet.get_balance(address="custom_address")
            assert sol_balance == 5.0

    @pytest.mark.asyncio
    async def test_get_token_balances_returns_empty(self, simple_wallet):
        """Test get_token_balances returns empty dict."""
        balances = await simple_wallet.get_token_balances()
        assert balances == {}

    def test_sign_transaction_with_bytes(self, simple_wallet):
        """Test signing transaction with bytes input."""
        tx_bytes = b"mock_transaction_data"
        signature = simple_wallet.sign_transaction("address", tx_bytes)

        assert isinstance(signature, bytes)
        assert signature == b"mock_signature_bytes"

    def test_keypair_property(self, simple_wallet, mock_keypair):
        """Test keypair property returns underlying keypair."""
        assert simple_wallet.keypair == mock_keypair


class TestTreasuryTraderSingleton:
    """Tests for TreasuryTrader singleton pattern."""

    def test_singleton_same_profile_returns_same_instance(self):
        """Test that same profile returns same instance."""
        TreasuryTrader._instances = {}

        trader1 = TreasuryTrader(profile="treasury")
        trader2 = TreasuryTrader(profile="treasury")

        assert trader1 is trader2

    def test_singleton_different_profiles_return_different_instances(self):
        """Test that different profiles return different instances."""
        TreasuryTrader._instances = {}

        trader1 = TreasuryTrader(profile="treasury")
        trader2 = TreasuryTrader(profile="demo")

        assert trader1 is not trader2
        assert trader1._profile == "treasury"
        assert trader2._profile == "demo"

    def test_profile_normalization(self):
        """Test that profile is normalized to lowercase."""
        TreasuryTrader._instances = {}

        trader1 = TreasuryTrader(profile="TREASURY")
        trader2 = TreasuryTrader(profile="treasury")

        assert trader1 is trader2
        assert trader1._profile == "treasury"


class TestEnvironmentResolution:
    """Tests for environment variable resolution."""

    def test_get_env_without_prefix(self, treasury_trader_instance, monkeypatch):
        """Test env resolution when no prefix (treasury profile)."""
        monkeypatch.setenv("TEST_VAR", "test_value")

        value = treasury_trader_instance._get_env("TEST_VAR")
        assert value == "test_value"

    def test_get_env_with_prefix(self, monkeypatch):
        """Test env resolution with profile prefix."""
        TreasuryTrader._instances = {}
        monkeypatch.setenv("DEMO_TEST_VAR", "demo_value")
        monkeypatch.setenv("TEST_VAR", "default_value")

        trader = TreasuryTrader(profile="demo")
        value = trader._get_env("TEST_VAR")

        # Should return prefixed value
        assert value == "demo_value"

    def test_get_env_with_default(self, treasury_trader_instance):
        """Test env resolution with default value."""
        value = treasury_trader_instance._get_env("NONEXISTENT_VAR", "default")
        assert value == "default"

    def test_get_wallet_password_priority(self, treasury_trader_instance, monkeypatch):
        """Test wallet password resolution priority."""
        monkeypatch.setenv("TREASURY_WALLET_PASSWORD", "treasury_pass")
        monkeypatch.setenv("JARVIS_WALLET_PASSWORD", "jarvis_pass")
        monkeypatch.setenv("WALLET_PASSWORD", "wallet_pass")

        # Should return first matching key
        password = treasury_trader_instance._get_wallet_password()
        assert password in ("treasury_pass", "jarvis_pass", "wallet_pass")

    def test_get_wallet_dir_custom(self, treasury_trader_instance, monkeypatch):
        """Test custom wallet directory."""
        monkeypatch.setenv("WALLET_DIR", "/custom/wallet/dir")

        wallet_dir = treasury_trader_instance._get_wallet_dir()
        assert wallet_dir == Path("/custom/wallet/dir").expanduser()

    def test_default_keypair_path_treasury(self, treasury_trader_instance):
        """Test default keypair path for treasury profile."""
        path = treasury_trader_instance._default_keypair_path()
        assert path.name == "treasury_keypair.json"
        assert "data" in str(path)

    def test_default_keypair_path_demo(self, monkeypatch):
        """Test default keypair path for demo profile."""
        TreasuryTrader._instances = {}
        trader = TreasuryTrader(profile="demo")

        path = trader._default_keypair_path()
        assert path.name == "demo_treasury_keypair.json"


class TestKeypairLoading:
    """Tests for keypair loading and decryption."""

    def test_load_encrypted_keypair_plaintext_array(self, treasury_trader_instance, tmp_path):
        """Test loading plaintext keypair (array format)."""
        import json

        keypair_path = tmp_path / "keypair.json"
        mock_keypair_data = [1, 2, 3, 4] + [0] * 60  # 64 bytes total
        keypair_path.write_text(json.dumps(mock_keypair_data))

        with patch('solders.keypair.Keypair.from_bytes') as mock_from_bytes:
            mock_from_bytes.return_value = MockKeypair()

            result = treasury_trader_instance._load_encrypted_keypair(keypair_path)

            mock_from_bytes.assert_called_once()
            assert result is not None

    def test_load_encrypted_keypair_missing_password(self, treasury_trader_instance, tmp_path, monkeypatch):
        """Test encrypted keypair without password."""
        import json

        monkeypatch.delenv("JARVIS_WALLET_PASSWORD", raising=False)

        keypair_path = tmp_path / "keypair.json"
        encrypted_data = {
            "encrypted_key": "dGVzdA==",
            "salt": "dGVzdA==",
            "nonce": "dGVzdA=="
        }
        keypair_path.write_text(json.dumps(encrypted_data))

        result = treasury_trader_instance._load_encrypted_keypair(keypair_path)
        assert result is None

    def test_load_encrypted_keypair_file_not_found(self, treasury_trader_instance, tmp_path):
        """Test loading keypair from non-existent file."""
        missing_path = tmp_path / "nonexistent.json"

        result = treasury_trader_instance._load_encrypted_keypair(missing_path)
        assert result is None


class TestTreasuryTraderPublicAPI:
    """Tests for TreasuryTrader public API methods."""

    @pytest.mark.asyncio
    async def test_get_tp_sl_levels(self, treasury_trader_instance):
        """Test TP/SL level calculation."""
        with patch('bots.treasury.trading.treasury_trader.RiskChecker.get_tp_sl_levels') as mock_get_levels:
            mock_get_levels.return_value = (150.0, 80.0)

            tp, sl = treasury_trader_instance.get_tp_sl_levels(100.0, "A+")

            assert tp == 150.0
            assert sl == 80.0
            mock_get_levels.assert_called_once_with(100.0, "A+")

    @pytest.mark.asyncio
    async def test_get_balance_not_initialized(self):
        """Test get_balance when not initialized."""
        TreasuryTrader._instances = {}
        trader = TreasuryTrader(profile="treasury")

        # Mock _ensure_initialized to return False
        with patch.object(trader, '_ensure_initialized', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = (False, "Not initialized")

            sol, usd = await trader.get_balance()

            assert sol == 0.0
            assert usd == 0.0

    @pytest.mark.asyncio
    async def test_get_balance_initialized(self, treasury_trader_instance):
        """Test get_balance when initialized."""
        # Mock engine
        mock_engine = MagicMock()
        mock_engine.get_portfolio_value = AsyncMock(return_value=(10.0, 1000.0))

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        sol, usd = await treasury_trader_instance.get_balance()

        assert sol == 10.0
        assert usd == 1000.0

    @pytest.mark.asyncio
    async def test_get_open_positions_not_initialized(self):
        """Test get_open_positions when not initialized."""
        TreasuryTrader._instances = {}
        trader = TreasuryTrader(profile="treasury")

        positions = await trader.get_open_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_get_open_positions_initialized(self, treasury_trader_instance):
        """Test get_open_positions when initialized."""
        mock_position = Position(
            id="test123",
            token_mint="mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=105.0,
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )

        mock_engine = MagicMock()
        mock_engine.get_open_positions = MagicMock(return_value=[mock_position])

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        positions = await treasury_trader_instance.get_open_positions()

        assert len(positions) == 1
        assert positions[0].id == "test123"

    @pytest.mark.asyncio
    async def test_close_position(self, treasury_trader_instance):
        """Test close_position."""
        mock_engine = MagicMock()
        mock_engine.close_position = AsyncMock(return_value=(True, "Closed successfully"))

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        success, message = await treasury_trader_instance.close_position("test123", user_id=12345)

        assert success is True
        assert "Closed successfully" in message

    @pytest.mark.asyncio
    async def test_monitor_and_close_breached_positions(self, treasury_trader_instance):
        """Test monitor_and_close_breached_positions."""
        mock_engine = MagicMock()
        mock_engine.monitor_stop_losses = AsyncMock(return_value=[
            {"position_id": "test123", "action": "closed"}
        ])

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        results = await treasury_trader_instance.monitor_and_close_breached_positions()

        assert len(results) == 1
        assert results[0]["position_id"] == "test123"


class TestPositionHealth:
    """Tests for position health monitoring."""

    @pytest.mark.asyncio
    async def test_get_position_health_not_initialized(self):
        """Test position health when not initialized."""
        TreasuryTrader._instances = {}
        trader = TreasuryTrader(profile="treasury")

        # Mock _ensure_initialized to return False
        with patch.object(trader, '_ensure_initialized', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = (False, "Not initialized")

            health = await trader.get_position_health()

            assert health["healthy"] is False
            assert "error" in health

    @pytest.mark.asyncio
    async def test_get_position_health_no_positions(self, treasury_trader_instance):
        """Test position health with no open positions."""
        mock_engine = MagicMock()
        mock_engine.get_open_positions = MagicMock(return_value=[])

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        health = await treasury_trader_instance.get_position_health()

        assert health["healthy"] is True
        assert health["positions"] == []
        assert health["alerts"] == []

    @pytest.mark.asyncio
    async def test_get_position_health_with_sl_breach(self, treasury_trader_instance):
        """Test position health with stop loss breach."""
        breached_position = Position(
            id="breach123",
            token_mint="mint",
            token_symbol="BREACH",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=85.0,  # Below SL
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )

        mock_engine = MagicMock()
        mock_engine.get_open_positions = MagicMock(return_value=[breached_position])

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        health = await treasury_trader_instance.get_position_health()

        assert health["healthy"] is False
        assert len(health["alerts"]) > 0
        assert "SL_BREACHED" in str(health["positions"][0]["status"])

    @pytest.mark.asyncio
    async def test_get_position_health_with_tp_hit(self, treasury_trader_instance):
        """Test position health with take profit hit."""
        tp_position = Position(
            id="tp123",
            token_mint="mint",
            token_symbol="PROFIT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            current_price=125.0,  # Above TP
            amount=10.0,
            amount_usd=1000.0,
            take_profit_price=120.0,
            stop_loss_price=90.0,
            status=TradeStatus.OPEN,
            opened_at=datetime.utcnow().isoformat(),
        )

        mock_engine = MagicMock()
        mock_engine.get_open_positions = MagicMock(return_value=[tp_position])

        treasury_trader_instance._engine = mock_engine
        treasury_trader_instance._initialized = True

        health = await treasury_trader_instance.get_position_health()

        assert len(health["alerts"]) > 0
        assert "TP_HIT" in str(health["positions"][0]["status"])


class TestExecuteBuyWithTpSl:
    """Tests for execute_buy_with_tp_sl method."""

    @pytest.mark.asyncio
    async def test_execute_buy_missing_user_id(self, treasury_trader_instance):
        """Test trade execution without user_id."""
        treasury_trader_instance._initialized = True
        treasury_trader_instance._engine = MagicMock()

        result = await treasury_trader_instance.execute_buy_with_tp_sl(
            token_mint="mint",
            amount_sol=1.0,
            take_profit_price=120.0,
            stop_loss_price=80.0,
            user_id=None  # Missing user_id
        )

        assert result["success"] is False
        assert "User ID required" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_buy_not_initialized(self):
        """Test trade execution when not initialized."""
        TreasuryTrader._instances = {}
        trader = TreasuryTrader(profile="treasury")

        # Mock _ensure_initialized to fail
        with patch.object(trader, '_ensure_initialized', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = (False, "Initialization failed")

            result = await trader.execute_buy_with_tp_sl(
                token_mint="mint",
                amount_sol=1.0,
                take_profit_price=120.0,
                stop_loss_price=80.0,
                user_id=12345
            )

            assert result["success"] is False
            assert "Initialization failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_buy_emergency_stop(self, treasury_trader_instance):
        """Test trade execution when emergency stop is active."""
        with patch('bots.treasury.trading.treasury_trader.EMERGENCY_STOP_AVAILABLE', True):
            with patch('bots.treasury.trading.treasury_trader.get_emergency_stop_manager') as mock_get_manager:
                mock_manager = MagicMock()
                mock_manager.is_trading_allowed = MagicMock(return_value=(False, "Emergency stop active"))
                mock_get_manager.return_value = mock_manager

                result = await treasury_trader_instance.execute_buy_with_tp_sl(
                    token_mint="mint",
                    amount_sol=1.0,
                    take_profit_price=120.0,
                    stop_loss_price=80.0,
                    user_id=12345
                )

                assert result["success"] is False
                assert "EMERGENCY STOP" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_buy_invalid_tp_sl_uses_fallback(self, treasury_trader_instance):
        """Test that invalid TP/SL falls back to calculated defaults."""
        # Mock initialization and dependencies
        treasury_trader_instance._initialized = True

        mock_jupiter = AsyncMock()
        mock_jupiter.get_token_price = AsyncMock(return_value=100.0)
        mock_jupiter.get_token_info = AsyncMock(return_value=MagicMock(symbol="TEST"))

        mock_engine = MagicMock()
        mock_engine.jupiter = mock_jupiter
        mock_engine.open_position = AsyncMock(return_value=(False, "Mocked trade", None))

        treasury_trader_instance._engine = mock_engine

        # Mock _resolve_token_mint
        with patch.object(treasury_trader_instance, '_resolve_token_mint', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = "full_mint_address_12345"

            # Mock get_tp_sl_levels to return fallback values
            with patch.object(treasury_trader_instance, 'get_tp_sl_levels') as mock_get_levels:
                mock_get_levels.return_value = (150.0, 80.0)

                result = await treasury_trader_instance.execute_buy_with_tp_sl(
                    token_mint="partial_mint",
                    amount_sol=1.0,
                    take_profit_price=50.0,  # Invalid (below current price)
                    stop_loss_price=150.0,  # Invalid (above current price)
                    user_id=12345,
                    sentiment_grade="A"
                )

                # Should have called fallback
                mock_get_levels.assert_called_once_with(100.0, "A")


class TestTokenMintResolution:
    """Tests for token mint resolution."""

    @pytest.mark.asyncio
    async def test_resolve_token_mint_already_full(self, treasury_trader_instance):
        """Test that full token mints are returned as-is."""
        full_mint = "So11111111111111111111111111111111111111112"

        result = await treasury_trader_instance._resolve_token_mint(full_mint)

        assert result == full_mint

    @pytest.mark.asyncio
    async def test_resolve_token_mint_via_dexscreener(self, treasury_trader_instance):
        """Test token resolution via DexScreener."""
        # Create async context manager for response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "pairs": [
                {
                    "chainId": "solana",
                    "baseToken": {
                        "symbol": "TEST",
                        "name": "Test Token",
                        "address": "resolved_full_address_12345"
                    },
                    "liquidity": {"usd": 100000}
                }
            ]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create async context manager for session
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await treasury_trader_instance._resolve_token_mint("partial", "TEST")

            assert result == "resolved_full_address_12345"

    @pytest.mark.asyncio
    async def test_resolve_token_mint_no_results(self, treasury_trader_instance):
        """Test token resolution when no results found."""
        # Create async context manager for response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"pairs": []})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        # Create async context manager for session
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await treasury_trader_instance._resolve_token_mint("partial", "UNKNOWN")

            assert result is None
