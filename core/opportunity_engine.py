"""Dual-market opportunity engine for crypto + Solana tokenized equities."""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from core import config as config_module
from core import fee_model, tokenized_equities_universe, event_catalyst
from core import sentiment_trading

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ENGINE_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "state_path": "data/trader/opportunity_state.json",
    "persist_state_on_start": True,
    "knowledge_base_path": "data/trader/trading_knowledge_base.json",
    "update_knowledge_base": True,
    "asset_classes": ["crypto", "tokenized_equities_solana"],
    "tokenized_equity_sources": ["xstocks.fi", "backed.fi", "prestocks.com"],
    "crypto_priority_weight": 1.0,
    "equities_priority_weight": 1.0,
    "max_equities_exposure_pct": 40.0,
    "min_edge_to_cost_ratio": 2.0,
    "min_edge_to_cost_ratio_high_vol": 3.0,
    "low_liquidity_usd": 50000.0,
    "low_volume_usd": 25000.0,
    "risk_off_mode_trigger": {
        "btc_volatility_pct": 6.0,
        "sol_volatility_pct": 8.0,
        "sentiment_floor": 0.2,
    },
    "signal_timeframe": "1h",
    "crypto_universe_path": "data/trader/crypto_universe.json",
    "tokenized_equities": {
        "cache_path": "data/trader/tokenized_equities_universe.json",
        "sources": [],
        "allow_network": False,
        "refresh_on_start": False,
    },
    "scoring_weights": {
        "sentiment": 0.35,
        "momentum": 0.20,
        "catalyst": 0.15,
        "liquidity": 0.15,
        "cost_efficiency": 0.15,
    },
    "cost_model": {
        "network_fee_usd": 0.0025,
        "dex_fee_bps": 30.0,
        "aggregator_fee_bps": 0.0,
        "platform_fee_bps": 0.0,
        "conversion_bps": 0.0,
        "spread_bps": 15.0,
        "slippage_bps": 30.0,
        "max_cost_pct": 0.03,
        "overrides": {
            "tokenized_equity": {
                "spread_bps": 40.0,
                "slippage_bps": 50.0,
                "platform_fee_bps": 5.0,
                "conversion_bps": 5.0,
            },
            "crypto_major": {
                "spread_bps": 8.0,
                "slippage_bps": 10.0,
            },
            "crypto_meme": {
                "spread_bps": 30.0,
                "slippage_bps": 80.0,
                "conversion_bps": 5.0,
            },
        },
    },
    "expected_edge_pct": {
        "min": 0.01,
        "max": 0.15,
    },
    "compliance": {
        "jurisdiction": "unknown",
        "kyc_required": "unknown",
        "eligible": "unknown",
    },
}

TICKER_RE = re.compile(r"(?:\\$|\\b)([A-Z][A-Z0-9]{1,7})\\b")
TICKER_BLOCKLIST = {"USD", "USDC", "USDT", "ETH", "BTC"}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def load_engine_config() -> Dict[str, Any]:
    config = config_module.load_config()
    engine_cfg = config.get("opportunity_engine", {})
    return _deep_merge(DEFAULT_ENGINE_CONFIG, engine_cfg)


def load_engine_state(engine_cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], Path]:
    state_path = config_module.resolve_path(
        engine_cfg.get("state_path", DEFAULT_ENGINE_CONFIG["state_path"])
    )
    defaults = {
        "asset_classes": list(engine_cfg.get("asset_classes", [])),
        "tokenized_equity_sources": list(engine_cfg.get("tokenized_equity_sources", [])),
        "equities_priority_weight": float(engine_cfg.get("equities_priority_weight", 1.0)),
        "crypto_priority_weight": float(engine_cfg.get("crypto_priority_weight", 1.0)),
    }
    state = _load_json(state_path)
    if not isinstance(state, dict):
        state = defaults
        if engine_cfg.get("persist_state_on_start", False):
            _write_json(state_path, state)
    else:
        state = _deep_merge(defaults, state)
    return state, state_path


