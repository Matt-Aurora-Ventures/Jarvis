"""Route tasks to fast or deep models with lightweight heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core import config


_CODE_KEYWORDS = (
    "traceback",
    "stack trace",
    "exception",
    "error",
    "bug",
    "refactor",
    "optimize",
    "unit test",
    "pytest",
    "def ",
    "class ",
    "import ",
    "sql",
    "regex",
    "http",
)


@dataclass
class RouteDecision:
    mode: str
    provider: str
    model: Optional[str]
    max_output_tokens: int
    reason: str


class ModelRouter:
    """Selects a route based on role, prompt length, and keywords."""

    def __init__(self, cfg: Optional[Dict[str, Any]] = None) -> None:
        self._cfg = cfg or config.load_config()
        router_cfg = self._cfg.get("router", {})
        self._provider = str(router_cfg.get("provider", "auto")).lower()
        ollama_model = self._cfg.get("providers", {}).get("ollama", {}).get("model", "")
        self._fast_model = str(router_cfg.get("fast_model") or ollama_model or "").strip()
        self._deep_model = str(router_cfg.get("deep_model") or self._fast_model or "").strip()
        self._fast_tokens = int(router_cfg.get("fast_max_tokens", 256))
        self._deep_tokens = int(router_cfg.get("deep_max_tokens", 900))

    def route(self, role: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> RouteDecision:
        context = context or {}
        forced = str(context.get("route", "")).lower()
        if forced in {"fast", "deep"}:
            mode = forced
            reason = "forced"
        else:
            role = (role or "").lower()
            prompt_lower = prompt.lower()
            if role in {"planner", "reflector", "coder", "executor"}:
                mode = "deep"
                reason = f"role:{role}"
            elif len(prompt) > 1200 or any(keyword in prompt_lower for keyword in _CODE_KEYWORDS):
                mode = "deep"
                reason = "content"
            else:
                mode = "fast"
                reason = "lightweight"

        max_output_tokens = self._deep_tokens if mode == "deep" else self._fast_tokens
        model = self._deep_model if mode == "deep" else self._fast_model
        provider = self._provider if model else "auto"
        return RouteDecision(
            mode=mode,
            provider=provider,
            model=model or None,
            max_output_tokens=max_output_tokens,
            reason=reason,
        )
