"""Birdeye API client for fast Solana token data."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "birdeye_cache"
BASE_URL = "https://public-api.birdeye.so"
USER_AGENT = "LifeOS/1.0 (Jarvis Birdeye Client)"

# Rate limiting settings
RATE_LIMIT_REQUESTS_PER_MINUTE = 100  # BirdEye free tier
_request_timestamps: List[float] = []
_last_rate_limit_time: float = 0
_rate_limit_backoff: float = 0


@dataclass
class BirdEyeResult:
    """Result wrapper for BirdEye API calls."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cached: bool = False
    retryable: bool = True


def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    """Exponential backoff with jitter."""
    delay = min(max_delay, base * (2 ** attempt))
    jitter = delay * 0.1 * random.random()
    return delay + jitter


def _check_rate_limit() -> Tuple[bool, float]:
    """Check if we should rate limit. Returns (should_wait, wait_seconds)."""
    global _rate_limit_backoff, _last_rate_limit_time
    
    now = time.time()
    
    # If we hit a rate limit recently, enforce backoff
    if _rate_limit_backoff > 0:
        time_since_limit = now - _last_rate_limit_time
        if time_since_limit < _rate_limit_backoff:
            return True, _rate_limit_backoff - time_since_limit
        _rate_limit_backoff = 0  # Reset backoff
    
    # Clean old timestamps (older than 60 seconds)
    cutoff = now - 60
    _request_timestamps[:] = [t for t in _request_timestamps if t > cutoff]
    
    # Check if we're at the limit
    if len(_request_timestamps) >= RATE_LIMIT_REQUESTS_PER_MINUTE:
        oldest = _request_timestamps[0]
        wait_time = 60 - (now - oldest) + 0.1
        if wait_time > 0:
            return True, wait_time
    
    return False, 0


def _record_request():
    """Record a request for rate limiting."""
    _request_timestamps.append(time.time())


def _record_rate_limit():
    """Record that we hit a rate limit."""
    global _rate_limit_backoff, _last_rate_limit_time
    _last_rate_limit_time = time.time()
    _rate_limit_backoff = min(_rate_limit_backoff * 2 if _rate_limit_backoff > 0 else 5, 60)
    logger.warning(f"BirdEye rate limit hit, backing off for {_rate_limit_backoff:.1f}s")


def _load_api_key() -> Optional[str]:
    """Load API key from secrets file or environment."""
    secrets_path = ROOT / "secrets" / "keys.json"
    if secrets_path.exists():
        try:
            data = json.loads(secrets_path.read_text())
            key = data.get("birdeye", {}).get("api_key")
            if key:
                return key
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load BirdEye key from secrets: {e}")
    
    env_key = os.getenv("BIRDEYE_API_KEY")
    if env_key:
        return env_key
    
    logger.debug("No BirdEye API key found")
    return None


def load_api_key() -> Optional[str]:
    """Load BirdEye API key from secrets if available."""
    return _load_api_key()


def has_api_key() -> bool:
    """Return True if a BirdEye API key is configured."""
    return bool(_load_api_key())


def get_api_status() -> Dict[str, Any]:
    """Get current API status including rate limit info."""
    now = time.time()
    cutoff = now - 60
    recent_requests = len([t for t in _request_timestamps if t > cutoff])
    
    return {
        "has_api_key": has_api_key(),
        "requests_last_minute": recent_requests,
        "rate_limit": RATE_LIMIT_REQUESTS_PER_MINUTE,
        "rate_limit_backoff": _rate_limit_backoff if _rate_limit_backoff > 0 else None,
        "base_url": BASE_URL,
    }


