"""
Trading Tool Contracts - Strict I/O schemas for trading operations.

These contracts wrap the Jupiter/Bags trading APIs with proper:
- Input validation
- Output schemas
- Side effect declarations
- Cost tracking
- Audit logging

Usage:
    from core.tools.trading_contracts import get_price, get_quote, execute_swap

    # All calls are validated, logged, and trackable
    result = await get_price(token_mint="So11...112")
    print(result["price"])
"""

import logging
from typing import Optional

from core.tools import Tool, ToolCategory, get_tool_registry

logger = logging.getLogger(__name__)

# Get the registry for registration
registry = get_tool_registry()


@registry.register
@Tool(
    name="get_token_price",
    version="1.0.0",
    description="Get the current USD price for a Solana token",
    category=ToolCategory.READ_ONLY,
    inputs={
        "token_mint": str,  # Solana token mint address
    },
    outputs={
        "price": float,     # Current price in USD
        "source": str,      # Price source (jupiter, dexscreener, etc.)
    },
    required_inputs=["token_mint"],
    side_effects=[],
    cost_estimate=0.0,  # Free API call
    retry_safe=True,
    tags=["trading", "price", "query"],
)
async def get_token_price(token_mint: str) -> dict:
    """Get token price from Jupiter."""
    try:
        from bots.treasury.jupiter import JupiterClient

        jupiter = JupiterClient()
        price = await jupiter.get_token_price(token_mint)

        return {
            "price": price,
            "source": "jupiter",
        }
    except Exception as e:
        logger.error(f"get_token_price failed: {e}")
        raise


@registry.register
@Tool(
    name="get_token_info",
    version="1.0.0",
    description="Get metadata for a Solana token (name, symbol, decimals)",
    category=ToolCategory.READ_ONLY,
    inputs={
        "token_mint": str,  # Solana token mint address
    },
    outputs={
        "name": str,
        "symbol": str,
        "decimals": int,
        "logo_uri": str,
    },
    required_inputs=["token_mint"],
    side_effects=[],
    cost_estimate=0.0,
    retry_safe=True,
    tags=["trading", "metadata", "query"],
)
async def get_token_info(token_mint: str) -> dict:
    """Get token info from Jupiter."""
    try:
        from bots.treasury.jupiter import JupiterClient

        jupiter = JupiterClient()
        info = await jupiter.get_token_info(token_mint)

        if info:
            return {
                "name": info.name,
                "symbol": info.symbol,
                "decimals": info.decimals,
                "logo_uri": info.logo_uri or "",
            }
        else:
            raise ValueError(f"Token not found: {token_mint}")
    except Exception as e:
        logger.error(f"get_token_info failed: {e}")
        raise


@registry.register
@Tool(
    name="get_swap_quote",
    version="1.0.0",
    description="Get a swap quote from Jupiter DEX aggregator",
    category=ToolCategory.READ_ONLY,
    inputs={
        "input_mint": str,      # Token to sell
        "output_mint": str,     # Token to buy
        "amount": int,          # Amount in smallest units (lamports)
        "slippage_bps": int,    # Slippage tolerance in basis points
    },
    outputs={
        "in_amount": int,
        "out_amount": int,
        "price": float,
        "price_impact_pct": float,
        "route_count": int,
    },
    required_inputs=["input_mint", "output_mint", "amount"],
    side_effects=[],
    cost_estimate=0.0,
    retry_safe=True,
    tags=["trading", "quote", "query"],
)
async def get_swap_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,  # 1% default
) -> dict:
    """Get swap quote from Jupiter."""
    try:
        from bots.treasury.jupiter import JupiterClient

        jupiter = JupiterClient()
        quote = await jupiter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps,
        )

        if quote:
            return {
                "in_amount": quote.in_amount,
                "out_amount": quote.out_amount,
                "price": quote.price,
                "price_impact_pct": quote.price_impact_pct,
                "route_count": len(quote.route_plan) if hasattr(quote, 'route_plan') else 1,
            }
        else:
            raise ValueError("Failed to get quote")
    except Exception as e:
        logger.error(f"get_swap_quote failed: {e}")
        raise


