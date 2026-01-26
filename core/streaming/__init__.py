"""
Yellowstone gRPC (Geyser) streaming module for real-time Solana data.

This module provides:
- GeyserClient: Low-level gRPC client for Yellowstone Geyser
- PoolMonitor: DEX pool monitoring (Raydium, Orca, Jupiter)
- WhaleTracker: Whale wallet tracking and copy trading signals

Usage:
    from core.streaming import GeyserClient, PoolMonitor, WhaleTracker

    # Initialize client
    client = GeyserClient.helius()

    # Start pool monitoring
    pool_monitor = PoolMonitor(client)
    pool_monitor.on_pool_event(handle_pool_event)
    await pool_monitor.start()

    # Start whale tracking
    whale_tracker = WhaleTracker(client)
    whale_tracker.on_whale_event(handle_whale_event)
    await whale_tracker.start()
"""

from core.streaming.events import (
    StreamingEvent,
    EventType,
)
from core.streaming.geyser_client import (
    GeyserClient,
    GeyserConfig,
    GeyserConnectionState,
    AccountUpdate,
    SubscriptionFilter,
    GeyserError,
    GeyserConnectionError,
    GeyserSubscriptionError,
)
from core.streaming.pool_monitor import (
    PoolMonitor,
    PoolMonitorConfig,
    DEXType,
    PoolState,
    PoolUpdate,
    PoolEvent,
    PoolEventType,
)
from core.streaming.whale_tracker import (
    WhaleTracker,
    WhaleTrackerConfig,
    WalletConfig,
    WalletActivity,
    WhaleEvent,
    WhaleEventType,
    TradeDirection,
    WalletCategory,
    WalletScore,
)

__all__ = [
    # Events
    "StreamingEvent",
    "EventType",
    # Geyser Client
    "GeyserClient",
    "GeyserConfig",
    "GeyserConnectionState",
    "AccountUpdate",
    "SubscriptionFilter",
    "GeyserError",
    "GeyserConnectionError",
    "GeyserSubscriptionError",
    # Pool Monitor
    "PoolMonitor",
    "PoolMonitorConfig",
    "DEXType",
    "PoolState",
    "PoolUpdate",
    "PoolEvent",
    "PoolEventType",
    # Whale Tracker
    "WhaleTracker",
    "WhaleTrackerConfig",
    "WalletConfig",
    "WalletActivity",
    "WhaleEvent",
    "WhaleEventType",
    "TradeDirection",
    "WalletCategory",
    "WalletScore",
]
