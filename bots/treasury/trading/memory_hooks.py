"""
Treasury Memory Integration

Hooks for storing trade outcomes and recalling historical performance.
Integrates with core.memory for persistent learning across trading sessions.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from core.async_utils import fire_and_forget, TaskTracker
from core.memory import retain_fact, recall

logger = logging.getLogger(__name__)

# Module-level task tracker for memory operations
_memory_tracker = TaskTracker("treasury_memory")

# Environment flag to enable/disable memory integration
TREASURY_MEMORY_ENABLED = os.getenv("TREASURY_MEMORY_ENABLED", "true").lower() == "true"


async def store_trade_outcome(
    token_symbol: str,
    token_mint: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    hold_duration_hours: float,
    strategy: str,
    sentiment_score: Optional[float] = None,
    exit_reason: str = "manual",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Store trade outcome in memory.

    Creates a fact with full trade context for future recall and learning.

    Args:
        token_symbol: Token symbol (e.g., 'KR8TIV')
        token_mint: Token mint address
        entry_price: Entry price in USD
        exit_price: Exit price in USD
        pnl_pct: Profit/loss percentage
        hold_duration_hours: How long position was held
        strategy: Trading strategy used
        sentiment_score: Optional sentiment score (0-1)
        exit_reason: Why position was closed ('manual', 'take_profit', 'stop_loss', 'trailing_stop')
        metadata: Additional trade metadata

    Returns:
        Fact ID from memory system
    """
    if not TREASURY_MEMORY_ENABLED:
        logger.debug("Treasury memory disabled - skipping store_trade_outcome")
        return -1

    try:
        # Ensure strategy entity exists
        await ensure_strategy_entity(strategy)

        # Build human-readable content
        outcome = "WIN" if pnl_pct > 0 else "LOSS"
        content = (
            f"{outcome}: {token_symbol} trade closed "
            f"[{entry_price:.6f} → {exit_price:.6f}] "
            f"P&L: {pnl_pct:+.2f}% "
            f"({hold_duration_hours:.1f}h hold) "
            f"Strategy: {strategy} "
            f"Exit: {exit_reason}"
        )

        if sentiment_score is not None:
            content += f" | Sentiment: {sentiment_score:.2f}"

        # Context for filtering
        context = f"trade_outcome|{token_mint}"

        # Entities to track
        entities = [f"@{token_symbol}", strategy]

        # Build metadata
        full_metadata = {
            "token_symbol": token_symbol,
            "token_mint": token_mint,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "hold_duration_hours": hold_duration_hours,
            "strategy": strategy,
            "sentiment_score": sentiment_score,
            "exit_reason": exit_reason,
            "outcome": outcome,
        }

        if metadata:
            full_metadata.update(metadata)

        # Store in memory (sync operation - run in thread pool)
        fact_id = await asyncio.to_thread(
            retain_fact,
            content=content,
            context=context,
            entities=entities,
            source="treasury",
            confidence=1.0,
            auto_extract_entities=False,  # We provide explicit entities
        )

        logger.info(f"Stored trade outcome for {token_symbol}: fact_id={fact_id}")
        return fact_id

    except Exception as e:
        logger.error(f"Failed to store trade outcome for {token_symbol}: {e}")
        return -1


def store_trade_outcome_async(
    token_symbol: str,
    token_mint: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    hold_duration_hours: float,
    strategy: str,
    sentiment_score: Optional[float] = None,
    exit_reason: str = "manual",
    metadata: Optional[Dict[str, Any]] = None,
) -> asyncio.Task:
    """
    Fire-and-forget wrapper for store_trade_outcome.

    Use this in trading operations to avoid blocking on memory writes.

    Returns:
        Background task (can be ignored)
    """
    return fire_and_forget(
        store_trade_outcome(
            token_symbol=token_symbol,
            token_mint=token_mint,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            hold_duration_hours=hold_duration_hours,
            strategy=strategy,
            sentiment_score=sentiment_score,
            exit_reason=exit_reason,
            metadata=metadata,
        ),
        name=f"store_trade_{token_symbol}",
        tracker=_memory_tracker,
    )


