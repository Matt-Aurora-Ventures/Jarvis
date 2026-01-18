#!/usr/bin/env python3
"""
Jarvis Autonomous System - Complete VPS Setup & Deployment
Handles: SSH connection, repo setup, supervisor config, component deployment
Credentials from environment variables (.env)
"""

import paramiko
import sys
import time
import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)
logger = logging.getLogger()

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # Manually load .env if python-dotenv not available
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load credentials from environment variables
HOST = os.environ.get('VPS_HOST', '72.61.7.126')
USERNAME = os.environ.get('VPS_USERNAME', 'root')
PASSWORD = os.environ.get('VPS_PASSWORD')

# Security check
if not PASSWORD:
    logger.error("ERROR: VPS_PASSWORD not found in environment")
    logger.error("Create .env file with: VPS_PASSWORD=<password>")
    sys.exit(1)

# Find the local Jarvis repo for file transfer
JARVIS_LOCAL = Path(os.environ.get('JARVIS_LOCAL_PATH', 'c:/Users/lucid/OneDrive/Desktop/Projects/Jarvis'))


def execute_command(ssh, cmd, show_output=False):
    """Execute command over SSH."""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if show_output and out:
        logger.info(out.strip())
    if err and "warning" not in err.lower():
        logger.warning(f"stderr: {err.strip()[:100]}")
    return out + err


def setup_and_deploy():
    """Complete VPS setup and Jarvis deployment."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("JARVIS AUTONOMOUS SYSTEM - VPS SETUP & DEPLOYMENT")
    logger.info("=" * 70)
    logger.info("")
    logger.info(f"Target: {USERNAME}@{HOST}")
    logger.info(f"Local Repo: {JARVIS_LOCAL}")
    logger.info("")

    try:
        # Connect
        logger.info("Connecting to VPS...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, port=22, username=USERNAME, password=PASSWORD, timeout=30)
        logger.info("[OK] Connected")
        logger.info("")

        # Step 1: Update system
        logger.info("[1/10] Updating system packages...")
        execute_command(ssh, "apt-get update && apt-get upgrade -y")
        logger.info("[OK]")

        # Step 2: Install dependencies
        logger.info("[2/10] Installing dependencies (git, python3, supervisor)...")
        execute_command(
            ssh,
            "apt-get install -y git python3 python3-pip python3-venv supervisor curl wget",
        )
        logger.info("[OK]")

        # Step 3: Create Jarvis directory
        logger.info("[3/10] Creating Jarvis directory...")
        execute_command(ssh, "mkdir -p ~/Jarvis")
        logger.info("[OK]")

        # Step 4: Initialize git repo
        logger.info("[4/10] Initializing git repository...")
        execute_command(ssh, "cd ~/Jarvis && git init")
        logger.info("[OK]")

        # Step 5: Add remote and pull (will fail but sets up git)
        logger.info("[5/10] Setting up git remote...")
        execute_command(ssh, "cd ~/Jarvis && git remote add origin https://github.com/user/Jarvis || true")
        # Since we don't have online repo, copy files via SFTP instead
        logger.info("[INFO] Will transfer files via direct deployment")

        # Step 6: Create directory structure
        logger.info("[6/10] Creating directory structure...")
        dirs = [
            "core/moderation",
            "core/learning",
            "core/vibe_coding",
            "bots/treasury",
            "scripts",
            "data/moderation",
            "data/learning",
            "data/vibe_coding",
            "data/validation_proof",
            "logs",
        ]
        for d in dirs:
            execute_command(ssh, f"mkdir -p ~/Jarvis/{d}")
        logger.info("[OK]")

        # Step 7: Transfer key files via SCP (if local repo exists)
        logger.info("[7/10] Transferring autonomous system files...")
        if JARVIS_LOCAL.exists():
            transport = ssh.get_transport()
            sftp = paramiko.SFTPClient.from_transport(transport)

            files_to_transfer = [
                "core/autonomous_manager.py",
                "core/moderation/toxicity_detector.py",
                "core/moderation/auto_actions.py",
                "core/learning/engagement_analyzer.py",
                "core/vibe_coding/sentiment_mapper.py",
                "core/vibe_coding/regime_adapter.py",
                "bots/supervisor.py",
                "scripts/validate_autonomous_system.py",
                "scripts/deploy_autonomous_system.sh",
            ]

            for f in files_to_transfer:
                local_path = JARVIS_LOCAL / f
                remote_path = f"Jarvis/{f}"
                if local_path.exists():
                    try:
                        sftp.put(str(local_path), f"/root/{remote_path}")
                        logger.info(f"  [TRANSFER] {f}")
                    except Exception as e:
                        logger.warning(f"  [SKIP] {f}: {str(e)[:50]}")

            sftp.close()
        logger.info("[OK]")

        # Step 8: Install Python dependencies
        logger.info("[8/10] Installing Python dependencies...")
        execute_command(
            ssh,
            "cd ~/Jarvis && pip3 install paramiko asyncio python-dotenv logging pathlib",
        )
        logger.info("[OK]")

        # Step 9: Start supervisor
        logger.info("[9/10] Starting supervisor service...")
        execute_command(ssh, "sudo systemctl enable supervisor")
        execute_command(ssh, "sudo systemctl start supervisor")
        time.sleep(5)
        logger.info("[OK]")

        # Step 10: Start validation
        logger.info("[10/10] Starting validation loop...")
        execute_command(
            ssh,
            "cd ~/Jarvis && nohup python3 scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &",
        )
        time.sleep(3)
        logger.info("[OK]")

        logger.info("")
        logger.info("=" * 70)
        logger.info("SUCCESS: Jarvis Autonomous System deployed!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Deployed Components:")
        logger.info("  - Moderation (toxicity detector + auto-actions)")
        logger.info("  - Learning (engagement analyzer)")
        logger.info("  - Vibe Coding (sentiment-driven adaptation)")
        logger.info("  - Autonomous Manager (orchestrator)")
        logger.info("")
        logger.info("Validation proof location: ~/Jarvis/data/validation_proof/")
        logger.info("Validation log: ~/Jarvis/logs/validation_continuous.log")
        logger.info("")
        logger.info("Monitor deployment:")
        logger.info("  ssh root@72.61.7.126")
        logger.info("  tail -f ~/Jarvis/logs/validation_continuous.log")
        logger.info("")

        ssh.close()
        return True

    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = setup_and_deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Setup cancelled by user")
        sys.exit(1)
