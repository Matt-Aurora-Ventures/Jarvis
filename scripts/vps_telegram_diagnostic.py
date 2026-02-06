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
from typing import Optional, Tuple

# Windows terminals can default to legacy encodings (cp1252) that can't print
# some unicode symbols used by this script. Avoid crashing on print().
def _ensure_stdio() -> None:
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_ensure_stdio()

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
        # ClawdBots deployments keep tokens here.
        project_root / "tokens.env",
        Path("/root/clawdbots/tokens.env"),
        # OpenClaw gateway deployments often keep env here.
        project_root / "docker" / "clawdbot-gateway" / ".env",
        Path("/docker/clawdbot-gateway/.env"),
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


def _tg_get(token: str, method: str) -> Tuple[Optional[int], dict, Optional[str]]:
    """Call Telegram Bot API method safely without leaking token."""
    if not token:
        return None, {}, "missing token"
    try:
        import requests

        url = f"https://api.telegram.org/bot{token}/{method}"
        # Avoid inheriting hostile/broken proxy env vars on locked-down hosts.
        sess = requests.Session()
        sess.trust_env = False
        resp = sess.get(url, timeout=10)
        status = resp.status_code
        try:
            data = resp.json()
        except Exception:
            data = {"ok": False}
        if data.get("ok"):
            return status, data, None
        description = (data.get("description") or resp.text or "").strip()
        return status, data, description or "unknown error"
    except Exception as exc:
        return None, {}, str(exc)


