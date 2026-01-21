"""
Unit tests for Market Maker system.

Tests the actual core.market_maker module API.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile


class TestMarketMakerImports:
    """Test that all market maker components can be imported."""

    def test_market_maker_import(self):
        """Test that MarketMaker can be imported."""
        from core.market_maker import (
            MarketMaker,
            MMConfig,
            MMOrder,
            MMStats,
            InventoryState,
            MMOrderStatus,
            MMStrategy,
            OrderSide,
        )
        assert MarketMaker is not None
        assert MMConfig is not None
        assert MMOrder is not None
        assert MMStats is not None
        assert InventoryState is not None
        assert MMOrderStatus is not None
        assert MMStrategy is not None
        assert OrderSide is not None


class TestMMStrategy:
    """Tests for MMStrategy enum."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        from core.market_maker import MMStrategy

        assert MMStrategy.SIMPLE.value == "simple"
        assert MMStrategy.DYNAMIC.value == "dynamic"
        assert MMStrategy.INVENTORY.value == "inventory"
        assert MMStrategy.AVELLANEDA.value == "avellaneda"
        assert MMStrategy.GRID.value == "grid"


class TestOrderSide:
    """Tests for OrderSide enum."""

    def test_order_side_values(self):
        """Test order side enum values."""
        from core.market_maker import OrderSide

        assert OrderSide.BID.value == "bid"
        assert OrderSide.ASK.value == "ask"


class TestMMOrderStatus:
    """Tests for MMOrderStatus enum."""

    def test_order_status_values(self):
        """Test order status enum values."""
        from core.market_maker import MMOrderStatus

        assert MMOrderStatus.ACTIVE.value == "active"
        assert MMOrderStatus.FILLED.value == "filled"
        assert MMOrderStatus.CANCELLED.value == "cancelled"
        assert MMOrderStatus.EXPIRED.value == "expired"


class TestMMConfig:
    """Tests for MMConfig dataclass."""

    def test_config_creation(self):
        """Test creating a market maker config."""
        from core.market_maker import MMConfig, MMStrategy

        config = MMConfig(
            symbol="SOL-USDC",
            strategy=MMStrategy.SIMPLE,
            base_spread_bps=10.0,
            min_spread_bps=5.0,
            max_spread_bps=50.0,
            order_size=1.0,
            num_levels=3,
            level_spacing_bps=5.0,
            max_inventory=100.0,
            inventory_target=0.0,
            refresh_interval_ms=5000,
            min_order_value=10.0,
        )

        assert config.symbol == "SOL-USDC"
        assert config.strategy == MMStrategy.SIMPLE
        assert config.base_spread_bps == 10.0
        assert config.num_levels == 3
        assert config.enabled is True


class TestMMOrder:
    """Tests for MMOrder dataclass."""

    def test_order_creation(self):
        """Test creating a market maker order."""
        from core.market_maker import MMOrder, OrderSide, MMOrderStatus

        now = datetime.utcnow()
        order = MMOrder(
            order_id="order123",
            symbol="SOL-USDC",
            side=OrderSide.BID,
            price=100.0,
            size=1.0,
            filled_size=0.0,
            status=MMOrderStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        assert order.order_id == "order123"
        assert order.symbol == "SOL-USDC"
        assert order.side == OrderSide.BID
        assert order.price == 100.0
        assert order.status == MMOrderStatus.ACTIVE


class TestMarketMakerInitialization:
    """Tests for MarketMaker initialization."""

    def test_basic_initialization(self):
        """Test basic market maker initialization."""
        from core.market_maker import MarketMaker

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_mm.db")
            mm = MarketMaker(db_path=db_path)

            assert mm is not None
            assert mm._running is False
            assert len(mm.configs) == 0

    def test_configure(self):
        """Test configuring a market for trading."""
        from core.market_maker import MarketMaker, MMStrategy

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_mm.db")
            mm = MarketMaker(db_path=db_path)

            config = mm.configure(
                symbol="SOL-USDC",
                strategy=MMStrategy.SIMPLE,
                base_spread_bps=10.0,
                min_spread_bps=5.0,
                max_spread_bps=50.0,
                order_size=1.0,
                num_levels=3,
                level_spacing_bps=5.0,
                max_inventory=100.0,
                inventory_target=0.0,
                refresh_interval_ms=5000,
                min_order_value=10.0,
            )

            assert "SOL-USDC" in mm.configs
            assert config.symbol == "SOL-USDC"
            assert config.strategy == MMStrategy.SIMPLE


class TestInventoryState:
    """Tests for InventoryState dataclass."""

    def test_inventory_state_creation(self):
        """Test creating an inventory state."""
        from core.market_maker import InventoryState

        now = datetime.utcnow()
        state = InventoryState(
            symbol="SOL-USDC",
            base_balance=100.0,
            quote_balance=5000.0,
            inventory_delta=10.0,
            skew=0.01,
            updated_at=now,
        )

        assert state.symbol == "SOL-USDC"
        assert state.base_balance == 100.0
        assert state.quote_balance == 5000.0
        assert state.inventory_delta == 10.0
        assert state.skew == 0.01


class TestMMStats:
    """Tests for MMStats dataclass."""

    def test_stats_creation(self):
        """Test creating market maker stats."""
        from core.market_maker import MMStats

        stats = MMStats(
            symbol="SOL-USDC",
            total_volume=10000.0,
            total_trades=100,
            total_pnl=500.0,
            realized_pnl=450.0,
            unrealized_pnl=50.0,
            spread_captured=100.0,
            inventory_cost=-50.0,
            uptime_percent=99.5,
            fill_rate=0.85,
        )

        assert stats.symbol == "SOL-USDC"
        assert stats.total_volume == 10000.0
        assert stats.total_trades == 100
        assert stats.total_pnl == 500.0
        assert stats.fill_rate == 0.85
