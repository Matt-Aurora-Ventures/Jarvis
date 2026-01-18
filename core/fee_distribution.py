"""
Fee Distribution & Revenue System

Revenue Model:
- 0.5% success fees on all winning trades via Bags API
- Distribution:
  * 75% → Users who generated the trades
  * 5% → Charity (social impact)
  * 20% → Company funds & founder
- All fees reinvest back into Treasury and ecosystem

This creates perfect incentive alignment:
- Users make money → share rewards
- Company funds development
- Charity creates positive impact
- Treasury grows autonomously
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)


class FeeType(Enum):
    """Types of fees."""
    SUCCESS_FEE = "success"  # 0.5% on winning trades
    PERFORMANCE_FEE = "performance"  # Bonus for beat target
    LIQUIDATION_FEE = "liquidation"  # Fee if position liquidated
    WITHDRAWAL_FEE = "withdrawal"  # Small % on wallet withdrawal


class BeneficiaryType(Enum):
    """Types of beneficiaries."""
    USER = "user"  # User who generated the trade
    COMPANY = "company"  # Jarvis company
    FOUNDER = "founder"  # Founder allocation
    CHARITY = "charity"  # Charitable donation
    TREASURY = "treasury"  # Treasury reinvestment


@dataclass
class SuccessFee:
    """Success fee from winning trade."""
    tx_id: str  # Original trade transaction ID
    user_id: int
    symbol: str
    entry_price: float
    exit_price: float
    gross_pnl: float  # PnL before fees
    success_fee_amount: float  # 0.5% of gross PnL
    recorded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeeDistribution:
    """Distribution of a success fee."""
    fee_id: str
    tx_id: str
    total_fee: float

    # Distribution breakdown (always sums to 100%)
    user_amount: float  # 75%
    charity_amount: float  # 5%
    company_amount: float  # 20%

    # Status
    status: str = "pending"  # pending, distributed, claimed
    distributed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'fee_id': self.fee_id,
            'total_fee': self.total_fee,
            'user_amount': self.user_amount,
            'charity_amount': self.charity_amount,
            'company_amount': self.company_amount,
            'user_pct': 75,
            'charity_pct': 5,
            'company_pct': 20,
        }


@dataclass
class UserFeeBalance:
    """User's accumulated fee balance."""
    user_id: int
    total_earned_fees: float = 0.0
    total_claimed_fees: float = 0.0
    pending_fees: float = 0.0

    @property
    def available_to_claim(self) -> float:
        """Fees ready to claim."""
        return self.total_earned_fees - self.total_claimed_fees


