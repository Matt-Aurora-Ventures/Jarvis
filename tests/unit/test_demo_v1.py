"""
JARVIS V1 Demo Test Suite

Comprehensive tests for:
- Trade Intelligence Engine
- Learning Dashboard
- Demo UI Components
- Sentiment Engine Integration
- Generative Compression Memory
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json
import tempfile
from pathlib import Path


class TestTradeIntelligenceEngine:
    """Test the self-improving trade intelligence engine."""

    def test_engine_initialization(self):
        """Test engine can be initialized."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()
        assert engine is not None
        assert engine._tier1 == [] or isinstance(engine._tier1, list)
        assert engine._tier2 == [] or isinstance(engine._tier2, list)

    def test_record_trade_win(self):
        """Test recording a winning trade."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        outcome = engine.record_trade(
            trade_id="test_001",
            token_address="So11111111111111111111111111111111111111112",
            token_symbol="TEST",
            entry_price=0.0001,
            exit_price=0.00015,  # 50% gain
            amount_sol=1.0,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=1),
            exit_time=datetime.now(timezone.utc),
            market_regime="BULL",
            sentiment_score=0.7,
            signal_type="STRONG_BUY",
            reasons=["High volume", "Bullish pattern"],
        )

        assert outcome is not None
        assert outcome.outcome == "WIN"
        assert outcome.pnl_pct > 0
        assert len(outcome.lessons) > 0

    def test_record_trade_loss(self):
        """Test recording a losing trade."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        outcome = engine.record_trade(
            trade_id="test_002",
            token_address="So11111111111111111111111111111111111111112",
            token_symbol="TEST",
            entry_price=0.0001,
            exit_price=0.00007,  # 30% loss
            amount_sol=1.0,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=2),
            exit_time=datetime.now(timezone.utc),
            market_regime="BEAR",
            sentiment_score=0.3,
            signal_type="NEUTRAL",
        )

        assert outcome is not None
        assert outcome.outcome == "LOSS"
        assert outcome.pnl_pct < 0

    def test_learning_updates(self):
        """Test that learning patterns are updated."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        # Record multiple trades
        for i in range(5):
            engine.record_trade(
                trade_id=f"test_{i:03d}",
                token_address="So11111111111111111111111111111111111111112",
                token_symbol=f"TEST{i}",
                entry_price=0.0001,
                exit_price=0.00012 if i % 2 == 0 else 0.00008,
                amount_sol=1.0,
                entry_time=datetime.now(timezone.utc) - timedelta(hours=1),
                exit_time=datetime.now(timezone.utc),
                market_regime="BULL",
                sentiment_score=0.6,
                signal_type="BUY",
            )

        # Check that learning occurred
        summary = engine.get_learning_summary()
        assert "signals" in summary
        assert "regimes" in summary

    def test_get_recommendation(self):
        """Test getting trade recommendations."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        # Record some trades first to have data
        for i in range(10):
            engine.record_trade(
                trade_id=f"rec_test_{i:03d}",
                token_address="So11111111111111111111111111111111111111112",
                token_symbol=f"REC{i}",
                entry_price=0.0001,
                exit_price=0.00015 if i < 7 else 0.00008,  # 70% win rate
                amount_sol=1.0,
                entry_time=datetime.now(timezone.utc) - timedelta(hours=1),
                exit_time=datetime.now(timezone.utc),
                market_regime="BULL",
                sentiment_score=0.7,
                signal_type="BUY",
            )

        rec = engine.get_trade_recommendation(
            signal_type="BUY",
            market_regime="BULL",
            sentiment_score=0.7,
        )

        assert "action" in rec
        assert "confidence" in rec
        assert "expected_return" in rec
        assert "reasons" in rec

    def test_compression_stats(self):
        """Test compression statistics."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        stats = engine.get_compression_stats()
        assert "tier1_trades" in stats
        assert "tier2_patterns" in stats
        assert "compression_ratio" in stats


class TestDemoMenuBuilder:
    """Test the demo UI menu builders."""

    def test_main_menu_build(self):
        """Test main menu can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address="AbCdEfGhIjKlMnOpQrStUvWxYz123456789012345",
            sol_balance=10.5,
            usd_value=2100.0,
            is_live=False,
            open_positions=3,
            total_pnl=125.50,
            market_regime={"regime": "BULL", "risk_level": "LOW"},
        )

        assert text is not None
        assert "JARVIS" in text
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_main_menu_with_ai_auto_enabled(self):
        """Test main menu shows AI auto-trade status when enabled."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.main_menu(
            wallet_address="AbCdEfGhIjKlMnOpQrStUvWxYz123456789012345",
            sol_balance=10.5,
            usd_value=2100.0,
            ai_auto_enabled=True,
        )

        assert "JARVIS" in text
        assert "AUTO-TRADE ACTIVE" in text

    def test_learning_dashboard_build(self):
        """Test learning dashboard can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        learning_stats = {
            "total_trades_analyzed": 50,
            "pattern_memories": 5,
            "stable_strategies": 2,
            "signals": {
                "BUY": {"win_rate": "65%", "avg_return": "+12.3%", "trades": 30},
            },
            "regimes": {
                "BULL": {"win_rate": "70%", "avg_return": "+15.0%"},
            },
            "optimal_hold_time": 45,
        }

        compression_stats = {
            "compression_ratio": 8.5,
            "learned_patterns": 15,
        }

        text, keyboard = DemoMenuBuilder.learning_dashboard(
            learning_stats=learning_stats,
            compression_stats=compression_stats,
        )

        assert text is not None
        assert "Learning" in text or "LEARNING" in text
        assert "Compression" in text or "compression" in text.lower()
        assert keyboard is not None

    def test_recommendation_view_build(self):
        """Test recommendation view can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        recommendation = {
            "action": "BUY",
            "confidence": 0.75,
            "expected_return": 12.5,
            "suggested_hold_minutes": 45,
            "reasons": ["High win rate", "Favorable regime"],
            "warnings": [],
        }

        text, keyboard = DemoMenuBuilder.recommendation_view(
            recommendation=recommendation,
            token_symbol="BONK",
            market_regime="BULL",
        )

        assert text is not None
        assert "BUY" in text
        assert keyboard is not None

    def test_positions_menu_empty(self):
        """Test positions menu with no positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.positions_menu(
            positions=[],
            total_pnl=0.0,
        )

        assert text is not None
        assert "No open positions" in text

    def test_positions_menu_with_positions(self):
        """Test positions menu with positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        positions = [
            {
                "symbol": "BONK",
                "pnl_pct": 25.5,
                "pnl_usd": 12.75,
                "entry_price": 0.00001,
                "current_price": 0.0000125,
                "id": "pos_001",
            },
        ]

        text, keyboard = DemoMenuBuilder.positions_menu(
            positions=positions,
            total_pnl=12.75,
        )

        assert text is not None
        assert "BONK" in text
        assert keyboard is not None

    def test_performance_dashboard_build(self):
        """Test performance dashboard can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        performance_stats = {
            "total_trades": 47,
            "wins": 31,
            "losses": 16,
            "win_rate": 66.0,
            "total_pnl": 1247.50,
            "total_pnl_pct": 24.95,
            "best_trade": {"symbol": "BONK", "pnl_pct": 142.5},
            "worst_trade": {"symbol": "BOME", "pnl_pct": -35.2},
            "current_streak": 3,
            "avg_hold_time_minutes": 45,
            "daily_pnl": 125.50,
            "weekly_pnl": 487.25,
            "monthly_pnl": 1247.50,
            "avg_trades_per_day": 2.3,
        }

        text, keyboard = DemoMenuBuilder.performance_dashboard(performance_stats)

        assert text is not None
        assert "PERFORMANCE" in text
        assert "Win Rate" in text
        assert "66.0%" in text
        assert "BONK" in text
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_performance_dashboard_negative_pnl(self):
        """Test performance dashboard with negative PnL."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        performance_stats = {
            "total_trades": 10,
            "wins": 3,
            "losses": 7,
            "win_rate": 30.0,
            "total_pnl": -250.00,
            "total_pnl_pct": -5.0,
            "current_streak": -3,
            "avg_hold_time_minutes": 30,
            "daily_pnl": -50.00,
            "weekly_pnl": -150.00,
            "monthly_pnl": -250.00,
            "avg_trades_per_day": 1.0,
        }

        text, keyboard = DemoMenuBuilder.performance_dashboard(performance_stats)

        assert text is not None
        assert "250.00" in text  # Total PnL amount
        assert "30.0%" in text  # Win rate
        assert keyboard is not None

    def test_trade_history_view_empty(self):
        """Test trade history view with no trades."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.trade_history_view([])

        assert text is not None
        assert "No trades recorded" in text
        assert keyboard is not None

    def test_trade_history_view_with_trades(self):
        """Test trade history view with trades."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        trades = [
            {"symbol": "BONK", "pnl_pct": 42.5, "pnl_usd": 85.00},
            {"symbol": "WIF", "pnl_pct": -12.3, "pnl_usd": -24.60},
            {"symbol": "POPCAT", "pnl_pct": 28.7, "pnl_usd": 57.40},
        ]

        text, keyboard = DemoMenuBuilder.trade_history_view(trades)

        assert text is not None
        assert "BONK" in text
        assert "WIF" in text
        assert "POPCAT" in text
        assert "42.5%" in text
        assert keyboard is not None

    def test_trade_history_pagination(self):
        """Test trade history pagination."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        # Create 10 trades to test pagination
        trades = [
            {"symbol": f"TOKEN{i}", "pnl_pct": i * 10, "pnl_usd": i * 20}
            for i in range(10)
        ]

        # Page 1
        text, keyboard = DemoMenuBuilder.trade_history_view(trades, page=0, page_size=5)
        assert "Page 1/2" in text
        assert "TOKEN0" in text
        assert "TOKEN4" in text
        assert "TOKEN5" not in text

        # Page 2
        text, keyboard = DemoMenuBuilder.trade_history_view(trades, page=1, page_size=5)
        assert "Page 2/2" in text
        assert "TOKEN5" in text
        assert "TOKEN0" not in text

    def test_quick_trade_menu_build(self):
        """Test quick trade menu can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        trending = [
            {"symbol": "BONK", "change_24h": 15.2, "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
            {"symbol": "WIF", "change_24h": -5.3, "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
        ]
        positions = [
            {"symbol": "PEPE", "pnl_pct": 25.0, "pnl_usd": 50.0, "id": "pos_001"},
        ]

        text, keyboard = DemoMenuBuilder.quick_trade_menu(
            trending_tokens=trending,
            positions=positions,
            sol_balance=5.5,
            market_regime="BULL",
        )

        assert text is not None
        assert "QUICK TRADE" in text
        assert "BONK" in text
        assert "WIF" in text
        assert "5.5" in text  # SOL balance
        assert keyboard is not None

    def test_quick_trade_menu_no_positions(self):
        """Test quick trade menu with no positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.quick_trade_menu(
            trending_tokens=[],
            positions=[],
            sol_balance=1.0,
            market_regime="NEUTRAL",
        )

        assert text is not None
        assert "QUICK TRADE" in text
        assert "Positions: *0*" in text

    def test_snipe_mode_view_build(self):
        """Test snipe mode view can be built."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.snipe_mode_view()

        assert text is not None
        assert "SNIPE MODE" in text
        assert "Paste a Solana token address" in text
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_watchlist_menu_empty(self):
        """Test watchlist menu with empty list."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.watchlist_menu([])

        assert text is not None
        assert "WATCHLIST" in text
        assert "empty" in text.lower()
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) >= 2  # Add + Back buttons

    def test_watchlist_menu_with_tokens(self):
        """Test watchlist menu with tokens."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        watchlist = [
            {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "price": 0.00002, "change_24h": 15.5},
            {"symbol": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "price": 1.25, "change_24h": -8.2},
        ]

        text, keyboard = DemoMenuBuilder.watchlist_menu(watchlist)

        assert text is not None
        assert "WATCHLIST" in text
        assert "BONK" in text
        assert "WIF" in text
        assert "15.5" in text  # Change percentage
        assert keyboard is not None
        # 2 token rows + Add/Refresh + Back
        assert len(keyboard.inline_keyboard) >= 4

    def test_watchlist_menu_with_alert(self):
        """Test watchlist menu with price alert."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        watchlist = [
            {"symbol": "PEPE", "address": "addr123", "price": 0.001, "change_24h": 5.0, "alert": 0.002},
        ]

        text, keyboard = DemoMenuBuilder.watchlist_menu(watchlist)

        assert "PEPE" in text
        assert "Alert" in text
        assert "0.002" in text

    def test_wallet_menu_enhanced(self):
        """Test enhanced wallet menu with token holdings."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        holdings = [
            {"symbol": "BONK", "value_usd": 150.50},
            {"symbol": "WIF", "value_usd": 75.25},
        ]

        text, keyboard = DemoMenuBuilder.wallet_menu(
            wallet_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            sol_balance=5.5,
            usd_value=1100.0,
            has_wallet=True,
            token_holdings=holdings,
            total_holdings_usd=225.75,
        )

        assert text is not None
        assert "WALLET MANAGEMENT" in text
        assert "5.5" in text  # SOL balance
        assert "1,100" in text  # USD value
        assert "BONK" in text
        assert "Token Holdings" in text
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) >= 5  # Enhanced buttons

    def test_token_holdings_view_empty(self):
        """Test token holdings view with no tokens."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.token_holdings_view([], 0.0)

        assert "TOKEN HOLDINGS" in text
        assert "No tokens found" in text
        assert keyboard is not None

    def test_token_holdings_view_with_tokens(self):
        """Test token holdings view with tokens."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        holdings = [
            {"symbol": "BONK", "amount": 1000000, "value_usd": 150.50, "change_24h": 15.5},
            {"symbol": "WIF", "amount": 50, "value_usd": 75.25, "change_24h": -8.2},
        ]

        text, keyboard = DemoMenuBuilder.token_holdings_view(holdings, 225.75)

        assert "BONK" in text
        assert "WIF" in text
        assert "150.50" in text
        assert "225.75" in text
        assert "15.5" in text

    def test_wallet_activity_view_empty(self):
        """Test wallet activity view with no transactions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_activity_view([])

        assert "WALLET ACTIVITY" in text
        assert "No recent activity" in text

    def test_wallet_activity_view_with_transactions(self):
        """Test wallet activity view with transactions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        transactions = [
            {"type": "buy", "symbol": "BONK", "amount": 0.5, "timestamp": "10:30", "status": "confirmed"},
            {"type": "sell", "symbol": "WIF", "amount": 1.0, "timestamp": "09:15", "status": "confirmed"},
        ]

        text, keyboard = DemoMenuBuilder.wallet_activity_view(transactions)

        assert "BUY" in text
        assert "SELL" in text
        assert "BONK" in text
        assert "WIF" in text

    def test_send_sol_view(self):
        """Test send SOL view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.send_sol_view(sol_balance=5.5)

        assert "SEND SOL" in text
        assert "5.5" in text
        assert "Available" in text

    def test_export_key_confirm(self):
        """Test export key confirmation dialog."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.export_key_confirm()

        assert "EXPORT PRIVATE KEY" in text
        assert "SECURITY WARNING" in text
        assert "NEVER share" in text
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2

    def test_wallet_reset_confirm(self):
        """Test wallet reset confirmation dialog."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_reset_confirm()

        assert "RESET WALLET" in text
        assert "IRREVERSIBLE" in text
        assert keyboard is not None

    def test_settings_menu_with_ai_auto_trade(self):
        """Test settings menu shows AI auto-trade status."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.settings_menu(
            is_live=False,
            ai_auto_trade=True,
        )

        assert "SETTINGS" in text
        assert "AI Auto-Trade" in text
        assert "ENABLED" in text
        assert keyboard is not None
        # Check for AI Auto-Trade Settings button
        assert any("AI Auto-Trade" in str(btn) for row in keyboard.inline_keyboard for btn in row)

    def test_ai_auto_trade_settings_view(self):
        """Test AI auto-trade settings view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
            enabled=True,
            risk_level="AGGRESSIVE",
            max_position_size=1.0,
            min_confidence=0.8,
        )

        assert "AI AUTO-TRADE SETTINGS" in text
        assert "ENABLED" in text
        assert "AGGRESSIVE" in text
        assert "1" in text  # Max position
        assert "80%" in text  # Confidence
        assert keyboard is not None
        # Multiple rows for risk levels and settings
        assert len(keyboard.inline_keyboard) >= 6

    def test_ai_auto_trade_settings_disabled(self):
        """Test AI auto-trade settings when disabled."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.ai_auto_trade_settings(
            enabled=False,
            risk_level="CONSERVATIVE",
        )

        assert "DISABLED" in text
        assert "CONSERVATIVE" in text
        assert "Enable AI Trading" in str(keyboard.inline_keyboard)

    def test_ai_auto_trade_status_view(self):
        """Test AI auto-trade status view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.ai_auto_trade_status(
            enabled=True,
            trades_today=5,
            pnl_today=125.50,
            last_trade="BONK +42%",
        )

        assert "AI TRADING STATUS" in text
        assert "ACTIVE" in text
        assert "5" in text  # Trades
        assert "125.50" in text  # PnL
        assert "BONK" in text
        assert keyboard is not None

    def test_ai_auto_trade_status_paused(self):
        """Test AI auto-trade status when paused."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.ai_auto_trade_status(
            enabled=False,
            pnl_today=-50.0,
        )

        assert "PAUSED" in text
        assert "50.00" in text  # PnL shown
        assert "idle" in text.lower()

    # ========== P&L ALERTS TESTS ==========

    def test_pnl_alerts_overview_empty(self):
        """Test P&L alerts overview with no alerts."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.pnl_alerts_overview(
            alerts=[],
            positions=[],
        )

        assert "P&L ALERTS" in text
        assert "No active alerts" in text
        assert keyboard is not None

    def test_pnl_alerts_overview_with_alerts(self):
        """Test P&L alerts overview with active alerts."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        alerts = [
            {"symbol": "BONK", "type": "percent", "target": 50, "direction": "above", "triggered": False},
            {"symbol": "WIF", "type": "percent", "target": -25, "direction": "below", "triggered": True},
        ]

        text, keyboard = DemoMenuBuilder.pnl_alerts_overview(
            alerts=alerts,
            positions=[],
        )

        assert "P&L ALERTS" in text
        assert "Active Alerts:* 1" in text  # One not triggered (with markdown)
        assert "Triggered:* 1" in text  # With markdown
        assert "BONK" in text
        assert "WIF" in text
        assert "+50" in text

    def test_pnl_alerts_overview_with_positions(self):
        """Test P&L alerts overview shows add alert buttons for positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        positions = [
            {"id": "1", "symbol": "BONK"},
            {"id": "2", "symbol": "WIF"},
        ]

        text, keyboard = DemoMenuBuilder.pnl_alerts_overview(
            alerts=[],
            positions=positions,
        )

        assert keyboard is not None
        # Check keyboard has add alert buttons
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("BONK" in btn for btn in buttons)
        assert any("WIF" in btn for btn in buttons)

    def test_position_alert_setup(self):
        """Test position alert setup view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        position = {
            "id": "pos123",
            "symbol": "BONK",
            "pnl_pct": 15.5,
            "pnl_usd": 25.0,
            "entry_price": 0.0001,
            "current_price": 0.000115,
        }

        text, keyboard = DemoMenuBuilder.position_alert_setup(
            position=position,
            existing_alerts=[],
        )

        assert "SET ALERT: BONK" in text
        assert "Current Position" in text
        assert "15.5" in text  # PnL %
        assert "Quick Presets" in text
        assert keyboard is not None

        # Check preset buttons exist
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("+25%" in btn for btn in buttons)
        assert any("+50%" in btn for btn in buttons)
        assert any("-10%" in btn for btn in buttons)

    def test_position_alert_setup_with_existing_alerts(self):
        """Test position alert setup shows existing alerts."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        position = {
            "id": "pos123",
            "symbol": "BONK",
            "pnl_pct": 15.5,
            "pnl_usd": 25.0,
            "entry_price": 0.0001,
            "current_price": 0.000115,
        }

        existing_alerts = [
            {"position_id": "pos123", "type": "percent", "target": 50, "direction": "above"},
            {"position_id": "pos123", "type": "percent", "target": -25, "direction": "below"},
        ]

        text, keyboard = DemoMenuBuilder.position_alert_setup(
            position=position,
            existing_alerts=existing_alerts,
        )

        assert "Active Alerts:" in text
        assert "+50" in text
        assert "-25" in text

    def test_alert_created_success(self):
        """Test alert created success message."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.alert_created_success(
            symbol="BONK",
            alert_type="percent",
            target=50.0,
            direction="above",
        )

        assert "ALERT CREATED" in text
        assert "BONK" in text
        assert "+50" in text
        assert "📈" in text  # Above direction
        assert "notified" in text.lower()

    def test_alert_created_success_loss_direction(self):
        """Test alert created success for loss direction."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.alert_created_success(
            symbol="WIF",
            alert_type="percent",
            target=-25.0,
            direction="below",
        )

        assert "WIF" in text
        assert "-25" in text
        assert "📉" in text  # Below direction


