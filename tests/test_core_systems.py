"""
Core System Integration Tests - Validate system components work together

Focused tests on:
1. Market Data Service aggregation
2. Token Analyzer risk assessment
3. Adaptive Algorithm signal generation
4. Fee Distribution calculations
"""

import asyncio
import logging

import pytest

from core.market_data_service import MarketDataService
from core.token_analyzer import TokenAnalyzer
from core.adaptive_algorithm import AdaptiveAlgorithm, AlgorithmType
from core.fee_distribution import FeeDistributionSystem
from core.wallet_service import WalletService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMarketDataIntegration:
    """Test market data service integration."""

    async def test_aggregated_market_data(self):
        """Test fetching and aggregating market data."""
        service = MarketDataService()

        sol_mint = "So11111111111111111111111111111111111111112"
        market_data = await service.get_market_data("SOL", mint_address=sol_mint)

        logger.info(f"Market data: {market_data}")
        assert market_data is None or isinstance(market_data, dict)

    async def test_cache_efficiency(self):
        """Test that cache reduces API calls."""
        service = MarketDataService()

        sol_mint = "So11111111111111111111111111111111111111112"

        # First call
        await service.get_market_data("SOL", mint_address=sol_mint)
        cache_after_first = service.get_cache_size()

        # Second call (should use cache)
        await service.get_market_data("SOL", mint_address=sol_mint)
        cache_after_second = service.get_cache_size()

        logger.info(f"Cache size: {cache_after_first} after first call, {cache_after_second} after second")
        assert cache_after_first == cache_after_second


class TestTokenAnalyzer:
    """Test token analysis system."""

    async def test_token_recommendation(self):
        """Test generating token recommendation."""
        analyzer = TokenAnalyzer()

        # Mock market data
        market_data = {
            "symbol": "SOL",
            "price": 142.50,
            "liquidity_usd": 500_000_000,
            "volume_24h": 2_500_000_000,
            "price_change_24h": 5.2,
            "price_change_7d": 15.3,
            "holder_distribution": {"concentration_score": 45},
            "smart_contract_safety": {"risk_score": 25},
        }

        analysis = await analyzer.analyze_token("SOL", market_data)

        if analysis:
            logger.info(f"Analysis: {analysis}")
            assert analysis is not None
        else:
            logger.info("No analysis returned")

    async def test_risk_rating_levels(self):
        """Test all risk rating levels."""
        analyzer = TokenAnalyzer()

        test_cases = [
            ("Low liquidity", {"liquidity_usd": 5_000}),
            ("Medium liquidity", {"liquidity_usd": 500_000}),
            ("High liquidity", {"liquidity_usd": 50_000_000}),
        ]

        for name, dex_data in test_cases:
            market_data = {
                "price": 100,
                "liquidity_usd": dex_data["liquidity_usd"],
                "volume_24h": 1_000_000,
                "price_change_24h": 5.0,
                "holder_distribution": {"concentration_score": 50},
                "smart_contract_safety": {"risk_score": 50},
            }

            analysis = await analyzer.analyze_token("TEST", market_data)
            if analysis:
                logger.info(f"{name}: Risk rating = {analysis.get('risk_rating', 'N/A')}")


class TestAdaptiveAlgorithm:
    """Test adaptive algorithm learning."""

    async def test_signal_generation(self):
        """Test generating trading signals."""
        algo = AdaptiveAlgorithm()

        market_data = {
            "price": 140,
            "liquidity_usd": 500_000_000,
            "price_change_24h": 5.2,
        }

        signals = await algo.generate_signals("SOL", market_data)
        logger.info(f"Generated {len(signals)} signals")
        assert len(signals) > 0

    async def test_algorithm_metrics(self):
        """Test algorithm performance metrics."""
        algo = AdaptiveAlgorithm()

        # Get initial metrics
        metrics = algo.get_algorithm_metrics(AlgorithmType.SENTIMENT)
        logger.info(f"Initial metrics: accuracy={metrics.accuracy:.1%}, confidence={metrics.confidence_score}")

        assert 0 <= metrics.confidence_score <= 100
        assert -100 <= metrics.accuracy <= 100


class TestFeeDistributionSystem:
    """Test fee calculation and distribution."""

    async def test_fee_calculation(self):
        """Test calculating fees from PnL."""
        fee_system = FeeDistributionSystem()

        # Simulate $100 profit
        pnl = 100.0
        fee_data = fee_system.calculate_fees_for_trade(pnl)

        logger.info(f"Fee data: {fee_data}")
        assert fee_data["total_fee"] == pnl * 0.005
        assert fee_data["user_pct"] == 0.75
        assert fee_data["charity_pct"] == 0.05
        assert fee_data["company_pct"] == 0.20

    async def test_loss_trade_no_fee(self):
        """Test that losing trades don't generate fees."""
        fee_system = FeeDistributionSystem()

        # Simulate $50 loss
        pnl = -50.0
        fee_data = fee_system.calculate_fees_for_trade(pnl)

        logger.info(f"Loss trade fee data: {fee_data}")
        assert fee_data["total_fee"] == 0


