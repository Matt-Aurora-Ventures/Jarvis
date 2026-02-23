"""ai_signal_bridge.py — AI signal -> Jupiter Perps ExecutionIntent pipeline.

Three signal sources, each contributing real alpha:
    1. Grok Perps Analysis  (weight 0.50) — dedicated leveraged trading prompt
    2. Price Momentum       (weight 0.30) — pure price action, no AI
    3. Ecosystem Sentiment  (weight 0.20) — aggregated token verdicts

Modes (PERPS_AI_MODE env var):
    disabled  — all signals dropped silently (default)
    alert     — log signal + optional Telegram alert, no execution
    live      — generate ExecutionIntent and queue for execution

Usage as runner task:
    queue = asyncio.Queue()
    stop  = asyncio.Event()
    task  = asyncio.create_task(
        ai_signal_loop(queue, stop, position_manager, cost_gate, tuner,
                       poll_interval=300)
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Protocol

from core.jupiter_perps.intent import (
    CollateralMint,
    ExecutionIntent,
    ClosePosition,
    Noop,
    OpenPosition,
    Side,
    new_idempotency_key,
)
from core.utils.secret_store import get_secret

if TYPE_CHECKING:
    from core.jupiter_perps.cost_gate import CostGate
    from core.jupiter_perps.position_manager import PositionManager
    from core.jupiter_perps.self_adjuster import PerpsAutoTuner

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env vars)
# ---------------------------------------------------------------------------

_AI_MODE = os.environ.get("PERPS_AI_MODE", "disabled").lower()
_MAX_USD = float(os.environ.get("PERPS_AI_MAX_USD", "500"))
_MIN_CONFIDENCE = float(os.environ.get("PERPS_AI_MIN_CONFIDENCE", "0.75"))
_COOLDOWN_SECONDS = int(os.environ.get("PERPS_AI_COOLDOWN_MINUTES", "60")) * 60
_BASE_SIZE_USD = float(os.environ.get("PERPS_AI_BASE_SIZE_USD", "100"))

# Perps-eligible assets and their market strings
_PERPS_ASSETS: dict[str, str] = {
    "SOL": "SOL-USD",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}

# Leverage table: (min_confidence, max_confidence) -> leverage multiplier
_LEVERAGE_TABLE: list[tuple[float, float, float]] = [
    (0.70, 0.80, 2.0),
    (0.80, 0.85, 3.0),
    (0.85, 0.90, 5.0),
    (0.90, 0.95, 7.0),
    (0.95, 1.01, 10.0),
]

# Default source weights (tuned by self-adjuster over time)
DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "grok_perps": 0.50,
    "momentum": 0.30,
    "aggregate": 0.20,
}

DEFAULT_PROVIDER_RELIABILITY: dict[str, float] = {
    "xai": 0.95,
    "openai": 0.92,
    "anthropic": 0.92,
    "rules": 0.95,
    "ecosystem": 0.90,
    "operator": 1.00,
    "unknown": 0.75,
}

_DEFAULT_GROK_MODEL = "grok-4-1-fast-non-reasoning"
_DEFAULT_PROVIDER_LIST = "xai"
_DEFAULT_ARBITRATION_MARGIN = 0.35
_DEFAULT_MIN_DIRECTION_SCORE = 0.15


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AISignal:
    """Normalised signal from any AI source."""

    asset: str               # SOL | BTC | ETH
    direction: str           # long | short | neutral
    confidence: float        # 0.0 - 1.0
    regime: str              # bull | bear | ranging
    source: str              # grok_perps | momentum | aggregate | manual
    rationale: str = ""
    expected_move_pct: float = 0.0  # expected price move (from Grok)
    max_leverage: float = 0.0       # recommended max leverage (from Grok)
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = "unknown"       # xai | openai | anthropic | rules | ecosystem | operator
    model: str = ""


@dataclass(frozen=True)
class LLMProviderConfig:
    """Runtime config for one LLM adapter."""

    name: str
    model: str
    endpoint: str
    api_key: str
    api_style: str = "openai_chat"  # openai_chat | anthropic_messages
    timeout_seconds: float = 30.0


class PerpsLLMAdapter(Protocol):
    """Adapter contract for querying one LLM provider."""

    config: LLMProviderConfig

    async def analyze_asset(self, asset: str) -> AISignal | None:
        """Return one normalized signal for an asset."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _parse_provider_list(value: str) -> list[str]:
    providers: list[str] = []
    for part in value.split(","):
        name = part.strip().lower()
        if name and name not in providers:
            providers.append(name)
    return providers


def _load_provider_reliability() -> dict[str, float]:
    reliability = dict(DEFAULT_PROVIDER_RELIABILITY)
    raw = os.environ.get("PERPS_AI_PROVIDER_RELIABILITY_JSON", "").strip()
    if not raw:
        return reliability

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Invalid PERPS_AI_PROVIDER_RELIABILITY_JSON; using defaults")
        return reliability

    if not isinstance(parsed, dict):
        log.warning("PERPS_AI_PROVIDER_RELIABILITY_JSON must be a JSON object; using defaults")
        return reliability

    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        try:
            reliability[key.lower()] = _clamp(float(value), 0.1, 2.0)
        except (TypeError, ValueError):
            continue
    return reliability


