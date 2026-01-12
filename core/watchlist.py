"""
Token Watchlist Manager - Track tokens of interest with alerts and notes.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class WatchlistPriority(Enum):
    """Priority levels for watchlist items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WatchlistCategory(Enum):
    """Categories for organizing watchlist items."""
    TRENDING = "trending"
    WHALE_ACTIVITY = "whale_activity"
    NEW_LISTING = "new_listing"
    SENTIMENT_SIGNAL = "sentiment_signal"
    TECHNICAL_SIGNAL = "technical_signal"
    INFLUENCER_MENTION = "influencer_mention"
    CUSTOM = "custom"


@dataclass
class WatchlistItem:
    """A token on the watchlist."""
    id: Optional[int] = None
    symbol: str = ""
    name: str = ""
    mint_address: str = ""
    category: WatchlistCategory = WatchlistCategory.CUSTOM
    priority: WatchlistPriority = WatchlistPriority.MEDIUM
    notes: str = ""
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    current_price: float = 0.0
    price_at_add: float = 0.0
    added_at: str = ""
    last_checked: str = ""
    alert_enabled: bool = True
    alert_threshold_percent: float = 10.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WatchlistAlert:
    """Alert triggered by watchlist conditions."""
    item_id: int
    symbol: str
    alert_type: str  # price_target, stop_loss, threshold
    message: str
    triggered_at: str
    price_at_trigger: float
    acknowledged: bool = False


