"""
Tests for core/wallet_manager.py - Multi-Wallet Manager

This test suite provides comprehensive coverage for the WalletManager class
including wallet configuration, role-based access, trading limits, balance
tracking, and the WalletSelector helper.
"""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import base58

from core.wallet_manager import (
    WalletRole,
    WalletStatus,
    WalletConfig,
    WalletBalance,
    WalletTransaction,
    WalletManager,
    WalletSelector,
    get_wallet_manager,
)


# === TEST FIXTURES ===

# Valid Solana addresses (32 bytes when decoded)
VALID_ADDRESS_1 = "11111111111111111111111111111111"  # System program - valid format
VALID_ADDRESS_2 = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"  # Token program
VALID_ADDRESS_3 = "So11111111111111111111111111111111111111112"  # Wrapped SOL
VALID_ADDRESS_4 = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC

# Invalid addresses
INVALID_ADDRESS_SHORT = "abc123"
INVALID_ADDRESS_INVALID_CHARS = "O0Il1"  # Invalid base58 chars


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            'wallets': [
                {
                    'name': 'Treasury',
                    'address': VALID_ADDRESS_1,
                    'role': 'treasury',
                    'status': 'active',
                    'daily_limit_sol': 10.0,
                    'single_tx_limit_sol': 2.0,
                    'allowed_tokens': [],
                    'blocked_tokens': [],
                    'description': 'Main treasury wallet',
                    'created_at': '2024-01-01T00:00:00Z',
                    'tags': ['main', 'treasury']
                },
                {
                    'name': 'Trading Wallet',
                    'address': VALID_ADDRESS_2,
                    'role': 'trading',
                    'status': 'active',
                    'daily_limit_sol': 5.0,
                    'single_tx_limit_sol': 1.0,
                    'allowed_tokens': [],
                    'blocked_tokens': [],
                    'description': 'Active trading',
                    'created_at': '2024-01-01T00:00:00Z',
                    'tags': ['trading']
                }
            ]
        }
        json.dump(config, f)
        f.flush()
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def empty_config_file():
    """Create an empty temporary directory for config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "wallets.json"
        yield config_path


@pytest.fixture
def wallet_manager(temp_config_file):
    """Create a WalletManager with test config."""
    return WalletManager(config_path=temp_config_file)


@pytest.fixture
def empty_wallet_manager(empty_config_file):
    """Create a WalletManager with no existing wallets."""
    return WalletManager(config_path=empty_config_file)


@pytest.fixture
def sample_wallet_config():
    """Create a sample WalletConfig."""
    return WalletConfig(
        name="Test Wallet",
        address=VALID_ADDRESS_3,
        role=WalletRole.HOT_WALLET,
        status=WalletStatus.ACTIVE,
        daily_limit_sol=2.0,
        single_tx_limit_sol=0.5,
        allowed_tokens=[],
        blocked_tokens=[],
        description="Test wallet",
    )


# === TESTS FOR ENUMS ===

class TestWalletRole:
    """Test WalletRole enum values."""

    def test_treasury_role(self):
        """Treasury role value."""
        assert WalletRole.TREASURY.value == "treasury"

    def test_trading_role(self):
        """Trading role value."""
        assert WalletRole.TRADING.value == "trading"

    def test_cold_storage_role(self):
        """Cold storage role value."""
        assert WalletRole.COLD_STORAGE.value == "cold"

    def test_hot_wallet_role(self):
        """Hot wallet role value."""
        assert WalletRole.HOT_WALLET.value == "hot"

    def test_dev_role(self):
        """Dev role value."""
        assert WalletRole.DEV.value == "dev"

    def test_monitoring_role(self):
        """Monitoring role value."""
        assert WalletRole.MONITORING.value == "monitoring"

    def test_role_from_value(self):
        """Can create role from string value."""
        role = WalletRole("treasury")
        assert role == WalletRole.TREASURY


class TestWalletStatus:
    """Test WalletStatus enum values."""

    def test_active_status(self):
        """Active status value."""
        assert WalletStatus.ACTIVE.value == "active"

    def test_paused_status(self):
        """Paused status value."""
        assert WalletStatus.PAUSED.value == "paused"

    def test_locked_status(self):
        """Locked status value."""
        assert WalletStatus.LOCKED.value == "locked"

    def test_archived_status(self):
        """Archived status value."""
        assert WalletStatus.ARCHIVED.value == "archived"


# === TESTS FOR DATACLASSES ===

class TestWalletConfig:
    """Test WalletConfig dataclass."""

    def test_create_minimal_config(self):
        """Create config with minimal required fields."""
        config = WalletConfig(
            name="Test",
            address=VALID_ADDRESS_1,
            role=WalletRole.TRADING,
        )
        assert config.name == "Test"
        assert config.address == VALID_ADDRESS_1
        assert config.role == WalletRole.TRADING
        assert config.status == WalletStatus.ACTIVE  # default
        assert config.daily_limit_sol == 1.0  # default
        assert config.single_tx_limit_sol == 0.1  # default

    def test_create_full_config(self):
        """Create config with all fields."""
        config = WalletConfig(
            name="Full Config",
            address=VALID_ADDRESS_1,
            role=WalletRole.TREASURY,
            status=WalletStatus.PAUSED,
            daily_limit_sol=100.0,
            single_tx_limit_sol=10.0,
            allowed_tokens=["token1", "token2"],
            blocked_tokens=["badtoken"],
            description="Full description",
            created_at="2024-01-01T00:00:00Z",
            last_used="2024-01-02T00:00:00Z",
            total_spent_today_sol=5.0,
            last_reset_date="2024-01-02",
            tags=["tag1", "tag2"],
        )
        assert config.daily_limit_sol == 100.0
        assert config.allowed_tokens == ["token1", "token2"]
        assert config.blocked_tokens == ["badtoken"]
        assert config.tags == ["tag1", "tag2"]

    def test_default_lists_are_independent(self):
        """Default lists should be independent instances."""
        config1 = WalletConfig(name="A", address=VALID_ADDRESS_1, role=WalletRole.TRADING)
        config2 = WalletConfig(name="B", address=VALID_ADDRESS_2, role=WalletRole.TRADING)

        config1.allowed_tokens.append("token1")
        assert "token1" not in config2.allowed_tokens


class TestWalletBalance:
    """Test WalletBalance dataclass."""

    def test_create_balance(self):
        """Create a wallet balance snapshot."""
        balance = WalletBalance(
            address=VALID_ADDRESS_1,
            sol_balance=10.5,
            usd_value=2100.0,
            token_balances={"mint1": 100.0, "mint2": 50.0},
            last_updated="2024-01-01T00:00:00Z"
        )
        assert balance.sol_balance == 10.5
        assert balance.usd_value == 2100.0
        assert len(balance.token_balances) == 2


class TestWalletTransaction:
    """Test WalletTransaction dataclass."""

    def test_create_transaction(self):
        """Create a transaction record."""
        tx = WalletTransaction(
            wallet_address=VALID_ADDRESS_1,
            tx_signature="abc123signature",
            timestamp="2024-01-01T00:00:00Z",
            tx_type="SWAP",
            amount=1.5,
            currency="SOL",
        )
        assert tx.tx_type == "SWAP"
        assert tx.amount == 1.5
        assert tx.status == "confirmed"  # default
        assert tx.fee == 0.0  # default


# === TESTS FOR WALLET MANAGER INITIALIZATION ===

class TestWalletManagerInit:
    """Test WalletManager initialization."""

    def test_init_with_existing_config(self, wallet_manager, temp_config_file):
        """Initialize with existing config file."""
        assert len(wallet_manager.wallets) == 2
        assert VALID_ADDRESS_1 in wallet_manager.wallets
        assert VALID_ADDRESS_2 in wallet_manager.wallets

    def test_init_with_nonexistent_config(self, empty_wallet_manager):
        """Initialize with non-existent config file."""
        assert len(empty_wallet_manager.wallets) == 0

    def test_init_with_encryption_key(self, empty_config_file):
        """Initialize with encryption key."""
        # Generate a valid Fernet key
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()

        manager = WalletManager(config_path=empty_config_file, encryption_key=key)
        assert manager._fernet is not None

    def test_init_default_config_path(self):
        """Default config path is set correctly."""
        with patch.object(Path, 'exists', return_value=False):
            manager = WalletManager()
            assert "wallets.json" in str(manager.config_path)

    def test_init_loads_wallet_roles_correctly(self, wallet_manager):
        """Wallet roles are loaded as enum values."""
        treasury = wallet_manager.wallets[VALID_ADDRESS_1]
        assert treasury.role == WalletRole.TREASURY
        assert isinstance(treasury.role, WalletRole)

    def test_init_loads_wallet_status_correctly(self, wallet_manager):
        """Wallet status is loaded as enum value."""
        treasury = wallet_manager.wallets[VALID_ADDRESS_1]
        assert treasury.status == WalletStatus.ACTIVE
        assert isinstance(treasury.status, WalletStatus)


class TestWalletManagerLoadWallets:
    """Test _load_wallets method."""

    def test_load_handles_corrupted_json(self, empty_config_file):
        """Handle corrupted JSON gracefully."""
        # Write corrupted JSON
        empty_config_file.write_text("{ invalid json }")

        # Should not raise, just log error
        manager = WalletManager(config_path=empty_config_file)
        assert len(manager.wallets) == 0

    def test_load_handles_missing_optional_fields(self, empty_config_file):
        """Handle config with missing optional fields."""
        config = {
            'wallets': [{
                'name': 'Minimal',
                'address': VALID_ADDRESS_1,
                'role': 'trading',
                # Missing: status, daily_limit_sol, etc.
            }]
        }
        empty_config_file.write_text(json.dumps(config))

        manager = WalletManager(config_path=empty_config_file)
        wallet = manager.wallets[VALID_ADDRESS_1]
        assert wallet.status == WalletStatus.ACTIVE  # default
        assert wallet.daily_limit_sol == 1.0  # default


# === TESTS FOR WALLET MANAGER SAVE ===

class TestWalletManagerSaveWallets:
    """Test _save_wallets method."""

    def test_save_creates_parent_directory(self, empty_config_file):
        """Save creates parent directory if needed."""
        nested_path = empty_config_file.parent / "nested" / "deep" / "wallets.json"
        manager = WalletManager(config_path=nested_path)

        config = WalletConfig(
            name="Test",
            address=VALID_ADDRESS_1,
            role=WalletRole.TRADING,
        )
        manager.wallets[config.address] = config
        manager._save_wallets()

        assert nested_path.exists()

    def test_save_persists_all_wallet_data(self, wallet_manager, temp_config_file):
        """Save persists complete wallet data."""
        # Modify a wallet
        wallet_manager.wallets[VALID_ADDRESS_1].daily_limit_sol = 999.0
        wallet_manager._save_wallets()

        # Reload and verify
        with open(temp_config_file) as f:
            data = json.load(f)

        treasury = next(w for w in data['wallets'] if w['address'] == VALID_ADDRESS_1)
        assert treasury['daily_limit_sol'] == 999.0


# === TESTS FOR ADD WALLET ===

class TestWalletManagerAddWallet:
    """Test add_wallet method."""

    def test_add_valid_wallet(self, empty_wallet_manager, sample_wallet_config):
        """Add a valid wallet."""
        result = empty_wallet_manager.add_wallet(sample_wallet_config)

        assert result is True
        assert sample_wallet_config.address in empty_wallet_manager.wallets
        assert empty_wallet_manager.wallets[sample_wallet_config.address].name == "Test Wallet"

    def test_add_wallet_sets_created_at(self, empty_wallet_manager, sample_wallet_config):
        """Add wallet sets created_at timestamp."""
        empty_wallet_manager.add_wallet(sample_wallet_config)

        wallet = empty_wallet_manager.wallets[sample_wallet_config.address]
        assert wallet.created_at != ""
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(wallet.created_at.replace('Z', '+00:00'))

    def test_add_duplicate_wallet_fails(self, wallet_manager):
        """Cannot add wallet with duplicate address."""
        duplicate = WalletConfig(
            name="Duplicate",
            address=VALID_ADDRESS_1,  # Already exists
            role=WalletRole.TRADING,
        )
        result = wallet_manager.add_wallet(duplicate)

        assert result is False

    def test_add_invalid_address_fails(self, empty_wallet_manager):
        """Cannot add wallet with invalid address."""
        invalid = WalletConfig(
            name="Invalid",
            address=INVALID_ADDRESS_SHORT,
            role=WalletRole.TRADING,
        )
        result = empty_wallet_manager.add_wallet(invalid)

        assert result is False

    def test_add_wallet_saves_config(self, empty_wallet_manager, sample_wallet_config, empty_config_file):
        """Add wallet persists to config file."""
        empty_wallet_manager.add_wallet(sample_wallet_config)

        assert empty_config_file.exists()
        with open(empty_config_file) as f:
            data = json.load(f)
        assert len(data['wallets']) == 1


# === TESTS FOR REMOVE WALLET ===

class TestWalletManagerRemoveWallet:
    """Test remove_wallet method."""

    def test_remove_trading_wallet(self, wallet_manager):
        """Remove a trading wallet."""
        result = wallet_manager.remove_wallet(VALID_ADDRESS_2)

        assert result is True
        assert VALID_ADDRESS_2 not in wallet_manager.wallets

    def test_remove_treasury_wallet_fails(self, wallet_manager):
        """Cannot remove treasury wallet."""
        result = wallet_manager.remove_wallet(VALID_ADDRESS_1)

        assert result is False
        assert VALID_ADDRESS_1 in wallet_manager.wallets

    def test_remove_nonexistent_wallet(self, wallet_manager):
        """Remove nonexistent wallet returns False."""
        result = wallet_manager.remove_wallet("nonexistent_address")

        assert result is False


# === TESTS FOR UPDATE WALLET ===

class TestWalletManagerUpdateWallet:
    """Test update_wallet method."""

    def test_update_daily_limit(self, wallet_manager):
        """Update daily limit."""
        result = wallet_manager.update_wallet(VALID_ADDRESS_2, {'daily_limit_sol': 10.0})

        assert result is True
        assert wallet_manager.wallets[VALID_ADDRESS_2].daily_limit_sol == 10.0

    def test_update_status(self, wallet_manager):
        """Update wallet status."""
        result = wallet_manager.update_wallet(VALID_ADDRESS_2, {'status': 'paused'})

        assert result is True
        assert wallet_manager.wallets[VALID_ADDRESS_2].status == WalletStatus.PAUSED

    def test_update_role(self, wallet_manager):
        """Update wallet role."""
        result = wallet_manager.update_wallet(VALID_ADDRESS_2, {'role': 'hot'})

        assert result is True
        assert wallet_manager.wallets[VALID_ADDRESS_2].role == WalletRole.HOT_WALLET

    def test_update_multiple_fields(self, wallet_manager):
        """Update multiple fields at once."""
        updates = {
            'daily_limit_sol': 20.0,
            'single_tx_limit_sol': 5.0,
            'description': 'Updated description'
        }
        result = wallet_manager.update_wallet(VALID_ADDRESS_2, updates)

        assert result is True
        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        assert wallet.daily_limit_sol == 20.0
        assert wallet.single_tx_limit_sol == 5.0
        assert wallet.description == 'Updated description'

    def test_update_nonexistent_wallet(self, wallet_manager):
        """Update nonexistent wallet returns False."""
        result = wallet_manager.update_wallet("nonexistent", {'daily_limit_sol': 10.0})

        assert result is False

    def test_update_ignores_unknown_fields(self, wallet_manager):
        """Update ignores fields that don't exist on WalletConfig."""
        result = wallet_manager.update_wallet(VALID_ADDRESS_2, {'unknown_field': 'value'})

        assert result is True  # Operation succeeds but field is ignored


