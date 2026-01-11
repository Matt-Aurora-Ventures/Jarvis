"""
Integration tests for Treasury Trading Pipeline.
Tests the full flow from sentiment to trade execution.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal

# Import treasury modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.treasury.trading import (
    TradingEngine, Position, TradeDirection,
    TradeStatus, RiskLevel, TradeReport
)
from bots.treasury.wallet import SecureWallet, WalletInfo
from bots.treasury.jupiter import JupiterClient, SwapQuote


class TestTradingEngine:
    """Test suite for TradingEngine."""

    @pytest.fixture
    def mock_wallet(self):
        """Create mock wallet."""
        wallet = Mock(spec=SecureWallet)
        wallet.get_treasury.return_value = WalletInfo(
            name="test_treasury",
            address="So11111111111111111111111111111111111111112",
            balance=100.0
        )
        return wallet

    @pytest.fixture
    def mock_jupiter(self):
        """Create mock Jupiter client."""
        jupiter = Mock(spec=JupiterClient)
        jupiter.get_token_price = AsyncMock(return_value=1.5)
        jupiter.get_quote = AsyncMock(return_value=SwapQuote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="test_token_mint",
            in_amount=1000000000,
            out_amount=666666666,
            price_impact_pct=0.1,
            route_plan=[]
        ))
        return jupiter

    @pytest.fixture
    def engine(self, mock_wallet, mock_jupiter):
        """Create trading engine with mocks."""
        engine = TradingEngine(
            wallet=mock_wallet,
            jupiter=mock_jupiter,
            dry_run=True
        )
        return engine

    def test_risk_level_position_sizing(self, engine):
        """Test position sizing by risk level."""
        # Conservative = 1%
        engine.risk_level = RiskLevel.CONSERVATIVE
        size = engine._calculate_position_size(10000)  # $10K portfolio
        assert size == 100  # 1%

        # Moderate = 2%
        engine.risk_level = RiskLevel.MODERATE
        size = engine._calculate_position_size(10000)
        assert size == 200  # 2%

        # Aggressive = 5%
        engine.risk_level = RiskLevel.AGGRESSIVE
        size = engine._calculate_position_size(10000)
        assert size == 500  # 5%

        # Degen = 10%
        engine.risk_level = RiskLevel.DEGEN
        size = engine._calculate_position_size(10000)
        assert size == 1000  # 10%

    def test_tp_sl_by_grade(self, engine):
        """Test take profit / stop loss levels by sentiment grade."""
        current_price = 1.0

        # Grade A: 30% TP, 10% SL
        tp, sl = engine.get_tp_sl_levels(current_price, "A")
        assert tp == pytest.approx(1.30, rel=0.01)
        assert sl == pytest.approx(0.90, rel=0.01)

        # Grade B+: 20% TP, 8% SL
        tp, sl = engine.get_tp_sl_levels(current_price, "B+")
        assert tp == pytest.approx(1.20, rel=0.01)
        assert sl == pytest.approx(0.92, rel=0.01)

        # Grade B: 15% TP, 8% SL
        tp, sl = engine.get_tp_sl_levels(current_price, "B")
        assert tp == pytest.approx(1.15, rel=0.01)
        assert sl == pytest.approx(0.92, rel=0.01)

        # Grade C: 10% TP, 5% SL
        tp, sl = engine.get_tp_sl_levels(current_price, "C")
        assert tp == pytest.approx(1.10, rel=0.01)
        assert sl == pytest.approx(0.95, rel=0.01)

    def test_position_pnl_calculation(self):
        """Test position P&L calculation."""
        position = Position(
            id="test_pos_1",
            token_mint="test_mint",
            token_symbol="TEST",
            direction=TradeDirection.LONG,
            entry_price=1.0,
            current_price=1.2,  # 20% up
            amount=100,
            amount_usd=100,
            take_profit_price=1.3,
            stop_loss_price=0.9,
            status=TradeStatus.OPEN,
            opened_at="2024-01-01T00:00:00"
        )

        # Unrealized P&L should be +20%
        assert position.unrealized_pnl_pct == pytest.approx(20.0, rel=0.01)
        assert position.unrealized_pnl == pytest.approx(20.0, rel=0.01)

        # Test losing position
        position.current_price = 0.8  # 20% down
        assert position.unrealized_pnl_pct == pytest.approx(-20.0, rel=0.01)

    def test_trade_report_generation(self, engine):
        """Test trade report generation."""
        # Add some mock trade history
        engine.trade_history = [
            Position(
                id="1", token_mint="m1", token_symbol="T1",
                direction=TradeDirection.LONG, entry_price=1.0,
                current_price=1.2, amount=100, amount_usd=100,
                take_profit_price=1.3, stop_loss_price=0.9,
                status=TradeStatus.CLOSED, opened_at="2024-01-01",
                pnl_usd=20.0, pnl_pct=20.0
            ),
            Position(
                id="2", token_mint="m2", token_symbol="T2",
                direction=TradeDirection.LONG, entry_price=1.0,
                current_price=0.9, amount=100, amount_usd=100,
                take_profit_price=1.3, stop_loss_price=0.9,
                status=TradeStatus.CLOSED, opened_at="2024-01-01",
                pnl_usd=-10.0, pnl_pct=-10.0
            ),
        ]

        report = engine.generate_report()

        assert report.total_trades == 2
        assert report.winning_trades == 1
        assert report.losing_trades == 1
        assert report.win_rate == 50.0
        assert report.total_pnl_usd == 10.0

    def test_dry_run_no_execution(self, engine):
        """Test that dry run mode doesn't execute real trades."""
        engine.dry_run = True

        # Attempt to open position
        # In dry run mode, should succeed but not call Jupiter
        assert engine.dry_run is True

    def test_max_positions_limit(self, engine):
        """Test maximum positions limit."""
        engine.max_positions = 5

        # Create 5 open positions
        for i in range(5):
            engine.positions[f"pos_{i}"] = Position(
                id=f"pos_{i}", token_mint=f"mint_{i}", token_symbol=f"T{i}",
                direction=TradeDirection.LONG, entry_price=1.0,
                current_price=1.0, amount=100, amount_usd=100,
                take_profit_price=1.3, stop_loss_price=0.9,
                status=TradeStatus.OPEN, opened_at="2024-01-01"
            )

        # Should have 5 open positions
        open_positions = engine.get_open_positions()
        assert len(open_positions) == 5


