"""
JARVIS API Type Stubs

This module provides typed stubs for JARVIS public APIs to enable:
- IDE autocomplete
- Type checking with mypy
- Documentation generation

Usage:
    from docs.api_stubs import (
        TradingEngine,
        Position,
        ReActDecision,
        SentimentResult,
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)


# =============================================================================
# Type Variables
# =============================================================================

T = TypeVar("T")
AsyncFunc = TypeVar("AsyncFunc", bound=Callable[..., Coroutine[Any, Any, Any]])


# =============================================================================
# Enums
# =============================================================================

class TradeDirection(Enum):
    """Direction of a trade."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class TradeStatus(Enum):
    """Status of a trading position."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class RiskLevel(Enum):
    """Trading risk level."""
    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"
    DEGEN = "DEGEN"


class DecisionType(Enum):
    """Dexter agent decision types."""
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    HOLD = "HOLD"
    ERROR = "ERROR"


class SentimentGrade(Enum):
    """Sentiment analysis grade."""
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D = "D"
    F = "F"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Position:
    """
    Represents an open or closed trading position.

    Attributes:
        id: Unique position identifier
        token_mint: Solana token mint address
        token_symbol: Token trading symbol
        direction: Long or short position
        entry_price: Price at entry
        current_price: Current market price
        amount: Token quantity
        amount_usd: Position value in USD
        take_profit_price: Take profit target
        stop_loss_price: Stop loss target
        status: Current position status
        opened_at: ISO timestamp of entry
        closed_at: ISO timestamp of exit (if closed)
        exit_price: Price at exit (if closed)
        pnl_usd: Realized profit/loss in USD
        pnl_pct: Realized profit/loss percentage
        sentiment_grade: Sentiment grade at entry
        sentiment_score: Sentiment score at entry
    """
    id: str
    token_mint: str
    token_symbol: str
    direction: TradeDirection
    entry_price: float
    current_price: float
    amount: float
    amount_usd: float
    take_profit_price: float
    stop_loss_price: float
    status: TradeStatus
    opened_at: str
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    sentiment_grade: str = ""
    sentiment_score: float = 0.0

    @property
    def is_open(self) -> bool:
        """Check if position is currently open."""
        ...

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized profit/loss in USD."""
        ...

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized profit/loss percentage."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        ...

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create position from dictionary."""
        ...


@dataclass
class TradeReport:
    """
    Trading performance summary report.

    Attributes:
        total_trades: Total number of trades
        winning_trades: Number of profitable trades
        losing_trades: Number of losing trades
        win_rate: Win rate percentage (0-100)
        total_pnl_usd: Total realized P&L in USD
        total_pnl_pct: Total realized P&L percentage
        best_trade_pnl: Best single trade P&L
        worst_trade_pnl: Worst single trade P&L
        avg_trade_pnl: Average trade P&L
        average_win_usd: Average winning trade
        average_loss_usd: Average losing trade
        open_positions: Number of open positions
        unrealized_pnl: Total unrealized P&L
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_pct: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    average_win_usd: float = 0.0
    average_loss_usd: float = 0.0
    open_positions: int = 0
    unrealized_pnl: float = 0.0

    def to_telegram_message(self) -> str:
        """Format report for Telegram (HTML)."""
        ...


@dataclass
class ReActDecision:
    """
    Result of a Dexter ReAct reasoning loop.

    Attributes:
        decision: Final decision (BUY, SELL, HOLD, ERROR)
        symbol: Token symbol analyzed
        rationale: Human-readable explanation
        confidence: Decision confidence (0-100)
        tools_used: List of tools used in reasoning
        grok_sentiment_score: Grok sentiment score
        market_data: Collected market data
        iterations: Number of reasoning iterations
        cost_usd: Total LLM cost for decision
    """
    decision: DecisionType
    symbol: str = ""
    rationale: str = ""
    confidence: float = 0.0
    tools_used: List[str] = field(default_factory=list)
    grok_sentiment_score: float = 0.0
    market_data: Dict[str, Any] = field(default_factory=dict)
    iterations: int = 0
    cost_usd: float = 0.0


@dataclass
class SentimentResult:
    """
    Result of sentiment analysis.

    Attributes:
        symbol: Token symbol
        score: Sentiment score (0-100)
        grade: Letter grade (A+, A, B, etc.)
        recommendation: BUY, SELL, or HOLD
        confidence: Analysis confidence
        sources: Data sources used
        timestamp: Analysis timestamp
    """
    symbol: str
    score: float
    grade: str
    recommendation: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class SwapQuote:
    """
    Jupiter swap quote.

    Attributes:
        input_mint: Input token mint address
        output_mint: Output token mint address
        in_amount: Input amount (lamports/smallest unit)
        out_amount: Expected output amount
        price_impact_pct: Price impact percentage
        slippage_bps: Slippage tolerance in basis points
        route: Routing path
    """
    input_mint: str
    output_mint: str
    in_amount: int
    out_amount: int
    price_impact_pct: float
    slippage_bps: int
    route: List[Dict[str, Any]]


@dataclass
class WalletInfo:
    """
    Wallet information.

    Attributes:
        address: Solana public key (base58)
        balance_sol: SOL balance
        balance_usd: Estimated USD value
        tokens: List of token balances
    """
    address: str
    balance_sol: float
    balance_usd: float
    tokens: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Protocol Classes (Interfaces)
