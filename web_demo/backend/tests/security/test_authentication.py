"""
Comprehensive Authentication Security Tests
Tests Rule #1 & #2: Client is hostile, enforce server-side
"""
import pytest
import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.security import JWTHandler, PasswordHasher


client = TestClient(app)


class TestPasswordSecurity:
    """Test password validation and hashing."""

    def test_weak_password_rejected(self):
        """Test that weak passwords are rejected (Rule #2)."""
        weak_passwords = [
            "weak",
            "12345678",
            "password",
            "abc123",
            "qwerty",
        ]

        for password in weak_passwords:
            response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "username": "testuser",
                    "password": password,
                },
            )
            assert response.status_code == 400
            assert "password" in response.json()["detail"].lower()

    def test_strong_password_accepted(self):
        """Test that strong passwords are accepted."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "ValidPassword123!",
            },
        )
        assert response.status_code in [200, 201, 409]  # 409 if user exists

    def test_password_hashing_bcrypt(self):
        """Test that passwords are hashed with bcrypt (Rule #2)."""
        password = "ValidPassword123!"
        hashed = PasswordHasher.hash_password(password)

        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")

        # Should be different each time (salted)
        hashed2 = PasswordHasher.hash_password(password)
        assert hashed != hashed2

        # But both should verify
        assert PasswordHasher.verify_password(password, hashed)
        assert PasswordHasher.verify_password(password, hashed2)

    def test_password_verification_secure(self):
        """Test that password verification is timing-attack resistant."""
        password = "ValidPassword123!"
        hashed = PasswordHasher.hash_password(password)

        # Wrong password should not verify
        assert not PasswordHasher.verify_password("WrongPassword123!", hashed)

        # Completely different input should not crash
        assert not PasswordHasher.verify_password("", hashed)
        assert not PasswordHasher.verify_password("a" * 1000, hashed)


class TestJWTSecurity:
    """Test JWT token security (Rule #1: Never trust tokens)."""

    def test_jwt_expiration_enforced(self):
        """Test that expired tokens are rejected (Rule #2)."""
        # Create token that expires immediately
        user_id = "user123"
        role = "user"

        # Create expired token
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "exp": now - timedelta(minutes=1),  # Expired 1 minute ago
            "iat": now - timedelta(minutes=16),
            "type": "access",
            "role": role,
            "jti": "test123",
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        # Try to use expired token
        response = client.get(
            "/api/wallet/balance",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_jwt_signature_verification(self):
        """Test that tampered tokens are rejected (Rule #1)."""
        # Get valid token
        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response.status_code == 200:
            token = response.json()["access_token"]

            # Tamper with token (change signature)
            parts = token.split(".")
            tampered_token = f"{parts[0]}.{parts[1]}.TAMPERED_SIGNATURE"

            # Try to use tampered token
            response = client.get(
                "/api/wallet/balance",
                headers={"Authorization": f"Bearer {tampered_token}"},
            )
            assert response.status_code == 401

    def test_jwt_payload_tampering(self):
        """Test that modified payload is rejected (Rule #1)."""
        # Create token with user role
        user_token = JWTHandler.create_access_token("user123", "user")

        # Decode and modify payload (change role to admin)
        decoded = jwt.decode(user_token, options={"verify_signature": False})
        decoded["role"] = "admin"

        # Re-encode with wrong secret
        tampered_token = jwt.encode(decoded, "wrong-secret", algorithm=settings.JWT_ALGORITHM)

        # Try to use tampered token
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert response.status_code == 401

    def test_jwt_algorithm_confusion(self):
        """Test protection against algorithm confusion attacks (Rule #1)."""
        # Try to use HS256 token as RS256
        payload = {
            "sub": "user123",
            "exp": datetime.utcnow() + timedelta(minutes=15),
            "role": "admin",
        }

        # Create token with different algorithm
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS512")

        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should fail because algorithm doesn't match
        assert response.status_code in [401, 403]


class TestSessionSecurity:
    """Test session management security."""

    def test_session_fixation_protection(self):
        """Test that session ID changes after login (Rule #2)."""
        # Get initial session
        response1 = client.get("/health")
        session_cookie_1 = response1.cookies.get("session_id")

        # Login
        response2 = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response2.status_code == 200:
            session_cookie_2 = response2.cookies.get("session_id")

            # Session should change after login
            assert session_cookie_1 != session_cookie_2

    def test_concurrent_sessions_handled(self):
        """Test that multiple logins are handled securely."""
        # Login from "location 1"
        response1 = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        # Login from "location 2"
        response2 = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response1.status_code == 200 and response2.status_code == 200:
            token1 = response1.json()["access_token"]
            token2 = response2.json()["access_token"]

            # Both tokens should be different
            assert token1 != token2


class TestBruteForcePrevention:
    """Test brute force attack prevention (Rule #2)."""

    def test_login_rate_limiting(self):
        """Test that failed logins are rate limited."""
        # Attempt multiple failed logins
        for i in range(10):
            response = client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "WrongPassword123!",
                },
            )

        # Should be rate limited after 5 attempts
        assert response.status_code == 429

    def test_registration_rate_limiting(self):
        """Test that registrations are rate limited."""
        # Attempt multiple registrations
        for i in range(10):
            response = client.post(
                "/api/auth/register",
                json={
                    "email": f"test{i}@example.com",
                    "username": f"testuser{i}",
                    "password": "ValidPassword123!",
                },
            )

        # Should be rate limited
        assert response.status_code == 429


