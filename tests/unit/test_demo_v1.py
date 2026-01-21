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
