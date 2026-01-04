"""Minimal RugCheck client for liquidity lock checks on Solana tokens."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "rugcheck_cache"
BASE_URL = "https://api.rugcheck.xyz/v1/tokens"
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USER_AGENT = "LifeOS/1.0 (Jarvis RugCheck Client)"


def fetch_report(mint: str, *, cache_ttl_seconds: int = 3600) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/{mint}/report"
    return _get_json(url, cache_ttl_seconds=cache_ttl_seconds)


def has_locked_liquidity(
    report: Optional[Dict[str, Any]],
    *,
    min_locked_pct: float = 50.0,
    min_locked_usd: float = 0.0,
) -> bool:
    if not report:
        return False

    markets = report.get("markets") or []
    for market in markets:
        lp = market.get("lp", {}) or {}
        pct = _to_float(lp.get("lpLockedPct"))
        usd = _to_float(lp.get("lpLockedUSD"))
        if pct >= min_locked_pct and usd >= min_locked_usd:
            return True

    lockers = report.get("lockers") or {}
    for locker in lockers.values():
        usd = _to_float(locker.get("usdcLocked"))
        if usd >= min_locked_usd and min_locked_pct <= 0:
            return True

    return False


def best_lock_stats(report: Optional[Dict[str, Any]]) -> Dict[str, float]:
    if not report:
        return {"best_lp_locked_pct": 0.0, "best_lp_locked_usd": 0.0}
    best_pct = 0.0
    best_usd = 0.0
    markets = report.get("markets") or []
    for market in markets:
        lp = market.get("lp", {}) or {}
        pct = _to_float(lp.get("lpLockedPct"))
        usd = _to_float(lp.get("lpLockedUSD"))
        if pct > best_pct or (pct == best_pct and usd > best_usd):
            best_pct = pct
            best_usd = usd
    return {"best_lp_locked_pct": best_pct, "best_lp_locked_usd": best_usd}


def evaluate_safety(
    report: Optional[Dict[str, Any]],
    *,
    min_locked_pct: float = 50.0,
    min_locked_usd: float = 0.0,
    require_spl_program: bool = True,
    require_authorities_revoked: bool = True,
    max_transfer_fee_bps: float = 0.0,
    require_not_rugged: bool = True,
) -> Dict[str, Any]:
    issues: list[str] = []
    if not report:
        return {"ok": False, "issues": ["missing_report"], "details": {}}

    if require_not_rugged and report.get("rugged") is True:
        issues.append("rugged_flag")

    if require_spl_program and report.get("tokenProgram") != SPL_TOKEN_PROGRAM:
        issues.append("non_spl_program")

    if require_authorities_revoked:
        mint_auth = _authority_value(report, "mintAuthority")
        freeze_auth = _authority_value(report, "freezeAuthority")
        if mint_auth:
            issues.append("mint_authority_active")
        if freeze_auth:
            issues.append("freeze_authority_active")

    if max_transfer_fee_bps is not None:
        fee_pct = _to_float((report.get("transferFee") or {}).get("pct"))
        fee_bps = fee_pct * 100
        if fee_bps > max_transfer_fee_bps:
            issues.append("transfer_fee")

    if not has_locked_liquidity(report, min_locked_pct=min_locked_pct, min_locked_usd=min_locked_usd):
        issues.append("liquidity_not_locked")

    details = best_lock_stats(report)
    details["token_program"] = report.get("tokenProgram")
    details["mint_authority"] = _authority_value(report, "mintAuthority")
    details["freeze_authority"] = _authority_value(report, "freezeAuthority")
    details["transfer_fee_bps"] = _to_float((report.get("transferFee") or {}).get("pct")) * 100
    return {"ok": not issues, "issues": issues, "details": details}


def _authority_value(report: Dict[str, Any], key: str) -> Optional[str]:
    value = report.get(key)
    if value:
        return str(value)
    token = report.get("token") or {}
    token_value = token.get(key)
    if token_value:
        return str(token_value)
    return None


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    cache_ttl_seconds: int = 0,
) -> Optional[Dict[str, Any]]:
    cache_path = None
    if cache_ttl_seconds > 0:
        cache_path = _cache_path(url, params)
        cached = _read_cache(cache_path, cache_ttl_seconds)
        if cached is not None:
            return cached

    headers = {"User-Agent": USER_AGENT}
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            resp.raise_for_status()
            payload = resp.json()
            if cache_path:
                _write_cache(cache_path, payload)
            return payload
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(backoff_seconds * (attempt + 1))

    if last_error:
        print(f"[rugcheck] request failed: {last_error}")
    return None


def _cache_path(url: str, params: Optional[Dict[str, Any]]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = url
    if params:
        params_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
        key = f"{url}?{params_str}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / f"{digest}.json"


def _read_cache(path: Path, ttl_seconds: int) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    cached_at = payload.get("cached_at")
    if not cached_at:
        return None
    if time.time() - cached_at > ttl_seconds:
        return None
    return payload.get("data")


def _write_cache(path: Path, data: Dict[str, Any]) -> None:
    payload = {"cached_at": time.time(), "data": data}
    path.write_text(json.dumps(payload))


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
