#!/usr/bin/env python3
"""
Simple VPS Deployment Script using SSH Key Auth

Prerequisites:
- SSH key set up on VPS (see vps_ssh_setup_instructions.md)
- SSH config entry 'jarvis-vps' exists

Usage:
    python scripts/deploy_vps.py
    python scripts/deploy_vps.py --restart  # Also restart services
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_ssh_command(command: str, host: str = "jarvis-vps") -> tuple[bool, str]:
    """Run command on VPS via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, command],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def test_connection(host: str = "jarvis-vps") -> bool:
    """Test if SSH connection works."""
    print(f"Testing SSH connection to {host}...")
    success, output = run_ssh_command("echo 'Connected!' && hostname", host)
    if success:
        print(f"✓ Connected: {output}")
        return True
    else:
        print(f"✗ Connection failed: {output}")
        print("\nSSH key may not be set up. See scripts/vps_ssh_setup_instructions.md")
        return False


def deploy(host: str = "jarvis-vps", restart: bool = False) -> bool:
    """Deploy latest code to VPS."""

    if not test_connection(host):
        return False

    print("\n" + "=" * 60)
    print("DEPLOYING TO VPS")
    print("=" * 60)

    # Step 1: Pull latest code
    print("\n[1/3] Pulling latest code...")
    success, output = run_ssh_command(
        "cd ~/Jarvis && git fetch origin main && git reset --hard origin/main",
        host
    )
    if success:
        print(f"✓ {output[:200]}")
    else:
        print(f"✗ Git pull failed: {output}")
        return False

    # Step 2: Check Python environment
    print("\n[2/3] Checking Python environment...")
    success, output = run_ssh_command(
        "cd ~/Jarvis && python3 --version && pip3 show python-telegram-bot >/dev/null 2>&1 && echo 'Dependencies OK'",
        host
    )
    if success:
        print(f"✓ {output}")
    else:
        print("Installing dependencies...")
        run_ssh_command("cd ~/Jarvis && pip3 install -r requirements.txt", host)

    # Step 3: Optionally restart services
    if restart:
        print("\n[3/3] Restarting services...")

        # Try systemd first
        success, output = run_ssh_command(
            "systemctl restart jarvis-supervisor 2>/dev/null && echo 'Restarted via systemd'",
            host
        )
        if success and "Restarted" in output:
            print(f"✓ {output}")
        else:
            # Fall back to manual restart
            print("Using manual restart...")
            run_ssh_command("pkill -f 'python.*supervisor.py' || true", host)
            success, output = run_ssh_command(
                "cd ~/Jarvis && nohup python3 bots/supervisor.py > /tmp/supervisor.log 2>&1 & sleep 2 && pgrep -f supervisor.py && echo 'Supervisor started'",
                host
            )
            if success:
                print(f"✓ {output}")
            else:
                print(f"⚠ Restart may have failed: {output}")
    else:
        print("\n[3/3] Skipping service restart (use --restart to restart)")

    # Verify deployment
    print("\n" + "=" * 60)
    print("VERIFYING DEPLOYMENT")
    print("=" * 60)

    success, output = run_ssh_command(
        "cd ~/Jarvis && git log -1 --oneline && ps aux | grep -c 'python.*supervisor' | xargs -I{} echo 'Supervisor processes: {}'",
        host
    )
    print(output)

    print("\n✓ Deployment complete!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Deploy Jarvis to VPS")
    parser.add_argument("--host", default="jarvis-vps", help="SSH host alias")
    parser.add_argument("--restart", action="store_true", help="Restart services after deploy")
    parser.add_argument("--test", action="store_true", help="Only test connection")

    args = parser.parse_args()

    if args.test:
        return 0 if test_connection(args.host) else 1

    return 0 if deploy(args.host, args.restart) else 1


if __name__ == "__main__":
    sys.exit(main())
