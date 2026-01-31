"""
Repository Pattern Implementation for Jarvis.

Provides a clean abstraction layer between business logic and database access.
Each repository handles a specific domain (Users, Trades, Positions, etc.)

Usage:
    from core.database.repositories import UserRepository, TradeRepository
    
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(123456)
    
    trade_repo = TradeRepository()
    trades = await trade_repo.get_open_trades(user_id=user.id)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
import logging

from . import get_core_db, get_analytics_db, get_cache_db, ConnectionPool
from core.security_validation import sanitize_sql_identifier

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Base Repository
# =============================================================================

class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.
    
    Subclasses must define:
    - table_name: str
    - _row_to_entity(row): Convert DB row to entity
    - _entity_to_dict(entity): Convert entity to dict for INSERT/UPDATE
    """
    
    table_name: str = ""

    def __init__(self, pool: ConnectionPool):
        self.pool = pool

        # Validate table_name to prevent SQL injection
        # table_name should be a string literal from class definition, not dynamic
        if self.table_name:
            try:
                # This will raise ValidationError if table_name contains forbidden characters
                sanitize_sql_identifier(self.table_name)
            except Exception as e:
                raise ValueError(
                    f"Invalid table_name '{self.table_name}' for {self.__class__.__name__}: {e}. "
                    "table_name must be a valid SQL identifier (alphanumeric + underscore only)."
                )
    
    @abstractmethod
    def _row_to_entity(self, row) -> T:
        """Convert a database row to a domain entity."""
        pass
    
    @abstractmethod
    def _entity_to_dict(self, entity: T) -> Dict[str, Any]:
        """Convert a domain entity to a dict for database operations."""
        pass
    
    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by primary key.

        NOTE: This generic implementation uses SELECT * which is inefficient.
        Child classes should override this with explicit column lists for production use.
        Example:
            columns = "id, name, created_at"
            cursor.execute(f"SELECT {columns} FROM {self.table_name} WHERE id = ?", (id,))
        """
        # Fallback implementation - child classes should override with explicit columns
        with self.pool.cursor() as cursor:
            # Get column list from table schema for optimization
            # table_name is validated in __init__, but sanitize again for safety
            safe_table = sanitize_sql_identifier(self.table_name)
            cursor.execute(f"PRAGMA table_info({safe_table})")
            # Sanitize each column name from schema to prevent injection
            column_names = [sanitize_sql_identifier(col[1]) for col in cursor.fetchall()]
            columns = ", ".join(column_names)

            cursor.execute(f"SELECT {columns} FROM {safe_table} WHERE id = ?", (id,))
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all entities with pagination.

        NOTE: This generic implementation dynamically builds column list from schema.
        Child classes should override with explicit column lists for maximum performance.
        """
        with self.pool.cursor() as cursor:
            # Get column list from table schema (cached per table)
            # table_name is validated in __init__, but sanitize again for safety
            safe_table = sanitize_sql_identifier(self.table_name)
            cursor.execute(f"PRAGMA table_info({safe_table})")
            # Sanitize each column name from schema to prevent injection
            column_names = [sanitize_sql_identifier(col[1]) for col in cursor.fetchall()]
            columns = ", ".join(column_names)

            cursor.execute(
                f"SELECT {columns} FROM {safe_table} ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def count(self) -> int:
        """Count all entities."""
        with self.pool.cursor() as cursor:
            safe_table = sanitize_sql_identifier(self.table_name)
            cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
            return cursor.fetchone()[0]
    
    def delete(self, id: int) -> bool:
        """Delete entity by ID."""
        with self.pool.cursor() as cursor:
            safe_table = sanitize_sql_identifier(self.table_name)
            cursor.execute(f"DELETE FROM {safe_table} WHERE id = ?", (id,))
            return cursor.rowcount > 0


# =============================================================================
# Domain Entities
# =============================================================================

@dataclass
class User:
    """User entity."""
    id: int = 0
    telegram_id: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Position:
    """Trading position entity."""
    id: int = 0
    user_id: int = 0
    token_mint: str = ""
    token_symbol: str = ""
    entry_price: float = 0.0
    current_price: float = 0.0
    quantity: float = 0.0
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    status: str = "open"
    opened_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None


@dataclass
class Trade:
    """Trade entity (executed transaction)."""
    id: int = 0
    user_id: int = 0
    position_id: Optional[int] = None
    token_mint: str = ""
    token_symbol: str = ""
    side: str = "buy"  # buy/sell
    price: float = 0.0
    quantity: float = 0.0
    total_value: float = 0.0
    fee: float = 0.0
    tx_signature: Optional[str] = None
    status: str = "completed"
    executed_at: datetime = field(default_factory=datetime.now)


@dataclass 
class BotConfig:
    """Bot configuration entity."""
    id: int = 0
    key: str = ""
    value: str = ""
    description: Optional[str] = None
    updated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# Concrete Repositories
# =============================================================================

class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    table_name = "users"
    
    def __init__(self):
        super().__init__(get_core_db())
    
    def _row_to_entity(self, row) -> User:
        return User(
            id=row['id'],
            telegram_id=row['telegram_id'],
            username=row['username'],
            first_name=row.get('first_name'),
            is_admin=bool(row.get('is_admin', 0)),
            is_active=bool(row.get('is_active', 1)),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else datetime.now(),
        )
    
    def _entity_to_dict(self, entity: User) -> Dict[str, Any]:
        return {
            'telegram_id': entity.telegram_id,
            'username': entity.username,
            'first_name': entity.first_name,
            'is_admin': int(entity.is_admin),
            'is_active': int(entity.is_active),
            'updated_at': datetime.now().isoformat(),
        }
    
    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        # Optimized: Only fetch needed columns (hardcoded safe column names)
        columns = "id, telegram_id, username, first_name, is_admin, is_active, created_at, updated_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"SELECT {columns} FROM {safe_table} WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None
    
    def get_admins(self) -> List[User]:
        """Get all admin users."""
        # Optimized: Only fetch needed columns (hardcoded safe column names)
        columns = "id, telegram_id, username, first_name, is_admin, is_active, created_at, updated_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"SELECT {columns} FROM {safe_table} WHERE is_admin = 1"
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def create(self, user: User) -> User:
        """Create a new user."""
        data = self._entity_to_dict(user)
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ','.join(['?' for _ in cols])

        # Sanitize table and column names
        safe_table = sanitize_sql_identifier(self.table_name)
        safe_cols = [sanitize_sql_identifier(col) for col in cols]

        with self.pool.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {safe_table} ({','.join(safe_cols)}) VALUES ({placeholders})",
                vals
            )
            user.id = cursor.lastrowid
        return user


