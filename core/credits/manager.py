"""
Credit Manager - Core credit operations.

Handles:
- Credit purchases
- Credit consumption
- Balance tracking
- Usage logging
- Transaction history
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.credits.models import (
    CreditBalance,
    CreditPackage,
    CreditTransaction,
    ApiUsage,
    TransactionType,
    User,
    UserTier,
    get_endpoint_cost,
    init_database,
)

logger = logging.getLogger("jarvis.credits")


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits."""
    pass


class UserNotFoundError(Exception):
    """Raised when user doesn't exist."""
    pass


class CreditManager:
    """
    Manages credit operations for the platform.

    Usage:
        manager = CreditManager()

        # Create user
        user = manager.create_user(email="user@example.com")

        # Add credits (after payment)
        manager.add_credits(user.id, amount=100, reason="purchase", package_id="pro_100")

        # Consume credits
        success = manager.consume_credits(user.id, amount=5, endpoint="/api/trade/execute")

        # Check balance
        balance = manager.get_balance(user.id)
    """

    def __init__(self, db_path: str = None):
        """Initialize credit manager."""
        if db_path is None:
            data_dir = Path(os.getenv("DATA_DIR", "data"))
            db_path = str(data_dir / "credits.db")

        self.db_path = db_path
        self._conn = init_database(db_path)
        logger.info(f"Credit manager initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    # =========================================================================
    # User Management
    # =========================================================================

    def create_user(
        self,
        email: str,
        user_id: str = None,
        tier: UserTier = UserTier.FREE,
        stripe_customer_id: str = None,
        wallet_address: str = None,
    ) -> User:
        """Create a new user."""
        if user_id is None:
            user_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Create user
            cursor.execute(
                """
                INSERT INTO users (id, email, created_at, tier, stripe_customer_id, wallet_address, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, now, tier.value, stripe_customer_id, wallet_address, now),
            )

            # Initialize credit balance
            cursor.execute(
                """
                INSERT INTO credit_balances (user_id, balance, updated_at)
                VALUES (?, 0, ?)
                """,
                (user_id, now),
            )

            conn.commit()
            logger.info(f"Created user: {user_id} ({email})")

            return User(
                id=user_id,
                email=email,
                tier=tier,
                stripe_customer_id=stripe_customer_id,
                wallet_address=wallet_address,
            )

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f"User already exists: {e}")
        finally:
            conn.close()

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return User(
            id=row[0],
            email=row[1],
            created_at=datetime.fromisoformat(row[2]),
            tier=UserTier(row[3]),
            stripe_customer_id=row[4],
            wallet_address=row[5],
            metadata=json.loads(row[6]) if row[6] else {},
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return User(
            id=row[0],
            email=row[1],
            created_at=datetime.fromisoformat(row[2]),
            tier=UserTier(row[3]),
            stripe_customer_id=row[4],
            wallet_address=row[5],
            metadata=json.loads(row[6]) if row[6] else {},
        )

    def update_user_stripe(self, user_id: str, stripe_customer_id: str) -> bool:
        """Update user's Stripe customer ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET stripe_customer_id = ?, updated_at = ? WHERE id = ?",
            (stripe_customer_id, datetime.now(timezone.utc).isoformat(), user_id),
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    # =========================================================================
    # Credit Operations
    # =========================================================================

    def get_balance(self, user_id: str) -> CreditBalance:
        """Get user's current credit balance."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM credit_balances WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise UserNotFoundError(f"User not found: {user_id}")

        return CreditBalance(
            user_id=row[0],
            balance=row[1],
            lifetime_purchased=row[2],
            lifetime_consumed=row[3],
            lifetime_bonus=row[4],
            last_purchase_at=datetime.fromisoformat(row[5]) if row[5] else None,
            last_consumption_at=datetime.fromisoformat(row[6]) if row[6] else None,
            updated_at=datetime.fromisoformat(row[7]) if row[7] else datetime.now(timezone.utc),
        )

    def add_credits(
        self,
        user_id: str,
        amount: int,
        transaction_type: TransactionType = TransactionType.PURCHASE,
        description: str = "",
        stripe_payment_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> CreditTransaction:
        """
        Add credits to a user's balance.

        Args:
            user_id: User ID
            amount: Credits to add (must be positive)
            transaction_type: Type of transaction
            description: Human-readable description
            stripe_payment_id: Stripe payment ID for purchases
            metadata: Additional metadata

        Returns:
            Transaction record
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Get current balance
            cursor.execute("SELECT balance FROM credit_balances WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if not row:
                raise UserNotFoundError(f"User not found: {user_id}")

            current_balance = row[0]
            new_balance = current_balance + amount

            # Update balance
            if transaction_type == TransactionType.PURCHASE:
                cursor.execute(
                    """
                    UPDATE credit_balances
                    SET balance = ?, lifetime_purchased = lifetime_purchased + ?,
                        last_purchase_at = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_balance, amount, now, now, user_id),
                )
            elif transaction_type == TransactionType.BONUS:
                cursor.execute(
                    """
                    UPDATE credit_balances
                    SET balance = ?, lifetime_bonus = lifetime_bonus + ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_balance, amount, now, user_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE credit_balances
                    SET balance = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_balance, now, user_id),
                )

            # Record transaction
            cursor.execute(
                """
                INSERT INTO credit_transactions
                (user_id, type, amount, balance_after, description, stripe_payment_id, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    transaction_type.value,
                    amount,
                    new_balance,
                    description,
                    stripe_payment_id,
                    json.dumps(metadata or {}),
                    now,
                ),
            )

            transaction_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Added {amount} credits to {user_id}, new balance: {new_balance}")

            return CreditTransaction(
                id=transaction_id,
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                balance_after=new_balance,
                description=description,
                stripe_payment_id=stripe_payment_id,
                metadata=metadata or {},
            )

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def consume_credits(
        self,
        user_id: str,
        amount: int = None,
        endpoint: str = None,
        description: str = "",
        request_id: str = None,
        duration_ms: int = 0,
        metadata: Dict[str, Any] = None,
    ) -> Tuple[bool, int]:
        """
        Consume credits for API usage.

        Args:
            user_id: User ID
            amount: Credits to consume (uses endpoint cost if not provided)
            endpoint: API endpoint for cost lookup
            description: Description of usage
            request_id: Unique request ID
            duration_ms: Request duration
            metadata: Additional metadata

        Returns:
            Tuple of (success, remaining_balance)

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
        """
        # Determine cost
        if amount is None:
            if endpoint:
                amount = get_endpoint_cost(endpoint)
            else:
                amount = 1

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Get current balance
            cursor.execute("SELECT balance FROM credit_balances WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if not row:
                raise UserNotFoundError(f"User not found: {user_id}")

            current_balance = row[0]

            if current_balance < amount:
                raise InsufficientCreditsError(
                    f"Insufficient credits: {current_balance} < {amount}"
                )

            new_balance = current_balance - amount

            # Update balance
            cursor.execute(
                """
                UPDATE credit_balances
                SET balance = ?, lifetime_consumed = lifetime_consumed + ?,
                    last_consumption_at = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (new_balance, amount, now, now, user_id),
            )

            # Record transaction
            cursor.execute(
                """
                INSERT INTO credit_transactions
                (user_id, type, amount, balance_after, description, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    TransactionType.CONSUMPTION.value,
                    -amount,
                    new_balance,
                    description or endpoint or "api_usage",
                    json.dumps(metadata or {}),
                    now,
                ),
            )

            # Log API usage
            if endpoint:
                cursor.execute(
                    """
                    INSERT INTO api_usage
                    (user_id, endpoint, credits_consumed, request_id, duration_ms, success, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        user_id,
                        endpoint,
                        amount,
                        request_id or "",
                        duration_ms,
                        json.dumps(metadata or {}),
                        now,
                    ),
                )

            conn.commit()

            logger.debug(f"Consumed {amount} credits from {user_id}, remaining: {new_balance}")

            return True, new_balance

        except InsufficientCreditsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.error(f"Credit consumption failed: {e}")
            raise e
        finally:
            conn.close()

    def check_credits(self, user_id: str, amount: int) -> bool:
        """Check if user has enough credits."""
        try:
            balance = self.get_balance(user_id)
            return balance.balance >= amount
        except UserNotFoundError:
            return False

    # =========================================================================
    # Packages
    # =========================================================================

    def get_packages(self, active_only: bool = True) -> List[CreditPackage]:
        """Get available credit packages."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if active_only:
            cursor.execute("SELECT * FROM credit_packages WHERE active = 1 ORDER BY price_cents")
        else:
            cursor.execute("SELECT * FROM credit_packages ORDER BY price_cents")

        rows = cursor.fetchall()
        conn.close()

        packages = []
        for row in rows:
            packages.append(CreditPackage(
                id=row[0],
                name=row[1],
                credits=row[2],
                bonus_credits=row[3],
                price_cents=row[4],
                description=row[5] or "",
                active=bool(row[6]),
                popular=bool(row[7]),
                stripe_price_id=row[8],
            ))

        return packages

    def get_package(self, package_id: str) -> Optional[CreditPackage]:
        """Get a specific package."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM credit_packages WHERE id = ?", (package_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return CreditPackage(
            id=row[0],
            name=row[1],
            credits=row[2],
            bonus_credits=row[3],
            price_cents=row[4],
            description=row[5] or "",
            active=bool(row[6]),
            popular=bool(row[7]),
            stripe_price_id=row[8],
        )

    # =========================================================================
    # History & Analytics
    # =========================================================================

    def get_transactions(
        self,
        user_id: str,
        limit: int = 100,
        transaction_type: TransactionType = None,
    ) -> List[CreditTransaction]:
        """Get transaction history for a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if transaction_type:
            cursor.execute(
                """
                SELECT * FROM credit_transactions
                WHERE user_id = ? AND type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, transaction_type.value, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM credit_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )

        rows = cursor.fetchall()
        conn.close()

        return [
            CreditTransaction(
                id=row[0],
                user_id=row[1],
                type=TransactionType(row[2]),
                amount=row[3],
                balance_after=row[4],
                description=row[5] or "",
                stripe_payment_id=row[6],
                metadata=json.loads(row[7]) if row[7] else {},
                created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(timezone.utc),
            )
            for row in rows
        ]

    def get_usage_stats(
        self,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get usage statistics for a user."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Total consumption
        cursor.execute(
            """
            SELECT SUM(credits_consumed), COUNT(*)
            FROM api_usage
            WHERE user_id = ?
              AND timestamp > datetime('now', ? || ' days')
            """,
            (user_id, -days),
        )
        row = cursor.fetchone()
        total_consumed = row[0] or 0
        total_requests = row[1] or 0

        # By endpoint
        cursor.execute(
            """
            SELECT endpoint, SUM(credits_consumed), COUNT(*)
            FROM api_usage
            WHERE user_id = ?
              AND timestamp > datetime('now', ? || ' days')
            GROUP BY endpoint
            ORDER BY SUM(credits_consumed) DESC
            """,
            (user_id, -days),
        )
        by_endpoint = {row[0]: {"credits": row[1], "requests": row[2]} for row in cursor.fetchall()}

        # Daily consumption
        cursor.execute(
            """
            SELECT DATE(timestamp), SUM(credits_consumed)
            FROM api_usage
            WHERE user_id = ?
              AND timestamp > datetime('now', ? || ' days')
            GROUP BY DATE(timestamp)
            ORDER BY DATE(timestamp)
            """,
            (user_id, -days),
        )
        daily = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "period_days": days,
            "total_consumed": total_consumed,
            "total_requests": total_requests,
            "avg_per_day": total_consumed / days if days > 0 else 0,
            "by_endpoint": by_endpoint,
            "daily": daily,
        }

    def get_revenue_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get revenue statistics (admin)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Total revenue
        cursor.execute(
            """
            SELECT SUM(amount), COUNT(*)
            FROM credit_transactions
            WHERE type = 'purchase'
              AND created_at > datetime('now', ? || ' days')
            """,
            (-days,),
        )
        row = cursor.fetchone()

        # Would need to join with packages to get actual revenue
        # For now, estimate based on package pricing

        conn.close()

        return {
            "period_days": days,
            "total_credits_sold": row[0] or 0,
            "purchase_count": row[1] or 0,
        }

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()


# =============================================================================
# Singleton
# =============================================================================

_manager: Optional[CreditManager] = None


def get_credit_manager() -> CreditManager:
    """Get or create the singleton credit manager."""
    global _manager

    if _manager is None:
        _manager = CreditManager()

    return _manager
