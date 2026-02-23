"""
intent.py — Execution intent schema for Jupiter Perps.

The execution service accepts EXACTLY these six intent types:
    OpenPosition, ReducePosition, ClosePosition, CreateTPSL, CancelRequest, Noop

All intents are immutable dataclasses. Every intent carries:
    - idempotency_key: UUID v4 string — callers must generate this.
      The execution service deduplicates on this key (check-then-skip).
    - created_at_ns: nanosecond timestamp for ordering/audit.

Design constraints:
    - No AI-generated fields
    - No dynamic dispatch or eval
    - All fields are primitive types (str, float, int, bool)
    - Frozen dataclass: hashable, safe to use as dict keys

Collateral mints (mainnet):
    SOL  : So11111111111111111111111111111111111111112
    USDC : EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
    USDT : Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB

Markets supported by Jupiter Perps:
    SOL-USD, BTC-USD, ETH-USD, JLP-USD, BONK-USD
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class IntentType(str, Enum):
    OPEN_POSITION = "open_position"
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    CREATE_TPSL = "create_tpsl"
    CANCEL_REQUEST = "cancel_request"
    NOOP = "noop"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class CollateralMint(str, Enum):
    SOL = "So11111111111111111111111111111111111111112"
    USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


# Supported markets
SUPPORTED_MARKETS: frozenset[str] = frozenset(
    {"SOL-USD", "BTC-USD", "ETH-USD", "JLP-USD", "BONK-USD"}
)

# Leverage constraints
MIN_LEVERAGE = 1.0
MAX_LEVERAGE = 100.0

# Size constraints (USD notional)
MIN_POSITION_USD = 10.0
MAX_POSITION_USD = 1_000_000.0


def new_idempotency_key() -> str:
    """Generate a fresh UUID v4 idempotency key."""
    return str(uuid.uuid4())


def _now_ns() -> int:
    return time.time_ns()


@dataclass(frozen=True)
class OpenPosition:
    """Open a new leveraged position on Jupiter Perps."""

    intent_type: Literal[IntentType.OPEN_POSITION] = field(
        default=IntentType.OPEN_POSITION, init=False
    )
    idempotency_key: str
    market: str                    # e.g. "SOL-USD"
    side: Side                     # "long" or "short"
    collateral_mint: CollateralMint
    collateral_amount_usd: float   # USD value of collateral deposited
    leverage: float                # 1.0–100.0
    size_usd: float                # = collateral * leverage (computed by caller)
    max_slippage_bps: int = 50     # 0.5% default
    created_at_ns: int = field(default_factory=_now_ns)

    def __post_init__(self) -> None:
        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(f"Unsupported market: {self.market}")
        if not (MIN_LEVERAGE <= self.leverage <= MAX_LEVERAGE):
            raise ValueError(
                f"Leverage {self.leverage} outside [{MIN_LEVERAGE}, {MAX_LEVERAGE}]"
            )
        if not (MIN_POSITION_USD <= self.size_usd <= MAX_POSITION_USD):
            raise ValueError(
                f"Size ${self.size_usd} outside [{MIN_POSITION_USD}, {MAX_POSITION_USD}]"
            )
        if self.max_slippage_bps < 0 or self.max_slippage_bps > 10_000:
            raise ValueError(f"Slippage {self.max_slippage_bps}bps out of range")


@dataclass(frozen=True)
class ReducePosition:
    """Partially close an existing position (take profit or reduce exposure)."""

    intent_type: Literal[IntentType.REDUCE_POSITION] = field(
        default=IntentType.REDUCE_POSITION, init=False
    )
    idempotency_key: str
    position_pda: str              # On-chain PDA address of the position
    reduce_size_usd: float         # USD notional to remove (must be < position size)
    max_slippage_bps: int = 100
    created_at_ns: int = field(default_factory=_now_ns)

    def __post_init__(self) -> None:
        if self.reduce_size_usd <= 0:
            raise ValueError("reduce_size_usd must be positive")


@dataclass(frozen=True)
class ClosePosition:
    """Fully close an existing position."""

    intent_type: Literal[IntentType.CLOSE_POSITION] = field(
        default=IntentType.CLOSE_POSITION, init=False
    )
    idempotency_key: str
    position_pda: str              # On-chain PDA address of the position
    max_slippage_bps: int = 100
    created_at_ns: int = field(default_factory=_now_ns)


@dataclass(frozen=True)
class CreateTPSL:
    """Create an on-chain take-profit or stop-loss trigger order.

    This creates a PositionRequest PDA with requestType=Trigger on Jupiter.
    Jupiter's keepers monitor these on-chain and execute when the oracle price
    crosses the trigger_price. The order persists even if our process crashes.

    trigger_above_threshold:
        True  = Take Profit (execute when price >= trigger_price)
        False = Stop Loss (execute when price <= trigger_price)
    For shorts, the logic is inverted by the caller:
        True  = Stop Loss (execute when price >= trigger_price, i.e. short goes against you)
        False = Take Profit (execute when price <= trigger_price, i.e. short profits)
    """

    intent_type: Literal[IntentType.CREATE_TPSL] = field(
        default=IntentType.CREATE_TPSL, init=False
    )
    idempotency_key: str
    position_pda: str               # On-chain PDA of the position to protect
    trigger_price: float             # USD price at which to trigger
    trigger_above_threshold: bool    # True = trigger when price >= target
    entire_position: bool = True     # Close entire position when triggered
    size_usd: float = 0.0           # If not entire_position, USD notional to close
    created_at_ns: int = field(default_factory=_now_ns)

    def __post_init__(self) -> None:
        if self.trigger_price <= 0:
            raise ValueError(f"trigger_price must be positive, got {self.trigger_price}")
        if not self.entire_position and self.size_usd <= 0:
            raise ValueError("size_usd must be positive when entire_position is False")


@dataclass(frozen=True)
class CancelRequest:
    """Cancel a pending PositionRequest PDA (e.g. unfilled open order or TP/SL)."""

    intent_type: Literal[IntentType.CANCEL_REQUEST] = field(
        default=IntentType.CANCEL_REQUEST, init=False
    )
    idempotency_key: str
    request_pda: str               # On-chain PDA address of the PositionRequest
    created_at_ns: int = field(default_factory=_now_ns)


@dataclass(frozen=True)
class Noop:
    """
    No-operation intent. Used for heartbeat/liveness checks.
    The execution service processes this without submitting any transaction.
    """

    intent_type: Literal[IntentType.NOOP] = field(
        default=IntentType.NOOP, init=False
    )
    idempotency_key: str = field(default_factory=new_idempotency_key)
    created_at_ns: int = field(default_factory=_now_ns)


# Union type for all valid intents
ExecutionIntent = OpenPosition | ReducePosition | ClosePosition | CreateTPSL | CancelRequest | Noop
