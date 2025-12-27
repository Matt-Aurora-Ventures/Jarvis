import json
import os
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
KEYS_PATH = ROOT / "secrets" / "keys.json"


def _load_keys() -> Dict[str, str]:
    try:
        with open(KEYS_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_key(name: str, env_name: str) -> str:
    keys = _load_keys()
    value = keys.get(name, "")
    if value:
        return value
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


def get_anthropic_key() -> str:
    return get_key("anthropic_api_key", "ANTHROPIC_API_KEY")


def get_openai_key() -> str:
    return get_key("openai_api_key", "OPENAI_API_KEY")


def get_brave_key() -> str:
    return get_key("brave_api_key", "BRAVE_API_KEY")
