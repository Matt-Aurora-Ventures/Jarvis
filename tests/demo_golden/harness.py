"""Golden snapshot harness for /demo and key Telegram commands.

Runs handlers with mocked dependencies to produce deterministic outputs.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
import re
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, Mock, patch

from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes

# Ensure project root is on sys.path for direct execution
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class GoldenResult:
    text: str
    parse_mode: Optional[str]
    keyboard: Optional[List[List[Dict[str, Optional[str]]]]]


def _serialize_keyboard(reply_markup) -> Optional[List[List[Dict[str, Optional[str]]]]]:
    if not reply_markup:
        return None
    rows: List[List[Dict[str, Optional[str]]]] = []
    for row in reply_markup.inline_keyboard:
        row_data = []
        for button in row:
            row_data.append(
                {
                    "text": button.text,
                    "callback_data": getattr(button, "callback_data", None),
                }
            )
        rows.append(row_data)
    return rows


def _normalize_text(text: str) -> str:
    # Trim outer whitespace for stability
    cleaned = text.strip()
    # Dates/times
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", cleaned)
    cleaned = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<TIME>", cleaned)
    # Position or tx identifiers
    cleaned = re.sub(r"\bpos_[A-Za-z0-9]+\b", "pos_<ID>", cleaned)
    cleaned = re.sub(r"\bpending_[A-Za-z0-9]+\b", "pending_<ID>", cleaned)
    cleaned = re.sub(r"\btx_[A-Za-z0-9]+\b", "tx_<ID>", cleaned)
    # Long opaque ids / addresses
    cleaned = re.sub(r"\b[A-Za-z0-9]{24,}\b", "<ID>", cleaned)
    return cleaned


def _build_mock_update(user_id: int = 111111111, username: str = "admin") -> Update:
    user = Mock(spec=User)
    user.id = user_id
    user.username = username
    user.first_name = "Admin"
    user.last_name = "User"

    chat = Mock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"

    message = Mock(spec=Message)
    message.chat = chat
    message.chat_id = chat.id
    message.from_user = user
    message.message_id = 1
    message.reply_text = AsyncMock()
    message.edit_text = AsyncMock()
    message.delete = AsyncMock()

    update = Mock(spec=Update)
    update.update_id = 1
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    update.message = message
    return update


def _build_callback_update(data: str, base_update: Update) -> Update:
    message = base_update.effective_message
    query = Mock(spec=CallbackQuery)
    query.id = "callback_123"
    query.from_user = base_update.effective_user
    query.message = message
    query.data = data
    query.answer = AsyncMock()

    update = Mock(spec=Update)
    update.update_id = 2
    update.effective_user = base_update.effective_user
    update.effective_chat = base_update.effective_chat
    update.effective_message = message
    update.callback_query = query
    update.message = None
    return update


def _build_context() -> ContextTypes.DEFAULT_TYPE:
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.user_data = {}
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context


class _FakeTreasury:
    def __init__(self, address: str):
        self.address = address


class _FakeWallet:
    def __init__(self, address: str):
        self._treasury = _FakeTreasury(address)

    def get_treasury(self):
        return self._treasury


class _FakePosition:
    def __init__(
        self,
        token_symbol: str,
        entry_price: float,
        current_price: float,
        pnl_usd: float,
        pnl_pct: float,
        pos_id: str,
    ):
        self.token_symbol = token_symbol
        self.entry_price = entry_price
        self.current_price = current_price
        self.unrealized_pnl = pnl_usd
        self.unrealized_pnl_pct = pnl_pct
        self.take_profit_price = entry_price * 1.2
        self.stop_loss_price = entry_price * 0.9
        self.id = pos_id
        self.token_mint = "So11111111111111111111111111111111111111112"
        self.entry_usd = entry_price * 1000


class _FakeEngine:
    def __init__(self, positions: List[_FakePosition], address: str = "DemoWallet1111111111111111111111111111111111"):
        self._positions = positions
        self.wallet = _FakeWallet(address)
        self.dry_run = True
        self.max_positions = 5
        self.risk_level = Mock()
        self.risk_level.value = "MODERATE"

    async def get_portfolio_value(self):
        return 10.0, 2000.0

    async def update_positions(self):
        return None

    def get_open_positions(self):
        return list(self._positions)


class _FakeScorekeeper:
    def __init__(self):
        self.scorecard = Mock()
        self.scorecard.win_rate = 62.5
        self.scorecard.current_streak = 3
        self.scorecard.total_pnl_sol = 1.2345


class _FakeFeeManager:
    def calculate_success_fee(self, entry_price, exit_price, amount_sol, token_symbol):
        return {"applies": True, "fee_amount": 0.12, "net_profit": 1.23}


class _FakeIntelligence:
    def get_learning_summary(self):
        return {
            "total_trades_analyzed": 42,
            "pattern_memories": 7,
            "stable_strategies": 3,
            "signals": {
                "fast_breakout_v1": {"win_rate": "58%", "avg_return": "12%", "trades": 11},
                "mean_revert_v2": {"win_rate": "47%", "avg_return": "-2%", "trades": 8},
            },
            "regimes": {
                "BULL_MARKET": {"win_rate": "60%", "avg_return": "8%"},
                "RANGE_BOUND": {"win_rate": "50%", "avg_return": "1%"},
            },
            "optimal_hold_time": 90,
        }

    def get_compression_stats(self):
        return {"compression_ratio": 2.5, "learned_patterns": 12}


def _extract_last_reply(message: Message) -> GoldenResult:
    if message.reply_text.call_args_list:
        call = message.reply_text.call_args_list[-1]
    elif message.edit_text.call_args_list:
        call = message.edit_text.call_args_list[-1]
    else:
        raise AssertionError("No reply_text/edit_text calls captured")

    args, kwargs = call
    text = args[0] if args else kwargs.get("text", "")
    parse_mode = kwargs.get("parse_mode")
    keyboard = _serialize_keyboard(kwargs.get("reply_markup"))
    return GoldenResult(text=_normalize_text(text), parse_mode=parse_mode, keyboard=keyboard)


def _extract_last_edit(message: Message) -> GoldenResult:
    if not message.edit_text.call_args_list:
        raise AssertionError("No edit_text calls captured")
    call = message.edit_text.call_args_list[-1]
    args, kwargs = call
    text = args[0] if args else kwargs.get("text", "")
    parse_mode = kwargs.get("parse_mode")
    keyboard = _serialize_keyboard(kwargs.get("reply_markup"))
    return GoldenResult(text=_normalize_text(text), parse_mode=parse_mode, keyboard=keyboard)


def run_case(case_name: str) -> GoldenResult:
    base_update = _build_mock_update()
    context = _build_context()
    admin_id = base_update.effective_user.id

    # Common config mock
    config = Mock()
    config.admin_ids = {admin_id}
    config.is_admin = lambda uid, username=None: uid == admin_id
    config.telegram_token = "test-token"
    config.sentiment_interval_seconds = 3600
    config.daily_cost_limit_usd = 10.0
    config.has_grok = lambda: False
    config.get_optional_missing = lambda: []

    fake_positions = [
        _FakePosition("TEST", 0.01, 0.012, 12.34, 23.4, "pos_abc123"),
        _FakePosition("MOON", 0.02, 0.018, -4.56, -10.0, "pos_def456"),
    ]
    demo_engine = _FakeEngine(fake_positions)
    treasury_engine = _FakeEngine([fake_positions[0]])
    fake_intel = _FakeIntelligence()
    fake_bags_tokens = [
        {
            "symbol": "TEST",
            "name": "Test Token",
            "address": "So11111111111111111111111111111111111111112",
            "price_usd": 0.0123,
            "change_24h": 5.6,
            "volume_24h": 1_250_000,
            "liquidity": 480_000,
            "market_cap": 12_000_000,
            "holders": 1234,
            "sentiment": "bullish",
            "sentiment_score": 0.72,
            "signal": "BUY",
        },
        {
            "symbol": "MOON",
            "name": "Moon Token",
            "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "price_usd": 0.0042,
            "change_24h": -3.4,
            "volume_24h": 980_000,
            "liquidity": 210_000,
            "market_cap": 4_200_000,
            "holders": 842,
            "sentiment": "neutral",
            "sentiment_score": 0.51,
            "signal": "HOLD",
        },
    ]

    async def _simple_report(update, _context):
        await update.message.reply_text(
            "*report*\n\nall systems nominal.\n",
            parse_mode="Markdown",
        )

    async def _trade_ticket(query, token):
        await query.message.reply_text(
            f"*trade ticket* {token}",
            parse_mode="Markdown",
        )

    async def _close_position(query, pos_id):
        await query.message.reply_text(
            f"*position closed* {pos_id}",
            parse_mode="Markdown",
        )

    with ExitStack() as stack:
        stack.enter_context(patch("tg_bot.handlers.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.handlers.commands_base.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.handlers.sentiment.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.handlers.trading.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.handlers.trading._is_rate_limited", return_value=False))
        stack.enter_context(patch("tg_bot.handlers.demo.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.handlers.demo.demo_core.get_config", return_value=config))
        stack.enter_context(patch("tg_bot.bot_core.SENTIMENT_REPORT_AVAILABLE", False))
        stack.enter_context(patch("tg_bot.bot_core._generate_simple_report", new=_simple_report))
        stack.enter_context(patch("tg_bot.bot_core._get_treasury_engine", new=AsyncMock(return_value=treasury_engine)))
        stack.enter_context(patch("tg_bot.handlers.demo._get_demo_engine", new=AsyncMock(return_value=demo_engine)))
        stack.enter_context(patch("tg_bot.handlers.demo.demo_core._get_demo_engine", new=AsyncMock(return_value=demo_engine)))
        stack.enter_context(
            patch(
                "tg_bot.handlers.demo.get_market_regime",
                new=AsyncMock(return_value={"regime": "BULL", "risk_level": "LOW", "btc_change_24h": 1.2, "sol_change_24h": -0.4}),
            )
        )
        stack.enter_context(
            patch(
                "tg_bot.handlers.demo.demo_core.get_market_regime",
                new=AsyncMock(return_value={"regime": "BULL", "risk_level": "LOW", "btc_change_24h": 1.2, "sol_change_24h": -0.4}),
            )
        )
        stack.enter_context(patch("tg_bot.handlers.demo.get_trending_with_sentiment", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("tg_bot.handlers.demo.get_bags_top_tokens_with_sentiment", new=AsyncMock(return_value=fake_bags_tokens)))
        stack.enter_context(
            patch(
                "tg_bot.handlers.demo.demo_sentiment.get_market_regime",
                new=AsyncMock(return_value={"regime": "BULL", "risk_level": "LOW", "btc_change_24h": 1.2, "sol_change_24h": -0.4}),
            )
        )
        stack.enter_context(patch("tg_bot.handlers.demo.demo_sentiment.get_trending_with_sentiment", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("tg_bot.handlers.demo.demo_sentiment.get_bags_top_tokens_with_sentiment", new=AsyncMock(return_value=fake_bags_tokens)))
        stack.enter_context(patch("core.dexscreener.get_boosted_tokens_with_data", return_value=[]))
        stack.enter_context(
            patch(
                "tg_bot.handlers.demo._execute_swap_with_fallback",
                new=AsyncMock(return_value={"success": True, "amount_out": 12345, "tx_hash": "tx_demo", "source": "bags_fm"}),
            )
        )
        stack.enter_context(patch("tg_bot.handlers.demo.get_success_fee_manager", return_value=_FakeFeeManager()))
        stack.enter_context(patch("tg_bot.handlers.demo.get_trade_intelligence", return_value=fake_intel))
        stack.enter_context(patch("bots.treasury.scorekeeper.get_scorekeeper", return_value=_FakeScorekeeper()))
        stack.enter_context(patch("tg_bot.bot_core._is_treasury_admin", return_value=True))
        stack.enter_context(patch("tg_bot.bot_core._show_trade_ticket", new=_trade_ticket))
        stack.enter_context(patch("tg_bot.bot_core._close_position_callback", new=_close_position))

        if case_name == "start_admin":
            from tg_bot.handlers.commands_base import start
            context.args = []
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(start(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "help_admin":
            from tg_bot.handlers.commands_base import help_command
            context.args = []
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(help_command(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "dashboard_empty":
            from tg_bot.handlers.trading import dashboard
            # Empty positions to avoid network
            treasury_engine._positions = []
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(dashboard(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "positions_sample":
            from tg_bot.handlers.trading import positions
            treasury_engine._positions = [fake_positions[0]]
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(positions(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "report_simple":
            from tg_bot.handlers.sentiment import report
            context.args = []
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(report(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "trade_ticket":
            from tg_bot.handlers.trading import button_callback
            cb_update = _build_callback_update("trade_So11111111111111111111111111111111111111112", base_update)
            cb_update.callback_query.message.reply_text.reset_mock()
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(button_callback(cb_update, context))
            return _extract_last_reply(cb_update.callback_query.message)

        if case_name == "close_position":
            from tg_bot.handlers.trading import button_callback
            cb_update = _build_callback_update("sell_pos:pos_abc123", base_update)
            cb_update.callback_query.message.reply_text.reset_mock()
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(button_callback(cb_update, context))
            return _extract_last_reply(cb_update.callback_query.message)

        if case_name == "demo_main":
            from tg_bot.handlers.demo import demo
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "demo_positions":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:positions", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_buy_prompt":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:buy:0.1", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_bags_fm":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:bags_fm", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_insta_snipe":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:insta_snipe", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_buy_confirm":
            from tg_bot.handlers.demo import demo_message_handler
            context.user_data["awaiting_token"] = True
            context.user_data["buy_amount"] = 0.1
            base_update.message.text = "So11111111111111111111111111111111111111112"
            base_update.message.reply_text.reset_mock()
            base_update.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_message_handler(base_update, context))
            return _extract_last_reply(base_update.message)

        if case_name == "demo_sell_all_confirm":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:sell_all", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_sell_position":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:sell:pos_abc123:50", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_refresh":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:refresh", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

        if case_name == "demo_learning":
            from tg_bot.handlers.demo import demo_callback
            cb_update = _build_callback_update("demo:learning", base_update)
            cb_update.callback_query.message.edit_text.reset_mock()
            import asyncio
            asyncio.run(demo_callback(cb_update, context))
            return _extract_last_edit(cb_update.callback_query.message)

    raise ValueError(f"Unknown case: {case_name}")


def generate_golden(output_dir: Path, cases: List[str]) -> Dict[str, GoldenResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, GoldenResult] = {}
    for case in cases:
        result = run_case(case)
        results[case] = result
        payload = {
            "text": result.text,
            "parse_mode": result.parse_mode,
            "keyboard": result.keyboard,
        }
        (output_dir / f"{case}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    cases = [
        "start_admin",
        "help_admin",
        "dashboard_empty",
        "positions_sample",
        "report_simple",
        "trade_ticket",
        "close_position",
        "demo_main",
        "demo_positions",
        "demo_buy_prompt",
        "demo_bags_fm",
        "demo_insta_snipe",
        "demo_buy_confirm",
        "demo_sell_all_confirm",
        "demo_sell_position",
        "demo_refresh",
        "demo_learning",
    ]
    base = Path(__file__).resolve().parent
    generate_golden(base / "golden", cases)
