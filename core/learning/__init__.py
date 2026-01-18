"""
Self-Improvement Learning System

Analyzes performance metrics and autonomously improves Jarvis:
- Engagement analysis (which tweets/responses work best)
- Content optimization (adjust category weights)
- A/B testing (test variants)
- User satisfaction tracking
"""

from .engagement_analyzer import EngagementAnalyzer
from .content_optimizer import ContentOptimizer

__all__ = ["EngagementAnalyzer", "ContentOptimizer"]
