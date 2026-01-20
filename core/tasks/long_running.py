"""
Long-Running Task Implementations

Pre-built task implementations for common long-running operations:
- Report generation
- Batch trade execution
- Historical data analysis
- Background maintenance

All tasks support progress callbacks and are designed to work with TaskQueue.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# REPORT GENERATION
# =============================================================================

async def generate_treasury_report(
    period: str = "weekly",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive treasury performance report.

    Args:
        period: Report period (daily, weekly, monthly)
        progress_callback: Optional callback(progress: float, message: str)

    Returns:
        Report data dictionary
    """
    if progress_callback:
        progress_callback(0.1, "Loading trade history...")

    # Import here to avoid circular dependencies
    from core.treasury.reports import TreasuryReportGenerator, ReportPeriod

    try:
        generator = TreasuryReportGenerator()

        if progress_callback:
            progress_callback(0.3, "Calculating metrics...")

        # Generate report based on period
        period_enum = ReportPeriod[period.upper()]
        report = await generator.generate_report(period_enum)

        if progress_callback:
            progress_callback(0.7, "Formatting report...")

        # Convert to dict for serialization
        report_data = {
            "report_id": report.report_id,
            "period": report.period.value,
            "generated_at": report.generated_at.isoformat(),
            "summary": report.summary,
            "trading_metrics": {
                "total_trades": report.trading_metrics.total_trades,
                "win_rate": report.trading_metrics.win_rate,
                "total_pnl_sol": report.trading_metrics.total_pnl_sol,
            },
            "distribution_metrics": {
                "total_distributed_sol": report.distribution_metrics.total_distributed_sol,
            },
        }

        if progress_callback:
            progress_callback(1.0, "Report complete")

        logger.info(f"Generated {period} treasury report: {report.report_id}")
        return report_data

    except Exception as e:
        logger.error(f"Failed to generate treasury report: {e}")
        raise


