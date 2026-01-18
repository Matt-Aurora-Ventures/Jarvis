"""
Ambassador Program for Jarvis Community.

Requirements:
- 3+ months active user
- Profit > $500 (demonstrating skill)
- Community involvement (votes, posts, etc.)

Benefits:
- 15% commission on referrals (vs 10%)
- Featured on community page
- Early access to new features
- Direct communication channel with team
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.community.ambassador")


class ApplicationStatus(Enum):
    """Ambassador application status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def init_ambassador_db(db_path: str) -> sqlite3.Connection:
    """Initialize the ambassador database schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ambassadors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ambassadors (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'pending',
            applied_at TEXT,
            approved_at TEXT,
            tier TEXT DEFAULT 'standard',
            commission_rate REAL DEFAULT 0.15,
            total_referrals INTEGER DEFAULT 0,
            total_commission REAL DEFAULT 0,
            notes TEXT
        )
    """)

    # Ambassador applications table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ambassador_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            account_age_months INTEGER,
            total_pnl REAL,
            community_score INTEGER,
            application_text TEXT,
            status TEXT DEFAULT 'pending',
            submitted_at TEXT,
            reviewed_at TEXT,
            reviewer_notes TEXT
        )
    """)

    # Ambassador benefits table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ambassador_benefits (
            user_id TEXT PRIMARY KEY,
            referral_commission_rate REAL DEFAULT 0.15,
            featured_profile INTEGER DEFAULT 1,
            early_access INTEGER DEFAULT 1,
            direct_channel INTEGER DEFAULT 1,
            custom_referral_page INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES ambassadors(user_id)
        )
    """)

    conn.commit()
    return conn


# Ambassador requirements
AMBASSADOR_REQUIREMENTS = {
    "account_age_months": 3,
    "total_pnl": 500.0,
    "community_score": 25,
}


