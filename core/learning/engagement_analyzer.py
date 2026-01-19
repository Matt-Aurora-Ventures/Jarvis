"""
Engagement Analyzer - Learns what content performs best.

Analyzes:
- Tweet engagement (likes, retweets, replies)
- Telegram response quality
- Topic performance
- Optimal posting times
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ContentMetrics:
    """Performance metrics for a piece of content."""
    content_id: str
    category: str
    platform: str  # "twitter" or "telegram"
    posted_at: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    engagement_rate: float = 0.0
    quality_score: float = 0.0  # 0-100 calculated by analyzer


class EngagementAnalyzer:
    """
    Autonomous learning engine that improves Jarvis by analyzing what works.

    Learns:
    - Which tweet categories perform best
    - Optimal posting frequency
    - Topics with highest engagement
    - Time-of-day patterns
    """

    def __init__(self, data_dir: str = "data/learning"):
        """Initialize analyzer."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.metrics: List[ContentMetrics] = []
        self.category_performance: Dict[str, float] = {}  # category -> avg engagement
        self.optimal_posting_time: Optional[str] = None

        self._load_historical_data()

    def record_engagement(
        self,
        content_id: str,
        category: str,
        platform: str,
        likes: int,
        retweets: int = 0,
        replies: int = 0
    ) -> ContentMetrics:
        """Record engagement metrics for content."""
        metric = ContentMetrics(
            content_id=content_id,
            category=category,
            platform=platform,
            posted_at=datetime.now(timezone.utc).isoformat(),
            likes=likes,
            retweets=retweets,
            replies=replies,
        )

        # Calculate engagement rate
        total_interactions = likes + retweets + replies
        if total_interactions > 0:
            metric.engagement_rate = total_interactions / max(1, likes + retweets)  # Interactions / impressions est.

        # Quality score (0-100)
        metric.quality_score = min(100, (likes * 0.5 + retweets * 1.0 + replies * 1.5))

        self.metrics.append(metric)

        # Update category performance
        self._update_category_performance(category, metric.quality_score)

        logger.info(f"Recorded engagement: {category} - Score: {metric.quality_score:.1f}")

        return metric

    def _update_category_performance(self, category: str, score: float):
        """Update running average for category."""
        if category not in self.category_performance:
            self.category_performance[category] = score
        else:
            # Exponential moving average (more weight to recent)
            self.category_performance[category] = 0.7 * score + 0.3 * self.category_performance[category]

    def get_top_categories(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get best-performing content categories."""
        if not self.category_performance:
            return []

        sorted_categories = sorted(
            self.category_performance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_categories[:top_n]

    def get_category_weights(self) -> Dict[str, float]:
        """
        Get normalized category weights for content generation.

        Higher scores = more likely to be chosen.
        Used by autonomous engine to adjust tweet frequency.

        Returns:
            Dict of category -> weight (0.0 - 1.0)
        """
        if not self.category_performance:
            return {}

        total = sum(self.category_performance.values())
        if total == 0:
            return {}

        return {
            cat: score / total
            for cat, score in self.category_performance.items()
        }

    def analyze_optimal_posting_time(self) -> Optional[Dict]:
        """Analyze what time of day gets best engagement."""
        try:
            if len(self.metrics) < 10:
                return None  # Need more data

            # Group by hour
            hourly_engagement = {}
            for metric in self.metrics:
                try:
                    posted = datetime.fromisoformat(metric.posted_at)
                    hour = posted.hour
                    if hour not in hourly_engagement:
                        hourly_engagement[hour] = []

                    hourly_engagement[hour].append(metric.quality_score)
                except (ValueError, AttributeError):
                    pass

            if not hourly_engagement:
                return None

            # Find best hour
            best_hour = max(
                hourly_engagement.items(),
                key=lambda x: statistics.mean(x[1])
            )[0]

            avg_by_hour = {
                hour: statistics.mean(scores)
                for hour, scores in hourly_engagement.items()
            }

            return {
                "best_hour_utc": best_hour,
                "avg_engagement_by_hour": avg_by_hour,
                "recommendation": f"Post around {best_hour}:00 UTC for best engagement"
            }

        except Exception as e:
            logger.error(f"Optimal time analysis failed: {e}")
            return None

    def get_improvement_recommendations(self) -> List[str]:
        """
        Generate recommendations for improving content.

        Returns:
            List of actionable suggestions
        """
        recommendations = []

        # Analyze what's working
        top_categories = self.get_top_categories(3)
        if top_categories:
            top_names = [cat for cat, _ in top_categories]
            recommendations.append(f"Focus on {top_names[0]}, {top_names[1]} content - highest engagement")

        # Time of day recommendation
        time_analysis = self.analyze_optimal_posting_time()
        if time_analysis:
            recommendations.append(time_analysis["recommendation"])

        # Low performer recommendation
        worst_categories = self.get_top_categories(top_n=100)[-3:] if self.category_performance else []
        if worst_categories:
            worst_names = [cat for cat, _ in worst_categories]
            recommendations.append(f"Reduce {worst_names[-1]} content - lowest engagement")

        # Volume recommendation
        if len(self.metrics) > 20:
            avg_likes = statistics.mean([m.likes for m in self.metrics[-20:]])
            if avg_likes < 5:
                recommendations.append("Engagement is low - try higher quality content or different times")
            elif avg_likes > 50:
                recommendations.append("Engagement is strong - maintain current content strategy")

        return recommendations

    def should_post_now(self, category: str) -> bool:
        """
        Intelligent posting decision.

        Should we post this category right now based on:
        - Performance history
        - Time of day
        - Recent post frequency

        Returns:
            True if good time to post
        """
        try:
            # Check posting frequency (don't spam)
            if len(self.metrics) > 0:
                last_post = datetime.fromisoformat(self.metrics[-1].posted_at)
                minutes_since_last = (datetime.now(timezone.utc) - last_post).total_seconds() / 60

                if minutes_since_last < 5:  # Min 5 min between posts
                    return False

            # Check optimal time
            time_analysis = self.analyze_optimal_posting_time()
            if time_analysis:
                current_hour = datetime.now(timezone.utc).hour
                best_hour = time_analysis["best_hour_utc"]

                # Post if within 2 hours of best time
                hour_diff = min(abs(current_hour - best_hour), 24 - abs(current_hour - best_hour))
                if hour_diff > 3:
                    return False  # Not optimal time, but don't block

            # Check category performance
            category_weights = self.get_category_weights()
            category_weight = category_weights.get(category, 0.0)

            # Categories with 0 weight are new/untested, so post them to learn
            if category_weight == 0.0:
                return True

            # Post high-performing categories more often
            if category_weight > 0.15:  # Top performer
                return True

            return True  # Default to posting

        except Exception as e:
            logger.error(f"Posting decision failed: {e}")
            return True  # Default to posting on error

    def _load_historical_data(self):
        """Load previous engagement metrics."""
        try:
            metrics_file = self.data_dir / "engagement_metrics.json"
            if metrics_file.exists():
                with open(metrics_file) as f:
                    data = json.load(f)

                for metric_data in data.get("metrics", []):
                    metric = ContentMetrics(**metric_data)
                    self.metrics.append(metric)
                    self._update_category_performance(metric.category, metric.quality_score)

                self.category_performance = data.get("category_performance", {})
                logger.info(f"Loaded {len(self.metrics)} historical metrics")

        except Exception as e:
            logger.error(f"Failed to load historical metrics: {e}")

    def save_state(self):
        """Persist learning data."""
        try:
            data = {
                "metrics": [
                    {
                        "content_id": m.content_id,
                        "category": m.category,
                        "platform": m.platform,
                        "posted_at": m.posted_at,
                        "likes": m.likes,
                        "retweets": m.retweets,
                        "replies": m.replies,
                        "engagement_rate": m.engagement_rate,
                        "quality_score": m.quality_score,
                    }
                    for m in self.metrics[-1000:]  # Keep last 1000
                ],
                "category_performance": self.category_performance,
            }

            with open(self.data_dir / "engagement_metrics.json", "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save learning state: {e}")

    def get_summary(self) -> Dict:
        """Get learning summary for display."""
        return {
            "total_metrics_recorded": len(self.metrics),
            "top_categories": self.get_top_categories(3),
            "recommendations": self.get_improvement_recommendations(),
            "category_weights": self.get_category_weights(),
        }
