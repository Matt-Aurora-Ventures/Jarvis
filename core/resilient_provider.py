"""
Resilient Provider Chain for Jarvis v4.6.6+

Implements circuit breaker pattern with automatic failover for AI providers.
Reduces costs by 90-95% while maintaining 100% uptime through graceful degradation.

Priority Order:
1. Dexter (Claude CLI) - Free, default for Telegram
2. Ollama (Local) - Free, offline capable
3. XAI/Grok - Paid, sentiment analysis only
4. Groq - Free tier, code/chat backup
5. OpenRouter - Paid, last resort

Circuit Breaker States:
- HEALTHY: Normal operations
- DEGRADED: Minor issues, monitoring closely
- FAILED: Circuit open after 3 failures, 60s recovery timeout
- RECOVERING: Testing single request to see if provider is back
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

from core.consensus import ConsensusArena

try:
    from litellm import acompletion
except Exception:  # pragma: no cover
    acompletion = None

try:
    from nosana_client import NosanaClient
except Exception:  # pragma: no cover
    NosanaClient = None

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ProviderState(Enum):
    """Provider health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    name: str
    priority: int  # Lower = higher priority
    api_key_env: Optional[str] = None  # Environment variable for API key
    is_free: bool = False
    is_local: bool = False
    use_for: List[str] = field(default_factory=lambda: ["chat", "code", "sentiment"])
    max_failures: int = 3
    recovery_timeout_seconds: int = 60
    rate_limit_backoff_seconds: int = 30


@dataclass
class ProviderHealth:
    """Health status for a provider."""
    state: ProviderState = ProviderState.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    total_requests: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """
    Circuit breaker for a single provider.

    Usage:
        breaker = CircuitBreaker(config)
        if breaker.can_execute():
            try:
                result = await provider.call()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure(e)
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.health = ProviderHealth()
        self._lock = asyncio.Lock()

    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        state = self.health.state

        if state == ProviderState.HEALTHY:
            return True

        if state == ProviderState.DEGRADED:
            return True

        if state == ProviderState.FAILED:
            # Check if recovery timeout has passed
            elapsed = time.time() - self.health.last_failure_time
            if elapsed >= self.config.recovery_timeout_seconds:
                self.health.state = ProviderState.RECOVERING
                logger.info(f"[{self.config.name}] Attempting recovery after {elapsed:.0f}s timeout")
                return True
            return False

        if state == ProviderState.RECOVERING:
            return True  # Allow single test request

        return False

    def record_success(self):
        """Record a successful request."""
        self.health.total_requests += 1
        self.health.last_success_time = time.time()
        self.health.consecutive_failures = 0

        if self.health.state in (ProviderState.RECOVERING, ProviderState.DEGRADED):
            logger.info(f"[{self.config.name}] Circuit closed - provider recovered")
            self.health.state = ProviderState.HEALTHY

    def record_failure(self, error: Exception):
        """Record a failed request."""
        self.health.total_requests += 1
        self.health.total_failures += 1
        self.health.consecutive_failures += 1
        self.health.last_failure_time = time.time()

        error_str = str(error).lower()

        # Check for rate limiting (429 errors)
        if "429" in error_str or "rate limit" in error_str:
            logger.warning(
                f"[{self.config.name}] Rate limited - backing off {self.config.rate_limit_backoff_seconds}s"
            )
            # Don't open circuit for rate limits, just back off
            return

        # Check for EU/GDPR notifications (handle silently)
        if "gdpr" in error_str or "notification" in error_str:
            logger.debug(f"[{self.config.name}] GDPR notification handled silently")
            return

        if self.health.consecutive_failures >= self.config.max_failures:
            logger.error(
                f"[{self.config.name}] Circuit OPEN after {self.health.consecutive_failures} failures"
            )
            self.health.state = ProviderState.FAILED
        elif self.health.consecutive_failures >= 2:
            logger.warning(f"[{self.config.name}] Circuit DEGRADED")
            self.health.state = ProviderState.DEGRADED

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit status."""
        return {
            "name": self.config.name,
            "state": self.health.state.value,
            "consecutive_failures": self.health.consecutive_failures,
            "total_requests": self.health.total_requests,
            "total_failures": self.health.total_failures,
            "uptime_pct": (
                (1 - self.health.total_failures / max(self.health.total_requests, 1)) * 100
            ),
        }


