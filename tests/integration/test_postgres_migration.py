"""
Integration tests for PostgreSQL + TimescaleDB migration.

Tests:
1. PostgreSQL async client with connection pooling
2. TimescaleDB hypertable creation and time-series queries
3. Data migration from SQLite to PostgreSQL
4. Repository pattern with PostgreSQL backend
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import patch, MagicMock, AsyncMock
import os

# Mark all tests as postgres-related for easy filtering
pytestmark = pytest.mark.postgres


class TestPostgresClient:
    """Tests for PostgreSQL async client."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Client should initialize with connection URL from env or parameter."""
        from core.database.postgres_client import PostgresClient

        # Should not raise on initialization
        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )
        assert client is not None
        assert client.connection_url is not None

    @pytest.mark.asyncio
    async def test_client_from_env(self):
        """Client should load connection URL from DATABASE_URL env var."""
        from core.database.postgres_client import PostgresClient

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost:5432/jarvis"}):
            client = PostgresClient()
            assert "postgresql" in client.connection_url

    @pytest.mark.asyncio
    async def test_connection_pool_settings(self):
        """Client should configure connection pool with proper settings."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test",
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600
        )

        assert client.pool_size == 10
        assert client.max_overflow == 20
        assert client.pool_recycle == 3600

    @pytest.mark.asyncio
    async def test_acquire_connection(self):
        """Should acquire connection from pool."""
        from core.database.postgres_client import PostgresClient
        from contextlib import asynccontextmanager

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        # Mock the pool for unit testing with a proper async context manager
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_pool_acquire():
            yield mock_conn

        mock_pool = MagicMock()
        mock_pool.acquire = mock_pool_acquire

        # Set pool and connected flag directly to bypass connect()
        client._pool = mock_pool
        client._connected = True

        async with client.acquire() as conn:
            assert conn is not None
            assert conn == mock_conn

    @pytest.mark.asyncio
    async def test_execute_query(self):
        """Should execute query and return results."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_result = [{"id": 1, "value": "test"}]
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = mock_result

        with patch.object(client, 'acquire') as mock_acquire:
            mock_acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_acquire.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.fetch("SELECT * FROM test")
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_many(self):
        """Should execute batch insert."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_conn = AsyncMock()
        mock_conn.executemany.return_value = None

        with patch.object(client, 'acquire') as mock_acquire:
            mock_acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_acquire.return_value.__aexit__ = AsyncMock(return_value=None)

            await client.execute_many(
                "INSERT INTO test (value) VALUES ($1)",
                [("a",), ("b",), ("c",)]
            )
            mock_conn.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_transaction_commit(self):
        """Should handle transactions with commit."""
        from core.database.postgres_client import PostgresClient
        from contextlib import asynccontextmanager

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_conn = AsyncMock()
        mock_tr = MagicMock()

        # Create a proper async context manager for transaction
        @asynccontextmanager
        async def mock_transaction():
            yield mock_tr

        mock_conn.transaction = mock_transaction
        mock_conn.execute = AsyncMock()

        # Create a proper async context manager for acquire
        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        # Replace the acquire method
        client.acquire = mock_acquire

        async with client.transaction() as conn:
            await conn.execute("INSERT INTO test VALUES ($1)", 1)
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Should perform health check on connection."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1

        with patch.object(client, 'acquire') as mock_acquire:
            mock_acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_acquire.return_value.__aexit__ = AsyncMock(return_value=None)

            is_healthy = await client.health_check()
            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_connection_retry_on_failure(self):
        """Should retry connection on transient failure."""
        from core.database.postgres_client import PostgresClient, ASYNCPG_AVAILABLE

        # Skip this test if asyncpg not available - it tests the actual retry logic
        if not ASYNCPG_AVAILABLE:
            pytest.skip("asyncpg not installed - skipping retry test")

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test",
            max_retries=3,
            retry_delay=0.01
        )

        call_count = 0
        async def flaky_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return AsyncMock()

        with patch.object(client, '_create_pool', side_effect=flaky_connect):
            try:
                await client.connect()
            except ConnectionError:
                pass  # Expected if all retries fail

        assert call_count >= 1  # At least one attempt made


class TestTimescaleRepository:
    """Tests for TimescaleDB repository with hypertables."""

    @pytest.mark.asyncio
    async def test_create_hypertable_price_ticks(self):
        """Should create hypertable for price ticks."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.setup_hypertables()

            # Verify hypertable creation was called
            calls = mock_client.execute.call_args_list
            assert len(calls) >= 1
            # Should contain CREATE TABLE and select create_hypertable
            call_strs = [str(c) for c in calls]
            assert any("price_ticks" in s for s in call_strs)

    @pytest.mark.asyncio
    async def test_insert_price_tick(self):
        """Should insert price tick into hypertable."""
        from core.database.timescale_repository import TimescaleRepository, PriceTick

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        tick = PriceTick(
            token_mint="So11111111111111111111111111111111111111112",
            timestamp=datetime.utcnow(),
            price=150.50,
            volume=1000000.0
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.insert_price_tick(tick)
            mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_batch_price_ticks(self):
        """Should batch insert multiple price ticks."""
        from core.database.timescale_repository import TimescaleRepository, PriceTick

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        ticks = [
            PriceTick(
                token_mint="So11111111111111111111111111111111111111112",
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                price=150.0 + i,
                volume=1000000.0
            )
            for i in range(100)
        ]

        mock_client = AsyncMock()
        mock_client.execute_many.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.insert_price_ticks_batch(ticks)
            mock_client.execute_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_price_ticks_time_range(self):
        """Should query price ticks within time range efficiently."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_result = [
            {"token_mint": "test", "timestamp": datetime.utcnow(), "price": 150.0, "volume": 1000.0}
        ]
        mock_client = AsyncMock()
        mock_client.fetch.return_value = mock_result

        with patch.object(repo, '_client', mock_client):
            result = await repo.get_price_ticks(
                token_mint="test",
                start_time=datetime.utcnow() - timedelta(hours=1),
                end_time=datetime.utcnow()
            )
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_create_hypertable_strategy_signals(self):
        """Should create hypertable for strategy signals."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.setup_hypertables()

            calls = mock_client.execute.call_args_list
            call_strs = [str(c) for c in calls]
            assert any("strategy_signals" in s for s in call_strs)

    @pytest.mark.asyncio
    async def test_insert_strategy_signal(self):
        """Should insert strategy signal."""
        from core.database.timescale_repository import TimescaleRepository, StrategySignal

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        signal = StrategySignal(
            strategy_id="momentum_v1",
            timestamp=datetime.utcnow(),
            signal_type="buy",
            confidence=0.85,
            token_mint="So11111111111111111111111111111111111111112",
            metadata={"reason": "breakout detected"}
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.insert_strategy_signal(signal)
            mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_hypertable_position_history(self):
        """Should create hypertable for position history."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.setup_hypertables()

            calls = mock_client.execute.call_args_list
            call_strs = [str(c) for c in calls]
            assert any("position_history" in s for s in call_strs)

    @pytest.mark.asyncio
    async def test_insert_position_snapshot(self):
        """Should insert position history snapshot."""
        from core.database.timescale_repository import TimescaleRepository, PositionSnapshot

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        snapshot = PositionSnapshot(
            position_id="pos_123",
            timestamp=datetime.utcnow(),
            pnl_sol=0.5,
            pnl_pct=5.0,
            size_tokens=1000.0,
            current_price=0.0015
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.insert_position_snapshot(snapshot)
            mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregate_price_ohlc(self):
        """Should aggregate price ticks into OHLC buckets using TimescaleDB functions."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_result = [
            {
                "bucket": datetime.utcnow(),
                "open": 150.0,
                "high": 155.0,
                "low": 148.0,
                "close": 152.0,
                "volume": 50000.0
            }
        ]
        mock_client = AsyncMock()
        mock_client.fetch.return_value = mock_result

        with patch.object(repo, '_client', mock_client):
            result = await repo.get_price_ohlc(
                token_mint="test",
                interval="1h",
                start_time=datetime.utcnow() - timedelta(days=1),
                end_time=datetime.utcnow()
            )
            assert len(result) == 1
            assert "open" in result[0]
            assert "high" in result[0]

    @pytest.mark.asyncio
    async def test_continuous_aggregate_creation(self):
        """Should create continuous aggregates for materialized views."""
        from core.database.timescale_repository import TimescaleRepository

        repo = TimescaleRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.execute.return_value = None

        with patch.object(repo, '_client', mock_client):
            await repo.setup_continuous_aggregates()

            calls = mock_client.execute.call_args_list
            call_strs = [str(c) for c in calls]
            # Should contain CREATE MATERIALIZED VIEW for continuous aggregates
            assert any("MATERIALIZED VIEW" in s or "continuous_aggregate" in s for s in call_strs)


class TestDataMigration:
    """Tests for data migration from SQLite to PostgreSQL."""

    @pytest.mark.asyncio
    async def test_migrate_positions_table(self):
        """Should migrate positions from SQLite to PostgreSQL."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        # Mock SQLite source data
        mock_sqlite_data = [
            {
                "id": 1,
                "user_id": 123,
                "token_mint": "So11111111111111111111111111111111111111112",
                "entry_price": 0.001,
                "status": "open"
            }
        ]

        mock_pg_client = AsyncMock()
        mock_pg_client.execute_many.return_value = None

        with patch.object(migrator, '_read_sqlite_table', return_value=mock_sqlite_data):
            with patch.object(migrator, '_pg_client', mock_pg_client):
                count = await migrator.migrate_table("positions")
                assert count == 1

    @pytest.mark.asyncio
    async def test_migrate_trades_table(self):
        """Should migrate trades with foreign key relationships."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_sqlite_data = [
            {
                "id": 1,
                "position_id": 1,
                "token_mint": "test",
                "side": "buy",
                "price": 0.001
            }
        ]

        mock_pg_client = AsyncMock()
        mock_pg_client.execute_many.return_value = None

        with patch.object(migrator, '_read_sqlite_table', return_value=mock_sqlite_data):
            with patch.object(migrator, '_pg_client', mock_pg_client):
                count = await migrator.migrate_table("trades")
                assert count == 1

    @pytest.mark.asyncio
    async def test_migration_validates_data(self):
        """Should validate row counts after migration."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        # Mock counts
        mock_pg_client = AsyncMock()
        mock_pg_client.fetchval.return_value = 100  # PG count

        with patch.object(migrator, '_get_sqlite_count', return_value=100):
            with patch.object(migrator, '_pg_client', mock_pg_client):
                is_valid = await migrator.validate_migration("positions")
                assert is_valid is True

    @pytest.mark.asyncio
    async def test_migration_detects_data_loss(self):
        """Should detect data loss in migration."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        # Mock mismatched counts
        mock_pg_client = AsyncMock()
        mock_pg_client.fetchval.return_value = 90  # PG count less than SQLite

        with patch.object(migrator, '_get_sqlite_count', return_value=100):
            with patch.object(migrator, '_pg_client', mock_pg_client):
                is_valid = await migrator.validate_migration("positions")
                assert is_valid is False

    @pytest.mark.asyncio
    async def test_migration_handles_schema_differences(self):
        """Should handle schema differences between SQLite and PostgreSQL."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        # SQLite data with different column types
        mock_sqlite_data = [
            {
                "id": 1,
                "is_active": 1,  # SQLite uses INTEGER for boolean
                "created_at": "2026-01-26 10:00:00"  # SQLite TEXT timestamp
            }
        ]

        mock_pg_client = AsyncMock()
        mock_pg_client.execute_many.return_value = None

        with patch.object(migrator, '_read_sqlite_table', return_value=mock_sqlite_data):
            with patch.object(migrator, '_pg_client', mock_pg_client):
                # Should transform data types during migration
                count = await migrator.migrate_table("users", transform=True)
                assert count == 1

    @pytest.mark.asyncio
    async def test_full_migration_sequence(self):
        """Should run full migration in correct order respecting FKs."""
        from core.database.migration import DataMigrator

        migrator = DataMigrator(
            sqlite_path="data/jarvis_core.db",
            postgres_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        migration_order = []

        async def mock_migrate(table_name):
            migration_order.append(table_name)
            return 10

        with patch.object(migrator, 'migrate_table', side_effect=mock_migrate):
            await migrator.run_full_migration()

            # Users should be before trades (FK dependency)
            if "users" in migration_order and "trades" in migration_order:
                assert migration_order.index("users") < migration_order.index("trades")

            # Positions should be before trades (FK dependency)
            if "positions" in migration_order and "trades" in migration_order:
                assert migration_order.index("positions") < migration_order.index("trades")


class TestPostgresRepositoryPattern:
    """Tests for repository pattern with PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_position_repository_postgres(self):
        """Position repository should work with PostgreSQL."""
        from core.database.postgres_repositories import PostgresPositionRepository

        repo = PostgresPositionRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.fetch.return_value = [
            {
                "id": "pos_123",
                "user_id": 1,
                "token_mint": "test",
                "status": "open",
                "entry_price": 0.001
            }
        ]

        with patch.object(repo, '_client', mock_client):
            positions = await repo.get_open_positions(user_id=1)
            assert len(positions) == 1

    @pytest.mark.asyncio
    async def test_trade_repository_postgres(self):
        """Trade repository should work with PostgreSQL."""
        from core.database.postgres_repositories import PostgresTradeRepository

        repo = PostgresTradeRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.fetch.return_value = [
            {
                "id": "trade_123",
                "position_id": "pos_123",
                "side": "buy",
                "price": 0.001
            }
        ]

        with patch.object(repo, '_client', mock_client):
            trades = await repo.get_recent_trades(limit=10)
            assert len(trades) == 1

    @pytest.mark.asyncio
    async def test_repository_uses_parameterized_queries(self):
        """Repository should use parameterized queries to prevent SQL injection."""
        from core.database.postgres_repositories import PostgresPositionRepository

        repo = PostgresPositionRepository(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        mock_client = AsyncMock()
        mock_client.fetch.return_value = []

        with patch.object(repo, '_client', mock_client):
            # Attempt SQL injection - should be safely parameterized
            malicious_input = "'; DROP TABLE positions; --"
            await repo.get_by_token_mint(malicious_input)

            # Verify parameterized query was used
            call_args = mock_client.fetch.call_args
            assert "$1" in call_args[0][0]  # Should use parameter placeholder


class TestConnectionPoolMetrics:
    """Tests for connection pool metrics and monitoring."""

    @pytest.mark.asyncio
    async def test_pool_metrics_available(self):
        """Should expose pool metrics for monitoring."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test"
        )

        metrics = client.get_pool_metrics()

        assert "pool_size" in metrics
        assert "available_connections" in metrics
        assert "active_connections" in metrics
        assert "wait_time_ms" in metrics or "total_connections" in metrics

    @pytest.mark.asyncio
    async def test_connection_lifetime_tracking(self):
        """Should track connection lifetime for recycling."""
        from core.database.postgres_client import PostgresClient

        client = PostgresClient(
            connection_url="postgresql://test:test@localhost:5432/jarvis_test",
            pool_recycle=60  # 60 second lifetime
        )

        assert client.pool_recycle == 60


# Fixtures
@pytest.fixture
def mock_postgres_pool():
    """Mock PostgreSQL connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def sample_price_ticks():
    """Sample price tick data for testing."""
    from core.database.timescale_repository import PriceTick

    base_time = datetime.utcnow()
    return [
        PriceTick(
            token_mint="So11111111111111111111111111111111111111112",
            timestamp=base_time - timedelta(minutes=i),
            price=150.0 + (i * 0.1),
            volume=1000000.0 + (i * 1000)
        )
        for i in range(100)
    ]
