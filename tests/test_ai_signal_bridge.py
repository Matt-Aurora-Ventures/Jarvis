from __future__ import annotations

import os

os.environ.setdefault("JARVIS_CORE_MINIMAL_IMPORTS", "1")

from core.jupiter_perps.ai_signal_bridge import (  # noqa: E402
    AISignal,
    _build_llm_adapter_configs,
    _resolve_provider_model,
    merge_signals,
)


def test_resolve_provider_model_prefers_explicit_xai_override(monkeypatch) -> None:
    monkeypatch.setenv("PERPS_AI_XAI_MODEL", "grok-custom-alpha")
    monkeypatch.setenv("PERPS_AI_GROK_MODEL", "grok-fallback")
    monkeypatch.setenv("PERPS_AI_MODEL", "grok-global")
    assert _resolve_provider_model("xai") == "grok-custom-alpha"


def test_build_llm_adapter_configs_filters_missing_keys(monkeypatch) -> None:
    monkeypatch.setenv("PERPS_AI_LLM_PROVIDERS", "xai,openai,anthropic")
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PERPS_AI_XAI_MODEL", "grok-4-1-fast-non-reasoning")
    monkeypatch.setenv("PERPS_AI_OPENAI_MODEL", "gpt-4.1-mini")

    configs = _build_llm_adapter_configs(timeout_seconds=25.0)
    names = [cfg.name for cfg in configs]

    assert names == ["xai", "openai"]
    assert all(cfg.timeout_seconds == 25.0 for cfg in configs)


def test_merge_signals_drops_ambiguous_conflict(monkeypatch) -> None:
    monkeypatch.setenv("PERPS_AI_ARBITRATION_MARGIN", "0.40")

    signals = [
        AISignal("BTC", "long", 0.80, "bull", "grok_perps", provider="xai"),
        AISignal("BTC", "short", 0.75, "bear", "momentum", provider="rules"),
    ]

    merged = merge_signals(signals)
    assert merged == []


def test_merge_signals_selects_dominant_side(monkeypatch) -> None:
    monkeypatch.setenv("PERPS_AI_ARBITRATION_MARGIN", "0.20")
    monkeypatch.setenv("PERPS_AI_MIN_DIRECTION_SCORE", "0.10")

    signals = [
        AISignal("SOL", "long", 0.93, "bull", "grok_perps", provider="xai", rationale="strong"),
        AISignal("SOL", "short", 0.55, "bear", "aggregate", provider="ecosystem", rationale="weak"),
    ]

    merged = merge_signals(signals)
    assert len(merged) == 1
    assert merged[0].direction == "long"
    assert merged[0].provider == "xai"
    assert merged[0].source.startswith("consensus(")


def test_merge_signals_uses_provider_reliability_override(monkeypatch) -> None:
    monkeypatch.setenv("PERPS_AI_ARBITRATION_MARGIN", "0.20")
    monkeypatch.setenv("PERPS_AI_PROVIDER_RELIABILITY_JSON", '{"xai": 0.4, "openai": 1.3}')

    signals = [
        AISignal("ETH", "long", 0.80, "bull", "grok_perps", provider="xai"),
        AISignal("ETH", "short", 0.80, "bear", "grok_perps", provider="openai"),
    ]

    merged = merge_signals(signals)
    assert len(merged) == 1
    assert merged[0].direction == "short"
    assert merged[0].provider == "openai"
