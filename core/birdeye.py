"""Birdeye API client for fast Solana token data."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "birdeye_cache"
BASE_URL = "https://public-api.birdeye.so"
USER_AGENT = "LifeOS/1.0 (Jarvis Birdeye Client)"

def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    return min(max_delay, base * (2 ** attempt))


def _load_api_key() -> Optional[str]:
    secrets_path = ROOT / "secrets" / "keys.json"
    if secrets_path.exists():
        try:
            data = json.loads(secrets_path.read_text())
            return data.get("birdeye", {}).get("api_key")
        except (json.JSONDecodeError, KeyError):
            pass
    env_key = os.getenv("BIRDEYE_API_KEY")
    if env_key:
        return env_key
    return None


def load_api_key() -> Optional[str]:
    """Load BirdEye API key from secrets if available."""
    return _load_api_key()


def has_api_key() -> bool:
    """Return True if a BirdEye API key is configured."""
    return bool(_load_api_key())


def fetch_token_price(
    address: str,
    *,
    chain: str = "solana",
    cache_ttl_seconds: int = 60,
) -> Optional[Dict[str, Any]]:
    """Fetch current token price."""
    api_key = load_api_key()
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain
    
    return _get_json(
        f"{BASE_URL}/defi/price",
        params={"address": address},
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def fetch_ohlcv(
    address: str,
    *,
    timeframe: str = "1H",
    chain: str = "solana",
    limit: int = 720,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Fetch OHLCV candle data.
    
    Timeframes: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
    """
    api_key = load_api_key()
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain
    
    # Calculate time range
    time_to = int(time.time())
    
    # Map timeframe to seconds
    tf_seconds = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1H": 3600, "2H": 7200, "4H": 14400, "6H": 21600,
        "8H": 28800, "12H": 43200, "1D": 86400, "3D": 259200,
        "1W": 604800, "1M": 2592000,
    }
    interval_secs = tf_seconds.get(timeframe, 3600)
    time_from = time_to - (limit * interval_secs)
    
    return _get_json(
        f"{BASE_URL}/defi/ohlcv",
        params={
            "address": address,
            "type": timeframe,
            "time_from": time_from,
            "time_to": time_to,
        },
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def fetch_token_overview(
    address: str,
    *,
    chain: str = "solana",
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """Fetch token overview with market data."""
    api_key = load_api_key()
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain
    
    return _get_json(
        f"{BASE_URL}/defi/token_overview",
        params={"address": address},
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def fetch_trending_tokens(
    *,
    chain: str = "solana",
    sort_by: Optional[str] = "rank",
    sort_type: Optional[str] = "asc",
    limit: int = 20,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """Fetch trending tokens."""
    api_key = load_api_key()
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain

    params = {
        "offset": 0,
        "limit": limit,
    }
    if sort_by:
        params["sort_by"] = sort_by
    if sort_type:
        params["sort_type"] = sort_type

    payload = _get_json(
        f"{BASE_URL}/defi/token_trending",
        params=params,
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )

    if payload is None and (sort_by or sort_type):
        payload = _get_json(
            f"{BASE_URL}/defi/token_trending",
            params={"offset": 0, "limit": limit},
            headers=headers,
            cache_ttl_seconds=cache_ttl_seconds,
        )

    return payload


def normalize_ohlcv(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize Birdeye OHLCV response to standard format."""
    items = data.get("data", {}).get("items", [])
    normalized = []
    for item in items:
        normalized.append({
            "timestamp": int(item.get("unixTime", 0)),
            "open": float(item.get("o", 0)),
            "high": float(item.get("h", 0)),
            "low": float(item.get("l", 0)),
            "close": float(item.get("c", 0)),
            "volume": float(item.get("v", 0)),
        })
    return sorted(normalized, key=lambda x: x["timestamp"])


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
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

    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
        
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=req_headers, params=params, timeout=timeout)
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
        print(f"[birdeye] request failed: {last_error}")
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


if __name__ == "__main__":
    # Test with a known token (RAY)
    address = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
    print(f"Testing Birdeye API with RAY token...")
    
    price = fetch_token_price(address)
    if price:
        print(f"Price: ${price.get('data', {}).get('value', 'N/A')}")
    
    ohlcv = fetch_ohlcv(address, timeframe="1H", limit=24)
    if ohlcv:
        candles = normalize_ohlcv(ohlcv)
        print(f"Got {len(candles)} hourly candles")
