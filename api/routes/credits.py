"""
Credits API Routes.

FastAPI endpoints for the credit system:
- Balance checking
- Credit purchase (Stripe checkout)
- Usage history
- Points/rewards redemption
- Referral program
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr

from api.pagination import PaginationParams, paginate

logger = logging.getLogger("jarvis.api.credits")

router = APIRouter(prefix="/api/credits", tags=["Credits"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CheckoutRequest(BaseModel):
    """Request to create Stripe checkout session."""
    user_id: str = Field(..., description="User identifier")
    package_id: str = Field(..., description="Credit package to purchase")
    success_url: str = Field(..., description="URL to redirect on success")
    cancel_url: str = Field(..., description="URL to redirect on cancel")


class CheckoutResponse(BaseModel):
    """Checkout session details."""
    checkout_url: str = Field(..., description="Stripe checkout URL")
    session_id: str = Field(..., description="Stripe session ID")


class BalanceResponse(BaseModel):
    """User's credit balance."""
    credits: int = Field(default=0, description="Available credits")
    points: int = Field(default=0, description="Reward points")
    tier: str = Field(default="free", description="User tier")
    lifetime_credits: int = Field(default=0, description="Total credits ever purchased")


class TransactionItem(BaseModel):
    """Single transaction record."""
    id: str
    type: str  # purchase, consumption, bonus, refund
    amount: int
    description: str
    created_at: str
    balance_after: int


class HistoryResponse(BaseModel):
    """Transaction history."""
    transactions: List[TransactionItem] = Field(default_factory=list)
    has_more: bool = Field(default=False)
    stats: Dict[str, int] = Field(default_factory=dict)


class RedeemRequest(BaseModel):
    """Request to redeem points for rewards."""
    user_id: str = Field(..., description="User identifier")
    reward_id: str = Field(..., description="Reward to redeem")


class RedeemResponse(BaseModel):
    """Redemption result."""
    success: bool
    reward: str
    points_spent: int
    remaining_points: int
    message: str


class ReferralResponse(BaseModel):
    """Referral program info."""
    code: str = Field(..., description="User's referral code")
    stats: Dict[str, int] = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    """Webhook processing result."""
    received: bool
    processed: bool


# =============================================================================
# Credit Packages & Rewards
# =============================================================================


CREDIT_PACKAGES = {
    "starter_25": {
        "name": "Starter",
        "credits": 100,
        "bonus": 0,
        "price_cents": 2500,
        "tier": "starter",
    },
    "pro_100": {
        "name": "Pro",
        "credits": 500,
        "bonus": 50,
        "price_cents": 10000,
        "tier": "pro",
    },
    "whale_500": {
        "name": "Whale",
        "credits": 3000,
        "bonus": 500,
        "price_cents": 50000,
        "tier": "whale",
    },
}

REWARDS = {
    "credits_100": {
        "name": "100 Credits",
        "cost": 500,
        "credits": 100,
    },
    "credits_500": {
        "name": "500 Credits",
        "cost": 2000,
        "credits": 500,
    },
    "priority_week": {
        "name": "Priority Access (1 Week)",
        "cost": 1000,
        "perk": "priority_access",
        "duration_days": 7,
    },
    "exclusive_signals": {
        "name": "Exclusive Signals (1 Month)",
        "cost": 3000,
        "perk": "exclusive_signals",
        "duration_days": 30,
    },
}


# =============================================================================
# Credits Service
# =============================================================================


