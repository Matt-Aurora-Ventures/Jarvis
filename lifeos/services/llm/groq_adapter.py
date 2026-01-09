"""
Groq LLM Service Adapter

Provides async interface to Groq's ultra-fast inference API.
Supports both the Groq SDK and HTTP fallback.

Features:
- Automatic rate limit handling with backoff
- Thread-safe request throttling
- Streaming support
- Health checks with latency tracking

Usage:
    adapter = GroqLLMAdapter(api_key="...")
    response = await adapter.generate("What is the weather?")
    print(response.content)
"""

import asyncio
import logging
import os
import threading
import time
from datetime import datetime
from typing import AsyncIterator, Dict, List, Optional, Any

import httpx

from lifeos.services.interfaces import (
    LLMService,
    LLMConfig,
    LLMMessage,
    LLMResponse,
    ServiceError,
    ServiceHealth,
    ServiceStatus,
)

logger = logging.getLogger(__name__)

# Rate limiting configuration
_GROQ_LOCK = threading.Lock()
_MIN_CALL_INTERVAL = 1.0  # seconds between calls
_LAST_CALL_TIME = 0.0

# API configuration
GROQ_API_BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
CONTEXT_LIMITS = {
    "llama-3.3-70b-versatile": 131072,
    "llama-3.1-8b-instant": 131072,
    "llama-3.1-70b-versatile": 131072,
    "mixtral-8x7b-32768": 32768,
    "gemma2-9b-it": 8192,
}


class GroqLLMAdapter(LLMService):
    """
    Groq LLM service adapter.

    Implements the LLMService interface for Groq's API.
    Handles rate limiting, retries, and error normalization.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
    ):
        """
        Initialize Groq adapter.

        Args:
            api_key: Groq API key (or set GROQ_API_KEY env var)
            model: Default model to use
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        self._model = model
        self._timeout = timeout
        self._sdk_client = None
        self._http_client: Optional[httpx.AsyncClient] = None

        # Try to initialize SDK client
        if self._api_key:
            try:
                from groq import Groq
                self._sdk_client = Groq(api_key=self._api_key)
            except ImportError:
                logger.debug("Groq SDK not installed, using HTTP fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq SDK: {e}")

    @property
    def service_name(self) -> str:
        return "groq"

    def get_model_name(self) -> str:
        return self._model

    def get_context_limit(self) -> int:
        return CONTEXT_LIMITS.get(self._model, 32768)

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=GROQ_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._http_client

    def _throttle(self) -> None:
        """Enforce minimum interval between calls."""
        global _LAST_CALL_TIME
        with _GROQ_LOCK:
            now = time.time()
            wait = _MIN_CALL_INTERVAL - (now - _LAST_CALL_TIME)
            if wait > 0:
                time.sleep(wait)
            _LAST_CALL_TIME = time.time()

    def _messages_to_api_format(
        self,
        messages: List[LLMMessage],
    ) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Groq API format."""
        result = []
        for msg in messages:
            entry: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    async def generate(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate response from a simple prompt."""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        return await self.chat(messages, config)

    async def chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Generate response from conversation history."""
        if not self._api_key:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message="No API key configured",
                retryable=False,
            )

        config = config or LLMConfig()
        api_messages = self._messages_to_api_format(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty,
        }

        if config.stop:
            payload["stop"] = config.stop
        if config.tools:
            payload["tools"] = config.tools
            if config.tool_choice:
                payload["tool_choice"] = config.tool_choice

        # Throttle requests
        self._throttle()

        # Try SDK first, then HTTP fallback
        if self._sdk_client:
            try:
                return await self._chat_sdk(payload)
            except Exception as e:
                logger.debug(f"SDK call failed, trying HTTP: {e}")

        return await self._chat_http(payload)

    async def _chat_sdk(self, payload: Dict[str, Any]) -> LLMResponse:
        """Use Groq SDK for chat completion."""
        try:
            # Run sync SDK in thread pool
            response = await asyncio.to_thread(
                self._sdk_client.chat.completions.create,
                **payload,
            )

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                finish_reason=choice.finish_reason or "stop",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                tool_calls=choice.message.tool_calls if hasattr(choice.message, "tool_calls") else None,
                raw_response=response,
            )
        except Exception as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message=str(e),
                original_error=e,
                retryable="rate" in str(e).lower() or "429" in str(e),
            )

    async def _chat_http(self, payload: Dict[str, Any]) -> LLMResponse:
        """Use HTTP API for chat completion."""
        client = self._get_http_client()

        try:
            response = await client.post("/chat/completions", json=payload)

            if response.status_code == 429:
                # Rate limited - wait and signal retryable
                await asyncio.sleep(3)
                raise ServiceError(
                    service_name=self.service_name,
                    operation="chat",
                    message="Rate limited (429)",
                    retryable=True,
                )

            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="chat",
                    message="No choices in response",
                    retryable=False,
                )

            choice = choices[0]
            message = choice.get("message", {})
            usage = data.get("usage", {})

            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", self._model),
                finish_reason=choice.get("finish_reason", "stop"),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                tool_calls=message.get("tool_calls"),
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message=f"HTTP {e.response.status_code}: {e.response.text}",
                original_error=e,
                retryable=e.response.status_code in (429, 500, 502, 503, 504),
            )
        except httpx.RequestError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message=str(e),
                original_error=e,
                retryable=True,
            )

    async def stream(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens."""
        if not self._api_key:
            raise ServiceError(
                service_name=self.service_name,
                operation="stream",
                message="No API key configured",
                retryable=False,
            )

        config = config or LLMConfig()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }

        self._throttle()
        client = self._get_http_client()

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            import json
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue

        except httpx.HTTPStatusError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="stream",
                message=f"HTTP {e.response.status_code}",
                original_error=e,
                retryable=e.response.status_code in (429, 500, 502, 503, 504),
            )

    async def health_check(self) -> ServiceHealth:
        """Check Groq API availability and latency."""
        if not self._api_key:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                message="No API key configured",
            )

        start_time = time.time()

        try:
            # Simple test request
            response = await self.generate(
                "Hi",
                config=LLMConfig(max_tokens=5, temperature=0),
            )

            latency = (time.time() - start_time) * 1000

            return ServiceHealth(
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
                message="OK",
                metadata={"model": response.model},
            )

        except ServiceError as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE if not e.retryable else ServiceStatus.DEGRADED,
                latency_ms=(time.time() - start_time) * 1000,
                message=e.message,
            )
        except Exception as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                latency_ms=(time.time() - start_time) * 1000,
                message=str(e),
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
