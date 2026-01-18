#!/usr/bin/env python3
"""Deploy bot lock fix to VPS via SSH with password auth."""

import subprocess
import sys
import os

# Credentials
HOST = "72.61.7.126"
USER = "jarvis"
PASSWORD = "bhjhbHBujbxbvxd57272#####"

# Commands to run on VPS
COMMANDS = [
    "cd /home/jarvis/Jarvis",
    "echo '=== Step 1: Pull latest code ==='",
    "git pull origin main",
    "",
    "echo '=== Step 2: Kill existing bot processes ==='",
    "pkill -9 -f 'tg_bot.bot' || true",
    "pkill -9 -f 'bot.py' || true",
    "sleep 2",
    "",
    "echo '=== Step 3: Clean lock file ==='",
    "rm -f /tmp/jarvis_bot.lock",
    "",
    "echo '=== Step 4: Verify lock fix ==='",
    "grep 'max_wait_time = 30' tg_bot/bot.py && echo '✓ Lock fix present' || (echo '✗ Lock fix NOT found'; exit 1)",
    "",
    "echo '=== Step 5: Start bot ==='",
    "nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> logs/tg_bot.log 2>&1 &",
    "sleep 3",
    "",
    "echo '=== Step 6: Check processes ==='",
    "ps aux | grep 'tg_bot.bot' | grep -v grep || echo 'Process not yet visible'",
    "",
    "echo '=== Step 7: Check lock ==='",
    "cat /tmp/jarvis_bot.lock 2>/dev/null || echo '(not yet created)'",
    "",
    "echo '=== Deployment Complete ==='",
]

def deploy():
    """Deploy via SSH using paramiko if available, otherwise use subprocess."""

    # Try paramiko first
    try:
        import paramiko
        print("Using paramiko for SSH connection...")
        return deploy_with_paramiko()
    except ImportError:
        print("paramiko not found, trying alternative method...")
        return deploy_with_subprocess()

def deploy_with_paramiko():
    """Deploy using paramiko."""
    import paramiko
    import time

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\nConnecting to {USER}@{HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("✓ Connected")

        command = " && ".join(COMMANDS)
        print(f"\nExecuting deployment commands...\n")

        stdin, stdout, stderr = ssh.exec_command(command)

        # Print output in real-time
        for line in stdout:
            print(line.rstrip())

        # Check for errors
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            print("\nErrors:")
            for line in stderr:
                print(line.rstrip())
            return False

        print("\n✓ Deployment successful!")
        return True

    except Exception as e:
        print(f"\n✗ Deployment failed: {e}")
        return False
    finally:
        ssh.close()

def deploy_with_subprocess():
    """Fallback: create a manual deployment guide."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  MANUAL DEPLOYMENT REQUIRED                                    ║
╚════════════════════════════════════════════════════════════════╝

SSH with password authentication is not available from this environment.

Run these commands manually on VPS:

ssh jarvis@72.61.7.126
# (password will be: bhjhbHBujbxbvxd57272#####)

Then paste these commands:

cd /home/jarvis/Jarvis
git pull origin main
bash scripts/redeploy_bot_fix.sh

Alternatively, copy and paste the entire script:
""")

    # Print the bash script
    script = " && ".join(COMMANDS)
    print("\n" + "="*60)
    print(script)
    print("="*60 + "\n")

    return False

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
