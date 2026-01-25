"""
Trading API Handlers.

FastAPI endpoints for trading operations:
- Position management (list, get, close, update)
- Trade execution (buy, sell, status, cancel)
- Admin authentication and authorization
- Request validation and error handling
"""

import logging
import uuid
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field, validator

from api.auth.key_auth import validate_api_key, APIKeyAuth, hash_key
from api.auth.jwt_auth import jwt_auth, JWTAuth, TokenPayload
from api.schemas.trading import (
    OrderSide,
    OrderType,
    OrderStatus,
    CreateOrderRequest,
    OrderResponse,
    CancelOrderRequest,
    PositionResponse,
    TradeResponse,
)

logger = logging.getLogger("jarvis.api.trading")

router = APIRouter(prefix="/api/trading", tags=["Trading"])

# Rate limiting state (per API key)
_rate_limit_state: Dict[str, Dict[str, Any]] = {}

# Solana address regex (base58, 32-44 chars)
SOLANA_ADDRESS_REGEX = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')


# =============================================================================
# Request/Response Models
# =============================================================================


class BuyOrderRequest(BaseModel):
    """Request to submit a buy order."""
    token_address: str = Field(..., description="Solana token mint address")
    amount_sol: float = Field(..., gt=0, le=100, description="Amount in SOL to spend")
    slippage_bps: int = Field(default=50, ge=1, le=1000, description="Slippage tolerance in basis points")
    max_price: Optional[float] = Field(None, gt=0, description="Maximum acceptable price")

    @validator('token_address')
    def validate_solana_address(cls, v):
        """Validate Solana address format."""
        if not SOLANA_ADDRESS_REGEX.match(v):
            raise ValueError("Invalid Solana address format")
        return v


class SellOrderRequest(BaseModel):
    """Request to submit a sell order."""
    token_address: str = Field(..., description="Solana token mint address")
    amount_tokens: Optional[float] = Field(None, gt=0, description="Amount of tokens to sell (None = all)")
    percentage: Optional[float] = Field(None, ge=1, le=100, description="Percentage of holdings to sell")
    slippage_bps: int = Field(default=50, ge=1, le=1000, description="Slippage tolerance in basis points")
    min_price: Optional[float] = Field(None, gt=0, description="Minimum acceptable price")

    @validator('token_address')
    def validate_solana_address(cls, v):
        """Validate Solana address format."""
        if not SOLANA_ADDRESS_REGEX.match(v):
            raise ValueError("Invalid Solana address format")
        return v

    @validator('percentage')
    def validate_sell_amount(cls, v, values):
        """Ensure either amount_tokens or percentage is provided."""
        if v is None and values.get('amount_tokens') is None:
            raise ValueError("Either amount_tokens or percentage must be provided")
        return v


class TradeStatusResponse(BaseModel):
    """Response for trade status query."""
    trade_id: str
    status: str
    token_address: str
    side: str
    requested_amount: float
    executed_amount: Optional[float] = None
    price: Optional[float] = None
    signature: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PositionUpdateRequest(BaseModel):
    """Request to update a position."""
    stop_loss: Optional[float] = Field(None, gt=0, description="Stop loss price")
    take_profit: Optional[float] = Field(None, gt=0, description="Take profit price")
    trailing_stop_percent: Optional[float] = Field(None, ge=1, le=50, description="Trailing stop percentage")


class PositionCloseRequest(BaseModel):
    """Request to close a position."""
    percentage: float = Field(default=100, ge=1, le=100, description="Percentage to close")
    slippage_bps: int = Field(default=50, ge=1, le=1000, description="Slippage tolerance")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_more: bool


# =============================================================================
# Trading Service (Mock implementation)
# =============================================================================


