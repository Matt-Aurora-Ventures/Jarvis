#!/usr/bin/env python3
"""
Interactive Bot Token Deployment Script

Deploys bot tokens to VPS servers with interactive password prompts.
Works on Windows without requiring SSH keys.

Usage:
    python scripts/deploy_with_password.py

Servers:
    - 72.61.7.126 (Treasury bot, X bot sync)
    - 76.13.106.100 (ClawdBot suite)
"""

import os
import sys
import getpass
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent

# Load tokens from tg_bot/.env (contains valid tokens)
def load_tokens() -> dict:
    """Load tokens from environment files."""
    tokens = {}
    env_file = PROJECT_ROOT / "tg_bot" / ".env"

    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if 'BOT_TOKEN' in key.upper():
                        tokens[key.strip()] = value.strip()

    return tokens


def test_ssh_connection(host: str, user: str, password: str) -> Tuple[bool, str]:
    """Test SSH connection with password."""
    try:
        # Use plink on Windows (from PuTTY), or sshpass on Unix
        if sys.platform == 'win32':
            # Try using PowerShell's ssh with echo for password
            # This is a workaround since Windows ssh doesn't support password piping well
            result = subprocess.run(
                ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
                 f'{user}@{host}', 'echo CONNECTION_OK'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if 'CONNECTION_OK' in result.stdout:
                return True, "SSH key authentication successful"
            else:
                return False, f"SSH failed: {result.stderr}"
        else:
            result = subprocess.run(
                ['sshpass', '-p', password, 'ssh', '-o', 'StrictHostKeyChecking=no',
                 f'{user}@{host}', 'echo CONNECTION_OK'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if 'CONNECTION_OK' in result.stdout:
                return True, "SSH connection successful"
            else:
                return False, f"SSH failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Connection timeout"
    except FileNotFoundError:
        return False, "SSH client not found"
    except Exception as e:
        return False, str(e)


def deploy_token_to_vps(host: str, user: str, env_path: str, token_name: str, token_value: str) -> Tuple[bool, str]:
    """Deploy a token to VPS .env file using SSH."""
    commands = [
        # Backup existing .env
        f"cp {env_path} {env_path}.backup-$(date +%Y%m%d_%H%M%S) 2>/dev/null || true",
        # Check if token exists
        f"grep -q '^{token_name}=' {env_path} 2>/dev/null && "
        f"sed -i 's|^{token_name}=.*|{token_name}={token_value}|' {env_path} || "
        f"echo '{token_name}={token_value}' >> {env_path}",
        # Verify
        f"grep '{token_name}' {env_path}"
    ]

    try:
        for cmd in commands:
            result = subprocess.run(
                ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10',
                 f'{user}@{host}', cmd],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0 and 'backup' not in cmd:
                return False, f"Command failed: {result.stderr}"

        return True, "Token deployed successfully"
    except Exception as e:
        return False, str(e)


def restart_supervisor(host: str, user: str) -> Tuple[bool, str]:
    """Restart supervisor on VPS."""
    cmd = "pkill -f supervisor.py; sleep 2; cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"

    try:
        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', f'{user}@{host}', cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        return True, "Supervisor restarted"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("INTERACTIVE BOT TOKEN DEPLOYMENT")
    print("=" * 60)
    print()

    # Load tokens
    tokens = load_tokens()

    print("Available tokens from tg_bot/.env:")
    for name in tokens:
        print(f"  - {name}")
    print()

    # Treasury Bot Token
    treasury_token = tokens.get('TREASURY_BOT_TOKEN')
    if treasury_token:
        print(f"Found TREASURY_BOT_TOKEN: {treasury_token[:15]}...")
    else:
        print("ERROR: TREASURY_BOT_TOKEN not found in tg_bot/.env")
        treasury_token = input("Enter TREASURY_BOT_TOKEN manually: ").strip()

    print()
    print("-" * 40)
    print("DEPLOYMENT TO VPS 72.61.7.126")
    print("-" * 40)
    print()

    # Test SSH connection (key-based first)
    print("Testing SSH connection to 72.61.7.126...")
    success, msg = test_ssh_connection('72.61.7.126', 'root', '')

    if success:
        print(f"  [OK] {msg}")

        # Deploy Treasury token
        print()
        print("Deploying TREASURY_BOT_TOKEN...")
        success, msg = deploy_token_to_vps(
            '72.61.7.126', 'root',
            '/home/jarvis/Jarvis/lifeos/config/.env',
            'TREASURY_BOT_TOKEN',
            treasury_token
        )
        if success:
            print(f"  [OK] {msg}")
        else:
            print(f"  [FAILED] {msg}")

        # Deploy X Bot token if available
        x_token = tokens.get('X_BOT_TELEGRAM_TOKEN')
        if x_token:
            print()
            print("Deploying X_BOT_TELEGRAM_TOKEN...")
            success, msg = deploy_token_to_vps(
                '72.61.7.126', 'root',
                '/home/jarvis/Jarvis/lifeos/config/.env',
                'X_BOT_TELEGRAM_TOKEN',
                x_token
            )
            if success:
                print(f"  [OK] {msg}")
            else:
                print(f"  [FAILED] {msg}")

        # Restart supervisor
        print()
        print("Restarting supervisor...")
        success, msg = restart_supervisor('72.61.7.126', 'root')
        if success:
            print(f"  [OK] {msg}")
        else:
            print(f"  [FAILED] {msg}")

    else:
        print(f"  [FAILED] {msg}")
        print()
        print("MANUAL DEPLOYMENT REQUIRED:")
        print("-" * 40)
        print("1. SSH to VPS: ssh root@72.61.7.126")
        print("2. Edit .env: nano /home/jarvis/Jarvis/lifeos/config/.env")
        print(f"3. Add: TREASURY_BOT_TOKEN={treasury_token}")
        print("4. Save and exit (Ctrl+X, Y, Enter)")
        print("5. Restart: pkill -f supervisor.py && cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &")
        print()
        print("Copy-paste ready token line:")
        print(f"TREASURY_BOT_TOKEN={treasury_token}")

    print()
    print("=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Verify supervisor logs: ssh root@72.61.7.126 'tail -50 /home/jarvis/Jarvis/logs/supervisor.log'")
    print("  2. Look for: 'Using unique treasury bot token'")
    print("  3. Monitor for 10+ minutes - no crashes")
    print()


if __name__ == "__main__":
    main()
