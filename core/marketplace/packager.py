"""
Data Packaging System
Prompt #95: Package anonymized data for marketplace

Creates purchasable data packages from anonymized trade data.
"""

import asyncio
import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import gzip
import base64

logger = logging.getLogger("jarvis.marketplace.packager")


# =============================================================================
# MODELS
# =============================================================================

class DataCategory(Enum):
    """Categories of data packages"""
    TRADE_PATTERNS = "trade_patterns"
    STRATEGY_SIGNALS = "strategy_signals"
    MARKET_TIMING = "market_timing"
    TOKEN_ANALYSIS = "token_analysis"
    AGGREGATE_METRICS = "aggregate_metrics"


class PackageFormat(Enum):
    """Data package formats"""
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


class PackageStatus(Enum):
    """Package lifecycle status"""
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


@dataclass
class DataPackage:
    """A purchasable data package"""
    id: str
    name: str
    description: str
    category: DataCategory
    format: PackageFormat
    record_count: int
    file_size_bytes: int
    content_hash: str  # SHA256 of content
    price_sol: float
    creator_wallet: str
    created_at: datetime
    expires_at: Optional[datetime]
    status: PackageStatus = PackageStatus.ACTIVE
    preview_data: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_url: Optional[str] = None  # IPFS or S3 URL


@dataclass
class PackageContributor:
    """A contributor to a data package"""
    wallet: str
    contribution_pct: float
    data_count: int


# =============================================================================
# DATA PACKAGER
# =============================================================================