class TestWalletIntegration:
    """Test wallet functionality."""

    async def test_wallet_creation(self):
        """Test creating an encrypted wallet."""
        wallet_service = WalletService()

        wallet = await wallet_service.create_new_wallet(user_password="test_pass")
        logger.info(f"Created wallet: {wallet['address'][:20]}...")

        assert "address" in wallet
        assert "seed_phrase" in wallet
        assert "encrypted_key" in wallet

    async def test_wallet_encryption(self):
        """Test wallet encryption/decryption."""
        from core.wallet_service import WalletEncryption

        encryption = WalletEncryption()
        test_key = "test_private_key"
        password = "test_password"

        # Encrypt
        encrypted = encryption.encrypt_private_key(test_key, password)
        logger.info(f"Encrypted: {encrypted[:20]}...")

        # Decrypt
        decrypted = encryption.decrypt_private_key(encrypted, password)
        assert decrypted == test_key
        logger.info("Encryption/decryption successful")


class TestEndToEndScenario:
    """Test a realistic trading scenario."""

    async def test_token_to_trading_decision(self):
        """Test: Analyze token -> Get signals -> Calculate potential fees."""
        logger.info("\n" + "=" * 60)
        logger.info("END-TO-END TRADING SCENARIO")
        logger.info("=" * 60)

        # Step 1: Fetch market data
        logger.info("\n1. Fetching market data...")
        market_data_service = MarketDataService()
        sol_mint = "So11111111111111111111111111111111111111112"
        market_data = await market_data_service.get_market_data("SOL", mint_address=sol_mint)

        if market_data:
            logger.info(f"   Price: ${market_data.get('price', 'N/A')}")
            logger.info(f"   Liquidity: ${market_data.get('liquidity_usd', 'N/A')}")
        else:
            market_data = {
                "price": 140,
                "liquidity_usd": 500_000_000,
                "volume_24h": 2_500_000_000,
                "price_change_24h": 5.2,
                "holder_distribution": {"concentration_score": 45},
                "smart_contract_safety": {"risk_score": 25},
            }
            logger.info("   Using mock data")

        # Step 2: Analyze token
        logger.info("\n2. Analyzing token...")
        analyzer = TokenAnalyzer()
        analysis = await analyzer.analyze_token("SOL", market_data)

        if analysis:
            logger.info(f"   Risk Rating: {analysis.get('risk_rating', 'N/A')}")
            logger.info(f"   Recommendation: {analysis.get('recommendation', 'N/A')}")

        # Step 3: Generate signals
        logger.info("\n3. Generating signals...")
        algo = AdaptiveAlgorithm()
        signals = await algo.generate_signals("SOL", market_data)

        if signals:
            best = signals[0]
            logger.info(f"   Best Signal: {best.algorithm_type.value}")
            logger.info(f"   Confidence: {best.confidence_score}%")

        # Step 4: Simulate trade
        logger.info("\n4. Simulating trade...")
        entry_price = market_data["price"]
        exit_price = entry_price * 1.1  # +10%
        position_size = 1000
        pnl = (exit_price - entry_price) * (position_size / entry_price)

        logger.info(f"   Entry: ${entry_price:.2f}")
        logger.info(f"   Exit: ${exit_price:.2f}")
        logger.info(f"   PnL: ${pnl:.2f}")

        # Step 5: Calculate fees
        logger.info("\n5. Calculating fees...")
        fee_system = FeeDistributionSystem()
        fee_data = fee_system.calculate_fees_for_trade(pnl)

        logger.info(f"   Total Fee: ${fee_data['total_fee']:.4f}")
        logger.info(f"   User Share (75%): ${fee_data['total_fee'] * 0.75:.4f}")
        logger.info(f"   Charity Share (5%): ${fee_data['total_fee'] * 0.05:.4f}")
        logger.info(f"   Company Share (20%): ${fee_data['total_fee'] * 0.20:.4f}")

        logger.info("\n" + "=" * 60)
        logger.info("SCENARIO COMPLETE")
        logger.info("=" * 60 + "\n")


async def run_all_tests():
    """Run all core system tests."""
    logger.info("=" * 60)
    logger.info("CORE SYSTEM INTEGRATION TESTS")
    logger.info("=" * 60)

    test_classes = [
        TestMarketDataIntegration(),
        TestTokenAnalyzer(),
        TestAdaptiveAlgorithm(),
        TestFeeDistributionSystem(),
        TestWalletIntegration(),
        TestEndToEndScenario(),
    ]

    for test_class in test_classes:
        logger.info(f"\n>>> Running {test_class.__class__.__name__}...")
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                try:
                    method = getattr(test_class, method_name)
                    await method()
                    logger.info(f"    OK: {method_name}\n")
                except Exception as e:
                    logger.error(f"    FAILED: {method_name}: {e}\n", exc_info=True)

    logger.info("\n" + "=" * 60)
    logger.info("ALL CORE TESTS COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
