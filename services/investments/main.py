"""Entry point — starts orchestrator, scheduler, and FastAPI server."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
import uvicorn

from services.investments.config import InvestmentConfig
from services.investments.fallback_runtime import FallbackOrchestrator
from services.investments.orchestrator import Orchestrator
from services.investments.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("investments.main")


_REQUIRED_RUNTIME_SCHEMA: dict[str, set[str]] = {
    "inv_decisions": {
        "basket_id",
        "trigger_type",
        "previous_weights",
        "basket_nav_usd",
        "risk_approved",
        "trader_confidence",
        "trader_reasoning",
    },
    "inv_nav_snapshots": {"basket_id", "ts", "nav_usd"},
    "inv_reflections": {"decision_id", "data", "calibration_hint"},
    "inv_bridge_jobs": {"state", "amount_usdc", "amount_raw"},
}


async def _verify_schema_compatibility(conn: asyncpg.Connection) -> None:
    """Fail fast when an existing database is missing columns current code needs."""
    rows = await conn.fetch(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY($1::text[])
        """,
        list(_REQUIRED_RUNTIME_SCHEMA.keys()),
    )

    columns_by_table: dict[str, set[str]] = {}
    for row in rows:
        columns_by_table.setdefault(row["table_name"], set()).add(row["column_name"])

    problems: list[str] = []
    for table_name, required_columns in _REQUIRED_RUNTIME_SCHEMA.items():
        present = columns_by_table.get(table_name)
        if not present:
            problems.append(f"{table_name} table is missing")
            continue

        missing_columns = sorted(required_columns - present)
        if missing_columns:
            problems.append(
                f"{table_name} missing columns: {', '.join(missing_columns)}"
            )

    if problems:
        raise RuntimeError(
            "Investment schema incompatible with current runtime: "
            + "; ".join(problems)
        )


async def _init_db(cfg: InvestmentConfig) -> asyncpg.Pool:
    logger.info("Connecting to PostgreSQL: %s", cfg.database_url.split("@")[-1])
    pool = await asyncpg.create_pool(
        cfg.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    # Quick connectivity check
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    logger.info("PostgreSQL connected.")
    return pool


async def _init_redis(cfg: InvestmentConfig) -> aioredis.Redis:
    logger.info("Connecting to Redis: %s", cfg.redis_url)
    rds = aioredis.from_url(cfg.redis_url, decode_responses=True)
    await rds.ping()
    logger.info("Redis connected.")
    return rds


async def _run_migrations(pool: asyncpg.Pool) -> None:
    """Apply SQL migrations if tables don't exist yet."""
    from pathlib import Path

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        return

    async with pool.acquire() as conn:
        # Check if we've already migrated
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'inv_decisions')"
        )
        if exists:
            logger.info("Migrations already applied — skipping.")
            return

        for sql_file in sorted(migrations_dir.glob("*.sql")):
            logger.info("Applying migration: %s", sql_file.name)
            sql = sql_file.read_text()
            await conn.execute(sql)

        await _verify_schema_compatibility(conn)
        logger.info("All migrations applied.")


async def main() -> None:
    cfg = InvestmentConfig()

    # Validate config
    missing = cfg.validate()
    if missing:
        logger.error("Missing required config: %s", ", ".join(missing))
        logger.error("Set environment variables or use DRY_RUN=true for testing.")
        sys.exit(1)

    logger.info("=== Jarvis Investment Service ===")
    logger.info("Mode: %s", "DRY RUN" if cfg.dry_run else "LIVE")
    logger.info("Basket: %s", cfg.basket_id)

    db = None
    rds = None
    orchestrator: Orchestrator | FallbackOrchestrator
    fallback_mode = False

    # Initialize infrastructure. In dry-run we can fall back to in-memory mode
    # when DB/Redis are not reachable, which keeps the API contract alive.
    try:
        db = await _init_db(cfg)
        rds = await _init_redis(cfg)
        await _run_migrations(db)
        async with db.acquire() as conn:
            await _verify_schema_compatibility(conn)
        orchestrator = Orchestrator(cfg, db, rds)
    except Exception:
        if not cfg.dry_run:
            raise
        fallback_mode = True
        logger.warning(
            "Failed to initialize DB/Redis in dry-run mode; starting fallback runtime.",
            exc_info=True,
        )
        orchestrator = FallbackOrchestrator(cfg)

    # Wire up FastAPI dependencies
    from services.investments.api import app, set_dependencies
    set_dependencies(orchestrator, db, rds)

    # Start event monitor (Phase 2) — only in live mode
    event_monitor = None
    if (not fallback_mode) and (not cfg.dry_run) and cfg.basket_address:
        try:
            from services.investments.event_monitor import EventMonitor
            event_monitor = EventMonitor(cfg, db, rds)
            await event_monitor.start()
            logger.info("Event monitor started for basket %s", cfg.basket_address)
        except Exception:
            logger.warning("Event monitor failed to start (non-fatal)", exc_info=True)

    # Build scheduler
    scheduler = None
    if not fallback_mode:
        scheduler = create_scheduler(orchestrator)
        scheduler.start()
        logger.info("Scheduler started with %d jobs.", len(scheduler.get_jobs()))
        if not cfg.enable_bridge_automation:
            logger.warning("Bridge automation disabled until CCTP path is fully verified.")
        if not cfg.enable_staking_automation:
            logger.warning("Staking automation disabled until Solana deposit path is fully verified.")
    else:
        logger.warning("Fallback runtime active: scheduler disabled.")

    # Graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: int, _frame: object) -> None:
        logger.info("Received signal %d — shutting down...", sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Start uvicorn in a background task
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=cfg.api_port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())
    logger.info("API server starting on port %d", cfg.api_port)

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    if event_monitor:
        await event_monitor.stop()
    server.should_exit = True
    await server_task
    await orchestrator.close()
    if db is not None:
        await db.close()
    if rds is not None:
        await rds.aclose()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