def _update_knowledge_base(engine_cfg: Dict[str, Any], summary: Dict[str, Any]) -> Optional[Path]:
    if not engine_cfg.get("update_knowledge_base", False):
        return None
    path = config_module.resolve_path(
        engine_cfg.get("knowledge_base_path", DEFAULT_ENGINE_CONFIG["knowledge_base_path"])
    )
    data = _load_json(path)
    if not isinstance(data, dict):
        data = {"runs": []}
    runs = data.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(summary)
    data["runs"] = runs[-200:]
    _write_json(path, data)
    return path


def _normalize_equity_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "symbol": str(item.get("symbol") or item.get("ticker") or "").upper(),
        "underlying_ticker": str(item.get("underlying_ticker") or item.get("ticker") or "").upper(),
        "mint_address": item.get("mint_address") or item.get("mint") or "",
        "issuer": item.get("issuer") or item.get("platform") or "unknown",
        "venues": item.get("venues") or item.get("markets") or [],
        "liquidity_usd": float(item.get("liquidity_usd") or 0.0),
        "volume_24h_usd": float(item.get("volume_24h_usd") or 0.0),
        "verified": bool(item.get("verified")) if item.get("verified") is not None else False,
        "fees_bps": float(item.get("fees_bps") or 0.0),
        "spread_bps": float(item.get("spread_bps") or 0.0),
        "notes": item.get("notes") or "",
        "source": item.get("source") or "",
    }


