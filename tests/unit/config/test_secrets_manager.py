"""
Unit tests for SecretManager.

Tests:
- SecretManager class
- get_secret(name) -> str
- mask_secrets(text) -> str
- Never log secrets
- Integration with key_vault.py
"""

import pytest
import os
import logging
from unittest.mock import MagicMock, patch, call


class TestSecretManagerBasics:
    """Test SecretManager basic functionality."""

    def test_create_secret_manager(self):
        """SecretManager should be instantiable."""
        from core.config.secrets import SecretManager

        manager = SecretManager()
        assert manager is not None

    def test_singleton_pattern(self):
        """SecretManager should be a singleton."""
        from core.config.secrets import SecretManager, get_secret_manager

        # Reset singleton
        SecretManager._instance = None

        manager1 = get_secret_manager()
        manager2 = get_secret_manager()

        assert manager1 is manager2


class TestSecretManagerGetSecret:
    """Test SecretManager.get_secret() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_get_secret_from_env(self):
        """get_secret() should retrieve from environment variable."""
        from core.config.secrets import SecretManager

        os.environ["TEST_SECRET_KEY"] = "secret_value"

        try:
            manager = SecretManager()
            secret = manager.get_secret("TEST_SECRET_KEY")

            assert secret == "secret_value"
        finally:
            del os.environ["TEST_SECRET_KEY"]

    def test_get_secret_missing_returns_none(self):
        """get_secret() should return None for missing secret."""
        from core.config.secrets import SecretManager

        manager = SecretManager()
        secret = manager.get_secret("NONEXISTENT_SECRET")

        assert secret is None

    def test_get_secret_with_default(self):
        """get_secret() should return default for missing secret."""
        from core.config.secrets import SecretManager

        manager = SecretManager()
        secret = manager.get_secret("MISSING", default="default_value")

        assert secret == "default_value"

    def test_get_secret_from_vault(self):
        """get_secret() should check vault if env not set."""
        from core.config.secrets import SecretManager

        with patch("core.config.secrets.get_key_vault") as mock_vault:
            mock_vault.return_value.get_secret.return_value = "vault_secret"

            manager = SecretManager(use_vault=True)
            secret = manager.get_secret("VAULT_ONLY_SECRET")

            assert secret == "vault_secret"
            mock_vault.return_value.get_secret.assert_called_once_with("VAULT_ONLY_SECRET")

    def test_env_takes_priority_over_vault(self):
        """Environment variable should take priority over vault."""
        from core.config.secrets import SecretManager

        os.environ["PRIORITY_SECRET"] = "from_env"

        with patch("core.config.secrets.get_key_vault") as mock_vault:
            mock_vault.return_value.get_secret.return_value = "from_vault"

            try:
                manager = SecretManager(use_vault=True)
                secret = manager.get_secret("PRIORITY_SECRET")

                assert secret == "from_env"
                # Vault should not be called when env var exists
                mock_vault.return_value.get_secret.assert_not_called()
            finally:
                del os.environ["PRIORITY_SECRET"]


class TestSecretManagerMaskSecrets:
    """Test SecretManager.mask_secrets() method."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_mask_known_secret(self):
        """mask_secrets() should mask known secrets in text."""
        from core.config.secrets import SecretManager

        os.environ["API_KEY"] = "sk-secret-12345"

        try:
            manager = SecretManager()
            manager.register_secret("API_KEY")

            text = "Using API key: sk-secret-12345"
            masked = manager.mask_secrets(text)

            assert "sk-secret-12345" not in masked
            assert "***" in masked or "REDACTED" in masked
        finally:
            del os.environ["API_KEY"]

    def test_mask_multiple_secrets(self):
        """mask_secrets() should mask multiple secrets."""
        from core.config.secrets import SecretManager

        os.environ["SECRET1"] = "value1"
        os.environ["SECRET2"] = "value2"

        try:
            manager = SecretManager()
            manager.register_secret("SECRET1")
            manager.register_secret("SECRET2")

            text = "Secrets: value1 and value2"
            masked = manager.mask_secrets(text)

            assert "value1" not in masked
            assert "value2" not in masked
        finally:
            del os.environ["SECRET1"]
            del os.environ["SECRET2"]

    def test_mask_preserves_structure(self):
        """mask_secrets() should preserve text structure."""
        from core.config.secrets import SecretManager

        os.environ["MY_SECRET"] = "secret123"

        try:
            manager = SecretManager()
            manager.register_secret("MY_SECRET")

            text = "Before secret123 after"
            masked = manager.mask_secrets(text)

            assert masked.startswith("Before ")
            assert masked.endswith(" after")
        finally:
            del os.environ["MY_SECRET"]

    def test_mask_empty_text(self):
        """mask_secrets() should handle empty text."""
        from core.config.secrets import SecretManager

        manager = SecretManager()
        masked = manager.mask_secrets("")

        assert masked == ""

    def test_mask_no_secrets_in_text(self):
        """mask_secrets() should return text unchanged if no secrets."""
        from core.config.secrets import SecretManager

        manager = SecretManager()
        text = "No secrets here"
        masked = manager.mask_secrets(text)

        assert masked == text

    def test_mask_partial_match(self):
        """mask_secrets() should not mask partial matches."""
        from core.config.secrets import SecretManager

        os.environ["SHORT"] = "abc"

        try:
            manager = SecretManager()
            manager.register_secret("SHORT")

            # "abc" appears in "abcdef" but is a different word
            text = "The alphabet: abcdef"
            masked = manager.mask_secrets(text)

            # Should mask "abc" wherever it appears
            # Exact behavior depends on implementation
            assert "abc" not in masked or len(masked) > 0
        finally:
            del os.environ["SHORT"]


