from __future__ import annotations

import time
from pathlib import Path

from core.jupiter_perps.control_board import (
    _REQUIRED_TOKEN_CLAIMS,
    _ReplayCache,
    _issue_signed_token,
    _verify_signed_token,
)


def test_signed_token_claims_and_validation() -> None:
    secret = "test-secret"
    token = _issue_signed_token(
        secret,
        sub="user-1",
        role="operator",
        issuer="jarvis-sniper",
        audience="vanguard-control",
        ttl_seconds=60,
    )
    payload = _verify_signed_token(
        token,
        secret,
        expected_issuer="jarvis-sniper",
        expected_audience="vanguard-control",
        required_claims=_REQUIRED_TOKEN_CLAIMS,
        max_ttl_seconds=60,
    )
    assert payload is not None
    assert payload["role"] == "operator"
    assert "vanguard:control" in payload["scopes"]


def test_token_replay_cache_is_one_time(tmp_path: Path) -> None:
    cache = _ReplayCache(tmp_path / "session_replay_cache.json", ttl_seconds=600)
    jti = "replay-jti"
    exp = int(time.time()) + 60
    assert cache.mark_once(jti, exp) is True
    assert cache.mark_once(jti, exp) is False


def test_missing_control_scope_fails_for_operator_role() -> None:
    secret = "test-secret"
    token = _issue_signed_token(
        secret,
        sub="user-2",
        role="operator",
        issuer="jarvis-sniper",
        audience="vanguard-control",
        ttl_seconds=60,
        scopes={"vanguard:open", "vanguard:read"},
    )
    payload = _verify_signed_token(
        token,
        secret,
        expected_issuer="jarvis-sniper",
        expected_audience="vanguard-control",
        required_claims=_REQUIRED_TOKEN_CLAIMS,
        max_ttl_seconds=60,
    )
    assert payload is None
