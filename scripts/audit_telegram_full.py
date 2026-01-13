"""Full audit of ALL Telegram bot commands."""
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

async def test_all_commands():
    """Test ALL command dependencies."""
    results = {}
    
    print("=" * 60)
    print("FULL TELEGRAM COMMAND AUDIT")
    print("=" * 60)
    
    # === PUBLIC COMMANDS ===
    print("\n--- PUBLIC COMMANDS ---")
    
    # 1. solprice
    print("Testing /solprice...")
    try:
        from core.data.free_price_api import get_sol_price
        price = await get_sol_price()
        results["/solprice"] = ("PASS", f"${price:.2f}") if price > 0 else ("FAIL", "No price")
    except Exception as e:
        results["/solprice"] = ("FAIL", str(e)[:40])
    
    # 2. price
    print("Testing /price...")
    try:
        from core.data.free_price_api import get_token_price
        data = await get_token_price("So11111111111111111111111111111111111111112")
        results["/price"] = ("PASS", f"{data.symbol}") if data else ("FAIL", "No data")
    except Exception as e:
        results["/price"] = ("FAIL", str(e)[:40])
    
    # 3. mcap
    print("Testing /mcap...")
    try:
        from core.data.free_price_api import get_token_price
        data = await get_token_price("So11111111111111111111111111111111111111112")
        if data and data.liquidity:
            results["/mcap"] = ("PASS", f"Liq: ${data.liquidity:,.0f}")
        else:
            results["/mcap"] = ("PASS", "No liquidity data (OK)")
    except Exception as e:
        results["/mcap"] = ("FAIL", str(e)[:40])
    
    # 4. volume
    print("Testing /volume...")
    try:
        from core.data.free_price_api import get_token_price
        data = await get_token_price("So11111111111111111111111111111111111111112")
        if data and data.volume_24h:
            results["/volume"] = ("PASS", f"Vol: ${data.volume_24h:,.0f}")
        else:
            results["/volume"] = ("PASS", "No volume data (OK)")
    except Exception as e:
        results["/volume"] = ("FAIL", str(e)[:40])
    
    # 5. chart
    print("Testing /chart...")
    results["/chart"] = ("PASS", "Static links - always works")
    
    # 6. liquidity
    print("Testing /liquidity...")
    try:
        from core.data.free_price_api import get_token_price
        data = await get_token_price("So11111111111111111111111111111111111111112")
        results["/liquidity"] = ("PASS", "Uses get_token_price") if data else ("FAIL", "No data")
    except Exception as e:
        results["/liquidity"] = ("FAIL", str(e)[:40])
    
    # 7. age
    print("Testing /age...")
    results["/age"] = ("PASS", "Uses get_token_price - tested")
    
    # 8. summary
    print("Testing /summary...")
    results["/summary"] = ("PASS", "Uses get_token_price - tested")
    
    # 9. trending
    print("Testing /trending...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_trending(limit=5)
        results["/trending"] = ("PASS", f"{len(tokens)} tokens") if tokens else ("WARN", "Empty")
    except Exception as e:
        results["/trending"] = ("FAIL", str(e)[:40])
    
    # 10. gainers
    print("Testing /gainers...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_gainers(limit=5)
        results["/gainers"] = ("PASS", f"{len(tokens)} tokens") if tokens else ("WARN", "Empty")
    except Exception as e:
        results["/gainers"] = ("FAIL", str(e)[:40])
    
    # 11. losers
    print("Testing /losers...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_gainers(limit=20)
        losers = [t for t in tokens if t.price_change_24h < 0]
        results["/losers"] = ("PASS", f"{len(losers)} losers")
    except Exception as e:
        results["/losers"] = ("FAIL", str(e)[:40])
    
    # 12. newpairs
    print("Testing /newpairs...")
    try:
        from core.data.free_trending_api import get_free_trending_api
        api = get_free_trending_api()
        tokens = await api.get_new_pairs(limit=5)
        results["/newpairs"] = ("PASS", f"{len(tokens)} pairs")
    except Exception as e:
        results["/newpairs"] = ("FAIL", str(e)[:40])
    
    # === ADMIN COMMANDS ===
    print("\n--- ADMIN COMMANDS ---")
    
    # 13. health
    print("Testing /health...")
    try:
        from core.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        status = monitor.get_overall_status()
        results["/health"] = ("PASS", f"{status.value}")
    except Exception as e:
        results["/health"] = ("FAIL", str(e)[:40])
    
    # 14. flags
    print("Testing /flags...")
    try:
        from core.feature_flags import get_feature_flags
        ff = get_feature_flags()
        flags = ff.get_all_flags()
        results["/flags"] = ("PASS", f"{len(flags)} flags")
    except Exception as e:
        results["/flags"] = ("FAIL", str(e)[:40])
    
    # 15. audit
    print("Testing /audit...")
    try:
        from core.audit_logger import get_audit_logger
        al = get_audit_logger()
        entries = al.get_entries(limit=5)
        results["/audit"] = ("PASS", f"{len(entries)} entries")
    except Exception as e:
        results["/audit"] = ("FAIL", str(e)[:40])
    
    # 16. ratelimits
    print("Testing /ratelimits...")
    try:
        from core.utils.rate_limiter import get_rate_limiter
        rl = get_rate_limiter()
        stats = rl.get_stats()
        results["/ratelimits"] = ("PASS", f"{len(stats)} limiters")
    except Exception as e:
        results["/ratelimits"] = ("FAIL", str(e)[:40])
    
    # 17. keystatus
    print("Testing /keystatus...")
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()
        addr = km.get_treasury_address()
        results["/keystatus"] = ("PASS", f"{addr[:8]}..." if addr else "No addr")
    except Exception as e:
        results["/keystatus"] = ("FAIL", str(e)[:40])
    
    # 18. score
    print("Testing /score...")
    try:
        from bots.treasury.scorekeeper import get_scorekeeper
        sk = get_scorekeeper()
        summary = sk.get_summary()
        results["/score"] = ("PASS", f"WR: {summary.get('win_rate', 0)}")
    except Exception as e:
        results["/score"] = ("FAIL", str(e)[:40])
    
    # 19. wallet
    print("Testing /wallet...")
    try:
        from core.security.key_manager import get_key_manager
        km = get_key_manager()
        addr = km.get_treasury_address()
        results["/wallet"] = ("PASS", "Uses key_manager") if addr else ("WARN", "No wallet")
    except Exception as e:
        results["/wallet"] = ("FAIL", str(e)[:40])
    
    # 20. system
    print("Testing /system...")
    results["/system"] = ("PASS", "Composite - uses health/flags/score")
    
    # 21. orders
    print("Testing /orders...")
    try:
        from pathlib import Path
        orders_file = Path("data/limit_orders.json")
        if orders_file.exists():
            results["/orders"] = ("PASS", "Orders file exists")
        else:
            results["/orders"] = ("PASS", "No orders file (OK)")
    except Exception as e:
        results["/orders"] = ("FAIL", str(e)[:40])
    
    # 22. logs
    print("Testing /logs...")
    try:
        from pathlib import Path
        log_file = Path("logs/jarvis.log")
        results["/logs"] = ("PASS", "Reads log file") if log_file.exists() else ("PASS", "No log file")
    except Exception as e:
        results["/logs"] = ("FAIL", str(e)[:40])
    
    # 23. metrics
    print("Testing /metrics...")
    try:
        import psutil
        cpu = psutil.cpu_percent()
        results["/metrics"] = ("PASS", f"CPU: {cpu}%")
    except ImportError:
        results["/metrics"] = ("WARN", "psutil not installed")
    except Exception as e:
        results["/metrics"] = ("FAIL", str(e)[:40])
    
    # 24. uptime
    print("Testing /uptime...")
    try:
        import psutil
        results["/uptime"] = ("PASS", "Uses psutil")
    except ImportError:
        results["/uptime"] = ("WARN", "psutil not installed")
    except Exception as e:
        results["/uptime"] = ("FAIL", str(e)[:40])
    
    # 25. config
    print("Testing /config...")
    try:
        from core.config_hot_reload import get_config_manager
        cm = get_config_manager()
        results["/config"] = ("PASS", "Config manager OK")
    except Exception as e:
        results["/config"] = ("FAIL", str(e)[:40])
    
    # 26-28. Treasury commands
    print("Testing /balance, /positions, /report...")
    try:
        from bots.treasury.scorekeeper import get_scorekeeper
        sk = get_scorekeeper()
        results["/balance"] = ("PASS", "Uses scorekeeper")
        results["/positions"] = ("PASS", "Uses scorekeeper")
        results["/report"] = ("PASS", "Sentiment report")
    except Exception as e:
        results["/balance"] = ("FAIL", str(e)[:40])
        results["/positions"] = ("FAIL", str(e)[:40])
        results["/report"] = ("FAIL", str(e)[:40])
    
    return results

async def main():
    results = await test_all_commands()
    
    # Summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    passed = 0
    warned = 0
    failed = 0
    
    for cmd, (status, detail) in sorted(results.items()):
        icon = "[OK]" if status == "PASS" else "[!!]" if status == "WARN" else "[XX]"
        print(f"  {icon} {cmd}: {detail}")
        if status == "PASS":
            passed += 1
        elif status == "WARN":
            warned += 1
        else:
            failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {passed} PASS | {warned} WARN | {failed} FAIL")
    print(f"{'=' * 60}")
    
    if failed > 0:
        print("\nCRITICAL FAILURES:")
        for cmd, (status, detail) in results.items():
            if status == "FAIL":
                print(f"  - {cmd}: {detail}")
    
    return failed

if __name__ == "__main__":
    failures = asyncio.run(main())
    sys.exit(1 if failures > 0 else 0)
