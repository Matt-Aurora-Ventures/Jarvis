"""Utilities for Anthropic-compatible endpoints (including local Ollama)."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse


DEFAULT_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def _is_local_base_url(base_url: str) -> bool:
    """Return True if the base URL points to localhost."""
    try:
        host = urlparse(base_url).hostname
    except Exception:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def get_anthropic_base_url() -> Optional[str]:
    """Return optional Anthropic base URL override (local-only by default)."""
    base_url = os.getenv("OLLAMA_ANTHROPIC_BASE_URL", "").strip()
    if not base_url:
        base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()

    if not base_url:
        return None

    # Block remote Anthropic endpoints unless explicitly allowed.
    if not _is_local_base_url(base_url) and os.getenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", "").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return None

    return base_url


def is_local_anthropic() -> bool:
    """Return True if Anthropic compatibility is configured locally."""
    base_url = get_anthropic_base_url()
    return bool(base_url and _is_local_base_url(base_url))


def get_anthropic_api_key() -> str:
    """Return an Anthropic-compatible API key, preferring local Ollama."""
    # Use Ollama-compatible tokens first.
    key = os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if not key:
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    # For local Ollama, accept missing keys by using a placeholder.
    if is_local_anthropic():
        return key or "ollama"

    # Remote Anthropic is blocked by default (unless explicitly allowed).
    if os.getenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", "").lower() in ("1", "true", "yes", "on"):
        return key

    return ""


def get_anthropic_messages_url() -> str:
    """Resolve the Anthropic messages URL, honoring any base URL override."""
    base_url = get_anthropic_base_url()
    if not base_url:
        if os.getenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", "").lower() in ("1", "true", "yes", "on"):
            return DEFAULT_ANTHROPIC_MESSAGES_URL
        return ""

    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"
