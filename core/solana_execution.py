"""Reliable Solana execution helpers with RPC failover and confirmation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
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

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RPC_CONFIG = ROOT / "config" / "rpc_providers.json"

# Jupiter API endpoints - public.jupiterapi.com is the only one that works from this machine
JUPITER_QUOTE_API = "https://public.jupiterapi.com/quote"
JUPITER_SWAP_API = "https://public.jupiterapi.com/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3  # failures before marking endpoint as unhealthy
CIRCUIT_BREAKER_RECOVERY_SECONDS = 60  # seconds before retrying a failed endpoint
RPC_HEALTH_CACHE_SECONDS = 10  # cache health check results for this long

# Global state for circuit breaker and health caching
_endpoint_failures: Dict[str, int] = {}
_endpoint_last_failure: Dict[str, float] = {}
_endpoint_health_cache: Dict[str, Tuple[bool, float]] = {}


def _backoff_delay(base: float, attempt: int, max_delay: float = 30.0) -> float:
    """Exponential backoff with jitter to prevent thundering herd."""
    delay = min(max_delay, base * (2 ** attempt))
    jitter = delay * 0.1 * random.random()
    return delay + jitter


def _is_rate_limited(status: int) -> bool:
    """Check if response indicates rate limiting."""
    return status in (429, 503, 502)


def _mark_endpoint_failure(endpoint_url: str) -> None:
    """Record a failure for circuit breaker tracking."""
    _endpoint_failures[endpoint_url] = _endpoint_failures.get(endpoint_url, 0) + 1
    _endpoint_last_failure[endpoint_url] = time.time()
    logger.warning(f"RPC endpoint failure #{_endpoint_failures[endpoint_url]}: {endpoint_url}")


def _mark_endpoint_success(endpoint_url: str) -> None:
    """Reset failure count on success."""
    _endpoint_failures[endpoint_url] = 0


def _is_endpoint_available(endpoint_url: str) -> bool:
    """Check if endpoint is available (not circuit-broken)."""
    failures = _endpoint_failures.get(endpoint_url, 0)
    if failures < CIRCUIT_BREAKER_FAILURE_THRESHOLD:
        return True
    # Check if recovery period has passed
    last_failure = _endpoint_last_failure.get(endpoint_url, 0)
    if time.time() - last_failure > CIRCUIT_BREAKER_RECOVERY_SECONDS:
        logger.info(f"RPC endpoint recovery attempt: {endpoint_url}")
        return True
    return False


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers - useful for testing or manual recovery."""
    global _endpoint_failures, _endpoint_last_failure, _endpoint_health_cache
    _endpoint_failures.clear()
    _endpoint_last_failure.clear()
    _endpoint_health_cache.clear()
    logger.info("All RPC circuit breakers reset")


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
    """Make HTTP request with retry logic and circuit breaker awareness."""
    if not HAS_AIOHTTP:
        return None
    
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    last_error = None
    
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method == "GET":
                    async with session.get(url, params=params) as resp:
                        if _is_rate_limited(resp.status):
                            retry_after = resp.headers.get("Retry-After")
                            wait_time = float(retry_after) if retry_after else _backoff_delay(backoff_seconds, attempt)
                            logger.warning(f"Rate limited on {url}, waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        if resp.status != 200:
                            last_error = f"HTTP {resp.status}"
                            continue
                        return await resp.json()
                else:
                    async with session.post(url, json=json_payload) as resp:
                        if _is_rate_limited(resp.status):
                            retry_after = resp.headers.get("Retry-After")
                            wait_time = float(retry_after) if retry_after else _backoff_delay(backoff_seconds, attempt)
                            logger.warning(f"Rate limited on {url}, waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                            continue
                        if resp.status != 200:
                            last_error = f"HTTP {resp.status}"
                            continue
                        return await resp.json()
        except asyncio.TimeoutError:
            last_error = "timeout"
            logger.warning(f"Request timeout on {url} (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
        except aiohttp.ClientError as e:
            last_error = str(e)
            logger.warning(f"Client error on {url}: {e} (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
        except Exception as e:
            last_error = str(e)
            logger.error(f"Unexpected error on {url}: {e}")
            await asyncio.sleep(_backoff_delay(backoff_seconds, attempt))
    
    logger.error(f"Request failed after {retries} attempts: {url} - {last_error}")
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
    if "connection" in lower or "network" in lower:
        return "retryable"
    if "rate" in lower or "429" in lower or "503" in lower:
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


def is_retryable_error(error: Optional[str]) -> bool:
    """Check if an error is retryable."""
    return classify_simulation_error(error) == "retryable"


@dataclass
class RpcEndpoint:
    name: str
    url: str
    timeout_ms: int = 30000
    rate_limit: int = 100  # requests per second (approximate)


@dataclass
class SwapExecutionResult:
    success: bool
    signature: Optional[str] = None
    error: Optional[str] = None
    endpoint: Optional[str] = None
    simulation_error: Optional[str] = None
    error_hint: Optional[str] = None  # Human-readable hint
    retryable: bool = False  # Whether the operation can be retried


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
    """Load Solana RPC endpoints from config with fallback defaults."""
    if not RPC_CONFIG.exists():
        logger.warning("RPC config not found, using public endpoint")
        return [RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com", rate_limit=10)]

    try:
        payload = json.loads(RPC_CONFIG.read_text())
    except Exception as e:
        logger.error(f"Failed to load RPC config: {e}")
        return [RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com", rate_limit=10)]

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
                    rate_limit=int(primary.get("rate_limit", 100)),
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
                rate_limit=int(fallback.get("rate_limit", 50)),
            )
        )

    if not endpoints:
        logger.warning("No valid RPC endpoints configured, using public endpoint")
        endpoints.append(RpcEndpoint(name="public_solana", url="https://api.mainnet-beta.solana.com", rate_limit=10))
    
    logger.info(f"Loaded {len(endpoints)} Solana RPC endpoints")
    return endpoints


async def _rpc_health(endpoint: RpcEndpoint) -> bool:
    """Check RPC endpoint health with caching."""
    if not HAS_AIOHTTP:
        return True
    
    # Check circuit breaker first
    if not _is_endpoint_available(endpoint.url):
        logger.debug(f"Endpoint {endpoint.name} is circuit-broken")
        return False
    
    # Check cache
    cached = _endpoint_health_cache.get(endpoint.url)
    if cached:
        is_healthy, cache_time = cached
        if time.time() - cache_time < RPC_HEALTH_CACHE_SECONDS:
            return is_healthy
    
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
    timeout = aiohttp.ClientTimeout(total=min(endpoint.timeout_ms / 1000, 5))  # Cap health check at 5s
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint.url, json=payload) as resp:
                if resp.status != 200:
                    _endpoint_health_cache[endpoint.url] = (False, time.time())
                    return False
                data = await resp.json()
                is_healthy = data.get("result") == "ok"
                _endpoint_health_cache[endpoint.url] = (is_healthy, time.time())
                if is_healthy:
                    _mark_endpoint_success(endpoint.url)
                return is_healthy
    except Exception as e:
        logger.debug(f"Health check failed for {endpoint.name}: {e}")
        _endpoint_health_cache[endpoint.url] = (False, time.time())
        _mark_endpoint_failure(endpoint.url)
        return False


async def get_healthy_endpoints(endpoints: Iterable[RpcEndpoint]) -> List[RpcEndpoint]:
    """Get list of healthy endpoints, checking in parallel."""
    endpoints_list = list(endpoints)
    
    # Filter out circuit-broken endpoints first
    available = [ep for ep in endpoints_list if _is_endpoint_available(ep.url)]
    
    if not available:
        logger.warning("All endpoints circuit-broken, allowing recovery attempt")
        available = endpoints_list
    
    # Check health in parallel
    health_tasks = [_rpc_health(ep) for ep in available]
    results = await asyncio.gather(*health_tasks, return_exceptions=True)
    
    healthy: List[RpcEndpoint] = []
    for ep, result in zip(available, results):
        if result is True:  # Explicitly True, not an exception
            healthy.append(ep)
    
    if not healthy:
        logger.warning("No healthy endpoints found, returning all available")
        return available
    
    logger.debug(f"Found {len(healthy)}/{len(endpoints_list)} healthy endpoints")
    return healthy


async def get_swap_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    *,
    slippage_bps: int = 100,
    retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """Get swap quote from Jupiter with retry logic."""
    if not HAS_AIOHTTP:
        logger.error("aiohttp not available for swap quote")
        return None
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": slippage_bps,
    }
    result = await _request_json("GET", JUPITER_QUOTE_API, params=params, retries=retries)
    if result:
        logger.debug(f"Got swap quote: {input_mint[:8]}... -> {output_mint[:8]}... for {amount}")
    return result


async def get_swap_transaction(
    quote: Dict[str, Any],
    user_public_key: str,
    *,
    priority_fee: str = "auto",
    retries: int = 3,
) -> Optional[str]:
    """Get swap transaction from Jupiter with retry logic."""
    if not HAS_AIOHTTP:
        logger.error("aiohttp not available for swap transaction")
        return None
    payload = {
        "quoteResponse": quote,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": priority_fee,
    }
    data = await _request_json("POST", JUPITER_SWAP_API, json_payload=payload, retries=retries)
    if not data:
        logger.error("Failed to get swap transaction from Jupiter")
        return None
    return data.get("swapTransaction")


async def _confirm_signature(
    client: "AsyncClient",
    signature: str,
    *,
    commitment: str = "confirmed",
    timeout_seconds: int = 30,
    poll_interval: float = 0.5,
) -> Tuple[bool, Optional[str]]:
    """Confirm transaction signature with exponential backoff polling."""
    start = time.time()
    poll_count = 0
    
    while time.time() - start < timeout_seconds:
        try:
            resp = await client.get_signature_statuses([signature])
            value = resp.value[0] if resp.value else None
            if value:
                if value.err:
                    error_str = str(value.err)
                    logger.warning(f"Transaction {signature[:16]}... failed: {error_str}")
                    return False, error_str
                status = value.confirmation_status or ""
                if commitment == "processed" or status in ("confirmed", "finalized"):
                    logger.info(f"Transaction {signature[:16]}... {status}")
                    return True, None
        except Exception as exc:
            logger.debug(f"Status check failed: {exc}")
        
        poll_count += 1
        # Exponential backoff for polling, starting at poll_interval
        wait_time = min(poll_interval * (1.2 ** min(poll_count, 10)), 2.0)
        await asyncio.sleep(wait_time)
    
    logger.warning(f"Transaction {signature[:16]}... confirmation timeout after {timeout_seconds}s")
    return False, "confirmation_timeout"


async def get_recent_blockhash(endpoints: List[RpcEndpoint]) -> Optional[Tuple[str, int]]:
    """Get recent blockhash from healthy endpoints."""
    if not HAS_SOLANA:
        return None
    
    healthy = await get_healthy_endpoints(endpoints)
    for endpoint in healthy:
        try:
            async with AsyncClient(endpoint.url) as client:
                resp = await client.get_latest_blockhash()
                if resp and resp.value:
                    blockhash = str(resp.value.blockhash)
                    last_valid = resp.value.last_valid_block_height
                    _mark_endpoint_success(endpoint.url)
                    logger.debug(f"Got blockhash from {endpoint.name}: {blockhash[:16]}...")
                    return blockhash, last_valid
        except Exception as e:
            logger.warning(f"Failed to get blockhash from {endpoint.name}: {e}")
            _mark_endpoint_failure(endpoint.url)
            continue
    
    logger.error("Failed to get blockhash from any endpoint")
    return None


async def execute_swap_transaction(
    signed_tx: "VersionedTransaction",
    endpoints: List[RpcEndpoint],
    *,
    simulate: bool = True,
    commitment: str = "confirmed",
    refresh_signed_tx: Optional[Callable[[], "VersionedTransaction"]] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> SwapExecutionResult:
    """
    Execute a signed swap transaction with robust failover and retry logic.
    
    Features:
    - Circuit breaker pattern for failing endpoints
    - Automatic blockhash refresh on expiry
    - Exponential backoff between retries
    - Parallel health checking of endpoints
    """
    if not HAS_SOLANA:
        return SwapExecutionResult(success=False, error="solana_sdk_missing", retryable=False)

    ok, error = require_poly_gnosis_safe("solana_swap_execute")
    if not ok:
        return SwapExecutionResult(success=False, error=error, retryable=False)

    healthy = await get_healthy_endpoints(endpoints)
    if not healthy:
        return SwapExecutionResult(
            success=False, 
            error="no_healthy_endpoints", 
            error_hint="All RPC endpoints are unavailable. Check network or API keys.",
            retryable=True
        )

    last_error = None
    last_simulation_error = None
    refresh_count = 0
    max_refreshes = 2
    current_tx = signed_tx

    for attempt in range(max_retries):
        for endpoint in healthy:
            try:
                async with AsyncClient(endpoint.url, timeout=endpoint.timeout_ms / 1000) as client:
                    # Simulation phase
                    if simulate:
                        try:
                            sim = await client.simulate_transaction(current_tx)
                            if sim.value and sim.value.err:
                                sim_error = str(sim.value.err)
                                error_class = classify_simulation_error(sim_error)
                                hint = describe_simulation_error(sim_error)
                                
                                if error_class == "permanent":
                                    logger.error(f"Permanent simulation error: {sim_error}")
                                    return SwapExecutionResult(
                                        success=False,
                                        error="simulation_failed",
                                        simulation_error=sim_error,
                                        error_hint=hint,
                                        endpoint=endpoint.name,
                                        retryable=False,
                                    )
                                
                                # Retryable error - try blockhash refresh
                                if _is_blockhash_expired(sim_error) and refresh_signed_tx and refresh_count < max_refreshes:
                                    logger.info("Blockhash expired during simulation, refreshing...")
                                    try:
                                        current_tx = refresh_signed_tx()
                                        refresh_count += 1
                                        continue  # Retry with new tx
                                    except Exception as refresh_exc:
                                        last_error = f"refresh_failed: {refresh_exc}"
                                
                                last_simulation_error = sim_error
                                _mark_endpoint_failure(endpoint.url)
                                continue  # Try next endpoint
                        except Exception as sim_exc:
                            logger.warning(f"Simulation exception on {endpoint.name}: {sim_exc}")
                            _mark_endpoint_failure(endpoint.url)
                            continue

                    # Send transaction
                    opts = TxOpts(skip_preflight=False, max_retries=3, preflight_commitment=commitment)
                    try:
                        send_resp = await client.send_transaction(current_tx, opts=opts)
                    except Exception as send_exc:
                        send_error = str(send_exc)
                        logger.warning(f"Send failed on {endpoint.name}: {send_error}")
                        
                        if _is_blockhash_expired(send_error) and refresh_signed_tx and refresh_count < max_refreshes:
                            logger.info("Blockhash expired during send, refreshing...")
                            try:
                                current_tx = refresh_signed_tx()
                                refresh_count += 1
                                continue
                            except Exception as refresh_exc:
                                last_error = f"refresh_failed: {refresh_exc}"
                        
                        _mark_endpoint_failure(endpoint.url)
                        last_error = send_error
                        continue
                    
                    if not send_resp.value:
                        last_error = "send_returned_no_value"
                        _mark_endpoint_failure(endpoint.url)
                        continue
                    
                    signature = str(send_resp.value)
                    logger.info(f"Transaction sent via {endpoint.name}: {signature[:16]}...")
                    
                    # Confirm transaction
                    confirmed, confirm_err = await _confirm_signature(
                        client, signature, commitment=commitment, timeout_seconds=30
                    )
                    
                    if confirmed:
                        _mark_endpoint_success(endpoint.url)
                        return SwapExecutionResult(
                            success=True,
                            signature=signature,
                            endpoint=endpoint.name,
                            retryable=False,
                        )
                    
                    # Confirmation failed
                    last_error = confirm_err or "confirmation_failed"
                    
                    if _is_blockhash_expired(last_error) and refresh_signed_tx and refresh_count < max_refreshes:
                        logger.info("Blockhash expired during confirmation, refreshing...")
                        try:
                            current_tx = refresh_signed_tx()
                            refresh_count += 1
                            continue
                        except Exception as refresh_exc:
                            last_error = f"refresh_failed: {refresh_exc}"
                    
                    _mark_endpoint_failure(endpoint.url)
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on {endpoint.name}")
                _mark_endpoint_failure(endpoint.url)
                last_error = "timeout"
                continue
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"Unexpected error on {endpoint.name}: {last_error}")
                
                if _is_blockhash_expired(last_error) and refresh_signed_tx and refresh_count < max_refreshes:
                    try:
                        current_tx = refresh_signed_tx()
                        refresh_count += 1
                        continue
                    except Exception as refresh_exc:
                        last_error = f"refresh_failed: {refresh_exc}"
                
                _mark_endpoint_failure(endpoint.url)
                continue
        
        # All endpoints tried, wait before retry
        if attempt < max_retries - 1:
            wait_time = _backoff_delay(retry_delay, attempt)
            logger.info(f"Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            # Refresh healthy endpoints for next attempt
            healthy = await get_healthy_endpoints(endpoints)

    # Build final error result
    final_error = last_error or "rpc_failed"
    error_hint = describe_simulation_error(last_simulation_error or last_error)
    is_retryable = is_retryable_error(final_error)
    
    logger.error(f"Transaction failed after {max_retries} attempts: {final_error}")
    
    return SwapExecutionResult(
        success=False, 
        error=final_error,
        simulation_error=last_simulation_error,
        error_hint=error_hint,
        retryable=is_retryable,
    )


async def simulate_transaction(
    signed_tx: "VersionedTransaction",
    endpoints: List[RpcEndpoint],
) -> SwapExecutionResult:
    """Simulate a transaction across healthy endpoints."""
    if not HAS_SOLANA:
        return SwapExecutionResult(success=False, error="solana_sdk_missing", retryable=False)

    healthy = await get_healthy_endpoints(endpoints)
    last_error = None
    
    for endpoint in healthy:
        try:
            async with AsyncClient(endpoint.url, timeout=endpoint.timeout_ms / 1000) as client:
                sim = await client.simulate_transaction(signed_tx)
                if sim.value and sim.value.err:
                    sim_error = str(sim.value.err)
                    hint = describe_simulation_error(sim_error)
                    return SwapExecutionResult(
                        success=False,
                        error="simulation_failed",
                        simulation_error=sim_error,
                        error_hint=hint,
                        endpoint=endpoint.name,
                        retryable=is_retryable_error(sim_error),
                    )
                _mark_endpoint_success(endpoint.url)
                return SwapExecutionResult(success=True, endpoint=endpoint.name)
        except Exception as exc:
            last_error = str(exc)
            logger.warning(f"Simulation failed on {endpoint.name}: {last_error}")
            _mark_endpoint_failure(endpoint.url)
            continue
    
    return SwapExecutionResult(
        success=False, 
        error=last_error or "simulation_failed",
        retryable=True,
    )


# Convenience function for getting endpoints with health status
async def get_endpoint_status() -> Dict[str, Any]:
    """Get status of all configured RPC endpoints."""
    endpoints = load_solana_rpc_endpoints()
    statuses = []
    
    for ep in endpoints:
        is_healthy = await _rpc_health(ep)
        failures = _endpoint_failures.get(ep.url, 0)
        is_available = _is_endpoint_available(ep.url)
        
        statuses.append({
            "name": ep.name,
            "url": ep.url[:50] + "..." if len(ep.url) > 50 else ep.url,
            "healthy": is_healthy,
            "available": is_available,
            "failures": failures,
            "rate_limit": ep.rate_limit,
        })
    
    return {
        "endpoints": statuses,
        "total": len(endpoints),
        "healthy": sum(1 for s in statuses if s["healthy"]),
        "available": sum(1 for s in statuses if s["available"]),
    }