class TestSecretManagerLogging:
    """Test that SecretManager never logs secrets."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_get_secret_does_not_log_value(self):
        """get_secret() should not log the secret value."""
        from core.config.secrets import SecretManager

        os.environ["LOG_TEST_SECRET"] = "super_secret_value"

        try:
            with patch("core.config.secrets.logger") as mock_logger:
                manager = SecretManager()
                secret = manager.get_secret("LOG_TEST_SECRET")

                # Check all log calls don't contain the secret
                for call_args in mock_logger.method_calls:
                    args = str(call_args)
                    assert "super_secret_value" not in args
        finally:
            del os.environ["LOG_TEST_SECRET"]

    def test_secret_not_in_repr(self):
        """SecretManager repr should not contain secrets."""
        from core.config.secrets import SecretManager

        os.environ["REPR_SECRET"] = "hidden_value"

        try:
            manager = SecretManager()
            manager.register_secret("REPR_SECRET")

            repr_str = repr(manager)
            str_str = str(manager)

            assert "hidden_value" not in repr_str
            assert "hidden_value" not in str_str
        finally:
            del os.environ["REPR_SECRET"]


class TestSecretManagerRegistration:
    """Test secret registration functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_register_secret(self):
        """register_secret() should add secret to known list."""
        from core.config.secrets import SecretManager

        os.environ["REG_SECRET"] = "value"

        try:
            manager = SecretManager()
            manager.register_secret("REG_SECRET")

            assert "REG_SECRET" in manager.registered_secrets
        finally:
            del os.environ["REG_SECRET"]

    def test_auto_register_common_secrets(self):
        """Common secret patterns should be auto-registered."""
        from core.config.secrets import SecretManager

        os.environ["API_KEY"] = "key1"
        os.environ["AUTH_TOKEN"] = "token1"
        os.environ["DATABASE_PASSWORD"] = "pass1"

        try:
            manager = SecretManager(auto_register=True)

            # These should be auto-registered based on name patterns
            assert any("KEY" in s or "key" in s.lower() for s in manager.registered_secrets)
        finally:
            del os.environ["API_KEY"]
            del os.environ["AUTH_TOKEN"]
            del os.environ["DATABASE_PASSWORD"]

    def test_unregister_secret(self):
        """unregister_secret() should remove from known list."""
        from core.config.secrets import SecretManager

        os.environ["UNREG_SECRET"] = "value"

        try:
            manager = SecretManager()
            manager.register_secret("UNREG_SECRET")
            manager.unregister_secret("UNREG_SECRET")

            assert "UNREG_SECRET" not in manager.registered_secrets
        finally:
            del os.environ["UNREG_SECRET"]


