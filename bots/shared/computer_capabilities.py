"""
Computer Control Capabilities for ClawdBots.

This module provides ClawdBots running on VPS with the ability to control
Daryl's Windows machine via Tailscale.

Usage in any ClawdBot:
    from bots.shared.computer_capabilities import (
        browse_web,
        control_computer,
        send_telegram_web,
        check_remote_status,
    )

    # Browser automation - LLM navigates like a human
    result = await browse_web("Go to coingecko.com and get the price of SOL")

    # Full computer control
    result = await control_computer("Open notepad and write a poem about Solana")

    # Telegram Web (when API is limited)
    result = await send_telegram_web("Saved Messages", "Hello from VPS!")
"""

import os
import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Import aiohttp for HTTP requests
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not installed. Run: pip install aiohttp")


# Configuration from environment
def _get_config():
    """Get remote control configuration."""
    return {
        "host": os.environ.get("JARVIS_LOCAL_IP", "100.102.41.120"),
        "port": int(os.environ.get("JARVIS_REMOTE_PORT", "8765")),
        "api_key": os.environ.get("JARVIS_REMOTE_API_KEY"),
    }


class RemoteComputerControl:
    """
    Control Daryl's Windows computer from VPS via Tailscale.

    This connects to the remote_control_server.py running on Windows.
    """

    def __init__(self):
        config = _get_config()
        self.host = config["host"]
        self.port = config["port"]
        self.api_key = config["api_key"]
        self.base_url = f"http://{self.host}:{self.port}"
        self.timeout = 300  # 5 min for long tasks

        if not self.api_key:
            logger.warning(
                "JARVIS_REMOTE_API_KEY not set. Remote control will fail."
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to remote control server."""
        if not HAS_AIOHTTP:
            return {"error": "aiohttp not installed", "success": False}

        url = f"{self.base_url}{endpoint}"
        headers = {"X-API-Key": self.api_key or ""}

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method == "GET":
                    async with session.get(url, headers=headers) as resp:
                        return await resp.json()
                elif method == "POST":
                    async with session.post(url, headers=headers, json=data) as resp:
                        return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Remote control request failed: {e}")
            return {"error": str(e), "success": False}
        except asyncio.TimeoutError:
            return {"error": "Request timed out", "success": False}

    async def is_available(self) -> bool:
        """Check if Windows machine is reachable."""
        try:
            result = await self._request("GET", "/health")
            return result.get("status") == "healthy"
        except Exception:
            return False

    async def browse(self, task: str) -> Dict[str, Any]:
        """
        Browser automation on Windows machine.

        The LLM navigates web pages like a human - reads the DOM,
        understands the page, clicks buttons by meaning not coordinates.

        Args:
            task: Natural language task
                  "Go to twitter.com and check my notifications"
                  "Search google for 'solana ecosystem' and summarize results"

        Returns:
            Dict with success, result
        """
        logger.info(f"Remote browse: {task[:50]}...")
        return await self._request("POST", "/browser", {"task": task})

    async def computer(self, task: str) -> Dict[str, Any]:
        """
        Full computer control on Windows machine.

        Can do ANYTHING you can do on the computer:
        - Open/control applications
        - Read/write files
        - Run commands
        - Take screenshots
        - And more

        Args:
            task: Natural language task
                  "Check what programs are running"
                  "Create a folder called 'reports' on the desktop"
                  "Open Chrome and take a screenshot"

        Returns:
            Dict with success, output
        """
        logger.info(f"Remote computer: {task[:50]}...")
        return await self._request("POST", "/computer", {"task": task})

    async def telegram_send(self, chat: str, message: str) -> Dict[str, Any]:
        """
        Send Telegram message via Web interface.

        Uses Telegram Web on Windows - useful when bot API is limited
        or need to send from Daryl's personal account.

        Args:
            chat: Chat name or username
            message: Message to send
        """
        logger.info(f"Remote telegram send to {chat}")
        return await self._request("POST", "/telegram", {
            "action": "send_message",
            "chat": chat,
            "message": message,
        })

    async def telegram_read(self, chat: str, count: int = 10) -> Dict[str, Any]:
        """Read recent messages from a Telegram chat."""
        return await self._request("POST", "/telegram", {
            "action": "read_messages",
            "chat": chat,
            "count": count,
        })


# Singleton instance
_remote = None


def _get_remote() -> RemoteComputerControl:
    """Get singleton remote control instance."""
    global _remote
    if _remote is None:
        _remote = RemoteComputerControl()
    return _remote


# ============================================
# CONVENIENCE FUNCTIONS FOR CLAWDBOTS
# ============================================

async def browse_web(task: str) -> str:
    """
    Browse the web on Daryl's Windows machine.

    Examples:
        result = await browse_web("Go to coingecko.com and get SOL price")
        result = await browse_web("Check my twitter notifications")
        result = await browse_web("Go to pump.fun and find trending tokens")

    Returns:
        String result or error message
    """
    remote = _get_remote()
    result = await remote.browse(task)

    if result.get("success"):
        return str(result.get("result", "Task completed"))
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


async def control_computer(task: str) -> str:
    """
    Control Daryl's Windows computer.

    Examples:
        result = await control_computer("What files are on the desktop?")
        result = await control_computer("Open calculator")
        result = await control_computer("Take a screenshot and save it")

    Returns:
        String result or error message
    """
    remote = _get_remote()
    result = await remote.computer(task)

    if result.get("success"):
        return str(result.get("output", "Task completed"))
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


async def send_telegram_web(chat: str, message: str) -> str:
    """
    Send Telegram message via Web on Daryl's computer.

    Useful for sending from Daryl's personal account,
    not the bot account.

    Examples:
        await send_telegram_web("Saved Messages", "Reminder: check portfolio")
        await send_telegram_web("Trading Group", "SOL looking bullish!")

    Returns:
        Success message or error
    """
    remote = _get_remote()
    result = await remote.telegram_send(chat, message)

    if result.get("success"):
        return f"Sent to {chat}: {message[:50]}..."
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


async def read_telegram_web(chat: str, count: int = 10) -> str:
    """
    Read recent Telegram messages via Web.

    Returns:
        Message list or error
    """
    remote = _get_remote()
    result = await remote.telegram_read(chat, count)

    if result.get("success"):
        return str(result.get("result", "No messages"))
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


async def check_remote_status() -> Dict[str, Any]:
    """
    Check if Windows machine is available for remote control.

    Returns:
        Dict with available (bool), status info
    """
    remote = _get_remote()
    available = await remote.is_available()

    if available:
        return {
            "available": True,
            "host": remote.host,
            "capabilities": [
                "browse_web - LLM-native browser automation",
                "control_computer - Full computer control",
                "send_telegram_web - Telegram via Web",
                "read_telegram_web - Read Telegram chats",
            ],
        }
    else:
        return {
            "available": False,
            "host": remote.host,
            "error": "Windows machine not reachable. Is the server running?",
        }


# ============================================
# CAPABILITY DESCRIPTION FOR LLM CONTEXT
# ============================================

COMPUTER_CAPABILITIES_PROMPT = """
## Computer Control Capabilities

You have the ability to control Daryl's Windows computer remotely via Tailscale.

### Available Functions:

1. **browse_web(task)** - Browse the internet
   - The LLM navigates like a human (understands pages, clicks by meaning)
   - Examples:
     - "Go to coingecko.com and get SOL price"
     - "Check twitter.com/Jarvis_lifeos notifications"
     - "Go to pump.fun and list trending tokens"

2. **control_computer(task)** - Full computer control
   - Can do ANYTHING on the computer
   - Examples:
     - "What programs are currently running?"
     - "Create a file called notes.txt on the desktop"
     - "Open Chrome and take a screenshot"
     - "Check the Downloads folder for new files"

3. **send_telegram_web(chat, message)** - Send Telegram via Web
   - Uses Daryl's personal Telegram account (not bot)
   - Examples:
     - send_telegram_web("Saved Messages", "Reminder note")
     - send_telegram_web("Trading Chat", "SOL update...")

4. **read_telegram_web(chat, count)** - Read Telegram messages
   - Read recent messages from any chat

### Usage in Code:

```python
from bots.shared.computer_capabilities import (
    browse_web,
    control_computer,
    send_telegram_web,
)

# Browser task
result = await browse_web("Go to google.com and search for 'solana news'")

# Computer task
result = await control_computer("List files in C:\\Users\\lucid\\Downloads")

# Telegram Web
result = await send_telegram_web("Saved Messages", "Test message")
```

### When to Use:
- Use browse_web for web research, checking sites, social media
- Use control_computer for file operations, app control, screenshots
- Use send_telegram_web when you need to send FROM Daryl's account (not bot)
"""


def get_capabilities_prompt() -> str:
    """Get the capabilities prompt to include in LLM context."""
    return COMPUTER_CAPABILITIES_PROMPT
