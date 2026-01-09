"""
Notification service adapters.

Provides unified interface for sending notifications across platforms.
"""

from .desktop_adapter import DesktopNotificationAdapter

__all__ = ["DesktopNotificationAdapter"]
