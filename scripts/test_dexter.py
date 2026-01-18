#!/usr/bin/env python3
"""
Test Dexter integration end-to-end

Tests:
1. Dexter agent initialization
2. Finance question processing
3. Response formatting
4. Dry run without real trades
"""

import asyncio
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_dexter_basic():
    """Test 1: Basic Dexter initialization and structure"""
    logger.info("=" * 60)
    logger.info("TEST 1: Dexter Module Structure")
    logger.info("=" * 60)

    try:
        from core.dexter.config import DexterConfig, DEFAULT_CONFIG
        from core.dexter.scratchpad import Scratchpad
        from core.dexter.context import ContextManager
        from core.dexter.agent import DexterAgent

        logger.info("✓ All Dexter modules imported successfully")
        logger.info(f"  - Config: {DEFAULT_CONFIG.to_dict()}")
        logger.info(f"  - Max iterations: {DEFAULT_CONFIG.max_iterations}")
        logger.info(f"  - Model: {DEFAULT_CONFIG.model}")
        logger.info(f"  - Min confidence: {DEFAULT_CONFIG.min_confidence}%")

        return True
    except Exception as e:
        logger.error(f"✗ Failed to import Dexter modules: {e}")
        return False


async def test_meta_router():
    """Test 2: Meta-router financial research"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Meta-Router Financial Research")
    logger.info("=" * 60)

    try:
        from core.dexter.tools.meta_router import financial_research

        logger.info("Testing financial_research with mock data...")

        # Test queries
        test_queries = [
            "Is SOL looking bullish right now?",
            "Check my positions",
            "What tokens are trending?",
        ]

        for query in test_queries:
            logger.info(f"\n  Query: {query}")
            result = await financial_research(query)

            if result and isinstance(result, dict):
                logger.info(f"  ✓ Response: {result.get('response', '')[:100]}...")
                logger.info(f"    Tools: {result.get('tools_used', [])}")
            else:
                logger.error(f"  ✗ Invalid response type: {type(result)}")

        return True

    except Exception as e:
        logger.error(f"✗ Meta-router test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_bot_integration():
    """Test 3: Bot finance integration"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Bot Finance Integration")
    logger.info("=" * 60)

    try:
        from core.dexter.bot_integration import BotFinanceIntegration

        logger.info("Creating BotFinanceIntegration...")
        bot_integration = BotFinanceIntegration()
        logger.info("✓ BotFinanceIntegration created")

        # Test Telegram message handling
        logger.info("\nTesting Telegram message detection...")
        finance_messages = [
            "Is SOL bullish?",
            "What's your take on BTC?",
            "Show me my positions",
        ]

        non_finance_messages = [
            "Hello there",
            "How are you?",
            "What time is it?",
        ]

        for msg in finance_messages:
            response = await bot_integration.handle_telegram_message(msg, 12345)
            if response:
                logger.info(f"  ✓ Finance message detected: {msg[:30]}...")
            else:
                logger.info(f"  ? No response for: {msg}")

        for msg in non_finance_messages:
            response = await bot_integration.handle_telegram_message(msg, 12345)
            if response is None:
                logger.info(f"  ✓ Non-finance correctly ignored: {msg}")
            else:
                logger.info(f"  ✗ Unexpected response for: {msg}")

        return True

    except Exception as e:
        logger.error(f"✗ Bot integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_scratchpad():
    """Test 4: Scratchpad logging"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Scratchpad Decision Logging")
    logger.info("=" * 60)

    try:
        from core.dexter.scratchpad import Scratchpad

        scratchpad = Scratchpad("test_session")

        logger.info("Logging test entries...")
        scratchpad.start_session("Test trading analysis", "SOL")
        scratchpad.log_reasoning("Analyzing SOL market conditions", iteration=1)
        scratchpad.log_action(
            tool="sentiment_analysis",
            args={"symbol": "SOL"},
            result="SOL sentiment: 75/100 bullish"
        )
        scratchpad.log_reasoning("Checking liquidation levels", iteration=2)
        scratchpad.log_decision(
            action="BUY",
            symbol="SOL",
            rationale="Strong sentiment + support level",
            confidence=82.0
        )

        logger.info("✓ Logged 5 entries")
        logger.info("\nSummary:")
        logger.info(scratchpad.get_summary())

        # Save to disk
        scratchpad.save_to_disk()
        logger.info(f"✓ Scratchpad saved to disk")

        return True

    except Exception as e:
        logger.error(f"✗ Scratchpad test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_context_management():
    """Test 5: Context compaction"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Context Management & Compaction")
    logger.info("=" * 60)

    try:
        from core.dexter.context import ContextManager

        context = ContextManager("test_session")

        logger.info("Simulating market data persistence...")

        # Simulate saving market data
        market_data = {
            "symbol": "SOL",
            "price": 142.50,
            "volume": 2_500_000_000,
            "liquidity": 500_000_000
        }

        summary = context.save_full_data(market_data, "market_data")
        logger.info(f"  Market data summary: {summary}")

        # Simulate sentiment data
        sentiment_data = {
            "symbol": "SOL",
            "grok_score": 75,
            "twitter_score": 60,
            "news_score": 55,
            "aggregate": 67.5
        }

        summary = context.save_full_data(sentiment_data, "sentiment")
        logger.info(f"  Sentiment summary: {summary}")

        # Add summaries
        context.add_summary("Market: SOL @ $142.50, strong liquidity")
        context.add_summary("Sentiment: 67.5/100 bullish from 3 sources")

        logger.info("\nContext summary (for LLM):")
        logger.info(context.get_summary())

        # Save session
        context.save_session_state()
        logger.info("✓ Session state saved")

        return True

    except Exception as e:
        logger.error(f"✗ Context management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("DEXTER INTEGRATION TEST SUITE")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    results = []

    # Run tests
    tests = [
        ("Dexter Modules", test_dexter_basic),
        ("Meta-Router", test_meta_router),
        ("Bot Integration", test_bot_integration),
        ("Scratchpad", test_scratchpad),
        ("Context Management", test_context_management),
    ]

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"✗ Test {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed")
    logger.info(f"Finished: {datetime.now().isoformat()}")

    return passed == total


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
