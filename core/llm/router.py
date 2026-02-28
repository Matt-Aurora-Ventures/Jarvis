"""
JARVIS LLM Router - Task-Based Model Selection

Routes different tasks to the most appropriate LLM:
- Fast tasks -> Groq (low latency)
- Complex reasoning -> Larger models
- Private tasks -> Ollama (local)
- Token analysis -> xAI/Grok

Dependencies: Requires providers.py
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .providers import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    UnifiedLLM,
    get_llm,
)

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks for routing."""
    # Fast, simple tasks
    QUICK_RESPONSE = "quick_response"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"

    # Complex reasoning
    ANALYSIS = "analysis"
    CODE_GENERATION = "code_generation"
    PLANNING = "planning"

    # Domain-specific
    TRADING = "trading"
    SENTIMENT = "sentiment"
    RESEARCH = "research"

    # Privacy-sensitive
    PRIVATE = "private"
    LOCAL_ONLY = "local_only"

    # Conversation
    CHAT = "chat"
    ASSISTANT = "assistant"


@dataclass
class RoutingRule:
    """Rule for routing a task type."""
    task_type: TaskType
    preferred_providers: List[LLMProvider]
    temperature: float = 0.7
    max_tokens: int = 1024
    system_prompt: Optional[str] = None


# Default routing rules
DEFAULT_RULES: Dict[TaskType, RoutingRule] = {
    # Fast tasks - prefer Groq for speed
    TaskType.QUICK_RESPONSE: RoutingRule(
        task_type=TaskType.QUICK_RESPONSE,
        preferred_providers=[LLMProvider.GROQ, LLMProvider.OLLAMA],
        temperature=0.5,
        max_tokens=256,
    ),
    TaskType.CLASSIFICATION: RoutingRule(
        task_type=TaskType.CLASSIFICATION,
        preferred_providers=[LLMProvider.GROQ, LLMProvider.OLLAMA],
        temperature=0.1,
        max_tokens=128,
    ),
    TaskType.SUMMARIZATION: RoutingRule(
        task_type=TaskType.SUMMARIZATION,
        preferred_providers=[LLMProvider.GROQ, LLMProvider.XAI],
        temperature=0.3,
        max_tokens=512,
    ),

    # Complex reasoning - prefer larger models
    TaskType.ANALYSIS: RoutingRule(
        task_type=TaskType.ANALYSIS,
        preferred_providers=[LLMProvider.XAI, LLMProvider.GROQ],
        temperature=0.5,
        max_tokens=2048,
    ),
    TaskType.CODE_GENERATION: RoutingRule(
        task_type=TaskType.CODE_GENERATION,
        preferred_providers=[LLMProvider.XAI, LLMProvider.OPENROUTER],
        temperature=0.2,
        max_tokens=4096,
    ),
    TaskType.PLANNING: RoutingRule(
        task_type=TaskType.PLANNING,
        preferred_providers=[LLMProvider.XAI, LLMProvider.GROQ],
        temperature=0.4,
        max_tokens=2048,
    ),

    # Domain-specific - xAI for crypto knowledge
    TaskType.TRADING: RoutingRule(
        task_type=TaskType.TRADING,
        preferred_providers=[LLMProvider.XAI, LLMProvider.GROQ],
        temperature=0.3,
        max_tokens=1024,
        system_prompt="You are a crypto trading analyst. Be precise and risk-aware.",
    ),
    TaskType.SENTIMENT: RoutingRule(
        task_type=TaskType.SENTIMENT,
        preferred_providers=[LLMProvider.XAI, LLMProvider.GROQ],
        temperature=0.2,
        max_tokens=512,
        system_prompt="Analyze market sentiment objectively. Focus on facts.",
    ),
    TaskType.RESEARCH: RoutingRule(
        task_type=TaskType.RESEARCH,
        preferred_providers=[LLMProvider.XAI, LLMProvider.OPENROUTER],
        temperature=0.5,
        max_tokens=4096,
    ),

    # Privacy-sensitive - local only
    TaskType.PRIVATE: RoutingRule(
        task_type=TaskType.PRIVATE,
        preferred_providers=[LLMProvider.OLLAMA],
        temperature=0.7,
        max_tokens=1024,
    ),
    TaskType.LOCAL_ONLY: RoutingRule(
        task_type=TaskType.LOCAL_ONLY,
        preferred_providers=[LLMProvider.OLLAMA],
        temperature=0.7,
        max_tokens=1024,
    ),

    # Conversation - balanced
    TaskType.CHAT: RoutingRule(
        task_type=TaskType.CHAT,
        preferred_providers=[LLMProvider.GROQ, LLMProvider.XAI, LLMProvider.OLLAMA],
        temperature=0.8,
        max_tokens=1024,
    ),
    TaskType.ASSISTANT: RoutingRule(
        task_type=TaskType.ASSISTANT,
        preferred_providers=[LLMProvider.XAI, LLMProvider.GROQ],
        temperature=0.7,
        max_tokens=2048,
        system_prompt="You are JARVIS, an AI assistant. Be helpful, concise, and proactive.",
    ),
}


