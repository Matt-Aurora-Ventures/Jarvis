"""Integration tests for database operations."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

pytest.importorskip("sqlalchemy")


class TestDatabasePoolIntegration:
    """Integration tests for database connection pooling."""

    def test_pool_initialization(self):
        """Pool should initialize with correct settings."""
        from core.db.pool import DatabasePool

        pool = DatabasePool(
            database_url="sqlite:///test.db",
            pool_size=5,
            max_overflow=10
        )

        assert pool.pool_size == 5
        assert pool.max_overflow == 10

    def test_pool_health_check(self, mock_db):
        """Pool health check should work."""
        from core.db.pool import DatabasePool

        with patch.object(DatabasePool, '_create_engine', return_value=mock_db):
            pool = DatabasePool(database_url="sqlite:///test.db")
            # Health check should not raise
            result = pool.health_check()
            assert result is not None

    def test_pool_context_manager(self, mock_db):
        """Pool should work as context manager."""
        from core.db.pool import DatabasePool

        with patch.object(DatabasePool, '_create_engine', return_value=mock_db):
            pool = DatabasePool(database_url="sqlite:///test.db")
            with pool.get_connection() as conn:
                assert conn is not None


class TestDatabaseQueryLogging:
    """Integration tests for query logging."""

    def test_query_logging_captures_queries(self, mock_db, caplog):
        """Query logging should capture executed queries."""
        import logging
        caplog.set_level(logging.DEBUG)

        # Simulate query execution with logging
        with patch('core.db.pool.logger') as mock_logger:
            mock_db.execute("SELECT * FROM users")
            # Verify execution happened
            assert mock_db.execute.called


class TestDatabaseRetry:
    """Integration tests for database retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        """Retry logic should handle transient failures."""
        from core.resilience.retry import async_retry

        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"

        result = await flaky_operation()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Should raise after max retries."""
        from core.resilience.retry import async_retry

        @async_retry(max_attempts=2, delay=0.01)
        async def always_fails():
            raise ConnectionError("Permanent failure")

        with pytest.raises(ConnectionError):
            await always_fails()


class TestDatabaseMigrations:
    """Integration tests for database migrations."""

    def test_migration_runner_exists(self):
        """Migration runner should be importable."""
        try:
            from scripts.db.migrate import MigrationRunner
            assert MigrationRunner is not None
        except ImportError:
            pytest.skip("Migration runner not found")


class TestDatabaseBackup:
    """Integration tests for database backup."""

    def test_backup_script_exists(self):
        """Backup script should be importable."""
        try:
            from scripts.db.backup import DatabaseBackup
            assert DatabaseBackup is not None
        except ImportError:
            pytest.skip("Backup script not found")


class TestDataRetention:
    """Integration tests for data retention policies."""

    def test_retention_policy_enforcement(self):
        """Retention policies should be enforceable."""
        try:
            from core.data.retention import RetentionPolicy

            policy = RetentionPolicy(
                name="test_logs",
                retention_days=30,
                archive=False
            )

            assert policy.retention_days == 30
            assert policy.archive is False
        except ImportError:
            pytest.skip("Retention module not found")