class CreditsService:
    """
    Service for credit operations.

    In production, this would use the CreditManager from core/credits/
    and integrate with Stripe.
    """

    def __init__(self):
        # Mock data stores
        self._users: Dict[str, Dict[str, Any]] = {}
        self._transactions: Dict[str, List[Dict]] = {}
        self._referral_codes: Dict[str, str] = {}
        self._referral_stats: Dict[str, Dict[str, int]] = {}

    def get_or_create_user(self, user_id: str) -> Dict[str, Any]:
        """Get or create user record."""
        if user_id not in self._users:
            self._users[user_id] = {
                "credits": 0,
                "points": 0,
                "tier": "free",
                "lifetime_credits": 0,
                "created_at": datetime.now(timezone.utc),
            }
            # Generate referral code
            import hashlib
            code = hashlib.md5(user_id.encode()).hexdigest()[:8].upper()
            self._referral_codes[user_id] = code
            self._referral_stats[user_id] = {"count": 0, "earned": 0}

        return self._users[user_id]

    def get_balance(self, user_id: str) -> BalanceResponse:
        """Get user's balance."""
        user = self.get_or_create_user(user_id)

        return BalanceResponse(
            credits=user["credits"],
            points=user["points"],
            tier=user["tier"],
            lifetime_credits=user["lifetime_credits"],
        )

    async def create_checkout_session(
        self,
        user_id: str,
        package_id: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResponse:
        """Create Stripe checkout session."""
        if package_id not in CREDIT_PACKAGES:
            raise HTTPException(400, f"Invalid package: {package_id}")

        package = CREDIT_PACKAGES[package_id]

        # In production, this would call Stripe
        # stripe.checkout.Session.create(...)

        # Mock session
        import uuid
        session_id = f"cs_mock_{uuid.uuid4().hex[:16]}"

        return CheckoutResponse(
            checkout_url=f"https://checkout.stripe.com/pay/{session_id}",
            session_id=session_id,
        )

    def add_credits(
        self,
        user_id: str,
        credits: int,
        bonus: int,
        points: int,
        tx_type: str,
        description: str,
    ) -> None:
        """Add credits to user account."""
        user = self.get_or_create_user(user_id)

        total = credits + bonus
        user["credits"] += total
        user["points"] += points
        user["lifetime_credits"] += total

        # Update tier based on lifetime credits
        if user["lifetime_credits"] >= 3500:
            user["tier"] = "whale"
        elif user["lifetime_credits"] >= 550:
            user["tier"] = "pro"
        elif user["lifetime_credits"] >= 100:
            user["tier"] = "starter"

        # Record transaction
        if user_id not in self._transactions:
            self._transactions[user_id] = []

        import uuid
        self._transactions[user_id].append({
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "type": tx_type,
            "amount": total,
            "description": description,
            "created_at": datetime.now(timezone.utc),
            "balance_after": user["credits"],
        })

    def get_transactions(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        tx_type: Optional[str] = None,
    ) -> HistoryResponse:
        """Get user's transaction history."""
        self.get_or_create_user(user_id)
        transactions = self._transactions.get(user_id, [])

        # Filter by type if specified
        if tx_type:
            transactions = [t for t in transactions if t["type"] == tx_type]

        # Paginate
        start = (page - 1) * limit
        end = start + limit
        page_transactions = transactions[start:end]

        # Calculate stats
        stats = {
            "totalPurchased": sum(t["amount"] for t in transactions if t["type"] == "purchase"),
            "totalUsed": sum(abs(t["amount"]) for t in transactions if t["type"] == "consumption"),
            "totalBonus": sum(t["amount"] for t in transactions if t["type"] == "bonus"),
        }

        return HistoryResponse(
            transactions=[
                TransactionItem(
                    id=t["id"],
                    type=t["type"],
                    amount=t["amount"],
                    description=t["description"],
                    created_at=t["created_at"].isoformat(),
                    balance_after=t["balance_after"],
                )
                for t in page_transactions
            ],
            has_more=len(transactions) > end,
            stats=stats,
        )

    def redeem_reward(self, user_id: str, reward_id: str) -> RedeemResponse:
        """Redeem points for a reward."""
        if reward_id not in REWARDS:
            raise HTTPException(400, f"Invalid reward: {reward_id}")

        reward = REWARDS[reward_id]
        user = self.get_or_create_user(user_id)

        if user["points"] < reward["cost"]:
            raise HTTPException(400, "Insufficient points")

        # Deduct points
        user["points"] -= reward["cost"]

        # Apply reward
        if "credits" in reward:
            user["credits"] += reward["credits"]

        return RedeemResponse(
            success=True,
            reward=reward["name"],
            points_spent=reward["cost"],
            remaining_points=user["points"],
            message=f"Successfully redeemed {reward['name']}!",
        )

    def get_referral_info(self, user_id: str) -> ReferralResponse:
        """Get user's referral information."""
        self.get_or_create_user(user_id)

        return ReferralResponse(
            code=self._referral_codes.get(user_id, ""),
            stats=self._referral_stats.get(user_id, {"count": 0, "earned": 0}),
        )

    async def handle_webhook(self, payload: bytes, signature: str) -> bool:
        """Handle Stripe webhook."""
        # In production, this would:
        # 1. Verify webhook signature
        # 2. Parse event
        # 3. Handle checkout.session.completed
        # 4. Add credits to user

        # Mock success
        return True


# Singleton service instance
_credits_service: Optional[CreditsService] = None


def get_credits_service() -> CreditsService:
    """Get or create credits service."""
    global _credits_service
    if _credits_service is None:
        _credits_service = CreditsService()
    return _credits_service


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/balance/{user_id}", response_model=BalanceResponse)
async def get_balance(
    user_id: str,
    service: CreditsService = Depends(get_credits_service),
):
    """Get user's credit balance."""
    try:
        return service.get_balance(user_id)
    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        raise HTTPException(500, str(e))


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    service: CreditsService = Depends(get_credits_service),
):
    """Create Stripe checkout session for credit purchase."""
    try:
        return await service.create_checkout_session(
            request.user_id,
            request.package_id,
            request.success_url,
            request.cancel_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout: {e}")
        raise HTTPException(500, str(e))


@router.get("/history/{user_id}", response_model=HistoryResponse)
async def get_history(
    user_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    type: Optional[str] = Query(None, description="Filter by transaction type"),
    service: CreditsService = Depends(get_credits_service),
):
    """
    Get user's transaction history with pagination.

    Supports optional filtering by transaction type (purchase, consumption, bonus, refund).
    """
    try:
        return service.get_transactions(user_id, page, page_size, type)
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(500, str(e))


@router.post("/redeem", response_model=RedeemResponse)
async def redeem_points(
    request: RedeemRequest,
    service: CreditsService = Depends(get_credits_service),
):
    """Redeem points for rewards."""
    try:
        return service.redeem_reward(request.user_id, request.reward_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redeeming reward: {e}")
        raise HTTPException(500, str(e))


@router.get("/referral/{user_id}", response_model=ReferralResponse)
async def get_referral(
    user_id: str,
    service: CreditsService = Depends(get_credits_service),
):
    """Get user's referral program information."""
    try:
        return service.get_referral_info(user_id)
    except Exception as e:
        logger.error(f"Error fetching referral info: {e}")
        raise HTTPException(500, str(e))


@router.get("/packages")
async def get_packages():
    """Get available credit packages."""
    return {
        "packages": [
            {
                "id": pkg_id,
                "name": pkg["name"],
                "credits": pkg["credits"],
                "bonus": pkg["bonus"],
                "price_cents": pkg["price_cents"],
                "price_usd": pkg["price_cents"] / 100,
                "total_credits": pkg["credits"] + pkg["bonus"],
            }
            for pkg_id, pkg in CREDIT_PACKAGES.items()
        ]
    }


@router.get("/rewards")
async def get_rewards():
    """Get available rewards for redemption."""
    return {
        "rewards": [
            {
                "id": reward_id,
                "name": reward["name"],
                "cost": reward["cost"],
            }
            for reward_id, reward in REWARDS.items()
        ]
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    service: CreditsService = Depends(get_credits_service),
):
    """Handle Stripe webhook events."""
    try:
        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")

        success = await service.handle_webhook(payload, signature)

        return WebhookResponse(received=True, processed=success)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(400, str(e))