class TradingService:
    """
    Service for executing trades and managing positions.

    In production, this connects to the actual trading engine.
    """

    def __init__(self):
        self._positions: Dict[str, Dict] = {}
        self._trades: Dict[str, Dict] = {}
        self._orders: Dict[str, Dict] = {}

    def get_positions(
        self,
        user_id: str,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResponse:
        """Get list of positions for a user."""
        user_positions = [
            p for p in self._positions.values()
            if p.get("user_id") == user_id
        ]

        if status_filter:
            user_positions = [
                p for p in user_positions
                if p.get("status") == status_filter
            ]

        total = len(user_positions)
        start = (page - 1) * page_size
        end = start + page_size
        items = user_positions[start:end]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total
        )

    def get_position(self, position_id: str, user_id: str) -> Optional[Dict]:
        """Get a single position by ID."""
        position = self._positions.get(position_id)
        if position and position.get("user_id") == user_id:
            return position
        return None

    def close_position(
        self,
        position_id: str,
        user_id: str,
        percentage: float = 100,
        slippage_bps: int = 50
    ) -> Dict:
        """Close a position (fully or partially)."""
        position = self.get_position(position_id, user_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        if position.get("status") == "closed":
            raise HTTPException(status_code=400, detail="Position already closed")

        # Create close trade
        trade_id = str(uuid.uuid4())
        close_amount = position.get("size", 0) * (percentage / 100)

        self._trades[trade_id] = {
            "trade_id": trade_id,
            "position_id": position_id,
            "status": "pending",
            "side": "sell" if position.get("side") == "buy" else "buy",
            "amount": close_amount,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update position
        if percentage >= 100:
            position["status"] = "closing"
        else:
            position["size"] -= close_amount

        return {
            "trade_id": trade_id,
            "message": f"Closing {percentage}% of position",
            "estimated_amount": close_amount,
        }

    def update_position(
        self,
        position_id: str,
        user_id: str,
        update: PositionUpdateRequest
    ) -> Dict:
        """Update position parameters."""
        position = self.get_position(position_id, user_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        if update.stop_loss is not None:
            position["stop_loss"] = update.stop_loss
        if update.take_profit is not None:
            position["take_profit"] = update.take_profit
        if update.trailing_stop_percent is not None:
            position["trailing_stop_percent"] = update.trailing_stop_percent

        position["updated_at"] = datetime.now(timezone.utc).isoformat()

        return position

    def submit_buy_order(self, user_id: str, request: BuyOrderRequest) -> Dict:
        """Submit a buy order."""
        trade_id = str(uuid.uuid4())

        trade = {
            "trade_id": trade_id,
            "user_id": user_id,
            "status": "pending",
            "side": "buy",
            "token_address": request.token_address,
            "requested_amount": request.amount_sol,
            "slippage_bps": request.slippage_bps,
            "max_price": request.max_price,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._trades[trade_id] = trade

        return {
            "trade_id": trade_id,
            "status": "pending",
            "message": f"Buy order submitted for {request.amount_sol} SOL",
        }

    def submit_sell_order(self, user_id: str, request: SellOrderRequest) -> Dict:
        """Submit a sell order."""
        trade_id = str(uuid.uuid4())

        trade = {
            "trade_id": trade_id,
            "user_id": user_id,
            "status": "pending",
            "side": "sell",
            "token_address": request.token_address,
            "requested_amount": request.amount_tokens,
            "percentage": request.percentage,
            "slippage_bps": request.slippage_bps,
            "min_price": request.min_price,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._trades[trade_id] = trade

        return {
            "trade_id": trade_id,
            "status": "pending",
            "message": "Sell order submitted",
        }

    def get_trade(self, trade_id: str, user_id: str) -> Optional[Dict]:
        """Get trade status."""
        trade = self._trades.get(trade_id)
        if trade and trade.get("user_id") == user_id:
            return trade
        return None

    def cancel_trade(self, trade_id: str, user_id: str) -> Dict:
        """Cancel a pending trade."""
        trade = self.get_trade(trade_id, user_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        if trade.get("status") not in ("pending", "submitted"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel trade with status: {trade.get('status')}"
            )

        trade["status"] = "cancelled"
        trade["updated_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "trade_id": trade_id,
            "status": "cancelled",
            "message": "Trade cancelled successfully",
        }


# Singleton service instance
_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    """Get or create trading service."""
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service


# =============================================================================
# Rate Limiting
# =============================================================================


def check_rate_limit(api_key: str, limit_per_minute: int = 60) -> bool:
    """Check if request is within rate limit."""
    import time

    now = time.time()
    key_hash = hash_key(api_key)

    if key_hash not in _rate_limit_state:
        _rate_limit_state[key_hash] = {
            "requests": [],
            "blocked_until": 0,
        }

    state = _rate_limit_state[key_hash]

    # Check if blocked
    if state["blocked_until"] > now:
        return False

    # Clean old requests (older than 1 minute)
    state["requests"] = [t for t in state["requests"] if t > now - 60]

    # Check limit
    if len(state["requests"]) >= limit_per_minute:
        state["blocked_until"] = now + 60  # Block for 1 minute
        return False

    # Add current request
    state["requests"].append(now)
    return True


async def rate_limit_dependency(api_key: str = Depends(validate_api_key)):
    """Dependency that enforces rate limiting."""
    if not check_rate_limit(api_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": "60"},
        )
    return api_key


# =============================================================================
# Admin Authentication
# =============================================================================


ADMIN_SCOPES = ["admin", "trading:admin"]


async def require_admin(token: TokenPayload = Depends(jwt_auth)) -> TokenPayload:
    """Dependency that requires admin scope."""
    if not any(scope in token.scopes for scope in ADMIN_SCOPES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return token


# =============================================================================
# Position Management Endpoints
# =============================================================================


@router.get("/positions", response_model=PaginatedResponse)
async def list_positions(
    status: Optional[str] = Query(None, description="Filter by status (open, closed, closing)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    List open positions.

    Returns paginated list of positions for the authenticated user.
    """
    # In production, extract user_id from API key metadata
    user_id = hash_key(api_key)[:16]

    try:
        return service.get_positions(
            user_id=user_id,
            status_filter=status,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Get single position details.

    Returns detailed information about a specific position.
    """
    user_id = hash_key(api_key)[:16]

    position = service.get_position(position_id, user_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return position


@router.post("/positions/{position_id}/close")
async def close_position(
    position_id: str,
    request: PositionCloseRequest,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Close a position.

    Initiates closing of a position (fully or partially).
    """
    user_id = hash_key(api_key)[:16]

    try:
        return service.close_position(
            position_id=position_id,
            user_id=user_id,
            percentage=request.percentage,
            slippage_bps=request.slippage_bps,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/positions/{position_id}")
async def update_position(
    position_id: str,
    request: PositionUpdateRequest,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Update position parameters.

    Updates stop loss, take profit, or trailing stop settings.
    """
    user_id = hash_key(api_key)[:16]

    try:
        return service.update_position(
            position_id=position_id,
            user_id=user_id,
            update=request,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Trade Execution Endpoints
# =============================================================================


@router.post("/trades/buy")
async def submit_buy_order(
    request: BuyOrderRequest,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Submit a buy order.

    Submits an order to buy tokens with SOL.
    """
    user_id = hash_key(api_key)[:16]

    try:
        return service.submit_buy_order(user_id, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting buy order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trades/sell")
async def submit_sell_order(
    request: SellOrderRequest,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Submit a sell order.

    Submits an order to sell tokens for SOL.
    """
    user_id = hash_key(api_key)[:16]

    try:
        return service.submit_sell_order(user_id, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting sell order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{trade_id}")
async def get_trade_status(
    trade_id: str,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Get trade status.

    Returns current status and details of a trade.
    """
    user_id = hash_key(api_key)[:16]

    trade = service.get_trade(trade_id, user_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    return trade


@router.delete("/trades/{trade_id}")
async def cancel_trade(
    trade_id: str,
    api_key: str = Depends(rate_limit_dependency),
    service: TradingService = Depends(get_trading_service),
):
    """
    Cancel a pending trade.

    Cancels a trade that has not yet been executed.
    """
    user_id = hash_key(api_key)[:16]

    try:
        return service.cancel_trade(trade_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Admin Endpoints
# =============================================================================


@router.get("/admin/positions")
async def admin_list_all_positions(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: TokenPayload = Depends(require_admin),
    service: TradingService = Depends(get_trading_service),
):
    """
    Admin: List all positions.

    Returns positions for all users (admin only).
    """
    try:
        # Get all positions without user filter
        all_positions = list(service._positions.values())

        if user_id:
            all_positions = [p for p in all_positions if p.get("user_id") == user_id]
        if status:
            all_positions = [p for p in all_positions if p.get("status") == status]

        total = len(all_positions)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_positions[start:end]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total,
        )
    except Exception as e:
        logger.error(f"Error in admin list positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/positions/{position_id}/force-close")
async def admin_force_close_position(
    position_id: str,
    admin: TokenPayload = Depends(require_admin),
    service: TradingService = Depends(get_trading_service),
):
    """
    Admin: Force close a position.

    Force closes any position regardless of ownership (admin only).
    """
    position = service._positions.get(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    position["status"] = "force_closed"
    position["closed_by_admin"] = admin.sub
    position["updated_at"] = datetime.now(timezone.utc).isoformat()

    logger.warning(f"Admin {admin.sub} force-closed position {position_id}")

    return {
        "position_id": position_id,
        "status": "force_closed",
        "message": "Position force closed by admin",
    }


@router.get("/admin/trades")
async def admin_list_all_trades(
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: TokenPayload = Depends(require_admin),
    service: TradingService = Depends(get_trading_service),
):
    """
    Admin: List all trades.

    Returns trades for all users (admin only).
    """
    all_trades = list(service._trades.values())

    if user_id:
        all_trades = [t for t in all_trades if t.get("user_id") == user_id]
    if status:
        all_trades = [t for t in all_trades if t.get("status") == status]

    total = len(all_trades)
    start = (page - 1) * page_size
    end = start + page_size
    items = all_trades[start:end]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )
