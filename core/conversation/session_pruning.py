"""
Context Pruning - Clean up old and excess conversation contexts.

Provides:
- prune_old_contexts(max_age): Remove contexts older than max_age
- prune_by_count(max_contexts): Keep only most recent contexts
- create_pruning_task: Create a periodic pruning callable
- prune_all: Combined age and count pruning
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional
import logging

from .session_manager import ConversationManager


logger = logging.getLogger(__name__)


def prune_old_contexts(
    manager: ConversationManager,
    max_age_seconds: int = 3600
) -> int:
    """
    Remove contexts older than max_age_seconds.

    Args:
        manager: ConversationManager to prune
        max_age_seconds: Maximum age in seconds (default 1 hour)

    Returns:
        Number of contexts removed
    """
    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    removed = 0

    # Get list of contexts to check
    contexts_to_check = list(manager._contexts.items())

    for key, ctx in contexts_to_check:
        if ctx.last_activity < cutoff:
            # Remove from in-memory cache
            if key in manager._contexts:
                del manager._contexts[key]
            # Remove from storage
            manager._storage.delete_context(ctx.user_id, ctx.chat_id)
            removed += 1
            logger.debug(f"Pruned old context: {key}")

    if removed > 0:
        logger.info(f"Pruned {removed} old contexts (max_age={max_age_seconds}s)")

    return removed


def prune_by_count(
    manager: ConversationManager,
    max_contexts: int = 1000
) -> int:
    """
    Remove oldest contexts when count exceeds max_contexts.

    Keeps the most recently active contexts.

    Args:
        manager: ConversationManager to prune
        max_contexts: Maximum number of contexts to keep

    Returns:
        Number of contexts removed
    """
    contexts = list(manager._contexts.values())

    if len(contexts) <= max_contexts:
        return 0

    # Sort by last_activity (oldest first)
    contexts.sort(key=lambda ctx: ctx.last_activity)

    # Calculate how many to remove
    to_remove = len(contexts) - max_contexts
    removed = 0

    for ctx in contexts[:to_remove]:
        key = manager._make_key(ctx.user_id, ctx.chat_id)
        if key in manager._contexts:
            del manager._contexts[key]
        manager._storage.delete_context(ctx.user_id, ctx.chat_id)
        removed += 1
        logger.debug(f"Pruned excess context: {key}")

    if removed > 0:
        logger.info(f"Pruned {removed} contexts (max_count={max_contexts})")

    return removed


def prune_all(
    manager: ConversationManager,
    max_age_seconds: int = 3600,
    max_contexts: int = 1000
) -> Dict[str, int]:
    """
    Perform combined age and count pruning.

    First removes old contexts, then trims by count if still over limit.

    Args:
        manager: ConversationManager to prune
        max_age_seconds: Maximum age in seconds
        max_contexts: Maximum number of contexts to keep

    Returns:
        Dict with pruned_by_age and pruned_by_count
    """
    age_removed = prune_old_contexts(manager, max_age_seconds)
    count_removed = prune_by_count(manager, max_contexts)

    return {
        "pruned_by_age": age_removed,
        "pruned_by_count": count_removed,
        "total_removed": age_removed + count_removed
    }


def create_pruning_task(
    manager: ConversationManager,
    interval_seconds: int = 300,
    max_age_seconds: int = 3600,
    max_contexts: int = 1000
) -> Callable[[], Dict[str, Any]]:
    """
    Create a pruning task callable for periodic execution.

    The returned callable can be used with a scheduler or run manually.

    Args:
        manager: ConversationManager to prune
        interval_seconds: How often pruning should run (for logging)
        max_age_seconds: Maximum age for contexts
        max_contexts: Maximum number of contexts

    Returns:
        Callable that performs pruning and returns results
    """
    def prune_task() -> Dict[str, Any]:
        """Execute pruning and return results."""
        start = datetime.utcnow()

        result = prune_all(manager, max_age_seconds, max_contexts)

        elapsed = (datetime.utcnow() - start).total_seconds()

        return {
            "pruned_by_age": result["pruned_by_age"],
            "pruned_by_count": result["pruned_by_count"],
            "total_removed": result["total_removed"],
            "elapsed_seconds": elapsed,
            "remaining_contexts": manager.context_count(),
            "timestamp": datetime.utcnow().isoformat()
        }

    return prune_task


class PruningScheduler:
    """
    Simple scheduler for periodic context pruning.

    Note: For production use, consider using APScheduler or similar.
    This is a basic implementation for demonstration.
    """

    def __init__(
        self,
        manager: ConversationManager,
        interval_seconds: int = 300,
        max_age_seconds: int = 3600,
        max_contexts: int = 1000
    ):
        self.manager = manager
        self.interval_seconds = interval_seconds
        self.max_age_seconds = max_age_seconds
        self.max_contexts = max_contexts
        self._task = create_pruning_task(
            manager,
            interval_seconds,
            max_age_seconds,
            max_contexts
        )
        self._running = False
        self._last_run: Optional[datetime] = None

    def run_once(self) -> Dict[str, Any]:
        """Run pruning once and return results."""
        result = self._task()
        self._last_run = datetime.utcnow()
        return result

    def should_run(self) -> bool:
        """Check if pruning should run based on interval."""
        if self._last_run is None:
            return True
        elapsed = (datetime.utcnow() - self._last_run).total_seconds()
        return elapsed >= self.interval_seconds

    def run_if_needed(self) -> Optional[Dict[str, Any]]:
        """Run pruning if interval has elapsed."""
        if self.should_run():
            return self.run_once()
        return None
