"""
API Credit System for Jarvis.

Provides a normie-friendly payment layer:
- Purchase credits with credit card (Stripe)
- Consume credits for API usage
- Points/rewards system
- Cash-out capability

No blockchain knowledge required for users.

Usage:
    from core.credits import (
        get_credit_manager,
        purchase_credits,
        consume_credits,
        get_balance,
    )

    # Purchase credits
    session = await purchase_credits(user_id, package_id="pro_100")

    # Check balance
    balance = await get_balance(user_id)

    # Consume credits
    success = await consume_credits(user_id, amount=5, description="trade_execute")
"""

from core.credits.manager import (
    CreditManager,
    get_credit_manager,
)
from core.credits.models import (
    CreditPackage,
    CreditTransaction,
    CreditBalance,
    TransactionType,
)
from core.credits.stripe_integration import (
    create_checkout_session,
    handle_webhook,
    get_payment_status,
)
from core.credits.middleware import (
    CreditMeteringMiddleware,
    metered,
)

__all__ = [
    # Manager
    "CreditManager",
    "get_credit_manager",
    # Models
    "CreditPackage",
    "CreditTransaction",
    "CreditBalance",
    "TransactionType",
    # Stripe
    "create_checkout_session",
    "handle_webhook",
    "get_payment_status",
    # Middleware
    "CreditMeteringMiddleware",
    "metered",
]
