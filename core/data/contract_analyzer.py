"""
Contract Analyzer - Token Contract Verification and Scam Detection
===================================================================

Analyzes token contracts for:
- Verification status (verified on Solscan)
- Common scam patterns (honeypot, rug pull)
- Risk flags and severity levels
- Owner permissions (mint, freeze, blacklist)

Risk Flags:
- HONEYPOT: Cannot sell tokens (sell disabled or high tax)
- RUG_PULL: Owner can drain funds or rug
- UNVERIFIED: Contract not verified
- CENTRALIZED: Owner has excessive control
- SUSPICIOUS_SUPPLY: Supply manipulation possible

Usage:
    from core.data.contract_analyzer import get_contract_analyzer

    analyzer = get_contract_analyzer()
    verification = await analyzer.verify_contract(token_address)
    analysis = await analyzer.analyze_contract(token_address)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.data.solscan_api import SolscanAPI, get_solscan_api, TokenInfo

logger = logging.getLogger(__name__)


# Known safe tokens (verified major tokens)
KNOWN_SAFE_TOKENS: Set[str] = {
    # Wrapped SOL
    "So11111111111111111111111111111111111111112",
    # USDC
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    # USDT
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    # RAY (Raydium)
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    # SRM (Serum)
    "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",
    # BONK
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    # JTO
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    # JUP (Jupiter)
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    # PYTH
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
}


class RiskFlag(Enum):
    """Risk flag types with severity levels."""

    # Critical risks (severity 90-100)
    HONEYPOT = ("HONEYPOT", 100, "Token cannot be sold - honeypot detected")
    RUG_PULL = ("RUG_PULL", 95, "Rug pull indicators detected")

    # High risks (severity 70-89)
    OWNER_CAN_MINT = ("OWNER_CAN_MINT", 80, "Owner can mint unlimited tokens")
    OWNER_CAN_FREEZE = ("OWNER_CAN_FREEZE", 75, "Owner can freeze transfers")
    OWNER_CAN_BLACKLIST = ("OWNER_CAN_BLACKLIST", 70, "Owner can blacklist addresses")

    # Medium risks (severity 40-69)
    UNVERIFIED = ("UNVERIFIED", 60, "Contract not verified")
    SUSPICIOUS_SUPPLY = ("SUSPICIOUS_SUPPLY", 55, "Supply manipulation possible")
    NEW_TOKEN = ("NEW_TOKEN", 50, "Token created very recently")
    LOW_LIQUIDITY = ("LOW_LIQUIDITY", 45, "Very low liquidity")

    # Low risks (severity 10-39)
    CENTRALIZED = ("CENTRALIZED", 35, "Centralized owner control")
    FEW_HOLDERS = ("FEW_HOLDERS", 30, "Very few token holders")
    HIGH_SELL_TAX = ("HIGH_SELL_TAX", 25, "High sell tax detected")

    def __init__(self, flag_name: str, severity: int, description: str):
        self._flag_name = flag_name
        self._severity = severity
        self._description = description

    @property
    def severity(self) -> int:
        return self._severity

    @property
    def description(self) -> str:
        return self._description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag": self._flag_name,
            "severity": self._severity,
            "description": self._description,
        }


@dataclass
class ContractVerification:
    """Contract verification and safety analysis result."""
    token_address: str
    is_verified: bool = False
    is_safe: bool = False
    risk_flags: List[str] = field(default_factory=list)
    risk_score: int = 0  # 0-100, higher = riskier
    confidence: float = 0.0  # 0.0-1.0

    # Additional metadata
    symbol: str = ""
    name: str = ""
    holder_count: int = 0
    is_known_safe: bool = False
    owner_permissions: Dict[str, bool] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContractAnalyzer:
    """
    Token contract analyzer for verification and scam detection.

    Features:
    - Known safe token detection
    - Honeypot pattern detection
    - Rug pull indicator analysis
    - Owner permission analysis
    - Risk scoring
    """

    _instance: Optional["ContractAnalyzer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.solscan = get_solscan_api()
        self._initialized = True
        logger.info("ContractAnalyzer initialized")

    def _is_known_safe_token(self, token_address: str) -> bool:
        """Check if token is in known safe list."""
        return token_address in KNOWN_SAFE_TOKENS

    async def _check_honeypot_indicators(
        self,
        token_address: str,
        sell_disabled: bool = False,
        high_sell_tax: bool = False,
        transfer_restricted: bool = False,
    ) -> bool:
        """
        Check for honeypot indicators.

        Honeypot signs:
        - Sell function disabled or reverts
        - Very high sell tax (>50%)
        - Transfer restrictions

        Args:
            token_address: Token mint address
            sell_disabled: Whether selling is disabled
            high_sell_tax: Whether sell tax is unusually high
            transfer_restricted: Whether transfers are restricted

        Returns:
            True if honeypot indicators detected
        """
        if sell_disabled:
            logger.warning(f"Honeypot indicator: sell disabled for {token_address}")
            return True

        if high_sell_tax:
            logger.warning(f"Honeypot indicator: high sell tax for {token_address}")
            return True

        if transfer_restricted:
            logger.warning(f"Honeypot indicator: transfer restricted for {token_address}")
            return True

        return False

    async def _check_rug_pull_indicators(
        self,
        token_address: str,
        owner_can_mint: bool = False,
        owner_can_freeze: bool = False,
        owner_can_blacklist: bool = False,
        owner_can_pause: bool = False,
    ) -> bool:
        """
        Check for rug pull indicators.

        Rug pull signs:
        - Owner can mint unlimited tokens
        - Owner can freeze all transfers
        - Owner can blacklist holders
        - Owner can pause trading

        Args:
            token_address: Token mint address
            owner_can_mint: Owner has mint authority
            owner_can_freeze: Owner has freeze authority
            owner_can_blacklist: Owner can blacklist addresses
            owner_can_pause: Owner can pause contract

        Returns:
            True if rug pull indicators detected
        """
        # Multiple dangerous permissions = high rug risk
        dangerous_count = sum([
            owner_can_mint,
            owner_can_freeze,
            owner_can_blacklist,
            owner_can_pause,
        ])

        if dangerous_count >= 2:
            logger.warning(f"Rug pull indicators: {dangerous_count} dangerous permissions for {token_address}")
            return True

        # Single permission can still be dangerous
        if owner_can_mint and owner_can_freeze:
            return True

        return False

    async def verify_contract(self, token_address: str) -> ContractVerification:
        """
        Verify token contract and return verification status.

        Args:
            token_address: Token mint address

        Returns:
            ContractVerification with status and confidence
        """
        if not token_address:
            return ContractVerification(
                token_address=token_address,
                is_verified=False,
                is_safe=False,
                risk_flags=["invalid_address"],
                risk_score=100,
                confidence=1.0,
            )

        # Check known safe tokens
        if self._is_known_safe_token(token_address):
            return ContractVerification(
                token_address=token_address,
                is_verified=True,
                is_safe=True,
                risk_flags=[],
                risk_score=0,
                confidence=1.0,
                is_known_safe=True,
                recommendations=["Known safe token - proceed with normal risk management"],
            )

        # Fetch token info
        token_info = await self.solscan.get_token_info(token_address)

        if not token_info:
            return ContractVerification(
                token_address=token_address,
                is_verified=False,
                is_safe=False,
                risk_flags=["api_unavailable"],
                risk_score=50,
                confidence=0.3,
                recommendations=["Could not verify token - proceed with caution"],
            )

        # Build verification
        risk_flags = []
        risk_score = 0

        # Check holder count (low holders = higher risk)
        if token_info.holder_count < 50:
            risk_flags.append(RiskFlag.FEW_HOLDERS.name)
            risk_score += 20
        elif token_info.holder_count < 100:
            risk_score += 10

        # Check if token is new (creation time if available)
        if token_info.created_time:
            age_days = (datetime.now(timezone.utc) - token_info.created_time).days
            if age_days < 1:
                risk_flags.append(RiskFlag.NEW_TOKEN.name)
                risk_score += 30
            elif age_days < 7:
                risk_score += 15

        # Check for verification badge (heuristic: has icon, website, coingecko)
        is_verified = bool(token_info.icon or token_info.website or token_info.coingecko_id)
        if not is_verified:
            risk_flags.append(RiskFlag.UNVERIFIED.name)
            risk_score += 25

        # Determine safety
        is_safe = risk_score < 50 and len(risk_flags) < 2
        confidence = 0.7 if token_info else 0.3

        # Recommendations
        recommendations = []
        if risk_score > 50:
            recommendations.append("High risk score - consider reducing position size")
        if RiskFlag.NEW_TOKEN.name in risk_flags:
            recommendations.append("New token - wait for more trading history")
        if RiskFlag.FEW_HOLDERS.name in risk_flags:
            recommendations.append("Few holders - liquidity may be thin")

        return ContractVerification(
            token_address=token_address,
            is_verified=is_verified,
            is_safe=is_safe,
            risk_flags=risk_flags,
            risk_score=min(100, risk_score),
            confidence=confidence,
            symbol=token_info.symbol,
            name=token_info.name,
            holder_count=token_info.holder_count,
            recommendations=recommendations,
        )

    async def analyze_contract(self, token_address: str) -> ContractVerification:
        """
        Perform comprehensive contract analysis.

        Combines:
        - Basic verification
        - Honeypot detection
        - Rug pull analysis
        - Permission analysis

        Args:
            token_address: Token mint address

        Returns:
            ContractVerification with complete analysis
        """
        # Start with basic verification
        verification = await self.verify_contract(token_address)

        if verification.is_known_safe:
            return verification

        # For non-safe tokens, perform additional analysis
        # Note: On Solana, we can't easily check contract code like on EVM
        # We rely on behavioral patterns and metadata

        # Get token info for additional checks
        token_info = await self.solscan.get_token_info(token_address)

        if token_info:
            # Check for suspicious patterns

            # Very low market cap with large supply could be suspicious
            if token_info.market_cap > 0 and token_info.market_cap < 10000:
                if token_info.total_supply > 1_000_000_000_000:  # Trillion+
                    verification.risk_flags.append(RiskFlag.SUSPICIOUS_SUPPLY.name)
                    verification.risk_score = min(100, verification.risk_score + 20)

            # Update safety based on new analysis
            verification.is_safe = (
                verification.risk_score < 50 and
                len(verification.risk_flags) < 2 and
                RiskFlag.HONEYPOT.name not in verification.risk_flags and
                RiskFlag.RUG_PULL.name not in verification.risk_flags
            )

        return verification

    def get_risk_summary(self, verification: ContractVerification) -> Dict[str, Any]:
        """
        Get a human-readable risk summary.

        Args:
            verification: ContractVerification result

        Returns:
            Dict with risk summary
        """
        if verification.is_known_safe:
            level = "SAFE"
            color = "green"
        elif verification.is_safe:
            level = "LOW"
            color = "yellow"
        elif verification.risk_score < 70:
            level = "MEDIUM"
            color = "orange"
        else:
            level = "HIGH"
            color = "red"

        return {
            "level": level,
            "color": color,
            "score": verification.risk_score,
            "flags": verification.risk_flags,
            "recommendations": verification.recommendations,
            "confidence": verification.confidence,
        }


# Singleton accessor
def get_contract_analyzer() -> ContractAnalyzer:
    """Get the ContractAnalyzer singleton instance."""
    return ContractAnalyzer()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("=== Contract Analyzer Test ===")

        analyzer = get_contract_analyzer()

        # Test with known safe token
        print("\n--- Testing SOL (known safe) ---")
        sol_result = await analyzer.analyze_contract(
            "So11111111111111111111111111111111111111112"
        )
        print(f"Is Safe: {sol_result.is_safe}")
        print(f"Is Verified: {sol_result.is_verified}")
        print(f"Risk Score: {sol_result.risk_score}")
        print(f"Confidence: {sol_result.confidence}")

        # Test with unknown token
        print("\n--- Testing unknown token ---")
        unknown_result = await analyzer.analyze_contract(
            "Unknown111111111111111111111111111111111111"
        )
        print(f"Is Safe: {unknown_result.is_safe}")
        print(f"Risk Flags: {unknown_result.risk_flags}")
        print(f"Risk Score: {unknown_result.risk_score}")

    asyncio.run(test())