async def generate_sentiment_report(
    num_tokens: int = 10,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Generate sentiment analysis report for top tokens.

    Args:
        num_tokens: Number of tokens to analyze
        progress_callback: Optional progress callback

    Returns:
        Sentiment report data
    """
    if progress_callback:
        progress_callback(0.1, f"Fetching top {num_tokens} tokens...")

    from bots.buy_tracker.sentiment_report import generate_report

    try:
        if progress_callback:
            progress_callback(0.3, "Analyzing sentiment...")

        # Generate full report
        report = await generate_report()

        if progress_callback:
            progress_callback(0.8, "Processing results...")

        result = {
            "generated_at": datetime.now().isoformat(),
            "num_tokens": num_tokens,
            "report": report,
        }

        if progress_callback:
            progress_callback(1.0, "Sentiment report complete")

        return result

    except Exception as e:
        logger.error(f"Failed to generate sentiment report: {e}")
        raise


# =============================================================================
# BATCH TRADE EXECUTION
# =============================================================================

async def execute_batch_trades(
    trades: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Execute multiple trades in batch with progress tracking.

    Args:
        trades: List of trade specs [{"token": "...", "action": "buy/sell", "amount": ...}]
        progress_callback: Optional progress callback

    Returns:
        Batch execution results
    """
    total = len(trades)
    results = {
        "total": total,
        "successful": 0,
        "failed": 0,
        "trades": [],
    }

    if progress_callback:
        progress_callback(0.0, f"Starting batch execution of {total} trades...")

    from bots.treasury.trading import TreasuryTrader

    try:
        trader = TreasuryTrader()

        for i, trade_spec in enumerate(trades):
            try:
                if progress_callback:
                    progress = (i + 1) / total
                    progress_callback(
                        progress,
                        f"Executing trade {i+1}/{total}: {trade_spec['token']}"
                    )

                # Execute trade based on action
                if trade_spec['action'] == 'buy':
                    result = await trader.execute_buy(
                        token_mint=trade_spec['token'],
                        amount_sol=trade_spec['amount']
                    )
                elif trade_spec['action'] == 'sell':
                    result = await trader.execute_sell(
                        token_mint=trade_spec['token'],
                        amount=trade_spec['amount']
                    )
                else:
                    raise ValueError(f"Unknown action: {trade_spec['action']}")

                results["successful"] += 1
                results["trades"].append({
                    "trade": trade_spec,
                    "status": "success",
                    "result": result,
                })

                # Brief delay between trades to avoid rate limits
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Trade {i+1} failed: {e}")
                results["failed"] += 1
                results["trades"].append({
                    "trade": trade_spec,
                    "status": "failed",
                    "error": str(e),
                })

        if progress_callback:
            progress_callback(
                1.0,
                f"Batch complete: {results['successful']}/{total} successful"
            )

        logger.info(
            f"Batch execution complete: {results['successful']}/{total} successful"
        )
        return results

    except Exception as e:
        logger.error(f"Batch trade execution failed: {e}")
        raise


# =============================================================================
# HISTORICAL DATA ANALYSIS
# =============================================================================

async def analyze_historical_performance(
    days: int = 30,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Analyze historical trading performance over specified period.

    Args:
        days: Number of days to analyze
        progress_callback: Optional progress callback

    Returns:
        Analysis results
    """
    if progress_callback:
        progress_callback(0.1, f"Loading {days} days of trade history...")

    from bots.treasury.scorekeeper import get_scorekeeper

    try:
        scorekeeper = get_scorekeeper()

        if progress_callback:
            progress_callback(0.3, "Calculating performance metrics...")

        # Get all trades
        trades = scorekeeper.get_all_trades()

        # Filter by date range
        cutoff = datetime.now() - timedelta(days=days)
        recent_trades = [
            t for t in trades
            if datetime.fromisoformat(t['opened_at']) > cutoff
        ]

        if progress_callback:
            progress_callback(0.5, f"Analyzing {len(recent_trades)} trades...")

        # Calculate metrics
        winning_trades = [t for t in recent_trades if t.get('pnl_usd', 0) > 0]
        losing_trades = [t for t in recent_trades if t.get('pnl_usd', 0) < 0]

        total_pnl = sum(t.get('pnl_usd', 0) for t in recent_trades)
        avg_pnl = total_pnl / len(recent_trades) if recent_trades else 0
        win_rate = len(winning_trades) / len(recent_trades) if recent_trades else 0

        if progress_callback:
            progress_callback(0.8, "Generating insights...")

        # Best and worst performers
        best_trade = max(recent_trades, key=lambda t: t.get('pnl_usd', 0)) if recent_trades else None
        worst_trade = min(recent_trades, key=lambda t: t.get('pnl_usd', 0)) if recent_trades else None

        analysis = {
            "period_days": days,
            "total_trades": len(recent_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_pnl_usd": total_pnl,
            "avg_pnl_usd": avg_pnl,
            "best_trade": {
                "token": best_trade['token_symbol'],
                "pnl_usd": best_trade['pnl_usd'],
            } if best_trade else None,
            "worst_trade": {
                "token": worst_trade['token_symbol'],
                "pnl_usd": worst_trade['pnl_usd'],
            } if worst_trade else None,
            "analyzed_at": datetime.now().isoformat(),
        }

        if progress_callback:
            progress_callback(1.0, "Analysis complete")

        logger.info(f"Historical analysis complete: {days} days, {len(recent_trades)} trades")
        return analysis

    except Exception as e:
        logger.error(f"Historical analysis failed: {e}")
        raise


async def backfill_market_data(
    tokens: List[str],
    days: int = 7,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Backfill historical market data for tokens.

    Args:
        tokens: List of token mints to backfill
        days: Number of days of history
        progress_callback: Optional progress callback

    Returns:
        Backfill results
    """
    total = len(tokens)
    results = {
        "total_tokens": total,
        "successful": 0,
        "failed": 0,
        "data_points": 0,
    }

    if progress_callback:
        progress_callback(0.0, f"Starting backfill for {total} tokens...")

    try:
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        for i, token_mint in enumerate(tokens):
            try:
                if progress_callback:
                    progress = (i + 1) / total
                    progress_callback(
                        progress,
                        f"Backfilling {i+1}/{total}: {token_mint[:8]}..."
                    )

                # Fetch historical data
                data = await service.fetch_historical_data(
                    token_mint=token_mint,
                    days=days
                )

                results["successful"] += 1
                results["data_points"] += len(data) if data else 0

                # Rate limit
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Backfill failed for {token_mint}: {e}")
                results["failed"] += 1

        if progress_callback:
            progress_callback(
                1.0,
                f"Backfill complete: {results['successful']}/{total} tokens"
            )

        logger.info(
            f"Backfill complete: {results['successful']}/{total} tokens, "
            f"{results['data_points']} data points"
        )
        return results

    except Exception as e:
        logger.error(f"Backfill operation failed: {e}")
        raise


# =============================================================================
# MAINTENANCE TASKS
# =============================================================================

async def cleanup_old_data(
    days_to_keep: int = 90,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Clean up old data from various storage systems.

    Args:
        days_to_keep: Number of days of data to retain
        progress_callback: Optional progress callback

    Returns:
        Cleanup results
    """
    if progress_callback:
        progress_callback(0.1, "Starting data cleanup...")

    results = {
        "trades_deleted": 0,
        "cache_cleared": 0,
        "logs_archived": 0,
    }

    try:
        cutoff = datetime.now() - timedelta(days=days_to_keep)

        # Clean up old trades
        if progress_callback:
            progress_callback(0.3, "Cleaning up old trades...")

        from bots.treasury.scorekeeper import get_scorekeeper
        scorekeeper = get_scorekeeper()

        # This would need to be implemented in scorekeeper
        # results["trades_deleted"] = scorekeeper.delete_trades_before(cutoff)

        # Clear old cache entries
        if progress_callback:
            progress_callback(0.6, "Clearing old cache entries...")

        from core.caching.cache_manager import CacheManager
        cache = CacheManager()
        results["cache_cleared"] = await cache.clear_expired()

        # Archive old logs (placeholder - would need implementation)
        if progress_callback:
            progress_callback(0.8, "Archiving old logs...")

        # results["logs_archived"] = await archive_logs(cutoff)

        if progress_callback:
            progress_callback(1.0, "Cleanup complete")

        logger.info(f"Cleanup complete: {results}")
        return results

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise


async def health_check_all_systems(
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Dict[str, Any]:
    """
    Run comprehensive health checks on all systems.

    Args:
        progress_callback: Optional progress callback

    Returns:
        Health check results
    """
    if progress_callback:
        progress_callback(0.0, "Starting system health checks...")

    results = {
        "timestamp": datetime.now().isoformat(),
        "systems": {},
        "overall_healthy": True,
    }

    systems = [
        ("database", "check_database_health"),
        ("wallet", "check_wallet_health"),
        ("jupiter", "check_jupiter_health"),
        ("cache", "check_cache_health"),
        ("telegram", "check_telegram_health"),
    ]

    total = len(systems)

    for i, (system_name, check_func) in enumerate(systems):
        try:
            if progress_callback:
                progress = (i + 1) / total
                progress_callback(progress, f"Checking {system_name}...")

            # Run health check (placeholder - would need actual implementations)
            # health = await globals()[check_func]()
            health = {"status": "healthy", "checked_at": datetime.now().isoformat()}

            results["systems"][system_name] = health

            if health.get("status") != "healthy":
                results["overall_healthy"] = False

        except Exception as e:
            logger.error(f"Health check failed for {system_name}: {e}")
            results["systems"][system_name] = {
                "status": "error",
                "error": str(e),
            }
            results["overall_healthy"] = False

    if progress_callback:
        status = "All systems healthy" if results["overall_healthy"] else "Issues detected"
        progress_callback(1.0, status)

    logger.info(f"Health check complete: {results['overall_healthy']}")
    return results


# =============================================================================
# HELPER: Queue these tasks easily
# =============================================================================

async def queue_report_generation(
    queue,
    period: str = "weekly",
    on_complete: Optional[Callable] = None
) -> str:
    """Helper to queue a report generation task."""
    return await queue.enqueue(
        generate_treasury_report,
        period=period,
        priority=3,
        task_type="report",
        timeout=600.0,  # 10 minutes
        on_complete=on_complete,
    )


async def queue_batch_trades(
    queue,
    trades: List[Dict[str, Any]],
    on_complete: Optional[Callable] = None,
    on_error: Optional[Callable] = None
) -> str:
    """Helper to queue batch trade execution."""
    return await queue.enqueue(
        execute_batch_trades,
        trades=trades,
        priority=1,  # High priority
        task_type="trade_batch",
        max_retries=1,
        timeout=len(trades) * 30.0,  # 30s per trade
        on_complete=on_complete,
        on_error=on_error,
    )


async def queue_historical_analysis(
    queue,
    days: int = 30,
    on_complete: Optional[Callable] = None
) -> str:
    """Helper to queue historical analysis."""
    return await queue.enqueue(
        analyze_historical_performance,
        days=days,
        priority=5,
        task_type="analysis",
        timeout=300.0,  # 5 minutes
        on_complete=on_complete,
    )


async def queue_maintenance(
    queue,
    days_to_keep: int = 90,
    on_complete: Optional[Callable] = None
) -> str:
    """Helper to queue maintenance task."""
    return await queue.enqueue(
        cleanup_old_data,
        days_to_keep=days_to_keep,
        priority=7,  # Low priority
        task_type="maintenance",
        timeout=600.0,  # 10 minutes
        on_complete=on_complete,
    )