class AmbassadorManager:
    """
    Manages the ambassador program.

    Usage:
        manager = AmbassadorManager()

        # Check eligibility
        eligible = manager.check_eligibility(
            user_id="user1",
            account_age_months=4,
            total_pnl=600.0,
            community_score=50
        )

        # Apply
        result = manager.apply_for_ambassador(
            user_id="user1",
            account_age_months=4,
            total_pnl=600.0,
            community_score=50
        )

        # Get benefits
        benefits = manager.get_ambassador_benefits("user1")
    """

    def __init__(self, db_path: str = None):
        """Initialize ambassador manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "community" / "ambassador.db")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = init_ambassador_db(db_path)
        logger.info(f"Ambassador manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Eligibility Checking
    # =========================================================================

    def check_eligibility(
        self,
        user_id: str,
        account_age_months: int,
        total_pnl: float,
        community_score: int,
    ) -> Dict[str, Any]:
        """
        Check if user meets ambassador requirements.

        Args:
            user_id: User identifier
            account_age_months: How long user has been active
            total_pnl: Total profit/loss
            community_score: Community engagement score

        Returns:
            Eligibility result with missing requirements
        """
        missing = []

        if account_age_months < AMBASSADOR_REQUIREMENTS["account_age_months"]:
            missing.append("account_age")

        if total_pnl < AMBASSADOR_REQUIREMENTS["total_pnl"]:
            missing.append("total_pnl")

        if community_score < AMBASSADOR_REQUIREMENTS["community_score"]:
            missing.append("community_score")

        is_eligible = len(missing) == 0

        return {
            "is_eligible": is_eligible,
            "missing_requirements": missing,
            "requirements": AMBASSADOR_REQUIREMENTS,
            "current_values": {
                "account_age_months": account_age_months,
                "total_pnl": total_pnl,
                "community_score": community_score,
            },
        }

    # =========================================================================
    # Application Management
    # =========================================================================

    def apply_for_ambassador(
        self,
        user_id: str,
        account_age_months: int,
        total_pnl: float,
        community_score: int,
        application_text: str = None,
    ) -> Dict[str, Any]:
        """
        Submit an ambassador application.

        Args:
            user_id: User identifier
            account_age_months: Account age
            total_pnl: Total profit
            community_score: Community engagement score
            application_text: Optional application text

        Returns:
            Application result
        """
        # Check eligibility first
        eligibility = self.check_eligibility(
            user_id, account_age_months, total_pnl, community_score
        )

        if not eligibility["is_eligible"]:
            return {
                "status": "rejected",
                "message": "Does not meet requirements",
                "missing": eligibility["missing_requirements"],
            }

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        # Check for existing pending application
        cursor.execute("""
            SELECT id FROM ambassador_applications
            WHERE user_id = ? AND status = 'pending'
        """, (user_id,))

        if cursor.fetchone():
            conn.close()
            return {"status": "pending", "message": "Application already pending"}

        # Submit application
        cursor.execute("""
            INSERT INTO ambassador_applications (
                user_id, account_age_months, total_pnl, community_score,
                application_text, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            user_id, account_age_months, total_pnl, community_score,
            application_text, now
        ))

        conn.commit()
        conn.close()

        logger.info(f"Ambassador application submitted: {user_id}")
        return {"status": "pending", "message": "Application submitted for review"}

    def get_pending_applications(self) -> List[Dict[str, Any]]:
        """Get all pending applications."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ambassador_applications WHERE status = 'pending'
            ORDER BY submitted_at ASC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def review_application(
        self,
        user_id: str,
        approved: bool,
        reviewer_notes: str = None,
    ) -> Dict[str, Any]:
        """
        Review and approve/reject an ambassador application.

        Args:
            user_id: Applicant's user ID
            approved: Whether to approve
            reviewer_notes: Optional notes

        Returns:
            Review result
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        status = "approved" if approved else "rejected"

        # Update application
        cursor.execute("""
            UPDATE ambassador_applications
            SET status = ?, reviewed_at = ?, reviewer_notes = ?
            WHERE user_id = ? AND status = 'pending'
        """, (status, now, reviewer_notes, user_id))

        if cursor.rowcount == 0:
            conn.close()
            return {"success": False, "message": "No pending application found"}

        # If approved, create ambassador record
        if approved:
            cursor.execute("""
                INSERT INTO ambassadors (
                    user_id, status, applied_at, approved_at,
                    commission_rate
                ) VALUES (?, 'approved', ?, ?, 0.15)
                ON CONFLICT(user_id) DO UPDATE SET
                    status = 'approved',
                    approved_at = excluded.approved_at
            """, (user_id, now, now))

            # Add benefits
            cursor.execute("""
                INSERT INTO ambassador_benefits (
                    user_id, referral_commission_rate, featured_profile,
                    early_access, direct_channel
                ) VALUES (?, 0.15, 1, 1, 1)
                ON CONFLICT(user_id) DO NOTHING
            """, (user_id,))

        conn.commit()
        conn.close()

        logger.info(f"Ambassador application {status} for {user_id}")
        return {"success": True, "status": status}

    # =========================================================================
    # Ambassador Management
    # =========================================================================

    def is_ambassador(self, user_id: str) -> bool:
        """Check if user is an approved ambassador."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status FROM ambassadors WHERE user_id = ? AND status = 'approved'
        """, (user_id,))

        result = cursor.fetchone()
        conn.close()

        return result is not None

    def get_ambassador(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get ambassador details."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ambassadors WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_all_ambassadors(self) -> List[Dict[str, Any]]:
        """Get all approved ambassadors."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ambassadors WHERE status = 'approved'
            ORDER BY total_referrals DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # =========================================================================
    # Benefits
    # =========================================================================

    def get_ambassador_benefits(self, user_id: str) -> Dict[str, Any]:
        """
        Get ambassador benefits for a user.

        Returns standard benefits even for non-ambassadors
        (with default values showing what they'd get).
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM ambassador_benefits WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            benefits = dict(row)
            benefits["featured_profile"] = bool(benefits["featured_profile"])
            benefits["early_access"] = bool(benefits["early_access"])
            benefits["direct_channel"] = bool(benefits["direct_channel"])
            benefits["custom_referral_page"] = bool(benefits["custom_referral_page"])
            return benefits

        # Return default/preview benefits for non-ambassadors
        return {
            "user_id": user_id,
            "referral_commission_rate": 0.15,  # 15% vs standard 10%
            "featured_profile": True,
            "early_access": True,
            "direct_channel": True,
            "custom_referral_page": False,
            "is_preview": True,  # Indicates these are preview values
        }

    def update_ambassador_stats(
        self,
        user_id: str,
        referrals_added: int = 0,
        commission_added: float = 0,
    ) -> bool:
        """Update ambassador statistics."""
        if not self.is_ambassador(user_id):
            return False

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE ambassadors
            SET total_referrals = total_referrals + ?,
                total_commission = total_commission + ?
            WHERE user_id = ?
        """, (referrals_added, commission_added, user_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    # =========================================================================
    # Tier Management
    # =========================================================================

    def upgrade_tier(self, user_id: str, new_tier: str) -> bool:
        """
        Upgrade ambassador tier based on performance.

        Tiers:
        - standard: Default (15% commission)
        - gold: 50+ referrals (17% commission)
        - platinum: 100+ referrals (20% commission)
        """
        tier_rates = {
            "standard": 0.15,
            "gold": 0.17,
            "platinum": 0.20,
        }

        if new_tier not in tier_rates:
            return False

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE ambassadors
            SET tier = ?, commission_rate = ?
            WHERE user_id = ?
        """, (new_tier, tier_rates[new_tier], user_id))

        # Also update benefits
        cursor.execute("""
            UPDATE ambassador_benefits
            SET referral_commission_rate = ?,
                custom_referral_page = ?
            WHERE user_id = ?
        """, (tier_rates[new_tier], 1 if new_tier in ["gold", "platinum"] else 0, user_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def check_tier_upgrades(self) -> List[Dict[str, Any]]:
        """Check and apply tier upgrades for all ambassadors."""
        conn = self._get_conn()
        cursor = conn.cursor()

        upgrades = []

        cursor.execute("""
            SELECT user_id, tier, total_referrals FROM ambassadors
            WHERE status = 'approved'
        """)

        for row in cursor.fetchall():
            user_id = row["user_id"]
            current_tier = row["tier"]
            referrals = row["total_referrals"]

            new_tier = None
            if referrals >= 100 and current_tier != "platinum":
                new_tier = "platinum"
            elif referrals >= 50 and current_tier == "standard":
                new_tier = "gold"

            if new_tier:
                self.upgrade_tier(user_id, new_tier)
                upgrades.append({
                    "user_id": user_id,
                    "old_tier": current_tier,
                    "new_tier": new_tier,
                })

        conn.close()
        return upgrades

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_ambassador_stats(self) -> Dict[str, Any]:
        """Get overall ambassador program statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_ambassadors,
                SUM(total_referrals) as total_referrals,
                SUM(total_commission) as total_commission_paid,
                AVG(total_referrals) as avg_referrals_per_ambassador
            FROM ambassadors
            WHERE status = 'approved'
        """)

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else {}

    def export_ambassador_data(self, filepath: str = None) -> str:
        """Export ambassador program data to JSON."""
        if filepath is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            filepath = str(data_dir / "community" / "ambassador_report.json")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": self.get_ambassador_stats(),
            "ambassadors": self.get_all_ambassadors(),
            "pending_applications": len(self.get_pending_applications()),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported ambassador data to {filepath}")
        return filepath
