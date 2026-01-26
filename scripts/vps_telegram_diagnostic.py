#!/usr/bin/env python3
"""VPS Telegram Bot Diagnostic Script.

Run this on the VPS to diagnose Telegram bot issues:
    python scripts/vps_telegram_diagnostic.py

Or run locally to check local environment:
    python scripts/vps_telegram_diagnostic.py --local
"""

import os
import subprocess
import sys
from pathlib import Path

# Colors for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def ok(msg: str) -> str:
    return f"{Colors.GREEN}✓{Colors.RESET} {msg}"


def warn(msg: str) -> str:
    return f"{Colors.YELLOW}⚠{Colors.RESET} {msg}"


def fail(msg: str) -> str:
    return f"{Colors.RED}✗{Colors.RESET} {msg}"


def info(msg: str) -> str:
    return f"{Colors.BLUE}ℹ{Colors.RESET} {msg}"


def header(msg: str) -> str:
    return f"\n{Colors.BOLD}{'=' * 60}\n{msg}\n{'=' * 60}{Colors.RESET}"


def load_env_files(project_root: Path) -> dict:
    """Load environment variables from .env files (same order as supervisor)."""
    env_files = [
        project_root / "tg_bot" / ".env",
        project_root / "bots" / "twitter" / ".env",
        project_root / ".env",
    ]
    
    loaded_vars = {}
    for env_path in env_files:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in loaded_vars:
                            loaded_vars[key] = (value, str(env_path))
    return loaded_vars


def mask_value(value: str) -> str:
    """Mask sensitive values for display."""
    if not value or len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def check_env_vars(project_root: Path) -> tuple[list, list, list]:
    """Check required environment variables."""
    issues = []
    warnings = []
    successes = []
    
    env_vars = load_env_files(project_root)
    
    # Critical: Telegram bot token
    critical_vars = [
        ("TELEGRAM_BOT_TOKEN", "Main Telegram bot - REQUIRED"),
        ("TELEGRAM_ADMIN_IDS", "Admin user IDs - REQUIRED for admin commands"),
    ]
    
    # Buy bot vars
    buy_bot_vars = [
        ("TELEGRAM_BUY_BOT_TOKEN", "Buy bot dedicated token (prevents callback conflicts)"),
        ("TELEGRAM_BUY_BOT_CHAT_ID", "Chat ID for buy notifications"),
        ("BUY_BOT_TOKEN_ADDRESS", "Solana token address to track"),
        ("HELIUS_API_KEY", "Helius API for Solana RPC"),
    ]
    
    # Optional but recommended
    optional_vars = [
        ("ANTHROPIC_API_KEY", "Claude API for AI features"),
        ("XAI_API_KEY", "Grok API for sentiment analysis"),
        ("BIRDEYE_API_KEY", "Birdeye API for token data"),
    ]
    
    print(header("CRITICAL ENVIRONMENT VARIABLES"))
    for var, desc in critical_vars:
        if var in env_vars:
            value, source = env_vars[var]
            successes.append(var)
            print(ok(f"{var}: {mask_value(value)} (from {Path(source).name})"))
        else:
            issues.append(var)
            print(fail(f"{var}: NOT SET - {desc}"))
    
    print(header("BUY BOT CONFIGURATION"))
    for var, desc in buy_bot_vars:
        if var in env_vars:
            value, source = env_vars[var]
            successes.append(var)
            print(ok(f"{var}: {mask_value(value)} (from {Path(source).name})"))
        else:
            warnings.append(var)
            print(warn(f"{var}: NOT SET - {desc}"))
    
    # Check for token conflict
    main_token = env_vars.get("TELEGRAM_BOT_TOKEN", (None, None))[0]
    buy_token = env_vars.get("TELEGRAM_BUY_BOT_TOKEN", (None, None))[0]
    if main_token and buy_token and main_token == buy_token:
        issues.append("TOKEN_CONFLICT")
        print(fail("TELEGRAM_BUY_BOT_TOKEN matches TELEGRAM_BOT_TOKEN - callbacks will break!"))
    elif main_token and not buy_token:
        print(warn("Buy bot will use main token - consider setting TELEGRAM_BUY_BOT_TOKEN"))
    
    print(header("OPTIONAL CONFIGURATION"))
    for var, desc in optional_vars:
        if var in env_vars:
            value, source = env_vars[var]
            print(ok(f"{var}: {mask_value(value)}"))
        else:
            print(info(f"{var}: not set - {desc}"))
    
    return issues, warnings, successes