def _source_weight(source: str, weights: dict[str, float]) -> float:
    if source.startswith("consensus(") and source.endswith(")"):
        inner = source[len("consensus("):-1]
        first = inner.split(",")[0].strip() if inner else source
        return weights.get(first, weights.get(source, 0.1))
    return weights.get(source, 0.1)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    return str(content).strip()


def _lookup_leverage(confidence: float) -> float:
    """Map confidence to leverage via the table. Below min returns 1.0."""
    for lo, hi, lev in _LEVERAGE_TABLE:
        if lo <= confidence < hi:
            return lev
    return 1.0


def _compute_size(confidence: float, leverage: float, multiplier: float = 1.0) -> float:
    """Size = min(max_usd, base * confidence * leverage_factor * tuner_multiplier)."""
    raw = _BASE_SIZE_USD * confidence * (1.0 + (leverage - 1.0) * 0.3) * multiplier
    return min(raw, _MAX_USD)


def _collateral_for_asset(asset: str) -> CollateralMint:
    """Pick collateral mint. SOL positions use SOL collateral, others use USDC."""
    if asset == "SOL":
        return CollateralMint.SOL
    return CollateralMint.USDC


class _CooldownTracker:
    """Per-asset cooldown enforcement."""

    def __init__(self) -> None:
        self._last_signal: dict[str, float] = {}

    def is_cooled_down(self, asset: str) -> bool:
        last = self._last_signal.get(asset, 0.0)
        return (time.time() - last) >= _COOLDOWN_SECONDS

    def record(self, asset: str) -> None:
        self._last_signal[asset] = time.time()

    def seconds_remaining(self, asset: str) -> float:
        last = self._last_signal.get(asset, 0.0)
        remaining = _COOLDOWN_SECONDS - (time.time() - last)
        return max(0.0, remaining)


# Module-level cooldown tracker (shared across polls within a single process)
_cooldowns = _CooldownTracker()


# ---------------------------------------------------------------------------
# Signal -> Intent conversion
# ---------------------------------------------------------------------------


def signal_to_intent(
    signal: AISignal,
    size_multiplier: float = 1.0,
) -> ExecutionIntent | None:
    """Convert an AISignal to an ExecutionIntent, or None if dropped.

    Args:
        signal: The merged AI signal
        size_multiplier: Position size multiplier from self-adjuster (half-Kelly)
    """
    # Drop neutral signals
    if signal.direction == "neutral":
        return None

    # Validate asset
    market = _PERPS_ASSETS.get(signal.asset.upper())
    if market is None:
        log.debug("Unsupported perps asset: %s", signal.asset)
        return None

    # Confidence gate
    if signal.confidence < _MIN_CONFIDENCE:
        log.debug(
            "Signal below confidence threshold: %s %.2f < %.2f",
            signal.asset, signal.confidence, _MIN_CONFIDENCE,
        )
        return None

    # Cooldown gate
    if not _cooldowns.is_cooled_down(signal.asset):
        remaining = _cooldowns.seconds_remaining(signal.asset)
        log.debug("Cooldown active for %s: %.0fs remaining", signal.asset, remaining)
        return None

    # Regime-aware confidence adjustment
    effective_confidence = signal.confidence
    if signal.regime == "bear" and signal.direction == "long":
        effective_confidence *= 0.75
    elif signal.regime == "bull" and signal.direction == "short":
        effective_confidence *= 0.75
    elif signal.regime == "bull" and signal.direction == "long":
        effective_confidence *= 1.05

    # Re-check after adjustment
    if effective_confidence < _MIN_CONFIDENCE:
        log.debug(
            "Signal below threshold after regime adjustment: %s %.3f",
            signal.asset, effective_confidence,
        )
        return None

    # Clamp confidence
    effective_confidence = min(effective_confidence, 1.0)

    # Use Grok's recommended max leverage if available, else table lookup
    leverage = _lookup_leverage(effective_confidence)
    if signal.max_leverage > 0:
        leverage = min(leverage, signal.max_leverage)

    size_usd = _compute_size(effective_confidence, leverage, size_multiplier)
    collateral = _collateral_for_asset(signal.asset)
    side = Side.LONG if signal.direction == "long" else Side.SHORT
    collateral_amount = size_usd / leverage

    intent = OpenPosition(
        idempotency_key=f"ai-{signal.source}-{signal.asset}-{new_idempotency_key()}",
        market=market,
        side=side,
        collateral_mint=collateral,
        collateral_amount_usd=round(collateral_amount, 2),
        leverage=leverage,
        size_usd=round(size_usd, 2),
        max_slippage_bps=50,
    )

    _cooldowns.record(signal.asset)
    return intent


def exit_decision_to_intent(
    idempotency_key: str,
    position_pda: str,
) -> ClosePosition:
    """Convert an exit decision into a ClosePosition intent."""
    return ClosePosition(
        idempotency_key=f"exit-{idempotency_key}-{new_idempotency_key()}",
        position_pda=position_pda,
        max_slippage_bps=100,
    )


# ---------------------------------------------------------------------------
# Signal Source 1: Grok Perps Analysis
# ---------------------------------------------------------------------------

