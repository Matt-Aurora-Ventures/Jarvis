"""
DexTools API Client
===================

Integrates with DexTools for:
- Real-time token data and charts
- Hot pairs tracking
- Token audit/security scores
- Trading history and analytics

DexTools has a paid API but offers limited free access.
This module provides both API integration and scraping fallbacks.

Usage:
    from core.dextools import get_token_info, get_hot_pairs
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
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
CACHE_DIR = ROOT / "data" / "trader" / "dextools_cache"
CONFIG_PATH = ROOT / "secrets" / "keys.json"

# DexTools API (requires API key for full access)
DEXTOOLS_API_BASE = "https://public-api.dextools.io/trial/v2"
DEXTOOLS_FREE_API = "https://api.dextools.io/v1"  # Limited free endpoints

# Chain mappings
CHAIN_MAP = {
    "solana": "solana",
    "sol": "solana",
    "ethereum": "ether",
    "eth": "ether",
    "base": "base",
    "bsc": "bsc",
    "bnb": "bsc",
    "arbitrum": "arbitrum",
    "polygon": "polygon",
}

# Rate limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 30  # Conservative for free tier
_request_timestamps: List[float] = []
CACHE_TTL_SECONDS = 120  # 2 minutes


@dataclass
class DexToolsToken:
    """Token data from DexTools."""
    address: str
    chain: str
    symbol: str
    name: str
    price_usd: float = 0.0
    price_change_24h: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    holders: int = 0
    total_supply: float = 0.0
    circulating_supply: float = 0.0
    market_cap: float = 0.0
    fdv: float = 0.0
    audit_score: float = 0.0  # DexTools audit score
    dext_score: float = 0.0  # DEXT score
    creation_time: Optional[float] = None
    socials: Dict[str, str] = field(default_factory=dict)


@dataclass
class DexToolsPair:
    """Trading pair from DexTools."""
    pair_address: str
    chain: str
    dex: str
    base_token: str
    base_symbol: str
    quote_token: str
    quote_symbol: str
    price_usd: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    txns_24h: int = 0
    buys_24h: int = 0
    sells_24h: int = 0
    hot_level: int = 0  # DexTools hot ranking
    creation_block: int = 0


@dataclass
class DexToolsResult:
    """Result wrapper for DexTools operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    cached: bool = False
    source: str = "dextools"


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_api_key() -> Optional[str]:
    """Load DexTools API key from config."""
    # Try environment variable first
    key = os.environ.get("DEXTOOLS_API_KEY")
    if key:
        return key
    
    # Try secrets file
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
            return config.get("dextools_api_key")
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _get_chain_id(chain: str) -> str:
    """Normalize chain identifier."""
    return CHAIN_MAP.get(chain.lower(), chain.lower())


def _check_rate_limit() -> Tuple[bool, float]:
    """Check if we should rate limit."""
    now = time.time()
    cutoff = now - 60
    _request_timestamps[:] = [t for t in _request_timestamps if t > cutoff]
    
    if len(_request_timestamps) >= RATE_LIMIT_REQUESTS_PER_MINUTE:
        oldest = _request_timestamps[0]
        wait_time = 60 - (now - oldest) + 0.1
        return True, max(0, wait_time)
    return False, 0


def _record_request():
    """Record a request for rate limiting."""
    _request_timestamps.append(time.time())


def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    """Exponential backoff with jitter."""
    delay = min(max_delay, base * (2 ** attempt))
    jitter = delay * 0.1 * random.random()
    return delay + jitter


def _load_cache(key: str) -> Optional[Dict[str, Any]]:
    """Load cached data."""
    cache_file = CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        if time.time() - data.get("cached_at", 0) > CACHE_TTL_SECONDS:
            return None
        return data.get("payload")
    except (json.JSONDecodeError, IOError):
        return None


def _save_cache(key: str, payload: Any):
    """Save data to cache."""
    _ensure_cache_dir()
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps({
        "payload": payload,
        "cached_at": time.time(),
    }, indent=2))


