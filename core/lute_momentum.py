"""
Lute.gg Momentum Tracker
========================

Tracks momentum signals from lute.gg trading terminal for token calls,
trending tokens, and smart trader activity.

Lute.gg provides:
- Token "calls" from traders
- Trending token rankings  
- Social trading features (friends trading together)
- Revenue share on trades

Since Lute doesn't have a public API, this module:
1. Provides scraping utilities for public data
2. Tracks known momentum signals
3. Integrates with Grok sentiment for call validation

Usage:
    from core.lute_momentum import get_trending_calls, validate_call_with_sentiment
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
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
CACHE_DIR = ROOT / "data" / "trader" / "lute_cache"
CALLS_CACHE = CACHE_DIR / "calls.json"

# Lute.gg URLs
LUTE_BASE = "https://lute.gg"
LUTE_TRADE = f"{LUTE_BASE}/trade"

# Cache settings
CACHE_TTL_SECONDS = 300  # 5 minutes
RATE_LIMIT_DELAY = 2.0  # Seconds between requests


@dataclass
class LuteCall:
    """A token call/recommendation from Lute.gg."""
    token_address: str
    token_symbol: str
    token_name: str
    caller_username: str
    caller_rank: str  # Bronze, Silver, Sapphire, Ruby, Diamond, Emerald, Master
    call_time: float
    chain: str = "solana"
    conviction: str = "medium"  # low, medium, high
    notes: str = ""
    validated: bool = False  # Whether sentiment validated
    sentiment_score: float = 0.0


@dataclass 
class LuteTrending:
    """Trending token from Lute.gg."""
    token_address: str
    token_symbol: str
    rank: int
    volume_rank: int = 0
    trader_count: int = 0
    momentum_score: float = 0.0


@dataclass
class LuteMomentumResult:
    """Result wrapper for Lute momentum operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    cached: bool = False
    source: str = "lute.gg"


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cache() -> Dict[str, Any]:
    """Load cached data."""
    if not CALLS_CACHE.exists():
        return {"calls": [], "trending": [], "updated": 0}
    try:
        return json.loads(CALLS_CACHE.read_text())
    except (json.JSONDecodeError, IOError):
        return {"calls": [], "trending": [], "updated": 0}


def _save_cache(data: Dict[str, Any]):
    """Save cache data."""
    _ensure_cache_dir()
    data["updated"] = time.time()
    CALLS_CACHE.write_text(json.dumps(data, indent=2))


def _is_cache_valid(cache: Dict[str, Any]) -> bool:
    """Check if cache is still valid."""
    updated = cache.get("updated", 0)
    return (time.time() - updated) < CACHE_TTL_SECONDS