# =============================================================================

class TradingEngineProtocol(Protocol):
    """Interface for the trading engine."""

    async def open_position(
        self,
        token_mint: str,
        token_symbol: str,
        amount_usd: float,
        sentiment_grade: str = "",
        sentiment_score: float = 0.0,
    ) -> Optional[Position]:
        """
        Open a new trading position.

        Args:
            token_mint: Solana token mint address
            token_symbol: Token symbol (e.g., "SOL")
            amount_usd: Position size in USD
            sentiment_grade: Optional sentiment grade
            sentiment_score: Optional sentiment score

        Returns:
            Position object if successful, None if failed

        Raises:
            ValueError: If parameters are invalid
            InsufficientBalanceError: If wallet balance too low
        """
        ...

    async def close_position(
        self,
        position_id: str,
        reason: str = "Manual close",
    ) -> Optional[Position]:
        """
        Close an existing position.

        Args:
            position_id: ID of position to close
            reason: Reason for closing

        Returns:
            Closed position with final P&L, or None if failed
        """
        ...

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a position by ID."""
        ...

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        ...

    def generate_report(self) -> TradeReport:
        """Generate trading performance report."""
        ...


class SentimentAnalyzerProtocol(Protocol):
    """Interface for sentiment analysis."""

    async def analyze(self, symbol: str) -> SentimentResult:
        """
        Analyze sentiment for a token.

        Args:
            symbol: Token symbol to analyze

        Returns:
            SentimentResult with score and recommendation
        """
        ...

    async def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending tokens by sentiment."""
        ...


class DexterAgentProtocol(Protocol):
    """Interface for Dexter ReAct agent."""

    async def analyze_trading_opportunity(
        self,
        symbol: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReActDecision:
        """
        Run ReAct reasoning loop for trading decision.

        Args:
            symbol: Token symbol to analyze
            context: Additional context (optional)

        Returns:
            ReActDecision with reasoning trace
        """
        ...

    def get_scratchpad(self) -> str:
        """Get formatted reasoning scratchpad."""
        ...


class JupiterClientProtocol(Protocol):
    """Interface for Jupiter DEX client."""

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100,
    ) -> SwapQuote:
        """Get swap quote from Jupiter."""
        ...

    async def execute_swap(
        self,
        quote: SwapQuote,
        wallet: Any,
    ) -> str:
        """Execute swap and return transaction signature."""
        ...

    async def get_token_price(self, token_mint: str) -> float:
        """Get current token price in USD."""
        ...


class WalletProtocol(Protocol):
    """Interface for secure wallet."""

    def get_info(self) -> WalletInfo:
        """Get wallet information."""
        ...

    async def sign_transaction(self, transaction: Any) -> Any:
        """Sign a Solana transaction."""
        ...

    def get_public_key(self) -> str:
        """Get wallet public key (base58)."""
        ...


# =============================================================================
# Function Signatures
# =============================================================================

async def get_aggregated_sentiment(symbol: str) -> SentimentResult:
    """
    Get aggregated sentiment for a token from multiple sources.

    Args:
        symbol: Token symbol (e.g., "SOL", "BONK")

    Returns:
        SentimentResult with combined score and grade

    Example:
        >>> sentiment = await get_aggregated_sentiment("SOL")
        >>> print(f"Score: {sentiment.score}, Grade: {sentiment.grade}")
        Score: 78.5, Grade: B+
    """
    ...


async def get_market_data(token_mint: str) -> Dict[str, Any]:
    """
    Get comprehensive market data for a token.

    Args:
        token_mint: Solana token mint address

    Returns:
        Dictionary with price, volume, liquidity, etc.

    Example:
        >>> data = await get_market_data("So111...")
        >>> print(f"Price: ${data['price']}")
        Price: $105.50
    """
    ...


def is_feature_enabled(flag_name: str, user_id: Optional[int] = None) -> bool:
    """
    Check if a feature flag is enabled.

    Args:
        flag_name: Name of the feature flag
        user_id: Optional user ID for user-specific flags

    Returns:
        True if feature is enabled, False otherwise

    Example:
        >>> if is_feature_enabled("new_algo_v2", user_id=123):
        ...     use_new_algorithm()
    """
    ...


def log_event(event: str, **kwargs: Any) -> None:
    """
    Log a structured event to JSONL audit log.

    Args:
        event: Event type (e.g., "TRADE_EXECUTED")
        **kwargs: Additional event data

    Example:
        >>> log_event("TRADE_EXECUTED", token="SOL", pnl=25.0)
    """
    ...


# =============================================================================
# Export All
# =============================================================================

__all__ = [
    # Enums
    "TradeDirection",
    "TradeStatus",
    "RiskLevel",
    "DecisionType",
    "SentimentGrade",
    # Data Classes
    "Position",
    "TradeReport",
    "ReActDecision",
    "SentimentResult",
    "SwapQuote",
    "WalletInfo",
    # Protocols
    "TradingEngineProtocol",
    "SentimentAnalyzerProtocol",
    "DexterAgentProtocol",
    "JupiterClientProtocol",
    "WalletProtocol",
    # Functions
    "get_aggregated_sentiment",
    "get_market_data",
    "is_feature_enabled",
    "log_event",
]
