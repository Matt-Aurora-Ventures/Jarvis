from bots.alvara_manager.grok_allocator import BasketWeights
from pydantic import ValidationError
import pytest

def test_basket_weights_valid():
    basket = BasketWeights(allocations={"WETH": 50.0, "LINK": 50.0})
    assert basket.allocations["WETH"] == 50.0

def test_basket_weights_invalid():
    # Sums to 110%
    with pytest.raises(ValidationError) as excinfo:
        BasketWeights(allocations={"WETH": 50.0, "LINK": 60.0})
    assert "must sum to 100%" in str(excinfo.value)

def test_basket_weights_float_math():
    basket = BasketWeights(allocations={"WETH": 33.33, "LINK": 33.33, "AAVE": 33.34})
    assert basket.allocations["WETH"] == 33.33
