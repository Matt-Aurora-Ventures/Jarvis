"""Anthropic AI provider implementation."""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import List

logger = logging.getLogger(__name__)

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider:
    """Provider for Anthropic AI models (Claude)."""

    def __init__(self, api_key: str = "", **kwargs):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var)
            **kwargs: model, max_tokens, temperature, system
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = kwargs.get("model", _DEFAULT_MODEL)
        try:
            self.max_tokens = int(kwargs.get("max_tokens", 1024))
        except (ValueError, TypeError):
            self.max_tokens = 1024
        try:
            self.temperature = float(kwargs.get("temperature", 0.7))
        except (ValueError, TypeError):
            self.temperature = 0.7
        self.config = kwargs

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate completion using Anthropic Messages API (synchronous).

        Args:
            prompt: Input prompt (treated as user message)
            **kwargs: Override defaults: model, max_tokens, temperature, system

        Returns:
            Generated text string
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")

        model = kwargs.get("model", self.model)
        try:
            max_tokens = int(kwargs.get("max_tokens", self.max_tokens))
        except (ValueError, TypeError):
            max_tokens = self.max_tokens
        try:
            temperature = float(kwargs.get("temperature", self.temperature))
        except (ValueError, TypeError):
            temperature = self.temperature
        system = kwargs.get("system", "")

        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            _ANTHROPIC_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            logger.error("Anthropic API error %s: %s", exc.code, body_err)
            raise RuntimeError(f"Anthropic API returned {exc.code}: {body_err}") from exc
        except Exception as exc:
            logger.error("AnthropicProvider.generate() failed: %s", exc)
            raise

    def get_available_models(self) -> List[str]:
        """Get list of available Anthropic models."""
        return [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]
