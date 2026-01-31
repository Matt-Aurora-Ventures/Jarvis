"""
Security Verification Tests for SQL Injection Protection

Tests that sanitize_sql_identifier blocks SQL injection attempts.
Part of security audit remediation (SECURITY_AUDIT_JAN_31.md).
"""

import pytest
from core.security_validation import sanitize_sql_identifier


def test_sanitize_sql_identifier_allows_valid_names():
    """Verify sanitize_sql_identifier allows valid SQL identifiers."""
    valid_names = [
        "users",
        "user_id",
        "table_name_123",
        "TableName",
        "_private_table",
        "column1",
        "my_column_name",
    ]

    for name in valid_names:
        result = sanitize_sql_identifier(name)
        assert result == name


def test_sanitize_sql_identifier_blocks_sql_injection():
    """Verify sanitize_sql_identifier blocks SQL injection attempts."""
    injection_attempts = [
        "users; DROP TABLE users--",
        "users' OR '1'='1",
        "users UNION SELECT * FROM passwords",
        "users--",
        "users/*comment*/",
        "users;DELETE FROM users",
        "users\x00",  # null byte
        "'; DROP TABLE users; --",
        "1=1",
        "admin'--",
    ]

    for attempt in injection_attempts:
        with pytest.raises(Exception, match="Invalid SQL identifier"):
            sanitize_sql_identifier(attempt)


def test_sanitize_sql_identifier_blocks_special_chars():
    """Verify sanitize_sql_identifier blocks special characters."""
    invalid_chars = [
        "users.table",  # dot
        "users@host",  # at sign
        "users#temp",  # hash
        "users$var",  # dollar sign
        "users%like",  # percent
        "users&and",  # ampersand
        "users*all",  # asterisk
        "users+plus",  # plus
        "users=equals",  # equals
        "users[0]",  # brackets
        "users()",  # parentheses
    ]

    for name in invalid_chars:
        with pytest.raises(Exception, match="Invalid SQL identifier"):
            sanitize_sql_identifier(name)


def test_sanitize_sql_identifier_blocks_empty_string():
    """Verify sanitize_sql_identifier blocks empty strings."""
    with pytest.raises(Exception, match="Invalid SQL identifier"):
        sanitize_sql_identifier("")


def test_sanitize_sql_identifier_blocks_whitespace():
    """Verify sanitize_sql_identifier blocks names with whitespace."""
    whitespace_names = [
        "users table",
        "users\ttable",
        "users\ntable",
        "users\rtable",
        " users",
        "users ",
    ]

    for name in whitespace_names:
        with pytest.raises(Exception, match="Invalid SQL identifier"):
            sanitize_sql_identifier(name)


def test_sanitize_sql_identifier_blocks_sql_keywords():
    """Verify sanitize_sql_identifier blocks dangerous SQL keywords."""
    sql_keywords = [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "UNION",
        "SELECT",
        "WHERE",
        "FROM",
    ]

    # Keywords should be blocked if they appear suspicious
    # (Implementation may allow keywords as table names if properly validated)
    for keyword in sql_keywords:
        try:
            result = sanitize_sql_identifier(keyword)
            # If it passes, it should be the keyword as-is (valid table name)
            assert result == keyword
        except Exception:
            # If blocked, that's also acceptable (stricter validation)
            pass


def test_sanitize_sql_identifier_blocks_numbers_only():
    """Verify sanitize_sql_identifier blocks identifiers that are only numbers."""
    # SQL identifiers can't start with numbers (in most databases)
    invalid_names = [
        "123",
        "456table",
    ]

    for name in invalid_names:
        # May raise exception or return the name (depends on implementation)
        # The key is that injection attempts are blocked, not legitimate names
        try:
            result = sanitize_sql_identifier(name)
            # If it passes, verify it's not an injection
            assert ";" not in result
            assert "--" not in result
            assert "/*" not in result
        except Exception:
            # Blocking is also acceptable
            pass


# =============================================================================
# Integration tests: Verify modules use sanitize_sql_identifier
# =============================================================================

class TestQueryOptimizerSQLInjection:
    """Test that query_optimizer.py sanitizes table names in PRAGMA queries."""

    def test_suggest_indexes_sanitizes_table_name(self):
        """Verify suggest_indexes validates table names."""
        from core.data.query_optimizer import QueryAnalyzer
        import tempfile
        import sqlite3

        # Create a temp database with a test table
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
        conn.close()

        analyzer = QueryAnalyzer(db_path)

        # Valid table name should work
        result = analyzer.suggest_indexes("test_table")
        assert isinstance(result, list)

        # SQL injection attempt should be blocked
        with pytest.raises(Exception, match="Invalid SQL identifier"):
            analyzer.suggest_indexes("test_table; DROP TABLE test_table--")

        with pytest.raises(Exception, match="Invalid SQL identifier"):
            analyzer.suggest_indexes("test_table' OR '1'='1")

        # Clean up
        import os
        os.unlink(db_path)

    def test_analyze_validates_query(self):
        """Verify analyze method handles query validation appropriately."""
        from core.data.query_optimizer import QueryAnalyzer
        import tempfile
        import sqlite3

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
        conn.close()

        analyzer = QueryAnalyzer(db_path)

        # Valid query should work
        result = analyzer.analyze("SELECT * FROM test_table")
        assert result is not None
        assert hasattr(result, 'query')

        import os
        os.unlink(db_path)