_GROK_PERPS_PROMPT = """Analyze current conditions for leveraged perpetual futures trading on {asset}-USD.

Consider:
1. Current price trend direction and strength (4h and daily timeframes)
2. Key support and resistance levels relative to current price
3. Whether the market is in a trending or ranging state
4. Volatility regime (expanding, contracting, or stable)
5. General market sentiment for this asset

You MUST respond with ONLY valid JSON, no other text:
{{
    "direction": "long" or "short" or "neutral",
    "confidence": 0.0 to 1.0,
    "max_leverage": 1 to 20,
    "expected_move_pct": float (expected % move in your direction),
    "timeframe_hours": int (how long the move takes),
    "regime": "bull" or "bear" or "ranging",
    "rationale": "one sentence explanation"
}}
"""


def _resolve_provider_model(provider: str) -> str:
    provider = provider.lower()
    if provider == "xai":
        return (
            os.environ.get("PERPS_AI_XAI_MODEL", "").strip()
            or os.environ.get("PERPS_AI_GROK_MODEL", "").strip()
            or os.environ.get("PERPS_AI_MODEL", "").strip()
            or _DEFAULT_GROK_MODEL
        )
    if provider == "openai":
        return os.environ.get("PERPS_AI_OPENAI_MODEL", "gpt-4o-mini").strip()
    if provider == "anthropic":
        return os.environ.get("PERPS_AI_ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
    return ""


def _build_llm_adapter_configs(timeout_seconds: float) -> list[LLMProviderConfig]:
    provider_list = _parse_provider_list(
        os.environ.get("PERPS_AI_LLM_PROVIDERS", _DEFAULT_PROVIDER_LIST),
    )
    if not provider_list:
        provider_list = ["xai"]

    configs: list[LLMProviderConfig] = []
    for provider in provider_list:
        if provider == "xai":
            api_key = get_secret("XAI_API_KEY")
            if not api_key:
                log.debug("XAI_API_KEY not set; skipping xai adapter")
                continue
            configs.append(
                LLMProviderConfig(
                    name="xai",
                    model=_resolve_provider_model("xai"),
                    endpoint=os.environ.get("PERPS_AI_XAI_ENDPOINT", "https://api.x.ai/v1/chat/completions").strip(),
                    api_key=api_key,
                    api_style="openai_chat",
                    timeout_seconds=timeout_seconds,
                ),
            )
            continue

        if provider == "openai":
            api_key = get_secret("OPENAI_API_KEY")
            if not api_key:
                log.debug("OPENAI_API_KEY not set; skipping openai adapter")
                continue
            configs.append(
                LLMProviderConfig(
                    name="openai",
                    model=_resolve_provider_model("openai"),
                    endpoint=os.environ.get("PERPS_AI_OPENAI_ENDPOINT", "https://api.openai.com/v1/chat/completions").strip(),
                    api_key=api_key,
                    api_style="openai_chat",
                    timeout_seconds=timeout_seconds,
                ),
            )
            continue

        if provider == "anthropic":
            api_key = get_secret("ANTHROPIC_API_KEY")
            if not api_key:
                log.debug("ANTHROPIC_API_KEY not set; skipping anthropic adapter")
                continue
            configs.append(
                LLMProviderConfig(
                    name="anthropic",
                    model=_resolve_provider_model("anthropic"),
                    endpoint=os.environ.get("PERPS_AI_ANTHROPIC_ENDPOINT", "https://api.anthropic.com/v1/messages").strip(),
                    api_key=api_key,
                    api_style="anthropic_messages",
                    timeout_seconds=timeout_seconds,
                ),
            )
            continue

        log.debug("Unknown provider '%s' in PERPS_AI_LLM_PROVIDERS; ignoring", provider)

    return configs


class _HTTPPerpsAdapter:
    """Adapter wrapper to keep provider-specific code isolated."""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    async def analyze_asset(self, asset: str) -> AISignal | None:
        if self.config.name == "xai":
            return await _call_grok_perps(
                asset,
                self.config.api_key,
                endpoint=self.config.endpoint,
                model=self.config.model,
                timeout_seconds=self.config.timeout_seconds,
            )
        if self.config.name == "openai":
            return await _call_openai_perps(
                asset,
                self.config.api_key,
                endpoint=self.config.endpoint,
                model=self.config.model,
                timeout_seconds=self.config.timeout_seconds,
            )
        if self.config.name == "anthropic":
            return await _call_anthropic_perps(
                asset,
                self.config.api_key,
                endpoint=self.config.endpoint,
                model=self.config.model,
                timeout_seconds=self.config.timeout_seconds,
            )
        return None


async def _extract_perps_signals() -> list[AISignal]:
    """Run configured LLM adapters against each perps asset and normalize outputs."""
    timeout_seconds = _clamp(
        float(os.environ.get("PERPS_AI_PROVIDER_TIMEOUT_SECONDS", "30.0")),
        5.0,
        120.0,
    )
    configs = _build_llm_adapter_configs(timeout_seconds)
    adapters: list[PerpsLLMAdapter] = [_HTTPPerpsAdapter(cfg) for cfg in configs]
    tasks: list[Any] = []
    for adapter in adapters:
        for asset in _PERPS_ASSETS:
            tasks.append(adapter.analyze_asset(asset))

    if not tasks:
        return []

    signals: list[AISignal] = []
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, AISignal):
            signals.append(result)
            continue
        if isinstance(result, Exception):
            log.debug("LLM perps analysis task failed", exc_info=result)
    return signals