async def recall_token_history(
    token_symbol: str,
    k: int = 20,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """
    Recall past trades for a specific token.

    Args:
        token_symbol: Token symbol to search for
        k: Maximum results to return
        days: Look back this many days

    Returns:
        List of past trade outcomes sorted by date desc
    """
    if not TREASURY_MEMORY_ENABLED:
        logger.debug("Treasury memory disabled - skipping recall_token_history")
        return []

    try:
        # Determine time filter based on days
        if days <= 1:
            time_filter = "today"
        elif days <= 7:
            time_filter = "week"
        elif days <= 30:
            time_filter = "month"
        elif days <= 90:
            time_filter = "quarter"
        else:
            time_filter = "year"

        # Query memory
        results = await recall(
            query=f"{token_symbol} trade",
            k=k,
            time_filter=time_filter,
            source_filter="treasury",
            context_filter="trade_outcome",
        )

        logger.debug(f"Recalled {len(results)} trades for {token_symbol}")
        return results

    except Exception as e:
        logger.error(f"Failed to recall token history for {token_symbol}: {e}")
        return []


async def should_enter_based_on_history(
    token_symbol: str,
    min_win_rate: float = 0.3,
    min_trades: int = 3,
) -> Tuple[bool, str]:
    """
    Check if historical performance supports entering this token.

    Args:
        token_symbol: Token to check
        min_win_rate: Minimum acceptable win rate (default 30%)
        min_trades: Minimum trade count to have confidence (default 3)

    Returns:
        (should_enter, reason) tuple
        - should_enter: True if history supports entry (or no history exists)
        - reason: Human-readable explanation
    """
    if not TREASURY_MEMORY_ENABLED:
        return True, "Memory disabled - proceeding without history check"

    try:
        history = await recall_token_history(token_symbol, k=50, days=90)

        if len(history) < min_trades:
            return True, f"New/untested token - only {len(history)} prior trades"

        # Parse outcomes from history
        wins = 0
        losses = 0

        for trade in history:
            content = trade.get("content", "")
            if "WIN:" in content:
                wins += 1
            elif "LOSS:" in content:
                losses += 1

        total = wins + losses
        if total == 0:
            return True, "No historical data found"

        win_rate = wins / total

        if win_rate < min_win_rate:
            return False, f"Low win rate: {win_rate*100:.0f}% ({wins}W/{losses}L)"

        return True, f"Good history: {win_rate*100:.0f}% wins ({wins}W/{losses}L)"

    except Exception as e:
        logger.error(f"Failed to check history for {token_symbol}: {e}")
        return True, f"History check failed: {e}"


async def get_strategy_performance(
    strategy: str,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Get performance metrics for a trading strategy.

    Args:
        strategy: Strategy name (e.g., 'momentum', 'bags_graduation')
        days: Look back this many days

    Returns:
        Dict with performance metrics:
        - strategy: str
        - trade_count: int
        - win_count: int
        - win_rate: float
        - avg_pnl: float
        - total_pnl: float
    """
    if not TREASURY_MEMORY_ENABLED:
        return {
            "strategy": strategy,
            "trade_count": 0,
            "win_count": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_pnl": 0.0,
        }

    try:
        # Determine time filter
        if days <= 7:
            time_filter = "week"
        elif days <= 30:
            time_filter = "month"
        elif days <= 90:
            time_filter = "quarter"
        else:
            time_filter = "year"

        # Query for this strategy
        results = await recall(
            query=f"Strategy: {strategy}",
            k=1000,  # Get all trades for this strategy
            time_filter=time_filter,
            source_filter="treasury",
            context_filter="trade_outcome",
        )

        # Calculate metrics
        wins = 0
        total_pnl = 0.0
        trade_count = 0

        for trade in results:
            content = trade.get("content", "")

            if "WIN:" in content:
                wins += 1
                trade_count += 1
            elif "LOSS:" in content:
                trade_count += 1

            # Try to extract P&L from content
            # Format: "P&L: +15.50%"
            try:
                if "P&L:" in content:
                    pnl_part = content.split("P&L:")[1].split("%")[0].strip()
                    pnl_value = float(pnl_part)
                    total_pnl += pnl_value
            except (IndexError, ValueError):
                pass

        win_rate = (wins / trade_count * 100) if trade_count > 0 else 0.0
        avg_pnl = (total_pnl / trade_count) if trade_count > 0 else 0.0

        return {
            "strategy": strategy,
            "trade_count": trade_count,
            "win_count": wins,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
        }

    except Exception as e:
        logger.error(f"Failed to get strategy performance for {strategy}: {e}")
        return {
            "strategy": strategy,
            "trade_count": 0,
            "win_count": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "total_pnl": 0.0,
        }


async def list_all_strategies() -> List[Dict[str, Any]]:
    """
    List all trading strategies with performance metrics.

    Returns:
        List of strategy performance dicts
    """
    if not TREASURY_MEMORY_ENABLED:
        return []

    try:
        # Get all trade outcomes
        results = await recall(
            query="Strategy:",
            k=10000,  # Get all trades
            time_filter="all",
            source_filter="treasury",
            context_filter="trade_outcome",
        )

        # Extract unique strategies
        strategies = set()
        for trade in results:
            content = trade.get("content", "")
            # Parse "Strategy: {name}"
            if "Strategy:" in content:
                try:
                    strategy = content.split("Strategy:")[1].split()[0].strip()
                    strategies.add(strategy)
                except IndexError:
                    pass

        # Get performance for each strategy
        strategy_perfs = []
        for strategy in strategies:
            perf = await get_strategy_performance(strategy, days=90)
            strategy_perfs.append(perf)

        # Sort by trade count descending
        strategy_perfs.sort(key=lambda x: x["trade_count"], reverse=True)

        logger.info(f"Found {len(strategy_perfs)} strategies")
        return strategy_perfs

    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        return []


async def ensure_strategy_entity(strategy: str) -> None:
    """
    Ensure strategy entity exists in memory system.

    This is called automatically when storing trades.

    Args:
        strategy: Strategy name
    """
    if not TREASURY_MEMORY_ENABLED:
        return

    try:
        # Import here to avoid circular dependency
        from core.memory.entity_profiles import get_entity_profile, create_entity_profile

        # Check if strategy entity exists
        profile = await asyncio.to_thread(get_entity_profile, strategy)

        if not profile:
            # Create strategy entity
            await asyncio.to_thread(
                create_entity_profile,
                entity_name=strategy,
                entity_type="strategy",
                summary=f"Trading strategy: {strategy}",
            )
            logger.info(f"Created strategy entity: {strategy}")

    except Exception as e:
        logger.warning(f"Failed to ensure strategy entity for {strategy}: {e}")


async def get_all_strategies_summary() -> str:
    """
    Get human-readable summary of all strategy performance.

    Returns:
        Markdown-formatted summary suitable for Telegram/reporting
    """
    if not TREASURY_MEMORY_ENABLED:
        return "Treasury memory disabled - no strategy data available"

    try:
        strategies = await list_all_strategies()

        if not strategies:
            return "No strategy data available yet"

        # Build markdown table
        lines = ["**Strategy Performance Summary**\n"]
        lines.append("```")
        lines.append(f"{'Strategy':<20} {'Trades':>7} {'Wins':>5} {'WR%':>6} {'Avg PnL%':>9}")
        lines.append("-" * 60)

        for strat in strategies:
            lines.append(
                f"{strat['strategy']:<20} "
                f"{strat['trade_count']:>7} "
                f"{strat['win_count']:>5} "
                f"{strat['win_rate']:>6.1f} "
                f"{strat['avg_pnl']:>+9.2f}"
            )

        lines.append("```")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Failed to generate strategy summary: {e}")
        return f"Error generating summary: {e}"