class TestDCAFeature:
    """Test DCA (Dollar Cost Averaging) feature."""

    def test_dca_overview_empty(self):
        """Test DCA overview with no plans."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.dca_overview(dca_plans=[])

        assert "DCA" in text
        assert "No active DCA plans" in text or "📅" in text
        assert keyboard is not None
        # Should have "New Plan" button
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("New" in btn or "➕" in btn for btn in buttons)

    def test_dca_overview_with_plans(self):
        """Test DCA overview with active plans."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        plans = [
            {
                "id": "dca_test1",
                "symbol": "BONK",
                "amount": 0.5,
                "frequency": "daily",
                "active": True,
                "executions": 5,
                "total_invested": 2.5,
            },
            {
                "id": "dca_test2",
                "symbol": "WIF",
                "amount": 1.0,
                "frequency": "weekly",
                "active": False,
                "executions": 2,
                "total_invested": 2.0,
            },
        ]

        text, keyboard = DemoMenuBuilder.dca_overview(
            dca_plans=plans,
            total_invested=4.5,
            total_tokens_bought=2,
        )

        assert "BONK" in text  # Active plan shown in detail
        assert "daily" in text.lower() or "Daily" in text
        assert "Paused:* 1" in text or "Paused: 1" in text  # Paused count shown
        assert keyboard is not None
        # Should have pause/delete buttons for each plan
        buttons = [btn.callback_data for row in keyboard.inline_keyboard for btn in row if btn.callback_data]
        assert any("dca_pause" in btn for btn in buttons)
        assert any("dca_delete" in btn for btn in buttons)

    def test_dca_setup_no_token(self):
        """Test DCA setup showing token selection."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        watchlist = [
            {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
            {"symbol": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
        ]

        text, keyboard = DemoMenuBuilder.dca_setup(watchlist=watchlist)

        assert "DCA" in text
        assert "token" in text.lower() or "select" in text.lower()
        assert keyboard is not None
        # Should show watchlist tokens
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("BONK" in btn for btn in buttons)
        assert any("WIF" in btn for btn in buttons)

    def test_dca_setup_with_token(self):
        """Test DCA setup with token selected, showing amount options."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.dca_setup(
            token_symbol="BONK",
            token_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        )

        assert "BONK" in text
        assert "amount" in text.lower() or "SOL" in text
        assert keyboard is not None
        # Should have amount buttons
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("0.1" in btn or "0.5" in btn or "1" in btn for btn in buttons)

    def test_dca_frequency_select(self):
        """Test DCA frequency selection."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.dca_frequency_select(
            token_symbol="BONK",
            token_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            amount=0.5,
        )

        assert "BONK" in text
        assert "0.5" in text
        assert "frequency" in text.lower() or "often" in text.lower() or "interval" in text.lower()
        assert keyboard is not None
        # Should have frequency buttons
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("hourly" in btn.lower() or "hour" in btn.lower() for btn in buttons)
        assert any("daily" in btn.lower() or "day" in btn.lower() for btn in buttons)
        assert any("weekly" in btn.lower() or "week" in btn.lower() for btn in buttons)

    def test_dca_plan_created(self):
        """Test DCA plan created success message."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.dca_plan_created(
            token_symbol="BONK",
            amount=0.5,
            frequency="daily",
            first_execution="Now",
        )

        assert "BONK" in text
        assert "0.5" in text
        assert "daily" in text.lower() or "Daily" in text
        assert "created" in text.lower() or "✅" in text or "success" in text.lower()
        assert keyboard is not None
        # Should have button to view plans or go back
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("View" in btn or "DCA" in btn or "Back" in btn for btn in buttons)


