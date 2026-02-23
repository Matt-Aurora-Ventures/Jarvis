"""
Cost Calculator for API calls.

Calculates costs based on model-specific pricing (Jan 2026 rates).
"""

from typing import Dict, List, Optional, Any


# Model pricing: per 1K tokens (Jan 2026)
# Format: provider -> model -> {input_per_1k, output_per_1k}
MODEL_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "grok": {
        # Grok 4-1 fast: $0.20/$0.50 per 1M tokens = $0.00020/$0.00050 per 1K
        "grok-4-1-fast-non-reasoning": {
            "input_per_1k": 0.00020,
            "output_per_1k": 0.00050,
        },
        "grok-4-1-fast-reasoning": {
            "input_per_1k": 0.00020,
            "output_per_1k": 0.00050,
        },
        # Grok 4: higher capability, same fast-track pricing
        "grok-4": {
            "input_per_1k": 0.00300,
            "output_per_1k": 0.01500,
        },
        # Legacy models
        "grok-3": {
            "input_per_1k": 0.001,
            "output_per_1k": 0.001,
        },
        "grok-3-mini": {
            "input_per_1k": 0.0005,
            "output_per_1k": 0.0005,
        },
        "grok-2": {
            "input_per_1k": 0.001,
            "output_per_1k": 0.001,
        },
    },
    "openai": {
        # GPT-4o: $0.015/1K input, $0.06/1K output
        "gpt-4o": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.06,
        },
        "gpt-4o-mini": {
            "input_per_1k": 0.00015,  # Much cheaper mini
            "output_per_1k": 0.0006,
        },
        "gpt-4-turbo": {
            "input_per_1k": 0.01,
            "output_per_1k": 0.03,
        },
        "gpt-3.5-turbo": {
            "input_per_1k": 0.0005,
            "output_per_1k": 0.0015,
        },
    },
    "anthropic": {
        # Claude 4.6 models (Feb 2026 pricing)
        "claude-opus-4-6": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.075,
        },
        "claude-sonnet-4-6": {
            "input_per_1k": 0.003,
            "output_per_1k": 0.015,
        },
        "claude-haiku-4-5-20251001": {
            "input_per_1k": 0.00025,
            "output_per_1k": 0.00125,
        },
        # Legacy model names (still valid on API)
        "claude-opus-4": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.075,
        },
        "claude-opus-4-5-20251101": {
            "input_per_1k": 0.015,
            "output_per_1k": 0.075,
        },
        "claude-sonnet-4": {
            "input_per_1k": 0.003,
            "output_per_1k": 0.015,
        },
        "claude-sonnet-4-20250514": {
            "input_per_1k": 0.003,
            "output_per_1k": 0.015,
        },
        "claude-3-5-sonnet": {
            "input_per_1k": 0.003,
            "output_per_1k": 0.015,
        },
        "claude-3-haiku": {
            "input_per_1k": 0.00025,
            "output_per_1k": 0.00125,
        },
    },
    "groq": {
        # Groq models (fast inference)
        "llama-3.3-70b": {
            "input_per_1k": 0.00059,
            "output_per_1k": 0.00079,
        },
        "mixtral-8x7b": {
            "input_per_1k": 0.00024,
            "output_per_1k": 0.00024,
        },
    },
    "local": {
        # Local models (free)
        "ollama": {
            "input_per_1k": 0.0,
            "output_per_1k": 0.0,
        },
    },
}


class CostCalculator:
    """
    Calculate API costs based on provider, model, and token usage.

    Usage:
        calc = CostCalculator()
        cost = calc.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
    """

    def __init__(self, custom_pricing: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None):
        """
        Initialize the calculator.

        Args:
            custom_pricing: Optional custom pricing to override defaults
        """
        self._pricing = {**MODEL_PRICING}
        if custom_pricing:
            for provider, models in custom_pricing.items():
                if provider not in self._pricing:
                    self._pricing[provider] = {}
                self._pricing[provider].update(models)

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate the cost of an API call.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "grok")
            model: Model name (e.g., "gpt-4o", "claude-opus-4")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = self._get_model_pricing(provider, model)
        if pricing is None:
            return 0.0

        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]

        return input_cost + output_cost

    def _get_model_pricing(
        self,
        provider: str,
        model: str,
    ) -> Optional[Dict[str, float]]:
        """
        Get pricing for a specific provider/model combination.

        Returns None if not found (unknown provider/model).
        """
        provider_lower = provider.lower()
        model_lower = model.lower()

        if provider_lower not in self._pricing:
            return None

        provider_models = self._pricing[provider_lower]

        # Direct match
        if model_lower in provider_models:
            return provider_models[model_lower]

        # Partial match (for model variants)
        for model_key, pricing in provider_models.items():
            if model_key in model_lower or model_lower in model_key:
                return pricing

        # Return first model as fallback for known provider
        if provider_models:
            return list(provider_models.values())[0]

        return None

    def get_pricing(self, provider: str, model: str) -> Dict[str, float]:
        """
        Get pricing info for a provider/model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Dict with 'input' and 'output' keys (per 1K tokens)
        """
        pricing = self._get_model_pricing(provider, model)
        if pricing is None:
            return {"input": 0.0, "output": 0.0}

        return {
            "input": pricing["input_per_1k"],
            "output": pricing["output_per_1k"],
        }

    def list_providers(self) -> List[str]:
        """
        List all supported providers.

        Returns:
            List of provider names
        """
        return list(self._pricing.keys())

    def list_models(self, provider: str) -> List[str]:
        """
        List all models for a provider.

        Args:
            provider: Provider name

        Returns:
            List of model names
        """
        provider_lower = provider.lower()
        if provider_lower not in self._pricing:
            return []
        return list(self._pricing[provider_lower].keys())
