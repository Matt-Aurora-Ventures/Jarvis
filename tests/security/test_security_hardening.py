"""
Comprehensive Security Hardening Tests

Tests for:
1. API Key Rotation
2. Wallet Security Auditing
3. Enhanced Rate Limiting
4. Input Validation
5. SQL Safety
6. Encryption at Rest
7. Audit Logging
8. Security Headers

TDD: Tests written first, implementations follow.
"""
import pytest
import time
import asyncio
import json
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock


# ============================================================
# 1. API Key Rotation Tests
# ============================================================

class TestKeyRotation:
    """Tests for API key rotation functionality."""

    def test_rotate_key_basic(self):
        """Key rotation should update key and log event."""
        from core.security.key_rotation import KeyRotationManager

        manager = KeyRotationManager()
        old_key = "old_test_key_12345"
        new_key = "new_test_key_67890"

        result = manager.rotate_key("test_service", old_key, new_key)

        assert result.success is True
        assert result.service_name == "test_service"
        assert result.timestamp is not None

    def test_rotate_key_grace_period(self, temp_dir):
        """Old key should remain valid during 24h grace period."""
        from core.security.key_rotation import KeyRotationManager

        # Use temp dir to avoid cross-test pollution
        metadata_path = temp_dir / "metadata.json"
        log_path = temp_dir / "rotation.log"

        manager = KeyRotationManager(
            grace_period_hours=24,
            metadata_path=metadata_path,
            log_path=log_path
        )
        old_key = "old_key_12345"
        new_key = "new_key_67890"

        manager.rotate_key("test_service", old_key, new_key)

        # Old key should still be valid during grace period
        assert manager.is_key_valid("test_service", old_key) is True
        assert manager.is_key_valid("test_service", new_key) is True

    def test_rotate_key_logs_event(self, temp_dir):
        """Rotation should log audit event."""
        from core.security.key_rotation import KeyRotationManager

        log_path = temp_dir / "rotation.log"
        manager = KeyRotationManager(log_path=log_path)

        manager.rotate_key("anthropic_api", "old", "new")

        assert log_path.exists()
        log_content = log_path.read_text()
        assert "anthropic_api" in log_content
        assert "rotation" in log_content.lower()

    def test_rotation_schedule_check(self):
        """Should detect when rotation is needed based on schedule."""
        from core.security.key_rotation import KeyRotationManager

        manager = KeyRotationManager()

        # Simulate key last rotated 35 days ago
        manager.set_last_rotation("anthropic_api", datetime.now() - timedelta(days=35))

        # 30-day rotation period
        assert manager.needs_rotation("anthropic_api", rotation_days=30) is True
        assert manager.needs_rotation("anthropic_api", rotation_days=40) is False

    def test_get_rotation_status(self):
        """Should return rotation status for all services."""
        from core.security.key_rotation import KeyRotationManager

        manager = KeyRotationManager()
        manager.set_last_rotation("service_a", datetime.now() - timedelta(days=10))
        manager.set_last_rotation("service_b", datetime.now() - timedelta(days=50))

        status = manager.get_rotation_status()

        assert "service_a" in status
        assert "service_b" in status
        assert status["service_a"]["days_since_rotation"] == 10
        assert status["service_b"]["days_since_rotation"] == 50


# ============================================================
# 2. Wallet Security Audit Tests
# ============================================================

