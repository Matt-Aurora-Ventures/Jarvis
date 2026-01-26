"""Security testing suite for Phase 6 security infrastructure.

Tests the secret vault, encrypted keystore, input validation, and rate limiting.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Test imports
from core.secrets.vault import SecretVault, get_vault, reset_vault
from core.wallet.keystore import WalletKeystore
from core.validation import (
    validate_token_address,
    validate_amount,
    validate_percentage,
    validate_user_id,
    validate_callback_data,
    validate_sql_identifier,
    ValidationError,
)
from core.rate_limiting import RateLimiter, get_rate_limiter, reset_rate_limiter


class TestSecretVault:
    """Test suite for SecretVault."""
    
    def setup_method(self):
        """Reset vault before each test."""
        reset_vault()
    
    def teardown_method(self):
        """Clean up after tests."""
        reset_vault()
    
    def test_vault_loads_required_secrets(self):
        """Test that vault loads required secrets from environment."""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'test-api-key',
            'TELEGRAM_BOT_TOKEN': 'test-bot-token'
        }):
            vault = get_vault()
            assert vault.get('anthropic_api_key') == 'test-api-key'
            assert vault.get('telegram_bot_token') == 'test-bot-token'
    
    def test_vault_raises_on_missing_required_secret(self):
        """Test that vault raises error if required secret missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Required secrets missing"):
                SecretVault()
    
    def test_vault_allows_optional_secrets_missing(self):
        """Test that optional secrets can be missing."""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'test-key',
            'TELEGRAM_BOT_TOKEN': 'test-token'
        }):
            vault = get_vault()
            assert vault.get('bags_api_key') is None
            assert vault.is_set('bags_api_key') is False
    
    def test_vault_get_required_raises_on_none(self):
        """Test get_required raises if secret not set."""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'test-key',
            'TELEGRAM_BOT_TOKEN': 'test-token'
        }):
            vault = get_vault()
            with pytest.raises(ValueError, match="Required secret not set"):
                vault.get_required('bags_api_key')
    
    def test_vault_safe_repr(self):
        """Test that vault repr never exposes secret values."""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'secret-key-12345',
            'TELEGRAM_BOT_TOKEN': 'secret-token-67890'
        }):
            vault = get_vault()
            repr_str = repr(vault)
            assert 'secret-key' not in repr_str
            assert 'secret-token' not in repr_str
            assert 'SecretVault' in repr_str
    
    def test_vault_singleton(self):
        """Test that get_vault returns same instance."""
        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': 'test-key',
            'TELEGRAM_BOT_TOKEN': 'test-token'
        }):
            vault1 = get_vault()
            vault2 = get_vault()
            assert vault1 is vault2


class TestWalletKeystore:
    """Test suite for encrypted wallet keystore."""
    
    def test_keystore_encrypts_wallet(self):
        """Test that keystore encrypts wallet data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            keystore_path = Path(tmpdir) / "test_wallets.enc"
            keystore = WalletKeystore("test-password", keystore_path)
            
            # Store wallet
            private_key = b"test-private-key-data-12345"
            keystore.store_wallet("test_wallet", private_key)
            
            # Load it back
            loaded_key = keystore.load_wallet("test_wallet")
            assert loaded_key == private_key
    
    def test_keystore_wrong_password_fails(self):
        """Test that wrong password fails to decrypt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            keystore_path = Path(tmpdir) / "test_wallets.enc"
            
            # Store with one password
            keystore1 = WalletKeystore("password1", keystore_path)
            keystore1.store_wallet("wallet", b"secret-data")
            
            # Try to load with different password
            keystore2 = WalletKeystore("password2", keystore_path)
            with pytest.raises(ValueError, match="Incorrect master password"):
                keystore2.load_wallet("wallet")
    
    def test_keystore_list_wallets(self):
        """Test listing all wallet names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            keystore_path = Path(tmpdir) / "test_wallets.enc"
            keystore = WalletKeystore("test-password", keystore_path)
            
            keystore.store_wallet("wallet1", b"data1")
            keystore.store_wallet("wallet2", b"data2")
            
            wallets = keystore.list_wallets()
            assert set(wallets) == {"wallet1", "wallet2"}
    
    def test_keystore_remove_wallet(self):
        """Test removing wallet from keystore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            keystore_path = Path(tmpdir) / "test_wallets.enc"
            keystore = WalletKeystore("test-password", keystore_path)
            
            keystore.store_wallet("wallet1", b"data1")
            keystore.remove_wallet("wallet1")
            
            with pytest.raises(KeyError):
                keystore.load_wallet("wallet1")


