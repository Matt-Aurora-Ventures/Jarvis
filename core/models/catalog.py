"""
JARVIS Model Catalog - Centralized model definitions.

Contains all supported models with specifications and pricing.
Pricing is per 1M tokens (input/output) in USD.
"""

from typing import Any, Dict, List, Optional


# Model catalog organized by provider
MODEL_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "anthropic": [
        {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6",
            "context": 200000,
            "cost_in": 15.0,
            "cost_out": 75.0,
            "description": "Most capable Claude model (Feb 2026)",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "context": 200000,
            "cost_in": 3.0,
            "cost_out": 15.0,
            "description": "Balanced performance and cost (Feb 2026) — recommended default",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-haiku-4-5-20251001",
            "name": "Claude Haiku 4.5",
            "context": 200000,
            "cost_in": 0.8,
            "cost_out": 4.0,
            "description": "Fastest and cheapest Claude model",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-opus-4-5",
            "name": "Claude Opus 4.5 (Legacy)",
            "context": 200000,
            "cost_in": 15.0,
            "cost_out": 75.0,
            "description": "Most capable model for complex tasks",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-sonnet-4-5",
            "name": "Claude Sonnet 4.5",
            "context": 200000,
            "cost_in": 3.0,
            "cost_out": 15.0,
            "description": "Balanced performance and cost",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-haiku-4",
            "name": "Claude Haiku 4",
            "context": 200000,
            "cost_in": 0.8,
            "cost_out": 4.0,
            "description": "Fast and efficient for simple tasks",
            "features": ["vision", "tool_use", "long_context"],
        },
        {
            "id": "claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4 (May 2025)",
            "context": 200000,
            "cost_in": 3.0,
            "cost_out": 15.0,
            "description": "Previous generation Sonnet",
            "features": ["vision", "tool_use", "long_context"],
        },
    ],
    "openai": [
        {
            "id": "gpt-4-turbo",
            "name": "GPT-4 Turbo",
            "context": 128000,
            "cost_in": 10.0,
            "cost_out": 30.0,
            "description": "Fast GPT-4 with vision",
            "features": ["vision", "function_calling"],
        },
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "context": 128000,
            "cost_in": 2.5,
            "cost_out": 10.0,
            "description": "Optimized GPT-4",
            "features": ["vision", "function_calling"],
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "context": 128000,
            "cost_in": 0.15,
            "cost_out": 0.6,
            "description": "Cost-effective GPT-4",
            "features": ["vision", "function_calling"],
        },
        {
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "context": 16000,
            "cost_in": 0.5,
            "cost_out": 1.5,
            "description": "Legacy fast model",
            "features": ["function_calling"],
        },
        {
            "id": "o1",
            "name": "o1",
            "context": 200000,
            "cost_in": 15.0,
            "cost_out": 60.0,
            "description": "Reasoning model",
            "features": ["reasoning"],
        },
        {
            "id": "o1-mini",
            "name": "o1 Mini",
            "context": 128000,
            "cost_in": 3.0,
            "cost_out": 12.0,
            "description": "Smaller reasoning model",
            "features": ["reasoning"],
        },
    ],
    "xai": [
        {
            "id": "grok-4-1-fast-non-reasoning",
            "name": "Grok 4-1 Fast",
            "context": 2000000,
            "cost_in": 0.20,
            "cost_out": 0.50,
            "description": "Fast, cheap Grok with 2M context — recommended default",
            "features": ["realtime_data", "long_context", "x_search"],
        },
        {
            "id": "grok-4-1-fast-reasoning",
            "name": "Grok 4-1 Fast Reasoning",
            "context": 2000000,
            "cost_in": 0.20,
            "cost_out": 0.50,
            "description": "Reasoning variant of Grok 4-1 Fast",
            "features": ["realtime_data", "long_context", "reasoning", "x_search"],
        },
        {
            "id": "grok-4",
            "name": "Grok 4",
            "context": 2000000,
            "cost_in": 3.0,
            "cost_out": 15.0,
            "description": "Most capable Grok model",
            "features": ["realtime_data", "long_context", "reasoning", "x_search"],
        },
        {
            "id": "grok-3",
            "name": "Grok 3 (Legacy)",
            "context": 128000,
            "cost_in": 5.0,
            "cost_out": 15.0,
            "description": "Previous generation flagship",
            "features": ["realtime_data", "long_context"],
        },
        {
            "id": "grok-3-mini",
            "name": "Grok 3 Mini (Legacy)",
            "context": 128000,
            "cost_in": 0.3,
            "cost_out": 0.5,
            "description": "Previous generation efficient model",
            "features": ["realtime_data"],
        },
    ],
    "groq": [
        {
            "id": "llama-3.3-70b-versatile",
            "name": "Llama 3.3 70B",
            "context": 128000,
            "cost_in": 0.59,
            "cost_out": 0.79,
            "description": "Fast Llama on Groq",
            "features": ["fast_inference"],
        },
        {
            "id": "mixtral-8x7b-32768",
            "name": "Mixtral 8x7B",
            "context": 32768,
            "cost_in": 0.24,
            "cost_out": 0.24,
            "description": "Mixture of experts",
            "features": ["fast_inference"],
        },
        {
            "id": "gemma2-9b-it",
            "name": "Gemma 2 9B",
            "context": 8192,
            "cost_in": 0.2,
            "cost_out": 0.2,
            "description": "Google Gemma 2",
            "features": ["fast_inference"],
        },
    ],
    "ollama": [
        {
            "id": "llama3.2",
            "name": "Llama 3.2 (Local)",
            "context": 128000,
            "cost_in": 0.0,
            "cost_out": 0.0,
            "description": "Local Llama model",
            "features": ["local", "private"],
        },
        {
            "id": "mistral",
            "name": "Mistral (Local)",
            "context": 32000,
            "cost_in": 0.0,
            "cost_out": 0.0,
            "description": "Local Mistral model",
            "features": ["local", "private"],
        },
        {
            "id": "codellama",
            "name": "Code Llama (Local)",
            "context": 16000,
            "cost_in": 0.0,
            "cost_out": 0.0,
            "description": "Local code model",
            "features": ["local", "private", "code"],
        },
    ],
}


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Get model information by ID.

    Args:
        model_id: The model identifier

    Returns:
        Model info dict with provider added, or None if not found
    """
    model_lower = model_id.lower()

    for provider, models in MODEL_CATALOG.items():
        for model in models:
            if model["id"].lower() == model_lower:
                return {**model, "provider": provider}

    return None


def list_providers() -> List[str]:
    """
    List all available providers.

    Returns:
        List of provider names
    """
    return list(MODEL_CATALOG.keys())


def list_models(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List models, optionally filtered by provider.

    Args:
        provider: Optional provider name to filter by

    Returns:
        List of model info dicts with provider added
    """
    result = []

    if provider:
        provider_lower = provider.lower()
        if provider_lower in MODEL_CATALOG:
            for model in MODEL_CATALOG[provider_lower]:
                result.append({**model, "provider": provider_lower})
    else:
        for prov, models in MODEL_CATALOG.items():
            for model in models:
                result.append({**model, "provider": prov})

    return result