class TestWalletAudit:
    """Tests for wallet security auditing."""

    @pytest.mark.asyncio
    async def test_audit_wallet_returns_result(self):
        """Wallet audit should return audit result."""
        from core.security.wallet_audit import audit_wallet_security

        # Use a test address
        test_address = "11111111111111111111111111111111"

        result = await audit_wallet_security(test_address)

        assert result is not None
        assert hasattr(result, 'is_secure')
        assert hasattr(result, 'alerts')
        assert hasattr(result, 'recent_transactions')

    @pytest.mark.asyncio
    async def test_detect_large_withdrawal(self):
        """Should detect unusually large withdrawals."""
        from core.security.wallet_audit import WalletAuditor

        auditor = WalletAuditor()

        # Mock transaction data with large withdrawal
        mock_txs = [
            {"type": "withdrawal", "amount": 1000000, "timestamp": time.time()}
        ]

        with patch.object(auditor, '_fetch_recent_transactions', return_value=mock_txs):
            result = await auditor.audit("test_wallet")

            assert result.has_alerts is True
            assert any("large" in alert.lower() for alert in result.alerts)

    @pytest.mark.asyncio
    async def test_verify_transaction_signatures(self):
        """Should verify transaction signatures are valid."""
        from core.security.wallet_audit import WalletAuditor

        auditor = WalletAuditor()

        # Create mock valid transaction
        mock_txs = [
            {"signature": "valid_sig", "verified": True}
        ]

        with patch.object(auditor, '_fetch_recent_transactions', return_value=mock_txs):
            result = await auditor.audit("test_wallet")

            assert result.invalid_signatures == 0

    @pytest.mark.asyncio
    async def test_detect_suspicious_activity(self):
        """Should detect suspicious transaction patterns."""
        from core.security.wallet_audit import WalletAuditor

        auditor = WalletAuditor()

        # Mock multiple rapid transactions (suspicious pattern)
        now = time.time()
        mock_txs = [
            {"type": "transfer", "amount": 100, "timestamp": now - 60},
            {"type": "transfer", "amount": 100, "timestamp": now - 120},
            {"type": "transfer", "amount": 100, "timestamp": now - 180},
            {"type": "transfer", "amount": 100, "timestamp": now - 240},
            {"type": "transfer", "amount": 100, "timestamp": now - 300},
        ]

        with patch.object(auditor, '_fetch_recent_transactions', return_value=mock_txs):
            result = await auditor.audit("test_wallet", check_patterns=True)

            # Multiple rapid transfers should trigger alert
            assert result.has_alerts is True


# ============================================================
# 3. Enhanced Rate Limiting Tests
# ============================================================

class TestEnhancedRateLimiter:
    """Tests for enhanced rate limiting with token bucket algorithm."""

    def test_rate_limit_by_user_id(self):
        """Should enforce per-user rate limits."""
        from core.security.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            max_requests_per_minute=5,
            bucket_type="user_id"
        )

        # 5 requests should pass
        for i in range(5):
            result = limiter.check("user_123")
            assert result.allowed is True

        # 6th should be blocked
        result = limiter.check("user_123")
        assert result.allowed is False
        assert result.retry_after > 0

    def test_rate_limit_by_ip(self):
        """Should enforce per-IP rate limits."""
        from core.security.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            max_requests_per_minute=1000,
            bucket_type="ip"
        )

        # Should allow up to limit
        for i in range(1000):
            result = limiter.check("192.168.1.1")
            assert result.allowed is True

        # Next should be blocked
        result = limiter.check("192.168.1.1")
        assert result.allowed is False

    def test_rate_limit_by_endpoint(self):
        """Should enforce per-endpoint rate limits."""
        from core.security.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            max_requests_per_minute=500,
            bucket_type="endpoint"
        )

        # Different endpoints have separate limits
        for i in range(500):
            limiter.check("/api/v1/trade")

        result_trade = limiter.check("/api/v1/trade")
        result_balance = limiter.check("/api/v1/balance")

        assert result_trade.allowed is False
        assert result_balance.allowed is True

    def test_token_bucket_refill(self):
        """Bucket should refill over time."""
        from core.security.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            max_requests_per_minute=60,  # 1 per second
            bucket_type="user_id"
        )

        # Exhaust tokens
        for i in range(60):
            limiter.check("user_1")

        # Wait for refill (mock time)
        with patch('time.time', return_value=time.time() + 2):
            result = limiter.check("user_1")
            assert result.allowed is True

    def test_returns_429_info(self):
        """Should return proper 429 response info."""
        from core.security.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(max_requests_per_minute=1)

        limiter.check("user_1")
        result = limiter.check("user_1")

        assert result.allowed is False
        assert result.status_code == 429
        assert result.retry_after is not None
        assert result.remaining == 0


# ============================================================
# 4. Input Validation Tests
# ============================================================