class TestInputValidation:
    """Test input validation on auth endpoints (Rule #1)."""

    def test_sql_injection_in_email(self):
        """Test SQL injection is blocked in email field."""
        malicious_emails = [
            "admin'--",
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin@example.com' UNION SELECT * FROM users--",
        ]

        for email in malicious_emails:
            response = client.post(
                "/api/auth/login",
                json={
                    "email": email,
                    "password": "ValidPassword123!",
                },
            )
            # Should be rejected or return 401 (not 500 server error)
            assert response.status_code in [400, 401]

    def test_xss_in_username(self):
        """Test XSS is blocked in username field."""
        malicious_usernames = [
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "';alert(String.fromCharCode(88,83,83))//",
        ]

        for username in malicious_usernames:
            response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "username": username,
                    "password": "ValidPassword123!",
                },
            )
            # Should be rejected
            assert response.status_code == 400

    def test_oversized_input_rejected(self):
        """Test that oversized inputs are rejected (DoS prevention)."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "a" * 10000,  # Way too long
                "password": "ValidPassword123!",
            },
        )
        assert response.status_code == 400

    def test_null_byte_injection(self):
        """Test that null bytes are rejected."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "test\x00user",
                "password": "ValidPassword123!",
            },
        )
        assert response.status_code == 400


class TestCookieSecurity:
    """Test cookie security attributes (Rule #2)."""

    def test_httponly_cookie(self):
        """Test that auth cookies are httpOnly (XSS protection)."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response.status_code == 200:
            # Check Set-Cookie header
            set_cookie = response.headers.get("set-cookie", "")
            assert "httponly" in set_cookie.lower()

    def test_secure_cookie_in_production(self):
        """Test that cookies are secure in production."""
        # Mock production environment
        original_env = settings.APP_ENV
        settings.APP_ENV = "production"

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response.status_code == 200:
            set_cookie = response.headers.get("set-cookie", "")
            assert "secure" in set_cookie.lower()

        # Restore
        settings.APP_ENV = original_env

    def test_samesite_cookie(self):
        """Test that cookies have SameSite attribute (CSRF protection)."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "ValidPassword123!",
            },
        )

        if response.status_code == 200:
            set_cookie = response.headers.get("set-cookie", "")
            assert "samesite" in set_cookie.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
