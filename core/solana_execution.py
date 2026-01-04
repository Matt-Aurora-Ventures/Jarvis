"""Reliable Solana execution helpers with RPC failover and confirmation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import aiohttp
    HAS_AIOHTTP = True
except Exception:
    HAS_AIOHTTP = False

try:
    from solders.transaction import VersionedTransaction
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.types import TxOpts
    HAS_SOLANA = True
except Exception:
    HAS_SOLANA = False
    VersionedTransaction = None
    AsyncClient = None
    TxOpts = None

ROOT = Path(__file__).resolve().parents[1]
RPC_CONFIG = ROOT / "config" / "rpc_providers.json"

JUPITER_QUOTE_API = "https://public.jupiterapi.com/quote"
JUPITER_SWAP_API = "https://public.jupiterapi.com/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@dataclass
class RpcEndpoint:
    name: str
    url: str
    timeout_ms: int = 30000


@dataclass
class SwapExecutionResult:
    success: bool
    signature: Optional[str] = None
    error: Optional[str] = None
    endpoint: Optional[str] = None
    simulation_error: Optional[str] = None


def _substitute_env(value: str) -> Optional[str]:
    if "${" not in value:
        return value
    start = value.find("${")
    end = value.find("}", start + 2)
    if start == -1 or end == -1:
        return value
    env_name = value[start + 2 : end]
    env_value = os.environ.get(env_name)
    if not env_value:
        return None
    return value.replace(f"${{{env_name}}}", env_value)


def load_solana_rpc_endpoints() -> List[RpcEndpoint]:
    if not RPC_CONFIG.exists():
        return [RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com")]

    try:
        payload = json.loads(RPC_CONFIG.read_text())
    except Exception:
        return [RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com")]

    solana_cfg = payload.get("solana", {})
    endpoints: List[RpcEndpoint] = []

    primary = solana_cfg.get("primary", {}) or {}
    if primary.get("url"):
        url = _substitute_env(primary["url"])
        if url:
            endpoints.append(
                RpcEndpoint(
                    name=str(primary.get("name", "primary")),
                    url=url,
                    timeout_ms=int(primary.get("timeout_ms", 30000)),
                )
            )

    for fallback in solana_cfg.get("fallback", []) or []:
        url = _substitute_env(str(fallback.get("url", "")))
        if not url:
            continue
        endpoints.append(
            RpcEndpoint(
                name=str(fallback.get("name", "fallback")),
                url=url,
                timeout_ms=int(fallback.get("timeout_ms", 30000)),
            )
        )

    if not endpoints:
        endpoints.append(RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com"))
    return endpoints


async def _rpc_health(endpoint: RpcEndpoint) -> bool:
    if not HAS_AIOHTTP:
        return True
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
    timeout = aiohttp.ClientTimeout(total=endpoint.timeout_ms / 1000)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint.url, json=payload) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                return data.get("result") == "ok"
    except Exception:
        return False


async def get_healthy_endpoints(endpoints: Iterable[RpcEndpoint]) -> List[RpcEndpoint]:
    healthy: List[RpcEndpoint] = []
    for endpoint in endpoints:
        if await _rpc_health(endpoint):
            healthy.append(endpoint)
    return healthy or list(endpoints)


async def get_swap_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    *,
    slippage_bps: int = 100,
) -> Optional[Dict[str, Any]]:
    if not HAS_AIOHTTP:
        return None
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": slippage_bps,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(JUPITER_QUOTE_API, params=params) as resp:
            if resp.status != 200:
                return None
            return await resp.json()


async def get_swap_transaction(
    quote: Dict[str, Any],
    user_public_key: str,
) -> Optional[str]:
    if not HAS_AIOHTTP:
        return None
    payload = {
        "quoteResponse": quote,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(JUPITER_SWAP_API, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("swapTransaction")


async def _confirm_signature(
    client: "AsyncClient",
    signature: str,
    *,
    commitment: str = "confirmed",
    timeout_seconds: int = 30,
) -> Tuple[bool, Optional[str]]:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            resp = await client.get_signature_statuses([signature])
        except Exception as exc:
            await asyncio.sleep(1)
            continue
        value = resp.value[0] if resp.value else None
        if value:
            if value.err:
                return False, str(value.err)
            status = value.confirmation_status or ""
            if commitment == "processed" or status in ("confirmed", "finalized"):
                return True, None
        await asyncio.sleep(1)
    return False, "confirmation_timeout"


async def execute_swap_transaction(
    signed_tx: "VersionedTransaction",
    endpoints: List[RpcEndpoint],
    *,
    simulate: bool = True,
    commitment: str = "confirmed",
) -> SwapExecutionResult:
    if not HAS_SOLANA:
        return SwapExecutionResult(success=False, error="solana_sdk_missing")

    healthy = await get_healthy_endpoints(endpoints)
    last_error = None

    for endpoint in healthy:
        try:
            async with AsyncClient(endpoint.url) as client:
                if simulate:
                    sim = await client.simulate_transaction(signed_tx)
                    if sim.value and sim.value.err:
                        return SwapExecutionResult(
                            success=False,
                            error="simulation_failed",
                            simulation_error=str(sim.value.err),
                            endpoint=endpoint.name,
                        )

                opts = TxOpts(skip_preflight=False, max_retries=3, preflight_commitment=commitment)
                send_resp = await client.send_transaction(signed_tx, opts=opts)
                if not send_resp.value:
                    last_error = "send_failed"
                    continue
                signature = str(send_resp.value)
                confirmed, err = await _confirm_signature(client, signature, commitment=commitment)
                if confirmed:
                    return SwapExecutionResult(
                        success=True,
                        signature=signature,
                        endpoint=endpoint.name,
                    )
                last_error = err or "confirmation_failed"
        except Exception as exc:
            last_error = str(exc)
            continue

    return SwapExecutionResult(success=False, error=last_error or "rpc_failed")


async def simulate_transaction(
    signed_tx: "VersionedTransaction",
    endpoints: List[RpcEndpoint],
) -> SwapExecutionResult:
    if not HAS_SOLANA:
        return SwapExecutionResult(success=False, error="solana_sdk_missing")

    healthy = await get_healthy_endpoints(endpoints)
    for endpoint in healthy:
        try:
            async with AsyncClient(endpoint.url) as client:
                sim = await client.simulate_transaction(signed_tx)
                if sim.value and sim.value.err:
                    return SwapExecutionResult(
                        success=False,
                        error="simulation_failed",
                        simulation_error=str(sim.value.err),
                        endpoint=endpoint.name,
                    )
                return SwapExecutionResult(success=True, endpoint=endpoint.name)
        except Exception as exc:
            continue
    return SwapExecutionResult(success=False, error="simulation_failed")