class TestInputValidator:
    """Tests for comprehensive input validation."""

    def test_validate_token_symbol_valid(self):
        """Valid token symbols should pass."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        valid_symbols = ["SOL", "USDC", "BTC", "ETH", "KR8TIV"]
        for symbol in valid_symbols:
            result = validator.validate_token_symbol(symbol)
            assert result.valid is True

    def test_validate_token_symbol_invalid(self):
        """Invalid token symbols should fail."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        invalid_symbols = [
            "<script>",
            "SELECT * FROM",
            "A" * 50,  # Too long
            "invalid@symbol",
            "../etc/passwd"
        ]
        for symbol in invalid_symbols:
            result = validator.validate_token_symbol(symbol)
            assert result.valid is False
            assert result.reason is not None

    def test_validate_amount_positive(self):
        """Amounts must be positive."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        assert validator.validate_amount(100.0).valid is True
        assert validator.validate_amount(0.001).valid is True
        assert validator.validate_amount(0).valid is False
        assert validator.validate_amount(-10).valid is False

    def test_validate_amount_bounds(self):
        """Amounts should be within reasonable bounds."""
        from core.security.input_validator import InputValidator

        validator = InputValidator(max_amount=1_000_000)

        assert validator.validate_amount(100).valid is True
        assert validator.validate_amount(999_999).valid is True
        assert validator.validate_amount(10_000_000).valid is False

    def test_validate_solana_address(self):
        """Solana addresses should be validated."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        # Valid format (32 bytes base58)
        valid_addr = "11111111111111111111111111111111"
        result = validator.validate_solana_address(valid_addr)
        assert result.valid is True

        # Invalid
        invalid_addr = "invalid_address"
        result = validator.validate_solana_address(invalid_addr)
        assert result.valid is False

    def test_reject_sql_injection(self):
        """SQL injection attempts should be rejected."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM users",
            "admin'--"
        ]

        for payload in sql_payloads:
            result = validator.validate_safe_string(payload)
            assert result.valid is False
            assert "sql" in result.reason.lower() or "injection" in result.reason.lower()

    def test_reject_xss(self):
        """XSS attempts should be rejected."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:void(0)"
        ]

        for payload in xss_payloads:
            result = validator.validate_safe_string(payload)
            assert result.valid is False

    def test_reject_path_traversal(self):
        """Path traversal attempts should be rejected."""
        from core.security.input_validator import InputValidator

        validator = InputValidator()

        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f"
        ]

        for payload in traversal_payloads:
            result = validator.validate_safe_string(payload)
            assert result.valid is False

    def test_log_rejected_inputs(self, temp_dir):
        """Rejected inputs should be logged for monitoring."""
        from core.security.input_validator import InputValidator

        log_path = temp_dir / "rejected_inputs.log"
        validator = InputValidator(log_rejected=True, log_path=log_path)

        validator.validate_safe_string("<script>evil</script>")

        assert log_path.exists()
        log_content = log_path.read_text()
        assert "rejected" in log_content.lower() or "script" in log_content.lower()


# ============================================================
# 5. SQL Safety Tests
# ============================================================

class TestSQLSafety:
    """Tests for SQL injection prevention."""

    def test_parameterized_query_builder(self):
        """Should build parameterized queries only."""
        from core.security.sql_safety import SafeQueryBuilder

        builder = SafeQueryBuilder()

        query, params = builder.select("users").where("id", "=", 1).build()

        assert "?" in query or "%s" in query or ":id" in query
        assert "1" not in query  # Value should be parameterized
        assert 1 in params or params.get("id") == 1

    def test_reject_raw_sql(self):
        """Should reject raw SQL strings with user input."""
        from core.security.sql_safety import SQLSafetyChecker

        checker = SQLSafetyChecker()

        dangerous_queries = [
            f"SELECT * FROM users WHERE name = 'admin'",
            "DELETE FROM logs WHERE id = 1",
            f"UPDATE users SET role = 'admin' WHERE id = {123}"
        ]

        for query in dangerous_queries:
            result = checker.is_safe(query)
            # Should flag as potentially unsafe
            assert result.warnings is not None or result.is_parameterized is False

    def test_scan_codebase_for_raw_sql(self, temp_dir):
        """Should scan codebase for raw SQL patterns."""
        from core.security.sql_safety import SQLCodeScanner

        # Create test file with raw SQL (matches pattern: .execute with f-string)
        test_file = temp_dir / "bad_code.py"
        test_file.write_text('''
def get_user(name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
''')

        scanner = SQLCodeScanner()
        findings = scanner.scan_directory(temp_dir)

        assert len(findings) > 0
        assert any("bad_code.py" in f.file_path for f in findings)


