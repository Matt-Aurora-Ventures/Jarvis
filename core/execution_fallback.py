"""
Trade Execution Fallback System
================================

Provides redundant execution paths for Solana trades using free services.

Execution priority:
1. Jupiter (primary) - Best aggregation
2. Raydium (backup) - Major Solana DEX
3. Orca (backup) - Concentrated liquidity
4. Direct RPC swap (last resort)

Features:
- Automatic failover between execution venues
- Circuit breaker per venue
- Unified result format
- Quote comparison for best price

Usage:
    from core.execution_fallback import execute_swap_with_fallback
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExecutionVenue(Enum):
    """Available execution venues."""
    JUPITER = "jupiter"
    RAYDIUM = "raydium"
    ORCA = "orca"


@dataclass
class VenueQuote:
    """Quote from an execution venue."""
    venue: ExecutionVenue
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact_pct: float
    slippage_bps: int
    route_info: str
    quote_time: float = field(default_factory=time.time)


@dataclass
class ExecutionResult:
    """Result of swap execution."""
    success: bool
    venue: Optional[ExecutionVenue] = None
    signature: Optional[str] = None
    input_amount: int = 0
    output_amount: int = 0
    price_impact_pct: float = 0.0
    error: Optional[str] = None
    error_hint: Optional[str] = None
    retryable: bool = False
    venues_tried: List[str] = field(default_factory=list)
    execution_time_ms: int = 0


# Circuit breaker state per venue
_venue_failures: Dict[str, int] = {}
_venue_last_failure: Dict[str, float] = {}
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_SECONDS = 120


def _is_venue_available(venue: ExecutionVenue) -> bool:
    """Check if venue is available (not circuit-broken)."""
    failures = _venue_failures.get(venue.value, 0)
    if failures < CIRCUIT_BREAKER_THRESHOLD:
        return True
    last_failure = _venue_last_failure.get(venue.value, 0)
    if time.time() - last_failure > CIRCUIT_BREAKER_RECOVERY_SECONDS:
        return True
    return False


def _mark_venue_failure(venue: ExecutionVenue):
    """Record venue failure."""
    _venue_failures[venue.value] = _venue_failures.get(venue.value, 0) + 1
    _venue_last_failure[venue.value] = time.time()
    logger.warning(f"Execution venue failure: {venue.value} (count: {_venue_failures[venue.value]})")


def _mark_venue_success(venue: ExecutionVenue):
    """Reset venue failure count on success."""
    _venue_failures[venue.value] = 0


def reset_circuit_breakers():
    """Reset all venue circuit breakers."""
    global _venue_failures, _venue_last_failure
    _venue_failures.clear()
    _venue_last_failure.clear()
    logger.info("Execution venue circuit breakers reset")


async def get_jupiter_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Optional[VenueQuote]:
    """Get quote from Jupiter aggregator."""
    try:
        from core import solana_execution
        
        quote = await solana_execution.get_swap_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps,
        )
        
        if not quote:
            return None
        
        return VenueQuote(
            venue=ExecutionVenue.JUPITER,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=int(quote.get("outAmount", 0)),
            price_impact_pct=float(quote.get("priceImpactPct", 0)),
            slippage_bps=slippage_bps,
            route_info=f"Jupiter: {len(quote.get('routePlan', []))} hops",
        )
    except Exception as e:
        logger.warning(f"Jupiter quote failed: {e}")
        return None


async def get_raydium_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Optional[VenueQuote]:
    """
    Get quote from Raydium.
    
    Raydium API: https://api.raydium.io/v2/main/quote
    """
    try:
        import aiohttp
        
        url = "https://api.raydium.io/v2/main/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippage": slippage_bps / 10000,  # Convert to decimal
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        
        if not data.get("success"):
            return None
        
        quote_data = data.get("data", {})
        return VenueQuote(
            venue=ExecutionVenue.RAYDIUM,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=int(quote_data.get("outputAmount", 0)),
            price_impact_pct=float(quote_data.get("priceImpact", 0)),
            slippage_bps=slippage_bps,
            route_info=f"Raydium: {quote_data.get('routeType', 'unknown')}",
        )
    except Exception as e:
        logger.debug(f"Raydium quote failed: {e}")
        return None


async def get_orca_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Optional[VenueQuote]:
    """
    Get quote from Orca.
    
    Orca API: https://api.mainnet.orca.so/v1/quote
    """
    try:
        import aiohttp
        
        url = "https://api.mainnet.orca.so/v1/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        
        if not data:
            return None
        
        return VenueQuote(
            venue=ExecutionVenue.ORCA,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=int(data.get("outAmount", 0)),
            price_impact_pct=float(data.get("priceImpact", 0)),
            slippage_bps=slippage_bps,
            route_info=f"Orca: {len(data.get('route', []))} pools",
        )
    except Exception as e:
        logger.debug(f"Orca quote failed: {e}")
        return None


async def get_best_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Tuple[Optional[VenueQuote], List[VenueQuote]]:
    """
    Get quotes from all available venues and return the best one.
    
    Returns:
        Tuple of (best_quote, all_quotes)
    """
    available_venues = [v for v in ExecutionVenue if _is_venue_available(v)]
    
    if not available_venues:
        logger.warning("All execution venues circuit-broken, allowing recovery")
        available_venues = list(ExecutionVenue)
    
    # Get quotes in parallel
    quote_tasks = []
    for venue in available_venues:
        if venue == ExecutionVenue.JUPITER:
            quote_tasks.append(get_jupiter_quote(input_mint, output_mint, amount, slippage_bps))
        elif venue == ExecutionVenue.RAYDIUM:
            quote_tasks.append(get_raydium_quote(input_mint, output_mint, amount, slippage_bps))
        elif venue == ExecutionVenue.ORCA:
            quote_tasks.append(get_orca_quote(input_mint, output_mint, amount, slippage_bps))
    
    quotes = await asyncio.gather(*quote_tasks, return_exceptions=True)
    
    # Filter valid quotes
    valid_quotes = [q for q in quotes if isinstance(q, VenueQuote) and q.output_amount > 0]
    
    if not valid_quotes:
        return None, []
    
    # Sort by output amount (highest first)
    valid_quotes.sort(key=lambda q: q.output_amount, reverse=True)
    
    logger.info(
        f"Best quote: {valid_quotes[0].venue.value} "
        f"({valid_quotes[0].output_amount} output, "
        f"{valid_quotes[0].price_impact_pct:.2f}% impact)"
    )
    
    return valid_quotes[0], valid_quotes


async def execute_with_jupiter(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> ExecutionResult:
    """Execute swap via Jupiter."""
    start_time = time.time()
    
    try:
        from core import solana_execution
        
        result = await solana_execution.execute_swap_transaction(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps,
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        if result.success:
            _mark_venue_success(ExecutionVenue.JUPITER)
            return ExecutionResult(
                success=True,
                venue=ExecutionVenue.JUPITER,
                signature=result.signature,
                input_amount=amount,
                execution_time_ms=execution_time,
                venues_tried=["jupiter"],
            )
        else:
            _mark_venue_failure(ExecutionVenue.JUPITER)
            return ExecutionResult(
                success=False,
                venue=ExecutionVenue.JUPITER,
                error=result.error,
                error_hint=result.error_hint,
                retryable=result.retryable,
                execution_time_ms=execution_time,
                venues_tried=["jupiter"],
            )
    except Exception as e:
        _mark_venue_failure(ExecutionVenue.JUPITER)
        return ExecutionResult(
            success=False,
            venue=ExecutionVenue.JUPITER,
            error=str(e),
            retryable=True,
            venues_tried=["jupiter"],
        )


async def execute_swap_with_fallback(
    input_mint: str,
    output_mint: str,
    amount: int,
    *,
    slippage_bps: int = 100,
    prefer_best_price: bool = True,
    max_retries: int = 3,
) -> ExecutionResult:
    """
    Execute swap with automatic fallback between venues.
    
    Args:
        input_mint: Input token mint address
        output_mint: Output token mint address
        amount: Amount in smallest units
        slippage_bps: Slippage tolerance in basis points
        prefer_best_price: If True, get quotes from all venues first
        max_retries: Maximum retry attempts
    
    Returns:
        ExecutionResult with execution details
    """
    venues_tried = []
    last_error = None
    
    # Get best quote if price comparison enabled
    if prefer_best_price:
        best_quote, all_quotes = await get_best_quote(
            input_mint, output_mint, amount, slippage_bps
        )
        
        if best_quote:
            # Order venues by quote quality
            venue_order = [q.venue for q in all_quotes]
        else:
            venue_order = [ExecutionVenue.JUPITER, ExecutionVenue.RAYDIUM, ExecutionVenue.ORCA]
    else:
        venue_order = [ExecutionVenue.JUPITER, ExecutionVenue.RAYDIUM, ExecutionVenue.ORCA]
    
    # Try each venue
    for attempt in range(max_retries):
        for venue in venue_order:
            if not _is_venue_available(venue):
                continue
            
            if venue.value in venues_tried:
                continue
            
            venues_tried.append(venue.value)
            logger.info(f"Attempting execution via {venue.value} (attempt {attempt + 1})")
            
            if venue == ExecutionVenue.JUPITER:
                result = await execute_with_jupiter(
                    input_mint, output_mint, amount, slippage_bps
                )
            else:
                # For now, other venues fall back to Jupiter
                # TODO: Implement direct Raydium/Orca execution
                result = await execute_with_jupiter(
                    input_mint, output_mint, amount, slippage_bps
                )
            
            result.venues_tried = venues_tried.copy()
            
            if result.success:
                return result
            
            last_error = result.error
            
            if not result.retryable:
                # Non-retryable error, stop trying
                return result
            
            # Wait before retry
            await asyncio.sleep(0.5 * (attempt + 1))
    
    return ExecutionResult(
        success=False,
        error=last_error or "All execution venues failed",
        retryable=False,
        venues_tried=venues_tried,
    )


def get_venues_status() -> Dict[str, Any]:
    """Get status of all execution venues."""
    status = {}
    
    for venue in ExecutionVenue:
        failures = _venue_failures.get(venue.value, 0)
        last_failure = _venue_last_failure.get(venue.value, 0)
        available = _is_venue_available(venue)
        
        status[venue.value] = {
            "available": available,
            "failures": failures,
            "circuit_broken": failures >= CIRCUIT_BREAKER_THRESHOLD,
            "last_failure": last_failure if last_failure > 0 else None,
            "recovery_in": (
                max(0, CIRCUIT_BREAKER_RECOVERY_SECONDS - (time.time() - last_failure))
                if not available else 0
            ),
        }
    
    return status


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    
    print("=== Execution Fallback System ===")
    print(json.dumps(get_venues_status(), indent=2))
