"""
Fee Calculator - 0.5% Success Fee on Winning Trades.

Calculates fees only on profitable trades and distributes:
- 75% to user (0.375% of profit)
- 5% to charity (0.025% of profit)
- 20% to Jarvis company (0.1% of profit)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_FEE_RATE = 0.005  # 0.5%
USER_SHARE = 0.75  # 75%
CHARITY_SHARE = 0.05  # 5%
COMPANY_SHARE = 0.20  # 20%


@dataclass
class FeeRecord:
    """A single fee record."""
    id: str
    user_id: str
    amount: float
    symbol: str
    trade_id: str
    user_share: float
    charity_share: float
    company_share: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeeCalculator:
    """
    Calculates trading fees on profitable trades.

    Usage:
        calc = FeeCalculator()

        # Calculate fee for a profitable trade
        fee = calc.calculate_fee(
            entry_price=100.0,
            exit_price=120.0,
            position_size=10.0
        )

        # Get fee distribution breakdown
        distribution = calc.calculate_fee_distribution(
            entry_price=100.0,
            exit_price=120.0,
            position_size=10.0
        )
    """

    def __init__(
        self,
        fee_rate: float = DEFAULT_FEE_RATE,
        data_dir: Optional[Path] = None
    ):
        self.fee_rate = fee_rate
        self.user_share_rate = USER_SHARE
        self.charity_share_rate = CHARITY_SHARE
        self.company_share_rate = COMPANY_SHARE

        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parents[2] / "data" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.fees_file = self.data_dir / "fees.jsonl"

        # In-memory cache for daily aggregation
        self._daily_fees: List[FeeRecord] = []

    def calculate_fee(
        self,
        entry_price: float,
        exit_price: float,
        position_size: float,
        user_tier: str = "free"
    ) -> float:
        """
        Calculate fee on a trade.

        Fee is only charged on profit:
            fee = max(0, (exit_price - entry_price) * position_size * fee_rate)

        Args:
            entry_price: Price at entry
            exit_price: Price at exit
            position_size: Number of units
            user_tier: User subscription tier (for future tier-based rates)

        Returns:
            Fee amount (0 if no profit)
        """
        profit = (exit_price - entry_price) * position_size

        if profit <= 0:
            return 0.0

        # Calculate fee (future: adjust rate based on tier)
        fee = profit * self.fee_rate

        return round(fee, 6)

    def calculate_fee_distribution(
        self,
        entry_price: float,
        exit_price: float,
        position_size: float,
        user_tier: str = "free"
    ) -> Dict[str, float]:
        """
        Calculate fee and its distribution.

        Returns:
            Dict with:
                - total_fee: Total fee amount
                - user_share: Amount to user (75%)
                - charity_share: Amount to charity (5%)
                - company_share: Amount to company (20%)
        """
        total_fee = self.calculate_fee(entry_price, exit_price, position_size, user_tier)

        return {
            'total_fee': round(total_fee, 6),
            'user_share': round(total_fee * self.user_share_rate, 6),
            'charity_share': round(total_fee * self.charity_share_rate, 6),
            'company_share': round(total_fee * self.company_share_rate, 6),
            'profit': round((exit_price - entry_price) * position_size, 6),
            'fee_rate': self.fee_rate,
        }

    def record_fee(
        self,
        user_id: str,
        amount: float,
        symbol: str,
        trade_id: str
    ) -> FeeRecord:
        """
        Record a fee payment.

        Args:
            user_id: User who generated the fee
            amount: Total fee amount
            symbol: Trading pair (e.g., SOL/USDC)
            trade_id: Associated trade ID

        Returns:
            FeeRecord
        """
        record = FeeRecord(
            id=f"fee_{int(time.time() * 1000)}_{user_id[:8]}",
            user_id=user_id,
            amount=amount,
            symbol=symbol,
            trade_id=trade_id,
            user_share=round(amount * self.user_share_rate, 6),
            charity_share=round(amount * self.charity_share_rate, 6),
            company_share=round(amount * self.company_share_rate, 6),
        )

        # Store in memory
        self._daily_fees.append(record)

        # Persist to file
        with open(self.fees_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        return record

    def get_daily_totals(self, date: Optional[str] = None) -> Dict[str, float]:
        """
        Get aggregated totals for a day.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Dict with totals for fees, user earnings, charity, company
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Filter fees for the date
        start_ts = datetime.strptime(date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).timestamp()
        end_ts = start_ts + 86400

        # Use in-memory cache first
        day_fees = [
            f for f in self._daily_fees
            if start_ts <= f.timestamp < end_ts
        ]

        # Also read from file if cache is empty
        if not day_fees and self.fees_file.exists():
            with open(self.fees_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if start_ts <= data.get('timestamp', 0) < end_ts:
                            day_fees.append(FeeRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue

        return {
            'date': date,
            'total_fees': round(sum(f.amount for f in day_fees), 6),
            'user_earnings': round(sum(f.user_share for f in day_fees), 6),
            'charity_amount': round(sum(f.charity_share for f in day_fees), 6),
            'company_revenue': round(sum(f.company_share for f in day_fees), 6),
            'fee_count': len(day_fees),
        }

    def get_monthly_totals(self, month: str) -> Dict[str, float]:
        """
        Get aggregated totals for a month.

        Args:
            month: Month string (YYYY-MM)

        Returns:
            Dict with monthly totals
        """
        month_fees: List[FeeRecord] = []

        if self.fees_file.exists():
            with open(self.fees_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        ts = data.get('timestamp', 0)
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        if dt.strftime("%Y-%m") == month:
                            month_fees.append(FeeRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue

        return {
            'month': month,
            'total_fees': round(sum(f.amount for f in month_fees), 6),
            'user_earnings': round(sum(f.user_share for f in month_fees), 6),
            'charity_amount': round(sum(f.charity_share for f in month_fees), 6),
            'company_revenue': round(sum(f.company_share for f in month_fees), 6),
            'fee_count': len(month_fees),
        }

    def get_user_fees(self, user_id: str) -> List[FeeRecord]:
        """Get all fees for a user."""
        user_fees: List[FeeRecord] = []

        if self.fees_file.exists():
            with open(self.fees_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get('user_id') == user_id:
                            user_fees.append(FeeRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue

        return user_fees
