"""Lightweight DexScreener API client with caching."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "dexscreener_cache"
BASE_URL = "https://api.dexscreener.com/latest/dex"
USER_AGENT = "LifeOS/1.0 (Jarvis DexScreener Client)"


def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    return min(max_delay, base * (2 ** attempt))


def fetch_token_pairs(token_address: str, *, cache_ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/tokens/{token_address}"
    return _get_json(url, cache_ttl_seconds=cache_ttl_seconds)


def search_pairs(query: str, *, cache_ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/search"
    params = {"q": query}
    return _get_json(url, params=params, cache_ttl_seconds=cache_ttl_seconds)


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
            if resp.status_code in (429, 503):
                time.sleep(_backoff_delay(backoff_seconds, attempt))
                continue
            resp.raise_for_status()
            payload = resp.json()
            if cache_path:
                _write_cache(cache_path, payload)
            return payload
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(_backoff_delay(backoff_seconds, attempt))

    if last_error:
        print(f"[dexscreener] request failed: {last_error}")
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
