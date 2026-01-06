"""GeckoTerminal API client for Solana DEX data with robust error handling."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "geckoterminal_cache"
BASE_URL = "https://api.geckoterminal.com/api/v2"
USER_AGENT = "LifeOS/1.0 (Jarvis GeckoTerminal Client)"

# Rate limiting - GeckoTerminal free tier is limited
RATE_LIMIT_REQUESTS_PER_MINUTE = 30
_request_timestamps: List[float] = []
_last_rate_limit_time: float = 0
_rate_limit_backoff: float = 0


@dataclass
class GeckoTerminalResult:
    """Result wrapper for GeckoTerminal API calls."""
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
    """Check if we should rate limit."""
    global _rate_limit_backoff, _last_rate_limit_time
    
    now = time.time()
    
    if _rate_limit_backoff > 0:
        time_since_limit = now - _last_rate_limit_time
        if time_since_limit < _rate_limit_backoff:
            return True, _rate_limit_backoff - time_since_limit
        _rate_limit_backoff = 0
    
    cutoff = now - 60
    _request_timestamps[:] = [t for t in _request_timestamps if t > cutoff]
    
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
    _rate_limit_backoff = min(_rate_limit_backoff * 2 if _rate_limit_backoff > 0 else 10, 120)
    logger.warning(f"GeckoTerminal rate limit hit, backing off for {_rate_limit_backoff:.1f}s")


def get_api_status() -> Dict[str, Any]:
    """Get current API status."""
    now = time.time()
    cutoff = now - 60
    recent_requests = len([t for t in _request_timestamps if t > cutoff])
    
    return {
        "available": HAS_REQUESTS,
        "requests_last_minute": recent_requests,
        "rate_limit": RATE_LIMIT_REQUESTS_PER_MINUTE,
        "rate_limit_backoff": _rate_limit_backoff if _rate_limit_backoff > 0 else None,
        "base_url": BASE_URL,
    }


def fetch_pools(
    network: str,
    *,
    page: int = 1,
    sort: str = "h24_volume_usd_desc",
    include_tokens: bool = True,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """Fetch pools for a network (legacy API)."""
    params: Dict[str, Any] = {
        "page": page,
        "sort": sort,
    }
    if include_tokens:
        params["include"] = "base_token,quote_token"
    result = _get_json(
        f"{BASE_URL}/networks/{network}/pools",
        params=params,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result.data if result.success else None


def fetch_pools_safe(
    network: str,
    *,
    page: int = 1,
    sort: str = "h24_volume_usd_desc",
    include_tokens: bool = True,
    cache_ttl_seconds: int = 300,
) -> GeckoTerminalResult:
    """Fetch pools for a network with full error info."""
    params: Dict[str, Any] = {
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
    """Fetch token info (legacy API)."""
    result = _get_json(
        f"{BASE_URL}/networks/{network}/tokens/{address}",
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result.data if result.success else None


def fetch_pool_ohlcv(
    network: str,
    pool_address: str,
    timeframe: str,
    *,
    limit: int = 720,
    before_timestamp: Optional[int] = None,
    cache_ttl_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """Fetch OHLCV data for a pool (legacy API)."""
    params: Dict[str, Any] = {"limit": limit}
    if before_timestamp is not None:
        params["before_timestamp"] = before_timestamp
    result = _get_json(
        f"{BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}",
        params=params,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return result.data if result.success else None


def fetch_pool_ohlcv_safe(
    network: str,
    pool_address: str,
    timeframe: str,
    *,
    limit: int = 720,
    before_timestamp: Optional[int] = None,
    cache_ttl_seconds: int = 300,
) -> GeckoTerminalResult:
    """Fetch OHLCV data for a pool with full error info."""
    params: Dict[str, Any] = {"limit": limit}
    if before_timestamp is not None:
        params["before_timestamp"] = before_timestamp
    return _get_json(
        f"{BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}",
        params=params,
        cache_ttl_seconds=cache_ttl_seconds,
    )


def extract_included_tokens(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Extract included token data from API response."""
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
    """Normalize OHLCV list to standard format."""
    normalized: List[Dict[str, Any]] = []
    for row in ohlcv_list:
        if len(row) < 6:
            continue
        try:
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
        except (TypeError, ValueError) as e:
            logger.debug(f"Failed to normalize OHLCV row: {e}")
            continue
    return normalized


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    retries: int = 3,
    backoff_seconds: float = 2.0,
    cache_ttl_seconds: int = 0,
) -> GeckoTerminalResult:
    """Make HTTP request with retry logic and rate limiting."""
    
    if not HAS_REQUESTS:
        return GeckoTerminalResult(success=False, error="requests_not_installed", retryable=False)
    
    # Check cache first
    cache_path = None
    if cache_ttl_seconds > 0:
        cache_path = _cache_path(url, params)
        cached = _read_cache(cache_path, cache_ttl_seconds)
        if cached is not None:
            return GeckoTerminalResult(success=True, data=cached, cached=True)

    # Check rate limit
    should_wait, wait_time = _check_rate_limit()
    if should_wait:
        logger.debug(f"Rate limit active, waiting {wait_time:.1f}s")
        time.sleep(wait_time)

    headers = {"User-Agent": USER_AGENT}
    last_error = None
    last_retryable = True
    
    for attempt in range(retries):
        try:
            _record_request()
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            # Handle rate limiting
            if resp.status_code == 429:
                _record_rate_limit()
                retry_after = resp.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after else _backoff_delay(backoff_seconds, attempt)
                logger.warning(f"GeckoTerminal rate limited, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            
            # Handle server errors with retry
            if resp.status_code in (500, 502, 503, 504):
                logger.warning(f"GeckoTerminal server error {resp.status_code}, retrying...")
                time.sleep(_backoff_delay(backoff_seconds, attempt))
                continue
            
            # Handle client errors (no retry)
            if resp.status_code >= 400:
                error_type = f"http_{resp.status_code}"
                logger.error(f"GeckoTerminal error: {error_type}")
                return GeckoTerminalResult(success=False, error=error_type, retryable=False)
            
            # Success
            payload = resp.json()
            
            # Cache successful response
            if cache_path:
                _write_cache(cache_path, payload)
            
            return GeckoTerminalResult(success=True, data=payload)
            
        except requests.Timeout:
            last_error = "timeout"
            last_retryable = True
            logger.warning(f"GeckoTerminal timeout (attempt {attempt + 1}/{retries})")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.ConnectionError as e:
            last_error = "connection_error"
            last_retryable = True
            logger.warning(f"GeckoTerminal connection error: {e}")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.RequestException as exc:
            last_error = str(exc)
            last_retryable = True
            logger.warning(f"GeckoTerminal request error: {exc}")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except json.JSONDecodeError:
            last_error = "invalid_json"
            last_retryable = False
            logger.error("GeckoTerminal returned invalid JSON")
            break

    logger.error(f"GeckoTerminal request failed after {retries} attempts: {last_error}")
    return GeckoTerminalResult(success=False, error=last_error, retryable=last_retryable)


def _cache_path(url: str, params: Optional[Dict[str, Any]]) -> Path:
    """Generate cache file path."""
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
    if not cached_at or time.time() - cached_at > ttl_seconds:
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
    """Clear all cached data."""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for path in CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except Exception:
            pass
    logger.info(f"Cleared {count} GeckoTerminal cache files")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("API Status:", get_api_status())
    print("\nFetching Solana pools...")
    
    result = fetch_pools_safe("solana", page=1)
    if result.success:
        pools = result.data.get("data", []) if result.data else []
        print(f"Found {len(pools)} pools")
        for pool in pools[:3]:
            attrs = pool.get("attributes", {})
            print(f"  {attrs.get('name')}: ${attrs.get('base_token_price_usd', 'N/A')}")
