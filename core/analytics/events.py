"""
Event Tracking System.

Comprehensive event tracking for analytics:
- User actions (register, login, trades)
- System events (fees, distributions)
- Real-time WebSocket feed
- Aggregation for metrics dashboards

Events are written to PostgreSQL and optionally forwarded to
analytics services (Mixpanel, Amplitude).
"""

import asyncio
import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.security_validation import sanitize_sql_identifier
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.analytics.events")


# =============================================================================
# Event Types
# =============================================================================


class EventType(Enum):
    """Event type enumeration."""
    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # Credits events
    CREDITS_PURCHASED = "credits.purchased"
    CREDITS_CONSUMED = "credits.consumed"
    CREDITS_REFUNDED = "credits.refunded"

    # Trading events
    TRADE_QUOTE = "trade.quote"
    TRADE_EXECUTED = "trade.executed"
    TRADE_FAILED = "trade.failed"

    # Staking events
    STAKE_CREATED = "stake.created"
    STAKE_UNSTAKED = "stake.unstaked"
    STAKE_COOLDOWN_COMPLETE = "stake.cooldown_complete"
    REWARDS_CLAIMED = "rewards.claimed"

    # Fee events
    FEE_COLLECTED = "fee.collected"
    FEE_DISTRIBUTED = "fee.distributed"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_ALERT = "system.alert"


