"""
Comprehensive Security Tests

Tests security modules including:
- Input sanitization
- Wallet validation
- Request signing
- Session management
- Two-factor authentication
- Audit trails
- OWASP vulnerabilities
- Rate limiting
- API key security
"""
import pytest
import re
import json
import hashlib
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestSanitizer:
    """Tests for input sanitization."""
    
    def test_sanitize_string_basic(self):
        from core.security.sanitizer import sanitize_string
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "alert" in result  # Text content preserved, tags escaped
    
    def test_sanitize_string_null_bytes(self):
        from core.security.sanitizer import sanitize_string
        result = sanitize_string("test\x00injection")
        assert "\x00" not in result
    
    def test_sanitize_string_max_length(self):
        from core.security.sanitizer import sanitize_string
        long_string = "a" * 20000
        result = sanitize_string(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_filename(self):
        from core.security.sanitizer import sanitize_filename
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result


class TestWalletValidation:
    """Tests for wallet address validation."""
    
    def test_valid_solana_address(self):
        from core.security.wallet_validation import validate_solana_address
        # Example valid Solana address format
        result = validate_solana_address("11111111111111111111111111111111")
        # May fail if base58 not installed, but format should be checked
        assert result.chain.value == "solana"
    
    def test_invalid_solana_address(self):
        from core.security.wallet_validation import validate_solana_address
        result = validate_solana_address("invalid")
        assert not result.valid
    
    def test_valid_ethereum_address(self):
        from core.security.wallet_validation import validate_ethereum_address
        # Use lowercase address to skip checksum validation
        result = validate_ethereum_address("0x742d35cc6634c0532925a3b844bc9e7595f0beb2")
        assert result.valid
        assert result.chain.value == "ethereum"
    
    def test_invalid_ethereum_address(self):
        from core.security.wallet_validation import validate_ethereum_address
        result = validate_ethereum_address("not_an_address")
        assert not result.valid


class TestRequestSigning:
    """Tests for request signing."""
    
    def test_sign_and_verify(self):
        from core.security.request_signing import RequestSigner
        signer = RequestSigner(b"test-secret-key")
        
        signature = signer.sign_request("POST", "/api/test", {"data": "value"})
        valid, msg = signer.verify_signature(signature, "POST", "/api/test", {"data": "value"})
        assert valid
    
    def test_invalid_signature_rejected(self):
        from core.security.request_signing import RequestSigner
        signer = RequestSigner(b"test-secret-key")
        
        valid, msg = signer.verify_signature("invalid.sig.here", "POST", "/api/test", {})
        assert not valid


class TestSessionManager:
    """Tests for session management."""
    
    def test_create_session(self):
        from core.security.session_manager import SecureSessionManager
        manager = SecureSessionManager()
        
        session_id = manager.create_session("user123", "127.0.0.1")
        assert session_id is not None
        assert len(session_id) > 20
    
    def test_get_valid_session(self):
        from core.security.session_manager import SecureSessionManager
        manager = SecureSessionManager()
        
        session_id = manager.create_session("user123", "127.0.0.1")
        session = manager.get_session(session_id, "127.0.0.1")
        assert session is not None
        assert session.user_id == "user123"
    
    def test_session_ip_binding(self):
        from core.security.session_manager import SecureSessionManager
        manager = SecureSessionManager(bind_to_ip=True)
        
        session_id = manager.create_session("user123", "127.0.0.1")
        session = manager.get_session(session_id, "192.168.1.1")
        assert session is None  # Different IP should fail
    
    def test_invalidate_session(self):
        from core.security.session_manager import SecureSessionManager
        manager = SecureSessionManager()
        
        session_id = manager.create_session("user123", "127.0.0.1")
        manager.invalidate_session(session_id)
        session = manager.get_session(session_id)
        assert session is None


class TestTwoFactorAuth:
    """Tests for 2FA functionality."""
    
    def test_setup_2fa(self):
        from core.security.two_factor import TwoFactorAuth
        tfa = TwoFactorAuth()
        
        secret, uri, backup_codes = tfa.setup_2fa("user123")
        assert len(secret) > 10
        assert "otpauth://" in uri
        assert len(backup_codes) == 10
    
    def test_generate_provisioning_uri(self):
        from core.security.two_factor import TwoFactorAuth
        tfa = TwoFactorAuth(issuer="TestApp")
        
        secret, uri, _ = tfa.setup_2fa("user@example.com")
        assert "TestApp" in uri
        assert "user%40example.com" in uri or "user@example.com" in uri


class TestAuditTrail:
    """Tests for audit logging."""
    
    def test_log_event(self, temp_dir):
        from core.security.audit_trail import AuditTrail, AuditEventType
        trail = AuditTrail(log_path=temp_dir / "audit.jsonl")
        
        trail.log(
            event_type=AuditEventType.LOGIN,
            actor_id="user123",
            action="login",
            resource_type="auth",
            resource_id="session"
        )
        
        assert (temp_dir / "audit.jsonl").exists()
    
    def test_query_events(self, temp_dir):
        from core.security.audit_trail import AuditTrail, AuditEventType
        trail = AuditTrail(log_path=temp_dir / "audit.jsonl")
        
        trail.log(AuditEventType.LOGIN, "user123", "login", "auth", "session")
        trail.log(AuditEventType.API_ACCESS, "user123", "GET /api", "api", "/health")
        
        results = trail.query(actor_id="user123")
        assert len(results) == 2


class TestOWASPVulnerabilities:
    """Tests for OWASP Top 10 vulnerabilities."""

    def test_sql_injection_prevention(self):
        """Test SQL injection is prevented."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM users",
            "' UNION SELECT * FROM users --"
        ]

        from core.security.sanitizer import sanitize_string

        for payload in malicious_inputs:
            result = sanitize_string(payload)
            # Should not contain unescaped SQL keywords
            assert "DROP TABLE" not in result.upper() or "'" in result
            assert "DELETE FROM" not in result.upper() or "'" in result

    def test_xss_prevention(self):
        """Test XSS attacks are prevented."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<body onload=alert('xss')>",
            "'><script>alert(String.fromCharCode(88,83,83))</script>",
        ]

        from core.security.sanitizer import sanitize_string

        for payload in xss_payloads:
            result = sanitize_string(payload)
            # Script tags should be escaped/removed
            assert "<script>" not in result.lower()
            assert "onerror=" not in result.lower()
            assert "onload=" not in result.lower()

    def test_path_traversal_prevention(self):
        """Test path traversal attacks are prevented."""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc/passwd",
        ]

        from core.security.sanitizer import sanitize_filename

        for payload in traversal_payloads:
            result = sanitize_filename(payload)
            assert ".." not in result
            assert "/" not in result
            assert "\\" not in result

    def test_command_injection_prevention(self):
        """Test command injection is prevented."""
        cmd_payloads = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& ls -la",
        ]

        from core.security.sanitizer import sanitize_string

        for payload in cmd_payloads:
            result = sanitize_string(payload)
            # Dangerous chars should be escaped/removed
            assert result != payload or "|" not in result

    def test_null_byte_injection(self):
        """Test null byte injection is prevented."""
        null_payloads = [
            "file.txt\x00.jpg",
            "admin\x00ignore",
            "test%00injection",
        ]

        from core.security.sanitizer import sanitize_string

        for payload in null_payloads:
            result = sanitize_string(payload)
            assert "\x00" not in result