async def _call_grok_perps(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """Make a single xAI Grok API call for perps analysis on one asset."""
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        # Fall back to urllib if httpx not available
        return await _call_grok_perps_urllib(
            asset,
            api_key,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    prompt = _GROK_PERPS_PROMPT.format(asset=asset)

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 300,
            },
        )
        response.raise_for_status()
        data = response.json()

    content = _normalize_text_content(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    return _parse_grok_response(asset, content, provider="xai", model=model)


async def _call_grok_perps_urllib(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """Fallback xAI call using stdlib urllib."""
    import urllib.request  # noqa: PLC0415

    prompt = _GROK_PERPS_PROMPT.format(asset=asset)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
    }).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    def _do_request() -> str:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return _normalize_text_content(data.get("choices", [{}])[0].get("message", {}).get("content", ""))

    content = await asyncio.to_thread(_do_request)
    return _parse_grok_response(asset, content, provider="xai", model=model)


async def _call_openai_perps(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """OpenAI-compatible adapter for perps analysis."""
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        return await _call_openai_perps_urllib(
            asset,
            api_key,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    prompt = _GROK_PERPS_PROMPT.format(asset=asset)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = _normalize_text_content(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    return _parse_grok_response(asset, content, provider="openai", model=model)


async def _call_openai_perps_urllib(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """Fallback OpenAI-compatible adapter using urllib."""
    import urllib.request  # noqa: PLC0415

    prompt = _GROK_PERPS_PROMPT.format(asset=asset)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    def _do_request() -> str:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return _normalize_text_content(data.get("choices", [{}])[0].get("message", {}).get("content", ""))

    content = await asyncio.to_thread(_do_request)
    return _parse_grok_response(asset, content, provider="openai", model=model)


async def _call_anthropic_perps(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """Anthropic adapter for perps analysis."""
    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        return await _call_anthropic_perps_urllib(
            asset,
            api_key,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    prompt = _GROK_PERPS_PROMPT.format(asset=asset)
    payload = {
        "model": model,
        "max_tokens": 300,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": os.environ.get("PERPS_AI_ANTHROPIC_VERSION", "2023-06-01"),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = _normalize_text_content(data.get("content", []))
    return _parse_grok_response(asset, content, provider="anthropic", model=model)


async def _call_anthropic_perps_urllib(
    asset: str,
    api_key: str,
    *,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> AISignal | None:
    """Fallback Anthropic adapter using urllib."""
    import urllib.request  # noqa: PLC0415

    prompt = _GROK_PERPS_PROMPT.format(asset=asset)
    payload = json.dumps({
        "model": model,
        "max_tokens": 300,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": os.environ.get("PERPS_AI_ANTHROPIC_VERSION", "2023-06-01"),
            "Content-Type": "application/json",
        },
    )

    def _do_request() -> str:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return _normalize_text_content(data.get("content", []))

    content = await asyncio.to_thread(_do_request)
    return _parse_grok_response(asset, content, provider="anthropic", model=model)


def _parse_grok_response(
    asset: str,
    content: str,
    *,
    provider: str = "xai",
    model: str = "",
) -> AISignal | None:
    """Parse provider JSON response into an AISignal."""
    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        log.debug("%s returned non-JSON for %s: %s", provider, asset, content[:120])
        return None

    direction = str(parsed.get("direction", "neutral")).lower()
    if direction not in ("long", "short", "neutral"):
        direction = "neutral"

    confidence = _clamp(_safe_float(parsed.get("confidence", 0.0)), 0.0, 1.0)

    if direction == "neutral" or confidence < 0.5:
        return None

    regime = str(parsed.get("regime", "ranging")).lower()
    if regime not in ("bull", "bear", "ranging"):
        regime = "ranging"

    raw = dict(parsed)
    raw["provider"] = provider
    if model:
        raw["model"] = model

    return AISignal(
        asset=asset,
        direction=direction,
        confidence=confidence,
        regime=regime,
        source="grok_perps",
        rationale=str(parsed.get("rationale", "")),
        expected_move_pct=_safe_float(parsed.get("expected_move_pct", 0.0)),
        max_leverage=_safe_float(parsed.get("max_leverage", 0.0)),
        raw=raw,
        provider=provider,
        model=model,
    )


# ---------------------------------------------------------------------------
# Signal Source 2: Price Momentum (pure price action — no AI)
# ---------------------------------------------------------------------------


async def _extract_momentum_signals() -> list[AISignal]:
    """Compute momentum from real price changes. No AI hallucination risk."""
    signals: list[AISignal] = []

    prices = await _fetch_price_changes()
    if not prices:
        return signals

    for asset, changes in prices.items():
        if asset not in _PERPS_ASSETS:
            continue

        change_1h = changes.get("1h", 0.0)
        change_4h = changes.get("4h", 0.0)
        change_24h = changes.get("24h", 0.0)

        # Weighted momentum score
        momentum = (change_1h * 0.5) + (change_4h * 0.3) + (change_24h * 0.2)

        # Require minimum momentum magnitude
        if abs(momentum) < 1.5:
            continue

        # Require trend alignment: short-term and long-term must agree
        if (change_1h > 0 and change_24h < -2.0) or (change_1h < 0 and change_24h > 2.0):
            continue  # conflicting timeframes

        direction = "long" if momentum > 0 else "short"

        # Confidence scales with momentum magnitude (capped)
        raw_confidence = min(abs(momentum) / 10.0, 1.0)  # 10% move = max confidence
        confidence = 0.50 + (raw_confidence * 0.40)  # range: 0.50 - 0.90

        # Determine regime from 24h trend
        if change_24h > 3.0:
            regime = "bull"
        elif change_24h < -3.0:
            regime = "bear"
        else:
            regime = "ranging"

        signals.append(AISignal(
            asset=asset,
            direction=direction,
            confidence=round(confidence, 3),
            regime=regime,
            source="momentum",
            rationale=f"Momentum: 1h={change_1h:+.1f}% 4h={change_4h:+.1f}% 24h={change_24h:+.1f}%",
            raw={"1h": change_1h, "4h": change_4h, "24h": change_24h, "score": momentum},
            provider="rules",
            model="momentum-v1",
        ))

    return signals


async def _fetch_price_changes() -> dict[str, dict[str, float]]:
    """Fetch recent price changes for perps-eligible assets.

    Returns: {"SOL": {"1h": 2.3, "4h": 5.1, "24h": 8.0}, ...}
    """
    try:
        return await _fetch_coingecko_changes()
    except Exception:
        log.debug("Price change fetch failed", exc_info=True)
        return {}


async def _fetch_coingecko_changes() -> dict[str, dict[str, float]]:
    """Fallback price changes from CoinGecko free API."""
    import urllib.request  # noqa: PLC0415

    cg_ids = {"SOL": "solana", "BTC": "bitcoin", "ETH": "ethereum"}
    ids_param = ",".join(cg_ids.values())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd&include_24hr_change=true"

    def _do() -> dict:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read())

    data = await asyncio.to_thread(_do)
    result: dict[str, dict[str, float]] = {}
    for asset, cg_id in cg_ids.items():
        if cg_id in data:
            change_24h = float(data[cg_id].get("usd_24h_change", 0.0))
            # CoinGecko only gives 24h — estimate shorter timeframes conservatively
            result[asset] = {
                "1h": change_24h / 8.0,   # rough approximation
                "4h": change_24h / 3.0,
                "24h": change_24h,
            }
    return result


# ---------------------------------------------------------------------------
# Signal Source 3: Ecosystem Sentiment (improved)
# ---------------------------------------------------------------------------


async def _extract_token_aggregate_signals() -> list[AISignal]:
    """Aggregate Grok token-level sentiment across the Solana ecosystem.

    If the majority of trending tokens are bullish with high confidence,
    that's a proxy for a bullish SOL ecosystem -> long SOL perps.
    """
    signals: list[AISignal] = []

    try:
        from bots.buy_tracker.sentiment_report import (  # noqa: PLC0415
            SentimentReportGenerator,
        )

        generator = SentimentReportGenerator.__new__(SentimentReportGenerator)
        tokens = await generator._get_trending_tokens(limit=20)
        if not tokens or len(tokens) < 5:
            return signals
    except Exception:
        log.debug("Could not load token sentiments")
        return signals

    # Count directional verdicts, weighted by market cap
    bullish_weight = 0.0
    bearish_weight = 0.0
    total_weight = 0.0
    total_grok_score = 0.0
    scored_count = 0

    for token in tokens:
        verdict = getattr(token, "grok_verdict", "NEUTRAL").upper()
        grok_score = getattr(token, "grok_score", 0.0)
        mcap = getattr(token, "market_cap", 1.0) or 1.0
        # Log-scale market cap weight to avoid whale tokens dominating
        import math  # noqa: PLC0415
        weight = max(1.0, math.log10(max(mcap, 1.0)))

        total_weight += weight
        if verdict == "BULLISH":
            bullish_weight += weight
        elif verdict == "BEARISH":
            bearish_weight += weight

        if grok_score != 0.0:
            total_grok_score += grok_score
            scored_count += 1

    if total_weight == 0 or scored_count == 0:
        return signals

    avg_score = total_grok_score / scored_count
    bull_ratio = bullish_weight / total_weight
    bear_ratio = bearish_weight / total_weight

    # Strong ecosystem bullish signal -> long SOL
    if bull_ratio >= 0.55 and avg_score > 0.2:
        confidence = min(0.50 + bull_ratio * 0.3 + avg_score * 0.15, 0.88)
        signals.append(AISignal(
            asset="SOL",
            direction="long",
            confidence=round(confidence, 3),
            regime="bull" if bull_ratio >= 0.65 else "ranging",
            source="aggregate",
            rationale=(
                f"Ecosystem: {bull_ratio:.0%} bullish (weighted), "
                f"avg Grok score {avg_score:.2f}, {scored_count} tokens"
            ),
            provider="ecosystem",
            model="token-aggregate-v1",
        ))
    # Strong ecosystem bearish signal -> short SOL
    elif bear_ratio >= 0.55 and avg_score < -0.2:
        confidence = min(0.50 + bear_ratio * 0.3 + abs(avg_score) * 0.15, 0.88)
        signals.append(AISignal(
            asset="SOL",
            direction="short",
            confidence=round(confidence, 3),
            regime="bear" if bear_ratio >= 0.65 else "ranging",
            source="aggregate",
            rationale=(
                f"Ecosystem: {bear_ratio:.0%} bearish (weighted), "
                f"avg Grok score {avg_score:.2f}, {scored_count} tokens"
            ),
            provider="ecosystem",
            model="token-aggregate-v1",
        ))

    return signals


# ---------------------------------------------------------------------------
# System state check
# ---------------------------------------------------------------------------


async def _check_system_state() -> tuple[bool, str]:
    """Check kill switches and system health before processing signals."""
    try:
        from core.context_loader import JarvisContext  # noqa: PLC0415

        if not JarvisContext.is_trading_enabled():
            return False, "LIFEOS_KILL_SWITCH active"
    except Exception:
        log.debug("JarvisContext unavailable — skipping system state check")

    return True, "ok"


# ---------------------------------------------------------------------------
# Weighted signal merging
# ---------------------------------------------------------------------------


def merge_signals(
    signals: list[AISignal],
    weights: dict[str, float] | None = None,
) -> list[AISignal]:
    """Merge signals using source weights plus provider reliability.

    Conflict handling is probabilistic: if one side dominates by weighted score
    it wins; otherwise the asset is dropped as ambiguous.
    """
    source_weights = weights or DEFAULT_SOURCE_WEIGHTS
    provider_reliability = _load_provider_reliability()
    arbitration_margin = _clamp(
        _safe_float(
            os.environ.get("PERPS_AI_ARBITRATION_MARGIN", _DEFAULT_ARBITRATION_MARGIN),
            _DEFAULT_ARBITRATION_MARGIN,
        ),
        0.05,
        0.90,
    )
    min_direction_score = _clamp(
        _safe_float(
            os.environ.get("PERPS_AI_MIN_DIRECTION_SCORE", _DEFAULT_MIN_DIRECTION_SCORE),
            _DEFAULT_MIN_DIRECTION_SCORE,
        ),
        0.01,
        1.50,
    )

    by_asset: dict[str, list[AISignal]] = {}
    for signal in signals:
        by_asset.setdefault(signal.asset, []).append(signal)

    merged: list[AISignal] = []
    for asset, group in by_asset.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        buckets: dict[str, list[tuple[AISignal, float, float]]] = {"long": [], "short": []}
        for signal in group:
            if signal.direction not in ("long", "short"):
                continue
            base_weight = _source_weight(signal.source, source_weights)
            provider_key = signal.provider.lower().strip() if signal.provider else "unknown"
            reliability = provider_reliability.get(
                provider_key,
                provider_reliability.get("unknown", 0.75),
            )
            effective_weight = max(base_weight * reliability, 0.01)
            score = signal.confidence * effective_weight
            buckets[signal.direction].append((signal, score, effective_weight))

        if not buckets["long"] and not buckets["short"]:
            continue

        long_score = sum(score for _, score, _ in buckets["long"])
        short_score = sum(score for _, score, _ in buckets["short"])
        total_score = long_score + short_score
        if total_score <= 0:
            continue

        if long_score >= short_score:
            winner_direction = "long"
            winner_score = long_score
            loser_score = short_score
        else:
            winner_direction = "short"
            winner_score = short_score
            loser_score = long_score

        margin = (winner_score - loser_score) / total_score
        if winner_score < min_direction_score:
            log.info(
                "Low conviction signals for %s (winner_score=%.3f < %.3f); dropping",
                asset,
                winner_score,
                min_direction_score,
            )
            continue

        if loser_score > 0 and margin < arbitration_margin:
            log.info(
                "Ambiguous conflict for %s (margin=%.3f < %.3f); dropping",
                asset,
                margin,
                arbitration_margin,
            )
            continue

        winners = buckets[winner_direction]
        total_weight = sum(weight for _, _, weight in winners)
        weighted_confidence = (
            sum(signal.confidence * weight for signal, _, weight in winners) / total_weight
            if total_weight > 0
            else max(signal.confidence for signal, _, _ in winners)
        )

        consensus_bonus = min((len(winners) - 1) * 0.02, 0.06)
        margin_bonus = min(margin * 0.18, 0.12)
        final_confidence = min(weighted_confidence + consensus_bonus + margin_bonus, 0.98)

        ranked = sorted(winners, key=lambda item: item[1], reverse=True)
        best = ranked[0][0]

        regime_scores: dict[str, float] = {}
        for signal, score, _ in winners:
            regime_scores[signal.regime] = regime_scores.get(signal.regime, 0.0) + score
        merged_regime = max(regime_scores.items(), key=lambda item: item[1])[0]

        source_order: list[str] = []
        provider_order: list[str] = []
        for signal, _, _ in ranked:
            if signal.source not in source_order:
                source_order.append(signal.source)
            provider_name = signal.provider or "unknown"
            if provider_name not in provider_order:
                provider_order.append(provider_name)

        rationale_parts = [signal.rationale for signal, _, _ in ranked if signal.rationale]
        merged.append(AISignal(
            asset=asset,
            direction=winner_direction,
            confidence=round(final_confidence, 3),
            regime=merged_regime,
            source=f"consensus({','.join(source_order)})",
            rationale=" | ".join(rationale_parts[:3]),
            expected_move_pct=best.expected_move_pct,
            max_leverage=best.max_leverage,
            provider="multi" if len(provider_order) > 1 else provider_order[0],
            model=best.model,
            raw={
                "arb_margin": round(margin, 4),
                "long_score": round(long_score, 4),
                "short_score": round(short_score, 4),
                "providers": provider_order,
                "sources": source_order,
            },
        ))

    return merged


# ---------------------------------------------------------------------------
# Alert dispatch
# ---------------------------------------------------------------------------


async def _send_telegram_message(chat_id: str, text: str) -> bool:
    """Send a Telegram message via the Bot API (lightweight, no dependencies)."""
    import urllib.request  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415

    bot_token = get_secret("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")

    def _do() -> bool:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return resp.status == 200

    return await asyncio.to_thread(_do)


async def _send_alert(signal: AISignal, intent: ExecutionIntent | None) -> None:
    """Send Telegram alert about an AI signal."""
    try:
        chat_id = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID", "")
        if not chat_id:
            return

        mode_label = "LIVE" if _AI_MODE == "live" else "ALERT ONLY"

        if intent is None:
            intent_desc = "no intent generated"
        elif isinstance(intent, OpenPosition):
            intent_desc = (
                f"{intent.side.value.upper()} {intent.market} "
                f"@ {intent.leverage}x ${intent.size_usd:.0f}"
            )
        elif isinstance(intent, ClosePosition):
            intent_desc = f"CLOSE {intent.position_pda[:16]}..."
        else:
            intent_desc = str(type(intent).__name__)

        msg = (
            f"[PERPS AI {mode_label}] {signal.asset} {signal.direction.upper()}\n"
            f"Confidence: {signal.confidence:.0%} | Regime: {signal.regime}\n"
            f"Source: {signal.source} | Provider: {signal.provider}\n"
            f"Intent: {intent_desc}\n"
            f"Rationale: {signal.rationale}"
        )

        await _send_telegram_message(chat_id, msg)
    except Exception:
        log.debug("Could not send Telegram alert", exc_info=True)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def ai_signal_loop(
    queue: asyncio.Queue[ExecutionIntent],
    stop_event: asyncio.Event,
    position_manager: PositionManager | None = None,
    cost_gate: CostGate | None = None,
    tuner: PerpsAutoTuner | None = None,
    poll_interval: int = 300,
) -> None:
    """Main AI signal bridge loop. Runs as an asyncio task inside the runner.

    Every `poll_interval` seconds:
      1. Check system state (kill switch)
      2. Extract signals from all sources
      3. Check signal reversals against open positions
      4. Merge multi-source signals (weighted)
      5. Run each through cost gate
      6. Convert to ExecutionIntents
      7. Queue intents (live mode) or log alerts (alert mode)
    """
    log.info(
        "AI signal bridge started mode=%s interval=%ds min_confidence=%.2f max_usd=%.0f",
        _AI_MODE, poll_interval, _MIN_CONFIDENCE, _MAX_USD,
    )

    if _AI_MODE == "disabled":
        log.info("AI signal bridge disabled — sleeping until stop")
        await stop_event.wait()
        return

    while not stop_event.is_set():
        try:
            await _poll_once(queue, position_manager, cost_gate, tuner)
        except Exception:
            log.exception("AI signal bridge poll error")

        # Interruptible sleep
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
            break
        except asyncio.TimeoutError:
            pass

    log.info("AI signal bridge stopped")


async def _poll_once(
    queue: asyncio.Queue[ExecutionIntent],
    position_manager: PositionManager | None,
    cost_gate: CostGate | None,
    tuner: PerpsAutoTuner | None,
) -> None:
    """Single poll cycle: extract -> merge -> gate -> dispatch."""

    # System state check
    ok, reason = await _check_system_state()
    if not ok:
        log.info("AI signal bridge paused: %s", reason)
        return

    # Get source weights from tuner (or defaults)
    weights = tuner.get_weights() if tuner is not None else None

    # Extract signals from all sources concurrently
    results = await asyncio.gather(
        _extract_perps_signals(),
        _extract_momentum_signals(),
        _extract_token_aggregate_signals(),
        return_exceptions=True,
    )

    raw_signals: list[AISignal] = []
    for result in results:
        if isinstance(result, list):
            raw_signals.extend(result)
        elif isinstance(result, Exception):
            log.debug("Signal source error: %s", result)

    if not raw_signals:
        log.debug("No AI signals this cycle")
        return

    # Check signal reversals against open positions
    if position_manager is not None:
        for signal in raw_signals:
            if signal.direction in ("long", "short"):
                exits = position_manager.check_signal_reversal(
                    signal.asset, signal.direction, signal.confidence,
                )
                for exit_dec in exits:
                    intent = exit_decision_to_intent(
                        exit_dec.idempotency_key, exit_dec.position_pda,
                    )
                    if _AI_MODE == "live":
                        try:
                            queue.put_nowait(intent)
                            log.info("Signal reversal close queued: %s", exit_dec.reason)
                        except asyncio.QueueFull:
                            log.warning("Queue full — dropped reversal close")

    # Merge multi-source signals
    merged = merge_signals(raw_signals, weights=weights)
    log.info("AI signals: %d raw -> %d merged", len(raw_signals), len(merged))

    for signal in merged:
        # Get size multiplier from tuner
        size_mult = 1.0
        if tuner is not None:
            size_mult = tuner.get_position_size_multiplier(signal.source)

        intent = signal_to_intent(signal, size_multiplier=size_mult)

        if _AI_MODE == "alert":
            await _send_alert(signal, intent)
            continue

        if _AI_MODE == "live" and intent is not None:
            # Run through cost gate
            if cost_gate is not None and position_manager is not None and isinstance(intent, OpenPosition):
                verdict = cost_gate.evaluate(
                    market=intent.market,
                    side=intent.side.value,
                    size_usd=intent.size_usd,
                    leverage=intent.leverage,
                    confidence=signal.confidence,
                    position_manager=position_manager,
                )
                if not verdict.passed:
                    log.info("Cost gate rejected %s %s: %s", signal.asset, signal.direction, verdict.reason)
                    await _send_alert(signal, None)
                    continue

            await _send_alert(signal, intent)
            try:
                queue.put_nowait(intent)
                log.info(
                    "AI intent queued: %s %s %s %.0fx $%.0f [%s]",
                    signal.asset, signal.direction, intent.market,
                    intent.leverage, intent.size_usd, signal.source,
                )
            except asyncio.QueueFull:
                log.warning(
                    "Queue full — dropped AI intent for %s %s",
                    signal.asset, signal.direction,
                )


# ---------------------------------------------------------------------------
# Manual signal injection (for Telegram /perps commands)
# ---------------------------------------------------------------------------


def create_manual_signal(
    asset: str,
    direction: str,
    confidence: float = 0.90,
    rationale: str = "manual operator signal",
) -> AISignal:
    """Create a manual signal from operator command (e.g., Telegram /perps open)."""
    return AISignal(
        asset=asset.upper(),
        direction=direction.lower(),
        confidence=confidence,
        regime="ranging",
        source="manual",
        rationale=rationale,
        provider="operator",
        model="manual-v1",
    )


async def process_manual_signal(
    signal: AISignal,
    queue: asyncio.Queue[ExecutionIntent],
) -> ExecutionIntent | None:
    """Process a manual signal immediately, bypassing cooldown for manual source."""
    market = _PERPS_ASSETS.get(signal.asset.upper())
    if market is None:
        return None

    if signal.direction == "neutral":
        return None

    leverage = _lookup_leverage(signal.confidence)
    size_usd = _compute_size(signal.confidence, leverage)
    collateral = _collateral_for_asset(signal.asset)
    side = Side.LONG if signal.direction == "long" else Side.SHORT

    intent = OpenPosition(
        idempotency_key=f"manual-{signal.asset}-{new_idempotency_key()}",
        market=market,
        side=side,
        collateral_mint=collateral,
        collateral_amount_usd=round(size_usd / leverage, 2),
        leverage=leverage,
        size_usd=round(size_usd, 2),
        max_slippage_bps=50,
    )

    if _AI_MODE == "live":
        try:
            queue.put_nowait(intent)
        except asyncio.QueueFull:
            log.warning("Queue full — could not queue manual intent")
            return None

    await _send_alert(signal, intent)
    return intent


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s")

    # Test signal -> intent conversion
    test_signals = [
        AISignal("SOL", "long", 0.85, "bull", "grok_perps", "Test bullish SOL"),
        AISignal("BTC", "short", 0.72, "bear", "momentum", "Test bearish BTC"),
        AISignal("ETH", "long", 0.50, "ranging", "aggregate", "Below threshold"),
        AISignal("SOL", "neutral", 0.90, "bull", "manual", "Neutral = noop"),
        AISignal("DOGE", "long", 0.95, "bull", "manual", "Unsupported asset"),
    ]

    print("=== Signal -> Intent Test ===")
    for sig in test_signals:
        intent = signal_to_intent(sig)
        if intent is not None and isinstance(intent, OpenPosition):
            print(f"  {sig.asset} {sig.direction} conf={sig.confidence:.2f} -> "
                  f"{intent.market} {intent.side.value} {intent.leverage}x ${intent.size_usd:.0f}")
        else:
            print(f"  {sig.asset} {sig.direction} conf={sig.confidence:.2f} -> DROPPED")

    # Test weighted merge
    print("\n=== Weighted Merge Test ===")
    merge_input = [
        AISignal("SOL", "long", 0.80, "bull", "grok_perps", "Grok bullish"),
        AISignal("SOL", "long", 0.75, "bull", "momentum", "Momentum up"),
        AISignal("SOL", "long", 0.70, "bull", "aggregate", "Ecosystem bullish"),
        AISignal("BTC", "long", 0.82, "bull", "grok_perps", "BTC up"),
        AISignal("BTC", "short", 0.78, "bear", "momentum", "BTC bearish momentum"),
    ]
    merged = merge_signals(merge_input)
    for m in merged:
        print(f"  {m.asset} {m.direction} conf={m.confidence:.3f} src={m.source}")

    print("\n=== Leverage Table ===")
    for conf in [0.50, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
        lev = _lookup_leverage(conf)
        size = _compute_size(conf, lev)
        print(f"  conf={conf:.2f} -> leverage={lev:.0f}x size=${size:.0f}")
