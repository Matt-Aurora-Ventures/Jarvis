"""Lightweight GeckoTerminal API client for Solana DEX data (no API key)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "geckoterminal_cache"
BASE_URL = "https://api.geckoterminal.com/api/v2"
USER_AGENT = "LifeOS/1.0 (Jarvis GeckoTerminal Client)"


def fetch_pools(
    network: str,
    *,
    page: int = 1,
    sort: str = "h24_volume_usd_desc",
    include_tokens: bool = True,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    params = {
        "page": page,
        "sort": sort,
    }
    if include_tokens:
        params["include"] = "base_token,quote_token"
    return _get_json(
        f"{BASE_URL}/networks/{network}/pools",
        params=params,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def fetch_token(
    network: str,
    address: str,
    *,
    cache_ttl_seconds: int = 3600,
) -> Optional[Dict[str, Any]]:
    return _get_json(
        f"{BASE_URL}/networks/{network}/tokens/{address}",
        cache_ttl_seconds=cache_ttl_seconds,
    )


def fetch_pool_ohlcv(
    network: str,
    pool_address: str,
    timeframe: str,
    *,
    limit: int = 720,
    before_timestamp: Optional[int] = None,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any] = {"limit": limit}
    if before_timestamp is not None:
        params["before_timestamp"] = before_timestamp
    return _get_json(
        f"{BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}",
        params=params,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def extract_included_tokens(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    included = payload.get("included", []) or []
    tokens: Dict[str, Dict[str, Any]] = {}
    for item in included:
        if item.get("type") != "token":
            continue
        token_id = item.get("id")
        if not token_id:
            continue
        tokens[token_id] = item.get("attributes", {}) or {}
    return tokens


def normalize_ohlcv_list(ohlcv_list: List[List[Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in ohlcv_list:
        if len(row) < 6:
            continue
        timestamp, open_price, high, low, close, volume = row[:6]
        normalized.append(
            {
                "timestamp": int(timestamp),
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
            }
        )
    return normalized


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
        print(f"[geckoterminal] request failed: {last_error}")
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
