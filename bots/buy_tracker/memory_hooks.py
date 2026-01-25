"""
Buy Tracker memory hooks for purchase event tracking and analysis.

Integrates with core memory system to:
- Store purchase events for tracking
- Recall purchase history by token or wallet
- Calculate aggregated buy statistics
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from core.async_utils import fire_and_forget, TaskTracker
from core.memory import retain_fact, recall

logger = logging.getLogger(__name__)

# Module-level task tracker
_memory_tracker = TaskTracker("buy_tracker_memory")

# Environment variable to enable/disable memory operations
BUY_TRACKER_MEMORY_ENABLED = os.getenv("BUY_TRACKER_MEMORY_ENABLED", "true").lower() == "true"


async def store_purchase_event(
    token_symbol: str,
    token_mint: str,
    buyer_wallet: str,
    purchase_amount_sol: float,
    token_amount: float,
    price_at_purchase: float,
    source: str = "kr8tiv",  # kr8tiv, whale_watch, etc.
    metadata: Optional[Dict] = None,
) -> int:
    """
    Store purchase event for tracking.

    Args:
        token_symbol: Token ticker symbol
        token_mint: Token mint address
        buyer_wallet: Buyer's wallet address
        purchase_amount_sol: Amount in SOL
        token_amount: Amount of tokens purchased
        price_at_purchase: Price per token at purchase time
        source: Source of the purchase event (kr8tiv, whale_watch, etc.)
        metadata: Additional metadata (market_cap, buyer_position_pct, etc.)

    Returns:
        Fact ID from memory system

    Example:
        fact_id = await store_purchase_event(
            token_symbol="KR8TIV",
            token_mint="kr8tiv123...",
            buyer_wallet="abc...xyz",
            purchase_amount_sol=1.5,
            token_amount=1000000,
            price_at_purchase=0.0000015
        )
    """
    if not BUY_TRACKER_MEMORY_ENABLED:
        logger.debug("Buy Tracker memory disabled, skipping purchase storage")
        return -1

    try:
        # Calculate USD value if metadata available
        usd_amount = 0.0
        if metadata and "sol_price_usd" in metadata:
            usd_amount = purchase_amount_sol * metadata["sol_price_usd"]

        # Build entities
        # Shorten wallet for entity extraction
        wallet_short = f"{buyer_wallet[:8]}...{buyer_wallet[-8:]}" if len(buyer_wallet) > 20 else buyer_wallet
        entities = [f"@{token_symbol}", f"@{wallet_short}"]

        # Build summary
        summary = (
            f"Purchase: {token_symbol}\n"
            f"Amount: {purchase_amount_sol:.2f} SOL ({token_amount:,.0f} tokens)\n"
            f"Price: ${price_at_purchase:.8f}"
        )

        if usd_amount > 0:
            summary += f"\nUSD value: ${usd_amount:.2f}"

        if metadata:
            market_cap = metadata.get("market_cap")
            buyer_position_pct = metadata.get("buyer_position_pct")

            if market_cap:
                summary += f"\nMarket cap: ${market_cap:,.0f}"
            if buyer_position_pct:
                summary += f"\nBuyer position: {buyer_position_pct:.2f}%"

        summary += f"\nBuyer: {wallet_short}"
        summary += f"\nSource: {source}"

        # Build context with key metrics
        context_parts = [
            "purchase_event",
            token_mint[:12],
            f"sol:{purchase_amount_sol:.2f}",
            f"source:{source}",
        ]

        context = "|".join(context_parts)

        # Store in memory (retain_fact is sync - run in thread pool)
        fact_id = await asyncio.to_thread(
            retain_fact,
            content=summary,
            context=context,
            source="buy_tracker",
            entities=entities,
            confidence=1.0,
        )

        logger.debug(f"Stored purchase event for {token_symbol} (fact_id={fact_id})")
        return fact_id

    except Exception as e:
        logger.error(f"Failed to store purchase event: {e}")
        return -1


async def recall_purchase_history(
    token_symbol: Optional[str] = None,
    buyer_wallet: Optional[str] = None,
    k: int = 20,
) -> List[Dict[str, Any]]:
    """
    Recall purchase history for a token or wallet.

    Args:
        token_symbol: Filter by token symbol
        buyer_wallet: Filter by buyer wallet
        k: Maximum results to return

    Returns:
        List of purchase events sorted by timestamp

    Example:
        # All KR8TIV purchases
        history = await recall_purchase_history(token_symbol="KR8TIV", k=50)
        for purchase in history:
            print(f"Purchase: {purchase['content'][:50]}...")
    """
    if not BUY_TRACKER_MEMORY_ENABLED:
        logger.debug("Buy Tracker memory disabled, returning empty history")
        return []

    try:
        # Build query
        query_parts = ["purchase"]

        if token_symbol:
            query_parts.append(token_symbol)

        if buyer_wallet:
            # Shorten wallet for search
            wallet_short = f"{buyer_wallet[:8]}...{buyer_wallet[-8:]}" if len(buyer_wallet) > 20 else buyer_wallet
            query_parts.append(wallet_short)

        query = " ".join(query_parts)

        # Recall from memory
        results = await recall(
            query=query,
            k=k,
            source_filter="buy_tracker",
            context_filter="purchase_event",
            time_filter="month",  # Last month
        )

        # Parse SOL amounts from context for sorting
        for result in results:
            context_str = result.get("context", "")

            try:
                # Extract SOL amount (format: "...sol:{amount}...")
                if "sol:" in context_str:
                    sol_str = context_str.split("sol:")[1].split("|")[0]
                    result["purchase_amount_sol"] = float(sol_str)
                else:
                    result["purchase_amount_sol"] = 0.0
            except (ValueError, IndexError):
                result["purchase_amount_sol"] = 0.0

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return results

    except Exception as e:
        logger.error(f"Failed to recall purchase history: {e}")
        return []


async def get_token_buy_stats(
    token_symbol: str,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Get aggregated buy statistics for a token.

    Args:
        token_symbol: Token ticker symbol
        days: Lookback period in days

    Returns:
        {
            "total_purchases": int,
            "total_sol_volume": float,
            "unique_buyers": int,
            "avg_purchase_size": float,
            "largest_purchase": float,
        }

    Example:
        stats = await get_token_buy_stats("KR8TIV", days=7)
        print(f"Total purchases: {stats['total_purchases']}")
        print(f"Total volume: {stats['total_sol_volume']:.2f} SOL")
    """
    if not BUY_TRACKER_MEMORY_ENABLED:
        logger.debug("Buy Tracker memory disabled, returning empty stats")
        return {
            "total_purchases": 0,
            "total_sol_volume": 0.0,
            "unique_buyers": 0,
            "avg_purchase_size": 0.0,
            "largest_purchase": 0.0,
        }

    try:
        # Get purchase history
        purchases = await recall_purchase_history(token_symbol=token_symbol, k=200)

        if not purchases:
            return {
                "total_purchases": 0,
                "total_sol_volume": 0.0,
                "unique_buyers": 0,
                "avg_purchase_size": 0.0,
                "largest_purchase": 0.0,
            }

        # Extract metrics
        sol_amounts = []
        unique_buyers_set = set()

        for purchase in purchases:
            sol_amount = purchase.get("purchase_amount_sol", 0.0)
            if sol_amount > 0:
                sol_amounts.append(sol_amount)

            # Extract buyer from content
            content = purchase.get("content", "")
            if "Buyer:" in content:
                try:
                    buyer = content.split("Buyer:")[1].strip().split("\n")[0].strip()
                    unique_buyers_set.add(buyer)
                except (IndexError, AttributeError):
                    pass

        # Calculate stats
        total_purchases = len(sol_amounts)
        total_sol_volume = sum(sol_amounts)
        unique_buyers = len(unique_buyers_set)
        avg_purchase_size = total_sol_volume / total_purchases if total_purchases > 0 else 0.0
        largest_purchase = max(sol_amounts) if sol_amounts else 0.0

        return {
            "total_purchases": total_purchases,
            "total_sol_volume": total_sol_volume,
            "unique_buyers": unique_buyers,
            "avg_purchase_size": avg_purchase_size,
            "largest_purchase": largest_purchase,
        }

    except Exception as e:
        logger.error(f"Failed to get token buy stats: {e}")
        return {
            "total_purchases": 0,
            "total_sol_volume": 0.0,
            "unique_buyers": 0,
            "avg_purchase_size": 0.0,
            "largest_purchase": 0.0,
        }