def _parse_xstocks(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    items: List[Dict[str, Any]] = []
    match = re.search(r'__NEXT_DATA__\" type=\"application/json\">(.*?)</script>', text, re.DOTALL)
    if not match:
        return items, ["xstocks: __NEXT_DATA__ not found"]

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return items, [f"xstocks: failed to parse __NEXT_DATA__ ({exc})"]

    products = payload.get("props", {}).get("pageProps", {}).get("products", [])
    if not isinstance(products, list):
        return items, ["xstocks: products list missing"]

    for product in products:
        if not isinstance(product, dict):
            continue
        symbol = str(product.get("symbol") or "").upper()
        name = str(product.get("name") or "")
        addresses = product.get("addresses") or {}
        solana_address = addresses.get("solana")
        if not solana_address:
            continue
        underlying = symbol.rstrip("X").rstrip("x")
        items.append(
            {
                "symbol": symbol,
                "underlying_ticker": underlying,
                "mint_address": solana_address,
                "issuer": "xstocks",
                "venues": ["solana_dex"],
                "verified": True,
                "notes": name,
                "source": "https://xstocks.fi",
            }
        )

    if not items:
        warnings.append("xstocks: no solana addresses found")

    return items, warnings


def _fetch_xstocks() -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        resp = requests.get("https://xstocks.fi", timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], [f"xstocks: request failed ({exc})"]
    return _parse_xstocks(resp.text)


def _extract_equity_items(payload: Any, *, source: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            keys = {str(k).lower() for k in node.keys()}
            mint = node.get("mint") or node.get("mint_address") or node.get("solanaMint") or node.get("solana_address")
            symbol = node.get("symbol") or node.get("ticker")
            if mint and symbol:
                items.append(
                    {
                        "symbol": str(symbol).upper(),
                        "underlying_ticker": str(node.get("underlying") or symbol).upper(),
                        "mint_address": mint,
                        "issuer": source,
                        "venues": node.get("venues") or ["solana_dex"],
                        "verified": bool(node.get("verified")) if node.get("verified") is not None else False,
                        "notes": node.get("name") or node.get("description") or "",
                        "source": source,
                    }
                )
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(payload)
    return items


def _fetch_backed() -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        resp = requests.get("https://backed.fi", timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], [f"backed: request failed ({exc})"]

    text = resp.text
    match = re.search(r'__NEXT_DATA__\" type=\"application/json\">(.*?)</script>', text, re.DOTALL)
    if not match:
        return [], ["backed: __NEXT_DATA__ not found"]
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [], [f"backed: failed to parse __NEXT_DATA__ ({exc})"]

    items = _extract_equity_items(payload, source="backed")
    if not items:
        warnings.append("backed: no solana mints found")
    return items, warnings


def _fetch_prestocks() -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        resp = requests.get("https://prestocks.com", timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [], [f"prestocks: request failed ({exc})"]

    text = resp.text
    match = re.search(r'__NEXT_DATA__\" type=\"application/json\">(.*?)</script>', text, re.DOTALL)
    if not match:
        return [], ["prestocks: __NEXT_DATA__ not found"]
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [], [f"prestocks: failed to parse __NEXT_DATA__ ({exc})"]

    items = _extract_equity_items(payload, source="prestocks")
    if not items:
        warnings.append("prestocks: no solana mints found")
    return items, warnings


def _normalize_crypto_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "symbol": str(item.get("symbol") or item.get("ticker") or "").upper(),
        "mint_address": item.get("mint_address") or item.get("mint") or "",
        "category": item.get("category") or "crypto",
        "liquidity_usd": float(item.get("liquidity_usd") or 0.0),
        "volume_24h_usd": float(item.get("volume_24h_usd") or 0.0),
        "source": item.get("source") or "",
    }


def get_tokenized_equities_universe(
    engine_cfg: Dict[str, Any],
    *,
    refresh: bool = False,
) -> Dict[str, Any]:
    eq_cfg = engine_cfg.get("tokenized_equities", {})
    cache_path = config_module.resolve_path(
        eq_cfg.get("cache_path", DEFAULT_ENGINE_CONFIG["tokenized_equities"]["cache_path"])
    )
    items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    sources_used: List[str] = []

    cached = _load_json(cache_path)
    if isinstance(cached, dict):
        cached_items = cached.get("items")
        if isinstance(cached_items, list):
            items.extend(cached_items)
        sources_used.extend([str(s) for s in cached.get("sources", []) if s])
    elif isinstance(cached, list):
        items.extend(cached)

    sources = eq_cfg.get("sources") or engine_cfg.get("tokenized_equity_sources", [])
    if refresh and eq_cfg.get("allow_network") and sources:
        for source in sources:
            source_str = str(source)
            try:
                if "xstocks.fi" in source_str:
                    fetched, fetch_warnings = _fetch_xstocks()
                    items.extend(fetched)
                    warnings.extend(fetch_warnings)
                    sources_used.append("https://xstocks.fi")
                    continue
                if "backed.fi" in source_str:
                    fetched, fetch_warnings = _fetch_backed()
                    items.extend(fetched)
                    warnings.extend(fetch_warnings)
                    sources_used.append("https://backed.fi")
                    continue
                if "prestocks.com" in source_str:
                    fetched, fetch_warnings = _fetch_prestocks()
                    items.extend(fetched)
                    warnings.extend(fetch_warnings)
                    sources_used.append("https://prestocks.com")
                    continue

                if source_str.startswith(("http://", "https://")):
                    resp = requests.get(source_str, timeout=20)
                    resp.raise_for_status()
                    payload = resp.json()
                else:
                    payload = _load_json(Path(source_str))
                if payload is None:
                    warnings.append(f"equities source unreadable: {source_str}")
                    continue
                sources_used.append(source_str)
                if isinstance(payload, dict):
                    payload = payload.get("items") or payload.get("data") or payload.get("tokens") or []
                if isinstance(payload, list):
                    items.extend(payload)
            except requests.RequestException as exc:
                warnings.append(f"equities source failed: {source_str} ({exc})")

    normalized = [_normalize_equity_item(item) for item in items if isinstance(item, dict)]

    if not normalized:
        warnings.append("no tokenized equities loaded; provide sources or cache file")

    snapshot = {
        "items": normalized,
        "sources": sorted(set(sources_used)),
        "updated_at": time.time(),
        "warnings": warnings,
    }
    if refresh and eq_cfg.get("allow_network"):
        _write_json(cache_path, snapshot)

    return snapshot


def load_crypto_universe(engine_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = config_module.resolve_path(
        engine_cfg.get("crypto_universe_path", DEFAULT_ENGINE_CONFIG["crypto_universe_path"])
    )
    payload = _load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    if not isinstance(payload, list):
        payload = []
    normalized = [_normalize_crypto_item(item) for item in payload if isinstance(item, dict)]
    if not normalized:
        normalized = [
            {"symbol": "BTC", "category": "crypto_major", "liquidity_usd": 0.0, "volume_24h_usd": 0.0},
            {"symbol": "ETH", "category": "crypto_major", "liquidity_usd": 0.0, "volume_24h_usd": 0.0},
            {"symbol": "SOL", "category": "crypto_major", "liquidity_usd": 0.0, "volume_24h_usd": 0.0},
        ]
    return normalized


def _extract_tickers(signal: Dict[str, Any]) -> List[str]:
    tickers: List[str] = []
    provided = signal.get("tickers")
    if isinstance(provided, list):
        tickers.extend([str(t).upper() for t in provided if t])
    text = signal.get("text") or ""
    if isinstance(text, str) and text:
        tickers.extend([t for t in TICKER_RE.findall(text) if t not in TICKER_BLOCKLIST])
    return sorted(set(tickers))


def _signal_strength(signal: Dict[str, Any]) -> Tuple[float, float]:
    confidence = signal.get("confidence")
    sentiment_score = signal.get("sentiment_score")
    polarity = signal.get("polarity")
    if isinstance(confidence, (int, float)):
        conf = max(0.0, min(1.0, float(confidence)))
    else:
        conf = 0.5
    if isinstance(sentiment_score, (int, float)):
        sent = max(0.0, min(1.0, float(sentiment_score)))
    elif isinstance(polarity, (int, float)):
        sent = (float(polarity) + 1.0) / 2.0
        sent = max(0.0, min(1.0, sent))
    else:
        sent = conf
    return sent, conf


def map_sentiment_to_assets(
    signal: Dict[str, Any],
    crypto_universe: List[Dict[str, Any]],
    equities_universe: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tickers = _extract_tickers(signal)
    sentiment_score, confidence = _signal_strength(signal)
    mapped: List[Dict[str, Any]] = []

    for ticker in tickers:
        crypto_match = next((c for c in crypto_universe if c["symbol"] == ticker), None)
        equity_match = next((e for e in equities_universe if e["underlying_ticker"] == ticker), None)
        if crypto_match:
            mapped.append(
                {
                    "asset_type": "crypto",
                    "symbol": crypto_match["symbol"],
                    "mint_address": crypto_match.get("mint_address", ""),
                    "category": crypto_match.get("category", "crypto"),
                    "liquidity_usd": crypto_match.get("liquidity_usd", 0.0),
                    "volume_24h_usd": crypto_match.get("volume_24h_usd", 0.0),
                    "signal": signal,
                    "sentiment_score": sentiment_score,
                    "confidence": confidence,
                }
            )
        if equity_match:
            mapped.append(
                {
                    "asset_type": "tokenized_equity",
                    "symbol": equity_match.get("symbol") or ticker,
                    "underlying_ticker": equity_match.get("underlying_ticker") or ticker,
                    "mint_address": equity_match.get("mint_address", ""),
                    "issuer": equity_match.get("issuer", "unknown"),
                    "venues": equity_match.get("venues", []),
                    "liquidity_usd": equity_match.get("liquidity_usd", 0.0),
                    "volume_24h_usd": equity_match.get("volume_24h_usd", 0.0),
                    "verified": equity_match.get("verified", False),
                    "signal": signal,
                    "sentiment_score": sentiment_score,
                    "confidence": confidence,
                }
            )
    return mapped


def estimate_all_in_cost(
    asset: Dict[str, Any],
    *,
    size_usd: float,
    venue: str,
    cost_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    overrides = cost_cfg.get("overrides", {})
    asset_type = asset.get("asset_type")
    category = asset.get("category")
    override_key = asset_type if asset_type else category
    override = overrides.get(override_key, {})

    def _val(key: str) -> float:
        base = float(cost_cfg.get(key, 0.0))
        if key in override:
            return float(override[key])
        return base

    network_fee = float(cost_cfg.get("network_fee_usd", 0.0))
    dex_fee_bps = _val("dex_fee_bps")
    aggregator_fee_bps = _val("aggregator_fee_bps")
    platform_fee_bps = _val("platform_fee_bps")
    conversion_bps = _val("conversion_bps")
    spread_bps = asset.get("spread_bps") or _val("spread_bps")
    slippage_bps = _val("slippage_bps")
    asset_fee_bps = float(asset.get("fees_bps") or 0.0)

    total_bps = (
        dex_fee_bps
        + aggregator_fee_bps
        + platform_fee_bps
        + conversion_bps
        + spread_bps
        + slippage_bps
        + asset_fee_bps
    )
    total_pct = total_bps / 10000.0
    total_usd = (size_usd * total_pct) + network_fee

    return {
        "venue": venue,
        "size_usd": size_usd,
        "network_fee_usd": network_fee,
        "dex_fee_bps": dex_fee_bps,
        "aggregator_fee_bps": aggregator_fee_bps,
        "platform_fee_bps": platform_fee_bps,
        "conversion_bps": conversion_bps,
        "spread_bps": spread_bps,
        "slippage_bps": slippage_bps,
        "asset_fee_bps": asset_fee_bps,
        "total_bps": total_bps,
        "total_pct": total_pct,
        "total_usd": total_usd,
    }


def _score_liquidity(liquidity_usd: float, volume_usd: float) -> float:
    if liquidity_usd <= 0 and volume_usd <= 0:
        return 0.0
    liquidity_score = min(1.0, math.log10(max(liquidity_usd, 1.0)) / 6.0)
    volume_score = min(1.0, math.log10(max(volume_usd, 1.0)) / 6.0)
    return max(liquidity_score, volume_score)


def _score_cost_efficiency(cost_pct: float, max_cost_pct: float) -> float:
    if max_cost_pct <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (cost_pct / max_cost_pct)))


def _estimate_expected_edge(
    signal: Dict[str, Any],
    engine_cfg: Dict[str, Any],
) -> Tuple[Optional[float], Optional[str]]:
    expected = signal.get("expected_edge_pct")
    if isinstance(expected, (int, float)):
        return float(expected), None
    conf = signal.get("confidence")
    if not isinstance(conf, (int, float)):
        return None, "expected edge unknown"
    conf = max(0.0, min(1.0, float(conf)))
    min_edge = engine_cfg.get("expected_edge_pct", {}).get("min", 0.01)
    max_edge = engine_cfg.get("expected_edge_pct", {}).get("max", 0.15)
    estimate = min_edge + (max_edge - min_edge) * conf
    return estimate, "heuristic_from_confidence"


def _required_edge_ratio(
    candidate: Dict[str, Any],
    liquidity_score: float,
    engine_cfg: Dict[str, Any],
) -> float:
    base = float(engine_cfg.get("min_edge_to_cost_ratio", 2.0))
    high = float(engine_cfg.get("min_edge_to_cost_ratio_high_vol", 3.0))
    low_liquidity = candidate.get("liquidity_usd", 0.0) < float(
        engine_cfg.get("low_liquidity_usd", 0.0)
    )
    low_volume = candidate.get("volume_24h_usd", 0.0) < float(
        engine_cfg.get("low_volume_usd", 0.0)
    )
    if liquidity_score < 0.35 or low_liquidity or low_volume:
        return max(base, high)
    return base


def _probabilistic_scores(
    *,
    sentiment_score: float,
    confidence: float,
    liquidity_score: float,
    expected_edge_pct: float,
    cost_pct: float,
    engine_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    prob_win = min(0.85, max(0.05, (sentiment_score * 0.45) + (confidence * 0.25) + (liquidity_score * 0.30)))
    expected_return = expected_edge_pct - cost_pct
    expected_drawdown = float(engine_cfg.get("risk_off_mode_trigger", {}).get("sol_volatility_pct", 8.0)) / 100
    edge_to_cost = expected_edge_pct / cost_pct if cost_pct else None
    timeframe = engine_cfg.get("signal_timeframe", "1h")
    uncertainty = max(0.0, min(1.0, 1.0 - ((confidence * 0.6) + (liquidity_score * 0.4))))
    return {
        "prob_win": prob_win,
        "expected_return_pct": expected_return,
        "expected_drawdown_pct": expected_drawdown,
        "edge_to_cost_ratio": edge_to_cost,
        "time_to_resolution": timeframe,
        "uncertainty": uncertainty,
    }


def _load_backtest_summary() -> Optional[Dict[str, Any]]:
    path = ROOT / "data" / "trader" / "solana_dex_one_day" / "summary.json"
    summary = _load_json(path)
    if isinstance(summary, dict):
        return summary
    return None


def _build_execution_plan(asset: Dict[str, Any]) -> Dict[str, Any]:
    if asset.get("asset_type") == "tokenized_equity":
        return {
            "order_type": "limit",
            "execution_style": "split",
            "notes": "Prefer limit orders and split sizing for thin liquidity.",
        }
    return {
        "order_type": "market",
        "execution_style": "single",
        "notes": "Use slippage guardrails and avoid thin liquidity spikes.",
    }


def run_engine(
    *,
    signals_path: Optional[Path] = None,
    refresh_equities: bool = False,
    capital_usd: float = 20.0,
) -> Dict[str, Any]:
    engine_cfg = load_engine_config()
    state, state_path = load_engine_state(engine_cfg)
    equities_snapshot = tokenized_equities_universe.load_universe()
    if refresh_equities:
        equities_snapshot = tokenized_equities_universe.refresh_universe()
    equities_universe = equities_snapshot.get("items", [])
    crypto_universe = load_crypto_universe(engine_cfg)

    if signals_path:
        raw_signals = _load_json(signals_path)
        if isinstance(raw_signals, dict):
            raw_signals = raw_signals.get("signals", [])
        if not isinstance(raw_signals, list):
            raw_signals = []
    else:
        raw_signals = [s.to_dict() for s in sentiment_trading.load_recent_signals()]

    catalyst_scores: Dict[str, float] = {}
    catalyst_horizons: Dict[str, str] = {}
    for signal in raw_signals:
        text = signal.get("text") if isinstance(signal, dict) else None
        if not text:
            continue
        events = event_catalyst.extract_events(text)
        if not events:
            continue
        mapped = event_catalyst.map_events_to_universe(events, equities_universe)
        for entry in mapped:
            asset = entry.get("asset", {})
            symbol = str(asset.get("symbol") or asset.get("underlying_ticker") or "").upper()
            if not symbol:
                continue
            catalyst_scores[symbol] = max(catalyst_scores.get(symbol, 0.0), float(entry.get("catalyst_score", 0.7)))
            catalyst_horizons[symbol] = entry.get("horizon", "hours")

    candidates: List[Dict[str, Any]] = []
    for signal in raw_signals:
        if not isinstance(signal, dict):
            continue
        candidates.extend(map_sentiment_to_assets(signal, crypto_universe, equities_universe))

    scoring_weights = engine_cfg.get("scoring_weights", {})
    cost_cfg = engine_cfg.get("cost_model", {})
    compliance = engine_cfg.get("compliance", {})
    max_cost_pct = float(cost_cfg.get("max_cost_pct", 0.03))
    analysis_complete = True
    blocking_issues: List[str] = []

    if not equities_universe:
        analysis_complete = False
        blocking_issues.append("tokenized_equities_universe_empty")

    ranked: List[Dict[str, Any]] = []
    rejections: List[Dict[str, Any]] = []

    for candidate in candidates:
        signal = candidate.get("signal", {})
        sentiment_score, confidence = _signal_strength(signal)
        momentum_score = float(signal.get("momentum_score", sentiment_score))
        candidate_symbol = str(candidate.get("symbol") or "").upper()
        catalyst_score = float(signal.get("catalyst_score", 0.0))
        if candidate_symbol in catalyst_scores:
            catalyst_score = max(catalyst_score, catalyst_scores[candidate_symbol])
        liquidity_score = _score_liquidity(
            candidate.get("liquidity_usd", 0.0), candidate.get("volume_24h_usd", 0.0)
        )

        cost = fee_model.estimate_costs(
            notional_usd=capital_usd,
            asset_type="tokenized_equity" if candidate.get("asset_type") == "tokenized_equity" else "crypto",
            issuer=candidate.get("issuer", ""),
        )
        cost_efficiency = _score_cost_efficiency(cost["total_pct"], max_cost_pct)
        expected_edge_pct, edge_note = _estimate_expected_edge(signal, engine_cfg)

        if expected_edge_pct is None:
            rejections.append(
                {
                    "candidate": candidate,
                    "reason": "missing_expected_edge",
                    "note": edge_note,
                }
            )
            continue

        edge_to_cost = expected_edge_pct / cost["total_pct"] if cost["total_pct"] > 0 else None
        required_ratio = _required_edge_ratio(candidate, liquidity_score, engine_cfg)
        if edge_to_cost is None or edge_to_cost < required_ratio:
            rejections.append(
                {
                    "candidate": candidate,
                    "reason": "edge_to_cost_below_min",
                    "edge_to_cost_ratio": edge_to_cost,
                    "expected_edge_pct": expected_edge_pct,
                    "cost_pct": cost["total_pct"],
                    "required_ratio": required_ratio,
                }
            )
            continue

        score = (
            sentiment_score * scoring_weights.get("sentiment", 0.0)
            + momentum_score * scoring_weights.get("momentum", 0.0)
            + catalyst_score * scoring_weights.get("catalyst", 0.0)
            + liquidity_score * scoring_weights.get("liquidity", 0.0)
            + cost_efficiency * scoring_weights.get("cost_efficiency", 0.0)
        )
        weight = float(
            state.get(
                "equities_priority_weight" if candidate.get("asset_type") == "tokenized_equity" else "crypto_priority_weight",
                1.0,
            )
        )
        score *= weight

        probabilistic = _probabilistic_scores(
            sentiment_score=sentiment_score,
            confidence=confidence,
            liquidity_score=liquidity_score,
            expected_edge_pct=expected_edge_pct,
            cost_pct=cost["total_pct"],
            engine_cfg=engine_cfg,
        )
        if candidate_symbol in catalyst_horizons:
            probabilistic["time_to_resolution"] = catalyst_horizons[candidate_symbol]

        ranked.append(
            {
                "asset_type": candidate.get("asset_type"),
                "symbol": candidate.get("symbol"),
                "underlying_ticker": candidate.get("underlying_ticker"),
                "mint_address": candidate.get("mint_address"),
                "issuer": candidate.get("issuer"),
                "venues": candidate.get("venues", []),
                "scores": {
                    "opportunity": score,
                    "sentiment": sentiment_score,
                    "momentum": momentum_score,
                    "catalyst": catalyst_score,
                    "liquidity": liquidity_score,
                    "cost_efficiency": cost_efficiency,
                },
                "costs": cost,
                "expected_edge_pct": expected_edge_pct,
                "edge_to_cost_ratio": edge_to_cost,
                "probabilistic": probabilistic,
                "signal": signal,
            }
        )

    ranked.sort(key=lambda item: item["scores"]["opportunity"], reverse=True)

    crypto_candidates = [c for c in ranked if c.get("asset_type") == "crypto"]
    equity_candidates = [c for c in ranked if c.get("asset_type") == "tokenized_equity"]

    trade_intents: List[Dict[str, Any]] = []
    execution_plans: List[Dict[str, Any]] = []
    cost_models: List[Dict[str, Any]] = []

    for item in ranked:
        tradable = True
        compliance_status = compliance.copy()
        if item.get("asset_type") == "tokenized_equity":
            if not item.get("issuer") or item.get("issuer") == "unknown":
                tradable = False
            if not item.get("mint_address"):
                tradable = False
            if not item.get("underlying_ticker"):
                tradable = False
        if compliance_status.get("eligible") in ("unknown", False):
            tradable = False
        if not analysis_complete:
            tradable = False

        trade_intent = {
            "symbol": item.get("symbol"),
            "asset_type": item.get("asset_type"),
            "tradable": tradable,
            "entry": {
                "price": None,
                "order_type": "limit" if item.get("asset_type") == "tokenized_equity" else "market",
                "notes": "price_required",
            },
            "exit": {
                "take_profit_pct": item["signal"].get("take_profit_pct"),
                "stop_loss_pct": item["signal"].get("stop_loss_pct"),
                "notes": "configure in execution layer",
            },
            "edge_to_cost_ratio": item.get("edge_to_cost_ratio"),
            "liquidity_exit_risk": item["scores"].get("liquidity", 0.0) < 0.35,
            "compliance_unknown": compliance_status.get("eligible") in ("unknown", False),
            "risk_notes": item["signal"].get("risk_notes", []),
        }
        trade_intents.append(trade_intent)
        execution_plans.append(_build_execution_plan(item))
        cost_models.append(item["costs"])

    if not analysis_complete:
        trade_intents = []
        execution_plans = []
        cost_models = []

    validation_summary = _load_backtest_summary()
    knowledge_path = _update_knowledge_base(
        engine_cfg,
        {
            "timestamp": time.time(),
            "analysis_complete": analysis_complete,
            "ranked_count": len(ranked),
            "crypto_candidates": len(crypto_candidates),
            "equity_candidates": len(equity_candidates),
            "blocking_issues": blocking_issues,
        },
    )

    catalysts: List[Dict[str, Any]] = []
    for signal in raw_signals:
        text = signal.get("text") if isinstance(signal, dict) else None
        if not text:
            continue
        events = event_catalyst.extract_events(text)
        if not events:
            continue
        catalysts.extend(event_catalyst.map_events_to_universe(events, equities_universe))

    unified_ranked = ranked

    return {
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": {
            "config": engine_cfg,
            "state": state,
            "state_path": str(state_path),
            "capital_usd": capital_usd,
        },
        "analysis_complete": analysis_complete,
        "blocking_reasons": blocking_issues,
        "universe": {
            "crypto": crypto_universe,
            "tokenized_equities": equities_snapshot,
        },
        "signals": raw_signals,
        "candidates": {
            "crypto": crypto_candidates,
            "tokenized_equities": equity_candidates,
        },
        "ranked": ranked,
        "unified_ranked": unified_ranked,
        "trade_intents": trade_intents,
        "execution_plans": execution_plans,
        "cost_models": cost_models,
        "catalysts": catalysts,
        "validation_summary": validation_summary,
        "risk_model": {
            "max_equities_exposure_pct": engine_cfg.get("max_equities_exposure_pct"),
            "min_edge_to_cost_ratio": engine_cfg.get("min_edge_to_cost_ratio"),
            "min_edge_to_cost_ratio_high_vol": engine_cfg.get("min_edge_to_cost_ratio_high_vol"),
            "compliance": compliance,
        },
        "post_trade": {
            "tracking": "core/risk_manager.py trade journal",
            "notes": "Log entries to trades.json with cost/edge annotations.",
        },
        "knowledge_base_path": str(knowledge_path) if knowledge_path else None,
        "rejections": rejections,
    }


if __name__ == "__main__":
    output = run_engine()
    print(json.dumps(output, indent=2))