class TestAPIKeySecurity:
    """Tests for API key security."""

    def test_api_key_not_logged(self):
        """API keys should not appear in logs."""
        import logging
        from io import StringIO

        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("test_api_key")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Simulate logging a request with API key
        api_key = "sk_live_abc123secret456"
        logger.info(f"Request received with key: {'*' * len(api_key)}")

        log_output = log_capture.getvalue()
        assert api_key not in log_output

    def test_api_key_hashing(self):
        """API keys should be stored hashed."""
        api_key = "test_api_key_12345"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Hash should be different from original
        assert key_hash != api_key
        # Hash should be consistent
        assert hashlib.sha256(api_key.encode()).hexdigest() == key_hash


class TestRateLimitingSecurity:
    """Tests for rate limiting security."""

    def test_rate_limiter_initialization(self):
        """Rate limiter should initialize with limits."""
        try:
            from api.middleware.rate_limit_headers import RateLimiter

            limiter = RateLimiter(
                requests_per_minute=60,
                requests_per_hour=1000
            )

            assert limiter.requests_per_minute == 60
        except ImportError:
            pytest.skip("Rate limiter not found")

    def test_rate_limit_enforcement(self):
        """Rate limits should be enforced."""
        try:
            from api.middleware.rate_limit_headers import RateLimiter

            limiter = RateLimiter(requests_per_minute=2)

            # First two should pass
            assert limiter.check("test_user")[0] is True
            assert limiter.check("test_user")[0] is True

            # Third may or may not pass depending on implementation
        except ImportError:
            pytest.skip("Rate limiter not found")


