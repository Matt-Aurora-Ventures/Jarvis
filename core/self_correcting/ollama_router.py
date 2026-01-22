"""
Ollama AI Router - Local AI Model Integration

Routes AI requests to Ollama-hosted local models as an alternative to Claude API.
Supports:
- Automatic fallback to Claude if Ollama unavailable
- Model selection based on task type
- Cost tracking (Ollama = free, Claude = paid)
- Performance comparison between models

Recommended Ollama Models:
- qwen3-coder: Code generation and analysis
- GPT-OSS 20B: General purpose reasoning
- llama3.1: Fast general tasks
- deepseek-coder: Advanced code tasks
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import aiohttp


logger = logging.getLogger("jarvis.ollama_router")


class TaskType(Enum):
    """Types of AI tasks."""
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TEXT_GENERATION = "text_generation"
    DATA_EXTRACTION = "data_extraction"
    REASONING = "reasoning"
    CHAT = "chat"


class ModelTier(Enum):
    """Model capability tiers."""
    LOCAL_FAST = "local_fast"  # Ollama - fast, good enough
    LOCAL_ADVANCED = "local_advanced"  # Ollama - more capable
    CLOUD_STANDARD = "cloud_standard"  # Claude Sonnet
    CLOUD_ADVANCED = "cloud_advanced"  # Claude Opus


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    provider: str  # "ollama" or "anthropic"
    tier: ModelTier
    cost_per_1k_tokens: float
    good_for: List[TaskType]
    max_tokens: int = 4096
    endpoint: Optional[str] = None


# Model registry
MODELS: Dict[str, ModelConfig] = {
    # Ollama models (local, free)
    "qwen3-coder": ModelConfig(
        name="qwen3-coder",
        provider="ollama",
        tier=ModelTier.LOCAL_ADVANCED,
        cost_per_1k_tokens=0.0,
        good_for=[TaskType.CODE_GENERATION, TaskType.CODE_ANALYSIS],
        max_tokens=8192
    ),
    "gpt-oss-20b": ModelConfig(
        name="gpt-oss-20b",
        provider="ollama",
        tier=ModelTier.LOCAL_ADVANCED,
        cost_per_1k_tokens=0.0,
        good_for=[TaskType.REASONING, TaskType.TEXT_GENERATION, TaskType.CHAT],
        max_tokens=4096
    ),
    "llama3.1": ModelConfig(
        name="llama3.1",
        provider="ollama",
        tier=ModelTier.LOCAL_FAST,
        cost_per_1k_tokens=0.0,
        good_for=[TaskType.CHAT, TaskType.SENTIMENT_ANALYSIS],
        max_tokens=4096
    ),

    # Claude models (cloud, paid)
    "claude-sonnet-3.5": ModelConfig(
        name="claude-sonnet-3-5-20240620",
        provider="anthropic",
        tier=ModelTier.CLOUD_STANDARD,
        cost_per_1k_tokens=0.003,
        good_for=list(TaskType),  # Good for everything
        max_tokens=8192
    ),
    "claude-opus-3": ModelConfig(
        name="claude-3-opus-20240229",
        provider="anthropic",
        tier=ModelTier.CLOUD_ADVANCED,
        cost_per_1k_tokens=0.015,
        good_for=list(TaskType),  # Best for everything
        max_tokens=4096
    )
}


@dataclass
class ModelResponse:
    """Response from a model."""
    text: str
    model_used: str
    provider: str
    tokens_used: int
    cost: float
    latency_ms: float
    success: bool
    error: Optional[str] = None


class OllamaRouter:
    """
    Routes AI requests to appropriate models.

    Preferences:
    1. Try local Ollama model if suitable
    2. Fall back to Claude if Ollama unavailable or task too complex
    3. Track performance and costs
    """

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        prefer_local: bool = True,
        auto_fallback: bool = True
    ):
        self.ollama_base_url = ollama_base_url
        self.prefer_local = prefer_local
        self.auto_fallback = auto_fallback

        self.ollama_available = False
        self._check_ollama_task = None

        # Statistics
        self.stats = {
            "total_requests": 0,
            "ollama_requests": 0,
            "claude_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency_ms": 0.0,
            "errors": 0
        }

        logger.info(f"OllamaRouter initialized (prefer_local={prefer_local})")

    async def start(self):
        """Start router and check Ollama availability."""
        await self._check_ollama_availability()

        # Periodically check Ollama availability
        self._check_ollama_task = asyncio.create_task(
            self._periodic_ollama_check()
        )

    async def stop(self):
        """Stop router."""
        if self._check_ollama_task:
            self._check_ollama_task.cancel()

    async def _check_ollama_availability(self) -> bool:
        """Check if Ollama is running and available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ollama_base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=2.0)
                ) as resp:
                    if resp.status == 200:
                        self.ollama_available = True
                        logger.info("Ollama is available")
                        return True
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")

        self.ollama_available = False
        return False

    async def _periodic_ollama_check(self):
        """Periodically check if Ollama becomes available."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            await self._check_ollama_availability()

    def select_model(
        self,
        task_type: TaskType,
        prefer_tier: Optional[ModelTier] = None
    ) -> ModelConfig:
        """
        Select best model for a task.

        Logic:
        1. If prefer_local and Ollama available, use local model
        2. Otherwise use Claude
        3. Select specific model based on task type
        """
        # Filter models suitable for this task
        suitable_models = [
            model for model in MODELS.values()
            if task_type in model.good_for
        ]

        if not suitable_models:
            # Default to Claude Sonnet
            return MODELS["claude-sonnet-3.5"]

        # Prefer local if enabled and available
        if self.prefer_local and self.ollama_available:
            local_models = [
                m for m in suitable_models if m.provider == "ollama"
            ]
            if local_models:
                # Use advanced local model if available
                advanced = [m for m in local_models if m.tier == ModelTier.LOCAL_ADVANCED]
                return advanced[0] if advanced else local_models[0]

        # Use Claude
        if prefer_tier:
            tier_models = [m for m in suitable_models if m.tier == prefer_tier]
            if tier_models:
                return tier_models[0]

        # Default to Claude Sonnet (good balance)
        return MODELS["claude-sonnet-3.5"]

    async def query(
        self,
        prompt: str,
        task_type: TaskType = TaskType.TEXT_GENERATION,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        prefer_tier: Optional[ModelTier] = None
    ) -> ModelResponse:
        """
        Query AI model with automatic routing.

        Returns model response with metadata.
        """
        start_time = datetime.now()
        self.stats["total_requests"] += 1

        # Select model
        model_config = self.select_model(task_type, prefer_tier)

        logger.info(
            f"Routing {task_type.value} to {model_config.name} ({model_config.provider})"
        )

        # Route to appropriate provider
        try:
            if model_config.provider == "ollama":
                response = await self._query_ollama(
                    model_config, prompt, system_prompt, max_tokens, temperature
                )
            else:  # anthropic
                response = await self._query_anthropic(
                    model_config, prompt, system_prompt, max_tokens, temperature
                )

            # Update stats
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            response.latency_ms = latency_ms

            self.stats["total_tokens"] += response.tokens_used
            self.stats["total_cost"] += response.cost

            # Update avg latency (exponential moving average)
            alpha = 0.2
            self.stats["avg_latency_ms"] = \
                alpha * latency_ms + (1 - alpha) * self.stats["avg_latency_ms"]

            if model_config.provider == "ollama":
                self.stats["ollama_requests"] += 1
            else:
                self.stats["claude_requests"] += 1

            return response

        except Exception as e:
            logger.error(f"Query failed: {e}")
            self.stats["errors"] += 1

            # Try fallback to Claude if using Ollama
            if model_config.provider == "ollama" and self.auto_fallback:
                logger.info("Falling back to Claude...")
                fallback_model = MODELS["claude-sonnet-3.5"]
                return await self._query_anthropic(
                    fallback_model, prompt, system_prompt, max_tokens, temperature
                )

            # Return error response
            return ModelResponse(
                text="",
                model_used=model_config.name,
                provider=model_config.provider,
                tokens_used=0,
                cost=0.0,
                latency_ms=0.0,
                success=False,
                error=str(e)
            )

    async def _query_ollama(
        self,
        model: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> ModelResponse:
        """Query Ollama model."""
        async with aiohttp.ClientSession() as session:
            # Prepare request
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            request_data = {
                "model": model.name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            async with session.post(
                f"{self.ollama_base_url}/api/chat",
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=60.0)
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama returned status {resp.status}")

                result = await resp.json()
                response_text = result["message"]["content"]

                # Estimate tokens (rough approximation)
                tokens_used = len(prompt.split()) + len(response_text.split())

                return ModelResponse(
                    text=response_text,
                    model_used=model.name,
                    provider="ollama",
                    tokens_used=tokens_used,
                    cost=0.0,  # Free!
                    latency_ms=0.0,  # Will be set by caller
                    success=True
                )

    async def _query_anthropic(
        self,
        model: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> ModelResponse:
        """Query Claude API."""
        # Import here to avoid dependency if not used
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise Exception("anthropic library not installed")

        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise Exception("ANTHROPIC_API_KEY not set")

        client = AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model=model.name,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or "",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        cost = (tokens_used / 1000) * model.cost_per_1k_tokens

        return ModelResponse(
            text=response_text,
            model_used=model.name,
            provider="anthropic",
            tokens_used=tokens_used,
            cost=cost,
            latency_ms=0.0,  # Will be set by caller
            success=True
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            **self.stats,
            "ollama_available": self.ollama_available,
            "prefer_local": self.prefer_local,
            "cost_savings": self.stats["ollama_requests"] * 0.003  # Estimated savings vs Claude
        }


# Global router instance
_ollama_router: Optional[OllamaRouter] = None


def get_ollama_router() -> OllamaRouter:
    """Get the global Ollama router instance."""
    global _ollama_router
    if _ollama_router is None:
        _ollama_router = OllamaRouter()
    return _ollama_router
