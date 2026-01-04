"""Jupiter API client for Solana token quotes and swaps."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "trader" / "jupiter_cache"
QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
PRICE_URL = "https://price.jup.ag/v6/price"
TOKEN_LIST_URL = "https://token.jup.ag/all"
USER_AGENT = "LifeOS/1.0 (Jarvis Jupiter Client)"

# Common token mints
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V"


def get_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    *,
    slippage_bps: int = 50,
    only_direct_routes: bool = False,
    cache_ttl_seconds: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Get a swap quote from Jupiter.
    
    Args:
        input_mint: Token mint address to swap from
        output_mint: Token mint address to swap to
        amount: Amount in smallest unit (lamports for SOL, etc)
        slippage_bps: Slippage tolerance in basis points (50 = 0.5%)
        only_direct_routes: If true, only use direct routes (faster but less optimal)
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": slippage_bps,
    }
    if only_direct_routes:
        params["onlyDirectRoutes"] = "true"
    
    return _get_json(QUOTE_URL, params=params, cache_ttl_seconds=cache_ttl_seconds)


def get_price(
    token_ids: List[str],
    *,
    vs_currency: str = "usd",
    cache_ttl_seconds: int = 60,
) -> Optional[Dict[str, Any]]:
    """
    Get token prices from Jupiter Price API.
    
    Args:
        token_ids: List of token mint addresses
        vs_currency: Quote currency (usd, sol)
    """
    params = {
        "ids": ",".join(token_ids),
        "vsToken": USDC_MINT if vs_currency == "usd" else SOL_MINT,
    }
    return _get_json(PRICE_URL, params=params, cache_ttl_seconds=cache_ttl_seconds)


def get_sol_price_in_usd(*, cache_ttl_seconds: int = 60) -> Optional[float]:
    """Get current SOL price in USD."""
    result = get_price([SOL_MINT], vs_currency="usd", cache_ttl_seconds=cache_ttl_seconds)
    if result and result.get("data"):
        return result["data"].get(SOL_MINT, {}).get("price")
    return None


def get_token_price_in_sol(
    token_mint: str,
    *,
    cache_ttl_seconds: int = 60,
) -> Optional[float]:
    """Get token price in SOL."""
    # Get quote for 1 token -> SOL
    # First we need to know the token decimals, assume 9 for now
    amount = 1_000_000_000  # 1 token with 9 decimals
    
    quote = get_quote(
        token_mint,
        SOL_MINT,
        amount,
        slippage_bps=100,
        only_direct_routes=True,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    
    if quote and quote.get("outAmount"):
        out_amount = int(quote["outAmount"])
        # SOL has 9 decimals
        return out_amount / 1_000_000_000
    return None


def get_token_price_in_usd(
    token_mint: str,
    *,
    cache_ttl_seconds: int = 60,
) -> Optional[float]:
    """Get token price in USD."""
    sol_price = get_sol_price_in_usd(cache_ttl_seconds=cache_ttl_seconds)
    token_price_sol = get_token_price_in_sol(token_mint, cache_ttl_seconds=cache_ttl_seconds)
    
    if sol_price and token_price_sol:
        return sol_price * token_price_sol
    return None


def fetch_token_list(*, cache_ttl_seconds: int = 3600) -> List[Dict[str, Any]]:
    """Fetch the full Jupiter token list."""
    result = _get_json(TOKEN_LIST_URL, cache_ttl_seconds=cache_ttl_seconds)
    if isinstance(result, list):
        return result
    return []


def estimate_swap_impact(
    input_mint: str,
    output_mint: str,
    amount_usd: float,
    *,
    cache_ttl_seconds: int = 30,
) -> Optional[Dict[str, Any]]:
    """
    Estimate the price impact of a swap.
    
    Returns dict with:
        - input_amount: Amount of input token
        - output_amount: Amount of output token received
        - price_impact_pct: Estimated price impact percentage
        - route_info: Route details
    """
    # Get SOL price to convert USD to amount
    sol_price = get_sol_price_in_usd(cache_ttl_seconds=cache_ttl_seconds)
    if not sol_price:
        return None
    
    # If input is SOL, calculate lamports directly
    if input_mint == SOL_MINT:
        amount_lamports = int((amount_usd / sol_price) * 1_000_000_000)
    else:
        # For other tokens, estimate based on USDC value
        # Assume 6 decimals for USDC-like tokens
        amount_lamports = int(amount_usd * 1_000_000)
    
    quote = get_quote(
        input_mint,
        output_mint,
        amount_lamports,
        slippage_bps=100,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    
    if not quote:
        return None
    
    return {
        "input_amount": amount_lamports,
        "output_amount": int(quote.get("outAmount", 0)),
        "price_impact_pct": float(quote.get("priceImpactPct", 0)),
        "route_plan": quote.get("routePlan", []),
        "other_amount_threshold": quote.get("otherAmountThreshold"),
    }


def _get_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
    retries: int = 3,
    backoff_seconds: float = 0.5,
    cache_ttl_seconds: int = 0,
) -> Optional[Any]:
    cache_path = None
    if cache_ttl_seconds > 0:
        cache_path = _cache_path(url, params)
        cached = _read_cache(cache_path, cache_ttl_seconds)
        if cached is not None:
            return cached

    headers = {"User-Agent": USER_AGENT}
    last_error = None
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            resp.raise_for_status()
            payload = resp.json()
            if cache_path:
                _write_cache(cache_path, payload)
            return payload
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(backoff_seconds * (attempt + 1))

    if last_error:
        print(f"[jupiter] request failed: {last_error}")
    return None


def _cache_path(url: str, params: Optional[Dict[str, Any]]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = url
    if params:
        params_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
        key = f"{url}?{params_str}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / f"{digest}.json"


def _read_cache(path: Path, ttl_seconds: int) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    cached_at = payload.get("cached_at")
    if not cached_at:
        return None
    if time.time() - cached_at > ttl_seconds:
        return None
    return payload.get("data")


def _write_cache(path: Path, data: Any) -> None:
    payload = {"cached_at": time.time(), "data": data}
    path.write_text(json.dumps(payload))


if __name__ == "__main__":
    print("Testing Jupiter API...")
    
    # Test SOL price
    sol_price = get_sol_price_in_usd()
    print(f"SOL Price: ${sol_price:.2f}" if sol_price else "SOL Price: N/A")
    
    # Test a quote (1 SOL -> USDC)
    quote = get_quote(
        SOL_MINT,
        USDC_MINT,
        1_000_000_000,  # 1 SOL
        slippage_bps=50,
    )
    if quote:
        out_amount = int(quote.get("outAmount", 0)) / 1_000_000  # USDC has 6 decimals
        impact = quote.get("priceImpactPct", 0)
        print(f"1 SOL -> {out_amount:.2f} USDC (impact: {float(impact)*100:.4f}%)")
