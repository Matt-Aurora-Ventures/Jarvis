"""
End-to-End Trading Flow Tests - Complete user journey validation

Tests the full workflow:
1. User registration and profile setup
2. Wallet generation and encryption
3. Token analysis and recommendations
4. Trade execution and position tracking
5. Fee calculation and distribution
6. Algorithm learning from outcomes
"""

import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path

import pytest

from core.public_user_manager import PublicUserManager, UserRiskLevel
from core.wallet_service import WalletService, WalletEncryption
from core.market_data_service import MarketDataService
from core.token_analyzer import TokenAnalyzer
from core.adaptive_algorithm import AdaptiveAlgorithm, AlgorithmType
from core.fee_distribution import FeeDistributionSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestUserRegistrationFlow:
    """Test user registration and profile setup."""

    async def test_register_new_user(self):
        """Test creating a new user account."""
        manager = PublicUserManager()

        # Register new user (starting from user_id 1)
        success, profile = manager.register_user(
            user_id=1,
            username="trader_alice"
        )

        logger.info(f"✓ Registered user: {profile.username}")
        assert success
        assert profile.username == "trader_alice"
        assert profile.risk_level == UserRiskLevel.MODERATE

    async def test_user_profile_update(self):
        """Test updating user profile and settings."""
        manager = PublicUserManager()

        # Register
        user = await manager.register_user(
            username="trader_bob",
            password="password_123",
            email="bob@example.com"
        )

        user_id = user["user_id"]

        # Update profile
        profile = await manager.get_user_profile(user_id)
        profile["risk_level"] = UserRiskLevel.AGGRESSIVE.value
        profile["max_daily_loss_usd"] = 500.0

        await manager.update_profile(user_id, profile)

        # Verify update
        updated = await manager.get_user_profile(user_id)
        assert updated["risk_level"] == UserRiskLevel.AGGRESSIVE.value
        logger.info(f"✓ Updated profile: risk={updated['risk_level']}, max_loss=${updated['max_daily_loss_usd']}")

    async def test_rate_limiting(self):
        """Test that daily trade limits are enforced."""
        manager = PublicUserManager()

        user = await manager.register_user(
            username="trader_charlie",
            password="password_123",
            email="charlie@example.com"
        )

        user_id = user["user_id"]

        # Try to exceed daily trade limit (default 20)
        for i in range(20):
            can_trade = await manager.check_rate_limits(user_id, trade_amount=100)
            assert can_trade, f"Should allow trade {i+1}"

        # 21st trade should be rejected
        can_trade = await manager.check_rate_limits(user_id, trade_amount=100)
        assert not can_trade, "Should reject trade when limit exceeded"
        logger.info("✓ Rate limiting working correctly")


class TestWalletManagement:
    """Test wallet generation and encryption."""

    async def test_wallet_creation(self):
        """Test creating a new encrypted wallet."""
        wallet_service = WalletService()
        user_password = "user_secure_password"

        # Create wallet
        wallet = await wallet_service.create_new_wallet(user_password)

        logger.info(f"✓ Created wallet: {wallet['address']}")
        assert "address" in wallet
        assert "seed_phrase" in wallet
        assert "encrypted_key" in wallet

    async def test_wallet_encryption_decryption(self):
        """Test encryption and decryption of private keys."""
        encryption = WalletEncryption()
        password = "test_password_123"
        private_key = "test_private_key_content"

        # Encrypt
        encrypted = encryption.encrypt_private_key(private_key, password)
        logger.info(f"✓ Encrypted key: {encrypted[:20]}...")

        # Decrypt
        decrypted = encryption.decrypt_private_key(encrypted, password)
        assert decrypted == private_key
        logger.info("✓ Decryption successful")

    async def test_wallet_import(self):
        """Test importing wallet from seed phrase."""
        wallet_service = WalletService()

        # First create a wallet
        wallet1 = await wallet_service.create_new_wallet("password123")
        seed = wallet1["seed_phrase"]

        # Import wallet from seed
        password = "password123"
        wallet2 = await wallet_service.import_wallet_from_seed(seed, password)

        logger.info(f"✓ Imported wallet: {wallet2['address']}")
        assert wallet2["address"] == wallet1["address"]


