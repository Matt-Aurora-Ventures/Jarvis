"""RPC diagnostics helpers for Solana endpoints."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from core import solana_execution, solana_wallet

try:
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    AsyncClient = None

try:
    import aiohttp
    HAS_AIOHTTP = True
except Exception:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    from solders.system_program import transfer, TransferParams
    from solders.transaction import Transaction
    HAS_SOLDERS = True
except Exception:
    HAS_SOLDERS = False
    transfer = None
    TransferParams = None
    Transaction = None


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _build_probe_tx(keypair, blockhash) -> Optional["Transaction"]:
    if not HAS_SOLDERS or not keypair:
        return None
    try:
        ix = transfer(
            TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=keypair.pubkey(),
                lamports=1,
            )
        )
        return Transaction.new_signed_with_payer(
            [ix],
            keypair.pubkey(),
            [keypair],
            blockhash,
        )
    except Exception:
        return None


async def _probe_endpoint(
    endpoint: solana_execution.RpcEndpoint,
    *,
    keypair=None,
    include_simulation: bool = True,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "name": endpoint.name,
        "url": endpoint.url,
        "timeout_ms": endpoint.timeout_ms,
    }

    if not HAS_SOLANA or AsyncClient is None:
        result["error"] = "solana_sdk_missing"
        return result

    timeout_seconds = endpoint.timeout_ms / 1000
    async with AsyncClient(endpoint.url, timeout=timeout_seconds) as client:
        # Health
        start = time.perf_counter()
        if HAS_AIOHTTP:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(endpoint.url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            result["health_ok"] = data.get("result") == "ok"
                        else:
                            result["health_ok"] = False
                            result["health_error"] = f"http_{resp.status}"
            except Exception as exc:
                result["health_ok"] = False
                result["health_error"] = str(exc) or repr(exc)
        else:
            result["health_ok"] = None
            result["health_error"] = "aiohttp_missing"
        result["health_ms"] = round((time.perf_counter() - start) * 1000, 2)

        # Latest blockhash
        blockhash = None
        start = time.perf_counter()
        try:
            resp = await client.get_latest_blockhash()
            if resp and resp.value:
                blockhash = resp.value.blockhash
                result["blockhash"] = str(blockhash)
                result["last_valid_block_height"] = resp.value.last_valid_block_height
        except Exception as exc:
            result["blockhash_error"] = str(exc) or repr(exc)
        result["blockhash_ms"] = round((time.perf_counter() - start) * 1000, 2)

        # Simulation
        if include_simulation and keypair and blockhash:
            start = time.perf_counter()
            tx = _build_probe_tx(keypair, blockhash)
            if tx is None:
                result["simulate_ok"] = None
                result["simulate_error"] = "simulation_unavailable"
            else:
                try:
                    sim = await client.simulate_transaction(tx)
                    if sim.value and sim.value.err:
                        result["simulate_ok"] = False
                        result["simulate_error"] = str(sim.value.err)
                        result["simulate_hint"] = solana_execution.describe_simulation_error(
                            result["simulate_error"]
                        )
                    else:
                        result["simulate_ok"] = True
                except Exception as exc:
                    result["simulate_ok"] = False
                    result["simulate_error"] = str(exc) or repr(exc)
            result["simulate_ms"] = round((time.perf_counter() - start) * 1000, 2)
        else:
            result["simulate_ok"] = None
            if not include_simulation:
                result["simulate_error"] = "skipped"
            elif not keypair:
                result["simulate_error"] = "missing_keypair"
            else:
                result["simulate_error"] = "missing_blockhash"

    return result


def run_solana_rpc_diagnostics(*, include_simulation: bool = True) -> Dict[str, Any]:
    endpoints = solana_execution.load_solana_rpc_endpoints()
    keypair = solana_wallet.load_keypair()

    async def _run():
        tasks = [
            _probe_endpoint(
                endpoint,
                keypair=keypair,
                include_simulation=include_simulation,
            )
            for endpoint in endpoints
        ]
        return await asyncio.gather(*tasks)

    results = _run_async(_run())
    return {
        "timestamp": time.time(),
        "include_simulation": include_simulation,
        "keypair_loaded": bool(keypair),
        "endpoints": results,
    }


if __name__ == "__main__":
    payload = run_solana_rpc_diagnostics(include_simulation=True)
    import json

    print(json.dumps(payload, indent=2))
