"""
Tests for Data Consent Module.

Tests consent management, GDPR compliance, and data deletion.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os
import json

# Import modules to test
from core.data_consent.models import (
    ConsentTier,
    DataCategory,
    ConsentRecord,
    DataDeletionRequest,
    get_consent_terms,
    init_database,
)
from core.data_consent.manager import ConsentManager


class TestConsentTier:
    """Tests for ConsentTier enum."""

    def test_tier_values(self):
        """Test tier values exist."""
        assert ConsentTier.TIER_0.value == "tier_0"
        assert ConsentTier.TIER_1.value == "tier_1"
        assert ConsentTier.TIER_2.value == "tier_2"

    def test_tier_descriptions(self):
        """Test tier meanings from terms."""
        terms = get_consent_terms("1.0")

        assert ConsentTier.TIER_0 in terms["summary"]
        assert ConsentTier.TIER_1 in terms["summary"]
        assert ConsentTier.TIER_2 in terms["summary"]


class TestDataCategory:
    """Tests for DataCategory enum."""

    def test_category_values(self):
        """Test category values exist."""
        assert DataCategory.TRADE_PATTERNS.value == "trade_patterns"
        assert DataCategory.FEATURE_USAGE.value == "feature_usage"
        assert DataCategory.SENTIMENT_DATA.value == "sentiment"

    def test_improvement_categories(self):
        """Test improvement categories for TIER_1."""
        cats = DataCategory.improvement_categories()

        assert DataCategory.FEATURE_USAGE in cats
        assert DataCategory.ERROR_PATTERNS in cats
        assert DataCategory.SESSION_PATTERNS in cats
        # Trading data should NOT be in improvement
        assert DataCategory.TRADE_PATTERNS not in cats

    def test_marketplace_categories(self):
        """Test marketplace categories for TIER_2."""
        cats = DataCategory.marketplace_categories()

        assert DataCategory.TRADE_PATTERNS in cats
        assert DataCategory.STRATEGY_PERFORMANCE in cats
        assert DataCategory.SENTIMENT_DATA in cats


class TestConsentRecord:
    """Tests for ConsentRecord model."""

    def test_record_creation(self):
        """Test ConsentRecord creation."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_1,
            categories=DataCategory.improvement_categories(),
        )

        assert record.user_id == "user_123"
        assert record.tier == ConsentTier.TIER_1
        assert record.revoked is False

    def test_record_allows_improvement_category(self):
        """Test TIER_1 allows improvement categories."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_1,
            categories=DataCategory.improvement_categories(),
        )

        assert record.allows_category(DataCategory.FEATURE_USAGE) is True
        assert record.allows_category(DataCategory.TRADE_PATTERNS) is False

    def test_record_allows_marketplace_category(self):
        """Test TIER_2 allows marketplace categories."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_2,
            categories=(
                DataCategory.improvement_categories() +
                DataCategory.marketplace_categories()
            ),
        )

        assert record.allows_category(DataCategory.FEATURE_USAGE) is True
        assert record.allows_category(DataCategory.TRADE_PATTERNS) is True
        assert record.allows_category(DataCategory.SENTIMENT_DATA) is True

    def test_record_tier_0_denies_all(self):
        """Test TIER_0 denies all categories."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_0,
            categories=[],
        )

        assert record.allows_category(DataCategory.FEATURE_USAGE) is False
        assert record.allows_category(DataCategory.TRADE_PATTERNS) is False

    def test_revoked_record_denies_all(self):
        """Test revoked consent denies all categories."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_2,
            categories=DataCategory.marketplace_categories(),
            revoked=True,
        )

        assert record.allows_category(DataCategory.TRADE_PATTERNS) is False

    def test_record_to_dict(self):
        """Test record serialization."""
        record = ConsentRecord(
            user_id="user_123",
            tier=ConsentTier.TIER_1,
            categories=DataCategory.improvement_categories(),
        )

        data = record.to_dict()

        assert data["user_id"] == "user_123"
        assert data["tier"] == "tier_1"
        assert isinstance(data["categories"], list)


class TestDataDeletionRequest:
    """Tests for DataDeletionRequest model."""

    def test_request_creation(self):
        """Test deletion request creation."""
        request = DataDeletionRequest(
            id=1,
            user_id="user_123",
            categories=[DataCategory.TRADE_PATTERNS],
            status="pending",
        )

        assert request.id == 1
        assert request.status == "pending"

    def test_request_to_dict(self):
        """Test request serialization."""
        request = DataDeletionRequest(
            id=1,
            user_id="user_123",
            categories=[DataCategory.TRADE_PATTERNS],
            status="pending",
        )

        data = request.to_dict()

        assert data["id"] == 1
        assert data["status"] == "pending"


