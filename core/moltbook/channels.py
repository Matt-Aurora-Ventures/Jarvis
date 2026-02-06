"""
Moltbook Channel Configurations for ClawdBots.

Defines channel subscriptions, priorities, and posting rules for each bot:
- Jarvis (CTO): Technical channels - bugtracker, devops, security, crypto
- Friday (CMO): Marketing channels - marketing, trending, copywriting, brand
- Matt (COO): Strategy channels - strategy, synthesis, growth, operations

All bots share the m/kr8tiv channel for team coordination.

TODO: MCP - Channel configurations may be dynamically loaded from MCP
in future versions.
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Channel Definitions
# =============================================================================

JARVIS_CHANNELS: List[Dict[str, Any]] = [
    {
        "channel": "m/bugtracker",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": True,
        "description": "Bug reports, fixes, and debugging learnings",
    },
    {
        "channel": "m/devops",
        "priority": "MEDIUM",
        "read_frequency": "every_4_hours",
        "contribute": True,
        "description": "DevOps, deployment, and infrastructure",
    },
    {
        "channel": "m/security",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": False,  # Read-only for security updates
        "description": "Security advisories and vulnerability disclosures",
    },
    {
        "channel": "m/crypto",
        "priority": "MEDIUM",
        "read_frequency": "every_4_hours",
        "contribute": True,
        "description": "Cryptocurrency, blockchain, and Solana development",
    },
    {
        "channel": "m/kr8tiv",
        "priority": "HIGH",
        "read_frequency": "every_30_minutes",
        "contribute": True,
        "description": "KR8TIV team coordination and shared learnings",
    },
]

FRIDAY_CHANNELS: List[Dict[str, Any]] = [
    {
        "channel": "m/marketing",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": True,
        "description": "Marketing strategies and campaign insights",
    },
    {
        "channel": "m/trending",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": False,  # Observe trends, don't post
        "description": "Current trends and viral content analysis",
    },
    {
        "channel": "m/copywriting",
        "priority": "MEDIUM",
        "read_frequency": "daily",
        "contribute": True,
        "description": "Copywriting tips, templates, and examples",
    },
    {
        "channel": "m/brand",
        "priority": "MEDIUM",
        "read_frequency": "daily",
        "contribute": True,
        "description": "Brand voice, identity, and guidelines",
    },
    {
        "channel": "m/kr8tiv",
        "priority": "HIGH",
        "read_frequency": "every_30_minutes",
        "contribute": True,
        "description": "KR8TIV team coordination and shared learnings",
    },
]

MATT_CHANNELS: List[Dict[str, Any]] = [
    {
        "channel": "m/strategy",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": True,
        "description": "Business strategy and planning",
    },
    {
        "channel": "m/synthesis",
        "priority": "HIGH",
        "read_frequency": "every_hour",
        "contribute": True,
        "description": "Cross-functional synthesis and insights",
    },
    {
        "channel": "m/growth",
        "priority": "MEDIUM",
        "read_frequency": "every_4_hours",
        "contribute": True,
        "description": "Growth metrics, experiments, and optimization",
    },
    {
        "channel": "m/operations",
        "priority": "MEDIUM",
        "read_frequency": "every_4_hours",
        "contribute": True,
        "description": "Operational processes and efficiency",
    },
    {
        "channel": "m/kr8tiv",
        "priority": "HIGH",
        "read_frequency": "every_30_minutes",
        "contribute": True,
        "description": "KR8TIV team coordination and shared learnings",
    },
]

# =============================================================================
# Posting Rules
# =============================================================================

POSTING_RULES: Dict[str, Dict[str, Any]] = {
    "jarvis": {
        "require_approval": False,  # CTO can post technical content freely
        "max_posts_per_day": 5,
        "min_confidence": 0.8,
        "allowed_topics": ["bugs", "fixes", "devops", "crypto", "technical"],
    },
    "friday": {
        "require_approval": True,  # CMO needs Matt approval for public posts
        "max_posts_per_day": 3,
        "min_confidence": 0.85,  # Higher bar for marketing content
        "allowed_topics": ["marketing", "brand", "copywriting", "trends"],
    },
    "matt": {
        "require_approval": False,  # COO approves others, doesn't need approval
        "max_posts_per_day": 4,
        "min_confidence": 0.8,
        "allowed_topics": ["strategy", "synthesis", "growth", "operations"],
    },
}

# Channel name validation pattern
CHANNEL_NAME_PATTERN = re.compile(r"^m/[a-z0-9_-]+$")


# =============================================================================
# Public Functions
# =============================================================================


def get_bot_channels(bot_name: str) -> List[Dict[str, Any]]:
    """
    Get channel configurations for a specific bot.

    Args:
        bot_name: Bot identifier (jarvis, friday, matt, or with clawdb prefix)

    Returns:
        List of channel configurations

    Example:
        >>> channels = get_bot_channels("jarvis")
        >>> channels[0]["channel"]
        'm/bugtracker'
    """
    # Normalize bot name
    name = bot_name.lower().replace("clawdb", "").replace("clawd", "")

    if name in ("jarvis", "j"):
        return JARVIS_CHANNELS.copy()
    elif name in ("friday", "f"):
        return FRIDAY_CHANNELS.copy()
    elif name in ("matt", "m"):
        return MATT_CHANNELS.copy()
    else:
        logger.warning(f"Unknown bot name: {bot_name}, returning empty channels")
        return []


def get_posting_rules(bot_name: str) -> Dict[str, Any]:
    """
    Get posting rules for a specific bot.

    Args:
        bot_name: Bot identifier

    Returns:
        Dictionary of posting rules

    Example:
        >>> rules = get_posting_rules("friday")
        >>> rules["require_approval"]
        True
    """
    # Normalize bot name
    name = bot_name.lower().replace("clawdb", "").replace("clawd", "")

    if name in ("jarvis", "j"):
        return POSTING_RULES["jarvis"].copy()
    elif name in ("friday", "f"):
        return POSTING_RULES["friday"].copy()
    elif name in ("matt", "m"):
        return POSTING_RULES["matt"].copy()
    else:
        # Default restrictive rules for unknown bots
        logger.warning(f"Unknown bot name: {bot_name}, using default rules")
        return {
            "require_approval": True,
            "max_posts_per_day": 1,
            "min_confidence": 0.9,
            "allowed_topics": [],
        }


def validate_channel_name(channel: str) -> bool:
    """
    Validate a channel name follows the correct format.

    Valid format: m/<alphanumeric-with-underscores-and-hyphens>

    Args:
        channel: Channel name to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_channel_name("m/bugtracker")
        True
        >>> validate_channel_name("bugtracker")
        False
        >>> validate_channel_name("m/")
        False
    """
    if not channel or not isinstance(channel, str):
        return False

    # Check for m/ prefix
    if not channel.startswith("m/"):
        return False

    # Check for empty name after prefix
    if len(channel) <= 2:
        return False

    # Validate format with regex
    return bool(CHANNEL_NAME_PATTERN.match(channel))


def get_channels_by_frequency(
    bot_name: str,
    frequency: str,
) -> List[Dict[str, Any]]:
    """
    Get channels filtered by read frequency.

    Args:
        bot_name: Bot identifier
        frequency: Target frequency (e.g., "every_hour", "every_30_minutes")

    Returns:
        List of channels matching the frequency

    Example:
        >>> hourly = get_channels_by_frequency("jarvis", "every_hour")
        >>> all(c["read_frequency"] == "every_hour" for c in hourly)
        True
    """
    channels = get_bot_channels(bot_name)
    return [c for c in channels if c.get("read_frequency") == frequency]


def get_all_shared_channels() -> List[str]:
    """
    Get list of channels that all bots share.

    Returns:
        List of shared channel names
    """
    jarvis_channels = {c["channel"] for c in JARVIS_CHANNELS}
    friday_channels = {c["channel"] for c in FRIDAY_CHANNELS}
    matt_channels = {c["channel"] for c in MATT_CHANNELS}

    shared = jarvis_channels & friday_channels & matt_channels
    return list(shared)


def get_contributer_channels(bot_name: str) -> List[Dict[str, Any]]:
    """
    Get channels where the bot can contribute (post).

    Args:
        bot_name: Bot identifier

    Returns:
        List of channels with contribute=True
    """
    channels = get_bot_channels(bot_name)
    return [c for c in channels if c.get("contribute", False)]