def _make_request(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """Make a request to DexTools API."""
    if not HAS_REQUESTS:
        logger.error("requests library not available")
        return None
    
    api_key = _load_api_key()
    
    # Check rate limit
    should_limit, wait_time = _check_rate_limit()
    if should_limit:
        logger.debug(f"Rate limiting, waiting {wait_time:.1f}s")
        time.sleep(wait_time)
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "LifeOS/1.0 DexTools Client",
    }
    
    if api_key:
        headers["X-API-KEY"] = api_key
        base_url = DEXTOOLS_API_BASE
    else:
        base_url = DEXTOOLS_FREE_API
    
    url = f"{base_url}{endpoint}"
    
    for attempt in range(retries):
        try:
            _record_request()
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = _backoff_delay(2.0, attempt)
                logger.warning(f"DexTools rate limited, waiting {wait:.1f}s")
                time.sleep(wait)
                continue
            elif resp.status_code == 401:
                logger.warning("DexTools API key invalid or missing")
                return None
            else:
                logger.warning(f"DexTools returned {resp.status_code}: {resp.text[:200]}")
                return None
                
        except Exception as e:
            logger.warning(f"DexTools request failed: {e}")
            if attempt < retries - 1:
                time.sleep(_backoff_delay(1.0, attempt))
    
    return None


def get_token_info(
    token_address: str,
    chain: str = "solana",
) -> DexToolsResult:
    """
    Get detailed token information from DexTools.
    
    Args:
        token_address: Token contract address
        chain: Blockchain (solana, ethereum, base, etc.)
    
    Returns:
        DexToolsResult with DexToolsToken
    """
    chain_id = _get_chain_id(chain)
    cache_key = f"token_{chain_id}_{token_address[:16]}"
    
    # Check cache
    cached = _load_cache(cache_key)
    if cached:
        return DexToolsResult(
            success=True,
            data=DexToolsToken(**cached),
            cached=True,
        )
    
    # Fetch from API
    data = _make_request(f"/token/{chain_id}/{token_address}")
    
    if data and data.get("data"):
        token_data = _parse_token_response(token_address, chain_id, data["data"])
        _save_cache(cache_key, token_data.__dict__)
        return DexToolsResult(success=True, data=token_data)
    
    # Fallback: Try DexScreener for basic data
    try:
        from core import dexscreener
        result = dexscreener.get_pairs_by_token(token_address)
        if result.success and result.data:
            pairs = result.data.get("pairs", [])
            if pairs:
                pair = pairs[0]
                base = pair.get("baseToken", {})
                token = DexToolsToken(
                    address=token_address,
                    chain=chain_id,
                    symbol=base.get("symbol", ""),
                    name=base.get("name", ""),
                    price_usd=float(pair.get("priceUsd", 0) or 0),
                    price_change_24h=float(pair.get("priceChange", {}).get("h24", 0) or 0),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                    liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                )
                return DexToolsResult(
                    success=True,
                    data=token,
                    error="Using DexScreener fallback",
                )
    except Exception as e:
        logger.debug(f"DexScreener fallback failed: {e}")
    
    return DexToolsResult(
        success=False,
        error="Failed to fetch token info",
    )


def _parse_token_response(
    address: str,
    chain: str,
    data: Dict[str, Any],
) -> DexToolsToken:
    """Parse DexTools token API response."""
    return DexToolsToken(
        address=address,
        chain=chain,
        symbol=data.get("symbol", ""),
        name=data.get("name", ""),
        price_usd=float(data.get("reprPair", {}).get("price", 0) or 0),
        volume_24h=float(data.get("metrics", {}).get("volume", 0) or 0),
        liquidity_usd=float(data.get("metrics", {}).get("liquidity", 0) or 0),
        holders=int(data.get("holders", 0)),
        total_supply=float(data.get("totalSupply", 0) or 0),
        circulating_supply=float(data.get("circulatingSupply", 0) or 0),
        market_cap=float(data.get("marketCap", 0) or 0),
        fdv=float(data.get("fdv", 0) or 0),
        audit_score=float(data.get("audit", {}).get("score", 0) or 0),
        dext_score=float(data.get("dextScore", {}).get("total", 0) or 0),
        creation_time=data.get("creationTime"),
        socials={
            k: v for k, v in data.get("links", {}).items()
            if v and isinstance(v, str)
        },
    )


