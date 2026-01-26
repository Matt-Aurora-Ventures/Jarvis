"""
TimescaleDB Repository for Time-Series Data.

Provides optimized storage and querying for:
- Price ticks (token prices over time)
- Strategy signals (trading signals with timestamps)
- Position history (position snapshots over time)

Uses TimescaleDB hypertables for:
- 10-100x faster time-range queries
- Automatic data partitioning
- Efficient compression
- Continuous aggregates for OHLC data

Usage:
    from core.database.timescale_repository import TimescaleRepository, PriceTick

    repo = TimescaleRepository()
    await repo.setup_hypertables()

    tick = PriceTick(
        token_mint="...",
        timestamp=datetime.utcnow(),
        price=150.50,
        volume=1000000.0
    )
    await repo.insert_price_tick(tick)

    # Query OHLC aggregates
    ohlc = await repo.get_price_ohlc(
        token_mint="...",
        interval="1h",
        start_time=datetime.utcnow() - timedelta(days=1),
        end_time=datetime.utcnow()
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .postgres_client import PostgresClient, get_postgres_client

logger = logging.getLogger(__name__)


@dataclass
class PriceTick:
    """Price tick data point."""
    token_mint: str
    timestamp: datetime
    price: float
    volume: float = 0.0
    source: str = "jupiter"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StrategySignal:
    """Strategy trading signal."""
    strategy_id: str
    timestamp: datetime
    signal_type: str  # "buy", "sell", "hold"
    confidence: float
    token_mint: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PositionSnapshot:
    """Position state at a point in time."""
    position_id: str
    timestamp: datetime
    pnl_sol: float
    pnl_pct: float
    size_tokens: float
    current_price: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OHLCBar:
    """OHLC candlestick data."""
    bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class TimescaleRepository:
    """
    Repository for TimescaleDB time-series data.

    Manages hypertables for efficient time-series storage and queries.
    """

    def __init__(
        self,
        connection_url: Optional[str] = None,
        client: Optional[PostgresClient] = None
    ):
        """
        Initialize TimescaleDB repository.

        Args:
            connection_url: PostgreSQL connection URL (optional if client provided)
            client: Existing PostgresClient instance (optional)
        """
        if client:
            self._client = client
        elif connection_url:
            self._client = PostgresClient(connection_url=connection_url)
        else:
            self._client = get_postgres_client()

    async def setup_hypertables(self) -> None:
        """
        Create TimescaleDB hypertables for time-series data.

        Creates tables:
        - price_ticks: Token price history
        - strategy_signals: Trading signals
        - position_history: Position snapshots
        """
        # Create price_ticks table
        await self._client.execute("""
            CREATE TABLE IF NOT EXISTS price_ticks (
                token_mint TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                volume DOUBLE PRECISION DEFAULT 0,
                source TEXT DEFAULT 'jupiter',
                metadata JSONB,
                PRIMARY KEY (token_mint, timestamp)
            );
        """)

        # Convert to hypertable (TimescaleDB)
        await self._client.execute("""
            SELECT create_hypertable('price_ticks', 'timestamp',
                if_not_exists => TRUE,
                chunk_time_interval => INTERVAL '1 day'
            );
        """)

        # Create strategy_signals table
        await self._client.execute("""
            CREATE TABLE IF NOT EXISTS strategy_signals (
                id SERIAL,
                strategy_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                signal_type TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                token_mint TEXT NOT NULL,
                metadata JSONB,
                PRIMARY KEY (id, timestamp)
            );
        """)

        # Convert to hypertable
        await self._client.execute("""
            SELECT create_hypertable('strategy_signals', 'timestamp',
                if_not_exists => TRUE,
                chunk_time_interval => INTERVAL '1 day'
            );
        """)

        # Create position_history table
        await self._client.execute("""
            CREATE TABLE IF NOT EXISTS position_history (
                position_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                pnl_sol DOUBLE PRECISION NOT NULL,
                pnl_pct DOUBLE PRECISION NOT NULL,
                size_tokens DOUBLE PRECISION NOT NULL,
                current_price DOUBLE PRECISION NOT NULL,
                metadata JSONB,
                PRIMARY KEY (position_id, timestamp)
            );
        """)

        # Convert to hypertable
        await self._client.execute("""
            SELECT create_hypertable('position_history', 'timestamp',
                if_not_exists => TRUE,
                chunk_time_interval => INTERVAL '1 day'
            );
        """)

        # Create indexes for common queries
        await self._client.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_ticks_token_time
            ON price_ticks (token_mint, timestamp DESC);
        """)

        await self._client.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_strategy_time
            ON strategy_signals (strategy_id, timestamp DESC);
        """)

        await self._client.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_history_pos_time
            ON position_history (position_id, timestamp DESC);
        """)

        logger.info("TimescaleDB hypertables created")

    async def setup_continuous_aggregates(self) -> None:
        """
        Create continuous aggregates for OHLC data.

        Creates materialized views that automatically aggregate price ticks
        into OHLC bars for efficient querying.
        """
        # Create 1-hour OHLC continuous aggregate
        await self._client.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS price_ohlc_1h
            WITH (timescaledb.continuous) AS
            SELECT
                token_mint,
                time_bucket('1 hour', timestamp) AS bucket,
                first(price, timestamp) AS open,
                max(price) AS high,
                min(price) AS low,
                last(price, timestamp) AS close,
                sum(volume) AS volume
            FROM price_ticks
            GROUP BY token_mint, time_bucket('1 hour', timestamp)
            WITH NO DATA;
        """)

        # Create 1-day OHLC continuous aggregate
        await self._client.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS price_ohlc_1d
            WITH (timescaledb.continuous) AS
            SELECT
                token_mint,
                time_bucket('1 day', timestamp) AS bucket,
                first(price, timestamp) AS open,
                max(price) AS high,
                min(price) AS low,
                last(price, timestamp) AS close,
                sum(volume) AS volume
            FROM price_ticks
            GROUP BY token_mint, time_bucket('1 day', timestamp)
            WITH NO DATA;
        """)

        # Set up refresh policies
        await self._client.execute("""
            SELECT add_continuous_aggregate_policy('price_ohlc_1h',
                start_offset => INTERVAL '3 hours',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE
            );
        """)

        await self._client.execute("""
            SELECT add_continuous_aggregate_policy('price_ohlc_1d',
                start_offset => INTERVAL '3 days',
                end_offset => INTERVAL '1 day',
                schedule_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            );
        """)

        logger.info("TimescaleDB continuous aggregates created")

    # =========================================================================
    # Price Ticks
    # =========================================================================

    async def insert_price_tick(self, tick: PriceTick) -> None:
        """Insert a single price tick."""
        await self._client.execute(
            """
            INSERT INTO price_ticks (token_mint, timestamp, price, volume, source, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (token_mint, timestamp) DO UPDATE
            SET price = EXCLUDED.price, volume = EXCLUDED.volume
            """,
            tick.token_mint,
            tick.timestamp,
            tick.price,
            tick.volume,
            tick.source,
            tick.metadata
        )

    async def insert_price_ticks_batch(self, ticks: List[PriceTick]) -> None:
        """Insert multiple price ticks efficiently."""
        if not ticks:
            return

        args = [
            (t.token_mint, t.timestamp, t.price, t.volume, t.source, t.metadata)
            for t in ticks
        ]

        await self._client.execute_many(
            """
            INSERT INTO price_ticks (token_mint, timestamp, price, volume, source, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (token_mint, timestamp) DO UPDATE
            SET price = EXCLUDED.price, volume = EXCLUDED.volume
            """,
            args
        )

    async def get_price_ticks(
        self,
        token_mint: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get price ticks for a token within time range.

        Uses TimescaleDB's optimized time-range queries.
        """
        return await self._client.fetch(
            """
            SELECT token_mint, timestamp, price, volume, source, metadata
            FROM price_ticks
            WHERE token_mint = $1
              AND timestamp >= $2
              AND timestamp <= $3
            ORDER BY timestamp DESC
            LIMIT $4
            """,
            token_mint,
            start_time,
            end_time,
            limit
        )

    async def get_price_ohlc(
        self,
        token_mint: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get OHLC bars for a token.

        Args:
            token_mint: Token address
            interval: Time interval ("1m", "5m", "15m", "1h", "4h", "1d")
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of OHLC bars
        """
        # Map interval to time_bucket parameter
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
        }

        bucket_interval = interval_map.get(interval, interval)

        return await self._client.fetch(
            f"""
            SELECT
                time_bucket('{bucket_interval}'::interval, timestamp) AS bucket,
                first(price, timestamp) AS open,
                max(price) AS high,
                min(price) AS low,
                last(price, timestamp) AS close,
                sum(volume) AS volume
            FROM price_ticks
            WHERE token_mint = $1
              AND timestamp >= $2
              AND timestamp <= $3
            GROUP BY bucket
            ORDER BY bucket DESC
            """,
            token_mint,
            start_time,
            end_time
        )

    async def get_latest_price(self, token_mint: str) -> Optional[float]:
        """Get the most recent price for a token."""
        result = await self._client.fetchrow(
            """
            SELECT price FROM price_ticks
            WHERE token_mint = $1
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            token_mint
        )
        return result["price"] if result else None

    # =========================================================================
    # Strategy Signals
    # =========================================================================

    async def insert_strategy_signal(self, signal: StrategySignal) -> None:
        """Insert a strategy signal."""
        await self._client.execute(
            """
            INSERT INTO strategy_signals
                (strategy_id, timestamp, signal_type, confidence, token_mint, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            signal.strategy_id,
            signal.timestamp,
            signal.signal_type,
            signal.confidence,
            signal.token_mint,
            signal.metadata
        )

    async def get_strategy_signals(
        self,
        strategy_id: str,
        start_time: datetime,
        end_time: datetime,
        signal_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get strategy signals within time range."""
        if signal_type:
            return await self._client.fetch(
                """
                SELECT strategy_id, timestamp, signal_type, confidence, token_mint, metadata
                FROM strategy_signals
                WHERE strategy_id = $1
                  AND timestamp >= $2
                  AND timestamp <= $3
                  AND signal_type = $4
                ORDER BY timestamp DESC
                LIMIT $5
                """,
                strategy_id,
                start_time,
                end_time,
                signal_type,
                limit
            )
        else:
            return await self._client.fetch(
                """
                SELECT strategy_id, timestamp, signal_type, confidence, token_mint, metadata
                FROM strategy_signals
                WHERE strategy_id = $1
                  AND timestamp >= $2
                  AND timestamp <= $3
                ORDER BY timestamp DESC
                LIMIT $4
                """,
                strategy_id,
                start_time,
                end_time,
                limit
            )

    # =========================================================================
    # Position History
    # =========================================================================

    async def insert_position_snapshot(self, snapshot: PositionSnapshot) -> None:
        """Insert a position snapshot."""
        await self._client.execute(
            """
            INSERT INTO position_history
                (position_id, timestamp, pnl_sol, pnl_pct, size_tokens, current_price, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (position_id, timestamp) DO UPDATE
            SET pnl_sol = EXCLUDED.pnl_sol,
                pnl_pct = EXCLUDED.pnl_pct,
                size_tokens = EXCLUDED.size_tokens,
                current_price = EXCLUDED.current_price
            """,
            snapshot.position_id,
            snapshot.timestamp,
            snapshot.pnl_sol,
            snapshot.pnl_pct,
            snapshot.size_tokens,
            snapshot.current_price,
            snapshot.metadata
        )

    async def insert_position_snapshots_batch(self, snapshots: List[PositionSnapshot]) -> None:
        """Insert multiple position snapshots."""
        if not snapshots:
            return

        args = [
            (s.position_id, s.timestamp, s.pnl_sol, s.pnl_pct, s.size_tokens, s.current_price, s.metadata)
            for s in snapshots
        ]

        await self._client.execute_many(
            """
            INSERT INTO position_history
                (position_id, timestamp, pnl_sol, pnl_pct, size_tokens, current_price, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (position_id, timestamp) DO UPDATE
            SET pnl_sol = EXCLUDED.pnl_sol,
                pnl_pct = EXCLUDED.pnl_pct
            """,
            args
        )

    async def get_position_history(
        self,
        position_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get position history within time range."""
        return await self._client.fetch(
            """
            SELECT position_id, timestamp, pnl_sol, pnl_pct, size_tokens, current_price, metadata
            FROM position_history
            WHERE position_id = $1
              AND timestamp >= $2
              AND timestamp <= $3
            ORDER BY timestamp DESC
            LIMIT $4
            """,
            position_id,
            start_time,
            end_time,
            limit
        )

    async def get_position_pnl_summary(
        self,
        position_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get PnL summary for a position over time range."""
        return await self._client.fetchrow(
            """
            SELECT
                position_id,
                first(pnl_sol, timestamp) AS start_pnl_sol,
                last(pnl_sol, timestamp) AS end_pnl_sol,
                max(pnl_sol) AS max_pnl_sol,
                min(pnl_sol) AS min_pnl_sol,
                max(pnl_pct) AS max_pnl_pct,
                min(pnl_pct) AS min_pnl_pct,
                count(*) AS snapshot_count
            FROM position_history
            WHERE position_id = $1
              AND timestamp >= $2
              AND timestamp <= $3
            GROUP BY position_id
            """,
            position_id,
            start_time,
            end_time
        )


# Global singleton
_timescale_repo: Optional[TimescaleRepository] = None


def get_timescale_repository() -> TimescaleRepository:
    """
    Get or create global TimescaleDB repository.

    Returns:
        Global TimescaleRepository singleton
    """
    global _timescale_repo
    if _timescale_repo is None:
        _timescale_repo = TimescaleRepository()
    return _timescale_repo


async def init_timescale(connection_url: Optional[str] = None) -> TimescaleRepository:
    """
    Initialize TimescaleDB repository and create hypertables.

    Args:
        connection_url: PostgreSQL connection URL

    Returns:
        Initialized TimescaleRepository
    """
    global _timescale_repo
    _timescale_repo = TimescaleRepository(connection_url=connection_url)
    await _timescale_repo.setup_hypertables()
    return _timescale_repo
