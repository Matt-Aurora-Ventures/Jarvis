"""
Token Screener - Multi-Factor Token Analysis
=============================================

Combines multiple data sources for comprehensive token screening:
- Rugcheck safety checks
- Market data (liquidity, volume, price)
- Social metrics (Twitter, Telegram presence)
- Holder distribution analysis

Provides:
- Risk scoring with configurable weights
- Token ranking by opportunity score
- Filtering by configurable criteria
- Cache management for efficient batch screening

Usage:
    from core.token_screener import TokenScreener, ScreeningCriteria

    screener = TokenScreener()
    criteria = ScreeningCriteria(min_market_cap=50000, min_liquidity=10000)
    results = screener.screen_tokens(["mint1", "mint2"], criteria)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "screener_cache"

# Default cache TTLs (in seconds)
CACHE_TTL_RUGCHECK = 3600  # 1 hour for safety data
CACHE_TTL_MARKET = 300     # 5 minutes for market data
CACHE_TTL_SOCIAL = 1800    # 30 minutes for social data
CACHE_TTL_SCREENING = 600  # 10 minutes for full screening results


class RiskLevel(Enum):
    """Risk classification levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ScreeningCriteria:
    """Configurable screening criteria for token filtering."""

    # Market cap thresholds
    min_market_cap: float = 10_000.0
    max_market_cap: float = 100_000_000.0

    # Liquidity thresholds
    min_liquidity: float = 5_000.0
    max_liquidity: float = 50_000_000.0

    # Volume thresholds (24h)
    min_volume_24h: float = 1_000.0
    max_volume_24h: float = 100_000_000.0

    # Age requirements (hours)
    min_age_hours: float = 0.0
    max_age_hours: float = 8760.0  # 1 year

    # Holder distribution
    min_holders: int = 10
    max_top_holder_pct: float = 50.0  # Top holder cannot hold more than 50%

    # Risk score threshold (0-100, higher = more risky)
    max_risk_score: float = 70.0

    # Rugcheck requirements
    require_locked_liquidity: bool = True
    min_locked_liquidity_pct: float = 50.0
    require_authorities_revoked: bool = True

    # Social requirements
    require_twitter: bool = False
    require_telegram: bool = False
    require_website: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "min_market_cap": self.min_market_cap,
            "max_market_cap": self.max_market_cap,
            "min_liquidity": self.min_liquidity,
            "max_liquidity": self.max_liquidity,
            "min_volume_24h": self.min_volume_24h,
            "max_volume_24h": self.max_volume_24h,
            "min_age_hours": self.min_age_hours,
            "max_age_hours": self.max_age_hours,
            "min_holders": self.min_holders,
            "max_top_holder_pct": self.max_top_holder_pct,
            "max_risk_score": self.max_risk_score,
            "require_locked_liquidity": self.require_locked_liquidity,
            "min_locked_liquidity_pct": self.min_locked_liquidity_pct,
            "require_authorities_revoked": self.require_authorities_revoked,
            "require_twitter": self.require_twitter,
            "require_telegram": self.require_telegram,
            "require_website": self.require_website,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScreeningCriteria":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RiskWeights:
    """Configurable weights for risk score calculation."""

    # Safety factors (higher weight = more important)
    rugcheck_safety: float = 0.25
    liquidity_lock: float = 0.20
    holder_distribution: float = 0.15

    # Market factors
    liquidity_depth: float = 0.15
    volume_stability: float = 0.10

    # Social/reputation factors
    social_presence: float = 0.10
    token_age: float = 0.05

    def validate(self) -> bool:
        """Validate that weights sum to 1.0."""
        total = (
            self.rugcheck_safety +
            self.liquidity_lock +
            self.holder_distribution +
            self.liquidity_depth +
            self.volume_stability +
            self.social_presence +
            self.token_age
        )
        return abs(total - 1.0) < 0.001

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "rugcheck_safety": self.rugcheck_safety,
            "liquidity_lock": self.liquidity_lock,
            "holder_distribution": self.holder_distribution,
            "liquidity_depth": self.liquidity_depth,
            "volume_stability": self.volume_stability,
            "social_presence": self.social_presence,
            "token_age": self.token_age,
        }


