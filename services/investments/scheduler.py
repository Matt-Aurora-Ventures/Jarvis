"""Scheduler — APScheduler jobs for daily cycle, NAV snapshots, and reflection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from services.investments.orchestrator import Orchestrator

logger = logging.getLogger("investments.scheduler")


def create_scheduler(orchestrator: Orchestrator) -> AsyncIOScheduler:
    """Build and return the APScheduler with all investment jobs."""

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Daily investment cycle at 00:00 UTC
    scheduler.add_job(
        _run_cycle,
        trigger=CronTrigger(hour=0, minute=0),
        args=[orchestrator],
        id="daily_investment_cycle",
        name="Daily Investment Cycle",
        max_instances=1,
        misfire_grace_time=3600,
    )

    # NAV snapshot every 15 minutes
    scheduler.add_job(
        _snapshot_nav,
        trigger=IntervalTrigger(minutes=15),
        args=[orchestrator],
        id="nav_snapshot",
        name="NAV Snapshot (15m)",
        max_instances=1,
    )

    # Reflection check every hour — looks for decisions older than 24h without reflections
    scheduler.add_job(
        _run_reflections,
        trigger=IntervalTrigger(hours=1),
        args=[orchestrator],
        id="reflection_check",
        name="Reflection Check (1h)",
        max_instances=1,
    )

    # Bridge fee check every 6 hours
    scheduler.add_job(
        _check_bridge,
        trigger=IntervalTrigger(hours=6),
        args=[orchestrator],
        id="bridge_fee_check",
        name="Bridge Fee Check (6h)",
        max_instances=1,
    )

    # Advance pending bridge jobs every 30 seconds
    scheduler.add_job(
        _advance_bridges,
        trigger=IntervalTrigger(seconds=30),
        args=[orchestrator],
        id="bridge_advance",
        name="Bridge Advance (30s)",
        max_instances=1,
    )

    # Staking deposit check every hour
    scheduler.add_job(
        _staking_deposit,
        trigger=IntervalTrigger(hours=1),
        args=[orchestrator],
        id="staking_deposit",
        name="Staking Deposit (1h)",
        max_instances=1,
    )

    logger.info("Scheduler created with %d jobs", len(scheduler.get_jobs()) if hasattr(scheduler, 'get_jobs') else 6)
    return scheduler


async def _run_cycle(orchestrator: Orchestrator) -> None:
    """Wrapper for the daily investment cycle."""
    try:
        result = await orchestrator.run_cycle()
        logger.info("Daily cycle result: %s", result.get("status"))
    except Exception:
        logger.exception("Daily investment cycle failed")


async def _snapshot_nav(orchestrator: Orchestrator) -> None:
    """Write NAV snapshot to time-series table."""
    try:
        await orchestrator.snapshot_nav()
    except Exception:
        logger.exception("NAV snapshot failed")


async def _run_reflections(orchestrator: Orchestrator) -> None:
    """Find unreflected decisions older than 24h and run reflection on them."""
    try:
        rows = await orchestrator.db.fetch(
            """
            SELECT d.id FROM inv_decisions d
            LEFT JOIN inv_reflections r ON r.decision_id = d.id
            WHERE r.id IS NULL
              AND d.created_at < NOW() - INTERVAL '24 hours'
              AND d.created_at > NOW() - INTERVAL '72 hours'
            ORDER BY d.created_at ASC
            LIMIT 5
            """
        )
        for row in rows:
            result = await orchestrator.reflection.run_reflection(row["id"])
            logger.info("Reflection for decision %d: %s", row["id"], result.get("status"))
    except Exception:
        logger.exception("Reflection check failed")


async def _check_bridge(orchestrator: Orchestrator) -> None:
    """Check if collected fees should be bridged to Solana."""
    try:
        job_id = await orchestrator.check_and_bridge_fees()
        if job_id:
            logger.info("Bridge job started: %d", job_id)
    except Exception:
        logger.exception("Bridge fee check failed")


async def _advance_bridges(orchestrator: Orchestrator) -> None:
    """Advance any pending bridge jobs through their state machine."""
    try:
        results = await orchestrator.advance_bridge_jobs()
        for r in results:
            logger.info("Bridge job %s → %s", r.get("id"), r.get("state"))
    except Exception:
        logger.exception("Bridge advance failed")


async def _staking_deposit(orchestrator: Orchestrator) -> None:
    """Deposit pending USDC to staking reward pool."""
    try:
        result = await orchestrator.run_staking_deposit()
        if result.get("deposited"):
            logger.info("Staking deposit: %s", result)
    except Exception:
        logger.exception("Staking deposit failed")
