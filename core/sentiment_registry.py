"""Cache-aware sentiment registry for candidate scoring."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional

from core import config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = ROOT / "data" / "trader" / "sentiment_registry.json"
GROK_CACHE_PATH = ROOT / "data" / "trader" / "grok_cache.json"
XAI_TWITTER_CACHE_PATH = ROOT / "data" / "trader" / "xai_cache" / "xai_twitter_cache.json"


@dataclass
class SentimentRegistryResult:
    symbol: str
    score: float
    sources: Dict[str, Any]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _config() -> Dict[str, Any]:
    cfg = config.load_config()
    registry_cfg = cfg.get("sentiment_registry", {}) if isinstance(cfg, dict) else {}
    return {
        "enabled": bool(registry_cfg.get("enabled", True)),
        "ttl_seconds": int(registry_cfg.get("ttl_seconds", 900)),
        "cache_only": bool(registry_cfg.get("cache_only", True)),
        "cache_path": registry_cfg.get("cache_path") or str(DEFAULT_CACHE_PATH),
        "xai_weight": float(registry_cfg.get("xai_weight", 0.4)),
        "heuristic_weight": float(registry_cfg.get("heuristic_weight", 0.6)),
    }


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _cache_key(text: str, focus: str) -> str:
    payload = f"{focus}::{text}".encode("utf-8")
    return sha256(payload).hexdigest()


def _lookup_grok_cache(text: str, focus: str = "trading") -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cache = _load_json(GROK_CACHE_PATH)
    entry = cache.get(_cache_key(text, focus))
    if not entry:
        return None
    return entry.get("payload")


def _parse_sentiment_label(label: str) -> float:
    lower = str(label or "").lower()
    if lower in {"positive", "bullish"}:
        return 0.75
    if lower in {"negative", "bearish"}:
        return 0.25
    if lower == "mixed":
        return 0.5
    return 0.5


def _lookup_handle_cache(handle: Optional[str]) -> Optional[Dict[str, Any]]:
    if not handle:
        return None
    handle = handle.lower().strip("@")
    cache = _load_json(XAI_TWITTER_CACHE_PATH)
    key = sha256(f"quick::{handle}".encode("utf-8")).hexdigest()
    entry = cache.get(key)
    if not entry:
        return None
    return entry.get("payload")


def _parse_handle_sentiment(payload: Dict[str, Any]) -> Optional[float]:
    text = str(payload.get("sentiment") or "")
    lowered = text.lower()
    if "very bullish" in lowered or "bullish" in lowered:
        return 0.7
    if "bearish" in lowered or "very bearish" in lowered:
        return 0.3
    if "neutral" in lowered:
        return 0.5
    return None


def _heuristic_score(
    *,
    base_score: float,
    momentum_score: Optional[float],
    liquidity_score: Optional[float],
    volume_score: Optional[float],
) -> float:
    momentum = _clamp(momentum_score if momentum_score is not None else base_score)
    liquidity = _clamp(liquidity_score if liquidity_score is not None else 0.5)
    volume = _clamp(volume_score if volume_score is not None else 0.5)

    score = (
        (base_score * 0.6)
        + (momentum * 0.2)
        + (liquidity * 0.1)
        + (volume * 0.1)
    )
    return _clamp(score)


class SentimentRegistry:
    def __init__(self) -> None:
        cfg = _config()
        self.enabled = cfg["enabled"]
        self.ttl_seconds = cfg["ttl_seconds"]
        self.cache_only = cfg["cache_only"]
        self.cache_path = Path(cfg["cache_path"])
        self.xai_weight = cfg["xai_weight"]
        self.heuristic_weight = cfg["heuristic_weight"]
        self._cache = _load_json(self.cache_path)

    def _get_cached(self, symbol: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(symbol)
        if not entry:
            return None
        timestamp = float(entry.get("timestamp", 0))
        if time.time() - timestamp > self.ttl_seconds:
            return None
        return entry

    def _set_cached(self, symbol: str, payload: Dict[str, Any]) -> None:
        self._cache[symbol] = payload
        _write_json(self.cache_path, self._cache)

    def score_candidate(
        self,
        *,
        symbol: str,
        base_score: float,
        text: Optional[str] = None,
        handle: Optional[str] = None,
        momentum_score: Optional[float] = None,
        liquidity_score: Optional[float] = None,
        volume_score: Optional[float] = None,
    ) -> Optional[SentimentRegistryResult]:
        if not self.enabled or not symbol:
            return None

        symbol = symbol.upper()
        cached = self._get_cached(symbol)
        if cached:
            return SentimentRegistryResult(
                symbol=symbol,
                score=float(cached.get("score", base_score)),
                sources=cached.get("sources", {}),
                timestamp=float(cached.get("timestamp", 0)),
            )

        sources: Dict[str, Any] = {"base_score": base_score}
        heuristic = _heuristic_score(
            base_score=base_score,
            momentum_score=momentum_score,
            liquidity_score=liquidity_score,
            volume_score=volume_score,
        )
        sources["heuristic_score"] = heuristic

        xai_score = None
        xai_conf = None
        if text:
            cached_payload = _lookup_grok_cache(text, focus="trading")
            if cached_payload:
                xai_score = _parse_sentiment_label(cached_payload.get("sentiment"))
                xai_conf = float(cached_payload.get("confidence", 0.0))
                sources["xai_cache"] = {
                    "score": xai_score,
                    "confidence": xai_conf,
                    "source": "grok_cache",
                }

        if xai_score is None and handle:
            handle_payload = _lookup_handle_cache(handle)
            if handle_payload:
                parsed = _parse_handle_sentiment(handle_payload)
                if parsed is not None:
                    xai_score = parsed
                    sources["xai_cache"] = {"score": xai_score, "source": "xai_twitter_cache"}

        if xai_score is not None:
            weighted = (
                (xai_score * self.xai_weight)
                + (heuristic * self.heuristic_weight)
            )
            final_score = _clamp(weighted)
        else:
            final_score = heuristic

        result = SentimentRegistryResult(
            symbol=symbol,
            score=final_score,
            sources=sources,
            timestamp=time.time(),
        )
        self._set_cached(symbol, result.to_dict())
        return result


_REGISTRY: Optional[SentimentRegistry] = None


def get_registry() -> SentimentRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SentimentRegistry()
    return _REGISTRY