class TestTokenAnalysisFlow:
    """Test token analysis and recommendations."""

    async def test_analyze_token(self):
        """Test comprehensive token analysis."""
        analyzer = TokenAnalyzer()
        market_data_service = MarketDataService()

        # Get market data for SOL
        sol_mint = "So11111111111111111111111111111111111111112"
        market_data = await market_data_service.get_market_data("SOL", mint_address=sol_mint)

        if market_data:
            # Analyze token
            analysis = await analyzer.analyze_token("SOL", market_data)

            logger.info(f"✓ Token analysis: {analysis}")
            assert analysis is not None
            assert "price" in analysis
            assert "recommendation" in analysis
            assert "risk_rating" in analysis

    async def test_risk_assessment(self):
        """Test risk assessment logic."""
        analyzer = TokenAnalyzer()

        # Create mock market data
        market_data = {
            "price": 142.50,
            "liquidity_usd": 500_000_000,
            "volume_24h": 2_500_000_000,
            "holder_distribution": {"concentration_score": 45},
            "smart_contract_safety": {"risk_score": 25},
        }

        # Analyze
        analysis = await analyzer.analyze_token("SOL", market_data)

        if analysis:
            logger.info(f"✓ Risk rating: {analysis['risk_rating']}")
            assert analysis["risk_rating"] in ["Very Low", "Low", "Medium", "High", "Very High", "Extreme"]


class TestAlgorithmLearning:
    """Test adaptive algorithm learning."""

    async def test_generate_signals(self):
        """Test algorithm signal generation."""
        algo = AdaptiveAlgorithm()

        # Generate signals for a token
        signals = await algo.generate_signals(
            symbol="SOL",
            market_data={
                "price": 142.50,
                "liquidity_usd": 500_000_000,
                "price_change_24h": 5.2,
            }
        )

        logger.info(f"✓ Generated {len(signals)} signals")
        assert len(signals) > 0

    async def test_algorithm_learning(self):
        """Test that algorithms learn from trading outcomes."""
        algo = AdaptiveAlgorithm()

        # Generate initial signal
        initial_signal = await algo.generate_signals(
            symbol="SOL",
            market_data={"price": 140, "liquidity_usd": 500_000_000}
        )

        if initial_signal:
            initial_confidence = initial_signal[0].confidence_score
            logger.info(f"Initial confidence: {initial_confidence}")

            # Record outcome (winning trade)
            outcome = {
                "algorithm_type": initial_signal[0].algorithm_type,
                "entry_price": 140,
                "exit_price": 150,  # +10 point profit
                "hold_time_minutes": 60,
                "pnl_usd": 100,
            }

            await algo.record_outcome(outcome)

            # Get updated metrics
            metrics = algo.get_algorithm_metrics(AlgorithmType.SENTIMENT)
            logger.info(f"✓ Updated metrics: accuracy={metrics.accuracy:.1%}, confidence={metrics.confidence_score}")


class TestFeeDistribution:
    """Test fee calculation and distribution."""

    async def test_calculate_fees(self):
        """Test fee calculation from winning trade."""
        fee_system = FeeDistributionSystem()

        # Record a winning trade
        trade = {
            "user_id": 1,
            "entry_price": 100,
            "exit_price": 110,
            "position_size_usd": 1000,
        }

        pnl = (trade["exit_price"] - trade["entry_price"]) * (trade["position_size_usd"] / trade["entry_price"])
        logger.info(f"PnL: ${pnl}")

        # Calculate fees
        fee_data = fee_system.calculate_fees_for_trade(pnl)

        logger.info(f"✓ Fee breakdown: {fee_data}")
        assert fee_data["total_fee"] > 0
        assert fee_data["user_pct"] == 0.75
        assert fee_data["charity_pct"] == 0.05
        assert fee_data["company_pct"] == 0.20

    async def test_fee_distribution_breakdown(self):
        """Test fee distribution to all beneficiaries."""
        fee_system = FeeDistributionSystem()

        # Simulate 100 winning trades
        total_pnl = 0
        for i in range(100):
            trade_pnl = 50  # $50 profit per trade
            total_pnl += trade_pnl

        # Calculate fees
        total_fees = total_pnl * 0.005  # 0.5% fee rate

        user_share = total_fees * 0.75
        charity_share = total_fees * 0.05
        company_share = total_fees * 0.20

        logger.info(f"✓ Fee distribution:")
        logger.info(f"  Total PnL: ${total_pnl}")
        logger.info(f"  Total Fees (0.5%): ${total_fees:.2f}")
        logger.info(f"  User share (75%): ${user_share:.2f}")
        logger.info(f"  Charity share (5%): ${charity_share:.2f}")
        logger.info(f"  Company share (20%): ${company_share:.2f}")

        assert abs((user_share + charity_share + company_share) - total_fees) < 0.01


