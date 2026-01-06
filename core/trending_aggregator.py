"""
Multi-Source Trending Token Aggregator
======================================

Combines trending token data from multiple DEX data providers for robust
signal generation. Supports velocity tracking and composite ranking.

Sources:
- Birdeye: Direct trending endpoint (/defi/token_trending)
- GeckoTerminal: Top pools by volume (proxy for trending)
- DexScreener: Boosted/trending tokens

Usage:
    from core.trending_aggregator import fetch_trending_all_sources, TrendingToken

    tokens = fetch_trending_all_sources(limit=50)
    rising = [t for t in tokens if t.velocity > 0.1]
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

from core import birdeye, geckoterminal, dexscreener


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "trending_cache"
HISTORY_FILE = CACHE_DIR / "trending_history.json"

# Source weights for composite ranking
SOURCE_WEIGHTS = {
    "birdeye": 0.45,       # Primary source with dedicated trending
    "geckoterminal": 0.35, # Good volume data
    "dexscreener": 0.20,   # Supplementary
}


@dataclass
class TrendingToken:
    """Unified trending token representation across sources."""
    mint: str
    symbol: str
    name: str

    # Aggregate ranking
    composite_rank: float = 0.0    # Weighted average across sources (lower = better)
    velocity: float = 0.0          # Trend momentum (positive = rising in ranks)

    # Per-source data
    birdeye_rank: Optional[int] = None
    gecko_rank: Optional[int] = None
    dexscreener_rank: Optional[int] = None

    # Velocity signals (change in rank over time)
    velocity_15m: float = 0.0
    velocity_1h: float = 0.0
    velocity_4h: float = 0.0

    # Market data (best available)
    liquidity_usd: float = 0.0
    volume_24h_usd: float = 0.0
    price_usd: float = 0.0
    price_change_24h: float = 0.0

    # Source metadata
    sources: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrendingToken":
        return cls(**data)


def fetch_trending_all_sources(
    limit: int = 50,
    cache_ttl_seconds: int = 60,
) -> List[TrendingToken]:
    """
    Fetch trending tokens from all sources and merge into unified list.

    Args:
        limit: Maximum tokens to return
        cache_ttl_seconds: Cache TTL for API calls

    Returns:
        List of TrendingToken sorted by composite_rank (best first)
    """
    all_tokens: Dict[str, TrendingToken] = {}

    # Fetch from Birdeye
    birdeye_tokens = _fetch_birdeye_trending(limit=limit * 2, cache_ttl=cache_ttl_seconds)
    for rank, token in enumerate(birdeye_tokens, 1):
        mint = token["mint"]
        if mint not in all_tokens:
            all_tokens[mint] = TrendingToken(
                mint=mint,
                symbol=token.get("symbol", ""),
                name=token.get("name", ""),
                liquidity_usd=token.get("liquidity", 0.0),
                volume_24h_usd=token.get("volume_24h", 0.0),
                price_usd=token.get("price", 0.0),
                price_change_24h=token.get("price_change_24h", 0.0),
            )
        all_tokens[mint].birdeye_rank = rank
        all_tokens[mint].sources.append("birdeye")

    # Fetch from GeckoTerminal (top pools as trending proxy)
    gecko_tokens = _fetch_gecko_trending(limit=limit * 2, cache_ttl=cache_ttl_seconds)
    for rank, token in enumerate(gecko_tokens, 1):
        mint = token["mint"]
        if mint not in all_tokens:
            all_tokens[mint] = TrendingToken(
                mint=mint,
                symbol=token.get("symbol", ""),
                name=token.get("name", ""),
                liquidity_usd=token.get("liquidity", 0.0),
                volume_24h_usd=token.get("volume_24h", 0.0),
                price_usd=token.get("price", 0.0),
            )
        all_tokens[mint].gecko_rank = rank
        if "geckoterminal" not in all_tokens[mint].sources:
            all_tokens[mint].sources.append("geckoterminal")
        # Update market data if better
        if token.get("liquidity", 0) > all_tokens[mint].liquidity_usd:
            all_tokens[mint].liquidity_usd = token.get("liquidity", 0)
        if token.get("volume_24h", 0) > all_tokens[mint].volume_24h_usd:
            all_tokens[mint].volume_24h_usd = token.get("volume_24h", 0)

    # Fetch from DexScreener (boosted tokens)
    dexscreener_tokens = _fetch_dexscreener_trending(limit=limit * 2, cache_ttl=cache_ttl_seconds)
    for rank, token in enumerate(dexscreener_tokens, 1):
        mint = token["mint"]
        if mint not in all_tokens:
            all_tokens[mint] = TrendingToken(
                mint=mint,
                symbol=token.get("symbol", ""),
                name=token.get("name", ""),
                liquidity_usd=token.get("liquidity", 0.0),
                volume_24h_usd=token.get("volume_24h", 0.0),
                price_usd=token.get("price", 0.0),
            )
        all_tokens[mint].dexscreener_rank = rank
        if "dexscreener" not in all_tokens[mint].sources:
            all_tokens[mint].sources.append("dexscreener")

    # Compute composite ranks
    tokens = list(all_tokens.values())
    _compute_composite_ranks(tokens)

    # Compute velocity signals
    _compute_velocity_signals(tokens)

    # Sort by composite rank (lower = better)
    tokens.sort(key=lambda t: t.composite_rank)

    # Update history for velocity tracking
    _update_history(tokens[:limit])

    return tokens[:limit]


def _fetch_birdeye_trending(limit: int, cache_ttl: int) -> List[Dict[str, Any]]:
    """Fetch trending from Birdeye API."""
    try:
        # BirdEye API max limit is 20 for trending
        safe_limit = min(limit, 20)
        data = birdeye.fetch_trending_tokens(limit=safe_limit, cache_ttl_seconds=cache_ttl)
        if not data:
            return []

        tokens = data.get("data", {}).get("tokens", [])
        if not tokens:
            # Try alternative response format
            tokens = data.get("data", [])

        result = []
        for t in tokens:
            result.append({
                "mint": t.get("address", ""),
                "symbol": t.get("symbol", ""),
                "name": t.get("name", ""),
                "liquidity": float(t.get("liquidity", 0) or 0),
                "volume_24h": float(t.get("v24hUSD", 0) or t.get("volume24h", 0) or 0),
                "price": float(t.get("price", 0) or 0),
                "price_change_24h": float(t.get("priceChange24h", 0) or 0),
            })
        return result
    except Exception as e:
        logger.warning(f"[trending_aggregator] Birdeye fetch failed: {e}")
        return []


def _fetch_gecko_trending(limit: int, cache_ttl: int) -> List[Dict[str, Any]]:
    """Fetch top pools from GeckoTerminal as trending proxy."""
    try:
        data = geckoterminal.fetch_pools(
            "solana",
            sort="h24_volume_usd_desc",
            include_tokens=True,
            cache_ttl_seconds=cache_ttl,
        )
        if not data:
            return []

        pools = data.get("data", [])
        tokens_map = geckoterminal.extract_included_tokens(data)

        result = []
        seen_mints: Set[str] = set()

        for pool in pools:
            attrs = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            # Get base token
            base_token = relationships.get("base_token", {}).get("data", {})
            token_id = base_token.get("id", "")

            # Extract mint from token ID (format: solana_ADDRESS)
            mint = ""
            if "_" in token_id:
                mint = token_id.split("_", 1)[1]

            if not mint or mint in seen_mints:
                continue
            seen_mints.add(mint)

            # Get token details
            token_attrs = tokens_map.get(token_id, {})

            result.append({
                "mint": mint,
                "symbol": token_attrs.get("symbol", attrs.get("name", "").split("/")[0]),
                "name": token_attrs.get("name", ""),
                "liquidity": float(attrs.get("reserve_in_usd", 0) or 0),
                "volume_24h": float(attrs.get("volume_usd", {}).get("h24", 0) or 0),
                "price": float(attrs.get("base_token_price_usd", 0) or 0),
            })

            if len(result) >= limit:
                break

        return result
    except Exception as e:
        logger.warning(f"[trending_aggregator] GeckoTerminal fetch failed: {e}")
        return []


def _fetch_dexscreener_trending(limit: int, cache_ttl: int) -> List[Dict[str, Any]]:
    """Fetch boosted/trending tokens from DexScreener."""
    try:
        # DexScreener doesn't have a direct trending endpoint,
        # but we can use the token boosters API
        url = "https://api.dexscreener.com/token-boosts/top/v1"

        headers = {"User-Agent": "LifeOS/1.0"}
        resp = requests.get(url, headers=headers, timeout=20)

        if resp.status_code != 200:
            return []

        data = resp.json()

        result = []
        seen_mints: Set[str] = set()

        for item in data:
            # Filter to Solana only
            chain = item.get("chainId", "")
            if chain != "solana":
                continue

            mint = item.get("tokenAddress", "")
            if not mint or mint in seen_mints:
                continue
            seen_mints.add(mint)

            result.append({
                "mint": mint,
                "symbol": item.get("symbol", ""),
                "name": item.get("name", ""),
                "liquidity": 0.0,  # Not available in boost API
                "volume_24h": 0.0,
                "price": 0.0,
            })

            if len(result) >= limit:
                break

        return result
    except Exception as e:
        logger.warning(f"[trending_aggregator] DexScreener fetch failed: {e}")
        return []


def _compute_composite_ranks(tokens: List[TrendingToken]) -> None:
    """Compute weighted composite rank for each token."""
    max_rank = len(tokens) + 1

    for token in tokens:
        weighted_sum = 0.0
        total_weight = 0.0

        if token.birdeye_rank is not None:
            weighted_sum += token.birdeye_rank * SOURCE_WEIGHTS["birdeye"]
            total_weight += SOURCE_WEIGHTS["birdeye"]

        if token.gecko_rank is not None:
            weighted_sum += token.gecko_rank * SOURCE_WEIGHTS["geckoterminal"]
            total_weight += SOURCE_WEIGHTS["geckoterminal"]

        if token.dexscreener_rank is not None:
            weighted_sum += token.dexscreener_rank * SOURCE_WEIGHTS["dexscreener"]
            total_weight += SOURCE_WEIGHTS["dexscreener"]

        if total_weight > 0:
            # Normalize by weight and add bonus for multi-source confirmation
            token.composite_rank = weighted_sum / total_weight

            # Bonus: reduce rank (improve position) for multi-source tokens
            source_count = len(token.sources)
            if source_count >= 2:
                token.composite_rank *= 0.9  # 10% bonus for 2+ sources
            if source_count >= 3:
                token.composite_rank *= 0.9  # Additional 10% for all 3 sources
        else:
            token.composite_rank = max_rank


def _compute_velocity_signals(tokens: List[TrendingToken]) -> None:
    """Compute velocity (rate of rank change) from historical data."""
    history = _load_history()
    now = time.time()

    for token in tokens:
        mint = token.mint

        # Get historical ranks
        hist = history.get(mint, [])
        if not hist:
            continue

        # Compute velocity for different windows
        # velocity = (old_rank - new_rank) / old_rank
        # Positive = rising in ranks (improving)

        for entry in hist:
            age_seconds = now - entry.get("timestamp", now)
            old_rank = entry.get("composite_rank", token.composite_rank)

            if old_rank <= 0:
                continue

            velocity = (old_rank - token.composite_rank) / old_rank

            if age_seconds <= 900:  # 15 min
                token.velocity_15m = max(token.velocity_15m, velocity)
            elif age_seconds <= 3600:  # 1 hour
                token.velocity_1h = max(token.velocity_1h, velocity)
            elif age_seconds <= 14400:  # 4 hours
                token.velocity_4h = max(token.velocity_4h, velocity)

        # Overall velocity is weighted combination
        token.velocity = (
            token.velocity_15m * 0.5 +
            token.velocity_1h * 0.3 +
            token.velocity_4h * 0.2
        )


def _load_history() -> Dict[str, List[Dict[str, Any]]]:
    """Load historical ranking data."""
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _update_history(tokens: List[TrendingToken]) -> None:
    """Update historical ranking data."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    history = _load_history()
    now = time.time()

    # Add current snapshot
    for token in tokens:
        mint = token.mint
        if mint not in history:
            history[mint] = []

        history[mint].append({
            "timestamp": now,
            "composite_rank": token.composite_rank,
            "birdeye_rank": token.birdeye_rank,
            "gecko_rank": token.gecko_rank,
            "dexscreener_rank": token.dexscreener_rank,
        })

        # Keep only last 4 hours of history
        cutoff = now - 14400
        history[mint] = [
            h for h in history[mint]
            if h.get("timestamp", 0) > cutoff
        ]

    # Clean up old tokens not seen recently
    cutoff = now - 86400  # 24 hours
    to_remove = []
    for mint, entries in history.items():
        if not entries or entries[-1].get("timestamp", 0) < cutoff:
            to_remove.append(mint)
    for mint in to_remove:
        del history[mint]

    # Save
    try:
        HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except IOError as e:
        logger.warning(f"[trending_aggregator] Failed to save history: {e}")


