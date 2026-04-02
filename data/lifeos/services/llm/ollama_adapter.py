"""
Ollama LLM Service Adapter

Provides async interface to locally-running Ollama models.
Supports streaming and multiple model switching.

Features:
- Automatic model availability detection
- Streaming support
- Context window management
- Health checks with model listing

Usage:
    adapter = OllamaLLMAdapter(model="llama3.1")
    response = await adapter.generate("What is Python?")
    print(response.content)
"""

import asyncio
import json
import logging
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

# Default configuration
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"
CONTEXT_LIMITS = {
    "llama3.1": 131072,
    "llama3.1:8b": 131072,
    "llama3.1:70b": 131072,
    "llama2": 4096,
    "mistral": 32768,
    "mixtral": 32768,
    "codellama": 16384,
    "phi3": 128000,
    "gemma2": 8192,
}


class OllamaLLMAdapter(LLMService):
    """
    Ollama LLM service adapter.

    Implements the LLMService interface for local Ollama models.
    Handles model management, streaming, and error normalization.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model: str = DEFAULT_MODEL,
        timeout: float = 120.0,
    ):
        """
        Initialize Ollama adapter.

        Args:
            host: Ollama API host URL
            model: Default model to use
            timeout: Request timeout in seconds
        """
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def service_name(self) -> str:
        return "ollama"

    def get_model_name(self) -> str:
        return self._model

    def get_context_limit(self) -> int:
        # Check for exact match first, then base model name
        if self._model in CONTEXT_LIMITS:
            return CONTEXT_LIMITS[self._model]
        base_model = self._model.split(":")[0]
        return CONTEXT_LIMITS.get(base_model, 4096)

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self._host,
                timeout=self._timeout,
            )
        return self._http_client

    def _messages_to_api_format(
        self,
        messages: List[LLMMessage],
    ) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Ollama API format."""
        result = []
        for msg in messages:
            entry: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            # Ollama doesn't use name/tool_calls in the same way
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
        config = config or LLMConfig()
        api_messages = self._messages_to_api_format(messages)

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
                "num_predict": config.max_tokens,
            },
        }

        if config.stop:
            payload["options"]["stop"] = config.stop

        client = self._get_http_client()

        try:
            response = await client.post("/api/chat", json=payload)

            if response.status_code == 404:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="chat",
                    message=f"Model '{self._model}' not found. Run: ollama pull {self._model}",
                    retryable=False,
                )

            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})

            # Ollama returns tokens in different format
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", self._model),
                finish_reason="stop",
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                raw_response=data,
            )

        except httpx.ConnectError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message="Cannot connect to Ollama. Is it running?",
                original_error=e,
                retryable=True,
            )
        except httpx.HTTPStatusError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="chat",
                message=f"HTTP {e.response.status_code}: {e.response.text}",
                original_error=e,
                retryable=e.response.status_code >= 500,
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
        config = config or LLMConfig()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }

        client = self._get_http_client()

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        message = data.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

        except httpx.ConnectError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="stream",
                message="Cannot connect to Ollama. Is it running?",
                original_error=e,
                retryable=True,
            )
        except httpx.HTTPStatusError as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="stream",
                message=f"HTTP {e.response.status_code}",
                original_error=e,
                retryable=e.response.status_code >= 500,
            )

    async def list_models(self) -> List[str]:
        """List available models."""
        client = self._get_http_client()

        try:
            response = await client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            return []

    async def health_check(self) -> ServiceHealth:
        """Check Ollama availability and model status."""
        start_time = time.time()

        try:
            models = await self.list_models()
            latency = (time.time() - start_time) * 1000

            if not models:
                return ServiceHealth(
                    status=ServiceStatus.DEGRADED,
                    latency_ms=latency,
                    message="Ollama running but no models installed",
                    metadata={"models": []},
                )

            model_available = self._model in models or any(
                m.startswith(self._model.split(":")[0]) for m in models
            )

            if not model_available:
                return ServiceHealth(
                    status=ServiceStatus.DEGRADED,
                    latency_ms=latency,
                    message=f"Model '{self._model}' not available",
                    metadata={"models": models},
                )

            return ServiceHealth(
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
                message="OK",
                metadata={"models": models, "active_model": self._model},
            )

        except ServiceError as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
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
