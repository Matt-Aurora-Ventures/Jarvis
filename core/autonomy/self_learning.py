"""
Self-Learning Loop
Tracks tweet engagement and learns what works
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "learning"
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TweetPerformance:
    """Track performance of a single tweet"""
    tweet_id: str
    content: str
    content_type: str  # market, sentiment, engagement, reply, etc.
    posted_at: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    impressions: int = 0
    engagement_rate: float = 0.0
    score: float = 0.0
    topics: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    hour_posted: int = 0
    day_of_week: int = 0
    
    def calculate_score(self):
        """Calculate engagement score (weighted)"""
        # Replies are most valuable, then RTs, then likes
        self.score = (self.replies * 3) + (self.retweets * 2) + self.likes
        if self.impressions > 0:
            self.engagement_rate = (self.likes + self.retweets + self.replies) / self.impressions
        return self.score


@dataclass
class LearningInsights:
    """Aggregated learning insights"""
    best_hours: List[int] = field(default_factory=list)
    best_days: List[int] = field(default_factory=list)
    best_topics: List[str] = field(default_factory=list)
    best_content_types: List[str] = field(default_factory=list)
    avg_engagement_rate: float = 0.0
    top_performing_patterns: List[str] = field(default_factory=list)
    avoid_patterns: List[str] = field(default_factory=list)


class SelfLearning:
    """
    Self-learning system that tracks what works and adapts.
    Uses engagement data to improve content generation.
    """
    
    def __init__(self):
        self.performance_file = DATA_DIR / "tweet_performance.json"
        self.insights_file = DATA_DIR / "learning_insights.json"
        self.performance_history: List[TweetPerformance] = []
        self.insights = LearningInsights()
        self._load_data()
    
    def _load_data(self):
        """Load historical performance data"""
        try:
            if self.performance_file.exists():
                data = json.loads(self.performance_file.read_text())
                self.performance_history = [
                    TweetPerformance(**p) for p in data
                ]
            if self.insights_file.exists():
                data = json.loads(self.insights_file.read_text())
                self.insights = LearningInsights(**data)
        except Exception as e:
            logger.error(f"Error loading learning data: {e}")
    
    def _save_data(self):
        """Save performance data"""
        try:
            self.performance_file.write_text(json.dumps(
                [asdict(p) for p in self.performance_history[-1000:]],  # Keep last 1000
                indent=2
            ))
            self.insights_file.write_text(json.dumps(asdict(self.insights), indent=2))
        except Exception as e:
            logger.error(f"Error saving learning data: {e}")
    
    def record_tweet(
        self,
        tweet_id: str,
        content: str,
        content_type: str,
        topics: List[str] = None,
        sentiment: str = "neutral"
    ):
        """Record a new tweet for tracking"""
        now = datetime.utcnow()
        perf = TweetPerformance(
            tweet_id=tweet_id,
            content=content,
            content_type=content_type,
            posted_at=now.isoformat(),
            topics=topics or [],
            sentiment=sentiment,
            hour_posted=now.hour,
            day_of_week=now.weekday()
        )
        self.performance_history.append(perf)
        self._save_data()
        logger.info(f"Recorded tweet {tweet_id} for learning")
    
    async def update_engagement(self, tweet_id: str, likes: int, retweets: int, replies: int, impressions: int = 0):
        """Update engagement metrics for a tweet"""
        for perf in self.performance_history:
            if perf.tweet_id == tweet_id:
                perf.likes = likes
                perf.retweets = retweets
                perf.replies = replies
                perf.impressions = impressions
                perf.calculate_score()
                self._save_data()
                logger.info(f"Updated engagement for {tweet_id}: score={perf.score:.1f}")
                return perf
        return None
    
    async def fetch_recent_engagement(self, twitter_client) -> int:
        """Fetch engagement for recent tweets"""
        updated = 0
        # Get tweets from last 24 hours that need updating
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        for perf in self.performance_history:
            try:
                posted = datetime.fromisoformat(perf.posted_at)
                if posted > cutoff and perf.score == 0:
                    # Fetch from Twitter API
                    metrics = await twitter_client.get_tweet_metrics(perf.tweet_id)
                    if metrics:
                        await self.update_engagement(
                            perf.tweet_id,
                            metrics.get("like_count", 0),
                            metrics.get("retweet_count", 0),
                            metrics.get("reply_count", 0),
                            metrics.get("impression_count", 0)
                        )
                        updated += 1
            except Exception as e:
                logger.debug(f"Could not fetch metrics for {perf.tweet_id}: {e}")
        
        return updated
    
    def analyze_patterns(self) -> LearningInsights:
        """Analyze performance patterns to generate insights"""
        if len(self.performance_history) < 10:
            logger.info("Not enough data for pattern analysis")
            return self.insights
        
        # Analyze by hour
        hour_scores = {}
        for perf in self.performance_history:
            hour = perf.hour_posted
            if hour not in hour_scores:
                hour_scores[hour] = []
            hour_scores[hour].append(perf.score)
        
        # Find best hours (top 3)
        avg_by_hour = {h: sum(s)/len(s) for h, s in hour_scores.items() if s}
        self.insights.best_hours = sorted(avg_by_hour.keys(), key=lambda h: avg_by_hour[h], reverse=True)[:3]
        
        # Analyze by day
        day_scores = {}
        for perf in self.performance_history:
            day = perf.day_of_week
            if day not in day_scores:
                day_scores[day] = []
            day_scores[day].append(perf.score)
        
        avg_by_day = {d: sum(s)/len(s) for d, s in day_scores.items() if s}
        self.insights.best_days = sorted(avg_by_day.keys(), key=lambda d: avg_by_day[d], reverse=True)[:3]
        
        # Analyze by content type
        type_scores = {}
        for perf in self.performance_history:
            ct = perf.content_type
            if ct not in type_scores:
                type_scores[ct] = []
            type_scores[ct].append(perf.score)
        
        avg_by_type = {t: sum(s)/len(s) for t, s in type_scores.items() if s}
        self.insights.best_content_types = sorted(avg_by_type.keys(), key=lambda t: avg_by_type[t], reverse=True)[:3]
        
        # Analyze by topic
        topic_scores = {}
        for perf in self.performance_history:
            for topic in perf.topics:
                if topic not in topic_scores:
                    topic_scores[topic] = []
                topic_scores[topic].append(perf.score)
        
        avg_by_topic = {t: sum(s)/len(s) for t, s in topic_scores.items() if len(s) >= 3}
        self.insights.best_topics = sorted(avg_by_topic.keys(), key=lambda t: avg_by_topic[t], reverse=True)[:5]
        
        # Calculate overall avg engagement
        total_engagement = sum(p.engagement_rate for p in self.performance_history if p.engagement_rate > 0)
        count_with_engagement = len([p for p in self.performance_history if p.engagement_rate > 0])
        if count_with_engagement > 0:
            self.insights.avg_engagement_rate = total_engagement / count_with_engagement
        
        # Find top performing patterns (content snippets from high performers)
        top_tweets = sorted(self.performance_history, key=lambda p: p.score, reverse=True)[:10]
        self.insights.top_performing_patterns = [t.content[:100] for t in top_tweets if t.score > 0]
        
        # Find patterns to avoid (bottom performers)
        bottom_tweets = sorted(self.performance_history, key=lambda p: p.score)[:5]
        self.insights.avoid_patterns = [t.content[:100] for t in bottom_tweets if t.score == 0]
        
        self._save_data()
        logger.info(f"Pattern analysis complete. Best hours: {self.insights.best_hours}")
        return self.insights
    
    def get_recommendations(self) -> Dict[str, Any]:
        """Get content recommendations based on learning"""
        self.analyze_patterns()
        
        now = datetime.utcnow()
        current_hour = now.hour
        current_day = now.weekday()
        
        # Is now a good time to post?
        is_good_hour = current_hour in self.insights.best_hours if self.insights.best_hours else True
        is_good_day = current_day in self.insights.best_days if self.insights.best_days else True
        
        return {
            "should_post": is_good_hour and is_good_day,
            "is_optimal_time": is_good_hour,
            "recommended_content_types": self.insights.best_content_types,
            "hot_topics": self.insights.best_topics,
            "avg_engagement_rate": self.insights.avg_engagement_rate,
            "best_hours_utc": self.insights.best_hours,
            "best_days": self.insights.best_days,
            "top_patterns": self.insights.top_performing_patterns[:3],
        }
    
    def get_content_type_weight(self, content_type: str) -> float:
        """Get weight for content type based on historical performance"""
        if not self.insights.best_content_types:
            return 1.0
        
        if content_type in self.insights.best_content_types:
            idx = self.insights.best_content_types.index(content_type)
            return 1.5 - (idx * 0.2)  # 1.5, 1.3, 1.1 for top 3
        return 0.8  # Lower weight for non-performing types


# Singleton
_self_learning: Optional[SelfLearning] = None

def get_self_learning() -> SelfLearning:
    global _self_learning
    if _self_learning is None:
        _self_learning = SelfLearning()
    return _self_learning
