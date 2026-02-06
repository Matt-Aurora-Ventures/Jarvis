"""
Moltbook - Knowledge Base Integration for ClawdBots.

Provides peer-to-peer learning capabilities via NotebookLM-style knowledge bases.
Currently uses mock/stub implementation - MCP integration pending.
"""

from .client import MoltbookClient
from .channels import (
    get_bot_channels,
    get_posting_rules,
    validate_channel_name,
    get_channels_by_frequency,
    JARVIS_CHANNELS,
    FRIDAY_CHANNELS,
    MATT_CHANNELS,
)

__all__ = [
    "MoltbookClient",
    "get_bot_channels",
    "get_posting_rules",
    "validate_channel_name",
    "get_channels_by_frequency",
    "JARVIS_CHANNELS",
    "FRIDAY_CHANNELS",
    "MATT_CHANNELS",
]
