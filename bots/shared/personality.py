"""
ClawdBot Personality Loader.

Provides a unified interface for loading bot personalities/souls from SOUL.md
files and personality.json configurations. Supports:
- Loading personality configurations for Jarvis, Matt, Friday
- Generating system prompts from personality data
- Extracting structured personality traits
- Adjusting response styles to match bot personality

Usage:
    from bots.shared.personality import load_personality, get_system_prompt

    config = load_personality("jarvis")
    prompt = get_system_prompt("jarvis")
    traits = get_personality_traits("jarvis")
    adjusted = adjust_response_style("hello", "jarvis")
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class PersonalityNotFoundError(Exception):
    """Raised when a requested bot personality is not found."""
    pass


class PersonalityLoadError(Exception):
    """Raised when there's an error loading a personality configuration."""
    pass


@dataclass
class PersonalityConfig:
    """
    Represents a bot's personality configuration.

    This is the main data structure for bot personalities, containing
    structured information extracted from personality.json and SOUL.md files.

    Attributes:
        name: Bot's display name (e.g., "ClawdJarvis")
        role: Bot's role description
        tone: Description of the bot's tone (e.g., "professional, witty")
        expertise_areas: List of areas the bot specializes in
        communication_style: Dict of communication preferences
        example_phrases: List of example phrases/patterns
        restrictions: List of things the bot should not do
        soul_content: Raw content from SOUL.md file
        identity_content: Raw content from IDENTITY.md file
        bootstrap_content: Raw content from BOOTSTRAP.md file
    """

    name: str
    role: str
    tone: str = ""
    expertise_areas: List[str] = field(default_factory=list)
    communication_style: Dict[str, Any] = field(default_factory=dict)
    example_phrases: List[str] = field(default_factory=list)
    restrictions: List[str] = field(default_factory=list)
    soul_content: Optional[str] = None
    identity_content: Optional[str] = None
    bootstrap_content: Optional[str] = None

    # Additional fields from personality.json
    model: str = ""
    style: str = ""
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert PersonalityConfig to dictionary."""
        return {
            "name": self.name,
            "role": self.role,
            "tone": self.tone,
            "expertise_areas": self.expertise_areas,
            "communication_style": self.communication_style,
            "example_phrases": self.example_phrases,
            "restrictions": self.restrictions,
            "soul_content": self.soul_content,
            "identity_content": self.identity_content,
            "bootstrap_content": self.bootstrap_content,
            "model": self.model,
            "style": self.style,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityConfig":
        """Create PersonalityConfig from dictionary."""
        return cls(
            name=data.get("name", ""),
            role=data.get("role", ""),
            tone=data.get("tone", ""),
            expertise_areas=data.get("expertise_areas", []),
            communication_style=data.get("communication_style", {}),
            example_phrases=data.get("example_phrases", []),
            restrictions=data.get("restrictions", []),
            soul_content=data.get("soul_content"),
            identity_content=data.get("identity_content"),
            bootstrap_content=data.get("bootstrap_content"),
            model=data.get("model", ""),
            style=data.get("style", ""),
            capabilities=data.get("capabilities", []),
        )


# Bot name mappings (short name -> directory name)
BOT_NAME_MAP = {
    "jarvis": "clawdjarvis",
    "clawdjarvis": "clawdjarvis",
    "matt": "clawdmatt",
    "clawdmatt": "clawdmatt",
    "friday": "clawdfriday",
    "clawdfriday": "clawdfriday",
}

# Personality cache
_personality_cache: Dict[str, PersonalityConfig] = {}
_cache_lock = threading.Lock()


def _get_bots_dir() -> Path:
    """Get the bots directory path."""
    # bots/shared/personality.py -> bots/
    return Path(__file__).parent.parent


def _normalize_bot_name(bot_name: str) -> str:
    """
    Normalize bot name to directory name.

    Args:
        bot_name: Bot name (case insensitive), e.g., "jarvis", "JARVIS", "clawdjarvis"

    Returns:
        Normalized directory name, e.g., "clawdjarvis"

    Raises:
        PersonalityNotFoundError: If bot name is not recognized
    """
    normalized = bot_name.lower().strip()

    if normalized in BOT_NAME_MAP:
        return BOT_NAME_MAP[normalized]

    raise PersonalityNotFoundError(f"Unknown bot: {bot_name}")


def _load_file_content(file_path: Path) -> Optional[str]:
    """Load file content if it exists, return None otherwise."""
    try:
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error reading {file_path}: {e}")
    return None


def _extract_personality_traits_from_soul(soul_content: str) -> Dict[str, Any]:
    """
    Extract structured personality traits from SOUL.md content.

    Parses the markdown to extract values, traits, style information.
    """
    traits = {
        "values": [],
        "traits": [],
        "boundaries": [],
    }

    if not soul_content:
        return traits

    current_section = None
    lines = soul_content.split("\n")

    for line in lines:
        line = line.strip()

        # Detect section headers
        if line.startswith("## "):
            section = line[3:].lower()
            if "value" in section:
                current_section = "values"
            elif "trait" in section or "personality" in section:
                current_section = "traits"
            elif "boundar" in section or "restrict" in section:
                current_section = "boundaries"
            elif "style" in section or "communication" in section:
                current_section = "style"
            else:
                current_section = None

        # Extract bullet points
        elif line.startswith("- ") and current_section:
            item = line[2:].strip()
            # Clean up bold markers
            item = item.replace("**", "").strip()
            if ":" in item:
                item = item.split(":")[0].strip()
            if item and current_section in traits:
                traits[current_section].append(item)

    return traits


def _build_personality_config(
    bot_dir: Path,
    config_data: Dict[str, Any],
) -> PersonalityConfig:
    """
    Build a PersonalityConfig from config data and soul files.

    Args:
        bot_dir: Path to bot directory
        config_data: Data from personality.json

    Returns:
        Populated PersonalityConfig
    """
    # Load soul files
    soul_path = config_data.get("soul_path")
    identity_path = config_data.get("identity_path")
    bootstrap_path = config_data.get("bootstrap_path")

    soul_content = _load_file_content(bot_dir / soul_path) if soul_path else None
    identity_content = _load_file_content(bot_dir / identity_path) if identity_path else None
    bootstrap_content = _load_file_content(bot_dir / bootstrap_path) if bootstrap_path else None

    # Extract traits from soul content
    soul_traits = _extract_personality_traits_from_soul(soul_content or "")

    # Build communication style dict
    communication_style = {
        "formality": "professional" if "professional" in config_data.get("tone", "").lower() else "casual",
        "verbosity": "concise" if "concise" in config_data.get("style", "").lower() else "normal",
    }

    # Build example phrases from soul content
    example_phrases = []
    if soul_content:
        # Look for example patterns in soul
        if "helpful" in soul_content.lower():
            example_phrases.append("How may I assist you?")
        if "witty" in soul_content.lower():
            example_phrases.append("I'll get right on that, sir.")

    # Build restrictions from soul boundaries
    restrictions = soul_traits.get("boundaries", [])

    return PersonalityConfig(
        name=config_data.get("name", ""),
        role=config_data.get("role", ""),
        tone=config_data.get("tone", ""),
        expertise_areas=config_data.get("capabilities", []),
        communication_style=communication_style,
        example_phrases=example_phrases,
        restrictions=restrictions,
        soul_content=soul_content,
        identity_content=identity_content,
        bootstrap_content=bootstrap_content,
        model=config_data.get("model", ""),
        style=config_data.get("style", ""),
        capabilities=config_data.get("capabilities", []),
    )


def load_personality(bot_name: str) -> PersonalityConfig:
    """
    Load a bot's personality configuration.

    Loads from personality.json and associated SOUL.md files in the bot's
    directory. Results are cached to avoid repeated file reads.

    Args:
        bot_name: Name of the bot (case insensitive)
            - "jarvis" or "clawdjarvis" for ClawdJarvis
            - "matt" or "clawdmatt" for ClawdMatt
            - "friday" or "clawdfriday" for ClawdFriday

    Returns:
        PersonalityConfig with loaded personality data

    Raises:
        PersonalityNotFoundError: If bot not found
        PersonalityLoadError: If config file is invalid

    Example:
        >>> config = load_personality("jarvis")
        >>> print(config.name)
        ClawdJarvis
    """
    dir_name = _normalize_bot_name(bot_name)

    # Check cache
    with _cache_lock:
        if dir_name in _personality_cache:
            return _personality_cache[dir_name]

    # Load from disk
    bots_dir = _get_bots_dir()
    bot_dir = bots_dir / dir_name

    if not bot_dir.exists() or not bot_dir.is_dir():
        raise PersonalityNotFoundError(f"Bot directory not found: {bot_dir}")

    config_path = bot_dir / "personality.json"
    if not config_path.exists():
        raise PersonalityNotFoundError(f"personality.json not found in {bot_dir}")

    try:
        config_text = config_path.read_text(encoding="utf-8")
        config_data = json.loads(config_text)
    except json.JSONDecodeError as e:
        raise PersonalityLoadError(f"Invalid JSON in {config_path}: {e}")
    except Exception as e:
        raise PersonalityLoadError(f"Error reading {config_path}: {e}")

    # Build config
    personality = _build_personality_config(bot_dir, config_data)

    # Cache it
    with _cache_lock:
        _personality_cache[dir_name] = personality

    logger.info(f"Loaded personality for {personality.name}")
    return personality


def reload_personality(bot_name: str) -> PersonalityConfig:
    """
    Reload a bot's personality from disk, clearing the cache.

    Args:
        bot_name: Name of the bot

    Returns:
        Fresh PersonalityConfig loaded from disk
    """
    dir_name = _normalize_bot_name(bot_name)

    with _cache_lock:
        if dir_name in _personality_cache:
            del _personality_cache[dir_name]

    return load_personality(bot_name)


def clear_personality_cache() -> None:
    """Clear all cached personalities."""
    global _personality_cache
    with _cache_lock:
        _personality_cache = {}
    logger.debug("Personality cache cleared")


def get_system_prompt(bot_name: str) -> str:
    """
    Generate a system prompt for the specified bot.

    Creates a comprehensive system prompt that includes:
    - Bot identity and role
    - Tone and style guidance
    - Core values and traits from SOUL
    - Capabilities and restrictions

    Args:
        bot_name: Name of the bot

    Returns:
        Complete system prompt string

    Example:
        >>> prompt = get_system_prompt("jarvis")
        >>> print(prompt[:50])
        You are ClawdJarvis (JARVIS - Just A Rather Very
    """
    config = load_personality(bot_name)

    parts = []

    # Identity section
    parts.append(f"You are {config.name}.")
    parts.append(f"\n## Role\n{config.role}")

    # Tone and style
    if config.tone:
        parts.append(f"\n## Tone\n{config.tone}")
    if config.style:
        parts.append(f"\n## Communication Style\n{config.style}")

    # Include soul content if available
    if config.soul_content:
        parts.append(f"\n## Core Identity and Values\n{config.soul_content}")

    # Include identity content if available
    if config.identity_content:
        parts.append(f"\n## Background\n{config.identity_content}")

    # Capabilities
    if config.capabilities:
        caps_list = ", ".join(config.capabilities)
        parts.append(f"\n## Capabilities\n{caps_list}")

    # Restrictions
    if config.restrictions:
        restrictions_text = "\n- ".join([""] + config.restrictions)
        parts.append(f"\n## Restrictions{restrictions_text}")

    return "\n".join(parts)


def get_personality_traits(bot_name: str) -> Dict[str, Any]:
    """
    Get structured personality traits for a bot.

    Returns a dictionary with key personality information suitable
    for programmatic use (e.g., for conditional logic based on personality).

    Args:
        bot_name: Name of the bot

    Returns:
        Dictionary with keys:
        - name: Bot's display name
        - role: Role description
        - tone: Tone description
        - expertise_areas: List of expertise areas
        - communication_style: Dict of style preferences

    Example:
        >>> traits = get_personality_traits("jarvis")
        >>> print(traits["expertise_areas"])
        ['trading', 'system_control', 'automation', ...]
    """
    config = load_personality(bot_name)

    return {
        "name": config.name,
        "role": config.role,
        "tone": config.tone,
        "expertise_areas": config.expertise_areas,
        "communication_style": config.communication_style,
        "model": config.model,
        "style": config.style,
        "capabilities": config.capabilities,
    }


def adjust_response_style(response: str, bot_name: str) -> str:
    """
    Adjust a response to match the bot's personality style.

    This function takes a raw response and adjusts it to better match
    the expected tone and style of the specified bot. For example:
    - Jarvis: Professional, slightly witty, Iron Man style
    - Matt: Careful, PR-focused, constructive
    - Friday: Warm, email-appropriate, professional

    Args:
        response: The original response text
        bot_name: Name of the bot whose style to apply

    Returns:
        Adjusted response text (may be unchanged if already appropriate)

    Example:
        >>> adjust_response_style("ok done", "jarvis")
        'Very well, the task has been completed.'
    """
    # Handle empty response
    if not response:
        return ""

    # Try to load personality, fall back to passthrough for unknown bots
    try:
        config = load_personality(bot_name)
    except PersonalityNotFoundError:
        return response

    # Apply style adjustments based on bot personality
    adjusted = response

    if config.name == "ClawdJarvis":
        # Jarvis: Professional, competent, slightly formal
        # Replace overly casual phrases
        casual_replacements = {
            "ok ": "Very well, ",
            "Ok ": "Very well, ",
            "OK ": "Very well, ",
            "ok, ": "Very well, ",
            "yeah ": "Yes, ",
            "Yeah ": "Yes, ",
            "gonna ": "going to ",
            "wanna ": "want to ",
            "i did": "I have completed",
            "done": "completed",
            "i'm done": "The task has been completed",
        }

        for casual, professional in casual_replacements.items():
            if casual.lower() in adjusted.lower():
                # Case-insensitive replacement while preserving sentence structure
                import re
                adjusted = re.sub(
                    re.escape(casual),
                    professional,
                    adjusted,
                    flags=re.IGNORECASE,
                    count=1  # Only replace first occurrence
                )

    elif config.name == "ClawdMatt":
        # Matt: PR-focused, careful with claims
        # Add qualifiers to strong statements
        strong_patterns = [
            ("is the best", "is among the best"),
            ("will definitely", "is expected to"),
            ("guaranteed", "highly likely"),
        ]
        for pattern, replacement in strong_patterns:
            adjusted = adjusted.replace(pattern, replacement)

    elif config.name == "ClawdFriday":
        # Friday: Email-appropriate, warm but professional
        # Ensure proper email conventions
        pass  # Friday's style is already appropriate for most text

    return adjusted


# Convenience exports
__all__ = [
    "PersonalityConfig",
    "PersonalityNotFoundError",
    "PersonalityLoadError",
    "load_personality",
    "reload_personality",
    "clear_personality_cache",
    "get_system_prompt",
    "get_personality_traits",
    "adjust_response_style",
]
