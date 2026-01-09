"""
Desktop Notification Service Adapter

Provides cross-platform desktop notifications.
Supports Windows (win10toast), macOS (pync/osascript), and Linux (notify-send).

Features:
- Automatic platform detection
- Fallback to print if no notification system available
- Sound support where available
- Action URL support (macOS)

Usage:
    adapter = DesktopNotificationAdapter()
    result = await adapter.send("Something happened!", title="Alert")
    if result.success:
        print("User notified")
"""

import asyncio
import logging
import platform
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lifeos.services.interfaces import (
    NotificationService,
    NotificationPriority,
    NotificationResult,
    ServiceError,
    ServiceHealth,
    ServiceStatus,
)

logger = logging.getLogger(__name__)


class DesktopNotificationAdapter(NotificationService):
    """
    Cross-platform desktop notification adapter.

    Implements the NotificationService interface for desktop notifications.
    Automatically detects platform and uses appropriate notification method.
    """

    def __init__(self):
        """Initialize desktop notification adapter."""
        self._platform = platform.system().lower()
        self._notifier = None
        self._method = "fallback"
        self._init_notifier()

    @property
    def service_name(self) -> str:
        return "desktop_notifications"

    @property
    def channel(self) -> str:
        return "system"

    def _init_notifier(self) -> None:
        """Initialize platform-specific notifier."""
        if self._platform == "windows":
            self._init_windows()
        elif self._platform == "darwin":
            self._init_macos()
        elif self._platform == "linux":
            self._init_linux()
        else:
            logger.warning(f"Unknown platform: {self._platform}, using fallback")

    def _init_windows(self) -> None:
        """Initialize Windows notifier."""
        try:
            from win10toast import ToastNotifier
            self._notifier = ToastNotifier()
            self._method = "win10toast"
            logger.debug("Using win10toast for notifications")
        except ImportError:
            try:
                from plyer import notification
                self._notifier = notification
                self._method = "plyer"
                logger.debug("Using plyer for notifications")
            except ImportError:
                logger.warning("No Windows notification library. Install win10toast or plyer")

    def _init_macos(self) -> None:
        """Initialize macOS notifier."""
        try:
            import pync
            self._notifier = pync
            self._method = "pync"
            logger.debug("Using pync for notifications")
        except ImportError:
            self._method = "osascript"
            logger.debug("Using osascript for notifications")

    def _init_linux(self) -> None:
        """Initialize Linux notifier."""
        try:
            from plyer import notification
            self._notifier = notification
            self._method = "plyer"
            logger.debug("Using plyer for notifications")
        except ImportError:
            try:
                subprocess.run(
                    ["which", "notify-send"],
                    check=True,
                    capture_output=True,
                )
                self._method = "notify-send"
                logger.debug("Using notify-send for notifications")
            except subprocess.CalledProcessError:
                logger.warning("No Linux notification method available")

    async def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """Send a desktop notification."""
        title = title or "Jarvis"
        metadata = metadata or {}

        try:
            success = False
            if self._method == "win10toast":
                success = await self._send_win10toast(title, message, metadata)
            elif self._method == "plyer":
                success = await self._send_plyer(title, message, metadata)
            elif self._method == "pync":
                success = await self._send_pync(title, message, metadata)
            elif self._method == "osascript":
                success = await self._send_osascript(title, message, metadata)
            elif self._method == "notify-send":
                success = await self._send_notify_send(title, message, priority, metadata)
            else:
                logger.info(f"[NOTIFICATION] {title}: {message}")
                success = True

            return NotificationResult(
                success=success,
                channel=self.channel,
                delivered_at=datetime.now(timezone.utc) if success else None,
            )

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return NotificationResult(
                success=False,
                channel=self.channel,
                error=str(e),
            )

    async def _send_win10toast(
        self,
        title: str,
        message: str,
        metadata: dict,
    ) -> bool:
        """Send Windows 10 toast notification."""
        duration = metadata.get("duration", 5)
        icon = metadata.get("icon")

        await asyncio.to_thread(
            self._notifier.show_toast,
            title,
            message,
            duration=duration,
            icon_path=icon,
            threaded=True,
        )
        return True

    async def _send_plyer(
        self,
        title: str,
        message: str,
        metadata: dict,
    ) -> bool:
        """Send notification via plyer."""
        timeout = metadata.get("duration", 10)

        await asyncio.to_thread(
            self._notifier.notify,
            title=title,
            message=message,
            timeout=timeout,
            app_name="Jarvis",
        )
        return True

    async def _send_pync(
        self,
        title: str,
        message: str,
        metadata: dict,
    ) -> bool:
        """Send macOS notification via pync."""
        sound = metadata.get("sound", True)
        action_url = metadata.get("action_url")

        kwargs = {
            "title": title,
            "message": message,
        }
        if sound:
            kwargs["sound"] = "default"
        if action_url:
            kwargs["open"] = action_url

        await asyncio.to_thread(self._notifier.notify, **kwargs)
        return True

    async def _send_osascript(
        self,
        title: str,
        message: str,
        metadata: dict,
    ) -> bool:
        """Send macOS notification via osascript."""
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')

        script = f'display notification "{safe_message}" with title "{safe_title}"'

        sound = metadata.get("sound", True)
        if sound:
            script += ' sound name "default"'

        await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
        )
        return True

    async def _send_notify_send(
        self,
        title: str,
        message: str,
        priority: NotificationPriority,
        metadata: dict,
    ) -> bool:
        """Send Linux notification via notify-send."""
        urgency_map = {
            NotificationPriority.LOW: "low",
            NotificationPriority.NORMAL: "normal",
            NotificationPriority.HIGH: "critical",
            NotificationPriority.CRITICAL: "critical",
        }
        urgency = urgency_map.get(priority, "normal")
        timeout = metadata.get("duration", 5) * 1000

        cmd = [
            "notify-send",
            "-u", urgency,
            "-t", str(timeout),
            title,
            message,
        ]

        await asyncio.to_thread(
            subprocess.run,
            cmd,
            check=True,
            capture_output=True,
        )
        return True

    async def send_batch(
        self,
        notifications: List[Dict[str, Any]],
    ) -> List[NotificationResult]:
        """Send multiple notifications."""
        results = []

        for notif in notifications:
            message = notif.get("message", "")
            title = notif.get("title")
            priority_str = notif.get("priority", "normal")

            try:
                priority = NotificationPriority(priority_str)
            except ValueError:
                priority = NotificationPriority.NORMAL

            result = await self.send(
                message=message,
                title=title,
                priority=priority,
                metadata=notif.get("metadata"),
            )
            results.append(result)

        return results

    async def health_check(self) -> ServiceHealth:
        """Check notification system availability."""
        start_time = time.time()

        if self._method == "fallback":
            return ServiceHealth(
                status=ServiceStatus.DEGRADED,
                latency_ms=0,
                message="No notification library available, using print fallback",
                metadata={"platform": self._platform, "method": self._method},
            )

        try:
            latency = (time.time() - start_time) * 1000

            return ServiceHealth(
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
                message="OK",
                metadata={
                    "platform": self._platform,
                    "method": self._method,
                },
            )

        except Exception as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                latency_ms=(time.time() - start_time) * 1000,
                message=str(e),
                metadata={"platform": self._platform, "method": self._method},
            )