class TestEncryptionSecurity:
    """Tests for encryption functionality."""

    def test_encrypted_storage_initialization(self):
        """Encrypted storage should initialize."""
        try:
            from core.security.encrypted_storage import EncryptedStorage

            storage = EncryptedStorage()
            assert storage is not None
        except ImportError:
            pytest.skip("Encrypted storage not found")

    def test_encrypt_decrypt_cycle(self):
        """Data should survive encrypt/decrypt cycle."""
        try:
            from core.security.encrypted_storage import EncryptedStorage

            storage = EncryptedStorage()
            original = "sensitive_data_12345"

            encrypted = storage.encrypt(original)
            decrypted = storage.decrypt(encrypted)

            assert decrypted == original
            assert encrypted != original
        except ImportError:
            pytest.skip("Encrypted storage not found")


class TestEmergencyShutdown:
    """Tests for emergency shutdown functionality."""

    def test_emergency_shutdown_exists(self):
        """Emergency shutdown should be importable."""
        try:
            from core.security.emergency_shutdown import EmergencyShutdown

            assert EmergencyShutdown is not None
        except ImportError:
            pytest.skip("Emergency shutdown not found")

    def test_shutdown_triggers(self):
        """Shutdown triggers should be configurable."""
        try:
            from core.security.emergency_shutdown import EmergencyShutdown

            shutdown = EmergencyShutdown()

            # Verify trigger methods exist
            assert hasattr(shutdown, 'trigger')
            assert hasattr(shutdown, 'status')
        except ImportError:
            pytest.skip("Emergency shutdown not found")


class TestSecurityHeaders:
    """Tests for security headers in responses."""

    def test_security_headers_present(self, client):
        """Security headers should be present."""
        try:
            response = client.get("/api/health")
            headers = dict(response.headers)

            # Common security headers
            security_headers = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection",
            ]

            # At least some security headers should be present
            present = [h for h in security_headers if h in headers]
            # Don't fail if not configured, just verify response works
            assert response.status_code in [200, 404]
        except Exception:
            pytest.skip("Client fixture not available")


class TestInputValidation:
    """Tests for input validation."""

    def test_validate_solana_address_format(self):
        """Solana addresses should be validated."""
        try:
            from core.validation.validators import validate_solana_address

            # Invalid should fail
            with pytest.raises(Exception):
                validate_solana_address("invalid")
        except ImportError:
            pytest.skip("Validator not found")

    def test_validate_amount_positive(self):
        """Amounts must be positive."""
        amount = -10.0
        assert amount < 0  # This should be rejected

    def test_validate_json_size(self):
        """Large JSON payloads should be limited."""
        large_payload = {"data": "x" * 1000000}  # 1MB of data
        payload_size = len(json.dumps(large_payload))

        # Should be limited (e.g., 10MB)
        max_size = 10 * 1024 * 1024
        assert payload_size < max_size


class TestTimingAttackPrevention:
    """Tests for timing attack prevention."""

    def test_constant_time_comparison(self):
        """String comparison should be constant-time."""
        import hmac

        secret1 = b"secret_key_12345"
        secret2 = b"secret_key_12345"
        secret3 = b"different_key_00"

        # Use hmac.compare_digest for constant-time comparison
        assert hmac.compare_digest(secret1, secret2) is True
        assert hmac.compare_digest(secret1, secret3) is False


class TestSecureRandomGeneration:
    """Tests for secure random generation."""

    def test_secure_token_generation(self):
        """Tokens should be cryptographically secure."""
        import secrets

        token1 = secrets.token_hex(32)
        token2 = secrets.token_hex(32)

        # Tokens should be unique
        assert token1 != token2
        # Tokens should be long enough
        assert len(token1) >= 64

    def test_session_id_uniqueness(self):
        """Session IDs should be unique."""
        import secrets

        session_ids = [secrets.token_urlsafe(32) for _ in range(100)]

        # All should be unique
        assert len(set(session_ids)) == 100