class DataPackager:
    """
    Creates and manages data packages for the marketplace.

    Features:
    - Package anonymized data by category
    - Generate preview data
    - Calculate contributor shares
    - Store packages (local or IPFS)
    """

    def __init__(
        self,
        db_path: str = None,
        storage_dir: str = None,
    ):
        self.db_path = db_path or os.getenv(
            "MARKETPLACE_DB",
            "data/marketplace.db"
        )
        self.storage_dir = storage_dir or os.getenv(
            "PACKAGE_STORAGE",
            "data/packages"
        )

        self._init_database()
        os.makedirs(self.storage_dir, exist_ok=True)

    def _init_database(self):
        """Initialize marketplace database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Packages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_packages (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                format TEXT NOT NULL,
                record_count INTEGER,
                file_size_bytes INTEGER,
                content_hash TEXT NOT NULL,
                price_sol REAL NOT NULL,
                creator_wallet TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                status TEXT NOT NULL,
                preview_json TEXT,
                metadata_json TEXT,
                storage_url TEXT
            )
        """)

        # Contributors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS package_contributors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id TEXT NOT NULL,
                wallet TEXT NOT NULL,
                contribution_pct REAL NOT NULL,
                data_count INTEGER,
                FOREIGN KEY (package_id) REFERENCES data_packages(id)
            )
        """)

        # Purchases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS package_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id TEXT NOT NULL,
                buyer_wallet TEXT NOT NULL,
                price_sol REAL NOT NULL,
                tx_signature TEXT,
                purchased_at TEXT NOT NULL,
                FOREIGN KEY (package_id) REFERENCES data_packages(id)
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # PACKAGE CREATION
    # =========================================================================

    async def create_package(
        self,
        name: str,
        description: str,
        category: DataCategory,
        data: List[Dict[str, Any]],
        price_sol: float,
        creator_wallet: str,
        format: PackageFormat = PackageFormat.JSON,
        expires_days: int = 30,
    ) -> DataPackage:
        """
        Create a new data package.

        Args:
            name: Package name
            description: Description
            category: Data category
            data: List of data records
            price_sol: Price in SOL
            creator_wallet: Creator's wallet
            format: Output format
            expires_days: Days until expiration

        Returns:
            Created DataPackage
        """
        # Generate package ID
        package_id = hashlib.sha256(
            f"{name}:{creator_wallet}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        # Serialize data
        content, file_size = await self._serialize_data(data, format)

        # Calculate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Generate preview
        preview = self._generate_preview(data)

        # Calculate expiration
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_days) if expires_days > 0 else None

        # Store content
        storage_url = await self._store_content(package_id, content, format)

        # Create package
        package = DataPackage(
            id=package_id,
            name=name,
            description=description,
            category=category,
            format=format,
            record_count=len(data),
            file_size_bytes=file_size,
            content_hash=content_hash,
            price_sol=price_sol,
            creator_wallet=creator_wallet,
            created_at=now,
            expires_at=expires_at,
            preview_data=preview,
            storage_url=storage_url,
        )

        # Calculate contributors
        contributors = self._calculate_contributors(data)

        # Save to database
        await self._save_package(package, contributors)

        logger.info(f"Created data package: {package_id} ({name})")

        return package

    async def create_strategy_package(
        self,
        strategy_name: str,
        since: datetime,
        until: datetime = None,
        price_sol: float = 0.1,
        creator_wallet: str = "",
    ) -> DataPackage:
        """Create a package of strategy performance data"""
        # Fetch strategy data from aggregator
        from core.data.aggregator import get_trade_aggregator

        aggregator = get_trade_aggregator()
        aggregates = await aggregator.aggregate_by_strategy(since, until)

        # Find the specific strategy
        strategy_data = next(
            (a for a in aggregates if a.group_value == strategy_name),
            None
        )

        if strategy_data is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        # Create package data
        data = [{
            "strategy": strategy_name,
            "period_start": since.isoformat(),
            "period_end": (until or datetime.now(timezone.utc)).isoformat(),
            "trade_count": strategy_data.trade_count,
            "win_rate": strategy_data.win_rate,
            "avg_pnl_pct": strategy_data.avg_pnl_pct,
            "sharpe_ratio": strategy_data.sharpe_ratio,
            "max_drawdown": strategy_data.max_pnl - strategy_data.min_pnl,
        }]

        return await self.create_package(
            name=f"{strategy_name} Performance Data",
            description=f"Historical performance data for {strategy_name} strategy",
            category=DataCategory.STRATEGY_SIGNALS,
            data=data,
            price_sol=price_sol,
            creator_wallet=creator_wallet,
        )

    async def create_token_package(
        self,
        token_mint: str,
        since: datetime,
        until: datetime = None,
        price_sol: float = 0.05,
        creator_wallet: str = "",
    ) -> DataPackage:
        """Create a package of token trading data"""
        from core.data.aggregator import get_trade_aggregator

        aggregator = get_trade_aggregator()
        tokens = await aggregator.aggregate_by_token(since, until)

        token_data = next(
            (t for t in tokens if t.token_mint == token_mint),
            None
        )

        if token_data is None:
            raise ValueError(f"Token not found: {token_mint}")

        data = [{
            "token_mint": token_mint,
            "symbol": token_data.symbol,
            "period_start": since.isoformat(),
            "period_end": (until or datetime.now(timezone.utc)).isoformat(),
            "trade_count": token_data.trade_count,
            "win_rate": token_data.win_rate,
            "avg_pnl_pct": token_data.avg_pnl_pct,
            "volume_bucket": token_data.total_volume_bucket,
            "unique_traders": token_data.unique_traders,
            "best_strategy": token_data.best_strategy,
        }]

        return await self.create_package(
            name=f"{token_data.symbol or token_mint[:8]} Trading Data",
            description=f"Trading analytics for {token_data.symbol or token_mint}",
            category=DataCategory.TOKEN_ANALYSIS,
            data=data,
            price_sol=price_sol,
            creator_wallet=creator_wallet,
        )

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    async def _serialize_data(
        self,
        data: List[Dict],
        format: PackageFormat,
    ) -> tuple[bytes, int]:
        """Serialize data to bytes"""
        if format == PackageFormat.JSON:
            content = json.dumps(data, default=str).encode('utf-8')
        elif format == PackageFormat.CSV:
            if not data:
                content = b""
            else:
                import io
                import csv
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
                content = output.getvalue().encode('utf-8')
        else:
            # Default to JSON
            content = json.dumps(data, default=str).encode('utf-8')

        # Compress
        compressed = gzip.compress(content)

        return compressed, len(compressed)

    async def _store_content(
        self,
        package_id: str,
        content: bytes,
        format: PackageFormat,
    ) -> str:
        """Store package content"""
        # For now, store locally
        # In production, upload to IPFS or S3

        extension = format.value
        filename = f"{package_id}.{extension}.gz"
        filepath = os.path.join(self.storage_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(content)

        return f"file://{filepath}"

    def _generate_preview(self, data: List[Dict], max_records: int = 3) -> Dict:
        """Generate preview of package data"""
        if not data:
            return {"sample": [], "fields": []}

        # Get sample records (redact sensitive fields)
        sample = []
        for record in data[:max_records]:
            preview_record = {}
            for key, value in record.items():
                if key in ['user_hash', 'wallet']:
                    preview_record[key] = "***"
                elif isinstance(value, float):
                    preview_record[key] = round(value, 4)
                else:
                    preview_record[key] = value
            sample.append(preview_record)

        return {
            "sample": sample,
            "fields": list(data[0].keys()) if data else [],
            "total_records": len(data),
        }

    def _calculate_contributors(
        self,
        data: List[Dict],
    ) -> List[PackageContributor]:
        """Calculate data contributors and their shares"""
        # Count contributions by user_hash
        contributions: Dict[str, int] = {}

        for record in data:
            user_hash = record.get("user_hash", "unknown")
            contributions[user_hash] = contributions.get(user_hash, 0) + 1

        total = sum(contributions.values())

        # Create contributor records
        contributors = []
        for wallet_hash, count in contributions.items():
            contributors.append(PackageContributor(
                wallet=wallet_hash,
                contribution_pct=(count / total * 100) if total > 0 else 0,
                data_count=count,
            ))

        # Sort by contribution
        contributors.sort(key=lambda c: -c.contribution_pct)

        return contributors

    # =========================================================================
    # PACKAGE RETRIEVAL
    # =========================================================================

    async def get_package(self, package_id: str) -> Optional[DataPackage]:
        """Get a package by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM data_packages WHERE id = ?",
            (package_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return self._row_to_package(row)

    async def list_packages(
        self,
        category: DataCategory = None,
        status: PackageStatus = PackageStatus.ACTIVE,
        limit: int = 50,
    ) -> List[DataPackage]:
        """List available packages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM data_packages WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category.value)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        packages = [self._row_to_package(row) for row in cursor.fetchall()]

        conn.close()
        return packages

    async def get_package_content(self, package_id: str) -> Optional[bytes]:
        """Get package content (for purchasers)"""
        package = await self.get_package(package_id)
        if package is None:
            return None

        if package.storage_url and package.storage_url.startswith("file://"):
            filepath = package.storage_url[7:]
            with open(filepath, 'rb') as f:
                compressed = f.read()
            return gzip.decompress(compressed)

        return None

    # =========================================================================
    # PURCHASES
    # =========================================================================

    async def record_purchase(
        self,
        package_id: str,
        buyer_wallet: str,
        price_sol: float,
        tx_signature: str = None,
    ):
        """Record a package purchase"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO package_purchases
            (package_id, buyer_wallet, price_sol, tx_signature, purchased_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            package_id,
            buyer_wallet,
            price_sol,
            tx_signature,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    async def get_purchase_count(self, package_id: str) -> int:
        """Get number of purchases for a package"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM package_purchases WHERE package_id = ?",
            (package_id,)
        )

        count = cursor.fetchone()[0]
        conn.close()

        return count

    async def has_purchased(
        self,
        package_id: str,
        buyer_wallet: str,
    ) -> bool:
        """Check if wallet has purchased a package"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM package_purchases
            WHERE package_id = ? AND buyer_wallet = ?
        """, (package_id, buyer_wallet))

        result = cursor.fetchone() is not None
        conn.close()

        return result

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _save_package(
        self,
        package: DataPackage,
        contributors: List[PackageContributor],
    ):
        """Save package to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO data_packages
            (id, name, description, category, format, record_count,
             file_size_bytes, content_hash, price_sol, creator_wallet,
             created_at, expires_at, status, preview_json, metadata_json,
             storage_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            package.id,
            package.name,
            package.description,
            package.category.value,
            package.format.value,
            package.record_count,
            package.file_size_bytes,
            package.content_hash,
            package.price_sol,
            package.creator_wallet,
            package.created_at.isoformat(),
            package.expires_at.isoformat() if package.expires_at else None,
            package.status.value,
            json.dumps(package.preview_data) if package.preview_data else None,
            json.dumps(package.metadata),
            package.storage_url,
        ))

        # Save contributors
        for contributor in contributors:
            cursor.execute("""
                INSERT INTO package_contributors
                (package_id, wallet, contribution_pct, data_count)
                VALUES (?, ?, ?, ?)
            """, (
                package.id,
                contributor.wallet,
                contributor.contribution_pct,
                contributor.data_count,
            ))

        conn.commit()
        conn.close()

    def _row_to_package(self, row: tuple) -> DataPackage:
        """Convert database row to DataPackage"""
        return DataPackage(
            id=row[0],
            name=row[1],
            description=row[2],
            category=DataCategory(row[3]),
            format=PackageFormat(row[4]),
            record_count=row[5],
            file_size_bytes=row[6],
            content_hash=row[7],
            price_sol=row[8],
            creator_wallet=row[9],
            created_at=datetime.fromisoformat(row[10]),
            expires_at=datetime.fromisoformat(row[11]) if row[11] else None,
            status=PackageStatus(row[12]),
            preview_data=json.loads(row[13]) if row[13] else None,
            metadata=json.loads(row[14]) if row[14] else {},
            storage_url=row[15],
        )


# =============================================================================
# SINGLETON
# =============================================================================

_packager: Optional[DataPackager] = None


def get_data_packager() -> DataPackager:
    """Get or create the data packager singleton"""
    global _packager
    if _packager is None:
        _packager = DataPackager()
    return _packager
