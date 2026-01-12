"""
Position Manager - Advanced position management and risk controls.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid
import threading

logger = logging.getLogger(__name__)


class PositionType(Enum):
    """Position types."""
    SPOT = "spot"
    PERP_LONG = "perp_long"
    PERP_SHORT = "perp_short"
    MARGIN_LONG = "margin_long"
    MARGIN_SHORT = "margin_short"


class RiskLevel(Enum):
    """Position risk levels."""
    SAFE = "safe"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    LIQUIDATION = "liquidation"


class PositionAction(Enum):
    """Position actions."""
    OPEN = "open"
    INCREASE = "increase"
    DECREASE = "decrease"
    CLOSE = "close"
    LIQUIDATE = "liquidate"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class PositionRisk:
    """Position risk metrics."""
    risk_level: RiskLevel
    health_factor: float  # > 1 is safe
    liquidation_price: float
    margin_ratio: float
    distance_to_liquidation_pct: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    max_loss_potential: float
    risk_score: int  # 0-100


@dataclass
class ManagedPosition:
    """A managed position with risk controls."""
    id: str
    symbol: str
    position_type: PositionType
    side: str  # "long" or "short"
    size: float
    entry_price: float
    current_price: float
    leverage: float
    margin: float
    notional_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    fees_paid: float
    funding_paid: float
    opened_at: str
    updated_at: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    max_loss: Optional[float] = None
    risk: Optional[PositionRisk] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionLimits:
    """Position limits and constraints."""
    max_position_size: float  # Max size in USD
    max_leverage: float
    max_positions: int
    max_exposure_per_symbol: float  # Max % of portfolio
    max_total_exposure: float  # Max % of portfolio in positions
    min_margin_ratio: float
    max_loss_per_position: float
    max_daily_loss: float


@dataclass
class PositionEvent:
    """Position event record."""
    position_id: str
    action: PositionAction
    price: float
    size: float
    pnl: float
    fee: float
    timestamp: str
    reason: str


class PositionManagerDB:
    """SQLite storage for position manager."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS managed_positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    position_type TEXT,
                    side TEXT,
                    size REAL,
                    entry_price REAL,
                    current_price REAL,
                    leverage REAL,
                    margin REAL,
                    notional_value REAL,
                    unrealized_pnl REAL,
                    unrealized_pnl_pct REAL,
                    realized_pnl REAL,
                    fees_paid REAL,
                    funding_paid REAL,
                    opened_at TEXT,
                    updated_at TEXT,
                    closed_at TEXT,
                    stop_loss REAL,
                    take_profit REAL,
                    trailing_stop_pct REAL,
                    trailing_stop_price REAL,
                    max_loss REAL,
                    risk_json TEXT,
                    metadata_json TEXT,
                    is_open INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS position_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id TEXT NOT NULL,
                    action TEXT,
                    price REAL,
                    size REAL,
                    pnl REAL,
                    fee REAL,
                    timestamp TEXT,
                    reason TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    total_value REAL,
                    total_margin REAL,
                    total_unrealized_pnl REAL,
                    total_exposure REAL,
                    position_count INTEGER,
                    health_factor REAL
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON managed_positions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_open ON managed_positions(is_open)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_position ON position_events(position_id)")

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