@dataclass
class Event:
    """An analytics event."""
    type: EventType
    user_id: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        if self.id is None:
            import uuid
            self.id = f"evt_{uuid.uuid4().hex[:16]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Event":
        return cls(
            id=data.get("id"),
            type=EventType(data["type"]),
            user_id=data.get("user_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            session_id=data.get("session_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
        )


# =============================================================================
# Event Sinks (Destinations)
# =============================================================================


class EventSink(ABC):
    """Abstract base class for event destinations."""

    @abstractmethod
    async def write(self, event: Event):
        """Write a single event."""
        pass

    @abstractmethod
    async def write_batch(self, events: List[Event]):
        """Write a batch of events."""
        pass

    async def close(self):
        """Clean up resources."""
        pass


class SQLiteEventSink(EventSink):
    """SQLite event storage."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            db_path = str(data_dir / "events.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                user_id TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")

        # Aggregation tables for metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_counts_hourly (
                event_type TEXT NOT NULL,
                hour TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (event_type, hour)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_counts_daily (
                event_type TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                sum_value REAL DEFAULT 0,
                PRIMARY KEY (event_type, date)
            )
        """)

        conn.commit()
        conn.close()

    async def write(self, event: Event):
        """Write single event."""
        await self.write_batch([event])

    async def write_batch(self, events: List[Event]):
        """Write batch of events."""
        if not events:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for event in events:
            cursor.execute(
                """
                INSERT OR IGNORE INTO events
                (id, type, user_id, timestamp, metadata, session_id, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.type.value,
                    event.user_id,
                    event.timestamp.isoformat(),
                    json.dumps(event.metadata),
                    event.session_id,
                    event.ip_address,
                    event.user_agent,
                ),
            )

            # Update hourly counts
            hour = event.timestamp.strftime("%Y-%m-%d-%H")
            cursor.execute(
                """
                INSERT INTO event_counts_hourly (event_type, hour, count)
                VALUES (?, ?, 1)
                ON CONFLICT(event_type, hour) DO UPDATE SET count = count + 1
                """,
                (event.type.value, hour),
            )

            # Update daily counts
            date = event.timestamp.strftime("%Y-%m-%d")
            value = event.metadata.get("amount", 0) or event.metadata.get("credits", 0) or 0
            cursor.execute(
                """
                INSERT INTO event_counts_daily (event_type, date, count, sum_value)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(event_type, date) DO UPDATE SET
                    count = count + 1,
                    sum_value = sum_value + excluded.sum_value
                """,
                (event.type.value, date, value),
            )

        conn.commit()
        conn.close()

    async def query(
        self,
        event_type: EventType = None,
        user_id: str = None,
        since: datetime = None,
        until: datetime = None,
        limit: int = 100,
    ) -> List[Event]:
        """Query events."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM events WHERE 1=1"
        params = []

        if event_type:
            query += " AND type = ?"
            params.append(event_type.value)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            events.append(Event(
                id=row[0],
                type=EventType(row[1]),
                user_id=row[2],
                timestamp=datetime.fromisoformat(row[3]),
                metadata=json.loads(row[4]) if row[4] else {},
                session_id=row[5],
                ip_address=row[6],
                user_agent=row[7],
            ))

        return events

    async def get_aggregates(
        self,
        event_type: EventType = None,
        granularity: str = "daily",
        since: datetime = None,
        until: datetime = None,
    ) -> List[Dict]:
        """Get aggregated event counts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        table = "event_counts_hourly" if granularity == "hourly" else "event_counts_daily"
        time_col = "hour" if granularity == "hourly" else "date"

        # Sanitize identifiers
        safe_table = sanitize_sql_identifier(table)
        safe_time_col = sanitize_sql_identifier(time_col)

        query = f"SELECT event_type, {safe_time_col}, count, sum_value FROM {safe_table} WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        if since:
            query += f" AND {safe_time_col} >= ?"
            params.append(since.strftime("%Y-%m-%d") if granularity == "daily" else since.strftime("%Y-%m-%d-%H"))

        if until:
            query += f" AND {safe_time_col} <= ?"
            params.append(until.strftime("%Y-%m-%d") if granularity == "daily" else until.strftime("%Y-%m-%d-%H"))

        query += f" ORDER BY {safe_time_col} DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "event_type": row[0],
                "period": row[1],
                "count": row[2],
                "sum_value": row[3],
            }
            for row in rows
        ]


class MixpanelSink(EventSink):
    """Mixpanel analytics integration."""

    def __init__(self, token: str = None):
        self.token = token or os.getenv("MIXPANEL_TOKEN", "")
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def write(self, event: Event):
        await self.write_batch([event])

    async def write_batch(self, events: List[Event]):
        if not self.token or not events:
            return

        try:
            import base64

            session = await self._get_session()

            for event in events:
                data = {
                    "event": event.type.value,
                    "properties": {
                        "token": self.token,
                        "distinct_id": event.user_id or "anonymous",
                        "time": int(event.timestamp.timestamp()),
                        **event.metadata,
                    },
                }

                encoded = base64.b64encode(json.dumps(data).encode()).decode()

                async with session.get(
                    f"https://api.mixpanel.com/track/?data={encoded}"
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"Mixpanel tracking failed: {resp.status}")

        except Exception as e:
            logger.error(f"Mixpanel error: {e}")

    async def close(self):
        if self._session:
            await self._session.close()


class WebSocketSink(EventSink):
    """Real-time WebSocket broadcast."""

    def __init__(self, connection_manager=None):
        self._manager = connection_manager

    async def write(self, event: Event):
        await self.write_batch([event])

    async def write_batch(self, events: List[Event]):
        if not self._manager:
            return

        for event in events:
            try:
                await self._manager.broadcast(
                    "events",
                    {
                        "type": "event",
                        "data": event.to_dict(),
                    },
                )
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")


# =============================================================================
# Event Tracker
# =============================================================================


class EventTracker:
    """
    Main event tracking service.

    Features:
    - Buffered writes for efficiency
    - Multiple sinks (SQLite, Mixpanel, WebSocket)
    - Automatic flushing
    """

    def __init__(
        self,
        sinks: List[EventSink] = None,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
    ):
        self._sinks = sinks or [SQLiteEventSink()]
        self._buffer: List[Event] = []
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the event tracker."""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Event tracker started")

    async def stop(self):
        """Stop the event tracker and flush remaining events."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self._flush()

        for sink in self._sinks:
            await sink.close()

        logger.info("Event tracker stopped")

    async def track(
        self,
        event_type: EventType,
        user_id: str = None,
        metadata: Dict[str, Any] = None,
        session_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Track an event."""
        event = Event(
            type=event_type,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        async with self._lock:
            self._buffer.append(event)

            if len(self._buffer) >= self._buffer_size:
                await self._flush()

        logger.debug(f"Tracked event: {event_type.value} for user {user_id}")

    async def _flush(self):
        """Flush buffer to all sinks."""
        if not self._buffer:
            return

        async with self._lock:
            events = self._buffer.copy()
            self._buffer.clear()

        for sink in self._sinks:
            try:
                await sink.write_batch(events)
            except Exception as e:
                logger.error(f"Error writing to sink {type(sink).__name__}: {e}")

    async def _flush_loop(self):
        """Background flush loop."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    # Convenience methods for common events
    async def user_registered(self, user_id: str, **metadata):
        await self.track(EventType.USER_REGISTERED, user_id, metadata)

    async def user_login(self, user_id: str, **metadata):
        await self.track(EventType.USER_LOGIN, user_id, metadata)

    async def credits_purchased(
        self,
        user_id: str,
        package_id: str,
        credits: int,
        amount_usd: float,
        **metadata,
    ):
        await self.track(
            EventType.CREDITS_PURCHASED,
            user_id,
            {"package_id": package_id, "credits": credits, "amount_usd": amount_usd, **metadata},
        )

    async def credits_consumed(
        self,
        user_id: str,
        credits: int,
        endpoint: str,
        **metadata,
    ):
        await self.track(
            EventType.CREDITS_CONSUMED,
            user_id,
            {"credits": credits, "endpoint": endpoint, **metadata},
        )

    async def trade_executed(
        self,
        user_id: str,
        input_mint: str,
        output_mint: str,
        amount_sol: float,
        signature: str,
        source: str = "bags",
        **metadata,
    ):
        await self.track(
            EventType.TRADE_EXECUTED,
            user_id,
            {
                "input_mint": input_mint,
                "output_mint": output_mint,
                "amount_sol": amount_sol,
                "signature": signature,
                "source": source,
                **metadata,
            },
        )

    async def stake_created(
        self,
        user_id: str,
        amount: int,
        signature: str,
        **metadata,
    ):
        await self.track(
            EventType.STAKE_CREATED,
            user_id,
            {"amount": amount, "signature": signature, **metadata},
        )

    async def rewards_claimed(
        self,
        user_id: str,
        amount_sol: float,
        signature: str,
        **metadata,
    ):
        await self.track(
            EventType.REWARDS_CLAIMED,
            user_id,
            {"amount_sol": amount_sol, "signature": signature, **metadata},
        )

    async def fee_collected(
        self,
        amount_sol: float,
        source: str,
        signature: str = None,
        **metadata,
    ):
        await self.track(
            EventType.FEE_COLLECTED,
            None,
            {"amount_sol": amount_sol, "source": source, "signature": signature, **metadata},
        )


# =============================================================================
# Metrics Aggregator
# =============================================================================


class MetricsAggregator:
    """Aggregates events into metrics for dashboards."""

    def __init__(self, sink: SQLiteEventSink = None):
        self._sink = sink or SQLiteEventSink()

    async def get_overview(
        self,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get overview metrics."""
        since = datetime.now(timezone.utc) - timedelta(days=period_days)

        # Get daily aggregates for key event types
        credits_purchased = await self._sink.get_aggregates(
            EventType.CREDITS_PURCHASED, "daily", since
        )
        trades_executed = await self._sink.get_aggregates(
            EventType.TRADE_EXECUTED, "daily", since
        )
        fees_collected = await self._sink.get_aggregates(
            EventType.FEE_COLLECTED, "daily", since
        )

        return {
            "period_days": period_days,
            "credits_purchased": {
                "count": sum(d["count"] for d in credits_purchased),
                "total_value": sum(d["sum_value"] for d in credits_purchased),
                "daily": credits_purchased[:7],  # Last 7 days
            },
            "trades_executed": {
                "count": sum(d["count"] for d in trades_executed),
                "total_volume": sum(d["sum_value"] for d in trades_executed),
                "daily": trades_executed[:7],
            },
            "fees_collected": {
                "count": sum(d["count"] for d in fees_collected),
                "total_sol": sum(d["sum_value"] for d in fees_collected),
                "daily": fees_collected[:7],
            },
        }

    async def get_user_metrics(
        self,
        user_id: str,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get metrics for a specific user."""
        since = datetime.now(timezone.utc) - timedelta(days=period_days)

        events = await self._sink.query(user_id=user_id, since=since, limit=1000)

        return {
            "user_id": user_id,
            "period_days": period_days,
            "total_events": len(events),
            "by_type": self._count_by_type(events),
            "recent_activity": [e.to_dict() for e in events[:10]],
        }

    def _count_by_type(self, events: List[Event]) -> Dict[str, int]:
        """Count events by type."""
        counts = {}
        for event in events:
            key = event.type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


# =============================================================================
# Singleton
# =============================================================================

_tracker: Optional[EventTracker] = None


def get_event_tracker() -> EventTracker:
    """Get singleton event tracker."""
    global _tracker
    if _tracker is None:
        _tracker = EventTracker()
    return _tracker


async def init_event_tracker():
    """Initialize and start the event tracker."""
    tracker = get_event_tracker()
    await tracker.start()
    return tracker


# =============================================================================
# FastAPI Integration
# =============================================================================


def create_events_router():
    """Create FastAPI router for events API."""
    try:
        from fastapi import APIRouter, Query
    except ImportError:
        return None

    router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
    sink = SQLiteEventSink()
    aggregator = MetricsAggregator(sink)

    @router.get("/events")
    async def get_events(
        type: str = None,
        user_id: str = None,
        limit: int = Query(default=50, le=500),
    ):
        """Get recent events."""
        event_type = EventType(type) if type else None
        events = await sink.query(event_type=event_type, user_id=user_id, limit=limit)
        return {"events": [e.to_dict() for e in events]}

    @router.get("/metrics/overview")
    async def get_overview_metrics(days: int = Query(default=30, le=365)):
        """Get overview metrics."""
        return await aggregator.get_overview(days)

    @router.get("/metrics/user/{user_id}")
    async def get_user_metrics(user_id: str, days: int = Query(default=30, le=365)):
        """Get user metrics."""
        return await aggregator.get_user_metrics(user_id, days)

    @router.get("/aggregates")
    async def get_aggregates(
        type: str = None,
        granularity: str = Query(default="daily", regex="^(hourly|daily)$"),
        days: int = Query(default=7, le=90),
    ):
        """Get event aggregates."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        event_type = EventType(type) if type else None
        aggregates = await sink.get_aggregates(event_type, granularity, since)
        return {"aggregates": aggregates}

    return router
