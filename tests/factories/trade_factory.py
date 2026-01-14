"""
Trade Factory

Factory classes for generating trading-related test data.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from decimal import Decimal

from .base import BaseFactory, RandomData, SequenceGenerator


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Order:
    """Order model for testing."""
    id: str
    user_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: OrderStatus
    filled_quantity: float
    average_price: Optional[float]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderFactory(BaseFactory[Order]):
    """Factory for creating Order test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: OrderSide = OrderSide.BUY,
        order_type: OrderType = OrderType.MARKET,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        status: OrderStatus = OrderStatus.PENDING,
        filled_quantity: float = 0.0,
        average_price: Optional[float] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Order:
        """Build an Order instance."""
        now = datetime.utcnow()

        return Order(
            id=id or RandomData.uuid(),
            user_id=user_id or RandomData.uuid(),
            symbol=symbol or RandomData.symbol(),
            side=side,
            order_type=order_type,
            quantity=quantity or RandomData.decimal(0.1, 100.0),
            price=price,
            status=status,
            filled_quantity=filled_quantity,
            average_price=average_price,
            created_at=created_at or now,
            updated_at=updated_at or now,
            metadata=metadata or {},
        )


class BuyOrderFactory(OrderFactory):
    """Factory for buy orders."""

    @classmethod
    def _build(cls, **kwargs) -> Order:
        kwargs.setdefault('side', OrderSide.BUY)
        return super()._build(**kwargs)


class SellOrderFactory(OrderFactory):
    """Factory for sell orders."""

    @classmethod
    def _build(cls, **kwargs) -> Order:
        kwargs.setdefault('side', OrderSide.SELL)
        return super()._build(**kwargs)


class FilledOrderFactory(OrderFactory):
    """Factory for filled orders."""

    @classmethod
    def _build(cls, **kwargs) -> Order:
        kwargs.setdefault('status', OrderStatus.FILLED)
        quantity = kwargs.get('quantity', RandomData.decimal(0.1, 100.0))
        kwargs.setdefault('filled_quantity', quantity)
        kwargs.setdefault('average_price', RandomData.decimal(10.0, 500.0))
        return super()._build(**kwargs)


@dataclass
class Trade:
    """Trade model for testing."""
    id: str
    order_id: str
    user_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fee: float
    fee_currency: str
    executed_at: datetime
    transaction_hash: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class TradeFactory(BaseFactory[Trade]):
    """Factory for creating Trade test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        order_id: Optional[str] = None,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: OrderSide = OrderSide.BUY,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        fee: Optional[float] = None,
        fee_currency: str = "SOL",
        executed_at: Optional[datetime] = None,
        transaction_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Trade:
        """Build a Trade instance."""
        qty = quantity or RandomData.decimal(0.1, 100.0)
        prc = price or RandomData.decimal(10.0, 500.0)

        return Trade(
            id=id or RandomData.uuid(),
            order_id=order_id or RandomData.uuid(),
            user_id=user_id or RandomData.uuid(),
            symbol=symbol or RandomData.symbol(),
            side=side,
            quantity=qty,
            price=prc,
            fee=fee or round(qty * prc * 0.001, 6),  # 0.1% fee
            fee_currency=fee_currency,
            executed_at=executed_at or datetime.utcnow(),
            transaction_hash=transaction_hash,
            metadata=metadata or {},
        )


@dataclass
class TradingSignal:
    """Trading signal model for testing."""
    id: str
    symbol: str
    action: str
    confidence: float
    reasoning: str
    source: str
    created_at: datetime
    expires_at: Optional[datetime]


class TradingSignalFactory(BaseFactory[TradingSignal]):
    """Factory for creating trading signal test instances."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        symbol: Optional[str] = None,
        action: Optional[str] = None,
        confidence: Optional[float] = None,
        reasoning: Optional[str] = None,
        source: str = "test",
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        **kwargs
    ) -> TradingSignal:
        """Build a TradingSignal instance."""
        return TradingSignal(
            id=id or RandomData.uuid(),
            symbol=symbol or RandomData.symbol(),
            action=action or RandomData.choice(["buy", "sell", "hold"]),
            confidence=confidence or RandomData.decimal(0.5, 1.0),
            reasoning=reasoning or "Test signal reasoning",
            source=source,
            created_at=created_at or datetime.utcnow(),
            expires_at=expires_at,
        )


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot for testing."""
    id: str
    user_id: str
    total_value_usd: float
    positions: List[Dict[str, Any]]
    created_at: datetime


class PortfolioSnapshotFactory(BaseFactory[PortfolioSnapshot]):
    """Factory for portfolio snapshots."""

    @classmethod
    def _build(
        cls,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        total_value_usd: Optional[float] = None,
        positions: Optional[List[Dict[str, Any]]] = None,
        created_at: Optional[datetime] = None,
        **kwargs
    ) -> PortfolioSnapshot:
        """Build a PortfolioSnapshot instance."""
        default_positions = [
            {"symbol": "SOL", "quantity": 10.0, "value_usd": 1500.0},
            {"symbol": "USDC", "quantity": 500.0, "value_usd": 500.0},
        ]

        pos = positions or default_positions
        total = total_value_usd or sum(p["value_usd"] for p in pos)

        return PortfolioSnapshot(
            id=id or RandomData.uuid(),
            user_id=user_id or RandomData.uuid(),
            total_value_usd=total,
            positions=pos,
            created_at=created_at or datetime.utcnow(),
        )
