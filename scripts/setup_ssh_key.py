#!/usr/bin/env python3
"""
Setup SSH Key-Based Authentication for VPS

This script copies your local SSH public key to the VPS,
enabling passwordless SSH access for future deployments.

Usage:
    python scripts/setup_ssh_key.py

Or with explicit password:
    python scripts/setup_ssh_key.py --password "your_password"
"""

import argparse
import os
import sys
import getpass
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("paramiko not installed. Run: pip install paramiko")
    sys.exit(1)

from dotenv import load_dotenv

# Load environment
load_dotenv()


def get_public_key() -> str:
    """Get the local SSH public key."""
    key_paths = [
        Path.home() / ".ssh" / "id_ed25519.pub",
        Path.home() / ".ssh" / "id_rsa.pub",
    ]

    for path in key_paths:
        if path.exists():
            return path.read_text().strip()

    raise FileNotFoundError(
        "No SSH public key found. Generate one with:\n"
        "  ssh-keygen -t ed25519 -C 'jarvis-deployment'"
    )


def setup_ssh_key(host: str, username: str, password: str, port: int = 22) -> bool:
    """
    Copy SSH public key to remote server.

    Returns True on success, False on failure.
    """
    public_key = get_public_key()
    print(f"Public key: {public_key[:50]}...")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to {username}@{host}:{port}...")
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )
        print("Connected!")

        # Commands to add key
        commands = f'''
# Create .ssh directory if not exists
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add key if not already present
if ! grep -q "{public_key}" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "{public_key}" >> ~/.ssh/authorized_keys
    echo "Key added successfully"
else
    echo "Key already present"
fi

# Fix permissions
chmod 600 ~/.ssh/authorized_keys
chown -R {username}:{username} ~/.ssh

# Verify
echo "Current authorized_keys:"
cat ~/.ssh/authorized_keys
'''

        stdin, stdout, stderr = ssh.exec_command(commands)
        result = stdout.read().decode()
        errors = stderr.read().decode()

        print(f"\nResult:\n{result}")
        if errors:
            print(f"\nWarnings/Errors:\n{errors}")

        ssh.close()
        return "Key added" in result or "Key already present" in result

    except paramiko.AuthenticationException as e:
        print(f"\nAuthentication failed: {e}")
        print("\nPossible causes:")
        print("1. Password is incorrect or has changed")
        print("2. Password auth may be disabled on the server")
        print("3. Root login may be disabled")
        print("\nTo fix, try:")
        print("1. Log in via Hostinger control panel (web console)")
        print("2. Check /etc/ssh/sshd_config for PermitRootLogin and PasswordAuthentication")
        return False

    except Exception as e:
        print(f"\nConnection failed: {e}")
        return False


def test_key_auth(host: str, username: str, port: int = 22) -> bool:
    """Test if key-based auth works."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path.home() / ".ssh" / "id_ed25519"

    try:
        print(f"\nTesting key-based auth to {username}@{host}:{port}...")
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=str(key_path),
            timeout=30,
        )

        stdin, stdout, stderr = ssh.exec_command("echo 'Key auth works!' && hostname")
        result = stdout.read().decode().strip()
        print(f"Success: {result}")

        ssh.close()
        return True

    except Exception as e:
        print(f"Key auth failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup SSH key-based auth for VPS")
    parser.add_argument("--host", default=os.getenv("VPS_HOST", "72.61.7.126"))
    parser.add_argument("--username", default=os.getenv("VPS_USERNAME", "root"))
    parser.add_argument("--password", default=None, help="VPS password (or enter interactively)")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--test-only", action="store_true", help="Only test key auth, don't setup")

    args = parser.parse_args()

    print("=" * 60)
    print("SSH KEY SETUP FOR JARVIS VPS")
    print("=" * 60)

    # Test key auth first
    if test_key_auth(args.host, args.username, args.port):
        print("\nKey-based auth already works! No setup needed.")
        return 0

    if args.test_only:
        print("\nKey auth not working. Run without --test-only to set up.")
        return 1

    # Get password
    password = args.password or os.getenv("VPS_PASSWORD")
    if not password:
        password = getpass.getpass(f"Enter password for {args.username}@{args.host}: ")

    # Setup key
    print("\n" + "=" * 60)
    print("COPYING SSH KEY TO VPS")
    print("=" * 60)

    if setup_ssh_key(args.host, args.username, password, args.port):
        print("\n" + "=" * 60)
        print("VERIFYING KEY-BASED AUTH")
        print("=" * 60)

        if test_key_auth(args.host, args.username, args.port):
            print("\n✓ SUCCESS! You can now SSH without a password:")
            print(f"  ssh {args.username}@{args.host}")
            print(f"  Or use: ssh jarvis-vps")
            return 0
        else:
            print("\nKey was added but auth test failed. Check server SSH config.")
            return 1
    else:
        print("\nFailed to setup SSH key. See errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
