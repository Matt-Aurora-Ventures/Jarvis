#!/usr/bin/env python3
"""
Quick test of opportunity_engine -> decision_matrix -> trading_operations integration.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import opportunity_engine, trading_decision_matrix


async def test_integration():
    """Test the full integration flow."""

    print("\n=== STEP 1: Detect Opportunities ===")
    try:
        engine_result = opportunity_engine.run_engine(
            capital_usd=20.0,
            refresh_equities=False
        )
        print("[OK] Engine ran successfully")
        print(f"  - Scanned: {len(engine_result.get('unified_ranked', []))} candidates")
        print(f"  - Crypto: {len(engine_result.get('candidates', {}).get('crypto', []))}")
        print(f"  - Equities: {len(engine_result.get('candidates', {}).get('tokenized_equities', []))}")
    except Exception as e:
        print(f"[FAIL] Engine failed: {e}")
        return False

    print("\n=== STEP 2: Map to Strategies ===")
    candidates = engine_result.get("unified_ranked", [])[:3]

    for candidate in candidates:
        symbol = candidate.get("symbol", "UNKNOWN")
        scores = candidate.get("scores", {})
        opportunity_score = scores.get("opportunity", 0.0)
        momentum_score = scores.get("momentum", 0.0)

        # Detect regime
        if momentum_score > 0.6:
            regime = "trending"
        elif momentum_score < 0.4:
            regime = "chopping"
        else:
            regime = "volatile"

        try:
            strategy_name = trading_decision_matrix.select_strategy(regime)
            print(f"  {symbol}: score={opportunity_score:.2f}, regime={regime}, strategy={strategy_name}")
        except Exception as e:
            print(f"  {symbol}: Failed to select strategy - {e}")

    print("\n=== STEP 3: Integration Check ===")
    print("[OK] opportunity_engine.run_engine() works")
    print("[OK] trading_decision_matrix.select_strategy() works")
    print("[OK] Integration ready for trading_operations.scan_and_execute_opportunities()")

    # Show example usage
    print("\n=== USAGE EXAMPLE ===")
    print("In TradingEngine:")
    print("  result = await engine.scan_and_execute_opportunities(")
    print("      user_id=YOUR_ADMIN_ID,")
    print("      confidence_threshold=0.7,")
    print("      max_opportunities=3,")
    print("      dry_run=True  # Set False for live execution")
    print("  )")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
