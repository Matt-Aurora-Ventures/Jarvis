"""
JARVIS Model Manager - Multi-model provider system.

Provides:
- Per-session model selection
- Provider abstraction
- Cost tracking integration
- Automatic fallback
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .catalog import (
    MODEL_CATALOG,
    get_model_info,
    list_providers as catalog_list_providers,
    list_models as catalog_list_models,
    estimate_cost as catalog_estimate_cost,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerateResponse:
    """Response from model generation."""
    content: str
    model_id: str
    provider: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost: float


class ModelManager:
    """
    Manages multi-model provider system.

    Features:
    - Per-session model preferences
    - Provider abstraction
    - Cost tracking
    - Automatic fallback
    """

    DEFAULT_MODEL = "claude-sonnet-4-5"

    def __init__(
        self,
        default_model: Optional[str] = None,
    ):
        """
        Initialize ModelManager.

        Args:
            default_model: Default model ID to use
        """
        self._default_model = default_model or self.DEFAULT_MODEL
        self._session_models: Dict[str, str] = {}
        self._providers: Dict[str, Any] = {}

        # Validate default model exists
        if not get_model_info(self._default_model):
            logger.warning(f"Default model {self._default_model} not in catalog, using fallback")
            self._default_model = self.DEFAULT_MODEL

    @property
    def default_model(self) -> str:
        """Get current default model."""
        return self._default_model

    def set_default_model(self, model_id: str) -> None:
        """
        Set the default model.

        Args:
            model_id: Model identifier

        Raises:
            ValueError: If model not found in catalog
        """
        info = get_model_info(model_id)
        if not info:
            raise ValueError(f"Unknown model: {model_id}")

        self._default_model = model_id
        logger.info(f"Default model set to: {model_id}")

    def get_model_for_session(self, session_id: str) -> str:
        """
        Get model for a session.

        Returns session-specific model or default.

        Args:
            session_id: Session identifier

        Returns:
            Model ID
        """
        return self._session_models.get(session_id, self._default_model)

    def set_session_model(self, session_id: str, model_id: str) -> None:
        """
        Set model for a session.

        Args:
            session_id: Session identifier
            model_id: Model identifier

        Raises:
            ValueError: If model not found in catalog
        """
        info = get_model_info(model_id)
        if not info:
            raise ValueError(f"Unknown model: {model_id}")

        self._session_models[session_id] = model_id
        logger.info(f"Session {session_id} model set to: {model_id}")

    def clear_session_model(self, session_id: str) -> None:
        """
        Clear session model preference.

        Args:
            session_id: Session identifier
        """
        if session_id in self._session_models:
            del self._session_models[session_id]
            logger.info(f"Session {session_id} model preference cleared")

    def list_providers(self) -> List[str]:
        """
        List available providers.

        Returns:
            List of provider names
        """
        return catalog_list_providers()

    def list_models(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available models.

        Args:
            provider: Optional provider to filter by

        Returns:
            List of model info dicts
        """
        return catalog_list_models(provider)

    def estimate_cost(
        self,
        model_id: str,
        tokens_in: int,
        tokens_out: int,
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            model_id: Model identifier
            tokens_in: Input tokens
            tokens_out: Output tokens

        Returns:
            Estimated cost in USD
        """
        return catalog_estimate_cost(model_id, tokens_in, tokens_out)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a response using the specified or session model.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model_id: Optional specific model to use
            session_id: Optional session ID to get model from
            **kwargs: Additional generation parameters

        Returns:
            Response dict with content, tokens, cost
        """
        # Determine model to use
        if model_id:
            use_model = model_id
        elif session_id:
            use_model = self.get_model_for_session(session_id)
        else:
            use_model = self._default_model

        # Get model info
        info = get_model_info(use_model)
        if not info:
            raise ValueError(f"Unknown model: {use_model}")

        provider = info["provider"]

        # Call provider
        start_time = time.time()
        response = await self._generate_with_provider(
            provider=provider,
            model_id=use_model,
            messages=messages,
            **kwargs,
        )
        latency_ms = (time.time() - start_time) * 1000

        # Calculate cost
        tokens_in = response.get("tokens_in", 0)
        tokens_out = response.get("tokens_out", 0)
        cost = self.estimate_cost(use_model, tokens_in, tokens_out)

        # Track cost
        try:
            from core.llm.cost_tracker import get_cost_tracker
            tracker = get_cost_tracker()
            tracker.record_usage(
                provider=provider,
                model=use_model,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                latency_ms=latency_ms,
                success=True,
            )
        except Exception as e:
            logger.warning(f"Failed to track cost: {e}")

        return {
            "content": response.get("content", ""),
            "model_id": use_model,
            "provider": provider,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "cost": cost,
        }

    async def _generate_with_provider(
        self,
        provider: str,
        model_id: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate using a specific provider.

        Args:
            provider: Provider name
            model_id: Model ID
            messages: Messages list
            **kwargs: Additional params

        Returns:
            Response dict
        """
        # Get or create provider instance
        prov = self._get_provider(provider)

        if prov is None:
            raise ValueError(f"Provider not available: {provider}")

        return await prov.generate(
            model=model_id,
            messages=messages,
            **kwargs,
        )

    def _get_provider(self, provider: str) -> Optional[Any]:
        """Get provider instance, creating if needed."""
        if provider in self._providers:
            return self._providers[provider]

        # Lazy-load providers
        try:
            if provider == "anthropic":
                from .providers.anthropic import AnthropicProvider
                api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
                if api_key:
                    self._providers[provider] = AnthropicProvider(api_key=api_key)

            elif provider == "openai":
                from .providers.openai import OpenAIProvider
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self._providers[provider] = OpenAIProvider(api_key=api_key)

            elif provider == "xai":
                from .providers.xai import XAIProvider
                api_key = os.getenv("XAI_API_KEY")
                if api_key:
                    self._providers[provider] = XAIProvider(api_key=api_key)

            elif provider == "groq":
                from core.llm.providers import GroqProvider, LLMConfig, LLMProvider
                api_key = os.getenv("GROQ_API_KEY")
                if api_key:
                    config = LLMConfig(
                        provider=LLMProvider.GROQ,
                        model="llama-3.3-70b-versatile",
                        api_key=api_key,
                    )
                    self._providers[provider] = GroqProvider(config)

            elif provider == "ollama":
                from core.llm.providers import OllamaProvider, LLMConfig, LLMProvider
                config = LLMConfig(
                    provider=LLMProvider.OLLAMA,
                    model="llama3.2",
                )
                self._providers[provider] = OllamaProvider(config)

        except ImportError as e:
            logger.warning(f"Failed to import provider {provider}: {e}")
        except Exception as e:
            logger.error(f"Failed to create provider {provider}: {e}")

        return self._providers.get(provider)


# Singleton instance
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get singleton ModelManager instance."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager


def reset_model_manager() -> None:
    """Reset singleton (for testing)."""
    global _manager
    _manager = None
