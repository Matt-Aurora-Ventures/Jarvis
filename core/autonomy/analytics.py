"""
Performance Analytics
Track and analyze bot performance metrics
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "analytics"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DailyMetrics:
    """Daily performance metrics"""
    date: str
    tweets_posted: int = 0
    replies_sent: int = 0
    mentions_received: int = 0
    mentions_replied: int = 0
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0
    total_impressions: int = 0
    engagement_rate: float = 0.0
    follower_count: int = 0
    follower_change: int = 0
    top_tweet_id: str = ""
    top_tweet_engagement: int = 0


@dataclass  
class ContentTypeMetrics:
    """Metrics by content type"""
    content_type: str
    count: int = 0
    total_engagement: int = 0
    avg_engagement: float = 0.0


class PerformanceAnalytics:
    """
    Track and analyze performance.
    Generate insights and recommendations.
    """
    
    def __init__(self):
        self.metrics_file = DATA_DIR / "daily_metrics.json"
        self.summary_file = DATA_DIR / "summary.json"
        
        self.daily_metrics: Dict[str, DailyMetrics] = {}
        self.content_metrics: Dict[str, ContentTypeMetrics] = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load analytics data"""
        try:
            if self.metrics_file.exists():
                data = json.loads(self.metrics_file.read_text())
                self.daily_metrics = {k: DailyMetrics(**v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading analytics: {e}")
    
    def _save_data(self):
        """Save analytics data"""
        try:
            # Keep last 90 days
            cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
            filtered = {k: asdict(v) for k, v in self.daily_metrics.items() if k >= cutoff}
            self.metrics_file.write_text(json.dumps(filtered, indent=2))
        except Exception as e:
            logger.error(f"Error saving analytics: {e}")
    
    def _get_today_key(self) -> str:
        """Get today's date key"""
        return datetime.utcnow().strftime("%Y-%m-%d")
    
    def _ensure_today(self) -> DailyMetrics:
        """Ensure today's metrics exist"""
        key = self._get_today_key()
        if key not in self.daily_metrics:
            self.daily_metrics[key] = DailyMetrics(date=key)
        return self.daily_metrics[key]
    
    def record_tweet(self, tweet_id: str, content_type: str = "general"):
        """Record a posted tweet"""
        metrics = self._ensure_today()
        metrics.tweets_posted += 1
        
        # Track by content type
        if content_type not in self.content_metrics:
            self.content_metrics[content_type] = ContentTypeMetrics(content_type=content_type)
        self.content_metrics[content_type].count += 1
        
        self._save_data()
    
    def record_reply(self):
        """Record a reply sent"""
        metrics = self._ensure_today()
        metrics.replies_sent += 1
        self._save_data()
    
    def record_mention(self, replied: bool = False):
        """Record a mention received"""
        metrics = self._ensure_today()
        metrics.mentions_received += 1
        if replied:
            metrics.mentions_replied += 1
        self._save_data()
    
    def update_engagement(
        self,
        tweet_id: str,
        likes: int,
        retweets: int,
        replies: int,
        impressions: int = 0,
        content_type: str = "general"
    ):
        """Update engagement metrics"""
        metrics = self._ensure_today()
        
        metrics.total_likes += likes
        metrics.total_retweets += retweets
        metrics.total_replies += replies
        metrics.total_impressions += impressions
        
        # Track top tweet
        engagement = likes + retweets + replies
        if engagement > metrics.top_tweet_engagement:
            metrics.top_tweet_id = tweet_id
            metrics.top_tweet_engagement = engagement
        
        # Calculate engagement rate
        if metrics.total_impressions > 0:
            total_eng = metrics.total_likes + metrics.total_retweets + metrics.total_replies
            metrics.engagement_rate = total_eng / metrics.total_impressions
        
        # Update content type metrics
        if content_type in self.content_metrics:
            cm = self.content_metrics[content_type]
            cm.total_engagement += engagement
            cm.avg_engagement = cm.total_engagement / cm.count if cm.count > 0 else 0
        
        self._save_data()
    
    def update_followers(self, count: int):
        """Update follower count"""
        metrics = self._ensure_today()
        
        # Calculate change from yesterday
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday in self.daily_metrics:
            prev_count = self.daily_metrics[yesterday].follower_count
            if prev_count > 0:
                metrics.follower_change = count - prev_count
        
        metrics.follower_count = count
        self._save_data()
    
    def get_daily_summary(self, date: str = None) -> Optional[DailyMetrics]:
        """Get metrics for a specific day"""
        if date is None:
            date = self._get_today_key()
        return self.daily_metrics.get(date)
    
    def get_weekly_summary(self) -> Dict[str, Any]:
        """Get summary for the past week"""
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        
        total_tweets = 0
        total_replies = 0
        total_likes = 0
        total_retweets = 0
        total_mentions = 0
        total_impressions = 0
        days_with_data = 0
        
        for i in range(7):
            date = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.daily_metrics:
                m = self.daily_metrics[date]
                total_tweets += m.tweets_posted
                total_replies += m.replies_sent
                total_likes += m.total_likes
                total_retweets += m.total_retweets
                total_mentions += m.mentions_received
                total_impressions += m.total_impressions
                days_with_data += 1
        
        avg_engagement_rate = 0
        if total_impressions > 0:
            avg_engagement_rate = (total_likes + total_retweets) / total_impressions
        
        return {
            "period": "7 days",
            "tweets_posted": total_tweets,
            "replies_sent": total_replies,
            "total_likes": total_likes,
            "total_retweets": total_retweets,
            "mentions_received": total_mentions,
            "avg_tweets_per_day": total_tweets / days_with_data if days_with_data > 0 else 0,
            "avg_engagement_rate": avg_engagement_rate,
            "days_with_data": days_with_data
        }
    
    def get_content_performance(self) -> Dict[str, Dict[str, Any]]:
        """Get performance by content type"""
        return {
            ct: {
                "count": m.count,
                "total_engagement": m.total_engagement,
                "avg_engagement": round(m.avg_engagement, 1)
            }
            for ct, m in self.content_metrics.items()
        }
    
    def get_best_performing_type(self) -> Optional[str]:
        """Get the best performing content type"""
        if not self.content_metrics:
            return None
        
        best = max(self.content_metrics.values(), key=lambda x: x.avg_engagement)
        return best.content_type if best.avg_engagement > 0 else None
    
    def get_growth_trend(self, days: int = 7) -> Dict[str, Any]:
        """Get growth trend over period"""
        dates = []
        followers = []
        engagement = []
        
        for i in range(days, -1, -1):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.daily_metrics:
                m = self.daily_metrics[date]
                dates.append(date)
                followers.append(m.follower_count)
                engagement.append(m.total_likes + m.total_retweets)
        
        # Calculate trends
        follower_trend = "stable"
        if len(followers) >= 2:
            if followers[-1] > followers[0]:
                follower_trend = "growing"
            elif followers[-1] < followers[0]:
                follower_trend = "declining"
        
        engagement_trend = "stable"
        if len(engagement) >= 2:
            avg_first_half = sum(engagement[:len(engagement)//2]) / max(1, len(engagement)//2)
            avg_second_half = sum(engagement[len(engagement)//2:]) / max(1, len(engagement) - len(engagement)//2)
            if avg_second_half > avg_first_half * 1.1:
                engagement_trend = "improving"
            elif avg_second_half < avg_first_half * 0.9:
                engagement_trend = "declining"
        
        return {
            "period_days": days,
            "follower_trend": follower_trend,
            "engagement_trend": engagement_trend,
            "data_points": len(dates)
        }
    
    def generate_insights(self) -> List[str]:
        """Generate actionable insights"""
        insights = []
        
        weekly = self.get_weekly_summary()
        trend = self.get_growth_trend()
        best_type = self.get_best_performing_type()
        
        # Tweet volume insight
        avg_tweets = weekly.get("avg_tweets_per_day", 0)
        if avg_tweets < 3:
            insights.append("posting volume is low. consider increasing to 5-10 tweets/day.")
        elif avg_tweets > 15:
            insights.append("high posting volume. quality over quantity might improve engagement.")
        
        # Engagement insight
        if trend["engagement_trend"] == "declining":
            insights.append("engagement declining. try different content types or posting times.")
        elif trend["engagement_trend"] == "improving":
            insights.append("engagement improving. keep doing what's working.")
        
        # Content type insight
        if best_type:
            insights.append(f"'{best_type}' content performs best. consider doing more of it.")
        
        # Reply rate insight
        mentions = weekly.get("mentions_received", 0)
        replies = weekly.get("replies_sent", 0)
        if mentions > 0:
            reply_rate = replies / mentions
            if reply_rate < 0.3:
                insights.append("low reply rate. engaging more could boost growth.")
        
        return insights
    
    def format_dashboard(self) -> str:
        """Format analytics as a text dashboard"""
        today = self.get_daily_summary()
        weekly = self.get_weekly_summary()
        trend = self.get_growth_trend()
        
        lines = ["📊 Performance Dashboard", ""]
        
        if today:
            lines.append(f"Today: {today.tweets_posted} tweets, {today.total_likes} likes")
        
        lines.append(f"Week: {weekly['tweets_posted']} tweets, {weekly['total_likes']} likes")
        lines.append(f"Trend: {trend['follower_trend']} followers, {trend['engagement_trend']} engagement")
        
        insights = self.generate_insights()
        if insights:
            lines.append("")
            lines.append("Insights:")
            for insight in insights[:3]:
                lines.append(f"• {insight}")
        
        return "\n".join(lines)


# Singleton
_analytics: Optional[PerformanceAnalytics] = None

def get_analytics() -> PerformanceAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = PerformanceAnalytics()
    return _analytics