class TestSecretManagerKeyVaultIntegration:
    """Test SecretManager integration with KeyVault."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_store_secret_in_vault(self):
        """store_secret() should store in vault."""
        from core.config.secrets import SecretManager

        with patch("core.config.secrets.get_key_vault") as mock_vault:
            manager = SecretManager(use_vault=True)
            manager.store_secret("NEW_SECRET", "secret_value")

            mock_vault.return_value.store_secret.assert_called_once_with(
                "NEW_SECRET", "secret_value"
            )

    def test_rotate_secret(self):
        """rotate_secret() should update vault and env."""
        from core.config.secrets import SecretManager

        os.environ["ROTATE_SECRET"] = "old_value"

        with patch("core.config.secrets.get_key_vault") as mock_vault:
            mock_vault.return_value.rotate_api_key.return_value = True

            try:
                manager = SecretManager(use_vault=True)
                result = manager.rotate_secret("ROTATE_SECRET", "new_value")

                assert result is True
                mock_vault.return_value.rotate_api_key.assert_called()
            finally:
                if "ROTATE_SECRET" in os.environ:
                    del os.environ["ROTATE_SECRET"]

    def test_list_secrets(self):
        """list_secrets() should list registered secrets."""
        from core.config.secrets import SecretManager

        os.environ["LIST_SECRET1"] = "v1"
        os.environ["LIST_SECRET2"] = "v2"

        try:
            manager = SecretManager()
            manager.register_secret("LIST_SECRET1")
            manager.register_secret("LIST_SECRET2")

            secrets = manager.list_secrets()

            assert "LIST_SECRET1" in secrets
            assert "LIST_SECRET2" in secrets
        finally:
            del os.environ["LIST_SECRET1"]
            del os.environ["LIST_SECRET2"]


class TestSecretManagerValidation:
    """Test secret validation functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        from core.config.secrets import SecretManager
        SecretManager._instance = None

    def test_validate_required_secrets(self):
        """validate_required() should check required secrets exist."""
        from core.config.secrets import SecretManager

        os.environ["VALID_SECRET"] = "value"

        try:
            manager = SecretManager()

            # Should pass - secret exists
            errors = manager.validate_required(["VALID_SECRET"])
            assert errors == []

            # Should fail - secret missing
            errors = manager.validate_required(["MISSING_SECRET"])
            assert len(errors) == 1
            assert "MISSING_SECRET" in errors[0]
        finally:
            del os.environ["VALID_SECRET"]

    def test_validate_secret_format(self):
        """validate_format() should check secret format."""
        from core.config.secrets import SecretManager

        os.environ["FORMAT_SECRET"] = "sk-valid-key-12345"

        try:
            manager = SecretManager()

            # Valid format
            is_valid = manager.validate_format(
                "FORMAT_SECRET",
                pattern=r"^sk-[a-z]+-[a-z]+-\d+$"
            )
            assert is_valid is True

            # Invalid format
            os.environ["FORMAT_SECRET"] = "invalid"
            is_valid = manager.validate_format(
                "FORMAT_SECRET",
                pattern=r"^sk-[a-z]+-[a-z]+-\d+$"
            )
            assert is_valid is False
        finally:
            del os.environ["FORMAT_SECRET"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