@registry.register
@Tool(
    name="check_token_safety",
    version="1.0.0",
    description="Check if a token is safe to trade (not a scam/honeypot)",
    category=ToolCategory.READ_ONLY,
    inputs={
        "token_mint": str,
        "token_symbol": str,
    },
    outputs={
        "is_safe": bool,
        "is_blocked": bool,
        "is_high_risk": bool,
        "block_reason": str,
    },
    required_inputs=["token_mint"],
    side_effects=[],
    cost_estimate=0.0,
    retry_safe=True,
    tags=["trading", "safety", "query"],
)
async def check_token_safety(
    token_mint: str,
    token_symbol: str = "",
) -> dict:
    """Check token safety using treasury engine rules."""
    try:
        from bots.treasury.trading import TreasuryEngine

        # Create a minimal engine just for safety checks
        # In production, use the singleton engine
        engine = TreasuryEngine.__new__(TreasuryEngine)
        engine.BLOCKED_TOKENS = TreasuryEngine.BLOCKED_TOKENS
        engine.BLOCKED_SYMBOLS = TreasuryEngine.BLOCKED_SYMBOLS

        is_blocked, block_reason = engine.is_blocked_token(token_mint, token_symbol)
        is_high_risk = engine.is_high_risk_token(token_mint)

        return {
            "is_safe": not is_blocked and not is_high_risk,
            "is_blocked": is_blocked,
            "is_high_risk": is_high_risk,
            "block_reason": block_reason,
        }
    except Exception as e:
        logger.error(f"check_token_safety failed: {e}")
        raise


@registry.register
@Tool(
    name="execute_trade",
    version="1.0.0",
    description="Execute a swap trade via Jupiter/Bags.fm",
    category=ToolCategory.FINANCIAL,
    inputs={
        "input_mint": str,
        "output_mint": str,
        "amount": int,
        "slippage_bps": int,
    },
    outputs={
        "success": bool,
        "signature": str,
        "in_amount": int,
        "out_amount": int,
        "error": str,
    },
    required_inputs=["input_mint", "output_mint", "amount"],
    side_effects=[
        "Transfers tokens from wallet",
        "Modifies blockchain state",
        "May incur transaction fees",
    ],
    cost_estimate=0.005,  # ~0.005 SOL in fees
    requires_approval=True,  # Requires user approval
    retry_safe=False,  # NOT safe to retry blindly
    tags=["trading", "execution", "action"],
)
async def execute_trade(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 200,  # 2% default for execution
) -> dict:
    """
    Execute a trade. Requires approval.

    WARNING: This is a real trade that transfers tokens.
    Only call after user confirmation.
    """
    try:
        from bots.treasury.jupiter import JupiterClient
        from bots.treasury.wallet import SecureWallet

        jupiter = JupiterClient()
        wallet = SecureWallet()

        # Get quote
        quote = await jupiter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps,
        )

        if not quote:
            return {
                "success": False,
                "signature": "",
                "in_amount": 0,
                "out_amount": 0,
                "error": "Failed to get quote",
            }

        # Execute swap
        result = await jupiter.execute_swap(quote, wallet)

        return {
            "success": result.success,
            "signature": result.signature or "",
            "in_amount": result.in_amount,
            "out_amount": result.out_amount,
            "error": result.error or "",
        }
    except Exception as e:
        logger.error(f"execute_trade failed: {e}")
        return {
            "success": False,
            "signature": "",
            "in_amount": 0,
            "out_amount": 0,
            "error": str(e),
        }


def register_trading_tools():
    """Register all trading tools with the registry."""
    # Tools are registered via @registry.register decorators above
    logger.info(f"Trading tools registered: {registry.list_tools(category=ToolCategory.READ_ONLY)}")
    logger.info(f"Trading actions registered: {registry.list_tools(category=ToolCategory.FINANCIAL)}")


# Auto-register on import
try:
    register_trading_tools()
except Exception as e:
    logger.warning(f"Trading tools registration skipped: {e}")
