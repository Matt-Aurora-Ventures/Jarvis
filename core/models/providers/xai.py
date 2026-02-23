"""xAI (X.AI) provider implementation."""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_XAI_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"


class XAIProvider:
    """Provider for xAI models (Grok) using the OpenAI-compatible API."""

    def __init__(self, api_key: str = "", **kwargs):
        """
        Initialize xAI provider.

        Args:
            api_key: xAI API key (falls back to XAI_API_KEY env var)
            **kwargs: Additional configuration options
        """
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")
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
        Generate completion using xAI API (synchronous).

        Args:
            prompt: Input prompt (treated as user message)
            **kwargs: Override defaults: model, max_tokens, temperature, system

        Returns:
            Generated text string
        """
        if not self.api_key:
            raise ValueError("XAI_API_KEY is not configured")

        model = kwargs.get("model", self.model)
        try:
            max_tokens = int(kwargs.get("max_tokens", self.max_tokens))
        except (ValueError, TypeError):
            max_tokens = self.max_tokens
        try:
            temperature = float(kwargs.get("temperature", self.temperature))
        except (ValueError, TypeError):
            temperature = self.temperature
        system = kwargs.get("system", "You are Grok, an AI assistant.")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{_XAI_BASE_URL}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.error("xAI API error %s: %s", exc.code, body)
            raise RuntimeError(f"xAI API returned {exc.code}: {body}") from exc
        except Exception as exc:
            logger.error("xAI generate() failed: %s", exc)
            raise

    def get_available_models(self) -> List[str]:
        """
        Get list of available xAI models.

        Returns:
            List of model names
        """
        return [
            "grok-4-1-fast-non-reasoning",
            "grok-4-1-fast-reasoning",
            "grok-4",
            "grok-3-mini",
            "grok-2-1212",
            "grok-2-vision-1212",
        ]
