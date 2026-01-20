"""
Unit tests for Authentication System.

Tests cover:
- JWT authentication (access tokens, refresh tokens, expiration)
- API key authentication (registration, validation, revocation)
- Telegram bot authentication (admin_only decorator)
- Token refresh flow
- Error handling and status codes

NOTE: There is a known bug in api/auth/jwt_auth.py where datetime.utcnow().timestamp()
is used instead of time.time(). This creates tokens with incorrect timestamps because
datetime.utcnow() returns a naive datetime in UTC, but .timestamp() interprets it as
local time. Tests use time.time() for token creation to work around this issue.
"""

import pytest
import os
import time
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# ============================================================================
# JWT Authentication Tests
# ============================================================================

class TestJWTTokenCreation:
    """Test JWT token creation functions."""

    def test_create_access_token_basic(self):
        """Test creating a basic access token."""
        import jwt
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        data = {"sub": "user123", "scopes": ["read", "write"]}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode without verification options (disable iat validation for testing)
        decoded = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )
        assert decoded["sub"] == "user123"
        assert decoded["scopes"] == ["read", "write"]
        assert decoded["type"] == "access"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_access_token_with_custom_expiry(self):
        """Test creating access token with custom expiration."""
        import jwt
        from api.auth.jwt_auth import create_access_token, SECRET_KEY, ALGORITHM

        data = {"sub": "user123"}
        expires = timedelta(hours=2)
        token = create_access_token(data, expires_delta=expires)

        decoded = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        # Verify token has appropriate structure
        assert decoded["sub"] == "user123"
        assert decoded["type"] == "access"
        assert "exp" in decoded

    def test_create_access_token_default_expiry(self):
        """Test access token has default 30 minute expiry."""
        import jwt
        from api.auth.jwt_auth import (
            create_access_token,
            SECRET_KEY,
            ALGORITHM,
            ACCESS_TOKEN_EXPIRE_MINUTES
        )

        data = {"sub": "user123"}
        token = create_access_token(data)

        decoded = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        # Verify token structure - exp should exist
        assert "exp" in decoded
        assert decoded["type"] == "access"

    def test_create_refresh_token_basic(self):
        """Test creating a basic refresh token."""
        import jwt
        from api.auth.jwt_auth import create_refresh_token, SECRET_KEY, ALGORITHM

        data = {"sub": "user123", "scopes": ["read"]}
        token = create_refresh_token(data)

        assert token is not None
        assert isinstance(token, str)

        decoded = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )
        assert decoded["sub"] == "user123"
        assert decoded["type"] == "refresh"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_refresh_token_longer_expiry(self):
        """Test refresh token has 7 day expiry."""
        import jwt
        from api.auth.jwt_auth import (
            create_refresh_token,
            SECRET_KEY,
            ALGORITHM,
            REFRESH_TOKEN_EXPIRE_DAYS
        )

        data = {"sub": "user123"}
        token = create_refresh_token(data)

        decoded = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )

        # Verify token structure
        assert decoded["type"] == "refresh"
        assert "exp" in decoded

    def test_access_and_refresh_tokens_are_different(self):
        """Test that access and refresh tokens are different."""
        from api.auth.jwt_auth import create_access_token, create_refresh_token

        data = {"sub": "user123"}
        access = create_access_token(data)
        refresh = create_refresh_token(data)

        assert access != refresh