@dataclass
class RugcheckData:
    """Safety data from rugcheck analysis."""

    is_safe: bool = False
    risk_score: float = 100.0  # 0-100, higher = more risky
    issues: List[str] = field(default_factory=list)

    lp_locked_pct: float = 0.0
    lp_locked_usd: float = 0.0
    mint_authority_active: bool = True
    freeze_authority_active: bool = True
    is_rugged: bool = False
    transfer_fee_bps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_safe": self.is_safe,
            "risk_score": self.risk_score,
            "issues": self.issues,
            "lp_locked_pct": self.lp_locked_pct,
            "lp_locked_usd": self.lp_locked_usd,
            "mint_authority_active": self.mint_authority_active,
            "freeze_authority_active": self.freeze_authority_active,
            "is_rugged": self.is_rugged,
            "transfer_fee_bps": self.transfer_fee_bps,
        }


@dataclass
class MarketData:
    """Market data for a token."""

    price_usd: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    liquidity_usd: float = 0.0
    market_cap: float = 0.0
    fdv: float = 0.0

    # Trading activity
    txns_24h: int = 0
    buys_24h: int = 0
    sells_24h: int = 0

    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "price_usd": self.price_usd,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "volume_1h": self.volume_1h,
            "liquidity_usd": self.liquidity_usd,
            "market_cap": self.market_cap,
            "fdv": self.fdv,
            "txns_24h": self.txns_24h,
            "buys_24h": self.buys_24h,
            "sells_24h": self.sells_24h,
            "source": self.source,
        }


@dataclass
class SocialMetrics:
    """Social presence metrics."""

    has_twitter: bool = False
    twitter_url: str = ""
    twitter_followers: int = 0

    has_telegram: bool = False
    telegram_url: str = ""
    telegram_members: int = 0

    has_website: bool = False
    website_url: str = ""

    has_discord: bool = False
    discord_url: str = ""

    social_score: float = 0.0  # 0-100, higher = better social presence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "has_twitter": self.has_twitter,
            "twitter_url": self.twitter_url,
            "twitter_followers": self.twitter_followers,
            "has_telegram": self.has_telegram,
            "telegram_url": self.telegram_url,
            "telegram_members": self.telegram_members,
            "has_website": self.has_website,
            "website_url": self.website_url,
            "has_discord": self.has_discord,
            "discord_url": self.discord_url,
            "social_score": self.social_score,
        }


@dataclass
class HolderData:
    """Holder distribution data."""

    total_holders: int = 0
    top_holder_pct: float = 100.0
    top_10_holders_pct: float = 100.0
    creator_holding_pct: float = 0.0

    distribution_score: float = 0.0  # 0-100, higher = better distribution

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_holders": self.total_holders,
            "top_holder_pct": self.top_holder_pct,
            "top_10_holders_pct": self.top_10_holders_pct,
            "creator_holding_pct": self.creator_holding_pct,
            "distribution_score": self.distribution_score,
        }


@dataclass
class ScreeningResult:
    """Complete screening result for a token."""

    mint: str
    symbol: str = ""
    name: str = ""

    # Aggregated data
    rugcheck: Optional[RugcheckData] = None
    market: Optional[MarketData] = None
    social: Optional[SocialMetrics] = None
    holders: Optional[HolderData] = None

    # Scoring
    risk_score: float = 100.0  # 0-100, higher = more risky
    risk_level: RiskLevel = RiskLevel.CRITICAL
    opportunity_score: float = 0.0  # 0-100, higher = better opportunity

    # Filtering
    passed_criteria: bool = False
    failed_reasons: List[str] = field(default_factory=list)

    # Metadata
    age_hours: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mint": self.mint,
            "symbol": self.symbol,
            "name": self.name,
            "rugcheck": self.rugcheck.to_dict() if self.rugcheck else None,
            "market": self.market.to_dict() if self.market else None,
            "social": self.social.to_dict() if self.social else None,
            "holders": self.holders.to_dict() if self.holders else None,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "opportunity_score": self.opportunity_score,
            "passed_criteria": self.passed_criteria,
            "failed_reasons": self.failed_reasons,
            "age_hours": self.age_hours,
            "timestamp": self.timestamp,
        }


@dataclass
class RiskReport:
    """Detailed risk analysis report."""

    mint: str
    overall_risk_score: float = 100.0
    risk_level: RiskLevel = RiskLevel.CRITICAL

    # Component scores
    safety_score: float = 0.0  # From rugcheck
    liquidity_score: float = 0.0
    distribution_score: float = 0.0
    social_score: float = 0.0
    age_score: float = 0.0

    # Issues
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Recommendation
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mint": self.mint,
            "overall_risk_score": self.overall_risk_score,
            "risk_level": self.risk_level.value,
            "safety_score": self.safety_score,
            "liquidity_score": self.liquidity_score,
            "distribution_score": self.distribution_score,
            "social_score": self.social_score,
            "age_score": self.age_score,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "recommendation": self.recommendation,
        }


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(prefix: str, mint: str) -> str:
    """Generate cache key for a token."""
    return f"{prefix}_{mint[:16]}"


