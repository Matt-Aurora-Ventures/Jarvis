"""
Model Router - Intelligent AI model selection for JARVIS.

Routes tasks to the best AI model based on:
- Task type (trading, code, chat, vision)
- Priority (speed, accuracy, cost)
- Provider availability
- Fallback chains
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """Capabilities that models can have."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    LONG_CONTEXT = "long_context"
    FAST_RESPONSE = "fast_response"
    LOW_COST = "low_cost"


class RoutingPriority(Enum):
    """Routing priority options."""
    SPEED = "speed"       # Fastest response
    ACCURACY = "accuracy" # Best quality
    COST = "cost"         # Cheapest option
    BALANCED = "balanced" # Balance all factors


@dataclass
class ModelProvider:
    """Configuration for a model provider."""
    name: str
    model_id: str
    api_key_env: str  # Environment variable name for API key
    capabilities: List[ModelCapability]
    priority: int = 1  # Lower = higher priority
    latency_ms: int = 500  # Expected latency
    cost_per_1k_tokens: float = 0.01
    max_tokens: int = 4096
    enabled: bool = True
    rate_limit: int = 60  # Requests per minute
    last_error: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "model_id": self.model_id,
            "capabilities": [c.value for c in self.capabilities],
            "priority": self.priority,
            "latency_ms": self.latency_ms,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "max_tokens": self.max_tokens,
            "enabled": self.enabled,
            "rate_limit": self.rate_limit,
            "error_count": self.error_count,
            "success_count": self.success_count,
        }

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.error_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        if not self.enabled:
            return False
        if self.last_error:
            # Cool down after errors
            cooldown = timedelta(minutes=5 * min(self.error_count, 6))
            if datetime.utcnow() - self.last_error < cooldown:
                return False
        return True


@dataclass
class RoutingResult:
    """Result of a routing decision."""
    provider: ModelProvider
    response: str
    latency_ms: float
    tokens_used: int = 0
    cost: float = 0.0
    fallback_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# Default provider configurations
DEFAULT_PROVIDERS = [
    ModelProvider(
        name="groq",
        model_id="llama-3.2-70b-versatile",
        api_key_env="GROQ_API_KEY",
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.FAST_RESPONSE,
            ModelCapability.LOW_COST,
        ],
        priority=1,
        latency_ms=100,
        cost_per_1k_tokens=0.001,
        max_tokens=8192,
    ),
    ModelProvider(
        name="grok",
        model_id="grok-2-latest",
        api_key_env="XAI_API_KEY",
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.FUNCTION_CALLING,
        ],
        priority=2,
        latency_ms=300,
        cost_per_1k_tokens=0.005,
        max_tokens=32768,
    ),
    ModelProvider(
        name="claude",
        model_id="claude-3-5-sonnet-20241022",
        api_key_env="ANTHROPIC_API_KEY",
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CODE_GENERATION,
            ModelCapability.VISION,
            ModelCapability.LONG_CONTEXT,
            ModelCapability.FUNCTION_CALLING,
        ],
        priority=3,
        latency_ms=500,
        cost_per_1k_tokens=0.015,
        max_tokens=200000,
    ),
    ModelProvider(
        name="openrouter",
        model_id="minimax/minimax-01",
        api_key_env="OPENROUTER_API_KEY",
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.LONG_CONTEXT,
        ],
        priority=4,
        latency_ms=400,
        cost_per_1k_tokens=0.002,
        max_tokens=1000000,
    ),
    ModelProvider(
        name="ollama",
        model_id="llama3.2",
        api_key_env="",  # Local, no key needed
        capabilities=[
            ModelCapability.TEXT_GENERATION,
            ModelCapability.LOW_COST,
        ],
        priority=99,  # Fallback only
        latency_ms=200,
        cost_per_1k_tokens=0.0,
        max_tokens=8192,
    ),
]


