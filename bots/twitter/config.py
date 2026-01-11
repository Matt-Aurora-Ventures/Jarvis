"""
JARVIS Twitter Bot Configuration
Environment variables and settings
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TwitterConfig:
    """Twitter API configuration"""
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    bearer_token: str = ""

    @classmethod
    def from_env(cls) -> "TwitterConfig":
        return cls(
            api_key=os.getenv("TWITTER_API_KEY", ""),
            api_secret=os.getenv("TWITTER_API_SECRET", ""),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""),
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN", "")
        )

    def is_valid(self) -> bool:
        return all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret
        ])


@dataclass
class GrokConfig:
    """xAI Grok configuration"""
    api_key: str = ""
    model: str = "grok-3"
    image_model: str = "grok-2-image"
    max_images_per_day: int = 6

    @classmethod
    def from_env(cls) -> "GrokConfig":
        return cls(
            api_key=os.getenv("XAI_API_KEY", "")
        )


@dataclass
class ScheduleConfig:
    """Posting schedule configuration"""
    # 24-hour format schedule
    schedule: Dict[int, str] = field(default_factory=lambda: {
        8: "morning_report",    # 8 AM - Morning market overview
        10: "token_spotlight",  # 10 AM - Trending token spotlight
        12: "stock_picks",      # 12 PM - Stock picks from Grok
        14: "macro_update",     # 2 PM - Macro/geopolitical update
        16: "commodities",      # 4 PM - Commodities & precious metals
        18: "grok_insight",     # 6 PM - Grok wisdom/insight
        20: "evening_wrap"      # 8 PM - Evening market wrap
    })

    # Timezone offset from UTC (e.g., -5 for EST, -8 for PST)
    timezone_offset: int = 0

    # Minimum time between tweets in seconds
    min_tweet_interval: int = 1800  # 30 minutes


@dataclass
class EngagementConfig:
    """Engagement settings"""
    auto_reply: bool = True
    reply_probability: float = 0.3  # Reply to 30% of mentions
    like_mentions: bool = True
    max_replies_per_hour: int = 5
    check_interval: int = 60  # Check mentions every 60 seconds


@dataclass
class BotConfiguration:
    """Complete bot configuration"""
    twitter: TwitterConfig = field(default_factory=TwitterConfig.from_env)
    grok: GrokConfig = field(default_factory=GrokConfig.from_env)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    engagement: EngagementConfig = field(default_factory=EngagementConfig)

    @classmethod
    def load(cls) -> "BotConfiguration":
        """Load configuration from environment"""
        return cls(
            twitter=TwitterConfig.from_env(),
            grok=GrokConfig.from_env()
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration, return (valid, errors)"""
        errors = []

        if not self.twitter.is_valid():
            errors.append("Twitter credentials incomplete - check TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")

        if not self.grok.api_key:
            errors.append("XAI_API_KEY not set")

        return len(errors) == 0, errors


# Environment variable template
ENV_TEMPLATE = """
# JARVIS Twitter Bot Environment Variables
# Copy to .env file and fill in your credentials

# Twitter API (get from developer.twitter.com)
TWITTER_API_KEY=your_api_key_here
TWITTER_API_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here
TWITTER_BEARER_TOKEN=your_bearer_token_here

# xAI Grok API (get from x.ai)
XAI_API_KEY=your_xai_api_key_here
"""


def print_env_template():
    """Print the environment variable template"""
    print(ENV_TEMPLATE)


def check_config() -> bool:
    """Check if configuration is valid"""
    config = BotConfiguration.load()
    valid, errors = config.validate()

    if valid:
        print("Configuration valid")
        return True
    else:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
