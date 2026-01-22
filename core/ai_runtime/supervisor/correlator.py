"""
Insight Correlator

Correlates insights from multiple agents to find patterns.
"""
import logging
from typing import List, Dict, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class InsightCorrelator:
    """
    Correlates insights from different agents to find system-wide patterns.
    """

    def __init__(self, correlation_window_minutes: int = 5):
        self.correlation_window = timedelta(minutes=correlation_window_minutes)
        self._insight_buffer: List[Dict[str, Any]] = []

    def add_insight(self, insight: Dict[str, Any]):
        """Add an insight to the correlation buffer."""
        insight["correlation_time"] = datetime.utcnow()
        self._insight_buffer.append(insight)

        # Prune old insights
        cutoff = datetime.utcnow() - self.correlation_window
        self._insight_buffer = [
            i for i in self._insight_buffer if i["correlation_time"] > cutoff
        ]

    def find_error_clusters(self) -> List[Dict[str, Any]]:
        """
        Find clusters of related errors across agents.

        Returns list of error clusters with evidence.
        """
        errors = [
            i
            for i in self._insight_buffer
            if i.get("payload", {}).get("insight", {}).get("insight_type") == "error"
        ]

        if len(errors) < 2:
            return []

        # Group by similarity (simple implementation - can be enhanced)
        clusters: Dict[str, List[Dict]] = defaultdict(list)
        for error in errors:
            summary = error.get("payload", {}).get("insight", {}).get("summary", "")
            # Use first 30 chars as cluster key
            cluster_key = summary[:30]
            clusters[cluster_key].append(error)

        # Return clusters with 2+ errors
        result = []
        for key, cluster in clusters.items():
            if len(cluster) >= 2:
                result.append(
                    {
                        "cluster_key": key,
                        "error_count": len(cluster),
                        "agents": list(set(e.get("agent") for e in cluster)),
                        "evidence": cluster,
                        "first_seen": min(
                            e["correlation_time"] for e in cluster
                        ).isoformat(),
                        "last_seen": max(
                            e["correlation_time"] for e in cluster
                        ).isoformat(),
                    }
                )

        return result

    def find_patterns(self) -> List[Dict[str, Any]]:
        """
        Find patterns in insights across agents.

        Returns list of detected patterns.
        """
        patterns = []

        # Pattern 1: High latency across multiple components
        latency_insights = [
            i
            for i in self._insight_buffer
            if i.get("payload", {}).get("insight", {}).get("insight_type") == "metric"
            and "latency" in str(i.get("payload", {})).lower()
        ]

        if len(latency_insights) >= 2:
            agents = list(set(i.get("agent") for i in latency_insights))
            patterns.append(
                {
                    "pattern_type": "latency_spike",
                    "affected_agents": agents,
                    "count": len(latency_insights),
                    "evidence": latency_insights,
                }
            )

        # Pattern 2: Repeated suggestions of same type
        suggestions = [
            i
            for i in self._insight_buffer
            if i.get("payload", {}).get("insight", {}).get("insight_type")
            == "suggestion"
        ]

        suggestion_types: Dict[str, List] = defaultdict(list)
        for sug in suggestions:
            summary = sug.get("payload", {}).get("insight", {}).get("summary", "")
            # Group by first 20 chars
            key = summary[:20]
            suggestion_types[key].append(sug)

        for key, items in suggestion_types.items():
            if len(items) >= 2:
                patterns.append(
                    {
                        "pattern_type": "repeated_suggestion",
                        "suggestion_summary": key,
                        "count": len(items),
                        "evidence": items,
                    }
                )

        return patterns

    def get_agent_activity(self) -> Dict[str, int]:
        """Get activity count by agent."""
        activity: Dict[str, int] = defaultdict(int)
        for insight in self._insight_buffer:
            agent = insight.get("agent", "unknown")
            activity[agent] += 1
        return dict(activity)

    def clear_buffer(self):
        """Clear the insight buffer."""
        self._insight_buffer = []

    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self._insight_buffer)
