#!/usr/bin/env python3
"""
Diagnostic tool for Hostinger VPS SSH connectivity issues.

Checks multiple connection paths and provides troubleshooting info.
"""

import socket
import sys
import subprocess
from pathlib import Path

def check_port(host: str, port: int, name: str = "") -> bool:
    """Check if a port is open on target host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        status = "[OK]" if result == 0 else "[CLOSED]"
        print(f"  {name:20s} (:{port:5d}) {status}")
        return result == 0
    except Exception as e:
        print(f"  {name:20s} (:{port:5d}) [ERROR] {e}")
        return False

def check_dns(host: str) -> bool:
    """Check if DNS resolves."""
    try:
        ip = socket.gethostbyname(host)
        print(f"[OK] DNS Resolved: {host} -> {ip}")
        return True
    except Exception as e:
        print(f"[FAILED] DNS Failed: {e}")
        return False

def check_ping(host: str) -> bool:
    """Check if host responds to ping."""
    try:
        # Use different ping command based on OS
        if sys.platform == "win32":
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "2000", host],
                capture_output=True,
                timeout=5
            )
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                capture_output=True,
                timeout=5
            )

        if result.returncode == 0:
            print(f"[OK] Ping successful to {host}")
            return True
        else:
            print(f"[FAILED] Ping failed to {host}")
            return False
    except Exception as e:
        print(f"[ERROR] Ping error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose_vps_connection.py <host> [username] [password]")
        print()
        print("Example:")
        print("  python diagnose_vps_connection.py 165.232.123.6 root mypassword")
        print()
        sys.exit(1)

    host = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else "root"
    password = sys.argv[3] if len(sys.argv) > 3 else "N/A"

    print()
    print("=" * 70)
    print("HOSTINGER VPS CONNECTIVITY DIAGNOSTIC")
    print("=" * 70)
    print()

    print(f"Target Host: {host}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password) if len(password) > 0 else 'N/A'}")
    print()

    # 1. DNS Check
    print("1. DNS Resolution:")
    dns_ok = check_dns(host)
    print()

    if not dns_ok:
        print("[FATAL] DNS resolution failed - check hostname is correct")
        sys.exit(1)

    # 2. Ping check
    print("2. Host Reachability (ICMP Ping):")
    ping_ok = check_ping(host)
    print()

    # 3. Port checks
    print("3. SSH Port Availability:")
    ports_to_check = [
        (22, "Standard SSH"),
        (2222, "Alt SSH 1"),
        (22222, "Alt SSH 2"),
        (443, "HTTPS (tunneling)"),
        (80, "HTTP (tunneling)"),
    ]

    for port, name in ports_to_check:
        check_port(host, port, name)

    print()

    # 4. Connection attempts
    print("4. SSH Connection Attempts:")

    ssh_commands = [
        f"ssh -v -o ConnectTimeout=10 -o StrictHostKeyChecking=no {username}@{host}",
        f"ssh -v -o ConnectTimeout=10 -o StrictHostKeyChecking=no -p 2222 {username}@{host}",
    ]

    for cmd in ssh_commands:
        print(f"  Trying: {cmd}")
        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=15,
                text=True
            )
            if "Permission denied" in result.stderr or "Authentification failed" in result.stderr:
                print(f"    -> Authentication error (user/password invalid)")
            elif "Connection timed out" in result.stderr or "Timeout" in result.stderr:
                print(f"    -> Connection timeout (port not accessible)")
            elif "Connection refused" in result.stderr:
                print(f"    -> Connection refused (SSH not running on port)")
            else:
                print(f"    -> Status: {result.returncode}")
        except subprocess.TimeoutExpired:
            print(f"    -> Command timeout (host unreachable)")
        except Exception as e:
            print(f"    -> Error: {e}")

    print()
    print("=" * 70)
    print("RECOMMENDATIONS:")
    print("=" * 70)
    print()

    if not ping_ok:
        print("1. Host does not respond to ping:")
        print("   - Check if firewall blocks ICMP")
        print("   - Verify VPS is powered on in Hostinger control panel")
        print("   - Check network settings in Hostinger")
        print()

    print("2. For Hostinger VPS:")
    print("   - Verify SSH is enabled in Hostinger control panel")
    print("   - Check firewall rules allow port 22")
    print("   - Try default username 'root' (not 'jarvis')")
    print("   - Check Hostinger IP restrictions (if any)")
    print("   - Try logging in via Hostinger web console first")
    print()

    print("3. Password authentication on Hostinger:")
    print("   - Must be enabled in sshd config")
    print("   - Default may require SSH key instead")
    print("   - Check /etc/ssh/sshd_config on VPS")
    print()

    print("4. If all checks pass but SSH still fails:")
    print("   - Try: ssh -vvv (extra verbose)")
    print("   - Check Hostinger control panel for IP whitelisting")
    print("   - Contact Hostinger support with diagnostic info")
    print()

if __name__ == "__main__":
    main()
