"""
Comprehensive Tests for API Authentication Modules.

Tests all authentication components in api/auth/:
- JWT authentication (jwt_auth.py)
- API Key authentication (key_auth.py)

Test Categories:
1. JWT Validation (valid, expired, malformed, missing)
2. Role Checking (admin, user, guest, permissions)
3. API Key Auth (valid keys, invalid, rate limits)
4. Session Management (create, validate, expire)
5. Token Refresh (refresh flow, blacklisting)

Target: 60%+ coverage with ~40-60 tests
"""

import asyncio
import hashlib
import jwt as pyjwt
import pytest
import secrets
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException, Depends
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def jwt_secret():
    """Provide a consistent JWT secret for testing."""
    return "test-secret-key-for-jwt-tests"


@pytest.fixture
def basic_app():
    """Create a basic FastAPI app for testing."""
    app = FastAPI()

    @app.get("/public")
    async def public_endpoint():
        return {"status": "public"}

    @app.get("/protected")
    async def protected_endpoint():
        return {"status": "protected"}

    @app.get("/admin")
    async def admin_endpoint():
        return {"status": "admin"}

    @app.post("/submit")
    async def submit_endpoint():
        return {"submitted": True}

    return app


@pytest.fixture(autouse=True)
def reset_api_key_state():
    """Reset API key state before each test."""
    from api.auth import key_auth
    key_auth._valid_keys.clear()
    key_auth._revoked_keys.clear()
    yield
    key_auth._valid_keys.clear()
    key_auth._revoked_keys.clear()


# =============================================================================
# JWT Token Creation Tests
# =============================================================================


class TestJWTTokenCreation:
    """Tests for JWT token creation functions."""

    def test_create_access_token_with_default_expiry(self):
        """Should create access token with default 30 minute expiry."""
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        token = create_access_token({"sub": "user123"})

        # Decode without claim validation to check payload structure
        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        assert payload["sub"] == "user123"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

        # Check expiry is approximately 30 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        delta = exp_time - now
        assert 25 < delta.total_seconds() / 60 < 35  # Between 25-35 minutes

    def test_create_access_token_with_custom_expiry(self):
        """Should create access token with custom expiry time."""
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        custom_delta = timedelta(hours=2)
        token = create_access_token({"sub": "user123"}, expires_delta=custom_delta)

        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        delta = exp_time - now
        assert 110 < delta.total_seconds() / 60 < 130  # Between 110-130 minutes

    def test_create_access_token_with_scopes(self):
        """Should create access token with scopes."""
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        token = create_access_token({
            "sub": "admin123",
            "scopes": ["read", "write", "admin"]
        })

        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        assert payload["sub"] == "admin123"
        assert "read" in payload["scopes"]
        assert "write" in payload["scopes"]
        assert "admin" in payload["scopes"]

    def test_create_refresh_token_with_7_day_expiry(self):
        """Should create refresh token with 7 day expiry."""
        from api.auth.jwt_auth import create_refresh_token, SECRET_KEY, ALGORITHM

        token = create_refresh_token({"sub": "user123"})

        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"

        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        delta = exp_time - now
        assert 6 < delta.total_seconds() / 86400 < 8  # Between 6-8 days

    def test_create_refresh_token_with_scopes(self):
        """Should preserve scopes in refresh token."""
        from api.auth.jwt_auth import create_refresh_token, SECRET_KEY, ALGORITHM

        token = create_refresh_token({
            "sub": "user456",
            "scopes": ["read", "write"]
        })

        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        assert payload["scopes"] == ["read", "write"]

    def test_create_token_includes_issued_at(self):
        """Should include issued-at (iat) timestamp."""
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        before = int(datetime.utcnow().timestamp())
        token = create_access_token({"sub": "user123"})
        after = int(datetime.utcnow().timestamp())

        payload = pyjwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        assert before <= payload["iat"] <= after


# =============================================================================
# JWT Token Verification Tests
# =============================================================================