class TestTrailingStopFeature:
    """Test Trailing Stop-Loss feature."""

    def test_trailing_stop_overview_empty(self):
        """Test trailing stop overview with no stops."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.trailing_stop_overview(trailing_stops=[])

        assert "TRAILING" in text.upper() or "🛡️" in text
        assert "No trailing stops" in text or "trailing stop" in text.lower()
        assert keyboard is not None
        # Should explain what trailing stops are
        assert "profit" in text.lower() or "moves UP" in text

    def test_trailing_stop_overview_with_stops(self):
        """Test trailing stop overview with active stops."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        stops = [
            {
                "id": "tsl_test1",
                "symbol": "BONK",
                "trail_percent": 10,
                "current_stop_price": 0.000018,
                "highest_price": 0.00002,
                "protected_value": 50.0,
                "protected_pnl": 25.0,
                "active": True,
            },
        ]
        positions = [{"id": "pos1", "symbol": "BONK"}]

        text, keyboard = DemoMenuBuilder.trailing_stop_overview(
            trailing_stops=stops,
            positions=positions,
        )

        assert "BONK" in text
        assert "10%" in text
        assert "Active" in text or "🛡️" in text
        assert keyboard is not None
        # Should have edit/delete buttons
        buttons = [btn.callback_data for row in keyboard.inline_keyboard for btn in row if btn.callback_data]
        assert any("tsl_edit" in btn for btn in buttons)
        assert any("tsl_delete" in btn for btn in buttons)

    def test_trailing_stop_setup_no_position(self):
        """Test trailing stop setup showing position selection."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        positions = [
            {"id": "pos1", "symbol": "BONK", "pnl_pct": 15.0},
            {"id": "pos2", "symbol": "WIF", "pnl_pct": -5.0},
        ]

        text, keyboard = DemoMenuBuilder.trailing_stop_setup(positions=positions)

        assert "TRAILING" in text.upper() or "🛡️" in text
        assert "Select" in text or "Position" in text
        assert keyboard is not None
        # Should show position buttons
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("BONK" in btn for btn in buttons)
        assert any("WIF" in btn for btn in buttons)

    def test_trailing_stop_setup_with_position(self):
        """Test trailing stop setup with position selected, showing trail % options."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        position = {
            "id": "pos1",
            "symbol": "BONK",
            "entry_price": 0.00001,
            "current_price": 0.00002,
            "pnl_pct": 100.0,
        }

        text, keyboard = DemoMenuBuilder.trailing_stop_setup(position=position)

        assert "BONK" in text
        assert "Entry" in text or "entry" in text
        assert "Current" in text or "current" in text
        assert keyboard is not None
        # Should have percentage buttons (5%, 10%, 15%, 20%)
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("5%" in btn for btn in buttons)
        assert any("10%" in btn for btn in buttons)
        assert any("15%" in btn for btn in buttons)
        assert any("20%" in btn for btn in buttons)

    def test_trailing_stop_created(self):
        """Test trailing stop created success message."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.trailing_stop_created(
            symbol="BONK",
            trail_percent=10,
            initial_stop=0.000018,
            current_price=0.00002,
        )

        assert "BONK" in text
        assert "10%" in text
        assert "CREATED" in text.upper() or "✅" in text
        assert "Stop" in text or "stop" in text
        assert keyboard is not None
        # Should have button to view all stops
        buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert any("Stop" in btn or "🛡️" in btn for btn in buttons)


class TestSentimentIntegration:
    """Test sentiment engine integration."""

    @pytest.mark.asyncio
    async def test_get_market_regime(self):
        """Test market regime fetching."""
        from tg_bot.handlers.demo import get_market_regime

        regime = await get_market_regime()

        assert regime is not None
        assert "regime" in regime
        assert regime["regime"] in ["BULL", "BEAR", "NEUTRAL", "UNKNOWN"]


class TestJarvisTheme:
    """Test UI theme constants."""

    def test_theme_constants(self):
        """Test theme constants exist."""
        from tg_bot.handlers.demo import JarvisTheme

        assert JarvisTheme.LIVE == "🟢"
        assert JarvisTheme.BUY == "🟢"
        assert JarvisTheme.SELL == "🔴"
        assert JarvisTheme.AUTO == "🤖"
        assert JarvisTheme.ROCKET == "🚀"


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_trade_intelligence(self):
        """Test getting trade intelligence engine."""
        from tg_bot.handlers.demo import get_trade_intelligence

        engine = get_trade_intelligence()
        # May be None if not properly initialized, but shouldn't crash
        assert engine is None or hasattr(engine, "record_trade")

    def test_get_bags_client(self):
        """Test getting Bags client."""
        from tg_bot.handlers.demo import get_bags_client

        client = get_bags_client()
        # May be None if not properly initialized
        assert client is None or hasattr(client, "swap")


class TestSentimentHubFeature:
    """Test Sentiment Hub UI components."""

    def test_sentiment_hub_main_no_wallet(self):
        """Test main hub view without wallet connected."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.sentiment_hub_main(
            market_regime={"regime": "BULL", "risk_level": "LOW"},
            last_report_time=datetime.now(timezone.utc),
            report_interval_minutes=15,
            wallet_connected=False,
        )

        assert "SENTIMENT HUB" in text
        assert "BULL" in text or "Bullish" in text.upper()
        assert "Next Report" in text or "countdown" in text.lower()
        assert keyboard is not None
        # Should have buttons for different sections
        assert any("bluechips" in str(btn.callback_data).lower() or "top10" in str(btn.callback_data).lower()
                   for row in keyboard.inline_keyboard for btn in row)

    def test_sentiment_hub_main_with_wallet(self):
        """Test main hub view with wallet connected."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.sentiment_hub_main(
            market_regime={"regime": "NEUTRAL", "risk_level": "NORMAL"},
            last_report_time=datetime.now(timezone.utc) - timedelta(minutes=10),
            report_interval_minutes=15,
            wallet_connected=True,
        )

        assert "SENTIMENT HUB" in text
        assert keyboard is not None

    def test_sentiment_hub_section_bluechips(self):
        """Test section view for blue chips."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        picks = [
            {"symbol": "SOL", "address": "So111", "price": 225.0, "change_24h": 2.5,
             "conviction": "HIGH", "tp_percent": 20, "sl_percent": 10, "score": 85},
            {"symbol": "JUP", "address": "JUP111", "price": 1.25, "change_24h": 5.0,
             "conviction": "MEDIUM", "tp_percent": 15, "sl_percent": 8, "score": 78},
        ]

        text, keyboard = DemoMenuBuilder.sentiment_hub_section(
            section="bluechips",
            picks=picks,
            market_regime={"regime": "BULL"},
        )

        assert "SOL" in text
        assert "JUP" in text
        assert "225" in text or "$225" in text
        assert keyboard is not None

    def test_sentiment_hub_section_trending(self):
        """Test section view for trending tokens."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        picks = [
            {"symbol": "FARTCOIN", "address": "FART111", "price": 0.001, "change_24h": 145.0,
             "conviction": "VERY HIGH", "tp_percent": 50, "sl_percent": 25, "score": 92},
        ]

        text, keyboard = DemoMenuBuilder.sentiment_hub_section(
            section="trending",
            picks=picks,
            market_regime={"regime": "BULL"},
        )

        assert "FARTCOIN" in text
        assert "145" in text  # Change percentage
        assert keyboard is not None

    def test_sentiment_hub_wallet_empty(self):
        """Test wallet view with no wallet."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.sentiment_hub_wallet(
            wallet_address="",
            sol_balance=0.0,
            usd_value=0.0,
            has_private_key=False,
        )

        assert "Wallet" in text or "wallet" in text
        assert keyboard is not None
        # Should have create/import options
        assert any("create" in str(btn.callback_data).lower() or "import" in str(btn.callback_data).lower()
                   for row in keyboard.inline_keyboard for btn in row)

    def test_sentiment_hub_wallet_connected(self):
        """Test wallet view with connected wallet."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.sentiment_hub_wallet(
            wallet_address="9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
            sol_balance=5.5,
            usd_value=1237.50,
            has_private_key=True,
        )

        assert "9BB6" in text or "pump" in text  # Address shown
        assert "5.5" in text or "5.50" in text  # Balance shown
        assert keyboard is not None

    def test_sentiment_hub_news(self):
        """Test news view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        news = [
            {"title": "SOL breaks $225", "source": "CoinDesk", "time": "2h ago", "sentiment": "bullish"},
            {"title": "Fed signals pause", "source": "Reuters", "time": "4h ago", "sentiment": "neutral"},
        ]
        macro = {"dxy_trend": "weakening", "fed_stance": "neutral", "risk_appetite": "high"}

        text, keyboard = DemoMenuBuilder.sentiment_hub_news(
            news_items=news,
            macro_analysis=macro,
        )

        assert "SOL breaks" in text or "225" in text
        assert "CoinDesk" in text
        assert keyboard is not None

    def test_sentiment_hub_traditional(self):
        """Test traditional markets view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        stocks = {"spy_change": 0.45, "qqq_change": 0.72, "outlook": "bullish"}
        dxy = {"value": 103.25, "change": -0.15, "trend": "weakening"}
        commodities = [{"symbol": "GOLD", "price": 2045.50, "change": 0.8}]

        text, keyboard = DemoMenuBuilder.sentiment_hub_traditional(
            stocks_outlook=stocks,
            dxy_data=dxy,
            commodities=commodities,
        )

        assert "103" in text  # DXY value
        assert "GOLD" in text
        assert keyboard is not None

    def test_sentiment_hub_buy_confirm(self):
        """Test buy confirmation view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.sentiment_hub_buy_confirm(
            symbol="BONK",
            address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            price=0.0000325,
            auto_sl_percent=15,
        )

        assert "BONK" in text
        assert "15%" in text  # SL percentage
        assert "Stop" in text or "SL" in text
        assert keyboard is not None


