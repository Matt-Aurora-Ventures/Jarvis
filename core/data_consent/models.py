"""
Data Consent Models.

Defines consent tiers, data categories, and related structures.
"""

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConsentTier(Enum):
    """
    User consent tiers for data collection.

    TIER_0: No data collection
        - User's data is never collected
        - No contribution to system improvement
        - No marketplace participation

    TIER_1: Anonymous improvement data
        - Anonymized usage patterns collected
        - Helps improve trading algorithms
        - No personal data shared
        - No marketplace earnings

    TIER_2: Marketplace participation
        - Anonymized data can be sold
        - User earns revenue share
        - Still no personal data exposed
        - Full control over data categories
    """
    TIER_0 = "tier_0"  # No collection
    TIER_1 = "tier_1"  # Anonymous improvement
    TIER_2 = "tier_2"  # Marketplace


class DataCategory(Enum):
    """Categories of data that can be collected."""

    # Trading data
    TRADE_PATTERNS = "trade_patterns"      # Trading frequency, times, sizes
    STRATEGY_PERFORMANCE = "strategy_perf" # Win rates, returns
    TOKEN_PREFERENCES = "token_prefs"      # Which tokens user trades

    # Usage data
    FEATURE_USAGE = "feature_usage"        # Which features are used
    SESSION_PATTERNS = "session_patterns"  # Usage times, duration
    ERROR_PATTERNS = "error_patterns"      # Common errors/issues

    # Market data
    MARKET_SIGNALS = "market_signals"      # Signals user follows
    SENTIMENT_DATA = "sentiment"           # Sentiment analysis contributions

    @classmethod
    def improvement_categories(cls) -> List["DataCategory"]:
        """Categories collected for TIER_1 (improvement)."""
        return [
            cls.FEATURE_USAGE,
            cls.ERROR_PATTERNS,
            cls.SESSION_PATTERNS,
        ]

    @classmethod
    def marketplace_categories(cls) -> List["DataCategory"]:
        """Additional categories for TIER_2 (marketplace)."""
        return [
            cls.TRADE_PATTERNS,
            cls.STRATEGY_PERFORMANCE,
            cls.TOKEN_PREFERENCES,
            cls.MARKET_SIGNALS,
            cls.SENTIMENT_DATA,
        ]


@dataclass
class ConsentRecord:
    """Record of a user's consent status."""

    user_id: str
    tier: ConsentTier
    categories: List[DataCategory] = field(default_factory=list)
    consented_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None  # For audit trail
    consent_version: str = "1.0"  # Version of consent terms
    revoked: bool = False
    revoked_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "tier": self.tier.value,
            "categories": [c.value for c in self.categories],
            "consented_at": self.consented_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "consent_version": self.consent_version,
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

    def allows_category(self, category: DataCategory) -> bool:
        """Check if consent covers a specific category."""
        if self.revoked:
            return False

        if self.tier == ConsentTier.TIER_0:
            return False

        if self.tier == ConsentTier.TIER_1:
            return category in DataCategory.improvement_categories()

        if self.tier == ConsentTier.TIER_2:
            return category in self.categories or category in DataCategory.improvement_categories()

        return False


@dataclass
class DataDeletionRequest:
    """Request to delete user data."""

    id: int
    user_id: str
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    categories: List[DataCategory] = field(default_factory=list)  # Empty = all
    status: str = "pending"  # pending, processing, completed, failed
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "requested_at": self.requested_at.isoformat(),
            "categories": [c.value for c in self.categories],
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


# =============================================================================
# Consent Terms
# =============================================================================

CONSENT_TERMS = {
    "1.0": {
        "version": "1.0",
        "effective_date": "2026-01-01",
        "summary": {
            ConsentTier.TIER_0: "No data collection. Your usage remains completely private.",
            ConsentTier.TIER_1: "Anonymous usage data helps improve the platform. No personal data is collected or shared.",
            ConsentTier.TIER_2: "Participate in the data marketplace. Earn revenue from your anonymized trading insights.",
        },
        "tier_details": {
            ConsentTier.TIER_0: {
                "what_collected": [],
                "how_used": "None",
                "who_sees": "No one",
                "your_control": "Full opt-out",
            },
            ConsentTier.TIER_1: {
                "what_collected": [
                    "Feature usage patterns (which features you use)",
                    "Session duration and timing",
                    "Error reports (without personal data)",
                ],
                "how_used": "Improve platform features and fix bugs",
                "who_sees": "Internal development team only",
                "your_control": "Opt-out anytime, request deletion",
            },
            ConsentTier.TIER_2: {
                "what_collected": [
                    "Everything in TIER_1, plus:",
                    "Anonymized trading patterns",
                    "Strategy performance metrics",
                    "Market signal interactions",
                ],
                "how_used": "Aggregated data sold to improve trading models",
                "who_sees": "Data buyers receive only aggregated, anonymized data",
                "your_control": "Choose categories, set price floor, withdraw anytime",
                "revenue_share": "60% of data sale revenue goes to contributors",
            },
        },
    }
}


def get_consent_terms(version: str = "1.0") -> Dict[str, Any]:
    """Get consent terms for a version."""
    return CONSENT_TERMS.get(version, CONSENT_TERMS["1.0"])


# =============================================================================
# Database Schema
# =============================================================================


def init_database(db_path: str = None) -> sqlite3.Connection:
    """Initialize consent database."""
    if db_path is None:
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        db_path = str(data_dir / "consent.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Consent records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consent_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            categories_json TEXT DEFAULT '[]',
            consented_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ip_address TEXT,
            consent_version TEXT DEFAULT '1.0',
            revoked INTEGER DEFAULT 0,
            revoked_at TEXT,
            UNIQUE(user_id)
        )
    """)

    # Consent history (audit trail)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consent_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_tier TEXT,
            new_tier TEXT,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            metadata_json TEXT
        )
    """)

    # Deletion requests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deletion_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            categories_json TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            completed_at TEXT,
            error_message TEXT
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON consent_history(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deletion_status ON deletion_requests(status)")

    conn.commit()
    return conn
