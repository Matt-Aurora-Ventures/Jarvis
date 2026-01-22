"""
JARVIS Tool Contracts - Strict I/O for all tools.

Every tool must declare:
- inputs (schema)
- outputs (schema)
- side effects
- failure modes

No "freeform" tool calls in production paths.

Usage:
    from core.tools import Tool, ToolContract, tool_registry

    @Tool(
        name="get_price",
        description="Get token price",
        inputs={"token": str, "chain": str},
        outputs={"price": float, "timestamp": int},
        side_effects=[],
        cost_estimate=0.001,
    )
    async def get_price(token: str, chain: str = "solana") -> dict:
        ...

    # Execute with logging
    result = await tool_registry.execute("get_price", token="SOL")

    # Replay a previous call
    result = await tool_registry.replay(call_id="abc123")
"""

from .contract import (
    Tool,
    ToolContract,
    ToolCall,
    ToolResult,
    ToolCategory,
)
from .registry import (
    ToolRegistry,
    get_tool_registry,
)
from .replay import (
    ToolCallLog,
    get_call_log,
)

__all__ = [
    # Contract
    "Tool",
    "ToolContract",
    "ToolCall",
    "ToolResult",
    "ToolCategory",
    # Registry
    "ToolRegistry",
    "get_tool_registry",
    # Replay
    "ToolCallLog",
    "get_call_log",
]
