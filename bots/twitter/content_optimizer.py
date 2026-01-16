"""Content optimizer for the Twitter autonomous engine."""

import logging
import random
from typing import Dict, List

from bots.twitter.engagement_tracker import get_engagement_tracker

logger = logging.getLogger(__name__)


class ContentOptimizer:
    """Weight content types by recent engagement performance."""

    def __init__(self, tracker=None):
        self._tracker = tracker or get_engagement_tracker()

    def _get_weights(self, content_types: List[str], hours: int = 168) -> Dict[str, float]:
        performance = self._tracker.get_category_performance(hours=hours)
        weights: Dict[str, float] = {}

        for content_type in content_types:
            stats = performance.get(content_type, {}) if performance else {}
            avg_likes = stats.get("avg_likes", 0) or 0
            avg_retweets = stats.get("avg_retweets", 0) or 0
            avg_replies = stats.get("avg_replies", 0) or 0

            engagement_score = avg_likes + (avg_retweets * 2) + (avg_replies * 3)
            weight = 1.0 + min(engagement_score / 5.0, 5.0)
            weights[content_type] = max(weight, 0.1)

        return weights

    def choose_type(self, content_types: List[str], hours: int = 168) -> str:
        """Return a weighted random content type selection."""
        if not content_types:
            return ""

        weights = self._get_weights(content_types, hours=hours)
        try:
            return random.choices(
                content_types,
                weights=[weights.get(t, 1.0) for t in content_types],
                k=1,
            )[0]
        except Exception as exc:
            logger.debug(f"Content optimizer fallback: {exc}")
            return random.choice(content_types)
