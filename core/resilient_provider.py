"""
JARVIS Resilient Provider Chain - Self-Healing LLM Infrastructure

Implements circuit breaker pattern with automatic fallback and recovery:
- XAI/Grok (sentiment) → Groq (fast/free) → OpenRouter/Minimax → Ollama (local) → Dexter (knowledge)
- NEVER throws exceptions to users - always returns a response
- Self-healing with automatic provider recovery
- Graceful degradation when all providers fail

Usage:
    from core.resilient_provider import get_resilient_provider

    provider = get_resilient_provider()
    result = await provider.call(
        prompt="What is the sentiment of BTC?",
        required_capability="sentiment",
        timeout=60.0
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta

from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


class ProviderState(Enum):
    """Provider health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class ProviderHealth:
    """Tracks health of a single provider."""
    name: str
    state: ProviderState = ProviderState.HEALTHY
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_threshold: int = 3
    recovery_timeout: float = 60.0  # seconds
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_error: Optional[str] = None
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0

    def should_attempt(self) -> bool:
        """Check if provider should be attempted based on circuit breaker logic."""
        if self.state == ProviderState.HEALTHY:
            return True

        if self.state == ProviderState.DEGRADED:
            return True  # Try degraded providers, they might recover

        if self.state == ProviderState.FAILED:
            # Check if recovery timeout has elapsed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = ProviderState.RECOVERING
                    logger.info(f"Provider {self.name} entering recovery state after {elapsed:.1f}s")
                    return True
            return False

        if self.state == ProviderState.RECOVERING:
            return True  # Allow recovery attempts

        return False

    def record_success(self):
        """Record successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        self.last_error = None

        # Transition to healthy
        if self.state != ProviderState.HEALTHY:
            logger.info(f"Provider {self.name} recovered to HEALTHY")
        self.state = ProviderState.HEALTHY

    def record_failure(self, error: str):
        """Record failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()
        self.last_error = error

        # State transitions
        if self.consecutive_failures >= self.failure_threshold:
            if self.state != ProviderState.FAILED:
                logger.warning(f"Provider {self.name} FAILED after {self.consecutive_failures} consecutive failures")
            self.state = ProviderState.FAILED
        elif self.consecutive_failures >= 1:
            if self.state == ProviderState.HEALTHY:
                logger.info(f"Provider {self.name} DEGRADED")
            self.state = ProviderState.DEGRADED

    def to_dict(self) -> Dict[str, Any]:
        """Export health info."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.successful_calls / self.total_calls, 3) if self.total_calls > 0 else 0,
            "last_error": self.last_error,
            "last_failure_time": datetime.fromtimestamp(self.last_failure_time).isoformat() if self.last_failure_time else None,
            "last_success_time": datetime.fromtimestamp(self.last_success_time).isoformat() if self.last_success_time else None,
        }


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    name: str
    call_func: Callable
    priority: int  # Lower = higher priority (1 = first choice)
    capabilities: set = field(default_factory=set)
    enabled: bool = True


@dataclass
class CallResult:
    """Result from provider call."""
    success: bool
    response: Optional[str] = None
    provider_used: Optional[str] = None
    degraded: bool = False
    error: Optional[str] = None
    fallback_count: int = 0
    latency_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResilientProviderChain:
    """
    Self-healing provider chain with circuit breakers.

    CRITICAL: NEVER throws exceptions to users - always returns a response.
    """

    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self.health: Dict[str, ProviderHealth] = {}
        self._lock = asyncio.Lock()

        # Graceful degradation responses
        self.degradation_responses = {
            "sentiment": "I'm temporarily unable to analyze sentiment. Please try again in a moment.",
            "code": "I'm having trouble with code generation right now. Please try again shortly.",
            "knowledge": "I'm experiencing connectivity issues. Please try again in a moment.",
            "chat": "I'm temporarily unavailable. Please try again shortly.",
            "default": "I'm experiencing technical difficulties. Please try again in a moment."
        }

    def register_provider(
        self,
        name: str,
        call_func: Callable,
        priority: int,
        capabilities: Optional[set] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0
    ):
        """Register a provider in the fallback chain."""
        self.providers[name] = ProviderConfig(
            name=name,
            call_func=call_func,
            priority=priority,
            capabilities=capabilities or {"chat"},
            enabled=True
        )

        self.health[name] = ProviderHealth(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

        logger.info(f"Registered provider: {name} (priority={priority}, capabilities={capabilities})")

    def _get_ordered_providers(self, required_capability: Optional[str] = None) -> List[ProviderConfig]:
        """Get providers ordered by priority, filtered by capability."""
        candidates = []

        for provider in self.providers.values():
            if not provider.enabled:
                continue

            # Check capability match
            if required_capability and required_capability not in provider.capabilities:
                continue

            # Check health
            health = self.health.get(provider.name)
            if health and health.should_attempt():
                candidates.append(provider)

        # Sort by priority (lower = higher priority)
        return sorted(candidates, key=lambda p: p.priority)

    async def call(
        self,
        prompt: str,
        required_capability: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs
    ) -> CallResult:
        """
        Call provider chain with automatic fallback.

        CRITICAL: This method NEVER raises exceptions - always returns a CallResult.

        Args:
            prompt: The prompt to send
            required_capability: Required capability (sentiment, code, knowledge, chat)
            timeout: Timeout per provider attempt
            **kwargs: Additional arguments passed to provider

        Returns:
            CallResult with response (always succeeds with fallback message if needed)
        """
        start_time = time.time()
        providers = self._get_ordered_providers(required_capability)

        if not providers:
            logger.error(f"No providers available for capability: {required_capability}")
            return CallResult(
                success=False,
                response=self._graceful_degradation_response(required_capability),
                degraded=True,
                error="No providers available"
            )

        fallback_count = 0
        last_error = None

        for provider_config in providers:
            provider_name = provider_config.name
            health = self.health[provider_name]

            try:
                logger.debug(f"Attempting provider: {provider_name} (state={health.state.value})")

                # Call provider with timeout
                response = await asyncio.wait_for(
                    provider_config.call_func(prompt, **kwargs),
                    timeout=timeout
                )

                # Success!
                health.record_success()
                latency_ms = (time.time() - start_time) * 1000

                return CallResult(
                    success=True,
                    response=response,
                    provider_used=provider_name,
                    degraded=fallback_count > 0,
                    fallback_count=fallback_count,
                    latency_ms=latency_ms,
                    metadata={"health_state": health.state.value}
                )

            except asyncio.TimeoutError:
                error_msg = f"Timeout after {timeout}s"
                logger.warning(f"Provider {provider_name} timeout: {error_msg}")
                health.record_failure(error_msg)
                last_error = error_msg
                fallback_count += 1

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Provider {provider_name} failed: {error_msg}")
                health.record_failure(error_msg)
                last_error = error_msg
                fallback_count += 1

        # All providers failed - return graceful degradation response
        logger.error(f"All {len(providers)} providers failed. Last error: {last_error}")

        return CallResult(
            success=False,
            response=self._graceful_degradation_response(required_capability),
            degraded=True,
            error=last_error,
            fallback_count=fallback_count,
            latency_ms=(time.time() - start_time) * 1000,
            metadata={"all_providers_failed": True}
        )

    def _graceful_degradation_response(self, capability: Optional[str] = None) -> str:
        """Get graceful degradation response for capability."""
        if capability and capability in self.degradation_responses:
            return self.degradation_responses[capability]
        return self.degradation_responses["default"]

    def get_health_report(self) -> Dict[str, Any]:
        """Get health report for all providers."""
        return {
            "providers": {name: health.to_dict() for name, health in self.health.items()},
            "timestamp": datetime.now().isoformat(),
            "total_providers": len(self.providers),
            "healthy_providers": sum(1 for h in self.health.values() if h.state == ProviderState.HEALTHY),
            "degraded_providers": sum(1 for h in self.health.values() if h.state == ProviderState.DEGRADED),
            "failed_providers": sum(1 for h in self.health.values() if h.state == ProviderState.FAILED),
        }

    def get_status_message(self) -> str:
        """Get human-readable status message."""
        report = self.get_health_report()

        lines = ["🏥 **Provider Health Status**\n"]

        for name, health in sorted(self.health.items(), key=lambda x: self.providers[x[0]].priority):
            state_emoji = {
                "healthy": "✅",
                "degraded": "⚠️",
                "failed": "❌",
                "recovering": "🔄"
            }.get(health["state"], "❓")

            success_rate = health.get("success_rate", 0)
            lines.append(f"{state_emoji} **{name}**: {health['state'].upper()} ({success_rate:.1%} success)")

        lines.append(f"\n📊 **Summary**: {report['healthy_providers']} healthy, {report['degraded_providers']} degraded, {report['failed_providers']} failed")

        return "\n".join(lines)

    def disable_provider(self, name: str):
        """Manually disable a provider."""
        if name in self.providers:
            self.providers[name].enabled = False
            logger.info(f"Provider {name} manually disabled")

    def enable_provider(self, name: str):
        """Manually enable a provider."""
        if name in self.providers:
            self.providers[name].enabled = True
            if name in self.health:
                self.health[name].state = ProviderState.HEALTHY
                self.health[name].consecutive_failures = 0
            logger.info(f"Provider {name} manually enabled")


# Global singleton instance
_resilient_provider: Optional[ResilientProviderChain] = None


def get_resilient_provider() -> ResilientProviderChain:
    """Get the global resilient provider instance."""
    global _resilient_provider
    if _resilient_provider is None:
        _resilient_provider = ResilientProviderChain()
    return _resilient_provider


async def initialize_providers():
    """
    Initialize all providers in the fallback chain.

    COST OPTIMIZATION (per user request):
    - Priority 1: Dexter (FREE via Claude CLI) - default for Telegram
    - Priority 2: Ollama (FREE, local) - works offline
    - Priority 3: XAI/Grok (PAID) - only for sentiment analysis
    - Priority 4: Groq (FREE tier) - backup for code/chat
    - Priority 5: OpenRouter (PAID) - last resort
    """
    provider = get_resilient_provider()

    # Priority 1: Dexter (FREE - default for Telegram to save costs)
    try:
        async def call_dexter(prompt: str, **kwargs) -> str:
            """Call Dexter via Claude CLI - completely free."""
            import subprocess

            try:
                # Use Claude CLI to query Dexter's knowledge base
                result = subprocess.run(
                    ["claude", "ask", prompt],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    raise Exception(f"Claude CLI error: {result.stderr}")

            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Fallback to Dexter agent directly
                from core.dexter.agent import DexterAgent
                agent = DexterAgent()
                decision = await agent.analyze_token("query", metadata={"prompt": prompt})
                return decision.rationale or "No response available"

        provider.register_provider(
            name="dexter",
            call_func=call_dexter,
            priority=1,  # HIGHEST PRIORITY - FREE
            capabilities={"chat", "knowledge", "search", "research", "code"},
            failure_threshold=5,
            recovery_timeout=30.0
        )
        logger.info("✅ Dexter provider registered (Priority 1 - FREE)")

    except Exception as e:
        logger.error(f"Failed to register Dexter: {e}")

    # Priority 2: Ollama (FREE, local)
    try:
        async def call_ollama(prompt: str, **kwargs) -> str:
            from core.ai_runtime.ollama_client import OllamaClient
            client = OllamaClient()
            return await client.generate(prompt, model="llama3.1:8b", **kwargs)

        provider.register_provider(
            name="ollama",
            call_func=call_ollama,
            priority=2,  # FREE local fallback
            capabilities={"chat", "code", "knowledge"},
            failure_threshold=5,
            recovery_timeout=30.0
        )
        logger.info("✅ Ollama provider registered (Priority 2 - FREE local)")

    except Exception as e:
        logger.error(f"Failed to register Ollama: {e}")

    # Priority 3: XAI/Grok (PAID - only for sentiment analysis)
    try:
        from core.models.providers.xai import XAIProvider
        from core import secrets

        xai_key = secrets.get_secret("xai", {}).get("api_key")
        if xai_key:
            async def call_xai(prompt: str, **kwargs) -> str:
                xai = XAIProvider(api_key=xai_key)
                return xai.generate(prompt, **kwargs)

            provider.register_provider(
                name="xai",
                call_func=call_xai,
                priority=3,  # PAID - use only for sentiment
                capabilities={"sentiment"},  # LIMITED to sentiment only
                failure_threshold=3,
                recovery_timeout=60.0
            )
            logger.info("✅ XAI/Grok provider registered (Priority 3 - PAID, sentiment only)")
        else:
            logger.warning("⚠️ XAI API key not found")

    except Exception as e:
        logger.error(f"Failed to register XAI: {e}")

    # Priority 4: Groq (FREE tier - backup for code/chat)
    try:
        from core.llm.providers import BaseLLMProvider, LLMConfig, LLMProvider as LLMProviderEnum
        import os

        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            async def call_groq(prompt: str, **kwargs) -> str:
                from core.llm.providers import GroqProvider
                config = LLMConfig(
                    provider=LLMProviderEnum.GROQ,
                    model="llama-3.1-70b-versatile",
                    api_key=groq_key,
                    max_tokens=kwargs.get("max_tokens", 2048)
                )
                groq_provider = GroqProvider(config)
                result = await groq_provider.generate(prompt)
                await groq_provider.close()
                return result.content

            provider.register_provider(
                name="groq",
                call_func=call_groq,
                priority=4,  # FREE tier, backup
                capabilities={"chat", "code", "knowledge"},
                failure_threshold=3,
                recovery_timeout=60.0
            )
            logger.info("✅ Groq provider registered (Priority 4 - FREE tier)")
        else:
            logger.warning("⚠️ GROQ_API_KEY not found")

    except Exception as e:
        logger.error(f"Failed to register Groq: {e}")

    # Priority 5: OpenRouter (PAID - last resort)
    try:
        import os
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            async def call_openrouter(prompt: str, **kwargs) -> str:
                from core.api_proxy.openrouter_proxy import OpenRouterProxy
                proxy = OpenRouterProxy(api_key=openrouter_key)
                return await proxy.generate(prompt, **kwargs)

            provider.register_provider(
                name="openrouter",
                call_func=call_openrouter,
                priority=5,  # PAID - last resort
                capabilities={"chat", "code", "knowledge"},
                failure_threshold=3,
                recovery_timeout=120.0
            )
            logger.info("✅ OpenRouter provider registered (Priority 5 - PAID)")

    except Exception as e:
        logger.error(f"Failed to register OpenRouter: {e}")

    logger.info(f"🚀 Resilient provider chain initialized with {len(provider.providers)} providers")
    logger.info("💰 Cost optimization: Dexter (FREE) is priority 1 for Telegram")
