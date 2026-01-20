"""
Transaction Verifier

Comprehensive token and transaction verification system:
- Token authenticity verification (rugpull detection)
- Liquidity validation (detect fake liquidity)
- Contract code analysis
- Ownership checks

Security-critical module for protecting against:
- Rugpulls
- Honeypots
- Fake tokens
- Manipulated liquidity
"""

import logging
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TokenFlag(str, Enum):
    """Token warning flags."""
    MINT_AUTHORITY = "mint_authority_active"
    FREEZE_AUTHORITY = "freeze_authority_active"
    LOW_LIQUIDITY = "low_liquidity"
    CONCENTRATED_HOLDINGS = "concentrated_holdings"
    NEW_TOKEN = "new_token"
    FEW_HOLDERS = "few_holders"
    SUSPICIOUS_NAME = "suspicious_name"
    UNVERIFIED_CONTRACT = "unverified_contract"
    PROXY_CONTRACT = "proxy_contract"
    BLACKLIST_FUNCTION = "has_blacklist_function"
    PAUSE_FUNCTION = "has_pause_function"
    HIGH_TAX = "high_tax"


# Suspicious token name patterns
SUSPICIOUS_NAME_PATTERNS = [
    r'safe.*moon', r'moon.*safe',
    r'elon.*\w+', r'\w+.*elon',
    r'shib.*\w+', r'\w+.*inu',
    r'doge.*\w+',
    r'free.*money', r'easy.*money',
    r'100x', r'1000x',
    r'guaranteed',
]

# Known dangerous contract functions
DANGEROUS_FUNCTIONS = [
    'blacklist', 'blacklistAddress', 'addToBlacklist',
    'pause', 'unpause', 'setPaused',
    'setFee', 'setTax', 'updateFee', 'changeFee',
    'setMaxTx', 'setMaxWallet',
    'excludeFromFee', 'includeInFee',
    'renounceOwnership',  # Good, but check if called
]


@dataclass
class TokenMetadata:
    """Token metadata for verification."""
    name: str
    symbol: str
    decimals: int
    supply: int
    mint_authority: Optional[str] = None
    freeze_authority: Optional[str] = None
    creator: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class LiquidityData:
    """Liquidity pool data."""
    total_liquidity_usd: float
    liquidity_locked: bool
    lock_duration_days: int = 0
    pool_age_days: float = 0
    liquidity_providers: int = 0
    wash_trading_score: float = 0


@dataclass
class ContractAnalysis:
    """Contract analysis results."""
    verified: bool
    source_available: bool
    has_proxy: bool
    functions: List[str] = field(default_factory=list)
    suspicious_functions: List[str] = field(default_factory=list)
    bytecode_hash: Optional[str] = None


@dataclass
class OwnershipData:
    """Ownership information."""
    owner_address: Optional[str]
    owner_is_contract: bool
    is_renounced: bool
    ownership_history: List[Dict[str, Any]] = field(default_factory=list)