class LLMRouter:
    """
    Intelligent LLM routing based on task type.

    Features:
    - Task-based provider selection
    - Automatic fallback
    - Custom routing rules
    - Performance tracking
    """

    def __init__(self, llm: Optional[UnifiedLLM] = None):
        self._llm = llm
        self.rules = DEFAULT_RULES.copy()
        # Backward compatibility alias expected by integration tests.
        self.routing_rules = self.rules
        self._stats: Dict[str, Dict[str, int]] = {}

    async def _get_llm(self) -> UnifiedLLM:
        """Get or create UnifiedLLM instance."""
        if self._llm is None:
            self._llm = await get_llm()
        return self._llm

    def add_rule(self, rule: RoutingRule):
        """Add or update a routing rule."""
        self.rules[rule.task_type] = rule

    def get_rule(self, task_type: TaskType) -> RoutingRule:
        """Get routing rule for task type."""
        return self.rules.get(task_type, self.rules[TaskType.CHAT])

    async def route(
        self,
        prompt: Union[str, List[Message]],
        task_type: TaskType = TaskType.CHAT,
        **kwargs
    ) -> LLMResponse:
        """
        Route a prompt to the appropriate provider.

        Args:
            prompt: User prompt or message list
            task_type: Type of task for routing
            **kwargs: Additional params to override

        Returns:
            LLMResponse from selected provider
        """
        rule = self.get_rule(task_type)
        llm = await self._get_llm()

        # Build message list
        if isinstance(prompt, str):
            messages = []
            if rule.system_prompt:
                messages.append(Message("system", rule.system_prompt))
            messages.append(Message("user", prompt))
        else:
            messages = prompt
            # Prepend system prompt if not already present
            if rule.system_prompt and (not messages or messages[0].role != "system"):
                messages = [Message("system", rule.system_prompt)] + messages

        # Apply rule settings, allow kwargs to override
        params = {
            "temperature": kwargs.get("temperature", rule.temperature),
            "max_tokens": kwargs.get("max_tokens", rule.max_tokens),
        }

        # Try providers in order of preference
        last_error = None
        for provider in rule.preferred_providers:
            if provider not in llm.providers:
                continue
            try:
                response = await llm.generate(messages, provider=provider, **params)
                self._record_success(task_type, provider)
                return response
            except Exception as e:
                logger.warning(f"Router: {provider.value} failed for {task_type.value}: {e}")
                last_error = e
                continue

        # Fall back to any available provider
        try:
            response = await llm.generate(messages, **params)
            return response
        except Exception as e:
            raise Exception(f"All providers failed for {task_type.value}. Last error: {last_error}")

    async def quick(self, prompt: str) -> str:
        """Quick response for simple queries."""
        response = await self.route(prompt, TaskType.QUICK_RESPONSE)
        return response.content

    async def analyze(self, prompt: str) -> str:
        """Deep analysis."""
        response = await self.route(prompt, TaskType.ANALYSIS)
        return response.content

    async def trade(self, prompt: str) -> str:
        """Trading-focused analysis."""
        response = await self.route(prompt, TaskType.TRADING)
        return response.content

    async def code(self, prompt: str) -> str:
        """Code generation."""
        response = await self.route(prompt, TaskType.CODE_GENERATION)
        return response.content

    async def chat(self, prompt: str) -> str:
        """General chat."""
        response = await self.route(prompt, TaskType.CHAT)
        return response.content

    async def private(self, prompt: str) -> str:
        """Private/local-only processing."""
        response = await self.route(prompt, TaskType.PRIVATE)
        return response.content

    def _record_success(self, task_type: TaskType, provider: LLMProvider):
        """Record successful routing for stats."""
        key = task_type.value
        if key not in self._stats:
            self._stats[key] = {}
        prov_key = provider.value
        self._stats[key][prov_key] = self._stats[key].get(prov_key, 0) + 1

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get routing statistics."""
        return self._stats

    async def close(self):
        """Close underlying LLM."""
        if self._llm:
            await self._llm.close()


# Singleton router
_router: Optional[LLMRouter] = None


async def get_router() -> LLMRouter:
    """Get singleton router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def route_task(
    prompt: str,
    task_type: TaskType = TaskType.CHAT,
    **kwargs
) -> str:
    """
    Quick helper to route a task.

    Args:
        prompt: User prompt
        task_type: Type of task
        **kwargs: Additional params

    Returns:
        Response content string
    """
    router = await get_router()
    response = await router.route(prompt, task_type, **kwargs)
    return response.content


# Task-specific shortcuts
async def quick_analyze(text: str) -> str:
    """Quick analysis shortcut."""
    return await route_task(text, TaskType.ANALYSIS)


async def quick_trade_analysis(query: str) -> str:
    """Trading analysis shortcut."""
    return await route_task(query, TaskType.TRADING)


async def quick_sentiment(text: str) -> str:
    """Sentiment analysis shortcut."""
    return await route_task(
        f"Analyze the sentiment of this text and provide a score from -1 (very negative) to 1 (very positive):\n\n{text}",
        TaskType.SENTIMENT
    )


async def quick_summarize(text: str, max_length: int = 200) -> str:
    """Summarization shortcut."""
    return await route_task(
        f"Summarize this in {max_length} words or less:\n\n{text}",
        TaskType.SUMMARIZATION
    )
