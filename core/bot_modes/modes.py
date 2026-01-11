"""
Bot Modes - Mode management for JARVIS.

Modes:
- ONLINE: Full connectivity, all features available
- DEGRADED: Limited connectivity, cached data, local LLM
- OFFLINE: No internet, local-only features
- MAINTENANCE: Scheduled downtime, status page only
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class BotMode(Enum):
    """Bot operating modes."""
    ONLINE = "online"           # Full connectivity
    DEGRADED = "degraded"       # Limited connectivity
    OFFLINE = "offline"         # No internet
    MAINTENANCE = "maintenance" # Scheduled downtime


class ModeCapability(Enum):
    """Capabilities available in different modes."""
    # Trading
    LIVE_TRADING = "live_trading"
    PAPER_TRADING = "paper_trading"
    TRADE_HISTORY = "trade_history"

    # Data
    REAL_TIME_PRICES = "realtime_prices"
    CACHED_PRICES = "cached_prices"
    MARKET_DATA = "market_data"
    WHALE_TRACKING = "whale_tracking"

    # AI
    CLOUD_LLM = "cloud_llm"
    LOCAL_LLM = "local_llm"

    # Alerts
    PUSH_ALERTS = "push_alerts"
    LOCAL_ALERTS = "local_alerts"

    # Portfolio
    LIVE_PORTFOLIO = "live_portfolio"
    CACHED_PORTFOLIO = "cached_portfolio"

    # Communication
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    WEBSOCKET = "websocket"

    # Other
    VOICE = "voice"
    JOURNAL = "journal"
    SETTINGS = "settings"


# Mode to capabilities mapping
MODE_CAPABILITIES: Dict[BotMode, Set[ModeCapability]] = {
    BotMode.ONLINE: {
        ModeCapability.LIVE_TRADING,
        ModeCapability.PAPER_TRADING,
        ModeCapability.TRADE_HISTORY,
        ModeCapability.REAL_TIME_PRICES,
        ModeCapability.CACHED_PRICES,
        ModeCapability.MARKET_DATA,
        ModeCapability.WHALE_TRACKING,
        ModeCapability.CLOUD_LLM,
        ModeCapability.LOCAL_LLM,
        ModeCapability.PUSH_ALERTS,
        ModeCapability.LOCAL_ALERTS,
        ModeCapability.LIVE_PORTFOLIO,
        ModeCapability.CACHED_PORTFOLIO,
        ModeCapability.TELEGRAM,
        ModeCapability.DISCORD,
        ModeCapability.EMAIL,
        ModeCapability.WEBSOCKET,
        ModeCapability.VOICE,
        ModeCapability.JOURNAL,
        ModeCapability.SETTINGS,
    },
    BotMode.DEGRADED: {
        ModeCapability.PAPER_TRADING,
        ModeCapability.TRADE_HISTORY,
        ModeCapability.CACHED_PRICES,
        ModeCapability.LOCAL_LLM,
        ModeCapability.LOCAL_ALERTS,
        ModeCapability.CACHED_PORTFOLIO,
        ModeCapability.VOICE,
        ModeCapability.JOURNAL,
        ModeCapability.SETTINGS,
    },
    BotMode.OFFLINE: {
        ModeCapability.TRADE_HISTORY,
        ModeCapability.CACHED_PRICES,
        ModeCapability.LOCAL_LLM,
        ModeCapability.LOCAL_ALERTS,
        ModeCapability.CACHED_PORTFOLIO,
        ModeCapability.VOICE,
        ModeCapability.JOURNAL,
        ModeCapability.SETTINGS,
    },
    BotMode.MAINTENANCE: {
        ModeCapability.SETTINGS,
    },
}


@dataclass
class ModeTransition:
    """Record of a mode transition."""
    from_mode: BotMode
    to_mode: BotMode
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MaintenanceWindow:
    """Scheduled maintenance window."""
    start_time: datetime
    end_time: datetime
    reason: str
    announced: bool = False


class BotModeManager:
    """
    Manager for bot operating modes.

    Handles:
    - Mode transitions
    - Capability checking
    - Maintenance windows
    - Mode history
    """

    def __init__(self):
        self._current_mode: BotMode = BotMode.ONLINE
        self._transitions: List[ModeTransition] = []
        self._maintenance_windows: List[MaintenanceWindow] = []
        self._mode_change_callbacks: List[Callable] = []
        self._last_connectivity_check: Optional[datetime] = None
        self._connectivity_check_interval = timedelta(seconds=30)

    @property
    def current_mode(self) -> BotMode:
        """Get current mode."""
        return self._current_mode

    def set_mode(self, mode: BotMode, reason: str = "") -> BotMode:
        """Set bot mode and notify callbacks."""
        if mode == self._current_mode:
            return mode

        old_mode = self._current_mode
        self._current_mode = mode

        # Record transition
        transition = ModeTransition(
            from_mode=old_mode,
            to_mode=mode,
            reason=reason,
        )
        self._transitions.append(transition)

        logger.info(f"Bot mode changed: {old_mode.value} -> {mode.value} ({reason})")

        # Notify callbacks
        for callback in self._mode_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(old_mode, mode, reason))
                else:
                    callback(old_mode, mode, reason)
            except Exception as e:
                logger.error(f"Error in mode change callback: {e}")

        return mode

    def has_capability(self, capability: ModeCapability) -> bool:
        """Check if a capability is available in current mode."""
        return capability in MODE_CAPABILITIES.get(self._current_mode, set())

    def get_available_capabilities(self) -> Set[ModeCapability]:
        """Get all available capabilities in current mode."""
        return MODE_CAPABILITIES.get(self._current_mode, set())

    def get_unavailable_capabilities(self) -> Set[ModeCapability]:
        """Get capabilities not available in current mode."""
        all_capabilities = set(ModeCapability)
        available = self.get_available_capabilities()
        return all_capabilities - available

    def on_mode_change(self, callback: Callable) -> None:
        """Register callback for mode changes."""
        self._mode_change_callbacks.append(callback)

    def schedule_maintenance(
        self,
        start_time: datetime,
        end_time: datetime,
        reason: str,
    ) -> MaintenanceWindow:
        """Schedule a maintenance window."""
        window = MaintenanceWindow(
            start_time=start_time,
            end_time=end_time,
            reason=reason,
        )
        self._maintenance_windows.append(window)
        logger.info(f"Maintenance scheduled: {start_time} to {end_time} - {reason}")
        return window

    def check_maintenance(self) -> Optional[MaintenanceWindow]:
        """Check if we're in a maintenance window."""
        now = datetime.utcnow()
        for window in self._maintenance_windows:
            if window.start_time <= now <= window.end_time:
                return window
        return None

    async def auto_detect_mode(self) -> BotMode:
        """
        Auto-detect appropriate mode based on connectivity.

        This checks:
        - Internet connectivity
        - API availability
        - Scheduled maintenance
        """
        # Check maintenance windows first
        maintenance = self.check_maintenance()
        if maintenance:
            self.set_mode(BotMode.MAINTENANCE, f"Scheduled: {maintenance.reason}")
            return self._current_mode

        # Check connectivity
        connectivity = await self._check_connectivity()

        if connectivity["full"]:
            self.set_mode(BotMode.ONLINE, "Full connectivity restored")
        elif connectivity["partial"]:
            self.set_mode(BotMode.DEGRADED, "Limited connectivity")
        else:
            self.set_mode(BotMode.OFFLINE, "No connectivity")

        self._last_connectivity_check = datetime.utcnow()
        return self._current_mode

    async def _check_connectivity(self) -> Dict[str, bool]:
        """Check connectivity to various services."""
        results = {
            "internet": False,
            "rpc": False,
            "api": False,
            "full": False,
            "partial": False,
        }

        try:
            # Simple internet check
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.google.com", timeout=5) as resp:
                    results["internet"] = resp.status == 200
        except Exception:
            results["internet"] = False

        # For now, assume if internet works, everything works
        results["rpc"] = results["internet"]
        results["api"] = results["internet"]
        results["full"] = all([results["internet"], results["rpc"], results["api"]])
        results["partial"] = results["internet"] and not results["full"]

        return results

    def get_mode_info(self) -> Dict[str, Any]:
        """Get current mode information."""
        maintenance = self.check_maintenance()

        return {
            "mode": self._current_mode.value,
            "capabilities": [c.value for c in self.get_available_capabilities()],
            "unavailable": [c.value for c in self.get_unavailable_capabilities()],
            "maintenance": {
                "active": maintenance is not None,
                "reason": maintenance.reason if maintenance else None,
                "end_time": maintenance.end_time.isoformat() if maintenance else None,
            } if maintenance else None,
            "last_check": self._last_connectivity_check.isoformat() if self._last_connectivity_check else None,
        }

    def get_transition_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get mode transition history."""
        return [
            {
                "from": t.from_mode.value,
                "to": t.to_mode.value,
                "reason": t.reason,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in self._transitions[-limit:]
        ]


# Singleton instance
_mode_manager: Optional[BotModeManager] = None


def get_mode_manager() -> BotModeManager:
    """Get the global mode manager instance."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = BotModeManager()
    return _mode_manager


def get_current_mode() -> BotMode:
    """Convenience function to get current mode."""
    return get_mode_manager().current_mode


def requires_online(capability: ModeCapability):
    """
    Decorator to require a specific capability.

    Usage:
        @requires_online(ModeCapability.LIVE_TRADING)
        async def execute_trade(params):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = get_mode_manager()
            if not manager.has_capability(capability):
                raise RuntimeError(
                    f"Capability {capability.value} not available in {manager.current_mode.value} mode"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
