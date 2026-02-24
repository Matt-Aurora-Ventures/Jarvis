from pydantic import BaseModel, root_validator
from typing import Dict

class BasketWeights(BaseModel):
    """
    Enforces the mathematically strict structure required by the ERC-7621 factory
    so the LLM cannot cause reverts by generating 101% or invalid sums.
    """
    allocations: Dict[str, float]

    @root_validator(pre=True)
    def check_weights(cls, values):
        allocs = values.get('allocations', {})
        total = sum(allocs.values())
        if not abs(total - 100.0) < 0.01:
            raise ValueError(f"Basket weights must sum to 100%. Got {total}%: {allocs}")
        return values

class GrokAllocator:
    def __init__(self, xai_client=None):
        self.client = xai_client

    async def determine_optimal_basket(self, macro_news: str) -> BasketWeights:
        """
        Polls the Grok AI model to parse narrative weightings.
        Mocks the LLM reasoning to output strict token distributions.
        """
        # Stand-in Grok behaviour evaluating recent news / narratives
        if "DeFi is booming" in macro_news:
            raw_output = {"WETH": 40.0, "UNI": 30.0, "AAVE": 30.0}
        else:
            # Default to stable/layer-1 split
            raw_output = {"WETH": 50.0, "WBTC": 50.0}

        # Forces the output through the Pydantic root_validator gate
        return BasketWeights(allocations=raw_output)