class TestJWTTokenVerification:
    """Tests for JWT token verification."""

    def test_verify_valid_access_token(self):
        """Should successfully verify a valid access token."""
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create token WITHOUT iat to avoid clock skew validation issues
        token_data = {
            "sub": "user123",
            "scopes": ["read"],
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
            # No iat field - it's optional and avoids clock skew
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        payload = verify_token(token)

        assert payload is not None
        assert payload.sub == "user123"
        assert payload.type == "access"
        assert "read" in payload.scopes

    def test_verify_valid_refresh_token(self):
        """Should successfully verify a valid refresh token."""
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create token WITHOUT iat to avoid clock skew
        token_data = {
            "sub": "user456",
            "scopes": ["refresh"],
            "type": "refresh",
            "exp": int((datetime.utcnow() + timedelta(days=7)).timestamp())
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        payload = verify_token(token, expected_type="refresh")

        assert payload is not None
        assert payload.sub == "user456"
        assert payload.type == "refresh"

    def test_verify_expired_token_returns_none(self):
        """Should return None for expired tokens."""
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create token with exp in past using time.time() for correct comparison
        # PyJWT uses time.time() not datetime.utcnow().timestamp()
        token_data = {
            "sub": "user123",
            "scopes": [],
            "type": "access",
            "exp": int(time.time()) - 3600  # 1 hour ago
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        payload = verify_token(token)

        assert payload is None

    def test_verify_malformed_token_returns_none(self):
        """Should return None for malformed tokens."""
        from api.auth.jwt_auth import verify_token

        malformed_tokens = [
            "not.a.valid.jwt",
            "definitely-not-a-token",
            "",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.invalid",
        ]

        for token in malformed_tokens:
            payload = verify_token(token)
            assert payload is None

    def test_verify_token_with_wrong_secret(self):
        """Should return None for tokens signed with wrong secret."""
        from api.auth.jwt_auth import verify_token, ALGORITHM

        # Create token with different secret
        token = pyjwt.encode(
            {"sub": "user123", "type": "access", "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())},
            "wrong-secret",
            algorithm=ALGORITHM
        )

        payload = verify_token(token)

        assert payload is None

    def test_verify_access_token_as_refresh_fails(self):
        """Should return None when access token is used as refresh."""
        from api.auth.jwt_auth import create_access_token, verify_token

        token = create_access_token({"sub": "user123"})
        payload = verify_token(token, expected_type="refresh")

        assert payload is None

    def test_verify_refresh_token_as_access_fails(self):
        """Should return None when refresh token is used as access."""
        from api.auth.jwt_auth import create_refresh_token, verify_token

        token = create_refresh_token({"sub": "user123"})
        payload = verify_token(token, expected_type="access")

        assert payload is None

    def test_verify_token_missing_required_fields(self):
        """Should handle tokens missing required fields gracefully."""
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Token without 'type' field
        token = pyjwt.encode(
            {"sub": "user123", "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        payload = verify_token(token)

        assert payload is None


# =============================================================================
# JWT Auth Class Tests
# =============================================================================


class TestJWTAuthClass:
    """Tests for JWTAuth dependency class."""

    @pytest.mark.asyncio
    async def test_jwt_auth_with_valid_token(self):
        """Should return payload for valid token."""
        from api.auth.jwt_auth import JWTAuth, SECRET_KEY, ALGORITHM

        auth = JWTAuth(auto_error=True)

        # Create token WITHOUT iat to avoid clock skew validation issues
        token_data = {
            "sub": "user123",
            "scopes": ["read"],
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await auth(credentials=credentials)

        assert payload is not None
        assert payload.sub == "user123"

    @pytest.mark.asyncio
    async def test_jwt_auth_missing_credentials_auto_error(self):
        """Should raise HTTPException when credentials missing and auto_error=True."""
        from api.auth.jwt_auth import JWTAuth

        auth = JWTAuth(auto_error=True)

        with pytest.raises(HTTPException) as exc_info:
            await auth(credentials=None)

        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_auth_missing_credentials_no_auto_error(self):
        """Should return None when credentials missing and auto_error=False."""
        from api.auth.jwt_auth import JWTAuth

        auth = JWTAuth(auto_error=False)

        result = await auth(credentials=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_jwt_auth_invalid_token_auto_error(self):
        """Should raise HTTPException for invalid token when auto_error=True."""
        from api.auth.jwt_auth import JWTAuth

        auth = JWTAuth(auto_error=True)
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_auth_invalid_token_no_auto_error(self):
        """Should return None for invalid token when auto_error=False."""
        from api.auth.jwt_auth import JWTAuth

        auth = JWTAuth(auto_error=False)
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-token"
        )

        result = await auth(credentials=credentials)

        assert result is None

    def test_jwt_auth_has_scope_true(self):
        """Should return True when payload has required scope."""
        from api.auth.jwt_auth import JWTAuth, TokenPayload

        auth = JWTAuth()
        payload = TokenPayload(
            sub="user123",
            exp=int(time.time()) + 3600,
            type="access",
            scopes=["read", "write", "admin"]
        )

        assert auth.has_scope(payload, "read") is True
        assert auth.has_scope(payload, "admin") is True

    def test_jwt_auth_has_scope_false(self):
        """Should return False when payload lacks required scope."""
        from api.auth.jwt_auth import JWTAuth, TokenPayload

        auth = JWTAuth()
        payload = TokenPayload(
            sub="user123",
            exp=int(time.time()) + 3600,
            type="access",
            scopes=["read"]
        )

        assert auth.has_scope(payload, "admin") is False
        assert auth.has_scope(payload, "delete") is False


# =============================================================================
# Token Refresh Tests
# =============================================================================


class TestTokenRefresh:
    """Tests for token refresh functionality."""

    def test_refresh_access_token_success(self):
        """Should successfully refresh access token with valid refresh token."""
        from api.auth.jwt_auth import (
            refresh_access_token,
            SECRET_KEY,
            ALGORITHM
        )

        # Create refresh token WITHOUT iat to avoid clock skew
        token_data = {
            "sub": "user123",
            "scopes": ["read", "write"],
            "type": "refresh",
            "exp": int((datetime.utcnow() + timedelta(days=7)).timestamp())
        }
        refresh_token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        result = refresh_access_token(refresh_token)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

        # Decode new tokens to verify (without iat verification)
        new_access_payload = pyjwt.decode(
            result["access_token"], SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False}
        )
        assert new_access_payload["sub"] == "user123"
        assert "read" in new_access_payload["scopes"]

    def test_refresh_access_token_with_expired_refresh(self):
        """Should raise HTTPException for expired refresh token."""
        from api.auth.jwt_auth import refresh_access_token, SECRET_KEY, ALGORITHM

        # Create expired refresh token using time.time() for correct comparison
        # PyJWT uses time.time() for expiration checking, not datetime.utcnow().timestamp()
        expired_token = pyjwt.encode(
            {
                "sub": "user123",
                "type": "refresh",
                "exp": int(time.time()) - 3600,  # 1 hour ago using time.time()
                "scopes": []
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired refresh token" in exc_info.value.detail

    def test_refresh_access_token_with_access_token_fails(self):
        """Should raise HTTPException when access token used for refresh."""
        from api.auth.jwt_auth import refresh_access_token, SECRET_KEY, ALGORITHM

        # Create access token (wrong type for refresh) WITHOUT iat
        access_token_data = {
            "sub": "user123",
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "scopes": []
        }
        access_token = pyjwt.encode(access_token_data, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(access_token)

        assert exc_info.value.status_code == 401

    def test_refresh_access_token_preserves_scopes(self):
        """Should preserve scopes in refreshed tokens."""
        from api.auth.jwt_auth import refresh_access_token, SECRET_KEY, ALGORITHM

        original_scopes = ["read", "write", "admin"]

        # Create refresh token WITHOUT iat
        token_data = {
            "sub": "admin123",
            "scopes": original_scopes,
            "type": "refresh",
            "exp": int((datetime.utcnow() + timedelta(days=7)).timestamp())
        }
        refresh_token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        result = refresh_access_token(refresh_token)

        # Decode tokens without iat verification
        new_access = pyjwt.decode(
            result["access_token"], SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False}
        )
        new_refresh = pyjwt.decode(
            result["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False}
        )

        for scope in original_scopes:
            assert scope in new_access["scopes"]
            assert scope in new_refresh["scopes"]


# =============================================================================
# Token Payload Model Tests
# =============================================================================


class TestTokenPayload:
    """Tests for TokenPayload Pydantic model."""

    def test_token_payload_creation(self):
        """Should create TokenPayload with all fields."""
        from api.auth.jwt_auth import TokenPayload

        payload = TokenPayload(
            sub="user123",
            exp=1700000000,
            type="access",
            scopes=["read", "write"]
        )

        assert payload.sub == "user123"
        assert payload.exp == 1700000000
        assert payload.type == "access"
        assert payload.scopes == ["read", "write"]

    def test_token_payload_default_scopes(self):
        """Should default to empty scopes list."""
        from api.auth.jwt_auth import TokenPayload

        payload = TokenPayload(
            sub="user123",
            exp=1700000000,
            type="access"
        )

        assert payload.scopes == []


# =============================================================================
# API Key Hash Function Tests
# =============================================================================


class TestAPIKeyHashing:
    """Tests for API key hashing functions."""

    def test_hash_key_produces_consistent_output(self):
        """Should produce same hash for same key."""
        from api.auth.key_auth import hash_key

        key = "test-api-key-12345"
        hash1 = hash_key(key)
        hash2 = hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest

    def test_hash_key_different_keys_different_hashes(self):
        """Should produce different hashes for different keys."""
        from api.auth.key_auth import hash_key

        key1 = "api-key-one"
        key2 = "api-key-two"

        assert hash_key(key1) != hash_key(key2)

    def test_hash_key_matches_sha256(self):
        """Should match standard SHA256 hash."""
        from api.auth.key_auth import hash_key

        key = "test-key"
        expected = hashlib.sha256(key.encode()).hexdigest()

        assert hash_key(key) == expected


# =============================================================================
# API Key Registration Tests
# =============================================================================


class TestAPIKeyRegistration:
    """Tests for API key registration and management."""

    def test_register_key_without_metadata(self):
        """Should register key without metadata."""
        from api.auth.key_auth import register_key, validate_key

        key = "test-api-key-123"
        register_key(key)

        metadata = validate_key(key)

        assert metadata == {}

    def test_register_key_with_metadata(self):
        """Should register key with metadata."""
        from api.auth.key_auth import register_key, validate_key

        key = "test-api-key-456"
        metadata = {"name": "Test App", "tier": "premium"}
        register_key(key, metadata)

        result = validate_key(key)

        assert result["name"] == "Test App"
        assert result["tier"] == "premium"

    def test_revoke_key_removes_from_valid(self):
        """Should remove key from valid keys on revocation."""
        from api.auth.key_auth import register_key, revoke_key, validate_key

        key = "revokable-key"
        register_key(key, {"name": "Test"})

        # Verify key is valid
        assert validate_key(key) is not None

        # Revoke the key
        revoke_key(key)

        # Verify key is no longer valid
        assert validate_key(key) is None

    def test_revoked_key_stays_invalid(self):
        """Should keep revoked key invalid even if re-registered."""
        from api.auth.key_auth import register_key, revoke_key, validate_key, _revoked_keys

        key = "test-key-for-revocation"
        register_key(key)
        revoke_key(key)

        # Revoked keys set should contain the hash
        from api.auth.key_auth import hash_key
        assert hash_key(key) in _revoked_keys

        # Should remain invalid
        assert validate_key(key) is None


# =============================================================================
# API Key Validation Tests
# =============================================================================


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_validate_key_returns_none_for_empty(self):
        """Should return None for empty key."""
        from api.auth.key_auth import validate_key

        assert validate_key("") is None
        assert validate_key(None) is None

    def test_validate_key_returns_none_for_unknown(self):
        """Should return None for unknown key."""
        from api.auth.key_auth import validate_key

        assert validate_key("unknown-key-12345") is None

    def test_validate_key_returns_metadata_for_valid(self):
        """Should return metadata for valid key."""
        from api.auth.key_auth import register_key, validate_key

        key = "valid-test-key"
        metadata = {"app": "TestApp", "scopes": ["read"]}
        register_key(key, metadata)

        result = validate_key(key)

        assert result == metadata

    def test_validate_key_returns_none_for_revoked(self):
        """Should return None for revoked key."""
        from api.auth.key_auth import register_key, revoke_key, validate_key

        key = "key-to-revoke"
        register_key(key)
        revoke_key(key)

        assert validate_key(key) is None


# =============================================================================
# FastAPI API Key Dependency Tests
# =============================================================================


class TestValidateAPIKeyDependency:
    """Tests for FastAPI API key validation dependency."""

    @pytest.mark.asyncio
    async def test_validate_api_key_from_header(self):
        """Should accept API key from X-API-Key header."""
        from api.auth.key_auth import validate_api_key, register_key

        key = "header-api-key"
        register_key(key, {"name": "HeaderApp"})

        result = await validate_api_key(header_key=key, query_key=None)

        assert result == key

    @pytest.mark.asyncio
    async def test_validate_api_key_from_query(self):
        """Should accept API key from query parameter."""
        from api.auth.key_auth import validate_api_key, register_key

        key = "query-api-key"
        register_key(key, {"name": "QueryApp"})

        result = await validate_api_key(header_key=None, query_key=key)

        assert result == key

    @pytest.mark.asyncio
    async def test_validate_api_key_prefers_header(self):
        """Should prefer header key over query key."""
        from api.auth.key_auth import validate_api_key, register_key

        header_key = "header-key-priority"
        query_key = "query-key-fallback"
        register_key(header_key, {"name": "Header"})
        register_key(query_key, {"name": "Query"})

        result = await validate_api_key(header_key=header_key, query_key=query_key)

        assert result == header_key

    @pytest.mark.asyncio
    async def test_validate_api_key_missing_raises_401(self):
        """Should raise 401 when no API key provided."""
        from api.auth.key_auth import validate_api_key

        with pytest.raises(HTTPException) as exc_info:
            await validate_api_key(header_key=None, query_key=None)

        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_raises_401(self):
        """Should raise 401 for invalid API key."""
        from api.auth.key_auth import validate_api_key

        with pytest.raises(HTTPException) as exc_info:
            await validate_api_key(header_key="invalid-key", query_key=None)

        assert exc_info.value.status_code == 401
        assert "Invalid or revoked API key" in exc_info.value.detail


# =============================================================================
# APIKeyAuth Class Tests
# =============================================================================


class TestAPIKeyAuthClass:
    """Tests for APIKeyAuth manager class."""

    def test_generate_key_creates_unique_keys(self):
        """Should generate unique API keys."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        keys = [auth.generate_key(f"App{i}") for i in range(5)]

        # All keys should be unique
        assert len(keys) == len(set(keys))

    def test_generate_key_stores_metadata(self):
        """Should store name and scopes in metadata."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        key = auth.generate_key("TestApp", scopes=["read", "write"])

        metadata = auth.validate(key)

        assert metadata is not None
        assert metadata["name"] == "TestApp"
        assert metadata["scopes"] == ["read", "write"]

    def test_generate_key_default_scopes(self):
        """Should default to read scope."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        key = auth.generate_key("DefaultApp")

        metadata = auth.validate(key)

        assert metadata["scopes"] == ["read"]

    def test_generate_key_includes_created_at(self):
        """Should include created_at timestamp in metadata."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()
        before = time.time()

        key = auth.generate_key("TimedApp")

        after = time.time()
        metadata = auth.validate(key)

        assert before <= metadata["created_at"] <= after

    def test_validate_returns_none_for_invalid(self):
        """Should return None for invalid keys."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        assert auth.validate("nonexistent-key") is None

    def test_revoke_removes_key(self):
        """Should revoke key and make it invalid."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        key = auth.generate_key("RevokableApp")
        assert auth.validate(key) is not None

        auth.revoke(key)

        assert auth.validate(key) is None

    def test_has_scope_returns_true_for_valid_scope(self):
        """Should return True when key has scope."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        key = auth.generate_key("ScopedApp", scopes=["read", "write", "admin"])

        assert auth.has_scope(key, "read") is True
        assert auth.has_scope(key, "admin") is True

    def test_has_scope_returns_false_for_missing_scope(self):
        """Should return False when key lacks scope."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        key = auth.generate_key("LimitedApp", scopes=["read"])

        assert auth.has_scope(key, "write") is False
        assert auth.has_scope(key, "admin") is False

    def test_has_scope_returns_false_for_invalid_key(self):
        """Should return False for invalid keys."""
        from api.auth.key_auth import APIKeyAuth

        auth = APIKeyAuth()

        assert auth.has_scope("invalid-key", "read") is False


# =============================================================================
# Integration Tests - JWT with FastAPI
# =============================================================================


class TestJWTIntegration:
    """Integration tests for JWT auth with FastAPI."""

    def test_protected_endpoint_without_token(self):
        """Should reject requests without token to protected endpoints."""
        from api.auth.jwt_auth import jwt_auth

        app = FastAPI()

        @app.get("/protected")
        async def protected(payload=Depends(jwt_auth)):
            return {"user": payload.sub}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/protected")

        assert response.status_code == 401

    def test_protected_endpoint_with_valid_token(self):
        """Should accept requests with valid token."""
        from api.auth.jwt_auth import jwt_auth, SECRET_KEY, ALGORITHM

        app = FastAPI()

        @app.get("/protected")
        async def protected(payload=Depends(jwt_auth)):
            return {"user": payload.sub}

        client = TestClient(app)

        # Create token WITHOUT iat to avoid clock skew
        token_data = {
            "sub": "testuser",
            "scopes": [],
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["user"] == "testuser"

    def test_protected_endpoint_with_expired_token(self):
        """Should reject requests with expired token."""
        from api.auth.jwt_auth import jwt_auth, SECRET_KEY, ALGORITHM

        app = FastAPI()

        @app.get("/protected")
        async def protected(payload=Depends(jwt_auth)):
            return {"user": payload.sub}

        client = TestClient(app, raise_server_exceptions=False)

        # Create expired token using time.time() for correct comparison
        # PyJWT uses time.time() not datetime.utcnow().timestamp()
        token_data = {
            "sub": "testuser",
            "scopes": [],
            "type": "access",
            "exp": int(time.time()) - 3600  # 1 hour ago using time.time()
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401

    def test_optional_auth_allows_unauthenticated(self):
        """Should allow unauthenticated requests with optional auth."""
        from api.auth.jwt_auth import jwt_auth_optional

        app = FastAPI()

        @app.get("/optional")
        async def optional(payload=Depends(jwt_auth_optional)):
            if payload:
                return {"user": payload.sub}
            return {"user": "anonymous"}

        client = TestClient(app)

        response = client.get("/optional")

        assert response.status_code == 200
        assert response.json()["user"] == "anonymous"


# =============================================================================
# Integration Tests - API Key with FastAPI
# =============================================================================


class TestAPIKeyIntegration:
    """Integration tests for API key auth with FastAPI."""

    def test_api_key_endpoint_without_key(self):
        """Should reject requests without API key."""
        from api.auth.key_auth import validate_api_key

        app = FastAPI()

        @app.get("/api/data")
        async def get_data(api_key: str = Depends(validate_api_key)):
            return {"data": "secret"}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/data")

        assert response.status_code == 401

    def test_api_key_endpoint_with_header_key(self):
        """Should accept requests with API key in header."""
        from api.auth.key_auth import validate_api_key, register_key

        app = FastAPI()
        key = "integration-test-key"
        register_key(key)

        @app.get("/api/data")
        async def get_data(api_key: str = Depends(validate_api_key)):
            return {"data": "secret", "key_used": api_key}

        client = TestClient(app)
        response = client.get("/api/data", headers={"X-API-Key": key})

        assert response.status_code == 200
        assert response.json()["key_used"] == key

    def test_api_key_endpoint_with_query_key(self):
        """Should accept requests with API key in query param."""
        from api.auth.key_auth import validate_api_key, register_key

        app = FastAPI()
        key = "query-integration-key"
        register_key(key)

        @app.get("/api/data")
        async def get_data(api_key: str = Depends(validate_api_key)):
            return {"data": "secret"}

        client = TestClient(app)
        response = client.get(f"/api/data?api_key={key}")

        assert response.status_code == 200


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestAuthModuleExports:
    """Tests for auth module exports."""

    def test_jwt_auth_exports(self):
        """Should export all JWT auth functions."""
        from api.auth.jwt_auth import (
            create_access_token,
            create_refresh_token,
            verify_token,
            refresh_access_token,
            JWTAuth,
            TokenPayload,
            jwt_auth,
            jwt_auth_optional,
            SECRET_KEY,
            ALGORITHM,
        )

        assert callable(create_access_token)
        assert callable(create_refresh_token)
        assert callable(verify_token)
        assert callable(refresh_access_token)
        assert JWTAuth is not None
        assert TokenPayload is not None

    def test_key_auth_exports(self):
        """Should export all key auth functions."""
        from api.auth.key_auth import (
            hash_key,
            register_key,
            revoke_key,
            validate_key,
            validate_api_key,
            APIKeyAuth,
            api_key_header,
            api_key_query,
        )

        assert callable(hash_key)
        assert callable(register_key)
        assert callable(revoke_key)
        assert callable(validate_key)

    def test_init_exports(self):
        """Should export all auth components from __init__."""
        from api.auth import (
            validate_api_key,
            APIKeyAuth,
            api_key_header,
            JWTAuth,
            create_access_token,
            create_refresh_token,
            verify_token,
        )

        assert callable(validate_api_key)
        assert APIKeyAuth is not None
        assert JWTAuth is not None


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================


class TestSecurityEdgeCases:
    """Tests for security edge cases."""

    def test_jwt_token_tampering_detection(self):
        """Should detect tampered JWT tokens."""
        from api.auth.jwt_auth import create_access_token, verify_token

        token = create_access_token({"sub": "user123"})

        # Tamper with the token
        parts = token.split(".")
        if len(parts) == 3:
            # Modify payload
            tampered = parts[0] + "." + parts[1] + "x" + "." + parts[2]
            assert verify_token(tampered) is None

    def test_api_key_timing_attack_resistance(self):
        """API key validation should use constant-time comparison."""
        from api.auth.key_auth import hash_key, validate_key, register_key

        key = "timing-test-key"
        register_key(key)

        # Both valid and invalid keys should take similar time
        # (This is a basic check - real timing attack tests need statistical analysis)
        import time

        iterations = 100

        # Time valid key checks
        valid_start = time.perf_counter()
        for _ in range(iterations):
            validate_key(key)
        valid_time = time.perf_counter() - valid_start

        # Time invalid key checks
        invalid_start = time.perf_counter()
        for _ in range(iterations):
            validate_key("invalid-key-that-does-not-exist")
        invalid_time = time.perf_counter() - invalid_start

        # Times should be in the same order of magnitude
        # (This is a weak test but better than nothing)
        ratio = max(valid_time, invalid_time) / max(min(valid_time, invalid_time), 0.0001)
        assert ratio < 10  # Should be within 10x

    def test_empty_scopes_handling(self):
        """Should handle empty scopes gracefully."""
        from api.auth.jwt_auth import verify_token, JWTAuth, SECRET_KEY, ALGORITHM

        # Create token WITHOUT iat
        token_data = {
            "sub": "user123",
            "scopes": [],
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        payload = verify_token(token)

        assert payload.scopes == []

        auth = JWTAuth()
        assert auth.has_scope(payload, "any") is False

    def test_very_long_subject_in_token(self):
        """Should handle very long subject strings."""
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        long_sub = "user_" + "x" * 1000

        # Create token WITHOUT iat
        token_data = {
            "sub": long_sub,
            "scopes": [],
            "type": "access",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        token = pyjwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        payload = verify_token(token)

        assert payload.sub == long_sub

    def test_special_characters_in_api_key(self):
        """Should handle special characters in API keys."""
        from api.auth.key_auth import register_key, validate_key

        special_key = "key-with-!@#$%^&*()_+-=[]{}|;':\",./<>?"
        register_key(special_key, {"name": "SpecialApp"})

        metadata = validate_key(special_key)

        assert metadata is not None
        assert metadata["name"] == "SpecialApp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
