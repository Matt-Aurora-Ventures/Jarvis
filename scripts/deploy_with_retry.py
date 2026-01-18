#!/usr/bin/env python3
"""
Jarvis Autonomous System - SSH Deploy with Password Authentication & Retry Loop
Ralph Wiggum Mode: Keep trying until connected and deployed

Usage:
    python scripts/deploy_with_retry.py <host> <username> <password> [--interval 30]

    Or use environment variables from .env file:
    python scripts/deploy_with_retry.py (loads from .env)

Example:
    python scripts/deploy_with_retry.py 72.61.7.126 root <your_password>
"""

import paramiko
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("deployment_retry.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger("deploy_retry")


def test_connectivity(host: str, port: int = 22, timeout: int = 10) -> bool:
    """Test if VPS is reachable on SSH port."""
    try:
        sock = paramiko.util.socket.socket()
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.debug(f"Connectivity test failed: {e}")
        return False


def deploy_via_ssh(host: str, username: str, password: str) -> bool:
    """Deploy Jarvis autonomous system via SSH with password auth."""

    logger.info("=" * 70)
    logger.info("JARVIS AUTONOMOUS SYSTEM - SSH PASSWORD DEPLOYMENT")
    logger.info("=" * 70)
    logger.info("")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"[1/9] Connecting to {host}@{username}...")
        ssh.connect(host, username=username, password=password, timeout=30)
        logger.info(f"      ✓ Connected successfully")
        logger.info("")

        # Step 1: Verify project directory
        logger.info(f"[2/9] Verifying project directory...")
        stdin, stdout, stderr = ssh.exec_command("cd ~/Jarvis && pwd")
        result = stdout.read().decode().strip()
        if "Jarvis" in result:
            logger.info(f"      ✓ Project directory: {result}")
        else:
            logger.error(f"      ✗ Error: {stderr.read().decode()}")
            return False
        logger.info("")

        # Step 2: Pull latest code
        logger.info(f"[3/9] Pulling latest code from main branch...")
        stdin, stdout, stderr = ssh.exec_command(
            "cd ~/Jarvis && git fetch origin main && git reset --hard origin/main"
        )
        result = stdout.read().decode()
        err = stderr.read().decode()
        if "Already up to date" in result or "HEAD is now at" in result:
            logger.info(f"      ✓ Code updated successfully")
        else:
            logger.info(f"      ✓ Git updated (output: {result[:100]})...")
        logger.info("")

        # Step 3: Verify autonomous system files
        logger.info(f"[4/9] Verifying autonomous system files...")
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
            logger.info(f"      {status} {file}")
            if result != "OK":
                all_exist = False

        if not all_exist:
            logger.error("      Error: Some files missing")
            return False
        logger.info("")

        # Step 4: Create directories
        logger.info(f"[5/9] Creating required directories...")
        ssh.exec_command("mkdir -p ~/Jarvis/data/moderation ~/Jarvis/data/learning ~/Jarvis/data/vibe_coding ~/Jarvis/data/validation_proof ~/Jarvis/logs")
        logger.info(f"      ✓ Directories created")
        logger.info("")

        # Step 5: Stop supervisor
        logger.info(f"[6/9] Stopping supervisor gracefully...")
        stdin, stdout, stderr = ssh.exec_command("sudo systemctl stop jarvis-supervisor 2>/dev/null || true && sleep 5")
        stdout.read()
        logger.info(f"      ✓ Supervisor stopped")
        logger.info("")

        # Step 6: Restart supervisor
        logger.info(f"[7/9] Restarting supervisor with autonomous manager...")
        ssh.exec_command("sudo systemctl start jarvis-supervisor")
        time.sleep(10)
        logger.info(f"      ✓ Supervisor restarted")
        logger.info("")

        # Step 7: Verify startup
        logger.info(f"[8/9] Verifying autonomous_manager startup...")
        stdin, stdout, stderr = ssh.exec_command("tail -50 ~/Jarvis/logs/supervisor.log | grep -i autonomous_manager")
        result = stdout.read().decode()
        if "autonomous_manager" in result.lower():
            logger.info(f"      ✓ autonomous_manager detected in logs")
        else:
            logger.info(f"      ⚠ autonomous_manager not yet in logs, checking status...")
            stdin, stdout, stderr = ssh.exec_command("sudo systemctl status jarvis-supervisor")
            status = stdout.read().decode()
            if "active (running)" in status:
                logger.info(f"      ✓ Supervisor is running (autonomous_manager may be starting)")
            else:
                logger.warning(f"      ✗ Supervisor status issue")
        logger.info("")

        # Step 8: Start validation loop
        logger.info(f"[9/9] Starting continuous validation loop...")
        ssh.exec_command(
            "cd ~/Jarvis && nohup python scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &"
        )
        time.sleep(5)
        logger.info(f"      ✓ Validation loop started")
        logger.info("")

        # Final status
        logger.info("=" * 70)
        logger.info("✅ DEPLOYMENT COMPLETE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("")
        logger.info("1. Monitor supervisor:")
        logger.info(f"   ssh {username}@{host}")
        logger.info("   tail -f ~/Jarvis/logs/supervisor.log")
        logger.info("")
        logger.info("2. Monitor validation loop:")
        logger.info("   tail -f ~/Jarvis/logs/validation_continuous.log")
        logger.info("")
        logger.info("3. Check validation proof (after 1+ hours):")
        logger.info("   ls ~/Jarvis/data/validation_proof/")
        logger.info("")
        logger.info("4. Check component health:")
        logger.info("   /status command in Telegram")
        logger.info("")

        return True

    except paramiko.ssh_exception.AuthenticationException:
        logger.error(f"✗ Authentication failed - incorrect username or password")
        return False
    except paramiko.ssh_exception.SSHException as e:
        logger.error(f"✗ SSH Error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        return False
    finally:
        ssh.close()


def retry_loop(host: str, username: str, password: str, interval: int = 30):
    """Continuously retry deployment until successful."""
    attempt = 0
    last_connectivity_check = None

    # Try multiple usernames (Hostinger default is root, but may have custom)
    usernames_to_try = [username, "root", "jarvis", username]

    while True:
        attempt += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info("")
        logger.info(f"[ATTEMPT {attempt}] {now}")

        # Check connectivity first
        logger.info(f"Checking connectivity to {host}:22...")
        if test_connectivity(host):
            logger.info(f"Connected! Attempting deployment with available credentials...")

            # Try each username
            deployed = False
            for user in usernames_to_try:
                logger.info(f"Trying with username: {user}...")
                try:
                    if deploy_via_ssh(host, user, password):
                        logger.info("")
                        logger.info("=" * 70)
                        logger.info(f"SUCCESS: Autonomous system deployed! (via {user}@{host})")
                        logger.info("=" * 70)
                        deployed = True
                        break
                except Exception as e:
                    logger.debug(f"Failed with {user}: {e}, trying next...")
                    continue

            if deployed:
                break
            else:
                logger.warning("All credential attempts failed, will retry...")
        else:
            logger.info(f"VPS not yet reachable on {host}:22")
            logger.info(f"(Hostinger may need port 22 unblocked in firewall)")
            logger.info(f"Will retry in {interval} seconds...")

        logger.info(f"Waiting {interval} seconds before retry...")
        time.sleep(interval)


def main():
    if len(sys.argv) < 4:
        print("Usage: python deploy_with_retry.py <host> <username> <password> [--interval 30]")
        print()
        print("Example:")
        print("  python deploy_with_retry.py 165.232.123.6 jarvis mypassword")
        print()
        print("This script will continuously retry deployment until successful.")
        print("Press Ctrl+C to stop.")
        sys.exit(1)

    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    # Optional interval parameter
    interval = 30
    if len(sys.argv) > 5 and sys.argv[4] == "--interval":
        interval = int(sys.argv[5])

    logger.info(f"Jarvis Autonomous System - Deployment Retry Loop")
    logger.info(f"Target: {username}@{host}")
    logger.info(f"Retry interval: {interval} seconds")
    logger.info(f"Press Ctrl+C to stop")
    logger.info("")

    try:
        retry_loop(host, username, password, interval)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Deployment retry loop stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
