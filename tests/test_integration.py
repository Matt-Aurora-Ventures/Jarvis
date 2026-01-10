"""
Integration Tests.

Tests that verify the integration between different modules:
- Bags.fm -> Treasury flow
- Credits -> API metering flow
- Staking -> Rewards distribution flow
- Consent -> Data collection flow
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = tmpdir
        yield tmpdir
        if old_data_dir:
            os.environ["DATA_DIR"] = old_data_dir
        else:
            os.environ.pop("DATA_DIR", None)


@pytest.fixture
def mock_solana_client():
    """Mock Solana RPC client."""
    client = MagicMock()
    client.get_balance = AsyncMock(return_value={"result": {"value": 10_000_000_000}})
    client.send_transaction = AsyncMock(return_value={"result": "mock_signature"})
    return client


# =============================================================================
# Bags.fm -> Treasury Integration
# =============================================================================


class TestBagsTreasuryIntegration:
    """Test integration between Bags.fm fee collection and Treasury."""

    @pytest.mark.asyncio
    async def test_fee_collection_flows_to_treasury(self, temp_data_dir):
        """Test that collected fees are properly distributed to treasury."""
        from core.treasury.bags_integration import TreasuryBagsIntegration, FeeAllocation

        # Create mock fee collector
        mock_fee_collector = MagicMock()
        mock_fee_collector.check_pending_fees = AsyncMock(
            return_value={"mint_abc123": 1.5}  # 1.5 SOL in fees
        )
        mock_fee_collector.collect_and_distribute = AsyncMock(
            return_value={
                "claimed": 1.5,
                "signatures": ["sig_mock_123"],
            }
        )

        # Create mock treasury
        mock_treasury = MagicMock()

        # Create integration with 50/30/20 split
        allocation = FeeAllocation(
            staking_rewards_pct=0.50,
            operations_pct=0.30,
            development_pct=0.20,
        )

        integration = TreasuryBagsIntegration(
            bags_fee_collector=mock_fee_collector,
            treasury_manager=mock_treasury,
            allocation=allocation,
        )

        # Execute collection
        record = await integration.collect_and_distribute()

        # Verify distribution
        assert record is not None
        assert record.total_fees_sol == 1.5
        assert record.to_staking_sol == pytest.approx(0.75, rel=0.01)  # 50%
        assert record.to_operations_sol == pytest.approx(0.45, rel=0.01)  # 30%
        assert record.to_development_sol == pytest.approx(0.30, rel=0.01)  # 20%

        # Verify stats updated
        stats = integration.get_stats()
        assert stats["total_collected_sol"] == 1.5
        assert stats["collection_count"] == 1

    @pytest.mark.asyncio
    async def test_no_fees_returns_none(self, temp_data_dir):
        """Test that no pending fees returns None."""
        from core.treasury.bags_integration import TreasuryBagsIntegration

        mock_fee_collector = MagicMock()
        mock_fee_collector.check_pending_fees = AsyncMock(return_value={})

        integration = TreasuryBagsIntegration(
            bags_fee_collector=mock_fee_collector,
            treasury_manager=MagicMock(),
        )

        record = await integration.collect_and_distribute()
        assert record is None

    def test_revenue_estimation(self, temp_data_dir):
        """Test revenue estimation from projected volume."""
        from core.treasury.bags_integration import TreasuryBagsIntegration

        integration = TreasuryBagsIntegration()

        # 1,000,000 SOL monthly volume
        estimate = integration.estimate_staking_rewards_funding(1_000_000)

        # Partner fee = 0.25% of volume = 2,500 SOL
        assert estimate["estimated_monthly_fees_sol"] == pytest.approx(2500, rel=0.01)

        # 50% to staking = 1,250 SOL
        assert estimate["to_staking_rewards_sol"] == pytest.approx(1250, rel=0.01)


# =============================================================================
# Credits -> API Metering Integration
# =============================================================================


class TestCreditsApiIntegration:
    """Test integration between credit system and API metering."""

    def test_credit_consumption_tracking(self, temp_data_dir):
        """Test that API calls consume credits correctly."""
        from api.routes.credits import CreditsService

        service = CreditsService()

        # Create user and add credits
        service.add_credits(
            user_id="test_user",
            credits=100,
            bonus=10,
            points=50,
            tx_type="purchase",
            description="Initial purchase",
        )

        # Check balance
        balance = service.get_balance("test_user")
        assert balance.credits == 110
        assert balance.points == 50

        # Get transaction history
        history = service.get_transactions("test_user")
        assert len(history.transactions) == 1
        assert history.stats["totalPurchased"] == 110

    @pytest.mark.asyncio
    async def test_checkout_creates_session(self, temp_data_dir):
        """Test Stripe checkout session creation."""
        from api.routes.credits import CreditsService

        service = CreditsService()

        response = await service.create_checkout_session(
            user_id="test_user",
            package_id="pro_100",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert response.checkout_url.startswith("https://checkout.stripe.com")
        assert response.session_id.startswith("cs_mock_")

    def test_points_redemption(self, temp_data_dir):
        """Test redeeming points for rewards."""
        from api.routes.credits import CreditsService

        service = CreditsService()

        # Add credits and points
        service.add_credits(
            user_id="test_user",
            credits=100,
            bonus=0,
            points=1000,
            tx_type="purchase",
            description="Test",
        )

        # Redeem for 100 credits (costs 500 points)
        result = service.redeem_reward("test_user", "credits_100")

        assert result.success is True
        assert result.points_spent == 500
        assert result.remaining_points == 500

        # Check balance updated
        balance = service.get_balance("test_user")
        assert balance.credits == 200  # 100 + 100
        assert balance.points == 500


# =============================================================================
# Staking -> Rewards Integration
# =============================================================================


class TestStakingRewardsIntegration:
    """Test integration between staking and rewards distribution."""

    def test_multiplier_progression(self, temp_data_dir):
        """Test time-weighted multiplier progression."""
        from api.routes.staking import StakingService
        from datetime import datetime, timezone, timedelta

        service = StakingService()

        # Create stake at different times
        user = "test_wallet"
        service._user_stakes[user] = {
            "amount": 1_000_000_000,  # 1 SOL worth
            "stake_start": datetime.now(timezone.utc) - timedelta(days=0),
        }

        stake = service.get_user_stake(user)
        assert stake.multiplier == 1.0  # Day 0

        # After 7 days
        service._user_stakes[user]["stake_start"] = datetime.now(timezone.utc) - timedelta(days=7)
        stake = service.get_user_stake(user)
        assert stake.multiplier == 1.5

        # After 30 days
        service._user_stakes[user]["stake_start"] = datetime.now(timezone.utc) - timedelta(days=30)
        stake = service.get_user_stake(user)
        assert stake.multiplier == 2.0

        # After 90 days
        service._user_stakes[user]["stake_start"] = datetime.now(timezone.utc) - timedelta(days=90)
        stake = service.get_user_stake(user)
        assert stake.multiplier == 2.5

    def test_pool_apy_calculation(self, temp_data_dir):
        """Test APY calculation based on pool state."""
        from api.routes.staking import StakingService

        service = StakingService()

        # Empty pool
        stats = service.get_pool_stats()
        assert stats.apy == 0.15  # Default 15%

        # Add stakers
        service._pool_stats["total_staked"] = 1000 * 10**9
        service._pool_stats["staker_count"] = 100

        stats = service.get_pool_stats()
        assert stats.totalStaked == 1000 * 10**9
        assert stats.stakerCount == 100


# =============================================================================
# Consent -> Data Collection Integration
# =============================================================================


class TestConsentDataIntegration:
    """Test integration between consent and data collection."""

    def test_consent_gates_data_collection(self, temp_data_dir):
        """Test that data collection respects consent."""
        from core.data_consent.manager import ConsentManager
        from core.data_consent.models import ConsentTier, DataCategory

        manager = ConsentManager(db_path=f"{temp_data_dir}/consent.db")

        user_id = "test_user"

        # No consent - should deny
        assert manager.check_consent(user_id) is False
        assert manager.check_consent(user_id, DataCategory.ANALYTICS) is False

        # TIER_0 - still deny non-essential
        manager.record_consent(user_id, ConsentTier.TIER_0)
        assert manager.check_consent(user_id) is False

        # TIER_1 - allow analytics
        manager.record_consent(user_id, ConsentTier.TIER_1)
        assert manager.check_consent(user_id) is True
        assert manager.check_consent(user_id, DataCategory.ANALYTICS) is True
        assert manager.check_consent(user_id, DataCategory.MARKETING) is False

        # TIER_2 - allow all (with specific categories)
        manager.record_consent(
            user_id,
            ConsentTier.TIER_2,
            categories=[DataCategory.ANALYTICS, DataCategory.MARKETING],
        )
        assert manager.check_consent(user_id, DataCategory.MARKETING) is True

    def test_deletion_request_workflow(self, temp_data_dir):
        """Test complete deletion request workflow."""
        from core.data_consent.manager import ConsentManager
        from core.data_consent.models import ConsentTier, DataCategory

        manager = ConsentManager(db_path=f"{temp_data_dir}/consent.db")

        user_id = "test_user"

        # Record consent
        manager.record_consent(user_id, ConsentTier.TIER_2)

        # Request deletion
        deletion_req = manager.request_deletion(
            user_id,
            categories=[DataCategory.ANALYTICS],
        )
        assert deletion_req.status == "pending"

        # Verify pending deletion exists
        pending = manager.get_pending_deletions()
        assert len(pending) == 1

        # Complete deletion
        manager.complete_deletion(deletion_req.id, success=True)

        # Verify completed
        completed = manager.get_deletion_request(deletion_req.id)
        assert completed.status == "completed"

        # No more pending
        pending = manager.get_pending_deletions()
        assert len(pending) == 0

    def test_consent_history_tracking(self, temp_data_dir):
        """Test that consent changes are tracked in history."""
        from core.data_consent.manager import ConsentManager
        from core.data_consent.models import ConsentTier

        manager = ConsentManager(db_path=f"{temp_data_dir}/consent.db")

        user_id = "test_user"

        # Record initial consent
        manager.record_consent(user_id, ConsentTier.TIER_1)

        # Update consent
        manager.record_consent(user_id, ConsentTier.TIER_2)

        # Revoke consent
        manager.revoke_consent(user_id)

        # Check history
        history = manager.get_consent_history(user_id)
        assert len(history) == 3

        # Most recent first
        assert history[0]["action"] == "consent_revoked"
        assert history[1]["action"] == "consent_updated"
        assert history[2]["action"] == "consent_given"


# =============================================================================
# End-to-End Integration
# =============================================================================


class TestEndToEndFlow:
    """Test complete end-to-end flows."""

    @pytest.mark.asyncio
    async def test_new_user_journey(self, temp_data_dir):
        """Test complete new user journey through the system."""
        from core.data_consent.manager import ConsentManager
        from core.data_consent.models import ConsentTier, DataCategory
        from api.routes.credits import CreditsService

        # 1. User provides consent
        consent_manager = ConsentManager(db_path=f"{temp_data_dir}/consent.db")
        user_id = "new_user_123"

        consent_manager.record_consent(
            user_id,
            ConsentTier.TIER_1,
            ip_address="192.168.1.1",
        )

        assert consent_manager.check_consent(user_id) is True

        # 2. User purchases credits
        credits_service = CreditsService()
        credits_service.add_credits(
            user_id=user_id,
            credits=500,
            bonus=50,
            points=100,
            tx_type="purchase",
            description="Pro package purchase",
        )

        balance = credits_service.get_balance(user_id)
        assert balance.credits == 550
        assert balance.tier == "pro"

        # 3. User makes API calls (consume credits)
        # Simulated by adding consumption transaction
        credits_service._users[user_id]["credits"] -= 100
        if user_id not in credits_service._transactions:
            credits_service._transactions[user_id] = []
        import uuid
        credits_service._transactions[user_id].append({
            "id": f"tx_{uuid.uuid4().hex[:12]}",
            "type": "consumption",
            "amount": -100,
            "description": "API usage",
            "created_at": datetime.now(timezone.utc),
            "balance_after": credits_service._users[user_id]["credits"],
        })

        balance = credits_service.get_balance(user_id)
        assert balance.credits == 450

        # 4. User redeems points
        result = credits_service.redeem_reward(user_id, "credits_100")
        assert result.success is True

        balance = credits_service.get_balance(user_id)
        assert balance.credits == 550  # 450 + 100

        # 5. User exports their data
        exported = consent_manager.export_user_data(user_id)
        assert exported["user_id"] == user_id
        assert exported["consent"] is not None

    @pytest.mark.asyncio
    async def test_trading_revenue_distribution(self, temp_data_dir):
        """Test complete trading revenue distribution flow."""
        from core.treasury.bags_integration import TreasuryBagsIntegration, FeeAllocation

        # Create integration
        mock_fee_collector = MagicMock()
        mock_treasury = MagicMock()

        integration = TreasuryBagsIntegration(
            bags_fee_collector=mock_fee_collector,
            treasury_manager=mock_treasury,
        )

        # Simulate multiple collection cycles
        fees_collected = [0.5, 1.2, 0.8, 2.0]

        for fee in fees_collected:
            mock_fee_collector.check_pending_fees = AsyncMock(
                return_value={"mint": fee}
            )
            mock_fee_collector.collect_and_distribute = AsyncMock(
                return_value={"claimed": fee, "signatures": ["sig"]}
            )

            await integration.collect_and_distribute()

        # Check cumulative stats
        stats = integration.get_stats()
        assert stats["total_collected_sol"] == pytest.approx(sum(fees_collected), rel=0.01)
        assert stats["collection_count"] == len(fees_collected)

        # Check revenue summary
        summary = integration.get_revenue_summary(period_days=30)
        assert summary["total_collected_sol"] == pytest.approx(sum(fees_collected), rel=0.01)


# =============================================================================
# API Integration Tests
# =============================================================================


class TestAPIIntegration:
    """Test FastAPI endpoint integration."""

    @pytest.fixture
    def test_client(self, temp_data_dir):
        """Create test client."""
        try:
            from fastapi.testclient import TestClient
            from api.fastapi_app import create_app

            app = create_app()
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI or test dependencies not installed")

    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_staking_endpoints(self, test_client):
        """Test staking API endpoints."""
        # Get pool stats
        response = test_client.get("/api/staking/pool")
        assert response.status_code == 200

        data = response.json()
        assert "totalStaked" in data
        assert "apy" in data

        # Get user stake (non-existent user)
        response = test_client.get("/api/staking/user/test_wallet")
        assert response.status_code == 200

        data = response.json()
        assert data["amount"] == 0

    def test_credits_endpoints(self, test_client):
        """Test credits API endpoints."""
        # Get packages
        response = test_client.get("/api/credits/packages")
        assert response.status_code == 200

        data = response.json()
        assert "packages" in data
        assert len(data["packages"]) > 0

        # Get balance (new user)
        response = test_client.get("/api/credits/balance/test_user")
        assert response.status_code == 200

        data = response.json()
        assert data["credits"] == 0
        assert data["tier"] == "free"

    def test_consent_endpoints(self, test_client):
        """Test consent API endpoints."""
        # Get options
        response = test_client.get("/api/consent/options")
        assert response.status_code == 200

        data = response.json()
        assert "tiers" in data
        assert "categories" in data

        # Get preferences (new user)
        response = test_client.get("/api/consent/preferences/test_user")
        assert response.status_code == 200

        data = response.json()
        assert data["tier"] == "TIER_0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