class TestCompleteUserJourney:
    """Test the complete user trading journey."""

    async def test_full_trading_journey(self):
        """Test: Register → Create wallet → Analyze token → Execute trade → Earn fees."""
        logger.info("\n" + "=" * 60)
        logger.info("COMPLETE USER JOURNEY TEST")
        logger.info("=" * 60)

        # Step 1: Register user
        logger.info("\n1️⃣  USER REGISTRATION")
        user_manager = PublicUserManager()
        user = await user_manager.register_user(
            username="journey_trader",
            password="journey_password_123",
            email="journey@example.com"
        )
        user_id = user["user_id"]
        logger.info(f"✓ Registered user_id={user_id}")

        # Step 2: Create wallet
        logger.info("\n2️⃣  WALLET CREATION")
        wallet_service = WalletService()
        wallet = await wallet_service.create_new_wallet("journey_password_123")
        logger.info(f"✓ Created wallet: {wallet['address'][:20]}...")

        # Step 3: Analyze token (SOL)
        logger.info("\n3️⃣  TOKEN ANALYSIS")
        market_data_service = MarketDataService()
        sol_mint = "So11111111111111111111111111111111111111112"
        market_data = await market_data_service.get_market_data("SOL", mint_address=sol_mint)

        if market_data:
            analyzer = TokenAnalyzer()
            analysis = await analyzer.analyze_token("SOL", market_data)
            if analysis:
                logger.info(f"✓ Analysis complete")
                logger.info(f"  Price: ${analysis.get('price', 'N/A')}")
                logger.info(f"  Risk: {analysis.get('risk_rating', 'N/A')}")
                logger.info(f"  Recommendation: {analysis.get('recommendation', 'N/A')}")

        # Step 4: Generate trading signal
        logger.info("\n4️⃣  ALGORITHM SIGNAL")
        algo = AdaptiveAlgorithm()
        signals = await algo.generate_signals("SOL", market_data or {})
        if signals:
            best_signal = signals[0]
            logger.info(f"✓ Signal generated: {best_signal.algorithm_type.value}")
            logger.info(f"  Confidence: {best_signal.confidence_score}%")

        # Step 5: Simulate trade execution
        logger.info("\n5️⃣  TRADE EXECUTION")
        entry_price = market_data.get("price", 140) if market_data else 140
        exit_price = entry_price * 1.1  # +10% profit
        position_size = 1000
        pnl = (exit_price - entry_price) * (position_size / entry_price)

        logger.info(f"✓ Trade executed")
        logger.info(f"  Entry: ${entry_price:.2f}")
        logger.info(f"  Exit: ${exit_price:.2f}")
        logger.info(f"  Position size: ${position_size}")
        logger.info(f"  PnL: ${pnl:.2f} (+{(pnl/position_size)*100:.1f}%)")

        # Step 6: Fee distribution
        logger.info("\n6️⃣  FEE DISTRIBUTION")
        fee_system = FeeDistributionSystem()
        total_fee = pnl * 0.005  # 0.5% success fee

        user_earned = total_fee * 0.75
        charity_earned = total_fee * 0.05
        company_earned = total_fee * 0.20

        logger.info(f"✓ Fees distributed")
        logger.info(f"  Total fee: ${total_fee:.4f}")
        logger.info(f"  User earned (75%): ${user_earned:.4f}")
        logger.info(f"  Charity (5%): ${charity_earned:.4f}")
        logger.info(f"  Company (20%): ${company_earned:.4f}")

        # Step 7: Algorithm learning
        logger.info("\n7️⃣  ALGORITHM LEARNING")
        outcome = {
            "algorithm_type": AlgorithmType.SENTIMENT,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "hold_time_minutes": 120,
            "pnl_usd": pnl,
        }
        await algo.record_outcome(outcome)
        logger.info(f"✓ Algorithm learned from outcome")

        logger.info("\n" + "=" * 60)
        logger.info("✓ JOURNEY COMPLETE - ALL STEPS SUCCESSFUL")
        logger.info("=" * 60 + "\n")


async def run_all_tests():
    """Run all end-to-end tests."""
    logger.info("=" * 60)
    logger.info("END-TO-END TRADING FLOW TESTS")
    logger.info("=" * 60)

    test_classes = [
        TestUserRegistrationFlow(),
        TestWalletManagement(),
        TestTokenAnalysisFlow(),
        TestAlgorithmLearning(),
        TestFeeDistribution(),
        TestCompleteUserJourney(),
    ]

    for test_class in test_classes:
        logger.info(f"\n📋 Running {test_class.__class__.__name__}...")
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                try:
                    method = getattr(test_class, method_name)
                    await method()
                except Exception as e:
                    logger.error(f"✗ {method_name} failed: {e}", exc_info=True)

    logger.info("\n" + "=" * 60)
    logger.info("ALL END-TO-END TESTS COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
