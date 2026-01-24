"""
Test bags.fm API connectivity and key validity.

Phase 4, Task 1: Verify bags.fm API Keys

This script tests:
1. API key authentication
2. Quote fetching (read-only, no risk)
3. Token info retrieval
4. Partner stats access
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.trading.bags_client import get_bags_client


async def test_bags_api():
    """Test bags.fm API connectivity."""
    print("=" * 60)
    print("bags.fm API Connectivity Test")
    print("=" * 60)

    # Get client (uses env vars BAGS_API_KEY and BAGS_PARTNER_KEY)
    client = get_bags_client()

    print(f"\n[Configuration]")
    print(f"  API Key: {'[OK] Set' if client.api_key else '[X] Missing'}")
    print(f"  Partner Key: {'[OK] Set' if client.partner_key else '[X] Missing'}")
    print(f"  Base URL: {client.BASE_URL}")

    if not client.api_key or not client.partner_key:
        print("\n[X] Missing API keys! Check .env file:")
        print("  BAGS_API_KEY=...")
        print("  BAGS_PARTNER_KEY=...")
        return False

    all_passed = True

    # Test 1: Get SOL/USDC quote (read-only, safe)
    print("\n" + "=" * 60)
    print("Test 1: Get Quote (SOL -> USDC)")
    print("=" * 60)
    try:
        # SOL mint address
        sol_mint = "So11111111111111111111111111111111111111112"
        # USDC mint address
        usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        quote = await client.get_quote(
            from_token=sol_mint,
            to_token=usdc_mint,
            amount=0.1,  # 0.1 SOL
            slippage_bps=100  # 1% slippage
        )

        if quote:
            print(f"[OK] Quote retrieved successfully!")
            print(f"  From: {quote.from_amount} SOL")
            print(f"  To: {quote.to_amount:.2f} USDC")
            print(f"  Price: ${quote.price:.2f}")
            print(f"  Fee: {quote.fee:.6f}")
            print(f"  Price Impact: {quote.price_impact:.2%}")
        else:
            print("[X] Quote retrieval failed (returned None)")
            all_passed = False

    except Exception as e:
        print(f"[X] Quote test failed: {e}")
        all_passed = False

    # Test 2: Get token info
    print("\n" + "=" * 60)
    print("Test 2: Get Token Info (SOL)")
    print("=" * 60)
    try:
        token = await client.get_token_info(sol_mint)

        if token:
            print(f"[OK] Token info retrieved!")
            print(f"  Symbol: {token.symbol}")
            print(f"  Name: {token.name}")
            print(f"  Decimals: {token.decimals}")
            print(f"  Price USD: ${token.price_usd:.2f}")
            print(f"  Price SOL: {token.price_sol:.6f}")
            print(f"  24h Volume: ${token.volume_24h:,.2f}")
            print(f"  Liquidity: ${token.liquidity:,.2f}")
            print(f"  Holders: {token.holders:,}")
            print(f"  Market Cap: ${token.market_cap:,.2f}")
        else:
            print("[X] Token info failed (returned None)")
            all_passed = False

    except Exception as e:
        print(f"[X] Token info test failed: {e}")
        # This might fail if bags.fm doesn't have SOL data - not critical
        print("  (Note: Some tokens may not be available on bags.fm)")

    # Test 3: Get trending tokens
    print("\n" + "=" * 60)
    print("Test 3: Get Trending Tokens")
    print("=" * 60)
    try:
        trending = await client.get_trending_tokens(limit=5)

        if trending:
            print(f"[OK] Trending tokens retrieved! ({len(trending)} tokens)")
            for i, token in enumerate(trending, 1):
                print(f"  {i}. {token.symbol}: ${token.price_usd:.6f} (Vol: ${token.volume_24h:,.0f})")
        else:
            print("  No trending tokens (empty list)")
            # Not a failure - might just be no trending tokens

    except Exception as e:
        print(f"[X] Trending tokens test failed: {e}")
        # Not critical for core functionality
        print("  (Note: Trending endpoint may not be available)")

    # Test 4: Get partner stats
    print("\n" + "=" * 60)
    print("Test 4: Get Partner Stats")
    print("=" * 60)
    try:
        stats = await client.get_partner_stats()

        if "error" not in stats:
            print(f"[OK] Partner stats retrieved!")
            print(f"  Total Volume: {stats.get('total_volume', 0):.2f} SOL")
            print(f"  Total Fees Earned: {stats.get('total_fees_earned', 0):.6f} SOL")
            print(f"  Pending Fees: {stats.get('pending_fees', 0):.6f} SOL")
            print(f"  Total Swaps: {stats.get('total_swaps', 0):,}")
            print(f"  Unique Users: {stats.get('unique_users', 0):,}")
        else:
            print(f"[X] Partner stats failed: {stats.get('error')}")
            all_passed = False

    except Exception as e:
        print(f"[X] Partner stats test failed: {e}")
        all_passed = False

    # Test 5: Client stats
    print("\n" + "=" * 60)
    print("Test 5: Local Client Stats")
    print("=" * 60)
    try:
        client_stats = client.get_client_stats()

        print(f"[OK] Client stats:")
        print(f"  Total Volume: {client_stats['total_volume']:.2f} SOL")
        print(f"  Total Partner Fees: {client_stats['total_partner_fees']:.6f} SOL")
        print(f"  Successful Swaps: {client_stats['successful_swaps']}")
        print(f"  Failed Swaps: {client_stats['failed_swaps']}")
        print(f"  Success Rate: {client_stats['success_rate']*100:.1f}%")
        print(f"  Requests (last min): {client_stats['requests_in_last_minute']}")

    except Exception as e:
        print(f"[X] Client stats test failed: {e}")
        all_passed = False

    # Close client
    await client.close()

    # Final summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    if all_passed:
        print("[OK] All critical tests PASSED!")
        print("\nbags.fm API is working correctly.")
        print("Ready for production use with:")
        print("  - Quote fetching [OK]")
        print("  - Partner stats [OK]")
        print("  - API authentication [OK]")
        return True
    else:
        print("[X] Some tests FAILED!")
        print("\nPlease check:")
        print("  1. BAGS_API_KEY is valid")
        print("  2. BAGS_PARTNER_KEY is valid")
        print("  3. Network connectivity to bags.fm API")
        print("  4. API keys have not expired")
        return False


if __name__ == "__main__":
    print("\n Starting bags.fm API Test...\n")

    result = asyncio.run(test_bags_api())

    print("\n" + "=" * 60)
    if result:
        print("[OK] bags.fm API Integration: READY")
        sys.exit(0)
    else:
        print("[X] bags.fm API Integration: NEEDS ATTENTION")
        sys.exit(1)