class TestInstaSnipeFeature:
    """Test Insta Snipe UI components."""

    def test_insta_snipe_with_token(self):
        """Test insta snipe view with a hot token."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        hottest = {
            "symbol": "FARTCOIN",
            "address": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
            "price": 0.00125,
            "change_24h": 145.5,
            "volume_24h": 2500000,
            "liquidity": 850000,
            "market_cap": 125000000,
            "conviction": "VERY HIGH",
            "sentiment_score": 92,
            "entry_timing": "GOOD",
            "sightings": 3,
        }

        text, keyboard = DemoMenuBuilder.insta_snipe_menu(
            hottest_token=hottest,
            market_regime={"regime": "BULL"},
            auto_sl_percent=15.0,
            auto_tp_percent=15.0,
        )

        assert "INSTA SNIPE" in text
        assert "FARTCOIN" in text
        assert "92" in text  # Sentiment score
        assert "VERY HIGH" in text or "🔥🔥🔥" in text  # Conviction
        assert "15%" in text  # SL/TP
        assert keyboard is not None
        # Should have snipe buttons
        assert any("snipe" in str(btn.callback_data).lower()
                   for row in keyboard.inline_keyboard for btn in row)

    def test_insta_snipe_no_token(self):
        """Test insta snipe view without a qualifying token."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.insta_snipe_menu(
            hottest_token=None,
            market_regime={"regime": "NEUTRAL"},
        )

        assert "INSTA SNIPE" in text
        assert "Scanning" in text or "No qualifying" in text
        assert keyboard is not None
        # Should have refresh option
        assert any("refresh" in str(btn.callback_data).lower() or "insta_snipe" in str(btn.callback_data).lower()
                   for row in keyboard.inline_keyboard for btn in row)

    def test_snipe_confirm(self):
        """Test snipe confirmation view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.snipe_confirm(
            symbol="FARTCOIN",
            address="9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
            amount=0.5,
            price=0.00125,
            sl_percent=15.0,
            tp_percent=15.0,
        )

        assert "CONFIRM" in text
        assert "FARTCOIN" in text
        assert "0.5" in text  # Amount
        assert "15%" in text  # SL/TP
        assert keyboard is not None

    def test_snipe_result_success(self):
        """Test snipe success result."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.snipe_result(
            success=True,
            symbol="FARTCOIN",
            amount=0.5,
            tx_hash="5xYz1234567890abcdefABCDEF",
            sl_set=True,
            tp_set=True,
        )

        assert "SUCCESSFUL" in text or "SUCCESS" in text
        assert "FARTCOIN" in text
        assert "5xYz" in text  # TX hash
        assert keyboard is not None

    def test_snipe_result_failure(self):
        """Test snipe failure result."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.snipe_result(
            success=False,
            symbol="FARTCOIN",
            amount=0.5,
            error="Insufficient balance",
        )

        assert "FAILED" in text
        assert "Insufficient" in text
        assert keyboard is not None


class TestSuccessFeeFeature:
    """Test the 0.5% success fee on winning trades."""

    def test_fee_manager_initialization(self):
        """Test fee manager can be initialized."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()
        assert manager is not None
        assert manager.SUCCESS_FEE_PERCENT == 0.5
        assert manager.total_fees_collected == 0.0
        assert manager.fee_transactions == []

    def test_fee_calculation_winning_trade(self):
        """Test fee is calculated on winning trades."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()

        result = manager.calculate_success_fee(
            entry_price=0.0001,
            exit_price=0.00015,  # 50% gain
            amount_sol=1.0,
            token_symbol="DOGE",
        )

        assert result["applies"] is True
        assert abs(result["pnl_percent"] - 50.0) < 0.01  # Allow floating point tolerance
        assert result["fee_percent"] == 0.5
        # Fee should be 0.5% of profit
        assert result["fee_amount"] > 0
        assert result["net_profit"] == result["pnl_usd"] - result["fee_amount"]

    def test_fee_calculation_losing_trade(self):
        """Test no fee on losing trades."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()

        result = manager.calculate_success_fee(
            entry_price=0.0001,
            exit_price=0.00007,  # 30% loss
            amount_sol=1.0,
            token_symbol="RUG",
        )

        assert result["applies"] is False
        assert result["fee_amount"] == 0.0
        assert "Not a winning" in result["reason"]

    def test_fee_calculation_breakeven_trade(self):
        """Test no fee on breakeven trades."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()

        result = manager.calculate_success_fee(
            entry_price=0.0001,
            exit_price=0.0001,  # No change
            amount_sol=1.0,
            token_symbol="FLAT",
        )

        assert result["applies"] is False
        assert result["fee_amount"] == 0.0

    def test_fee_stats(self):
        """Test fee stats reporting."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()
        stats = manager.get_fee_stats()

        assert stats["fee_percent"] == 0.5
        assert stats["total_collected"] == 0.0
        assert stats["transaction_count"] == 0
        assert "recent_fees" in stats

    def test_get_success_fee_manager_singleton(self):
        """Test fee manager singleton getter."""
        from core.trading.bags_client import get_success_fee_manager

        manager1 = get_success_fee_manager()
        manager2 = get_success_fee_manager()

        assert manager1 is not None
        assert manager1 is manager2  # Same instance

    def test_fee_stats_view_empty(self):
        """Test fee stats view with no fees."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.fee_stats_view()

        assert "SUCCESS FEE STATS" in text
        assert "0.5%" in text
        assert "Only on winning trades" in text
        assert "No fees collected" in text
        assert keyboard is not None

    def test_fee_stats_view_with_fees(self):
        """Test fee stats view with collected fees."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        recent_fees = [
            {"token": "PEPE", "fee_amount": 0.05, "pnl_usd": 10.0},
            {"token": "DOGE", "fee_amount": 0.10, "pnl_usd": 20.0},
        ]

        text, keyboard = DemoMenuBuilder.fee_stats_view(
            fee_percent=0.5,
            total_collected=0.15,
            transaction_count=2,
            recent_fees=recent_fees,
        )

        assert "SUCCESS FEE STATS" in text
        assert "$0.15" in text or "0.1500" in text  # Total collected
        assert "2 fee-bearing trades" in text
        assert "PEPE" in text
        assert "DOGE" in text
        assert keyboard is not None