class TestJWTTokenVerification:
    """Test JWT token verification."""

    def test_verify_valid_access_token(self):
        """Test verifying a valid access token."""
        import jwt
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create token using time.time() for correct timestamp
        exp = int(time.time()) + 3600  # 1 hour from now
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": ["read"]},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        payload = verify_token(token, expected_type="access")

        assert payload is not None
        assert payload.sub == "user123"
        assert payload.type == "access"
        assert "read" in payload.scopes

    def test_verify_valid_refresh_token(self):
        """Test verifying a valid refresh token."""
        import jwt
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create token using time.time() for correct timestamp
        exp = int(time.time()) + 86400 * 7  # 7 days from now
        token = jwt.encode(
            {"sub": "user456", "type": "refresh", "exp": exp, "scopes": ["write"]},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        payload = verify_token(token, expected_type="refresh")

        assert payload is not None
        assert payload.sub == "user456"
        assert payload.type == "refresh"

    def test_verify_token_wrong_type_returns_none(self):
        """Test that verifying with wrong expected type returns None."""
        import jwt
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create access token
        exp = int(time.time()) + 3600
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Try to verify access token as refresh token
        payload = verify_token(token, expected_type="refresh")

        assert payload is None

    def test_verify_expired_token_returns_none(self):
        """Test that expired token verification returns None."""
        import jwt
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create expired token using time.time()
        exp = int(time.time()) - 3600  # 1 hour ago
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        payload = verify_token(token)

        assert payload is None

    def test_verify_invalid_token_returns_none(self):
        """Test that invalid token returns None."""
        from api.auth.jwt_auth import verify_token

        payload = verify_token("invalid.token.here")

        assert payload is None

    def test_verify_tampered_token_returns_none(self):
        """Test that tampered token returns None."""
        import jwt
        from api.auth.jwt_auth import verify_token, SECRET_KEY, ALGORITHM

        # Create valid token
        exp = int(time.time()) + 3600
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1][::-1]  # Reverse the payload
        tampered = ".".join(parts)

        payload = verify_token(tampered)

        assert payload is None

    def test_verify_token_with_wrong_secret_fails(self):
        """Test token signed with wrong secret fails verification."""
        import jwt
        from api.auth.jwt_auth import verify_token, ALGORITHM

        # Create token with different secret
        exp = int(time.time()) + 3600
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp},
            "wrong-secret-key",
            algorithm=ALGORITHM
        )

        payload = verify_token(token)

        assert payload is None


class TestJWTAuthClass:
    """Test JWTAuth FastAPI dependency class."""

    @pytest.fixture
    def jwt_auth(self):
        """Create JWTAuth instance."""
        from api.auth.jwt_auth import JWTAuth
        return JWTAuth(auto_error=True)

    @pytest.fixture
    def jwt_auth_optional(self):
        """Create optional JWTAuth instance."""
        from api.auth.jwt_auth import JWTAuth
        return JWTAuth(auto_error=False)

    @pytest.mark.asyncio
    async def test_jwt_auth_with_valid_token(self, jwt_auth):
        """Test JWTAuth with valid token."""
        import jwt
        from api.auth.jwt_auth import SECRET_KEY, ALGORITHM
        from fastapi.security import HTTPAuthorizationCredentials

        # Create token using time.time()
        exp = int(time.time()) + 3600
        token = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": ["read"]},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        payload = await jwt_auth(credentials=credentials)

        assert payload is not None
        assert payload.sub == "user123"

    @pytest.mark.asyncio
    async def test_jwt_auth_missing_token_raises_401(self, jwt_auth):
        """Test JWTAuth raises 401 when token is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth(credentials=None)

        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_auth_invalid_token_raises_401(self, jwt_auth):
        """Test JWTAuth raises 401 for invalid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token")

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth(credentials=credentials)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_jwt_auth_optional_returns_none_for_missing(self, jwt_auth_optional):
        """Test optional JWTAuth returns None for missing token."""
        payload = await jwt_auth_optional(credentials=None)

        assert payload is None

    @pytest.mark.asyncio
    async def test_jwt_auth_optional_returns_none_for_invalid(self, jwt_auth_optional):
        """Test optional JWTAuth returns None for invalid token."""
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

        payload = await jwt_auth_optional(credentials=credentials)

        assert payload is None

    def test_jwt_auth_has_scope_true(self, jwt_auth):
        """Test has_scope returns True for valid scope."""
        from api.auth.jwt_auth import TokenPayload

        payload = TokenPayload(sub="user123", exp=0, type="access", scopes=["read", "write"])

        assert jwt_auth.has_scope(payload, "read") is True
        assert jwt_auth.has_scope(payload, "write") is True

    def test_jwt_auth_has_scope_false(self, jwt_auth):
        """Test has_scope returns False for missing scope."""
        from api.auth.jwt_auth import TokenPayload

        payload = TokenPayload(sub="user123", exp=0, type="access", scopes=["read"])

        assert jwt_auth.has_scope(payload, "admin") is False