def format_models_list(current_model: Optional[str] = None) -> str:
    """
    Format models list for Telegram display.

    Args:
        current_model: Optional current model ID to mark

    Returns:
        Formatted string for Telegram
    """
    lines = ["**Available Models**\n"]

    for provider in ["anthropic", "openai", "xai", "groq", "ollama"]:
        if provider not in MODEL_CATALOG:
            continue

        provider_title = {
            "anthropic": "Anthropic",
            "openai": "OpenAI",
            "xai": "xAI",
            "groq": "Groq",
            "ollama": "Ollama (Local)",
        }.get(provider, provider.title())

        lines.append(f"\n**{provider_title}**")

        for model in MODEL_CATALOG[provider]:
            marker = " [Current]" if model["id"] == current_model else ""
            cost_str = f"${model['cost_in']:.2f}/${model['cost_out']:.2f}" if model['cost_in'] > 0 else "Free"
            ctx_k = model['context'] // 1000

            lines.append(
                f"- `{model['id']}` - {model['name']} ({ctx_k}k ctx, {cost_str} per 1M){marker}"
            )

    lines.append("\nUse: `/model <model_id>` to switch")

    return "\n".join(lines)


def format_model_info(model_id: str) -> str:
    """
    Format single model info for display.

    Args:
        model_id: The model identifier

    Returns:
        Formatted string or error message
    """
    info = get_model_info(model_id)

    if not info:
        return f"Unknown model: {model_id}"

    lines = [
        f"**{info['name']}**",
        f"Provider: {info['provider'].title()}",
        f"Model ID: `{info['id']}`",
        f"Context: {info['context']:,} tokens ({info['context'] // 1000}k)",
        f"Pricing: ${info['cost_in']:.2f} / ${info['cost_out']:.2f} per 1M tokens (in/out)",
    ]

    if info.get("description"):
        lines.append(f"Description: {info['description']}")

    if info.get("features"):
        lines.append(f"Features: {', '.join(info['features'])}")

    return "\n".join(lines)


def estimate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float:
    """
    Estimate cost for a request.

    Args:
        model_id: The model identifier
        tokens_in: Input tokens
        tokens_out: Output tokens

    Returns:
        Estimated cost in USD
    """
    info = get_model_info(model_id)

    if not info:
        return 0.0

    cost_in = (tokens_in / 1_000_000) * info["cost_in"]
    cost_out = (tokens_out / 1_000_000) * info["cost_out"]

    return round(cost_in + cost_out, 6)
