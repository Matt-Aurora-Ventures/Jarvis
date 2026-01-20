"""
Tests for database migration system.

Verifies:
- Version tracking works correctly
- Forward migrations are applied in order
- Backward migrations (rollback) work
- Automatic migration on startup
- Migration history is recorded
- Errors are handled gracefully
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import will fail until we implement the module
from core.data.migrations import (
    Migration,
    MigrationRunner,
    MigrationHistory,
    MigrationError,
    get_migration_runner,
)


class TestMigration:
    """Test Migration dataclass."""

    def test_migration_creation(self):
        """Test creating a migration."""
        migration = Migration(
            version=1,
            name="create_users_table",
            up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE users;",
        )

        assert migration.version == 1
        assert migration.name == "create_users_table"
        assert "CREATE TABLE" in migration.up_sql
        assert "DROP TABLE" in migration.down_sql

    def test_migration_comparison(self):
        """Test migrations are compared by version."""
        m1 = Migration(version=1, name="first", up_sql="", down_sql="")
        m2 = Migration(version=2, name="second", up_sql="", down_sql="")

        assert m1 < m2
        assert m2 > m1

    def test_migration_equality(self):
        """Test migration equality by version."""
        m1 = Migration(version=1, name="first", up_sql="", down_sql="")
        m2 = Migration(version=1, name="different_name", up_sql="", down_sql="")

        assert m1 == m2  # Same version = equal

    def test_migration_with_callable(self):
        """Test migration with callable functions."""

        async def up_func(conn):
            await conn.execute("CREATE TABLE test;")

        async def down_func(conn):
            await conn.execute("DROP TABLE test;")

        migration = Migration(
            version=1,
            name="callable_migration",
            up_sql=up_func,
            down_sql=down_func,
        )

        assert callable(migration.up_sql)
        assert callable(migration.down_sql)


class TestMigrationHistory:
    """Test MigrationHistory model."""

    def test_history_entry_creation(self):
        """Test creating a history entry."""
        entry = MigrationHistory(
            version=1,
            name="test_migration",
            applied_at=datetime.utcnow(),
            success=True,
        )

        assert entry.version == 1
        assert entry.name == "test_migration"
        assert entry.success is True

    def test_history_entry_with_error(self):
        """Test history entry for failed migration."""
        entry = MigrationHistory(
            version=1,
            name="failed_migration",
            applied_at=datetime.utcnow(),
            success=False,
            error_message="Table already exists",
        )

        assert entry.success is False
        assert entry.error_message == "Table already exists"


class TestMigrationRunner:
    """Test MigrationRunner class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        try:
            os.unlink(f.name)
        except Exception:
            pass

    @pytest.fixture
    def sample_migrations(self):
        """Create sample migrations for testing."""
        return [
            Migration(
                version=1,
                name="create_users",
                up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
                down_sql="DROP TABLE users;",
            ),
            Migration(
                version=2,
                name="add_email",
                up_sql="ALTER TABLE users ADD COLUMN email TEXT;",
                down_sql="ALTER TABLE users DROP COLUMN email;",
            ),
            Migration(
                version=3,
                name="create_posts",
                up_sql="CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER);",
                down_sql="DROP TABLE posts;",
            ),
        ]

    @pytest.mark.asyncio
    async def test_runner_initialization(self, temp_db_path):
        """Test runner initializes correctly."""
        runner = MigrationRunner(db_path=temp_db_path)

        assert runner.db_path == temp_db_path
        assert runner._migrations == []

    @pytest.mark.asyncio
    async def test_register_migration(self, temp_db_path, sample_migrations):
        """Test registering migrations."""
        runner = MigrationRunner(db_path=temp_db_path)

        for m in sample_migrations:
            runner.register(m)

        assert len(runner._migrations) == 3
        # Should be sorted by version
        assert runner._migrations[0].version == 1
        assert runner._migrations[1].version == 2
        assert runner._migrations[2].version == 3

    @pytest.mark.asyncio
    async def test_get_current_version_empty(self, temp_db_path):
        """Test getting current version when no migrations applied."""
        runner = MigrationRunner(db_path=temp_db_path)
        await runner.initialize()

        version = await runner.get_current_version()
        assert version == 0

    @pytest.mark.asyncio
    async def test_migrate_up_single(self, temp_db_path, sample_migrations):
        """Test running a single migration up."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        result = await runner.migrate(target_version=1)

        assert result.success is True
        assert result.version == 1
        assert await runner.get_current_version() == 1

    @pytest.mark.asyncio
    async def test_migrate_up_all(self, temp_db_path, sample_migrations):
        """Test running all migrations up."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        result = await runner.migrate()  # No target = migrate to latest

        assert result.success is True
        assert result.version == 3
        assert await runner.get_current_version() == 3

    @pytest.mark.asyncio
    async def test_migrate_down_single(self, temp_db_path, sample_migrations):
        """Test rolling back a single migration."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        await runner.migrate(target_version=3)
        assert await runner.get_current_version() == 3

        # Rollback to version 2
        result = await runner.rollback(target_version=2)

        assert result.success is True
        assert await runner.get_current_version() == 2

    @pytest.mark.asyncio
    async def test_migrate_down_all(self, temp_db_path, sample_migrations):
        """Test rolling back all migrations."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        await runner.migrate()  # Apply all
        assert await runner.get_current_version() == 3

        # Rollback to 0
        result = await runner.rollback(target_version=0)

        assert result.success is True
        assert await runner.get_current_version() == 0

    @pytest.mark.asyncio
    async def test_migrate_idempotent(self, temp_db_path, sample_migrations):
        """Test that running migrations twice is safe."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        await runner.migrate(target_version=2)
        await runner.migrate(target_version=2)  # Should be no-op

        assert await runner.get_current_version() == 2

    @pytest.mark.asyncio
    async def test_pending_migrations(self, temp_db_path, sample_migrations):
        """Test getting list of pending migrations."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        pending = await runner.get_pending_migrations()

        assert len(pending) == 3
        assert pending[0].version == 1
        assert pending[1].version == 2
        assert pending[2].version == 3

        # Apply one
        await runner.migrate(target_version=1)
        pending = await runner.get_pending_migrations()

        assert len(pending) == 2
        assert pending[0].version == 2

    @pytest.mark.asyncio
    async def test_migration_history(self, temp_db_path, sample_migrations):
        """Test that migration history is recorded."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        await runner.migrate(target_version=2)

        history = await runner.get_history()

        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].success is True
        assert history[1].version == 2
        assert history[1].success is True

    @pytest.mark.asyncio
    async def test_migration_error_handling(self, temp_db_path):
        """Test that migration errors are handled gracefully."""
        runner = MigrationRunner(db_path=temp_db_path)

        # Invalid SQL migration
        bad_migration = Migration(
            version=1,
            name="bad_sql",
            up_sql="INVALID SQL SYNTAX HERE!!!",
            down_sql="DROP TABLE nonexistent;",
        )
        runner.register(bad_migration)

        await runner.initialize()

        with pytest.raises(MigrationError) as exc_info:
            await runner.migrate()

        assert "bad_sql" in str(exc_info.value)
        # Should still be at version 0
        assert await runner.get_current_version() == 0

    @pytest.mark.asyncio
    async def test_migration_error_recorded_in_history(self, temp_db_path):
        """Test that failed migrations are recorded in history."""
        runner = MigrationRunner(db_path=temp_db_path)

        bad_migration = Migration(
            version=1,
            name="bad_migration",
            up_sql="INVALID SQL",
            down_sql="",
        )
        runner.register(bad_migration)

        await runner.initialize()

        try:
            await runner.migrate()
        except MigrationError:
            pass

        history = await runner.get_history(include_failed=True)
        failed = [h for h in history if not h.success]

        assert len(failed) == 1
        assert failed[0].version == 1
        assert failed[0].error_message is not None

    @pytest.mark.asyncio
    async def test_callable_migration(self, temp_db_path):
        """Test migration with callable functions."""
        executed = {"up": False, "down": False}

        async def up_func(conn):
            executed["up"] = True
            await conn.execute("CREATE TABLE test_callable (id INTEGER);")

        async def down_func(conn):
            executed["down"] = True
            await conn.execute("DROP TABLE test_callable;")

        runner = MigrationRunner(db_path=temp_db_path)
        runner.register(
            Migration(
                version=1,
                name="callable_test",
                up_sql=up_func,
                down_sql=down_func,
            )
        )

        await runner.initialize()
        await runner.migrate()

        assert executed["up"] is True

        await runner.rollback(target_version=0)
        assert executed["down"] is True

    @pytest.mark.asyncio
    async def test_auto_migrate_on_startup(self, temp_db_path, sample_migrations):
        """Test automatic migration on startup."""
        runner = MigrationRunner(db_path=temp_db_path, auto_migrate=True)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()  # Should auto-migrate

        assert await runner.get_current_version() == 3

    @pytest.mark.asyncio
    async def test_skip_auto_migrate(self, temp_db_path, sample_migrations):
        """Test skipping automatic migration."""
        runner = MigrationRunner(db_path=temp_db_path, auto_migrate=False)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()  # Should NOT auto-migrate

        assert await runner.get_current_version() == 0

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, temp_db_path, sample_migrations):
        """Test dry run mode shows what would be applied."""
        runner = MigrationRunner(db_path=temp_db_path)
        for m in sample_migrations:
            runner.register(m)

        await runner.initialize()
        result = await runner.migrate(dry_run=True)

        assert result.dry_run is True
        assert len(result.would_apply) == 3
        # Should not have actually migrated
        assert await runner.get_current_version() == 0


class TestMigrationRunnerLogging:
    """Test migration logging."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        try:
            os.unlink(f.name)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_migration_logs_start(self, temp_db_path, caplog):
        """Test that migration start is logged."""
        import logging

        caplog.set_level(logging.INFO)

        runner = MigrationRunner(db_path=temp_db_path)
        runner.register(
            Migration(
                version=1,
                name="test_migration",
                up_sql="CREATE TABLE t (id INTEGER);",
                down_sql="DROP TABLE t;",
            )
        )

        await runner.initialize()
        await runner.migrate()

        assert any("Applying migration" in record.message for record in caplog.records)
        assert any("test_migration" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_migration_logs_completion(self, temp_db_path, caplog):
        """Test that migration completion is logged."""
        import logging

        caplog.set_level(logging.INFO)

        runner = MigrationRunner(db_path=temp_db_path)
        runner.register(
            Migration(
                version=1,
                name="test_migration",
                up_sql="CREATE TABLE t (id INTEGER);",
                down_sql="DROP TABLE t;",
            )
        )

        await runner.initialize()
        await runner.migrate()

        assert any("completed" in record.message.lower() for record in caplog.records)


class TestMigrationRunnerConcurrency:
    """Test concurrent migration safety."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        try:
            os.unlink(f.name)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_concurrent_migrations_safe(self, temp_db_path):
        """Test that concurrent migrations don't corrupt state."""
        runner = MigrationRunner(db_path=temp_db_path)
        runner.register(
            Migration(
                version=1,
                name="slow_migration",
                up_sql="CREATE TABLE concurrent_test (id INTEGER);",
                down_sql="DROP TABLE concurrent_test;",
            )
        )

        await runner.initialize()

        # Run two migrations concurrently
        results = await asyncio.gather(
            runner.migrate(),
            runner.migrate(),
            return_exceptions=True,
        )

        # One should succeed, one should be a no-op
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 1

        # Final state should be version 1
        assert await runner.get_current_version() == 1


class TestMigrationRunnerFactory:
    """Test get_migration_runner factory function."""

    def test_get_runner_returns_instance(self):
        """Test factory returns a runner instance."""
        runner = get_migration_runner()

        assert isinstance(runner, MigrationRunner)

    def test_get_runner_singleton(self):
        """Test factory returns same instance."""
        runner1 = get_migration_runner()
        runner2 = get_migration_runner()

        assert runner1 is runner2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
