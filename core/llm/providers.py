"""
JARVIS Unified LLM Provider - Multi-Backend AI Integration

Supports multiple free and paid LLM backends:
- Ollama (local, free, private)
- Groq (free tier: 30 req/min)
- OpenRouter (free models available)
- xAI/Grok (existing integration)
- OpenAI-compatible endpoints

Dependencies: pip install aiohttp
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import json

try:
    import aiohttp
    from aiohttp import ClientTimeout
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None
    ClientTimeout = None

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""
    OLLAMA = "ollama"
    GROQ = "groq"
    XAI = "xai"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    LOCAL = "local"  # Generic OpenAI-compatible local


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 60
    rate_limit: int = 30  # requests per minute
    priority: int = 0  # Lower = higher priority for fallback
    enabled: bool = True


@dataclass
class LLMResponse:
    """Unified response from any LLM."""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int = 0
    latency_ms: float = 0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant
    content: str


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._request_times: List[float] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Configure timeouts: 60s total, 30s connect (for LLM API calls)
            timeout = ClientTimeout(total=60, connect=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        return len(self._request_times) < self.config.rate_limit

    def _record_request(self):
        """Record a request for rate limiting."""
        self._request_times.append(time.time())

    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Generate a response."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a response."""
        pass

    async def health_check(self) -> bool:
        """Check if provider is available."""
        try:
            response = await self.generate([Message("user", "Hi")])
            return bool(response.content)
        except Exception:
            return False


class OllamaProvider(BaseLLMProvider):
    """
    Ollama - Local LLM provider.

    Free, private, runs on your machine.
    Install: https://ollama.ai
    Models: llama3.2, mistral, codellama, etc.
    """

    DEFAULT_URL = "http://localhost:11434"

    async def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        base_url = self.config.base_url or self.DEFAULT_URL
        session = await self._get_session()

        start = time.time()

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }

        try:
            async with session.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as resp:
                self._record_request()
                data = await resp.json()

                content = data.get("message", {}).get("content", "")
                tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.OLLAMA,
                    model=self.config.model,
                    tokens_used=tokens,
                    latency_ms=(time.time() - start) * 1000,
                    metadata={"eval_duration": data.get("eval_duration")}
                )
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        base_url = self.config.base_url or self.DEFAULT_URL
        session = await self._get_session()

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }

        async with session.post(f"{base_url}/api/chat", json=payload) as resp:
            self._record_request()
            async for line in resp.content:
                if line:
                    try:
                        data = json.loads(line)
                        if content := data.get("message", {}).get("content"):
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            base_url = self.config.base_url or self.DEFAULT_URL
            session = await self._get_session()
            async with session.get(f"{base_url}/api/tags", timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            base_url = self.config.base_url or self.DEFAULT_URL
            session = await self._get_session()
            async with session.get(f"{base_url}/api/tags") as resp:
                data = await resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []


class GroqProvider(BaseLLMProvider):
    """
    Groq - Fast inference, free tier available.

    Free tier: 30 requests/minute
    Models: llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it
    Get API key: https://console.groq.com
    """

    BASE_URL = "https://api.groq.com/openai/v1"

    async def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        session = await self._get_session()
        start = time.time()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        try:
            async with session.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as resp:
                self._record_request()
                data = await resp.json()

                if resp.status != 200:
                    raise Exception(f"Groq API error: {data}")

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.GROQ,
                    model=self.config.model,
                    tokens_used=usage.get("total_tokens", 0),
                    latency_ms=(time.time() - start) * 1000,
                    metadata={"usage": usage}
                )
        except Exception as e:
            logger.error(f"Groq error: {e}")
            raise

    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        session = await self._get_session()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as resp:
            self._record_request()
            async for line in resp.content:
                line = line.decode().strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if content := data["choices"][0].get("delta", {}).get("content"):
                            yield content
                    except json.JSONDecodeError:
                        continue


class XAIProvider(BaseLLMProvider):
    """
    xAI/Grok - Existing JARVIS integration.

    Models: grok-3-mini, grok-3
    """

    BASE_URL = "https://api.x.ai/v1"

    async def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        session = await self._get_session()
        start = time.time()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        try:
            async with session.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as resp:
                self._record_request()
                data = await resp.json()

                if resp.status != 200:
                    raise Exception(f"xAI API error: {data}")

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.XAI,
                    model=self.config.model,
                    tokens_used=usage.get("total_tokens", 0),
                    latency_ms=(time.time() - start) * 1000,
                )
        except Exception as e:
            logger.error(f"xAI error: {e}")
            raise

    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        session = await self._get_session()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as resp:
            self._record_request()
            async for line in resp.content:
                line = line.decode().strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if content := data["choices"][0].get("delta", {}).get("content"):
                            yield content
                    except json.JSONDecodeError:
                        continue


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter - Access to many models, some free.

    Free models available with API key.
    Get key: https://openrouter.ai
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    async def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        if not self._check_rate_limit():
            raise Exception("Rate limit exceeded")

        session = await self._get_session()
        start = time.time()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jarvis-ai",
            "X-Title": "JARVIS AI Assistant"
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        try:
            async with session.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as resp:
                self._record_request()
                data = await resp.json()

                if resp.status != 200:
                    raise Exception(f"OpenRouter API error: {data}")

                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.OPENROUTER,
                    model=self.config.model,
                    tokens_used=usage.get("total_tokens", 0),
                    latency_ms=(time.time() - start) * 1000,
                )
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            raise

    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        # Similar to other OpenAI-compatible streams
        session = await self._get_session()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }

        async with session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as resp:
            self._record_request()
            async for line in resp.content:
                line = line.decode().strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if content := data["choices"][0].get("delta", {}).get("content"):
                            yield content
                    except json.JSONDecodeError:
                        continue