# === TESTS FOR GET WALLET ===

class TestWalletManagerGetWallet:
    """Test get_wallet method."""

    def test_get_existing_wallet(self, wallet_manager):
        """Get an existing wallet."""
        wallet = wallet_manager.get_wallet(VALID_ADDRESS_1)

        assert wallet is not None
        assert wallet.name == "Treasury"

    def test_get_nonexistent_wallet(self, wallet_manager):
        """Get nonexistent wallet returns None."""
        wallet = wallet_manager.get_wallet("nonexistent")

        assert wallet is None


# === TESTS FOR GET WALLETS BY ROLE ===

class TestWalletManagerGetWalletsByRole:
    """Test get_wallets_by_role method."""

    def test_get_treasury_wallets(self, wallet_manager):
        """Get all treasury wallets."""
        wallets = wallet_manager.get_wallets_by_role(WalletRole.TREASURY)

        assert len(wallets) == 1
        assert wallets[0].address == VALID_ADDRESS_1

    def test_get_trading_wallets(self, wallet_manager):
        """Get all trading wallets."""
        wallets = wallet_manager.get_wallets_by_role(WalletRole.TRADING)

        assert len(wallets) == 1
        assert wallets[0].address == VALID_ADDRESS_2

    def test_get_nonexistent_role(self, wallet_manager):
        """Get wallets for role with no wallets."""
        wallets = wallet_manager.get_wallets_by_role(WalletRole.COLD_STORAGE)

        assert len(wallets) == 0


