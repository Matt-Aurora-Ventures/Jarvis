"""
Tests for DEX pool monitoring via Yellowstone Geyser.

Tests cover:
- Pool subscription management for Raydium, Orca, Jupiter
- Pool state parsing and change detection
- New pool discovery
- Price movement detection
- Liquidity change events
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Import the module under test (will fail until implemented)
try:
    from core.streaming.pool_monitor import (
        PoolMonitor,
        PoolMonitorConfig,
        DEXType,
        PoolState,
        PoolUpdate,
        PoolEvent,
        PoolEventType,
        RaydiumPoolParser,
        OrcaPoolParser,
        JupiterPoolParser,
    )
    from core.streaming.geyser_client import GeyserClient, AccountUpdate
    HAS_POOL_MONITOR = True
except ImportError:
    HAS_POOL_MONITOR = False
    PoolMonitor = None
    PoolMonitorConfig = None
    DEXType = None
    PoolState = None
    PoolUpdate = None
    PoolEvent = None
    PoolEventType = None
    RaydiumPoolParser = None
    OrcaPoolParser = None
    JupiterPoolParser = None


pytestmark = pytest.mark.skipif(not HAS_POOL_MONITOR, reason="pool_monitor not implemented yet")


# Known program IDs
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
JUPITER_LIMIT_V2 = "j1o2qRpjcyUwEvwtcfhEQefh773ZgjxcVRry7LDqg5X"


class TestDEXType:
    """Tests for DEX type enum."""

    def test_dex_types(self):
        """Should have all supported DEX types."""
        assert DEXType.RAYDIUM is not None
        assert DEXType.RAYDIUM_CLMM is not None
        assert DEXType.ORCA_WHIRLPOOL is not None
        assert DEXType.JUPITER is not None
        assert DEXType.METEORA is not None

    def test_dex_program_ids(self):
        """Should map to correct program IDs."""
        assert DEXType.RAYDIUM.program_id == RAYDIUM_AMM_V4
        assert DEXType.ORCA_WHIRLPOOL.program_id == ORCA_WHIRLPOOL


class TestPoolMonitorConfig:
    """Tests for PoolMonitorConfig."""

    def test_config_defaults(self):
        """Config should have sensible defaults."""
        config = PoolMonitorConfig()

        assert config.enabled_dexes == [DEXType.RAYDIUM, DEXType.ORCA_WHIRLPOOL]
        assert config.min_liquidity_usd == 1000
        assert config.price_change_threshold_pct == 1.0
        assert config.liquidity_change_threshold_pct == 5.0
        assert config.new_pool_min_tvl_usd == 500

    def test_config_custom_dexes(self):
        """Should accept custom DEX list."""
        config = PoolMonitorConfig(
            enabled_dexes=[DEXType.RAYDIUM],
            min_liquidity_usd=5000,
        )

        assert config.enabled_dexes == [DEXType.RAYDIUM]
        assert config.min_liquidity_usd == 5000

    def test_config_with_pool_filter(self):
        """Should support pool address filtering."""
        pools = ["Pool1...", "Pool2..."]
        config = PoolMonitorConfig(specific_pools=pools)

        assert config.specific_pools == pools


class TestPoolState:
    """Tests for PoolState dataclass."""

    def test_pool_state_creation(self):
        """Should create pool state with required fields."""
        state = PoolState(
            address="PoolAddress...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="TokenA...",
            token_b_mint="TokenB...",
            token_a_reserve=1000000000,
            token_b_reserve=500000000,
            lp_supply=750000000,
            fee_rate_bps=25,
            slot=12345678,
        )

        assert state.address == "PoolAddress..."
        assert state.dex_type == DEXType.RAYDIUM
        assert state.token_a_reserve == 1000000000

    def test_pool_state_price_calculation(self):
        """Should calculate price from reserves."""
        state = PoolState(
            address="PoolAddress...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="TokenA...",
            token_b_mint="TokenB...",
            token_a_reserve=1000000000,  # 1 token A
            token_b_reserve=500000000,   # 0.5 token B
            lp_supply=750000000,
            fee_rate_bps=25,
            slot=12345678,
        )

        # Price of A in terms of B
        price = state.get_price_a_per_b()
        assert price == pytest.approx(2.0, rel=0.01)  # 1A = 2B

    def test_pool_state_tvl_calculation(self):
        """Should calculate TVL when price data available."""
        state = PoolState(
            address="PoolAddress...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="So11111111111111111111111111111111111111112",  # SOL
            token_b_mint="TokenB...",
            token_a_reserve=10_000_000_000,  # 10 SOL
            token_b_reserve=500000000,
            lp_supply=750000000,
            fee_rate_bps=25,
            slot=12345678,
            token_a_price_usd=100.0,  # $100/SOL
            token_b_price_usd=0.001,
        )

        tvl = state.get_tvl_usd()
        # 10 SOL * $100 + token B value
        assert tvl > 1000


class TestPoolUpdate:
    """Tests for PoolUpdate dataclass."""

    def test_pool_update_from_states(self):
        """Should create update from before/after states."""
        before = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1000,
            token_b_reserve=500,
            lp_supply=750,
            fee_rate_bps=25,
            slot=100,
        )
        after = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1100,  # +10%
            token_b_reserve=450,   # -10%
            lp_supply=750,
            fee_rate_bps=25,
            slot=101,
        )

        update = PoolUpdate.from_states(before, after)

        assert update.pool_address == "Pool..."
        assert update.reserve_a_delta == 100
        assert update.reserve_b_delta == -50
        assert update.slot_delta == 1

    def test_pool_update_price_change(self):
        """Should calculate price change percentage."""
        before = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1000,
            token_b_reserve=1000,  # 1:1
            lp_supply=1000,
            fee_rate_bps=25,
            slot=100,
        )
        after = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1100,
            token_b_reserve=900,  # ~1.22:1
            lp_supply=1000,
            fee_rate_bps=25,
            slot=101,
        )

        update = PoolUpdate.from_states(before, after)
        price_change = update.get_price_change_pct()

        # Price changed from 1.0 to ~1.22, about 22% change
        assert abs(price_change) > 20


class TestPoolEventType:
    """Tests for pool event types."""

    def test_event_types(self):
        """Should have all expected event types."""
        assert PoolEventType.NEW_POOL is not None
        assert PoolEventType.PRICE_CHANGE is not None
        assert PoolEventType.LIQUIDITY_ADD is not None
        assert PoolEventType.LIQUIDITY_REMOVE is not None
        assert PoolEventType.SWAP is not None
        assert PoolEventType.POOL_CLOSED is not None


class TestPoolEvent:
    """Tests for PoolEvent dataclass."""

    def test_pool_event_creation(self):
        """Should create pool event with required fields."""
        event = PoolEvent(
            event_type=PoolEventType.PRICE_CHANGE,
            pool_address="Pool...",
            dex_type=DEXType.RAYDIUM,
            slot=12345678,
            timestamp=1234567890.0,
            data={"price_change_pct": 5.5},
        )

        assert event.event_type == PoolEventType.PRICE_CHANGE
        assert event.data["price_change_pct"] == 5.5


class TestRaydiumPoolParser:
    """Tests for Raydium pool account parsing."""

    def test_parse_amm_v4_pool(self):
        """Should parse Raydium AMM V4 pool account data."""
        # Mock Raydium AMM V4 account data (simplified)
        # Real format: https://github.com/raydium-io/raydium-amm/blob/master/program/src/state.rs
        mock_data = bytes(752)  # AMM V4 account size

        parser = RaydiumPoolParser()
        state = parser.parse(
            pubkey="PoolAddress...",
            data=mock_data,
            slot=12345678,
        )

        # Should return PoolState or None if invalid
        assert state is None or isinstance(state, PoolState)

    def test_parse_clmm_pool(self):
        """Should parse Raydium CLMM pool account data."""
        mock_data = bytes(1544)  # CLMM pool size

        parser = RaydiumPoolParser()
        state = parser.parse_clmm(
            pubkey="CLMMPool...",
            data=mock_data,
            slot=12345678,
        )

        assert state is None or isinstance(state, PoolState)

    def test_invalid_data_returns_none(self):
        """Should return None for invalid data."""
        parser = RaydiumPoolParser()

        # Too short
        state = parser.parse("Pool...", b"short", 1)
        assert state is None

        # Wrong discriminator (if applicable)
        state = parser.parse("Pool...", bytes(752), 1)
        # Should handle gracefully


class TestOrcaPoolParser:
    """Tests for Orca Whirlpool parsing."""

    def test_parse_whirlpool(self):
        """Should parse Orca Whirlpool account data."""
        mock_data = bytes(653)  # Whirlpool account size

        parser = OrcaPoolParser()
        state = parser.parse(
            pubkey="WhirlpoolAddress...",
            data=mock_data,
            slot=12345678,
        )

        assert state is None or isinstance(state, PoolState)

    def test_parse_whirlpool_with_ticks(self):
        """Should extract tick data for CLMM pools."""
        mock_data = bytes(653)

        parser = OrcaPoolParser()
        state = parser.parse(
            pubkey="WhirlpoolAddress...",
            data=mock_data,
            slot=12345678,
        )

        if state:
            assert hasattr(state, "current_tick") or state.extra_data is not None


class TestPoolMonitorInit:
    """Tests for PoolMonitor initialization."""

    def test_init_with_geyser_client(self):
        """Should initialize with GeyserClient."""
        mock_client = MagicMock(spec=GeyserClient)
        config = PoolMonitorConfig()

        monitor = PoolMonitor(mock_client, config)

        assert monitor.geyser_client == mock_client
        assert monitor.config == config

    def test_init_registers_parsers(self):
        """Should register parsers for enabled DEXes."""
        mock_client = MagicMock(spec=GeyserClient)
        config = PoolMonitorConfig(
            enabled_dexes=[DEXType.RAYDIUM, DEXType.ORCA_WHIRLPOOL]
        )

        monitor = PoolMonitor(mock_client, config)

        assert DEXType.RAYDIUM in monitor._parsers
        assert DEXType.ORCA_WHIRLPOOL in monitor._parsers


class TestPoolMonitorSubscription:
    """Tests for PoolMonitor subscription management."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_programs(self):
        """Should subscribe to DEX program accounts."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.subscribe_program = AsyncMock(return_value="sub-id")
        mock_client.state = MagicMock()

        config = PoolMonitorConfig(enabled_dexes=[DEXType.RAYDIUM])
        monitor = PoolMonitor(mock_client, config)

        await monitor.start()

        mock_client.subscribe_program.assert_called()
        assert RAYDIUM_AMM_V4 in str(mock_client.subscribe_program.call_args)

    @pytest.mark.asyncio
    async def test_start_with_specific_pools(self):
        """Should subscribe to specific pools if configured."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.subscribe_accounts = AsyncMock(return_value="sub-id")

        pools = ["Pool1...", "Pool2..."]
        config = PoolMonitorConfig(specific_pools=pools)
        monitor = PoolMonitor(mock_client, config)

        await monitor.start()

        mock_client.subscribe_accounts.assert_called_with(pools)

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self):
        """Should unsubscribe when stopped."""
        mock_client = MagicMock(spec=GeyserClient)
        mock_client.unsubscribe = AsyncMock()

        monitor = PoolMonitor(mock_client, PoolMonitorConfig())
        monitor._subscription_ids = ["sub-1", "sub-2"]

        await monitor.stop()

        assert mock_client.unsubscribe.call_count == 2


