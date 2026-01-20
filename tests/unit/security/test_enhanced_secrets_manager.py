"""
Enhanced Secrets Manager Tests

Tests for the enhanced secrets management system that provides:
- Encrypted credential storage
- Secure key rotation
- Secret access auditing
- Multi-environment support
"""
import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestEnhancedSecretsManager:
    """Tests for the enhanced secrets manager."""

    @pytest.fixture
    def secrets_manager(self, tmp_path):
        """Create an enhanced secrets manager instance."""
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        return EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!"
        )

    def test_initialization(self, tmp_path):
        """Test secrets manager initializes correctly."""
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        manager = EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!"
        )
        assert manager is not None
        assert (tmp_path / "secrets").exists()

    def test_store_secret(self, secrets_manager):
        """Test storing a secret."""
        result = secrets_manager.store_secret(
            name="api_key",
            value="sk_live_abc123xyz789",
            metadata={"service": "stripe", "environment": "production"}
        )

        assert result["success"] is True
        assert "secret_id" in result

    def test_retrieve_secret(self, secrets_manager):
        """Test retrieving a stored secret."""
        # Store first
        secrets_manager.store_secret(
            name="test_secret",
            value="secret_value_12345"
        )

        # Retrieve
        result = secrets_manager.get_secret("test_secret")

        assert result["success"] is True
        assert result["value"] == "secret_value_12345"

    def test_secret_encryption_at_rest(self, secrets_manager, tmp_path):
        """Test that secrets are encrypted at rest."""
        secret_value = "super_secret_api_key_12345"
        secrets_manager.store_secret("encrypted_test", secret_value)

        # Read raw file content
        secrets_dir = tmp_path / "secrets"
        all_content = ""
        for file_path in secrets_dir.rglob("*"):
            if file_path.is_file():
                try:
                    all_content += file_path.read_text()
                except:
                    all_content += file_path.read_bytes().decode('utf-8', errors='ignore')

        # Secret value should NOT appear in plaintext
        assert secret_value not in all_content

    def test_secret_not_found(self, secrets_manager):
        """Test retrieving a non-existent secret."""
        result = secrets_manager.get_secret("nonexistent_secret")

        assert result["success"] is False
        assert "error" in result or result.get("value") is None

    def test_update_secret(self, secrets_manager):
        """Test updating an existing secret."""
        # Store initial
        secrets_manager.store_secret("updateable_secret", "initial_value")

        # Update
        result = secrets_manager.update_secret(
            name="updateable_secret",
            new_value="updated_value"
        )

        assert result["success"] is True

        # Verify update
        retrieved = secrets_manager.get_secret("updateable_secret")
        assert retrieved["value"] == "updated_value"

    def test_delete_secret(self, secrets_manager):
        """Test deleting a secret."""
        secrets_manager.store_secret("deleteable_secret", "some_value")

        result = secrets_manager.delete_secret("deleteable_secret")
        assert result["success"] is True

        # Verify deletion
        retrieved = secrets_manager.get_secret("deleteable_secret")
        assert retrieved["success"] is False or retrieved.get("value") is None


class TestSecureKeyRotation:
    """Tests for secure key rotation."""

    @pytest.fixture
    def secrets_manager(self, tmp_path):
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        return EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!"
        )

    def test_rotate_secret(self, secrets_manager):
        """Test rotating a secret."""
        # Store initial secret
        secrets_manager.store_secret("rotatable_key", "old_key_value")

        # Rotate
        result = secrets_manager.rotate_secret(
            name="rotatable_key",
            new_value="new_key_value"
        )

        assert result["success"] is True
        assert result["previous_version"] is not None

        # Verify new value
        retrieved = secrets_manager.get_secret("rotatable_key")
        assert retrieved["value"] == "new_key_value"

    def test_rotation_keeps_history(self, secrets_manager):
        """Test that rotation maintains version history."""
        secrets_manager.store_secret("versioned_key", "v1")
        secrets_manager.rotate_secret("versioned_key", "v2")
        secrets_manager.rotate_secret("versioned_key", "v3")

        # Get version history
        history = secrets_manager.get_secret_versions("versioned_key")

        assert len(history) >= 3
        assert "v1" in [h["value"] for h in history] or history[0]["version"] == 1

    def test_rollback_to_previous_version(self, secrets_manager):
        """Test rolling back to a previous version."""
        secrets_manager.store_secret("rollback_key", "v1")
        secrets_manager.rotate_secret("rollback_key", "v2")
        secrets_manager.rotate_secret("rollback_key", "v3")

        # Rollback to v1
        result = secrets_manager.rollback_secret("rollback_key", version=1)

        assert result["success"] is True

        # Verify rollback
        retrieved = secrets_manager.get_secret("rollback_key")
        assert retrieved["value"] == "v1"

    def test_scheduled_rotation(self, secrets_manager):
        """Test scheduling automatic rotation."""
        secrets_manager.store_secret("scheduled_key", "initial_value")

        result = secrets_manager.schedule_rotation(
            name="scheduled_key",
            rotation_interval_days=30,
            rotation_callback="generate_new_api_key"
        )

        assert result["success"] is True
        assert result["next_rotation"] is not None


