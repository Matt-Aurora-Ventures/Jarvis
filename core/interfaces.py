"""
JARVIS Service Interfaces

Abstract interfaces that define contracts for common services.
Modules depend on interfaces, not implementations, enabling:
- Multiple implementations (Jupiter, Bags, etc. all implement ISwapService)
- Easy mocking for tests
- Runtime swapping of implementations
- Clear contracts for what services must provide

Usage:
    from core.interfaces import IPriceService, ISentimentService

    class MyPriceFetcher(IPriceService):
        async def get_price(self, symbol: str) -> float:
            ...
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


# ==================== Data Types ====================

@dataclass
class PriceData:
    """Standardized price data."""
    symbol: str
    price: float
    timestamp: float
    source: str
    change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None


@dataclass
class SentimentResult:
    """Standardized sentiment analysis result."""
    score: float  # -1.0 to 1.0
    grade: str    # A+, A, B+, B, C, D, F
    confidence: float  # 0.0 to 1.0
    source: str
    timestamp: float
    details: Dict[str, Any] = None

    @property
    def is_bullish(self) -> bool:
        return self.score > 0.2

    @property
    def is_bearish(self) -> bool:
        return self.score < -0.2


@dataclass
class SwapQuote:
    """Standardized swap quote."""
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact: float
    route: List[str]
    fees: float
    slippage: float
    expires_at: float
    raw_quote: Any = None  # Original provider quote


@dataclass
class SwapResult:
    """Result of a swap execution."""
    success: bool
    signature: Optional[str] = None
    input_amount: Optional[float] = None
    output_amount: Optional[float] = None
    error: Optional[str] = None
    gas_used: Optional[int] = None


@dataclass
class MessagePayload:
    """Standardized message for any platform."""
    text: str
    platform: str
    chat_id: Optional[str] = None
    reply_to: Optional[str] = None
    media_urls: List[str] = None
    buttons: List[Dict[str, str]] = None
    parse_mode: str = "markdown"


@dataclass
class TradeSignal:
    """Standardized trade signal."""
    symbol: str
    action: str  # "buy", "sell", "hold"
    confidence: float
    entry_price: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    reasoning: Optional[str] = None
    source: str = "unknown"
    timestamp: float = None


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Order:
    """Standardized order representation."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float
    price: Optional[float] = None
    status: str = "pending"
    filled_amount: float = 0
    created_at: float = None


# ==================== Service Interfaces ====================

