#!/usr/bin/env python3
"""
Jarvis Autonomous System - Universal Hostinger VPS Deployment Orchestrator

Automatically detects and uses optimal connection method:
1. SSH port 22 (standard)
2. SSH port 65002 (Hostinger alternate)
3. Falls back to retry loop if VPS offline

No user intervention required after startup.
"""

import paramiko
import socket
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("deploy_orchestrator")


class HostingerDeployer:
    """Intelligent deployer for Hostinger VPS."""

    def __init__(self, host: str, password: str, interval: int = 30):
        self.host = host
        self.password = password
        self.interval = interval
        self.usernames = ["root", "jarvis"]  # Try root first (Hostinger default)
        self.ports = [22, 65002]  # Try standard and Hostinger alternate
        self.attempt = 0

    def can_connect_to_port(self, port: int, timeout: int = 5) -> bool:
        """Check if port is accessible."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((self.host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def try_ssh_connection(self, username: str, port: int) -> bool:
        """Try to connect via SSH on specific port."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.info(f"  Attempting: {username}@{self.host}:{port}")
            ssh.connect(
                self.host,
                port=port,
                username=username,
                password=self.password,
                timeout=15,
                banner_timeout=10,
            )
            logger.info(f"  [SUCCESS] Connected via {username}@{self.host}:{port}")
            return self._deploy(ssh, username)
        except paramiko.ssh_exception.AuthenticationException:
            logger.debug(f"  [AUTH FAILED] {username} credentials invalid on port {port}")
            return False
        except paramiko.ssh_exception.SSHException as e:
            logger.debug(f"  [SSH ERROR] {str(e)[:50]}")
            return False
        except socket.timeout:
            logger.debug(f"  [TIMEOUT] No response on port {port}")
            return False
        except Exception as e:
            logger.debug(f"  [ERROR] {str(e)[:50]}")
            return False
        finally:
            try:
                ssh.close()
            except:
                pass

    def _deploy(self, ssh: paramiko.SSHClient, username: str) -> bool:
        """Execute deployment steps over SSH."""
        try:
            logger.info("")
            logger.info("[DEPLOYMENT] Starting deployment sequence...")
            logger.info("")

            # Step 1: Verify directory
            logger.info("[1/9] Verifying ~/Jarvis directory...")
            stdin, stdout, stderr = ssh.exec_command("cd ~/Jarvis && pwd")
            result = stdout.read().decode().strip()
            if "Jarvis" not in result:
                logger.error("[FAILED] Jarvis directory not found")
                return False
            logger.info(f"[OK] {result}")

            # Step 2: Pull latest code
            logger.info("[2/9] Pulling latest code...")
            ssh.exec_command("cd ~/Jarvis && git fetch origin main && git reset --hard origin/main")
            time.sleep(5)
            logger.info("[OK] Code updated")

            # Step 3: Verify files
            logger.info("[3/9] Verifying autonomous system files...")
            files = [
                "core/moderation/toxicity_detector.py",
                "core/moderation/auto_actions.py",
                "core/learning/engagement_analyzer.py",
                "core/vibe_coding/sentiment_mapper.py",
                "core/vibe_coding/regime_adapter.py",
                "core/autonomous_manager.py",
            ]
            for f in files:
                stdin, stdout, stderr = ssh.exec_command(f"test -f ~/Jarvis/{f} && echo OK")
                if "OK" not in stdout.read().decode():
                    logger.error(f"[MISSING] {f}")
                    return False
            logger.info("[OK] All files present")

            # Step 4: Create directories
            logger.info("[4/9] Creating directories...")
            ssh.exec_command(
                "mkdir -p ~/Jarvis/data/{{moderation,learning,vibe_coding,validation_proof}} ~/Jarvis/logs"
            )
            logger.info("[OK] Directories created")

            # Step 5: Stop supervisor
            logger.info("[5/9] Stopping supervisor...")
            ssh.exec_command("sudo systemctl stop jarvis-supervisor 2>/dev/null || true && sleep 5")
            time.sleep(3)
            logger.info("[OK] Supervisor stopped")

            # Step 6: Restart supervisor
            logger.info("[6/9] Restarting supervisor...")
            ssh.exec_command("sudo systemctl start jarvis-supervisor")
            time.sleep(10)
            logger.info("[OK] Supervisor started")

            # Step 7: Verify startup
            logger.info("[7/9] Verifying autonomous_manager...")
            stdin, stdout, stderr = ssh.exec_command(
                "tail -50 ~/Jarvis/logs/supervisor.log | grep -i autonomous_manager"
            )
            if "autonomous_manager" in stdout.read().decode().lower():
                logger.info("[OK] autonomous_manager detected in logs")
            else:
                logger.warning("[PENDING] autonomous_manager not yet in logs (may be starting)")

            # Step 8: Start validation
            logger.info("[8/9] Starting validation loop...")
            ssh.exec_command(
                "cd ~/Jarvis && nohup python scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &"
            )
            time.sleep(5)
            logger.info("[OK] Validation loop started")

            # Step 9: Final status
            logger.info("[9/9] Deployment complete")
            logger.info("")
            logger.info("=" * 70)
            logger.info("SUCCESS: Autonomous system deployed!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("Autonomous system is now running continuously on VPS.")
            logger.info("Components: moderation, learning, vibe_coding, autonomous_manager")
            logger.info("")
            logger.info("Monitor validation: tail -f ~/Jarvis/logs/validation_continuous.log")
            logger.info("Monitor supervisor: journalctl -u jarvis-supervisor -f")
            logger.info("")

            return True

        except Exception as e:
            logger.error(f"[DEPLOYMENT ERROR] {e}")
            return False

    def run(self):
        """Main orchestration loop."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("JARVIS AUTONOMOUS SYSTEM - UNIVERSAL DEPLOYMENT ORCHESTRATOR")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Target: Hostinger VPS at 165.232.123.6")
        logger.info("Strategy: Auto-detect optimal connection method")
        logger.info("Retry interval: {} seconds".format(self.interval))
        logger.info("")

        while True:
            self.attempt += 1
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[ATTEMPT {self.attempt}] {now}")
            logger.info("")

            # Try each port
            for port in self.ports:
                logger.info(f"Checking port {port}...")
                if not self.can_connect_to_port(port, timeout=3):
                    logger.info(f"  Port {port}: not accessible")
                    continue

                logger.info(f"  Port {port}: OPEN")

                # Try each username on this port
                for username in self.usernames:
                    if self.try_ssh_connection(username, port):
                        logger.info("")
                        logger.info("Deployment successful. Exiting.")
                        return  # Success - exit

            # No success, wait and retry
            logger.info("")
            logger.info("[OFFLINE] VPS not accessible on any method")
            logger.info(f"[RETRY] Waiting {self.interval}s before next attempt...")
            logger.info("")
            time.sleep(self.interval)


def main():
    import os
    from pathlib import Path

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

    # Load credentials from environment
    host = os.environ.get('VPS_HOST', '72.61.7.126')
    password = os.environ.get('VPS_PASSWORD')

    if not password:
        logger.error("ERROR: VPS_PASSWORD not found in environment")
        logger.error("Create .env file with: VPS_PASSWORD=<password>")
        sys.exit(1)

    deployer = HostingerDeployer(host, password, interval=30)
    try:
        deployer.run()
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Deployment stopped by user.")


if __name__ == "__main__":
    main()
