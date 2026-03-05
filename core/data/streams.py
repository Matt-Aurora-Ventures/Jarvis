"""
Push-based streaming for real-time price and event data.

Uses Solana ``logsSubscribe`` WebSocket RPC to monitor on-chain program activity
in real time. Replaces high-frequency REST polling for:
    - New pool creation (Raydium, Meteora)
    - Bags.fm graduation events (``migrate_meteora_damm``)
    - Swap volume / price updates

Target program IDs:
    - Raydium AMM v4:  675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8
    - Meteora DBC:     BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv
    - Pump.fun:        6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P

Usage::

    from core.data.streams import SolanaStreamManager

    manager = SolanaStreamManager()
    manager.on_graduation = handle_graduation
    manager.on_new_pool = handle_new_pool
    await manager.start()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RPC_WS = os.getenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")

# Program IDs to monitor
PROGRAM_IDS = {
    "raydium_amm_v4": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "meteora_dbc": "BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv",
    "pump_fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
}

# Instruction discriminators (first 8 bytes of SHA256 of the instruction name)
# These are used to identify specific instructions in log messages
GRADUATION_LOG_MARKERS = [
    "migrate_meteora_damm",
    "MigrateMeteoraDamm",
    "Program log: Instruction: MigrateMeteoraDamm",
]

POOL_INIT_LOG_MARKERS = [
    "InitializeMarket",
    "Initialize2",
    "Program log: Instruction: Initialize",
    "Program log: Instruction: InitializeMarket",
]


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class StreamEventType(Enum):
    """Types of events detected on the stream."""

    NEW_POOL = "new_pool"
    GRADUATION = "graduation"
    SWAP = "swap"
    LARGE_TRANSFER = "large_transfer"
    UNKNOWN = "unknown"


@dataclass
class StreamEvent:
    """A parsed event from the Solana log stream."""

    event_type: StreamEventType
    program_id: str
    signature: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accounts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    # Graduation-specific
    mint_address: Optional[str] = None
    pool_address: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"StreamEvent({self.event_type.value}, "
            f"program={self.program_id[:8]}..., "
            f"sig={self.signature[:16]}...)"
        )


# ---------------------------------------------------------------------------
# Event handlers type alias
# ---------------------------------------------------------------------------

EventHandler = Callable[[StreamEvent], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Stream manager
# ---------------------------------------------------------------------------

class SolanaStreamManager:
    """
    Manages persistent WebSocket subscriptions to Solana ``logsSubscribe``.

    Monitors target program IDs and dispatches parsed events to registered
    handlers. Auto-reconnects with exponential backoff.
    """

    def __init__(
        self,
        rpc_ws_url: str = DEFAULT_RPC_WS,
        programs: Optional[Dict[str, str]] = None,
    ) -> None:
        self._rpc_ws_url = rpc_ws_url
        self._programs = programs or PROGRAM_IDS
        self._ws: Optional[Any] = None
        self._running = False
        self._subscription_ids: Dict[str, int] = {}
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

        # Event handlers
        self._handlers: Dict[StreamEventType, List[EventHandler]] = {
            evt: [] for evt in StreamEventType
        }

        # Stats
        self._connected_at: Optional[float] = None
        self._messages_received = 0
        self._events_dispatched = 0
        self._reconnect_count = 0

    # -- Handler registration ---------------------------------------------------

    def on(self, event_type: StreamEventType, handler: EventHandler) -> None:
        """Register an async handler for a specific event type."""
        self._handlers[event_type].append(handler)

    @property
    def on_graduation(self) -> Optional[EventHandler]:
        handlers = self._handlers.get(StreamEventType.GRADUATION, [])
        return handlers[0] if handlers else None

    @on_graduation.setter
    def on_graduation(self, handler: EventHandler) -> None:
        self._handlers[StreamEventType.GRADUATION] = [handler]

    @property
    def on_new_pool(self) -> Optional[EventHandler]:
        handlers = self._handlers.get(StreamEventType.NEW_POOL, [])
        return handlers[0] if handlers else None

    @on_new_pool.setter
    def on_new_pool(self, handler: EventHandler) -> None:
        self._handlers[StreamEventType.NEW_POOL] = [handler]

    # -- Lifecycle --------------------------------------------------------------

    async def start(self) -> None:
        """Start the stream manager. Connects and subscribes to all programs."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets package not installed — streaming unavailable")
            return

        self._running = True
        logger.info("Starting Solana stream manager → %s", self._rpc_ws_url)

        while self._running:
            try:
                await self._connect_and_subscribe()
                await self._listen()
            except Exception as exc:
                if not self._running:
                    break
                self._reconnect_count += 1
                delay = min(
                    self._reconnect_delay * (2 ** min(self._reconnect_count, 6)),
                    self._max_reconnect_delay,
                )
                logger.warning(
                    "Stream disconnected (%s), reconnecting in %.1fs (attempt %d)",
                    exc, delay, self._reconnect_count,
                )
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        """Gracefully stop the stream manager."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("Solana stream manager stopped")

    # -- Connection -------------------------------------------------------------

    async def _connect_and_subscribe(self) -> None:
        """Establish WebSocket connection and subscribe to all program logs."""
        self._ws = await websockets.connect(  # type: ignore[attr-defined]
            self._rpc_ws_url,
            ping_interval=30,
            ping_timeout=10,
            max_size=2 ** 22,  # 4MB max message
        )
        self._connected_at = time.time()
        self._reconnect_delay = 1.0
        logger.info("Connected to Solana WebSocket RPC")

        # Subscribe to each program via logsSubscribe
        for name, program_id in self._programs.items():
            sub_id = await self._subscribe_logs(program_id)
            if sub_id is not None:
                self._subscription_ids[name] = sub_id
                logger.info("Subscribed to %s (%s) → sub_id=%d", name, program_id[:12], sub_id)

    async def _subscribe_logs(self, program_id: str) -> Optional[int]:
        """Send a logsSubscribe RPC request for a specific program."""
        request = {
            "jsonrpc": "2.0",
            "id": hash(program_id) & 0xFFFFFFFF,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [program_id]},
                {"commitment": "confirmed"},
            ],
        }
        await self._ws.send(json.dumps(request))

        # Wait for subscription confirmation
        try:
            resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            resp = json.loads(resp_raw)
            return resp.get("result")
        except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to subscribe to %s: %s", program_id[:12], exc)
            return None

    # -- Message processing -----------------------------------------------------

    async def _listen(self) -> None:
        """Listen for incoming WebSocket messages and dispatch events."""
        async for raw_msg in self._ws:
            self._messages_received += 1

            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            if msg.get("method") != "logsNotification":
                continue

            params = msg.get("params", {})
            result = params.get("result", {})
            value = result.get("value", {})

            logs = value.get("logs", [])
            signature = value.get("signature", "")
            err = value.get("err")

            if err:
                continue  # Skip failed transactions

            event = self._parse_logs(logs, signature)
            if event:
                await self._dispatch(event)

    def _parse_logs(self, logs: List[str], signature: str) -> Optional[StreamEvent]:
        """Parse log lines to detect known events."""
        if not logs:
            return None

        log_text = " ".join(logs)
        program_id = ""

        # Identify which program emitted the logs
        for name, pid in self._programs.items():
            if pid in log_text:
                program_id = pid
                break

        if not program_id:
            return None

        # Detect graduation events (highest priority)
        for marker in GRADUATION_LOG_MARKERS:
            if marker in log_text:
                event = StreamEvent(
                    event_type=StreamEventType.GRADUATION,
                    program_id=program_id,
                    signature=signature,
                    logs=logs,
                )
                # Try to extract mint and pool from account keys in logs
                self._extract_graduation_details(event, logs)
                return event

        # Detect new pool creation
        for marker in POOL_INIT_LOG_MARKERS:
            if marker in log_text:
                return StreamEvent(
                    event_type=StreamEventType.NEW_POOL,
                    program_id=program_id,
                    signature=signature,
                    logs=logs,
                )

        return None

    def _extract_graduation_details(
        self, event: StreamEvent, logs: List[str]
    ) -> None:
        """Try to extract mint address and pool address from graduation logs."""
        for log_line in logs:
            # Look for base58-encoded account references in log lines
            # Format varies but typically: "Program log: mint=<address>"
            if "mint" in log_line.lower():
                parts = log_line.split()
                for part in parts:
                    clean = part.strip(",;:=")
                    if len(clean) >= 32 and clean.isalnum():
                        event.mint_address = clean
                        break
            if "pool" in log_line.lower():
                parts = log_line.split()
                for part in parts:
                    clean = part.strip(",;:=")
                    if len(clean) >= 32 and clean.isalnum():
                        event.pool_address = clean
                        break

    async def _dispatch(self, event: StreamEvent) -> None:
        """Dispatch an event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
                self._events_dispatched += 1
            except Exception as exc:
                logger.error(
                    "Handler error for %s: %s", event.event_type.value, exc,
                    exc_info=True,
                )

    # -- Status -----------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current stream manager status for dashboards."""
        return {
            "running": self._running,
            "connected": self._ws is not None and not getattr(self._ws, "closed", True),
            "rpc_url": self._rpc_ws_url,
            "subscriptions": dict(self._subscription_ids),
            "programs_monitored": list(self._programs.keys()),
            "messages_received": self._messages_received,
            "events_dispatched": self._events_dispatched,
            "reconnect_count": self._reconnect_count,
            "uptime_seconds": (
                time.time() - self._connected_at
                if self._connected_at else 0
            ),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_stream_manager: Optional[SolanaStreamManager] = None


def get_stream_manager(
    rpc_ws_url: Optional[str] = None,
) -> SolanaStreamManager:
    """Return the global SolanaStreamManager singleton."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = SolanaStreamManager(
            rpc_ws_url=rpc_ws_url or DEFAULT_RPC_WS,
        )
    return _stream_manager