# === TESTS FOR GET WALLET FOR ROLE ===

class TestWalletManagerGetWalletForRole:
    """Test get_wallet_for_role method."""

    def test_get_active_trading_wallet(self, wallet_manager):
        """Get active trading wallet."""
        wallet = wallet_manager.get_wallet_for_role(WalletRole.TRADING)

        assert wallet is not None
        assert wallet.role == WalletRole.TRADING
        assert wallet.status == WalletStatus.ACTIVE

    def test_get_wallet_excludes_inactive(self, wallet_manager):
        """Inactive wallets are excluded."""
        # Pause the trading wallet
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        wallet = wallet_manager.get_wallet_for_role(WalletRole.TRADING)

        assert wallet is None

    def test_get_wallet_for_empty_role(self, wallet_manager):
        """Get wallet for role with no active wallets."""
        wallet = wallet_manager.get_wallet_for_role(WalletRole.DEV)

        assert wallet is None


# === TESTS FOR GET ACTIVE WALLETS ===

class TestWalletManagerGetActiveWallets:
    """Test get_active_wallets method."""

    def test_get_all_active(self, wallet_manager):
        """Get all active wallets."""
        wallets = wallet_manager.get_active_wallets()

        assert len(wallets) == 2

    def test_excludes_paused_wallets(self, wallet_manager):
        """Paused wallets are excluded."""
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        wallets = wallet_manager.get_active_wallets()

        assert len(wallets) == 1
        assert wallets[0].address == VALID_ADDRESS_1


