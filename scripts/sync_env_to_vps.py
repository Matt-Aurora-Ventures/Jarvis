#!/usr/bin/env python3
"""Sync tg_bot/.env to VPS.

Usage:
    python scripts/sync_env_to_vps.py
"""

import os
import subprocess
import sys
from pathlib import Path

# Load VPS credentials from root .env
project_root = Path(__file__).resolve().parents[1]
env_file = project_root / ".env"

if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)

VPS_HOST = os.environ.get("VPS_HOST", "72.61.7.126")
VPS_USER = os.environ.get("VPS_USERNAME", "root")
VPS_PASSWORD = os.environ.get("VPS_PASSWORD")
VPS_SSH_PORT = os.environ.get("VPS_SSH_PORT_PRIMARY", "22")

LOCAL_ENV = project_root / "tg_bot" / ".env"
REMOTE_PATH = "/home/jarvis/Jarvis/tg_bot/.env"


def main():
    print("=" * 50)
    print("SYNC ENV TO VPS")
    print("=" * 50)

    if not LOCAL_ENV.exists():
        print(f"ERROR: Local env file not found: {LOCAL_ENV}")
        return 1

    print(f"Local:  {LOCAL_ENV}")
    print(f"Remote: {VPS_USER}@{VPS_HOST}:{REMOTE_PATH}")
    print()

    # Show what will be synced (without exposing secrets)
    print("Keys being synced:")
    for line in LOCAL_ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, _ = line.partition("=")
            print(f"  - {key.strip()}")
    print()

    # Use scp command
    cmd = [
        "scp",
        "-P", VPS_SSH_PORT,
        str(LOCAL_ENV),
        f"{VPS_USER}@{VPS_HOST}:{REMOTE_PATH}"
    ]

    print(f"Running: scp -P {VPS_SSH_PORT} tg_bot/.env {VPS_USER}@{VPS_HOST}:{REMOTE_PATH}")
    print()

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("SUCCESS: Env file synced to VPS")
        print()
        print("Next steps:")
        print("  1. SSH to VPS: ssh root@" + VPS_HOST)
        print("  2. Restart supervisor: systemctl restart jarvis-supervisor")
        print("  3. Check logs: journalctl -u jarvis-supervisor -f")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"ERROR: SCP failed: {e}")
        print(f"stderr: {e.stderr}")
        print()
        print("Alternative: Manually copy the file")
        print(f"  1. SSH to VPS: ssh root@{VPS_HOST}")
        print(f"  2. Edit env file: nano {REMOTE_PATH}")
        print("  3. Add this line:")
        print("     BITQUERY_API_KEY=<your-key>")
        return 1
    except FileNotFoundError:
        print("ERROR: scp command not found")
        print()
        print("Alternative: Manually copy the file via SSH")
        return 1


if __name__ == "__main__":
    sys.exit(main())
