"""
Stripe Payment Handler.

Complete Stripe integration for credit purchases:
- Checkout session creation
- Webhook handling with signature verification
- Idempotent payment processing
- Credit balance management
"""

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.payments.stripe")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class StripeConfig:
    """Stripe configuration."""
    secret_key: str = ""
    publishable_key: str = ""
    webhook_secret: str = ""

    @classmethod
    def from_env(cls) -> "StripeConfig":
        return cls(
            secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
            publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
            webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        )


# Credit packages with Stripe price IDs
CREDIT_PACKAGES = {
    "starter_25": {
        "name": "Starter Pack",
        "description": "100 API credits for getting started",
        "credits": 100,
        "bonus_credits": 0,
        "points": 25,
        "price_cents": 2500,  # $25
        "stripe_price_id": os.getenv("STRIPE_PRICE_STARTER", "price_starter"),
        "tier_upgrade": "starter",
    },
    "pro_100": {
        "name": "Pro Pack",
        "description": "500 API credits + 50 bonus credits",
        "credits": 500,
        "bonus_credits": 50,
        "points": 150,
        "price_cents": 10000,  # $100
        "stripe_price_id": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
        "tier_upgrade": "pro",
    },
    "whale_500": {
        "name": "Whale Pack",
        "description": "3000 API credits + 500 bonus + priority support",
        "credits": 3000,
        "bonus_credits": 500,
        "points": 1000,
        "price_cents": 50000,  # $500
        "stripe_price_id": os.getenv("STRIPE_PRICE_WHALE", "price_whale"),
        "tier_upgrade": "whale",
    },
}


# =============================================================================
# Stripe Client Wrapper
# =============================================================================