# === TESTS FOR SET STATUS ===

class TestWalletManagerSetStatus:
    """Test set_status method."""

    def test_set_to_paused(self, wallet_manager):
        """Set wallet to paused."""
        result = wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        assert result is True
        assert wallet_manager.wallets[VALID_ADDRESS_2].status == WalletStatus.PAUSED

    def test_set_to_locked(self, wallet_manager):
        """Set wallet to locked."""
        result = wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.LOCKED)

        assert result is True
        assert wallet_manager.wallets[VALID_ADDRESS_2].status == WalletStatus.LOCKED

    def test_set_status_nonexistent_wallet(self, wallet_manager):
        """Set status on nonexistent wallet."""
        result = wallet_manager.set_status("nonexistent", WalletStatus.PAUSED)

        assert result is False


# === TESTS FOR CAN TRADE ===

class TestWalletManagerCanTrade:
    """Test can_trade method."""

    def test_can_trade_within_limits(self, wallet_manager):
        """Trade within all limits."""
        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 0.5)

        assert can_trade is True
        assert reason == "OK"

    def test_cannot_trade_wallet_not_found(self, wallet_manager):
        """Cannot trade - wallet not found."""
        can_trade, reason = wallet_manager.can_trade("nonexistent", 0.5)

        assert can_trade is False
        assert "not found" in reason.lower()

    def test_cannot_trade_paused_wallet(self, wallet_manager):
        """Cannot trade - wallet paused."""
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 0.5)

        assert can_trade is False
        assert "paused" in reason.lower()

    def test_cannot_trade_locked_wallet(self, wallet_manager):
        """Cannot trade - wallet locked."""
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.LOCKED)

        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 0.5)

        assert can_trade is False
        assert "locked" in reason.lower()

    def test_cannot_trade_monitoring_wallet(self, empty_wallet_manager):
        """Cannot trade - monitoring wallet."""
        config = WalletConfig(
            name="Monitor",
            address=VALID_ADDRESS_3,
            role=WalletRole.MONITORING,
        )
        empty_wallet_manager.wallets[config.address] = config

        can_trade, reason = empty_wallet_manager.can_trade(VALID_ADDRESS_3, 0.1)

        assert can_trade is False
        assert "monitoring" in reason.lower()

    def test_cannot_trade_cold_storage(self, empty_wallet_manager):
        """Cannot trade - cold storage wallet."""
        config = WalletConfig(
            name="Cold",
            address=VALID_ADDRESS_3,
            role=WalletRole.COLD_STORAGE,
        )
        empty_wallet_manager.wallets[config.address] = config

        can_trade, reason = empty_wallet_manager.can_trade(VALID_ADDRESS_3, 0.1)

        assert can_trade is False
        assert "cold storage" in reason.lower()

    def test_cannot_trade_exceeds_single_tx_limit(self, wallet_manager):
        """Cannot trade - exceeds single transaction limit."""
        # Trading wallet has single_tx_limit_sol=1.0
        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 2.0)

        assert can_trade is False
        assert "tx limit" in reason.lower()

    def test_cannot_trade_exceeds_daily_limit(self, wallet_manager):
        """Cannot trade - would exceed daily limit."""
        # Trading wallet has daily_limit_sol=5.0
        # Record some trades first
        wallet_manager.record_trade(VALID_ADDRESS_2, 4.5)

        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 1.0)

        assert can_trade is False
        assert "daily limit" in reason.lower()

    def test_cannot_trade_blocked_token(self, empty_wallet_manager):
        """Cannot trade - token is blocked."""
        config = WalletConfig(
            name="Restricted",
            address=VALID_ADDRESS_3,
            role=WalletRole.TRADING,
            blocked_tokens=["BLOCKED_TOKEN"],
        )
        empty_wallet_manager.wallets[config.address] = config

        can_trade, reason = empty_wallet_manager.can_trade(
            VALID_ADDRESS_3, 0.1, token_mint="BLOCKED_TOKEN"
        )

        assert can_trade is False
        assert "blocked" in reason.lower()

    def test_cannot_trade_token_not_allowed(self, empty_wallet_manager):
        """Cannot trade - token not in allowed list."""
        config = WalletConfig(
            name="Limited",
            address=VALID_ADDRESS_3,
            role=WalletRole.TRADING,
            allowed_tokens=["ALLOWED_TOKEN"],  # Only this token allowed
        )
        empty_wallet_manager.wallets[config.address] = config

        can_trade, reason = empty_wallet_manager.can_trade(
            VALID_ADDRESS_3, 0.1, token_mint="OTHER_TOKEN"
        )

        assert can_trade is False
        assert "allowed" in reason.lower()

    def test_can_trade_allowed_token(self, empty_wallet_manager):
        """Can trade - token is in allowed list."""
        config = WalletConfig(
            name="Limited",
            address=VALID_ADDRESS_3,
            role=WalletRole.TRADING,
            allowed_tokens=["ALLOWED_TOKEN"],
        )
        empty_wallet_manager.wallets[config.address] = config

        can_trade, reason = empty_wallet_manager.can_trade(
            VALID_ADDRESS_3, 0.1, token_mint="ALLOWED_TOKEN"
        )

        assert can_trade is True