def _cache_path(key: str) -> Path:
    """Get cache file path."""
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str, ttl_seconds: int) -> Optional[Dict[str, Any]]:
    """Read from cache if valid."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > ttl_seconds:
            return None
        return data.get("payload")
    except (json.JSONDecodeError, IOError):
        return None


def _write_cache(key: str, payload: Any) -> None:
    """Write to cache."""
    _ensure_cache_dir()
    path = _cache_path(key)
    path.write_text(json.dumps({
        "cached_at": time.time(),
        "payload": payload,
    }, indent=2))


def clear_cache(prefix: Optional[str] = None) -> int:
    """Clear cache files.

    Args:
        prefix: Optional prefix to filter (e.g., "rugcheck", "market")

    Returns:
        Number of files deleted
    """
    count = 0
    if not CACHE_DIR.exists():
        return count

    pattern = f"{prefix}_*.json" if prefix else "*.json"
    for f in CACHE_DIR.glob(pattern):
        try:
            f.unlink()
            count += 1
        except Exception:
            pass
    return count


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    if not CACHE_DIR.exists():
        return {"total_files": 0, "total_size_kb": 0, "categories": {}}

    stats: Dict[str, int] = {}
    total_size = 0

    for f in CACHE_DIR.glob("*.json"):
        total_size += f.stat().st_size
        prefix = f.stem.split("_")[0] if "_" in f.stem else "other"
        stats[prefix] = stats.get(prefix, 0) + 1

    return {
        "total_files": sum(stats.values()),
        "total_size_kb": round(total_size / 1024, 2),
        "categories": stats,
    }


class TokenScreener:
    """
    Multi-factor token screener.

    Aggregates data from multiple sources and provides:
    - Risk scoring
    - Token filtering by criteria
    - Token ranking by opportunity
    """

    def __init__(
        self,
        weights: Optional[RiskWeights] = None,
        chain: str = "solana",
    ):
        """Initialize screener.

        Args:
            weights: Custom risk weights
            chain: Blockchain to screen (default: solana)
        """
        self.weights = weights or RiskWeights()
        self.chain = chain

        if not self.weights.validate():
            logger.warning("Risk weights do not sum to 1.0, using defaults")
            self.weights = RiskWeights()

    def fetch_rugcheck_data(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> RugcheckData:
        """Fetch rugcheck safety data.

        Args:
            mint: Token mint address
            use_cache: Whether to use cached data

        Returns:
            RugcheckData with safety information
        """
        cache_key = _cache_key("rugcheck", mint)

        if use_cache:
            cached = _read_cache(cache_key, CACHE_TTL_RUGCHECK)
            if cached:
                return RugcheckData(**cached)

        result = RugcheckData()

        try:
            from core import rugcheck

            report = rugcheck.fetch_report(mint, cache_ttl_seconds=0)
            if not report:
                result.issues.append("fetch_failed")
                return result

            # Evaluate safety
            safety = rugcheck.evaluate_safety(report)
            lock_stats = rugcheck.best_lock_stats(report)

            result.is_safe = safety.get("ok", False)
            result.issues = safety.get("issues", [])
            result.lp_locked_pct = lock_stats.get("best_lp_locked_pct", 0.0)
            result.lp_locked_usd = lock_stats.get("best_lp_locked_usd", 0.0)
            result.mint_authority_active = bool(safety.get("details", {}).get("mint_authority"))
            result.freeze_authority_active = bool(safety.get("details", {}).get("freeze_authority"))
            result.is_rugged = report.get("rugged", False)
            result.transfer_fee_bps = safety.get("details", {}).get("transfer_fee_bps", 0.0)

            # Calculate risk score (0-100)
            risk = 0.0
            if result.is_rugged:
                risk = 100.0
            else:
                if result.mint_authority_active:
                    risk += 25.0
                if result.freeze_authority_active:
                    risk += 20.0
                if result.lp_locked_pct < 50:
                    risk += 30.0
                elif result.lp_locked_pct < 80:
                    risk += 15.0
                if result.transfer_fee_bps > 100:
                    risk += 15.0
                if "non_spl_program" in result.issues:
                    risk += 10.0

            result.risk_score = min(100.0, risk)

            # Cache result
            if use_cache:
                _write_cache(cache_key, result.to_dict())

        except ImportError:
            logger.warning("rugcheck module not available")
            result.issues.append("module_unavailable")
        except Exception as e:
            logger.warning(f"Rugcheck fetch failed for {mint}: {e}")
            result.issues.append(f"error: {str(e)[:50]}")

        return result

    def fetch_market_data(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> MarketData:
        """Fetch market data from multiple sources.

        Args:
            mint: Token mint address
            use_cache: Whether to use cached data

        Returns:
            MarketData with price, volume, liquidity
        """
        cache_key = _cache_key("market", mint)

        if use_cache:
            cached = _read_cache(cache_key, CACHE_TTL_MARKET)
            if cached:
                return MarketData(**cached)

        result = MarketData()

        # Try DexScreener first
        try:
            from core import dexscreener

            ds_result = dexscreener.get_pairs_by_token(mint)
            if ds_result.success and ds_result.data:
                pairs = ds_result.data.get("pairs", [])
                if pairs:
                    pair = pairs[0]
                    result.price_usd = float(pair.get("priceUsd", 0) or 0)
                    result.price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
                    result.price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
                    result.volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
                    result.volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
                    result.liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    result.market_cap = float(pair.get("marketCap", 0) or 0)
                    result.fdv = float(pair.get("fdv", 0) or 0)
                    result.txns_24h = int(pair.get("txns", {}).get("h24", {}).get("total", 0) or 0)
                    result.buys_24h = int(pair.get("txns", {}).get("h24", {}).get("buys", 0) or 0)
                    result.sells_24h = int(pair.get("txns", {}).get("h24", {}).get("sells", 0) or 0)
                    result.source = "dexscreener"

                    if use_cache:
                        _write_cache(cache_key, result.to_dict())
                    return result
        except ImportError:
            logger.debug("dexscreener module not available")
        except Exception as e:
            logger.debug(f"DexScreener fetch failed: {e}")

        # Fallback to DexTools
        try:
            from core import dextools

            dt_result = dextools.get_token_info(mint, chain=self.chain)
            if dt_result.success and dt_result.data:
                token = dt_result.data
                result.price_usd = token.price_usd
                result.price_change_24h = token.price_change_24h
                result.volume_24h = token.volume_24h
                result.liquidity_usd = token.liquidity_usd
                result.market_cap = token.market_cap
                result.fdv = token.fdv
                result.source = "dextools"

                if use_cache:
                    _write_cache(cache_key, result.to_dict())
                return result
        except ImportError:
            logger.debug("dextools module not available")
        except Exception as e:
            logger.debug(f"DexTools fetch failed: {e}")

        # Fallback to BirdEye
        try:
            from core import birdeye

            if birdeye.has_api_key():
                be_result = birdeye.fetch_token_price_safe(mint, chain=self.chain)
                if be_result.success and be_result.data:
                    price_data = be_result.data.get("data", {})
                    result.price_usd = float(price_data.get("value", 0) or 0)
                    result.source = "birdeye"

                    if use_cache:
                        _write_cache(cache_key, result.to_dict())
        except ImportError:
            logger.debug("birdeye module not available")
        except Exception as e:
            logger.debug(f"BirdEye fetch failed: {e}")

        return result

    def fetch_social_metrics(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> SocialMetrics:
        """Fetch social presence metrics.

        Args:
            mint: Token mint address
            use_cache: Whether to use cached data

        Returns:
            SocialMetrics with social presence info
        """
        cache_key = _cache_key("social", mint)

        if use_cache:
            cached = _read_cache(cache_key, CACHE_TTL_SOCIAL)
            if cached:
                return SocialMetrics(**cached)

        result = SocialMetrics()

        # Try DexTools for social links
        try:
            from core import dextools

            dt_result = dextools.get_token_info(mint, chain=self.chain)
            if dt_result.success and dt_result.data:
                socials = dt_result.data.socials or {}

                if socials.get("twitter"):
                    result.has_twitter = True
                    result.twitter_url = socials["twitter"]

                if socials.get("telegram"):
                    result.has_telegram = True
                    result.telegram_url = socials["telegram"]

                if socials.get("website"):
                    result.has_website = True
                    result.website_url = socials["website"]

                if socials.get("discord"):
                    result.has_discord = True
                    result.discord_url = socials["discord"]
        except Exception as e:
            logger.debug(f"Social fetch from DexTools failed: {e}")

        # Calculate social score
        score = 0.0
        if result.has_twitter:
            score += 30.0
            if result.twitter_followers > 1000:
                score += 10.0
            if result.twitter_followers > 10000:
                score += 10.0
        if result.has_telegram:
            score += 20.0
            if result.telegram_members > 500:
                score += 10.0
        if result.has_website:
            score += 15.0
        if result.has_discord:
            score += 5.0

        result.social_score = min(100.0, score)

        if use_cache:
            _write_cache(cache_key, result.to_dict())

        return result

    def fetch_holder_data(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> HolderData:
        """Fetch holder distribution data.

        Args:
            mint: Token mint address
            use_cache: Whether to use cached data

        Returns:
            HolderData with distribution info
        """
        cache_key = _cache_key("holders", mint)

        if use_cache:
            cached = _read_cache(cache_key, CACHE_TTL_MARKET)
            if cached:
                return HolderData(**cached)

        result = HolderData()

        # Try Helius for holder data
        try:
            from core import helius

            holders = helius.get_token_holders(mint, limit=20)
            if holders:
                result.total_holders = len(holders)

                # Calculate top holder concentration
                total_supply = sum(h.get("amount", 0) for h in holders)
                if total_supply > 0 and holders:
                    top_holder_amount = holders[0].get("amount", 0)
                    result.top_holder_pct = (top_holder_amount / total_supply) * 100

                    top_10_amount = sum(h.get("amount", 0) for h in holders[:10])
                    result.top_10_holders_pct = (top_10_amount / total_supply) * 100
        except ImportError:
            logger.debug("helius module not available")
        except Exception as e:
            logger.debug(f"Helius holder fetch failed: {e}")

        # Calculate distribution score (0-100, higher = better distribution)
        score = 100.0
        if result.top_holder_pct > 50:
            score -= 40.0
        elif result.top_holder_pct > 25:
            score -= 20.0
        elif result.top_holder_pct > 10:
            score -= 10.0

        if result.top_10_holders_pct > 80:
            score -= 30.0
        elif result.top_10_holders_pct > 60:
            score -= 15.0

        if result.total_holders < 50:
            score -= 20.0
        elif result.total_holders < 100:
            score -= 10.0

        result.distribution_score = max(0.0, score)

        if use_cache:
            _write_cache(cache_key, result.to_dict())

        return result

    def calculate_risk_score(
        self,
        rugcheck: RugcheckData,
        market: MarketData,
        social: SocialMetrics,
        holders: HolderData,
        age_hours: float = 0.0,
    ) -> Tuple[float, RiskLevel]:
        """Calculate composite risk score.

        Args:
            rugcheck: Rugcheck safety data
            market: Market data
            social: Social metrics
            holders: Holder data
            age_hours: Token age in hours

        Returns:
            Tuple of (risk_score, risk_level)
        """
        # Component scores (0-100, higher = worse for risk)
        safety_risk = rugcheck.risk_score

        # Liquidity risk (0-100)
        if market.liquidity_usd > 100_000:
            liquidity_risk = 10.0
        elif market.liquidity_usd > 50_000:
            liquidity_risk = 25.0
        elif market.liquidity_usd > 10_000:
            liquidity_risk = 50.0
        else:
            liquidity_risk = 80.0

        # Distribution risk (inverse of distribution score)
        distribution_risk = 100.0 - holders.distribution_score

        # Social risk (inverse of social score)
        social_risk = 100.0 - social.social_score

        # Age risk (newer = riskier)
        if age_hours > 168:  # > 1 week
            age_risk = 10.0
        elif age_hours > 24:  # > 1 day
            age_risk = 30.0
        elif age_hours > 6:
            age_risk = 50.0
        else:
            age_risk = 80.0

        # Volume stability risk
        if market.volume_24h > 0 and market.liquidity_usd > 0:
            vol_to_liq = market.volume_24h / market.liquidity_usd
            if vol_to_liq > 5:  # Very high turnover
                volume_risk = 60.0
            elif vol_to_liq > 2:
                volume_risk = 30.0
            else:
                volume_risk = 10.0
        else:
            volume_risk = 50.0

        # Calculate weighted risk
        risk_score = (
            safety_risk * self.weights.rugcheck_safety +
            (100.0 - rugcheck.lp_locked_pct) * self.weights.liquidity_lock +
            distribution_risk * self.weights.holder_distribution +
            liquidity_risk * self.weights.liquidity_depth +
            volume_risk * self.weights.volume_stability +
            social_risk * self.weights.social_presence +
            age_risk * self.weights.token_age
        )

        risk_score = min(100.0, max(0.0, risk_score))

        # Determine risk level
        if risk_score >= 80:
            level = RiskLevel.CRITICAL
        elif risk_score >= 60:
            level = RiskLevel.HIGH
        elif risk_score >= 40:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return risk_score, level

    def calculate_opportunity_score(
        self,
        risk_score: float,
        market: MarketData,
        social: SocialMetrics,
    ) -> float:
        """Calculate opportunity score.

        Args:
            risk_score: Composite risk score
            market: Market data
            social: Social metrics

        Returns:
            Opportunity score (0-100, higher = better)
        """
        # Start with inverse of risk
        base_score = 100.0 - risk_score

        # Bonus for momentum
        if market.price_change_24h > 20:
            base_score += 10.0
        elif market.price_change_24h > 10:
            base_score += 5.0
        elif market.price_change_24h < -20:
            base_score -= 10.0

        # Bonus for volume
        if market.volume_24h > 1_000_000:
            base_score += 10.0
        elif market.volume_24h > 100_000:
            base_score += 5.0

        # Bonus for social presence
        if social.social_score > 80:
            base_score += 10.0
        elif social.social_score > 50:
            base_score += 5.0

        # Bonus for buy/sell ratio
        if market.buys_24h > 0 and market.sells_24h > 0:
            ratio = market.buys_24h / market.sells_24h
            if ratio > 1.5:
                base_score += 10.0
            elif ratio > 1.2:
                base_score += 5.0
            elif ratio < 0.5:
                base_score -= 10.0

        return min(100.0, max(0.0, base_score))

    def check_criteria(
        self,
        result: ScreeningResult,
        criteria: ScreeningCriteria,
    ) -> Tuple[bool, List[str]]:
        """Check if token passes screening criteria.

        Args:
            result: Screening result to check
            criteria: Criteria to apply

        Returns:
            Tuple of (passed, failed_reasons)
        """
        failed: List[str] = []

        market = result.market or MarketData()
        rugcheck = result.rugcheck or RugcheckData()
        social = result.social or SocialMetrics()
        holders = result.holders or HolderData()

        # Market cap checks
        if market.market_cap > 0:
            if market.market_cap < criteria.min_market_cap:
                failed.append(f"market_cap_too_low: {market.market_cap:.0f} < {criteria.min_market_cap:.0f}")
            if market.market_cap > criteria.max_market_cap:
                failed.append(f"market_cap_too_high: {market.market_cap:.0f} > {criteria.max_market_cap:.0f}")

        # Liquidity checks
        if market.liquidity_usd < criteria.min_liquidity:
            failed.append(f"liquidity_too_low: {market.liquidity_usd:.0f} < {criteria.min_liquidity:.0f}")
        if market.liquidity_usd > criteria.max_liquidity:
            failed.append(f"liquidity_too_high: {market.liquidity_usd:.0f} > {criteria.max_liquidity:.0f}")

        # Volume checks
        if market.volume_24h < criteria.min_volume_24h:
            failed.append(f"volume_too_low: {market.volume_24h:.0f} < {criteria.min_volume_24h:.0f}")
        if market.volume_24h > criteria.max_volume_24h:
            failed.append(f"volume_too_high: {market.volume_24h:.0f} > {criteria.max_volume_24h:.0f}")

        # Age checks
        if result.age_hours > 0:
            if result.age_hours < criteria.min_age_hours:
                failed.append(f"too_young: {result.age_hours:.1f}h < {criteria.min_age_hours:.1f}h")
            if result.age_hours > criteria.max_age_hours:
                failed.append(f"too_old: {result.age_hours:.1f}h > {criteria.max_age_hours:.1f}h")

        # Holder checks
        if holders.total_holders < criteria.min_holders:
            failed.append(f"too_few_holders: {holders.total_holders} < {criteria.min_holders}")
        if holders.top_holder_pct > criteria.max_top_holder_pct:
            failed.append(f"top_holder_too_concentrated: {holders.top_holder_pct:.1f}% > {criteria.max_top_holder_pct:.1f}%")

        # Risk score check
        if result.risk_score > criteria.max_risk_score:
            failed.append(f"risk_too_high: {result.risk_score:.1f} > {criteria.max_risk_score:.1f}")

        # Rugcheck requirements
        if criteria.require_locked_liquidity:
            if rugcheck.lp_locked_pct < criteria.min_locked_liquidity_pct:
                failed.append(f"insufficient_lock: {rugcheck.lp_locked_pct:.1f}% < {criteria.min_locked_liquidity_pct:.1f}%")

        if criteria.require_authorities_revoked:
            if rugcheck.mint_authority_active:
                failed.append("mint_authority_active")
            if rugcheck.freeze_authority_active:
                failed.append("freeze_authority_active")

        if rugcheck.is_rugged:
            failed.append("token_rugged")

        # Social requirements
        if criteria.require_twitter and not social.has_twitter:
            failed.append("no_twitter")
        if criteria.require_telegram and not social.has_telegram:
            failed.append("no_telegram")
        if criteria.require_website and not social.has_website:
            failed.append("no_website")

        return len(failed) == 0, failed

    def screen_token(
        self,
        mint: str,
        criteria: Optional[ScreeningCriteria] = None,
        use_cache: bool = True,
    ) -> ScreeningResult:
        """Screen a single token.

        Args:
            mint: Token mint address
            criteria: Optional screening criteria
            use_cache: Whether to use cached data

        Returns:
            ScreeningResult with all data
        """
        criteria = criteria or ScreeningCriteria()

        # Check for cached full result
        cache_key = _cache_key("screening", mint)
        if use_cache:
            cached = _read_cache(cache_key, CACHE_TTL_SCREENING)
            if cached:
                result = ScreeningResult(mint=cached.get("mint", mint))
                result.symbol = cached.get("symbol", "")
                result.name = cached.get("name", "")
                if cached.get("rugcheck"):
                    result.rugcheck = RugcheckData(**cached["rugcheck"])
                if cached.get("market"):
                    result.market = MarketData(**cached["market"])
                if cached.get("social"):
                    result.social = SocialMetrics(**cached["social"])
                if cached.get("holders"):
                    result.holders = HolderData(**cached["holders"])
                result.risk_score = cached.get("risk_score", 100.0)
                result.risk_level = RiskLevel(cached.get("risk_level", "critical"))
                result.opportunity_score = cached.get("opportunity_score", 0.0)
                result.age_hours = cached.get("age_hours", 0.0)
                result.timestamp = cached.get("timestamp", time.time())

                # Re-check criteria (might have changed)
                passed, failed = self.check_criteria(result, criteria)
                result.passed_criteria = passed
                result.failed_reasons = failed

                return result

        # Fetch all data
        rugcheck = self.fetch_rugcheck_data(mint, use_cache)
        market = self.fetch_market_data(mint, use_cache)
        social = self.fetch_social_metrics(mint, use_cache)
        holders = self.fetch_holder_data(mint, use_cache)

        # Create result
        result = ScreeningResult(mint=mint)
        result.rugcheck = rugcheck
        result.market = market
        result.social = social
        result.holders = holders

        # Try to get symbol/name from market data source
        try:
            from core import dexscreener
            ds_result = dexscreener.get_pairs_by_token(mint)
            if ds_result.success and ds_result.data:
                pairs = ds_result.data.get("pairs", [])
                if pairs:
                    base = pairs[0].get("baseToken", {})
                    result.symbol = base.get("symbol", "")
                    result.name = base.get("name", "")
        except Exception:
            pass

        # Calculate scores
        result.risk_score, result.risk_level = self.calculate_risk_score(
            rugcheck, market, social, holders, result.age_hours
        )
        result.opportunity_score = self.calculate_opportunity_score(
            result.risk_score, market, social
        )

        # Check criteria
        passed, failed = self.check_criteria(result, criteria)
        result.passed_criteria = passed
        result.failed_reasons = failed

        # Cache result
        if use_cache:
            _write_cache(cache_key, result.to_dict())

        return result

    def screen_tokens(
        self,
        mints: List[str],
        criteria: Optional[ScreeningCriteria] = None,
        use_cache: bool = True,
    ) -> List[ScreeningResult]:
        """Screen multiple tokens.

        Args:
            mints: List of token mint addresses
            criteria: Optional screening criteria
            use_cache: Whether to use cached data

        Returns:
            List of ScreeningResults
        """
        results = []
        for mint in mints:
            try:
                result = self.screen_token(mint, criteria, use_cache)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to screen {mint}: {e}")
                results.append(ScreeningResult(
                    mint=mint,
                    failed_reasons=[f"screening_error: {str(e)[:50]}"]
                ))
        return results

    def rank_tokens(
        self,
        results: List[ScreeningResult],
        by: str = "opportunity",
        passed_only: bool = True,
        limit: int = 10,
    ) -> List[ScreeningResult]:
        """Rank tokens by score.

        Args:
            results: List of screening results
            by: Ranking method ("opportunity", "risk", "volume", "liquidity")
            passed_only: Only include tokens that passed criteria
            limit: Maximum results to return

        Returns:
            Sorted list of ScreeningResults
        """
        if passed_only:
            filtered = [r for r in results if r.passed_criteria]
        else:
            filtered = results

        if by == "opportunity":
            sorted_results = sorted(filtered, key=lambda r: r.opportunity_score, reverse=True)
        elif by == "risk":
            sorted_results = sorted(filtered, key=lambda r: r.risk_score)  # Lower = better
        elif by == "volume":
            sorted_results = sorted(
                filtered,
                key=lambda r: r.market.volume_24h if r.market else 0,
                reverse=True
            )
        elif by == "liquidity":
            sorted_results = sorted(
                filtered,
                key=lambda r: r.market.liquidity_usd if r.market else 0,
                reverse=True
            )
        else:
            sorted_results = filtered

        return sorted_results[:limit]

    def generate_risk_report(
        self,
        mint: str,
        use_cache: bool = True,
    ) -> RiskReport:
        """Generate detailed risk report.

        Args:
            mint: Token mint address
            use_cache: Whether to use cached data

        Returns:
            RiskReport with detailed analysis
        """
        result = self.screen_token(mint, use_cache=use_cache)

        report = RiskReport(mint=mint)
        report.overall_risk_score = result.risk_score
        report.risk_level = result.risk_level

        # Component scores
        rugcheck = result.rugcheck or RugcheckData()
        market = result.market or MarketData()
        social = result.social or SocialMetrics()
        holders = result.holders or HolderData()

        report.safety_score = 100.0 - rugcheck.risk_score
        report.liquidity_score = min(100.0, (market.liquidity_usd / 100_000) * 100)
        report.distribution_score = holders.distribution_score
        report.social_score = social.social_score
        report.age_score = min(100.0, (result.age_hours / 168) * 100)  # 1 week = 100%

        # Identify issues
        if rugcheck.is_rugged:
            report.critical_issues.append("Token has been flagged as rugged")
        if rugcheck.mint_authority_active:
            report.critical_issues.append("Mint authority is still active")
        if rugcheck.freeze_authority_active:
            report.warnings.append("Freeze authority is still active")
        if rugcheck.lp_locked_pct < 50:
            report.critical_issues.append(f"Only {rugcheck.lp_locked_pct:.1f}% liquidity locked")
        if rugcheck.transfer_fee_bps > 100:
            report.warnings.append(f"Transfer fee of {rugcheck.transfer_fee_bps:.0f} bps detected")
        if holders.top_holder_pct > 50:
            report.critical_issues.append(f"Top holder owns {holders.top_holder_pct:.1f}%")
        if market.liquidity_usd < 10_000:
            report.warnings.append(f"Low liquidity: ${market.liquidity_usd:.0f}")
        if not social.has_twitter:
            report.warnings.append("No Twitter presence")

        # Generate recommendation
        if report.critical_issues:
            report.recommendation = "AVOID - Critical issues detected"
        elif result.risk_level == RiskLevel.HIGH:
            report.recommendation = "CAUTION - High risk, proceed carefully"
        elif result.risk_level == RiskLevel.MEDIUM:
            report.recommendation = "MODERATE - Some risk factors present"
        else:
            report.recommendation = "ACCEPTABLE - Low risk profile"

        return report

    def get_top_recommendations(
        self,
        mints: List[str],
        criteria: Optional[ScreeningCriteria] = None,
        limit: int = 5,
    ) -> List[ScreeningResult]:
        """Get top recommended tokens.

        Args:
            mints: List of token mints to screen
            criteria: Screening criteria
            limit: Number of recommendations

        Returns:
            Top ranked tokens by opportunity score
        """
        results = self.screen_tokens(mints, criteria)
        return self.rank_tokens(results, by="opportunity", passed_only=True, limit=limit)


# Module-level convenience functions

_screener: Optional[TokenScreener] = None


def get_screener(chain: str = "solana") -> TokenScreener:
    """Get global screener instance."""
    global _screener
    if _screener is None or _screener.chain != chain:
        _screener = TokenScreener(chain=chain)
    return _screener


def quick_screen(
    mint: str,
    criteria: Optional[ScreeningCriteria] = None,
) -> ScreeningResult:
    """Quick screen a single token."""
    return get_screener().screen_token(mint, criteria)


def batch_screen(
    mints: List[str],
    criteria: Optional[ScreeningCriteria] = None,
) -> List[ScreeningResult]:
    """Screen multiple tokens."""
    return get_screener().screen_tokens(mints, criteria)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=== Token Screener ===")
    print(f"Cache stats: {get_cache_stats()}")

    # Example usage
    screener = TokenScreener()
    criteria = ScreeningCriteria(
        min_liquidity=10_000,
        min_volume_24h=5_000,
        max_risk_score=70,
    )

    print(f"\nScreening criteria: {criteria.to_dict()}")