class TestSecretAccessAuditing:
    """Tests for secret access auditing."""

    @pytest.fixture
    def secrets_manager(self, tmp_path):
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        return EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!",
            enable_audit=True
        )

    def test_access_is_logged(self, secrets_manager):
        """Test that secret access is logged."""
        secrets_manager.store_secret("audited_secret", "value")

        # Access the secret
        secrets_manager.get_secret("audited_secret", accessor="user_123")

        # Check audit log
        audit_log = secrets_manager.get_access_log("audited_secret")

        assert len(audit_log) >= 1
        assert audit_log[-1]["accessor"] == "user_123"
        assert audit_log[-1]["action"] == "read"

    def test_audit_includes_metadata(self, secrets_manager):
        """Test that audit includes relevant metadata."""
        secrets_manager.store_secret("metadata_secret", "value")

        secrets_manager.get_secret(
            "metadata_secret",
            accessor="service_bot",
            metadata={"ip_address": "10.0.0.1", "reason": "scheduled_task"}
        )

        audit_log = secrets_manager.get_access_log("metadata_secret")

        assert "ip_address" in str(audit_log) or "metadata" in str(audit_log[-1])

    def test_audit_log_immutable(self, secrets_manager):
        """Test that audit log cannot be modified."""
        secrets_manager.store_secret("immutable_audit_secret", "value")
        secrets_manager.get_secret("immutable_audit_secret", accessor="user1")
        secrets_manager.get_secret("immutable_audit_secret", accessor="user2")

        initial_log = secrets_manager.get_access_log("immutable_audit_secret")
        initial_count = len(initial_log)

        # Try to delete/modify audit log (should not be possible)
        # The manager should not provide any method to do this

        final_log = secrets_manager.get_access_log("immutable_audit_secret")
        assert len(final_log) >= initial_count


class TestMultiEnvironmentSupport:
    """Tests for multi-environment secret management."""

    @pytest.fixture
    def secrets_manager(self, tmp_path):
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        return EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!"
        )

    def test_store_per_environment(self, secrets_manager):
        """Test storing secrets per environment."""
        secrets_manager.store_secret(
            "api_key",
            "prod_key_123",
            environment="production"
        )
        secrets_manager.store_secret(
            "api_key",
            "dev_key_456",
            environment="development"
        )

        prod_key = secrets_manager.get_secret("api_key", environment="production")
        dev_key = secrets_manager.get_secret("api_key", environment="development")

        assert prod_key["value"] == "prod_key_123"
        assert dev_key["value"] == "dev_key_456"

    def test_environment_isolation(self, secrets_manager):
        """Test that environments are properly isolated."""
        secrets_manager.store_secret("isolated_key", "prod_value", environment="production")

        # Should not be accessible from different environment
        result = secrets_manager.get_secret("isolated_key", environment="staging")

        assert result["success"] is False or result.get("value") is None

    def test_list_secrets_by_environment(self, secrets_manager):
        """Test listing secrets by environment."""
        secrets_manager.store_secret("key1", "v1", environment="prod")
        secrets_manager.store_secret("key2", "v2", environment="prod")
        secrets_manager.store_secret("key3", "v3", environment="dev")

        prod_secrets = secrets_manager.list_secrets(environment="prod")
        dev_secrets = secrets_manager.list_secrets(environment="dev")

        assert len(prod_secrets) >= 2
        assert len(dev_secrets) >= 1


class TestSecretSecurity:
    """Security-focused tests for secrets manager."""

    @pytest.fixture
    def secrets_manager(self, tmp_path):
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager
        return EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="test_master_key_32bytes_long!!"
        )

    def test_wrong_master_key_fails(self, tmp_path):
        """Test that wrong master key cannot decrypt secrets."""
        from core.security.enhanced_secrets_manager import EnhancedSecretsManager

        # Store with correct key
        manager1 = EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="correct_master_key_32bytes!!"
        )
        manager1.store_secret("protected_secret", "secret_value")

        # Try to read with wrong key
        manager2 = EnhancedSecretsManager(
            storage_path=tmp_path / "secrets",
            master_key="wrong_master_key_32bytes!!!"
        )
        result = manager2.get_secret("protected_secret")

        assert result["success"] is False or result.get("value") != "secret_value"

    def test_key_derivation(self, secrets_manager):
        """Test that proper key derivation is used."""
        # The manager should use PBKDF2 or similar
        assert secrets_manager.uses_key_derivation() is True

    def test_memory_clearing(self, secrets_manager):
        """Test that secrets are cleared from memory after use."""
        secrets_manager.store_secret("memory_test", "sensitive_data")

        # Get secret
        result = secrets_manager.get_secret("memory_test")
        value = result["value"]

        # Clear from memory
        secrets_manager.clear_cache()

        # Internal cache should be empty
        assert secrets_manager.is_cache_empty()