class TestInputValidation:
    """Test suite for input validation functions."""
    
    def test_validate_token_address_valid(self):
        """Test valid Solana token address."""
        # Valid base58 address
        valid_addr = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        result = validate_token_address(valid_addr)
        assert result == valid_addr
    
    def test_validate_token_address_too_short(self):
        """Test that short addresses are rejected."""
        with pytest.raises(ValidationError, match="Invalid token address length"):
            validate_token_address("short")
    
    def test_validate_token_address_invalid_chars(self):
        """Test that non-base58 characters are rejected."""
        with pytest.raises(ValidationError, match="non-base58 characters"):
            validate_token_address("0" * 44)  # 0 is not in base58
    
    def test_validate_amount_valid(self):
        """Test valid amount validation."""
        result = validate_amount("10.5", min_val=0.0, max_val=100.0)
        assert float(result) == 10.5
    
    def test_validate_amount_below_min(self):
        """Test amount below minimum is rejected."""
        with pytest.raises(ValidationError, match="must be greater than"):
            validate_amount("0", min_val=0.0, max_val=100.0)
    
    def test_validate_amount_above_max(self):
        """Test amount above maximum is rejected."""
        with pytest.raises(ValidationError, match="must be less than"):
            validate_amount("200", min_val=0.0, max_val=100.0)
    
    def test_validate_percentage_valid(self):
        """Test valid percentage validation."""
        result = validate_percentage(25.5, min_val=0.0, max_val=100.0)
        assert result == 25.5
    
    def test_validate_user_id_valid(self):
        """Test valid Telegram user ID."""
        result = validate_user_id(12345)
        assert result == 12345
    
    def test_validate_user_id_negative(self):
        """Test negative user ID is rejected."""
        with pytest.raises(ValidationError, match="must be positive"):
            validate_user_id(-1)
    
    def test_validate_callback_data_valid(self):
        """Test valid callback data."""
        result = validate_callback_data("action:buy:token123")
        assert result == "action:buy:token123"
    
    def test_validate_callback_data_too_long(self):
        """Test callback data exceeding 64 bytes is rejected."""
        long_data = "x" * 100
        with pytest.raises(ValidationError, match="Callback data too long"):
            validate_callback_data(long_data)
    
    def test_validate_callback_data_forbidden_chars(self):
        """Test callback data with forbidden characters is rejected."""
        with pytest.raises(ValidationError, match="forbidden characters"):
            validate_callback_data("action;rm -rf /")  # Semicolon forbidden
    
    def test_sanitize_sql_identifier_valid(self):
        """Test valid SQL identifier."""
        result = sanitize_sql_identifier("table_name_123")
        assert result == "table_name_123"
    
    def test_sanitize_sql_identifier_invalid_chars(self):
        """Test SQL identifier with invalid characters is rejected."""
        with pytest.raises(ValidationError, match="Only alphanumeric"):
            sanitize_sql_identifier("table-name")  # Hyphen not allowed
    
    def test_sanitize_sql_identifier_sql_keyword(self):
        """Test SQL keywords are rejected as identifiers."""
        with pytest.raises(ValidationError, match="reserved keyword"):
            sanitize_sql_identifier("SELECT")


class TestRateLimiting:
    """Test suite for rate limiting."""
    
    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()
    
    def teardown_method(self):
        """Clean up after tests."""
        reset_rate_limiter()
    
    def test_rate_limiter_allows_within_limits(self):
        """Test that requests within limits are allowed."""
        limiter = get_rate_limiter(requests_per_minute=10, burst_size=3)
        user_id = 12345
        
        # First 3 requests should be allowed (within burst)
        assert limiter.check(user_id) is True
        assert limiter.check(user_id) is True
        assert limiter.check(user_id) is True
    
    def test_rate_limiter_blocks_burst(self):
        """Test that burst limit is enforced."""
        limiter = get_rate_limiter(requests_per_minute=100, burst_size=2)
        user_id = 12345
        
        # First 2 requests allowed
        assert limiter.check(user_id) is True
        assert limiter.check(user_id) is True
        
        # 3rd request in burst should be blocked
        assert limiter.check(user_id) is False
    
    def test_rate_limiter_per_user(self):
        """Test that rate limiting is per-user."""
        limiter = get_rate_limiter(requests_per_minute=10, burst_size=2)
        
        # User 1 hits burst limit
        assert limiter.check(111) is True
        assert limiter.check(111) is True
        assert limiter.check(111) is False
        
        # User 2 should still be allowed
        assert limiter.check(222) is True
        assert limiter.check(222) is True
    
    def test_rate_limiter_get_remaining(self):
        """Test getting remaining quota."""
        limiter = get_rate_limiter(requests_per_minute=10, burst_size=5)
        user_id = 12345
        
        # Make 2 requests
        limiter.check(user_id)
        limiter.check(user_id)
        
        remaining = limiter.get_remaining(user_id)
        assert remaining['burst_remaining'] <= 3
        assert remaining['minute_remaining'] <= 8
    
    def test_rate_limiter_reset_user(self):
        """Test resetting user rate limits."""
        limiter = get_rate_limiter(burst_size=1)
        user_id = 12345
        
        # Hit limit
        assert limiter.check(user_id) is True
        assert limiter.check(user_id) is False
        
        # Reset
        limiter.reset_user(user_id)
        
        # Should be allowed again
        assert limiter.check(user_id) is True
    
    def test_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
