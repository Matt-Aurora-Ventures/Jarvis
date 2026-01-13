"""Audit all Telegram bot commands - test each function."""
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

# All public commands to test
PUBLIC_COMMANDS = [
    "solprice",
    "trending", 
    "gainers",
    "losers",
    "newpairs",
    "price",      # needs token address
    "mcap",       # needs token address
    "volume",     # needs token address
    "chart",      # needs token address
    "liquidity",  # needs token address
    "age",        # needs token address
    "summary",    # needs token address
]

# Test token address (SOL wrapped)
TEST_TOKEN = "So11111111111111111111111111111111111111112"

async def test_free_apis():
    """Test the underlying free APIs."""
    results = {}
    
    print("=" * 60)
    print("TESTING FREE APIs")
    print("=" * 60)
    
    # Test 1: SOL Price
    print("\n1. Testing get_sol_price()...")
    try:
        from core.data.free_price_api import get_sol_price
        price = await get_sol_price()
        if price > 0:
            results["get_sol_price"] = ("PASS", f"${price:.2f}")
        else:
            results["get_sol_price"] = ("FAIL", "Price is 0")
    except Exception as e:
        results["get_sol_price"] = ("FAIL", str(e)[:50])
    
    # Test 2: Token Price
    print("2. Testing get_token_price()...")
    try:
        from core.data.free_price_api import get_token_price
        data = await get_token_price(TEST_TOKEN)
        if data and data.price_usd > 0:
            results["get_token_price"] = ("PASS", f"{data.symbol} ${data.price_usd:.2f}")
        else:
            results["get_token_price"] = ("FAIL", "No data returned")
    except Exception as e:
        results["get_token_price"] = ("FAIL", str(e)[:50])
    
    # Test 3: Trending
    print("3. Testing get_trending()...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_trending(limit=5)
        if tokens and len(tokens) > 0:
            results["get_trending"] = ("PASS", f"{len(tokens)} tokens")
        else:
            results["get_trending"] = ("FAIL", "No tokens returned")
    except Exception as e:
        results["get_trending"] = ("FAIL", str(e)[:50])
    
    # Test 4: Gainers
    print("4. Testing get_gainers()...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_gainers(limit=5)
        if tokens and len(tokens) > 0:
            results["get_gainers"] = ("PASS", f"{len(tokens)} tokens")
        else:
            results["get_gainers"] = ("FAIL", "No tokens returned")
    except Exception as e:
        results["get_gainers"] = ("FAIL", str(e)[:50])
    
    # Test 5: New Pairs
    print("5. Testing get_new_pairs()...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_new_pairs(limit=5)
        # Empty is OK - might just be no new pairs
        results["get_new_pairs"] = ("PASS", f"{len(tokens)} tokens")
    except Exception as e:
        results["get_new_pairs"] = ("FAIL", str(e)[:50])
    
    # Test 6: Rate Limiter
    print("6. Testing rate_limiter.get_stats()...")
    try:
        from core.utils.rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        stats = limiter.get_stats()
        if stats:
            results["rate_limiter"] = ("PASS", f"{len(stats)} limiters")
        else:
            results["rate_limiter"] = ("FAIL", "No stats returned")
    except Exception as e:
        results["rate_limiter"] = ("FAIL", str(e)[:50])
    
    # Print results
    print("\n" + "=" * 60)
    print("API TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, (status, detail) in results.items():
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {name}: {status} - {detail}")
        if status == "PASS":
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return results

async def test_bot_imports():
    """Test that all bot command functions can be imported."""
    print("\n" + "=" * 60)
    print("TESTING BOT IMPORTS")
    print("=" * 60)
    
    results = {}
    
    commands = [
        "start", "help_command", "status", "costs", "trending",
        "solprice", "mcap", "volume", "chart", "liquidity", "age",
        "summary", "price", "gainers", "losers", "newpairs",
        "signals", "analyze", "digest", "reload", "keystatus",
        "score", "health", "flags", "audit", "ratelimits",
        "config_cmd", "orders", "system", "wallet", "logs",
        "metrics", "uptime", "brain", "paper", "report",
        "balance", "positions", "settings"
    ]
    
    try:
        import tg_bot.bot as bot_module
        
        for cmd in commands:
            if hasattr(bot_module, cmd):
                results[cmd] = ("PASS", "Function exists")
            else:
                results[cmd] = ("FAIL", "Function not found")
    except Exception as e:
        print(f"Failed to import bot module: {e}")
        return {}
    
    # Print results
    passed = sum(1 for _, (s, _) in results.items() if s == "PASS")
    failed = sum(1 for _, (s, _) in results.items() if s == "FAIL")
    
    print(f"\nImport Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\nMissing functions:")
        for name, (status, _) in results.items():
            if status == "FAIL":
                print(f"  - {name}")
    
    return results

async def main():
    print("\n" + "=" * 60)
    print("JARVIS TELEGRAM COMMAND AUDIT")
    print("=" * 60)
    
    # Test APIs
    api_results = await test_free_apis()
    
    # Test imports
    import_results = await test_bot_imports()
    
    # Summary
    api_passed = sum(1 for _, (s, _) in api_results.items() if s == "PASS")
    api_total = len(api_results)
    import_passed = sum(1 for _, (s, _) in import_results.items() if s == "PASS")
    import_total = len(import_results)
    
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"APIs: {api_passed}/{api_total} passing")
    print(f"Imports: {import_passed}/{import_total} passing")
    
    # Return failures for fixing
    failures = []
    for name, (status, detail) in api_results.items():
        if status == "FAIL":
            failures.append(("API", name, detail))
    for name, (status, detail) in import_results.items():
        if status == "FAIL":
            failures.append(("IMPORT", name, detail))
    
    return failures

if __name__ == "__main__":
    failures = asyncio.run(main())
    if failures:
        print(f"\n{len(failures)} items need fixing")
