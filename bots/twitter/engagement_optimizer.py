"""
X/Twitter Engagement Optimizer

Advanced engagement optimization with:
- Sentiment-driven content selection
- Time-based posting optimization
- Thread composition for viral potential
- Emoji and formatting optimization
- Call-to-action effectiveness tracking
- Engagement trend analysis
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Sentiment intensity levels."""
    EXTREMELY_BULLISH = "🚀🚀"
    VERY_BULLISH = "🚀"
    BULLISH = "📈"
    NEUTRAL = "➡️"
    BEARISH = "📉"
    VERY_BEARISH = "💥"


class ContentType(Enum):
    """Content category types."""
    MARKET_UPDATE = "market_update"
    SENTIMENT_ANALYSIS = "sentiment"
    PRICE_ACTION = "price"
    WHALE_ALERT = "whale"
    LIQUIDATION = "liquidation"
    TECHNICAL = "technical"
    ONCHAIN = "onchain"
    PERSONAL = "personal"
    POLL = "poll"
    MEME = "meme"


@dataclass
class EngagementMetrics:
    """Engagement metrics for a post."""
    post_id: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    impressions: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sentiment_level: str = "neutral"
    content_type: str = "general"
    cta_type: Optional[str] = None  # Call-to-action type

    @property
    def engagement_score(self) -> float:
        """Calculate total engagement score."""
        return (self.likes * 1) + (self.retweets * 3) + (self.replies * 2)

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (engagement / impressions)."""
        if self.impressions == 0:
            return 0.0
        return self.engagement_score / self.impressions


@dataclass
class PerformancePattern:
    """Performance pattern for certain content types."""
    content_type: str
    sentiment_level: str
    avg_engagement_score: float = 0.0
    avg_engagement_rate: float = 0.0
    sample_count: int = 0
    best_posting_hour: int = 12  # 0-23 UTC
    best_day_of_week: int = 3  # 0=Monday, 3=Thursday


class EngagementOptimizer:
    """
    X/Twitter engagement optimizer.

    Learns from engagement patterns and optimizes future content.
    """

    def __init__(self):
        """Initialize optimizer."""
        self.engagement_history: List[EngagementMetrics] = []
        self.performance_patterns: Dict[str, PerformancePattern] = {}
        self._learning_enabled = True
        self._min_samples_for_pattern = 10

    # ==================== CONTENT OPTIMIZATION ====================

    def optimize_content(
        self,
        content: str,
        sentiment_level: float,  # 0-100
        content_type: ContentType,
    ) -> Tuple[str, str]:
        """
        Optimize content for maximum engagement.

        Args:
            content: Original content
            sentiment_level: Market sentiment (0-100)
            content_type: Type of content

        Returns:
            Tuple of (optimized_content, cta_type)
        """
        # Choose sentiment emoji tier
        sentiment_emoji = self._get_sentiment_emoji(sentiment_level)

        # Optimize formatting based on content type
        optimized = self._optimize_formatting(content, content_type)

        # Add relevant hashtags
        optimized = self._add_hashtags(optimized, content_type, sentiment_level)

        # Add call-to-action
        optimized, cta_type = self._add_cta(optimized, content_type, sentiment_level)

        # Add emoji for visual appeal
        optimized = self._optimize_emojis(optimized, content_type, sentiment_level)

        return optimized, cta_type

    def _get_sentiment_emoji(self, sentiment: float) -> str:
        """Get emoji based on sentiment level."""
        if sentiment >= 75:
            return SentimentLevel.EXTREMELY_BULLISH.value
        elif sentiment >= 60:
            return SentimentLevel.VERY_BULLISH.value
        elif sentiment >= 50:
            return SentimentLevel.BULLISH.value
        elif sentiment >= 40:
            return SentimentLevel.NEUTRAL.value
        elif sentiment >= 25:
            return SentimentLevel.BEARISH.value
        else:
            return SentimentLevel.VERY_BEARISH.value

    def _optimize_formatting(self, content: str, content_type: ContentType) -> str:
        """Optimize text formatting based on content type."""
        if content_type == ContentType.MARKET_UPDATE:
            # Add line breaks for readability
            lines = content.split('\n')
            return '\n'.join(lines)

        elif content_type == ContentType.SENTIMENT_ANALYSIS:
            # Highlight key numbers
            content = content.replace('$', '💰 $')
            content = content.replace('%', '% 📊')
            return content

        elif content_type == ContentType.TECHNICAL:
            # Highlight technical terms
            terms = {
                'support': '🔴 support',
                'resistance': '🟢 resistance',
                'breakout': '🚀 breakout',
                'reversal': '🔄 reversal',
            }
            for term, replacement in terms.items():
                content = content.replace(term, replacement, flags=2)  # case-insensitive
            return content

        elif content_type == ContentType.WHALE_ALERT:
            # Highlight whale amounts
            content = content.replace('whale', '🐋 WHALE')
            return content

        elif content_type == ContentType.LIQUIDATION:
            # Highlight liquidation data
            content = content.replace('liquidation', '💥 LIQUIDATION')
            return content

        return content

    def _add_hashtags(self, content: str, content_type: ContentType, sentiment: float) -> str:
        """Add relevant hashtags."""
        base_hashtags = ['#Crypto', '#Trading', '#Web3']

        type_hashtags = {
            ContentType.MARKET_UPDATE: ['#MarketUpdate', '#CryptoNews'],
            ContentType.SENTIMENT_ANALYSIS: ['#Sentiment', '#OnChain'],
            ContentType.TECHNICAL: ['#Technical', '#TA'],
            ContentType.WHALE_ALERT: ['#WhaleAlert', '#BigMoney'],
            ContentType.LIQUIDATION: ['#Liquidation', '#Risk'],
            ContentType.MEME: ['#Meme', '#CryptoTwitter'],
        }

        sentiment_hashtags = {
            'bullish': ['#Bullish', '#LongTerm'],
            'bearish': ['#Bearish', '#CautionRed'],
        }

        hashtags = base_hashtags + type_hashtags.get(content_type, [])

        if sentiment >= 60:
            hashtags.extend(sentiment_hashtags['bullish'])
        elif sentiment < 40:
            hashtags.extend(sentiment_hashtags['bearish'])

        # Add hashtags if space permits (Twitter limit)
        hashtag_text = ' '.join(hashtags)
        if len(content) + len(hashtag_text) < 270:  # Leave buffer
            content += f"\n\n{hashtag_text}"

        return content

    def _add_cta(self, content: str, content_type: ContentType, sentiment: float) -> Tuple[str, str]:
        """Add call-to-action."""
        ctas = {
            ContentType.MARKET_UPDATE: [
                "What's your take? 🤔",
                "DYOR always 🔍",
                "Your move? 👇",
            ],
            ContentType.SENTIMENT_ANALYSIS: [
                "Are you bullish or bearish? 🗳️",
                "What does the data say for you?",
                "Comment your analysis 👇",
            ],
            ContentType.TECHNICAL: [
                "What's your price target? 🎯",
                "Technical signal incoming? ⚡",
                "Chart it out 📉",
            ],
            ContentType.WHALE_ALERT: [
                "Is this bullish or bearish? 🤔",
                "What does whale movement mean? 🐋",
                "Your interpretation? 👇",
            ],
            ContentType.POLL: [
                "Vote now 🗳️",
                "What's your prediction? 👇",
            ],
        }

        cta_list = ctas.get(content_type, ["React if you agree 👍"])
        cta = cta_list[0]  # Could rotate
        cta_type = content_type.value

        content += f"\n\n{cta}"
        return content, cta_type

    def _optimize_emojis(self, content: str, content_type: ContentType, sentiment: float) -> str:
        """Optimize emoji usage."""
        # Don't add too many emojis (keep it clean)
        emoji_count = content.count('🚀') + content.count('📈') + content.count('💰')

        if emoji_count < 2:
            sentiment_emoji = self._get_sentiment_emoji(sentiment)
            # Add sentiment emoji if not present
            if sentiment_emoji not in content:
                content = f"{sentiment_emoji} {content}"

        return content

    # ==================== TIMING OPTIMIZATION ====================

    def get_optimal_posting_time(self, content_type: ContentType, sentiment: float) -> datetime:
        """
        Get optimal time to post based on learned patterns.

        Returns:
            Datetime for posting
        """
        pattern_key = f"{content_type.value}_{int(sentiment // 10) * 10}"

        if pattern_key in self.performance_patterns:
            pattern = self.performance_patterns[pattern_key]
            best_hour = pattern.best_posting_hour
            best_day = pattern.best_day_of_week
        else:
            # Default optimal times
            best_hour = 15  # 3 PM UTC (good for US market opening)
            best_day = 3  # Thursday

        # Calculate next optimal time
        now = datetime.utcnow()
        next_optimal = now.replace(hour=best_hour, minute=0, second=0, microsecond=0)

        # If time has passed, use tomorrow
        if next_optimal < now:
            next_optimal += timedelta(days=1)

        # Adjust to best day of week
        days_until_best = (best_day - next_optimal.weekday()) % 7
        if days_until_best > 0:
            next_optimal += timedelta(days=days_until_best)

        return next_optimal

    # ==================== LEARNING & TRACKING ====================

    def record_engagement(
        self,
        post_id: str,
        likes: int,
        retweets: int,
        replies: int,
        impressions: int,
        sentiment_level: str,
        content_type: str,
        cta_type: Optional[str] = None,
    ):
        """Record engagement metrics for learning."""
        metrics = EngagementMetrics(
            post_id=post_id,
            likes=likes,
            retweets=retweets,
            replies=replies,
            impressions=impressions,
            sentiment_level=sentiment_level,
            content_type=content_type,
            cta_type=cta_type,
        )

        self.engagement_history.append(metrics)

        # Update performance patterns
        self._update_patterns(metrics)

        logger.info(
            f"Recorded engagement for {post_id}: "
            f"Score={metrics.engagement_score}, "
            f"Rate={metrics.engagement_rate:.2%}"
        )

    def _update_patterns(self, metrics: EngagementMetrics):
        """Update performance patterns based on metrics."""
        pattern_key = f"{metrics.content_type}_{int(metrics.sentiment_level)}"

        if pattern_key not in self.performance_patterns:
            self.performance_patterns[pattern_key] = PerformancePattern(
                content_type=metrics.content_type,
                sentiment_level=metrics.sentiment_level,
            )

        pattern = self.performance_patterns[pattern_key]

        # Update average engagement
        old_avg = pattern.avg_engagement_score
        new_sample = metrics.engagement_score

        pattern.avg_engagement_score = (
            (old_avg * pattern.sample_count + new_sample) /
            (pattern.sample_count + 1)
        )

        pattern.avg_engagement_rate = (
            (pattern.avg_engagement_rate * pattern.sample_count + metrics.engagement_rate) /
            (pattern.sample_count + 1)
        )

        pattern.sample_count += 1

    def get_top_performing_patterns(self, limit: int = 5) -> List[PerformancePattern]:
        """Get top performing content patterns."""
        patterns = list(self.performance_patterns.values())
        patterns.sort(key=lambda p: p.avg_engagement_rate, reverse=True)
        return patterns[:limit]

    def get_engagement_report(self) -> str:
        """Generate engagement analysis report."""
        if not self.engagement_history:
            return "No engagement data yet"

        total_engagement = sum(m.engagement_score for m in self.engagement_history)
        avg_engagement = total_engagement / len(self.engagement_history)
        avg_rate = sum(m.engagement_rate for m in self.engagement_history) / len(self.engagement_history)

        best_post = max(self.engagement_history, key=lambda m: m.engagement_score)
        worst_post = min(self.engagement_history, key=lambda m: m.engagement_score)

        report = f"""
