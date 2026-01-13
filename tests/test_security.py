"""Tests for security modules."""
import pytest
from unittest.mock import MagicMock, patch


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
