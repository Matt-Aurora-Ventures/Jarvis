"""Intelligence scoring for bags.fm token launches."""

import logging
from typing import Optional
import aiohttp

from .models import (
    TokenMetadata,
    CreatorProfile,
    BondingMetrics,
    MarketMetrics,
    IntelScore,
    LaunchQuality,
    RiskLevel,
)

logger = logging.getLogger("jarvis.bags_intel.scorer")

# Scoring thresholds
THRESHOLDS = {
    "bonding_duration_optimal_min": 300,  # 5 min
    "bonding_duration_optimal_max": 3600,  # 1 hour
    "bonding_duration_sus_fast": 60,  # < 1 min suspicious
    "min_volume_sol": 10,
    "optimal_volume_sol": 50,
    "min_buyers": 20,
    "optimal_buyers": 100,
    "min_buy_sell_ratio": 1.5,
    "optimal_buy_sell_ratio": 3.0,
    "min_twitter_followers": 100,
    "optimal_twitter_followers": 1000,
    "min_account_age_days": 30,
    "sus_account_age_days": 7,
    "max_top10_pct": 50,
    "healthy_top10_pct": 30,
    "min_liquidity_usd": 5000,
    "optimal_liquidity_usd": 25000,
    "max_pump_1h": 100,
}


class IntelScorer:
    """Calculate intelligence scores for token launches."""

    def __init__(self, xai_api_key: Optional[str] = None):
        self.xai_api_key = xai_api_key

    async def calculate_score(
        self,
        token: TokenMetadata,
        creator: CreatorProfile,
        bonding: BondingMetrics,
        market: MarketMetrics,
    ) -> IntelScore:
        """Calculate comprehensive score."""
        red_flags = []
        green_flags = []
        warnings = []

        bonding_score = self._score_bonding(bonding, red_flags, green_flags, warnings)
        creator_score = self._score_creator(creator, token, red_flags, green_flags, warnings)
        social_score = self._score_social(token, red_flags, green_flags, warnings)
        market_score = self._score_market(market, red_flags, green_flags, warnings)
        distribution_score = self._score_distribution(market, red_flags, green_flags, warnings)

        # Weighted overall
        overall = (
            bonding_score * 0.25
            + creator_score * 0.20
            + social_score * 0.15
            + market_score * 0.25
            + distribution_score * 0.15
        )

        quality = self._determine_quality(overall)
        risk = self._determine_risk(red_flags, overall)

        # Grok analysis if available
        grok_summary = None
        if self.xai_api_key:
            grok_summary = await self._get_grok_analysis(
                token, creator, bonding, market, red_flags, green_flags
            )

        return IntelScore(
            overall_score=overall,
            launch_quality=quality,
            risk_level=risk,
            bonding_score=bonding_score,
            creator_score=creator_score,
            social_score=social_score,
            market_score=market_score,
            distribution_score=distribution_score,
            red_flags=red_flags,
            green_flags=green_flags,
            warnings=warnings,
            grok_summary=grok_summary,
        )

    def _score_bonding(self, b: BondingMetrics, red: list, green: list, warn: list) -> float:
        score = 50.0

        # Duration
        if b.duration_seconds < THRESHOLDS["bonding_duration_sus_fast"]:
            score -= 30
            red.append(f"Suspiciously fast graduation ({b.duration_seconds}s)")
        elif b.duration_seconds < THRESHOLDS["bonding_duration_optimal_min"]:
            score -= 15
            warn.append(f"Quick graduation ({b.duration_seconds // 60}m)")
        elif b.duration_seconds <= THRESHOLDS["bonding_duration_optimal_max"]:
            score += 20
            green.append(f"Healthy graduation time ({b.duration_seconds // 60}m)")

        # Volume
        if b.total_volume_sol >= THRESHOLDS["optimal_volume_sol"]:
            score += 20
            green.append(f"Strong volume ({b.total_volume_sol:.1f} SOL)")
        elif b.total_volume_sol >= THRESHOLDS["min_volume_sol"]:
            score += 10
        else:
            score -= 10
            warn.append(f"Low volume ({b.total_volume_sol:.1f} SOL)")

        # Buyers
        if b.unique_buyers >= THRESHOLDS["optimal_buyers"]:
            score += 15
            green.append(f"Many buyers ({b.unique_buyers})")
        elif b.unique_buyers >= THRESHOLDS["min_buyers"]:
            score += 5
        else:
            score -= 15
            red.append(f"Few buyers ({b.unique_buyers})")

        # Buy/sell ratio
        if b.buy_sell_ratio >= THRESHOLDS["optimal_buy_sell_ratio"]:
            score += 15
            green.append(f"Strong buy pressure ({b.buy_sell_ratio:.1f}x)")
        elif b.buy_sell_ratio >= THRESHOLDS["min_buy_sell_ratio"]:
            score += 5
        elif b.buy_sell_ratio < 1.0:
            score -= 20
            red.append(f"More sellers than buyers ({b.buy_sell_ratio:.1f}x)")

        return max(0, min(100, score))

    def _score_creator(
        self, c: CreatorProfile, t: TokenMetadata, red: list, green: list, warn: list
    ) -> float:
        score = 40.0

        if c.twitter_handle:
            score += 15
            green.append(f"Has Twitter (@{c.twitter_handle})")

            if c.twitter_followers:
                if c.twitter_followers >= THRESHOLDS["optimal_twitter_followers"]:
                    score += 25
                    green.append(f"Strong following ({c.twitter_followers:,})")
                elif c.twitter_followers >= THRESHOLDS["min_twitter_followers"]:
                    score += 10

            if c.twitter_account_age_days:
                if c.twitter_account_age_days >= THRESHOLDS["min_account_age_days"]:
                    score += 15
                    green.append(f"Established account ({c.twitter_account_age_days}d)")
                elif c.twitter_account_age_days < THRESHOLDS["sus_account_age_days"]:
                    score -= 25
                    red.append(f"New Twitter account ({c.twitter_account_age_days}d)")
        else:
            red.append("No Twitter linked")
            score -= 10

        if c.rugged_launches > 0:
            score -= 40
            red.append(f"Creator has {c.rugged_launches} previous rugs!")

        return max(0, min(100, score))

    def _score_social(self, t: TokenMetadata, red: list, green: list, warn: list) -> float:
        score = 50.0

        socials = sum([bool(t.twitter), bool(t.telegram), bool(t.website)])
        if socials >= 3:
            score += 20
            green.append(f"{socials} socials linked")
        elif socials >= 2:
            score += 10
        elif socials == 0:
            score -= 20
            red.append("No socials linked")

        if t.website:
            score += 10
            green.append("Has website")

        return max(0, min(100, score))

    def _score_market(self, m: MarketMetrics, red: list, green: list, warn: list) -> float:
        score = 50.0

        if m.liquidity_usd >= THRESHOLDS["optimal_liquidity_usd"]:
            score += 25
            green.append(f"Strong liquidity (${m.liquidity_usd:,.0f})")
        elif m.liquidity_usd >= THRESHOLDS["min_liquidity_usd"]:
            score += 10
        else:
            score -= 20
            red.append(f"Low liquidity (${m.liquidity_usd:,.0f})")

        if m.price_change_1h > THRESHOLDS["max_pump_1h"]:
            score -= 15
            warn.append(f"Pumping hard (+{m.price_change_1h:.0f}% 1h)")
        elif m.price_change_1h < -50:
            score -= 20
            red.append(f"Dumping ({m.price_change_1h:.0f}% 1h)")

        if m.buys_1h > 0 and m.sells_1h > 0:
            ratio = m.buys_1h / m.sells_1h
            if ratio > 2:
                score += 15
                green.append(f"Strong buy pressure ({m.buys_1h}B/{m.sells_1h}S)")
            elif ratio < 0.5:
                score -= 15
                red.append(f"Heavy selling ({m.buys_1h}B/{m.sells_1h}S)")

        return max(0, min(100, score))

    def _score_distribution(self, m: MarketMetrics, red: list, green: list, warn: list) -> float:
        score = 60.0

        if m.top_10_holder_pct > 0:
            if m.top_10_holder_pct <= THRESHOLDS["healthy_top10_pct"]:
                score += 30
                green.append(f"Well distributed (top 10: {m.top_10_holder_pct:.0f}%)")
            elif m.top_10_holder_pct <= THRESHOLDS["max_top10_pct"]:
                score += 10
                warn.append(f"Moderate concentration ({m.top_10_holder_pct:.0f}%)")
            else:
                score -= 30
                red.append(f"High concentration (top 10: {m.top_10_holder_pct:.0f}%)")

        if m.holder_count >= 500:
            score += 20
            green.append(f"Many holders ({m.holder_count})")
        elif m.holder_count >= 100:
            score += 10
        elif m.holder_count < 50 and m.holder_count > 0:
            score -= 15
            warn.append(f"Few holders ({m.holder_count})")

        return max(0, min(100, score))

    def _determine_quality(self, score: float) -> LaunchQuality:
        if score >= 80:
            return LaunchQuality.EXCEPTIONAL
        elif score >= 65:
            return LaunchQuality.STRONG
        elif score >= 50:
            return LaunchQuality.AVERAGE
        elif score >= 35:
            return LaunchQuality.WEAK
        return LaunchQuality.POOR

    def _determine_risk(self, red_flags: list, score: float) -> RiskLevel:
        has_rug = any("rug" in f.lower() for f in red_flags)
        if has_rug:
            return RiskLevel.EXTREME
        if len(red_flags) >= 4 or score < 30:
            return RiskLevel.HIGH
        if len(red_flags) >= 2 or score < 50:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    async def _get_grok_analysis(
        self,
        token: TokenMetadata,
        creator: CreatorProfile,
        bonding: BondingMetrics,
        market: MarketMetrics,
        red_flags: list,
        green_flags: list,
    ) -> Optional[str]:
        """Get Grok AI analysis."""
        try:
            prompt = f"""Analyze this new Solana token launch briefly (2-3 sentences):

Token: {token.name} ({token.symbol})
Market Cap: ${market.market_cap_usd:,.0f}
Liquidity: ${market.liquidity_usd:,.0f}
Bonding Duration: {bonding.duration_seconds // 60} min
Unique Buyers: {bonding.unique_buyers}
Creator Twitter: {'@' + creator.twitter_handle if creator.twitter_handle else 'None'}

Green Flags: {', '.join(green_flags[:3]) if green_flags else 'None'}
Red Flags: {', '.join(red_flags[:3]) if red_flags else 'None'}

Provide a concise risk assessment."""

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.xai_api_key}"},
                    json={
                        "model": "grok-4-1-fast-non-reasoning",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 150,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug(f"Grok analysis failed: {e}")
        return None
