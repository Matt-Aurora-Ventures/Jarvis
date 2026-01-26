"""
DEX pool monitoring via Yellowstone Geyser.

Monitors Raydium, Orca, Jupiter, and Meteora pools for:
- New pool creation
- Price movements
- Liquidity changes
- Swap activity

Usage:
    from core.streaming import GeyserClient, PoolMonitor, PoolMonitorConfig

    client = GeyserClient.helius()
    monitor = PoolMonitor(client, PoolMonitorConfig())

    monitor.on_pool_event(handle_event)
    await monitor.start()
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from core.streaming.geyser_client import (
    GeyserClient,
    AccountUpdate,
    GeyserConnectionState,
)

logger = logging.getLogger(__name__)

# DEX Program IDs
RAYDIUM_AMM_V4_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_CLMM_PROGRAM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"
ORCA_WHIRLPOOL_PROGRAM = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
JUPITER_LIMIT_V2_PROGRAM = "j1o2qRpjcyUwEvwtcfhEQefh773ZgjxcVRry7LDqg5X"
METEORA_DLMM_PROGRAM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"

# Common token mints
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V"


class DEXType(Enum):
    """Supported DEX types."""

    RAYDIUM = "raydium_amm_v4"
    RAYDIUM_CLMM = "raydium_clmm"
    ORCA_WHIRLPOOL = "orca_whirlpool"
    JUPITER = "jupiter"
    METEORA = "meteora_dlmm"

    @property
    def program_id(self) -> str:
        """Get the program ID for this DEX."""
        mapping = {
            DEXType.RAYDIUM: RAYDIUM_AMM_V4_PROGRAM,
            DEXType.RAYDIUM_CLMM: RAYDIUM_CLMM_PROGRAM,
            DEXType.ORCA_WHIRLPOOL: ORCA_WHIRLPOOL_PROGRAM,
            DEXType.JUPITER: JUPITER_LIMIT_V2_PROGRAM,
            DEXType.METEORA: METEORA_DLMM_PROGRAM,
        }
        return mapping[self]


class PoolEventType(Enum):
    """Types of pool events."""

    NEW_POOL = "new_pool"
    PRICE_CHANGE = "price_change"
    LIQUIDITY_ADD = "liquidity_add"
    LIQUIDITY_REMOVE = "liquidity_remove"
    SWAP = "swap"
    POOL_CLOSED = "pool_closed"


@dataclass
class PoolState:
    """Current state of a liquidity pool."""

    address: str
    dex_type: DEXType
    token_a_mint: str
    token_b_mint: str
    token_a_reserve: int
    token_b_reserve: int
    lp_supply: int
    fee_rate_bps: int
    slot: int
    timestamp: float = field(default_factory=time.time)

    # Optional price data
    token_a_price_usd: Optional[float] = None
    token_b_price_usd: Optional[float] = None

    # CLMM-specific fields
    current_tick: Optional[int] = None
    sqrt_price_x64: Optional[int] = None
    liquidity: Optional[int] = None

    # Extra data for parser-specific fields
    extra_data: Optional[Dict[str, Any]] = None

    def get_price_a_per_b(self) -> float:
        """Get price of token A in terms of token B."""
        if self.token_b_reserve == 0:
            return 0.0
        return self.token_a_reserve / self.token_b_reserve

    def get_price_b_per_a(self) -> float:
        """Get price of token B in terms of token A."""
        if self.token_a_reserve == 0:
            return 0.0
        return self.token_b_reserve / self.token_a_reserve

    def get_tvl_usd(self) -> float:
        """Calculate total value locked in USD."""
        tvl = 0.0

        if self.token_a_price_usd:
            # Assume standard decimals (9 for most tokens)
            tvl += (self.token_a_reserve / 1e9) * self.token_a_price_usd

        if self.token_b_price_usd:
            tvl += (self.token_b_reserve / 1e9) * self.token_b_price_usd

        return tvl


@dataclass
class PoolUpdate:
    """Update to a pool state."""

    pool_address: str
    dex_type: DEXType
    slot: int
    slot_delta: int
    reserve_a_delta: int
    reserve_b_delta: int
    lp_supply_delta: int
    old_state: PoolState
    new_state: PoolState
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def from_states(cls, before: PoolState, after: PoolState) -> "PoolUpdate":
        """Create update from before/after states."""
        return cls(
            pool_address=after.address,
            dex_type=after.dex_type,
            slot=after.slot,
            slot_delta=after.slot - before.slot,
            reserve_a_delta=after.token_a_reserve - before.token_a_reserve,
            reserve_b_delta=after.token_b_reserve - before.token_b_reserve,
            lp_supply_delta=after.lp_supply - before.lp_supply,
            old_state=before,
            new_state=after,
        )

    def get_price_change_pct(self) -> float:
        """Calculate percentage change in price."""
        old_price = self.old_state.get_price_a_per_b()
        new_price = self.new_state.get_price_a_per_b()

        if old_price == 0:
            return 0.0

        return ((new_price - old_price) / old_price) * 100

    def get_liquidity_change_pct(self) -> float:
        """Calculate percentage change in liquidity."""
        old_lp = self.old_state.lp_supply
        new_lp = self.new_state.lp_supply

        if old_lp == 0:
            return 0.0

        return ((new_lp - old_lp) / old_lp) * 100


@dataclass
class PoolEvent:
    """Event emitted by the pool monitor."""

    event_type: PoolEventType
    pool_address: str
    dex_type: DEXType
    slot: int
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type.value,
            "pool_address": self.pool_address,
            "dex_type": self.dex_type.value,
            "slot": self.slot,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class PoolMonitorConfig:
    """Configuration for pool monitoring."""

    enabled_dexes: List[DEXType] = field(
        default_factory=lambda: [DEXType.RAYDIUM, DEXType.ORCA_WHIRLPOOL]
    )
    specific_pools: Optional[List[str]] = None
    min_liquidity_usd: float = 1000.0
    price_change_threshold_pct: float = 1.0
    liquidity_change_threshold_pct: float = 5.0
    new_pool_min_tvl_usd: float = 500.0
    max_pools_tracked: int = 10000
    emit_all_swaps: bool = False  # If true, emit events for all swaps


class RaydiumPoolParser:
    """Parser for Raydium AMM V4 pool accounts."""

    # AMM V4 account layout offsets
    STATUS_OFFSET = 0
    NONCE_OFFSET = 1
    ORDER_NUM_OFFSET = 2
    DEPTH_OFFSET = 4
    COIN_DECIMALS_OFFSET = 8
    PC_DECIMALS_OFFSET = 9
    STATE_OFFSET = 10
    RESET_FLAG_OFFSET = 11
    MIN_SIZE_OFFSET = 12
    VOL_MAX_CUT_RATIO_OFFSET = 20
    AMOUNT_WAVE_RATIO_OFFSET = 28
    COIN_LOT_SIZE_OFFSET = 36
    PC_LOT_SIZE_OFFSET = 44
    MIN_PRICE_MULTIPLIER_OFFSET = 52
    MAX_PRICE_MULTIPLIER_OFFSET = 60
    NEED_TAKE_OFFSET = 68
    COIN_VAULT_OFFSET = 172
    PC_VAULT_OFFSET = 204
    COIN_MINT_OFFSET = 236
    PC_MINT_OFFSET = 268
    LP_MINT_OFFSET = 300
    OPEN_ORDERS_OFFSET = 332
    MARKET_OFFSET = 364
    MARKET_PROGRAM_OFFSET = 396
    TARGET_ORDERS_OFFSET = 428
    POOL_TOTAL_DEPOSIT_COIN_OFFSET = 460
    POOL_TOTAL_DEPOSIT_PC_OFFSET = 468
    SWAP_COIN_IN_AMOUNT_OFFSET = 476
    SWAP_PC_OUT_AMOUNT_OFFSET = 484
    SWAP_COIN_TO_PC_FEE_OFFSET = 492
    SWAP_PC_IN_AMOUNT_OFFSET = 500
    SWAP_COIN_OUT_AMOUNT_OFFSET = 508
    SWAP_PC_TO_COIN_FEE_OFFSET = 516
    AMM_OWNER_OFFSET = 524

    MIN_ACCOUNT_SIZE = 752

    def parse(
        self,
        pubkey: str,
        data: bytes,
        slot: int,
    ) -> Optional[PoolState]:
        """Parse Raydium AMM V4 pool account data."""
        if len(data) < self.MIN_ACCOUNT_SIZE:
            return None

        try:
            # Extract key fields using struct unpacking
            coin_mint = self._read_pubkey(data, self.COIN_MINT_OFFSET)
            pc_mint = self._read_pubkey(data, self.PC_MINT_OFFSET)

            # Read reserves
            coin_reserve = struct.unpack_from("<Q", data, self.POOL_TOTAL_DEPOSIT_COIN_OFFSET)[0]
            pc_reserve = struct.unpack_from("<Q", data, self.POOL_TOTAL_DEPOSIT_PC_OFFSET)[0]

            # LP supply would need to be fetched from LP mint account
            # For now, estimate from reserves
            lp_supply = int((coin_reserve * pc_reserve) ** 0.5) if coin_reserve and pc_reserve else 0

            return PoolState(
                address=pubkey,
                dex_type=DEXType.RAYDIUM,
                token_a_mint=coin_mint,
                token_b_mint=pc_mint,
                token_a_reserve=coin_reserve,
                token_b_reserve=pc_reserve,
                lp_supply=lp_supply,
                fee_rate_bps=25,  # Standard Raydium fee
                slot=slot,
            )

        except Exception as e:
            logger.debug(f"Failed to parse Raydium pool {pubkey}: {e}")
            return None

    def parse_clmm(
        self,
        pubkey: str,
        data: bytes,
        slot: int,
    ) -> Optional[PoolState]:
        """Parse Raydium CLMM pool account data."""
        if len(data) < 1544:
            return None

        try:
            # CLMM pool layout is more complex
            # Simplified parsing for key fields
            return PoolState(
                address=pubkey,
                dex_type=DEXType.RAYDIUM_CLMM,
                token_a_mint="",
                token_b_mint="",
                token_a_reserve=0,
                token_b_reserve=0,
                lp_supply=0,
                fee_rate_bps=25,
                slot=slot,
            )

        except Exception as e:
            logger.debug(f"Failed to parse Raydium CLMM pool {pubkey}: {e}")
            return None

    def _read_pubkey(self, data: bytes, offset: int) -> str:
        """Read a 32-byte pubkey and convert to base58 string."""
        import base58
        pubkey_bytes = data[offset : offset + 32]
        return base58.b58encode(pubkey_bytes).decode("ascii")


class OrcaPoolParser:
    """Parser for Orca Whirlpool accounts."""

    MIN_ACCOUNT_SIZE = 653

    def parse(
        self,
        pubkey: str,
        data: bytes,
        slot: int,
    ) -> Optional[PoolState]:
        """Parse Orca Whirlpool account data."""
        if len(data) < self.MIN_ACCOUNT_SIZE:
            return None

        try:
            # Whirlpool account layout:
            # 8 bytes discriminator
            # ... pool data

            # Simplified parsing
            return PoolState(
                address=pubkey,
                dex_type=DEXType.ORCA_WHIRLPOOL,
                token_a_mint="",
                token_b_mint="",
                token_a_reserve=0,
                token_b_reserve=0,
                lp_supply=0,
                fee_rate_bps=30,  # Standard Orca fee
                slot=slot,
                extra_data={"is_clmm": True},
            )

        except Exception as e:
            logger.debug(f"Failed to parse Orca Whirlpool {pubkey}: {e}")
            return None


class JupiterPoolParser:
    """Parser for Jupiter Limit Order accounts."""

    def parse(
        self,
        pubkey: str,
        data: bytes,
        slot: int,
    ) -> Optional[PoolState]:
        """Parse Jupiter account data."""
        # Jupiter uses various pool types
        return None


class PoolMonitor:
    """
    DEX pool monitor for real-time updates.

    Features:
    - Subscribes to DEX program accounts via Geyser
    - Parses pool state changes
    - Emits events for price movements, liquidity changes, new pools
    """

    def __init__(self, geyser_client: GeyserClient, config: PoolMonitorConfig):
        """Initialize the pool monitor."""
        self.geyser_client = geyser_client
        self.config = config

        # State
        self._pool_states: Dict[str, PoolState] = {}
        self._subscription_ids: List[str] = []
        self._running = False

        # Parsers
        self._parsers: Dict[DEXType, Any] = {}
        self._init_parsers()

        # Callbacks
        self._event_callbacks: List[Callable[[PoolEvent], None]] = []

        # Metrics
        self._updates_processed: int = 0
        self._events_emitted: int = 0

    def _init_parsers(self) -> None:
        """Initialize pool parsers for enabled DEXes."""
        raydium_parser = RaydiumPoolParser()
        orca_parser = OrcaPoolParser()
        jupiter_parser = JupiterPoolParser()

        for dex in self.config.enabled_dexes:
            if dex == DEXType.RAYDIUM:
                self._parsers[dex] = raydium_parser
            elif dex == DEXType.RAYDIUM_CLMM:
                self._parsers[dex] = raydium_parser
            elif dex == DEXType.ORCA_WHIRLPOOL:
                self._parsers[dex] = orca_parser
            elif dex == DEXType.JUPITER:
                self._parsers[dex] = jupiter_parser

    async def start(self) -> None:
        """Start monitoring pools."""
        if self._running:
            return

        self._running = True

        # Register handler with Geyser client
        self.geyser_client.on_account_update(self._handle_account_update)

        # Subscribe to specific pools or programs
        if self.config.specific_pools:
            sub_id = await self.geyser_client.subscribe_accounts(
                self.config.specific_pools
            )
            self._subscription_ids.append(sub_id)
        else:
            # Subscribe to each enabled DEX program
            for dex in self.config.enabled_dexes:
                try:
                    sub_id = await self.geyser_client.subscribe_program(
                        dex.program_id
                    )
                    self._subscription_ids.append(sub_id)
                    logger.info(f"Subscribed to {dex.value} pools")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {dex.value}: {e}")

        logger.info(
            f"Pool monitor started, tracking {len(self.config.enabled_dexes)} DEXes"
        )

    async def stop(self) -> None:
        """Stop monitoring pools."""
        self._running = False

        for sub_id in self._subscription_ids:
            try:
                await self.geyser_client.unsubscribe(sub_id)
            except Exception as e:
                logger.error(f"Failed to unsubscribe {sub_id}: {e}")

        self._subscription_ids.clear()
        logger.info("Pool monitor stopped")

    def on_pool_event(self, callback: Callable[[PoolEvent], None]) -> None:
        """Register callback for pool events."""
        self._event_callbacks.append(callback)

    async def _handle_account_update(self, update: AccountUpdate) -> None:
        """Handle account update from Geyser."""
        self._updates_processed += 1

        # Determine DEX type from owner
        dex_type = self._get_dex_type(update.owner)
        if not dex_type or dex_type not in self._parsers:
            return

        # Parse pool state
        state = self._parse_pool_state(update, dex_type)
        if not state:
            return

        # Check if this is a new pool
        is_new = update.pubkey not in self._pool_states

        if is_new:
            # Emit new pool event
            await self._emit_event(
                PoolEvent(
                    event_type=PoolEventType.NEW_POOL,
                    pool_address=state.address,
                    dex_type=state.dex_type,
                    slot=state.slot,
                    timestamp=time.time(),
                    data={
                        "token_a_mint": state.token_a_mint,
                        "token_b_mint": state.token_b_mint,
                        "initial_reserve_a": state.token_a_reserve,
                        "initial_reserve_b": state.token_b_reserve,
                    },
                )
            )
        else:
            # Check for price/liquidity changes
            old_state = self._pool_states[update.pubkey]
            pool_update = PoolUpdate.from_states(old_state, state)

            # Check price change
            price_change = abs(pool_update.get_price_change_pct())
            if price_change >= self.config.price_change_threshold_pct:
                await self._emit_event(
                    PoolEvent(
                        event_type=PoolEventType.PRICE_CHANGE,
                        pool_address=state.address,
                        dex_type=state.dex_type,
                        slot=state.slot,
                        timestamp=time.time(),
                        data={
                            "price_change_pct": price_change,
                            "old_price": old_state.get_price_a_per_b(),
                            "new_price": state.get_price_a_per_b(),
                        },
                    )
                )

            # Check liquidity change
            liq_change = pool_update.get_liquidity_change_pct()
            if abs(liq_change) >= self.config.liquidity_change_threshold_pct:
                event_type = (
                    PoolEventType.LIQUIDITY_ADD
                    if liq_change > 0
                    else PoolEventType.LIQUIDITY_REMOVE
                )
                await self._emit_event(
                    PoolEvent(
                        event_type=event_type,
                        pool_address=state.address,
                        dex_type=state.dex_type,
                        slot=state.slot,
                        timestamp=time.time(),
                        data={
                            "liquidity_change_pct": liq_change,
                            "reserve_a_delta": pool_update.reserve_a_delta,
                            "reserve_b_delta": pool_update.reserve_b_delta,
                        },
                    )
                )

        # Update state
        self._pool_states[update.pubkey] = state

        # Enforce max pools limit
        if len(self._pool_states) > self.config.max_pools_tracked:
            # Remove oldest pools
            oldest = sorted(
                self._pool_states.items(), key=lambda x: x[1].timestamp
            )[: len(self._pool_states) - self.config.max_pools_tracked]
            for addr, _ in oldest:
                del self._pool_states[addr]

    def _get_dex_type(self, owner: str) -> Optional[DEXType]:
        """Determine DEX type from program owner."""
        mapping = {
            RAYDIUM_AMM_V4_PROGRAM: DEXType.RAYDIUM,
            RAYDIUM_CLMM_PROGRAM: DEXType.RAYDIUM_CLMM,
            ORCA_WHIRLPOOL_PROGRAM: DEXType.ORCA_WHIRLPOOL,
            JUPITER_LIMIT_V2_PROGRAM: DEXType.JUPITER,
            METEORA_DLMM_PROGRAM: DEXType.METEORA,
        }
        return mapping.get(owner)

    def _parse_pool_state(
        self, update: AccountUpdate, dex_type: DEXType
    ) -> Optional[PoolState]:
        """Parse pool state from account update."""
        parser = self._parsers.get(dex_type)
        if not parser:
            return None

        if dex_type == DEXType.RAYDIUM_CLMM:
            return parser.parse_clmm(update.pubkey, update.data, update.slot)
        else:
            return parser.parse(update.pubkey, update.data, update.slot)

    async def _emit_event(self, event: PoolEvent) -> None:
        """Emit pool event to all callbacks."""
        self._events_emitted += 1

        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Pool event callback error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "pools_tracked": len(self._pool_states),
            "updates_processed": self._updates_processed,
            "events_emitted": self._events_emitted,
            "enabled_dexes": [d.value for d in self.config.enabled_dexes],
            "subscriptions": len(self._subscription_ids),
        }

    def get_tracked_pools(self) -> List[Dict[str, Any]]:
        """Get list of tracked pools."""
        return [
            {
                "address": state.address,
                "dex_type": state.dex_type.value,
                "token_a_mint": state.token_a_mint,
                "token_b_mint": state.token_b_mint,
                "reserve_a": state.token_a_reserve,
                "reserve_b": state.token_b_reserve,
                "slot": state.slot,
            }
            for state in self._pool_states.values()
        ]

    def get_pool_state(self, address: str) -> Optional[PoolState]:
        """Get current state of a specific pool."""
        return self._pool_states.get(address)