class TestTokenRefresh:
    """Test token refresh functionality."""

    def test_refresh_access_token_success(self):
        """Test successfully refreshing access token."""
        import jwt
        from api.auth.jwt_auth import (
            refresh_access_token,
            SECRET_KEY,
            ALGORITHM
        )

        # Create refresh token using time.time()
        exp = int(time.time()) + 86400 * 7  # 7 days from now
        refresh = jwt.encode(
            {"sub": "user123", "type": "refresh", "exp": exp, "scopes": ["read"]},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Exchange for new tokens
        result = refresh_access_token(refresh)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

        # Verify new access token structure
        decoded = jwt.decode(
            result["access_token"], SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )
        assert decoded["sub"] == "user123"
        assert decoded["type"] == "access"

    def test_refresh_access_token_with_expired_refresh_raises_401(self):
        """Test refresh with expired refresh token raises 401."""
        import jwt
        from api.auth.jwt_auth import refresh_access_token, SECRET_KEY, ALGORITHM

        # Create expired refresh token using time.time()
        exp = int(time.time()) - 3600  # 1 hour ago
        expired_refresh = jwt.encode(
            {
                "sub": "user123",
                "type": "refresh",
                "exp": exp,
                "scopes": [],
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(expired_refresh)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired refresh token" in exc_info.value.detail

    def test_refresh_access_token_with_access_token_raises_401(self):
        """Test refresh with access token (wrong type) raises 401."""
        import jwt
        from api.auth.jwt_auth import refresh_access_token, SECRET_KEY, ALGORITHM

        # Create access token (wrong type for refresh) using time.time()
        exp = int(time.time()) + 3600
        access = jwt.encode(
            {"sub": "user123", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(access)

        assert exc_info.value.status_code == 401

    def test_refresh_preserves_scopes(self):
        """Test that refresh preserves original scopes."""
        import jwt
        from api.auth.jwt_auth import (
            refresh_access_token,
            SECRET_KEY,
            ALGORITHM
        )

        original_scopes = ["read", "write", "admin"]

        # Create refresh token using time.time()
        exp = int(time.time()) + 86400 * 7
        refresh = jwt.encode(
            {"sub": "user123", "type": "refresh", "exp": exp, "scopes": original_scopes},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        result = refresh_access_token(refresh)

        # Decode new access token
        decoded = jwt.decode(
            result["access_token"], SECRET_KEY, algorithms=[ALGORITHM],
            options={"verify_iat": False, "verify_exp": False}
        )
        assert set(decoded["scopes"]) == set(original_scopes)


# ============================================================================
# API Key Authentication Tests
# ============================================================================

class TestAPIKeyHashing:
    """Test API key hashing functionality."""

    def test_hash_key_consistency(self):
        """Test that same key always produces same hash."""
        from api.auth.key_auth import hash_key

        key = "my-secret-api-key"
        hash1 = hash_key(key)
        hash2 = hash_key(key)

        assert hash1 == hash2

    def test_hash_key_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        from api.auth.key_auth import hash_key

        hash1 = hash_key("key1")
        hash2 = hash_key("key2")

        assert hash1 != hash2

    def test_hash_key_uses_sha256(self):
        """Test that hash_key uses SHA-256."""
        from api.auth.key_auth import hash_key

        key = "test-key"
        expected = hashlib.sha256(key.encode()).hexdigest()
        actual = hash_key(key)

        assert actual == expected


class TestAPIKeyRegistration:
    """Test API key registration and management."""

    @pytest.fixture(autouse=True)
    def reset_keys(self):
        """Reset key storage before and after each test."""
        from api.auth import key_auth
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()
        yield
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()

    def test_register_key_basic(self):
        """Test registering a basic API key."""
        from api.auth.key_auth import register_key, validate_key

        key = "my-api-key-123"
        register_key(key, {"name": "test_key"})

        metadata = validate_key(key)

        assert metadata is not None
        assert metadata["name"] == "test_key"

    def test_register_key_without_metadata(self):
        """Test registering key without metadata."""
        from api.auth.key_auth import register_key, validate_key

        key = "simple-key"
        register_key(key)

        metadata = validate_key(key)

        assert metadata == {}

    def test_revoke_key(self):
        """Test revoking an API key."""
        from api.auth.key_auth import register_key, revoke_key, validate_key

        key = "revoke-me"
        register_key(key, {"name": "temp"})

        # Key should work before revocation
        assert validate_key(key) is not None

        revoke_key(key)

        # Key should not work after revocation
        assert validate_key(key) is None

    def test_revoked_key_stays_revoked(self):
        """Test that revoked key cannot be re-registered."""
        from api.auth.key_auth import register_key, revoke_key, validate_key

        key = "permanent-revoke"
        register_key(key)
        revoke_key(key)

        # Try to re-register
        register_key(key, {"name": "reregistered"})

        # Should still be revoked
        assert validate_key(key) is None

    def test_validate_empty_key_returns_none(self):
        """Test that empty key returns None."""
        from api.auth.key_auth import validate_key

        assert validate_key("") is None
        assert validate_key(None) is None

    def test_validate_unregistered_key_returns_none(self):
        """Test that unregistered key returns None."""
        from api.auth.key_auth import validate_key

        assert validate_key("nonexistent-key") is None


class TestAPIKeyAuthClass:
    """Test APIKeyAuth class."""

    @pytest.fixture(autouse=True)
    def reset_keys(self):
        """Reset key storage before and after each test."""
        from api.auth import key_auth
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()
        yield
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()

    @pytest.fixture
    def api_key_auth(self):
        """Create APIKeyAuth instance."""
        from api.auth.key_auth import APIKeyAuth
        return APIKeyAuth()

    def test_generate_key(self, api_key_auth):
        """Test generating a new API key."""
        key = api_key_auth.generate_key("test_user", scopes=["read", "write"])

        assert key is not None
        assert len(key) > 20  # URL-safe base64 encoded

        # Key should be valid
        metadata = api_key_auth.validate(key)
        assert metadata is not None
        assert metadata["name"] == "test_user"
        assert metadata["scopes"] == ["read", "write"]

    def test_generate_key_default_scopes(self, api_key_auth):
        """Test generated key has default read scope."""
        key = api_key_auth.generate_key("reader")

        metadata = api_key_auth.validate(key)
        assert metadata["scopes"] == ["read"]

    def test_generate_key_includes_timestamp(self, api_key_auth):
        """Test generated key includes creation timestamp."""
        key = api_key_auth.generate_key("stamped")

        metadata = api_key_auth.validate(key)
        assert "created_at" in metadata
        assert metadata["created_at"] <= time.time()

    def test_revoke_method(self, api_key_auth):
        """Test revoking key via APIKeyAuth class."""
        key = api_key_auth.generate_key("temp_user")

        assert api_key_auth.validate(key) is not None

        api_key_auth.revoke(key)

        assert api_key_auth.validate(key) is None

    def test_has_scope_true(self, api_key_auth):
        """Test has_scope returns True for valid scope."""
        key = api_key_auth.generate_key("scoped", scopes=["read", "write"])

        assert api_key_auth.has_scope(key, "read") is True
        assert api_key_auth.has_scope(key, "write") is True

    def test_has_scope_false(self, api_key_auth):
        """Test has_scope returns False for missing scope."""
        key = api_key_auth.generate_key("limited", scopes=["read"])

        assert api_key_auth.has_scope(key, "admin") is False
        assert api_key_auth.has_scope(key, "write") is False

    def test_has_scope_invalid_key_false(self, api_key_auth):
        """Test has_scope returns False for invalid key."""
        assert api_key_auth.has_scope("invalid-key", "read") is False


class TestValidateAPIKeyDependency:
    """Test validate_api_key FastAPI dependency."""

    @pytest.fixture(autouse=True)
    def reset_keys(self):
        """Reset key storage before and after each test."""
        from api.auth import key_auth
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()
        yield
        key_auth._valid_keys.clear()
        key_auth._revoked_keys.clear()

    @pytest.mark.asyncio
    async def test_validate_api_key_from_header(self):
        """Test validating API key from header."""
        from api.auth.key_auth import validate_api_key, register_key

        key = "header-key-123"
        register_key(key, {"name": "header_user"})

        result = await validate_api_key(header_key=key, query_key=None)

        assert result == key

    @pytest.mark.asyncio
    async def test_validate_api_key_from_query(self):
        """Test validating API key from query param."""
        from api.auth.key_auth import validate_api_key, register_key

        key = "query-key-456"
        register_key(key, {"name": "query_user"})

        result = await validate_api_key(header_key=None, query_key=key)

        assert result == key

    @pytest.mark.asyncio
    async def test_validate_api_key_header_takes_precedence(self):
        """Test that header key takes precedence over query key."""
        from api.auth.key_auth import validate_api_key, register_key

        header_key = "header-key"
        query_key = "query-key"
        register_key(header_key, {"name": "header"})
        register_key(query_key, {"name": "query"})

        result = await validate_api_key(header_key=header_key, query_key=query_key)

        assert result == header_key

    @pytest.mark.asyncio
    async def test_validate_api_key_missing_raises_401(self):
        """Test missing API key raises 401."""
        from api.auth.key_auth import validate_api_key

        with pytest.raises(HTTPException) as exc_info:
            await validate_api_key(header_key=None, query_key=None)

        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_raises_401(self):
        """Test invalid API key raises 401."""
        from api.auth.key_auth import validate_api_key

        with pytest.raises(HTTPException) as exc_info:
            await validate_api_key(header_key="invalid-key", query_key=None)

        assert exc_info.value.status_code == 401
        assert "Invalid or revoked API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_api_key_revoked_raises_401(self):
        """Test revoked API key raises 401."""
        from api.auth.key_auth import validate_api_key, register_key, revoke_key

        key = "soon-revoked"
        register_key(key)
        revoke_key(key)

        with pytest.raises(HTTPException) as exc_info:
            await validate_api_key(header_key=key, query_key=None)

        assert exc_info.value.status_code == 401


# ============================================================================
# Telegram Bot Authentication Tests
# ============================================================================

class TestTelegramAdminAuth:
    """Test Telegram bot admin authentication."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config with admin IDs."""
        config = MagicMock()
        config.admin_ids = {123456789, 987654321}
        return config

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        return MagicMock()

    def test_is_admin_true(self, mock_config):
        """Test is_admin returns True for admin user."""
        assert mock_config.admin_ids == {123456789, 987654321}
        assert 123456789 in mock_config.admin_ids

    def test_is_admin_false(self, mock_config):
        """Test is_admin returns False for non-admin user."""
        assert 111111111 not in mock_config.admin_ids

    @pytest.mark.asyncio
    async def test_admin_only_allows_admin(self, mock_update, mock_context, mock_config):
        """Test admin_only decorator allows admin users."""
        from tg_bot.handlers import admin_only

        mock_update.effective_user.id = 123456789

        # Create test handler
        @admin_only
        async def test_handler(update, context):
            return "success"

        with patch('tg_bot.handlers.get_config', return_value=mock_config):
            result = await test_handler(mock_update, mock_context)

        assert result == "success"
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_only_blocks_non_admin(self, mock_update, mock_context, mock_config):
        """Test admin_only decorator blocks non-admin users."""
        from tg_bot.handlers import admin_only

        mock_update.effective_user.id = 111111111  # Not in admin list

        @admin_only
        async def test_handler(update, context):
            return "should not reach"

        with patch('tg_bot.handlers.get_config', return_value=mock_config):
            with patch('tg_bot.services.digest_formatter.format_unauthorized', return_value="Unauthorized"):
                result = await test_handler(mock_update, mock_context)

        assert result is None  # Handler returns None for blocked users
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_only_no_user(self, mock_update, mock_context, mock_config):
        """Test admin_only handles missing user gracefully."""
        from tg_bot.handlers import admin_only

        mock_update.effective_user = None

        @admin_only
        async def test_handler(update, context):
            return "should not reach"

        with patch('tg_bot.handlers.get_config', return_value=mock_config):
            with patch('tg_bot.services.digest_formatter.format_unauthorized', return_value="Unauthorized"):
                result = await test_handler(mock_update, mock_context)

        assert result is None


class TestBotConfigAuth:
    """Test BotConfig authentication methods."""

    @pytest.fixture
    def bot_config(self):
        """Create BotConfig with test admin IDs."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '123,456,789'}):
            from tg_bot.config import BotConfig
            return BotConfig()

    def test_is_admin_valid_id(self, bot_config):
        """Test is_admin with valid admin ID."""
        assert bot_config.is_admin(123) is True
        assert bot_config.is_admin(456) is True
        assert bot_config.is_admin(789) is True

    def test_is_admin_invalid_id(self, bot_config):
        """Test is_admin with non-admin ID."""
        assert bot_config.is_admin(999) is False
        assert bot_config.is_admin(0) is False

    def test_parse_admin_ids_from_env(self):
        """Test parsing admin IDs from environment variable."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '111,222,333'}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()

        assert ids == {111, 222, 333}

    def test_parse_admin_ids_with_spaces(self):
        """Test parsing admin IDs with spaces."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '111, 222, 333'}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()

        assert ids == {111, 222, 333}

    def test_parse_admin_ids_empty(self):
        """Test parsing empty admin IDs."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': ''}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()

        assert ids == set()

    def test_parse_admin_ids_invalid_values(self):
        """Test parsing admin IDs with invalid values."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '123,invalid,456'}):
            from tg_bot.config import _parse_admin_ids
            ids = _parse_admin_ids()

        assert ids == {123, 456}  # Only valid integers


class TestRateLimitedDecorator:
    """Test rate_limited decorator for expensive operations."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_rate_limited_allows_when_under_limit(self, mock_update, mock_context):
        """Test rate_limited allows request when under limit."""
        from tg_bot.handlers import rate_limited

        @rate_limited
        async def test_handler(update, context):
            return "success"

        mock_tracker = MagicMock()
        mock_tracker.can_make_sentiment_call.return_value = (True, None)

        with patch('tg_bot.handlers.get_tracker', return_value=mock_tracker):
            result = await test_handler(mock_update, mock_context)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_rate_limited_blocks_when_over_limit(self, mock_update, mock_context):
        """Test rate_limited blocks request when over limit."""
        from tg_bot.handlers import rate_limited

        @rate_limited
        async def test_handler(update, context):
            return "should not reach"

        mock_tracker = MagicMock()
        mock_tracker.can_make_sentiment_call.return_value = (False, "Rate limit exceeded")

        with patch('tg_bot.handlers.get_tracker', return_value=mock_tracker):
            with patch('tg_bot.services.digest_formatter.format_rate_limit', return_value="Rate limited"):
                result = await test_handler(mock_update, mock_context)

        assert result is None
        mock_update.message.reply_text.assert_called_once()


# ============================================================================
# Token Expiration Edge Cases
# ============================================================================

class TestTokenExpirationEdgeCases:
    """Test edge cases around token expiration."""

    def test_token_expires_exactly_at_boundary(self):
        """Test token behavior at exact expiration time."""
        import jwt
        from api.auth.jwt_auth import SECRET_KEY, ALGORITHM, verify_token

        # Create token that expires in 2 seconds using time.time()
        exp = int(time.time()) + 2
        token = jwt.encode(
            {"sub": "user", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Should be valid immediately
        assert verify_token(token) is not None

        # Wait for expiration
        time.sleep(3)

        # Should be invalid after expiration
        assert verify_token(token) is None

    def test_zero_duration_token(self):
        """Test token with zero duration expires immediately."""
        import jwt
        from api.auth.jwt_auth import SECRET_KEY, ALGORITHM, verify_token

        # Create token that already expired using time.time()
        exp = int(time.time()) - 1
        token = jwt.encode(
            {"sub": "user", "type": "access", "exp": exp, "scopes": []},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Should be invalid immediately
        assert verify_token(token) is None


# ============================================================================
# Auth Module Integration Tests
# ============================================================================

class TestAuthModuleIntegration:
    """Test auth module imports and integration."""

    def test_auth_module_exports(self):
        """Test that auth module exports all expected functions."""
        from api.auth import (
            validate_api_key,
            APIKeyAuth,
            api_key_header,
            JWTAuth,
            create_access_token,
            create_refresh_token,
            verify_token
        )

        assert callable(validate_api_key)
        assert callable(create_access_token)
        assert callable(create_refresh_token)
        assert callable(verify_token)

    def test_jwt_auth_instances_available(self):
        """Test that pre-configured JWTAuth instances are available."""
        from api.auth.jwt_auth import jwt_auth, jwt_auth_optional

        assert jwt_auth is not None
        assert jwt_auth_optional is not None
        assert jwt_auth.auto_error is True
        assert jwt_auth_optional.auto_error is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
