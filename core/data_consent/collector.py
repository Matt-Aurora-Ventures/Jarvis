"""
Data Collector - Anonymous data collection for improvement and marketplace.

Handles:
- Collecting data with consent verification
- Anonymization of user data
- Aggregation for marketplace
- Quality scoring

Privacy Principles:
- Never collect without consent
- Anonymize all data
- Aggregate before sharing
- Quality over quantity
"""

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.data_consent.models import (
    ConsentTier,
    DataCategory,
)

logger = logging.getLogger("jarvis.data_collector")


@dataclass
class AnonymizedData:
    """A piece of anonymized collected data."""

    id: int
    category: DataCategory
    anonymous_id: str  # Hashed user identifier
    data: Dict[str, Any]
    quality_score: float = 0.0
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    aggregation_eligible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "anonymous_id": self.anonymous_id,
            "data": self.data,
            "quality_score": self.quality_score,
            "collected_at": self.collected_at.isoformat(),
        }


@dataclass
class AggregatedDataset:
    """An aggregated dataset ready for marketplace."""

    id: str
    category: DataCategory
    record_count: int
    contributor_count: int
    time_range_start: datetime
    time_range_end: datetime
    quality_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "record_count": self.record_count,
            "contributor_count": self.contributor_count,
            "time_range": {
                "start": self.time_range_start.isoformat(),
                "end": self.time_range_end.isoformat(),
            },
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }


