"""Tests for bots.shared.allowlist - Telegram user authorization middleware."""

import json
import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


# Import the module under test
from bots.shared.allowlist import (
    AuthorizationLevel,
    load_allowlist,
    check_authorization,
    require_auth,
)


class TestAuthorizationLevel:
    """Test the AuthorizationLevel enum."""

    def test_levels_exist(self):
        assert AuthorizationLevel.OWNER is not None
        assert AuthorizationLevel.ADMIN is not None
        assert AuthorizationLevel.OPERATOR is not None
        assert AuthorizationLevel.OBSERVER is not None

    def test_level_ordering(self):
        """OWNER > ADMIN > OPERATOR > OBSERVER."""
        assert AuthorizationLevel.OWNER.value > AuthorizationLevel.ADMIN.value
        assert AuthorizationLevel.ADMIN.value > AuthorizationLevel.OPERATOR.value
        assert AuthorizationLevel.OPERATOR.value > AuthorizationLevel.OBSERVER.value


class TestLoadAllowlist:
    """Test allowlist loading from file and env."""

    def test_load_from_file(self, tmp_path):
        allowlist_file = tmp_path / "allowlist.json"
        data = {
            "users": {
                "123456": "OWNER",
                "789012": "ADMIN",
                "345678": "OPERATOR",
            }
        }
        allowlist_file.write_text(json.dumps(data))
        result = load_allowlist(str(allowlist_file))
        assert result["123456"] == AuthorizationLevel.OWNER
        assert result["789012"] == AuthorizationLevel.ADMIN
        assert result["345678"] == AuthorizationLevel.OPERATOR

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Missing file => empty dict (allow-all fallback)."""
        result = load_allowlist(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_load_from_env(self, tmp_path, monkeypatch):
        """CLAWDBOT_AUTHORIZED_USERS env var overrides file."""
        monkeypatch.setenv("CLAWDBOT_AUTHORIZED_USERS", "111:OWNER,222:ADMIN")
        result = load_allowlist(str(tmp_path / "nonexistent.json"))
        assert result["111"] == AuthorizationLevel.OWNER
        assert result["222"] == AuthorizationLevel.ADMIN

    def test_env_cleared_falls_back_to_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAWDBOT_AUTHORIZED_USERS", raising=False)
        allowlist_file = tmp_path / "allowlist.json"
        data = {"users": {"999": "OBSERVER"}}
        allowlist_file.write_text(json.dumps(data))
        result = load_allowlist(str(allowlist_file))
        assert result["999"] == AuthorizationLevel.OBSERVER


class TestCheckAuthorization:
    """Test check_authorization function."""

    def test_authorized_owner(self):
        allowlist = {"123": AuthorizationLevel.OWNER}
        assert check_authorization(123, AuthorizationLevel.ADMIN, allowlist) is True

    def test_exact_level_match(self):
        allowlist = {"123": AuthorizationLevel.ADMIN}
        assert check_authorization(123, AuthorizationLevel.ADMIN, allowlist) is True

    def test_insufficient_level(self):
        allowlist = {"123": AuthorizationLevel.OBSERVER}
        assert check_authorization(123, AuthorizationLevel.ADMIN, allowlist) is False

    def test_unknown_user_denied(self):
        allowlist = {"999": AuthorizationLevel.OWNER}
        assert check_authorization(123, AuthorizationLevel.OBSERVER, allowlist) is False

    def test_empty_allowlist_allows_all(self):
        """Empty allowlist = development mode, allow all."""
        assert check_authorization(123, AuthorizationLevel.OWNER, {}) is True

    def test_string_user_id(self):
        allowlist = {"123": AuthorizationLevel.ADMIN}
        assert check_authorization("123", AuthorizationLevel.ADMIN, allowlist) is True


class TestRequireAuthDecorator:
    """Test the require_auth decorator for bot handlers."""

    def test_decorator_blocks_unauthorized(self):
        allowlist = {"999": AuthorizationLevel.OWNER}

        @require_auth(AuthorizationLevel.ADMIN, allowlist=allowlist)
        async def handler(message):
            return "ok"

        msg = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "hacker"

        result = asyncio.get_event_loop().run_until_complete(handler(msg))
        assert result != "ok"  # Should be blocked

    def test_decorator_allows_authorized(self):
        allowlist = {"123": AuthorizationLevel.OWNER}

        @require_auth(AuthorizationLevel.ADMIN, allowlist=allowlist)
        async def handler(message):
            return "ok"

        msg = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "owner"

        result = asyncio.get_event_loop().run_until_complete(handler(msg))
        assert result == "ok"
