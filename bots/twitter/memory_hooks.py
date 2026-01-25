"""
X/Twitter memory hooks for post performance tracking and engagement pattern recall.

Integrates with core memory system to:
- Store post performance metrics after tweeting
- Recall high-engagement patterns for content optimization
- Analyze best posting times and content patterns
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from core.async_utils import fire_and_forget, TaskTracker
from core.memory import retain_fact, recall

logger = logging.getLogger(__name__)

# Module-level task tracker
_memory_tracker = TaskTracker("twitter_memory")

# Environment variable to enable/disable memory operations
TWITTER_MEMORY_ENABLED = os.getenv("TWITTER_MEMORY_ENABLED", "true").lower() == "true"


async def store_post_performance(
    tweet_id: str,
    content: str,
    likes: int,
    retweets: int,
    replies: int,
    impressions: Optional[int] = None,
    topic: Optional[str] = None,
    posting_time: Optional[datetime] = None,
) -> int:
    """
    Store X post performance metrics in memory.

    Args:
        tweet_id: Tweet ID
        content: Tweet content
        likes: Number of likes
        retweets: Number of retweets
        replies: Number of replies
        impressions: Number of impressions (if available)
        topic: Topic/category of the tweet
        posting_time: When the tweet was posted (default: now)

    Returns:
        Fact ID from memory system

    Example:
        fact_id = await store_post_performance(
            tweet_id="123456",
            content="Solana is pumping!",
            likes=50,
            retweets=10,
            replies=5,
            topic="market_sentiment"
        )
    """
    if not TWITTER_MEMORY_ENABLED:
        logger.debug("Twitter memory disabled, skipping post performance storage")
        return -1

    try:
        # Calculate engagement score
        engagement_score = likes + (retweets * 2) + (replies * 1.5)
        if impressions:
            engagement_rate = (likes + retweets + replies) / max(impressions, 1) * 100
        else:
            engagement_rate = None

        # Extract entities (@mentions, $cashtags)
        entities = []
        if topic:
            entities.append(f"@{topic}")

        # Extract cashtags from content
        words = content.split()
        for word in words:
            if word.startswith("$") and len(word) > 1:
                entities.append(word[:20])  # Limit length

        # Build content summary with metadata embedded
        content_preview = content[:200] + "..." if len(content) > 200 else content
        posting_hour = (posting_time or datetime.now(timezone.utc)).hour

        summary = (
            f"Tweet posted: {content_preview}\n"
            f"Engagement: {likes} likes, {retweets} retweets, {replies} replies\n"
            f"Score: {engagement_score:.1f}"
        )

        if engagement_rate is not None:
            summary += f", Rate: {engagement_rate:.2f}%"

        # Add metadata to summary
        summary += f"\nPosting hour: {posting_hour}, Length: {len(content)}"
        if topic:
            summary += f", Topic: {topic}"

        # Store in memory (retain_fact is sync - run in thread pool)
        fact_id = await asyncio.to_thread(
            retain_fact,
            content=summary,
            context=f"post_performance|{tweet_id}|score:{engagement_score:.1f}|hour:{posting_hour}",
            source="x_posting",
            entities=entities,
            confidence=1.0,
        )

        logger.debug(f"Stored post performance for tweet {tweet_id} (fact_id={fact_id})")
        return fact_id

    except Exception as e:
        logger.error(f"Failed to store post performance: {e}")
        return -1


async def recall_engagement_patterns(
    topic: Optional[str] = None,
    min_likes: int = 10,
    k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Recall high-engagement posts for pattern learning.

    Args:
        topic: Filter by topic/category
        min_likes: Minimum likes threshold
        k: Maximum results to return

    Returns:
        List of high-engagement posts sorted by engagement score

    Example:
        patterns = await recall_engagement_patterns(
            topic="market_sentiment",
            min_likes=20,
            k=5
        )
        for post in patterns:
            print(f"Tweet: {post['content']}")
            print(f"Score: {post.get('engagement_score')}")
    """
    if not TWITTER_MEMORY_ENABLED:
        logger.debug("Twitter memory disabled, returning empty patterns")
        return []

    try:
        # Build query
        query_parts = ["high engagement", "post performance"]
        if topic:
            query_parts.append(topic)

        query = " ".join(query_parts)

        # Recall from memory
        results = await recall(
            query=query,
            k=k * 2,  # Get more results for filtering
            source_filter="x_posting",
            context_filter="post_performance",
            time_filter="month",  # Last month of posts
        )

        # Filter by min_likes and sort by engagement score
        # Parse likes and score from content
        filtered = []
        for result in results:
            content = result.get("content", "")

            # Extract likes from content (format: "Engagement: {likes} likes, ...")
            try:
                if "likes" in content:
                    likes_str = content.split("likes")[0].split()[-1]
                    likes = int(likes_str)
                else:
                    likes = 0

                # Extract engagement score from context (format: "...score:{score}...")
                context_str = result.get("context", "")
                if "score:" in context_str:
                    score_str = context_str.split("score:")[1].split("|")[0]
                    engagement_score = float(score_str)
                else:
                    engagement_score = 0

                if likes >= min_likes:
                    result["engagement_score"] = engagement_score
                    result["parsed_likes"] = likes
                    filtered.append(result)
            except (ValueError, IndexError):
                # Skip if parsing fails
                continue

        # Sort by engagement score descending
        filtered.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)

        return filtered[:k]

    except Exception as e:
        logger.error(f"Failed to recall engagement patterns: {e}")
        return []


