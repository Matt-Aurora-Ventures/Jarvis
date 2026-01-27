"""Core secrets package for centralized secret management.

This package is imported as `core.secrets`. A legacy module also exists at
`core/secrets.py` with key validation helpers. To avoid import collisions,
we expose those helpers here so callers can always import from `core.secrets`.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from .vault import SecretVault, get_vault, reset_vault

ROOT = Path(__file__).resolve().parents[2]
KEYS_PATH = ROOT / "secrets" / "keys.json"


def _load_keys() -> Dict[str, Any]:
    try:
        with open(KEYS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_key(name: str, env_name: str) -> str:
    """Get API key from secrets file or environment."""
    keys = _load_keys()

    # Try flat format first
    value = keys.get(name, "")
    if value and isinstance(value, str):
        return value

    # Try nested format: extract base name and look for dict
    base_name = name.replace("_api_key", "").replace("_key", "")
    nested = keys.get(base_name, {})
    if isinstance(nested, dict):
        value = nested.get("api_key", "") or nested.get("key", "")
        if value:
            return str(value)

    # Fall back to environment variable
    return os.getenv(env_name, "")


def get_gemini_key() -> str:
    value = get_key("google_api_key", "GOOGLE_API_KEY")
    if not value:
        value = os.getenv("GEMINI_API_KEY", "")

    # Sanitize common copy-paste error
    if value and "YOUR_API_KEY_HERE" in value:
        value = value.replace("YOUR_API_KEY_HERE", "")
    return value.strip()


def get_groq_key() -> str:
    return get_key("groq_api_key", "GROQ_API_KEY")


def get_grok_key() -> str:
    """Get X.AI Grok API key (optional - for sentiment analysis)."""
    return get_key("xai_api_key", "XAI_API_KEY")


def get_anthropic_key() -> str:
    try:
        from core.llm.anthropic_utils import get_anthropic_api_key

        key = get_anthropic_api_key()
        if key:
            return key
    except Exception:
        pass
    return get_key("anthropic_api_key", "ANTHROPIC_API_KEY")


def get_openai_key() -> str:
    return get_key("openai_api_key", "OPENAI_API_KEY")


def get_brave_key() -> str:
    return get_key("brave_api_key", "BRAVE_API_KEY")


def get_minimax_key() -> str:
    """Get standalone Minimax API key."""
    return get_key("minimax_api_key", "MINIMAX_API_KEY")


def get_openrouter_key() -> str:
    """Get OpenRouter API key (PRIMARY provider for MiniMax 2.1)."""
    return get_key("openrouter_api_key", "OPENROUTER_API_KEY")


def get_birdeye_key() -> str:
    """Get BirdEye API key for token discovery."""
    return get_key("birdeye_api_key", "BIRDEYE_API_KEY")


def get_lunarcrush_key() -> str:
    """Get LunarCrush API key for social metrics."""
    return get_key("lunarcrush_api_key", "LUNARCRUSH_API_KEY")


def get_cryptopanic_key() -> str:
    """Get CryptoPanic API key for news."""
    return get_key("cryptopanic_api_key", "CRYPTOPANIC_API_KEY")


def get_finnhub_key() -> str:
    """Get Finnhub API key for market news."""
    return get_key("finnhub_api_key", "FINNHUB_API_KEY")


def get_twitter_key() -> str:
    """Get Twitter/X API key."""
    return get_key("x_api_key", "X_API_KEY") or get_key("twitter_api_key", "TWITTER_API_KEY")


def get_coinglass_key() -> str:
    """Get Coinglass API key for derivatives data."""
    return get_key("coinglass_api_key", "COINGLASS_API_KEY")


def list_configured_keys() -> Dict[str, bool]:
    """List all API keys and whether they're configured."""
    return {
        # LLM providers
        "openrouter": bool(get_openrouter_key()),
        "groq": bool(get_groq_key()),
        "grok": bool(get_grok_key()),
        "gemini": bool(get_gemini_key()),
        "openai": bool(get_openai_key()),
        "anthropic": bool(get_anthropic_key()),
        "minimax": bool(get_minimax_key()),
        # Data providers
        "birdeye": bool(get_birdeye_key()),
        "lunarcrush": bool(get_lunarcrush_key()),
        "cryptopanic": bool(get_cryptopanic_key()),
        "finnhub": bool(get_finnhub_key()),
        "coinglass": bool(get_coinglass_key()),
        # Social/Search
        "brave": bool(get_brave_key()),
        "twitter": bool(get_twitter_key()),
    }


def validate_required_keys(required: list = None) -> tuple:
    """Validate that required API keys are configured."""
    if required is None:
        required = ["anthropic", "grok", "twitter", "birdeye"]

    configured = list_configured_keys()
    missing = [key for key in required if not configured.get(key, False)]

    return len(missing) == 0, missing


def print_key_status():
    """Print a formatted status of all configured keys."""
    import logging

    logger = logging.getLogger(__name__)

    configured = list_configured_keys()
    configured_count = sum(1 for v in configured.values() if v)
    total = len(configured)

    logger.info(f"API Keys: {configured_count}/{total} configured")
    for key, is_set in configured.items():
        status = "OK" if is_set else "MISSING"
        logger.debug(f"  {key}: {status}")


__all__ = [
    "SecretVault",
    "get_vault",
    "reset_vault",
    "get_key",
    "get_gemini_key",
    "get_groq_key",
    "get_grok_key",
    "get_anthropic_key",
    "get_openai_key",
    "get_brave_key",
    "get_minimax_key",
    "get_openrouter_key",
    "get_birdeye_key",
    "get_lunarcrush_key",
    "get_cryptopanic_key",
    "get_finnhub_key",
    "get_twitter_key",
    "get_coinglass_key",
    "list_configured_keys",
    "validate_required_keys",
    "print_key_status",
]
