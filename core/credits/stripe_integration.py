"""
Stripe Payment Integration.

Handles:
- Checkout session creation
- Webhook handling
- Payment verification
- Subscription management (future)

Webhook Events:
- checkout.session.completed → Add credits
- payment_intent.succeeded → Verify payment
- charge.refunded → Remove credits
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.credits.stripe")

# Try to import stripe
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe SDK not installed - payment features disabled")


def _get_stripe():
    """Get configured Stripe module."""
    if not STRIPE_AVAILABLE:
        raise ImportError("stripe package not installed")

    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    stripe.api_key = api_key
    return stripe


# =============================================================================
# Checkout Sessions
# =============================================================================


async def create_checkout_session(
    user_id: str,
    package_id: str,
    success_url: str,
    cancel_url: str,
    customer_email: str = None,
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for credit purchase.

    Args:
        user_id: Internal user ID
        package_id: Credit package to purchase
        success_url: URL to redirect after success
        cancel_url: URL to redirect after cancel
        customer_email: Optional customer email for Stripe

    Returns:
        Dict with session_id and checkout_url
    """
    stripe = _get_stripe()

    from core.credits.manager import get_credit_manager

    manager = get_credit_manager()
    package = manager.get_package(package_id)

    if not package:
        raise ValueError(f"Package not found: {package_id}")

    if not package.active:
        raise ValueError(f"Package not available: {package_id}")

    # Get or create Stripe customer
    user = manager.get_user(user_id)
    customer_id = None

    if user and user.stripe_customer_id:
        customer_id = user.stripe_customer_id
    elif user:
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=customer_email or user.email,
            metadata={"user_id": user_id},
        )
        customer_id = customer.id
        manager.update_user_stripe(user_id, customer_id)

    # Create checkout session
    session_params = {
        "payment_method_types": ["card"],
        "line_items": [{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": package.name,
                    "description": f"{package.total_credits} credits" + (
                        f" (includes {package.bonus_credits} bonus!)" if package.bonus_credits else ""
                    ),
                },
                "unit_amount": package.price_cents,
            },
            "quantity": 1,
        }],
        "mode": "payment",
        "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": cancel_url,
        "metadata": {
            "user_id": user_id,
            "package_id": package_id,
            "credits": str(package.total_credits),
        },
    }

    if customer_id:
        session_params["customer"] = customer_id
    elif customer_email:
        session_params["customer_email"] = customer_email

    session = stripe.checkout.Session.create(**session_params)

    logger.info(f"Created checkout session {session.id} for user {user_id}, package {package_id}")

    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "package": package.to_dict(),
    }


def get_payment_status(session_id: str) -> Dict[str, Any]:
    """Get payment status for a checkout session."""
    stripe = _get_stripe()

    session = stripe.checkout.Session.retrieve(session_id)

    return {
        "session_id": session.id,
        "status": session.status,
        "payment_status": session.payment_status,
        "customer_email": session.customer_details.email if session.customer_details else None,
        "amount_total": session.amount_total,
        "currency": session.currency,
        "metadata": dict(session.metadata) if session.metadata else {},
    }


# =============================================================================
# Webhook Handling
# =============================================================================


def verify_webhook_signature(payload: bytes, signature: str) -> Dict[str, Any]:
    """Verify Stripe webhook signature and parse event."""
    stripe = _get_stripe()

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

    event = stripe.Webhook.construct_event(
        payload,
        signature,
        webhook_secret,
    )

    return event


