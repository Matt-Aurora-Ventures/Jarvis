"""
Wallet Verification System
Prompt #96: Wallet-based verification (NO KYC)

Verifies users based on on-chain activity without identity verification.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json

logger = logging.getLogger("jarvis.verification.wallet")


# =============================================================================
# MODELS
# =============================================================================

class VerificationLevel(Enum):
    """Wallet verification levels"""
    UNVERIFIED = "unverified"
    BASIC = "basic"          # Age + balance check
    STANDARD = "standard"    # Activity check
    VERIFIED = "verified"    # Full reputation check
    TRUSTED = "trusted"      # Long history + high reputation


class VerificationStatus(Enum):
    """Status of verification attempt"""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class VerificationCheck:
    """A single verification check"""
    name: str
    passed: bool
    details: str
    value: Any = None
    required: bool = True


@dataclass
class VerificationResult:
    """Result of wallet verification"""
    wallet: str
    level: VerificationLevel
    status: VerificationStatus
    checks: List[VerificationCheck]
    score: float  # 0-100
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalletProfile:
    """Profile information derived from wallet"""
    wallet: str
    age_days: int
    balance_sol: float
    transaction_count: int
    unique_programs: int
    nft_count: int
    defi_activity: bool
    first_activity: Optional[datetime] = None
    last_activity: Optional[datetime] = None


# =============================================================================
# VERIFICATION THRESHOLDS
# =============================================================================

class VerificationThresholds:
    """Thresholds for different verification levels"""

    # Basic level
    BASIC_MIN_AGE_DAYS = 7
    BASIC_MIN_BALANCE_SOL = 0.01

    # Standard level
    STANDARD_MIN_AGE_DAYS = 30
    STANDARD_MIN_BALANCE_SOL = 0.1
    STANDARD_MIN_TRANSACTIONS = 10

    # Verified level
    VERIFIED_MIN_AGE_DAYS = 90
    VERIFIED_MIN_BALANCE_SOL = 1.0
    VERIFIED_MIN_TRANSACTIONS = 50
    VERIFIED_MIN_PROGRAMS = 5

    # Trusted level
    TRUSTED_MIN_AGE_DAYS = 365
    TRUSTED_MIN_BALANCE_SOL = 5.0
    TRUSTED_MIN_TRANSACTIONS = 200
    TRUSTED_MIN_PROGRAMS = 10


# =============================================================================
# WALLET VERIFIER
# =============================================================================

class WalletVerifier:
    """
    Verifies wallets based on on-chain activity.

    NO KYC - Uses only on-chain data:
    - Wallet age
    - Balance history
    - Transaction activity
    - Program interactions
    - NFT holdings
    - DeFi participation
    """

    VERIFICATION_DURATION_DAYS = 90  # How long verification lasts

    def __init__(
        self,
        rpc_url: str = None,
        db_path: str = None,
    ):
        self.rpc_url = rpc_url or os.getenv(
            "SOLANA_RPC_URL",
            "https://api.mainnet-beta.solana.com"
        )
        self.db_path = db_path or os.getenv(
            "VERIFICATION_DB",
            "data/verification.db"
        )

        self._init_database()

    def _init_database(self):
        """Initialize verification database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Verification records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                level TEXT NOT NULL,
                status TEXT NOT NULL,
                score REAL,
                verified_at TEXT NOT NULL,
                expires_at TEXT,
                checks_json TEXT,
                metadata_json TEXT,
                UNIQUE(wallet)
            )
        """)

        # Wallet profiles cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_profiles (
                wallet TEXT PRIMARY KEY,
                age_days INTEGER,
                balance_sol REAL,
                transaction_count INTEGER,
                unique_programs INTEGER,
                nft_count INTEGER,
                defi_activity INTEGER,
                first_activity TEXT,
                last_activity TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    async def verify_wallet(
        self,
        wallet: str,
        target_level: VerificationLevel = VerificationLevel.STANDARD,
    ) -> VerificationResult:
        """
        Verify a wallet for a target level.

        Args:
            wallet: Solana wallet address
            target_level: Desired verification level

        Returns:
            VerificationResult with checks and level achieved
        """
        # Check for existing valid verification
        existing = await self.get_verification(wallet)
        if existing and existing.status == VerificationStatus.PASSED:
            if existing.expires_at and existing.expires_at > datetime.now(timezone.utc):
                if self._level_value(existing.level) >= self._level_value(target_level):
                    return existing

        # Get wallet profile
        profile = await self.get_wallet_profile(wallet)

        # Run verification checks
        checks = await self._run_checks(profile, target_level)

        # Calculate achieved level and score
        achieved_level, score = self._calculate_level(checks, profile)

        # Create result
        now = datetime.now(timezone.utc)
        result = VerificationResult(
            wallet=wallet,
            level=achieved_level,
            status=VerificationStatus.PASSED if achieved_level != VerificationLevel.UNVERIFIED else VerificationStatus.FAILED,
            checks=checks,
            score=score,
            verified_at=now,
            expires_at=now + timedelta(days=self.VERIFICATION_DURATION_DAYS),
            metadata={
                "target_level": target_level.value,
                "profile": {
                    "age_days": profile.age_days,
                    "balance_sol": profile.balance_sol,
                    "transaction_count": profile.transaction_count,
                },
            },
        )

        # Store result
        await self._save_verification(result)

        logger.info(
            f"Wallet verification: {wallet[:8]}... -> {achieved_level.value} "
            f"(score: {score:.1f})"
        )

        return result

    async def _run_checks(
        self,
        profile: WalletProfile,
        target_level: VerificationLevel,
    ) -> List[VerificationCheck]:
        """Run all verification checks"""
        checks = []

        # Age check
        checks.append(VerificationCheck(
            name="wallet_age",
            passed=profile.age_days >= VerificationThresholds.BASIC_MIN_AGE_DAYS,
            details=f"Wallet age: {profile.age_days} days",
            value=profile.age_days,
            required=True,
        ))

        # Balance check
        checks.append(VerificationCheck(
            name="balance",
            passed=profile.balance_sol >= VerificationThresholds.BASIC_MIN_BALANCE_SOL,
            details=f"Balance: {profile.balance_sol:.4f} SOL",
            value=profile.balance_sol,
            required=True,
        ))

        # Transaction activity
        checks.append(VerificationCheck(
            name="transaction_count",
            passed=profile.transaction_count >= VerificationThresholds.STANDARD_MIN_TRANSACTIONS,
            details=f"Transactions: {profile.transaction_count}",
            value=profile.transaction_count,
            required=target_level in [VerificationLevel.STANDARD, VerificationLevel.VERIFIED, VerificationLevel.TRUSTED],
        ))

        # Program diversity
        checks.append(VerificationCheck(
            name="program_diversity",
            passed=profile.unique_programs >= VerificationThresholds.VERIFIED_MIN_PROGRAMS,
            details=f"Unique programs: {profile.unique_programs}",
            value=profile.unique_programs,
            required=target_level in [VerificationLevel.VERIFIED, VerificationLevel.TRUSTED],
        ))

        # DeFi activity
        checks.append(VerificationCheck(
            name="defi_activity",
            passed=profile.defi_activity,
            details=f"DeFi active: {profile.defi_activity}",
            value=profile.defi_activity,
            required=False,
        ))

        # NFT holdings
        checks.append(VerificationCheck(
            name="nft_holdings",
            passed=profile.nft_count > 0,
            details=f"NFTs: {profile.nft_count}",
            value=profile.nft_count,
            required=False,
        ))

        # Recent activity
        if profile.last_activity:
            days_since_active = (datetime.now(timezone.utc) - profile.last_activity).days
            checks.append(VerificationCheck(
                name="recent_activity",
                passed=days_since_active < 30,
                details=f"Last active: {days_since_active} days ago",
                value=days_since_active,
                required=False,
            ))

        return checks

    def _calculate_level(
        self,
        checks: List[VerificationCheck],
        profile: WalletProfile,
    ) -> tuple[VerificationLevel, float]:
        """Calculate achieved verification level and score"""
        # Check required checks passed
        required_passed = all(c.passed for c in checks if c.required)
        all_passed = sum(1 for c in checks if c.passed)
        total_checks = len(checks)

        # Calculate base score
        score = (all_passed / total_checks) * 100 if total_checks > 0 else 0

        if not required_passed:
            return VerificationLevel.UNVERIFIED, score

        # Determine level based on thresholds
        if (
            profile.age_days >= VerificationThresholds.TRUSTED_MIN_AGE_DAYS and
            profile.balance_sol >= VerificationThresholds.TRUSTED_MIN_BALANCE_SOL and
            profile.transaction_count >= VerificationThresholds.TRUSTED_MIN_TRANSACTIONS and
            profile.unique_programs >= VerificationThresholds.TRUSTED_MIN_PROGRAMS
        ):
            return VerificationLevel.TRUSTED, min(score + 20, 100)

        if (
            profile.age_days >= VerificationThresholds.VERIFIED_MIN_AGE_DAYS and
            profile.balance_sol >= VerificationThresholds.VERIFIED_MIN_BALANCE_SOL and
            profile.transaction_count >= VerificationThresholds.VERIFIED_MIN_TRANSACTIONS
        ):
            return VerificationLevel.VERIFIED, min(score + 10, 100)

        if (
            profile.age_days >= VerificationThresholds.STANDARD_MIN_AGE_DAYS and
            profile.balance_sol >= VerificationThresholds.STANDARD_MIN_BALANCE_SOL and
            profile.transaction_count >= VerificationThresholds.STANDARD_MIN_TRANSACTIONS
        ):
            return VerificationLevel.STANDARD, score

        if (
            profile.age_days >= VerificationThresholds.BASIC_MIN_AGE_DAYS and
            profile.balance_sol >= VerificationThresholds.BASIC_MIN_BALANCE_SOL
        ):
            return VerificationLevel.BASIC, score

        return VerificationLevel.UNVERIFIED, score

    def _level_value(self, level: VerificationLevel) -> int:
        """Get numeric value for level comparison"""
        levels = {
            VerificationLevel.UNVERIFIED: 0,
            VerificationLevel.BASIC: 1,
            VerificationLevel.STANDARD: 2,
            VerificationLevel.VERIFIED: 3,
            VerificationLevel.TRUSTED: 4,
        }
        return levels.get(level, 0)

    # =========================================================================
    # WALLET PROFILE
    # =========================================================================

    async def get_wallet_profile(
        self,
        wallet: str,
        refresh: bool = False,
    ) -> WalletProfile:
        """
        Get wallet profile with on-chain data.

        Args:
            wallet: Wallet address
            refresh: Force refresh from chain

        Returns:
            WalletProfile with activity data
        """
        # Check cache
        if not refresh:
            cached = await self._get_cached_profile(wallet)
            if cached:
                return cached

        # Fetch from chain (simulated for now)
        profile = await self._fetch_wallet_data(wallet)

        # Cache profile
        await self._cache_profile(profile)

        return profile

    async def _fetch_wallet_data(self, wallet: str) -> WalletProfile:
        """
        Fetch wallet data from Solana.

        Note: This is a simplified implementation.
        In production, use actual RPC calls to get:
        - Account info for balance
        - Transaction history for activity
        - Token accounts for NFTs
        - Known DeFi program interactions
        """
        # Simulated data - replace with actual RPC calls
        # In production, use solana-py or similar

        try:
            # These would be actual RPC calls
            # balance = await self._get_balance(wallet)
            # transactions = await self._get_transactions(wallet)
            # first_tx = await self._get_first_transaction(wallet)

            # Simulated response for development
            import hashlib
            wallet_hash = int(hashlib.md5(wallet.encode()).hexdigest(), 16)

            # Derive pseudo-random but deterministic values from wallet
            age_days = (wallet_hash % 500) + 1
            balance = (wallet_hash % 10000) / 1000
            tx_count = (wallet_hash % 1000)
            programs = (wallet_hash % 20) + 1
            nft_count = (wallet_hash % 50)
            defi = (wallet_hash % 2) == 0

            first_activity = datetime.now(timezone.utc) - timedelta(days=age_days)
            last_activity = datetime.now(timezone.utc) - timedelta(days=(wallet_hash % 7))

            return WalletProfile(
                wallet=wallet,
                age_days=age_days,
                balance_sol=balance,
                transaction_count=tx_count,
                unique_programs=programs,
                nft_count=nft_count,
                defi_activity=defi,
                first_activity=first_activity,
                last_activity=last_activity,
            )

        except Exception as e:
            logger.error(f"Failed to fetch wallet data: {e}")
            return WalletProfile(
                wallet=wallet,
                age_days=0,
                balance_sol=0,
                transaction_count=0,
                unique_programs=0,
                nft_count=0,
                defi_activity=False,
            )

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def get_verification(self, wallet: str) -> Optional[VerificationResult]:
        """Get existing verification for a wallet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM wallet_verifications WHERE wallet = ?",
            (wallet,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        checks_data = json.loads(row[7]) if row[7] else []
        checks = [
            VerificationCheck(
                name=c["name"],
                passed=c["passed"],
                details=c["details"],
                value=c.get("value"),
                required=c.get("required", True),
            )
            for c in checks_data
        ]

        return VerificationResult(
            wallet=row[1],
            level=VerificationLevel(row[2]),
            status=VerificationStatus(row[3]),
            score=row[4],
            verified_at=datetime.fromisoformat(row[5]),
            expires_at=datetime.fromisoformat(row[6]) if row[6] else None,
            checks=checks,
            metadata=json.loads(row[8]) if row[8] else {},
        )

    async def _save_verification(self, result: VerificationResult):
        """Save verification result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        checks_json = json.dumps([
            {
                "name": c.name,
                "passed": c.passed,
                "details": c.details,
                "value": c.value,
                "required": c.required,
            }
            for c in result.checks
        ])

        cursor.execute("""
            INSERT OR REPLACE INTO wallet_verifications
            (wallet, level, status, score, verified_at, expires_at, checks_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.wallet,
            result.level.value,
            result.status.value,
            result.score,
            result.verified_at.isoformat(),
            result.expires_at.isoformat() if result.expires_at else None,
            checks_json,
            json.dumps(result.metadata),
        ))

        conn.commit()
        conn.close()

    async def _get_cached_profile(self, wallet: str) -> Optional[WalletProfile]:
        """Get cached wallet profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM wallet_profiles WHERE wallet = ?",
            (wallet,)
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Check if cache is fresh (< 24 hours)
        updated_at = datetime.fromisoformat(row[9]) if row[9] else None
        if updated_at and (datetime.now(timezone.utc) - updated_at).days >= 1:
            return None

        return WalletProfile(
            wallet=row[0],
            age_days=row[1],
            balance_sol=row[2],
            transaction_count=row[3],
            unique_programs=row[4],
            nft_count=row[5],
            defi_activity=bool(row[6]),
            first_activity=datetime.fromisoformat(row[7]) if row[7] else None,
            last_activity=datetime.fromisoformat(row[8]) if row[8] else None,
        )

    async def _cache_profile(self, profile: WalletProfile):
        """Cache wallet profile"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO wallet_profiles
            (wallet, age_days, balance_sol, transaction_count, unique_programs,
             nft_count, defi_activity, first_activity, last_activity, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.wallet,
            profile.age_days,
            profile.balance_sol,
            profile.transaction_count,
            profile.unique_programs,
            profile.nft_count,
            1 if profile.defi_activity else 0,
            profile.first_activity.isoformat() if profile.first_activity else None,
            profile.last_activity.isoformat() if profile.last_activity else None,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()


# =============================================================================
# SINGLETON
# =============================================================================

_verifier: Optional[WalletVerifier] = None


def get_wallet_verifier() -> WalletVerifier:
    """Get or create the wallet verifier singleton"""
    global _verifier
    if _verifier is None:
        _verifier = WalletVerifier()
    return _verifier
