"""Simulate Jupiter swap execution for an exit intent."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import exit_intents, solana_execution, solana_tokens, solana_wallet

try:
    from solana.rpc.async_api import AsyncClient
    from solders.transaction import VersionedTransaction
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    AsyncClient = None
    VersionedTransaction = None

REPORT_DIR = Path.home() / ".lifeos" / "trading" / "sim_reports"


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _find_intent(intent_id: Optional[str], symbol: Optional[str]) -> Optional[exit_intents.ExitIntent]:
    intents = exit_intents.load_active_intents()
    if intent_id:
        for intent in intents:
            if intent.id == intent_id:
                return intent
        return None
    if symbol:
        for intent in intents:
            if intent.symbol.upper() == symbol.upper():
                return intent
    return None


async def _simulate_swap(
    intent: exit_intents.ExitIntent,
    amount_base_units: int,
    endpoints: List[solana_execution.RpcEndpoint],
    *,
    endpoint_name: Optional[str] = None,
) -> Dict[str, Any]:
    keypair = solana_wallet.load_keypair()
    if not keypair:
        return {"error": "missing_keypair"}
    if not HAS_SOLANA or VersionedTransaction is None or AsyncClient is None:
        return {"error": "solana_sdk_missing"}

    quote = await solana_execution.get_swap_quote(
        intent.token_mint,
        solana_execution.USDC_MINT,
        amount_base_units,
        slippage_bps=200,
    )
    if not quote:
        return {"error": "quote_failed"}

    swap_tx = await solana_execution.get_swap_transaction(quote, str(keypair.pubkey()))
    if not swap_tx:
        return {"error": "swap_tx_failed"}

    signed = VersionedTransaction.from_bytes(__import__("base64").b64decode(swap_tx))
    signed_tx = VersionedTransaction(signed.message, [keypair])

    target_endpoints = endpoints
    if endpoint_name:
        target_endpoints = [e for e in endpoints if e.name == endpoint_name]
        if not target_endpoints:
            return {"error": f"endpoint_not_found:{endpoint_name}"}

    results = []
    for endpoint in target_endpoints:
        try:
            async with AsyncClient(endpoint.url) as client:
                sim = await client.simulate_transaction(signed_tx)
                sim_err = None
                logs = []
                if sim.value:
                    sim_err = sim.value.err
                    logs = sim.value.logs or []
                error = None
                if sim_err:
                    error = str(sim_err)
                results.append(
                    {
                        "endpoint": endpoint.name,
                        "success": sim_err is None,
                        "error": error,
                        "error_hint": solana_execution.describe_simulation_error(error) if error else None,
                        "error_class": solana_execution.classify_simulation_error(error) if error else None,
                        "logs": logs,
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "endpoint": endpoint.name,
                    "success": False,
                    "error": str(exc),
                    "error_hint": solana_execution.describe_simulation_error(str(exc)),
                    "error_class": solana_execution.classify_simulation_error(str(exc)),
                    "logs": [],
                }
            )

    return {
        "quote": quote,
        "results": results,
    }


def simulate_exit_intent(
    *,
    intent_id: Optional[str] = None,
    symbol: Optional[str] = None,
    size_pct: float = 100.0,
    endpoint: Optional[str] = None,
    write_report: bool = True,
) -> Dict[str, Any]:
    intent = _find_intent(intent_id, symbol)
    if not intent:
        return {"error": "intent_not_found"}

    decimals = solana_tokens.get_token_decimals(intent.token_mint, fallback=9)
    quantity = intent.remaining_quantity * (size_pct / 100.0)
    amount_base_units = int(quantity * (10**decimals))
    endpoints = solana_execution.load_solana_rpc_endpoints()

    payload = {
        "timestamp": time.time(),
        "intent_id": intent.id,
        "symbol": intent.symbol,
        "token_mint": intent.token_mint,
        "remaining_quantity": intent.remaining_quantity,
        "size_pct": size_pct,
        "decimals": decimals,
        "amount_base_units": amount_base_units,
        "endpoint": endpoint,
    }

    result = _run_async(
        _simulate_swap(
            intent,
            amount_base_units,
            endpoints,
            endpoint_name=endpoint,
        )
    )
    payload.update(result)

    if write_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"sim_exit_{intent.id}_{int(time.time())}.json"
        report_path.write_text(json.dumps(payload, indent=2))
        payload["report_path"] = str(report_path)

    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Simulate a Jupiter exit swap for an intent.")
    parser.add_argument("--intent-id", type=str, help="Exit intent id")
    parser.add_argument("--symbol", type=str, help="Symbol (fallback if no intent id)")
    parser.add_argument("--size-pct", type=float, default=100.0, help="Percent of remaining qty to simulate")
    parser.add_argument("--endpoint", type=str, help="RPC endpoint name to target")
    parser.add_argument("--no-report", action="store_true", help="Skip report file")
    args = parser.parse_args()

    payload = simulate_exit_intent(
        intent_id=args.intent_id,
        symbol=args.symbol,
        size_pct=args.size_pct,
        endpoint=args.endpoint,
        write_report=not args.no_report,
    )
    print(json.dumps(payload, indent=2))
