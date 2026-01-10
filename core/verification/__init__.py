"""
Wallet Verification System (NO KYC)

Wallet-based verification using on-chain activity and reputation.
"""

from core.verification.wallet_verify import WalletVerifier, VerificationResult
from core.verification.reputation import ReputationScorer, ReputationScore

__all__ = [
    "WalletVerifier",
    "VerificationResult",
    "ReputationScorer",
    "ReputationScore",
]
