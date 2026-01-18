"""
Affiliate Program - Referral tracking and commissions.

Structure:
- Referrer gets: 10% of referred user's first year fees
- Referree gets: $5 bonus after first winning trade
- Referral codes: JARVIS-XXXXXX format
"""

from __future__ import annotations

import json
import random
import string
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


REFERRER_COMMISSION_RATE = 0.10  # 10% of referree's fees
REFERREE_BONUS = 5.0  # $5 bonus
COMMISSION_DURATION_DAYS = 365  # 1 year


@dataclass
class ReferralCode:
    """A referral code."""
    code: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    uses: int = 0
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Referral:
    """A referral relationship."""
    id: str
    referrer_id: str
    referree_id: str
    code: str
    status: str = 'active'  # active, expired
    created_at: float = field(default_factory=time.time)
    referree_bonus_credited: bool = False
    total_fees_paid: float = 0.0
    total_commission_earned: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeePayment:
    """A fee payment from a referree."""
    referral_id: str
    amount: float
    commission: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AffiliateManager:
    """
    Manages affiliate/referral program.

    Usage:
        manager = AffiliateManager()

        # Generate referral code
        code = manager.generate_code("user_1")

        # Track new referral
        manager.track_referral(code, "user_2")

        # Record fee payment
        manager.record_referree_fee("user_2", 10.0)

        # Calculate commissions
        commissions = manager.calculate_commissions("user_1")
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.codes_file = self.data_dir / "referral_codes.json"
        self.referrals_file = self.data_dir / "referrals.json"
        self.payments_file = self.data_dir / "referral_payments.jsonl"

        # Load data
        self._codes: Dict[str, ReferralCode] = self._load_codes()
        self._referrals: Dict[str, Referral] = self._load_referrals()
        self._referree_to_referral: Dict[str, str] = self._build_referree_index()

    def _load_codes(self) -> Dict[str, ReferralCode]:
        """Load referral codes."""
        if self.codes_file.exists():
            try:
                data = json.loads(self.codes_file.read_text())
                return {
                    k: ReferralCode(**v)
                    for k, v in data.items()
                    if k != '_metadata'
                }
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_codes(self) -> None:
        """Save referral codes."""
        data = {k: v.to_dict() for k, v in self._codes.items()}
        data['_metadata'] = {'updated_at': time.time()}
        self.codes_file.write_text(json.dumps(data, indent=2))

    def _load_referrals(self) -> Dict[str, Referral]:
        """Load referrals."""
        if self.referrals_file.exists():
            try:
                data = json.loads(self.referrals_file.read_text())
                return {
                    k: Referral(**v)
                    for k, v in data.items()
                    if k != '_metadata'
                }
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_referrals(self) -> None:
        """Save referrals."""
        data = {k: v.to_dict() for k, v in self._referrals.items()}
        data['_metadata'] = {'updated_at': time.time()}
        self.referrals_file.write_text(json.dumps(data, indent=2))

    def _build_referree_index(self) -> Dict[str, str]:
        """Build referree to referral ID index."""
        return {
            r.referree_id: r.id
            for r in self._referrals.values()
        }

    def generate_code(self, user_id: str) -> str:
        """
        Generate a unique referral code for user.

        Args:
            user_id: User identifier

        Returns:
            Referral code (JARVIS-XXXXXX)
        """
        # Check if user already has a code
        for code in self._codes.values():
            if code.user_id == user_id and code.active:
                return code.code

        # Generate new code
        while True:
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            code = f"JARVIS-{suffix}"
            if code not in self._codes:
                break

        referral_code = ReferralCode(
            code=code,
            user_id=user_id,
        )

        self._codes[code] = referral_code
        self._save_codes()

        return code

    def track_referral(self, code: str, new_user_id: str) -> Referral:
        """
        Track a new referral.

        Args:
            code: Referral code used
            new_user_id: New user's identifier

        Returns:
            Created referral

        Raises:
            ValueError: If code is invalid or user already referred
        """
        if code not in self._codes:
            raise ValueError(f"Invalid referral code: {code}")

        if new_user_id in self._referree_to_referral:
            raise ValueError(f"User already referred: {new_user_id}")

        referral_code = self._codes[code]

        # Can't refer yourself
        if referral_code.user_id == new_user_id:
            raise ValueError("Cannot use your own referral code")

        referral = Referral(
            id=f"ref_{int(time.time() * 1000)}",
            referrer_id=referral_code.user_id,
            referree_id=new_user_id,
            code=code,
        )

        # Update code usage
        referral_code.uses += 1
        self._save_codes()

        # Store referral
        self._referrals[referral.id] = referral
        self._referree_to_referral[new_user_id] = referral.id
        self._save_referrals()

        return referral

    def process_first_win(self, user_id: str) -> bool:
        """
        Process first winning trade for a referree.

        Credits $5 bonus to referree.

        Args:
            user_id: User identifier

        Returns:
            True if bonus was credited
        """
        referral_id = self._referree_to_referral.get(user_id)
        if not referral_id:
            return False

        referral = self._referrals.get(referral_id)
        if not referral or referral.referree_bonus_credited:
            return False

        # Credit bonus (in production, this would call wallet manager)
        referral.referree_bonus_credited = True
        self._save_referrals()

        return True

    def record_referree_fee(
        self,
        user_id: str,
        fee_amount: float,
        months_ago: int = 0
    ) -> Optional[float]:
        """
        Record a fee payment from a referree.

        Args:
            user_id: Referree user ID
            fee_amount: Fee amount paid
            months_ago: For testing - simulate payment from N months ago

        Returns:
            Commission amount (or None if not a referree)
        """
        referral_id = self._referree_to_referral.get(user_id)
        if not referral_id:
            return None

        referral = self._referrals.get(referral_id)
        if not referral:
            return None

        # Check if within commission period
        # Commission is only paid for the first year after referral
        payment_timestamp = time.time()

        # For testing: simulate a referral that's old (created months_ago)
        # This means the referral was created months_ago from now
        if months_ago > 0:
            # Pretend the referral was created months_ago, so it's old
            effective_referral_age_days = months_ago * 30
        else:
            # Normal case: referral age is from creation to now
            effective_referral_age_days = (payment_timestamp - referral.created_at) / 86400

        if effective_referral_age_days > COMMISSION_DURATION_DAYS:
            return 0.0  # Past commission period

        # Calculate commission
        commission = fee_amount * REFERRER_COMMISSION_RATE

        # Update referral totals
        referral.total_fees_paid += fee_amount
        referral.total_commission_earned += commission
        self._save_referrals()

        # Record payment
        payment = FeePayment(
            referral_id=referral_id,
            amount=fee_amount,
            commission=commission,
            timestamp=payment_timestamp,
        )

        with open(self.payments_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payment.to_dict()) + "\n")

        return commission

    def calculate_commissions(self, user_id: str) -> Dict[str, Any]:
        """
        Calculate total commissions for a referrer.

        Args:
            user_id: Referrer user ID

        Returns:
            Commission summary
        """
        total_commission = 0.0
        referral_count = 0
        active_referrals = 0

        now = time.time()

        for referral in self._referrals.values():
            if referral.referrer_id != user_id:
                continue

            referral_count += 1
            referral_age_days = (now - referral.created_at) / 86400

            if referral_age_days <= COMMISSION_DURATION_DAYS:
                active_referrals += 1
                total_commission += referral.total_commission_earned

        return {
            'user_id': user_id,
            'total': round(total_commission, 6),
            'referral_count': referral_count,
            'active_referrals': active_referrals,
            'commission_rate': REFERRER_COMMISSION_RATE,
            'duration_days': COMMISSION_DURATION_DAYS,
        }

    def get_referrals(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all referrals for a user.

        Args:
            user_id: Referrer user ID

        Returns:
            List of referral details
        """
        referrals = []

        for referral in self._referrals.values():
            if referral.referrer_id == user_id:
                referrals.append(referral.to_dict())

        return referrals

    def get_referrer(self, user_id: str) -> Optional[str]:
        """
        Get the referrer for a user.

        Args:
            user_id: User identifier

        Returns:
            Referrer user ID (or None)
        """
        referral_id = self._referree_to_referral.get(user_id)
        if not referral_id:
            return None

        referral = self._referrals.get(referral_id)
        return referral.referrer_id if referral else None

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get affiliate leaderboard.

        Args:
            limit: Number of top affiliates

        Returns:
            List of top affiliates by commission
        """
        # Aggregate by referrer
        referrer_stats: Dict[str, Dict[str, Any]] = {}

        for referral in self._referrals.values():
            rid = referral.referrer_id
            if rid not in referrer_stats:
                referrer_stats[rid] = {
                    'user_id': rid,
                    'referral_count': 0,
                    'total_commission': 0.0,
                }

            referrer_stats[rid]['referral_count'] += 1
            referrer_stats[rid]['total_commission'] += referral.total_commission_earned

        # Sort by commission
        leaderboard = sorted(
            referrer_stats.values(),
            key=lambda x: x['total_commission'],
            reverse=True
        )

        return leaderboard[:limit]
