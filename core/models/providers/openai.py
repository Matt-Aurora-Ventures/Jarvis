"""OpenAI provider implementation."""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import List

logger = logging.getLogger(__name__)

_OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider:
    """Provider for OpenAI models (GPT-4, GPT-4o, etc)."""

    def __init__(self, api_key: str = "", **kwargs):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (falls back to OPENAI_API_KEY env var)
            **kwargs: model, max_tokens, temperature, system
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
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
        Generate completion using OpenAI Chat Completions API (synchronous).

        Args:
            prompt: Input prompt (treated as user message)
            **kwargs: Override defaults: model, max_tokens, temperature, system

        Returns:
            Generated text string
        """
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        model = kwargs.get("model", self.model)
        try:
            max_tokens = int(kwargs.get("max_tokens", self.max_tokens))
        except (ValueError, TypeError):
            max_tokens = self.max_tokens
        try:
            temperature = float(kwargs.get("temperature", self.temperature))
        except (ValueError, TypeError):
            temperature = self.temperature
        system = kwargs.get("system", "You are a helpful assistant.")

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
            _OPENAI_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            logger.error("OpenAI API error %s: %s", exc.code, body_err)
            raise RuntimeError(f"OpenAI API returned {exc.code}: {body_err}") from exc
        except Exception as exc:
            logger.error("OpenAIProvider.generate() failed: %s", exc)
            raise

    def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1",
            "o1-mini",
        ]
