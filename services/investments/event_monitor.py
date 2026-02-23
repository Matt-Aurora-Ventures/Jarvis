"""On-chain Event Monitor — polls Base chain for basket contract events.

Tracks:
  - Rebalanced(address indexed manager, uint256 timestamp)
  - FeeCollected(address indexed collector, uint256 amount)
  - Transfer(address indexed from, address indexed to, uint256 value)

Events are stored in the ``inv_basket_events`` table (created by
migrations/000_setup.sql).  The last processed block is persisted in Redis
so the monitor can resume without reprocessing.

Usage:
    monitor = EventMonitor(cfg, db_pool, redis)
    await monitor.start()   # runs as asyncio background task
    ...
    await monitor.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import redis.asyncio as aioredis
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.contract import AsyncContract

from services.investments.config import InvestmentConfig

logger = logging.getLogger("investments.events")

# ---------------------------------------------------------------------------
# Event ABI (only the topics we care about)
# ---------------------------------------------------------------------------

BASKET_EVENTS_ABI: list[dict[str, Any]] = [
    {
        "name": "Rebalanced",
        "type": "event",
        "inputs": [
            {"name": "manager", "type": "address", "indexed": True},
            {"name": "timestamp", "type": "uint256", "indexed": False},
        ],
    },
    {
        "name": "FeeCollected",
        "type": "event",
        "inputs": [
            {"name": "collector", "type": "address", "indexed": True},
            {"name": "amount", "type": "uint256", "indexed": False},
        ],
    },
    {
        "name": "Transfer",
        "type": "event",
        "inputs": [
            {"name": "from", "type": "address", "indexed": True},
            {"name": "to", "type": "address", "indexed": True},
            {"name": "value", "type": "uint256", "indexed": False},
        ],
    },
]

# Base chain average block time is ~2 seconds, poll every 12 seconds (6 blocks)
DEFAULT_POLL_INTERVAL_S = 12

# Maximum number of blocks to query in a single getLogs call.
# Public RPCs often cap this; 2000 is safe for Base.
MAX_BLOCK_RANGE = 2_000

# Redis key prefix for storing the last processed block number.
_REDIS_KEY_PREFIX = "inv:events:last_block"


class EventMonitor:
    """Polls Base chain for basket contract events and persists them to Postgres."""

    def __init__(
        self,
        cfg: InvestmentConfig,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
        *,
        poll_interval: int = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        self.cfg = cfg
        self.db = db
        self.redis = redis
        self.poll_interval = poll_interval

        # Web3 async provider
        self.w3 = AsyncWeb3(AsyncHTTPProvider(cfg.base_rpc_url))

        # Contract wrapper (events only)
        self.basket_address: str = AsyncWeb3.to_checksum_address(cfg.basket_address)
        self.contract: AsyncContract = self.w3.eth.contract(
            address=self.basket_address, abi=BASKET_EVENTS_ABI
        )

        # Pre-compute topic hashes for the events we track
        self._event_signatures: dict[str, str] = {}
        for evt_abi in BASKET_EVENTS_ABI:
            name = evt_abi["name"]
            input_types = ",".join(i["type"] for i in evt_abi["inputs"])
            sig = f"{name}({input_types})"
            topic = self.w3.keccak(text=sig).hex()
            self._event_signatures[topic] = name
        logger.info(
            "Tracking %d event signatures: %s",
            len(self._event_signatures),
            list(self._event_signatures.values()),
        )

        # Background task handle
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background polling loop as an asyncio Task."""
        if self._task is not None and not self._task.done():
            logger.warning("EventMonitor already running")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._poll_loop(), name="event-monitor")
        logger.info(
            "EventMonitor started (basket=%s, interval=%ds)",
            self.basket_address,
            self.poll_interval,
        )

    async def stop(self) -> None:
        """Signal the polling loop to stop and wait for it to finish."""
        if self._task is None or self._task.done():
            return

        logger.info("Stopping EventMonitor...")
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=30)
        except asyncio.TimeoutError:
            logger.warning("EventMonitor did not stop within 30s — cancelling")
            self._task.cancel()
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("EventMonitor stopped.")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------
    # Core polling loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Main loop: fetch new logs, decode, persist, repeat."""
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Event poll cycle failed — will retry next interval")

            # Sleep for the poll interval, but wake up early if stop is requested
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval
                )
                # If we reach here, the stop event was set
                break
            except asyncio.TimeoutError:
                # Normal path — poll interval elapsed
                pass

    async def _poll_once(self) -> None:
        """Run a single poll cycle: determine block range, fetch logs, store."""
        latest_block = await self.w3.eth.block_number
        from_block = await self._get_last_block() + 1

        if from_block > latest_block:
            return  # Nothing new

        # Clamp to MAX_BLOCK_RANGE to stay within RPC limits
        to_block = min(from_block + MAX_BLOCK_RANGE - 1, latest_block)

        logger.debug(
            "Polling events: blocks %d -> %d (latest=%d)",
            from_block,
            to_block,
            latest_block,
        )

        # Build topic filter — first topic is the event signature
        topic_hashes = list(self._event_signatures.keys())
        filter_params: dict[str, Any] = {
            "address": self.basket_address,
            "fromBlock": from_block,
            "toBlock": to_block,
            "topics": [topic_hashes],
        }

        try:
            raw_logs = await self.w3.eth.get_logs(filter_params)
        except Exception as exc:
            logger.error("get_logs failed (blocks %d-%d): %s", from_block, to_block, exc)
            raise

        if raw_logs:
            logger.info("Fetched %d events in blocks %d-%d", len(raw_logs), from_block, to_block)
            await self._process_logs(raw_logs)

        # Advance the cursor
        await self._set_last_block(to_block)

        # If we clamped, there are more blocks to process — loop immediately
        if to_block < latest_block:
            logger.info(
                "More blocks to process (%d remaining), continuing...",
                latest_block - to_block,
            )
            await self._poll_once()

    # ------------------------------------------------------------------
    # Log decoding and persistence
    # ------------------------------------------------------------------

    async def _process_logs(self, raw_logs: list[Any]) -> None:
        """Decode raw logs and insert them into the database."""
        rows: list[tuple[str, int, str, str, str]] = []

        for log in raw_logs:
            topic0 = log["topics"][0].hex() if log["topics"] else None
            event_name = self._event_signatures.get(topic0, "Unknown")

            decoded = self._decode_log(event_name, log)

            event_data: dict[str, Any] = {
                "event": event_name,
                "log_index": log.get("logIndex", 0),
                "decoded": decoded,
                "raw_topics": [t.hex() for t in log.get("topics", [])],
                "raw_data": log.get("data", "0x") if isinstance(log.get("data"), str) else log.get("data", b"").hex(),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

            rows.append((
                self.basket_address,
                log["blockNumber"],
                log["transactionHash"].hex(),
                event_name,
                json.dumps(event_data, default=str),
            ))

        if not rows:
            return

        # Batch insert — skip duplicates on (tx_hash + block)
        # Rows tuple: (basket_address, block_number, tx_hash, event_name, event_data_json)
        # We only need columns 1, 2, 3, and 5 (event_name is embedded inside event_data).
        insert_rows = [
            (r[0], r[1], r[2], r[4]) for r in rows
        ]
        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO inv_basket_events (basket_address, block_number, tx_hash, event_data)
                VALUES ($1, $2, $3, $4::jsonb)
                ON CONFLICT DO NOTHING
                """,
                insert_rows,
            )

        logger.info(
            "Stored %d events: %s",
            len(rows),
            ", ".join(f"{r[3]}@{r[1]}" for r in rows),
        )

        # Publish to Redis for real-time subscribers
        for row in rows:
            await self.redis.publish(
                "investments:basket_events",
                json.dumps({
                    "event": row[3],
                    "block": row[1],
                    "tx_hash": row[2],
                }),
            )

    def _decode_log(self, event_name: str, log: Any) -> dict[str, Any]:
        """Best-effort decode of event parameters from topics and data.

        For indexed parameters the values live in topics[1..N].
        For non-indexed parameters the values are ABI-encoded in data.
        """
        decoded: dict[str, Any] = {}

        try:
            if event_name == "Rebalanced":
                # topics[1] = manager (address, indexed)
                if len(log["topics"]) > 1:
                    decoded["manager"] = self._topic_to_address(log["topics"][1])
                # data = timestamp (uint256)
                data_hex = log.get("data", "0x")
                if isinstance(data_hex, bytes):
                    data_hex = data_hex.hex()
                if len(data_hex) >= 66:  # 0x + 64 hex chars
                    decoded["timestamp"] = int(data_hex[:66], 16)

            elif event_name == "FeeCollected":
                # topics[1] = collector (address, indexed)
                if len(log["topics"]) > 1:
                    decoded["collector"] = self._topic_to_address(log["topics"][1])
                # data = amount (uint256)
                data_hex = log.get("data", "0x")
                if isinstance(data_hex, bytes):
                    data_hex = data_hex.hex()
                if len(data_hex) >= 66:
                    decoded["amount_raw"] = int(data_hex[:66], 16)

            elif event_name == "Transfer":
                # topics[1] = from, topics[2] = to (both indexed)
                if len(log["topics"]) > 1:
                    decoded["from"] = self._topic_to_address(log["topics"][1])
                if len(log["topics"]) > 2:
                    decoded["to"] = self._topic_to_address(log["topics"][2])
                # data = value (uint256)
                data_hex = log.get("data", "0x")
                if isinstance(data_hex, bytes):
                    data_hex = data_hex.hex()
                if len(data_hex) >= 66:
                    decoded["value_raw"] = int(data_hex[:66], 16)

        except Exception as exc:
            logger.warning("Failed to decode %s event: %s", event_name, exc)
            decoded["decode_error"] = str(exc)

        return decoded

    @staticmethod
    def _topic_to_address(topic: bytes) -> str:
        """Extract a checksummed address from a 32-byte indexed topic."""
        # An address is 20 bytes, right-padded in a 32-byte topic
        raw = topic[-20:] if isinstance(topic, (bytes, bytearray)) else bytes.fromhex(topic.hex())[-20:]
        return AsyncWeb3.to_checksum_address(raw)

    # ------------------------------------------------------------------
    # Block cursor (persisted in Redis)
    # ------------------------------------------------------------------

    def _redis_key(self) -> str:
        return f"{_REDIS_KEY_PREFIX}:{self.basket_address}"

    async def _get_last_block(self) -> int:
        """Return the last fully-processed block number.

        If no cursor exists, defaults to the current block minus a small
        look-back window (256 blocks ~ 8 minutes on Base) so we don't miss
        recent events on first startup.
        """
        val = await self.redis.get(self._redis_key())
        if val is not None:
            return int(val)

        # First run — start from a recent block
        latest = await self.w3.eth.block_number
        start_block = max(0, latest - 256)
        logger.info(
            "No cursor found — starting event monitor from block %d (latest=%d)",
            start_block,
            latest,
        )
        return start_block

    async def _set_last_block(self, block_number: int) -> None:
        """Persist the last fully-processed block number to Redis."""
        await self.redis.set(self._redis_key(), str(block_number))

    # ------------------------------------------------------------------
    # Query helpers (for the rest of the system)
    # ------------------------------------------------------------------

    async def get_recent_events(
        self, limit: int = 50, event_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch recent events from the database.

        Args:
            limit: Maximum number of events to return.
            event_name: Optional filter (e.g. "Rebalanced", "Transfer").

        Returns:
            List of event dicts ordered by block_number descending.
        """
        if event_name:
            rows = await self.db.fetch(
                """
                SELECT id, basket_address, block_number, tx_hash, event_data, created_at
                FROM inv_basket_events
                WHERE basket_address = $1
                  AND event_data->>'event' = $2
                ORDER BY block_number DESC
                LIMIT $3
                """,
                self.basket_address,
                event_name,
                limit,
            )
        else:
            rows = await self.db.fetch(
                """
                SELECT id, basket_address, block_number, tx_hash, event_data, created_at
                FROM inv_basket_events
                WHERE basket_address = $1
                ORDER BY block_number DESC
                LIMIT $2
                """,
                self.basket_address,
                limit,
            )

        return [
            {
                "id": r["id"],
                "block_number": r["block_number"],
                "tx_hash": r["tx_hash"],
                "event_data": json.loads(r["event_data"])
                if isinstance(r["event_data"], str)
                else r["event_data"],
                "created_at": r["created_at"].isoformat()
                if r["created_at"]
                else None,
            }
            for r in rows
        ]

    async def get_rebalance_count(self, hours: int = 24) -> int:
        """Return the number of Rebalanced events in the last N hours."""
        row = await self.db.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM inv_basket_events
            WHERE basket_address = $1
              AND event_data->>'event' = 'Rebalanced'
              AND created_at > NOW() - make_interval(hours => $2)
            """,
            self.basket_address,
            hours,
        )
        return int(row["cnt"]) if row else 0
