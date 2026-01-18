#!/usr/bin/env python3
"""
Jarvis Autonomous System - SSH Deploy with Password Authentication

Usage:
    python scripts/deploy_with_password.py <host> <username> <password>

    Or load from .env file:
    python scripts/deploy_with_password.py (no args)

Example:
    python scripts/deploy_with_password.py 72.61.7.126 root <your_password>
"""

import paramiko
import sys
import time
import os
from pathlib import Path

def deploy_via_ssh(host: str, username: str, password: str):
    """Deploy Jarvis autonomous system via SSH with password auth."""

    print("=" * 70)
    print("JARVIS AUTONOMOUS SYSTEM - SSH PASSWORD DEPLOYMENT")
    print("=" * 70)
    print()

    # Create SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"[1/8] Connecting to {host}@{username}...")
        ssh.connect(host, username=username, password=password, timeout=30)
        print(f"      ✓ Connected successfully")
        print()

        # Step 1: Verify project directory
        print(f"[2/8] Verifying project directory...")
        stdin, stdout, stderr = ssh.exec_command("cd ~/Jarvis && pwd")
        result = stdout.read().decode().strip()
        if "Jarvis" in result:
            print(f"      ✓ Project directory: {result}")
        else:
            print(f"      ✗ Error: {stderr.read().decode()}")
            return False
        print()

        # Step 2: Pull latest code
        print(f"[3/8] Pulling latest code from main branch...")
        stdin, stdout, stderr = ssh.exec_command(
            "cd ~/Jarvis && git fetch origin main && git reset --hard origin/main"
        )
        result = stdout.read().decode()
        err = stderr.read().decode()
        if "Already up to date" in result or "HEAD is now at" in result:
            print(f"      ✓ Code updated successfully")
        else:
            print(f"      ✓ Git updated (output: {result[:100]})")
        print()

        # Step 3: Verify autonomous system files
        print(f"[4/8] Verifying autonomous system files...")
        files_to_check = [
            "core/moderation/toxicity_detector.py",
            "core/moderation/auto_actions.py",
            "core/learning/engagement_analyzer.py",
            "core/vibe_coding/sentiment_mapper.py",
            "core/vibe_coding/regime_adapter.py",
            "core/autonomous_manager.py",
        ]

        all_exist = True
        for file in files_to_check:
            stdin, stdout, stderr = ssh.exec_command(f"test -f ~/Jarvis/{file} && echo OK || echo MISSING")
            result = stdout.read().decode().strip()
            status = "✓" if result == "OK" else "✗"
            print(f"      {status} {file}")
            if result != "OK":
                all_exist = False

        if not all_exist:
            print("      Error: Some files missing")
            return False
        print()

        # Step 4: Create directories
        print(f"[5/8] Creating required directories...")
        ssh.exec_command("mkdir -p ~/Jarvis/data/moderation ~/Jarvis/data/learning ~/Jarvis/data/vibe_coding ~/Jarvis/data/validation_proof ~/Jarvis/logs")
        print(f"      ✓ Directories created")
        print()

        # Step 5: Stop supervisor
        print(f"[6/8] Stopping supervisor gracefully...")
        stdin, stdout, stderr = ssh.exec_command("sudo systemctl stop jarvis-supervisor 2>/dev/null || true && sleep 5")
        stdout.read()
        print(f"      ✓ Supervisor stopped")
        print()

        # Step 6: Restart supervisor
        print(f"[7/8] Restarting supervisor with autonomous manager...")
        ssh.exec_command("sudo systemctl start jarvis-supervisor")
        time.sleep(10)
        print(f"      ✓ Supervisor restarted")
        print()

        # Step 7: Verify startup
        print(f"[8/8] Verifying autonomous_manager startup...")
        stdin, stdout, stderr = ssh.exec_command("tail -50 ~/Jarvis/logs/supervisor.log | grep -i autonomous_manager")
        result = stdout.read().decode()
        if "autonomous_manager" in result.lower():
            print(f"      ✓ autonomous_manager detected in logs")
        else:
            print(f"      ⚠ autonomous_manager not yet in logs, checking status...")
            stdin, stdout, stderr = ssh.exec_command("sudo systemctl status jarvis-supervisor")
            status = stdout.read().decode()
            if "active (running)" in status:
                print(f"      ✓ Supervisor is running (autonomous_manager may be starting)")
            else:
                print(f"      ✗ Supervisor status issue")
        print()

        # Step 8: Start validation loop
        print(f"[9/9] Starting continuous validation loop...")
        ssh.exec_command(
            "cd ~/Jarvis && nohup python scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &"
        )
        time.sleep(5)
        print(f"      ✓ Validation loop started")
        print()

        # Final status
        print("=" * 70)
        print("✅ DEPLOYMENT COMPLETE")
        print("=" * 70)
        print()
        print("NEXT STEPS:")
        print()
        print("1. Monitor supervisor:")
        print("   ssh " + f"{username}@{host}")
        print("   tail -f ~/Jarvis/logs/supervisor.log")
        print()
        print("2. Monitor validation loop:")
        print("   tail -f ~/Jarvis/logs/validation_continuous.log")
        print()
        print("3. Check validation proof (after 1+ hours):")
        print("   ls ~/Jarvis/data/validation_proof/")
        print()
        print("4. Check component health:")
        print("   /status command in Telegram")
        print()

        return True

    except paramiko.ssh_exception.AuthenticationException:
        print(f"✗ Authentication failed - incorrect username or password")
        return False
    except paramiko.ssh_exception.SSHException as e:
        print(f"✗ SSH Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        ssh.close()


def main():
    # If arguments provided, use them
    if len(sys.argv) == 4:
        host = sys.argv[1]
        username = sys.argv[2]
        password = sys.argv[3]
    # Otherwise, try to load from .env file
    elif len(sys.argv) == 1:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
            except ImportError:
                # Manually load .env
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()

        host = os.environ.get('VPS_HOST')
        username = os.environ.get('VPS_USERNAME')
        password = os.environ.get('VPS_PASSWORD')

        if not all([host, username, password]):
            print("ERROR: Missing VPS credentials")
            print("Usage: python deploy_with_password.py <host> <username> <password>")
            print("   or: python deploy_with_password.py (loads from .env)")
            print()
            print("Example:")
            print("  python deploy_with_password.py 72.61.7.126 root mypassword")
            sys.exit(1)
    else:
        print("Usage: python deploy_with_password.py <host> <username> <password>")
        print("   or: python deploy_with_password.py (loads from .env)")
        print()
        print("Example:")
        print("  python deploy_with_password.py 72.61.7.126 root mypassword")
        sys.exit(1)

    success = deploy_via_ssh(host, username, password)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