def filter_rising_velocity(
    tokens: List[TrendingToken],
    min_velocity: float = 0.1,
) -> List[TrendingToken]:
    """Filter tokens with rising velocity (improving rank)."""
    return [t for t in tokens if t.velocity >= min_velocity]


def filter_by_liquidity(
    tokens: List[TrendingToken],
    min_liquidity_usd: float = 100_000,
) -> List[TrendingToken]:
    """Filter tokens by minimum liquidity."""
    return [t for t in tokens if t.liquidity_usd >= min_liquidity_usd]


def filter_by_volume(
    tokens: List[TrendingToken],
    min_volume_24h_usd: float = 250_000,
) -> List[TrendingToken]:
    """Filter tokens by minimum 24h volume."""
    return [t for t in tokens if t.volume_24h_usd >= min_volume_24h_usd]


# ============================================================================
# CLI Demo
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=== Multi-Source Trending Aggregator ===\n")

    print("Fetching trending tokens from all sources...")
    tokens = fetch_trending_all_sources(limit=20)

    print(f"\nTop 20 Trending Tokens (across {len(set(s for t in tokens for s in t.sources))} sources):\n")
    print(f"{'Rank':<5} {'Symbol':<12} {'Composite':<10} {'Velocity':<10} {'Sources':<20} {'Liquidity':>12}")
    print("-" * 80)

    for i, token in enumerate(tokens, 1):
        sources_str = ",".join(token.sources)
        liquidity_str = f"${token.liquidity_usd:,.0f}" if token.liquidity_usd > 0 else "N/A"
        vel_str = f"{token.velocity:+.2%}" if token.velocity != 0 else "0"

        print(f"{i:<5} {token.symbol[:11]:<12} {token.composite_rank:<10.2f} {vel_str:<10} {sources_str:<20} {liquidity_str:>12}")

    # Show rising velocity tokens
    rising = filter_rising_velocity(tokens, min_velocity=0.05)
    if rising:
        print(f"\n🚀 Rising Velocity Tokens ({len(rising)}):")
        for t in rising[:5]:
            print(f"  - {t.symbol}: velocity={t.velocity:+.2%}, rank={t.composite_rank:.1f}")

    print("\n✓ Trending aggregator ready")
