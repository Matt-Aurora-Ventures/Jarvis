"""
Twitter Engagement Tracker - Track tweet performance, engagement metrics, and audience insights.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "engagement.db"


@dataclass
class TweetMetrics:
    """Metrics for a single tweet."""
    tweet_id: str
    created_at: str
    text_preview: str  # First 100 chars
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    impressions: int = 0
    profile_clicks: int = 0
    url_clicks: int = 0
    hashtag_clicks: int = 0
    detail_expands: int = 0
    engagement_rate: float = 0.0
    last_updated: str = ""


@dataclass
class ThreadMetrics:
    """Aggregated metrics for a thread."""
    thread_id: str  # First tweet ID
    tweet_count: int
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0
    total_impressions: int = 0
    avg_engagement_rate: float = 0.0
    best_performing_tweet: str = ""
    created_at: str = ""


@dataclass
class AudienceInsight:
    """Audience analytics snapshot."""
    timestamp: str
    follower_count: int
    following_count: int
    follower_growth_24h: int = 0
    follower_growth_7d: int = 0
    top_follower_locations: Dict[str, int] = field(default_factory=dict)
    top_follower_interests: List[str] = field(default_factory=list)
    peak_engagement_hours: List[int] = field(default_factory=list)


class EngagementDB:
    """SQLite database for engagement tracking."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tweet metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tweet_metrics (
                    tweet_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    text_preview TEXT,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    quotes INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    profile_clicks INTEGER DEFAULT 0,
                    url_clicks INTEGER DEFAULT 0,
                    hashtag_clicks INTEGER DEFAULT 0,
                    detail_expands INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    last_updated TEXT,
                    thread_id TEXT
                )
            """)

            # Metrics history for tracking changes over time
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tweet_id TEXT,
                    timestamp TEXT,
                    likes INTEGER,
                    retweets INTEGER,
                    replies INTEGER,
                    impressions INTEGER,
                    FOREIGN KEY (tweet_id) REFERENCES tweet_metrics(tweet_id)
                )
            """)

            # Audience snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audience_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    follower_count INTEGER,
                    following_count INTEGER,
                    data_json TEXT
                )
            """)

            # Thread tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    tweet_count INTEGER,
                    created_at TEXT,
                    topic TEXT,
                    type TEXT
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_created ON tweet_metrics(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_thread ON tweet_metrics(thread_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_tweet ON metrics_history(tweet_id)")

            conn.commit()
            logger.info(f"Engagement database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_tweet_metrics(self, metrics: TweetMetrics, thread_id: str = None):
        """Save or update tweet metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tweet_metrics
                (tweet_id, created_at, text_preview, likes, retweets, replies,
                 quotes, impressions, profile_clicks, url_clicks, hashtag_clicks,
                 detail_expands, engagement_rate, last_updated, thread_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.tweet_id, metrics.created_at, metrics.text_preview,
                metrics.likes, metrics.retweets, metrics.replies, metrics.quotes,
                metrics.impressions, metrics.profile_clicks, metrics.url_clicks,
                metrics.hashtag_clicks, metrics.detail_expands, metrics.engagement_rate,
                datetime.now(timezone.utc).isoformat(), thread_id
            ))

            # Also save to history
            cursor.execute("""
                INSERT INTO metrics_history
                (tweet_id, timestamp, likes, retweets, replies, impressions)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                metrics.tweet_id, datetime.now(timezone.utc).isoformat(),
                metrics.likes, metrics.retweets, metrics.replies, metrics.impressions
            ))

            conn.commit()

    def get_tweet_metrics(self, tweet_id: str) -> Optional[Dict]:
        """Get metrics for a specific tweet."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tweet_metrics WHERE tweet_id = ?", (tweet_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_thread_metrics(self, thread_id: str) -> Optional[ThreadMetrics]:
        """Get aggregated metrics for a thread."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as tweet_count,
                    SUM(likes) as total_likes,
                    SUM(retweets) as total_retweets,
                    SUM(replies) as total_replies,
                    SUM(impressions) as total_impressions,
                    AVG(engagement_rate) as avg_engagement_rate,
                    MIN(created_at) as created_at
                FROM tweet_metrics
                WHERE thread_id = ?
            """, (thread_id,))
            row = cursor.fetchone()

            if not row or row['tweet_count'] == 0:
                return None

            # Find best performing tweet
            cursor.execute("""
                SELECT tweet_id FROM tweet_metrics
                WHERE thread_id = ?
                ORDER BY (likes + retweets * 2 + replies * 3) DESC
                LIMIT 1
            """, (thread_id,))
            best = cursor.fetchone()

            return ThreadMetrics(
                thread_id=thread_id,
                tweet_count=row['tweet_count'],
                total_likes=row['total_likes'] or 0,
                total_retweets=row['total_retweets'] or 0,
                total_replies=row['total_replies'] or 0,
                total_impressions=row['total_impressions'] or 0,
                avg_engagement_rate=row['avg_engagement_rate'] or 0.0,
                best_performing_tweet=best['tweet_id'] if best else "",
                created_at=row['created_at'] or ""
            )

    def get_top_tweets(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """Get top performing tweets by engagement."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *,
                    (likes + retweets * 2 + replies * 3) as engagement_score
                FROM tweet_metrics
                WHERE datetime(created_at) > datetime('now', ?)
                ORDER BY engagement_score DESC
                LIMIT ?
            """, (f'-{days} days', limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_engagement_trends(self, days: int = 30) -> Dict:
        """Get engagement trends over time."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    date(created_at) as date,
                    COUNT(*) as tweet_count,
                    SUM(likes) as total_likes,
                    SUM(retweets) as total_retweets,
                    SUM(impressions) as total_impressions,
                    AVG(engagement_rate) as avg_engagement_rate
                FROM tweet_metrics
                WHERE datetime(created_at) > datetime('now', ?)
                GROUP BY date(created_at)
                ORDER BY date ASC
            """, (f'-{days} days',))

            return {
                'daily_stats': [dict(row) for row in cursor.fetchall()]
            }

    def save_audience_snapshot(self, insight: AudienceInsight):
        """Save audience analytics snapshot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audience_snapshots
                (timestamp, follower_count, following_count, data_json)
                VALUES (?, ?, ?, ?)
            """, (
                insight.timestamp,
                insight.follower_count,
                insight.following_count,
                json.dumps(asdict(insight))
            ))
            conn.commit()

    def get_follower_growth(self, days: int = 30) -> List[Dict]:
        """Get follower growth over time."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, follower_count
                FROM audience_snapshots
                WHERE datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp ASC
            """, (f'-{days} days',))
            return [dict(row) for row in cursor.fetchall()]