<b>X/Twitter Engagement Report</b>

<b>Overall Stats:</b>
  Posts Analyzed: {len(self.engagement_history)}
  Avg Engagement Score: {avg_engagement:.0f}
  Avg Engagement Rate: {avg_rate:.2%}
  Total Engagement: {total_engagement:.0f}

<b>Best Post:</b>
  ID: {best_post.post_id}
  Score: {best_post.engagement_score}
  Type: {best_post.content_type}

<b>Worst Post:</b>
  ID: {worst_post.post_id}
  Score: {worst_post.engagement_score}
  Type: {worst_post.content_type}

<b>Top Performing Patterns:</b>
"""

        for i, pattern in enumerate(self.get_top_performing_patterns(3), 1):
            report += f"""  {i}. {pattern.content_type} ({pattern.sentiment_level})
     Avg Rate: {pattern.avg_engagement_rate:.2%}
     Sample Size: {pattern.sample_count}\n"""

        return report

    # ==================== CONTENT RECOMMENDATIONS ====================

    def recommend_content(self, current_sentiment: float) -> Dict[str, Any]:
        """Recommend optimal content based on sentiment."""
        recommendations = {
            'content_type': None,
            'sentiment_expectation': None,
            'posting_time': None,
            'reason': None,
        }

        # Get best performing type
        top_patterns = self.get_top_performing_patterns(1)
        if top_patterns:
            pattern = top_patterns[0]
            recommendations['content_type'] = pattern.content_type
            recommendations['sentiment_expectation'] = pattern.sentiment_level

        # Get optimal posting time
        if recommendations['content_type']:
            content_type = ContentType(recommendations['content_type'])
            recommendations['posting_time'] = self.get_optimal_posting_time(
                content_type, current_sentiment
            )

        recommendations['reason'] = (
            f"Based on {len(self.engagement_history)} analyzed posts, "
            f"{recommendations['content_type']} content has highest engagement"
        )

        return recommendations