class TestPoolMonitorEventHandling:
    """Tests for PoolMonitor event handling."""

    @pytest.mark.asyncio
    async def test_handles_account_update(self):
        """Should process account updates from Geyser."""
        mock_client = MagicMock(spec=GeyserClient)
        monitor = PoolMonitor(mock_client, PoolMonitorConfig())

        events_received = []

        def on_event(event: PoolEvent):
            events_received.append(event)

        monitor.on_pool_event(on_event)

        # Simulate account update
        update = AccountUpdate(
            pubkey="PoolAddress...",
            slot=12345678,
            lamports=1000000,
            owner=RAYDIUM_AMM_V4,
            data=bytes(752),
            executable=False,
            rent_epoch=100,
            write_version=999,
        )

        await monitor._handle_account_update(update)

        # May or may not emit event depending on parsing success
        # Just verify no crash

    @pytest.mark.asyncio
    async def test_detects_new_pool(self):
        """Should emit NEW_POOL event for newly seen pools."""
        mock_client = MagicMock(spec=GeyserClient)
        monitor = PoolMonitor(mock_client, PoolMonitorConfig())

        events_received = []

        def on_event(event: PoolEvent):
            events_received.append(event)

        monitor.on_pool_event(on_event)

        # Mock the parser to return valid state
        mock_state = PoolState(
            address="NewPool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1000000,
            token_b_reserve=1000000,
            lp_supply=1000000,
            fee_rate_bps=25,
            slot=12345678,
        )

        with patch.object(monitor, "_parse_pool_state", return_value=mock_state):
            update = AccountUpdate(
                pubkey="NewPool...",
                slot=12345678,
                lamports=1000000,
                owner=RAYDIUM_AMM_V4,
                data=bytes(752),
                executable=False,
                rent_epoch=100,
                write_version=999,
            )

            await monitor._handle_account_update(update)

        new_pool_events = [e for e in events_received if e.event_type == PoolEventType.NEW_POOL]
        assert len(new_pool_events) == 1

    @pytest.mark.asyncio
    async def test_detects_price_change(self):
        """Should emit PRICE_CHANGE event when threshold exceeded."""
        mock_client = MagicMock(spec=GeyserClient)
        config = PoolMonitorConfig(price_change_threshold_pct=1.0)
        monitor = PoolMonitor(mock_client, config)

        events_received = []

        def on_event(event: PoolEvent):
            events_received.append(event)

        monitor.on_pool_event(on_event)

        # Set up previous state
        old_state = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1000,
            token_b_reserve=1000,
            lp_supply=1000,
            fee_rate_bps=25,
            slot=100,
        )
        monitor._pool_states["Pool..."] = old_state

        # New state with 5% price change
        new_state = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1050,
            token_b_reserve=950,
            lp_supply=1000,
            fee_rate_bps=25,
            slot=101,
        )

        with patch.object(monitor, "_parse_pool_state", return_value=new_state):
            update = AccountUpdate(
                pubkey="Pool...",
                slot=101,
                lamports=1000000,
                owner=RAYDIUM_AMM_V4,
                data=bytes(752),
                executable=False,
                rent_epoch=100,
                write_version=1000,
            )

            await monitor._handle_account_update(update)

        price_events = [e for e in events_received if e.event_type == PoolEventType.PRICE_CHANGE]
        assert len(price_events) >= 1

    @pytest.mark.asyncio
    async def test_detects_liquidity_change(self):
        """Should emit liquidity events when threshold exceeded."""
        mock_client = MagicMock(spec=GeyserClient)
        config = PoolMonitorConfig(liquidity_change_threshold_pct=5.0)
        monitor = PoolMonitor(mock_client, config)

        events_received = []

        def on_event(event: PoolEvent):
            events_received.append(event)

        monitor.on_pool_event(on_event)

        # Set up previous state
        old_state = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1000,
            token_b_reserve=1000,
            lp_supply=1000,
            fee_rate_bps=25,
            slot=100,
        )
        monitor._pool_states["Pool..."] = old_state

        # New state with 10% liquidity add
        new_state = PoolState(
            address="Pool...",
            dex_type=DEXType.RAYDIUM,
            token_a_mint="A",
            token_b_mint="B",
            token_a_reserve=1100,
            token_b_reserve=1100,
            lp_supply=1100,
            fee_rate_bps=25,
            slot=101,
        )

        with patch.object(monitor, "_parse_pool_state", return_value=new_state):
            update = AccountUpdate(
                pubkey="Pool...",
                slot=101,
                lamports=1000000,
                owner=RAYDIUM_AMM_V4,
                data=bytes(752),
                executable=False,
                rent_epoch=100,
                write_version=1000,
            )

            await monitor._handle_account_update(update)

        liq_events = [e for e in events_received if e.event_type in [
            PoolEventType.LIQUIDITY_ADD, PoolEventType.LIQUIDITY_REMOVE
        ]]
        assert len(liq_events) >= 1


