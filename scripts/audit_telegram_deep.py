"""Deep audit of Telegram bot commands - test edge cases."""
import asyncio
import os
import sys
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\"'))

# Test tokens
TEST_TOKENS = [
    ("So11111111111111111111111111111111111111112", "Wrapped SOL"),
    ("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDC"),
]

async def test_price_commands():
    """Test price-related command logic."""
    results = {}
    
    print("\n" + "=" * 60)
    print("TESTING PRICE COMMANDS")
    print("=" * 60)
    
    from core.data.free_price_api import get_token_price, get_sol_price
    
    # Test 1: SOL price
    print("\n1. /solprice - SOL price lookup")
    try:
        price = await get_sol_price()
        if price > 0:
            results["/solprice"] = ("PASS", f"${price:.2f}")
        else:
            results["/solprice"] = ("FAIL", "Price is 0")
    except Exception as e:
        results["/solprice"] = ("FAIL", str(e)[:50])
    
    # Test 2: Token price with valid address
    print("2. /price - Token price with valid SOL address")
    try:
        data = await get_token_price(TEST_TOKENS[0][0])
        if data and data.price_usd > 0:
            results["/price (valid)"] = ("PASS", f"{data.symbol} ${data.price_usd:.2f}")
        else:
            results["/price (valid)"] = ("FAIL", "No data")
    except Exception as e:
        results["/price (valid)"] = ("FAIL", str(e)[:50])
    
    # Test 3: Token price with USDC
    print("3. /price - Token price with USDC address")
    try:
        data = await get_token_price(TEST_TOKENS[1][0])
        if data and data.price_usd > 0:
            results["/price (USDC)"] = ("PASS", f"{data.symbol} ${data.price_usd:.2f}")
        else:
            results["/price (USDC)"] = ("FAIL", "No data")
    except Exception as e:
        results["/price (USDC)"] = ("FAIL", str(e)[:50])
    
    # Test 4: Invalid token address
    print("4. /price - Invalid token address handling")
    try:
        data = await get_token_price("invalid_address_12345")
        if data is None:
            results["/price (invalid)"] = ("PASS", "Returns None correctly")
        else:
            results["/price (invalid)"] = ("WARN", "Should return None for invalid")
    except Exception as e:
        results["/price (invalid)"] = ("FAIL", str(e)[:50])
    
    return results

async def test_trending_commands():
    """Test trending-related commands."""
    results = {}
    
    print("\n" + "=" * 60)
    print("TESTING TRENDING COMMANDS")
    print("=" * 60)
    
    from core.data.free_trending_api import get_free_trending_api
    api = get_free_trending_api()
    
    # Test 1: Trending
    print("\n1. /trending - Get trending tokens")
    try:
        tokens = await api.get_trending(limit=10)
        if tokens:
            # Check data quality
            has_symbols = all(t.symbol for t in tokens)
            has_prices = all(t.price_usd >= 0 for t in tokens)
            if has_symbols and has_prices:
                results["/trending"] = ("PASS", f"{len(tokens)} tokens with data")
            else:
                results["/trending"] = ("WARN", "Missing symbol or price data")
        else:
            results["/trending"] = ("FAIL", "No tokens returned")
    except Exception as e:
        results["/trending"] = ("FAIL", str(e)[:50])
    
    # Test 2: Gainers
    print("2. /gainers - Get top gainers")
    try:
        tokens = await api.get_gainers(limit=10)
        if tokens:
            has_changes = all(hasattr(t, 'price_change_24h') for t in tokens)
            results["/gainers"] = ("PASS", f"{len(tokens)} gainers")
        else:
            results["/gainers"] = ("FAIL", "No gainers returned")
    except Exception as e:
        results["/gainers"] = ("FAIL", str(e)[:50])
    
    # Test 3: Losers (uses gainers internally)
    print("3. /losers - Get top losers")
    try:
        tokens = await api.get_gainers(limit=20)
        losers = [t for t in tokens if hasattr(t, 'price_change_24h') and t.price_change_24h < 0]
        results["/losers"] = ("PASS", f"{len(losers)} losers found")
    except Exception as e:
        results["/losers"] = ("FAIL", str(e)[:50])
    
    # Test 4: New pairs
    print("4. /newpairs - Get new trading pairs")
    try:
        tokens = await api.get_new_pairs(limit=10)
        results["/newpairs"] = ("PASS", f"{len(tokens)} new pairs")
    except Exception as e:
        results["/newpairs"] = ("FAIL", str(e)[:50])
    
    return results