class TransactionVerifier:
    """
    Comprehensive transaction and token verification.

    Analyzes tokens for potential scams, rugpulls, and honeypots
    before allowing trades.
    """

    def __init__(
        self,
        min_liquidity_usd: float = 10000,
        max_creator_holding_pct: float = 0.30,
        min_holder_count: int = 50,
        min_pool_age_hours: int = 24,
        cache_ttl_seconds: int = 300
    ):
        """
        Initialize the transaction verifier.

        Args:
            min_liquidity_usd: Minimum liquidity requirement
            max_creator_holding_pct: Max % creator can hold
            min_holder_count: Minimum number of holders
            min_pool_age_hours: Minimum pool age
            cache_ttl_seconds: Cache TTL for verifications
        """
        self.min_liquidity_usd = min_liquidity_usd
        self.max_creator_holding_pct = max_creator_holding_pct
        self.min_holder_count = min_holder_count
        self.min_pool_age_hours = min_pool_age_hours
        self.cache_ttl_seconds = cache_ttl_seconds

        self._cache: Dict[str, Tuple[datetime, Dict]] = {}

    def _is_valid_solana_address(self, address: str) -> bool:
        """Check if address is valid Solana format."""
        if not address or len(address) < 32 or len(address) > 44:
            return False
        # Basic base58 character check
        base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        return all(c in base58_chars for c in address)

    def _fetch_token_metadata(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch token metadata from chain/API.
        Override this method for actual implementation.
        """
        # Default implementation returns None
        # Real implementation would call Solana RPC or Birdeye API
        return None

    def _fetch_token_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive token data.
        Override this method for actual implementation.
        """
        return None

    def _fetch_liquidity_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch liquidity pool data.
        Override this method for actual implementation.
        """
        return None

    def _fetch_contract_source(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch contract source/bytecode.
        Override this method for actual implementation.
        """
        return None

    def _fetch_ownership_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch ownership data.
        Override this method for actual implementation.
        """
        return None

    async def _async_fetch_token_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Async version of fetch_token_data."""
        return self._fetch_token_data(token_address)

    def verify_token_authenticity(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Verify token authenticity and check for rugpull indicators.

        Args:
            token_address: Token mint address

        Returns:
            Dict with verification results
        """
        # Validate address format
        if not self._is_valid_solana_address(token_address):
            return {
                "verified": False,
                "error": "Invalid address format",
                "risk_score": 1.0,
                "warnings": ["Invalid token address"]
            }

        # Check cache
        if token_address in self._cache:
            cache_time, cached_result = self._cache[token_address]
            if (datetime.now(timezone.utc) - cache_time).seconds < self.cache_ttl_seconds:
                return cached_result

        try:
            metadata = self._fetch_token_metadata(token_address)

            if metadata is None:
                # Default to suspicious if we can't fetch data
                return {
                    "verified": False,
                    "error": "Could not fetch token metadata",
                    "risk_score": 0.7,
                    "warnings": ["Token metadata unavailable"]
                }

            warnings = []
            risk_score = 0.0

            # Check for suspicious name patterns
            name = metadata.get("name", "").lower()
            symbol = metadata.get("symbol", "").lower()
            for pattern in SUSPICIOUS_NAME_PATTERNS:
                if re.search(pattern, name, re.IGNORECASE) or re.search(pattern, symbol, re.IGNORECASE):
                    warnings.append(f"Suspicious name pattern: {pattern}")
                    risk_score += 0.15

            # Check mint authority
            if metadata.get("mint_authority"):
                warnings.append(TokenFlag.MINT_AUTHORITY.value)
                risk_score += 0.2

            # Check freeze authority
            if metadata.get("freeze_authority"):
                warnings.append(TokenFlag.FREEZE_AUTHORITY.value)
                risk_score += 0.25

            # Check supply (absurdly high supply is suspicious)
            supply = metadata.get("supply", 0)
            if supply > 1e18:  # More than 1 quintillion
                warnings.append("Extremely high token supply")
                risk_score += 0.1

            # Cap risk score at 1.0
            risk_score = min(risk_score, 1.0)

            result = {
                "verified": risk_score < 0.5,
                "risk_score": round(risk_score, 3),
                "warnings": warnings,
                "token_name": metadata.get("name"),
                "token_symbol": metadata.get("symbol"),
                "has_mint_authority": bool(metadata.get("mint_authority")),
                "has_freeze_authority": bool(metadata.get("freeze_authority"))
            }

            # Cache result
            self._cache[token_address] = (datetime.now(timezone.utc), result)

            return result

        except TimeoutError as e:
            return {
                "verified": False,
                "error": f"Timeout: {str(e)}",
                "risk_score": 0.8,
                "warnings": ["Verification timed out"]
            }
        except Exception as e:
            return {
                "verified": False,
                "error": str(e),
                "risk_score": 0.7,
                "warnings": [f"Verification error: {str(e)}"]
            }

    def detect_rugpull_indicators(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Detect specific rugpull indicators.

        Args:
            token_address: Token mint address

        Returns:
            Dict with rugpull analysis
        """
        try:
            token_data = self._fetch_token_data(token_address)

            if token_data is None:
                return {
                    "is_potential_rugpull": True,
                    "confidence": 0.5,
                    "indicators": ["data_unavailable"],
                    "error": "Could not fetch token data"
                }

            indicators = []
            confidence = 0.0

            # Check creator holdings
            creator_pct = token_data.get("creator_holdings_pct", 0)
            if creator_pct > self.max_creator_holding_pct:
                indicators.append("creator_concentration")
                confidence += 0.3

            # Check if liquidity is locked
            if not token_data.get("liquidity_locked", False):
                indicators.append("unlocked_liquidity")
                confidence += 0.2

            # Check contract verification
            if not token_data.get("contract_verified", False):
                indicators.append("unverified_contract")
                confidence += 0.15

            # Check token age
            age_hours = token_data.get("age_hours", 0)
            if age_hours < self.min_pool_age_hours:
                indicators.append("very_new_token")
                confidence += 0.15

            # Check holder count
            holder_count = token_data.get("holder_count", 0)
            if holder_count < self.min_holder_count:
                indicators.append("few_holders")
                confidence += 0.1

            # Check concentration
            top_10_pct = token_data.get("top_10_holdings_pct", 0)
            if top_10_pct > 0.80:
                indicators.append("concentrated_holdings")
                confidence += 0.2

            confidence = min(confidence, 1.0)

            return {
                "is_potential_rugpull": confidence > 0.5,
                "confidence": round(confidence, 3),
                "indicators": indicators,
                "creator_holdings_pct": creator_pct,
                "holder_count": holder_count,
                "liquidity_locked": token_data.get("liquidity_locked", False)
            }

        except Exception as e:
            return {
                "is_potential_rugpull": True,
                "confidence": 0.6,
                "indicators": ["error"],
                "error": str(e)
            }

    def verify_liquidity(
        self,
        token_address: str,
        min_liquidity_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Verify liquidity is legitimate.

        Args:
            token_address: Token mint address
            min_liquidity_usd: Override minimum liquidity requirement

        Returns:
            Dict with liquidity analysis
        """
        min_liq = min_liquidity_usd or self.min_liquidity_usd

        try:
            liq_data = self._fetch_liquidity_data(token_address)

            if liq_data is None:
                return {
                    "liquidity_valid": False,
                    "liquidity_score": 0.3,
                    "warnings": ["Could not fetch liquidity data"]
                }

            warnings = []
            score = 1.0

            total_liq = liq_data.get("total_liquidity_usd", 0)

            # Check minimum liquidity
            if total_liq < min_liq:
                warnings.append("low_liquidity")
                score -= 0.3

            # Check if locked
            if not liq_data.get("liquidity_locked", False):
                warnings.append("unlocked_liquidity")
                score -= 0.25

            # Check lock duration
            lock_days = liq_data.get("lock_duration_days", 0)
            if lock_days < 30:
                warnings.append("short_lock_duration")
                score -= 0.15

            # Check pool age
            pool_age = liq_data.get("pool_age_days", 0)
            if pool_age < 1:
                warnings.append("very_new_pool")
                score -= 0.2

            # Check LP count
            lp_count = liq_data.get("liquidity_providers", 0)
            if lp_count <= 1:
                warnings.append("single_liquidity_provider")
                score -= 0.2

            # Check wash trading
            wash_score = liq_data.get("wash_trading_score", 0)
            if wash_score > 0.5:
                warnings.append("fake_liquidity")
                score -= 0.3

            score = max(0, min(score, 1.0))

            return {
                "liquidity_valid": score >= 0.5,
                "liquidity_score": round(score, 3),
                "total_liquidity_usd": total_liq,
                "liquidity_locked": liq_data.get("liquidity_locked", False),
                "lock_duration_days": lock_days,
                "warnings": warnings
            }

        except Exception as e:
            return {
                "liquidity_valid": False,
                "liquidity_score": 0.2,
                "warnings": ["error"],
                "error": str(e)
            }

    def analyze_contract(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Analyze contract for dangerous patterns.

        Args:
            token_address: Token mint address

        Returns:
            Dict with contract analysis
        """
        try:
            contract_data = self._fetch_contract_source(token_address)

            if contract_data is None:
                return {
                    "is_safe": False,
                    "risk_level": RiskLevel.MEDIUM.value,
                    "dangerous_patterns": [],
                    "warnings": ["Could not fetch contract data"]
                }

            dangerous_patterns = []
            risk_level = RiskLevel.LOW

            # Check if verified
            if not contract_data.get("verified", False):
                dangerous_patterns.append("unverified")
                risk_level = RiskLevel.MEDIUM

            # Check if source available
            if not contract_data.get("source_available", False):
                dangerous_patterns.append("no_source")
                risk_level = RiskLevel.MEDIUM

            # Check for proxy
            if contract_data.get("has_proxy", False):
                dangerous_patterns.append("proxy_contract")
                risk_level = RiskLevel.MEDIUM

            # Check functions
            functions = contract_data.get("functions", [])
            suspicious = contract_data.get("suspicious_functions", [])

            for func in suspicious:
                if func.lower() in [f.lower() for f in DANGEROUS_FUNCTIONS]:
                    dangerous_patterns.append(f"dangerous_function:{func}")

            if "blacklist" in [f.lower() for f in functions]:
                dangerous_patterns.append("blacklist_capability")
                risk_level = RiskLevel.HIGH

            if "pause" in [f.lower() for f in functions]:
                dangerous_patterns.append("pause_capability")
                if risk_level != RiskLevel.HIGH:
                    risk_level = RiskLevel.MEDIUM

            return {
                "is_safe": len(dangerous_patterns) == 0,
                "risk_level": risk_level.value,
                "dangerous_patterns": dangerous_patterns,
                "verified": contract_data.get("verified", False),
                "has_proxy": contract_data.get("has_proxy", False),
                "function_count": len(functions)
            }

        except Exception as e:
            return {
                "is_safe": False,
                "risk_level": RiskLevel.HIGH.value,
                "dangerous_patterns": ["error"],
                "error": str(e)
            }

    def check_ownership(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Check ownership status.

        Args:
            token_address: Token mint address

        Returns:
            Dict with ownership analysis
        """
        try:
            ownership_data = self._fetch_ownership_data(token_address)

            if ownership_data is None:
                return {
                    "owner_address": None,
                    "is_renounced": False,
                    "ownership_risk": RiskLevel.MEDIUM.value,
                    "warnings": ["Could not fetch ownership data"]
                }

            risk = RiskLevel.LOW
            warnings = []

            owner = ownership_data.get("owner_address")
            is_renounced = ownership_data.get("renounced", False)
            owner_is_contract = ownership_data.get("owner_is_contract", False)

            if not is_renounced:
                if owner_is_contract:
                    warnings.append("owner_is_contract")
                    risk = RiskLevel.MEDIUM
                else:
                    warnings.append("owner_is_eoa")  # Externally owned account

            return {
                "owner_address": owner,
                "is_renounced": is_renounced,
                "owner_is_contract": owner_is_contract,
                "ownership_risk": risk.value,
                "warnings": warnings
            }

        except Exception as e:
            return {
                "owner_address": None,
                "is_renounced": False,
                "ownership_risk": RiskLevel.HIGH.value,
                "error": str(e)
            }

    def comprehensive_verify(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Run comprehensive verification on a token.

        Args:
            token_address: Token mint address

        Returns:
            Dict with complete verification results
        """
        results = {
            "token_address": token_address,
            "verification_time": datetime.now(timezone.utc).isoformat(),
            "token_authenticity": self.verify_token_authenticity(token_address),
            "rugpull_analysis": self.detect_rugpull_indicators(token_address),
            "liquidity_analysis": self.verify_liquidity(token_address),
            "contract_analysis": self.analyze_contract(token_address),
            "ownership_analysis": self.check_ownership(token_address)
        }

        # Calculate overall score
        scores = [
            1 - results["token_authenticity"].get("risk_score", 0.5),
            1 - results["rugpull_analysis"].get("confidence", 0.5),
            results["liquidity_analysis"].get("liquidity_score", 0.5),
            1.0 if results["contract_analysis"].get("is_safe", False) else 0.3,
        ]
        overall_score = sum(scores) / len(scores)

        # Determine recommendation
        if overall_score >= 0.7:
            recommendation = "SAFE_TO_TRADE"
        elif overall_score >= 0.5:
            recommendation = "PROCEED_WITH_CAUTION"
        elif overall_score >= 0.3:
            recommendation = "HIGH_RISK"
        else:
            recommendation = "DO_NOT_TRADE"

        results["overall_score"] = round(overall_score, 3)
        results["recommendation"] = recommendation

        return results

    async def async_verify_token(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """
        Async token verification.

        Args:
            token_address: Token mint address

        Returns:
            Verification results
        """
        data = await self._async_fetch_token_data(token_address)
        if data:
            return {"verified": True, "data": data}
        return {"verified": False, "error": "Could not fetch data"}


# Singleton
_verifier: Optional[TransactionVerifier] = None


def get_transaction_verifier() -> TransactionVerifier:
    """Get or create the transaction verifier singleton."""
    global _verifier
    if _verifier is None:
        _verifier = TransactionVerifier()
    return _verifier
