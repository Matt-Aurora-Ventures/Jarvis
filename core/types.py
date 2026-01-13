"""Type definitions for Jarvis core modules."""
from typing import TypedDict, Literal, Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


# Trading Types
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeDict(TypedDict):
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    price: float
    status: Literal["pending", "filled", "cancelled"]
    created_at: str


class PositionDict(TypedDict):
    symbol: str
    size: float
    entry_price: float
    unrealized_pnl: float
    liquidation_price: Optional[float]


class CandleDict(TypedDict):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestResultDict(TypedDict):
    symbol: str
    interval: str
    strategy: str
    total_trades: int
    win_rate: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    net_pnl: float


# Provider Types
class ProviderStatus(TypedDict):
    name: str
    available: bool
    latency_ms: Optional[float]
    error: Optional[str]


class ProviderResponse(TypedDict):
    content: str
    model: str
    tokens_used: int
    latency_ms: float


# Memory Types
class MemoryEntryDict(TypedDict):
    timestamp: str
    text: str
    source: str
    quality_score: Optional[float]


# Config Types
class ProviderConfigDict(TypedDict):
    name: str
    api_key: Optional[str]
    enabled: bool
    priority: int


class TradingConfigDict(TypedDict):
    max_position_pct: float
    default_slippage_bps: float
    risk_per_trade: float


# API Response Types
class APIErrorDict(TypedDict):
    code: str
    message: str
    details: Optional[Dict[str, Any]]


class APIResponseDict(TypedDict):
    success: bool
    data: Optional[Any]
    error: Optional[APIErrorDict]
    timestamp: str


class PaginatedResponseDict(TypedDict):
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


# WebSocket Types
class WSMessageDict(TypedDict):
    type: str
    channel: str
    data: Dict[str, Any]
    timestamp: float


# Health Check Types
class ServiceHealthDict(TypedDict):
    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: Optional[float]
    last_check: str


class HealthCheckDict(TypedDict):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    timestamp: float
    services: Dict[str, ServiceHealthDict]


# Audit Types
class AuditEventDict(TypedDict):
    timestamp: float
    event_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    success: bool


# Type aliases for common patterns
JSON = Dict[str, Any]
Headers = Dict[str, str]
QueryParams = Dict[str, Union[str, int, float, bool]]
