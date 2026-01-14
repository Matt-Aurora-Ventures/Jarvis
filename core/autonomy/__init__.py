"""
Jarvis Autonomy Module
Full autonomous operation capabilities
"""

from core.autonomy.self_learning import SelfLearning, get_self_learning
from core.autonomy.memory_system import MemorySystem, get_memory_system
from core.autonomy.reply_prioritizer import ReplyPrioritizer, get_reply_prioritizer
from core.autonomy.trending_detector import TrendingDetector, get_trending_detector
from core.autonomy.health_monitor import AutonomyHealthMonitor, get_health_monitor
from core.autonomy.content_calendar import ContentCalendar, get_content_calendar
from core.autonomy.confidence_scorer import ConfidenceScorer, get_confidence_scorer
from core.autonomy.alpha_detector import AlphaDetector, get_alpha_detector
from core.autonomy.voice_tuner import VoiceTuner, get_voice_tuner
from core.autonomy.thread_generator import ThreadGenerator, get_thread_generator
from core.autonomy.quote_strategy import QuoteStrategy, get_quote_strategy
from core.autonomy.analytics import PerformanceAnalytics, get_analytics
from core.autonomy.news_detector import NewsEventDetector, get_news_detector

__all__ = [
    "SelfLearning", "get_self_learning",
    "MemorySystem", "get_memory_system", 
    "ReplyPrioritizer", "get_reply_prioritizer",
    "TrendingDetector", "get_trending_detector",
    "AutonomyHealthMonitor", "get_health_monitor",
    "ContentCalendar", "get_content_calendar",
    "ConfidenceScorer", "get_confidence_scorer",
    "AlphaDetector", "get_alpha_detector",
    "VoiceTuner", "get_voice_tuner",
    "ThreadGenerator", "get_thread_generator",
    "QuoteStrategy", "get_quote_strategy",
    "PerformanceAnalytics", "get_analytics",
    "NewsEventDetector", "get_news_detector",
]
