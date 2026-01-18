"""
Trending Hashtag Tracker

Monitor: #crypto, #solana, #defi, #trading hashtags
Track: trending tokens, hot topics
Inject: relevant trending hashtags into tweets (max 3)
Frequency: check every 30 minutes
Store: trending.json with TTL
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter"

# Core monitored hashtags
CORE_HASHTAGS = [
    "#crypto",
    "#solana",
    "#defi",
    "#trading",
    "#bitcoin",
    "#ethereum",
    "#altcoins",
    "#nfa",
    "#dyor"
]


class TrendingTracker:
    """
    Tracks trending hashtags and injects them into tweets.

    Usage:
        tracker = TrendingTracker()

        # Fetch trending (call every 30 min)
        await tracker.fetch_trending()

        # Inject hashtags into a tweet
        enhanced = tracker.inject_hashtags("sol looking good nfa", max_hashtags=3)
    """

    # Default TTL for trending data (1 hour)
    DEFAULT_TTL_HOURS = 1

    # Refresh interval (30 minutes)
    REFRESH_INTERVAL_MINUTES = 30

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        twitter_client: Optional[Any] = None
    ):
        """
        Initialize trending tracker.

        Args:
            data_dir: Directory for storing trending data
            twitter_client: Optional Twitter client for fetching trends
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trending_file = self.data_dir / "trending.json"

        self._trending_cache: Dict[str, Dict[str, Any]] = {}
        self._last_fetch: Optional[datetime] = None

        # Load persisted data
        self._load_trending()

        # Twitter client
        if twitter_client:
            self._twitter_client = twitter_client
        else:
            try:
                from bots.twitter.twitter_client import TwitterClient
                self._twitter_client = TwitterClient()
            except ImportError:
                self._twitter_client = None
                logger.warning("TwitterClient not available")

    def _load_trending(self):
        """Load trending data from file."""
        try:
            if self.trending_file.exists():
                data = json.loads(self.trending_file.read_text())
                self._trending_cache = {}

                for hashtag, info in data.get("hashtags", {}).items():
                    # Convert TTL string back to datetime
                    ttl = info.get("ttl")
                    if isinstance(ttl, str):
                        ttl = datetime.fromisoformat(ttl.replace('Z', '+00:00'))
                    else:
                        ttl = datetime.now(timezone.utc)

                    self._trending_cache[hashtag] = {
                        "count": info.get("count", 0),
                        "ttl": ttl
                    }

                self._clean_expired_cache()
                logger.debug(f"Loaded {len(self._trending_cache)} trending hashtags")
        except Exception as e:
            logger.warning(f"Could not load trending data: {e}")
            self._trending_cache = {}

    def save_trending(self):
        """Save trending data to file."""
        try:
            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "hashtags": {}
            }

            for hashtag, info in self._trending_cache.items():
                ttl = info.get("ttl")
                if isinstance(ttl, datetime):
                    ttl = ttl.isoformat()

                data["hashtags"][hashtag] = {
                    "count": info.get("count", 0),
                    "ttl": ttl
                }

            self.trending_file.write_text(json.dumps(data, indent=2))
            logger.debug("Trending data saved")
        except Exception as e:
            logger.error(f"Failed to save trending data: {e}")

    def get_monitored_hashtags(self) -> List[str]:
        """
        Get list of hashtags being monitored.

        Returns:
            List of hashtag strings
        """
        return CORE_HASHTAGS.copy()

    async def fetch_trending(self) -> Dict[str, int]:
        """
        Fetch current trending hashtags from Twitter.

        Returns:
            Dict mapping hashtags to their counts
        """
        if not self._twitter_client:
            logger.warning("No Twitter client available for fetching trends")
            return {}

        try:
            # Connect if not connected
            if hasattr(self._twitter_client, 'connect') and not getattr(self._twitter_client, 'is_connected', False):
                self._twitter_client.connect()

            trending = {}
            ttl = datetime.now(timezone.utc) + timedelta(hours=self.DEFAULT_TTL_HOURS)

            # Search for each core hashtag
            for hashtag in CORE_HASHTAGS:
                try:
                    # Search recent tweets with this hashtag
                    results = await self._twitter_client.search_recent(
                        query=hashtag,
                        max_results=50
                    )

                    count = len(results) if results else 0
                    trending[hashtag] = count

                    # Update cache
                    self._trending_cache[hashtag] = {
                        "count": count,
                        "ttl": ttl
                    }

                except Exception as e:
                    logger.warning(f"Failed to fetch trends for {hashtag}: {e}")

            # Extract additional hashtags from results
            # (This would require parsing tweet text for other hashtags)

            self._last_fetch = datetime.now(timezone.utc)
            self.save_trending()

            logger.info(f"Fetched trends for {len(trending)} hashtags")
            return trending

        except Exception as e:
            logger.error(f"Failed to fetch trending: {e}")
            return {}

    def _clean_expired_cache(self):
        """Remove expired entries from cache."""
        now = datetime.now(timezone.utc)
        expired = []

        for hashtag, info in self._trending_cache.items():
            ttl = info.get("ttl")
            if isinstance(ttl, datetime) and ttl < now:
                expired.append(hashtag)

        for hashtag in expired:
            del self._trending_cache[hashtag]

        if expired:
            logger.debug(f"Cleaned {len(expired)} expired trending entries")

    def get_top_trending(self, limit: int = 5) -> List[str]:
        """
        Get top trending hashtags by count.

        Args:
            limit: Maximum number to return

        Returns:
            List of hashtag strings
        """
        self._clean_expired_cache()

        sorted_tags = sorted(
            self._trending_cache.items(),
            key=lambda x: x[1].get("count", 0),
            reverse=True
        )

        return [tag for tag, _ in sorted_tags[:limit]]

    def inject_hashtags(
        self,
        tweet: str,
        max_hashtags: int = 3,
        relevance_filter: bool = True
    ) -> str:
        """
        Inject trending hashtags into a tweet.

        Args:
            tweet: Original tweet text
            max_hashtags: Maximum hashtags to add (default 3)
            relevance_filter: Only add relevant hashtags

        Returns:
            Enhanced tweet with hashtags
        """
        self._clean_expired_cache()

        # Get current hashtags in tweet
        existing_hashtags = {
            word.lower() for word in tweet.split()
            if word.startswith('#')
        }

        # Get top trending that aren't already in tweet
        candidates = []
        for hashtag in self.get_top_trending(limit=10):
            if hashtag.lower() not in existing_hashtags:
                candidates.append(hashtag)

        # Apply relevance filter
        if relevance_filter:
            tweet_lower = tweet.lower()
            relevant = []

            for hashtag in candidates:
                tag_core = hashtag[1:].lower()  # Remove # for matching

                # Check if related term is in tweet
                if any(term in tweet_lower for term in [tag_core, tag_core[:4]]):
                    relevant.append(hashtag)

            # If no relevant tags, use top general crypto tags
            if not relevant:
                relevant = [h for h in candidates if h.lower() in ['#crypto', '#solana', '#defi']]

            candidates = relevant if relevant else candidates[:2]

        # Select hashtags to add
        hashtags_to_add = candidates[:max_hashtags]

        if not hashtags_to_add:
            return tweet

        # Calculate available space
        hashtag_str = " " + " ".join(hashtags_to_add)

        # Ensure we stay under 280 chars
        max_tweet_len = 280 - len(hashtag_str)

        if len(tweet) > max_tweet_len:
            # Truncate tweet to fit hashtags
            tweet = tweet[:max_tweet_len - 3].rstrip() + "..."

        return tweet.rstrip() + hashtag_str

    def get_relevant_hashtags(self, tokens: List[str]) -> List[str]:
        """
        Get relevant hashtags for specific tokens.

        Args:
            tokens: List of token symbols (e.g., ["SOL", "BTC"])

        Returns:
            List of relevant hashtags
        """
        hashtags = []

        # Token-specific hashtags
        token_map = {
            "SOL": ["#solana", "#sol"],
            "BTC": ["#bitcoin", "#btc"],
            "ETH": ["#ethereum", "#eth"],
            "WIF": ["#dogwifhat", "#memecoins"],
            "BONK": ["#bonk", "#memecoins"]
        }

        for token in tokens:
            token_upper = token.upper()
            if token_upper in token_map:
                hashtags.extend(token_map[token_upper])

        # Add general crypto hashtags
        hashtags.extend(["#crypto", "#defi"])

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for h in hashtags:
            if h.lower() not in seen:
                seen.add(h.lower())
                unique.append(h)

        return unique[:5]

    def should_refresh(self) -> bool:
        """
        Check if trending data should be refreshed.

        Returns:
            True if refresh is needed
        """
        if not self._last_fetch:
            return True

        elapsed = datetime.now(timezone.utc) - self._last_fetch
        return elapsed > timedelta(minutes=self.REFRESH_INTERVAL_MINUTES)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get trending tracker statistics.

        Returns:
            Dict with stats
        """
        self._clean_expired_cache()

        return {
            "cached_hashtags": len(self._trending_cache),
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "needs_refresh": self.should_refresh(),
            "top_trending": self.get_top_trending(5)
        }