async def get_best_posting_times(k: int = 5) -> List[Dict[str, Any]]:
    """
    Analyze past posts to find best posting times.

    Args:
        k: Number of top hours to return

    Returns:
        List of (hour, avg_engagement) sorted by engagement

    Example:
        best_times = await get_best_posting_times(k=3)
        for time_data in best_times:
            print(f"Hour {time_data['hour']}: avg engagement {time_data['avg_engagement']:.1f}")
    """
    if not TWITTER_MEMORY_ENABLED:
        logger.debug("Twitter memory disabled, returning empty posting times")
        return []

    try:
        # Recall all recent posts
        results = await recall(
            query="post performance",
            k=100,  # Get recent 100 posts
            source_filter="x_posting",
            context_filter="post_performance",
            time_filter="month",
        )

        # Group by hour and calculate average engagement
        # Parse hour and score from context field
        hour_stats: Dict[int, List[float]] = {}

        for result in results:
            context_str = result.get("context", "")

            try:
                # Extract posting hour (format: "...hour:{hour}...")
                if "hour:" in context_str:
                    hour_str = context_str.split("hour:")[1].split("|")[0]
                    hour = int(hour_str)
                else:
                    continue

                # Extract engagement score (format: "...score:{score}...")
                if "score:" in context_str:
                    score_str = context_str.split("score:")[1].split("|")[0]
                    score = float(score_str)
                else:
                    continue

                if score > 0:
                    if hour not in hour_stats:
                        hour_stats[hour] = []
                    hour_stats[hour].append(score)
            except (ValueError, IndexError):
                continue

        # Calculate averages
        hour_averages = []
        for hour, scores in hour_stats.items():
            avg_engagement = sum(scores) / len(scores)
            hour_averages.append({
                "hour": hour,
                "avg_engagement": avg_engagement,
                "post_count": len(scores),
            })

        # Sort by engagement
        hour_averages.sort(key=lambda x: x["avg_engagement"], reverse=True)

        return hour_averages[:k]

    except Exception as e:
        logger.error(f"Failed to get best posting times: {e}")
        return []


async def suggest_content_patterns() -> Dict[str, Any]:
    """
    Analyze high-performing posts for content patterns.

    Returns:
        {
            "high_engagement_topics": List[str],
            "avg_engagement_by_topic": Dict[str, float],
            "best_performing_posts": List[Dict],
        }

    Example:
        patterns = await suggest_content_patterns()
        print(f"Top topics: {patterns['high_engagement_topics']}")
        for post in patterns['best_performing_posts']:
            print(f"  - {post['content'][:50]}...")
    """
    if not TWITTER_MEMORY_ENABLED:
        logger.debug("Twitter memory disabled, returning empty patterns")
        return {
            "high_engagement_topics": [],
            "avg_engagement_by_topic": {},
            "best_performing_posts": [],
        }

    try:
        # Get high-engagement posts
        high_engagement = await recall_engagement_patterns(min_likes=15, k=50)

        # Group by topic
        # Parse topic from content field
        topic_stats: Dict[str, List[float]] = {}
        topics_seen = set()

        for post in high_engagement:
            content = post.get("content", "")
            score = post.get("engagement_score", 0)

            # Extract topic from content (format: "...Topic: {topic}")
            try:
                if "Topic:" in content:
                    topic = content.split("Topic:")[1].strip().split(",")[0].strip()
                else:
                    continue

                if topic and score > 0:
                    topics_seen.add(topic)
                    if topic not in topic_stats:
                        topic_stats[topic] = []
                    topic_stats[topic].append(score)
            except (IndexError, AttributeError):
                continue

        # Calculate averages by topic
        avg_by_topic = {}
        for topic, scores in topic_stats.items():
            avg_by_topic[topic] = sum(scores) / len(scores)

        # Sort topics by average engagement
        sorted_topics = sorted(
            avg_by_topic.keys(),
            key=lambda t: avg_by_topic[t],
            reverse=True
        )

        # Get best performing posts (top 5)
        best_posts = high_engagement[:5]

        return {
            "high_engagement_topics": sorted_topics[:10],
            "avg_engagement_by_topic": avg_by_topic,
            "best_performing_posts": best_posts,
        }

    except Exception as e:
        logger.error(f"Failed to suggest content patterns: {e}")
        return {
            "high_engagement_topics": [],
            "avg_engagement_by_topic": {},
            "best_performing_posts": [],
        }
