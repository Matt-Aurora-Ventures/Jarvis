"""
OpenAI LLM Service Adapter

Provides async interface to OpenAI's API.
Supports GPT-4, GPT-3.5-turbo, and compatible endpoints.

Features:
- Full tool/function calling support
- Streaming support
- Token usage tracking
- Health checks

Usage:
    adapter = OpenAILLMAdapter(api_key="...")
    response = await adapter.generate("Explain quantum computing")
    print(response.content)
"""

import asyncio
import logging
import os
import time
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

# API configuration
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
CONTEXT_LIMITS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
}


class OpenAILLMAdapter(LLMService):
    """
    OpenAI LLM service adapter.

    Implements the LLMService interface for OpenAI's API.
    Handles authentication, streaming, and error normalization.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        base_url: str = OPENAI_API_BASE,
        timeout: float = 60.0,
    ):
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Default model to use
            base_url: API base URL (for compatible endpoints)
            timeout: Request timeout in seconds
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def service_name(self) -> str:
        return "openai"

    def get_model_name(self) -> str:
        return self._model

    def get_context_limit(self) -> int:
        return CONTEXT_LIMITS.get(self._model, 8192)

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._http_client

    def _messages_to_api_format(
        self,
        messages: List[LLMMessage],
    ) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to OpenAI API format."""
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

        client = self._get_http_client()

        try:
            response = await client.post("/chat/completions", json=payload)

            if response.status_code == 401:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="chat",
                    message="Invalid API key",
                    retryable=False,
                )

            if response.status_code == 429:
                # Rate limited
                retry_after = response.headers.get("Retry-After", "60")
                raise ServiceError(
                    service_name=self.service_name,
                    operation="chat",
                    message=f"Rate limited. Retry after {retry_after}s",
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
                content=message.get("content", "") or "",
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
            error_body = ""
            try:
                error_body = e.response.json().get("error", {}).get("message", "")
            except Exception:
                error_body = e.response.text[:200]

            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message=f"HTTP {e.response.status_code}: {error_body}",
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
        """Check OpenAI API availability."""
        if not self._api_key:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                message="No API key configured",
            )

        start_time = time.time()

        try:
            # Simple models list to check connectivity
            client = self._get_http_client()
            response = await client.get("/models")
            latency = (time.time() - start_time) * 1000

            if response.status_code == 401:
                return ServiceHealth(
                    status=ServiceStatus.UNAVAILABLE,
                    latency_ms=latency,
                    message="Invalid API key",
                )

            response.raise_for_status()

            return ServiceHealth(
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
                message="OK",
                metadata={"model": self._model},
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