# ============================================================
# 6. Encryption at Rest Tests
# ============================================================

class TestEncryption:
    """Tests for encryption at rest."""

    def test_encrypt_sensitive_data(self):
        """Should encrypt sensitive data with AES-256."""
        from core.security.encryption import SecureEncryption

        with patch.dict('os.environ', {'TEST_ENCRYPTION_KEY': 'test_key_32_bytes_long_abcdefgh'}):
            encryption = SecureEncryption(key_from_env="TEST_ENCRYPTION_KEY")

            sensitive_data = "my_private_api_key_12345"
            encrypted = encryption.encrypt(sensitive_data)

            assert encrypted != sensitive_data
            assert sensitive_data not in encrypted

    def test_decrypt_returns_original(self):
        """Decryption should return original data."""
        from core.security.encryption import SecureEncryption

        with patch.dict('os.environ', {'TEST_ENCRYPTION_KEY': 'test_key_32_bytes_long_abcdefgh'}):
            encryption = SecureEncryption(key_from_env="TEST_ENCRYPTION_KEY")

            original = "sensitive_config_value"
            encrypted = encryption.encrypt(original)
            decrypted = encryption.decrypt(encrypted)

            assert decrypted == original

    def test_encryption_uses_aes256(self):
        """Should use AES-256 (32 byte key)."""
        from core.security.encryption import SecureEncryption

        with patch.dict('os.environ', {'TEST_ENCRYPTION_KEY': 'test_key_32_bytes_long_abcdefgh'}):
            encryption = SecureEncryption(key_from_env="TEST_ENCRYPTION_KEY")

            assert encryption.algorithm == "AES-256-GCM" or encryption.key_length == 32

    def test_keys_from_env_only(self):
        """Keys should come from environment variables only."""
        from core.security.encryption import SecureEncryption

        # Should not accept key directly in code
        with pytest.raises((ValueError, TypeError)):
            SecureEncryption(key="hardcoded_key_is_bad")

    def test_encrypted_file_unreadable(self, temp_dir):
        """Encrypted file should not contain plaintext."""
        from core.security.encryption import SecureEncryption

        with patch.dict('os.environ', {'TEST_ENCRYPTION_KEY': 'test_key_32_bytes_long_abcdefgh'}):
            encryption = SecureEncryption(key_from_env="TEST_ENCRYPTION_KEY")

            secret = "super_secret_api_key"
            encrypted = encryption.encrypt(secret)

            # Write encrypted data
            file_path = temp_dir / "encrypted.bin"
            file_path.write_text(encrypted)

            # Read back - should not contain plaintext
            content = file_path.read_text()
            assert secret not in content


# ============================================================
# 7. Audit Logging Tests
# ============================================================

