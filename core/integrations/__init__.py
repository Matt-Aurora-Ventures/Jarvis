"""
Platform integrations for Jarvis.
Provides connections to Trello, Gmail, Google Calendar, LinkedIn, X/Twitter, GitHub,
and automated sentiment bots for Telegram and X.
"""

from .trello_integration import TrelloIntegration
from .gmail_integration import GmailIntegration
from .google_calendar_integration import GoogleCalendarIntegration
from .github_integration import GitHubIntegration

# Sentiment bots (lazy import to avoid dependency issues)
try:
    from .telegram_sentiment_bot import (
        TelegramSentimentBot,
        get_bot as get_telegram_bot,
        start as start_telegram_bot,
        stop as stop_telegram_bot,
        push_sentiment as telegram_push_sentiment,
        push_report as telegram_push_report,
    )
except ImportError:
    TelegramSentimentBot = None
    get_telegram_bot = None
    start_telegram_bot = None
    stop_telegram_bot = None
    telegram_push_sentiment = None
    telegram_push_report = None

try:
    from .x_sentiment_bot import (
        XSentimentBot,
        get_bot as get_x_bot,
        start as start_x_bot,
        stop as stop_x_bot,
        post_sentiment as x_post_sentiment,
        post_report as x_post_report,
    )
except ImportError:
    XSentimentBot = None
    get_x_bot = None
    start_x_bot = None
    stop_x_bot = None
    x_post_sentiment = None
    x_post_report = None

__all__ = [
    # Core integrations
    "TrelloIntegration",
    "GmailIntegration",
    "GoogleCalendarIntegration",
    "GitHubIntegration",
    # Telegram bot
    "TelegramSentimentBot",
    "get_telegram_bot",
    "start_telegram_bot",
    "stop_telegram_bot",
    "telegram_push_sentiment",
    "telegram_push_report",
    # X bot
    "XSentimentBot",
    "get_x_bot",
    "start_x_bot",
    "stop_x_bot",
    "x_post_sentiment",
    "x_post_report",
]
