"""
Slack Integration for Jarvis.

Provides Slack workspace connectivity for:
- Alert notifications (system health, trading signals)
- Channel messaging (sentiment reports, treasury updates)
- Bot interactions (slash commands, message responses)
- Webhook integrations (real-time event delivery)

Setup:
1. Create Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: chat:write, channels:read, users:read
3. Install to workspace
4. Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET environment variables
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


class SlackChannel(Enum):
    """Predefined Slack channels for Jarvis notifications."""

    ALERTS = "#jarvis-alerts"
    TRADING = "#jarvis-trading"
    SENTIMENT = "#jarvis-sentiment"
    TREASURY = "#jarvis-treasury"
    GENERAL = "#general"


class MessageType(Enum):
    """Types of Slack messages for formatting."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"


@dataclass
class SlackMessage:
    """Structured Slack message."""

    text: str
    channel: str = SlackChannel.GENERAL.value
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    thread_ts: Optional[str] = None
    unfurl_links: bool = False
    unfurl_media: bool = True


@dataclass
class SlackConfig:
    """Slack integration configuration."""

    bot_token: str = ""
    signing_secret: str = ""
    default_channel: str = SlackChannel.ALERTS.value
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Load configuration from environment variables."""
        token = os.getenv("SLACK_BOT_TOKEN", "")
        secret = os.getenv("SLACK_SIGNING_SECRET", "")
        channel = os.getenv("SLACK_DEFAULT_CHANNEL", SlackChannel.ALERTS.value)

        return cls(
            bot_token=token,
            signing_secret=secret,
            default_channel=channel,
            enabled=bool(token),
        )


class SlackIntegration:
    """
    Slack integration client for Jarvis.

    Usage:
        slack = SlackIntegration.from_env()
        if slack.is_configured():
            slack.send_message("#alerts", "System started!")
            slack.send_alert("High CPU usage detected", severity="warning")
    """

    def __init__(self, config: Optional[SlackConfig] = None):
        self.config = config or SlackConfig.from_env()
        self._session = requests.Session()
        if self.config.bot_token:
            self._session.headers["Authorization"] = f"Bearer {self.config.bot_token}"
            self._session.headers["Content-Type"] = "application/json"

    @classmethod
    def from_env(cls) -> "SlackIntegration":
        """Create integration from environment variables."""
        return cls(SlackConfig.from_env())

    def is_configured(self) -> bool:
        """Check if Slack is properly configured."""
        return self.config.enabled and bool(self.config.bot_token)

    def validate_token(self) -> tuple[bool, str]:
        """
        Validate the Slack bot token.

        Returns:
            Tuple of (is_valid, message)
        """
        if not self.config.bot_token:
            return False, (
                "❌ SLACK_BOT_TOKEN not configured!\n"
                "To enable Slack notifications:\n"
                "  1. Create app at: https://api.slack.com/apps\n"
                "  2. Add Bot Token Scopes: chat:write, channels:read\n"
                "  3. Install to workspace\n"
                "  4. Set: export SLACK_BOT_TOKEN='xoxb-your-token'"
            )

        if not self.config.bot_token.startswith("xoxb-"):
            return False, (
                "⚠️ SLACK_BOT_TOKEN format invalid!\n"
                "Bot tokens should start with 'xoxb-'\n"
                f"Got: {self.config.bot_token[:10]}...\n"
                "Get a valid token from: https://api.slack.com/apps"
            )

        # Test the token
        try:
            response = self._api_call("auth.test")
            if response.get("ok"):
                team = response.get("team", "Unknown")
                user = response.get("user", "Unknown")
                return True, f"✓ Connected to {team} as {user}"
            else:
                error = response.get("error", "Unknown error")
                return False, f"❌ Token validation failed: {error}"
        except Exception as e:
            return False, f"❌ Connection error: {e}"

    def _api_call(
        self, method: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a Slack API call.

        Args:
            method: Slack API method name
            data: Request payload

        Returns:
            API response as dict
        """
        if not self.is_configured():
            logger.warning("Slack not configured, skipping API call")
            return {"ok": False, "error": "not_configured"}

        url = f"{SLACK_API_BASE}/{method}"

        try:
            response = self._session.post(url, json=data or {}, timeout=10)
            response.raise_for_status()
            result = response.json()

            if not result.get("ok"):
                logger.warning(f"Slack API error: {result.get('error')}")

            return result

        except requests.exceptions.Timeout:
            logger.error(f"Slack API timeout: {method}")
            return {"ok": False, "error": "timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Slack API request error: {e}")
            return {"ok": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Slack API error: {e}")
            return {"ok": False, "error": str(e)}

    def send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel name or ID
            text: Message text (fallback for notifications)
            blocks: Optional Block Kit blocks for rich formatting
            thread_ts: Optional thread timestamp for replies

        Returns:
            API response
        """
        data = {
            "channel": channel,
            "text": text,
        }

        if blocks:
            data["blocks"] = blocks
        if thread_ts:
            data["thread_ts"] = thread_ts

        result = self._api_call("chat.postMessage", data)

        if result.get("ok"):
            logger.info(f"Sent Slack message to {channel}")
        else:
            logger.error(f"Failed to send Slack message: {result.get('error')}")

        return result

    def send_alert(
        self,
        message: str,
        severity: str = "info",
        context: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a formatted alert message.

        Args:
            message: Alert message
            severity: One of: info, success, warning, error, alert
            context: Additional context data
            channel: Target channel (defaults to alerts channel)

        Returns:
            API response
        """
        # Color mapping for attachment sidebar
        colors = {
            "info": "#2196F3",  # Blue
            "success": "#4CAF50",  # Green
            "warning": "#FF9800",  # Orange
            "error": "#F44336",  # Red
            "alert": "#9C27B0",  # Purple
        }

        # Emoji mapping
        emojis = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "alert": "🚨",
        }

        emoji = emojis.get(severity, "ℹ️")
        color = colors.get(severity, colors["info"])

        # Build blocks
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{severity.upper()}*\n{message}",
                },
            }
        ]

        # Add context if provided
        if context:
            context_text = "\n".join(f"• *{k}:* {v}" for k, v in context.items())
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": context_text}],
                }
            )

        # Add timestamp
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            }
        )

        target_channel = channel or self.config.default_channel
        return self.send_message(target_channel, f"{emoji} {message}", blocks=blocks)

    def send_trading_signal(
        self,
        token: str,
        action: str,
        grade: str,
        confidence: float,
        price: float,
        reasoning: str,
    ) -> Dict[str, Any]:
        """
        Send a trading signal notification.

        Args:
            token: Token symbol
            action: BUY or SELL
            grade: Signal grade (A, B+, B, C, etc.)
            confidence: Confidence score (0-1)
            price: Current price
            reasoning: AI reasoning

        Returns:
            API response
        """
        emoji = "🟢" if action == "BUY" else "🔴"
        grade_emoji = {"A": "⭐", "B+": "✨", "B": "👍", "C": "👌"}.get(grade, "📊")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {action} Signal: ${token}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Grade:* {grade_emoji} {grade}"},
                    {"type": "mrkdwn", "text": f"*Confidence:* {confidence:.1%}"},
                    {"type": "mrkdwn", "text": f"*Price:* ${price:.6f}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:* {datetime.now().strftime('%H:%M:%S')}",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Analysis:*\n{reasoning}"},
            },
        ]

        return self.send_message(
            SlackChannel.TRADING.value,
            f"{emoji} {action} {token} @ ${price:.6f} (Grade: {grade})",
            blocks=blocks,
        )

    def send_treasury_update(
        self,
        balance: float,
        pnl_24h: float,
        positions: int,
        top_performer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send treasury status update.

        Args:
            balance: Total treasury balance in USD
            pnl_24h: 24h P&L percentage
            positions: Number of open positions
            top_performer: Best performing token

        Returns:
            API response
        """
        pnl_emoji = "📈" if pnl_24h >= 0 else "📉"
        pnl_color = "good" if pnl_24h >= 0 else "danger"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "💰 Treasury Update"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Balance:* ${balance:,.2f}"},
                    {"type": "mrkdwn", "text": f"*24h P&L:* {pnl_emoji} {pnl_24h:+.2f}%"},
                    {"type": "mrkdwn", "text": f"*Positions:* {positions}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Top:* {top_performer or 'N/A'}",
                    },
                ],
            },
        ]

        return self.send_message(
            SlackChannel.TREASURY.value,
            f"Treasury: ${balance:,.2f} | 24h: {pnl_24h:+.2f}%",
            blocks=blocks,
        )

    def send_sentiment_report(
        self,
        tokens: List[Dict[str, Any]],
        market_mood: str,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Send sentiment analysis report.

        Args:
            tokens: List of token sentiment data
            market_mood: Overall market sentiment
            timestamp: Report timestamp

        Returns:
            API response
        """
        ts = timestamp or datetime.now()
        mood_emoji = {"bullish": "🐂", "bearish": "🐻", "neutral": "😐"}.get(
            market_mood.lower(), "📊"
        )

        # Build token list
        token_lines = []
        for t in tokens[:10]:  # Top 10
            grade = t.get("grade", "?")
            symbol = t.get("symbol", "???")
            score = t.get("score", 0)
            grade_emoji = {"A": "🟢", "B+": "🟡", "B": "🟠", "C": "🔴"}.get(grade, "⚪")
            token_lines.append(f"{grade_emoji} *{symbol}* - Grade {grade} ({score:.0f})")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 Sentiment Report - {ts.strftime('%H:%M')}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Market Mood:* {mood_emoji} {market_mood.title()}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(token_lines)},
            },
        ]

        return self.send_message(
            SlackChannel.SENTIMENT.value,
            f"Sentiment Report: {market_mood} - {len(tokens)} tokens analyzed",
            blocks=blocks,
        )

    def get_channels(self) -> List[Dict[str, Any]]:
        """Get list of channels the bot can access."""
        result = self._api_call(
            "conversations.list", {"types": "public_channel,private_channel"}
        )
        return result.get("channels", [])

    def get_channel_id(self, channel_name: str) -> Optional[str]:
        """
        Get channel ID from channel name.

        Args:
            channel_name: Channel name (with or without #)

        Returns:
            Channel ID or None if not found
        """
        name = channel_name.lstrip("#")
        channels = self.get_channels()
        for ch in channels:
            if ch.get("name") == name:
                return ch.get("id")
        return None


# =============================================================================
# Module-level convenience functions
# =============================================================================

_integration: Optional[SlackIntegration] = None


def get_slack() -> SlackIntegration:
    """Get or create the global Slack integration instance."""
    global _integration
    if _integration is None:
        _integration = SlackIntegration.from_env()
    return _integration


def send_alert(
    message: str,
    severity: str = "info",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send an alert via Slack (convenience function)."""
    return get_slack().send_alert(message, severity, context)


def send_message(channel: str, text: str) -> Dict[str, Any]:
    """Send a message to Slack (convenience function)."""
    return get_slack().send_message(channel, text)


def is_configured() -> bool:
    """Check if Slack is configured (convenience function)."""
    return get_slack().is_configured()