class TestConsentManager:
    """Tests for ConsentManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ConsentManager with temp database."""
        db_path = str(tmp_path / "test_consent.db")
        return ConsentManager(db_path=db_path)

    def test_record_consent_tier_1(self, manager):
        """Test recording TIER_1 consent."""
        record = manager.record_consent(
            user_id="user_123",
            tier=ConsentTier.TIER_1,
            ip_address="192.168.1.1",
        )

        assert record.tier == ConsentTier.TIER_1
        assert record.ip_address == "192.168.1.1"
        assert len(record.categories) == 3  # Improvement categories

    def test_record_consent_tier_2(self, manager):
        """Test recording TIER_2 consent."""
        record = manager.record_consent(
            user_id="user_123",
            tier=ConsentTier.TIER_2,
            ip_address="192.168.1.1",
        )

        assert record.tier == ConsentTier.TIER_2
        assert len(record.categories) == 8  # All categories

    def test_get_consent(self, manager):
        """Test consent retrieval."""
        manager.record_consent("user_123", ConsentTier.TIER_1)

        record = manager.get_consent("user_123")

        assert record is not None
        assert record.tier == ConsentTier.TIER_1

    def test_get_consent_nonexistent(self, manager):
        """Test consent retrieval for nonexistent user."""
        record = manager.get_consent("nonexistent")

        assert record is None

    def test_check_consent_true(self, manager):
        """Test consent check returns true when consented."""
        manager.record_consent("user_123", ConsentTier.TIER_1)

        assert manager.check_consent("user_123") is True
        assert manager.check_consent("user_123", DataCategory.FEATURE_USAGE) is True

    def test_check_consent_false(self, manager):
        """Test consent check returns false when not consented."""
        manager.record_consent("user_123", ConsentTier.TIER_0)

        assert manager.check_consent("user_123") is False

    def test_check_consent_category_not_allowed(self, manager):
        """Test consent check for category not allowed by tier."""
        manager.record_consent("user_123", ConsentTier.TIER_1)

        # TIER_1 should not allow TRADE_PATTERNS
        assert manager.check_consent("user_123", DataCategory.TRADE_PATTERNS) is False

    def test_revoke_consent(self, manager):
        """Test consent revocation."""
        manager.record_consent("user_123", ConsentTier.TIER_2)

        result = manager.revoke_consent("user_123", ip_address="192.168.1.1")

        assert result is True
        record = manager.get_consent("user_123")
        assert record.revoked is True
        assert record.tier == ConsentTier.TIER_0

    def test_revoke_consent_nonexistent(self, manager):
        """Test revocation for nonexistent user."""
        result = manager.revoke_consent("nonexistent")

        assert result is False

    def test_update_consent(self, manager):
        """Test consent update (upgrade/downgrade)."""
        manager.record_consent("user_123", ConsentTier.TIER_1)
        manager.record_consent("user_123", ConsentTier.TIER_2)

        record = manager.get_consent("user_123")

        assert record.tier == ConsentTier.TIER_2

    def test_get_consented_users(self, manager):
        """Test getting list of consented users."""
        manager.record_consent("user_1", ConsentTier.TIER_1)
        manager.record_consent("user_2", ConsentTier.TIER_2)
        manager.record_consent("user_3", ConsentTier.TIER_0)

        users = manager.get_consented_users()

        assert "user_1" in users
        assert "user_2" in users
        assert "user_3" not in users

    def test_get_consented_users_by_tier(self, manager):
        """Test getting users by specific tier."""
        manager.record_consent("user_1", ConsentTier.TIER_1)
        manager.record_consent("user_2", ConsentTier.TIER_2)

        tier_1_users = manager.get_consented_users(tier=ConsentTier.TIER_1)
        tier_2_users = manager.get_consented_users(tier=ConsentTier.TIER_2)

        assert "user_1" in tier_1_users
        assert "user_2" not in tier_1_users
        assert "user_2" in tier_2_users