class IPriceService(ABC):
    """
    Interface for price data providers.

    Implementations: Jupiter, DexScreener, CoinGecko, TwelveData, Hyperliquid
    """

    @abstractmethod
    async def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        pass

    @abstractmethod
    async def get_price_data(self, symbol: str) -> Optional[PriceData]:
        """Get detailed price data for a symbol."""
        pass

    @abstractmethod
    async def get_prices_batch(self, symbols: List[str]) -> Dict[str, float]:
        """Get prices for multiple symbols."""
        pass

    async def get_historical(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV data. Optional implementation."""
        return []


class ISentimentService(ABC):
    """
    Interface for sentiment analysis providers.

    Implementations: Grok sentiment, EODHD, social aggregators
    """

    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text."""
        pass

    @abstractmethod
    async def analyze_symbol(self, symbol: str) -> SentimentResult:
        """Get aggregated sentiment for a symbol."""
        pass

    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts. Default implementation."""
        results = []
        for text in texts:
            results.append(await self.analyze(text))
        return results


class ISwapService(ABC):
    """
    Interface for token swap providers.

    Implementations: Jupiter, Raydium, Bags
    """

    @abstractmethod
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage: float = 0.5
    ) -> Optional[SwapQuote]:
        """Get a swap quote."""
        pass

    @abstractmethod
    async def execute_swap(
        self,
        quote: SwapQuote,
        wallet: Any
    ) -> SwapResult:
        """Execute a swap."""
        pass

    async def get_best_route(
        self,
        input_mint: str,
        output_mint: str,
        amount: int
    ) -> Optional[List[str]]:
        """Get best route for a swap. Optional."""
        return None


class IMessagingService(ABC):
    """
    Interface for messaging platforms.

    Implementations: Telegram, X/Twitter, Discord
    """

    @abstractmethod
    async def send_message(self, payload: MessagePayload) -> bool:
        """Send a message."""
        pass

    @abstractmethod
    async def send_to_chat(self, chat_id: str, text: str) -> bool:
        """Send text to a specific chat."""
        pass

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str
    ) -> bool:
        """Edit an existing message. Optional."""
        return False

    async def delete_message(self, chat_id: str, message_id: str) -> bool:
        """Delete a message. Optional."""
        return False


class IWalletService(ABC):
    """
    Interface for wallet operations.

    Implementations: Solana wallet, EVM wallet
    """

    @abstractmethod
    async def get_balance(self, token_mint: Optional[str] = None) -> float:
        """Get balance for native token or specific token."""
        pass

    @abstractmethod
    async def get_token_balances(self) -> Dict[str, float]:
        """Get all token balances."""
        pass

    @abstractmethod
    async def sign_transaction(self, transaction: Any) -> Any:
        """Sign a transaction."""
        pass

    @property
    @abstractmethod
    def address(self) -> str:
        """Get wallet address."""
        pass


class IOrderService(ABC):
    """
    Interface for order management.

    Implementations: Jupiter DCA, limit orders, etc.
    """

    @abstractmethod
    async def create_order(self, order: Order) -> Tuple[bool, str]:
        """Create a new order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        pass

    @abstractmethod
    async def get_open_orders(self) -> List[Order]:
        """Get all open orders."""
        pass


class IStorageService(ABC):
    """
    Interface for persistent storage.

    Implementations: SQLite, JSON files, Redis
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a value with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key."""
        pass

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values. Default implementation."""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result


class IAlertService(ABC):
    """
    Interface for alert delivery.

    Implementations: Telegram alerts, email, push notifications
    """

    @abstractmethod
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        data: Dict[str, Any] = None
    ) -> bool:
        """Send an alert."""
        pass

    @abstractmethod
    async def send_price_alert(
        self,
        symbol: str,
        price: float,
        condition: str,
        target: float
    ) -> bool:
        """Send a price alert."""
        pass


class IAIService(ABC):
    """
    Interface for AI/LLM providers.

    Implementations: Grok, Claude, OpenAI, local models
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Generate a completion."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None
    ) -> str:
        """Chat completion with message history."""
        pass

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings. Optional."""
        return []


class ISignalService(ABC):
    """
    Interface for trading signal generation.

    Implementations: Sentiment-based, technical, ML models
    """

    @abstractmethod
    async def generate_signal(self, symbol: str) -> Optional[TradeSignal]:
        """Generate a trading signal for a symbol."""
        pass

    @abstractmethod
    async def get_active_signals(self) -> List[TradeSignal]:
        """Get all currently active signals."""
        pass

    async def validate_signal(self, signal: TradeSignal) -> bool:
        """Validate a signal before execution. Optional."""
        return True


class IMonitoringService(ABC):
    """
    Interface for monitoring and metrics.

    Implementations: Prometheus, custom metrics
    """

    @abstractmethod
    def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None
    ):
        """Record a metric value."""
        pass

    @abstractmethod
    def increment_counter(
        self,
        name: str,
        amount: int = 1,
        tags: Dict[str, str] = None
    ):
        """Increment a counter."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get all recorded metrics."""
        pass


# ==================== Composite Interfaces ====================

class ITradingEngine(IPriceService, ISwapService, IOrderService):
    """
    Combined interface for a complete trading engine.
    Must implement price, swap, and order capabilities.
    """

    @abstractmethod
    async def open_position(
        self,
        symbol: str,
        amount_usd: float,
        take_profit_pct: float = None,
        stop_loss_pct: float = None
    ) -> Tuple[bool, str, Any]:
        """Open a new trading position."""
        pass

    @abstractmethod
    async def close_position(
        self,
        position_id: str,
        reason: str = "manual"
    ) -> Tuple[bool, str]:
        """Close an existing position."""
        pass


class IAnalyticsEngine(ISentimentService, ISignalService):
    """
    Combined interface for analytics.
    Must implement sentiment and signal generation.
    """

    @abstractmethod
    async def get_market_overview(self) -> Dict[str, Any]:
        """Get comprehensive market overview."""
        pass


# ==================== Factory Registration ====================

# Registry of interface implementations
_implementations: Dict[type, List[type]] = {}


def implements(interface: type):
    """
    Decorator to register a class as implementing an interface.

    Usage:
        @implements(IPriceService)
        class JupiterPriceService(IPriceService):
            ...
    """
    def decorator(cls: type) -> type:
        if interface not in _implementations:
            _implementations[interface] = []
        _implementations[interface].append(cls)
        return cls
    return decorator


def get_implementations(interface: type) -> List[type]:
    """Get all registered implementations of an interface."""
    return _implementations.get(interface, [])