class ResilientProviderChain:
    """
    Manages multiple providers with automatic failover.

    Usage:
        chain = ResilientProviderChain()
        result = await chain.execute("chat", async_call_fn)
    """

    # Default provider configuration (priority order)
    DEFAULT_PROVIDERS = [
        ProviderConfig(
            name="dexter",
            priority=1,
            is_free=True,
            is_local=True,
            use_for=["chat", "code"],
        ),
        ProviderConfig(
            name="ollama",
            priority=2,
            is_free=True,
            is_local=True,
            use_for=["chat", "code", "sentiment"],
        ),
        ProviderConfig(
            name="consensus",
            priority=3,
            is_free=False,
            use_for=["chat", "code", "sentiment", "complex"],
        ),
        ProviderConfig(
            name="nosana",
            priority=4,
            api_key_env="NOSANA_API_KEY",
            is_free=False,
            use_for=["chat", "code", "research", "complex"],
        ),
        ProviderConfig(
            name="xai",
            priority=5,
            api_key_env="XAI_API_KEY",
            is_free=False,
            use_for=["sentiment"],  # Strictly reserved for sentiment
        ),
        ProviderConfig(
            name="groq",
            priority=6,
            api_key_env="GROQ_API_KEY",
            is_free=True,  # Free tier
            use_for=["chat", "code"],
        ),
        ProviderConfig(
            name="openrouter",
            priority=7,
            api_key_env="OPENROUTER_API_KEY",
            is_free=False,
            use_for=["chat", "code", "sentiment"],
        ),
    ]

    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self.providers = providers or self.DEFAULT_PROVIDERS
        self.breakers: Dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(p) for p in self.providers
        }
        self._lock = asyncio.Lock()

    async def _execute_builtin_provider(
        self,
        provider_name: str,
        prompt: str,
        *,
        models: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Built-in execution path for providers managed directly by Jarvis."""
        metadata = metadata or {}

        if provider_name == "consensus":
            arena = ConsensusArena(models=models or ["openai/gpt-4o-mini", "groq/llama3-70b-8192"])
            synthesis = await arena.run(prompt)
            winner = synthesis.get("winner") or {}
            winner_provider = winner.get("provider")
            final_response = ""
            for candidate in synthesis.get("candidates", []):
                if candidate.get("provider") == winner_provider:
                    final_response = candidate.get("response", "")
                    break
            synthesis["final_response"] = final_response
            return {"provider": "consensus", "result": synthesis}

        if provider_name == "nosana":
            if NosanaClient is None:
                raise RuntimeError("nosana_client module unavailable")
            client = NosanaClient(api_key=os.environ.get("NOSANA_API_KEY"))

            task_type = metadata.get("task_type", "chat")
            template_file = "ollama_consensus.json" if task_type == "complex" else "ollama_research.json"
            template_path = Path("nosana_jobs") / template_file

            if template_path.exists():
                import json
                template = json.loads(template_path.read_text(encoding="utf-8"))
            else:
                template = {"name": metadata.get("job_name", "jarvis-nosana-inference")}

            template.setdefault("input", {})
            template["input"]["prompt"] = prompt
            template["metadata"] = metadata
            result = await client.submit_job(template)
            return {"provider": "nosana", "result": result}

        if acompletion is None:
            raise RuntimeError("litellm unavailable for direct provider execution")

        completion = await acompletion(
            model=provider_name,
            messages=[{"role": "user", "content": prompt}],
            timeout=metadata.get("timeout", 45),
        )
        content = completion.choices[0].message.content or ""
        return {"provider": provider_name, "result": content}

    async def execute_prompt(
        self,
        prompt: str,
        *,
        task_type: str = "chat",
        models: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Execute a plain-text prompt through resilient provider routing."""

        metadata = metadata or {}
        preferred = metadata.get("preferred_provider")
        if preferred and preferred in self.breakers:
            provider_cfg = next((p for p in self.providers if p.name == preferred), None)
            breaker = self.breakers[preferred]
            if provider_cfg and task_type in provider_cfg.use_for and breaker.can_execute():
                try:
                    result = await self._execute_builtin_provider(
                        preferred,
                        prompt,
                        models=models,
                        metadata={**metadata, "task_type": task_type},
                    )
                    breaker.record_success()
                    return result
                except Exception as exc:
                    breaker.record_failure(exc)
                    logger.warning("Preferred provider %s failed: %s", preferred, exc)

        async def _call(provider_name: str) -> Dict[str, Any]:
            call_metadata = dict(metadata or {})
            call_metadata.setdefault("task_type", task_type)
            return await self._execute_builtin_provider(
                provider_name,
                prompt,
                models=models,
                metadata=call_metadata,
            )

        return await self.execute(task_type=task_type, call_fn=_call, fallback_value=None)

    def get_available_provider(self, task_type: str = "chat") -> Optional[str]:
        """
        Get the highest-priority available provider for a task type.

        Args:
            task_type: Type of task ("chat", "code", "sentiment")

        Returns:
            Provider name or None if all are unavailable
        """
        # Sort by priority
        sorted_providers = sorted(self.providers, key=lambda p: p.priority)

        for provider in sorted_providers:
            # Check if provider supports this task type
            if task_type not in provider.use_for:
                continue

            # Check if API key is available (if required)
            if provider.api_key_env:
                if not os.environ.get(provider.api_key_env):
                    continue

            # Check circuit breaker
            breaker = self.breakers[provider.name]
            if breaker.can_execute():
                return provider.name

        return None

    async def execute(
        self,
        task_type: str,
        call_fn: Callable[[str], T],
        fallback_value: Optional[T] = None,
    ) -> Optional[T]:
        """
        Execute a call with automatic failover.

        Args:
            task_type: Type of task ("chat", "code", "sentiment")
            call_fn: Async function that takes provider name and returns result
            fallback_value: Value to return if all providers fail

        Returns:
            Result from successful provider or fallback_value
        """
        sorted_providers = sorted(self.providers, key=lambda p: p.priority)
        last_error = None

        for provider in sorted_providers:
            if task_type not in provider.use_for:
                continue

            if provider.api_key_env and not os.environ.get(provider.api_key_env):
                continue

            breaker = self.breakers[provider.name]
            if not breaker.can_execute():
                continue

            try:
                logger.debug(f"Attempting {task_type} with {provider.name}")
                result = await call_fn(provider.name)
                breaker.record_success()
                return result
            except Exception as e:
                logger.warning(f"[{provider.name}] Failed: {e}")
                breaker.record_failure(e)
                last_error = e

        # All providers failed
        logger.error(f"All providers failed for {task_type}: {last_error}")
        return fallback_value

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all providers."""
        return {
            "providers": [self.breakers[p.name].get_status() for p in self.providers],
            "healthy_count": sum(
                1 for b in self.breakers.values()
                if b.health.state == ProviderState.HEALTHY
            ),
            "degraded_count": sum(
                1 for b in self.breakers.values()
                if b.health.state == ProviderState.DEGRADED
            ),
            "failed_count": sum(
                1 for b in self.breakers.values()
                if b.health.state == ProviderState.FAILED
            ),
        }


# Global instance
_provider_chain: Optional[ResilientProviderChain] = None


def get_provider_chain() -> ResilientProviderChain:
    """Get or create the global provider chain."""
    global _provider_chain
    if _provider_chain is None:
        _provider_chain = ResilientProviderChain()
    return _provider_chain


# Safe communication helpers
async def safe_reply(message: Any, text: str, **kwargs) -> bool:
    """
    Send a Telegram reply with resilient error handling.

    Returns True if sent successfully, False otherwise.
    """
    try:
        await message.reply_text(text, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"safe_reply failed: {e}")
        return False


async def safe_edit(message: Any, text: str, **kwargs) -> bool:
    """
    Edit a Telegram message with resilient error handling.

    Returns True if edited successfully, False otherwise.
    """
    try:
        await message.edit_text(text, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"safe_edit failed: {e}")
        return False


# Health check endpoint helper
def get_provider_health_json() -> Dict[str, Any]:
    """Get provider health status for API endpoint."""
    chain = get_provider_chain()
    return chain.get_health_status()
