"""
Telegram Heartbeat System for ClawdBots.

Sends periodic heartbeat messages to a Telegram chat to keep Daryl informed
about bot health without being intrusive.

Features:
- Periodic heartbeat messages (configurable, default 6 hours)
- Status reporting (uptime, messages processed, API costs, memory usage)
- Emergency alerts for critical issues
- Manual trigger via send_heartbeat_now()
- Thread-safe background operation
- State persistence at /root/clawdbots/heartbeat_state.json

Usage:
    from bots.shared.heartbeat import TelegramHeartbeat, start_heartbeat_thread

    # Create heartbeat instance
    hb = TelegramHeartbeat(bot_name="ClawdJarvis")

    # Start background thread
    thread = start_heartbeat_thread(hb)

    # Record activity
    hb.record_message()
    hb.record_api_cost(0.002)

    # Manual heartbeat
    await hb.send_heartbeat_now()

    # Emergency alert
    await hb.send_emergency_alert("Critical error!")
"""

import asyncio
import json
import logging
import os
import psutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


def format_uptime(seconds: float) -> str:
    """Format uptime in human-readable format."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_heartbeat_message(bot_name: str, stats: Dict[str, Any]) -> str:
    """
    Format a heartbeat message for Telegram.

    Args:
        bot_name: Name of the bot
        stats: Dictionary containing:
            - uptime_seconds: Uptime in seconds
            - messages_processed: Number of messages processed
            - api_cost_usd: Total API cost in USD
            - memory_mb: Memory usage in MB

    Returns:
        Formatted message string
    """
    uptime = format_uptime(stats.get("uptime_seconds", 0))
    messages = stats.get("messages_processed", 0)
    api_cost = stats.get("api_cost_usd", 0.0)
    memory = stats.get("memory_mb", 0.0)

    # Get current time
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    message = f"""[Heartbeat] {bot_name}
---
Uptime: {uptime}
Messages: {messages:,}
API Cost: ${api_cost:.4f}
Memory: {memory:.1f} MB
---
{now}"""

    return message


def get_heartbeat_status(heartbeat: "TelegramHeartbeat") -> Dict[str, Any]:
    """
    Get the current heartbeat status.

    Args:
        heartbeat: TelegramHeartbeat instance

    Returns:
        Dictionary with status information
    """
    return {
        "running": heartbeat.running,
        "last_heartbeat": heartbeat.last_heartbeat.isoformat() if heartbeat.last_heartbeat else None,
        "heartbeat_count": heartbeat.heartbeat_count,
        "interval_seconds": heartbeat.interval_seconds,
        "bot_name": heartbeat.bot_name,
        "stats": heartbeat.stats.copy(),
    }


def start_heartbeat_thread(heartbeat: "TelegramHeartbeat") -> threading.Thread:
    """
    Start the heartbeat background thread.

    Args:
        heartbeat: TelegramHeartbeat instance

    Returns:
        Thread object (daemon thread)
    """
    thread = threading.Thread(
        target=heartbeat._run_loop,
        name=f"heartbeat-{heartbeat.bot_name}",
        daemon=True,
    )
    heartbeat._thread = thread
    heartbeat.running = True
    thread.start()
    return thread


class TelegramHeartbeat:
    """
    Telegram heartbeat system for ClawdBots.

    Sends periodic status messages to a Telegram chat.
    """

    def __init__(
        self,
        bot_token: str = None,
        chat_id: int = None,
        bot_name: str = "ClawdBot",
        interval_hours: float = 6.0,
        state_path: str = None,
    ):
        """
        Initialize the heartbeat system.

        Args:
            bot_token: Telegram bot token (or from TELEGRAM_BOT_TOKEN env)
            chat_id: Chat ID to send heartbeats to (or from HEARTBEAT_CHAT_ID env)
            bot_name: Name of the bot for message identification
            interval_hours: Interval between heartbeats in hours (default: 6)
            state_path: Path to state file (default: /root/clawdbots/heartbeat_state.json)
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id
        if self.chat_id is None:
            chat_id_str = os.environ.get("HEARTBEAT_CHAT_ID", "")
            if chat_id_str:
                try:
                    self.chat_id = int(chat_id_str)
                except ValueError:
                    self.chat_id = None

        self.bot_name = bot_name
        self.interval_seconds = int(interval_hours * 3600)
        self.state_path = Path(state_path or "/root/clawdbots/heartbeat_state.json")

        # Stats tracking
        self.stats: Dict[str, Any] = {
            "uptime_seconds": 0.0,
            "messages_processed": 0,
            "api_cost_usd": 0.0,
            "memory_mb": 0.0,
        }

        # Runtime state
        self.start_time = datetime.now(timezone.utc)
        self.last_heartbeat: Optional[datetime] = None
        self.heartbeat_count = 0
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def record_message(self) -> None:
        """Record a processed message."""
        self.stats["messages_processed"] += 1

    def record_api_cost(self, cost_usd: float) -> None:
        """Record API cost in USD."""
        self.stats["api_cost_usd"] += cost_usd

    def _update_stats(self) -> None:
        """Update dynamic stats (uptime, memory)."""
        # Update uptime
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.stats["uptime_seconds"] = uptime

        # Update memory usage
        try:
            process = psutil.Process(os.getpid())
            self.stats["memory_mb"] = process.memory_info().rss / (1024 * 1024)
        except Exception:
            pass  # psutil may fail in some environments

    def save_state(self) -> None:
        """Save heartbeat state to file."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "bot_name": self.bot_name,
                "heartbeat_count": self.heartbeat_count,
                "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
                "stats": self.stats.copy(),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }

            self.state_path.write_text(json.dumps(state, indent=2))
            logger.debug(f"Heartbeat state saved to {self.state_path}")
        except Exception as e:
            logger.warning(f"Failed to save heartbeat state: {e}")

    def load_state(self) -> bool:
        """
        Load heartbeat state from file.

        Returns:
            True if state was loaded, False otherwise
        """
        try:
            if not self.state_path.exists():
                return False

            state = json.loads(self.state_path.read_text())

            self.heartbeat_count = state.get("heartbeat_count", 0)

            last_hb = state.get("last_heartbeat")
            if last_hb:
                self.last_heartbeat = datetime.fromisoformat(last_hb)

            # Restore cumulative stats
            saved_stats = state.get("stats", {})
            self.stats["messages_processed"] = saved_stats.get("messages_processed", 0)
            self.stats["api_cost_usd"] = saved_stats.get("api_cost_usd", 0.0)

            logger.info(f"Heartbeat state loaded: {self.heartbeat_count} heartbeats")
            return True
        except Exception as e:
            logger.warning(f"Failed to load heartbeat state: {e}")
            return False

    async def _send_telegram_message(self, text: str, parse_mode: str = None) -> bool:
        """
        Send a message to Telegram.

        Args:
            text: Message text
            parse_mode: Optional parse mode (HTML, Markdown)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Heartbeat not configured: missing bot_token or chat_id")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("ok", False)
                    else:
                        logger.warning(f"Telegram API error: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_heartbeat_now(self) -> bool:
        """
        Send a heartbeat immediately.

        Returns:
            True if sent successfully, False otherwise
        """
        self._update_stats()
        message = format_heartbeat_message(self.bot_name, self.stats)

        success = await self._send_telegram_message(message)

        if success:
            self.heartbeat_count += 1
            self.last_heartbeat = datetime.now(timezone.utc)
            self.save_state()
            logger.info(f"Heartbeat #{self.heartbeat_count} sent for {self.bot_name}")

        return success

    async def send_emergency_alert(self, message: str) -> bool:
        """
        Send an emergency alert immediately.

        Args:
            message: Alert message

        Returns:
            True if sent successfully, False otherwise
        """
        alert_text = f"""[EMERGENCY ALERT] {self.bot_name}
---
{message}
---
{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}"""

        return await self._send_telegram_message(alert_text)

    def _run_loop(self) -> None:
        """Background loop for periodic heartbeats."""
        logger.info(f"Heartbeat thread started for {self.bot_name} (interval: {self.interval_seconds}s)")

        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while not self._stop_event.is_set():
                try:
                    # Send heartbeat
                    loop.run_until_complete(self.send_heartbeat_now())
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")

                # Wait for next interval or stop signal
                self._stop_event.wait(timeout=self.interval_seconds)

        finally:
            loop.close()
            logger.info(f"Heartbeat thread stopped for {self.bot_name}")

    def stop(self) -> None:
        """Stop the heartbeat background thread."""
        self.running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


# Convenience function for module-level access
_default_heartbeat: Optional[TelegramHeartbeat] = None


def get_default_heartbeat() -> Optional[TelegramHeartbeat]:
    """Get the default heartbeat instance."""
    return _default_heartbeat


def set_default_heartbeat(heartbeat: TelegramHeartbeat) -> None:
    """Set the default heartbeat instance."""
    global _default_heartbeat
    _default_heartbeat = heartbeat


async def send_heartbeat_now(heartbeat: TelegramHeartbeat = None) -> bool:
    """
    Send a heartbeat immediately.

    Args:
        heartbeat: Optional TelegramHeartbeat instance. If None, uses default.

    Returns:
        True if sent successfully, False otherwise
    """
    hb = heartbeat or _default_heartbeat
    if hb is None:
        logger.warning("No heartbeat instance available")
        return False
    return await hb.send_heartbeat_now()
