"""
Token counting and cost estimation utilities.

This implementation is intentionally model-agnostic and deterministic for tests.
It uses lightweight heuristics rather than vendor tokenizers.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, Iterable, List


class ModelType(str, Enum):
    GROK_3 = "grok-3"
    GPT_4 = "gpt-4"
    CLAUDE_3 = "claude-3"


_MODEL_FACTORS: Dict[ModelType, float] = {
    ModelType.GROK_3: 0.28,
    ModelType.GPT_4: 0.30,
    ModelType.CLAUDE_3: 0.27,
}

_MODEL_PRICING_INPUT: Dict[ModelType, float] = {
    ModelType.GROK_3: 0.0000020,
    ModelType.GPT_4: 0.0000100,
    ModelType.CLAUDE_3: 0.0000030,
}

_MODEL_PRICING_OUTPUT: Dict[ModelType, float] = {
    ModelType.GROK_3: 0.0000060,
    ModelType.GPT_4: 0.0000300,
    ModelType.CLAUDE_3: 0.0000150,
}


def _coerce_model(model: ModelType | str) -> ModelType:
    if isinstance(model, ModelType):
        return model
    try:
        return ModelType(str(model).lower())
    except Exception:
        return ModelType.GROK_3


class TokenCounter:
    """Heuristic token counter."""

    def count_tokens(self, text: str, model: ModelType | str = ModelType.GPT_4) -> int:
        if text is None:
            raise TypeError("text must be a string, not None")
        if not isinstance(text, str):
            raise TypeError(f"text must be a string, got {type(text).__name__}")
        if text == "":
            return 0

        model_key = _coerce_model(model)
        factor = _MODEL_FACTORS.get(model_key, 0.28)

        # Mix char-based and word-based estimates for more stable heuristic.
        char_estimate = math.ceil(len(text) * factor)
        word_estimate = len(text.split())
        return max(1, char_estimate, word_estimate)

    def count_messages(
        self,
        messages: Iterable[Dict[str, Any]],
        model: ModelType | str = ModelType.GPT_4,
    ) -> int:
        model_key = _coerce_model(model)
        total = 0
        for msg in list(messages):
            content = str(msg.get("content", ""))
            role = str(msg.get("role", ""))
            total += self.count_tokens(content, model_key)
            # Include lightweight protocol overhead for role framing.
            total += 3
            if role:
                total += 1
        return total

    def estimate_cost(
        self,
        token_count: int,
        model: ModelType | str = ModelType.GPT_4,
        is_output: bool = False,
    ) -> float:
        if token_count <= 0:
            return 0.0
        model_key = _coerce_model(model)
        price_table = _MODEL_PRICING_OUTPUT if is_output else _MODEL_PRICING_INPUT
        unit_price = price_table.get(model_key, 0.0000020)
        return float(token_count) * unit_price


def count_tokens(text: str, model: ModelType | str = ModelType.GPT_4) -> int:
    return TokenCounter().count_tokens(text, model=model)


def count_messages(
    messages: List[Dict[str, Any]],
    model: ModelType | str = ModelType.GPT_4,
) -> int:
    return TokenCounter().count_messages(messages, model=model)


def estimate_cost(
    token_count: int,
    model: ModelType | str = ModelType.GPT_4,
    is_output: bool = False,
) -> float:
    return TokenCounter().estimate_cost(token_count, model=model, is_output=is_output)