class DataCollector:
    """
    Collects and manages anonymized user data.

    All data collection requires verified consent.
    Data is anonymized before storage.
    """

    # Minimum records needed for aggregation (privacy threshold)
    MIN_AGGREGATION_SIZE = 10

    def __init__(
        self,
        consent_manager: Any = None,
        db_path: str = None,
        anonymization_salt: str = None,
    ):
        """
        Initialize data collector.

        Args:
            consent_manager: ConsentManager instance
            db_path: Path to collected data database
            anonymization_salt: Salt for anonymous ID generation
        """
        self.consent_manager = consent_manager
        self.anonymization_salt = anonymization_salt or os.getenv(
            "DATA_ANONYMIZATION_SALT",
            "jarvis_default_salt_change_in_prod"
        )

        self.db_path = db_path or str(
            Path(os.getenv("DATA_DIR", "data")) / "collected_data.db"
        )
        self._init_database()

    def _init_database(self):
        """Initialize collected data database."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Collected data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collected_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                anonymous_id TEXT NOT NULL,
                data_json TEXT NOT NULL,
                quality_score REAL DEFAULT 0.0,
                collected_at TEXT NOT NULL,
                aggregation_eligible INTEGER DEFAULT 1,
                aggregated INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0
            )
        """)

        # Aggregated datasets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aggregated_datasets (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                contributor_count INTEGER NOT NULL,
                time_range_start TEXT NOT NULL,
                time_range_end TEXT NOT NULL,
                quality_score REAL NOT NULL,
                metadata_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sold INTEGER DEFAULT 0
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_category ON collected_data(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_anonymous ON collected_data(anonymous_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_collected ON collected_data(collected_at)")

        conn.commit()
        conn.close()

        logger.info(f"Data collector database initialized: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _anonymize_id(self, user_id: str) -> str:
        """Create anonymous identifier from user ID."""
        combined = f"{user_id}:{self.anonymization_salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _ensure_consent_manager(self):
        """Ensure consent manager is available."""
        if self.consent_manager is None:
            from core.data_consent.manager import get_consent_manager
            self.consent_manager = get_consent_manager()

    # =========================================================================
    # Data Collection
    # =========================================================================

    def collect(
        self,
        user_id: str,
        category: DataCategory,
        data: Dict[str, Any],
    ) -> Optional[AnonymizedData]:
        """
        Collect data from a user (with consent verification).

        Args:
            user_id: User identifier
            category: Data category
            data: Data to collect

        Returns:
            AnonymizedData if collected, None if consent not given
        """
        self._ensure_consent_manager()

        # Verify consent
        if not self.consent_manager.check_consent(user_id, category):
            logger.debug(f"No consent for {category.value} from user")
            return None

        # Anonymize
        anonymous_id = self._anonymize_id(user_id)
        sanitized_data = self._sanitize_data(data)
        quality_score = self._calculate_quality(sanitized_data, category)

        now = datetime.now(timezone.utc)

        # Store
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO collected_data
            (category, anonymous_id, data_json, quality_score, collected_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (category.value, anonymous_id, json.dumps(sanitized_data),
             quality_score, now.isoformat()),
        )

        data_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Collected {category.value} data (quality: {quality_score:.2f})")

        return AnonymizedData(
            id=data_id,
            category=category,
            anonymous_id=anonymous_id,
            data=sanitized_data,
            quality_score=quality_score,
            collected_at=now,
        )

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove any potentially identifying information."""
        # Fields to always remove
        remove_fields = {
            "user_id", "email", "name", "address", "ip", "wallet",
            "phone", "ssn", "password", "api_key", "secret",
        }

        sanitized = {}
        for key, value in data.items():
            # Skip identifying fields
            if key.lower() in remove_fields:
                continue

            # Recursively sanitize nested dicts
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    def _calculate_quality(
        self,
        data: Dict[str, Any],
        category: DataCategory,
    ) -> float:
        """
        Calculate quality score for collected data.

        Quality factors:
        - Completeness (has expected fields)
        - Recency (recent data is more valuable)
        - Consistency (matches expected patterns)
        """
        score = 0.5  # Base score

        # Completeness
        expected_fields = self._get_expected_fields(category)
        if expected_fields:
            present = sum(1 for f in expected_fields if f in data)
            score += 0.3 * (present / len(expected_fields))

        # Data richness
        if len(data) > 3:
            score += 0.1
        if len(data) > 10:
            score += 0.1

        return min(score, 1.0)

    def _get_expected_fields(self, category: DataCategory) -> List[str]:
        """Get expected fields for a category."""
        field_map = {
            DataCategory.TRADE_PATTERNS: ["trade_count", "avg_size", "frequency"],
            DataCategory.STRATEGY_PERFORMANCE: ["win_rate", "returns", "sharpe"],
            DataCategory.TOKEN_PREFERENCES: ["tokens", "allocation"],
            DataCategory.FEATURE_USAGE: ["features", "frequency"],
            DataCategory.SESSION_PATTERNS: ["duration", "time_of_day"],
            DataCategory.ERROR_PATTERNS: ["error_type", "frequency"],
        }
        return field_map.get(category, [])

    # =========================================================================
    # Data Retrieval
    # =========================================================================

    def get_user_data(
        self,
        user_id: str,
        category: DataCategory = None,
    ) -> List[AnonymizedData]:
        """Get all data collected for a user."""
        anonymous_id = self._anonymize_id(user_id)

        conn = self._get_conn()
        cursor = conn.cursor()

        if category:
            cursor.execute(
                """
                SELECT * FROM collected_data
                WHERE anonymous_id = ? AND category = ? AND deleted = 0
                ORDER BY collected_at DESC
                """,
                (anonymous_id, category.value),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM collected_data
                WHERE anonymous_id = ? AND deleted = 0
                ORDER BY collected_at DESC
                """,
                (anonymous_id,),
            )

        rows = cursor.fetchall()
        conn.close()

        return [
            AnonymizedData(
                id=row[0],
                category=DataCategory(row[1]),
                anonymous_id=row[2],
                data=json.loads(row[3]),
                quality_score=row[4],
                collected_at=datetime.fromisoformat(row[5]),
                aggregation_eligible=bool(row[6]),
            )
            for row in rows
        ]

    # =========================================================================
    # Data Deletion
    # =========================================================================

    def delete_user_data(
        self,
        user_id: str,
        categories: List[DataCategory] = None,
    ) -> int:
        """
        Delete data for a user (soft delete for audit).

        Args:
            user_id: User identifier
            categories: Specific categories to delete (None = all)

        Returns:
            Number of records deleted
        """
        anonymous_id = self._anonymize_id(user_id)

        conn = self._get_conn()
        cursor = conn.cursor()

        if categories:
            category_values = [c.value for c in categories]
            placeholders = ",".join("?" * len(category_values))
            cursor.execute(
                f"""
                UPDATE collected_data
                SET deleted = 1
                WHERE anonymous_id = ? AND category IN ({placeholders})
                """,
                (anonymous_id, *category_values),
            )
        else:
            cursor.execute(
                "UPDATE collected_data SET deleted = 1 WHERE anonymous_id = ?",
                (anonymous_id,),
            )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Deleted {deleted_count} records for user")
        return deleted_count

    # =========================================================================
    # Aggregation
    # =========================================================================

    def aggregate_category(
        self,
        category: DataCategory,
        min_quality: float = 0.5,
    ) -> Optional[AggregatedDataset]:
        """
        Create aggregated dataset from collected data.

        Args:
            category: Category to aggregate
            min_quality: Minimum quality score to include

        Returns:
            AggregatedDataset if enough data, None otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get eligible data
        cursor.execute(
            """
            SELECT anonymous_id, data_json, quality_score, collected_at
            FROM collected_data
            WHERE category = ?
              AND aggregation_eligible = 1
              AND aggregated = 0
              AND deleted = 0
              AND quality_score >= ?
            ORDER BY collected_at
            """,
            (category.value, min_quality),
        )

        rows = cursor.fetchall()

        # Check minimum aggregation size
        unique_contributors = len(set(row[0] for row in rows))
        if unique_contributors < self.MIN_AGGREGATION_SIZE:
            conn.close()
            logger.info(f"Not enough contributors for {category.value}: {unique_contributors}")
            return None

        # Calculate aggregated stats
        all_data = [json.loads(row[1]) for row in rows]
        time_range_start = datetime.fromisoformat(rows[0][3])
        time_range_end = datetime.fromisoformat(rows[-1][3])
        avg_quality = sum(row[2] for row in rows) / len(rows)

        # Generate dataset ID
        dataset_id = f"{category.value}_{int(datetime.now().timestamp())}"

        # Store aggregated dataset
        metadata = self._compute_aggregated_metadata(category, all_data)

        cursor.execute(
            """
            INSERT INTO aggregated_datasets
            (id, category, record_count, contributor_count, time_range_start,
             time_range_end, quality_score, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, category.value, len(rows), unique_contributors,
             time_range_start.isoformat(), time_range_end.isoformat(),
             avg_quality, json.dumps(metadata)),
        )

        # Mark records as aggregated
        record_ids = [row[0] for row in rows]
        # Note: In production, would mark specific IDs

        conn.commit()
        conn.close()

        logger.info(f"Created aggregated dataset {dataset_id}: {len(rows)} records, {unique_contributors} contributors")

        return AggregatedDataset(
            id=dataset_id,
            category=category,
            record_count=len(rows),
            contributor_count=unique_contributors,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            quality_score=avg_quality,
            metadata=metadata,
        )

    def _compute_aggregated_metadata(
        self,
        category: DataCategory,
        data_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute metadata for aggregated dataset."""
        metadata = {
            "sample_count": len(data_list),
        }

        # Category-specific aggregations
        if category == DataCategory.TRADE_PATTERNS:
            trade_counts = [d.get("trade_count", 0) for d in data_list if "trade_count" in d]
            if trade_counts:
                metadata["avg_trade_count"] = sum(trade_counts) / len(trade_counts)

        elif category == DataCategory.STRATEGY_PERFORMANCE:
            win_rates = [d.get("win_rate", 0) for d in data_list if "win_rate" in d]
            if win_rates:
                metadata["avg_win_rate"] = sum(win_rates) / len(win_rates)

        return metadata

    def get_aggregated_datasets(
        self,
        category: DataCategory = None,
        unsold_only: bool = False,
    ) -> List[AggregatedDataset]:
        """Get available aggregated datasets."""
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM aggregated_datasets WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category.value)

        if unsold_only:
            query += " AND sold = 0"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            AggregatedDataset(
                id=row[0],
                category=DataCategory(row[1]),
                record_count=row[2],
                contributor_count=row[3],
                time_range_start=datetime.fromisoformat(row[4]),
                time_range_end=datetime.fromisoformat(row[5]),
                quality_score=row[6],
                metadata=json.loads(row[7]) if row[7] else {},
            )
            for row in rows
        ]

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get data collection statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # By category
        cursor.execute(
            """
            SELECT category, COUNT(*), AVG(quality_score)
            FROM collected_data
            WHERE deleted = 0
            GROUP BY category
            """
        )
        by_category = {
            row[0]: {"count": row[1], "avg_quality": row[2]}
            for row in cursor.fetchall()
        }

        # Total
        cursor.execute("SELECT COUNT(*) FROM collected_data WHERE deleted = 0")
        total_records = cursor.fetchone()[0]

        # Unique contributors
        cursor.execute("SELECT COUNT(DISTINCT anonymous_id) FROM collected_data WHERE deleted = 0")
        unique_contributors = cursor.fetchone()[0]

        # Aggregated datasets
        cursor.execute("SELECT COUNT(*) FROM aggregated_datasets")
        aggregated_count = cursor.fetchone()[0]

        conn.close()

        return {
            "total_records": total_records,
            "unique_contributors": unique_contributors,
            "by_category": by_category,
            "aggregated_datasets": aggregated_count,
        }
