"""
Viral Optimizer for Twitter/X Bot

Optimizes tweets for viral potential:
- Hashtag generation based on sentiment
- Engagement hooks (questions, calls-to-action)
- Timing optimization (best posting times)
"""

import logging
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "social" / "viral"


# Hashtag pools
CORE_CRYPTO_HASHTAGS = ["#crypto", "#defi", "#trading", "#nfa", "#dyor"]

TOKEN_HASHTAGS = {
    "SOL": ["#Solana", "#SOL"],
    "BTC": ["#Bitcoin", "#BTC"],
    "ETH": ["#Ethereum", "#ETH"],
    "WIF": ["#dogwifhat", "#WIF", "#memecoins"],
    "BONK": ["#BONK", "#memecoins"],
    "JUP": ["#Jupiter", "#JUP"],
    "RAY": ["#Raydium", "#RAY"],
}

BULLISH_HASHTAGS = ["#bullish", "#gainz", "#pump", "#ToTheMoon"]
BEARISH_HASHTAGS = ["#bearish", "#caution", "#dip"]

# Engagement hooks
QUESTION_HOOKS = [
    "thoughts?",
    "what's your take?",
    "agree or disagree?",
    "am i missing something?",
    "who's watching this?",
    "bullish or bearish?",
    "anyone else seeing this?",
    "what do you think?",
    "does this look familiar?",
    "what's your strategy here?",
]

CTA_HOOKS = [
    "follow for more alpha",
    "rt if you agree",
    "bookmark this",
    "save for later",
    "drop a comment",
    "tag a friend who needs to see this",
    "like if bullish",
]

CURIOSITY_HOOKS = [
    "here's what most miss...",
    "this is huge...",
    "pattern alert",
    "signal detected",
    "interesting development",
    "you won't believe this",
    "major update",
    "breaking pattern",
]


@dataclass
class PostingSchedule:
    """Configuration for optimal posting times."""

    audience: str = "crypto"
    timezone_str: str = "UTC"

    # Peak hours by audience type (UTC)
    peak_hours_crypto: List[int] = field(default_factory=lambda: [
        9, 10,    # EU market open
        13, 14, 15, 16,  # US market hours
        20, 21,   # Evening engagement
    ])

    peak_hours_general: List[int] = field(default_factory=lambda: [
        8, 9, 10,
        12, 13,
        17, 18, 19, 20,
    ])

    # Days with higher engagement (0=Monday, 6=Sunday)
    best_days: List[int] = field(default_factory=lambda: [1, 2, 3, 4])  # Tue-Fri

    def get_peak_hours(self) -> List[int]:
        """Get peak hours for the audience type."""
        if self.audience == "crypto":
            return self.peak_hours_crypto
        return self.peak_hours_general


