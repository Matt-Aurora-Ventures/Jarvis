"""
Telegram Integration for the Integration Hub.

Provides connection to Telegram Bot API with support for:
- Sending messages
- Sending photos
- Getting updates
- Health checking
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .base import Integration

logger = logging.getLogger(__name__)

# Telegram API base URL
TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramIntegration(Integration):
    """
    Telegram Bot API integration.

    Allows sending messages, photos, and receiving updates via Telegram Bot API.

    Example:
        integration = TelegramIntegration(bot_token="123456:ABC...")
        integration.connect()

        await integration.send_message(chat_id=12345, text="Hello!")
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
    ):
        """
        Initialize Telegram integration.

        Args:
            bot_token: Telegram bot token from BotFather.
                      Can also be set via TELEGRAM_BOT_TOKEN env var.
        """
        self._bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self._connected = False
        self._bot_info: Optional[Dict] = None

    @property
    def name(self) -> str:
        """Integration name."""
        return "telegram"

    @property
    def description(self) -> str:
        """Integration description."""
        return "Telegram Bot API integration for messaging and notifications"

    @property
    def required_config(self) -> List[str]:
        """Required configuration keys."""
        return ["bot_token"]

    def _validate_token(self) -> bool:
        """
        Validate the bot token by calling getMe.

        Returns:
            bool: True if token is valid
        """
        if not self._bot_token:
            return False

        try:
            import requests

            url = f"{TELEGRAM_API_BASE}/bot{self._bot_token}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self._bot_info = data.get("result")
                    return True
            return False
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False

    def connect(self) -> bool:
        """
        Connect to Telegram API by validating the token.

        Returns:
            bool: True if connection successful
        """
        if not self._bot_token:
            logger.error("No bot token provided")
            return False

        if self._validate_token():
            self._connected = True
            logger.info(f"Connected to Telegram as @{self._bot_info.get('username', 'unknown')}")
            return True

        return False

    def disconnect(self) -> None:
        """Disconnect from Telegram."""
        self._connected = False
        self._bot_info = None
        logger.info("Disconnected from Telegram")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def health_check(self) -> bool:
        """
        Check Telegram API health.

        Returns:
            bool: True if healthy
        """
        if not self._connected:
            return False

        # Re-validate token to ensure connection is still good
        return self._validate_token()

    async def _send_request(
        self,
        method: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send a request to Telegram API.

        Args:
            method: API method name (e.g., "sendMessage")
            data: Request payload
            files: Files to upload

        Returns:
            API response as dict
        """
        if not self._connected:
            raise RuntimeError("Not connected to Telegram")

        url = f"{TELEGRAM_API_BASE}/bot{self._bot_token}/{method}"

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                if files:
                    response = await client.post(url, data=data, files=files, timeout=30)
                else:
                    response = await client.post(url, json=data, timeout=30)

                return response.json()
        except ImportError:
            # Fallback to requests (sync)
            import requests

            if files:
                response = requests.post(url, data=data, files=files, timeout=30)
            else:
                response = requests.post(url, json=data, timeout=30)

            return response.json()

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
    ) -> bool:
        """
        Send a text message.

        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Parse mode ("Markdown", "HTML", or None)
            disable_notification: Send silently
            reply_to_message_id: Reply to specific message

        Returns:
            bool: True if sent successfully
        """
        data = {
            "chat_id": chat_id,
            "text": text,
        }

        if parse_mode:
            data["parse_mode"] = parse_mode
        if disable_notification:
            data["disable_notification"] = True
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        try:
            result = await self._send_request("sendMessage", data)
            return result.get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = "Markdown",
    ) -> bool:
        """
        Send a photo.

        Args:
            chat_id: Target chat ID
            photo: Photo URL or file_id
            caption: Photo caption
            parse_mode: Parse mode for caption

        Returns:
            bool: True if sent successfully
        """
        data = {
            "chat_id": chat_id,
            "photo": photo,
        }

        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode

        try:
            result = await self._send_request("sendPhoto", data)
            return result.get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            return False

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get incoming updates using long polling.

        Args:
            offset: Identifier of first update to be returned
            limit: Max number of updates (1-100)
            timeout: Timeout in seconds for long polling

        Returns:
            List of update objects
        """
        data = {
            "limit": min(limit, 100),
            "timeout": timeout,
        }

        if offset is not None:
            data["offset"] = offset

        try:
            result = await self._send_request("getUpdates", data)
            if result.get("ok"):
                return result.get("result", [])
            return []
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
            return []

    def get_bot_info(self) -> Optional[Dict]:
        """
        Get bot information.

        Returns:
            Bot info dict or None if not connected
        """
        return self._bot_info
