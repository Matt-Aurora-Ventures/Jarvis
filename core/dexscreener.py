"""DexScreener API client for Solana token data with robust error handling."""

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
CACHE_DIR = ROOT / "data" / "trader" / "dexscreener_cache"
BASE_URL = "https://api.dexscreener.com"
USER_AGENT = "LifeOS/1.0 (Jarvis DexScreener Client)"

# Rate limiting - DexScreener is generous but we should still be careful
RATE_LIMIT_REQUESTS_PER_MINUTE = 300
_request_timestamps: List[float] = []
_last_rate_limit_time: float = 0
_rate_limit_backoff: float = 0


@dataclass
class DexScreenerResult:
    """Result wrapper for DexScreener API calls."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cached: bool = False
    retryable: bool = True


@dataclass
class TokenPair:
    """Normalized token pair data."""
    chain_id: str
    dex_id: str
    pair_address: str
    base_token_address: str
    base_token_symbol: str
    base_token_name: str
    quote_token_address: str
    quote_token_symbol: str
    price_usd: float
    price_native: float
    liquidity_usd: float
    volume_24h: float
    volume_6h: float
    volume_1h: float
    price_change_24h: float
    price_change_6h: float
    price_change_1h: float
    price_change_5m: float
    txns_24h_buys: int
    txns_24h_sells: int
    created_at: Optional[int] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "TokenPair":
        """Create TokenPair from DexScreener API response."""
        base = data.get("baseToken", {})
        quote = data.get("quoteToken", {})
        liquidity = data.get("liquidity", {})
        volume = data.get("volume", {})
        price_change = data.get("priceChange", {})
        txns = data.get("txns", {}).get("h24", {})
        
        return cls(
            chain_id=data.get("chainId", ""),
            dex_id=data.get("dexId", ""),
            pair_address=data.get("pairAddress", ""),
            base_token_address=base.get("address", ""),
            base_token_symbol=base.get("symbol", ""),
            base_token_name=base.get("name", ""),
            quote_token_address=quote.get("address", ""),
            quote_token_symbol=quote.get("symbol", ""),
            price_usd=_safe_float(data.get("priceUsd")),
            price_native=_safe_float(data.get("priceNative")),
            liquidity_usd=_safe_float(liquidity.get("usd")),
            volume_24h=_safe_float(volume.get("h24")),
            volume_6h=_safe_float(volume.get("h6")),
            volume_1h=_safe_float(volume.get("h1")),
            price_change_24h=_safe_float(price_change.get("h24")),
            price_change_6h=_safe_float(price_change.get("h6")),
            price_change_1h=_safe_float(price_change.get("h1")),
            price_change_5m=_safe_float(price_change.get("m5")),
            txns_24h_buys=int(txns.get("buys", 0)),
            txns_24h_sells=int(txns.get("sells", 0)),
            created_at=data.get("pairCreatedAt"),
        )


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    _rate_limit_backoff = min(_rate_limit_backoff * 2 if _rate_limit_backoff > 0 else 5, 60)
    logger.warning(f"DexScreener rate limit hit, backing off for {_rate_limit_backoff:.1f}s")


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


# Legacy compatibility functions
def fetch_token_pairs(token_address: str, *, cache_ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
    """Fetch pairs for a token address (legacy API)."""
    result = get_pairs_by_token(token_address, cache_ttl_seconds=cache_ttl_seconds)
    return result.data if result.success else None


def search_pairs(
    query: str,
    *,
    cache_ttl_seconds: int = 60,
) -> DexScreenerResult:
    """
    Search for trading pairs by query.
    
    Args:
        query: Search query (e.g., "SOL", token address, pair name)
        cache_ttl_seconds: How long to cache results
    
    Returns:
        DexScreenerResult with list of pairs
    """
    return _get_json(
        f"{BASE_URL}/latest/dex/search",
        params={"q": query},
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_pairs_by_token(
    token_address: str,
    *,
    cache_ttl_seconds: int = 60,
) -> DexScreenerResult:
    """
    Get all pairs for a specific token address.
    """
    return _get_json(
        f"{BASE_URL}/latest/dex/tokens/{token_address}",
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_pair_by_address(
    chain_id: str,
    pair_address: str,
    *,
    cache_ttl_seconds: int = 60,
) -> DexScreenerResult:
    """
    Get specific pair by chain and address.
    """
    return _get_json(
        f"{BASE_URL}/latest/dex/pairs/{chain_id}/{pair_address}",
        cache_ttl_seconds=cache_ttl_seconds,
    )


def get_solana_trending(
    *,
    min_liquidity: float = 10_000,
    min_volume_24h: float = 100_000,
    max_liquidity: float = 1_000_000,
    limit: int = 50,
    cache_ttl_seconds: int = 120,
) -> List[TokenPair]:
    """
    Get trending Solana tokens with momentum.
    """
    result = search_pairs("SOL", cache_ttl_seconds=cache_ttl_seconds)
    
    if not result.success:
        logger.warning(f"Failed to fetch Solana trending: {result.error}")
        return []
    
    pairs = result.data.get("pairs", []) if result.data else []
    filtered: List[TokenPair] = []
    
    for pair_data in pairs:
        if pair_data.get("chainId") != "solana":
            continue
        
        try:
            pair = TokenPair.from_api(pair_data)
            
            if pair.liquidity_usd < min_liquidity:
                continue
            if pair.liquidity_usd > max_liquidity:
                continue
            if pair.volume_24h < min_volume_24h:
                continue
            
            filtered.append(pair)
            
            if len(filtered) >= limit:
                break
                
        except Exception as e:
            logger.debug(f"Failed to parse pair: {e}")
            continue
    
    filtered.sort(key=lambda p: p.volume_24h, reverse=True)
    logger.info(f"Found {len(filtered)} trending Solana pairs")
    return filtered


def get_momentum_tokens(
    *,
    min_liquidity: float = 10_000,
    min_volume_24h: float = 100_000,
    min_momentum: float = 0.02,
    limit: int = 20,
    cache_ttl_seconds: int = 120,
) -> List[TokenPair]:
    """
    Get Solana tokens showing momentum (recent price movement).
    """
    result = search_pairs("SOL", cache_ttl_seconds=cache_ttl_seconds)
    
    if not result.success:
        logger.warning(f"Failed to fetch momentum tokens: {result.error}")
        return []
    
    pairs = result.data.get("pairs", []) if result.data else []
    momentum_pairs: List[Tuple[TokenPair, float]] = []
    
    for pair_data in pairs:
        if pair_data.get("chainId") != "solana":
            continue
        
        try:
            pair = TokenPair.from_api(pair_data)
            
            if pair.liquidity_usd < min_liquidity:
                continue
            if pair.volume_24h < min_volume_24h:
                continue
            
            momentum_score = (
                abs(pair.price_change_5m) * 0.4 +
                abs(pair.price_change_1h) * 0.3 +
                abs(pair.price_change_6h) * 0.2 +
                abs(pair.price_change_24h) * 0.1
            )
            
            has_momentum = (
                abs(pair.price_change_5m) > min_momentum * 100 or
                abs(pair.price_change_1h) > min_momentum * 100 * 5 or
                abs(pair.price_change_6h) > min_momentum * 100 * 10
            )
            
            if not has_momentum:
                continue
            
            momentum_pairs.append((pair, momentum_score))
            
        except Exception as e:
            logger.debug(f"Failed to parse pair: {e}")
            continue
    
    momentum_pairs.sort(key=lambda x: x[1], reverse=True)
    
    result_pairs = [pair for pair, _ in momentum_pairs[:limit]]
    logger.info(f"Found {len(result_pairs)} momentum Solana pairs")
    return result_pairs


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 15,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    cache_ttl_seconds: int = 0,
) -> DexScreenerResult:
    """Make HTTP request with retry logic."""
    
    if not HAS_REQUESTS:
        return DexScreenerResult(success=False, error="requests_not_installed", retryable=False)
    
    # Check cache first
    cache_path = None
    if cache_ttl_seconds > 0:
        cache_path = _cache_path(url, params)
        cached = _read_cache(cache_path, cache_ttl_seconds)
        if cached is not None:
            return DexScreenerResult(success=True, data=cached, cached=True)
    
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
                logger.warning(f"DexScreener rate limited, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            
            # Handle server errors with retry
            if resp.status_code in (500, 502, 503, 504):
                logger.warning(f"DexScreener server error {resp.status_code}, retrying...")
                time.sleep(_backoff_delay(backoff_seconds, attempt))
                continue
            
            # Handle client errors (no retry)
            if resp.status_code >= 400:
                error_type = f"http_{resp.status_code}"
                logger.error(f"DexScreener error: {error_type}")
                return DexScreenerResult(success=False, error=error_type, retryable=False)
            
            # Success
            payload = resp.json()
            
            # Cache successful response
            if cache_path:
                _write_cache(cache_path, payload)
            
            return DexScreenerResult(success=True, data=payload)
            
        except requests.Timeout:
            last_error = "timeout"
            last_retryable = True
            logger.warning(f"DexScreener timeout (attempt {attempt + 1}/{retries})")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.ConnectionError as e:
            last_error = "connection_error"
            last_retryable = True
            logger.warning(f"DexScreener connection error: {e}")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except requests.RequestException as exc:
            last_error = str(exc)
            last_retryable = True
            logger.warning(f"DexScreener request error: {exc}")
            time.sleep(_backoff_delay(backoff_seconds, attempt))
            
        except json.JSONDecodeError:
            last_error = "invalid_json"
            last_retryable = False
            logger.error("DexScreener returned invalid JSON")
            break
    
    logger.error(f"DexScreener request failed after {retries} attempts: {last_error}")
    return DexScreenerResult(success=False, error=last_error, retryable=last_retryable)


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
    logger.info(f"Cleared {count} DexScreener cache files")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("API Status:", get_api_status())
    print("\nFetching trending Solana tokens...")
    
    trending = get_solana_trending(limit=10)
    for pair in trending[:5]:
        print(f"  {pair.base_token_symbol}: ${pair.price_usd:.8f} "
              f"(1h: {pair.price_change_1h:+.1f}%, Vol: ${pair.volume_24h/1000:.0f}K)")
    
    print("\nFetching momentum tokens...")
    momentum = get_momentum_tokens(limit=5)
    for pair in momentum:
        print(f"  {pair.base_token_symbol}: 5m={pair.price_change_5m:+.1f}%, "
              f"1h={pair.price_change_1h:+.1f}%, 24h={pair.price_change_24h:+.1f}%")
