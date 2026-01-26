"""
Whale wallet tracking via Yellowstone Geyser.

Tracks configured whale wallets for:
- Large buys/sells
- New position entries
- Position exits
- Accumulation/distribution patterns
- Copy trading signals

Usage:
    from core.streaming import GeyserClient, WhaleTracker, WhaleTrackerConfig

    client = GeyserClient.helius()
    config = WhaleTrackerConfig(
        wallets=[WalletConfig(address="...", label="Smart Money")]
    )
    tracker = WhaleTracker(client, config)

    tracker.on_whale_event(handle_event)
    await tracker.start()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import yaml

from core.streaming.geyser_client import (
    GeyserClient,
    AccountUpdate,
    GeyserConnectionState,
)

logger = logging.getLogger(__name__)

# Token Program ID
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


class WalletCategory(Enum):
    """Categories for tracked wallets."""

    WHALE = "whale"
    SMART_MONEY = "smart_money"
    SNIPER = "sniper"
    MARKET_MAKER = "market_maker"
    INSIDER = "insider"
    UNKNOWN = "unknown"


class TradeDirection(Enum):
    """Direction of a trade."""

    BUY = "buy"
    SELL = "sell"


class WhaleEventType(Enum):
    """Types of whale events."""

    LARGE_BUY = "large_buy"
    LARGE_SELL = "large_sell"
    NEW_POSITION = "new_position"
    POSITION_CLOSED = "position_closed"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


@dataclass
class WalletConfig:
    """Configuration for a tracked wallet."""

    address: str
    label: Optional[str] = None
    category: WalletCategory = WalletCategory.UNKNOWN
    min_trade_size_usd: float = 0.0
    track_all_tokens: bool = True
    tokens_to_track: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class WalletActivity:
    """Record of wallet activity."""

    wallet_address: str
    token_mint: str
    token_symbol: str
    amount_change: int
    direction: TradeDirection
    slot: int
    signature: str
    estimated_value_usd: float
    timestamp: float = field(default_factory=time.time)

    def is_large_trade(self, threshold_usd: float) -> bool:
        """Check if this is a large trade."""
        return self.estimated_value_usd >= threshold_usd


@dataclass
class WhaleEvent:
    """Event emitted by the whale tracker."""

    event_type: WhaleEventType
    wallet_address: str
    wallet_label: Optional[str]
    wallet_category: WalletCategory
    token_mint: str
    token_symbol: str
    amount: int
    value_usd: float
    slot: int
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type.value,
            "wallet_address": self.wallet_address,
            "wallet_label": self.wallet_label,
            "wallet_category": self.wallet_category.value,
            "token_mint": self.token_mint,
            "token_symbol": self.token_symbol,
            "amount": self.amount,
            "value_usd": self.value_usd,
            "slot": self.slot,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class WalletScore:
    """Score/metrics for a wallet."""

    address: str
    total_trades: int
    win_rate: float
    avg_profit_pct: float
    total_volume_usd: float
    avg_hold_time_hours: float
    category: WalletCategory

    def get_ranking_score(self) -> float:
        """Calculate overall ranking score (0-100)."""
        # Weighted scoring
        win_score = self.win_rate * 40  # 40% weight
        profit_score = min(self.avg_profit_pct / 50, 1.0) * 30  # 30% weight, cap at 50%
        volume_score = min(self.total_volume_usd / 1_000_000, 1.0) * 20  # 20% weight
        activity_score = min(self.total_trades / 100, 1.0) * 10  # 10% weight

        return win_score + profit_score + volume_score + activity_score


@dataclass
class CopyTradeSignal:
    """Signal for copy trading."""

    wallet_address: str
    wallet_score: WalletScore
    token_mint: str
    token_symbol: str
    direction: TradeDirection
    value_usd: float
    confidence: float
    timestamp: float


@dataclass
class WhaleTrackerConfig:
    """Configuration for whale tracking."""

    wallets: List[WalletConfig] = field(default_factory=list)
    min_trade_size_usd: float = 5000.0
    large_trade_threshold_usd: float = 50000.0
    accumulation_window_hours: float = 24.0
    accumulation_trade_count: int = 3
    copy_trade_enabled: bool = False
    copy_trade_min_wallet_score: float = 50.0

    @classmethod
    def from_file(cls, path: str) -> "WhaleTrackerConfig":
        """Load configuration from YAML file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)

            wallets = []
            for w in data.get("wallets", []):
                category = WalletCategory(w.get("category", "unknown"))
                wallets.append(
                    WalletConfig(
                        address=w["address"],
                        label=w.get("label"),
                        category=category,
                        min_trade_size_usd=w.get("min_trade_size_usd", 0),
                        track_all_tokens=w.get("track_all_tokens", True),
                        tokens_to_track=w.get("tokens_to_track", []),
                        enabled=w.get("enabled", True),
                    )
                )

            return cls(
                wallets=wallets,
                min_trade_size_usd=data.get("min_trade_size_usd", 5000),
                large_trade_threshold_usd=data.get("large_trade_threshold_usd", 50000),
                accumulation_window_hours=data.get("accumulation_window_hours", 24),
                copy_trade_enabled=data.get("copy_trade_enabled", False),
                copy_trade_min_wallet_score=data.get("copy_trade_min_wallet_score", 50),
            )

        except Exception as e:
            logger.error(f"Failed to load whale tracker config: {e}")
            return cls()