def fetch_token_price(
    address: str,
    *,
    chain: str = "solana",
    cache_ttl_seconds: int = 60,
) -> Optional[Dict[str, Any]]:
    """Fetch current token price."""
    api_key = load_api_key()
    if not api_key:
        logger.warning("No BirdEye API key - price fetch will likely fail")
    
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain
    
    result = _get_json(
        f"{BASE_URL}/defi/price",
        params={"address": address},
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result.data if result.success else None


def fetch_token_price_safe(
    address: str,
    *,
    chain: str = "solana",
    cache_ttl_seconds: int = 60,
) -> BirdEyeResult:
    """Fetch current token price with full error info."""
    api_key = load_api_key()
    if not api_key:
        return BirdEyeResult(success=False, error="no_api_key", retryable=False)
    
    headers = {"X-API-KEY": api_key, "x-chain": chain}
    
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
    if not api_key:
        logger.warning("No BirdEye API key - OHLCV fetch will likely fail")
    
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
    
    result = _get_json(
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
    return result.data if result.success else None


def fetch_ohlcv_safe(
    address: str,
    *,
    timeframe: str = "1H",
    chain: str = "solana",
    limit: int = 720,
    cache_ttl_seconds: int = 300,
) -> BirdEyeResult:
    """Fetch OHLCV with full error info."""
    api_key = load_api_key()
    if not api_key:
        return BirdEyeResult(success=False, error="no_api_key", retryable=False)
    
    headers = {"X-API-KEY": api_key, "x-chain": chain}
    
    time_to = int(time.time())
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
    if not api_key:
        logger.warning("No BirdEye API key - overview fetch will likely fail")
    
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain
    
    result = _get_json(
        f"{BASE_URL}/defi/token_overview",
        params={"address": address},
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result.data if result.success else None


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
    if not api_key:
        logger.warning("No BirdEye API key - trending fetch will likely fail")
    
    headers = {"X-API-KEY": api_key} if api_key else {}
    headers["x-chain"] = chain

    params: Dict[str, Any] = {
        "offset": 0,
        "limit": limit,
    }
    if sort_by:
        params["sort_by"] = sort_by
    if sort_type:
        params["sort_type"] = sort_type

    result = _get_json(
        f"{BASE_URL}/defi/token_trending",
        params=params,
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )

    # Fallback without sort params if failed
    if not result.success and (sort_by or sort_type):
        logger.debug("Retrying trending without sort params")
        result = _get_json(
            f"{BASE_URL}/defi/token_trending",
            params={"offset": 0, "limit": limit},
            headers=headers,
            cache_ttl_seconds=cache_ttl_seconds,
        )

    return result.data if result.success else None


def fetch_trending_tokens_safe(
    *,
    chain: str = "solana",
    limit: int = 20,
    cache_ttl_seconds: int = 300,
) -> BirdEyeResult:
    """Fetch trending tokens with full error info."""
    api_key = load_api_key()
    if not api_key:
        return BirdEyeResult(success=False, error="no_api_key", retryable=False)
    
    headers = {"X-API-KEY": api_key, "x-chain": chain}
    
    return _get_json(
        f"{BASE_URL}/defi/token_trending",
        params={"offset": 0, "limit": limit},
        headers=headers,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def normalize_ohlcv(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize Birdeye OHLCV response to standard format."""
    items = data.get("data", {}).get("items", [])
    normalized = []
    for item in items:
        try:
            normalized.append({
                "timestamp": int(item.get("unixTime", 0)),
                "open": float(item.get("o", 0)),
                "high": float(item.get("h", 0)),
                "low": float(item.get("l", 0)),
                "close": float(item.get("c", 0)),
                "volume": float(item.get("v", 0)),
            })
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to normalize OHLCV item: {e}")
            continue
    return sorted(normalized, key=lambda x: x["timestamp"])


def _classify_http_error(status_code: int, response_text: str = "") -> Tuple[str, bool]:
    """Classify HTTP errors and determine if retryable."""
    if status_code == 401:
        return "invalid_api_key", False
    elif status_code == 403:
        return "forbidden", False
    elif status_code == 404:
        return "not_found", False
    elif status_code == 429:
        return "rate_limited", True
    elif status_code in (500, 502, 503, 504):
        return "server_error", True
    elif status_code >= 400:
        return f"http_{status_code}", False
    return "unknown", True


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 20,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    cache_ttl_seconds: int = 0,
) -> BirdEyeResult:
    """Make HTTP request with retry logic and rate limiting."""
    
    # Check cache first
    cache_path = None
    if cache_ttl_seconds > 0:
        cache_path = _cache_path(url, params)
        cached = _read_cache(cache_path, cache_ttl_seconds)
        if cached is not None:
            return BirdEyeResult(success=True, data=cached, cached=True)

    # Check rate limit
    should_wait, wait_time = _check_rate_limit()
    if should_wait:
        logger.debug(f"Rate limit active, waiting {wait_time:.1f}s")
        time.sleep(wait_time)

    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    
    last_error = None
    last_retryable = True
    
    for attempt in range(retries):
        try:
            _record_request()
            resp = requests.get(url, headers=req_headers, params=params, timeout=timeout)
            
            # Handle rate limiting
            if resp.status_code == 429:
                _record_rate_limit()
                retry_after = resp.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after else _backoff_delay(backoff_seconds, attempt)
                logger.warning(f"BirdEye rate limited, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            
            # Handle server errors with retry
            if resp.status_code in (500, 502, 503, 504):
                logger.warning(f"BirdEye server error {resp.status_code}, retrying...")
                time.sleep(_backoff_delay(backoff_seconds, attempt))
                continue
            
            # Handle client errors (no retry)
            if resp.status_code >= 400:
                error_type, retryable = _classify_http_error(resp.status_code, resp.text)
                logger.error(f"BirdEye error: {error_type} ({resp.status_code})")
                return BirdEyeResult(success=False, error=error_type, retryable=retryable)
            
            # Success
            resp.raise_for_status()
            payload = resp.json()
            
            # Check for API-level errors in response
            if isinstance(payload, dict) and payload.get("success") is False:
                error_msg = payload.get("message", "api_error")
                logger.warning(f"BirdEye API error: {error_msg}")
                return BirdEyeResult(success=False, error=error_msg, retryable=False)
            
            # Cache successful response
            if cache_path:
                _write_cache(cache_path, payload)
            
            return BirdEyeResult(success=True, data=payload)
            
        except requests.Timeout:
            last_error = "timeout"
            last_retryable = True
            logger.warning(f"BirdEye timeout (attempt {attempt + 1}/{retries})")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.ConnectionError as e:
            last_error = "connection_error"
            last_retryable = True
            logger.warning(f"BirdEye connection error: {e} (attempt {attempt + 1}/{retries})")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.RequestException as exc:
            last_error = str(exc)
            last_retryable = True
            logger.warning(f"BirdEye request error: {exc} (attempt {attempt + 1}/{retries})")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except json.JSONDecodeError as e:
            last_error = "invalid_json"
            last_retryable = False
            logger.error(f"BirdEye returned invalid JSON: {e}")
            break

    logger.error(f"BirdEye request failed after {retries} attempts: {last_error}")
    return BirdEyeResult(success=False, error=last_error, retryable=last_retryable)


def _cache_path(url: str, params: Optional[Dict[str, Any]]) -> Path:
    """Generate cache file path for a request."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = url
    if params:
        params_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
        key = f"{url}?{params_str}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / f"{digest}.json"


def _read_cache(path: Path, ttl_seconds: int) -> Optional[Dict[str, Any]]:
    """Read from cache if valid."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        logger.debug(f"Invalid cache file: {path}")
        return None
    cached_at = payload.get("cached_at")
    if not cached_at:
        return None
    if time.time() - cached_at > ttl_seconds:
        logger.debug(f"Cache expired: {path}")
        return None
    return payload.get("data")


def _write_cache(path: Path, data: Dict[str, Any]) -> None:
    """Write data to cache."""
    try:
        payload = {"cached_at": time.time(), "data": data}
        path.write_text(json.dumps(payload))
    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")


def clear_cache() -> int:
    """Clear all cached data. Returns number of files deleted."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except Exception:
            pass
    logger.info(f"Cleared {count} BirdEye cache files")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # Test API status
    print("API Status:", get_api_status())
    
    # Test with a known token (RAY)
    address = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
    print(f"\nTesting Birdeye API with RAY token...")
    
    result = fetch_token_price_safe(address)
    if result.success:
        print(f"Price: ${result.data.get('data', {}).get('value', 'N/A')}")
    else:
        print(f"Price fetch failed: {result.error} (retryable: {result.retryable})")
    
    ohlcv = fetch_ohlcv(address, timeframe="1H", limit=24)
    if ohlcv:
        candles = normalize_ohlcv(ohlcv)
        print(f"Got {len(candles)} hourly candles")
    else:
        print("OHLCV fetch failed")
