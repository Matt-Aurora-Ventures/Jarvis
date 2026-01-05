"""Reliable Solana execution helpers with RPC failover and confirmation."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.transaction_guard import require_poly_gnosis_safe

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


def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    return min(max_delay, base * (2 ** attempt))


async def _request_json(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    retries: int = 3,
    backoff_seconds: float = 0.5,
    timeout_seconds: int = 20,
) -> Optional[Dict[str, Any]]:
    if not HAS_AIOHTTP:
        return None
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method == "GET":
                    async with session.get(url, params=params) as resp:
                        if resp.status in (429, 503):
                            await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
                            continue
                        if resp.status != 200:
                            return None
                        return await resp.json()
                async with session.post(url, json=json_payload) as resp:
                    if resp.status in (429, 503):
                        await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
                        continue
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception:
            await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
    return None


def _is_blockhash_expired(error: Optional[str]) -> bool:
    if not error:
        return False
    lower = error.lower()
    return "blockhash" in lower or "blockhashnotfound" in lower or "blockhash not found" in lower


def describe_simulation_error(error: Optional[str]) -> Optional[str]:
    """Return a short, human-readable hint for common Solana simulation errors."""
    if not error:
        return None

    lower = error.lower()
    if "alreadyprocessed" in lower:
        return "Transaction already processed; likely duplicate or replayed."
    if "blockhash" in lower:
        return "Blockhash expired; rebuild and re-sign the transaction."
    if "accountinuse" in lower:
        return "Account in use; retry with backoff."
    if "insufficientfunds" in lower:
        return "Insufficient funds for fee or transfer."
    if "invalidaccountdata" in lower:
        return "Invalid account data; verify mint/account ownership."
    if "uninitializedaccount" in lower:
        return "Account not initialized; create associated token account."
    if "signatureverificationfailed" in lower:
        return "Signature verification failed; ensure signer and recent blockhash match."

    match = re.search(r"InstructionErrorCustom\((\d+)\)", error)
    if match:
        code = match.group(1)
        return f"Custom program error {code}; program-specific constraint failed."
    return None


def classify_simulation_error(error: Optional[str]) -> str:
    """Classify simulation errors to reduce noisy retries."""
    if not error:
        return "unknown"

    lower = error.lower()
    if "alreadyprocessed" in lower:
        return "permanent"
    if "blockhash" in lower:
        return "retryable"
    if "accountinuse" in lower:
        return "retryable"
    if "timeout" in lower or "timed out" in lower:
        return "retryable"
    if "insufficientfunds" in lower:
        return "permanent"
    if "invalidaccountdata" in lower or "uninitializedaccount" in lower:
        return "permanent"
    if "signatureverificationfailed" in lower:
        return "permanent"
    if "instructionerrorcustom" in lower or "custom program error" in lower:
        return "permanent"
    return "unknown"


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
    return await _request_json("GET", JUPITER_QUOTE_API, params=params)


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
    data = await _request_json("POST", JUPITER_SWAP_API, json_payload=payload)
    if not data:
        return None
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
    refresh_signed_tx: Optional[Callable[[], "VersionedTransaction"]] = None,
) -> SwapExecutionResult:
    if not HAS_SOLANA:
        return SwapExecutionResult(success=False, error="solana_sdk_missing")

    ok, error = require_poly_gnosis_safe("solana_swap_execute")
    if not ok:
        return SwapExecutionResult(success=False, error=error)

    healthy = await get_healthy_endpoints(endpoints)
    last_error = None
    refreshed = False
    current_tx = signed_tx

    for endpoint in healthy:
        try:
            async with AsyncClient(endpoint.url) as client:
                if simulate:
                    sim = await client.simulate_transaction(current_tx)
                    if sim.value and sim.value.err:
                        return SwapExecutionResult(
                            success=False,
                            error="simulation_failed",
                            simulation_error=str(sim.value.err),
                            endpoint=endpoint.name,
                        )

                opts = TxOpts(skip_preflight=False, max_retries=3, preflight_commitment=commitment)
                send_resp = await client.send_transaction(current_tx, opts=opts)
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
                if refresh_signed_tx and not refreshed and _is_blockhash_expired(last_error):
                    try:
                        current_tx = refresh_signed_tx()
                        refreshed = True
                        continue
                    except Exception as refresh_exc:
                        last_error = str(refresh_exc)
        except Exception as exc:
            last_error = str(exc)
            if refresh_signed_tx and not refreshed and _is_blockhash_expired(last_error):
                try:
                    current_tx = refresh_signed_tx()
                    refreshed = True
                    continue
                except Exception as refresh_exc:
                    last_error = str(refresh_exc)
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