def check_processes() -> list:
    """Check for running telegram bot processes."""
    issues = []
    print(header("PROCESS CHECK"))
    
    try:
        # Check for telegram bot processes
        result = subprocess.run(
            ["pgrep", "-af", "tg_bot|telegram"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            processes = result.stdout.strip().split("\n")
            print(info(f"Found {len(processes)} telegram-related process(es):"))
            for proc in processes:
                print(f"    {proc[:80]}...")
            
            # Check for multiple bot.py instances
            bot_count = sum(1 for p in processes if "bot.py" in p)
            if bot_count > 1:
                issues.append("MULTIPLE_INSTANCES")
                print(fail(f"Multiple bot.py instances detected ({bot_count}) - lock conflict likely!"))
        else:
            print(info("No telegram bot processes currently running"))
    except FileNotFoundError:
        # pgrep not available (Windows)
        print(info("Process check skipped (pgrep not available on Windows)"))
    
    return issues


def check_supervisor_status() -> list:
    """Check systemd supervisor status."""
    issues = []
    print(header("SUPERVISOR STATUS"))
    
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "jarvis-supervisor"],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()
        if status == "active":
            print(ok("jarvis-supervisor is active"))
        else:
            issues.append("SUPERVISOR_INACTIVE")
            print(fail(f"jarvis-supervisor status: {status}"))
            print(info("Run: systemctl start jarvis-supervisor"))
    except FileNotFoundError:
        print(info("Supervisor check skipped (systemctl not available)"))
    
    return issues


def check_env_files(project_root: Path) -> list:
    """Check which .env files exist."""
    issues = []
    print(header("ENV FILE LOCATIONS"))
    
    env_files = [
        (project_root / "tg_bot" / ".env", "Primary for telegram bot"),
        (project_root / "bots" / "twitter" / ".env", "Twitter bot config"),
        (project_root / ".env", "Project root fallback"),
    ]
    
    found_any = False
    for path, desc in env_files:
        if path.exists():
            found_any = True
            size = path.stat().st_size
            print(ok(f"{path.relative_to(project_root)} ({size} bytes) - {desc}"))
        else:
            print(info(f"{path.relative_to(project_root)} - not found"))
    
    if not found_any:
        issues.append("NO_ENV_FILES")
        print(fail("No .env files found! Bot cannot start without TELEGRAM_BOT_TOKEN"))
    
    return issues


def check_legacy_configs(project_root: Path) -> list:
    """Check for legacy config files."""
    warnings = []
    print(header("LEGACY CONFIG FILES"))
    
    legacy_files = [
        project_root / "lifeos" / "config" / "telegram_bot.json",
        project_root / "lifeos" / "config" / "x_bot.json",
    ]
    
    for path in legacy_files:
        if path.exists():
            print(ok(f"{path.relative_to(project_root)} exists"))
        else:
            warnings.append(str(path.name))
            print(warn(f"{path.relative_to(project_root)} missing - legacy integrations may use defaults"))
    
    return warnings


def main():
    print(f"\n{Colors.BOLD}JARVIS TELEGRAM BOT DIAGNOSTIC{Colors.RESET}")
    print(f"{'=' * 60}\n")
    
    # Determine project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]
    
    # Check if we're on VPS or local
    is_local = "--local" in sys.argv or os.name == "nt"
    print(info(f"Running in {'LOCAL' if is_local else 'VPS'} mode"))
    print(info(f"Project root: {project_root}"))
    
    all_issues = []
    all_warnings = []
    
    # Run checks
    issues, warnings, _ = check_env_vars(project_root)
    all_issues.extend(issues)
    all_warnings.extend(warnings)
    
    all_issues.extend(check_env_files(project_root))
    all_warnings.extend(check_legacy_configs(project_root))
    
    if not is_local:
        all_issues.extend(check_processes())
        all_issues.extend(check_supervisor_status())
    
    # Summary
    print(header("SUMMARY"))
    if all_issues:
        print(fail(f"{len(all_issues)} critical issue(s) found:"))
        for issue in all_issues:
            print(f"    - {issue}")
    else:
        print(ok("No critical issues found"))
    
    if all_warnings:
        print(warn(f"{len(all_warnings)} warning(s):"))
        for warning in all_warnings:
            print(f"    - {warning}")
    
    # Recommendations
    if all_issues:
        print(header("RECOMMENDED ACTIONS"))
        if "TELEGRAM_BOT_TOKEN" in all_issues:
            print("1. Set TELEGRAM_BOT_TOKEN in tg_bot/.env or .env")
            print("   Get a token from @BotFather on Telegram")
        if "MULTIPLE_INSTANCES" in all_issues:
            print("2. Kill duplicate processes: pkill -f 'tg_bot/bot.py'")
            print("   Then restart supervisor: systemctl restart jarvis-supervisor")
        if "TOKEN_CONFLICT" in all_issues:
            print("3. Create a separate bot for buy notifications via @BotFather")
            print("   Set TELEGRAM_BUY_BOT_TOKEN to the new token")
        if "SUPERVISOR_INACTIVE" in all_issues:
            print("4. Start supervisor: systemctl start jarvis-supervisor")
    
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
