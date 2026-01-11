"""
Notifications module for Jarvis.

Provides cross-platform notifications for:
- Git push events (Telegram, X)
- System alerts
- Trading signals
- Sentiment updates
"""

from .git_notify import (
    GitCommitInfo,
    GitNotifier,
    get_notifier,
    notify_push,
    notify_push_sync,
)

__all__ = [
    "GitCommitInfo",
    "GitNotifier",
    "get_notifier",
    "notify_push",
    "notify_push_sync",
]