# Provider factory
PROVIDER_CLASSES = {
    LLMProvider.OLLAMA: OllamaProvider,
    LLMProvider.GROQ: GroqProvider,
    LLMProvider.XAI: XAIProvider,
    LLMProvider.OPENROUTER: OpenRouterProvider,
}


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """Create a provider instance from config."""
    provider_class = PROVIDER_CLASSES.get(config.provider)
    if not provider_class:
        raise ValueError(f"Unknown provider: {config.provider}")
    return provider_class(config)


class UnifiedLLM:
    """
    Unified LLM interface with automatic fallback.

    Features:
    - Multiple provider support
    - Automatic fallback on failure
    - Rate limit handling
    - Response caching
    - Health monitoring
    """

    def __init__(self):
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {}
        self._fallback_order: List[LLMProvider] = []
        self._cache: Dict[str, LLMResponse] = {}
        self._cache_ttl = 300  # 5 minutes

    def add_provider(self, config: LLMConfig) -> 'UnifiedLLM':
        """Add a provider to the pool."""
        if config.enabled:
            provider = create_provider(config)
            self.providers[config.provider] = provider
            self._update_fallback_order()
        return self

    def _update_fallback_order(self):
        """Update fallback order based on priority."""
        configs = [(p, self.providers[p].config.priority) for p in self.providers]
        configs.sort(key=lambda x: x[1])
        self._fallback_order = [p for p, _ in configs]

    async def generate(
        self,
        prompt: Union[str, List[Message]],
        provider: Optional[LLMProvider] = None,
        use_cache: bool = True,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response using available providers.

        Falls back to next provider on failure.
        """
        # Convert string to messages
        if isinstance(prompt, str):
            messages = [Message("user", prompt)]
        else:
            messages = prompt

        # Check cache
        cache_key = self._cache_key(messages, kwargs)
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            cached.cached = True
            return cached

        # Determine providers to try
        if provider:
            providers_to_try = [provider] if provider in self.providers else []
        else:
            providers_to_try = self._fallback_order

        last_error = None
        for prov in providers_to_try:
            try:
                llm = self.providers[prov]
                response = await llm.generate(messages, **kwargs)

                # Cache successful response
                if use_cache:
                    self._cache[cache_key] = response

                return response
            except Exception as e:
                logger.warning(f"Provider {prov.value} failed: {e}")
                last_error = e
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")

    async def stream(
        self,
        prompt: Union[str, List[Message]],
        provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a response from available providers."""
        if isinstance(prompt, str):
            messages = [Message("user", prompt)]
        else:
            messages = prompt

        providers_to_try = [provider] if provider else self._fallback_order

        for prov in providers_to_try:
            if prov not in self.providers:
                continue
            try:
                llm = self.providers[prov]
                async for chunk in llm.stream(messages, **kwargs):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Stream provider {prov.value} failed: {e}")
                continue

        raise Exception("All stream providers failed")

    def _cache_key(self, messages: List[Message], kwargs: dict) -> str:
        """Generate cache key for messages."""
        msg_str = "|".join(f"{m.role}:{m.content}" for m in messages)
        return f"{msg_str}|{json.dumps(kwargs, sort_keys=True)}"

    async def health_check(self) -> Dict[LLMProvider, bool]:
        """Check health of all providers."""
        results = {}
        for prov, llm in self.providers.items():
            results[prov] = await llm.health_check()
        return results

    async def close(self):
        """Close all provider sessions."""
        for llm in self.providers.values():
            await llm.close()


# Default configurations for easy setup
def get_default_configs() -> List[LLMConfig]:
    """Get default provider configurations from environment."""
    configs = []

    # Ollama (local, highest priority)
    ollama_url = (
        os.getenv("OLLAMA_URL")
        or os.getenv("OLLAMA_HOST")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    )

    configs.append(LLMConfig(
        provider=LLMProvider.OLLAMA,
        model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        base_url=ollama_url,
        priority=0,
        enabled=True,  # Always try, will fail gracefully if not running
    ))

    # Groq (free tier)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        configs.append(LLMConfig(
            provider=LLMProvider.GROQ,
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=groq_key,
            priority=1,
            rate_limit=30,
        ))

    # xAI/Grok
    xai_key = os.getenv("XAI_API_KEY")
    if xai_key:
        configs.append(LLMConfig(
            provider=LLMProvider.XAI,
            model=os.getenv("XAI_MODEL", "grok-3-mini"),
            api_key=xai_key,
            priority=2,
        ))

    # OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        configs.append(LLMConfig(
            provider=LLMProvider.OPENROUTER,
            model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"),
            api_key=openrouter_key,
            priority=3,
        ))

    return configs


async def create_default_llm() -> UnifiedLLM:
    """Create UnifiedLLM with default configs."""
    llm = UnifiedLLM()
    for config in get_default_configs():
        llm.add_provider(config)
    return llm


# Singleton instance
_llm: Optional[UnifiedLLM] = None


async def get_llm() -> UnifiedLLM:
    """Get singleton LLM instance."""
    global _llm
    if _llm is None:
        _llm = await create_default_llm()
    return _llm


# Quick usage functions
async def quick_generate(prompt: str, **kwargs) -> str:
    """Quick one-off generation."""
    llm = await get_llm()
    response = await llm.generate(prompt, **kwargs)
    return response.content


async def quick_chat(messages: List[Dict[str, str]], **kwargs) -> str:
    """Quick chat completion."""
    llm = await get_llm()
    msg_objects = [Message(m["role"], m["content"]) for m in messages]
    response = await llm.generate(msg_objects, **kwargs)
    return response.content
