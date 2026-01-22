"""Minimal Ollama client for AI runtime agents."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger("jarvis.ai_runtime.ollama")


@dataclass
class OllamaResponse:
    success: bool
    text: str = ""
    error: Optional[str] = None


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 12):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> OllamaResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            timeout = aiohttp.ClientTimeout(total=float(self.timeout_seconds))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        return OllamaResponse(success=False, error=f"status {resp.status}")
                    data = await resp.json()
                    text = ""
                    if isinstance(data, dict):
                        message = data.get("message") or {}
                        text = (message.get("content") or "").strip()
                    return OllamaResponse(success=True, text=text)
        except Exception as exc:
            logger.debug(f"Ollama chat failed: {exc}")
            return OllamaResponse(success=False, error=str(exc))
