"""Utilities for Anthropic-compatible endpoints (including local Ollama)."""

from __future__ import annotations

import os
from typing import Optional


DEFAULT_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def get_anthropic_base_url() -> Optional[str]:
    """Return optional Anthropic base URL override."""
    base_url = os.getenv("OLLAMA_ANTHROPIC_BASE_URL", "").strip()
    if not base_url:
        base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip()
    return base_url or None


def get_anthropic_messages_url() -> str:
    """Resolve the Anthropic messages URL, honoring any base URL override."""
    base_url = get_anthropic_base_url()
    if not base_url:
        return DEFAULT_ANTHROPIC_MESSAGES_URL

    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"