class WhaleTracker:
    """
    Whale wallet tracker for real-time monitoring.

    Features:
    - Tracks token balance changes for configured wallets
    - Detects large buys/sells
    - Identifies accumulation/distribution patterns
    - Emits copy trading signals
    """

    def __init__(self, geyser_client: GeyserClient, config: WhaleTrackerConfig):
        """Initialize the whale tracker."""
        self.geyser_client = geyser_client
        self.config = config

        # State
        self._tracked_wallets: Dict[str, WalletConfig] = {}
        self._wallet_subscriptions: Dict[str, str] = {}  # wallet -> subscription_id
        self._wallet_balances: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._activity_history: Dict[str, List[WalletActivity]] = defaultdict(list)
        self._wallet_scores: Dict[str, WalletScore] = {}
        self._running = False

        # Initialize tracked wallets
        for wallet in config.wallets:
            if wallet.enabled:
                self._tracked_wallets[wallet.address] = wallet

        # Callbacks
        self._event_callbacks: List[Callable[[WhaleEvent], None]] = []
        self._copy_trade_callbacks: List[Callable[[CopyTradeSignal], None]] = []

        # Metrics
        self._updates_processed: int = 0
        self._events_emitted: int = 0

        # Price cache
        self._price_cache: Dict[str, float] = {}
        self._price_cache_time: Dict[str, float] = {}

    async def start(self) -> None:
        """Start tracking whale wallets."""
        if self._running:
            return

        self._running = True

        # Register handler with Geyser client
        self.geyser_client.on_account_update(self._handle_account_update)

        # Subscribe to each wallet's token accounts
        for address, wallet in self._tracked_wallets.items():
            try:
                # Subscribe to the wallet address and its token accounts
                sub_id = await self.geyser_client.subscribe_accounts([address])
                self._wallet_subscriptions[address] = sub_id
                logger.info(f"Subscribed to wallet: {wallet.label or address[:8]}...")
            except Exception as e:
                logger.error(f"Failed to subscribe to {address}: {e}")

        logger.info(f"Whale tracker started, tracking {len(self._tracked_wallets)} wallets")

    async def stop(self) -> None:
        """Stop tracking."""
        self._running = False

        for address, sub_id in list(self._wallet_subscriptions.items()):
            try:
                await self.geyser_client.unsubscribe(sub_id)
            except Exception as e:
                logger.error(f"Failed to unsubscribe {address}: {e}")

        self._wallet_subscriptions.clear()
        logger.info("Whale tracker stopped")

    async def add_wallet(self, wallet: WalletConfig) -> None:
        """Add a wallet to track."""
        if wallet.address in self._tracked_wallets:
            return

        self._tracked_wallets[wallet.address] = wallet

        if self._running:
            try:
                sub_id = await self.geyser_client.subscribe_accounts([wallet.address])
                self._wallet_subscriptions[wallet.address] = sub_id
                logger.info(f"Added wallet: {wallet.label or wallet.address[:8]}...")
            except Exception as e:
                logger.error(f"Failed to subscribe to new wallet: {e}")

    async def remove_wallet(self, address: str) -> None:
        """Remove a wallet from tracking."""
        if address not in self._tracked_wallets:
            return

        del self._tracked_wallets[address]

        if address in self._wallet_subscriptions:
            try:
                await self.geyser_client.unsubscribe(self._wallet_subscriptions[address])
            except Exception as e:
                logger.error(f"Failed to unsubscribe: {e}")
            del self._wallet_subscriptions[address]

        logger.info(f"Removed wallet: {address[:8]}...")

    def on_whale_event(self, callback: Callable[[WhaleEvent], None]) -> None:
        """Register callback for whale events."""
        self._event_callbacks.append(callback)

    def on_copy_trade_signal(self, callback: Callable[[CopyTradeSignal], None]) -> None:
        """Register callback for copy trade signals."""
        self._copy_trade_callbacks.append(callback)

    async def _handle_account_update(self, update: AccountUpdate) -> None:
        """Handle account update from Geyser."""
        self._updates_processed += 1

        # Check if this is a token account for a tracked wallet
        if update.owner not in [TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID]:
            return

        # Parse token account to get wallet and mint
        token_info = self._parse_token_account(update.data)
        if not token_info:
            return

        wallet_address = token_info["owner"]
        token_mint = token_info["mint"]
        new_balance = token_info["amount"]

        # Check if this wallet is tracked
        if wallet_address not in self._tracked_wallets:
            return

        # Handle balance change
        await self._handle_balance_change(
            wallet_address=wallet_address,
            token_mint=token_mint,
            new_balance=new_balance,
            slot=update.slot,
        )

    def _parse_token_account(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse SPL token account data."""
        if len(data) < 165:
            return None

        try:
            import struct

            # Token account layout:
            # 32 bytes: mint
            # 32 bytes: owner
            # 8 bytes: amount
            # ... rest

            mint = data[0:32]
            owner = data[32:64]
            amount = struct.unpack("<Q", data[64:72])[0]

            import base58

            return {
                "mint": base58.b58encode(mint).decode("ascii"),
                "owner": base58.b58encode(owner).decode("ascii"),
                "amount": amount,
            }

        except Exception as e:
            logger.debug(f"Failed to parse token account: {e}")
            return None

    async def _handle_balance_change(
        self,
        wallet_address: str,
        token_mint: str,
        new_balance: int,
        slot: int,
    ) -> None:
        """Handle a token balance change."""
        wallet = self._tracked_wallets.get(wallet_address)
        if not wallet:
            return

        # Check if we should track this token
        if not wallet.track_all_tokens and token_mint not in wallet.tokens_to_track:
            return

        # Get previous balance
        prev_balance_info = self._wallet_balances[wallet_address].get(token_mint, {})
        prev_balance = prev_balance_info.get("amount", 0)
        prev_slot = prev_balance_info.get("slot", 0)

        # Skip if no change or same slot
        if new_balance == prev_balance or slot <= prev_slot:
            return

        # Calculate change
        amount_change = new_balance - prev_balance
        direction = TradeDirection.BUY if amount_change > 0 else TradeDirection.SELL

        # Get token price
        price_usd = await self._get_token_price_usd(token_mint)
        value_usd = abs(amount_change / 1e9 * price_usd) if price_usd else 0

        # Check if trade meets minimum threshold
        if value_usd < self.config.min_trade_size_usd:
            # Update balance but don't emit event
            self._wallet_balances[wallet_address][token_mint] = {
                "amount": new_balance,
                "slot": slot,
            }
            return

        # Determine event type
        is_large = value_usd >= self.config.large_trade_threshold_usd
        is_new_position = prev_balance == 0 and amount_change > 0
        is_closed_position = new_balance == 0 and prev_balance > 0

        # Create activity record
        activity = WalletActivity(
            wallet_address=wallet_address,
            token_mint=token_mint,
            token_symbol=self._get_token_symbol(token_mint),
            amount_change=amount_change,
            direction=direction,
            slot=slot,
            signature="",  # Would need transaction lookup
            estimated_value_usd=value_usd,
        )

        # Record activity
        self._activity_history[wallet_address].append(activity)

        # Trim history
        if len(self._activity_history[wallet_address]) > 1000:
            self._activity_history[wallet_address] = self._activity_history[
                wallet_address
            ][-500:]

        # Emit appropriate event
        if is_new_position:
            await self._emit_event(
                WhaleEvent(
                    event_type=WhaleEventType.NEW_POSITION,
                    wallet_address=wallet_address,
                    wallet_label=wallet.label,
                    wallet_category=wallet.category,
                    token_mint=token_mint,
                    token_symbol=activity.token_symbol,
                    amount=amount_change,
                    value_usd=value_usd,
                    slot=slot,
                    timestamp=time.time(),
                )
            )
        elif is_closed_position:
            await self._emit_event(
                WhaleEvent(
                    event_type=WhaleEventType.POSITION_CLOSED,
                    wallet_address=wallet_address,
                    wallet_label=wallet.label,
                    wallet_category=wallet.category,
                    token_mint=token_mint,
                    token_symbol=activity.token_symbol,
                    amount=abs(amount_change),
                    value_usd=value_usd,
                    slot=slot,
                    timestamp=time.time(),
                )
            )
        elif is_large:
            event_type = (
                WhaleEventType.LARGE_BUY
                if direction == TradeDirection.BUY
                else WhaleEventType.LARGE_SELL
            )
            await self._emit_event(
                WhaleEvent(
                    event_type=event_type,
                    wallet_address=wallet_address,
                    wallet_label=wallet.label,
                    wallet_category=wallet.category,
                    token_mint=token_mint,
                    token_symbol=activity.token_symbol,
                    amount=abs(amount_change),
                    value_usd=value_usd,
                    slot=slot,
                    timestamp=time.time(),
                )
            )

        # Check for accumulation/distribution patterns
        if self._detect_accumulation(wallet_address, token_mint):
            await self._emit_event(
                WhaleEvent(
                    event_type=WhaleEventType.ACCUMULATION,
                    wallet_address=wallet_address,
                    wallet_label=wallet.label,
                    wallet_category=wallet.category,
                    token_mint=token_mint,
                    token_symbol=activity.token_symbol,
                    amount=abs(amount_change),
                    value_usd=value_usd,
                    slot=slot,
                    timestamp=time.time(),
                    data={"pattern": "accumulation"},
                )
            )

        if self._detect_distribution(wallet_address, token_mint):
            await self._emit_event(
                WhaleEvent(
                    event_type=WhaleEventType.DISTRIBUTION,
                    wallet_address=wallet_address,
                    wallet_label=wallet.label,
                    wallet_category=wallet.category,
                    token_mint=token_mint,
                    token_symbol=activity.token_symbol,
                    amount=abs(amount_change),
                    value_usd=value_usd,
                    slot=slot,
                    timestamp=time.time(),
                    data={"pattern": "distribution"},
                )
            )

        # Check for copy trade signal
        if self.config.copy_trade_enabled and direction == TradeDirection.BUY:
            await self._check_copy_trade_signal(
                wallet_address=wallet_address,
                token_mint=token_mint,
                token_symbol=activity.token_symbol,
                value_usd=value_usd,
            )

        # Update balance
        self._wallet_balances[wallet_address][token_mint] = {
            "amount": new_balance,
            "slot": slot,
        }

    def _detect_accumulation(self, wallet_address: str, token_mint: str) -> bool:
        """Detect accumulation pattern."""
        history = self._activity_history.get(wallet_address, [])
        if len(history) < self.config.accumulation_trade_count:
            return False

        # Get recent activity for this token
        window_seconds = self.config.accumulation_window_hours * 3600
        cutoff = time.time() - window_seconds

        recent_buys = [
            a
            for a in history
            if a.token_mint == token_mint
            and a.direction == TradeDirection.BUY
            and a.timestamp > cutoff
        ]

        return len(recent_buys) >= self.config.accumulation_trade_count

    def _detect_distribution(self, wallet_address: str, token_mint: str) -> bool:
        """Detect distribution pattern."""
        history = self._activity_history.get(wallet_address, [])
        if len(history) < self.config.accumulation_trade_count:
            return False

        window_seconds = self.config.accumulation_window_hours * 3600
        cutoff = time.time() - window_seconds

        recent_sells = [
            a
            for a in history
            if a.token_mint == token_mint
            and a.direction == TradeDirection.SELL
            and a.timestamp > cutoff
        ]

        return len(recent_sells) >= self.config.accumulation_trade_count

    async def _check_copy_trade_signal(
        self,
        wallet_address: str,
        token_mint: str,
        token_symbol: str,
        value_usd: float,
    ) -> None:
        """Check if a copy trade signal should be emitted."""
        score = self._wallet_scores.get(wallet_address)
        if not score:
            return

        ranking = score.get_ranking_score()
        if ranking < self.config.copy_trade_min_wallet_score:
            return

        # Emit copy trade signal
        signal = CopyTradeSignal(
            wallet_address=wallet_address,
            wallet_score=score,
            token_mint=token_mint,
            token_symbol=token_symbol,
            direction=TradeDirection.BUY,
            value_usd=value_usd,
            confidence=ranking / 100.0,
            timestamp=time.time(),
        )

        for callback in self._copy_trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"Copy trade callback error: {e}")

    async def _emit_event(self, event: WhaleEvent) -> None:
        """Emit whale event to all callbacks."""
        self._events_emitted += 1

        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Whale event callback error: {e}")

    async def _get_token_price_usd(self, token_mint: str) -> float:
        """Get token price in USD."""
        # Check cache
        cache_ttl = 60  # 1 minute
        if token_mint in self._price_cache:
            if time.time() - self._price_cache_time.get(token_mint, 0) < cache_ttl:
                return self._price_cache[token_mint]

        # Try to get price from Jupiter
        try:
            from core.jupiter import get_token_price_in_usd

            price = get_token_price_in_usd(token_mint)
            if price:
                self._price_cache[token_mint] = price
                self._price_cache_time[token_mint] = time.time()
                return price
        except Exception:
            pass

        return 0.0

    def _get_token_symbol(self, token_mint: str) -> str:
        """Get token symbol from mint address."""
        # Known tokens
        known = {
            "So11111111111111111111111111111111111111112": "SOL",
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
            "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V": "USDT",
        }
        return known.get(token_mint, token_mint[:8] + "...")

    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        return {
            "wallets_tracked": len(self._tracked_wallets),
            "updates_processed": self._updates_processed,
            "events_emitted": self._events_emitted,
            "subscriptions": len(self._wallet_subscriptions),
        }

    def get_wallet_activity(
        self, wallet_address: str, limit: int = 100
    ) -> List[WalletActivity]:
        """Get recent activity for a wallet."""
        return self._activity_history.get(wallet_address, [])[-limit:]

    def get_top_wallets(self, n: int = 10) -> List[WalletScore]:
        """Get top-scoring wallets."""
        sorted_scores = sorted(
            self._wallet_scores.values(),
            key=lambda s: s.get_ranking_score(),
            reverse=True,
        )
        return sorted_scores[:n]

    def update_wallet_score(self, address: str, score: WalletScore) -> None:
        """Update score for a wallet."""
        self._wallet_scores[address] = score
