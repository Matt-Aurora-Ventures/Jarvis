#!/usr/bin/env python3
"""
Automated Dexter testing script - monitors logs for Dexter responses.
Can be run locally to track when Dexter is triggered and what responses are generated.
"""

import subprocess
import time
import json
from datetime import datetime
from pathlib import Path

# VPS connection
VPS = "root@72.61.7.126"
LOG_FILE = "/home/jarvis/Jarvis/logs/tg_bot.log"
SSH_KEY = Path.home() / ".ssh" / "id_ed25519"

def run_ssh_command(cmd):
    """Execute SSH command on VPS."""
    try:
        result = subprocess.run(
            ["ssh", "-i", str(SSH_KEY), VPS, cmd],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def get_bot_status():
    """Get current bot status."""
    cmd = "ps aux | grep 'tg_bot.bot' | grep -v grep"
    output = run_ssh_command(cmd)
    if output and "python" in output:
        parts = output.split()
        pid = parts[1]
        return {"status": "RUNNING", "pid": pid}
    return {"status": "NOT_RUNNING", "pid": None}

def get_log_size():
    """Get current log file size."""
    cmd = f"wc -l {LOG_FILE}"
    output = run_ssh_command(cmd)
    try:
        return int(output.split()[0])
    except:
        return 0

def get_recent_logs(lines=50):
    """Get recent log lines."""
    cmd = f"tail -{lines} {LOG_FILE}"
    return run_ssh_command(cmd)

def count_dexter_invocations():
    """Count Dexter invocations in logs."""
    cmd = f"grep -ic 'dexter\\|process_finance' {LOG_FILE} || echo '0'"
    output = run_ssh_command(cmd)
    try:
        return int(output.strip())
    except:
        return 0

def get_dexter_activity():
    """Get all Dexter-related log lines."""
    cmd = f"grep -i 'dexter\\|process_finance\\|finance.*response' {LOG_FILE} || echo '(no activity)'"
    return run_ssh_command(cmd)

def get_errors():
    """Get all ERROR lines from logs."""
    cmd = f"grep -i 'ERROR\\|EXCEPTION' {LOG_FILE} | tail -10 || echo '(no errors)'"
    return run_ssh_command(cmd)

def get_conflicts():
    """Check for Conflict errors."""
    cmd = f"grep -ic 'Conflict:' {LOG_FILE} || echo '0'"
    output = run_ssh_command(cmd)
    try:
        return int(output.strip())
    except:
        return 0

def monitor_live(duration_seconds=300):
    """Monitor logs in real-time for specified duration."""
    print("═" * 60)
    print("  DEXTER MONITORING - LIVE (Ctrl+C to stop)")
    print("═" * 60)
    print(f"\nMonitoring for {duration_seconds} seconds...")
    print("Looking for: DEXTER | FINANCE | GROK | ERROR | CONFLICT")
    print("")

    start_time = time.time()
    last_lines = 0

    while time.time() - start_time < duration_seconds:
        try:
            current_lines = get_log_size()
            if current_lines > last_lines:
                # New logs appeared
                new_line_count = current_lines - last_lines
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {new_line_count} new lines...")

                # Get the new lines
                cmd = f"tail -{new_line_count} {LOG_FILE}"
                new_logs = run_ssh_command(cmd)

                # Filter and display relevant lines
                for line in new_logs.split('\n'):
                    if any(kw in line.upper() for kw in ["DEXTER", "FINANCE", "GROK", "ERROR", "CONFLICT"]):
                        print(f"  {line}")

                last_lines = current_lines

            time.sleep(2)  # Check every 2 seconds

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

    print("\n" + "═" * 60)

def show_status():
    """Show comprehensive status."""
    print("═" * 60)
    print("  DEXTER TESTING - STATUS REPORT")
    print("═" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    print("")

    # Bot status
    print("BOT STATUS:")
    status = get_bot_status()
    if status["status"] == "RUNNING":
        print(f"  ✅ Running (PID: {status['pid']})")
    else:
        print(f"  ❌ Not running")

    # Log metrics
    print(f"\nLOG METRICS:")
    size = get_log_size()
    print(f"  Log lines: {size}")

    # Dexter activity
    print(f"\nDEXTER ACTIVITY:")
    dexter_count = count_dexter_invocations()
    print(f"  Dexter invocations: {dexter_count}")

    if dexter_count > 0:
        print(f"\n  Recent Dexter activity:")
        for line in get_dexter_activity().split('\n')[:10]:
            if line.strip():
                print(f"    {line}")

    # Errors
    print(f"\nERROR STATUS:")
    errors = get_errors()
    if errors == "(no errors)":
        print(f"  ✅ No errors")
    else:
        print(f"  ❌ Errors found:")
        for line in errors.split('\n')[:3]:
            if line.strip():
                print(f"    {line}")

    # Conflicts
    print(f"\nCONFLICT STATUS:")
    conflicts = get_conflicts()
    if conflicts == 0:
        print(f"  ✅ No Conflict errors")
    else:
        print(f"  ❌ Conflict errors: {conflicts}")

    print("\n" + "═" * 60)

def test_dexter():
    """Show test scenarios."""
    print("═" * 60)
    print("  DEXTER TEST SCENARIOS")
    print("═" * 60)
    print("")
    print("Finance Keywords (Any ONE triggers Dexter):")
    print("  token, price, sentiment, bullish, bearish, buy, sell,")
    print("  position, trade, crypto, sol, btc, eth, wallet,")
    print("  portfolio, should i, is, trending, moon, rug, pump,")
    print("  dump, volume, liquidity")
    print("")
    print("Test Questions to Send to @Jarviskr8tivbot:")
    print("")
    print("EASY:")
    print("  1. Is SOL bullish?")
    print("  2. What's the BTC sentiment?")
    print("  3. Is ETH trending?")
    print("")
    print("MEDIUM:")
    print("  4. Should I buy BONK?")
    print("  5. Check liquidation levels")
    print("  6. What's my portfolio sentiment?")
    print("")
    print("HARD:")
    print("  7. Is this a pump and dump?")
    print("  8. Calculate rug pull risk")
    print("  9. What tokens are trending?")
    print("")
    print("CONTROL (Should NOT trigger Dexter):")
    print("  10. Hi, how are you?")
    print("  11. Tell me a joke")
    print("")
    print("═" * 60)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "status":
            show_status()
        elif command == "monitor":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            monitor_live(duration)
        elif command == "tests":
            test_dexter()
        elif command == "dexter-count":
            print(f"Dexter invocations: {count_dexter_invocations()}")
        elif command == "errors":
            print(get_errors())
        elif command == "conflicts":
            print(f"Conflict errors: {get_conflicts()}")
        else:
            print(f"Unknown command: {command}")
    else:
        # Default: show status
        show_status()

    print("\nUsage:")
    print("  python scripts/test_dexter_automated.py status      - Show status")
    print("  python scripts/test_dexter_automated.py monitor [s] - Monitor for N seconds")
    print("  python scripts/test_dexter_automated.py tests       - Show test scenarios")
    print("  python scripts/test_dexter_automated.py dexter-count - Count invocations")
    print("  python scripts/test_dexter_automated.py errors      - Show errors")
    print("  python scripts/test_dexter_automated.py conflicts   - Show conflicts")
