"""Reconcile on-chain balances with local exit intents."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, dexscreener, exit_intents, solana_execution, solana_wallet

try:
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    AsyncClient = None

RECONCILE_REPORT = Path.home() / ".lifeos" / "trading" / "reconcile_report.json"


def _load_symbol_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def _fetch_price_usd(mint: str) -> Optional[float]:
    payload = dexscreener.fetch_token_pairs(mint, cache_ttl_seconds=20)
    if not payload:
        return None
    pairs = payload.get("pairs", []) or []
    if not pairs:
        return None
    best = max(
        pairs,
        key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0.0),
    )
    try:
        return float(best.get("priceUsd"))
    except (TypeError, ValueError):
        return None


async def _load_balances(owner: str, endpoints: List[solana_execution.RpcEndpoint]) -> Dict[str, float]:
    balances: Dict[str, float] = {}
    if not HAS_SOLANA:
        return balances
    for endpoint in endpoints:
        try:
            async with AsyncClient(endpoint.url) as client:
                resp = await client.get_token_accounts_by_owner(owner, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"})
                if not resp.value:
                    continue
                for item in resp.value:
                    info = item.account.data.parsed["info"]
                    mint = info["mint"]
                    amount = float(info["tokenAmount"]["uiAmount"] or 0.0)
                    if amount > 0:
                        balances[mint] = balances.get(mint, 0.0) + amount
                return balances
        except Exception:
            continue
    return balances


def reconcile_positions(*, auto_create_intents: bool = False) -> Dict[str, Any]:
    """Compare on-chain balances to exit intents and optionally create missing intents."""
    report: Dict[str, Any] = {
        "timestamp": time.time(),
        "auto_create_intents": auto_create_intents,
        "balances": {},
        "missing_intents": [],
        "created_intents": [],
        "notes": [],
    }

    if not HAS_SOLANA:
        report["notes"].append("solana_sdk_missing")
        _write_report(report)
        return report

    keypair = solana_wallet.load_keypair()
    if not keypair:
        report["notes"].append("missing_keypair")
        _write_report(report)
        return report

    cfg = config.load_config()
    daemon_cfg = cfg.get("trading_daemon", {})
    symbol_map_path = Path(daemon_cfg.get("symbol_map_path", Path.home() / ".lifeos" / "trading" / "symbol_map.json"))
    symbol_map = _load_symbol_map(symbol_map_path)
    endpoints = solana_execution.load_solana_rpc_endpoints()

    balances = _run_async(_load_balances(str(keypair.pubkey()), endpoints))
    report["balances"] = balances

    intents = exit_intents.load_active_intents()
    active_mints = {intent.token_mint for intent in intents}

    for symbol, mint in symbol_map.items():
        amount = balances.get(mint, 0.0)
        if amount <= 0:
            continue
        if mint in active_mints:
            continue
        price = _fetch_price_usd(mint) or 0.0
        report["missing_intents"].append(
            {"symbol": symbol, "mint": mint, "balance": amount, "price_usd": price}
        )
        if auto_create_intents and price > 0:
            intent = exit_intents.create_spot_intent(
                position_id=f"reconcile-{mint[:6]}-{int(time.time())}",
                token_mint=mint,
                symbol=symbol,
                entry_price=price,
                quantity=amount,
                is_paper=False,
            )
            intent.notes = "reconciled_from_chain"
            exit_intents.persist_intent(intent)
            report["created_intents"].append(intent.to_dict())

    _write_report(report)
    return report


def _write_report(report: Dict[str, Any]) -> None:
    RECONCILE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    RECONCILE_REPORT.write_text(json.dumps(report, indent=2))


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()