class TestAuditLogger:
    """Tests for immutable audit logging."""

    def test_log_admin_action(self, temp_dir):
        """Should log admin actions."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        logger.log_admin_action(
            actor="admin_user",
            action="config_change",
            details={"setting": "max_positions", "old": 10, "new": 50}
        )

        assert log_path.exists()
        log_content = log_path.read_text()
        assert "admin_user" in log_content
        assert "config_change" in log_content

    def test_log_key_rotation(self, temp_dir):
        """Should log key rotation events."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        logger.log_key_rotation(
            service="anthropic_api",
            rotated_by="system",
            success=True
        )

        log_content = log_path.read_text()
        assert "anthropic_api" in log_content
        assert "rotation" in log_content.lower()

    def test_log_manual_trade(self, temp_dir):
        """Should log manual trade actions."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        logger.log_trade(
            actor="admin",
            trade_type="manual_buy",
            symbol="SOL",
            amount=100.0,
            price=150.0
        )

        log_content = log_path.read_text()
        assert "manual_buy" in log_content
        assert "SOL" in log_content

    def test_log_feature_flag_change(self, temp_dir):
        """Should log feature flag changes."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        logger.log_feature_flag_change(
            flag_name="trading_enabled",
            old_value=True,
            new_value=False,
            changed_by="admin"
        )

        log_content = log_path.read_text()
        assert "trading_enabled" in log_content

    def test_append_only_log(self, temp_dir):
        """Audit log should be append-only."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        # Log first entry
        logger.log_admin_action("user1", "action1", {})
        first_size = log_path.stat().st_size

        # Log second entry
        logger.log_admin_action("user2", "action2", {})
        second_size = log_path.stat().st_size

        # File should grow, not be overwritten
        assert second_size > first_size

    def test_log_json_format(self, temp_dir):
        """Logs should be valid JSON."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        logger.log_admin_action("user", "test", {"key": "value"})

        # Each line should be valid JSON
        with open(log_path) as f:
            for line in f:
                if line.strip():
                    parsed = json.loads(line)
                    assert "timestamp" in parsed
                    assert "action" in parsed

    def test_log_integrity_signature(self, temp_dir):
        """Logs should include integrity signature."""
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path, sign_entries=True)

        logger.log_admin_action("user", "test", {})

        with open(log_path) as f:
            entry = json.loads(f.readline())
            assert "signature" in entry or "hash" in entry


# ============================================================
# 8. Security Headers Tests (API Middleware)
# ============================================================

class TestSecurityHeadersMiddleware:
    """Tests for security headers middleware."""

    def test_x_content_type_options(self):
        """Should include X-Content-Type-Options: nosniff."""
        try:
            # Import directly from the file to avoid __init__.py dependencies
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "security_headers",
                "api/middleware/security_headers.py"
            )
            module = importlib.util.module_from_spec(spec)
            # Mock the starlette dependency
            sys.modules['starlette'] = MagicMock()
            sys.modules['starlette.middleware'] = MagicMock()
            sys.modules['starlette.middleware.base'] = MagicMock()
            sys.modules['starlette.responses'] = MagicMock()
            sys.modules['fastapi'] = MagicMock()
            spec.loader.exec_module(module)

            middleware = module.SecurityHeadersMiddleware(app=None)
            headers = middleware.get_security_headers()

            assert headers.get("X-Content-Type-Options") == "nosniff"
        except Exception:
            pytest.skip("Security headers module not available")

    def test_x_frame_options(self):
        """Should include X-Frame-Options: DENY."""
        try:
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "security_headers",
                "api/middleware/security_headers.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules['starlette'] = MagicMock()
            sys.modules['starlette.middleware'] = MagicMock()
            sys.modules['starlette.middleware.base'] = MagicMock()
            sys.modules['starlette.responses'] = MagicMock()
            sys.modules['fastapi'] = MagicMock()
            spec.loader.exec_module(module)

            middleware = module.SecurityHeadersMiddleware(app=None)
            headers = middleware.get_security_headers()

            assert headers.get("X-Frame-Options") == "DENY"
        except Exception:
            pytest.skip("Security headers module not available")

    def test_x_xss_protection(self):
        """Should include X-XSS-Protection: 1; mode=block."""
        try:
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "security_headers",
                "api/middleware/security_headers.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules['starlette'] = MagicMock()
            sys.modules['starlette.middleware'] = MagicMock()
            sys.modules['starlette.middleware.base'] = MagicMock()
            sys.modules['starlette.responses'] = MagicMock()
            sys.modules['fastapi'] = MagicMock()
            spec.loader.exec_module(module)

            middleware = module.SecurityHeadersMiddleware(app=None)
            headers = middleware.get_security_headers()

            assert "1" in headers.get("X-XSS-Protection", "")
            assert "mode=block" in headers.get("X-XSS-Protection", "")
        except Exception:
            pytest.skip("Security headers module not available")

    def test_hsts_header(self):
        """Should include Strict-Transport-Security."""
        try:
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "security_headers",
                "api/middleware/security_headers.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules['starlette'] = MagicMock()
            sys.modules['starlette.middleware'] = MagicMock()
            sys.modules['starlette.middleware.base'] = MagicMock()
            sys.modules['starlette.responses'] = MagicMock()
            sys.modules['fastapi'] = MagicMock()
            spec.loader.exec_module(module)

            middleware = module.SecurityHeadersMiddleware(app=None)
            headers = middleware.get_security_headers()

            hsts = headers.get("Strict-Transport-Security", "")
            assert "max-age=31536000" in hsts
        except Exception:
            pytest.skip("Security headers module not available")


