"""
Revenue Model Module.

Implements the 0.5% fee system for Jarvis trading platform:
- Fee calculation on profitable trades
- User wallet management
- Charity distribution (5% of fees)
- Subscription tiers
- Affiliate program
- Invoice generation
- Financial reporting

Fee Distribution:
- User earns: 75% of fees (75% * 0.5% = 0.375%)
- Charity: 5% of fees (5% * 0.5% = 0.025%)
- Jarvis company: 20% of fees (20% * 0.5% = 0.1%)
"""

from core.revenue.fee_calculator import FeeCalculator
from core.revenue.user_wallet import UserWalletManager
from core.revenue.charity_handler import CharityHandler
from core.revenue.subscription_tiers import SubscriptionManager
from core.revenue.affiliate import AffiliateManager
from core.revenue.invoicing import InvoiceGenerator
from core.revenue.financial_report import FinancialReporter

__all__ = [
    "FeeCalculator",
    "UserWalletManager",
    "CharityHandler",
    "SubscriptionManager",
    "AffiliateManager",
    "InvoiceGenerator",
    "FinancialReporter",
]
