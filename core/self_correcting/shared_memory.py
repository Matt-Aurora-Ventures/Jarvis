"""
Shared Memory System for Self-Correcting AI

Centralized learning and memory system that all bot components can access.
Bots can store learnings, retrieve relevant past experiences, and adapt behavior.

Features:
- Persistent storage of learnings across sessions
- Semantic search for relevant past experiences
- Performance metrics tracking
- Auto-pruning of outdated/invalid learnings
- Thread-safe access
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading


logger = logging.getLogger("jarvis.shared_memory")


class LearningType(Enum):
    """Types of learnings that can be stored."""
    SUCCESS_PATTERN = "success_pattern"  # What worked
    FAILURE_PATTERN = "failure_pattern"  # What failed (avoid)
    OPTIMIZATION = "optimization"  # Performance improvement
    USER_PREFERENCE = "user_preference"  # User preferences discovered
    MARKET_INSIGHT = "market_insight"  # Trading insights
    ERROR_FIX = "error_fix"  # How errors were resolved
    BEHAVIORAL_ADJUSTMENT = "behavioral_adjustment"  # Bot behavior changes


@dataclass
class Learning:
    """A single learning entry."""
    id: str  # Unique identifier
    type: LearningType
    component: str  # Which bot/component learned this
    content: str  # The actual learning
    context: Dict[str, Any]  # Contextual data
    timestamp: datetime
    confidence: float  # 0.0-1.0, how confident we are
    success_rate: float  # Track if this learning actually helps
    usage_count: int = 0  # How many times applied
    last_used: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "component": self.component,
            "content": self.content,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Learning':
        """Create from dict."""
        return cls(
            id=data["id"],
            type=LearningType(data["type"]),
            component=data["component"],
            content=data["content"],
            context=data["context"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            confidence=data["confidence"],
            success_rate=data["success_rate"],
            usage_count=data.get("usage_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None
        )


class SharedMemory:
    """
    Shared memory system for all bot components.

    Thread-safe, persistent storage of learnings and insights.
    """

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.learnings_file = self.storage_path / "learnings.json"
        self.metrics_file = self.storage_path / "metrics.json"

        self.learnings: Dict[str, Learning] = {}
        self.metrics: Dict[str, Any] = {
            "total_learnings": 0,
            "total_queries": 0,
            "successful_applications": 0,
            "failed_applications": 0,
            "components": {}
        }

        self._lock = threading.Lock()

        # Load existing data
        self._load()

        logger.info(f"SharedMemory initialized with {len(self.learnings)} learnings")

    def _load(self):
        """Load learnings from disk."""
        if self.learnings_file.exists():
            try:
                with open(self.learnings_file, 'r') as f:
                    data = json.load(f)
                    for learning_dict in data:
                        learning = Learning.from_dict(learning_dict)
                        self.learnings[learning.id] = learning
                logger.info(f"Loaded {len(self.learnings)} learnings from disk")
            except Exception as e:
                logger.error(f"Failed to load learnings: {e}")

        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    self.metrics = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")

    def _save(self):
        """Save learnings to disk."""
        try:
            # Save learnings
            learnings_list = [l.to_dict() for l in self.learnings.values()]
            with open(self.learnings_file, 'w') as f:
                json.dump(learnings_list, f, indent=2)

            # Save metrics
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save learnings: {e}")

    def add_learning(
        self,
        component: str,
        learning_type: LearningType,
        content: str,
        context: Dict[str, Any] = None,
        confidence: float = 0.8
    ) -> str:
        """
        Add a new learning to shared memory.

        Returns the learning ID.
        """
        with self._lock:
            import uuid
            learning_id = str(uuid.uuid4())

            learning = Learning(
                id=learning_id,
                type=learning_type,
                component=component,
                content=content,
                context=context or {},
                timestamp=datetime.now(),
                confidence=confidence,
                success_rate=0.5,  # Start neutral
                usage_count=0
            )

            self.learnings[learning_id] = learning

            # Update metrics
            self.metrics["total_learnings"] += 1
            if component not in self.metrics["components"]:
                self.metrics["components"][component] = 0
            self.metrics["components"][component] += 1

            self._save()

            logger.info(f"[{component}] Added {learning_type.value} learning: {content[:100]}")
            return learning_id

    def search_learnings(
        self,
        query: str = None,
        component: str = None,
        learning_type: LearningType = None,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Learning]:
        """
        Search for relevant learnings.

        Simple keyword-based search for now. Could upgrade to semantic search later.
        """
        with self._lock:
            self.metrics["total_queries"] += 1

            results = []

            for learning in self.learnings.values():
                # Filter by criteria
                if component and learning.component != component:
                    continue
                if learning_type and learning.type != learning_type:
                    continue
                if learning.confidence < min_confidence:
                    continue

                # Simple keyword matching if query provided
                if query:
                    query_lower = query.lower()
                    if query_lower not in learning.content.lower():
                        # Also check context
                        context_str = json.dumps(learning.context).lower()
                        if query_lower not in context_str:
                            continue

                results.append(learning)

            # Sort by relevance (confidence * success_rate * recency)
            def score_learning(l: Learning) -> float:
                recency = 1.0 / (1 + (datetime.now() - l.timestamp).days)
                return l.confidence * l.success_rate * (1 + recency)

            results.sort(key=score_learning, reverse=True)

            return results[:limit]

    def mark_success(self, learning_id: str):
        """Mark a learning as successfully applied."""
        with self._lock:
            if learning_id in self.learnings:
                learning = self.learnings[learning_id]
                learning.usage_count += 1
                learning.last_used = datetime.now()

                # Update success rate (exponential moving average)
                alpha = 0.2
                learning.success_rate = alpha * 1.0 + (1 - alpha) * learning.success_rate

                self.metrics["successful_applications"] += 1
                self._save()

                logger.debug(f"Marked learning {learning_id} as successful")

    def mark_failure(self, learning_id: str):
        """Mark a learning as failed when applied."""
        with self._lock:
            if learning_id in self.learnings:
                learning = self.learnings[learning_id]
                learning.usage_count += 1
                learning.last_used = datetime.now()

                # Update success rate (exponential moving average)
                alpha = 0.2
                learning.success_rate = alpha * 0.0 + (1 - alpha) * learning.success_rate

                # Lower confidence
                learning.confidence *= 0.9

                self.metrics["failed_applications"] += 1
                self._save()

                logger.debug(f"Marked learning {learning_id} as failed")

    def prune_old_learnings(self, days: int = 90, min_success_rate: float = 0.3):
        """
        Remove old, low-value learnings.

        Keeps memory size manageable and removes outdated patterns.
        """
        with self._lock:
            cutoff_date = datetime.now() - timedelta(days=days)
            to_remove = []

            for learning_id, learning in self.learnings.items():
                # Remove if old AND low success rate
                if learning.timestamp < cutoff_date and learning.success_rate < min_success_rate:
                    to_remove.append(learning_id)

            for learning_id in to_remove:
                del self.learnings[learning_id]

            if to_remove:
                logger.info(f"Pruned {len(to_remove)} old/ineffective learnings")
                self._save()

    def get_component_stats(self, component: str) -> Dict[str, Any]:
        """Get statistics for a specific component."""
        with self._lock:
            component_learnings = [
                l for l in self.learnings.values() if l.component == component
            ]

            if not component_learnings:
                return {
                    "total_learnings": 0,
                    "avg_confidence": 0.0,
                    "avg_success_rate": 0.0
                }

            return {
                "total_learnings": len(component_learnings),
                "avg_confidence": sum(l.confidence for l in component_learnings) / len(component_learnings),
                "avg_success_rate": sum(l.success_rate for l in component_learnings) / len(component_learnings),
                "most_used": max(component_learnings, key=lambda l: l.usage_count).content[:100]
            }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global memory statistics."""
        with self._lock:
            return {
                **self.metrics,
                "active_learnings": len(self.learnings),
                "avg_confidence": sum(l.confidence for l in self.learnings.values()) / len(self.learnings) if self.learnings else 0.0
            }


# Global shared memory instance
_shared_memory: Optional[SharedMemory] = None


def get_shared_memory() -> SharedMemory:
    """Get the global shared memory instance."""
    global _shared_memory
    if _shared_memory is None:
        from pathlib import Path
        storage_path = Path.home() / ".lifeos" / "shared_memory"
        _shared_memory = SharedMemory(storage_path)
    return _shared_memory