class EngagementTracker:
    """
    Track and analyze Twitter engagement metrics.

    Usage:
        tracker = EngagementTracker()

        # After posting a tweet
        await tracker.track_tweet(tweet_id, tweet_text)

        # Get performance report
        report = await tracker.get_performance_report(days=7)
    """

    def __init__(self, api_client=None):
        self.db = EngagementDB()
        self.api = api_client  # Twitter API client
        self._tracking_interval = 3600  # 1 hour
        self._tracked_tweets: Dict[str, datetime] = {}

    async def track_tweet(self, tweet_id: str, text: str, thread_id: str = None):
        """Start tracking a tweet."""
        metrics = TweetMetrics(
            tweet_id=tweet_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            text_preview=text[:100] if text else ""
        )
        self.db.save_tweet_metrics(metrics, thread_id)
        self._tracked_tweets[tweet_id] = datetime.now(timezone.utc)
        logger.info(f"Started tracking tweet {tweet_id}")

    async def track_thread(self, tweet_ids: List[str], texts: List[str], topic: str = ""):
        """Track a thread of tweets."""
        if not tweet_ids:
            return

        thread_id = tweet_ids[0]

        # Save thread info
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO threads
                (thread_id, tweet_count, created_at, topic, type)
                VALUES (?, ?, ?, ?, 'sentiment_report')
            """, (
                thread_id, len(tweet_ids),
                datetime.now(timezone.utc).isoformat(), topic
            ))
            conn.commit()

        # Track each tweet
        for tweet_id, text in zip(tweet_ids, texts):
            await self.track_tweet(tweet_id, text, thread_id)

    async def update_metrics(self, tweet_id: str) -> Optional[TweetMetrics]:
        """Fetch and update metrics for a tweet from Twitter API."""
        if not self.api:
            logger.warning("No API client configured for metrics updates")
            return None

        try:
            # Fetch tweet data from Twitter API
            tweet_data = await self.api.get_tweet(tweet_id)
            if not tweet_data:
                logger.warning(f"Could not fetch tweet {tweet_id}")
                return None

            # Extract public metrics
            metrics_data = tweet_data.get("metrics", {})
            likes = metrics_data.get("like_count", 0)
            retweets = metrics_data.get("retweet_count", 0)
            replies = metrics_data.get("reply_count", 0)
            quotes = metrics_data.get("quote_count", 0)
            impressions = metrics_data.get("impression_count", 0)

            # Calculate engagement rate (engagements / impressions)
            total_engagements = likes + retweets + replies + quotes
            engagement_rate = (total_engagements / impressions * 100) if impressions > 0 else 0.0

            # Get existing metrics or create new
            existing = self.db.get_tweet_metrics(tweet_id)
            text_preview = existing.get("text_preview", "") if existing else tweet_data.get("text", "")[:100]
            created_at = existing.get("created_at", "") if existing else tweet_data.get("created_at", "")

            # Create updated metrics object
            metrics = TweetMetrics(
                tweet_id=tweet_id,
                created_at=str(created_at),
                text_preview=text_preview,
                likes=likes,
                retweets=retweets,
                replies=replies,
                quotes=quotes,
                impressions=impressions,
                engagement_rate=round(engagement_rate, 2),
                last_updated=datetime.now(timezone.utc).isoformat()
            )

            # Save to database
            self.db.save_tweet_metrics(metrics)
            logger.debug(f"Updated metrics for tweet {tweet_id}: {likes} likes, {retweets} RTs")

            return metrics

        except Exception as e:
            logger.error(f"Failed to update metrics for {tweet_id}: {e}")
            return None

    async def update_all_tracked(self):
        """Update metrics for all tracked tweets."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        for tweet_id, tracked_at in list(self._tracked_tweets.items()):
            if tracked_at < cutoff:
                del self._tracked_tweets[tweet_id]
                continue

            await self.update_metrics(tweet_id)
            await asyncio.sleep(1)  # Rate limiting

    def get_performance_report(self, days: int = 7) -> Dict:
        """Generate a performance report."""
        top_tweets = self.db.get_top_tweets(days=days)
        trends = self.db.get_engagement_trends(days=days)

        # Calculate summary stats
        total_tweets = len(top_tweets)
        total_likes = sum(t.get('likes', 0) for t in top_tweets)
        total_retweets = sum(t.get('retweets', 0) for t in top_tweets)
        total_impressions = sum(t.get('impressions', 0) for t in top_tweets)

        avg_engagement = (
            sum(t.get('engagement_rate', 0) for t in top_tweets) / total_tweets
            if total_tweets > 0 else 0
        )

        return {
            'period_days': days,
            'total_tweets': total_tweets,
            'total_likes': total_likes,
            'total_retweets': total_retweets,
            'total_impressions': total_impressions,
            'avg_engagement_rate': avg_engagement,
            'top_tweets': top_tweets[:5],
            'trends': trends
        }

    def get_category_performance(self, hours: int = 168) -> Dict[str, Dict[str, float]]:
        """
        Get average engagement by content category from X memory storage.

        Returns:
            {category: {avg_likes, avg_retweets, avg_replies, count}}
        """
        x_memory_db = Path(__file__).resolve().parents[2] / "data" / "jarvis_x_memory.db"
        if not x_memory_db.exists():
            return {}

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = sqlite3.connect(str(x_memory_db))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category,
                       COUNT(*) as count,
                       AVG(engagement_likes) as avg_likes,
                       AVG(engagement_retweets) as avg_retweets,
                       AVG(engagement_replies) as avg_replies
                FROM tweets
                WHERE posted_at > ?
                GROUP BY category
            """, (cutoff,))

            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    "count": row[1],
                    "avg_likes": round(row[2] or 0, 1),
                    "avg_retweets": round(row[3] or 0, 1),
                    "avg_replies": round(row[4] or 0, 1),
                }

            return results
        finally:
            conn.close()

    def get_best_posting_times(self) -> List[Dict]:
        """Analyze best times to post based on engagement."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    strftime('%H', created_at) as hour,
                    strftime('%w', created_at) as day_of_week,
                    AVG(engagement_rate) as avg_engagement,
                    COUNT(*) as tweet_count
                FROM tweet_metrics
                WHERE datetime(created_at) > datetime('now', '-30 days')
                GROUP BY hour, day_of_week
                HAVING tweet_count >= 3
                ORDER BY avg_engagement DESC
                LIMIT 10
            """)

            results = []
            day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            for row in cursor.fetchall():
                try:
                    day_idx = int(row['day_of_week'])
                    day = day_names[day_idx] if 0 <= day_idx < len(day_names) else 'Unknown'
                    hour = int(row['hour'])
                except (ValueError, TypeError, KeyError):
                    continue
                results.append({
                    'hour': hour,
                    'day': day,
                    'avg_engagement': row['avg_engagement'],
                    'sample_size': row['tweet_count']
                })
            return results

    def get_content_analysis(self) -> Dict:
        """Analyze which content types perform best."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Analyze by thread vs single tweet
            cursor.execute("""
                SELECT
                    CASE WHEN thread_id IS NOT NULL THEN 'thread' ELSE 'single' END as type,
                    AVG(engagement_rate) as avg_engagement,
                    AVG(likes) as avg_likes,
                    COUNT(*) as count
                FROM tweet_metrics
                WHERE datetime(created_at) > datetime('now', '-30 days')
                GROUP BY type
            """)

            by_type = {row['type']: dict(row) for row in cursor.fetchall()}

            # Analyze by length
            cursor.execute("""
                SELECT
                    CASE
                        WHEN length(text_preview) < 50 THEN 'short'
                        WHEN length(text_preview) < 100 THEN 'medium'
                        ELSE 'long'
                    END as length_category,
                    AVG(engagement_rate) as avg_engagement,
                    COUNT(*) as count
                FROM tweet_metrics
                WHERE datetime(created_at) > datetime('now', '-30 days')
                GROUP BY length_category
            """)

            by_length = {row['length_category']: dict(row) for row in cursor.fetchall()}

            return {
                'by_type': by_type,
                'by_length': by_length
            }

    def generate_insights(self) -> List[str]:
        """Generate actionable insights from the data."""
        insights = []

        report = self.get_performance_report(days=30)
        best_times = self.get_best_posting_times()
        content = self.get_content_analysis()

        # Engagement insights
        if report['avg_engagement_rate'] > 3.0:
            insights.append("Strong engagement rate - audience is highly responsive")
        elif report['avg_engagement_rate'] < 1.0:
            insights.append("Low engagement - consider adjusting content strategy")

        # Best posting times
        if best_times:
            top_time = best_times[0]
            insights.append(
                f"Best posting time: {top_time['day']} at {top_time['hour']}:00 UTC "
                f"({top_time['avg_engagement']:.2f}% avg engagement)"
            )

        # Content type insights
        if content.get('by_type'):
            if 'thread' in content['by_type'] and 'single' in content['by_type']:
                thread_eng = content['by_type']['thread'].get('avg_engagement', 0)
                single_eng = content['by_type']['single'].get('avg_engagement', 0)
                if thread_eng > single_eng * 1.5:
                    insights.append("Threads significantly outperform single tweets")
                elif single_eng > thread_eng * 1.5:
                    insights.append("Single tweets outperform threads - keep it concise")

        return insights


# Singleton instance
_tracker: Optional[EngagementTracker] = None

def get_engagement_tracker() -> EngagementTracker:
    """Get singleton engagement tracker."""
    global _tracker
    if _tracker is None:
        _tracker = EngagementTracker()
    return _tracker