class PositionManager:
    """
    Advanced position management with risk controls.

    Usage:
        manager = PositionManager()

        # Set limits
        manager.set_limits(PositionLimits(
            max_position_size=10000,
            max_leverage=5,
            max_positions=10
        ))

        # Open position
        position = await manager.open_position(
            symbol="SOL",
            side="long",
            size=1000,
            leverage=3
        )

        # Update prices
        manager.update_price("SOL", 110.0)

        # Check risk
        risk = manager.get_position_risk(position.id)

        # Close position
        await manager.close_position(position.id)
    """

    DEFAULT_LIMITS = PositionLimits(
        max_position_size=50000,
        max_leverage=10,
        max_positions=20,
        max_exposure_per_symbol=0.25,
        max_total_exposure=0.8,
        min_margin_ratio=0.05,
        max_loss_per_position=0.1,
        max_daily_loss=0.15
    )

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "position_manager.db"
        self.db = PositionManagerDB(db_path)

        self._positions: Dict[str, ManagedPosition] = {}
        self._prices: Dict[str, float] = {}
        self._limits = self.DEFAULT_LIMITS
        self._portfolio_value: float = 0
        self._lock = threading.Lock()
        self._execution_callback: Optional[Callable] = None
        self._alert_callback: Optional[Callable] = None

        self._load_positions()

    def _load_positions(self):
        """Load open positions from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM managed_positions WHERE is_open = 1")

            for row in cursor.fetchall():
                risk_data = json.loads(row['risk_json']) if row['risk_json'] else None
                risk = None
                if risk_data:
                    risk = PositionRisk(
                        risk_level=RiskLevel(risk_data['risk_level']),
                        health_factor=risk_data['health_factor'],
                        liquidation_price=risk_data['liquidation_price'],
                        margin_ratio=risk_data['margin_ratio'],
                        distance_to_liquidation_pct=risk_data['distance_to_liquidation_pct'],
                        unrealized_pnl=risk_data['unrealized_pnl'],
                        unrealized_pnl_pct=risk_data['unrealized_pnl_pct'],
                        max_loss_potential=risk_data['max_loss_potential'],
                        risk_score=risk_data['risk_score']
                    )

                position = ManagedPosition(
                    id=row['id'],
                    symbol=row['symbol'],
                    position_type=PositionType(row['position_type']),
                    side=row['side'],
                    size=row['size'],
                    entry_price=row['entry_price'],
                    current_price=row['current_price'],
                    leverage=row['leverage'],
                    margin=row['margin'],
                    notional_value=row['notional_value'],
                    unrealized_pnl=row['unrealized_pnl'],
                    unrealized_pnl_pct=row['unrealized_pnl_pct'],
                    realized_pnl=row['realized_pnl'],
                    fees_paid=row['fees_paid'],
                    funding_paid=row['funding_paid'],
                    opened_at=row['opened_at'],
                    updated_at=row['updated_at'],
                    stop_loss=row['stop_loss'],
                    take_profit=row['take_profit'],
                    trailing_stop_pct=row['trailing_stop_pct'],
                    trailing_stop_price=row['trailing_stop_price'],
                    max_loss=row['max_loss'],
                    risk=risk,
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )

                self._positions[position.id] = position

        logger.info(f"Loaded {len(self._positions)} open positions")

    def set_limits(self, limits: PositionLimits):
        """Set position limits."""
        self._limits = limits

    def set_portfolio_value(self, value: float):
        """Set current portfolio value."""
        self._portfolio_value = value

    def set_execution_callback(self, callback: Callable):
        """Set callback for executing trades."""
        self._execution_callback = callback

    def set_alert_callback(self, callback: Callable):
        """Set callback for risk alerts."""
        self._alert_callback = callback

    def update_price(self, symbol: str, price: float):
        """Update price for a symbol."""
        symbol = symbol.upper()
        self._prices[symbol] = price

        # Update all positions for this symbol
        with self._lock:
            for position in self._positions.values():
                if position.symbol == symbol:
                    self._update_position_metrics(position, price)

    def _update_position_metrics(self, position: ManagedPosition, price: float):
        """Update position metrics with new price."""
        position.current_price = price
        position.notional_value = position.size * price
        position.updated_at = datetime.now(timezone.utc).isoformat()

        # Calculate unrealized PnL
        if position.side == "long":
            position.unrealized_pnl = (price - position.entry_price) * position.size
        else:
            position.unrealized_pnl = (position.entry_price - price) * position.size

        entry_value = position.entry_price * position.size
        position.unrealized_pnl_pct = (position.unrealized_pnl / entry_value) * 100 if entry_value > 0 else 0

        # Update trailing stop
        if position.trailing_stop_pct:
            self._update_trailing_stop(position, price)

        # Update risk metrics
        position.risk = self._calculate_risk(position)

        # Check risk triggers
        self._check_risk_triggers(position)

        self._save_position(position)

    def _update_trailing_stop(self, position: ManagedPosition, price: float):
        """Update trailing stop price."""
        trail_pct = position.trailing_stop_pct / 100

        if position.side == "long":
            new_stop = price * (1 - trail_pct)
            if position.trailing_stop_price is None or new_stop > position.trailing_stop_price:
                position.trailing_stop_price = new_stop
        else:
            new_stop = price * (1 + trail_pct)
            if position.trailing_stop_price is None or new_stop < position.trailing_stop_price:
                position.trailing_stop_price = new_stop

    def _calculate_risk(self, position: ManagedPosition) -> PositionRisk:
        """Calculate position risk metrics."""
        # Liquidation price calculation
        if position.leverage > 1:
            maintenance_margin = 0.05  # 5%
            if position.side == "long":
                liq_price = position.entry_price * (1 - (1 / position.leverage) + maintenance_margin)
            else:
                liq_price = position.entry_price * (1 + (1 / position.leverage) - maintenance_margin)
        else:
            liq_price = 0  # Spot positions don't have liquidation

        # Distance to liquidation
        if liq_price > 0:
            distance = abs(position.current_price - liq_price) / position.current_price * 100
        else:
            distance = 100

        # Margin ratio
        margin_ratio = position.margin / position.notional_value if position.notional_value > 0 else 1

        # Health factor
        health_factor = margin_ratio / 0.05 if margin_ratio > 0 else 0  # 0.05 is min margin

        # Max loss potential
        if position.stop_loss:
            if position.side == "long":
                max_loss = (position.entry_price - position.stop_loss) * position.size
            else:
                max_loss = (position.stop_loss - position.entry_price) * position.size
        else:
            max_loss = position.margin  # Can lose all margin

        # Risk score (0-100)
        risk_score = 0
        if distance < 5:
            risk_score += 50
        elif distance < 10:
            risk_score += 30
        elif distance < 20:
            risk_score += 15

        if health_factor < 1.2:
            risk_score += 30
        elif health_factor < 1.5:
            risk_score += 15

        if position.leverage > 5:
            risk_score += 20
        elif position.leverage > 3:
            risk_score += 10

        # Determine risk level
        if health_factor < 1.0 or distance < 3:
            risk_level = RiskLevel.LIQUIDATION
        elif health_factor < 1.2 or distance < 5:
            risk_level = RiskLevel.CRITICAL
        elif health_factor < 1.5 or distance < 10:
            risk_level = RiskLevel.HIGH
        elif health_factor < 2.0 or distance < 20:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.SAFE

        return PositionRisk(
            risk_level=risk_level,
            health_factor=health_factor,
            liquidation_price=liq_price,
            margin_ratio=margin_ratio,
            distance_to_liquidation_pct=distance,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            max_loss_potential=max_loss,
            risk_score=min(100, risk_score)
        )

    def _check_risk_triggers(self, position: ManagedPosition):
        """Check and handle risk triggers."""
        if not position.risk:
            return

        # Check stop loss
        if position.stop_loss:
            triggered = (position.side == "long" and position.current_price <= position.stop_loss) or \
                       (position.side == "short" and position.current_price >= position.stop_loss)
            if triggered:
                logger.warning(f"Stop loss triggered for position {position.id}")
                import asyncio
                asyncio.create_task(self.close_position(position.id, reason="Stop loss triggered"))
                return

        # Check trailing stop
        if position.trailing_stop_price:
            triggered = (position.side == "long" and position.current_price <= position.trailing_stop_price) or \
                       (position.side == "short" and position.current_price >= position.trailing_stop_price)
            if triggered:
                logger.warning(f"Trailing stop triggered for position {position.id}")
                import asyncio
                asyncio.create_task(self.close_position(position.id, reason="Trailing stop triggered"))
                return

        # Check take profit
        if position.take_profit:
            triggered = (position.side == "long" and position.current_price >= position.take_profit) or \
                       (position.side == "short" and position.current_price <= position.take_profit)
            if triggered:
                logger.info(f"Take profit triggered for position {position.id}")
                import asyncio
                asyncio.create_task(self.close_position(position.id, reason="Take profit triggered"))
                return

        # Check max loss
        if position.max_loss and position.unrealized_pnl < -position.max_loss:
            logger.warning(f"Max loss exceeded for position {position.id}")
            import asyncio
            asyncio.create_task(self.close_position(position.id, reason="Max loss exceeded"))
            return

        # Alert on high risk
        if position.risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            if self._alert_callback:
                self._alert_callback(position, position.risk)

    async def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        leverage: float = 1,
        position_type: PositionType = PositionType.SPOT,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        max_loss: Optional[float] = None,
        entry_price: Optional[float] = None
    ) -> Optional[ManagedPosition]:
        """Open a new position."""
        symbol = symbol.upper()

        # Validate against limits
        validation = self._validate_new_position(symbol, size, leverage)
        if not validation['valid']:
            logger.error(f"Position validation failed: {validation['reason']}")
            return None

        # Get entry price
        price = entry_price or self._prices.get(symbol, 0)
        if price <= 0:
            logger.error(f"No price available for {symbol}")
            return None

        position_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        margin = size / leverage
        notional = size

        position = ManagedPosition(
            id=position_id,
            symbol=symbol,
            position_type=position_type,
            side=side,
            size=size / price,  # Convert to token amount
            entry_price=price,
            current_price=price,
            leverage=leverage,
            margin=margin,
            notional_value=notional,
            unrealized_pnl=0,
            unrealized_pnl_pct=0,
            realized_pnl=0,
            fees_paid=0,
            funding_paid=0,
            opened_at=now,
            updated_at=now,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=trailing_stop_pct,
            max_loss=max_loss or (margin * self._limits.max_loss_per_position)
        )

        position.risk = self._calculate_risk(position)

        # Execute if callback is set
        if self._execution_callback:
            result = await self._execution_callback(
                symbol=symbol,
                side=side,
                size=size,
                leverage=leverage
            )
            if not result.get('success'):
                logger.error(f"Failed to open position: {result.get('error')}")
                return None

        with self._lock:
            self._positions[position_id] = position

        self._save_position(position)
        self._record_event(position_id, PositionAction.OPEN, price, size / price, 0, 0, "Position opened")

        logger.info(f"Opened {side} {symbol} position {position_id}: ${size:.2f} @ {leverage}x")

        return position

    def _validate_new_position(
        self,
        symbol: str,
        size: float,
        leverage: float
    ) -> Dict[str, Any]:
        """Validate new position against limits."""
        # Check max position size
        if size > self._limits.max_position_size:
            return {'valid': False, 'reason': f'Size ${size} exceeds max ${self._limits.max_position_size}'}

        # Check max leverage
        if leverage > self._limits.max_leverage:
            return {'valid': False, 'reason': f'Leverage {leverage}x exceeds max {self._limits.max_leverage}x'}

        # Check max positions
        if len(self._positions) >= self._limits.max_positions:
            return {'valid': False, 'reason': f'Max positions ({self._limits.max_positions}) reached'}

        # Check exposure per symbol
        symbol_exposure = sum(
            p.notional_value for p in self._positions.values()
            if p.symbol == symbol
        ) + size

        if self._portfolio_value > 0:
            exposure_pct = symbol_exposure / self._portfolio_value
            if exposure_pct > self._limits.max_exposure_per_symbol:
                return {'valid': False, 'reason': f'Symbol exposure {exposure_pct:.0%} exceeds max'}

        # Check total exposure
        total_exposure = sum(p.notional_value for p in self._positions.values()) + size
        if self._portfolio_value > 0:
            total_pct = total_exposure / self._portfolio_value
            if total_pct > self._limits.max_total_exposure:
                return {'valid': False, 'reason': f'Total exposure {total_pct:.0%} exceeds max'}

        return {'valid': True, 'reason': ''}

    async def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = ""
    ) -> Optional[ManagedPosition]:
        """Close a position."""
        with self._lock:
            position = self._positions.get(position_id)

        if not position:
            logger.error(f"Position {position_id} not found")
            return None

        price = exit_price or self._prices.get(position.symbol, position.current_price)

        # Calculate final PnL
        if position.side == "long":
            pnl = (price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - price) * position.size

        position.realized_pnl = pnl
        position.unrealized_pnl = 0
        position.current_price = price

        # Execute if callback is set
        if self._execution_callback:
            result = await self._execution_callback(
                symbol=position.symbol,
                side="sell" if position.side == "long" else "buy",
                size=position.size * price,
                close=True
            )
            if not result.get('success'):
                logger.error(f"Failed to close position: {result.get('error')}")
                # Still mark as closed in system

        # Remove from active positions
        with self._lock:
            del self._positions[position_id]

        # Update in database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE managed_positions
                SET is_open = 0, realized_pnl = ?, current_price = ?,
                    updated_at = ?
                WHERE id = ?
            """, (pnl, price, datetime.now(timezone.utc).isoformat(), position_id))
            conn.commit()

        # Record event
        action = PositionAction.STOP_LOSS if "stop" in reason.lower() else \
                 PositionAction.TAKE_PROFIT if "profit" in reason.lower() else \
                 PositionAction.CLOSE

        self._record_event(position_id, action, price, position.size, pnl, 0, reason)

        logger.info(f"Closed position {position_id}: PnL = ${pnl:.2f} ({reason})")

        return position

    def _save_position(self, position: ManagedPosition):
        """Save position to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            risk_json = None
            if position.risk:
                risk_json = json.dumps({
                    'risk_level': position.risk.risk_level.value,
                    'health_factor': position.risk.health_factor,
                    'liquidation_price': position.risk.liquidation_price,
                    'margin_ratio': position.risk.margin_ratio,
                    'distance_to_liquidation_pct': position.risk.distance_to_liquidation_pct,
                    'unrealized_pnl': position.risk.unrealized_pnl,
                    'unrealized_pnl_pct': position.risk.unrealized_pnl_pct,
                    'max_loss_potential': position.risk.max_loss_potential,
                    'risk_score': position.risk.risk_score
                })

            cursor.execute("""
                INSERT OR REPLACE INTO managed_positions
                (id, symbol, position_type, side, size, entry_price, current_price,
                 leverage, margin, notional_value, unrealized_pnl, unrealized_pnl_pct,
                 realized_pnl, fees_paid, funding_paid, opened_at, updated_at,
                 stop_loss, take_profit, trailing_stop_pct, trailing_stop_price,
                 max_loss, risk_json, metadata_json, is_open)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                position.id, position.symbol, position.position_type.value,
                position.side, position.size, position.entry_price, position.current_price,
                position.leverage, position.margin, position.notional_value,
                position.unrealized_pnl, position.unrealized_pnl_pct, position.realized_pnl,
                position.fees_paid, position.funding_paid, position.opened_at, position.updated_at,
                position.stop_loss, position.take_profit, position.trailing_stop_pct,
                position.trailing_stop_price, position.max_loss, risk_json,
                json.dumps(position.metadata)
            ))
            conn.commit()

    def _record_event(
        self,
        position_id: str,
        action: PositionAction,
        price: float,
        size: float,
        pnl: float,
        fee: float,
        reason: str
    ):
        """Record position event."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO position_events
                (position_id, action, price, size, pnl, fee, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id, action.value, price, size, pnl, fee,
                datetime.now(timezone.utc).isoformat(), reason
            ))
            conn.commit()

    def get_position(self, position_id: str) -> Optional[ManagedPosition]:
        """Get position by ID."""
        return self._positions.get(position_id)

    def get_open_positions(self, symbol: Optional[str] = None) -> List[ManagedPosition]:
        """Get all open positions."""
        positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p.symbol == symbol.upper()]
        return positions

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        positions = list(self._positions.values())

        total_margin = sum(p.margin for p in positions)
        total_notional = sum(p.notional_value for p in positions)
        total_unrealized = sum(p.unrealized_pnl for p in positions)

        by_symbol = {}
        for p in positions:
            if p.symbol not in by_symbol:
                by_symbol[p.symbol] = {'long': 0, 'short': 0, 'pnl': 0}
            by_symbol[p.symbol][p.side] += p.notional_value
            by_symbol[p.symbol]['pnl'] += p.unrealized_pnl

        risk_positions = [p for p in positions if p.risk and p.risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]

        return {
            'position_count': len(positions),
            'total_margin': total_margin,
            'total_notional': total_notional,
            'total_unrealized_pnl': total_unrealized,
            'by_symbol': by_symbol,
            'high_risk_count': len(risk_positions),
            'portfolio_value': self._portfolio_value
        }


# Singleton
_manager: Optional[PositionManager] = None


def get_position_manager() -> PositionManager:
    """Get singleton position manager."""
    global _manager
    if _manager is None:
        _manager = PositionManager()
    return _manager