class StripeClient:
    """
    Stripe API client wrapper.

    Handles all Stripe API interactions with proper error handling.
    """

    def __init__(self, config: StripeConfig = None):
        self.config = config or StripeConfig.from_env()
        self._stripe = None

    def _get_stripe(self):
        """Lazy-load Stripe SDK."""
        if self._stripe is None:
            try:
                import stripe
                stripe.api_key = self.config.secret_key
                self._stripe = stripe
            except ImportError:
                logger.error("Stripe SDK not installed. Run: pip install stripe")
                raise RuntimeError("Stripe SDK not available")
        return self._stripe

    async def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        package_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session.

        Args:
            user_id: Internal user identifier
            user_email: User's email for receipt
            package_id: Credit package to purchase
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            metadata: Additional metadata to attach

        Returns:
            Dict with checkout_url and session_id
        """
        if package_id not in CREDIT_PACKAGES:
            raise ValueError(f"Invalid package: {package_id}")

        package = CREDIT_PACKAGES[package_id]
        stripe = self._get_stripe()

        session_metadata = {
            "user_id": user_id,
            "package_id": package_id,
            "credits": str(package["credits"]),
            "bonus_credits": str(package["bonus_credits"]),
            "points": str(package["points"]),
        }
        if metadata:
            session_metadata.update(metadata)

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer_email=user_email,
                line_items=[
                    {
                        "price": package["stripe_price_id"],
                        "quantity": 1,
                    }
                ],
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata=session_metadata,
                payment_intent_data={
                    "metadata": session_metadata,
                },
            )

            logger.info(f"Created checkout session {session.id} for user {user_id}")

            return {
                "checkout_url": session.url,
                "session_id": session.id,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating session: {e}")
            raise

    async def retrieve_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve a checkout session."""
        stripe = self._get_stripe()

        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                "id": session.id,
                "status": session.status,
                "payment_status": session.payment_status,
                "customer_email": session.customer_email,
                "metadata": dict(session.metadata),
                "amount_total": session.amount_total,
                "currency": session.currency,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving session: {e}")
            raise

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Verify and parse webhook payload.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            Parsed event object

        Raises:
            ValueError: Invalid signature
        """
        stripe = self._get_stripe()

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.webhook_secret,
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid webhook signature")
        except Exception as e:
            logger.error(f"Webhook parsing error: {e}")
            raise


# =============================================================================
# Payment Processor
# =============================================================================


class PaymentProcessor:
    """
    Processes payments and manages credit balances.

    Features:
    - Idempotent processing (no duplicate credits)
    - Transaction logging
    - Email notifications
    """

    def __init__(self, stripe_client: StripeClient = None):
        self.stripe = stripe_client or StripeClient()
        self._processed_events: set = set()  # In-memory idempotency (use Redis in prod)
        self._user_balances: Dict[str, Dict] = {}
        self._transactions: List[Dict] = []

    def _is_processed(self, event_id: str) -> bool:
        """Check if event was already processed."""
        return event_id in self._processed_events

    def _mark_processed(self, event_id: str):
        """Mark event as processed."""
        self._processed_events.add(event_id)

    async def handle_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            Processing result
        """
        # Verify signature
        event = self.stripe.verify_webhook_signature(payload, signature)

        event_id = event["id"]
        event_type = event["type"]

        logger.info(f"Received webhook: {event_type} ({event_id})")

        # Idempotency check
        if self._is_processed(event_id):
            logger.info(f"Event {event_id} already processed, skipping")
            return {"status": "already_processed", "event_id": event_id}

        # Route to handler
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "payment_intent.succeeded": self._handle_payment_succeeded,
            "payment_intent.payment_failed": self._handle_payment_failed,
            "charge.refunded": self._handle_refund,
        }

        handler = handlers.get(event_type)
        if handler:
            result = await handler(event["data"]["object"])
            self._mark_processed(event_id)
            return {"status": "processed", "event_id": event_id, **result}
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return {"status": "ignored", "event_id": event_id}

    async def _handle_checkout_completed(self, session: Dict) -> Dict:
        """Handle successful checkout."""
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        package_id = metadata.get("package_id")

        if not user_id or not package_id:
            logger.error(f"Missing metadata in session: {session.get('id')}")
            return {"error": "missing_metadata"}

        package = CREDIT_PACKAGES.get(package_id)
        if not package:
            logger.error(f"Invalid package in session: {package_id}")
            return {"error": "invalid_package"}

        # Credit the user
        credits_added = await self._add_credits(
            user_id=user_id,
            credits=package["credits"],
            bonus_credits=package["bonus_credits"],
            points=package["points"],
            source="stripe_checkout",
            reference=session.get("id"),
            package_id=package_id,
            tier_upgrade=package.get("tier_upgrade"),
        )

        # Send confirmation email
        await self._send_confirmation_email(
            email=session.get("customer_email"),
            package_name=package["name"],
            credits=credits_added,
            transaction_id=session.get("id"),
        )

        logger.info(
            f"Checkout completed: user={user_id}, package={package_id}, "
            f"credits={credits_added}"
        )

        return {
            "user_id": user_id,
            "credits_added": credits_added,
            "package": package_id,
        }

    async def _handle_payment_succeeded(self, payment_intent: Dict) -> Dict:
        """Handle successful payment intent (backup for checkout)."""
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")

        if not user_id:
            logger.info("Payment intent without user_id metadata, skipping")
            return {"status": "skipped_no_user"}

        # Check if already processed via checkout.session.completed
        reference = payment_intent.get("id")
        for tx in self._transactions:
            if tx.get("reference") == reference:
                logger.info(f"Payment {reference} already credited via checkout")
                return {"status": "already_credited"}

        logger.info(f"Payment succeeded for user {user_id}")
        return {"user_id": user_id, "payment_intent_id": reference}

    async def _handle_payment_failed(self, payment_intent: Dict) -> Dict:
        """Handle failed payment."""
        metadata = payment_intent.get("metadata", {})
        user_id = metadata.get("user_id")
        error = payment_intent.get("last_payment_error", {})

        logger.warning(
            f"Payment failed: user={user_id}, "
            f"error={error.get('message', 'unknown')}"
        )

        # Could send notification to user here

        return {
            "user_id": user_id,
            "error": error.get("message"),
        }

    async def _handle_refund(self, charge: Dict) -> Dict:
        """Handle refund - deduct credits."""
        metadata = charge.get("metadata", {}) or {}
        user_id = metadata.get("user_id")

        if not user_id:
            # Try to find from payment intent
            payment_intent = charge.get("payment_intent")
            logger.warning(f"Refund without user_id: charge={charge.get('id')}")
            return {"status": "no_user_id"}

        refund_amount = charge.get("amount_refunded", 0)

        # Calculate credits to deduct (proportional to refund)
        original_amount = charge.get("amount", 1)
        refund_ratio = refund_amount / original_amount

        # Find original transaction
        for tx in self._transactions:
            if tx.get("user_id") == user_id and tx.get("type") == "purchase":
                credits_to_deduct = int(tx.get("credits", 0) * refund_ratio)
                await self._deduct_credits(
                    user_id=user_id,
                    credits=credits_to_deduct,
                    reason="refund",
                    reference=charge.get("id"),
                )

                logger.info(
                    f"Refund processed: user={user_id}, "
                    f"credits_deducted={credits_to_deduct}"
                )

                return {
                    "user_id": user_id,
                    "credits_deducted": credits_to_deduct,
                }

        return {"status": "no_matching_transaction"}

    async def _add_credits(
        self,
        user_id: str,
        credits: int,
        bonus_credits: int,
        points: int,
        source: str,
        reference: str,
        package_id: str,
        tier_upgrade: str = None,
    ) -> int:
        """Add credits to user account."""
        total_credits = credits + bonus_credits

        # Get or create user balance
        if user_id not in self._user_balances:
            self._user_balances[user_id] = {
                "credits": 0,
                "points": 0,
                "tier": "free",
                "lifetime_credits": 0,
            }

        balance = self._user_balances[user_id]
        balance["credits"] += total_credits
        balance["points"] += points
        balance["lifetime_credits"] += total_credits

        if tier_upgrade:
            balance["tier"] = tier_upgrade

        # Record transaction
        import uuid
        self._transactions.append({
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "type": "purchase",
            "credits": total_credits,
            "points": points,
            "source": source,
            "reference": reference,
            "package_id": package_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return total_credits

    async def _deduct_credits(
        self,
        user_id: str,
        credits: int,
        reason: str,
        reference: str,
    ):
        """Deduct credits from user account."""
        if user_id in self._user_balances:
            self._user_balances[user_id]["credits"] = max(
                0, self._user_balances[user_id]["credits"] - credits
            )

            import uuid
            self._transactions.append({
                "id": f"tx_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "type": reason,
                "credits": -credits,
                "reference": reference,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    async def _send_confirmation_email(
        self,
        email: str,
        package_name: str,
        credits: int,
        transaction_id: str,
    ):
        """Send purchase confirmation email."""
        # In production, integrate with SendGrid/Mailgun/etc
        logger.info(
            f"[EMAIL] To: {email} | "
            f"Subject: Your {package_name} purchase is complete! | "
            f"Credits: {credits} | Ref: {transaction_id}"
        )

        # Placeholder for actual email sending
        # await send_email(
        #     to=email,
        #     template="purchase_confirmation",
        #     data={"package": package_name, "credits": credits, ...}
        # )


# =============================================================================
# FastAPI Routes
# =============================================================================


def create_stripe_router():
    """Create FastAPI router for Stripe endpoints."""
    try:
        from fastapi import APIRouter, HTTPException, Request
        from pydantic import BaseModel, Field, EmailStr
    except ImportError:
        return None

    router = APIRouter(prefix="/api/payments", tags=["Payments"])
    processor = PaymentProcessor()

    class CheckoutRequest(BaseModel):
        user_id: str = Field(..., description="User identifier")
        email: EmailStr = Field(..., description="User email for receipt")
        package_id: str = Field(..., description="Credit package ID")
        success_url: str = Field(..., description="Success redirect URL")
        cancel_url: str = Field(..., description="Cancel redirect URL")

    class CheckoutResponse(BaseModel):
        checkout_url: str
        session_id: str

    @router.post("/checkout", response_model=CheckoutResponse)
    async def create_checkout(request: CheckoutRequest):
        """Create Stripe checkout session."""
        try:
            result = await processor.stripe.create_checkout_session(
                user_id=request.user_id,
                user_email=request.email,
                package_id=request.package_id,
                success_url=request.success_url,
                cancel_url=request.cancel_url,
            )
            return CheckoutResponse(**result)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.error(f"Checkout error: {e}")
            raise HTTPException(500, "Failed to create checkout session")

    @router.post("/webhook")
    async def stripe_webhook(request: Request):
        """Handle Stripe webhook."""
        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")

        try:
            result = await processor.handle_webhook(payload, signature)
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            raise HTTPException(500, str(e))

    @router.get("/packages")
    async def get_packages():
        """Get available credit packages."""
        return {
            "packages": [
                {
                    "id": pkg_id,
                    "name": pkg["name"],
                    "description": pkg["description"],
                    "credits": pkg["credits"],
                    "bonus_credits": pkg["bonus_credits"],
                    "total_credits": pkg["credits"] + pkg["bonus_credits"],
                    "points": pkg["points"],
                    "price_cents": pkg["price_cents"],
                    "price_usd": pkg["price_cents"] / 100,
                }
                for pkg_id, pkg in CREDIT_PACKAGES.items()
            ]
        }

    @router.get("/session/{session_id}")
    async def get_session(session_id: str):
        """Get checkout session status."""
        try:
            result = await processor.stripe.retrieve_session(session_id)
            return result
        except Exception as e:
            raise HTTPException(404, f"Session not found: {e}")

    return router


# =============================================================================
# Singleton
# =============================================================================

_processor: Optional[PaymentProcessor] = None


def get_payment_processor() -> PaymentProcessor:
    """Get singleton payment processor."""
    global _processor
    if _processor is None:
        _processor = PaymentProcessor()
    return _processor