async def test_admin_commands():
    """Test admin command dependencies."""
    results = {}
    
    print("\n" + "=" * 60)
    print("TESTING ADMIN COMMAND DEPENDENCIES")
    print("=" * 60)
    
    # Test 1: Health monitor
    print("\n1. /health - Health monitor")
    try:
        from core.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        status = monitor.get_overall_status()
        results["/health"] = ("PASS", f"Status: {status.value}")
    except Exception as e:
        results["/health"] = ("FAIL", str(e)[:50])
    
    # Test 2: Feature flags
    print("2. /flags - Feature flags")
    try:
        from core.feature_flags import get_feature_flags
        ff = get_feature_flags()
        flags = ff.get_all_flags()
        results["/flags"] = ("PASS", f"{len(flags)} flags")
    except Exception as e:
        results["/flags"] = ("FAIL", str(e)[:50])
    
    # Test 3: Audit logger
    print("3. /audit - Audit logger")
    try:
        from core.audit_logger import get_audit_logger
        logger = get_audit_logger()
        entries = logger.get_entries(limit=5)
        results["/audit"] = ("PASS", f"{len(entries)} entries")
    except Exception as e:
        results["/audit"] = ("FAIL", str(e)[:50])
    
    # Test 4: Rate limiter stats
    print("4. /ratelimits - Rate limiter stats")
    try:
        from core.utils.rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        stats = limiter.get_stats()
        results["/ratelimits"] = ("PASS", f"{len(stats)} limiters")
    except Exception as e:
        results["/ratelimits"] = ("FAIL", str(e)[:50])
    
    # Test 5: Key manager
    print("5. /keystatus - Key manager")
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()
        status = km.get_status_report()  # Returns string
        addr = km.get_treasury_address()
        results["/keystatus"] = ("PASS", f"Addr: {addr[:8] if addr else 'None'}...")
    except Exception as e:
        results["/keystatus"] = ("FAIL", str(e)[:50])
    
    # Test 6: Scorekeeper
    print("6. /score - Scorekeeper")
    try:
        from bots.treasury.scorekeeper import get_scorekeeper
        sk = get_scorekeeper()
        summary = sk.get_summary()
        results["/score"] = ("PASS", f"Win rate: {summary.get('win_rate', 'N/A')}")
    except Exception as e:
        results["/score"] = ("FAIL", str(e)[:50])
    
    return results

async def main():
    print("\n" + "=" * 60)
    print("JARVIS TELEGRAM DEEP AUDIT")
    print("=" * 60)
    
    all_results = {}
    
    # Run all tests
    price_results = await test_price_commands()
    all_results.update(price_results)
    
    trending_results = await test_trending_commands()
    all_results.update(trending_results)
    
    admin_results = await test_admin_commands()
    all_results.update(admin_results)
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, (s, _) in all_results.items() if s == "PASS")
    warned = sum(1 for _, (s, _) in all_results.items() if s == "WARN")
    failed = sum(1 for _, (s, _) in all_results.items() if s == "FAIL")
    
    for name, (status, detail) in all_results.items():
        icon = "OK" if status == "PASS" else "!!" if status == "WARN" else "XX"
        print(f"  [{icon}] {name}: {detail}")
    
    print(f"\nTotal: {passed} passed, {warned} warnings, {failed} failed")
    
    if failed > 0:
        print("\nFAILURES TO FIX:")
        for name, (status, detail) in all_results.items():
            if status == "FAIL":
                print(f"  - {name}: {detail}")
    
    return all_results

if __name__ == "__main__":
    asyncio.run(main())