# === TESTS FOR RECORD TRADE ===

class TestWalletManagerRecordTrade:
    """Test record_trade method."""

    def test_record_trade_updates_spent(self, wallet_manager):
        """Record trade updates total spent."""
        wallet_manager.record_trade(VALID_ADDRESS_2, 0.5)

        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        assert wallet.total_spent_today_sol == 0.5

    def test_record_trade_updates_last_used(self, wallet_manager):
        """Record trade updates last used timestamp."""
        wallet_manager.record_trade(VALID_ADDRESS_2, 0.5)

        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        assert wallet.last_used is not None

    def test_record_trade_accumulates(self, wallet_manager):
        """Multiple trades accumulate."""
        wallet_manager.record_trade(VALID_ADDRESS_2, 0.5)
        wallet_manager.record_trade(VALID_ADDRESS_2, 0.3)

        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        assert wallet.total_spent_today_sol == pytest.approx(0.8)

    def test_record_trade_nonexistent_wallet(self, wallet_manager):
        """Record trade on nonexistent wallet does nothing."""
        # Should not raise
        wallet_manager.record_trade("nonexistent", 1.0)


# === TESTS FOR DAILY LIMIT RESET ===

class TestWalletManagerDailyLimitReset:
    """Test _maybe_reset_daily_limit method."""

    def test_reset_on_new_day(self, wallet_manager):
        """Daily limit resets on new day."""
        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        wallet.total_spent_today_sol = 3.0
        wallet.last_reset_date = "2020-01-01"  # Old date

        # This will trigger reset check
        wallet_manager.can_trade(VALID_ADDRESS_2, 0.1)

        assert wallet.total_spent_today_sol == 0.0
        assert wallet.last_reset_date == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_no_reset_same_day(self, wallet_manager):
        """No reset on same day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        wallet = wallet_manager.wallets[VALID_ADDRESS_2]
        wallet.total_spent_today_sol = 3.0
        wallet.last_reset_date = today

        wallet_manager._maybe_reset_daily_limit(wallet)

        assert wallet.total_spent_today_sol == 3.0


# === TESTS FOR ADDRESS VALIDATION ===

class TestWalletManagerValidateAddress:
    """Test _validate_address method."""

    def test_valid_address(self, wallet_manager):
        """Valid Solana address passes validation."""
        assert wallet_manager._validate_address(VALID_ADDRESS_1) is True
        assert wallet_manager._validate_address(VALID_ADDRESS_2) is True
        assert wallet_manager._validate_address(VALID_ADDRESS_3) is True

    def test_invalid_short_address(self, wallet_manager):
        """Short address fails validation."""
        assert wallet_manager._validate_address(INVALID_ADDRESS_SHORT) is False

    def test_invalid_characters(self, wallet_manager):
        """Invalid base58 characters fail validation."""
        # Note: base58 doesn't use 0, O, I, l
        assert wallet_manager._validate_address(INVALID_ADDRESS_INVALID_CHARS) is False

    def test_empty_address(self, wallet_manager):
        """Empty address fails validation."""
        assert wallet_manager._validate_address("") is False


# === TESTS FOR BALANCE MANAGEMENT ===

class TestWalletManagerBalance:
    """Test balance management methods."""

    def test_update_balance(self, wallet_manager):
        """Update wallet balance."""
        wallet_manager.update_balance(
            VALID_ADDRESS_1,
            sol_balance=10.5,
            token_balances={"token1": 100.0},
            usd_value=2100.0
        )

        balance = wallet_manager.balances[VALID_ADDRESS_1]
        assert balance.sol_balance == 10.5
        assert balance.usd_value == 2100.0
        assert balance.token_balances["token1"] == 100.0

    def test_update_balance_sets_timestamp(self, wallet_manager):
        """Update balance sets last_updated."""
        wallet_manager.update_balance(VALID_ADDRESS_1, sol_balance=5.0)

        balance = wallet_manager.balances[VALID_ADDRESS_1]
        assert balance.last_updated is not None

    def test_get_balance(self, wallet_manager):
        """Get cached balance."""
        wallet_manager.update_balance(VALID_ADDRESS_1, sol_balance=5.0)

        balance = wallet_manager.get_balance(VALID_ADDRESS_1)

        assert balance is not None
        assert balance.sol_balance == 5.0

    def test_get_balance_not_cached(self, wallet_manager):
        """Get balance returns None if not cached."""
        balance = wallet_manager.get_balance(VALID_ADDRESS_1)

        assert balance is None

    def test_get_total_balance(self, wallet_manager):
        """Get total balance across all wallets."""
        wallet_manager.update_balance(
            VALID_ADDRESS_1, sol_balance=10.0, usd_value=2000.0,
            token_balances={"token1": 100.0}
        )
        wallet_manager.update_balance(
            VALID_ADDRESS_2, sol_balance=5.0, usd_value=1000.0,
            token_balances={"token1": 50.0, "token2": 200.0}
        )

        total = wallet_manager.get_total_balance()

        assert total['total_sol'] == 15.0
        assert total['total_usd'] == 3000.0
        assert total['token_balances']['token1'] == 150.0
        assert total['token_balances']['token2'] == 200.0
        assert total['wallet_count'] == 2

    def test_get_total_balance_empty(self, empty_wallet_manager):
        """Get total balance with no balances cached."""
        total = empty_wallet_manager.get_total_balance()

        assert total['total_sol'] == 0.0
        assert total['total_usd'] == 0.0
        assert total['wallet_count'] == 0


# === TESTS FOR SUMMARY ===

class TestWalletManagerSummary:
    """Test get_summary method."""

    def test_get_summary(self, wallet_manager):
        """Get wallet summary."""
        summary = wallet_manager.get_summary()

        assert summary['total_wallets'] == 2
        assert summary['active_wallets'] == 2
        assert 'treasury' in summary['by_role']
        assert 'trading' in summary['by_role']

    def test_summary_by_role_counts(self, wallet_manager):
        """Summary includes correct counts per role."""
        summary = wallet_manager.get_summary()

        assert summary['by_role']['treasury']['count'] == 1
        assert summary['by_role']['treasury']['active'] == 1


# === TESTS FOR EXPORT ADDRESSES ===

class TestWalletManagerExportAddresses:
    """Test export_addresses method."""

    def test_export_all_addresses(self, wallet_manager):
        """Export all wallet addresses."""
        addresses = wallet_manager.export_addresses()

        assert len(addresses) == 2
        assert VALID_ADDRESS_1 in addresses
        assert VALID_ADDRESS_2 in addresses

    def test_export_by_role(self, wallet_manager):
        """Export addresses filtered by role."""
        addresses = wallet_manager.export_addresses(WalletRole.TREASURY)

        assert len(addresses) == 1
        assert VALID_ADDRESS_1 in addresses


# === TESTS FOR WALLET SELECTOR ===

class TestWalletSelector:
    """Test WalletSelector class."""

    def test_select_for_trade_trading_wallet(self, wallet_manager):
        """Select trading wallet for trade."""
        selector = WalletSelector(wallet_manager)

        wallet = selector.select_for_trade(0.5)

        assert wallet is not None
        assert wallet.role == WalletRole.TRADING

    def test_select_for_trade_fallback_to_hot(self, empty_wallet_manager):
        """Fall back to hot wallet if no trading wallet."""
        hot_wallet = WalletConfig(
            name="Hot",
            address=VALID_ADDRESS_3,
            role=WalletRole.HOT_WALLET,
            daily_limit_sol=5.0,
            single_tx_limit_sol=1.0,
        )
        empty_wallet_manager.wallets[hot_wallet.address] = hot_wallet

        selector = WalletSelector(empty_wallet_manager)
        wallet = selector.select_for_trade(0.5)

        assert wallet is not None
        assert wallet.role == WalletRole.HOT_WALLET

    def test_select_for_trade_no_valid_wallet(self, wallet_manager):
        """No valid wallet available for trade."""
        # Pause all trading/hot wallets
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        selector = WalletSelector(wallet_manager)
        wallet = selector.select_for_trade(0.5)

        assert wallet is None

    def test_select_for_trade_respects_limits(self, wallet_manager):
        """Selection respects trading limits."""
        # Request amount exceeds single tx limit
        selector = WalletSelector(wallet_manager)
        wallet = selector.select_for_trade(10.0)  # Trading wallet limit is 1.0

        assert wallet is None

    def test_select_for_trade_prefers_more_capacity(self, empty_wallet_manager):
        """Prefers wallet with more remaining capacity."""
        # Set today's date so daily limits aren't reset
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        wallet1 = WalletConfig(
            name="Trading1",
            address=VALID_ADDRESS_1,
            role=WalletRole.TRADING,
            daily_limit_sol=5.0,
            single_tx_limit_sol=2.0,
            total_spent_today_sol=4.0,  # Only 1.0 remaining
            last_reset_date=today,
        )
        wallet2 = WalletConfig(
            name="Trading2",
            address=VALID_ADDRESS_2,
            role=WalletRole.TRADING,
            daily_limit_sol=5.0,
            single_tx_limit_sol=2.0,
            total_spent_today_sol=1.0,  # 4.0 remaining
            last_reset_date=today,
        )
        empty_wallet_manager.wallets[wallet1.address] = wallet1
        empty_wallet_manager.wallets[wallet2.address] = wallet2

        selector = WalletSelector(empty_wallet_manager)
        wallet = selector.select_for_trade(0.5)

        # Should select wallet2 (more capacity)
        assert wallet.address == VALID_ADDRESS_2

    def test_select_for_monitoring(self, wallet_manager):
        """Select wallets for monitoring."""
        selector = WalletSelector(wallet_manager)

        wallets = selector.select_for_monitoring()

        assert len(wallets) == 2  # Both active

    def test_select_for_monitoring_includes_paused(self, wallet_manager):
        """Monitoring includes paused wallets."""
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.PAUSED)

        selector = WalletSelector(wallet_manager)
        wallets = selector.select_for_monitoring()

        assert len(wallets) == 2

    def test_select_for_monitoring_excludes_archived(self, wallet_manager):
        """Monitoring excludes archived wallets."""
        wallet_manager.set_status(VALID_ADDRESS_2, WalletStatus.ARCHIVED)

        selector = WalletSelector(wallet_manager)
        wallets = selector.select_for_monitoring()

        assert len(wallets) == 1


# === TESTS FOR SINGLETON ===

class TestGetWalletManager:
    """Test get_wallet_manager singleton."""

    def test_returns_wallet_manager(self):
        """Returns a WalletManager instance."""
        import core.wallet_manager as wm

        # Reset singleton
        wm._manager = None

        with patch.object(Path, 'exists', return_value=False):
            manager = get_wallet_manager()

        assert isinstance(manager, WalletManager)

    def test_returns_same_instance(self):
        """Returns the same instance on subsequent calls."""
        import core.wallet_manager as wm

        # Reset singleton
        wm._manager = None

        with patch.object(Path, 'exists', return_value=False):
            manager1 = get_wallet_manager()
            manager2 = get_wallet_manager()

        assert manager1 is manager2


# === TESTS FOR EDGE CASES ===

class TestWalletManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_save_handles_write_error(self, wallet_manager, temp_config_file):
        """Save handles write errors gracefully."""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            # Should not raise
            wallet_manager._save_wallets()

    def test_update_balance_with_no_tokens(self, wallet_manager):
        """Update balance with None token_balances."""
        wallet_manager.update_balance(VALID_ADDRESS_1, sol_balance=5.0)

        balance = wallet_manager.balances[VALID_ADDRESS_1]
        assert balance.token_balances == {}

    def test_can_trade_with_zero_amount(self, wallet_manager):
        """Can trade with zero amount."""
        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 0.0)

        assert can_trade is True

    def test_can_trade_with_empty_token_mint(self, wallet_manager):
        """Can trade with empty token mint."""
        can_trade, reason = wallet_manager.can_trade(VALID_ADDRESS_2, 0.5, token_mint="")

        # Empty string is falsy, so token checks are skipped
        assert can_trade is True

    def test_wallet_with_all_roles_blocked_for_trading(self, empty_wallet_manager):
        """Verify all non-trading roles are blocked."""
        blocked_roles = [WalletRole.MONITORING, WalletRole.COLD_STORAGE]

        for role in blocked_roles:
            config = WalletConfig(
                name=f"Test {role.value}",
                address=VALID_ADDRESS_3,
                role=role,
            )
            empty_wallet_manager.wallets[config.address] = config

            can_trade, reason = empty_wallet_manager.can_trade(VALID_ADDRESS_3, 0.1)
            assert can_trade is False, f"Role {role} should not be able to trade"

            del empty_wallet_manager.wallets[config.address]