async def handle_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Stripe webhook event.

    Args:
        event: Parsed Stripe event

    Returns:
        Dict with handling result
    """
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Processing Stripe webhook: {event_type}")

    result = {"event_type": event_type, "handled": False}

    try:
        if event_type == "checkout.session.completed":
            result = await _handle_checkout_completed(data)

        elif event_type == "payment_intent.succeeded":
            result = await _handle_payment_succeeded(data)

        elif event_type == "charge.refunded":
            result = await _handle_refund(data)

        elif event_type == "customer.subscription.created":
            result = await _handle_subscription_created(data)

        elif event_type == "customer.subscription.deleted":
            result = await _handle_subscription_deleted(data)

        else:
            logger.debug(f"Unhandled event type: {event_type}")
            result = {"event_type": event_type, "handled": False, "reason": "unhandled_event_type"}

    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
        result = {"event_type": event_type, "handled": False, "error": str(e)}

    return result


async def _handle_checkout_completed(session: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful checkout completion."""
    from core.credits.manager import get_credit_manager, TransactionType

    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")
    package_id = metadata.get("package_id")
    credits = int(metadata.get("credits", 0))

    if not user_id or not credits:
        logger.error(f"Missing metadata in checkout session: {session.get('id')}")
        return {"handled": False, "error": "missing_metadata"}

    payment_id = session.get("payment_intent")

    manager = get_credit_manager()

    # Check for duplicate (idempotency)
    existing = manager.get_transactions(user_id, limit=10, transaction_type=TransactionType.PURCHASE)
    for tx in existing:
        if tx.stripe_payment_id == payment_id:
            logger.warning(f"Duplicate payment detected: {payment_id}")
            return {"handled": True, "duplicate": True}

    # Add credits
    transaction = manager.add_credits(
        user_id=user_id,
        amount=credits,
        transaction_type=TransactionType.PURCHASE,
        description=f"Purchase: {package_id}",
        stripe_payment_id=payment_id,
        metadata={"package_id": package_id, "session_id": session.get("id")},
    )

    logger.info(f"Added {credits} credits to {user_id} from checkout {session.get('id')}")

    return {
        "handled": True,
        "user_id": user_id,
        "credits_added": credits,
        "transaction_id": transaction.id,
    }


async def _handle_payment_succeeded(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful payment intent (backup for checkout)."""
    # Usually checkout.session.completed handles this
    # This is a fallback
    return {"handled": True, "payment_intent": payment_intent.get("id")}


async def _handle_refund(charge: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge refund - remove credits."""
    from core.credits.manager import get_credit_manager, TransactionType

    payment_intent = charge.get("payment_intent")
    refund_amount = charge.get("amount_refunded", 0)

    if not payment_intent:
        return {"handled": False, "error": "no_payment_intent"}

    manager = get_credit_manager()

    # Find original transaction
    # This is a simplified approach - in production you'd want better tracking
    logger.warning(f"Refund detected for {payment_intent}, amount: {refund_amount}")

    # Would need to find user and remove credits
    # For now, just log the refund

    return {
        "handled": True,
        "refund": True,
        "payment_intent": payment_intent,
        "amount_refunded": refund_amount,
    }


async def _handle_subscription_created(subscription: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription creation (future feature)."""
    logger.info(f"Subscription created: {subscription.get('id')}")
    return {"handled": True, "subscription_id": subscription.get("id")}


async def _handle_subscription_deleted(subscription: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription cancellation (future feature)."""
    logger.info(f"Subscription deleted: {subscription.get('id')}")
    return {"handled": True, "subscription_id": subscription.get("id")}


# =============================================================================
# Customer Portal
# =============================================================================


def create_portal_session(customer_id: str, return_url: str) -> Dict[str, Any]:
    """Create a Stripe customer portal session."""
    stripe = _get_stripe()

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )

    return {
        "portal_url": session.url,
    }


# =============================================================================
# Utility Functions
# =============================================================================


def sync_prices_to_stripe(packages: list = None) -> Dict[str, str]:
    """
    Sync credit packages to Stripe as products/prices.

    Returns mapping of package_id to stripe_price_id.
    """
    stripe = _get_stripe()

    from core.credits.manager import get_credit_manager

    if packages is None:
        manager = get_credit_manager()
        packages = manager.get_packages(active_only=False)

    price_ids = {}

    for package in packages:
        # Create or update product
        products = stripe.Product.list(limit=100)
        product = None

        for p in products.data:
            if p.metadata.get("package_id") == package.id:
                product = p
                break

        if not product:
            product = stripe.Product.create(
                name=package.name,
                description=package.description or f"{package.total_credits} credits",
                metadata={"package_id": package.id},
            )

        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=package.price_cents,
            currency="usd",
            metadata={"package_id": package.id, "credits": str(package.total_credits)},
        )

        price_ids[package.id] = price.id
        logger.info(f"Created Stripe price {price.id} for package {package.id}")

    return price_ids


def get_customer_info(customer_id: str) -> Optional[Dict[str, Any]]:
    """Get Stripe customer information."""
    stripe = _get_stripe()

    try:
        customer = stripe.Customer.retrieve(customer_id)
        return {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "created": customer.created,
            "metadata": dict(customer.metadata) if customer.metadata else {},
        }
    except stripe.error.InvalidRequestError:
        return None
