"""
Remote Control Client for ClawdBots.

Call this from your VPS/Telegram bots to control your local Windows machine
via Tailscale.

Usage:
    from core.automation.remote_control_client import RemoteControl

    remote = RemoteControl()

    # Browser automation
    result = await remote.browser("Go to google.com and search for 'solana'")

    # Full computer control
    result = await remote.computer("List files in Downloads folder")

    # Telegram Web
    result = await remote.telegram_send("Saved Messages", "Hello!")
"""

import asyncio
import os
from typing import Any, Dict, Optional

import aiohttp

# Default Tailscale IP for Windows machine
# Set JARVIS_LOCAL_IP env var or update this
DEFAULT_LOCAL_IP = os.getenv("JARVIS_LOCAL_IP", "100.x.x.x")  # Your Tailscale IP
DEFAULT_PORT = 8765
API_KEY_ENV = "JARVIS_REMOTE_API_KEY"


class RemoteControl:
    """
    Client for controlling your local Windows machine via Tailscale.

    For ClawdBots running on VPS to control your home computer.
    """

    def __init__(
        self,
        host: str = None,
        port: int = DEFAULT_PORT,
        api_key: str = None,
        timeout: int = 300,  # 5 min timeout for long tasks
    ):
        """
        Initialize remote control client.

        Args:
            host: Tailscale IP of your Windows machine
            port: Port of remote control server
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.host = host or os.getenv("JARVIS_LOCAL_IP", DEFAULT_LOCAL_IP)
        self.port = port
        self.api_key = api_key or os.getenv(API_KEY_ENV)
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"

        if not self.api_key:
            raise ValueError(
                f"API key required. Set {API_KEY_ENV} environment variable."
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to remote control server."""
        url = f"{self.base_url}{endpoint}"
        headers = {"X-API-Key": self.api_key}

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    return await resp.json()
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as resp:
                    return await resp.json()

    async def health(self) -> bool:
        """Check if remote control server is reachable."""
        try:
            result = await self._request("GET", "/health")
            return result.get("status") == "healthy"
        except Exception:
            return False

    async def status(self) -> Dict:
        """Get remote control server status."""
        return await self._request("GET", "/status")

    async def browser(self, task: str) -> Dict[str, Any]:
        """
        Execute a browser automation task on local machine.

        Args:
            task: Natural language description of what to do
                  e.g., "Go to twitter.com and post 'Hello world'"

        Returns:
            Dict with success status and result
        """
        return await self._request("POST", "/browser", {"task": task})

    async def computer(self, task: str) -> Dict[str, Any]:
        """
        Execute a full computer control task on local machine.

        Args:
            task: Natural language description of what to do
                  e.g., "Create a file called test.txt on the desktop"

        Returns:
            Dict with success status and output
        """
        return await self._request("POST", "/computer", {"task": task})

    async def telegram_send(self, chat: str, message: str) -> Dict[str, Any]:
        """
        Send a Telegram message via Telegram Web on local machine.

        Args:
            chat: Chat name or username
            message: Message to send
        """
        return await self._request("POST", "/telegram", {
            "action": "send_message",
            "chat": chat,
            "message": message,
        })

    async def telegram_read(self, chat: str, count: int = 10) -> Dict[str, Any]:
        """
        Read recent Telegram messages from local machine.

        Args:
            chat: Chat name or username
            count: Number of messages to read
        """
        return await self._request("POST", "/telegram", {
            "action": "read_messages",
            "chat": chat,
            "count": count,
        })


# Convenience functions for quick use

async def remote_browser(task: str) -> Dict[str, Any]:
    """Quick browser automation."""
    remote = RemoteControl()
    return await remote.browser(task)


async def remote_computer(task: str) -> Dict[str, Any]:
    """Quick computer control."""
    remote = RemoteControl()
    return await remote.computer(task)


async def remote_telegram(chat: str, message: str) -> Dict[str, Any]:
    """Quick Telegram send."""
    remote = RemoteControl()
    return await remote.telegram_send(chat, message)


# Test functions
async def test_connection():
    """Test connection to local machine."""
    remote = RemoteControl()

    print("Testing connection to local machine...")
    if await remote.health():
        print("✓ Remote control server is healthy")
        status = await remote.status()
        print(f"✓ Status: {status}")
    else:
        print("✗ Cannot reach remote control server")
        print(f"  - Check that server is running on {remote.host}:{remote.port}")
        print(f"  - Check Tailscale is connected")


if __name__ == "__main__":
    asyncio.run(test_connection())
