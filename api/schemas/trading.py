"""Trading-related Pydantic schemas."""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from enum import Enum
from datetime import datetime


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CreateOrderRequest(BaseModel):
    """Request schema for creating an order."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy/sell)")
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    amount: float = Field(..., gt=0, le=1000000, description="Order amount")
    price: Optional[float] = Field(None, gt=0, description="Limit price (required for limit orders)")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price (required for stop orders)")
    reduce_only: bool = Field(default=False, description="Reduce position only")
    post_only: bool = Field(default=False, description="Post only (maker)")
    client_order_id: Optional[str] = Field(None, max_length=64, description="Client order ID")
    
    @validator('price')
    def price_required_for_limit(cls, v, values):
        order_type = values.get('order_type')
        if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and v is None:
            raise ValueError('Price is required for limit orders')
        return v
    
    @validator('stop_price')
    def stop_price_required_for_stop(cls, v, values):
        order_type = values.get('order_type')
        if order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and v is None:
            raise ValueError('Stop price is required for stop orders')
        return v
    
    @validator('symbol')
    def symbol_uppercase(cls, v):
        return v.upper()
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "SOL/USDC",
                "side": "buy",
                "order_type": "market",
                "amount": 10.0
            }
        }


class OrderResponse(BaseModel):
    """Response schema for an order."""
    order_id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    amount: float
    filled_amount: float = 0
    remaining_amount: float = 0
    price: Optional[float] = None
    average_price: Optional[float] = None
    stop_price: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CancelOrderRequest(BaseModel):
    """Request schema for cancelling an order."""
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    
    @validator('order_id')
    def at_least_one_id(cls, v, values):
        if not v and not values.get('client_order_id'):
            raise ValueError('Either order_id or client_order_id must be provided')
        return v


class PositionResponse(BaseModel):
    """Response schema for a position."""
    symbol: str
    side: OrderSide
    size: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float] = None
    unrealized_pnl: float
    realized_pnl: float = 0
    leverage: float = 1
    margin: float = 0
    margin_ratio: Optional[float] = None
    
    class Config:
        from_attributes = True


class TradeResponse(BaseModel):
    """Response schema for a trade."""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    amount: float
    price: float
    fee: float = 0
    fee_currency: str = "USDC"
    realized_pnl: Optional[float] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    """Request schema for running a backtest."""
    symbol: str = Field(..., min_length=1, max_length=20)
    interval: str = Field(..., pattern=r'^[0-9]+[mhd]$')
    strategy: str = Field(default="sma_cross")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: float = Field(default=10000, gt=0)
    params: dict = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC",
                "interval": "1h",
                "strategy": "sma_cross",
                "params": {"fast": 5, "slow": 20}
            }
        }


class BacktestResponse(BaseModel):
    """Response schema for backtest results."""
    symbol: str
    interval: str
    strategy: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    net_pnl: float
    gross_profit: float
    gross_loss: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    start_date: datetime
    end_date: datetime
    duration_days: int
