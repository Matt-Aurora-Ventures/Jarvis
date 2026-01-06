"""
GMGN.ai Token Metrics Client
============================

Integrates with GMGN.ai for:
- Smart money wallet tracking
- Token security checks (honeypot, rug pull detection)
- Insider/sniper activity monitoring
- New token FOMO alerts
- Pump.fun token tracking

GMGN doesn't have a public API but offers IP whitelist access for trading users.
This module provides scraping utilities and integrates with their data.

Usage:
    from core.gmgn_metrics import get_token_security, get_smart_money_activity
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
CACHE_DIR = ROOT / "data" / "trader" / "gmgn_cache"
TOKEN_CACHE = CACHE_DIR / "tokens.json"
SMART_MONEY_CACHE = CACHE_DIR / "smart_money.json"

# GMGN URLs (for reference - requires IP whitelist)
GMGN_BASE = "https://gmgn.ai"
GMGN_API_BASE = "https://gmgn.ai/defi/quotation/v1"  # Inferred API path

# Rate limiting - GMGN limits to 2 req/sec
RATE_LIMIT_REQUESTS_PER_SECOND = 2
_last_request_time: float = 0

# Cache settings
CACHE_TTL_SECONDS = 180  # 3 minutes for token data


@dataclass
class TokenSecurity:
    """Token security assessment from GMGN."""
    token_address: str
    chain: str
    is_honeypot: bool = False
    is_mintable: bool = False
    is_renounced: bool = False
    lp_burned: bool = False
    lp_locked: bool = False
    lp_lock_percentage: float = 0.0
    holder_count: int = 0
    top_10_holder_pct: float = 0.0
    creator_balance_pct: float = 0.0
    security_score: float = 0.0  # 0-100, higher is safer
    risk_level: str = "unknown"  # low, medium, high, critical
    warnings: List[str] = field(default_factory=list)


@dataclass
class SmartMoneyWallet:
    """Smart money wallet profile."""
    address: str
    label: str  # insider, sniper, whale, kol, etc.
    win_rate: float = 0.0
    total_trades: int = 0
    total_pnl_usd: float = 0.0
    avg_hold_time_hours: float = 0.0
    last_active: float = 0.0
    tokens_traded: List[str] = field(default_factory=list)


@dataclass
class SmartMoneyActivity:
    """Smart money activity on a token."""
    token_address: str
    insider_buys: int = 0
    insider_sells: int = 0
    sniper_count: int = 0
    first_70_buyers_pnl: float = 0.0
    whale_accumulation: bool = False
    smart_money_signal: str = "neutral"  # bullish, bearish, neutral
    notable_wallets: List[SmartMoneyWallet] = field(default_factory=list)


@dataclass
class GMGNResult:
    """Result wrapper for GMGN operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    cached: bool = False
    source: str = "gmgn.ai"


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _rate_limit():
    """Apply rate limiting."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    min_delay = 1.0 / RATE_LIMIT_REQUESTS_PER_SECOND
    if elapsed < min_delay:
        time.sleep(min_delay - elapsed)
    _last_request_time = time.time()


def _load_token_cache() -> Dict[str, Any]:
    """Load token cache."""
    if not TOKEN_CACHE.exists():
        return {}
    try:
        return json.loads(TOKEN_CACHE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def _save_token_cache(data: Dict[str, Any]):
    """Save token cache."""
    _ensure_cache_dir()
    TOKEN_CACHE.write_text(json.dumps(data, indent=2))


def _get_cached_token(address: str) -> Optional[Dict[str, Any]]:
    """Get cached token data if valid."""
    cache = _load_token_cache()
    entry = cache.get(address)
    if not entry:
        return None
    if time.time() - entry.get("cached_at", 0) > CACHE_TTL_SECONDS:
        return None
    return entry.get("data")


def _set_cached_token(address: str, data: Dict[str, Any]):
    """Cache token data."""
    cache = _load_token_cache()
    cache[address] = {"data": data, "cached_at": time.time()}
    # Limit cache size
    if len(cache) > 500:
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k].get("cached_at", 0))
        for old_key in sorted_keys[:100]:
            del cache[old_key]
    _save_token_cache(cache)


def _make_request(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> Optional[Dict[str, Any]]:
    """Make a request to GMGN API (requires IP whitelist)."""
    if not HAS_REQUESTS:
        logger.error("requests library not available")
        return None
    
    _rate_limit()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": GMGN_BASE,
        "Referer": f"{GMGN_BASE}/",
    }
    
    url = f"{GMGN_API_BASE}{endpoint}"
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403:
            logger.warning("GMGN API access denied - IP whitelist required")
            return None
        else:
            logger.warning(f"GMGN API returned {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"GMGN request failed: {e}")
        return None


def analyze_token_security(
    token_address: str,
    chain: str = "sol",
) -> GMGNResult:
    """
    Analyze token security using GMGN data.
    
    Checks for:
    - Honeypot detection
    - LP burned/locked status
    - Mintable token
    - Ownership renounced
    - Top holder concentration
    
    Args:
        token_address: Token contract address
        chain: Chain identifier (sol, eth, base, bsc)
    
    Returns:
        GMGNResult with TokenSecurity
    """
    # Check cache first
    cached = _get_cached_token(token_address)
    if cached:
        return GMGNResult(
            success=True,
            data=TokenSecurity(**cached),
            cached=True,
        )
    
    # Try to fetch from GMGN
    # Note: This requires IP whitelist access
    data = _make_request(f"/token/{chain}/{token_address}/security")
    
    if data:
        security = _parse_security_response(token_address, chain, data)
        _set_cached_token(token_address, asdict(security))
        return GMGNResult(success=True, data=security)
    
    # Fallback: Use heuristic analysis from other sources
    security = _heuristic_security_check(token_address, chain)
    return GMGNResult(
        success=True,
        data=security,
        error="Using heuristic analysis - GMGN API requires IP whitelist",
    )


def _parse_security_response(
    address: str,
    chain: str,
    data: Dict[str, Any],
) -> TokenSecurity:
    """Parse GMGN security response into TokenSecurity."""
    d = data.get("data", data)
    
    warnings = []
    
    is_honeypot = d.get("is_honeypot", False)
    is_mintable = d.get("is_mintable", False)
    is_renounced = d.get("is_renounced", False)
    lp_burned = d.get("lp_burned", False)
    lp_locked = d.get("lp_locked", False)
    
    if is_honeypot:
        warnings.append("HONEYPOT DETECTED")
    if is_mintable and not is_renounced:
        warnings.append("Token is mintable")
    if not lp_burned and not lp_locked:
        warnings.append("LP not burned or locked")
    
    top_10_pct = float(d.get("top_10_holder_pct", 0))
    if top_10_pct > 50:
        warnings.append(f"Top 10 holders own {top_10_pct:.1f}%")
    
    # Calculate security score
    score = 100
    if is_honeypot:
        score -= 100
    if is_mintable and not is_renounced:
        score -= 30
    if not lp_burned and not lp_locked:
        score -= 25
    if top_10_pct > 80:
        score -= 20
    elif top_10_pct > 50:
        score -= 10
    
    score = max(0, score)
    
    # Determine risk level
    if score >= 70:
        risk_level = "low"
    elif score >= 40:
        risk_level = "medium"
    elif score > 0:
        risk_level = "high"
    else:
        risk_level = "critical"
    
    return TokenSecurity(
        token_address=address,
        chain=chain,
        is_honeypot=is_honeypot,
        is_mintable=is_mintable,
        is_renounced=is_renounced,
        lp_burned=lp_burned,
        lp_locked=lp_locked,
        lp_lock_percentage=float(d.get("lp_lock_pct", 0)),
        holder_count=int(d.get("holder_count", 0)),
        top_10_holder_pct=top_10_pct,
        creator_balance_pct=float(d.get("creator_balance_pct", 0)),
        security_score=score,
        risk_level=risk_level,
        warnings=warnings,
    )


def _heuristic_security_check(address: str, chain: str) -> TokenSecurity:
    """
    Perform heuristic security check when GMGN API not available.
    Uses RugCheck and other free sources.
    """
    # Try RugCheck for Solana
    if chain in ("sol", "solana"):
        try:
            from core import rugcheck
            result = rugcheck.check_token(address)
            if result:
                risks = result.get("risks", [])
                is_honeypot = any("honeypot" in r.get("name", "").lower() for r in risks)
                warnings = [r.get("description", r.get("name", "")) for r in risks[:5]]
                
                risk_level = result.get("riskLevel", "unknown").lower()
                score_map = {"good": 80, "warn": 50, "danger": 20, "unknown": 40}
                score = score_map.get(risk_level, 40)
                
                return TokenSecurity(
                    token_address=address,
                    chain=chain,
                    is_honeypot=is_honeypot,
                    security_score=score,
                    risk_level=risk_level if risk_level != "warn" else "medium",
                    warnings=warnings,
                )
        except Exception as e:
            logger.debug(f"RugCheck fallback failed: {e}")
    
    # Return unknown if no data available
    return TokenSecurity(
        token_address=address,
        chain=chain,
        risk_level="unknown",
        warnings=["Security data unavailable - manual review recommended"],
    )


def get_smart_money_activity(
    token_address: str,
    chain: str = "sol",
) -> GMGNResult:
    """
    Get smart money activity for a token.
    
    Tracks:
    - Insider trader activity
    - Sniper wallets
    - First 70 buyers analysis
    - Whale accumulation patterns
    
    Args:
        token_address: Token address
        chain: Chain identifier
    
    Returns:
        GMGNResult with SmartMoneyActivity
    """
    # Try GMGN API
    data = _make_request(f"/token/{chain}/{token_address}/smart_money")
    
    if data:
        activity = _parse_smart_money_response(token_address, data)
        return GMGNResult(success=True, data=activity)
    
    # Return empty activity if no data
    return GMGNResult(
        success=True,
        data=SmartMoneyActivity(token_address=token_address),
        error="Smart money data requires GMGN IP whitelist",
    )


def _parse_smart_money_response(
    address: str,
    data: Dict[str, Any],
) -> SmartMoneyActivity:
    """Parse GMGN smart money response."""
    d = data.get("data", data)
    
    insider_buys = int(d.get("insider_buys", 0))
    insider_sells = int(d.get("insider_sells", 0))
    sniper_count = int(d.get("sniper_count", 0))
    
    # Determine signal
    if insider_buys > insider_sells * 2:
        signal = "bullish"
    elif insider_sells > insider_buys * 2:
        signal = "bearish"
    else:
        signal = "neutral"
    
    notable_wallets = []
    for w in d.get("notable_wallets", [])[:10]:
        notable_wallets.append(SmartMoneyWallet(
            address=w.get("address", ""),
            label=w.get("label", "unknown"),
            win_rate=float(w.get("win_rate", 0)),
            total_trades=int(w.get("total_trades", 0)),
            total_pnl_usd=float(w.get("pnl_usd", 0)),
        ))
    
    return SmartMoneyActivity(
        token_address=address,
        insider_buys=insider_buys,
        insider_sells=insider_sells,
        sniper_count=sniper_count,
        first_70_buyers_pnl=float(d.get("first_70_pnl", 0)),
        whale_accumulation=d.get("whale_accumulation", False),
        smart_money_signal=signal,
        notable_wallets=notable_wallets,
    )


def get_trending_tokens(
    chain: str = "sol",
    category: str = "new",  # new, almost_bonded, migrated
    limit: int = 20,
) -> GMGNResult:
    """
    Get trending tokens from GMGN.
    
    Categories:
    - new: Newly created tokens
    - almost_bonded: Tokens close to bonding curve completion
    - migrated: Tokens that migrated from pump.fun
    
    Args:
        chain: Chain identifier
        category: Token category
        limit: Maximum results
    
    Returns:
        GMGNResult with list of token data
    """
    data = _make_request(f"/rank/{chain}/{category}", params={"limit": limit})
    
    if data:
        tokens = data.get("data", {}).get("tokens", [])
        return GMGNResult(success=True, data=tokens)
    
    return GMGNResult(
        success=False,
        error="Trending tokens require GMGN IP whitelist access",
    )


def track_wallet(wallet_address: str, chain: str = "sol") -> GMGNResult:
    """
    Track a specific wallet for smart money activity.
    
    Args:
        wallet_address: Wallet to track
        chain: Chain identifier
    
    Returns:
        GMGNResult with wallet profile
    """
    data = _make_request(f"/wallet/{chain}/{wallet_address}")
    
    if data:
        d = data.get("data", data)
        wallet = SmartMoneyWallet(
            address=wallet_address,
            label=d.get("label", "unknown"),
            win_rate=float(d.get("win_rate", 0)),
            total_trades=int(d.get("total_trades", 0)),
            total_pnl_usd=float(d.get("pnl_usd", 0)),
            avg_hold_time_hours=float(d.get("avg_hold_hours", 0)),
            last_active=float(d.get("last_active", 0)),
            tokens_traded=d.get("recent_tokens", [])[:20],
        )
        return GMGNResult(success=True, data=wallet)
    
    return GMGNResult(
        success=False,
        error="Wallet tracking requires GMGN IP whitelist",
    )


def clear_cache() -> int:
    """Clear GMGN cache."""
    count = 0
    for cache_file in [TOKEN_CACHE, SMART_MONEY_CACHE]:
        try:
            if cache_file.exists():
                cache_file.unlink()
                count += 1
        except Exception:
            pass
    return count


def get_api_status() -> Dict[str, Any]:
    """Get GMGN integration status."""
    cache = _load_token_cache()
    return {
        "available": HAS_REQUESTS,
        "cached_tokens": len(cache),
        "rate_limit": f"{RATE_LIMIT_REQUESTS_PER_SECOND} req/sec",
        "source": "gmgn.ai",
        "note": "Full API access requires IP whitelist application",
        "whitelist_url": "https://forms.gle/7kp58kunJ6Ab3FNr6",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== GMGN.ai Token Metrics ===")
    print(json.dumps(get_api_status(), indent=2))
    
    # Test security check
    print("\n=== Testing Security Check ===")
    test_token = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"  # RAY
    result = analyze_token_security(test_token)
    if result.success:
        print(f"Security score: {result.data.security_score}")
        print(f"Risk level: {result.data.risk_level}")
        print(f"Warnings: {result.data.warnings}")
