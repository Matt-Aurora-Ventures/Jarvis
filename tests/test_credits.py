"""
Tests for Credit System Module.

Tests credit management, Stripe integration, and metering middleware.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Import modules to test
from core.credits.models import (
    CreditPackage,
    CreditTransaction,
    CreditBalance,
    TransactionType,
    UserTier,
    CREDIT_PACKAGES,
)
from core.credits.manager import CreditManager
from core.credits.middleware import CreditMeteringMiddleware, MeteringResult


class TestCreditPackage:
    """Tests for CreditPackage model."""

    def test_package_creation(self):
        """Test CreditPackage creation."""
        package = CreditPackage(
            id="test_100",
            name="Test Package",
            credits=100,
            price_usd=25.0,
            bonus_credits=10,
            tier="starter",
        )

        assert package.credits == 100
        assert package.price_usd == 25.0
        assert package.bonus_credits == 10

    def test_total_credits(self):
        """Test total credits calculation."""
        package = CreditPackage(
            id="test_100",
            name="Test Package",
            credits=100,
            price_usd=25.0,
            bonus_credits=10,
            tier="starter",
        )

        assert package.total_credits == 110

    def test_predefined_packages_exist(self):
        """Test predefined packages are available."""
        assert "starter_25" in CREDIT_PACKAGES
        assert "pro_100" in CREDIT_PACKAGES
        assert "whale_500" in CREDIT_PACKAGES


class TestCreditTransaction:
    """Tests for CreditTransaction model."""

    def test_transaction_creation(self):
        """Test CreditTransaction creation."""
        tx = CreditTransaction(
            id="tx_123",
            user_id="user_456",
            amount=100,
            type=TransactionType.PURCHASE,
            description="Test purchase",
        )

        assert tx.amount == 100
        assert tx.type == TransactionType.PURCHASE

    def test_transaction_to_dict(self):
        """Test transaction serialization."""
        tx = CreditTransaction(
            id="tx_123",
            user_id="user_456",
            amount=100,
            type=TransactionType.PURCHASE,
            description="Test purchase",
        )

        data = tx.to_dict()

        assert data["id"] == "tx_123"
        assert data["amount"] == 100
        assert data["type"] == "purchase"


class TestCreditBalance:
    """Tests for CreditBalance model."""

    def test_balance_creation(self):
        """Test CreditBalance creation."""
        balance = CreditBalance(
            user_id="user_123",
            credits=500,
            points=1000,
            tier=UserTier.PRO,
        )

        assert balance.credits == 500
        assert balance.points == 1000
        assert balance.tier == UserTier.PRO

    def test_balance_sufficient(self):
        """Test balance sufficiency check."""
        balance = CreditBalance(
            user_id="user_123",
            credits=500,
            points=1000,
            tier=UserTier.PRO,
        )

        assert balance.has_sufficient(400) is True
        assert balance.has_sufficient(500) is True
        assert balance.has_sufficient(501) is False

    def test_balance_to_dict(self):
        """Test balance serialization."""
        balance = CreditBalance(
            user_id="user_123",
            credits=500,
            points=1000,
            tier=UserTier.PRO,
        )

        data = balance.to_dict()

        assert data["credits"] == 500
        assert data["tier"] == "pro"


class TestUserTier:
    """Tests for UserTier enum."""

    def test_tier_values(self):
        """Test tier values exist."""
        assert UserTier.FREE.value == "free"
        assert UserTier.STARTER.value == "starter"
        assert UserTier.PRO.value == "pro"
        assert UserTier.WHALE.value == "whale"

    def test_tier_from_points(self):
        """Test tier determination from points."""
        assert UserTier.from_points(0) == UserTier.FREE
        assert UserTier.from_points(500) == UserTier.FREE
        assert UserTier.from_points(1000) == UserTier.STARTER
        assert UserTier.from_points(5000) == UserTier.PRO
        assert UserTier.from_points(25000) == UserTier.WHALE


class TestCreditManager:
    """Tests for CreditManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a CreditManager with temp database."""
        db_path = str(tmp_path / "test_credits.db")
        return CreditManager(db_path=db_path)

    def test_create_user(self, manager):
        """Test user creation."""
        user = manager.create_user(
            email="test@example.com",
            user_id="user_123",
        )

        assert user.user_id == "user_123"
        assert user.credits == 0
        assert user.tier == UserTier.FREE

    def test_create_user_with_tier(self, manager):
        """Test user creation with specific tier."""
        user = manager.create_user(
            email="test@example.com",
            user_id="user_123",
            tier=UserTier.PRO,
        )

        assert user.tier == UserTier.PRO

    def test_get_balance(self, manager):
        """Test balance retrieval."""
        manager.create_user("test@example.com", "user_123")

        balance = manager.get_balance("user_123")

        assert balance is not None
        assert balance.credits == 0

    def test_get_balance_nonexistent(self, manager):
        """Test balance retrieval for nonexistent user."""
        balance = manager.get_balance("nonexistent")

        assert balance is None

    def test_add_credits(self, manager):
        """Test adding credits."""
        manager.create_user("test@example.com", "user_123")

        tx = manager.add_credits(
            user_id="user_123",
            amount=100,
            transaction_type=TransactionType.PURCHASE,
            description="Test purchase",
        )

        assert tx.amount == 100
        balance = manager.get_balance("user_123")
        assert balance.credits == 100

    def test_add_credits_with_points(self, manager):
        """Test adding credits also adds points."""
        manager.create_user("test@example.com", "user_123")

        manager.add_credits(
            user_id="user_123",
            amount=100,
            transaction_type=TransactionType.PURCHASE,
            description="Test purchase",
            points=50,
        )

        balance = manager.get_balance("user_123")
        assert balance.credits == 100
        assert balance.points == 50

    def test_consume_credits_success(self, manager):
        """Test successful credit consumption."""
        manager.create_user("test@example.com", "user_123")
        manager.add_credits("user_123", 100, TransactionType.PURCHASE, "Setup")

        success, remaining = manager.consume_credits(
            user_id="user_123",
            amount=30,
            endpoint="/api/trade",
            description="Trade execution",
        )

        assert success is True
        assert remaining == 70

    def test_consume_credits_insufficient(self, manager):
        """Test consumption with insufficient credits."""
        manager.create_user("test@example.com", "user_123")
        manager.add_credits("user_123", 20, TransactionType.PURCHASE, "Setup")

        success, remaining = manager.consume_credits(
            user_id="user_123",
            amount=30,
            endpoint="/api/trade",
            description="Trade execution",
        )

        assert success is False
        assert remaining == 20  # Unchanged

    def test_get_transactions(self, manager):
        """Test transaction history retrieval."""
        manager.create_user("test@example.com", "user_123")
        manager.add_credits("user_123", 100, TransactionType.PURCHASE, "Purchase 1")
        manager.add_credits("user_123", 50, TransactionType.BONUS, "Bonus")
        manager.consume_credits("user_123", 25, "/api/test", "Usage")

        transactions = manager.get_transactions("user_123", limit=10)

        assert len(transactions) == 3

    def test_tier_upgrade_on_points(self, manager):
        """Test automatic tier upgrade when points threshold reached."""
        manager.create_user("test@example.com", "user_123")

        # Add enough points for STARTER tier (1000+)
        manager.add_credits(
            "user_123", 100, TransactionType.PURCHASE, "Purchase",
            points=1500
        )

        balance = manager.get_balance("user_123")
        assert balance.tier == UserTier.STARTER


class TestCreditMeteringMiddleware:
    """Tests for CreditMeteringMiddleware."""

    @pytest.fixture
    def middleware(self, tmp_path):
        """Create middleware with temp database."""
        db_path = str(tmp_path / "test_credits.db")
        manager = CreditManager(db_path=db_path)
        return CreditMeteringMiddleware(credit_manager=manager)

    @pytest.mark.asyncio
    async def test_check_and_deduct_success(self, middleware):
        """Test successful credit check and deduction."""
        # Setup user with credits
        middleware.credit_manager.create_user("test@example.com", "user_123")
        middleware.credit_manager.add_credits(
            "user_123", 100, TransactionType.PURCHASE, "Setup"
        )

        result = await middleware.check_and_deduct(
            user_id="user_123",
            endpoint="/api/trade",
            cost=5,
        )

        assert result.allowed is True
        assert result.remaining == 95

    @pytest.mark.asyncio
    async def test_check_and_deduct_insufficient(self, middleware):
        """Test rejection when insufficient credits."""
        middleware.credit_manager.create_user("test@example.com", "user_123")
        middleware.credit_manager.add_credits(
            "user_123", 3, TransactionType.PURCHASE, "Setup"
        )

        result = await middleware.check_and_deduct(
            user_id="user_123",
            endpoint="/api/trade",
            cost=5,
        )

        assert result.allowed is False
        assert result.remaining == 3

    @pytest.mark.asyncio
    async def test_check_and_deduct_unknown_user(self, middleware):
        """Test rejection for unknown user."""
        result = await middleware.check_and_deduct(
            user_id="unknown_user",
            endpoint="/api/trade",
            cost=5,
        )

        assert result.allowed is False

    def test_get_endpoint_cost_default(self, middleware):
        """Test default endpoint cost."""
        cost = middleware.get_endpoint_cost("/api/unknown")

        assert cost == 1  # Default cost

    def test_get_endpoint_cost_custom(self, middleware):
        """Test custom endpoint cost."""
        middleware.endpoint_costs["/api/expensive"] = 10

        cost = middleware.get_endpoint_cost("/api/expensive")

        assert cost == 10


class TestMeteringResult:
    """Tests for MeteringResult dataclass."""

    def test_metering_result_creation(self):
        """Test MeteringResult creation."""
        result = MeteringResult(
            allowed=True,
            remaining=95,
            cost=5,
            user_id="user_123",
        )

        assert result.allowed is True
        assert result.remaining == 95
        assert result.cost == 5

    def test_metering_result_with_error(self):
        """Test MeteringResult with error."""
        result = MeteringResult(
            allowed=False,
            remaining=0,
            cost=5,
            user_id="user_123",
            error="Insufficient credits",
        )

        assert result.allowed is False
        assert result.error == "Insufficient credits"


class TestStripeIntegration:
    """Tests for Stripe integration (mocked)."""

    @pytest.mark.asyncio
    async def test_create_checkout_session(self):
        """Test checkout session creation."""
        with patch('stripe.checkout.Session.create') as mock_create:
            mock_create.return_value = MagicMock(
                id="cs_test_123",
                url="https://checkout.stripe.com/test",
            )

            from core.credits.stripe_integration import create_checkout_session

            session = await create_checkout_session(
                user_id="user_123",
                package_id="pro_100",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            assert session is not None

    @pytest.mark.asyncio
    async def test_handle_webhook_checkout_complete(self):
        """Test webhook handling for completed checkout."""
        # This would test the webhook handling
        pass


class TestIntegration:
    """Integration tests for credit system."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Setup integration test environment."""
        db_path = str(tmp_path / "test_credits.db")
        manager = CreditManager(db_path=db_path)
        middleware = CreditMeteringMiddleware(credit_manager=manager)

        # Create test user
        manager.create_user("test@example.com", "test_user")

        return {"manager": manager, "middleware": middleware}

    @pytest.mark.asyncio
    async def test_full_purchase_and_use_flow(self, setup):
        """Test complete flow: purchase -> use credits."""
        manager = setup["manager"]
        middleware = setup["middleware"]

        # Purchase credits
        manager.add_credits(
            user_id="test_user",
            amount=100,
            transaction_type=TransactionType.PURCHASE,
            description="Pro package purchase",
            points=100,
        )

        # Use some credits
        for i in range(5):
            result = await middleware.check_and_deduct(
                user_id="test_user",
                endpoint="/api/trade",
                cost=5,
            )
            assert result.allowed is True

        # Check final balance
        balance = manager.get_balance("test_user")
        assert balance.credits == 75  # 100 - (5 * 5)
        assert balance.points == 100

    @pytest.mark.asyncio
    async def test_credit_exhaustion(self, setup):
        """Test behavior when credits are exhausted."""
        manager = setup["manager"]
        middleware = setup["middleware"]

        # Small amount of credits
        manager.add_credits(
            user_id="test_user",
            amount=10,
            transaction_type=TransactionType.PURCHASE,
            description="Small purchase",
        )

        # Use all credits
        for i in range(2):
            result = await middleware.check_and_deduct(
                user_id="test_user",
                endpoint="/api/trade",
                cost=5,
            )
            assert result.allowed is True

        # Next request should fail
        result = await middleware.check_and_deduct(
            user_id="test_user",
            endpoint="/api/trade",
            cost=5,
        )
        assert result.allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