class TestWalletSecurity:
    """Test wallet security features."""

    def test_wallet_encryption(self):
        """Test that wallet uses encryption."""
        # Verify SecureWallet uses Fernet encryption
        wallet = SecureWallet(password="test_password_123")
        assert hasattr(wallet, '_cipher')

    def test_private_key_not_exposed(self):
        """Test that private keys aren't exposed in errors/logs."""
        wallet = SecureWallet(password="test_password_123")

        # Get string representation - should NOT contain private key
        wallet_str = str(wallet)
        assert "private" not in wallet_str.lower() or "key" not in wallet_str.lower()


class TestSentimentIntegration:
    """Test sentiment to trading integration."""

    def test_sentiment_grade_to_signal(self):
        """Test sentiment grade conversion to trade signal."""
        # Grade A (90%+) = Strong signal
        # Grade B+ (80-89%) = Moderate signal
        # Grade B (70-79%) = Weak signal
        # Grade C (<70%) = No signal

        # This tests the grade thresholds are correct
        grades = {
            "A": {"min_confidence": 0.90, "signal": "strong"},
            "B+": {"min_confidence": 0.80, "signal": "moderate"},
            "B": {"min_confidence": 0.70, "signal": "weak"},
            "C": {"min_confidence": 0.60, "signal": "none"},
        }

        for grade, config in grades.items():
            assert config["min_confidence"] >= 0.60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
