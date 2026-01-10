"""
Consent Manager - Core consent operations.

Handles:
- Recording consent
- Checking consent status
- Processing deletion requests
- Audit trail
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.data_consent.models import (
    ConsentTier,
    ConsentRecord,
    DataCategory,
    DataDeletionRequest,
    init_database,
    get_consent_terms,
)

logger = logging.getLogger("jarvis.consent")


class ConsentManager:
    """
    Manages user consent for data collection.

    GDPR-compliant consent management:
    - Explicit opt-in required
    - Easy opt-out
    - Right to deletion
    - Full audit trail
    """

    def __init__(self, db_path: str = None):
        """Initialize consent manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            db_path = str(data_dir / "consent.db")

        self.db_path = db_path
        self._conn = init_database(db_path)
        logger.info(f"Consent manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    # =========================================================================
    # Consent Operations
    # =========================================================================

    def get_consent(self, user_id: str) -> Optional[ConsentRecord]:
        """Get user's current consent status."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM consent_records WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return ConsentRecord(
            user_id=row[1],
            tier=ConsentTier(row[2]),
            categories=[DataCategory(c) for c in json.loads(row[3])],
            consented_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            ip_address=row[6],
            consent_version=row[7],
            revoked=bool(row[8]),
            revoked_at=datetime.fromisoformat(row[9]) if row[9] else None,
        )

    def record_consent(
        self,
        user_id: str,
        tier: ConsentTier,
        categories: List[DataCategory] = None,
        ip_address: str = None,
        consent_version: str = "1.0",
    ) -> ConsentRecord:
        """
        Record or update user consent.

        Args:
            user_id: User identifier
            tier: Consent tier
            categories: Data categories (for TIER_2)
            ip_address: IP for audit trail
            consent_version: Version of consent terms

        Returns:
            ConsentRecord
        """
        now = datetime.now(timezone.utc)

        # Default categories based on tier
        if categories is None:
            if tier == ConsentTier.TIER_1:
                categories = DataCategory.improvement_categories()
            elif tier == ConsentTier.TIER_2:
                categories = (
                    DataCategory.improvement_categories() +
                    DataCategory.marketplace_categories()
                )
            else:
                categories = []

        conn = self._get_conn()
        cursor = conn.cursor()

        # Get existing consent for audit
        old_tier = None
        cursor.execute("SELECT tier FROM consent_records WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            old_tier = row[0]

        # Insert or update
        categories_json = json.dumps([c.value for c in categories])

        cursor.execute(
            """
            INSERT INTO consent_records
            (user_id, tier, categories_json, consented_at, updated_at, ip_address, consent_version, revoked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                tier = excluded.tier,
                categories_json = excluded.categories_json,
                updated_at = excluded.updated_at,
                ip_address = excluded.ip_address,
                consent_version = excluded.consent_version,
                revoked = 0,
                revoked_at = NULL
            """,
            (user_id, tier.value, categories_json, now.isoformat(), now.isoformat(),
             ip_address, consent_version),
        )

        # Record in audit history
        cursor.execute(
            """
            INSERT INTO consent_history
            (user_id, action, old_tier, new_tier, timestamp, ip_address, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, "consent_given" if old_tier is None else "consent_updated",
             old_tier, tier.value, now.isoformat(), ip_address,
             json.dumps({"categories": [c.value for c in categories]})),
        )

        conn.commit()
        conn.close()

        logger.info(f"Consent recorded for {user_id}: {tier.value}")

        return ConsentRecord(
            user_id=user_id,
            tier=tier,
            categories=categories,
            consented_at=now,
            updated_at=now,
            ip_address=ip_address,
            consent_version=consent_version,
        )

    def revoke_consent(
        self,
        user_id: str,
        ip_address: str = None,
    ) -> bool:
        """
        Revoke user consent (opt-out).

        Args:
            user_id: User identifier
            ip_address: IP for audit trail

        Returns:
            True if revoked
        """
        now = datetime.now(timezone.utc)

        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current tier for audit
        cursor.execute("SELECT tier FROM consent_records WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        old_tier = row[0]

        # Update to revoked
        cursor.execute(
            """
            UPDATE consent_records
            SET tier = ?, revoked = 1, revoked_at = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (ConsentTier.TIER_0.value, now.isoformat(), now.isoformat(), user_id),
        )

        # Record in audit
        cursor.execute(
            """
            INSERT INTO consent_history
            (user_id, action, old_tier, new_tier, timestamp, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, "consent_revoked", old_tier, ConsentTier.TIER_0.value,
             now.isoformat(), ip_address),
        )

        conn.commit()
        conn.close()

        logger.info(f"Consent revoked for {user_id}")
        return True

    def check_consent(
        self,
        user_id: str,
        category: DataCategory = None,
    ) -> bool:
        """
        Check if user has consented to data collection.

        Args:
            user_id: User identifier
            category: Specific category to check (None = any collection)

        Returns:
            True if consented
        """
        consent = self.get_consent(user_id)

        if consent is None:
            return False

        if consent.revoked:
            return False

        if consent.tier == ConsentTier.TIER_0:
            return False

        if category is None:
            return consent.tier in (ConsentTier.TIER_1, ConsentTier.TIER_2)

        return consent.allows_category(category)

    def get_consented_users(
        self,
        tier: ConsentTier = None,
        category: DataCategory = None,
    ) -> List[str]:
        """
        Get list of users who have consented.

        Args:
            tier: Filter by specific tier
            category: Filter by category consent

        Returns:
            List of user IDs
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if tier:
            cursor.execute(
                "SELECT user_id FROM consent_records WHERE tier = ? AND revoked = 0",
                (tier.value,),
            )
        else:
            cursor.execute(
                "SELECT user_id, tier, categories_json FROM consent_records WHERE revoked = 0"
            )

        rows = cursor.fetchall()
        conn.close()

        if tier:
            return [row[0] for row in rows]

        # Filter by category if specified
        users = []
        for row in rows:
            user_id, user_tier, categories_json = row

            if category is None:
                if user_tier != ConsentTier.TIER_0.value:
                    users.append(user_id)
            else:
                if user_tier == ConsentTier.TIER_1.value:
                    if category in DataCategory.improvement_categories():
                        users.append(user_id)
                elif user_tier == ConsentTier.TIER_2.value:
                    categories = [DataCategory(c) for c in json.loads(categories_json)]
                    if category in categories:
                        users.append(user_id)

        return users

    # =========================================================================
    # Deletion Requests
    # =========================================================================

    def request_deletion(
        self,
        user_id: str,
        categories: List[DataCategory] = None,
    ) -> DataDeletionRequest:
        """
        Request data deletion.

        Args:
            user_id: User identifier
            categories: Specific categories to delete (None = all)

        Returns:
            DeletionRequest
        """
        now = datetime.now(timezone.utc)
        categories = categories or []

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO deletion_requests
            (user_id, requested_at, categories_json, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (user_id, now.isoformat(), json.dumps([c.value for c in categories])),
        )

        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Deletion request {request_id} created for {user_id}")

        return DataDeletionRequest(
            id=request_id,
            user_id=user_id,
            requested_at=now,
            categories=categories,
            status="pending",
        )

    def get_deletion_request(self, request_id: int) -> Optional[DataDeletionRequest]:
        """Get deletion request by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM deletion_requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return DataDeletionRequest(
            id=row[0],
            user_id=row[1],
            requested_at=datetime.fromisoformat(row[2]),
            categories=[DataCategory(c) for c in json.loads(row[3])],
            status=row[4],
            completed_at=datetime.fromisoformat(row[5]) if row[5] else None,
            error_message=row[6],
        )

    def get_pending_deletions(self) -> List[DataDeletionRequest]:
        """Get all pending deletion requests."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM deletion_requests WHERE status = 'pending' ORDER BY requested_at"
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            DataDeletionRequest(
                id=row[0],
                user_id=row[1],
                requested_at=datetime.fromisoformat(row[2]),
                categories=[DataCategory(c) for c in json.loads(row[3])],
                status=row[4],
            )
            for row in rows
        ]

    def complete_deletion(
        self,
        request_id: int,
        success: bool = True,
        error_message: str = None,
    ):
        """Mark deletion request as complete."""
        now = datetime.now(timezone.utc)

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE deletion_requests
            SET status = ?, completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            ("completed" if success else "failed", now.isoformat(), error_message, request_id),
        )

        conn.commit()
        conn.close()

        logger.info(f"Deletion request {request_id} marked as {'completed' if success else 'failed'}")

    # =========================================================================
    # Audit & Reporting
    # =========================================================================

    def get_consent_history(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get consent history for a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT action, old_tier, new_tier, timestamp, metadata_json
            FROM consent_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "action": row[0],
                "old_tier": row[1],
                "new_tier": row[2],
                "timestamp": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
            }
            for row in rows
        ]

    def get_consent_stats(self) -> Dict[str, Any]:
        """Get consent statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Count by tier
        cursor.execute(
            """
            SELECT tier, COUNT(*) FROM consent_records
            WHERE revoked = 0
            GROUP BY tier
            """
        )
        by_tier = {row[0]: row[1] for row in cursor.fetchall()}

        # Total users
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM consent_records")
        total_users = cursor.fetchone()[0]

        # Pending deletions
        cursor.execute("SELECT COUNT(*) FROM deletion_requests WHERE status = 'pending'")
        pending_deletions = cursor.fetchone()[0]

        conn.close()

        return {
            "total_users": total_users,
            "by_tier": by_tier,
            "tier_0_count": by_tier.get(ConsentTier.TIER_0.value, 0),
            "tier_1_count": by_tier.get(ConsentTier.TIER_1.value, 0),
            "tier_2_count": by_tier.get(ConsentTier.TIER_2.value, 0),
            "pending_deletions": pending_deletions,
        }

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all data we have about a user (GDPR data portability)."""
        consent = self.get_consent(user_id)
        history = self.get_consent_history(user_id)

        return {
            "user_id": user_id,
            "consent": consent.to_dict() if consent else None,
            "history": history,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Singleton
# =============================================================================

_manager: Optional[ConsentManager] = None


def get_consent_manager() -> ConsentManager:
    """Get or create the singleton consent manager."""
    global _manager

    if _manager is None:
        _manager = ConsentManager()

    return _manager


# =============================================================================
# Convenience Functions
# =============================================================================


async def check_consent(user_id: str, category: DataCategory = None) -> bool:
    """Check if user has consented."""
    return get_consent_manager().check_consent(user_id, category)


async def record_consent(
    user_id: str,
    tier: ConsentTier,
    categories: List[DataCategory] = None,
    ip_address: str = None,
) -> ConsentRecord:
    """Record user consent."""
    return get_consent_manager().record_consent(user_id, tier, categories, ip_address)


async def revoke_consent(user_id: str, ip_address: str = None) -> bool:
    """Revoke user consent."""
    return get_consent_manager().revoke_consent(user_id, ip_address)