def get_hot_pairs(
    chain: str = "solana",
    limit: int = 20,
) -> DexToolsResult:
    """
    Get hot/trending pairs from DexTools.
    
    Args:
        chain: Blockchain
        limit: Maximum results
    
    Returns:
        DexToolsResult with list of DexToolsPair
    """
    chain_id = _get_chain_id(chain)
    cache_key = f"hot_{chain_id}"
    
    # Check cache
    cached = _load_cache(cache_key)
    if cached:
        pairs = [DexToolsPair(**p) for p in cached]
        return DexToolsResult(success=True, data=pairs, cached=True)
    
    # Fetch from API
    data = _make_request(f"/ranking/{chain_id}/hot", params={"limit": limit})
    
    if data and data.get("data"):
        pairs = []
        for p in data["data"][:limit]:
            pairs.append(_parse_pair_response(chain_id, p))
        
        _save_cache(cache_key, [p.__dict__ for p in pairs])
        return DexToolsResult(success=True, data=pairs)
    
    # Fallback to DexScreener
    try:
        from core import dexscreener
        pairs_data = dexscreener.get_solana_trending(limit=limit)
        if pairs_data:
            pairs = [
                DexToolsPair(
                    pair_address=p.pair_address,
                    chain=chain_id,
                    dex=p.dex_id,
                    base_token=p.base_token_address,
                    base_symbol=p.base_token_symbol,
                    quote_token=p.quote_token_address,
                    quote_symbol=p.quote_token_symbol,
                    price_usd=p.price_usd,
                    price_change_24h=p.price_change_24h,
                    volume_24h=p.volume_24h,
                    liquidity_usd=p.liquidity_usd,
                )
                for p in pairs_data
            ]
            return DexToolsResult(
                success=True,
                data=pairs,
                error="Using DexScreener fallback",
            )
    except Exception as e:
        logger.debug(f"DexScreener fallback failed: {e}")
    
    return DexToolsResult(success=False, error="Failed to fetch hot pairs")


def _parse_pair_response(chain: str, data: Dict[str, Any]) -> DexToolsPair:
    """Parse DexTools pair response."""
    return DexToolsPair(
        pair_address=data.get("address", ""),
        chain=chain,
        dex=data.get("exchange", ""),
        base_token=data.get("mainToken", {}).get("address", ""),
        base_symbol=data.get("mainToken", {}).get("symbol", ""),
        quote_token=data.get("sideToken", {}).get("address", ""),
        quote_symbol=data.get("sideToken", {}).get("symbol", ""),
        price_usd=float(data.get("price", 0) or 0),
        price_change_1h=float(data.get("variation1h", 0) or 0),
        price_change_24h=float(data.get("variation24h", 0) or 0),
        volume_24h=float(data.get("volume24h", 0) or 0),
        liquidity_usd=float(data.get("liquidity", 0) or 0),
        txns_24h=int(data.get("txns24h", 0)),
        buys_24h=int(data.get("buys24h", 0)),
        sells_24h=int(data.get("sells24h", 0)),
        hot_level=int(data.get("hotLevel", 0)),
        creation_block=int(data.get("creationBlock", 0)),
    )


def get_token_audit(
    token_address: str,
    chain: str = "solana",
) -> DexToolsResult:
    """
    Get token audit/security score from DexTools.
    
    Args:
        token_address: Token address
        chain: Blockchain
    
    Returns:
        DexToolsResult with audit data
    """
    chain_id = _get_chain_id(chain)
    
    data = _make_request(f"/token/{chain_id}/{token_address}/audit")
    
    if data and data.get("data"):
        return DexToolsResult(success=True, data=data["data"])
    
    return DexToolsResult(success=False, error="Audit data unavailable")


def search_tokens(
    query: str,
    chain: str = "solana",
    limit: int = 10,
) -> DexToolsResult:
    """
    Search for tokens by name or symbol.
    
    Args:
        query: Search query
        chain: Blockchain
        limit: Maximum results
    
    Returns:
        DexToolsResult with list of tokens
    """
    chain_id = _get_chain_id(chain)
    
    data = _make_request(
        f"/token/{chain_id}/search",
        params={"query": query, "limit": limit}
    )
    
    if data and data.get("data"):
        tokens = [
            DexToolsToken(
                address=t.get("address", ""),
                chain=chain_id,
                symbol=t.get("symbol", ""),
                name=t.get("name", ""),
            )
            for t in data["data"][:limit]
        ]
        return DexToolsResult(success=True, data=tokens)
    
    return DexToolsResult(success=False, error="Search failed")


def clear_cache() -> int:
    """Clear DexTools cache."""
    count = 0
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
    return count


def get_api_status() -> Dict[str, Any]:
    """Get DexTools integration status."""
    api_key = _load_api_key()
    return {
        "available": HAS_REQUESTS,
        "has_api_key": bool(api_key),
        "rate_limit": f"{RATE_LIMIT_REQUESTS_PER_MINUTE} req/min",
        "recent_requests": len(_request_timestamps),
        "cache_ttl": CACHE_TTL_SECONDS,
        "source": "dextools.io",
        "note": "Full API requires paid subscription" if not api_key else "API key configured",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== DexTools API Client ===")
    print(json.dumps(get_api_status(), indent=2))