class WatchlistDB:
    """SQLite storage for watchlist."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    mint_address TEXT,
                    category TEXT DEFAULT 'custom',
                    priority TEXT DEFAULT 'medium',
                    notes TEXT,
                    target_price REAL,
                    stop_loss REAL,
                    current_price REAL DEFAULT 0,
                    price_at_add REAL DEFAULT 0,
                    added_at TEXT,
                    last_checked TEXT,
                    alert_enabled INTEGER DEFAULT 1,
                    alert_threshold_percent REAL DEFAULT 10,
                    tags_json TEXT,
                    metadata_json TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    symbol TEXT,
                    alert_type TEXT,
                    message TEXT,
                    triggered_at TEXT,
                    price_at_trigger REAL,
                    acknowledged INTEGER DEFAULT 0,
                    FOREIGN KEY (item_id) REFERENCES watchlist(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    timestamp TEXT,
                    price REAL,
                    FOREIGN KEY (item_id) REFERENCES watchlist(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_active ON watchlist(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_item ON watchlist_alerts(item_id)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class WatchlistManager:
    """
    Manage token watchlist with alerts and tracking.

    Usage:
        manager = WatchlistManager()

        # Add token to watchlist
        manager.add_token(WatchlistItem(
            symbol="BONK",
            name="Bonk",
            mint_address="DezXAZ...",
            category=WatchlistCategory.TRENDING,
            target_price=0.00005
        ))

        # Check for alerts
        alerts = manager.check_alerts()

        # Get watchlist
        tokens = manager.get_watchlist(category=WatchlistCategory.TRENDING)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "watchlist.db"
        self.db = WatchlistDB(db_path)

    def add_token(self, item: WatchlistItem) -> int:
        """Add a token to the watchlist."""
        item.added_at = datetime.now(timezone.utc).isoformat()
        item.last_checked = item.added_at

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watchlist
                (symbol, name, mint_address, category, priority, notes,
                 target_price, stop_loss, current_price, price_at_add,
                 added_at, last_checked, alert_enabled, alert_threshold_percent,
                 tags_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.symbol.upper(), item.name, item.mint_address,
                item.category.value, item.priority.value, item.notes,
                item.target_price, item.stop_loss, item.current_price, item.price_at_add,
                item.added_at, item.last_checked, 1 if item.alert_enabled else 0,
                item.alert_threshold_percent, json.dumps(item.tags),
                json.dumps(item.metadata)
            ))
            conn.commit()
            item_id = cursor.lastrowid

        logger.info(f"Added {item.symbol} to watchlist (id={item_id})")
        return item_id

    def remove_token(self, item_id: int = None, symbol: str = None) -> bool:
        """Remove a token from the watchlist."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if item_id:
                cursor.execute("UPDATE watchlist SET is_active = 0 WHERE id = ?", (item_id,))
            elif symbol:
                cursor.execute("UPDATE watchlist SET is_active = 0 WHERE symbol = ?", (symbol.upper(),))
            else:
                return False

            conn.commit()
            return cursor.rowcount > 0

    def update_token(self, item_id: int, updates: Dict[str, Any]) -> bool:
        """Update a watchlist item."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            set_clauses = []
            values = []

            for key, value in updates.items():
                if key in ('category', 'priority'):
                    if hasattr(value, 'value'):
                        value = value.value
                elif key in ('tags', 'metadata'):
                    value = json.dumps(value)
                    key = f"{key}_json"
                elif key == 'alert_enabled':
                    value = 1 if value else 0

                set_clauses.append(f"{key} = ?")
                values.append(value)

            if not set_clauses:
                return False

            values.append(item_id)
            cursor.execute(f"""
                UPDATE watchlist
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, values)
            conn.commit()

            return cursor.rowcount > 0

    def get_token(self, item_id: int = None, symbol: str = None) -> Optional[WatchlistItem]:
        """Get a specific watchlist item."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if item_id:
                cursor.execute("SELECT * FROM watchlist WHERE id = ? AND is_active = 1", (item_id,))
            elif symbol:
                cursor.execute("SELECT * FROM watchlist WHERE symbol = ? AND is_active = 1", (symbol.upper(),))
            else:
                return None

            row = cursor.fetchone()
            return self._row_to_item(row) if row else None

    def get_watchlist(
        self,
        category: WatchlistCategory = None,
        priority: WatchlistPriority = None,
        alert_enabled: bool = None
    ) -> List[WatchlistItem]:
        """Get watchlist items with optional filters."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM watchlist WHERE is_active = 1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category.value)
            if priority:
                query += " AND priority = ?"
                params.append(priority.value)
            if alert_enabled is not None:
                query += " AND alert_enabled = ?"
                params.append(1 if alert_enabled else 0)

            query += " ORDER BY priority DESC, added_at DESC"

            cursor.execute(query, params)
            return [self._row_to_item(row) for row in cursor.fetchall()]

    def _row_to_item(self, row: sqlite3.Row) -> WatchlistItem:
        """Convert database row to WatchlistItem."""
        return WatchlistItem(
            id=row['id'],
            symbol=row['symbol'],
            name=row['name'] or "",
            mint_address=row['mint_address'] or "",
            category=WatchlistCategory(row['category']),
            priority=WatchlistPriority(row['priority']),
            notes=row['notes'] or "",
            target_price=row['target_price'],
            stop_loss=row['stop_loss'],
            current_price=row['current_price'] or 0,
            price_at_add=row['price_at_add'] or 0,
            added_at=row['added_at'] or "",
            last_checked=row['last_checked'] or "",
            alert_enabled=bool(row['alert_enabled']),
            alert_threshold_percent=row['alert_threshold_percent'] or 10,
            tags=json.loads(row['tags_json']) if row['tags_json'] else [],
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
        )

    def update_price(self, item_id: int, price: float):
        """Update current price for a watchlist item."""
        now = datetime.now(timezone.utc).isoformat()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE watchlist
                SET current_price = ?, last_checked = ?
                WHERE id = ?
            """, (price, now, item_id))

            cursor.execute("""
                INSERT INTO watchlist_price_history (item_id, timestamp, price)
                VALUES (?, ?, ?)
            """, (item_id, now, price))

            conn.commit()

    def check_alerts(self, current_prices: Dict[str, float] = None) -> List[WatchlistAlert]:
        """Check all watchlist items for alert conditions."""
        alerts = []
        items = self.get_watchlist(alert_enabled=True)

        for item in items:
            # Use provided price or stored price
            if current_prices and item.symbol in current_prices:
                current_price = current_prices[item.symbol]
                self.update_price(item.id, current_price)
            else:
                current_price = item.current_price

            if current_price <= 0 or item.price_at_add <= 0:
                continue

            # Check target price
            if item.target_price and current_price >= item.target_price:
                alert = WatchlistAlert(
                    item_id=item.id,
                    symbol=item.symbol,
                    alert_type="price_target",
                    message=f"{item.symbol} hit target price: ${current_price:.8f} >= ${item.target_price:.8f}",
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                    price_at_trigger=current_price
                )
                alerts.append(alert)
                self._save_alert(alert)

            # Check stop loss
            if item.stop_loss and current_price <= item.stop_loss:
                alert = WatchlistAlert(
                    item_id=item.id,
                    symbol=item.symbol,
                    alert_type="stop_loss",
                    message=f"{item.symbol} hit stop loss: ${current_price:.8f} <= ${item.stop_loss:.8f}",
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                    price_at_trigger=current_price
                )
                alerts.append(alert)
                self._save_alert(alert)

            # Check threshold
            change_percent = ((current_price - item.price_at_add) / item.price_at_add) * 100
            if abs(change_percent) >= item.alert_threshold_percent:
                direction = "up" if change_percent > 0 else "down"
                alert = WatchlistAlert(
                    item_id=item.id,
                    symbol=item.symbol,
                    alert_type="threshold",
                    message=f"{item.symbol} moved {direction} {abs(change_percent):.1f}% since added",
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                    price_at_trigger=current_price
                )
                alerts.append(alert)
                self._save_alert(alert)

        return alerts

    def _save_alert(self, alert: WatchlistAlert):
        """Save an alert to the database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO watchlist_alerts
                (item_id, symbol, alert_type, message, triggered_at, price_at_trigger)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                alert.item_id, alert.symbol, alert.alert_type,
                alert.message, alert.triggered_at, alert.price_at_trigger
            ))
            conn.commit()

    def get_alerts(
        self,
        unacknowledged_only: bool = True,
        item_id: int = None
    ) -> List[WatchlistAlert]:
        """Get alerts."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM watchlist_alerts WHERE 1=1"
            params = []

            if unacknowledged_only:
                query += " AND acknowledged = 0"
            if item_id:
                query += " AND item_id = ?"
                params.append(item_id)

            query += " ORDER BY triggered_at DESC"

            cursor.execute(query, params)

            return [
                WatchlistAlert(
                    item_id=row['item_id'],
                    symbol=row['symbol'],
                    alert_type=row['alert_type'],
                    message=row['message'],
                    triggered_at=row['triggered_at'],
                    price_at_trigger=row['price_at_trigger'],
                    acknowledged=bool(row['acknowledged'])
                )
                for row in cursor.fetchall()
            ]

    def acknowledge_alert(self, alert_id: int):
        """Acknowledge an alert."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE watchlist_alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
            conn.commit()

    def get_summary(self) -> Dict[str, Any]:
        """Get watchlist summary."""
        items = self.get_watchlist()
        alerts = self.get_alerts(unacknowledged_only=True)

        by_category = {}
        by_priority = {}

        for item in items:
            cat = item.category.value
            pri = item.priority.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_priority[pri] = by_priority.get(pri, 0) + 1

        return {
            'total_tokens': len(items),
            'by_category': by_category,
            'by_priority': by_priority,
            'active_alerts': len(alerts),
            'alert_enabled_count': len([i for i in items if i.alert_enabled])
        }


# Singleton
_manager: Optional[WatchlistManager] = None

def get_watchlist_manager() -> WatchlistManager:
    """Get singleton watchlist manager."""
    global _manager
    if _manager is None:
        _manager = WatchlistManager()
    return _manager
