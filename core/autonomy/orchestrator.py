"""
Autonomy Orchestrator
Central controller that coordinates all autonomy modules
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class AutonomyOrchestrator:
    """
    Central orchestrator for all autonomy systems.
    Coordinates self-learning, memory, trending detection, etc.
    """
    
    def __init__(self):
        self._initialized = False
        self._running = False
        
        # Lazy-loaded modules
        self._self_learning = None
        self._memory_system = None
        self._reply_prioritizer = None
        self._trending_detector = None
        self._health_monitor = None
        self._content_calendar = None
        self._confidence_scorer = None
        self._alpha_detector = None
        self._voice_tuner = None
        self._thread_generator = None
        self._quote_strategy = None
        self._analytics = None
        self._news_detector = None
        self._sentiment_pipeline = None

    # =========================================================================
    # Module Accessors (lazy loading)
    # =========================================================================
    
    @property
    def learning(self):
        if self._self_learning is None:
            from core.autonomy.self_learning import get_self_learning
            self._self_learning = get_self_learning()
        return self._self_learning
    
    @property
    def memory(self):
        if self._memory_system is None:
            from core.autonomy.memory_system import get_memory_system
            self._memory_system = get_memory_system()
        return self._memory_system
    
    @property
    def prioritizer(self):
        if self._reply_prioritizer is None:
            from core.autonomy.reply_prioritizer import get_reply_prioritizer
            self._reply_prioritizer = get_reply_prioritizer()
        return self._reply_prioritizer
    
    @property
    def trending(self):
        if self._trending_detector is None:
            from core.autonomy.trending_detector import get_trending_detector
            self._trending_detector = get_trending_detector()
        return self._trending_detector
    
    @property
    def health(self):
        if self._health_monitor is None:
            from core.autonomy.health_monitor import get_health_monitor
            self._health_monitor = get_health_monitor()
        return self._health_monitor
    
    @property
    def calendar(self):
        if self._content_calendar is None:
            from core.autonomy.content_calendar import get_content_calendar
            self._content_calendar = get_content_calendar()
        return self._content_calendar
    
    @property
    def confidence(self):
        if self._confidence_scorer is None:
            from core.autonomy.confidence_scorer import get_confidence_scorer
            self._confidence_scorer = get_confidence_scorer()
        return self._confidence_scorer
    
    @property
    def alpha(self):
        if self._alpha_detector is None:
            from core.autonomy.alpha_detector import get_alpha_detector
            self._alpha_detector = get_alpha_detector()
        return self._alpha_detector
    
    @property
    def voice(self):
        if self._voice_tuner is None:
            from core.autonomy.voice_tuner import get_voice_tuner
            self._voice_tuner = get_voice_tuner()
        return self._voice_tuner
    
    @property
    def threads(self):
        if self._thread_generator is None:
            from core.autonomy.thread_generator import get_thread_generator
            self._thread_generator = get_thread_generator()
        return self._thread_generator
    
    @property
    def quotes(self):
        if self._quote_strategy is None:
            from core.autonomy.quote_strategy import get_quote_strategy
            self._quote_strategy = get_quote_strategy()
        return self._quote_strategy
    
    @property
    def analytics(self):
        if self._analytics is None:
            from core.autonomy.analytics import get_analytics
            self._analytics = get_analytics()
        return self._analytics

    @property
    def news(self):
        """News event detector for monitoring crypto news."""
        if self._news_detector is None:
            from core.autonomy.news_detector import get_news_detector
            self._news_detector = get_news_detector()
        return self._news_detector

    @property
    def sentiment_pipeline(self):
        """Sentiment trading pipeline for multi-source signal aggregation."""
        if self._sentiment_pipeline is None:
            from core.sentiment_trading import get_sentiment_pipeline
            self._sentiment_pipeline = get_sentiment_pipeline()
        return self._sentiment_pipeline

    # =========================================================================
    # Core Operations
    # =========================================================================
    
    async def initialize(self):
        """Initialize all autonomy systems"""
        if self._initialized:
            return
        
        logger.info("Initializing autonomy systems...")
        
        # Initialize core modules
        _ = self.learning
        _ = self.memory
        _ = self.analytics
        _ = self.health
        
        self._initialized = True
        logger.info("Autonomy systems initialized")
    
    async def run_background_tasks(self):
        """Run all background maintenance tasks"""
        tasks = []
        
        # Fetch engagement for recent tweets
        tasks.append(self._update_learning())
        
        # Scan for trends
        tasks.append(self._scan_trends())
        
        # Scan for alpha
        tasks.append(self._scan_alpha())

        # Scan for news events
        tasks.append(self._scan_news())

        # Scan sentiment pipeline
        tasks.append(self._scan_sentiment())

        # Health checks
        tasks.append(self._run_health_checks())
        
        # Cleanup old data
        tasks.append(self._cleanup())
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _update_learning(self):
        """Update learning from recent engagement"""
        try:
            self.learning.analyze_patterns()
        except Exception as e:
            logger.debug(f"Learning update error: {e}")
    
    async def _scan_trends(self):
        """Scan for trending topics"""
        try:
            if self.trending.should_scan():
                await self.trending.scan_for_trends()
        except Exception as e:
            logger.debug(f"Trend scan error: {e}")
    
    async def _scan_alpha(self):
        """Scan for alpha opportunities"""
        try:
            await self.alpha.scan_for_alpha()
        except Exception as e:
            logger.debug(f"Alpha scan error: {e}")

    async def _scan_news(self):
        """Scan for news events"""
        try:
            await self.news.scan_news()
            # Process high priority alerts
            await self.news.process_alerts()
        except Exception as e:
            logger.debug(f"News scan error: {e}")

    async def _scan_sentiment(self):
        """Scan sentiment pipeline for trading signals"""
        try:
            signals = await self.sentiment_pipeline.scan_all_sources()
            if signals:
                logger.info(f"Sentiment pipeline found {len(signals)} signals")
        except Exception as e:
            logger.debug(f"Sentiment pipeline error: {e}")

    async def _run_health_checks(self):
        """Run health checks"""
        try:
            await self.health.run_all_checks()
        except Exception as e:
            logger.debug(f"Health check error: {e}")
    
    async def _cleanup(self):
        """Cleanup old data"""
        try:
            self.memory.cleanup_old_conversations(days=7)
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
    
    # =========================================================================
    # Content Decision Making
    # =========================================================================
    
    def get_content_recommendations(self) -> Dict[str, Any]:
        """
        Get comprehensive content recommendations based on all systems.
        """
        recommendations = {
            "should_post": True,
            "optimal_time": self.calendar.is_optimal_time(),
            "content_types": [],
            "topics": [],
            "warnings": [],
            "insights": []
        }
        
        # Learning recommendations
        learning_recs = self.learning.get_recommendations()
        if not learning_recs.get("should_post", True):
            recommendations["warnings"].append("Learning suggests suboptimal time")
        recommendations["content_types"].extend(learning_recs.get("recommended_content_types", []))
        recommendations["topics"].extend(learning_recs.get("hot_topics", []))
        
        # Calendar recommendations
        calendar_suggestions = self.calendar.get_content_suggestions()
        for suggestion in calendar_suggestions[:2]:
            if suggestion.get("type"):
                recommendations["content_types"].append(suggestion["type"])
        
        # Alpha signals
        alpha_signals = self.alpha.get_actionable_signals(50)
        for signal in alpha_signals[:2]:
            recommendations["topics"].append(signal.token)
        
        # Trending topics
        hot_topics = self.trending.get_hot_topics(60)
        for topic in hot_topics[:2]:
            recommendations["topics"].append(topic.topic)
        
        # Confidence adjustment
        if self.confidence.should_be_conservative():
            recommendations["warnings"].append("Recent accuracy low - be conservative")
        
        # Analytics insights
        recommendations["insights"] = self.analytics.generate_insights()
        
        # Deduplicate
        recommendations["content_types"] = list(dict.fromkeys(recommendations["content_types"]))[:5]
        recommendations["topics"] = list(dict.fromkeys(recommendations["topics"]))[:5]
        
        return recommendations
    
    def should_reply_to_mention(self, mention: Dict[str, Any]) -> tuple:
        """
        Decide if we should reply to a mention.
        
        Returns: (should_reply, priority_score, reason)
        """
        # Get user memory
        user_memory = self.memory.get_user(mention.get("user_id", ""))
        
        # Score the mention
        score = self.prioritizer.score_mention(
            tweet_id=mention.get("id", ""),
            user_id=mention.get("user_id", ""),
            username=mention.get("username", ""),
            text=mention.get("text", ""),
            follower_count=mention.get("follower_count", 0),
            is_verified=mention.get("is_verified", False),
            user_memory=user_memory
        )
        
        return score.should_reply, score.priority_score, score.skip_reason
    
    def get_voice_for_context(
        self,
        context: str,
        market_condition: str = None,
        user_memory = None
    ) -> str:
        """Get tuned voice prompt for context"""
        user_adjustments = self.voice.get_voice_for_user(user_memory)
        return self.voice.get_tuned_prompt(
            context=context,
            market_condition=market_condition,
            extra_context=user_adjustments.get("extra_context", "")
        )
    
    # =========================================================================
    # Recording & Tracking
    # =========================================================================
    
    def record_tweet_posted(
        self,
        tweet_id: str,
        content: str,
        content_type: str,
        topics: List[str] = None
    ):
        """Record that a tweet was posted"""
        # Learning
        self.learning.record_tweet(
            tweet_id=tweet_id,
            content=content,
            content_type=content_type,
            topics=topics or []
        )
        
        # Analytics
        self.analytics.record_tweet(tweet_id, content_type)
    
    def record_reply_sent(
        self,
        tweet_id: str,
        user_id: str,
        username: str
    ):
        """Record that we sent a reply"""
        # Memory
        self.memory.remember_user(user_id, username)
        
        # Prioritizer
        self.prioritizer.mark_replied(tweet_id)
        
        # Analytics
        self.analytics.record_reply()
    
    def record_mention_received(
        self,
        user_id: str,
        username: str,
        replied: bool = False
    ):
        """Record that we received a mention"""
        self.memory.remember_user(user_id, username)
        self.analytics.record_mention(replied)
    
    # =========================================================================
    # Status & Reporting
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get full autonomy status"""
        return {
            "initialized": self._initialized,
            "running": self._running,
            "health": self.health.get_status_summary(),
            "learning": {
                "tweets_tracked": len(self.learning.performance_history),
                "best_hours": self.learning.insights.best_hours,
                "best_types": self.learning.insights.best_content_types
            },
            "memory": {
                "users_known": len(self.memory.users),
                "conversations": len(self.memory.conversations)
            },
            "confidence": self.confidence.get_accuracy_stats(),
            "analytics": self.analytics.get_weekly_summary(),
            "reply_stats": self.prioritizer.get_reply_stats(),
            "quote_stats": self.quotes.get_quote_stats()
        }
    
    def format_status_report(self) -> str:
        """Format status as readable report"""
        status = self.get_status()
        
        lines = [
            "🤖 Jarvis Autonomy Status",
            "",
            f"Health: {status['health']['overall']}",
            f"Users Known: {status['memory']['users_known']}",
            f"Tweets Tracked: {status['learning']['tweets_tracked']}",
            "",
            f"Accuracy: {status['confidence'].get('message', 'no data')}",
            "",
            self.analytics.format_dashboard()
        ]
        
        return "\n".join(lines)


# Singleton
_orchestrator: Optional[AutonomyOrchestrator] = None

def get_orchestrator() -> AutonomyOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AutonomyOrchestrator()
    return _orchestrator