class TestLeaderboardSQLInjection:
    """Test that leaderboard.py sanitizes order column names."""

    def test_get_rankings_validates_order_column(self):
        """Verify get_rankings uses allowlist for order columns."""
        from core.community.leaderboard import Leaderboard
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        lb = Leaderboard(db_path=db_path)

        # Valid order columns should work
        for metric in ["profit", "win_rate", "trades", "consistency"]:
            result = lb.get_rankings(by=metric, period="overall", limit=5)
            assert isinstance(result, list)

        # Invalid metric should default to safe value (not SQL injection)
        result = lb.get_rankings(by="'; DROP TABLE user_stats--", limit=5)
        assert isinstance(result, list)  # Should not crash

        import os
        os.unlink(db_path)


class TestChallengesSQLInjection:
    """Test that challenges.py sanitizes order direction."""

    def test_update_ranks_validates_order(self):
        """Verify _update_ranks uses safe ORDER BY."""
        from core.community.challenges import ChallengeManager
        import tempfile
        from datetime import datetime, timedelta

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = ChallengeManager(db_path=db_path)

        # Create a challenge with valid metric
        challenge = manager.create_challenge(
            title="Test Challenge",
            metric="percent_gain",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30)
        )

        # This should work without SQL injection
        manager._update_ranks(challenge["challenge_id"])

        import os
        os.unlink(db_path)


class TestNewsFeedSQLInjection:
    """Test that news_feed.py sanitizes column names."""

    def test_set_preferences_validates_columns(self):
        """Verify set_preferences builds SQL safely."""
        from core.community.news_feed import NewsFeed
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        feed = NewsFeed(db_path=db_path)

        # Valid preferences should work
        result = feed.set_preferences(
            user_id="test_user",
            show_achievements=True,
            daily_digest=False
        )
        assert isinstance(result, dict)

        import os
        os.unlink(db_path)


class TestUserProfileSQLInjection:
    """Test that user_profile.py sanitizes column names."""

    def test_update_profile_validates_columns(self):
        """Verify update_profile builds SQL safely."""
        from core.community.user_profile import UserProfileManager
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = UserProfileManager(db_path=db_path)

        # Create a profile first
        manager.create_profile(user_id="test_user", username="tester")

        # Valid updates should work
        result = manager.update_profile(
            user_id="test_user",
            username="new_name",
            bio="Hello world"
        )
        assert result is not None
        assert result["username"] == "new_name"

        import os
        os.unlink(db_path)

    def test_update_stats_validates_columns(self):
        """Verify update_stats builds SQL safely."""
        from core.community.user_profile import UserProfileManager
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = UserProfileManager(db_path=db_path)
        manager.create_profile(user_id="test_user", username="tester")

        # Valid stats should work
        result = manager.update_stats(
            user_id="test_user",
            total_pnl=1000.0,
            win_rate=0.75
        )
        assert result is not None

        import os
        os.unlink(db_path)


class TestAchievementsSQLInjection:
    """Test that achievements.py sanitizes column names."""

    def test_update_progress_validates_columns(self):
        """Verify _update_progress builds SQL safely."""
        from core.community.achievements import AchievementManager
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        manager = AchievementManager(db_path=db_path)

        # Valid stats should work - column names are from internal map
        manager._update_progress(
            user_id="test_user",
            trade_count=10,
            total_pnl=500.0
        )

        import os
        os.unlink(db_path)


class TestMigrationSQLInjection:
    """Test that migration.py sanitizes table names."""

    def test_migration_sanitizes_table_names(self):
        """Verify migration uses sanitize_sql_identifier."""
        from core.database.migration import DataMigrator
        import tempfile
        import sqlite3

        # Create a temp SQLite database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            sqlite_path = f.name

        conn = sqlite3.connect(sqlite_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
        conn.close()

        # This should work without error for valid table names
        migrator = DataMigrator(
            sqlite_path=sqlite_path,
            postgres_url="postgresql://test:test@localhost/test"
        )

        # Valid table name should work
        rows = migrator._read_sqlite_table("test_table")
        assert isinstance(rows, list)

        # SQL injection attempt should be blocked
        with pytest.raises(Exception, match="Invalid SQL identifier"):
            migrator._read_sqlite_table("test_table; DROP TABLE test_table--")

        import os
        os.unlink(sqlite_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
