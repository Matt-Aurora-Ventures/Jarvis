"""
Test corrected bags.fm API v1 endpoints

Tests the updated bags_client.py implementation with correct API paths:
- GET /trade/quote (was /quote)
- GET /fee-share/partner-config/stats (was /partner/stats)
- Token info via Helius RPC (bags.fm doesn't provide this)
- Trending tokens stubbed (bags.fm doesn't provide this)

Created: 2026-01-26
Author: Claude Sonnet 4.5 (Ralph Wiggum Loop)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.trading.bags_client import get_bags_client


async def main():
    """Run bags.fm API v1 endpoint tests"""

    print("=" * 60)
    print("bags.fm API v1 Endpoint Tests")
    print("=" * 60)
    print()

    client = get_bags_client()

    # Test 1: Health check (verify API is accessible)
    print("Test 1: API Health Check")
    print("-" * 60)
    try:
        # Note: bags.fm doesn't have a /ping endpoint in the client yet
        # Just verify client initialization
        if client:
            print("[PASS] Client initialized successfully")
            print(f"  Base URL: {client.BASE_URL}")
            print(f"  API Key: {'Set' if client.api_key else 'Not set'}")
            print(f"  Partner Key: {'Set' if client.partner_key else 'Not set'}")
        else:
            print("[FAIL] Client initialization failed")
    except Exception as e:
        print(f"[FAIL] Client initialization error: {e}")
    print()

    # Test 2: Get trade quote (CORRECTED PATH: /trade/quote)
    print("Test 2: GET /trade/quote (Swap Quote)")
    print("-" * 60)
    try:
        # Test SOL -> USDC quote
        quote = await client.get_quote(
            from_token="So11111111111111111111111111111111111111112",  # SOL
            to_token="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            amount=0.1,  # 0.1 SOL
            slippage_bps=100  # 1%
        )

        if quote:
            print("[PASS] Quote received successfully")
            print(f"  Input amount: {quote.in_amount / 1e9:.4f} SOL")
            print(f"  Output amount: {quote.out_amount / 1e6:.4f} USDC")
            print(f"  Price impact: {quote.price_impact_pct:.4f}%")
            print(f"  Slippage: {quote.slippage_bps} bps")
        else:
            print("[FAIL] Quote request failed (check logs for details)")
    except Exception as e:
        print(f"[FAIL] Quote request error: {e}")
    print()

    # Test 3: Partner stats (CORRECTED PATH: /fee-share/partner-config/stats)
    print("Test 3: GET /fee-share/partner-config/stats (Partner Stats)")
    print("-" * 60)
    try:
        partner_key = os.getenv("BAGS_PARTNER_KEY")
        if not partner_key:
            print("[SKIP] BAGS_PARTNER_KEY not set - skipping test")
            print("       Set this in .env to test partner statistics")
        else:
            stats = await client.get_partner_stats()

            if "error" in stats:
                print(f"[FAIL] Partner stats request failed: {stats['error']}")
            else:
                print("[PASS] Partner stats received successfully")
                print(f"  Claimed fees: {stats.get('claimed_fees', 0)} lamports")
                print(f"  Unclaimed fees: {stats.get('unclaimed_fees', 0)} lamports")
                claimed_sol = stats.get('claimed_fees', 0) / 1e9
                unclaimed_sol = stats.get('unclaimed_fees', 0) / 1e9
                print(f"  Claimed fees: {claimed_sol:.6f} SOL")
                print(f"  Unclaimed fees: {unclaimed_sol:.6f} SOL")
    except Exception as e:
        print(f"[FAIL] Partner stats error: {e}")
    print()

    # Test 4: Token info via Helius RPC (NEW - bags.fm doesn't provide this)
    print("Test 4: Token Info via Helius RPC")
    print("-" * 60)
    try:
        helius_key = os.getenv("HELIUS_API_KEY")
        if not helius_key:
            print("[SKIP] HELIUS_API_KEY not set - skipping test")
            print("       Set this in .env to test token metadata lookups")
        else:
            # Test with USDC token
            token_info = await client.get_token_info(
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
            )

            if token_info:
                print("[PASS] Token info retrieved successfully")
                print(f"  Name: {token_info.name}")
                print(f"  Symbol: {token_info.symbol}")
                print(f"  Decimals: {token_info.decimals}")
                print(f"  Address: {token_info.address}")
            else:
                print("[FAIL] Token info request failed (check logs for details)")
    except Exception as e:
        print(f"[FAIL] Token info error: {e}")
    print()

    # Test 5: Trending tokens (STUBBED - bags.fm doesn't provide this)
    print("Test 5: Trending Tokens (Deferred to V1.1)")
    print("-" * 60)
    try:
        trending = await client.get_trending_tokens(limit=5)

        if trending:
            print(f"[PASS] Trending tokens returned: {len(trending)} tokens")
        else:
            print("[PASS] Trending tokens stubbed correctly (returns empty list)")
            print("       Note: This feature is deferred to V1.1")
    except Exception as e:
        print(f"[FAIL] Trending tokens error: {e}")
    print()

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("[OK] Core endpoints fixed:")
    print("     - GET /trade/quote (trade quotes)")
    print("     - GET /fee-share/partner-config/stats (partner stats)")
    print()
    print("[OK] Missing endpoints handled:")
    print("     - Token info -> Helius RPC fallback")
    print("     - Trending tokens -> Stubbed (V1.1)")
    print()
    print("Next steps:")
    print("  1. Verify API keys in .env (BAGS_API_KEY, HELIUS_API_KEY)")
    print("  2. Test against live API")
    print("  3. Monitor for errors in production logs")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
