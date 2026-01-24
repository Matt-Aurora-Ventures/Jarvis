import json
from types import SimpleNamespace

import pytest

from bots.treasury.trading.trading_risk import RiskChecker
from bots.treasury.trading.constants import (
    ESTABLISHED_TOKENS,
    MAX_HIGH_RISK_POSITION_PCT,
    MAX_UNVETTED_POSITION_PCT,
    MAX_TRADE_USD,
    MAX_DAILY_USD,
    MAX_POSITION_PCT,
    TP_SL_CONFIG,
)


def test_classify_token_risk_established():
    mint = next(iter(ESTABLISHED_TOKENS.keys()))
    tier = RiskChecker.classify_token_risk(mint, ESTABLISHED_TOKENS[mint])
    assert tier == "ESTABLISHED"


def test_classify_token_risk_high_risk():
    tier = RiskChecker.classify_token_risk("pump_fun_token", "PUMP")
    assert tier == "HIGH_RISK"


def test_risk_adjusted_position_size_high_risk():
    base = 100.0
    adjusted, tier = RiskChecker.get_risk_adjusted_position_size("pump_token", "PUMP", base)
    assert tier == "HIGH_RISK"
    assert adjusted == pytest.approx(base * MAX_HIGH_RISK_POSITION_PCT)


def test_risk_adjusted_position_size_micro():
    base = 100.0
    adjusted, tier = RiskChecker.get_risk_adjusted_position_size("unknown_token", "ZZZ", base)
    assert tier == "MICRO"
    assert adjusted == pytest.approx(base * MAX_UNVETTED_POSITION_PCT)


def test_check_spending_limits_exceeds_single_trade():
    checker = RiskChecker(daily_volume_file=None)
    allowed, reason = checker.check_spending_limits(MAX_TRADE_USD + 1.0, portfolio_usd=10000)
    assert allowed is False
    assert "exceeds max single trade" in reason


def test_check_spending_limits_exceeds_daily(tmp_path):
    daily_file = tmp_path / "daily_volume.json"
    checker = RiskChecker(daily_volume_file=daily_file)

    checker.add_daily_volume(MAX_DAILY_USD - 10.0)
    allowed, reason = checker.check_spending_limits(20.0, portfolio_usd=10000)

    assert allowed is False
    assert "Daily limit reached" in reason


def test_check_spending_limits_position_pct(tmp_path):
    daily_file = tmp_path / "daily_volume.json"
    checker = RiskChecker(daily_volume_file=daily_file)
    checker.add_daily_volume(0.0)

    portfolio_usd = 100.0
    amount_usd = (MAX_POSITION_PCT * portfolio_usd) + 1.0

    allowed, reason = checker.check_spending_limits(amount_usd, portfolio_usd=portfolio_usd)
    assert allowed is False
    assert "exceeds max" in reason


def test_get_tp_sl_levels_defaults():
    entry_price = 100.0
    tp, sl = RiskChecker.get_tp_sl_levels(entry_price, "B")
    assert tp == pytest.approx(entry_price * (1 + TP_SL_CONFIG["B"]["take_profit"]))
    assert sl == pytest.approx(entry_price * (1 - TP_SL_CONFIG["B"]["stop_loss"]))


def test_get_tp_sl_levels_custom_override():
    entry_price = 200.0
    tp, sl = RiskChecker.get_tp_sl_levels(entry_price, "A", custom_tp=0.5, custom_sl=0.25)
    assert tp == pytest.approx(entry_price * 1.5)
    assert sl == pytest.approx(entry_price * 0.75)