def _print_tg_token_health(token_label: str, token: str) -> list:
    """Print getMe + getWebhookInfo for a token. Returns list of issues."""
    issues = []
    status, data, err = _tg_get(token, "getMe")
    if err:
        issues.append(f"TELEGRAM_TOKEN_INVALID_{token_label}")
        print(fail(f"{token_label}: getMe failed ({status}): {err}"))
        return issues

    bot = (data.get("result") or {})
    username = bot.get("username") or "(unknown)"
    print(ok(f"{token_label}: getMe OK (@{username})"))

    status, data, err = _tg_get(token, "getWebhookInfo")
    if err:
        issues.append(f"TELEGRAM_WEBHOOK_CHECK_FAILED_{token_label}")
        print(warn(f"{token_label}: getWebhookInfo failed ({status}): {err}"))
        return issues

    info = (data.get("result") or {})
    url = info.get("url") or ""
    pending = info.get("pending_update_count", 0)
    last_error = info.get("last_error_message") or ""

    if url:
        issues.append(f"TELEGRAM_WEBHOOK_SET_{token_label}")
        print(warn(f"{token_label}: webhook is SET ({url[:60]}...) pending={pending}"))
    else:
        print(ok(f"{token_label}: webhook cleared (polling OK) pending={pending}"))
    if last_error:
        print(warn(f"{token_label}: webhook last_error={last_error[:120]}"))

    return issues


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

    clawdbot_tokens = [
        ("CLAWDJARVIS_BOT_TOKEN", "ClawdJarvis Telegram bot token"),
        ("CLAWDFRIDAY_BOT_TOKEN", "ClawdFriday Telegram bot token"),
        ("CLAWDMATT_BOT_TOKEN", "ClawdMatt Telegram bot token"),
    ]

    openclaw_tokens = [
        ("JARVIS_TELEGRAM_TOKEN", "OpenClaw gateway: Jarvis Telegram token"),
        ("FRIDAY_TELEGRAM_TOKEN", "OpenClaw gateway: Friday Telegram token"),
        ("MATT_TELEGRAM_TOKEN", "OpenClaw gateway: Matt Telegram token"),
        ("YODA_TELEGRAM_TOKEN", "OpenClaw gateway: Yoda Telegram token"),
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

    # Token health checks (safe: does not call getUpdates).
    main_token = env_vars.get("TELEGRAM_BOT_TOKEN", (None, None))[0]
    if main_token:
        print(header("TELEGRAM TOKEN HEALTH (MAIN BOT)"))
        issues.extend(_print_tg_token_health("TELEGRAM_BOT_TOKEN", main_token))
    
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

    print(header("CLAWDBOTS TOKENS (TELEBOT/pyTelegramBotAPI)"))
    any_clawdbot_token = False
    for var, desc in clawdbot_tokens:
        if var in env_vars:
            any_clawdbot_token = True
            value, source = env_vars[var]
            successes.append(var)
            print(ok(f"{var}: {mask_value(value)} (from {Path(source).name})"))
        else:
            warnings.append(var)
            print(warn(f"{var}: NOT SET - {desc}"))

    # Check for telebot dependency only if ClawdBots tokens are present.
    if any_clawdbot_token:
        try:
            import telebot  # noqa: F401
            print(ok("pyTelegramBotAPI/telebot: import OK"))
        except Exception:
            issues.append("MISSING_PYTELEGRAMBOTAPI")
            print(fail("pyTelegramBotAPI missing (cannot import `telebot`). Install: pip3 install pyTelegramBotAPI"))

    # Token health checks for clawdbots.
    if any_clawdbot_token:
        print(header("TELEGRAM TOKEN HEALTH (CLAWDBOTS)"))
        for var, _desc in clawdbot_tokens:
            token = env_vars.get(var, (None, None))[0]
            if token:
                issues.extend(_print_tg_token_health(var, token))

    print(header("OPENCLAW GATEWAY TOKENS (DOCKER)"))
    any_openclaw_token = False
    for var, desc in openclaw_tokens:
        if var in env_vars:
            any_openclaw_token = True
            value, source = env_vars[var]
            successes.append(var)
            print(ok(f"{var}: {mask_value(value)} (from {Path(source).name})"))
        else:
            print(info(f"{var}: not set - {desc}"))

    if any_openclaw_token:
        print(header("TELEGRAM TOKEN HEALTH (OPENCLAW)"))
        for var, _desc in openclaw_tokens:
            token = env_vars.get(var, (None, None))[0]
            if token:
                issues.extend(_print_tg_token_health(var, token))
    
    return issues, warnings, successes


def check_processes() -> list:
    """Check for running telegram bot processes."""
    issues = []
    print(header("PROCESS CHECK"))
    
    try:
        # Check for telegram bot processes
        result = subprocess.run(
            ["pgrep", "-af", "tg_bot|telegram|clawd"],
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
    print(header("SERVICE STATUS"))
    
    try:
        # Jarvis main supervisor (VPS1)
        result = subprocess.run(
            ["systemctl", "is-active", "jarvis-supervisor"],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()
        if status == "active":
            print(ok("jarvis-supervisor is active"))
        elif status == "unknown":
            print(info("jarvis-supervisor not installed on this host"))
        else:
            issues.append("SUPERVISOR_INACTIVE")
            print(fail(f"jarvis-supervisor status: {status}"))

        # ClawdBots fleet (VPS2)
        claw_services = [
            "clawdbots.target",
            "clawdjarvis",
            "clawdfriday",
            "clawdmatt",
            "clawdbot-gateway",
        ]
        for svc in claw_services:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True,
                text=True,
            )
            status = result.stdout.strip()
            if status == "active":
                print(ok(f"{svc} is active"))
            elif status == "unknown":
                print(info(f"{svc} not installed on this host"))
            else:
                issues.append(f"CLAWDBOTS_{svc.replace('.', '_')}_INACTIVE")
                print(fail(f"{svc} status: {status}"))
    except FileNotFoundError:
        print(info("Supervisor check skipped (systemctl not available)"))
    
    return issues


def check_docker_containers() -> list:
    """Check docker container health for OpenClaw gateway deployments."""
    issues = []
    print(header("DOCKER CONTAINERS (OPENCLAW)"))

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print(info("Docker not installed; skipping docker checks"))
        return issues

    if result.returncode != 0:
        print(warn(f"docker ps failed (rc={result.returncode}): {result.stderr.strip()[:120]}"))
        return issues

    lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
    if not lines:
        print(info("No running docker containers"))
        return issues

    containers = {}
    for ln in lines:
        name, _, status = ln.partition("\t")
        containers[name.strip()] = status.strip()

    expected = [
        "clawdbot-friday",
        "clawdbot-matt",
        "clawdbot-jarvis",
        "clawdbot-watchdog",
        "clawdbot-yoda",
    ]

    any_expected = any(name in containers for name in expected)
    if not any_expected:
        print(info("No OpenClaw clawdbot-* containers detected"))
        # Still show a small sample for debugging.
        sample = list(containers.items())[:8]
        for name, status in sample:
            print(info(f"{name}: {status[:80]}"))
        return issues

    for name in expected:
        if name not in containers:
            continue
        status = containers[name]
        if status.lower().startswith("up"):
            print(ok(f"{name}: {status[:80]}"))
        else:
            issues.append(f"DOCKER_CONTAINER_UNHEALTHY_{name}")
            print(fail(f"{name}: {status[:80]}"))

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
        all_issues.extend(check_docker_containers())
    
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
        if "MISSING_PYTELEGRAMBOTAPI" in all_issues:
            print("2. Install ClawdBots Telegram dependency: pip3 install pyTelegramBotAPI")
        if "MULTIPLE_INSTANCES" in all_issues:
            print("3. Kill duplicate processes: pkill -f 'tg_bot/bot.py'")
            print("   Then restart supervisor: systemctl restart jarvis-supervisor")
        if "TOKEN_CONFLICT" in all_issues:
            print("4. Create a separate bot for buy notifications via @BotFather")
            print("   Set TELEGRAM_BUY_BOT_TOKEN to the new token")
        if "SUPERVISOR_INACTIVE" in all_issues:
            print("5. Start supervisor: systemctl start jarvis-supervisor")
        clawdbots_inactive = [i for i in all_issues if i.startswith("CLAWDBOTS_") and i.endswith("_INACTIVE")]
        if clawdbots_inactive:
            print("6. Start ClawdBots fleet: systemctl start clawdbots.target")
            print("   Check logs: journalctl -u clawdjarvis -f (or clawdfriday/clawdmatt)")
        if "CLAWDBOTS_clawdbot-gateway_INACTIVE" in all_issues:
            print("7. Restart OpenClaw gateway service: systemctl restart clawdbot-gateway")
        docker_unhealthy = [i for i in all_issues if i.startswith("DOCKER_CONTAINER_UNHEALTHY_")]
        if docker_unhealthy:
            print("8. Restart docker containers (OpenClaw): docker restart clawdbot-friday clawdbot-matt clawdbot-jarvis")
    
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