class TestPnlReportView:
    """Test the P&L report view UI."""

    def test_pnl_report_empty(self):
        """Test P&L report with no positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.pnl_report_view()

        assert "P&L REPORT" in text
        assert "Total P&L" in text
        assert "Win Rate" in text
        assert "No open positions" in text
        assert keyboard is not None

    def test_pnl_report_with_positions(self):
        """Test P&L report with positions."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        positions = [
            {"symbol": "PEPE", "pnl_pct": 25.5, "pnl_usd": 5.0},
            {"symbol": "DOGE", "pnl_pct": -10.0, "pnl_usd": -2.0},
            {"symbol": "WIF", "pnl_pct": 50.0, "pnl_usd": 10.0},
        ]
        best = {"symbol": "WIF", "pnl_pct": 50.0}
        worst = {"symbol": "DOGE", "pnl_pct": -10.0}

        text, keyboard = DemoMenuBuilder.pnl_report_view(
            positions=positions,
            total_pnl_usd=13.0,
            total_pnl_percent=21.8,
            winners=2,
            losers=1,
            best_trade=best,
            worst_trade=worst,
        )

        assert "P&L REPORT" in text
        assert "+$13.00" in text or "13.00" in text
        assert "Winners: 🟢 2" in text
        assert "Losers: 🔴 1" in text
        assert "WIF" in text  # Best trade
        assert "DOGE" in text  # Worst trade
        assert keyboard is not None


