from typing import Dict, Any, Optional
from core.open_claw.signals.engines import MacroEngine, MicroEngine, PolicyEnvelope
from core.open_claw.signals.stats import wilson_lower_bound
import asyncio

class OpenClawSDK:
    """
    Decoupled algorithmic logic entrypoint for Open Claw strategy execution.
    It takes purely mathematical bounds and parses inputs through the Bifurcated engines.
    """
    def __init__(self, default_leverage: float = 1.0):
        self.default_leverage = default_leverage
        self.macro_engine = MacroEngine()
        # Mock states
        self.historical_performance: Dict[str, Dict[str, int]] = {
            "strategy_1": {"wins": 95, "total": 100},
            "strategy_2": {"wins": 1, "total": 1}
        }

    async def evaluate_market_opportunity(self, strategy_id: str, market: str, current_price: float, xai_client=None) -> Dict[str, Any]:
        """
        Main pipeline blending engines and statistical confidence gates.
        Does not touch execution directly. Only returns instruction packages.
        """
        # 1. Gate: Check Strategy Confidence via Wilson Lower Bound
        perf = self.historical_performance.get(strategy_id, {"wins": 0, "total": 0})
        confidence = wilson_lower_bound(perf["wins"], perf["total"])

        if confidence < 0.60:
            return {"action": "FLAT", "reason": "Low confidence score", "confidence": confidence}

        # 2. Macro Envelope: Get broad bounds
        policy = self.macro_engine.generate_policy(market, current_price)

        # 3. Micro Tick Check: Fast safety validations
        micro = MicroEngine(policy)
        safe_to_execute = await micro.evaluate_tick(market, current_price, xai_client)

        if not safe_to_execute:
            return {"action": "FLAT", "reason": "Micro engine safety failed or envelope invalidated", "confidence": confidence}

        # Passed all gates
        return {
            "action": policy.bias,
            "max_leverage": min(self.default_leverage, policy.max_lev),
            "confidence": confidence,
            "reason": "Passed all decoupled checks."
        }
