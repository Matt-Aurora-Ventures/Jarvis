"""Tests for bots.shared.allowlist - Telegram user authorization middleware."""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bots.shared.allowlist import (
    AuthorizationLevel,
    load_allowlist,
    check_authorization,
    require_auth,
    _get_global_allowlist,
)


class TestAuthorizationLevel:
    def test_ordering(self):
        assert AuthorizationLevel.OBSERVER < AuthorizationLevel.OPERATOR
        assert AuthorizationLevel.OPERATOR < AuthorizationLevel.ADMIN
        assert AuthorizationLevel.ADMIN < AuthorizationLevel.OWNER

    def test_values(self):
        assert AuthorizationLevel.OBSERVER == 10
        assert AuthorizationLevel.OWNER == 40


class TestLoadAllowlist:
    def test_from_env_var(self, monkeypatch):
        monkeypatch.setenv("CLAWDBOT_AUTHORIZED_USERS", "123:OWNER,456:ADMIN")
        result = load_allowlist()
        assert result == {
            "123": AuthorizationLevel.OWNER,
            "456": AuthorizationLevel.ADMIN,
        }

    def test_from_env_var_with_spaces(self, monkeypatch):
        monkeypatch.setenv("CLAWDBOT_AUTHORIZED_USERS", " 123 : OWNER , 456 : ADMIN ")
        result = load_allowlist()
        assert result["123"] == AuthorizationLevel.OWNER

    def test_empty_env_falls_through(self, monkeypatch):
        monkeypatch.setenv("CLAWDBOT_AUTHORIZED_USERS", "")
        # No file either -> empty dict
        result = load_allowlist(filepath="/nonexistent/path.json")
        assert result == {}

    def test_from_json_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAWDBOT_AUTHORIZED_USERS", raising=False)
        f = tmp_path / "allowlist.json"
        f.write_text(json.dumps({"users": {"999": "OPERATOR"}}))
        result = load_allowlist(filepath=str(f))
        assert result == {"999": AuthorizationLevel.OPERATOR}

    def test_no_config_returns_empty(self, monkeypatch):
        monkeypatch.delenv("CLAWDBOT_AUTHORIZED_USERS", raising=False)
        result = load_allowlist(filepath="/nonexistent/allowlist.json")
        assert result == {}

    def test_invalid_level_in_env(self, monkeypatch):
        monkeypatch.setenv("CLAWDBOT_AUTHORIZED_USERS", "123:SUPERUSER")
        result = load_allowlist()
        assert result == {}  # Invalid level skipped


class TestCheckAuthorization:
    def test_empty_allowlist_allows_all(self):
        assert check_authorization(999, AuthorizationLevel.OWNER, {}) is True

    def test_authorized_user(self):
        al = {"123": AuthorizationLevel.ADMIN}
        assert check_authorization(123, AuthorizationLevel.ADMIN, al) is True
        assert check_authorization(123, AuthorizationLevel.OBSERVER, al) is True

    def test_insufficient_level(self):
        al = {"123": AuthorizationLevel.OBSERVER}
        assert check_authorization(123, AuthorizationLevel.ADMIN, al) is False

    def test_unknown_user_denied(self):
        al = {"123": AuthorizationLevel.OWNER}
        assert check_authorization(999, AuthorizationLevel.OBSERVER, al) is False

    def test_int_and_str_user_id(self):
        al = {"123": AuthorizationLevel.OWNER}
        assert check_authorization(123, AuthorizationLevel.OWNER, al) is True
        assert check_authorization("123", AuthorizationLevel.OWNER, al) is True


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_authorized_passes(self):
        al = {"123": AuthorizationLevel.ADMIN}

        @require_auth(AuthorizationLevel.ADMIN, allowlist=al)
        async def handler(message):
            return "ok"

        msg = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "testuser"
        result = await handler(msg)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unauthorized_blocked(self):
        al = {"123": AuthorizationLevel.OBSERVER}

        @require_auth(AuthorizationLevel.OWNER, allowlist=al)
        async def handler(message):
            return "ok"

        msg = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "testuser"
        msg.text = "/admin_command"
        result = await handler(msg)
        assert result is None

    @pytest.mark.asyncio
    async def test_dev_mode_allows_all(self):
        @require_auth(AuthorizationLevel.OWNER, allowlist={})
        async def handler(message):
            return "ok"

        msg = MagicMock()
        msg.from_user.id = 999
        result = await handler(msg)
        assert result == "ok"
