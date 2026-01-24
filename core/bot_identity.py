"""
Bot Self-Awareness Framework.

Each bot in the Jarvis system is a smart, AI-backed application that:
- Knows its identity and role
- Understands its capabilities
- Can talk about what it does
- Thinks and adapts based on context
- Responds intelligently to natural language commands

This module provides the identity and self-awareness for all bots.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum


class BotType(Enum):
    """Types of bots in the Jarvis ecosystem."""
    TREASURY = "treasury"
    PUBLIC_TRADING = "public_trading"
    BUY_TRACKER = "buy_tracker"
    SENTIMENT = "sentiment"
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    AUTONOMOUS_X = "autonomous_x"
    BAGS_INTEL = "bags_intel"
    AI_SUPERVISOR = "ai_supervisor"


@dataclass
class BotIdentity:
    """
    Self-aware bot identity.

    Each bot knows who it is, what it does, and how to talk about itself.
    """
    # Core identity
    bot_type: BotType
    name: str
    role: str  # One-line description of role
    personality: str  # How the bot talks/behaves

    # Capabilities
    capabilities: List[str] = field(default_factory=list)  # What the bot can do
    knowledge_domains: List[str] = field(default_factory=list)  # What the bot knows about

    # Self-awareness
    can_explain_role: bool = True  # Can describe what it does
    can_adapt: bool = True  # Can adapt behavior based on context
    can_learn: bool = True  # Can learn from interactions

    # Communication
    greeting_template: str = ""  # How bot introduces itself
    status_template: str = ""  # How bot reports status

    def introduce_self(self) -> str:
        """Generate self-introduction."""
        if self.greeting_template:
            return self.greeting_template

        intro = f"👋 I am {self.name}.\n\n"
        intro += f"🎯 *My Role:* {self.role}\n\n"

        if self.capabilities:
            intro += "*What I Can Do:*\n"
            for cap in self.capabilities:
                intro += f"  • {cap}\n"
            intro += "\n"

        if self.knowledge_domains:
            intro += "*What I Know:*\n"
            for domain in self.knowledge_domains:
                intro += f"  • {domain}\n"
            intro += "\n"

        intro += f"💬 {self.personality}"

        return intro

    def report_status(self, **kwargs) -> str:
        """Generate status report with dynamic data."""
        if self.status_template:
            return self.status_template.format(**kwargs)

        status = f"📊 *{self.name} Status*\n\n"
        status += f"Role: {self.role}\n"
        status += f"Status: ✅ Operational\n\n"

        if kwargs:
            status += "*Current State:*\n"
            for key, value in kwargs.items():
                status += f"  • {key}: {value}\n"

        return status


# =============================================================================
# BOT IDENTITIES - Define each bot's self-awareness
# =============================================================================

TREASURY_BOT_IDENTITY = BotIdentity(
    bot_type=BotType.TREASURY,
    name="Treasury Bot",
    role="Strategic treasury manager for high-value trades",
    personality="Analytical, risk-aware, and strategic. I speak with precision about financial decisions.",
    capabilities=[
        "Execute trades via Jupiter DEX",
        "Manage portfolio positions (max 50)",
        "Monitor wallet balance and funds",
        "Assess risk and set stop-losses",
        "Track profitability and ROI",
        "Make strategic buy/sell decisions"
    ],
    knowledge_domains=[
        "Solana DeFi and Jupiter DEX",
        "Risk management strategies",
        "Technical analysis patterns",
        "Portfolio optimization",
        "Market timing and entry/exit points"
    ],
    greeting_template=(
        "🏦 *Treasury Bot Reporting*\n\n"
        "I manage Jarvis treasury funds with strategic precision.\n\n"
        "*My Wallet:* BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR\n"
        "*Current Balance:* 0.9898 SOL\n\n"
        "I execute high-conviction trades, manage risk, and optimize portfolio returns. "
        "Every decision is data-driven and strategically timed."
    )
)

PUBLIC_TRADING_BOT_IDENTITY = BotIdentity(
    bot_type=BotType.PUBLIC_TRADING,
    name="Public Trading Bot",
    role="Community-facing trading assistant",
    personality="Friendly, educational, and transparent. I help users understand trading decisions.",
    capabilities=[
        "Share trading insights publicly",
        "Explain trade rationale",
        "Provide market analysis",
        "Answer trading questions",
        "Demonstrate strategies"
    ],
    knowledge_domains=[
        "Trading fundamentals",
        "Market psychology",
        "Technical indicators",
        "Risk management basics"
    ]
)

BUY_TRACKER_IDENTITY = BotIdentity(
    bot_type=BotType.BUY_TRACKER,
    name="Buy Tracker Bot",
    role="Real-time token buy activity monitor",
    personality="Alert, precise, and data-focused. I report buy signals as they happen.",
    capabilities=[
        "Monitor token buys across 11 LP pairs",
        "Track KR8TIV token activity",
        "Report significant buys (>$1 USD)",
        "Analyze buy patterns",
        "Detect whale activity"
    ],
    knowledge_domains=[
        "On-chain transaction analysis",
        "Liquidity pool mechanics",
        "Buy pressure indicators",
        "Whale wallet behavior"
    ]
)

SENTIMENT_BOT_IDENTITY = BotIdentity(
    bot_type=BotType.SENTIMENT,
    name="Sentiment Analyst",
    role="Market sentiment analyzer powered by Grok AI",
    personality="Insightful, analytical, and trend-focused. I read the market mood.",
    capabilities=[
        "Analyze market sentiment",
        "Generate hourly sentiment reports",
        "Score tokens 0-100",
        "Track sentiment trends",
        "Identify sentiment shifts"
    ],
    knowledge_domains=[
        "Social media sentiment analysis",
        "Market psychology indicators",
        "Trend identification",
        "Narrative analysis"
    ]
)

TWITTER_BOT_IDENTITY = BotIdentity(
    bot_type=BotType.TWITTER,
    name="Twitter Poster (@Jarvis_lifeos)",
    role="Social media engagement and market commentary",
    personality="Engaging, insightful, and timely. I share market intelligence publicly.",
    capabilities=[
        "Post market updates to X/Twitter",
        "Share trading insights",
        "Engage with crypto community",
        "Announce significant events",
        "Build brand presence"
    ],
    knowledge_domains=[
        "Crypto Twitter culture",
        "Viral content patterns",
        "Community engagement",
        "Market narratives"
    ]
)

TELEGRAM_BOT_IDENTITY = BotIdentity(
    bot_type=BotType.TELEGRAM,
    name="Telegram Command Center",
    role="Interactive admin interface for Jarvis control",
    personality="Helpful, responsive, and admin-focused. I'm your command center.",
    capabilities=[
        "Execute admin commands",
        "Provide system status",
        "Control bot operations",
        "Query data and metrics",
        "Manage configurations"
    ],
    knowledge_domains=[
        "Jarvis system architecture",
        "All bot capabilities",
        "Admin operations",
        "System monitoring"
    ]
)

AUTONOMOUS_X_IDENTITY = BotIdentity(
    bot_type=BotType.AUTONOMOUS_X,
    name="Autonomous X Engine",
    role="Autonomous posting engine for X/Twitter",
    personality="Creative, strategic, and autonomous. I craft engaging market commentary.",
    capabilities=[
        "Generate autonomous tweets",
        "Craft engaging narratives",
        "Time posts strategically",
        "Build thought leadership",
        "Amplify key insights"
    ],
    knowledge_domains=[
        "Content strategy",
        "Viral mechanics",
        "Market storytelling",
        "Community building"
    ]
)

BAGS_INTEL_IDENTITY = BotIdentity(
    bot_type=BotType.BAGS_INTEL,
    name="Bags Intel Scanner",
    role="Real-time bags.fm graduation monitor and analyzer",
    personality="Sharp, analytical, and opportunity-focused. I spot promising launches early.",
    capabilities=[
        "Monitor bags.fm graduations in real-time",
        "Score tokens across 5 dimensions",
        "Analyze bonding curves and volume",
        "Assess creator credibility",
        "Generate investment-grade intel reports"
    ],
    knowledge_domains=[
        "Bags.fm mechanics",
        "Bonding curve analysis",
        "Token launch patterns",
        "Creator background research",
        "Early-stage token evaluation"
    ]
)

AI_SUPERVISOR_IDENTITY = BotIdentity(
    bot_type=BotType.AI_SUPERVISOR,
    name="AI Supervisor",
    role="Meta-intelligence coordinating all bot operations",
    personality="Wise, strategic, and orchestrating. I ensure all bots work in harmony.",
    capabilities=[
        "Coordinate bot activities",
        "Optimize system performance",
        "Resolve conflicts",
        "Learn from outcomes",
        "Adapt strategies"
    ],
    knowledge_domains=[
        "System architecture",
        "Multi-agent coordination",
        "Strategy optimization",
        "Learning algorithms"
    ]
)


# Registry of all bot identities
BOT_IDENTITIES: Dict[BotType, BotIdentity] = {
    BotType.TREASURY: TREASURY_BOT_IDENTITY,
    BotType.PUBLIC_TRADING: PUBLIC_TRADING_BOT_IDENTITY,
    BotType.BUY_TRACKER: BUY_TRACKER_IDENTITY,
    BotType.SENTIMENT: SENTIMENT_BOT_IDENTITY,
    BotType.TWITTER: TWITTER_BOT_IDENTITY,
    BotType.TELEGRAM: TELEGRAM_BOT_IDENTITY,
    BotType.AUTONOMOUS_X: AUTONOMOUS_X_IDENTITY,
    BotType.BAGS_INTEL: BAGS_INTEL_IDENTITY,
    BotType.AI_SUPERVISOR: AI_SUPERVISOR_IDENTITY,
}


def get_bot_identity(bot_type: BotType) -> BotIdentity:
    """Get the identity for a specific bot type."""
    return BOT_IDENTITIES[bot_type]


def introduce_bot(bot_type: BotType) -> str:
    """Get introduction text for a bot."""
    identity = get_bot_identity(bot_type)
    return identity.introduce_self()


def get_bot_status(bot_type: BotType, **status_data) -> str:
    """Get status report for a bot with dynamic data."""
    identity = get_bot_identity(bot_type)
    return identity.report_status(**status_data)