class TestDeletionRequests:
    """Tests for deletion request functionality."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ConsentManager with temp database."""
        db_path = str(tmp_path / "test_consent.db")
        return ConsentManager(db_path=db_path)

    def test_request_deletion(self, manager):
        """Test creating a deletion request."""
        request = manager.request_deletion(
            user_id="user_123",
            categories=[DataCategory.TRADE_PATTERNS],
        )

        assert request.user_id == "user_123"
        assert request.status == "pending"
        assert DataCategory.TRADE_PATTERNS in request.categories

    def test_request_deletion_all_data(self, manager):
        """Test requesting deletion of all data."""
        request = manager.request_deletion(
            user_id="user_123",
            categories=None,  # All data
        )

        assert len(request.categories) == 0  # Empty means all

    def test_get_deletion_request(self, manager):
        """Test retrieving deletion request."""
        created = manager.request_deletion("user_123")

        retrieved = manager.get_deletion_request(created.id)

        assert retrieved is not None
        assert retrieved.user_id == "user_123"

    def test_get_pending_deletions(self, manager):
        """Test getting all pending deletions."""
        manager.request_deletion("user_1")
        manager.request_deletion("user_2")

        pending = manager.get_pending_deletions()

        assert len(pending) == 2

    def test_complete_deletion_success(self, manager):
        """Test marking deletion as complete."""
        request = manager.request_deletion("user_123")

        manager.complete_deletion(request.id, success=True)

        completed = manager.get_deletion_request(request.id)
        assert completed.status == "completed"
        assert completed.completed_at is not None

    def test_complete_deletion_failure(self, manager):
        """Test marking deletion as failed."""
        request = manager.request_deletion("user_123")

        manager.complete_deletion(
            request.id,
            success=False,
            error_message="Database error"
        )

        failed = manager.get_deletion_request(request.id)
        assert failed.status == "failed"
        assert failed.error_message == "Database error"


class TestConsentHistory:
    """Tests for consent audit trail."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ConsentManager with temp database."""
        db_path = str(tmp_path / "test_consent.db")
        return ConsentManager(db_path=db_path)

    def test_consent_history_recorded(self, manager):
        """Test that consent changes are recorded in history."""
        manager.record_consent("user_123", ConsentTier.TIER_1, ip_address="1.1.1.1")
        manager.record_consent("user_123", ConsentTier.TIER_2, ip_address="2.2.2.2")
        manager.revoke_consent("user_123", ip_address="3.3.3.3")

        history = manager.get_consent_history("user_123")

        assert len(history) == 3
        assert history[0]["action"] == "consent_revoked"
        assert history[1]["action"] == "consent_updated"
        assert history[2]["action"] == "consent_given"

    def test_consent_history_includes_metadata(self, manager):
        """Test that history includes metadata."""
        manager.record_consent(
            "user_123",
            ConsentTier.TIER_2,
            categories=[DataCategory.TRADE_PATTERNS, DataCategory.SENTIMENT_DATA],
        )

        history = manager.get_consent_history("user_123")

        assert "metadata" in history[0]
        assert "categories" in history[0]["metadata"]


class TestConsentStats:
    """Tests for consent statistics."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ConsentManager with temp database."""
        db_path = str(tmp_path / "test_consent.db")
        return ConsentManager(db_path=db_path)

    def test_get_consent_stats(self, manager):
        """Test consent statistics."""
        manager.record_consent("user_1", ConsentTier.TIER_0)
        manager.record_consent("user_2", ConsentTier.TIER_1)
        manager.record_consent("user_3", ConsentTier.TIER_1)
        manager.record_consent("user_4", ConsentTier.TIER_2)

        stats = manager.get_consent_stats()

        assert stats["total_users"] == 4
        assert stats["tier_0_count"] == 1
        assert stats["tier_1_count"] == 2
        assert stats["tier_2_count"] == 1


class TestDataExport:
    """Tests for GDPR data export."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ConsentManager with temp database."""
        db_path = str(tmp_path / "test_consent.db")
        return ConsentManager(db_path=db_path)

    def test_export_user_data(self, manager):
        """Test exporting all user data."""
        manager.record_consent("user_123", ConsentTier.TIER_1)
        manager.record_consent("user_123", ConsentTier.TIER_2)

        export = manager.export_user_data("user_123")

        assert export["user_id"] == "user_123"
        assert export["consent"] is not None
        assert len(export["history"]) == 2
        assert "exported_at" in export


class TestConsentTerms:
    """Tests for consent terms."""

    def test_get_consent_terms_v1(self):
        """Test getting v1.0 consent terms."""
        terms = get_consent_terms("1.0")

        assert terms["version"] == "1.0"
        assert "summary" in terms
        assert "tier_details" in terms

    def test_consent_terms_tier_details(self):
        """Test tier details in consent terms."""
        terms = get_consent_terms("1.0")

        tier_1_details = terms["tier_details"][ConsentTier.TIER_1]
        assert "what_collected" in tier_1_details
        assert "how_used" in tier_1_details
        assert "who_sees" in tier_1_details

        tier_2_details = terms["tier_details"][ConsentTier.TIER_2]
        assert "revenue_share" in tier_2_details

    def test_consent_terms_fallback(self):
        """Test fallback to default version."""
        terms = get_consent_terms("nonexistent")

        assert terms["version"] == "1.0"


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_init_database_creates_tables(self, tmp_path):
        """Test database initialization creates required tables."""
        db_path = str(tmp_path / "test.db")

        conn = init_database(db_path)

        # Check tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "consent_records" in tables
        assert "consent_history" in tables
        assert "deletion_requests" in tables

        conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