class FeeDistributionSystem:
    """
    Manages all fee collection and distribution.

    Ensures:
    - 0.5% success fees collected on winning trades
    - Proper distribution to all beneficiaries
    - Transparent tracking and reporting
    - Regular settlement to Treasury
    """

    def __init__(self, db_path: str = "~/.lifeos/fees.db"):
        """Initialize fee system."""
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Fee percentages
        self.SUCCESS_FEE_PCT = 0.005  # 0.5%

        # Distribution percentages
        self.USER_PCT = 0.75  # 75%
        self.CHARITY_PCT = 0.05  # 5%
        self.COMPANY_PCT = 0.20  # 20%

        self._init_database()

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Success fees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS success_fees (
                tx_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                gross_pnl REAL NOT NULL,
                success_fee_amount REAL NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)

        # Fee distributions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fee_distributions (
                fee_id TEXT PRIMARY KEY,
                tx_id TEXT UNIQUE NOT NULL,
                total_fee REAL NOT NULL,
                user_amount REAL NOT NULL,
                charity_amount REAL NOT NULL,
                company_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                distributed_at TEXT,
                FOREIGN KEY (tx_id) REFERENCES success_fees(tx_id)
            )
        """)

        # User fee balances table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_fee_balances (
                user_id INTEGER PRIMARY KEY,
                total_earned_fees REAL DEFAULT 0.0,
                total_claimed_fees REAL DEFAULT 0.0,
                pending_fees REAL DEFAULT 0.0,
                last_updated TEXT NOT NULL
            )
        """)

        # Company revenue tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_revenue (
                month TEXT PRIMARY KEY,
                total_revenue REAL,
                treasury_reinvest REAL,
                founder_allocation REAL,
                recorded_at TEXT
            )
        """)

        # Charity donations tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS charity_donations (
                donation_id TEXT PRIMARY KEY,
                amount REAL,
                recipient TEXT,
                donated_at TEXT,
                reason TEXT
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Fee system database initialized at {self.db_path}")

    # ==================== FEE COLLECTION ====================

    def calculate_success_fee(self, gross_pnl: float) -> float:
        """
        Calculate success fee from winning trade PnL.

        Args:
            gross_pnl: Gross profit before fees

        Returns:
            Success fee amount (0.5% of PnL)
        """
        if gross_pnl <= 0:
            return 0.0

        return gross_pnl * self.SUCCESS_FEE_PCT

    def record_successful_trade(self, tx_id: str, user_id: int, symbol: str,
                               entry_price: float, exit_price: float,
                               gross_pnl: float) -> Tuple[bool, Optional[SuccessFee]]:
        """
        Record a successful trade and calculate fees.

        Args:
            tx_id: Transaction ID
            user_id: User who made the trade
            symbol: Token symbol
            entry_price: Entry price
            exit_price: Exit price
            gross_pnl: Gross profit (before fees)

        Returns:
            (success, SuccessFee)
        """
        try:
            success_fee_amount = self.calculate_success_fee(gross_pnl)

            if success_fee_amount <= 0:
                return False, None

            fee = SuccessFee(
                tx_id=tx_id,
                user_id=user_id,
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                gross_pnl=gross_pnl,
                success_fee_amount=success_fee_amount,
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO success_fees (
                    tx_id, user_id, symbol, entry_price, exit_price,
                    gross_pnl, success_fee_amount, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, user_id, symbol, entry_price, exit_price,
                gross_pnl, success_fee_amount, datetime.utcnow().isoformat()
            ))

            conn.commit()
            conn.close()

            logger.info(
                f"Success fee recorded: {symbol} ${success_fee_amount:.2f} "
                f"(${gross_pnl:.2f} PnL) for user {user_id}"
            )

            # Distribute the fee
            self._distribute_success_fee(fee)

            return True, fee

        except Exception as e:
            logger.error(f"Failed to record success fee: {e}")
            return False, None

    # ==================== FEE DISTRIBUTION ====================

    def _distribute_success_fee(self, fee: SuccessFee):
        """
        Distribute a success fee to all beneficiaries.

        Distribution:
        - 75% to user
        - 5% to charity
        - 20% to company
        """
        try:
            total = fee.success_fee_amount

            # Calculate distribution
            user_amount = total * self.USER_PCT
            charity_amount = total * self.CHARITY_PCT
            company_amount = total * self.COMPANY_PCT

            # Create distribution record
            fee_id = f"dist_{fee.tx_id}_{datetime.utcnow().timestamp():.0f}"

            distribution = FeeDistribution(
                fee_id=fee_id,
                tx_id=fee.tx_id,
                total_fee=total,
                user_amount=user_amount,
                charity_amount=charity_amount,
                company_amount=company_amount,
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Record distribution
            cursor.execute("""
                INSERT INTO fee_distributions (
                    fee_id, tx_id, total_fee, user_amount,
                    charity_amount, company_amount, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                distribution.fee_id, distribution.tx_id,
                distribution.total_fee, distribution.user_amount,
                distribution.charity_amount, distribution.company_amount,
                'pending'
            ))

            # Update user balance
            cursor.execute("""
                INSERT INTO user_fee_balances (user_id, total_earned_fees, pending_fees, last_updated)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_earned_fees = total_earned_fees + ?,
                    pending_fees = pending_fees + ?,
                    last_updated = ?
            """, (
                fee.user_id, user_amount, user_amount, datetime.utcnow().isoformat(),
                user_amount, user_amount, datetime.utcnow().isoformat()
            ))

            conn.commit()
            conn.close()

            logger.info(
                f"Fee distributed: User ${user_amount:.2f}, "
                f"Charity ${charity_amount:.2f}, "
                f"Company ${company_amount:.2f}"
            )

        except Exception as e:
            logger.error(f"Fee distribution failed: {e}")

    # ==================== USER FEE MANAGEMENT ====================

    def get_user_fee_balance(self, user_id: int) -> Optional[UserFeeBalance]:
        """Get user's fee balance."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT user_id, total_earned_fees, total_claimed_fees, pending_fees "
                "FROM user_fee_balances WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return UserFeeBalance(user_id=user_id)

            return UserFeeBalance(
                user_id=row[0],
                total_earned_fees=row[1],
                total_claimed_fees=row[2],
                pending_fees=row[3],
            )

        except Exception as e:
            logger.error(f"Failed to get user fee balance: {e}")
            return None

    def claim_user_fees(self, user_id: int, amount: float) -> Tuple[bool, str]:
        """
        Allow user to claim their accumulated fees.

        Args:
            user_id: User ID
            amount: Amount to claim

        Returns:
            (success, message)
        """
        try:
            balance = self.get_user_fee_balance(user_id)

            if not balance:
                return False, "Fee balance not found"

            available = balance.available_to_claim

            if amount > available:
                return False, f"Insufficient fees to claim. Available: ${available:.2f}"

            if amount <= 0:
                return False, "Claim amount must be positive"

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE user_fee_balances
                SET total_claimed_fees = total_claimed_fees + ?,
                    pending_fees = pending_fees - ?,
                    last_updated = ?
                WHERE user_id = ?
            """, (amount, amount, datetime.utcnow().isoformat(), user_id))

            conn.commit()
            conn.close()

            logger.info(f"User {user_id} claimed ${amount:.2f} in fees")
            return True, f"Claimed ${amount:.2f}"

        except Exception as e:
            logger.error(f"Fee claim failed: {e}")
            return False, f"Claim failed: {e}"

    # ==================== COMPANY REVENUE ====================

    def get_monthly_revenue(self, month: str = None) -> Dict[str, float]:
        """
        Get company revenue breakdown for a month.

        Args:
            month: "YYYY-MM" format, defaults to current month

        Returns:
            {'total_revenue': float, 'company': float, 'charity': float, 'treasury': float}
        """
        try:
            if not month:
                month = datetime.utcnow().strftime("%Y-%m")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all fees from this month
            cursor.execute("""
                SELECT SUM(total_fee) FROM fee_distributions
                WHERE status = 'distributed' AND
                      SUBSTR(distributed_at, 1, 7) = ?
            """, (month,))

            result = cursor.fetchone()
            total_fees = result[0] or 0.0

            conn.close()

            company_amount = total_fees * self.COMPANY_PCT
            charity_amount = total_fees * self.CHARITY_PCT
            treasury_amount = total_fees * 0.25  # 25% of company portion goes to treasury

            return {
                'month': month,
                'total_revenue': total_fees,
                'company_funds': company_amount * 0.8,  # 80% company funds
                'founder_allocation': company_amount * 0.2,  # 20% founder
                'charity_donations': charity_amount,
                'treasury_reinvest': treasury_amount,
            }

        except Exception as e:
            logger.error(f"Failed to get monthly revenue: {e}")
            return {}

    def get_yearly_revenue(self, year: int = None) -> Dict[str, float]:
        """
        Get full year revenue.

        Args:
            year: Year (defaults to current)

        Returns:
            Yearly revenue breakdown
        """
        try:
            if not year:
                year = datetime.utcnow().year

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT SUM(total_fee) FROM fee_distributions
                WHERE status = 'distributed' AND
                      SUBSTR(distributed_at, 1, 4) = ?
            """, (str(year),))

            result = cursor.fetchone()
            total_fees = result[0] or 0.0

            conn.close()

            return {
                'year': year,
                'total_revenue': total_fees,
                'company_funds': total_fees * self.COMPANY_PCT * 0.8,
                'founder_allocation': total_fees * self.COMPANY_PCT * 0.2,
                'charity_donations': total_fees * self.CHARITY_PCT,
                'user_earnings': total_fees * self.USER_PCT,
                'treasury_reinvest': total_fees * 0.05,  # 5% of revenue
            }

        except Exception as e:
            logger.error(f"Failed to get yearly revenue: {e}")
            return {}

    # ==================== REPORTING ====================

    def get_fee_statistics(self) -> Dict[str, Any]:
        """Get overall fee system statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total fees collected
            cursor.execute("SELECT SUM(success_fee_amount) FROM success_fees")
            total_fees = cursor.fetchone()[0] or 0.0

            # Number of profitable trades
            cursor.execute("SELECT COUNT(*) FROM success_fees")
            profitable_trades = cursor.fetchone()[0] or 0

            # Total distributed
            cursor.execute("SELECT SUM(total_fee) FROM fee_distributions WHERE status = 'distributed'")
            total_distributed = cursor.fetchone()[0] or 0.0

            # User earnings
            cursor.execute("SELECT SUM(total_earned_fees) FROM user_fee_balances")
            total_user_earnings = cursor.fetchone()[0] or 0.0

            # Charity donations
            cursor.execute("SELECT SUM(amount) FROM charity_donations")
            total_charity = cursor.fetchone()[0] or 0.0

            conn.close()

            return {
                'total_fees_collected': total_fees,
                'profitable_trades': profitable_trades,
                'avg_fee_per_trade': total_fees / profitable_trades if profitable_trades > 0 else 0,
                'total_distributed': total_distributed,
                'pending_distribution': total_fees - total_distributed,
                'total_user_earnings': total_user_earnings,
                'total_charity_donations': total_charity,
                'company_revenue': total_distributed * self.COMPANY_PCT,
                'treasury_size': total_distributed * 0.05,  # Estimated
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def generate_fee_report(self) -> str:
        """Generate human-readable fee report."""
        try:
            stats = self.get_fee_statistics()
            monthly = self.get_monthly_revenue()

            report = f"""
╔════════════════════════════════════════════════════════════════╗
║                      FEE DISTRIBUTION REPORT                   ║
╚════════════════════════════════════════════════════════════════╝

📊 OVERALL STATISTICS
├─ Total Fees Collected: ${stats.get('total_fees_collected', 0):.2f}
├─ Profitable Trades: {stats.get('profitable_trades', 0)}
├─ Avg Fee per Trade: ${stats.get('avg_fee_per_trade', 0):.4f}
└─ Pending Distribution: ${stats.get('pending_distribution', 0):.2f}

📈 MONTHLY REVENUE (Current)
├─ Total: ${monthly.get('total_revenue', 0):.2f}
├─ User Earnings (75%): ${monthly.get('total_revenue', 0) * 0.75:.2f}
├─ Charity (5%): ${monthly.get('charity_donations', 0):.2f}
└─ Company (20%): ${monthly.get('company_funds', 0) + monthly.get('founder_allocation', 0):.2f}

💰 COMPANY BREAKDOWN
├─ Company Funds (16%): ${monthly.get('company_funds', 0):.2f}
├─ Founder Allocation (4%): ${monthly.get('founder_allocation', 0):.2f}
└─ Treasury Reinvest: ${monthly.get('treasury_reinvest', 0):.2f}

❤️ CHARITABLE IMPACT
└─ Total Donated: ${stats.get('total_charity_donations', 0):.2f}

💎 USER BENEFITS
└─ Total Distributed to Users: ${stats.get('total_user_earnings', 0):.2f}

═════════════════════════════════════════════════════════════════

✨ INCENTIVE ALIGNMENT
The system ensures:
✅ Users earn 75% of fees they generate
✅ Company funds sustainable development
✅ Charity creates positive social impact
✅ Treasury grows autonomously

═════════════════════════════════════════════════════════════════
"""
            return report

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return "Report generation failed"
