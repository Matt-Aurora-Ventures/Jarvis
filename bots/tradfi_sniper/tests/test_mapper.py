from bots.tradfi_sniper.strategy_mapper import load_tradfi_strategy
from pydantic import ValidationError
import pytest

def test_mapper_valid():
    config = load_tradfi_strategy("xstock_intraday")
    assert config.stopLossPct == 4.0
    assert config.takeProfitPct == 10.0

def test_mapper_invalid():
    with pytest.raises(ValueError) as excinfo:
        load_tradfi_strategy("invalid_preset")
    assert "Invalid TradFi preset" in str(excinfo.value)
