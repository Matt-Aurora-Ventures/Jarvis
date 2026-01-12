"""
Liquidation Monitor - Real-time position liquidation risk monitoring.
Tracks margin health, calculates liquidation prices, and sends alerts.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable


class RiskLevel(Enum):
    """Position risk levels."""
    SAFE = "safe"                    # > 50% margin
    LOW = "low"                      # 30-50% margin
    MEDIUM = "medium"                # 20-30% margin
    HIGH = "high"                    # 10-20% margin
    CRITICAL = "critical"            # 5-10% margin
    LIQUIDATION_IMMINENT = "imminent"  # < 5% margin


class PositionType(Enum):
    """Position types."""
    SPOT_MARGIN = "spot_margin"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    OPTIONS = "options"


class AlertAction(Enum):
    """Actions to take on alert."""
    NOTIFY = "notify"                # Just send notification
    ADD_MARGIN = "add_margin"        # Auto-add margin
    REDUCE_POSITION = "reduce"       # Reduce position size
    CLOSE_POSITION = "close"         # Close entire position
    HEDGE = "hedge"                  # Open hedge position


@dataclass
class LeveragedPosition:
    """A leveraged position being monitored."""
    position_id: str
    symbol: str
    position_type: PositionType
    side: str                        # "long" or "short"
    size: float                      # Position size in base currency
    entry_price: float
    current_price: float
    leverage: float
    margin: float                    # Collateral amount
    maintenance_margin_rate: float   # e.g., 0.05 for 5%
    liquidation_price: float
    unrealized_pnl: float
    margin_ratio: float              # Current margin / Maintenance margin
    risk_level: RiskLevel
    exchange: str
    created_at: datetime
    updated_at: datetime
    auto_actions: List[AlertAction] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class LiquidationAlert:
    """Alert for liquidation risk."""
    alert_id: str
    position_id: str
    symbol: str
    risk_level: RiskLevel
    margin_ratio: float
    liquidation_price: float
    current_price: float
    distance_to_liquidation: float   # Percentage
    message: str
    triggered_at: datetime
    acknowledged: bool = False
    actions_taken: List[str] = field(default_factory=list)


@dataclass
class MarginCall:
    """Margin call event."""
    call_id: str
    position_id: str
    symbol: str
    required_margin: float
    current_margin: float
    shortfall: float
    deadline: Optional[datetime]
    auto_liquidation: bool
    created_at: datetime
    resolved: bool = False
    resolution: Optional[str] = None


class LiquidationMonitor:
    """
    Real-time liquidation risk monitor.
    Tracks leveraged positions and alerts on liquidation risk.
    """

    # Risk level thresholds (margin ratio)
    RISK_THRESHOLDS = {
        RiskLevel.SAFE: 5.0,           # > 500% of maintenance
        RiskLevel.LOW: 3.0,            # 300-500%
        RiskLevel.MEDIUM: 2.0,         # 200-300%
        RiskLevel.HIGH: 1.5,           # 150-200%
        RiskLevel.CRITICAL: 1.2,       # 120-150%
        RiskLevel.LIQUIDATION_IMMINENT: 1.0  # < 120%
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "liquidation_monitor.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.positions: Dict[str, LeveragedPosition] = {}
        self.alert_callbacks: List[Callable] = []
        self.margin_call_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Auto-action handlers
        self.action_handlers: Dict[AlertAction, Callable] = {}

        self._load_positions()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    leverage REAL NOT NULL,
                    margin REAL NOT NULL,
                    maintenance_margin_rate REAL NOT NULL,
                    liquidation_price REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    margin_ratio REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    auto_actions TEXT,
                    metadata TEXT,
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    margin_ratio REAL NOT NULL,
                    liquidation_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    distance_to_liquidation REAL NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    acknowledged INTEGER DEFAULT 0,
                    actions_taken TEXT,
                    FOREIGN KEY (position_id) REFERENCES positions(position_id)
                );

                CREATE TABLE IF NOT EXISTS margin_calls (
                    call_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    required_margin REAL NOT NULL,
                    current_margin REAL NOT NULL,
                    shortfall REAL NOT NULL,
                    deadline TEXT,
                    auto_liquidation INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0,
                    resolution TEXT,
                    FOREIGN KEY (position_id) REFERENCES positions(position_id)
                );

                CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
                CREATE INDEX IF NOT EXISTS idx_positions_risk ON positions(risk_level);
                CREATE INDEX IF NOT EXISTS idx_alerts_position ON alerts(position_id);
                CREATE INDEX IF NOT EXISTS idx_margin_calls_position ON margin_calls(position_id);
            """)

    def _load_positions(self):
        """Load active positions from database."""
        import json
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE active = 1"
            ).fetchall()

            for row in rows:
                position = LeveragedPosition(
                    position_id=row["position_id"],
                    symbol=row["symbol"],
                    position_type=PositionType(row["position_type"]),
                    side=row["side"],
                    size=row["size"],
                    entry_price=row["entry_price"],
                    current_price=row["current_price"],
                    leverage=row["leverage"],
                    margin=row["margin"],
                    maintenance_margin_rate=row["maintenance_margin_rate"],
                    liquidation_price=row["liquidation_price"],
                    unrealized_pnl=row["unrealized_pnl"],
                    margin_ratio=row["margin_ratio"],
                    risk_level=RiskLevel(row["risk_level"]),
                    exchange=row["exchange"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    auto_actions=[AlertAction(a) for a in json.loads(row["auto_actions"] or "[]")],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                self.positions[position.position_id] = position

    def add_position(
        self,
        position_id: str,
        symbol: str,
        position_type: PositionType,
        side: str,
        size: float,
        entry_price: float,
        leverage: float,
        margin: float,
        maintenance_margin_rate: float = 0.05,
        exchange: str = "unknown",
        auto_actions: Optional[List[AlertAction]] = None,
        metadata: Optional[Dict] = None
    ) -> LeveragedPosition:
        """Add a position to monitor."""
        import json
        import uuid

        # Calculate liquidation price
        liquidation_price = self._calculate_liquidation_price(
            side, entry_price, leverage, maintenance_margin_rate
        )

        # Calculate unrealized PnL (starts at 0)
        unrealized_pnl = 0.0

        # Calculate margin ratio
        position_value = size * entry_price
        maintenance_margin = position_value * maintenance_margin_rate
        margin_ratio = margin / maintenance_margin if maintenance_margin > 0 else float('inf')

        # Determine risk level
        risk_level = self._get_risk_level(margin_ratio)

        now = datetime.now()
        position = LeveragedPosition(
            position_id=position_id or str(uuid.uuid4())[:8],
            symbol=symbol,
            position_type=position_type,
            side=side,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
            leverage=leverage,
            margin=margin,
            maintenance_margin_rate=maintenance_margin_rate,
            liquidation_price=liquidation_price,
            unrealized_pnl=unrealized_pnl,
            margin_ratio=margin_ratio,
            risk_level=risk_level,
            exchange=exchange,
            created_at=now,
            updated_at=now,
            auto_actions=auto_actions or [],
            metadata=metadata or {}
        )

        with self._lock:
            self.positions[position.position_id] = position

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO positions
                (position_id, symbol, position_type, side, size, entry_price,
                 current_price, leverage, margin, maintenance_margin_rate,
                 liquidation_price, unrealized_pnl, margin_ratio, risk_level,
                 exchange, created_at, updated_at, auto_actions, metadata, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                position.position_id, position.symbol, position.position_type.value,
                position.side, position.size, position.entry_price,
                position.current_price, position.leverage, position.margin,
                position.maintenance_margin_rate, position.liquidation_price,
                position.unrealized_pnl, position.margin_ratio, position.risk_level.value,
                position.exchange, position.created_at.isoformat(),
                position.updated_at.isoformat(),
                json.dumps([a.value for a in position.auto_actions]),
                json.dumps(position.metadata)
            ))

        return position

    def _calculate_liquidation_price(
        self,
        side: str,
        entry_price: float,
        leverage: float,
        maintenance_margin_rate: float
    ) -> float:
        """Calculate liquidation price for a position."""
        if side == "long":
            # Long liquidation: price drops
            liquidation_price = entry_price * (1 - (1 / leverage) + maintenance_margin_rate)
        else:
            # Short liquidation: price rises
            liquidation_price = entry_price * (1 + (1 / leverage) - maintenance_margin_rate)

        return max(0, liquidation_price)

    def _get_risk_level(self, margin_ratio: float) -> RiskLevel:
        """Determine risk level from margin ratio."""
        if margin_ratio >= self.RISK_THRESHOLDS[RiskLevel.SAFE]:
            return RiskLevel.SAFE
        elif margin_ratio >= self.RISK_THRESHOLDS[RiskLevel.LOW]:
            return RiskLevel.LOW
        elif margin_ratio >= self.RISK_THRESHOLDS[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        elif margin_ratio >= self.RISK_THRESHOLDS[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif margin_ratio >= self.RISK_THRESHOLDS[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        else:
            return RiskLevel.LIQUIDATION_IMMINENT

    def update_price(self, symbol: str, current_price: float) -> List[LiquidationAlert]:
        """Update price for all positions of a symbol."""
        import json
        import uuid

        alerts = []
        now = datetime.now()

        with self._lock:
            for position in self.positions.values():
                if position.symbol != symbol:
                    continue

                old_risk_level = position.risk_level

                # Update current price
                position.current_price = current_price
                position.updated_at = now

                # Recalculate unrealized PnL
                if position.side == "long":
                    position.unrealized_pnl = (current_price - position.entry_price) * position.size
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.size

                # Recalculate margin ratio
                position_value = position.size * current_price
                effective_margin = position.margin + position.unrealized_pnl
                maintenance_margin = position_value * position.maintenance_margin_rate
                position.margin_ratio = effective_margin / maintenance_margin if maintenance_margin > 0 else float('inf')

                # Update risk level
                position.risk_level = self._get_risk_level(position.margin_ratio)

                # Calculate distance to liquidation
                if position.side == "long":
                    distance = (current_price - position.liquidation_price) / current_price * 100
                else:
                    distance = (position.liquidation_price - current_price) / current_price * 100

                # Check if risk level increased (worsened)
                risk_order = list(RiskLevel)
                if risk_order.index(position.risk_level) > risk_order.index(old_risk_level):
                    # Create alert
                    alert = LiquidationAlert(
                        alert_id=str(uuid.uuid4())[:8],
                        position_id=position.position_id,
                        symbol=symbol,
                        risk_level=position.risk_level,
                        margin_ratio=position.margin_ratio,
                        liquidation_price=position.liquidation_price,
                        current_price=current_price,
                        distance_to_liquidation=distance,
                        message=self._generate_alert_message(position, distance),
                        triggered_at=now
                    )
                    alerts.append(alert)

                    # Save alert to database
                    with self._get_db() as conn:
                        conn.execute("""
                            INSERT INTO alerts
                            (alert_id, position_id, symbol, risk_level, margin_ratio,
                             liquidation_price, current_price, distance_to_liquidation,
                             message, triggered_at, acknowledged, actions_taken)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '[]')
                        """, (
                            alert.alert_id, alert.position_id, alert.symbol,
                            alert.risk_level.value, alert.margin_ratio,
                            alert.liquidation_price, alert.current_price,
                            alert.distance_to_liquidation, alert.message,
                            alert.triggered_at.isoformat()
                        ))

                    # Trigger callbacks
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert)
                        except Exception:
                            pass

                    # Execute auto-actions
                    self._execute_auto_actions(position, alert)

                # Update position in database
                with self._get_db() as conn:
                    conn.execute("""
                        UPDATE positions SET
                        current_price = ?, unrealized_pnl = ?, margin_ratio = ?,
                        risk_level = ?, updated_at = ?
                        WHERE position_id = ?
                    """, (
                        position.current_price, position.unrealized_pnl,
                        position.margin_ratio, position.risk_level.value,
                        position.updated_at.isoformat(), position.position_id
                    ))

        return alerts

    def _generate_alert_message(self, position: LeveragedPosition, distance: float) -> str:
        """Generate human-readable alert message."""
        messages = {
            RiskLevel.LOW: f"{position.symbol} position at LOW risk - {distance:.1f}% from liquidation",
            RiskLevel.MEDIUM: f"{position.symbol} position at MEDIUM risk - {distance:.1f}% from liquidation",
            RiskLevel.HIGH: f"WARNING: {position.symbol} at HIGH risk - only {distance:.1f}% from liquidation!",
            RiskLevel.CRITICAL: f"CRITICAL: {position.symbol} near liquidation - {distance:.1f}% remaining!",
            RiskLevel.LIQUIDATION_IMMINENT: f"DANGER: {position.symbol} LIQUIDATION IMMINENT - {distance:.1f}%!"
        }
        return messages.get(position.risk_level, f"{position.symbol} risk level: {position.risk_level.value}")

    def _execute_auto_actions(self, position: LeveragedPosition, alert: LiquidationAlert):
        """Execute automatic actions based on position config."""
        for action in position.auto_actions:
            if action in self.action_handlers:
                try:
                    self.action_handlers[action](position, alert)
                    alert.actions_taken.append(action.value)
                except Exception:
                    pass

    def add_margin(self, position_id: str, amount: float) -> bool:
        """Add margin to a position."""
        with self._lock:
            if position_id not in self.positions:
                return False

            position = self.positions[position_id]
            position.margin += amount
            position.updated_at = datetime.now()

            # Recalculate margin ratio
            position_value = position.size * position.current_price
            effective_margin = position.margin + position.unrealized_pnl
            maintenance_margin = position_value * position.maintenance_margin_rate
            position.margin_ratio = effective_margin / maintenance_margin if maintenance_margin > 0 else float('inf')
            position.risk_level = self._get_risk_level(position.margin_ratio)

            # Update database
            with self._get_db() as conn:
                conn.execute("""
                    UPDATE positions SET
                    margin = ?, margin_ratio = ?, risk_level = ?, updated_at = ?
                    WHERE position_id = ?
                """, (
                    position.margin, position.margin_ratio,
                    position.risk_level.value, position.updated_at.isoformat(),
                    position_id
                ))

            return True

    def close_position(self, position_id: str) -> Optional[LeveragedPosition]:
        """Close and remove a position from monitoring."""
        with self._lock:
            if position_id not in self.positions:
                return None

            position = self.positions.pop(position_id)

            with self._get_db() as conn:
                conn.execute(
                    "UPDATE positions SET active = 0 WHERE position_id = ?",
                    (position_id,)
                )

            return position

    def get_position(self, position_id: str) -> Optional[LeveragedPosition]:
        """Get a specific position."""
        return self.positions.get(position_id)

    def get_positions_by_risk(self, min_risk: RiskLevel = RiskLevel.MEDIUM) -> List[LeveragedPosition]:
        """Get positions at or above a certain risk level."""
        risk_order = list(RiskLevel)
        min_index = risk_order.index(min_risk)

        return [
            p for p in self.positions.values()
            if risk_order.index(p.risk_level) >= min_index
        ]

    def get_total_risk_exposure(self) -> Dict:
        """Get summary of total risk exposure."""
        total_value = 0.0
        total_pnl = 0.0
        by_risk = {level: [] for level in RiskLevel}

        for position in self.positions.values():
            position_value = position.size * position.current_price
            total_value += position_value
            total_pnl += position.unrealized_pnl
            by_risk[position.risk_level].append(position)

        return {
            "total_positions": len(self.positions),
            "total_value": total_value,
            "total_unrealized_pnl": total_pnl,
            "by_risk_level": {
                level.value: len(positions)
                for level, positions in by_risk.items()
            },
            "high_risk_positions": len(by_risk[RiskLevel.HIGH]) +
                                   len(by_risk[RiskLevel.CRITICAL]) +
                                   len(by_risk[RiskLevel.LIQUIDATION_IMMINENT])
        }

    def create_margin_call(
        self,
        position_id: str,
        required_margin: float,
        deadline: Optional[datetime] = None,
        auto_liquidation: bool = True
    ) -> Optional[MarginCall]:
        """Create a margin call for a position."""
        import uuid

        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        shortfall = required_margin - position.margin

        if shortfall <= 0:
            return None

        margin_call = MarginCall(
            call_id=str(uuid.uuid4())[:8],
            position_id=position_id,
            symbol=position.symbol,
            required_margin=required_margin,
            current_margin=position.margin,
            shortfall=shortfall,
            deadline=deadline,
            auto_liquidation=auto_liquidation,
            created_at=datetime.now()
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO margin_calls
                (call_id, position_id, symbol, required_margin, current_margin,
                 shortfall, deadline, auto_liquidation, created_at, resolved, resolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """, (
                margin_call.call_id, margin_call.position_id, margin_call.symbol,
                margin_call.required_margin, margin_call.current_margin,
                margin_call.shortfall, margin_call.deadline.isoformat() if margin_call.deadline else None,
                1 if margin_call.auto_liquidation else 0,
                margin_call.created_at.isoformat()
            ))

        # Trigger callbacks
        for callback in self.margin_call_callbacks:
            try:
                callback(margin_call)
            except Exception:
                pass

        return margin_call

    def register_alert_callback(self, callback: Callable[[LiquidationAlert], None]):
        """Register callback for liquidation alerts."""
        self.alert_callbacks.append(callback)

    def register_margin_call_callback(self, callback: Callable[[MarginCall], None]):
        """Register callback for margin calls."""
        self.margin_call_callbacks.append(callback)

    def register_action_handler(self, action: AlertAction, handler: Callable):
        """Register handler for auto-actions."""
        self.action_handlers[action] = handler

    async def start_monitoring(self, interval: float = 1.0):
        """Start continuous monitoring loop."""
        self._monitoring = True

        while self._monitoring:
            # In a real implementation, this would fetch prices
            # For now, it just checks existing data
            await asyncio.sleep(interval)

    def stop_monitoring(self):
        """Stop monitoring loop."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()

    def get_alerts(
        self,
        position_id: Optional[str] = None,
        unacknowledged_only: bool = False,
        limit: int = 100
    ) -> List[LiquidationAlert]:
        """Get historical alerts."""
        import json

        with self._get_db() as conn:
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []

            if position_id:
                query += " AND position_id = ?"
                params.append(position_id)

            if unacknowledged_only:
                query += " AND acknowledged = 0"

            query += " ORDER BY triggered_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

            return [
                LiquidationAlert(
                    alert_id=row["alert_id"],
                    position_id=row["position_id"],
                    symbol=row["symbol"],
                    risk_level=RiskLevel(row["risk_level"]),
                    margin_ratio=row["margin_ratio"],
                    liquidation_price=row["liquidation_price"],
                    current_price=row["current_price"],
                    distance_to_liquidation=row["distance_to_liquidation"],
                    message=row["message"],
                    triggered_at=datetime.fromisoformat(row["triggered_at"]),
                    acknowledged=bool(row["acknowledged"]),
                    actions_taken=json.loads(row["actions_taken"] or "[]")
                )
                for row in rows
            ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?",
                (alert_id,)
            )
            return cursor.rowcount > 0


# Singleton instance
_liquidation_monitor: Optional[LiquidationMonitor] = None


def get_liquidation_monitor() -> LiquidationMonitor:
    """Get or create the liquidation monitor singleton."""
    global _liquidation_monitor
    if _liquidation_monitor is None:
        _liquidation_monitor = LiquidationMonitor()
    return _liquidation_monitor
