"""
JARVIS Social Media Integration

Twitter/X bot and Telegram prediction bot for public engagement.
Includes image generation, viral optimization, and trending tracking.
"""

from .twitter_bot import (
    JarvisTwitterBot,
    TweetContent,
    TweetScheduler,
    get_twitter_bot,
)
from .twitter_compliance import (
    TwitterCompliance,
    validate_tweet_content,
)
from .twitter_content import (
    ContentGenerator,
    JarvisPersonality,
)
from .telegram_bot import (
    JarvisTelegramBot,
    UserAccount,
    get_telegram_bot,
)
from .image_generator import (
    ImageGenerator,
    ImageConfig,
)
from .viral_optimizer import (
    ViralOptimizer,
    PostingSchedule,
)
from .trending_tracker import (
    TrendingTokenTracker,
    PumpDumpDetector,
    MentionTracker,
)

__all__ = [
    # Twitter
    "JarvisTwitterBot",
    "TweetContent",
    "TweetScheduler",
    "get_twitter_bot",
    "TwitterCompliance",
    "validate_tweet_content",
    "ContentGenerator",
    "JarvisPersonality",
    # Telegram
    "JarvisTelegramBot",
    "UserAccount",
    "get_telegram_bot",
    # Image Generation
    "ImageGenerator",
    "ImageConfig",
    # Viral Optimization
    "ViralOptimizer",
    "PostingSchedule",
    # Trending Tracking
    "TrendingTokenTracker",
    "PumpDumpDetector",
    "MentionTracker",
]
