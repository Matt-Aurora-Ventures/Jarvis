"""
Notification Channels - Abstract base and concrete channel implementations.

Supports:
- TelegramChannel: Send notifications via Telegram Bot API
- DiscordChannel: Send notifications via Discord webhook (stub)
- EmailChannel: Send notifications via SMTP (stub)
- WebhookChannel: Send notifications via HTTP POST
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import re


class Channel(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Return the channel type identifier."""
        pass

    @abstractmethod
    async def send(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a notification through this channel.

        Args:
            notification: Notification dict with title, message, priority, etc.

        Returns:
            Dict with at minimum: success (bool), and optionally error, message_id
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate the channel configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        pass


class TelegramChannel(Channel):
    """
    Telegram notification channel using Bot API.

    Sends messages to a specific chat using the Telegram Bot API.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        parse_mode: str = "Markdown",
        disable_notification: bool = False,
        timeout: int = 30,
    ):
        """
        Initialize Telegram channel.

        Args:
            bot_token: Telegram Bot API token
            chat_id: Target chat ID (user, group, or channel)
            parse_mode: Message parse mode (Markdown, HTML, or None)
            disable_notification: Send message silently
            timeout: Request timeout in seconds
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._parse_mode = parse_mode
        self._disable_notification = disable_notification
        self._timeout = timeout

    @property
    def channel_type(self) -> str:
        return "telegram"

    def validate_config(self) -> bool:
        """Validate Telegram configuration."""
        return bool(self._bot_token and self._chat_id)

    async def send(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification via Telegram Bot API.

        Args:
            notification: Notification dict

        Returns:
            Dict with success, message_id (on success), or error (on failure)
        """
        if not self.validate_config():
            return {"success": False, "error": "Invalid Telegram configuration"}

        try:
            import aiohttp

            # Format message
            title = notification.get("title", "")
            message = notification.get("message", "")

            if self._parse_mode == "Markdown":
                text = f"*{title}*\n\n{message}" if title else message
            elif self._parse_mode == "HTML":
                text = f"<b>{title}</b>\n\n{message}" if title else message
            else:
                text = f"{title}\n\n{message}" if title else message

            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": text,
                "disable_notification": self._disable_notification,
            }

            if self._parse_mode:
                payload["parse_mode"] = self._parse_mode

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    data = await response.json()

                    if response.status == 200 and data.get("ok"):
                        return {
                            "success": True,
                            "message_id": data.get("result", {}).get("message_id"),
                        }
                    else:
                        return {
                            "success": False,
                            "error": data.get("description", f"HTTP {response.status}"),
                        }

        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class DiscordChannel(Channel):
    """
    Discord notification channel using webhooks.

    Note: This is a stub implementation. Full implementation would
    support rich embeds and mentions.
    """

    def __init__(
        self,
        webhook_url: str,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize Discord channel.

        Args:
            webhook_url: Discord webhook URL
            username: Optional custom username for the bot
            avatar_url: Optional custom avatar URL
            timeout: Request timeout in seconds
        """
        self._webhook_url = webhook_url
        self._username = username
        self._avatar_url = avatar_url
        self._timeout = timeout

    @property
    def channel_type(self) -> str:
        return "discord"

    def validate_config(self) -> bool:
        """Validate Discord webhook URL."""
        if not self._webhook_url:
            return False

        # Basic URL validation
        webhook_pattern = r"^https://discord\.com/api/webhooks/\d+/[\w-]+$"
        return bool(re.match(webhook_pattern, self._webhook_url)) or self._webhook_url.startswith("https://")

    async def send(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification via Discord webhook.

        Note: This is a stub implementation that returns a "not implemented" result.
        For a full implementation, use the Discord webhook API.

        Args:
            notification: Notification dict

        Returns:
            Dict indicating stub status
        """
        if not self.validate_config():
            return {"success": False, "error": "Invalid Discord webhook configuration"}

        # Stub implementation
        # In a real implementation, this would send to the Discord webhook API
        return {
            "success": False,
            "error": "Discord channel not fully implemented (stub)",
            "stub": True,
        }


class EmailChannel(Channel):
    """
    Email notification channel using SMTP.

    Note: This is a stub implementation. Full implementation would
    support HTML emails, attachments, and various SMTP providers.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_address: str = "",
        to_addresses: Optional[List[str]] = None,
        use_tls: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize Email channel.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
            from_address: Sender email address
            to_addresses: List of recipient email addresses
            use_tls: Use TLS encryption
            timeout: Connection timeout in seconds
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._to_addresses = to_addresses or []
        self._use_tls = use_tls
        self._timeout = timeout

    @property
    def channel_type(self) -> str:
        return "email"

    def validate_config(self) -> bool:
        """Validate email configuration."""
        return bool(
            self._smtp_host
            and self._smtp_port > 0
            and self._from_address
            and self._to_addresses
        )

    async def send(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification via email.

        Note: This is a stub implementation that returns a "not implemented" result.
        For a full implementation, use smtplib or aiosmtplib.

        Args:
            notification: Notification dict

        Returns:
            Dict indicating stub status
        """
        if not self.validate_config():
            return {"success": False, "error": "Invalid email configuration"}

        # Stub implementation
        # In a real implementation, this would send via SMTP
        return {
            "success": False,
            "error": "Email channel not fully implemented (stub)",
            "stub": True,
        }


class WebhookChannel(Channel):
    """
    Generic webhook notification channel.

    Sends notifications as JSON payloads to any HTTP endpoint.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        method: str = "POST",
        timeout: int = 30,
    ):
        """
        Initialize Webhook channel.

        Args:
            url: Webhook endpoint URL
            headers: Optional HTTP headers (e.g., authorization)
            method: HTTP method (POST, PUT)
            timeout: Request timeout in seconds
        """
        self._url = url
        self._headers = headers or {}
        self._method = method.upper()
        self._timeout = timeout

    @property
    def channel_type(self) -> str:
        return "webhook"

    def validate_config(self) -> bool:
        """Validate webhook configuration."""
        if not self._url:
            return False

        # Basic URL validation
        url_pattern = r"^https?://.+"
        return bool(re.match(url_pattern, self._url))

    async def send(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification via HTTP webhook.

        Args:
            notification: Notification dict

        Returns:
            Dict with success status
        """
        if not self.validate_config():
            return {"success": False, "error": "Invalid webhook configuration"}

        try:
            import aiohttp

            # Prepare payload
            payload = {
                "notification_id": notification.get("id"),
                "title": notification.get("title"),
                "message": notification.get("message"),
                "priority": notification.get("priority"),
                "type": notification.get("type"),
                "data": notification.get("data", {}),
                "timestamp": notification.get("created_at"),
            }

            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    "json": payload,
                    "headers": self._headers,
                    "timeout": aiohttp.ClientTimeout(total=self._timeout),
                }

                if self._method == "POST":
                    async with session.post(self._url, **request_kwargs) as response:
                        return self._handle_response(response)
                elif self._method == "PUT":
                    async with session.put(self._url, **request_kwargs) as response:
                        return self._handle_response(response)
                else:
                    return {"success": False, "error": f"Unsupported method: {self._method}"}

        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_response(self, response) -> Dict[str, Any]:
        """Handle HTTP response."""
        if response.status < 400:
            return {"success": True, "status_code": response.status}
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status}",
                "status_code": response.status,
            }
