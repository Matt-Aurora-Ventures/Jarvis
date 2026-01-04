"""Audit suite runner for LifeOS trading + routing."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from core import (
    config,
    position_reconciler,
    solana_execution,
    solana_wallet,
    x_sentiment,
    tokenized_equities_universe,
    fee_model,
    event_catalyst,
)

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "data" / "trader" / "audit_reports"


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def rpc_health_check() -> Dict[str, Any]:
    endpoints = solana_execution.load_solana_rpc_endpoints()
    healthy = _run_async(solana_execution.get_healthy_endpoints(endpoints))
    return {
        "endpoints": [e.url for e in endpoints],
        "healthy": [e.url for e in healthy],
        "ok": len(healthy) > 0,
    }


def jupiter_quote_test() -> Dict[str, Any]:
    quote = _run_async(
        solana_execution.get_swap_quote(
            solana_execution.SOL_MINT,
            solana_execution.USDC_MINT,
            1000000,
            slippage_bps=100,
        )
    )
    return {"ok": bool(quote), "quote": quote}


def swap_simulation_test() -> Dict[str, Any]:
    if not solana_execution.HAS_SOLANA or not solana_execution.HAS_AIOHTTP:
        return {"ok": False, "error": "dependencies_missing"}
    keypair = solana_wallet.load_keypair()
    if not keypair:
        return {"ok": False, "error": "missing_keypair"}

    quote = _run_async(
        solana_execution.get_swap_quote(
            solana_execution.SOL_MINT,
            solana_execution.USDC_MINT,
            1000000,
            slippage_bps=100,
        )
    )
    if not quote:
        return {"ok": False, "error": "quote_failed"}
    swap_tx = _run_async(solana_execution.get_swap_transaction(quote, str(keypair.pubkey())))
    if not swap_tx:
        return {"ok": False, "error": "swap_tx_failed"}
    import base64

    tx = solana_execution.VersionedTransaction.from_bytes(base64.b64decode(swap_tx))
    signed = solana_execution.VersionedTransaction(tx.message, [keypair])
    endpoints = solana_execution.load_solana_rpc_endpoints()
    result = _run_async(solana_execution.simulate_transaction(signed, endpoints))
    return {"ok": result.success, "error": result.error, "endpoint": result.endpoint}


def grok_cache_test() -> Dict[str, Any]:
    before = _read_usage()
    text = "SOL sentiment test for cache"
    _ = x_sentiment.analyze_sentiment(text, focus="trading")
    mid = _read_usage()
    _ = x_sentiment.analyze_sentiment(text, focus="trading")
    after = _read_usage()
    return {
        "ok": True,
        "usage_before": before,
        "usage_after_first": mid,
        "usage_after_second": after,
    }


def tokenized_equities_ingestion_test() -> Dict[str, Any]:
    snapshot = tokenized_equities_universe.refresh_universe()
    ok, issues = tokenized_equities_universe.validate_universe(snapshot)
    items = snapshot.get("items", [])
    return {
        "ok": ok,
        "count": len(items),
        "issues": issues,
        "warnings": snapshot.get("warnings", []),
    }


def fee_model_test() -> Dict[str, Any]:
    crypto = fee_model.estimate_costs(notional_usd=20.0, asset_type="crypto")
    equity = fee_model.estimate_costs(notional_usd=20.0, asset_type="tokenized_equity", issuer="prestocks")
    return {
        "ok": crypto["total_pct"] > 0 and equity["total_pct"] > 0,
        "crypto": crypto,
        "equity": equity,
    }


def event_catalyst_test() -> Dict[str, Any]:
    text = "OpenAI earnings launch next week should move markets"
    events = event_catalyst.extract_events(text)
    snapshot = tokenized_equities_universe.load_universe()
    mapped = event_catalyst.map_events_to_universe(events, snapshot.get("items", []))
    return {"ok": bool(events), "events": [e.to_dict() for e in events], "mapped": mapped}


def router_status() -> Dict[str, Any]:
    cfg = config.load_config()
    return {
        "router": cfg.get("router", {}),
        "providers": cfg.get("providers", {}),
    }


def reconcile_check() -> Dict[str, Any]:
    report = position_reconciler.reconcile_positions(auto_create_intents=False)
    return {"ok": True, "report": report}


def _read_usage() -> Dict[str, Any]:
    path = x_sentiment.USAGE_PATH if hasattr(x_sentiment, "USAGE_PATH") else ROOT / "data" / "trader" / "grok_usage.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def run_all() -> Dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.time(),
        "rpc_health": rpc_health_check(),
        "jupiter_quote": jupiter_quote_test(),
        "swap_simulation": swap_simulation_test(),
        "grok_cache": grok_cache_test(),
        "tokenized_equities_ingestion": tokenized_equities_ingestion_test(),
        "fee_model": fee_model_test(),
        "event_catalyst": event_catalyst_test(),
        "router": router_status(),
        "reconcile": reconcile_check(),
    }
    out_path = AUDIT_DIR / f"audit_{int(time.time())}.json"
    out_path.write_text(json.dumps(report, indent=2))
    report["report_path"] = str(out_path)
    return report
