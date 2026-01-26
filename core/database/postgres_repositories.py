"""
PostgreSQL Repository Pattern Implementation.

Provides async repositories for PostgreSQL backend:
- PostgresPositionRepository
- PostgresTradeRepository
- PostgresUserRepository
- PostgresConfigRepository

Usage:
    from core.database.postgres_repositories import PostgresPositionRepository

    repo = PostgresPositionRepository()
    positions = await repo.get_open_positions(user_id=123)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from .postgres_client import PostgresClient, get_postgres_client

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Domain Entities (same as SQLite versions for compatibility)
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
    id: str = ""
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
    id: str = ""
    user_id: int = 0
    position_id: Optional[str] = None
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
# Base Repository
# =============================================================================

class PostgresBaseRepository(ABC, Generic[T]):
    """
    Abstract base repository for PostgreSQL.

    Subclasses must define:
    - table_name: str
    - _row_to_entity(row): Convert DB row to entity
    """

    table_name: str = ""

    def __init__(
        self,
        connection_url: Optional[str] = None,
        client: Optional[PostgresClient] = None
    ):
        if client:
            self._client = client
        elif connection_url:
            self._client = PostgresClient(connection_url=connection_url)
        else:
            self._client = get_postgres_client()

    @abstractmethod
    def _row_to_entity(self, row: Dict[str, Any]) -> T:
        """Convert a database row to a domain entity."""
        pass

    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by primary key."""
        row = await self._client.fetchrow(
            f"SELECT * FROM {self.table_name} WHERE id = $1",
            id
        )
        return self._row_to_entity(row) if row else None

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        rows = await self._client.fetch(
            f"SELECT * FROM {self.table_name} ORDER BY id DESC LIMIT $1 OFFSET $2",
            limit,
            offset
        )
        return [self._row_to_entity(row) for row in rows]

    async def count(self) -> int:
        """Count all entities."""
        return await self._client.fetchval(
            f"SELECT COUNT(*) FROM {self.table_name}"
        )

    async def delete(self, id: Any) -> bool:
        """Delete entity by ID."""
        result = await self._client.execute(
            f"DELETE FROM {self.table_name} WHERE id = $1",
            id
        )
        return "DELETE" in result


# =============================================================================
# Concrete Repositories
# =============================================================================