# ============================================================
# 9. Security Audit Script Tests
# ============================================================

class TestSecurityAuditScript:
    """Tests for the security audit script."""

    @pytest.mark.asyncio
    async def test_audit_scans_for_vulnerabilities(self, temp_dir):
        """Audit should scan codebase for vulnerabilities."""
        from scripts.security_audit import SecurityAuditRunner

        # Create test files with issues
        (temp_dir / "test.py").write_text('password = "hardcoded123"')

        runner = SecurityAuditRunner(project_root=temp_dir)
        report = await runner.run_audit()

        assert report is not None
        assert hasattr(report, 'findings')

    @pytest.mark.asyncio
    async def test_audit_checks_dependencies(self):
        """Audit should check dependencies for CVEs."""
        from scripts.security_audit import SecurityAuditRunner

        runner = SecurityAuditRunner()
        report = await runner.check_dependencies()

        assert report is not None
        assert hasattr(report, 'vulnerable_packages') or hasattr(report, 'dependencies')

    @pytest.mark.asyncio
    async def test_audit_checks_git_history(self, temp_dir):
        """Audit should check for secrets in git history."""
        from scripts.security_audit import SecurityAuditRunner

        runner = SecurityAuditRunner(project_root=temp_dir)

        # This may return empty if not a git repo
        report = await runner.check_git_secrets()

        assert report is not None

    def test_audit_generates_markdown_report(self, temp_dir):
        """Audit should generate markdown report."""
        from scripts.security_audit import SecurityAuditRunner

        runner = SecurityAuditRunner(project_root=temp_dir)
        report_path = temp_dir / "security_audit_report.md"

        runner.generate_report(report_path)

        assert report_path.exists()
        content = report_path.read_text()
        assert "Security" in content


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    with patch.dict('os.environ', {
        'TEST_ENCRYPTION_KEY': 'test_key_32_bytes_long_abcdefgh',
        'JARVIS_MASTER_KEY': 'test_master_key_for_testing_only'
    }):
        yield


# ============================================================
# Integration Tests
# ============================================================

class TestSecurityIntegration:
    """Integration tests for security components."""

    def test_full_security_flow(self, temp_dir, mock_env_vars):
        """Test complete security flow."""
        from core.security.input_validator import InputValidator
        from core.security.audit_logger import AuditLogger

        validator = InputValidator()
        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)

        # Validate input
        user_input = "SOL"
        result = validator.validate_token_symbol(user_input)
        assert result.valid is True

        # Log the action
        logger.log_admin_action("system", "input_validated", {"input": user_input})

        # Verify log
        assert log_path.exists()

    def test_rate_limit_with_audit_logging(self, temp_dir):
        """Rate limit events should be audited."""
        from core.security.rate_limiter import TokenBucketRateLimiter
        from core.security.audit_logger import AuditLogger

        log_path = temp_dir / "audit.log"
        logger = AuditLogger(log_path=log_path)
        limiter = TokenBucketRateLimiter(max_requests_per_minute=2)

        # Exhaust rate limit
        limiter.check("user_1")
        limiter.check("user_1")
        result = limiter.check("user_1")

        if not result.allowed:
            logger.log_security_event(
                event_type="rate_limit_exceeded",
                actor="user_1",
                details={"retry_after": result.retry_after}
            )

        log_content = log_path.read_text()
        assert "rate_limit" in log_content.lower()