class TestClosePositionResult:
    """Test the close position result UI with success fee."""

    def test_close_position_winning_trade_with_fee(self):
        """Test close result shows fee on winning trade."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.close_position_result(
            success=True,
            symbol="PEPE",
            amount=0.5,
            entry_price=0.0001,
            exit_price=0.00015,
            pnl_usd=11.25,  # $11.25 profit
            pnl_percent=50.0,
            success_fee=0.05625,  # 0.5% of $11.25
            net_profit=11.19375,
            tx_hash="5xYz1234567890abcdefABCDEF",
        )

        assert "POSITION CLOSED" in text
        assert "PEPE" in text
        assert "P&L" in text
        assert "+$11.25" in text or "11.25" in text
        assert "Success Fee" in text
        assert "0.5%" in text
        assert "Net Profit" in text
        assert keyboard is not None

    def test_close_position_losing_trade_no_fee(self):
        """Test close result shows no fee on losing trade."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.close_position_result(
            success=True,
            symbol="RUG",
            amount=0.5,
            entry_price=0.0001,
            exit_price=0.00007,
            pnl_usd=-7.5,
            pnl_percent=-30.0,
            success_fee=0.0,
            tx_hash="abc123xyz",
        )

        assert "POSITION CLOSED" in text
        assert "RUG" in text
        assert "No success fee" in text or "losing trade" in text
        assert keyboard is not None

    def test_close_position_failed(self):
        """Test close position failure view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.close_position_result(
            success=False,
            symbol="FAIL",
            amount=0.5,
            entry_price=0.0001,
            exit_price=0.0001,
            pnl_usd=0,
            pnl_percent=0,
            error="Slippage too high",
        )

        assert "FAILED" in text
        assert "Slippage" in text
        assert keyboard is not None


class TestWalletImportExport:
    """Test wallet import/export UI components."""

    def test_wallet_import_prompt(self):
        """Test wallet import prompt view."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_import_prompt()

        assert "IMPORT WALLET" in text
        assert "Private Key" in text
        assert "Seed Phrase" in text
        assert "Security Warning" in text
        assert keyboard is not None
        # Should have key and seed options
        assert any("import_mode" in str(btn.callback_data)
                   for row in keyboard.inline_keyboard for btn in row)

    def test_wallet_import_input_key(self):
        """Test wallet import input view for private key."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="key")

        assert "PRIVATE KEY" in text
        assert "Base58" in text
        assert keyboard is not None

    def test_wallet_import_input_seed(self):
        """Test wallet import input view for seed phrase."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_import_input(import_type="seed")

        assert "SEED PHRASE" in text
        assert "12 or 24 word" in text
        assert keyboard is not None

    def test_wallet_import_result_success(self):
        """Test wallet import success result."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_import_result(
            success=True,
            wallet_address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        )

        assert "WALLET IMPORTED" in text
        assert "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" in text
        assert "Delete the message" in text
        assert keyboard is not None

    def test_wallet_import_result_failure(self):
        """Test wallet import failure result."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.wallet_import_result(
            success=False,
            error="Invalid private key format",
        )

        assert "IMPORT FAILED" in text
        assert "Invalid private key" in text
        assert keyboard is not None

    def test_export_key_show(self):
        """Test private key export display."""
        from tg_bot.handlers.demo import DemoMenuBuilder

        text, keyboard = DemoMenuBuilder.export_key_show(
            private_key="5KQwrPbwdL6PhXujxW37FSSQZ1JiwsST4cqQzDeyXtP79zkvFD3",
            wallet_address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        )

        assert "PRIVATE KEY" in text
        assert "5KQwrPbwdL6PhXujxW37FSSQZ1JiwsST4cqQzDeyXtP79zkvFD3" in text
        assert "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" in text
        assert "CRITICAL SECURITY" in text
        assert "NEVER share" in text
        assert keyboard is not None