def fetch_lute_page(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch a page from Lute.gg with rate limiting."""
    if not HAS_REQUESTS:
        logger.error("requests library not available")
        return None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"Lute.gg returned {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def parse_token_from_lute_url(url: str) -> Optional[Dict[str, str]]:
    """Parse token address and chain from Lute URL."""
    # Pattern: /trade/solana/TOKEN_ADDRESS or /trade?token=ADDRESS
    patterns = [
        r"/trade/(\w+)/([A-Za-z0-9]{32,44})",
        r"/trade\?.*token=([A-Za-z0-9]{32,44})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return {"chain": groups[0], "address": groups[1]}
            elif len(groups) == 1:
                return {"chain": "solana", "address": groups[0]}
    return None


def extract_calls_from_x(posts: List[Dict[str, Any]]) -> List[LuteCall]:
    """
    Extract Lute calls from X/Twitter posts.
    
    Looks for patterns like:
    - lute.gg/trade/solana/ADDRESS
    - "calling" or "call" with token mentions
    - $TICKER with lute.gg links
    """
    calls = []
    
    for post in posts:
        text = post.get("text", "")
        author = post.get("author", "unknown")
        timestamp = post.get("timestamp", time.time())
        
        # Look for lute.gg trade links
        lute_links = re.findall(r"lute\.gg/trade[^\s\"'<>]*", text, re.IGNORECASE)
        
        for link in lute_links:
            token_info = parse_token_from_lute_url(link)
            if token_info:
                # Extract token symbol if mentioned
                ticker_match = re.search(r"\$([A-Z]{2,10})", text)
                symbol = ticker_match.group(1) if ticker_match else ""
                
                # Detect conviction level from text
                conviction = "medium"
                if any(w in text.lower() for w in ["strong", "ape", "100x", "gem", "easy"]):
                    conviction = "high"
                elif any(w in text.lower() for w in ["risky", "small", "careful", "degen"]):
                    conviction = "low"
                
                calls.append(LuteCall(
                    token_address=token_info["address"],
                    token_symbol=symbol,
                    token_name="",
                    caller_username=author,
                    caller_rank="unknown",
                    call_time=timestamp,
                    chain=token_info["chain"],
                    conviction=conviction,
                    notes=text[:200],
                ))
    
    return calls


def add_call(call: LuteCall) -> bool:
    """Add a call to the cache."""
    try:
        cache = _load_cache()
        calls = cache.get("calls", [])
        
        # Check for duplicate
        for existing in calls:
            if (existing.get("token_address") == call.token_address and 
                existing.get("caller_username") == call.caller_username):
                return False  # Already exists
        
        calls.append(asdict(call))
        
        # Keep only last 100 calls
        if len(calls) > 100:
            calls = calls[-100:]
        
        cache["calls"] = calls
        _save_cache(cache)
        return True
    except Exception as e:
        logger.error(f"Failed to add call: {e}")
        return False


def get_recent_calls(
    *,
    max_age_hours: float = 24,
    chain: str = "solana",
    min_conviction: str = "low",
) -> LuteMomentumResult:
    """
    Get recent token calls.
    
    Args:
        max_age_hours: Maximum age of calls to return
        chain: Filter by chain
        min_conviction: Minimum conviction level (low, medium, high)
    
    Returns:
        LuteMomentumResult with list of LuteCall
    """
    try:
        cache = _load_cache()
        calls_data = cache.get("calls", [])
        
        cutoff = time.time() - (max_age_hours * 3600)
        conviction_levels = {"low": 0, "medium": 1, "high": 2}
        min_level = conviction_levels.get(min_conviction, 0)
        
        filtered = []
        for call_dict in calls_data:
            if call_dict.get("call_time", 0) < cutoff:
                continue
            if call_dict.get("chain") != chain:
                continue
            call_level = conviction_levels.get(call_dict.get("conviction", "low"), 0)
            if call_level < min_level:
                continue
            filtered.append(LuteCall(**call_dict))
        
        return LuteMomentumResult(
            success=True,
            data=filtered,
            cached=True,
        )
    except Exception as e:
        logger.error(f"Failed to get recent calls: {e}")
        return LuteMomentumResult(success=False, error=str(e))


def validate_call_with_sentiment(
    call: LuteCall,
    sentiment_func: Optional[callable] = None,
) -> LuteCall:
    """
    Validate a call using Grok sentiment analysis.
    
    Args:
        call: The call to validate
        sentiment_func: Optional custom sentiment function
    
    Returns:
        Updated LuteCall with validation status
    """
    if sentiment_func is None:
        try:
            from core.x_sentiment import analyze_sentiment
            sentiment_func = analyze_sentiment
        except ImportError:
            call.validated = False
            return call
    
    try:
        # Analyze sentiment of the call notes
        result = sentiment_func(
            call.notes or f"${call.token_symbol} on lute.gg",
            context=f"Token call from {call.caller_username}",
            focus="trading"
        )
        
        if result:
            call.validated = True
            call.sentiment_score = result.confidence
            
            # Upgrade/downgrade conviction based on sentiment
            if result.sentiment == "positive" and result.confidence > 0.7:
                if call.conviction == "medium":
                    call.conviction = "high"
            elif result.sentiment == "negative":
                call.conviction = "low"
        
        return call
    except Exception as e:
        logger.warning(f"Sentiment validation failed: {e}")
        call.validated = False
        return call


def get_momentum_signals(
    *,
    chain: str = "solana",
    include_unvalidated: bool = True,
) -> LuteMomentumResult:
    """
    Get aggregated momentum signals from Lute calls.
    
    Returns tokens with multiple recent calls or high-conviction calls.
    """
    result = get_recent_calls(chain=chain, max_age_hours=12)
    if not result.success:
        return result
    
    calls: List[LuteCall] = result.data or []
    if not include_unvalidated:
        calls = [c for c in calls if c.validated]
    
    # Aggregate by token
    token_signals: Dict[str, Dict[str, Any]] = {}
    
    for call in calls:
        addr = call.token_address
        if addr not in token_signals:
            token_signals[addr] = {
                "token_address": addr,
                "token_symbol": call.token_symbol,
                "call_count": 0,
                "high_conviction_count": 0,
                "callers": [],
                "avg_sentiment": 0.0,
                "latest_call": 0,
                "momentum_score": 0.0,
            }
        
        sig = token_signals[addr]
        sig["call_count"] += 1
        if call.conviction == "high":
            sig["high_conviction_count"] += 1
        sig["callers"].append(call.caller_username)
        if call.validated:
            sig["avg_sentiment"] = (sig["avg_sentiment"] + call.sentiment_score) / 2
        sig["latest_call"] = max(sig["latest_call"], call.call_time)
    
    # Calculate momentum scores
    for addr, sig in token_signals.items():
        recency_factor = max(0, 1 - (time.time() - sig["latest_call"]) / (12 * 3600))
        sig["momentum_score"] = (
            sig["call_count"] * 0.3 +
            sig["high_conviction_count"] * 0.4 +
            sig["avg_sentiment"] * 0.2 +
            recency_factor * 0.1
        )
        sig["callers"] = list(set(sig["callers"]))[:5]  # Dedupe and limit
    
    # Sort by momentum score
    sorted_signals = sorted(
        token_signals.values(),
        key=lambda x: x["momentum_score"],
        reverse=True
    )
    
    return LuteMomentumResult(
        success=True,
        data=sorted_signals[:20],  # Top 20
    )


def clear_cache() -> int:
    """Clear the Lute cache."""
    try:
        if CALLS_CACHE.exists():
            CALLS_CACHE.unlink()
        return 1
    except Exception:
        return 0


def get_api_status() -> Dict[str, Any]:
    """Get Lute integration status."""
    cache = _load_cache()
    return {
        "available": True,
        "cache_valid": _is_cache_valid(cache),
        "cached_calls": len(cache.get("calls", [])),
        "last_update": cache.get("updated", 0),
        "source": "lute.gg",
        "note": "Lute.gg has no public API - uses cached calls from X/Twitter",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Lute.gg Momentum Tracker ===")
    print(json.dumps(get_api_status(), indent=2))
