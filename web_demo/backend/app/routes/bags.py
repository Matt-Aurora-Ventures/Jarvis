"""
Bags.fm Trading Routes
Integration with bags-swap-api for Solana token swaps.
"""

from fastapi import APIRouter, HTTPException, Security, Request, status
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, Any, List
import logging

from ..services.bags_service import get_bags_service
from ..services.supervisor_bridge import get_supervisor_bridge
from ..security import get_current_user, validate_amount
from ..middleware.security_validator import (
    SwapQuoteRequest,
    SwapTransactionRequest,
    security_monitor,
    sanitize_error_message,
    log_security_event,
    validate_bags_api_key
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bags", tags=["Bags Trading"])


class QuoteRequest(BaseModel):
    """Request for swap quote."""
    input_mint: str = Field(..., description="Input token mint address")
    output_mint: str = Field(..., description="Output token mint address")
    amount: int = Field(..., gt=0, description="Amount in smallest units (lamports)")
    slippage_mode: str = Field(default="auto", description="auto or fixed")
    slippage_bps: Optional[int] = Field(default=None, description="Basis points for fixed slippage")


class SwapRequest(BaseModel):
    """Request to create swap transaction."""
    quote_response: Dict[str, Any] = Field(..., description="Quote data from /quote endpoint")
    user_public_key: str = Field(..., description="User's Solana wallet public key")


@router.post("/quote")
async def get_swap_quote(
    req: Request,
    request: SwapQuoteRequest,
    current_user: Dict = Security(get_current_user)
):
    """
    Get a quote for swapping tokens via Bags.fm.

    Returns:
        Quote with output amount, route, fees, and service fee breakdown

    Security: Input validated (Solana addresses, amounts), API key checked, errors sanitized.
    """
    # Validate Bags API configuration
    await validate_bags_api_key(req)

    bags = get_bags_service()

    try:
        # Get quote from Bags API
        quote = await bags.get_quote(
            input_mint=request.input_mint,
            output_mint=request.output_mint,
            amount=request.amount,
            slippage_mode=request.slippage_mode,
            slippage_bps=request.slippage_bps
        )

        # Log successful quote
        await log_security_event(
            event_type="quote_success",
            severity="info",
            details={
                "input_mint": request.input_mint[:8] + "...",  # Truncate for privacy
                "output_mint": request.output_mint[:8] + "...",
                "amount": request.amount
            },
            request=req
        )

        # Log to supervisor
        bridge = get_supervisor_bridge()
        bridge.publish_event(
            event_type="quote_requested",
            data={
                "input_mint": request.input_mint,
                "output_mint": request.output_mint,
                "amount": request.amount,
                "user_id": current_user["user_id"]
            }
        )

        return quote

    except ValidationError as e:
        security_monitor.log_validation_failure(
            endpoint="/api/v1/bags/quote",
            error=str(e),
            client_ip=req.client.host
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid swap quote request"
        )
    except Exception as e:
        logger.error(f"Quote error: {e}", exc_info=True)
        await log_security_event(
            event_type="quote_error",
            severity="error",
            details={"error_type": type(e).__name__},
            request=req
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message(e)
        )


@router.post("/swap")
async def create_swap_transaction(
    req: Request,
    request: SwapRequest,
    current_user: Dict = Security(get_current_user)
):
    """
    Create a swap transaction for user to sign.

    The transaction is created but NOT executed - user must sign with their wallet.

    Security: Validates user wallet address, logs transaction creation, monitors for suspicious patterns.
    """
    await validate_bags_api_key(req)

    bags = get_bags_service()

    try:
        # Create swap transaction
        swap_data = await bags.create_swap_transaction(
            quote_response=request.quote_response,
            user_public_key=request.user_public_key
        )

        # Log successful swap creation
        await log_security_event(
            event_type="swap_created",
            severity="info",
            details={
                "user_wallet": request.user_public_key[:8] + "...",
                "input_mint": request.quote_response.get("inputMint", "")[:8] + "...",
                "output_mint": request.quote_response.get("outputMint", "")[:8] + "..."
            },
            request=req
        )

        # Log to supervisor
        bridge = get_supervisor_bridge()
        bridge.publish_event(
            event_type="swap_initiated",
            data={
                "user_public_key": request.user_public_key,
                "input_mint": request.quote_response.get("inputMint"),
                "output_mint": request.quote_response.get("outputMint"),
                "in_amount": request.quote_response.get("inAmount"),
                "out_amount": request.quote_response.get("outAmount"),
                "user_id": current_user["user_id"]
            }
        )

        return swap_data

    except ValidationError as e:
        security_monitor.log_validation_failure(
            endpoint="/api/v1/bags/swap",
            error=str(e),
            client_ip=req.client.host
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid swap transaction request"
        )
    except Exception as e:
        logger.error(f"Swap creation error: {e}", exc_info=True)
        await log_security_event(
            event_type="swap_error",
            severity="error",
            details={"error_type": type(e).__name__},
            request=req
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message(e)
        )


@router.get("/tokens/popular")
async def get_popular_tokens(current_user: Dict = Security(get_current_user)):
    """
    Get list of popular tokens for UI suggestions.

    Returns:
        List of tokens with symbol, mint address, name, and decimals
    """
    bags = get_bags_service()

    try:
        tokens = await bags.get_popular_tokens()
        return {"tokens": tokens}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_bags_health():
    """
    Check if Bags.fm service is healthy.

    Public endpoint (no auth required).
    """
    bags = get_bags_service()
    health = await bags.get_health()
    return health


@router.get("/stats")
async def get_bags_stats(current_user: Dict = Security(get_current_user)):
    """
    Get Bags.fm usage statistics (admin only).

    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    bags = get_bags_service()

    stats = await bags.get_usage_stats()

    if stats is None:
        raise HTTPException(
            status_code=503,
            detail="Statistics unavailable (requires BAGS_API_KEY)"
        )

    return stats
