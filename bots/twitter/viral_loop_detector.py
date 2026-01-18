"""
Viral Loop Detector

Detect successful tweet patterns:
- High engagement tweets (>100 likes/RT)
- Common attributes: length, emojis, hashtags, time posted

Store: successful_patterns.json
Suggest: similar patterns for future tweets
Measure: how many successful tweets follow top patterns
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from collections import Counter

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "twitter"

# Viral thresholds
VIRAL_THRESHOLD_LIKES = 100
VIRAL_THRESHOLD_RETWEETS = 50


class ViralLoopDetector:
    """
    Detects viral tweet patterns and suggests optimizations.

    Usage:
        detector = ViralLoopDetector()

        # Check if a tweet is viral
        is_viral = detector.is_viral(tweet_data)

        # Record viral tweet
        detector.record_viral_tweet(tweet_data)

        # Get pattern suggestions
        suggestions = detector.get_pattern_suggestions()
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize viral loop detector.

        Args:
            data_dir: Directory for storing pattern data
        """
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.data_dir / "successful_patterns.json"

        self._viral_tweets: List[Dict[str, Any]] = []
        self._patterns: Dict[str, Any] = {}

        self._load_patterns()

    def _load_patterns(self):
        """Load patterns from file."""
        try:
            if self.patterns_file.exists():
                data = json.loads(self.patterns_file.read_text())
                self._viral_tweets = data.get("viral_tweets", [])
                self._patterns = data.get("aggregated_patterns", {})
                logger.debug(f"Loaded {len(self._viral_tweets)} viral tweet patterns")
        except Exception as e:
            logger.warning(f"Could not load patterns: {e}")
            self._viral_tweets = []
            self._patterns = {}

    def _save_patterns(self):
        """Save patterns to file."""
        try:
            # Aggregate patterns from viral tweets
            self._aggregate_patterns()

            data = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "viral_tweets": self._viral_tweets[-100:],  # Keep last 100
                "aggregated_patterns": self._patterns
            }

            self.patterns_file.write_text(json.dumps(data, indent=2))
            logger.debug("Patterns saved")
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")

    def is_viral(self, tweet_data: Dict[str, Any]) -> bool:
        """
        Check if a tweet meets viral thresholds.

        Args:
            tweet_data: Dict with likes, retweets, replies

        Returns:
            True if tweet is considered viral
        """
        likes = tweet_data.get("likes", 0)
        retweets = tweet_data.get("retweets", 0)

        # Viral if either threshold is met
        return likes >= VIRAL_THRESHOLD_LIKES or retweets >= VIRAL_THRESHOLD_RETWEETS

    def extract_patterns(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract pattern attributes from a tweet.

        Args:
            tweet_data: Dict with tweet content and metadata

        Returns:
            Dict of pattern attributes
        """
        text = tweet_data.get("text", "")
        created_at = tweet_data.get("created_at", "")

        # Calculate length
        length = len(text)

        # Count emojis (simplified emoji detection)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+"
        )
        emoji_count = len(emoji_pattern.findall(text))

        # Count hashtags
        hashtag_count = text.count('#')

        # Count cashtags
        cashtag_count = text.count('$')

        # Extract hour posted
        hour_posted = None
        if created_at:
            try:
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    dt = created_at
                hour_posted = dt.hour
            except Exception:
                pass

        # Check for patterns
        has_nfa = 'nfa' in text.lower()
        has_question = '?' in text
        has_numbers = bool(re.search(r'\d+', text))
        has_link = 'http' in text.lower() or 't.me' in text.lower()

        # Length category
        if length < 100:
            length_category = "short"
        elif length < 200:
            length_category = "medium"
        else:
            length_category = "long"

        return {
            "length": length,
            "length_category": length_category,
            "emoji_count": emoji_count,
            "hashtag_count": hashtag_count,
            "cashtag_count": cashtag_count,
            "hour_posted": hour_posted,
            "has_nfa": has_nfa,
            "has_question": has_question,
            "has_numbers": has_numbers,
            "has_link": has_link
        }

    def record_viral_tweet(self, tweet_data: Dict[str, Any]):
        """
        Record a viral tweet and its patterns.

        Args:
            tweet_data: Dict with tweet content and metrics
        """
        if not self.is_viral(tweet_data):
            logger.debug("Tweet does not meet viral threshold")
            return

        patterns = self.extract_patterns(tweet_data)

        record = {
            "tweet_id": tweet_data.get("id"),
            "text_preview": tweet_data.get("text", "")[:100],
            "likes": tweet_data.get("likes", 0),
            "retweets": tweet_data.get("retweets", 0),
            "replies": tweet_data.get("replies", 0),
            "patterns": patterns,
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }

        self._viral_tweets.append(record)
        self._save_patterns()

        logger.info(f"Recorded viral tweet: {record['tweet_id']} ({record['likes']} likes)")

    def _aggregate_patterns(self):
        """Aggregate patterns from all viral tweets."""
        if not self._viral_tweets:
            return

        # Collect all pattern values
        lengths = []
        emoji_counts = []
        hashtag_counts = []
        hours = []
        length_categories = Counter()
        features = Counter()

        for tweet in self._viral_tweets:
            patterns = tweet.get("patterns", {})

            if patterns.get("length"):
                lengths.append(patterns["length"])
            if patterns.get("emoji_count") is not None:
                emoji_counts.append(patterns["emoji_count"])
            if patterns.get("hashtag_count") is not None:
                hashtag_counts.append(patterns["hashtag_count"])
            if patterns.get("hour_posted") is not None:
                hours.append(patterns["hour_posted"])
            if patterns.get("length_category"):
                length_categories[patterns["length_category"]] += 1

            # Count boolean features
            if patterns.get("has_nfa"):
                features["nfa"] += 1
            if patterns.get("has_question"):
                features["question"] += 1
            if patterns.get("has_numbers"):
                features["numbers"] += 1
            if patterns.get("has_link"):
                features["link"] += 1

        # Calculate aggregates
        self._patterns = {
            "total_viral_tweets": len(self._viral_tweets),
            "optimal_length": {
                "min": min(lengths) if lengths else 0,
                "max": max(lengths) if lengths else 280,
                "avg": sum(lengths) / len(lengths) if lengths else 150
            },
            "optimal_emoji_count": {
                "avg": sum(emoji_counts) / len(emoji_counts) if emoji_counts else 0,
                "max_common": max(set(emoji_counts), key=emoji_counts.count) if emoji_counts else 0
            },
            "optimal_hashtag_count": {
                "avg": sum(hashtag_counts) / len(hashtag_counts) if hashtag_counts else 0
            },
            "best_hours": self._get_best_hours(hours),
            "length_category_distribution": dict(length_categories),
            "feature_rates": {
                k: round(v / len(self._viral_tweets) * 100, 1)
                for k, v in features.items()
            } if self._viral_tweets else {}
        }

    def _get_best_hours(self, hours: List[int]) -> List[int]:
        """Get best performing hours."""
        if not hours:
            return [14, 15, 16]  # Default afternoon hours

        hour_counts = Counter(hours)
        return [h for h, _ in hour_counts.most_common(3)]

    def get_pattern_suggestions(self) -> Dict[str, Any]:
        """
        Get suggestions for optimizing future tweets.

        Returns:
            Dict with optimization suggestions
        """
        if not self._patterns:
            self._aggregate_patterns()

        if not self._patterns.get("total_viral_tweets"):
            return {
                "status": "insufficient_data",
                "message": "Need more viral tweets to generate suggestions"
            }

        suggestions = {
            "status": "success",
            "based_on_tweets": self._patterns.get("total_viral_tweets", 0),
            "recommendations": []
        }

        # Length recommendation
        optimal_length = self._patterns.get("optimal_length", {})
        avg_len = optimal_length.get("avg", 150)
        suggestions["optimal_length"] = int(avg_len)
        suggestions["recommendations"].append(
            f"Aim for {int(avg_len)} characters (range: {optimal_length.get('min', 50)}-{optimal_length.get('max', 250)})"
        )

        # Emoji recommendation
        emoji_data = self._patterns.get("optimal_emoji_count", {})
        avg_emoji = emoji_data.get("avg", 0)
        suggestions["recommended_emoji_count"] = round(avg_emoji, 1)
        if avg_emoji > 0:
            suggestions["recommendations"].append(
                f"Use {round(avg_emoji, 1)} emojis on average"
            )

        # Hashtag recommendation
        hashtag_data = self._patterns.get("optimal_hashtag_count", {})
        avg_hashtags = hashtag_data.get("avg", 2)
        suggestions["recommended_hashtag_count"] = round(avg_hashtags, 1)
        suggestions["recommendations"].append(
            f"Include {round(avg_hashtags)} hashtags"
        )

        # Best hours
        best_hours = self._patterns.get("best_hours", [14, 15, 16])
        suggestions["recommended_hours"] = best_hours
        suggestions["recommendations"].append(
            f"Post at {', '.join([f'{h}:00' for h in best_hours])} UTC"
        )

        # Feature recommendations
        feature_rates = self._patterns.get("feature_rates", {})
        if feature_rates.get("nfa", 0) > 50:
            suggestions["recommendations"].append("Include NFA disclaimer")
        if feature_rates.get("numbers", 0) > 50:
            suggestions["recommendations"].append("Include specific numbers/stats")

        return suggestions

    def calculate_pattern_match(self, tweet_attrs: Dict[str, Any]) -> float:
        """
        Calculate how well a tweet matches successful patterns.

        Args:
            tweet_attrs: Dict with tweet attributes (text, hour_posted, etc.)

        Returns:
            Match score from 0-100
        """
        if not self._patterns.get("total_viral_tweets"):
            return 50.0  # Default neutral score

        score = 50.0  # Start at neutral

        # Check length
        text = tweet_attrs.get("text", "")
        length = len(text) if isinstance(text, str) else 0

        optimal = self._patterns.get("optimal_length", {})
        if optimal.get("min", 0) <= length <= optimal.get("max", 280):
            score += 10
        elif abs(length - optimal.get("avg", 150)) < 50:
            score += 5

        # Check hour
        hour = tweet_attrs.get("hour_posted")
        if hour in self._patterns.get("best_hours", []):
            score += 15

        # Check features
        feature_rates = self._patterns.get("feature_rates", {})
        if tweet_attrs.get("has_nfa") and feature_rates.get("nfa", 0) > 50:
            score += 10
        if tweet_attrs.get("has_numbers") and feature_rates.get("numbers", 0) > 50:
            score += 10

        return min(100.0, max(0.0, score))

    def get_viral_rate(self, days: int = 7) -> float:
        """
        Calculate viral rate over recent period.

        Args:
            days: Number of days to look back

        Returns:
            Percentage of tweets that went viral
        """
        # This would need total tweet count to calculate properly
        # For now, return count of recent viral tweets
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_viral = [
            t for t in self._viral_tweets
            if datetime.fromisoformat(t.get("recorded_at", "2000-01-01").replace('Z', '+00:00')) > cutoff
        ]

        return len(recent_viral)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get detector statistics.

        Returns:
            Dict with stats
        """
        return {
            "total_viral_tweets_recorded": len(self._viral_tweets),
            "patterns_available": bool(self._patterns),
            "viral_threshold_likes": VIRAL_THRESHOLD_LIKES,
            "viral_threshold_retweets": VIRAL_THRESHOLD_RETWEETS,
            "best_hours": self._patterns.get("best_hours", [])
        }
