"""
API Client Implementations

Unified API clients for external services:
- GrokClient: xAI Grok API
- TelegramClient: Telegram Bot API
- OpenAIClient: OpenAI API
- AnthropicClient: Anthropic Claude API
"""

from core.api.clients.grok import GrokClient, GrokResponse
from core.api.clients.telegram import TelegramClient, TelegramResponse

__all__ = [
    "GrokClient",
    "GrokResponse",
    "TelegramClient",
    "TelegramResponse",
]
