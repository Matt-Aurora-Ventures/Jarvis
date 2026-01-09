"""
Scheduler for Self-Improving Tasks.

Handles scheduled operations:
- Nightly reflection cycle (3am)
- Proactive suggestion checks (every 15 min when active)
- Prediction resolution (daily)
- Reflection consolidation (weekly)

Uses APScheduler for background task execution.
"""

import logging
from datetime import datetime, time
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("jarvis.scheduler")

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed - scheduling features disabled")


class SelfImprovingScheduler:
    """
    Scheduler for self-improving background tasks.

    Usage:
        scheduler = SelfImprovingScheduler(orchestrator)
        scheduler.start()

        # Later
        scheduler.stop()
    """

    def __init__(
        self,
        orchestrator,  # SelfImprovingOrchestrator
        use_async: bool = False,
    ):
        self.orchestrator = orchestrator
        self.use_async = use_async
        self._scheduler = None
        self._running = False

        if not APSCHEDULER_AVAILABLE:
            logger.warning("APScheduler not available - using manual scheduling")

    def _get_scheduler(self):
        """Get or create scheduler instance."""
        if self._scheduler is None:
            if APSCHEDULER_AVAILABLE:
                if self.use_async:
                    self._scheduler = AsyncIOScheduler()
                else:
                    self._scheduler = BackgroundScheduler()
            else:
                self._scheduler = ManualScheduler()
        return self._scheduler

    def start(self):
        """Start the scheduler with default jobs."""
        scheduler = self._get_scheduler()

        if APSCHEDULER_AVAILABLE:
            # Nightly reflection at 3am
            scheduler.add_job(
                self._run_nightly_reflection,
                CronTrigger(hour=3, minute=0),
                id="nightly_reflection",
                replace_existing=True,
            )

            # Proactive check every 15 minutes during active hours (9am-10pm)
            scheduler.add_job(
                self._run_proactive_check,
                CronTrigger(
                    minute="*/15",
                    hour="9-22",
                ),
                id="proactive_check",
                replace_existing=True,
            )

            # Weekly reflection consolidation on Sunday at 4am
            scheduler.add_job(
                self._run_consolidation,
                CronTrigger(day_of_week="sun", hour=4),
                id="weekly_consolidation",
                replace_existing=True,
            )

            scheduler.start()
            self._running = True
            logger.info("Self-improving scheduler started")

        else:
            logger.info("Running in manual scheduling mode")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler and APSCHEDULER_AVAILABLE:
            self._scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")

    def _run_nightly_reflection(self):
        """Run nightly reflection cycle."""
        logger.info("Running scheduled nightly reflection")
        try:
            result = self.orchestrator.run_nightly_cycle_sync()
            logger.info(f"Nightly reflection complete: {result}")
        except Exception as e:
            logger.error(f"Nightly reflection failed: {e}")

    async def _run_nightly_reflection_async(self):
        """Async version of nightly reflection."""
        logger.info("Running scheduled nightly reflection (async)")
        try:
            result = await self.orchestrator.run_nightly_cycle()
            logger.info(f"Nightly reflection complete: {result}")
        except Exception as e:
            logger.error(f"Nightly reflection failed: {e}")

    def _run_proactive_check(self):
        """Run proactive suggestion check."""
        # Get current context (simplified - in real use, gather more context)
        context = {
            "time": datetime.utcnow().isoformat(),
            "day_of_week": datetime.utcnow().strftime("%A"),
            "hour": datetime.utcnow().hour,
        }

        try:
            suggestion = self.orchestrator.proactive.check_for_suggestion_sync(context)
            if suggestion:
                logger.info(f"Proactive suggestion generated: {suggestion.message[:50]}...")
                # In real implementation, would notify user via Telegram/etc.
        except Exception as e:
            logger.error(f"Proactive check failed: {e}")

    def _run_consolidation(self):
        """Run weekly reflection consolidation."""
        logger.info("Running weekly reflection consolidation")
        # This would call orchestrator.reflexion.consolidate_reflections()
        # Simplified for now

    def trigger_nightly_now(self) -> Dict[str, Any]:
        """Manually trigger nightly cycle (for testing)."""
        return self.orchestrator.run_nightly_cycle_sync()

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        status = {
            "running": self._running,
            "apscheduler_available": APSCHEDULER_AVAILABLE,
        }

        if self._scheduler and APSCHEDULER_AVAILABLE:
            jobs = self._scheduler.get_jobs()
            status["jobs"] = [
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs
            ]

        return status


class ManualScheduler:
    """
    Fallback scheduler when APScheduler is not available.
    Requires manual triggering of tasks.
    """

    def __init__(self):
        self.jobs = {}

    def add_job(self, func: Callable, trigger, id: str, **kwargs):
        self.jobs[id] = {"func": func, "trigger": str(trigger)}

    def start(self):
        logger.info("Manual scheduler started (no automatic execution)")

    def shutdown(self):
        logger.info("Manual scheduler stopped")

    def get_jobs(self):
        return []


def create_scheduler(orchestrator, start: bool = True) -> SelfImprovingScheduler:
    """Create and optionally start a scheduler."""
    scheduler = SelfImprovingScheduler(orchestrator)
    if start:
        scheduler.start()
    return scheduler
