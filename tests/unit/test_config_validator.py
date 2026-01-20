"""
Tests for Configuration Validator.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from core.config.validator import (
    ConfigValidator,
    ConfigValidationError,
    ValidationLevel,
    validate_config,
    get_validator,
)


@pytest.fixture
def validator():
    """Create fresh validator instance."""
    return ConfigValidator()


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment for testing."""
    # Clear all JARVIS-related env vars
    env_vars = [k for k in os.environ.keys() if any(
        prefix in k for prefix in [
            "TELEGRAM", "TREASURY", "JARVIS", "XAI", "ANTHROPIC",
            "X_", "SOLANA", "HELIUS", "BIRDEYE", "LIFEOS"
        ]
    )]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestTelegramValidation:
    """Test Telegram config validation."""

    def test_valid_telegram_token(self, validator):
        """Valid Telegram bot token."""
        is_valid, msg = validator._validate_telegram_token("123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        assert is_valid
        assert msg is None

    def test_invalid_telegram_token_format(self, validator):
        """Invalid token format."""
        is_valid, msg = validator._validate_telegram_token("invalid-token")
        assert not is_valid
        assert "format" in msg.lower()

    def test_empty_telegram_token(self, validator):
        """Empty token."""
        is_valid, msg = validator._validate_telegram_token("")
        assert not is_valid
        assert "required" in msg.lower()

    def test_valid_admin_ids(self, validator):
        """Valid admin ID list."""
        is_valid, msg = validator._validate_admin_ids("123456789,987654321")
        assert is_valid
        assert msg is None

    def test_single_admin_id(self, validator):
        """Single admin ID."""
        is_valid, msg = validator._validate_admin_ids("123456789")
        assert is_valid

    def test_invalid_admin_id_not_numeric(self, validator):
        """Non-numeric admin ID."""
        is_valid, msg = validator._validate_admin_ids("123456789,abc")
        assert not is_valid
        assert "numeric" in msg.lower()

    def test_invalid_admin_id_too_short(self, validator):
        """Admin ID too short."""
        is_valid, msg = validator._validate_admin_ids("123")
        assert not is_valid
        assert "length" in msg.lower()

    def test_valid_chat_id_positive(self, validator):
        """Valid positive chat ID."""
        is_valid, msg = validator._validate_chat_id("123456789")
        assert is_valid

    def test_valid_chat_id_negative(self, validator):
        """Valid negative chat ID (group)."""
        is_valid, msg = validator._validate_chat_id("-1001234567890")
        assert is_valid

    def test_invalid_chat_id(self, validator):
        """Invalid chat ID."""
        is_valid, msg = validator._validate_chat_id("not-a-number")
        assert not is_valid
        assert "numeric" in msg.lower()


class TestWalletValidation:
    """Test wallet config validation."""

    def test_valid_solana_address(self, validator):
        """Valid Solana address."""
        # Example Solana address (base58, 32-44 chars)
        address = "7EqQdEULxWcraVx3mXKFjc84LhCkMGZCkRuDpvcMwJeK"
        is_valid, msg = validator._validate_solana_address(address)
        assert is_valid
        assert msg is None

    def test_invalid_solana_address_too_short(self, validator):
        """Address too short."""
        is_valid, msg = validator._validate_solana_address("123")
        assert not is_valid
        assert "format" in msg.lower()

    def test_invalid_solana_address_invalid_chars(self, validator):
        """Address with invalid characters."""
        is_valid, msg = validator._validate_solana_address("0OIl" * 10)  # Contains 0, O, I, l
        assert not is_valid

    def test_valid_wallet_path(self, validator):
        """Valid wallet keypair file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Write valid keypair JSON (64-byte array)
            import json
            keypair = [0] * 64  # Dummy keypair
            json.dump(keypair, f)
            temp_path = f.name

        try:
            is_valid, msg = validator._validate_wallet_path(temp_path)
            assert is_valid
            assert msg is None
        finally:
            Path(temp_path).unlink()

    def test_wallet_path_not_exists(self, validator):
        """Wallet file doesn't exist."""
        is_valid, msg = validator._validate_wallet_path("/nonexistent/wallet.json")
        assert not is_valid
        assert "does not exist" in msg.lower()

    def test_wallet_path_invalid_json(self, validator):
        """Wallet file is not valid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json")
            temp_path = f.name

        try:
            is_valid, msg = validator._validate_wallet_path(temp_path)
            assert not is_valid
            assert "json" in msg.lower()
        finally:
            Path(temp_path).unlink()

    def test_wallet_path_wrong_format(self, validator):
        """Wallet file is not 64-byte array."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump([1, 2, 3], f)  # Wrong size
            temp_path = f.name

        try:
            is_valid, msg = validator._validate_wallet_path(temp_path)
            assert not is_valid
            assert "64 bytes" in msg.lower()
        finally:
            Path(temp_path).unlink()

    def test_valid_password_strong(self, validator):
        """Strong password."""
        is_valid, msg = validator._validate_password("MyStrongPass123!")
        assert is_valid

    def test_password_too_short(self, validator):
        """Password too short."""
        is_valid, msg = validator._validate_password("Short1")
        assert not is_valid
        assert "12 characters" in msg

    def test_password_weak(self, validator):
        """Password missing complexity."""
        is_valid, msg = validator._validate_password("alllowercase123")
        assert not is_valid
        assert "uppercase" in msg.lower()


class TestAPIKeyValidation:
    """Test API key validation."""

    def test_valid_xai_key(self, validator):
        """Valid XAI API key."""
        key = "xai-" + "a" * 40
        is_valid, msg = validator._validate_api_key(key, "xai")
        assert is_valid

    def test_invalid_xai_key(self, validator):
        """Invalid XAI key format."""
        is_valid, msg = validator._validate_api_key("invalid-key", "xai")
        assert not is_valid

    def test_valid_anthropic_key(self, validator):
        """Valid Anthropic key."""
        key = "sk-ant-" + "a" * 40
        is_valid, msg = validator._validate_api_key(key, "anthropic")
        assert is_valid

    def test_valid_generic_key(self, validator):
        """Valid generic API key."""
        key = "a" * 30
        is_valid, msg = validator._validate_api_key(key, "generic")
        assert is_valid

    def test_invalid_generic_key_too_short(self, validator):
        """Generic key too short."""
        is_valid, msg = validator._validate_api_key("short", "generic")
        assert not is_valid


class TestURLValidation:
    """Test URL validation."""

    def test_valid_https_url(self, validator):
        """Valid HTTPS URL."""
        is_valid, msg = validator._validate_url("https://api.mainnet-beta.solana.com")
        assert is_valid

    def test_valid_http_url(self, validator):
        """Valid HTTP URL."""
        is_valid, msg = validator._validate_url("http://localhost:8899")
        assert is_valid

    def test_valid_url_with_port(self, validator):
        """URL with port number."""
        is_valid, msg = validator._validate_url("https://api.example.com:8080/path")
        assert is_valid

    def test_invalid_url_no_protocol(self, validator):
        """URL without protocol."""
        is_valid, msg = validator._validate_url("api.example.com")
        assert not is_valid

    def test_invalid_url_format(self, validator):
        """Invalid URL format."""
        is_valid, msg = validator._validate_url("not a url")
        assert not is_valid


class TestNumericValidation:
    """Test numeric value validation."""

    def test_valid_float_in_range(self, validator):
        """Valid float in range."""
        is_valid, msg = validator._validate_float_range("5.5", min_val=0.0, max_val=10.0)
        assert is_valid

    def test_float_below_min(self, validator):
        """Float below minimum."""
        is_valid, msg = validator._validate_float_range("-1.0", min_val=0.0, max_val=10.0)
        assert not is_valid
        assert "minimum" in msg.lower()

    def test_float_above_max(self, validator):
        """Float above maximum."""
        is_valid, msg = validator._validate_float_range("20.0", min_val=0.0, max_val=10.0)
        assert not is_valid
        assert "maximum" in msg.lower()

    def test_invalid_float(self, validator):
        """Not a valid float."""
        is_valid, msg = validator._validate_float_range("not-a-number", min_val=0.0)
        assert not is_valid
        assert "invalid number" in msg.lower()

    def test_valid_port(self, validator):
        """Valid port number."""
        is_valid, msg = validator._validate_port("8080")
        assert is_valid

    def test_port_below_range(self, validator):
        """Port below 1."""
        is_valid, msg = validator._validate_port("0")
        assert not is_valid
        assert "range" in msg.lower()

    def test_port_above_range(self, validator):
        """Port above 65535."""
        is_valid, msg = validator._validate_port("99999")
        assert not is_valid
        assert "range" in msg.lower()


class TestBooleanValidation:
    """Test boolean validation."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "1", "on"])
    def test_valid_true_values(self, validator, value):
        """Valid true values."""
        is_valid, msg = validator._validate_boolean(value)
        assert is_valid

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "0", "off"])
    def test_valid_false_values(self, validator, value):
        """Valid false values."""
        is_valid, msg = validator._validate_boolean(value)
        assert is_valid

    def test_invalid_boolean(self, validator):
        """Invalid boolean value."""
        is_valid, msg = validator._validate_boolean("maybe")
        assert not is_valid


class TestFullValidation:
    """Test full configuration validation."""

    def test_minimal_valid_config(self, clean_env):
        """Minimal valid configuration."""
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")

        validator = ConfigValidator()
        is_valid, results = validator.validate(strict=False)

        # Should be valid with just required fields
        assert is_valid
        # May or may not have warnings depending on optional fields
        # (some optional fields won't trigger warnings if not set)

    def test_missing_required_config_strict(self, clean_env):
        """Missing required config in strict mode."""
        validator = ConfigValidator()

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate(strict=True)

        assert len(exc_info.value.errors) > 0
        assert any("TELEGRAM_BOT_TOKEN" in e.key for e in exc_info.value.errors)

    def test_missing_required_config_non_strict(self, clean_env):
        """Missing required config in non-strict mode."""
        validator = ConfigValidator()
        is_valid, results = validator.validate(strict=False)

        assert not is_valid
        errors = [r for r in results if r.level == ValidationLevel.ERROR]
        assert len(errors) > 0

    def test_conflicting_wallet_config(self, clean_env):
        """Both wallet path and private key set."""
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")
        clean_env.setenv("TREASURY_WALLET_PATH", "/path/to/wallet.json")
        clean_env.setenv("WALLET_PRIVATE_KEY", "a" * 44)

        validator = ConfigValidator()
        is_valid, results = validator.validate(strict=False)

        # Should warn about conflicting config
        warnings = [r for r in results if "WALLET_CONFIG" in r.key]
        assert len(warnings) > 0

    def test_incomplete_twitter_api_config(self, clean_env):
        """Twitter API key without secret."""
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")
        clean_env.setenv("X_API_KEY", "a" * 25)
        # Missing X_API_SECRET

        validator = ConfigValidator()
        is_valid, results = validator.validate(strict=False)

        # Should warn about missing X_API_SECRET
        warnings = [r for r in results if "X_API_CONFIG" in r.key]
        assert len(warnings) > 0

    def test_full_valid_config(self, clean_env):
        """Fully configured system."""
        # Set all required
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")

        # Set optional but common
        clean_env.setenv("XAI_API_KEY", "xai-" + "a" * 40)
        clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "a" * 40)
        clean_env.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        clean_env.setenv("TREASURY_LIVE_MODE", "false")

        validator = ConfigValidator()
        is_valid, results = validator.validate(strict=False)

        # Should be valid
        assert is_valid
        # Might still have some info/warnings about other optional fields


class TestGroupSummary:
    """Test configuration group summary."""

    def test_group_summary_empty(self, clean_env):
        """Group summary with no config."""
        validator = ConfigValidator()
        groups = validator.get_group_summary()

        assert "telegram" in groups
        assert "wallet" in groups
        assert groups["telegram"]["configured"] == 0
        assert groups["telegram"]["missing"] > 0

    def test_group_summary_partial(self, clean_env):
        """Group summary with partial config."""
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")

        validator = ConfigValidator()
        groups = validator.get_group_summary()

        # Telegram group should have some configured
        assert groups["telegram"]["configured"] >= 2
        # Other groups should be mostly empty
        assert groups["apis"]["configured"] == 0


class TestValidationSummary:
    """Test validation summary formatting."""

    def test_summary_no_errors(self, validator):
        """Summary with no validation errors."""
        summary = validator.get_validation_summary([])
        assert "valid" in summary.lower()

    def test_summary_with_errors(self, validator):
        """Summary with errors."""
        from core.config.validator import ValidationResult

        results = [
            ValidationResult(
                key="TEST_KEY",
                level=ValidationLevel.ERROR,
                message="Test error",
                is_valid=False
            )
        ]

        summary = validator.get_validation_summary(results)
        assert "ERROR" in summary
        assert "TEST_KEY" in summary


class TestCLIMode:
    """Test CLI validation mode."""

    def test_cli_execution(self, clean_env, capsys):
        """Test running validator from CLI."""
        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "123456789")

        from core.config.validator import print_validation_summary
        print_validation_summary()

        captured = capsys.readouterr()
        assert "Configuration" in captured.out
        assert "by Group" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