class PositionRepository(BaseRepository[Position]):
    """Repository for Position operations."""
    
    table_name = "positions"
    
    def __init__(self):
        super().__init__(get_core_db())
    
    def _row_to_entity(self, row) -> Position:
        return Position(
            id=row['id'],
            user_id=row['user_id'],
            token_mint=row['token_mint'],
            token_symbol=row.get('token_symbol', ''),
            entry_price=float(row.get('entry_price', 0)),
            current_price=float(row.get('current_price', 0)),
            quantity=float(row.get('quantity', 0)),
            cost_basis=float(row.get('cost_basis', 0)),
            unrealized_pnl=float(row.get('unrealized_pnl', 0)),
            unrealized_pnl_pct=float(row.get('unrealized_pnl_pct', 0)),
            take_profit_pct=float(row['take_profit_pct']) if row.get('take_profit_pct') else None,
            stop_loss_pct=float(row['stop_loss_pct']) if row.get('stop_loss_pct') else None,
            status=row.get('status', 'open'),
            opened_at=datetime.fromisoformat(row['opened_at']) if row.get('opened_at') else datetime.now(),
            closed_at=datetime.fromisoformat(row['closed_at']) if row.get('closed_at') else None,
        )
    
    def _entity_to_dict(self, entity: Position) -> Dict[str, Any]:
        return {
            'user_id': entity.user_id,
            'token_mint': entity.token_mint,
            'token_symbol': entity.token_symbol,
            'entry_price': entity.entry_price,
            'current_price': entity.current_price,
            'quantity': entity.quantity,
            'cost_basis': entity.cost_basis,
            'take_profit_pct': entity.take_profit_pct,
            'stop_loss_pct': entity.stop_loss_pct,
            'status': entity.status,
        }
    
    def get_open_positions(self, user_id: Optional[int] = None) -> List[Position]:
        """Get all open positions, optionally filtered by user."""
        # Optimized: Only fetch needed columns for trading hot path (hardcoded safe column names)
        columns = "id, user_id, token_mint, token_symbol, entry_price, current_price, quantity, cost_basis, unrealized_pnl, unrealized_pnl_pct, take_profit_pct, stop_loss_pct, status, opened_at, closed_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            if user_id:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} WHERE status = 'open' AND user_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} WHERE status = 'open'"
                )
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def get_by_token(self, token_mint: str, user_id: Optional[int] = None) -> List[Position]:
        """Get positions for a specific token."""
        # Optimized: Only fetch needed columns (hardcoded safe column names)
        columns = "id, user_id, token_mint, token_symbol, entry_price, current_price, quantity, cost_basis, unrealized_pnl, unrealized_pnl_pct, take_profit_pct, stop_loss_pct, status, opened_at, closed_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            if user_id:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} WHERE token_mint = ? AND user_id = ?",
                    (token_mint, user_id)
                )
            else:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} WHERE token_mint = ?",
                    (token_mint,)
                )
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def close_position(self, position_id: int) -> bool:
        """Mark a position as closed."""
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"UPDATE {safe_table} SET status = 'closed', closed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), position_id)
            )
            return cursor.rowcount > 0


