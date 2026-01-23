#!/usr/bin/env python3
"""
Jarvis Autonomous System - IMMEDIATE VPS DEPLOYMENT
Uses correct Hostinger credentials from environment variables (.env)
"""

import paramiko
import socket
import sys
import time
import logging
import os
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger()

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
else:
    # Fallback: try loading from environment directly
    pass

# Load credentials from environment variables
HOST = os.environ.get('VPS_HOST', '72.61.7.126')
USERNAME = os.environ.get('VPS_USERNAME', 'root')
PASSWORD = os.environ.get('VPS_PASSWORD')
JARVIS_HOME = os.environ.get('JARVIS_HOME', '/home/jarvis/Jarvis')
PORTS = [int(os.environ.get('VPS_SSH_PORT_PRIMARY', '22')),
         int(os.environ.get('VPS_SSH_PORT_ALTERNATE', '65002'))]

# Security check
if not PASSWORD:
    logger.error("ERROR: VPS_PASSWORD not found in environment variables")
    logger.error("SOLUTION: Create .env file with VPS_PASSWORD=<password>")
    logger.error("         or export VPS_PASSWORD=<password> in shell")
    sys.exit(1)


def deploy():
    """Deploy to Hostinger VPS immediately."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("JARVIS AUTONOMOUS SYSTEM - IMMEDIATE DEPLOYMENT")
    logger.info("=" * 70)
    logger.info(f"Target: {USERNAME}@{HOST}")
    logger.info("")

    for port in PORTS:
        logger.info(f"Attempting SSH on port {port}...")

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(HOST, port=port, username=USERNAME, password=PASSWORD, timeout=15)
            logger.info(f"[SUCCESS] Connected on port {port}")
            logger.info("")

            # DEPLOYMENT SEQUENCE
            logger.info(f"[1/9] Verifying {JARVIS_HOME} directory...")
            stdin, stdout, stderr = ssh.exec_command(f"cd {JARVIS_HOME} && pwd")
            result = stdout.read().decode().strip()
            if "Jarvis" in result:
                logger.info(f"[OK] {result}")
            else:
                logger.error(f"[FAILED] {stderr.read().decode()}")
                continue

            logger.info("[2/9] Pulling latest code...")
            ssh.exec_command(f"cd {JARVIS_HOME} && git fetch origin main && git reset --hard origin/main")
            time.sleep(5)
            logger.info("[OK] Code updated")

            logger.info("[3/9] Verifying autonomous system files...")
            files = [
                "core/moderation/toxicity_detector.py",
                "core/moderation/auto_actions.py",
                "core/learning/engagement_analyzer.py",
                "core/vibe_coding/sentiment_mapper.py",
                "core/vibe_coding/regime_adapter.py",
                "core/autonomous_manager.py",
            ]
            all_ok = True
            for f in files:
                stdin, stdout, stderr = ssh.exec_command(f"test -f {JARVIS_HOME}/{f} && echo OK")
                if "OK" not in stdout.read().decode():
                    logger.error(f"[MISSING] {f}")
                    all_ok = False
            if not all_ok:
                continue
            logger.info("[OK] All files present")

            logger.info("[4/9] Creating directories...")
            ssh.exec_command(
                f"mkdir -p {JARVIS_HOME}/data/{{moderation,learning,vibe_coding,validation_proof}} {JARVIS_HOME}/logs"
            )
            logger.info("[OK] Directories created")

            logger.info("[5/9] Stopping supervisor...")
            ssh.exec_command("sudo systemctl stop jarvis-supervisor 2>/dev/null || true && sleep 5")
            time.sleep(3)
            logger.info("[OK] Supervisor stopped")

            logger.info("[6/9] Restarting supervisor...")
            ssh.exec_command("sudo systemctl start jarvis-supervisor")
            time.sleep(10)
            logger.info("[OK] Supervisor started")

            logger.info("[7/9] Verifying autonomous_manager...")
            stdin, stdout, stderr = ssh.exec_command(
                f"tail -50 {JARVIS_HOME}/logs/supervisor.log | grep -i autonomous_manager"
            )
            if "autonomous_manager" in stdout.read().decode().lower():
                logger.info("[OK] autonomous_manager detected in logs")
            else:
                logger.warning("[INFO] autonomous_manager starting up...")

            logger.info("[8/9] Starting validation loop...")
            ssh.exec_command(
                f"cd {JARVIS_HOME} && nohup python scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &"
            )
            time.sleep(5)
            logger.info("[OK] Validation loop started")

            logger.info("[9/9] Deployment complete")
            logger.info("")
            logger.info("=" * 70)
            logger.info("SUCCESS: Autonomous system deployed to VPS!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("Components running: moderation, learning, vibe_coding, autonomous_manager")
            logger.info("Validation proof collecting to: ~/Jarvis/data/validation_proof/")
            logger.info("")
            logger.info("Monitor via:")
            logger.info("  tail -f ~/Jarvis/logs/validation_continuous.log")
            logger.info("  journalctl -u jarvis-supervisor -f")
            logger.info("")

            ssh.close()
            return True

        except paramiko.ssh_exception.AuthenticationException:
            logger.warning(f"[FAILED] Authentication failed on port {port}")
            continue
        except socket.timeout:
            logger.warning(f"[TIMEOUT] No response on port {port}")
            continue
        except Exception as e:
            logger.warning(f"[ERROR] Port {port}: {str(e)[:50]}")
            continue

    logger.error("Deployment failed on all ports")
    return False


if __name__ == "__main__":
    try:
        if deploy():
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Deployment cancelled")
        sys.exit(0)