# Integration tests
class TestDemoIntegration:
    """Integration tests for the demo system."""

    def test_full_trade_cycle(self):
        """Test recording a trade and getting a recommendation."""
        from core.trade_intelligence import TradeIntelligenceEngine

        engine = TradeIntelligenceEngine()

        # Record some training trades
        for i in range(20):
            win = i % 3 != 0  # ~67% win rate
            engine.record_trade(
                trade_id=f"cycle_{i:03d}",
                token_address="So11111111111111111111111111111111111111112",
                token_symbol=f"CYC{i}",
                entry_price=0.0001,
                exit_price=0.00015 if win else 0.00007,
                amount_sol=1.0,
                entry_time=datetime.now(timezone.utc) - timedelta(hours=1),
                exit_time=datetime.now(timezone.utc),
                market_regime="BULL",
                sentiment_score=0.65,
                signal_type="BUY",
            )

        # Get recommendation
        rec = engine.get_trade_recommendation(
            signal_type="BUY",
            market_regime="BULL",
            sentiment_score=0.65,
        )

        # Should have learned that BUY in BULL is good
        assert rec["action"] in ["BUY", "NEUTRAL"]
        assert rec["confidence"] > 0.5

        # Check learning summary
        summary = engine.get_learning_summary()
        assert summary["total_trades_analyzed"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