class PostgresUserRepository(PostgresBaseRepository[User]):
    """Repository for User operations."""

    table_name = "users"

    def _row_to_entity(self, row: Dict[str, Any]) -> User:
        return User(
            id=row['id'] if 'id' in row else row.get('user_id', 0),
            telegram_id=row.get('telegram_id') or row.get('telegram_user_id', 0),
            username=row.get('username') or row.get('telegram_username'),
            first_name=row.get('first_name'),
            is_admin=bool(row.get('is_admin', False)),
            is_active=bool(row.get('is_active', True)),
            created_at=row.get('created_at') or datetime.now(),
            updated_at=row.get('updated_at') or datetime.now(),
        )

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        row = await self._client.fetchrow(
            f"SELECT * FROM {self.table_name} WHERE telegram_user_id = $1",
            telegram_id
        )
        return self._row_to_entity(row) if row else None

    async def get_admins(self) -> List[User]:
        """Get all admin users."""
        rows = await self._client.fetch(
            f"SELECT * FROM {self.table_name} WHERE is_admin = true"
        )
        return [self._row_to_entity(row) for row in rows]

    async def create(self, user: User) -> User:
        """Create a new user."""
        row = await self._client.fetchrow(
            """
            INSERT INTO users (telegram_user_id, telegram_username, first_name, is_admin, is_active)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user.telegram_id,
            user.username,
            user.first_name,
            user.is_admin,
            user.is_active
        )
        return self._row_to_entity(row)


class PostgresPositionRepository(PostgresBaseRepository[Position]):
    """Repository for Position operations."""

    table_name = "positions"

    def _row_to_entity(self, row: Dict[str, Any]) -> Position:
        return Position(
            id=str(row.get('id', '')),
            user_id=row.get('user_id', 0),
            token_mint=row.get('token_mint', ''),
            token_symbol=row.get('symbol') or row.get('token_symbol', ''),
            entry_price=float(row.get('entry_price', 0)),
            current_price=float(row.get('current_price', 0)),
            quantity=float(row.get('quantity') or row.get('entry_amount_tokens', 0)),
            cost_basis=float(row.get('cost_basis') or row.get('entry_amount_sol', 0)),
            unrealized_pnl=float(row.get('unrealized_pnl') or row.get('pnl_sol', 0)),
            unrealized_pnl_pct=float(row.get('unrealized_pnl_pct') or row.get('pnl_pct', 0)),
            take_profit_pct=float(row['take_profit_pct']) if row.get('take_profit_pct') else None,
            stop_loss_pct=float(row['stop_loss_pct']) if row.get('stop_loss_pct') else None,
            status=row.get('status', 'open'),
            opened_at=row.get('opened_at') or datetime.now(),
            closed_at=row.get('closed_at'),
        )

    async def get_open_positions(self, user_id: Optional[int] = None) -> List[Position]:
        """Get all open positions, optionally filtered by user."""
        if user_id is not None:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} WHERE status = 'open' AND user_id = $1",
                user_id
            )
        else:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} WHERE status = 'open'"
            )
        return [self._row_to_entity(row) for row in rows]

    async def get_by_token_mint(self, token_mint: str, user_id: Optional[int] = None) -> List[Position]:
        """Get positions for a specific token."""
        if user_id is not None:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} WHERE token_mint = $1 AND user_id = $2",
                token_mint,
                user_id
            )
        else:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} WHERE token_mint = $1",
                token_mint
            )
        return [self._row_to_entity(row) for row in rows]

    async def close_position(self, position_id: str) -> bool:
        """Mark a position as closed."""
        result = await self._client.execute(
            f"UPDATE {self.table_name} SET status = 'closed', closed_at = $1 WHERE id = $2",
            datetime.utcnow(),
            position_id
        )
        return "UPDATE" in result


class PostgresTradeRepository(PostgresBaseRepository[Trade]):
    """Repository for Trade operations."""

    table_name = "trades"

    def _row_to_entity(self, row: Dict[str, Any]) -> Trade:
        return Trade(
            id=str(row.get('id', '')),
            user_id=row.get('user_id', 0),
            position_id=str(row['position_id']) if row.get('position_id') else None,
            token_mint=row.get('token_mint', ''),
            token_symbol=row.get('symbol') or row.get('token_symbol', ''),
            side=row.get('side', 'buy'),
            price=float(row.get('price', 0)),
            quantity=float(row.get('quantity') or row.get('amount_tokens', 0)),
            total_value=float(row.get('total_value') or row.get('amount_sol', 0)),
            fee=float(row.get('fee', 0)),
            tx_signature=row.get('tx_signature'),
            status=row.get('status', 'completed'),
            executed_at=row.get('executed_at') or row.get('timestamp') or datetime.now(),
        )

    async def get_recent_trades(self, user_id: Optional[int] = None, limit: int = 50) -> List[Trade]:
        """Get recent trades."""
        if user_id is not None:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2",
                user_id,
                limit
            )
        else:
            rows = await self._client.fetch(
                f"SELECT * FROM {self.table_name} ORDER BY timestamp DESC LIMIT $1",
                limit
            )
        return [self._row_to_entity(row) for row in rows]

    async def get_by_tx_signature(self, tx_signature: str) -> Optional[Trade]:
        """Get trade by transaction signature."""
        row = await self._client.fetchrow(
            f"SELECT * FROM {self.table_name} WHERE tx_signature = $1",
            tx_signature
        )
        return self._row_to_entity(row) if row else None


class PostgresConfigRepository(PostgresBaseRepository[BotConfig]):
    """Repository for bot configuration."""

    table_name = "bot_config"

    def _row_to_entity(self, row: Dict[str, Any]) -> BotConfig:
        return BotConfig(
            id=row.get('id', 0),
            key=row.get('key', ''),
            value=row.get('value', ''),
            description=row.get('description'),
            updated_at=row.get('updated_at') or datetime.now(),
        )

    async def get_value(self, key: str, default: str = "") -> str:
        """Get config value by key."""
        row = await self._client.fetchrow(
            f"SELECT value FROM {self.table_name} WHERE key = $1",
            key
        )
        return row['value'] if row else default

    async def set_value(
        self,
        key: str,
        value: str,
        description: Optional[str] = None
    ) -> None:
        """Set config value (upsert)."""
        await self._client.execute(
            """
            INSERT INTO bot_config (key, value, description, updated_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
            """,
            key,
            value,
            description,
            datetime.utcnow()
        )


# =============================================================================
# Factory Functions
# =============================================================================

def get_position_repository(
    connection_url: Optional[str] = None
) -> PostgresPositionRepository:
    """Get position repository instance."""
    return PostgresPositionRepository(connection_url=connection_url)


def get_trade_repository(
    connection_url: Optional[str] = None
) -> PostgresTradeRepository:
    """Get trade repository instance."""
    return PostgresTradeRepository(connection_url=connection_url)


def get_user_repository(
    connection_url: Optional[str] = None
) -> PostgresUserRepository:
    """Get user repository instance."""
    return PostgresUserRepository(connection_url=connection_url)


def get_config_repository(
    connection_url: Optional[str] = None
) -> PostgresConfigRepository:
    """Get config repository instance."""
    return PostgresConfigRepository(connection_url=connection_url)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Entities
    "User",
    "Position",
    "Trade",
    "BotConfig",
    # Repositories
    "PostgresBaseRepository",
    "PostgresUserRepository",
    "PostgresPositionRepository",
    "PostgresTradeRepository",
    "PostgresConfigRepository",
    # Factory functions
    "get_position_repository",
    "get_trade_repository",
    "get_user_repository",
    "get_config_repository",
]
