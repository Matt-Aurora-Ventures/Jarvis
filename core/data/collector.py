"""
Trade Data Collector
Prompt #88: Anonymous Trade Data Collector - Collection pipeline

Collects anonymized trade data based on user consent.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import json

from core.data.anonymizer import DataAnonymizer, get_anonymizer
from core.data_consent.models import ConsentTier, DataCategory

logger = logging.getLogger("jarvis.data.collector")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class CollectionResult:
    """Result of a data collection attempt"""
    collected: bool
    reason: str
    record_id: Optional[str] = None
    tier: Optional[ConsentTier] = None


@dataclass
class CollectionStats:
    """Statistics for data collection"""
    total_collected: int = 0
    total_skipped: int = 0
    skipped_no_consent: int = 0
    skipped_category_denied: int = 0
    skipped_validation_failed: int = 0
    by_tier: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)


# =============================================================================
# TRADE DATA COLLECTOR
# =============================================================================

class TradeDataCollector:
    """
    Collects anonymized trade data based on user consent.

    Flow:
    1. Check user consent tier and categories
    2. Validate trade data
    3. Anonymize data
    4. Store in database
    5. Emit for further processing

    Privacy-first design:
    - Only collect with explicit consent
    - Always anonymize before storage
    - Track consent tier for transparency
    """

    def __init__(
        self,
        db_path: str = None,
        anonymizer: DataAnonymizer = None,
        consent_manager=None,
    ):
        self.db_path = db_path or os.getenv(
            "TRADE_DATA_DB",
            "data/trade_data.db"
        )
        self._anonymizer = anonymizer or get_anonymizer()
        self._consent_manager = consent_manager
        self._stats = CollectionStats()
        self._callbacks: List[Callable] = []

        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for trade data"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Anonymized trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anonymized_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_hash TEXT NOT NULL,
                time_bucket TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                symbol TEXT,
                side TEXT,
                amount_bucket INTEGER,
                outcome TEXT,
                pnl_pct REAL,
                hold_duration_seconds INTEGER,
                strategy_name TEXT,
                consent_tier TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                market_conditions_json TEXT,
                metadata_json TEXT
            )
        """)

        # Indexes for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_user_hash
            ON anonymized_trades(user_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_time
            ON anonymized_trades(time_bucket)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_token
            ON anonymized_trades(token_mint)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_strategy
            ON anonymized_trades(strategy_name)
        """)

        # Collection audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_hash TEXT NOT NULL,
                action TEXT NOT NULL,
                consent_tier TEXT,
                categories_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # CONSENT CHECKING
    # =========================================================================

    def _get_consent_manager(self):
        """Get consent manager (lazy load)"""
        if self._consent_manager is None:
            try:
                from core.data_consent.manager import get_consent_manager
                self._consent_manager = get_consent_manager()
            except ImportError:
                logger.warning("Consent manager not available")
                return None
        return self._consent_manager

    async def check_consent(
        self,
        user_id: str,
        category: DataCategory = DataCategory.TRADE_PATTERNS,
    ) -> tuple[bool, Optional[ConsentTier], str]:
        """
        Check if user has consented to data collection.

        Args:
            user_id: User identifier
            category: Data category to collect

        Returns:
            (has_consent, tier, reason)
        """
        consent_mgr = self._get_consent_manager()
        if consent_mgr is None:
            return False, None, "Consent manager unavailable"

        try:
            consent = consent_mgr.get_consent(user_id)

            if consent is None:
                return False, None, "No consent record"

            if consent.revoked:
                return False, None, "Consent revoked"

            if consent.tier == ConsentTier.TIER_0:
                return False, ConsentTier.TIER_0, "User opted out (TIER_0)"

            if not consent.allows_category(category):
                return False, consent.tier, f"Category {category.value} not allowed"

            return True, consent.tier, "Consent granted"

        except Exception as e:
            logger.error(f"Consent check error: {e}")
            return False, None, f"Error: {e}"

    # =========================================================================
    # COLLECTION
    # =========================================================================

    async def collect_trade(
        self,
        user_id: str,
        trade_data: Dict[str, Any],
        category: DataCategory = DataCategory.TRADE_PATTERNS,
    ) -> CollectionResult:
        """
        Collect a trade if user has consented.

        Args:
            user_id: User identifier (wallet address)
            trade_data: Raw trade data
            category: Data category

        Returns:
            CollectionResult with status
        """
        # Check consent
        has_consent, tier, reason = await self.check_consent(user_id, category)

        if not has_consent:
            self._stats.total_skipped += 1
            if tier == ConsentTier.TIER_0 or tier is None:
                self._stats.skipped_no_consent += 1
            else:
                self._stats.skipped_category_denied += 1

            return CollectionResult(
                collected=False,
                reason=reason,
                tier=tier,
            )

        # Add wallet to trade data for anonymization
        trade_with_wallet = {
            "wallet": user_id,
            "timestamp": datetime.now(timezone.utc),
            **trade_data,
        }

        # Anonymize
        anonymized = self._anonymizer.anonymize_trade(trade_with_wallet)

        # Validate anonymization
        is_valid, issues = self._anonymizer.validate_anonymized(anonymized)
        if not is_valid:
            logger.warning(f"Anonymization validation failed: {issues}")
            self._stats.skipped_validation_failed += 1
            return CollectionResult(
                collected=False,
                reason=f"Validation failed: {issues}",
                tier=tier,
            )

        # Store
        record_id = await self._store_trade(anonymized, tier)

        # Update stats
        self._stats.total_collected += 1
        tier_key = tier.value if tier else "unknown"
        self._stats.by_tier[tier_key] = self._stats.by_tier.get(tier_key, 0) + 1
        self._stats.by_category[category.value] = self._stats.by_category.get(category.value, 0) + 1

        # Log audit
        await self._log_audit(
            user_hash=anonymized.get("user_hash", ""),
            action="collect",
            tier=tier,
            categories=[category],
        )

        # Notify callbacks
        for callback in self._callbacks:
            try:
                await callback(anonymized, tier)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        logger.debug(f"Collected trade for user_hash={anonymized.get('user_hash', '')[:8]}...")

        return CollectionResult(
            collected=True,
            reason="Collected successfully",
            record_id=record_id,
            tier=tier,
        )

    async def _store_trade(
        self,
        anonymized: Dict[str, Any],
        tier: ConsentTier,
    ) -> str:
        """Store anonymized trade in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO anonymized_trades
            (user_hash, time_bucket, token_mint, symbol, side, amount_bucket,
             outcome, pnl_pct, hold_duration_seconds, strategy_name,
             consent_tier, collected_at, market_conditions_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            anonymized.get("user_hash", ""),
            anonymized.get("time_bucket", ""),
            anonymized.get("token_mint", ""),
            anonymized.get("symbol", ""),
            anonymized.get("side", ""),
            anonymized.get("amount_bucket", 0),
            anonymized.get("outcome", ""),
            anonymized.get("pnl_pct"),
            anonymized.get("hold_duration_seconds"),
            anonymized.get("strategy_name", ""),
            tier.value if tier else "",
            datetime.now(timezone.utc).isoformat(),
            json.dumps(anonymized.get("market_conditions", {})),
            json.dumps({}),
        ))

        record_id = str(cursor.lastrowid)
        conn.commit()
        conn.close()

        return record_id

    async def _log_audit(
        self,
        user_hash: str,
        action: str,
        tier: Optional[ConsentTier],
        categories: List[DataCategory],
    ):
        """Log collection action for audit trail"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO collection_audit
            (user_hash, action, consent_tier, categories_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_hash,
            action,
            tier.value if tier else None,
            json.dumps([c.value for c in categories]),
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_collection(self, callback: Callable):
        """Register a callback for new collections"""
        self._callbacks.append(callback)

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_collected_count(
        self,
        since: Optional[datetime] = None,
    ) -> int:
        """Get count of collected trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if since:
            cursor.execute("""
                SELECT COUNT(*) FROM anonymized_trades
                WHERE collected_at >= ?
            """, (since.isoformat(),))
        else:
            cursor.execute("SELECT COUNT(*) FROM anonymized_trades")

        count = cursor.fetchone()[0]
        conn.close()

        return count

    async def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        total = await self.get_collected_count()

        return {
            "total_collected": total,
            "session_collected": self._stats.total_collected,
            "session_skipped": self._stats.total_skipped,
            "by_tier": self._stats.by_tier,
            "by_category": self._stats.by_category,
            "consent_rate": (
                self._stats.total_collected /
                (self._stats.total_collected + self._stats.total_skipped) * 100
                if (self._stats.total_collected + self._stats.total_skipped) > 0
                else 0
            ),
        }

    async def get_trades_for_aggregation(
        self,
        since: datetime,
        until: Optional[datetime] = None,
        strategy: Optional[str] = None,
        token_mint: Optional[str] = None,
        tier: Optional[ConsentTier] = None,
    ) -> List[Dict[str, Any]]:
        """Get trades for aggregation/analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM anonymized_trades WHERE time_bucket >= ?"
        params = [since.isoformat()]

        if until:
            query += " AND time_bucket <= ?"
            params.append(until.isoformat())

        if strategy:
            query += " AND strategy_name = ?"
            params.append(strategy)

        if token_mint:
            query += " AND token_mint = ?"
            params.append(token_mint)

        if tier:
            query += " AND consent_tier = ?"
            params.append(tier.value)

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return trades


# =============================================================================
# SINGLETON
# =============================================================================

_collector: Optional[TradeDataCollector] = None


def get_trade_collector() -> TradeDataCollector:
    """Get or create the trade collector singleton"""
    global _collector
    if _collector is None:
        _collector = TradeDataCollector()
    return _collector


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_collector_endpoints(collector: TradeDataCollector):
    """Create data collection API endpoints"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/data/collection", tags=["Data Collection"])

    @router.get("/stats")
    async def get_stats():
        """Get collection statistics"""
        return await collector.get_stats()

    @router.get("/count")
    async def get_count():
        """Get total collected count"""
        count = await collector.get_collected_count()
        return {"count": count}

    return router
