"""
Demo Bot - Sentiment & Market Data Module

Contains:
- Market regime detection
- AI sentiment for tokens
- Trending tokens with sentiment
- Conviction picks generation
- Bags.fm top tokens
- Sentiment cache management
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Sentiment Data Cache (US-008: 15-Minute Update Cycle)
# =============================================================================

_SENTIMENT_CACHE = {"tokens": [], "last_update": None, "macro": {}}
_SENTIMENT_LOCK = asyncio.Lock()


async def _update_sentiment_cache(context: Any = None) -> None:
    """
    Update sentiment data cache from sentiment_report_data.json.

    US-008: This function is called every 15 minutes to refresh the cached
    sentiment data displayed in the demo bot.

    Data source: bots/twitter/sentiment_report_data.json (updated by sentiment_report.py)
    """
    async with _SENTIMENT_LOCK:
        try:
            sentiment_file = Path(__file__).resolve().parents[3] / "bots" / "twitter" / "sentiment_report_data.json"
            if not sentiment_file.exists():
                logger.debug("Sentiment report data not available yet")
                return

            with open(sentiment_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            _SENTIMENT_CACHE["tokens"] = data.get("tokens_raw", [])
            _SENTIMENT_CACHE["last_update"] = datetime.now(timezone.utc)
            _SENTIMENT_CACHE["macro"] = {
                "stocks": data.get("stocks", ""),
                "commodities": data.get("commodities", ""),
                "metals": data.get("metals", ""),
                "solana": data.get("solana", ""),
            }

            logger.info(f"Sentiment cache updated: {len(_SENTIMENT_CACHE['tokens'])} tokens")

        except Exception as e:
            logger.warning(f"Failed to update sentiment cache: {e}")


def get_cached_sentiment_tokens() -> List[Dict[str, Any]]:
    """Get cached sentiment tokens (updated every 15 min)."""
    return _SENTIMENT_CACHE.get("tokens", [])


def get_cached_macro_sentiment() -> Dict[str, str]:
    """Get cached macro sentiment data."""
    return _SENTIMENT_CACHE.get("macro", {})


def get_sentiment_cache_age() -> Optional[timedelta]:
    """Get age of sentiment cache."""
    last_update = _SENTIMENT_CACHE.get("last_update")
    if not last_update:
        return None
    return datetime.now(timezone.utc) - last_update


# =============================================================================
# Market Regime Detection
# =============================================================================

async def get_market_regime() -> Dict[str, Any]:
    """Get current market regime from sentiment engine."""
    try:
        # Try to get real market data from DexScreener
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Get SOL price data
            async with session.get(
                "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        sol_pair = pairs[0]
                        sol_change = float(sol_pair.get("priceChange", {}).get("h24", 0))

                        # Determine regime based on SOL price action
                        if sol_change > 5:
                            regime = "BULL"
                            risk = "LOW"
                        elif sol_change > 0:
                            regime = "NEUTRAL"
                            risk = "NORMAL"
                        elif sol_change > -5:
                            regime = "NEUTRAL"
                            risk = "NORMAL"
                        else:
                            regime = "BEAR"
                            risk = "HIGH"

                        return {
                            "btc_trend": "BULLISH" if sol_change > 0 else "BEARISH",
                            "sol_trend": "BULLISH" if sol_change > 0 else "BEARISH",
                            "btc_change_24h": sol_change * 0.7,  # Approximate BTC correlation
                            "sol_change_24h": sol_change,
                            "risk_level": risk,
                            "regime": regime,
                        }

        # Try cached regime from sentiment engine (if available)
        try:
            from core.caching.sentiment_cache import get_sentiment_cache
            cache = get_sentiment_cache()
            cached = await cache.get_market_regime()
            if cached:
                return cached
        except Exception as e:
            logger.warning(f"Could not load cached regime: {e}")

        return {
            "btc_trend": "NEUTRAL",
            "sol_trend": "NEUTRAL",
            "btc_change_24h": 0.0,
            "sol_change_24h": 0.0,
            "risk_level": "NORMAL",
            "regime": "NEUTRAL",
        }
    except Exception as e:
        logger.warning(f"Could not fetch market regime: {e}")
        return {"regime": "UNKNOWN", "risk_level": "UNKNOWN"}


# =============================================================================
# AI Sentiment for Tokens
# =============================================================================

async def get_ai_sentiment_for_token(address: str) -> Dict[str, Any]:
    """Get AI sentiment analysis for a token."""
    # Import here to avoid circular imports
    from tg_bot.handlers.demo.demo_trading import get_bags_client

    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signal = await service.get_comprehensive_signal(
            address, include_sentiment=True
        )
        return {
            "symbol": signal.symbol,
            "price": signal.price_usd,
            "change_24h": signal.price_change_24h,
            "volume": signal.volume_24h,
            "liquidity": signal.liquidity_usd,
            "sentiment": signal.sentiment,
            "score": signal.sentiment_score,
            "confidence": signal.sentiment_confidence,
            "summary": signal.sentiment_summary,
            "signal": signal.signal,
            "signal_score": signal.signal_score,
            "reasons": signal.signal_reasons,
        }
    except Exception as e:
        logger.warning(f"Could not get sentiment: {e}")

    # Fallback to Bags token info if signal service is unavailable
    try:
        bags_client = get_bags_client()
        if bags_client:
            token = await bags_client.get_token_info(address)
            if token:
                return {
                    "symbol": token.symbol or address[:6],
                    "price": token.price_usd,
                    "change_24h": token.price_change_24h,
                    "volume": token.volume_24h,
                    "liquidity": token.liquidity,
                    "sentiment": "neutral",
                    "score": 0.5,
                    "confidence": 0.0,
                    "summary": "Bags price data",
                    "signal": "NEUTRAL",
                    "signal_score": 0.5,
                    "reasons": ["Bags fallback"],
                }
    except Exception as e:
        logger.warning(f"Could not get Bags fallback sentiment: {e}")

    # Fallback to Jupiter/DexScreener token data for price + symbol
    try:
        from bots.treasury.jupiter import JupiterClient
        jupiter = JupiterClient()
        token = await jupiter.get_token_info(address)
        if token:
            return {
                "symbol": token.symbol or address[:6],
                "price": token.price_usd,
                "change_24h": getattr(token, "price_change_24h", 0),
                "volume": getattr(token, "volume_24h", 0),
                "liquidity": getattr(token, "liquidity", 0),
                "sentiment": "neutral",
                "score": 0.5,
                "confidence": 0.0,
                "summary": "Jupiter/Dex fallback",
                "signal": "NEUTRAL",
                "signal_score": 0.5,
                "reasons": ["Jupiter fallback"],
            }
    except Exception as e:
        logger.warning(f"Could not get Jupiter fallback sentiment: {e}")

    return {"sentiment": "unknown", "score": 0, "confidence": 0}


# =============================================================================
# Trending Tokens with Sentiment
# =============================================================================

async def get_trending_with_sentiment(limit: int = 15) -> List[Dict[str, Any]]:
    """Get trending tokens with AI sentiment overlay."""
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signals = await service.get_trending_tokens(limit=limit)
        if signals:
            return [
                {
                    "symbol": s.symbol,
                    "address": s.address,
                    "price_usd": s.price_usd,
                    "change_24h": s.price_change_24h,
                    "volume": s.volume_24h,
                    "liquidity": s.liquidity_usd,
                    "sentiment": s.sentiment,
                    "sentiment_score": s.sentiment_score,
                    "signal": s.signal,
                }
                for s in signals
            ]
    except Exception as e:
        logger.warning(f"Could not get trending: {e}")

    # DexScreener fallback - reliable trending token data
    try:
        from core.dexscreener import get_solana_trending
        dex_tokens = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: get_solana_trending(
                min_liquidity=10_000,
                min_volume_24h=50_000,
                limit=limit
            )
        )
        if dex_tokens:
            return [
                {
                    "symbol": t.base_token_symbol,
                    "address": t.base_token_address,
                    "price_usd": t.price_usd,
                    "change_24h": t.price_change_24h,
                    "volume": t.volume_24h,
                    "liquidity": t.liquidity_usd,
                    "sentiment": "neutral",  # No AI sentiment in fallback
                    "sentiment_score": 0.5,
                    "signal": "NEUTRAL",
                    "chart_url": f"https://dexscreener.com/solana/{t.base_token_address}",
                }
                for t in dex_tokens
            ]
    except Exception as e:
        logger.warning(f"Could not get DexScreener trending fallback: {e}")
    return []


# =============================================================================
# Conviction Picks
# =============================================================================

def _conviction_label(score: float) -> str:
    """Convert score to conviction label.

    NOTE: Conviction thresholds are aligned to demo UX:
      - HIGH: 85+
      - MEDIUM: 60–84
      - LOW: <60
    """
    if score >= 85:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def _default_tp_sl(conviction: str) -> Tuple[int, int]:
    """Get default TP/SL for conviction level."""
    if conviction == "HIGH":
        return 30, 12
    if conviction == "MEDIUM":
        return 22, 12
    return 15, 15


def _grade_for_signal_name(signal_name: str) -> str:
    """Convert signal name to grade."""
    mapping = {
        "STRONG_BUY": "A",
        "BUY": "B+",
        "NEUTRAL": "C+",
        "SELL": "C",
        "STRONG_SELL": "C",
        "AVOID": "C",
    }
    return mapping.get((signal_name or "").upper(), "B")


def _pick_key(pick: Dict[str, Any]) -> str:
    """Get unique key for a pick."""
    address = (pick.get("address") or "").lower().strip()
    if address:
        return address
    return (pick.get("symbol") or "").lower().strip()


def _load_treasury_top_picks(limit: int = 5) -> List[Dict[str, Any]]:
    """Load treasury top picks from temp file."""
    try:
        picks_file = Path(tempfile.gettempdir()) / "jarvis_top_picks.json"
        if not picks_file.exists():
            return []
        with open(picks_file, "r") as handle:
            data = json.load(handle) or []
        picks = []
        for entry in data[:limit]:
            symbol = entry.get("symbol", "???")
            address = entry.get("contract") or ""
            conviction_score = float(entry.get("conviction", 0) or 0)
            conviction = _conviction_label(conviction_score)
            entry_price = float(entry.get("entry_price", 0) or 0)
            target_price = float(entry.get("target_price", 0) or 0)
            stop_loss = float(entry.get("stop_loss", 0) or 0)
            tp_pct = 0
            sl_pct = 0
            if entry_price > 0 and target_price > 0:
                tp_pct = int(round(((target_price - entry_price) / entry_price) * 100))
            if entry_price > 0 and stop_loss > 0:
                sl_pct = int(round(((entry_price - stop_loss) / entry_price) * 100))
            if not tp_pct or not sl_pct:
                tp_pct, sl_pct = _default_tp_sl(conviction)
            picks.append({
                "symbol": symbol,
                "address": address,
                "conviction": conviction,
                "thesis": entry.get("reasoning", ""),
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "tp_percent": tp_pct,
                "sl_percent": sl_pct,
                "score": conviction_score,
            })
        return picks
    except Exception as e:
        logger.warning(f"Could not load treasury picks: {e}")
        return []


def _get_pick_stats() -> Dict[str, Any]:
    """Get statistics about picks performance."""
    return {
        "total_picks": 0,
        "winning_picks": 0,
        "losing_picks": 0,
        "avg_return": 0.0,
        "best_return": 0.0,
        "worst_return": 0.0,
    }


async def get_conviction_picks() -> List[Dict[str, Any]]:
    """
    Get AI conviction picks with multi-source analysis.

    Combines:
    - Treasury top picks
    - Sentiment engine picks
    - Technical analysis

    Returns:
        List of pick dictionaries with conviction scores
    """
    picks = []

    # Load treasury picks
    treasury_picks = _load_treasury_top_picks(limit=5)
    picks.extend(treasury_picks)

    # Try signal service picks
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()
        signals = await service.get_top_signals(limit=5)
        if signals:
            for s in signals:
                # Skip if already in picks
                if any(_pick_key(p) == s.address.lower() for p in picks):
                    continue
                signal_name = s.signal or "NEUTRAL"
                conviction = "HIGH" if signal_name == "STRONG_BUY" else "MEDIUM" if signal_name == "BUY" else "LOW"
                tp_pct, sl_pct = _default_tp_sl(conviction)
                picks.append({
                    "symbol": s.symbol,
                    "address": s.address,
                    "conviction": conviction,
                    "thesis": s.sentiment_summary or "",
                    "entry_price": s.price_usd,
                    "target_price": s.price_usd * (1 + tp_pct / 100),
                    "stop_loss": s.price_usd * (1 - sl_pct / 100),
                    "tp_percent": tp_pct,
                    "sl_percent": sl_pct,
                    "score": (s.sentiment_score or 0.5) * 100,
                    "grade": _grade_for_signal_name(signal_name),
                    "signal": signal_name,
                })
    except Exception as e:
        logger.warning(f"Could not get signal service picks: {e}")

    if picks:
        return picks[:10]  # Limit to 10 picks

    # Fallback: REAL ranked data only (no placeholders)
    #
    # Spec:
    #  1) Use get_bags_top_tokens_with_sentiment()
    #  2) Sort by score desc
    #  3) Take top 5
    #  4) Group handled at render time (HIGH 85+ / MED 70–84 / LOW <70)
    try:
        bags_tokens = await get_bags_top_tokens_with_sentiment(limit=25)
    except Exception:
        bags_tokens = []

    for t in (bags_tokens or []):
        sentiment_score = float(t.get("sentiment_score", 0.5) or 0.5)
        score = int(round(sentiment_score * 100))
        conviction = _conviction_label(score)
        tp_pct, sl_pct = _default_tp_sl(conviction)
        price = float(t.get("price_usd", 0) or 0)

        picks.append({
            "symbol": t.get("symbol", "???"),
            "address": t.get("address", ""),
            "conviction": conviction,
            # No demo placeholder thesis
            "thesis": "",
            "entry_price": price,
            "target_price": price * (1 + tp_pct / 100) if price else 0,
            "stop_loss": price * (1 - sl_pct / 100) if price else 0,
            "tp_percent": tp_pct,
            "sl_percent": sl_pct,
            "score": score,
            "signal": t.get("signal", "NEUTRAL"),
            "sentiment": t.get("sentiment", "neutral"),
            "change_24h": float(t.get("change_24h", 0) or 0),
            "volume_24h": float(t.get("volume_24h", t.get("volume", 0)) or 0),
            "chart_url": t.get("chart_url"),
        })

    if picks:
        picks = sorted(picks, key=lambda p: float(p.get("score", 0) or 0), reverse=True)
        return picks[:10]

    # Real data only: if all upstream sources fail, return empty and let the UI
    # display a clear empty-state rather than injecting placeholder tokens.
    return []


# =============================================================================
# Bags.fm Top Tokens (Bags + DexScreener Fallback)
# =============================================================================

_BAGS_POOLS_MINTS_CACHE: Optional[set[str]] = None
_BAGS_POOLS_MINTS_CACHE_TS: Optional[datetime] = None
_BAGS_POOLS_MINTS_LOCK = asyncio.Lock()
_BAGS_POOLS_MINTS_TTL_SEC: int = 24 * 60 * 60  # 24 hours


def _looks_like_bags_launch_mint(address: str) -> bool:
    """Best-effort check for "bags.fm launch" mints.

    In practice, bags.fm launch mints have a vanity suffix "BAGS". We use this to
    prevent DexScreener trending (often dominated by pump.fun) from polluting the
    "🎒 BAGS.FM TOP 15" menu.

    This is intentionally conservative: if we cannot confidently classify the
    mint as a bags launch, we exclude it from this specific menu.
    """
    addr = (address or "").strip()
    if not addr:
        return False
    # pump.fun launch mints often end with "pump" (user report). Block them here.
    lower = addr.lower()
    if lower.endswith("pump"):
        return False
    return lower.endswith("bags")


def _bags_pools_mints_cache_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "bags" / "bags_pools_token_mints.txt"


async def _get_bags_pools_token_mints(*, force_refresh: bool = False) -> set[str]:
    """Return a cached set of token mints launched via bags.fm DBC pools.

    Source-of-truth: GET https://public-api-v2.bags.fm/api/v1/solana/bags/pools

    Note: This endpoint returns a large payload (100k+ items) and currently does
    not accept query params. We cache it aggressively to avoid UI timeouts.
    """
    global _BAGS_POOLS_MINTS_CACHE, _BAGS_POOLS_MINTS_CACHE_TS

    now = datetime.now(timezone.utc)
    cache_path = _bags_pools_mints_cache_path()

    def _load_from_disk() -> set[str]:
        if not cache_path.exists():
            return set()
        try:
            mints = set()
            for raw in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
                mint = (raw or "").strip()
                if mint:
                    mints.add(mint)
            return mints
        except Exception:
            return set()

    async with _BAGS_POOLS_MINTS_LOCK:
        # Memory cache
        if (
            not force_refresh
            and _BAGS_POOLS_MINTS_CACHE
            and _BAGS_POOLS_MINTS_CACHE_TS
            and (now - _BAGS_POOLS_MINTS_CACHE_TS).total_seconds() <= _BAGS_POOLS_MINTS_TTL_SEC
        ):
            return _BAGS_POOLS_MINTS_CACHE

        # Disk cache (mtime-based)
        if not force_refresh and cache_path.exists():
            try:
                age = now.timestamp() - cache_path.stat().st_mtime
            except Exception:
                age = None
            if age is not None and age <= _BAGS_POOLS_MINTS_TTL_SEC:
                mints = _load_from_disk()
                if mints:
                    _BAGS_POOLS_MINTS_CACHE = mints
                    _BAGS_POOLS_MINTS_CACHE_TS = now
                    return mints

        # Fetch from Bags (public)
        try:
            import httpx

            url = "https://public-api-v2.bags.fm/api/v1/solana/bags/pools"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                payload = resp.json() or {}

            if not payload.get("success"):
                raise RuntimeError("bags_pools_api_failed")

            items = payload.get("response") or []
            seen = set()
            ordered: List[str] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                mint = (it.get("tokenMint") or "").strip()
                if not mint or mint in seen:
                    continue
                seen.add(mint)
                ordered.append(mint)

            mints = set(ordered)
            if mints:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text("\n".join(ordered).rstrip("\n") + "\n", encoding="utf-8")

                _BAGS_POOLS_MINTS_CACHE = mints
                _BAGS_POOLS_MINTS_CACHE_TS = now
            return mints
        except Exception as e:
            logger.warning(f"Failed to fetch bags pools mints: {e}")
            # Last resort: serve stale disk cache (even if expired).
            mints = _load_from_disk()
            if mints:
                _BAGS_POOLS_MINTS_CACHE = mints
                _BAGS_POOLS_MINTS_CACHE_TS = now
            return mints


async def _get_dexscreener_trending_pairs(*, limit: int) -> List[Any]:
    """Async wrapper around core.dexscreener.get_solana_trending (sync)."""
    def _fetch() -> List[Any]:
        from core.dexscreener import get_solana_trending
        # Keep filters permissive; we filter and rank by volume after bags-only filtering.
        return get_solana_trending(
            min_liquidity=2_000,
            min_volume_24h=0,
            max_liquidity=50_000_000,
            limit=limit,
            cache_ttl_seconds=120,
        )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def _fallback_bags_top_tokens_via_dexscreener(limit: int) -> List[Dict[str, Any]]:
    """Bags Top 15 fallback when bags.fm leaderboard endpoints are unavailable.

    Strategy:
    - Pull trending Solana tokens from DexScreener
    - Filter to bags launch mints (vanity suffix "BAGS"), then rank by 24h volume
    """
    try:
        fetch_limit = max(250, limit * 25)
        pairs = await _get_dexscreener_trending_pairs(limit=fetch_limit)
        if not pairs:
            return []

        out: List[Dict[str, Any]] = []
        for p in pairs:
            address = (getattr(p, "base_token_address", "") or "").strip()
            if not _looks_like_bags_launch_mint(address):
                continue

            symbol = (getattr(p, "base_token_symbol", "") or "").strip()
            name = (getattr(p, "base_token_name", "") or "").strip()
            pair_address = (getattr(p, "pair_address", "") or "").strip()
            out.append({
                "address": address,
                "symbol": symbol or address[:6],
                "name": name or symbol or address[:6],
                "decimals": 9,
                "price_usd": float(getattr(p, "price_usd", 0) or 0),
                "price_sol": float(getattr(p, "price_native", 0) or 0),
                "volume_24h": float(getattr(p, "volume_24h", 0) or 0),
                "liquidity": float(getattr(p, "liquidity_usd", 0) or 0),
                "holders": 0,
                "market_cap": 0,
                "price_change_24h": float(getattr(p, "price_change_24h", 0) or 0),
                "chart_url": f"https://dexscreener.com/solana/{pair_address or address}",
                "source": "dexscreener_bags_only",
            })

        out.sort(key=lambda t: float(t.get("volume_24h", 0) or 0), reverse=True)
        return out[:limit]
    except Exception as e:
        logger.warning(f"DexScreener fallback for Bags top tokens failed: {e}")
        return []


async def get_bags_top_tokens_with_sentiment(limit: int = 15) -> List[Dict[str, Any]]:
    """\
    Get Bags.fm top tokens by volume with sentiment overlay.

    IMPORTANT: For the /demo "BAGS Top 15" menu, we only want tokens launched on bags.fm.
    That means:
      - Prefer the official bags.fm API (/tokens/top via BagsClient)
      - Do NOT "guess" using name/symbol suffixes like "bags" or address patterns

    If the bags.fm leaderboard endpoint is unavailable, we return an empty list and the UI
    shows a clear empty-state (this prevents DexScreener "trending" tokens, usually pump.fun,
    from being mislabeled as bags.fm launches).
    """
    from tg_bot.handlers.demo.demo_trading import get_bags_client

    def _field(token: Any, key: str, default: Any = None) -> Any:
        if isinstance(token, dict):
            return token.get(key, default)
        return getattr(token, key, default)

    def _coerce_volume(token: Any) -> float:
        return float(_field(token, "volume_24h", _field(token, "volume", 0)) or 0)

    try:
        from core.feature_flags import is_xai_enabled

        bags_client = get_bags_client()
        # We may need to fetch more than `limit` to get enough bags launch mints after filtering.
        fetch_limit = max(limit * 6, 90)
        fetch_limit = min(fetch_limit, 200)

        tokens: List[Any] = []
        if bags_client:
            # Telegram callbacks are time-sensitive; cap total wait here to avoid handler timeouts.
            tokens = await asyncio.wait_for(
                bags_client.get_top_tokens_by_volume(limit=fetch_limit, allow_public=True),
                timeout=7.0,
            )

        # Filter to bags launch mints only (prevents pump.fun tokens in the Bags menu).
        tokens = [
            t for t in (tokens or [])
            if _looks_like_bags_launch_mint(_field(t, "address", ""))
        ]

        if not tokens:
            return []

        tokens = sorted(tokens, key=_coerce_volume, reverse=True)

        result: List[Dict[str, Any]] = []
        allow_ai_sentiment = is_xai_enabled(default=True)
        for t in tokens[:limit]:
            address = _field(t, "address", "")
            # Get sentiment for each token
            if allow_ai_sentiment:
                try:
                    sentiment = await get_ai_sentiment_for_token(address)
                except Exception:
                    sentiment = {"sentiment": "neutral", "score": 0.5, "signal": "NEUTRAL"}
            else:
                sentiment = {"sentiment": "neutral", "score": 0.5, "signal": "NEUTRAL"}

            change_24h = _field(t, "price_change_24h", None)
            if change_24h is None:
                change_24h = sentiment.get("change_24h", 0)

            result.append({
                "symbol": _field(t, "symbol", "") or address[:6],
                "name": _field(t, "name", ""),
                "address": address,
                "price_usd": _field(t, "price_usd", 0),
                "change_24h": change_24h or 0,
                "volume_24h": _coerce_volume(t),
                "liquidity": _field(t, "liquidity", 0),
                "holders": _field(t, "holders", 0),
                "market_cap": _field(t, "market_cap", 0),
                "sentiment": sentiment.get("sentiment", "neutral"),
                "sentiment_score": sentiment.get("score", 0.5),
                "signal": sentiment.get("signal", "NEUTRAL"),
                "chart_url": _field(t, "chart_url", None),
                "source": _field(t, "source", "bags_fm"),
            })

        return result

    except Exception as e:
        logger.warning(f"Could not get Bags top tokens: {e}")
        return []