class TestPoolMonitorMetrics:
    """Tests for PoolMonitor metrics."""

    def test_get_stats(self):
        """Should return monitoring statistics."""
        mock_client = MagicMock(spec=GeyserClient)
        monitor = PoolMonitor(mock_client, PoolMonitorConfig())

        monitor._pool_states = {"Pool1": MagicMock(), "Pool2": MagicMock()}
        monitor._events_emitted = 50
        monitor._updates_processed = 100

        stats = monitor.get_stats()

        assert stats["pools_tracked"] == 2
        assert stats["events_emitted"] == 50
        assert stats["updates_processed"] == 100

    def test_get_tracked_pools(self):
        """Should return list of tracked pools."""
        mock_client = MagicMock(spec=GeyserClient)
        monitor = PoolMonitor(mock_client, PoolMonitorConfig())

        mock_state1 = MagicMock()
        mock_state1.address = "Pool1"
        mock_state1.dex_type = DEXType.RAYDIUM

        mock_state2 = MagicMock()
        mock_state2.address = "Pool2"
        mock_state2.dex_type = DEXType.ORCA_WHIRLPOOL

        monitor._pool_states = {"Pool1": mock_state1, "Pool2": mock_state2}

        pools = monitor.get_tracked_pools()

        assert len(pools) == 2
        assert "Pool1" in [p["address"] for p in pools]