class ModelRouter:
    """
    Intelligent model router for JARVIS.

    Automatically selects the best AI model based on:
    - Task requirements
    - Provider availability
    - Cost/speed/accuracy preferences
    """

    def __init__(self, providers: Optional[List[ModelProvider]] = None):
        self.providers = providers or DEFAULT_PROVIDERS.copy()
        self._request_counts: Dict[str, List[datetime]] = {}
        self._cache: Dict[str, Tuple[str, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    def add_provider(self, provider: ModelProvider) -> None:
        """Add a new provider."""
        self.providers.append(provider)

    def get_stats(self) -> Dict[str, Any]:
        """Return provider health and usage stats."""
        return {
            "providers": [provider.to_dict() for provider in self.providers],
            "cache_entries": len(self._cache),
        }

    def remove_provider(self, name: str) -> bool:
        """Remove a provider by name."""
        for i, p in enumerate(self.providers):
            if p.name == name:
                self.providers.pop(i)
                return True
        return False

    def get_provider(self, name: str) -> Optional[ModelProvider]:
        """Get provider by name."""
        for p in self.providers:
            if p.name == name:
                return p
        return None

    async def route(
        self,
        task: str,
        priority: RoutingPriority = RoutingPriority.BALANCED,
        required_capabilities: Optional[List[ModelCapability]] = None,
        provider: Optional[str] = None,
        image: Optional[bytes] = None,
        max_tokens: int = 2048,
        use_cache: bool = True,
        fallback_used: bool = False,
    ) -> RoutingResult:
        """
        Route a task to the best available model.

        Args:
            task: The task/prompt to send
            priority: Routing priority (speed, accuracy, cost, balanced)
            required_capabilities: Required model capabilities
            provider: Force specific provider
            image: Optional image for vision tasks
            max_tokens: Maximum response tokens
            use_cache: Use response cache

        Returns:
            RoutingResult with response and metadata
        """
        start_time = time.time()

        # Check cache
        if use_cache:
            cache_key = f"{task[:100]}:{priority.value}"
            if cache_key in self._cache:
                cached, cached_at = self._cache[cache_key]
                if datetime.utcnow() - cached_at < self._cache_ttl:
                    return RoutingResult(
                        provider=self.providers[0],
                        response=cached,
                        latency_ms=0,
                        metadata={"from_cache": True},
                    )

        # Auto-detect required capabilities
        if required_capabilities is None:
            required_capabilities = self._detect_capabilities(task, image)

        # Select provider
        if provider:
            selected = self.get_provider(provider)
            if not selected or not selected.is_healthy():
                raise ValueError(f"Provider {provider} not available")
        else:
            selected = self._select_provider(priority, required_capabilities)

        if not selected:
            raise RuntimeError("No available providers")

        # Check rate limit
        if not self._check_rate_limit(selected.name):
            # Try fallback
            fallback = self._get_fallback(selected, required_capabilities)
            if fallback:
                selected = fallback
                fallback_used = True
            else:
                raise RuntimeError(f"Rate limit exceeded for {selected.name}")

        # Execute request
        try:
            response = await self._execute_request(selected, task, image, max_tokens)

            # Record success
            selected.success_count += 1
            self._record_request(selected.name)

            latency_ms = (time.time() - start_time) * 1000

            result = RoutingResult(
                provider=selected,
                response=response,
                latency_ms=latency_ms,
                tokens_used=len(response) // 4,  # Rough estimate
                cost=len(response) / 4000 * selected.cost_per_1k_tokens,
                fallback_used=fallback_used,
            )

            # Cache result
            if use_cache:
                self._cache[cache_key] = (response, datetime.utcnow())

            return result

        except Exception as e:
            logger.error(f"Error with provider {selected.name}: {e}")
            selected.error_count += 1
            selected.last_error = datetime.utcnow()

            # Try fallback
            fallback = self._get_fallback(selected, required_capabilities)
            if fallback:
                logger.info(f"Falling back to {fallback.name}")
                return await self.route(
                    task=task,
                    priority=priority,
                    required_capabilities=required_capabilities,
                    provider=fallback.name,
                    image=image,
                    max_tokens=max_tokens,
                    use_cache=False,
                    fallback_used=True,
                )

            raise

    def _detect_capabilities(
        self,
        task: str,
        image: Optional[bytes],
    ) -> List[ModelCapability]:
        """Auto-detect required capabilities from task."""
        capabilities = [ModelCapability.TEXT_GENERATION]

        if image:
            capabilities.append(ModelCapability.VISION)

        # Code-related keywords
        code_keywords = ["code", "function", "implement", "debug", "fix", "program"]
        if any(kw in task.lower() for kw in code_keywords):
            capabilities.append(ModelCapability.CODE_GENERATION)

        # Long context
        if len(task) > 10000:
            capabilities.append(ModelCapability.LONG_CONTEXT)

        return capabilities

    def _select_provider(
        self,
        priority: RoutingPriority,
        required_capabilities: List[ModelCapability],
    ) -> Optional[ModelProvider]:
        """Select best provider based on priority and capabilities."""
        # Filter to capable and healthy providers
        candidates = [
            p for p in self.providers
            if p.is_healthy() and all(c in p.capabilities for c in required_capabilities)
        ]

        if not candidates:
            # Relax capability requirements for fallback
            candidates = [p for p in self.providers if p.is_healthy()]

        if not candidates:
            return None

        # Sort based on priority
        if priority == RoutingPriority.SPEED:
            candidates.sort(key=lambda p: p.latency_ms)
        elif priority == RoutingPriority.COST:
            candidates.sort(key=lambda p: p.cost_per_1k_tokens)
        elif priority == RoutingPriority.ACCURACY:
            # Higher priority providers are assumed more accurate
            candidates.sort(key=lambda p: (p.priority, -p.success_rate))
        else:  # BALANCED
            # Score based on all factors
            def score(p: ModelProvider) -> float:
                return (
                    (1 / max(p.latency_ms, 1)) * 0.3 +
                    (1 / max(p.cost_per_1k_tokens, 0.001)) * 0.001 * 0.3 +
                    (1 / max(p.priority, 1)) * 0.2 +
                    p.success_rate * 0.2
                )
            candidates.sort(key=score, reverse=True)

        return candidates[0]

    def _get_fallback(
        self,
        failed_provider: ModelProvider,
        required_capabilities: List[ModelCapability],
    ) -> Optional[ModelProvider]:
        """Get fallback provider after failure."""
        candidates = [
            p for p in self.providers
            if p.name != failed_provider.name and
               p.is_healthy() and
               all(c in p.capabilities for c in required_capabilities)
        ]

        if not candidates:
            # Try ollama as last resort
            ollama = self.get_provider("ollama")
            if ollama and ollama.enabled:
                return ollama
            return None

        return candidates[0]

    def _check_rate_limit(self, provider_name: str) -> bool:
        """Check if provider is within rate limits."""
        provider = self.get_provider(provider_name)
        if not provider:
            return False

        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        if provider_name in self._request_counts:
            self._request_counts[provider_name] = [
                t for t in self._request_counts[provider_name]
                if t > minute_ago
            ]

        requests = len(self._request_counts.get(provider_name, []))
        return requests < provider.rate_limit

    def _record_request(self, provider_name: str) -> None:
        """Record a request for rate limiting."""
        if provider_name not in self._request_counts:
            self._request_counts[provider_name] = []
        self._request_counts[provider_name].append(datetime.utcnow())

    async def _execute_request(
        self,
        provider: ModelProvider,
        task: str,
        image: Optional[bytes],
        max_tokens: int,
    ) -> str:
        """Execute request to provider."""
        # This is a placeholder - actual implementation would call the APIs
        # For now, return a mock response

        if provider.name == "groq":
            return await self._call_groq(provider, task, max_tokens)
        elif provider.name == "grok":
            return await self._call_grok(provider, task, max_tokens)
        elif provider.name == "claude":
            return await self._call_claude(provider, task, image, max_tokens)
        elif provider.name == "openrouter":
            return await self._call_openrouter(provider, task, max_tokens)
        elif provider.name == "ollama":
            return await self._call_ollama(provider, task, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider.name}")

    async def _call_groq(self, provider: ModelProvider, task: str, max_tokens: int) -> str:
        """Call Groq API."""
        import os
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=os.getenv(provider.api_key_env))
            response = await client.chat.completions.create(
                model=provider.model_id,
                messages=[{"role": "user", "content": task}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except ImportError:
            logger.warning("Groq library not installed")
            raise

    async def _call_grok(self, provider: ModelProvider, task: str, max_tokens: int) -> str:
        """Call xAI Grok API."""
        import os
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=os.getenv(provider.api_key_env),
                base_url="https://api.x.ai/v1",
            )
            response = await client.chat.completions.create(
                model=provider.model_id,
                messages=[{"role": "user", "content": task}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            raise

    async def _call_claude(
        self,
        provider: ModelProvider,
        task: str,
        image: Optional[bytes],
        max_tokens: int,
    ) -> str:
        """Call Anthropic Claude API."""
        import os
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=os.getenv(provider.api_key_env))

            messages = [{"role": "user", "content": task}]

            response = await client.messages.create(
                model=provider.model_id,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.content[0].text
        except ImportError:
            logger.warning("Anthropic library not installed")
            raise

    async def _call_openrouter(self, provider: ModelProvider, task: str, max_tokens: int) -> str:
        """Call OpenRouter API."""
        import os
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=os.getenv(provider.api_key_env),
                base_url="https://openrouter.ai/api/v1",
            )
            response = await client.chat.completions.create(
                model=provider.model_id,
                messages=[{"role": "user", "content": task}],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise

    async def _call_ollama(self, provider: ModelProvider, task: str, max_tokens: int) -> str:
        """Call local Ollama API."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": provider.model_id,
                        "prompt": task,
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    else:
                        raise RuntimeError(f"Ollama error: {resp.status}")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "providers": [p.to_dict() for p in self.providers],
            "cache_size": len(self._cache),
            "healthy_providers": sum(1 for p in self.providers if p.is_healthy()),
        }


# Singleton instance
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
