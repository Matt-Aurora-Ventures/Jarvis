from core.intel.tradfi_feed import get_tradfi_momentum

def test_momentum():
    bias = get_tradfi_momentum()
    assert bias in ["BULLISH", "BEARISH", "NEUTRAL"]
