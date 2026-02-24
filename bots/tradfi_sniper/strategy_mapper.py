from pydantic import BaseModel
from typing import Dict

class TradFiConfig(BaseModel):
    strategyId: str
    stopLossPct: float
    takeProfitPct: float
    minLiquidityUsd: float

# These MUST exactly match the parameters established in the jarvis-sniper frontend UI
# found at: src/app/api/backtest/route.ts -> STRATEGY_CONFIGS
TRADFI_PRESETS_MAP: Dict[str, TradFiConfig] = {
    "xstock_intraday": TradFiConfig(
        strategyId="xstock_intraday", stopLossPct=4.0, takeProfitPct=10.0, minLiquidityUsd=10000.0
    ),
    "prestock_speculative": TradFiConfig(
        strategyId="prestock_speculative", stopLossPct=4.0, takeProfitPct=10.0, minLiquidityUsd=5000.0
    ),
    "index_leveraged": TradFiConfig(
        strategyId="index_leveraged", stopLossPct=4.0, takeProfitPct=10.0, minLiquidityUsd=10000.0
    )
}

def load_tradfi_strategy(preset_name: str) -> TradFiConfig:
    """Enforces execution boundaries for Solana SPL equities bridging to the Sniper UI."""
    if preset_name not in TRADFI_PRESETS_MAP:
        raise ValueError(f"Invalid TradFi preset: {preset_name}")
    return TRADFI_PRESETS_MAP[preset_name]