class TradeRepository(BaseRepository[Trade]):
    """Repository for Trade operations."""
    
    table_name = "trades"
    
    def __init__(self):
        super().__init__(get_core_db())
    
    def _row_to_entity(self, row) -> Trade:
        return Trade(
            id=row['id'],
            user_id=row['user_id'],
            position_id=row.get('position_id'),
            token_mint=row['token_mint'],
            token_symbol=row.get('token_symbol', ''),
            side=row.get('side', 'buy'),
            price=float(row.get('price', 0)),
            quantity=float(row.get('quantity', 0)),
            total_value=float(row.get('total_value', 0)),
            fee=float(row.get('fee', 0)),
            tx_signature=row.get('tx_signature'),
            status=row.get('status', 'completed'),
            executed_at=datetime.fromisoformat(row['executed_at']) if row.get('executed_at') else datetime.now(),
        )
    
    def _entity_to_dict(self, entity: Trade) -> Dict[str, Any]:
        return {
            'user_id': entity.user_id,
            'position_id': entity.position_id,
            'token_mint': entity.token_mint,
            'token_symbol': entity.token_symbol,
            'side': entity.side,
            'price': entity.price,
            'quantity': entity.quantity,
            'total_value': entity.total_value,
            'fee': entity.fee,
            'tx_signature': entity.tx_signature,
            'status': entity.status,
            'executed_at': entity.executed_at.isoformat(),
        }
    
    def get_recent_trades(self, user_id: Optional[int] = None, limit: int = 50) -> List[Trade]:
        """Get recent trades."""
        # Optimized: Only fetch needed columns for trade history (hardcoded safe column names)
        columns = "id, user_id, position_id, token_mint, token_symbol, side, price, quantity, total_value, fee, tx_signature, status, executed_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            if user_id:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} WHERE user_id = ? ORDER BY executed_at DESC LIMIT ?",
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    f"SELECT {columns} FROM {safe_table} ORDER BY executed_at DESC LIMIT ?",
                    (limit,)
                )
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def get_by_tx_signature(self, tx_signature: str) -> Optional[Trade]:
        """Get trade by transaction signature."""
        # Optimized: Only fetch needed columns (hardcoded safe column names)
        columns = "id, user_id, position_id, token_mint, token_symbol, side, price, quantity, total_value, fee, tx_signature, status, executed_at"
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"SELECT {columns} FROM {safe_table} WHERE tx_signature = ?",
                (tx_signature,)
            )
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None


class ConfigRepository(BaseRepository[BotConfig]):
    """Repository for bot configuration."""
    
    table_name = "bot_config"
    
    def __init__(self):
        super().__init__(get_core_db())
    
    def _row_to_entity(self, row) -> BotConfig:
        return BotConfig(
            id=row['id'],
            key=row['key'],
            value=row['value'],
            description=row.get('description'),
            updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else datetime.now(),
        )
    
    def _entity_to_dict(self, entity: BotConfig) -> Dict[str, Any]:
        return {
            'key': entity.key,
            'value': entity.value,
            'description': entity.description,
            'updated_at': datetime.now().isoformat(),
        }
    
    def get_value(self, key: str, default: str = "") -> str:
        """Get config value by key."""
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"SELECT value FROM {safe_table} WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else default
    
    def set_value(self, key: str, value: str, description: Optional[str] = None) -> None:
        """Set config value (upsert)."""
        safe_table = sanitize_sql_identifier(self.table_name)
        with self.pool.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO {safe_table} (key, value, description, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?""",
                (key, value, description, datetime.now().isoformat(), value, datetime.now().isoformat())
            )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base
    "BaseRepository",
    # Entities
    "User",
    "Position",
    "Trade",
    "BotConfig",
    # Repositories
    "UserRepository",
    "PositionRepository",
    "TradeRepository",
    "ConfigRepository",
]