class ViralOptimizer:
    """
    Optimizes tweet content for viral potential.

    Usage:
        optimizer = ViralOptimizer()
        hashtags = optimizer.generate_hashtags({"overall": 0.7, "category": "bullish"})
        optimized = optimizer.optimize_tweet("sol looking good", sentiment_data)
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        timezone: str = "UTC"
    ):
        """
        Initialize viral optimizer.

        Args:
            data_dir: Directory for storing optimization data
            timezone: Timezone for posting schedule
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.timezone = timezone
        self.schedule = PostingSchedule()

        # Track used hooks for variety
        self._recent_hooks: List[str] = []

    def generate_hashtags(
        self,
        sentiment_data: Dict[str, Any],
        max_hashtags: int = 5
    ) -> List[str]:
        """
        Generate hashtags based on sentiment data.

        Args:
            sentiment_data: Dict with overall sentiment, category, top_token
            max_hashtags: Maximum number of hashtags to return

        Returns:
            List of hashtag strings
        """
        hashtags = []

        # Get category-specific hashtags
        category = sentiment_data.get("category", "neutral")
        if category == "bullish":
            hashtags.extend(random.sample(BULLISH_HASHTAGS, min(2, len(BULLISH_HASHTAGS))))
        elif category == "bearish":
            hashtags.extend(random.sample(BEARISH_HASHTAGS, min(2, len(BEARISH_HASHTAGS))))

        # Add token-specific hashtags
        top_token = sentiment_data.get("top_token", "")
        if top_token and top_token.upper() in TOKEN_HASHTAGS:
            token_tags = TOKEN_HASHTAGS[top_token.upper()]
            hashtags.extend(random.sample(token_tags, min(1, len(token_tags))))

        # Add core crypto hashtags
        core_tags = random.sample(CORE_CRYPTO_HASHTAGS, min(2, len(CORE_CRYPTO_HASHTAGS)))
        hashtags.extend(core_tags)

        # Remove duplicates while preserving order
        seen = set()
        unique_hashtags = []
        for h in hashtags:
            h_lower = h.lower()
            if h_lower not in seen:
                seen.add(h_lower)
                unique_hashtags.append(h)

        return unique_hashtags[:max_hashtags]

    def generate_token_hashtags(
        self,
        tokens: List[str],
        max_hashtags: int = 5
    ) -> List[str]:
        """
        Generate hashtags for specific tokens.

        Args:
            tokens: List of token symbols
            max_hashtags: Maximum number of hashtags

        Returns:
            List of hashtag strings
        """
        hashtags = []

        for token in tokens:
            token_upper = token.upper()
            if token_upper in TOKEN_HASHTAGS:
                # Add first (main) hashtag for each token
                hashtags.append(TOKEN_HASHTAGS[token_upper][0])

        # Add a core crypto hashtag
        hashtags.extend(random.sample(CORE_CRYPTO_HASHTAGS, 1))

        # Remove duplicates
        seen = set()
        unique = []
        for h in hashtags:
            if h.lower() not in seen:
                seen.add(h.lower())
                unique.append(h)

        return unique[:max_hashtags]

    def generate_hook(
        self,
        hook_type: str = "question",
        context: str = ""
    ) -> str:
        """
        Generate an engagement hook.

        Args:
            hook_type: "question", "cta", or "curiosity"
            context: Context for the hook (not used in simple version)

        Returns:
            Hook string
        """
        if hook_type == "question":
            pool = QUESTION_HOOKS
        elif hook_type == "cta":
            pool = CTA_HOOKS
        else:  # curiosity
            pool = CURIOSITY_HOOKS

        # Avoid recently used hooks
        available = [h for h in pool if h not in self._recent_hooks[-5:]]
        if not available:
            available = pool

        hook = random.choice(available)

        # Track usage
        self._recent_hooks.append(hook)
        if len(self._recent_hooks) > 20:
            self._recent_hooks = self._recent_hooks[-20:]

        return hook

    def append_hook(
        self,
        tweet: str,
        hook_type: str = "question",
        context: str = ""
    ) -> str:
        """
        Append an engagement hook to a tweet.

        Args:
            tweet: Original tweet text
            hook_type: Type of hook to add
            context: Context for hook generation

        Returns:
            Tweet with hook appended
        """
        hook = self.generate_hook(hook_type, context)

        # Calculate available space
        max_len = 280
        combined = f"{tweet} {hook}"

        if len(combined) <= max_len:
            return combined

        # Truncate tweet to fit hook
        available = max_len - len(hook) - 4  # 4 for "... "
        truncated = tweet[:available].rstrip() + "... " + hook

        return truncated

    def get_optimal_posting_time(self) -> datetime:
        """
        Get the next optimal posting time.

        Returns:
            datetime of next optimal posting window
        """
        now = datetime.now(timezone.utc)
        peak_hours = self.schedule.get_peak_hours()

        # Find next peak hour
        current_hour = now.hour

        for hour in sorted(peak_hours):
            if hour > current_hour:
                # Same day
                return now.replace(hour=hour, minute=0, second=0, microsecond=0)

        # Next day, first peak hour
        next_day = now + timedelta(days=1)
        first_peak = min(peak_hours)
        return next_day.replace(hour=first_peak, minute=0, second=0, microsecond=0)

    def is_good_time_to_post(self) -> bool:
        """
        Check if current time is good for posting.

        Returns:
            True if current time is in a peak window
        """
        now = datetime.now(timezone.utc)
        peak_hours = self.schedule.get_peak_hours()

        return now.hour in peak_hours

    def minutes_until_peak(self) -> int:
        """
        Calculate minutes until next peak posting hour.

        Returns:
            Minutes until next peak
        """
        now = datetime.now(timezone.utc)
        optimal = self.get_optimal_posting_time()

        delta = optimal - now
        return int(delta.total_seconds() / 60)

    def optimize_tweet(
        self,
        tweet: str,
        sentiment_data: Dict[str, Any],
        add_hook: bool = False,
        add_hashtags: bool = True
    ) -> str:
        """
        Optimize a tweet for viral potential.

        Args:
            tweet: Original tweet text
            sentiment_data: Sentiment data for hashtag generation
            add_hook: Whether to add an engagement hook
            add_hashtags: Whether to add hashtags

        Returns:
            Optimized tweet
        """
        result = tweet.rstrip()

        # Add hook if requested
        if add_hook:
            hook = self.generate_hook("question")
            if len(result) + len(hook) + 1 <= 280:
                result = f"{result} {hook}"

        # Add hashtags if requested
        if add_hashtags:
            hashtags = self.generate_hashtags(sentiment_data, max_hashtags=3)

            hashtag_str = " " + " ".join(hashtags)
            if len(result) + len(hashtag_str) <= 280:
                result = result + hashtag_str
            else:
                # Add as many as fit
                for hashtag in hashtags:
                    if len(result) + len(hashtag) + 1 <= 280:
                        result = f"{result} {hashtag}"
                    else:
                        break

        return result

    def calculate_viral_score(self, tweet: str) -> float:
        """
        Calculate viral potential score for a tweet.

        Args:
            tweet: Tweet text

        Returns:
            Score from 0-100
        """
        score = 50.0  # Base score

        tweet_lower = tweet.lower()

        # Length bonus (optimal 100-200 chars)
        length = len(tweet)
        if 100 <= length <= 200:
            score += 10
        elif length < 50:
            score -= 10
        elif length > 250:
            score -= 5

        # Question mark bonus (engagement)
        if "?" in tweet:
            score += 10

        # Hashtag bonus (discovery)
        hashtag_count = tweet.count("#")
        if 1 <= hashtag_count <= 3:
            score += 5
        elif hashtag_count > 5:
            score -= 5

        # Call to action bonus
        cta_words = ["follow", "like", "rt", "retweet", "comment", "share"]
        if any(word in tweet_lower for word in cta_words):
            score += 5

        # Emojis (moderate use)
        # Simple check - not comprehensive
        has_numbers = any(c.isdigit() for c in tweet)
        if has_numbers:
            score += 3  # Data/metrics tend to engage

        # Crypto keywords
        crypto_words = ["bullish", "bearish", "pump", "dip", "moon", "alpha"]
        crypto_hits = sum(1 for word in crypto_words if word in tweet_lower)
        score += min(crypto_hits * 2, 10)

        # Cap score
        return max(0, min(100, score))
