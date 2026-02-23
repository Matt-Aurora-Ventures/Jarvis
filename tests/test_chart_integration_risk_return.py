"""Tests for ChartIntegration risk/return volatility computation."""

from __future__ import annotations

from io import BytesIO
from types import ModuleType, SimpleNamespace
import importlib
import sys

import pytest


def _ensure_telegram_stubs() -> None:
    """Provide telegram stubs so chart integration can import in test env."""
    if "telegram" not in sys.modules:
        telegram_mod = ModuleType("telegram")
        telegram_mod.InputMediaPhoto = object
        sys.modules["telegram"] = telegram_mod

    if "telegram.constants" not in sys.modules:
        telegram_constants_mod = ModuleType("telegram.constants")

        class _ParseMode:
            HTML = "HTML"
            MARKDOWN = "MARKDOWN"

        telegram_constants_mod.ParseMode = _ParseMode
        sys.modules["telegram.constants"] = telegram_constants_mod

    if "telegram.ext" not in sys.modules:
        telegram_ext_mod = ModuleType("telegram.ext")

        class _ContextTypes:
            DEFAULT_TYPE = object

        telegram_ext_mod.ContextTypes = _ContextTypes
        sys.modules["telegram.ext"] = telegram_ext_mod


_ensure_telegram_stubs()
chart_integration_mod = importlib.import_module("tg_bot.services.chart_integration")
ChartIntegration = chart_integration_mod.ChartIntegration


class _FakeTrader:
    def __init__(self, positions):
        self._positions = positions

    def get_open_positions(self):
        return self._positions


class _FakeDashboard:
    pass


@pytest.mark.asyncio
async def test_generate_risk_return_uses_live_price_change_for_volatility(monkeypatch):
    positions = [
        SimpleNamespace(token_symbol="SOL", current_value_usd=1000.0, unrealized_pnl_pct=4.0, token_mint=""),
        SimpleNamespace(token_symbol="BTC", current_value_usd=500.0, unrealized_pnl_pct=-2.0, token_mint=""),
    ]
    ci = ChartIntegration(_FakeTrader(positions), _FakeDashboard())

    async def fake_prices():
        return {
            "solana": {"usd_24h_change": 6.0},   # -> 42.0
            "bitcoin": {"usd_24h_change": -1.0},  # -> 7.0
        }

    from tg_bot.services.market_intelligence import MarketIntelligence

    monkeypatch.setattr(MarketIntelligence, "_fetch_live_prices", staticmethod(fake_prices))

    captured = {}

    def fake_generate_risk_return_plot(position_data):
        captured["data"] = position_data
        return BytesIO(b"png")

    ci.chart_gen.generate_risk_return_plot = fake_generate_risk_return_plot

    result = await ci._generate_risk_return_data()

    assert result is not None
    data = captured["data"]
    assert len(data) == 2
    assert data[0]["symbol"] == "SOL"
    assert data[0]["volatility"] == pytest.approx(42.0)
    assert data[1]["symbol"] == "BTC"
    assert data[1]["volatility"] == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_generate_risk_return_falls_back_to_position_pnl_when_market_data_missing(monkeypatch):
    positions = [
        SimpleNamespace(token_symbol="ABC", current_value_usd=2000.0, unrealized_pnl_pct=-12.0, token_mint=""),
    ]
    ci = ChartIntegration(_FakeTrader(positions), _FakeDashboard())

    async def fake_prices():
        return {}

    from tg_bot.services.market_intelligence import MarketIntelligence

    monkeypatch.setattr(MarketIntelligence, "_fetch_live_prices", staticmethod(fake_prices))

    captured = {}

    def fake_generate_risk_return_plot(position_data):
        captured["data"] = position_data
        return BytesIO(b"png")

    ci.chart_gen.generate_risk_return_plot = fake_generate_risk_return_plot

    result = await ci._generate_risk_return_data()

    assert result is not None
    data = captured["data"]
    assert len(data) == 1
    assert data[0]["symbol"] == "ABC"
    # Fallback volatility is abs(unrealized_pnl_pct) * 2
    assert data[0]["volatility"] == pytest.approx(24.0)


@pytest.mark.asyncio
async def test_generate_risk_return_returns_none_without_positions():
    ci = ChartIntegration(_FakeTrader([]), _FakeDashboard())
    result = await ci._generate_risk_return_data()
    assert result is None
