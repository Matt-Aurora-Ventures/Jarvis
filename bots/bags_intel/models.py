"""Data models for Bags Intel."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class LaunchQuality(Enum):
    """Classification of launch quality based on metrics."""
    EXCEPTIONAL = "exceptional"  # Top 10% metrics
    STRONG = "strong"  # Above average
    AVERAGE = "average"  # Meets baseline
    WEAK = "weak"  # Below average
    POOR = "poor"  # Red flags present


class RiskLevel(Enum):
    """Risk assessment for the token."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class TokenMetadata:
    """Basic token information."""
    mint_address: str
    name: str
    symbol: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None


@dataclass
class CreatorProfile:
    """Information about the token creator."""
    wallet_address: str
    twitter_handle: Optional[str] = None
    twitter_followers: Optional[int] = None
    twitter_account_age_days: Optional[int] = None
    previous_launches: int = 0
    rugged_launches: int = 0


@dataclass
class BondingMetrics:
    """Metrics from the bonding curve phase."""
    duration_seconds: int
    total_volume_sol: float
    unique_buyers: int
    unique_sellers: int
    buy_sell_ratio: float
    graduation_mcap_usd: float


@dataclass
class MarketMetrics:
    """Current market data."""
    price_usd: float
    price_sol: float
    market_cap_usd: float
    liquidity_usd: float
    volume_24h_usd: float
    price_change_1h: float
    buys_1h: int
    sells_1h: int
    holder_count: int = 0
    top_10_holder_pct: float = 0.0


@dataclass
class IntelScore:
    """Composite intelligence score."""
    overall_score: float  # 0-100
    launch_quality: LaunchQuality
    risk_level: RiskLevel

    # Component scores
    bonding_score: float
    creator_score: float
    social_score: float
    market_score: float
    distribution_score: float

    # Flags
    green_flags: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # AI analysis
    grok_summary: Optional[str] = None


@dataclass
class GraduationEvent:
    """A token graduation (bonding out) event."""
    token: TokenMetadata
    creator: CreatorProfile
    bonding: BondingMetrics
    market: MarketMetrics
    score: IntelScore
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tx_signature: Optional[str] = None

    @property
    def is_reportable(self) -> bool:
        """Check if meets reporting thresholds."""
        return self.market.market_cap_usd >= 10000 and self.score.overall_score >= 30

    def to_telegram_html(self) -> str:
        """Format for Telegram notification."""
        s = self.score

        quality_emoji = {
            LaunchQuality.EXCEPTIONAL: "🌟",
            LaunchQuality.STRONG: "✅",
            LaunchQuality.AVERAGE: "➖",
            LaunchQuality.WEAK: "⚠️",
            LaunchQuality.POOR: "🚨",
        }.get(s.launch_quality, "❓")

        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.EXTREME: "🔴",
        }.get(s.risk_level, "⚪")

        lines = [
            f"<b>🎯 BAGS.FM INTEL REPORT</b>",
            f"",
            f"<b>{self.token.symbol}</b> - {self.token.name}",
            f"<code>{self.token.mint_address}</code>",
            f"",
            f"<b>📊 Score:</b> {s.overall_score:.0f}/100 {quality_emoji}",
            f"<b>⚡ Risk:</b> {s.risk_level.value.upper()} {risk_emoji}",
            f"",
            f"<b>💰 Market</b>",
            f"• MCap: ${self.market.market_cap_usd:,.0f}",
            f"• Liq: ${self.market.liquidity_usd:,.0f}",
            f"• Price: ${self.market.price_usd:.8f}",
            f"",
            f"<b>📈 Bonding Curve</b>",
            f"• Duration: {self.bonding.duration_seconds // 60}m",
            f"• Volume: {self.bonding.total_volume_sol:.1f} SOL",
            f"• Buyers: {self.bonding.unique_buyers}",
            f"• Buy/Sell: {self.bonding.buy_sell_ratio:.1f}x",
            f"",
            f"<b>👤 Creator</b>",
        ]

        if self.creator.twitter_handle:
            lines.append(f"• Twitter: @{self.creator.twitter_handle}")
            if self.creator.twitter_followers:
                lines.append(f"• Followers: {self.creator.twitter_followers:,}")

        lines.extend([
            f"",
            f"<b>🎯 Scores</b>",
            f"• Bonding: {s.bonding_score:.0f}",
            f"• Creator: {s.creator_score:.0f}",
            f"• Social: {s.social_score:.0f}",
            f"• Market: {s.market_score:.0f}",
            f"• Distribution: {s.distribution_score:.0f}",
        ])

        if s.green_flags:
            lines.append(f"")
            lines.append(f"<b>✅ Green Flags</b>")
            for flag in s.green_flags[:4]:
                lines.append(f"• {flag}")

        if s.red_flags:
            lines.append(f"")
            lines.append(f"<b>🚨 Red Flags</b>")
            for flag in s.red_flags[:4]:
                lines.append(f"• {flag}")

        if s.grok_summary:
            lines.extend([f"", f"<b>🤖 AI Analysis</b>", s.grok_summary[:400]])

        lines.extend([
            f"",
            f"<a href='https://bags.fm/token/{self.token.mint_address}'>Bags</a> | "
            f"<a href='https://dexscreener.com/solana/{self.token.mint_address}'>DexScreener</a>",
        ])

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/storage."""
        return {
            "type": "bags_intel_report",
            "timestamp": self.timestamp.isoformat(),
            "token": {
                "mint": self.token.mint_address,
                "name": self.token.name,
                "symbol": self.token.symbol,
                "twitter": self.token.twitter,
                "website": self.token.website,
            },
            "scores": {
                "overall": self.score.overall_score,
                "quality": self.score.launch_quality.value,
                "risk": self.score.risk_level.value,
                "bonding": self.score.bonding_score,
                "creator": self.score.creator_score,
                "social": self.score.social_score,
                "market": self.score.market_score,
                "distribution": self.score.distribution_score,
            },
            "market": {
                "mcap_usd": self.market.market_cap_usd,
                "liquidity_usd": self.market.liquidity_usd,
                "price_usd": self.market.price_usd,
            },
            "bonding_curve": {
                "duration_seconds": self.bonding.duration_seconds,
                "volume_sol": self.bonding.total_volume_sol,
                "unique_buyers": self.bonding.unique_buyers,
                "buy_sell_ratio": self.bonding.buy_sell_ratio,
            },
            "creator": {
                "wallet": self.creator.wallet_address,
                "twitter": self.creator.twitter_handle,
            },
            "flags": {
                "green": self.score.green_flags,
                "red": self.score.red_flags,
                "warnings": self.score.warnings,
            },
            "ai_analysis": {"summary": self.score.grok_summary},
        }
