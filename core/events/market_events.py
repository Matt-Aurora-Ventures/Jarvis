"""
Market Event Engine - Event detection is the primary alpha source.

The primary alpha in Solana DeFi comes from detecting events, not indicator
signals. Indicators are secondary confirmation tools. This module defines
market event types and the detection/classification layer.

Event hierarchy:
    1. Event Detected (stream or polling)
    2. Asset Class Identified (via asset registry)
    3. Cost Check (is this tradeable at all?)
    4. Strategy Router (Thompson Sampling selects strategy)
    5. Position Sizing (ATR + Kelly)
    6. Exit Management (ATR trailing + volume confirmation)

Detectable events:
    - TOKEN_LAUNCH: New token on bonding curve (Pump.fun, Bags.fm)
    - GRADUATION: Token migrates from bonding curve to AMM pool
    - LIQUIDITY_INFLOW: Large liquidity add to existing pool
    - VOLUME_EXPLOSION: Volume exceeds 5x 20-bar average
    - WALLET_ACCUMULATION: Smart wallet adds position (TODO: wallet tracking)
    - ORACLE_UPDATE: xStock oracle price refresh
    - REGIME_CHANGE: Market regime shift (risk-on/risk-off)

Usage::

    from core.events.market_events import (
        MarketEvent, MarketEventType, classify_stream_event,
    )

    event = classify_stream_event(stream_event, registry)
    if event and event.is_tradeable:
        pipeline.process(event)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from core.data.asset_registry import AssetClass, AssetRegistry, AssetRecord
except ImportError:
    AssetClass = None  # type: ignore[assignment,misc]
    AssetRegistry = None  # type: ignore[assignment,misc]

try:
    from core.data.streams import StreamEvent, StreamEventType
except ImportError:
    StreamEvent = None  # type: ignore[assignment,misc]
    StreamEventType = None  # type: ignore[assignment,misc]

try:
    from core.trading.fee_model import calculate_trade_cost, TradeCost
except ImportError:
    calculate_trade_cost = None  # type: ignore[assignment]
    TradeCost = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class MarketEventType(Enum):
    """Primary alpha-generating events in Solana DeFi."""

    # Launch events (highest urgency)
    TOKEN_LAUNCH = "token_launch"
    GRADUATION = "graduation"

    # Liquidity events
    LIQUIDITY_INFLOW = "liquidity_inflow"
    LIQUIDITY_DRAIN = "liquidity_drain"
    POOL_CREATED = "pool_created"

    # Volume / momentum events
    VOLUME_EXPLOSION = "volume_explosion"
    PRICE_BREAKOUT = "price_breakout"
    PRICE_BREAKDOWN = "price_breakdown"

    # Wallet events (requires on-chain tracking)
    WALLET_ACCUMULATION = "wallet_accumulation"
    WHALE_DUMP = "whale_dump"

    # xStock events
    ORACLE_UPDATE = "oracle_update"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"

    # Regime events
    REGIME_CHANGE = "regime_change"

    # Exit triggers
    STOP_HIT = "stop_hit"
    TAKE_PROFIT = "take_profit"
    GRADUATION_EXIT = "graduation_exit"


class EventUrgency(Enum):
    """How fast must the system respond to this event."""

    IMMEDIATE = "immediate"   # < 500ms (launches, graduations)
    FAST = "fast"             # < 5s (volume explosions, breakouts)
    NORMAL = "normal"         # < 30s (liquidity changes, regime shifts)
    LOW = "low"               # < 5min (oracle updates, wallet tracking)


# Urgency mapping
EVENT_URGENCY: Dict[MarketEventType, EventUrgency] = {
    MarketEventType.TOKEN_LAUNCH: EventUrgency.IMMEDIATE,
    MarketEventType.GRADUATION: EventUrgency.IMMEDIATE,
    MarketEventType.GRADUATION_EXIT: EventUrgency.IMMEDIATE,
    MarketEventType.VOLUME_EXPLOSION: EventUrgency.FAST,
    MarketEventType.PRICE_BREAKOUT: EventUrgency.FAST,
    MarketEventType.PRICE_BREAKDOWN: EventUrgency.FAST,
    MarketEventType.WHALE_DUMP: EventUrgency.FAST,
    MarketEventType.STOP_HIT: EventUrgency.FAST,
    MarketEventType.TAKE_PROFIT: EventUrgency.FAST,
    MarketEventType.LIQUIDITY_INFLOW: EventUrgency.NORMAL,
    MarketEventType.LIQUIDITY_DRAIN: EventUrgency.NORMAL,
    MarketEventType.POOL_CREATED: EventUrgency.NORMAL,
    MarketEventType.WALLET_ACCUMULATION: EventUrgency.NORMAL,
    MarketEventType.REGIME_CHANGE: EventUrgency.NORMAL,
    MarketEventType.ORACLE_UPDATE: EventUrgency.LOW,
    MarketEventType.MARKET_OPEN: EventUrgency.LOW,
    MarketEventType.MARKET_CLOSE: EventUrgency.LOW,
}


# ---------------------------------------------------------------------------
# Market Event
# ---------------------------------------------------------------------------

@dataclass
class MarketEvent:
    """
    A classified market event ready for the trading pipeline.

    This is the primary input to the trading system. Everything downstream
    (cost check, strategy selection, sizing, exits) flows from this.
    """

    event_type: MarketEventType
    urgency: EventUrgency
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Asset identification
    mint_address: Optional[str] = None
    symbol: Optional[str] = None
    asset_class: Optional[AssetClass] = None

    # Market context
    current_price: float = 0.0
    pool_liquidity_usd: float = 0.0
    volume_24h_usd: float = 0.0
    volume_ratio: float = 0.0  # current_volume / avg_volume

    # Event-specific data
    data: Dict[str, Any] = field(default_factory=dict)

    # Cost pre-check (populated by pipeline)
    estimated_cost: Optional[Any] = None  # TradeCost when available
    is_tradeable: bool = False
    cost_check_reason: str = ""

    # Source tracing
    source_event_id: str = ""
    source_type: str = ""  # "stream", "polling", "webhook", "manual"

    # Processing state
    processed: bool = False
    processing_latency_ms: float = 0.0

    def __repr__(self) -> str:
        symbol = self.symbol or (self.mint_address[:8] + "..." if self.mint_address else "unknown")
        return (
            f"MarketEvent({self.event_type.value}, {symbol}, "
            f"urgency={self.urgency.value}, tradeable={self.is_tradeable})"
        )

    def mark_processed(self, start_time: float) -> None:
        """Mark event as processed and record latency."""
        self.processed = True
        self.processing_latency_ms = (time.time() - start_time) * 1000


# ---------------------------------------------------------------------------
# Event classification from stream events
# ---------------------------------------------------------------------------

def classify_stream_event(
    stream_event: Any,
    asset_registry: Optional[Any] = None,
) -> Optional[MarketEvent]:
    """
    Convert a raw StreamEvent from core.data.streams into a classified MarketEvent.

    This is the bridge between the WebSocket layer and the trading pipeline.
    """
    if StreamEvent is None or stream_event is None:
        return None

    if not isinstance(stream_event, StreamEvent):
        return None

    event_type: Optional[MarketEventType] = None
    data: Dict[str, Any] = {}

    # Map StreamEventType to MarketEventType
    if stream_event.event_type == StreamEventType.GRADUATION:
        event_type = MarketEventType.GRADUATION
        data["pool_address"] = stream_event.pool_address
    elif stream_event.event_type == StreamEventType.NEW_POOL:
        # Could be launch or pool creation depending on program
        if stream_event.program_id == "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P":
            event_type = MarketEventType.TOKEN_LAUNCH
        else:
            event_type = MarketEventType.POOL_CREATED
    elif stream_event.event_type == StreamEventType.SWAP:
        # Swaps are not events by themselves unless volume is unusual
        # The pipeline should aggregate these into volume_explosion events
        return None
    else:
        return None

    if event_type is None:
        return None

    # Determine asset class from registry if available
    asset_class = None
    if asset_registry and AssetRegistry and stream_event.mint_address:
        record = asset_registry.get(stream_event.mint_address)
        if record:
            asset_class = record.asset_class

    # Build the market event
    urgency = EVENT_URGENCY.get(event_type, EventUrgency.NORMAL)

    return MarketEvent(
        event_type=event_type,
        urgency=urgency,
        timestamp=stream_event.timestamp,
        mint_address=stream_event.mint_address,
        asset_class=asset_class,
        data=data,
        source_event_id=stream_event.signature,
        source_type="stream",
    )


# ---------------------------------------------------------------------------
# Volume explosion detection
# ---------------------------------------------------------------------------

class VolumeTracker:
    """
    Tracks rolling volume per asset and detects volume explosions.

    A volume explosion is when current-bar volume exceeds N times the
    20-bar average. This is a primary alpha signal for memecoins.
    """

    def __init__(
        self,
        explosion_multiplier: float = 5.0,
        window_size: int = 20,
    ) -> None:
        self._multiplier = explosion_multiplier
        self._window_size = window_size
        self._volumes: Dict[str, List[float]] = {}  # mint -> recent volumes

    def update(self, mint_address: str, volume: float) -> Optional[MarketEvent]:
        """
        Record a volume observation. Returns a MarketEvent if explosion detected.
        """
        if mint_address not in self._volumes:
            self._volumes[mint_address] = []

        history = self._volumes[mint_address]
        history.append(volume)

        # Keep only the window
        if len(history) > self._window_size + 1:
            self._volumes[mint_address] = history[-self._window_size - 1:]
            history = self._volumes[mint_address]

        if len(history) < self._window_size + 1:
            return None  # Not enough data

        # Average of the previous N bars (excluding current)
        avg_volume = sum(history[:-1]) / len(history[:-1])
        if avg_volume <= 0:
            return None

        ratio = volume / avg_volume

        if ratio >= self._multiplier:
            return MarketEvent(
                event_type=MarketEventType.VOLUME_EXPLOSION,
                urgency=EventUrgency.FAST,
                mint_address=mint_address,
                volume_ratio=ratio,
                data={
                    "current_volume": volume,
                    "avg_volume": avg_volume,
                    "ratio": ratio,
                    "threshold": self._multiplier,
                },
                source_type="volume_tracker",
            )
        return None

    def reset(self, mint_address: str) -> None:
        """Clear volume history for an asset."""
        self._volumes.pop(mint_address, None)

    @property
    def tracked_count(self) -> int:
        return len(self._volumes)


# ---------------------------------------------------------------------------
# Cost pre-check
# ---------------------------------------------------------------------------

def precheck_cost(
    event: MarketEvent,
    trade_size_usd: float = 500.0,
    min_edge_pct: Optional[float] = None,
) -> MarketEvent:
    """
    Run a cost viability check on a market event before routing to strategies.

    Populates event.estimated_cost, event.is_tradeable, and event.cost_check_reason.
    If min_edge_pct is provided, checks edge >= 2x cost. Otherwise just calculates cost.
    """
    if calculate_trade_cost is None or event.asset_class is None:
        event.cost_check_reason = "missing_dependencies"
        event.is_tradeable = False
        return event

    pool_liq = event.pool_liquidity_usd if event.pool_liquidity_usd > 0 else 50_000

    cost = calculate_trade_cost(
        asset_class=event.asset_class,
        pool_liquidity_usd=pool_liq,
        trade_size_usd=trade_size_usd,
    )
    event.estimated_cost = cost

    if min_edge_pct is not None:
        # Edge must be >= 2x round-trip cost
        if min_edge_pct >= cost.total_round_trip_pct * 2.0:
            event.is_tradeable = True
            event.cost_check_reason = (
                f"viable: edge {min_edge_pct:.2%} >= 2x cost {cost.total_round_trip_pct:.2%}"
            )
        else:
            event.is_tradeable = False
            event.cost_check_reason = (
                f"insufficient_edge: {min_edge_pct:.2%} < 2x cost {cost.total_round_trip_pct:.2%}"
            )
    else:
        # No edge estimate yet - mark tradeable if cost is below threshold
        if cost.total_round_trip_pct < 0.10:  # < 10% RT cost
            event.is_tradeable = True
            event.cost_check_reason = f"cost_acceptable: {cost.total_round_trip_pct:.2%} RT"
        else:
            event.is_tradeable = False
            event.cost_check_reason = f"cost_too_high: {cost.total_round_trip_pct:.2%} RT"

    return event
