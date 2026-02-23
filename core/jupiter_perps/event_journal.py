"""Append-only event journal for Jupiter Perps execution.

Two-tier persistence:
    1. SQLite (WAL mode) — local to signer host, always available.
       Zero network dependency. This is the PRIMARY write tier.
    2. PostgreSQL — optional async replica for Zone B dashboards.
       If unreachable, the signer continues writing to SQLite.

On the signer host (Zone C), pass sqlite_path to get local persistence
even when PostgreSQL is down. On Zone B, pass dsn for Postgres and
optionally sqlite_path as a read cache.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
from enum import Enum
from typing import Any

log = logging.getLogger(__name__)

try:
    import psycopg
    from psycopg.rows import dict_row

    _HAS_PSYCOPG = True
except ImportError:
    _HAS_PSYCOPG = False

try:
    import aiosqlite

    _HAS_AIOSQLITE = True
except ImportError:
    _HAS_AIOSQLITE = False


class EventStatus(str, Enum):
    PENDING = "pending"
    SIMULATED = "simulated"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    SKIPPED = "skipped"


def _to_json(obj: Any) -> str:
    """Serialize dataclasses/enums to a deterministic JSON payload."""

    def default(value: Any) -> Any:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return dataclasses.asdict(value)
        if isinstance(value, Enum):
            return value.value
        raise TypeError(f"Cannot serialize {type(value)}")

    return json.dumps(obj, default=default, sort_keys=True)


class EventJournal:
    """Two-tier execution event store: SQLite primary, PostgreSQL replica."""

    def __init__(
        self,
        dsn: str,
        sqlite_path: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._sqlite_path = sqlite_path or os.environ.get(
            "PERPS_SQLITE_PATH", ""
        )
        self._pg: Any = None       # psycopg AsyncConnection
        self._sqlite: Any = None   # aiosqlite Connection

    @property
    def has_local(self) -> bool:
        return self._sqlite is not None

    @property
    def has_remote(self) -> bool:
        return self._pg is not None

    async def connect(self) -> None:
        # --- SQLite (primary) ---
        if _HAS_AIOSQLITE and self._sqlite_path:
            try:
                self._sqlite = await aiosqlite.connect(self._sqlite_path)
                await self._sqlite.execute("PRAGMA journal_mode=WAL")
                await self._sqlite.execute("PRAGMA synchronous=NORMAL")
                await self._sqlite.execute("PRAGMA busy_timeout=5000")
                self._sqlite.row_factory = aiosqlite.Row
                await self._ensure_sqlite_schema()
                log.info("EventJournal SQLite connected: %s", self._sqlite_path)
            except Exception:
                log.exception("SQLite connection failed — continuing without local store")
                self._sqlite = None
        elif self._sqlite_path and not _HAS_AIOSQLITE:
            log.warning("aiosqlite not installed — cannot use local SQLite journal")

        # --- PostgreSQL (replica) ---
        if _HAS_PSYCOPG and self._dsn:
            try:
                self._pg = await psycopg.AsyncConnection.connect(
                    self._dsn, row_factory=dict_row
                )
                await self._ensure_pg_schema()
                log.info("EventJournal PostgreSQL connected")
            except Exception:
                log.warning("PostgreSQL connection failed — using SQLite only")
                self._pg = None
        elif self._dsn and not _HAS_PSYCOPG:
            log.warning("psycopg not installed — PostgreSQL journal unavailable")

        if self._sqlite is None and self._pg is None:
            log.warning("EventJournal has NO persistence — running in memory-only mode")

    async def close(self) -> None:
        if self._sqlite is not None:
            await self._sqlite.close()
        if self._pg is not None:
            await self._pg.close()

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    async def _ensure_sqlite_schema(self) -> None:
        await self._sqlite.executescript(
            """
            CREATE TABLE IF NOT EXISTS execution_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT    NOT NULL UNIQUE,
                intent_type     TEXT    NOT NULL,
                status          TEXT    NOT NULL,
                intent_json     TEXT    NOT NULL,
                tx_signature    TEXT,
                slot            INTEGER,
                block_time      INTEGER,
                error_msg       TEXT,
                created_at      REAL    NOT NULL,
                updated_at      REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reconciliation_failures (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at     REAL    NOT NULL,
                chain_positions TEXT    NOT NULL,
                db_positions    TEXT    NOT NULL,
                discrepancies   TEXT    NOT NULL,
                resolved        INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS idempotency_log (
                idempotency_key TEXT PRIMARY KEY,
                processed_at    REAL    NOT NULL,
                outcome         TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_exec_events_status
                ON execution_events (status);
            CREATE INDEX IF NOT EXISTS idx_exec_events_created
                ON execution_events (created_at);
            """
        )
        await self._sqlite.commit()

    async def _ensure_pg_schema(self) -> None:
        async with self._pg.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_events (
                    id              BIGSERIAL PRIMARY KEY,
                    idempotency_key TEXT        NOT NULL UNIQUE,
                    intent_type     TEXT        NOT NULL,
                    status          TEXT        NOT NULL,
                    intent_json     JSONB       NOT NULL,
                    tx_signature    TEXT,
                    slot            BIGINT,
                    block_time      BIGINT,
                    error_msg       TEXT,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS reconciliation_failures (
                    id              BIGSERIAL PRIMARY KEY,
                    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    chain_positions JSONB       NOT NULL,
                    db_positions    JSONB       NOT NULL,
                    discrepancies   JSONB       NOT NULL,
                    resolved        BOOLEAN     NOT NULL DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS idempotency_log (
                    idempotency_key TEXT PRIMARY KEY,
                    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    outcome         TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_exec_events_status ON execution_events (status);
                CREATE INDEX IF NOT EXISTS idx_exec_events_created ON execution_events (created_at);
                """
            )
            await self._pg.commit()

    # ------------------------------------------------------------------
    # Internal helpers: write to SQLite then PostgreSQL
    # ------------------------------------------------------------------

    def _now(self) -> float:
        return time.time()

    async def _sqlite_exec(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute on SQLite, return cursor. Caller must commit."""
        if self._sqlite is None:
            return None
        return await self._sqlite.execute(sql, params)

    async def _pg_exec_safe(self, fn: Any) -> None:
        """Run a PostgreSQL operation, swallow errors so SQLite stays primary."""
        if self._pg is None:
            return
        try:
            await fn()
        except Exception:
            log.debug("PostgreSQL write failed — SQLite has the record", exc_info=True)

    # ------------------------------------------------------------------
    # Public API (unchanged interface, two-tier underneath)
    # ------------------------------------------------------------------

    async def log_intent(self, intent: Any) -> bool:
        """
        Insert a pending intent event.

        Returns True when inserted, False when the idempotency key already exists.
        """
        key = intent.idempotency_key
        intent_type = intent.intent_type.value
        status = EventStatus.PENDING.value
        intent_json = _to_json(intent)
        now = self._now()

        # --- SQLite (primary) ---
        if self._sqlite is not None:
            try:
                cursor = await self._sqlite.execute(
                    """
                    INSERT OR IGNORE INTO execution_events
                        (idempotency_key, intent_type, status, intent_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (key, intent_type, status, intent_json, now, now),
                )
                await self._sqlite.commit()
                inserted = (cursor.rowcount or 0) > 0
            except Exception:
                log.debug("SQLite log_intent failed", exc_info=True)
                inserted = True  # Assume insertable, let PG be the judge
        else:
            inserted = True  # No local store — assume new

        # --- PostgreSQL (replica) ---
        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO execution_events
                        (idempotency_key, intent_type, status, intent_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (key, intent_type, status, intent_json),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] log_intent type=%s key=%s", type(intent).__name__, key)

        return inserted

    async def log_rejected(self, intent: Any, reason: str) -> None:
        """Persist deterministic risk-gate rejection for observability."""
        key = intent.idempotency_key
        intent_type = intent.intent_type.value
        status = EventStatus.FAILED.value
        intent_json = _to_json(intent)
        reason_trunc = reason[:2000]
        now = self._now()

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    """
                    INSERT OR REPLACE INTO execution_events
                        (idempotency_key, intent_type, status, intent_json, error_msg,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, intent_type, status, intent_json, reason_trunc, now, now),
                )
                await self._sqlite.execute(
                    "INSERT OR IGNORE INTO idempotency_log (idempotency_key, processed_at, outcome) VALUES (?, ?, 'failed')",
                    (key, now),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite log_rejected failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO execution_events
                        (idempotency_key, intent_type, status, intent_json, error_msg)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (idempotency_key) DO UPDATE
                    SET status = EXCLUDED.status,
                        error_msg = EXCLUDED.error_msg,
                        updated_at = NOW()
                    """,
                    (key, intent_type, status, intent_json, reason_trunc),
                )
                await cur.execute(
                    "INSERT INTO idempotency_log (idempotency_key, outcome) VALUES (%s, 'failed') ON CONFLICT (idempotency_key) DO NOTHING",
                    (key,),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] log_rejected key=%s reason=%s", key, reason)

    async def mark_simulated(self, idempotency_key: str, note: str = "dry_run") -> None:
        now = self._now()
        note_trunc = note[:2000]

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    "UPDATE execution_events SET status = ?, error_msg = ?, updated_at = ? WHERE idempotency_key = ?",
                    (EventStatus.SIMULATED.value, note_trunc, now, idempotency_key),
                )
                await self._sqlite.execute(
                    "INSERT OR IGNORE INTO idempotency_log (idempotency_key, processed_at, outcome) VALUES (?, ?, 'simulated')",
                    (idempotency_key, now),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite mark_simulated failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    "UPDATE execution_events SET status = %s, error_msg = %s, updated_at = NOW() WHERE idempotency_key = %s",
                    (EventStatus.SIMULATED.value, note_trunc, idempotency_key),
                )
                await cur.execute(
                    "INSERT INTO idempotency_log (idempotency_key, outcome) VALUES (%s, 'simulated') ON CONFLICT (idempotency_key) DO NOTHING",
                    (idempotency_key,),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] mark_simulated key=%s", idempotency_key)

    async def mark_submitted(self, idempotency_key: str, tx_signature: str) -> None:
        now = self._now()

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    "UPDATE execution_events SET status = ?, tx_signature = ?, updated_at = ? WHERE idempotency_key = ?",
                    (EventStatus.SUBMITTED.value, tx_signature, now, idempotency_key),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite mark_submitted failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    "UPDATE execution_events SET status = %s, tx_signature = %s, updated_at = NOW() WHERE idempotency_key = %s",
                    (EventStatus.SUBMITTED.value, tx_signature, idempotency_key),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] mark_submitted key=%s sig=%s", idempotency_key, tx_signature)

    async def mark_confirmed(self, idempotency_key: str, slot: int, block_time: int) -> None:
        now = self._now()

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    "UPDATE execution_events SET status = ?, slot = ?, block_time = ?, updated_at = ? WHERE idempotency_key = ?",
                    (EventStatus.CONFIRMED.value, slot, block_time, now, idempotency_key),
                )
                await self._sqlite.execute(
                    "INSERT OR IGNORE INTO idempotency_log (idempotency_key, processed_at, outcome) VALUES (?, ?, 'executed')",
                    (idempotency_key, now),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite mark_confirmed failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    "UPDATE execution_events SET status = %s, slot = %s, block_time = %s, updated_at = NOW() WHERE idempotency_key = %s",
                    (EventStatus.CONFIRMED.value, slot, block_time, idempotency_key),
                )
                await cur.execute(
                    "INSERT INTO idempotency_log (idempotency_key, outcome) VALUES (%s, 'executed') ON CONFLICT (idempotency_key) DO NOTHING",
                    (idempotency_key,),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] mark_confirmed key=%s slot=%s", idempotency_key, slot)

    async def mark_failed(self, idempotency_key: str, error_msg: str) -> None:
        now = self._now()
        err = error_msg[:2000]

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    "UPDATE execution_events SET status = ?, error_msg = ?, updated_at = ? WHERE idempotency_key = ?",
                    (EventStatus.FAILED.value, err, now, idempotency_key),
                )
                await self._sqlite.execute(
                    "INSERT OR IGNORE INTO idempotency_log (idempotency_key, processed_at, outcome) VALUES (?, ?, 'failed')",
                    (idempotency_key, now),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite mark_failed failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    "UPDATE execution_events SET status = %s, error_msg = %s, updated_at = NOW() WHERE idempotency_key = %s",
                    (EventStatus.FAILED.value, err, idempotency_key),
                )
                await cur.execute(
                    "INSERT INTO idempotency_log (idempotency_key, outcome) VALUES (%s, 'failed') ON CONFLICT (idempotency_key) DO NOTHING",
                    (idempotency_key,),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] mark_failed key=%s error=%s", idempotency_key, error_msg)

    async def mark_skipped(self, idempotency_key: str) -> None:
        now = self._now()

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    "UPDATE execution_events SET status = ?, updated_at = ? WHERE idempotency_key = ?",
                    (EventStatus.SKIPPED.value, now, idempotency_key),
                )
                await self._sqlite.execute(
                    "INSERT OR IGNORE INTO idempotency_log (idempotency_key, processed_at, outcome) VALUES (?, ?, 'skipped_duplicate')",
                    (idempotency_key, now),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite mark_skipped failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    "UPDATE execution_events SET status = %s, updated_at = NOW() WHERE idempotency_key = %s",
                    (EventStatus.SKIPPED.value, idempotency_key),
                )
                await cur.execute(
                    "INSERT INTO idempotency_log (idempotency_key, outcome) VALUES (%s, 'skipped_duplicate') ON CONFLICT (idempotency_key) DO NOTHING",
                    (idempotency_key,),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.info("[MEMORY] mark_skipped key=%s", idempotency_key)

    async def get_projected_positions(self) -> list[dict]:
        """Replay confirmed/simulated events into a local projection.

        Reads from SQLite first (local truth), falls back to PostgreSQL.
        """
        rows: list[Any] = []

        if self._sqlite is not None:
            try:
                cursor = await self._sqlite.execute(
                    """
                    SELECT intent_json, tx_signature, slot, status
                    FROM execution_events
                    WHERE status IN ('confirmed', 'simulated')
                      AND intent_type IN ('open_position', 'reduce_position', 'close_position')
                    ORDER BY id ASC
                    """
                )
                raw_rows = await cursor.fetchall()
                rows = [
                    {
                        "intent_json": json.loads(r["intent_json"]) if isinstance(r["intent_json"], str) else r["intent_json"],
                        "tx_signature": r["tx_signature"],
                        "slot": r["slot"],
                        "status": r["status"],
                    }
                    for r in raw_rows
                ]
            except Exception:
                log.debug("SQLite get_projected_positions failed", exc_info=True)

        if not rows and self._pg is not None:
            try:
                async with self._pg.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT intent_json, tx_signature, slot, status
                        FROM execution_events
                        WHERE status IN ('confirmed', 'simulated')
                          AND intent_type IN ('open_position', 'reduce_position', 'close_position')
                        ORDER BY id ASC
                        """
                    )
                    rows = await cur.fetchall()
            except Exception:
                log.debug("PostgreSQL get_projected_positions failed", exc_info=True)

        if not rows:
            return []

        positions: dict[str, dict] = {}
        for row in rows:
            intent = row["intent_json"]
            intent_type = intent.get("intent_type")
            if intent_type == "open_position":
                key = intent.get("position_pda") or intent.get("idempotency_key", "unknown")
                positions[key] = {
                    "pda": key,
                    "market": intent.get("market"),
                    "side": intent.get("side"),
                    "size_usd": float(intent.get("size_usd", 0.0)),
                    "tx_signature": row["tx_signature"],
                    "slot": row["slot"],
                    "status": row["status"],
                }
                continue

            pda = intent.get("position_pda")
            if not pda:
                continue

            if intent_type == "close_position":
                positions.pop(pda, None)
            elif intent_type == "reduce_position" and pda in positions:
                reduce_size = float(intent.get("reduce_size_usd", 0.0))
                positions[pda]["size_usd"] = max(0.0, positions[pda]["size_usd"] - reduce_size)
                if positions[pda]["size_usd"] == 0.0:
                    positions.pop(pda, None)

        return list(positions.values())

    async def record_reconciliation_failure(
        self,
        chain_positions: list[dict],
        db_positions: list[dict],
        discrepancies: list[dict],
    ) -> None:
        now = self._now()
        chain_json = json.dumps(chain_positions, sort_keys=True)
        db_json = json.dumps(db_positions, sort_keys=True)
        disc_json = json.dumps(discrepancies, sort_keys=True)

        if self._sqlite is not None:
            try:
                await self._sqlite.execute(
                    """
                    INSERT INTO reconciliation_failures
                        (detected_at, chain_positions, db_positions, discrepancies)
                    VALUES (?, ?, ?, ?)
                    """,
                    (now, chain_json, db_json, disc_json),
                )
                await self._sqlite.commit()
            except Exception:
                log.debug("SQLite record_reconciliation_failure failed", exc_info=True)

        async def _pg_write() -> None:
            async with self._pg.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO reconciliation_failures
                        (chain_positions, db_positions, discrepancies)
                    VALUES (%s::jsonb, %s::jsonb, %s::jsonb)
                    """,
                    (chain_json, db_json, disc_json),
                )
                await self._pg.commit()

        await self._pg_exec_safe(_pg_write)

        if self._sqlite is None and self._pg is None:
            log.warning("[MEMORY] reconciliation_failure count=%d", len(discrepancies))
