#!/usr/bin/env python3
"""Get Moltbook claim URL from VPS via SSH"""
import paramiko
import sys

HOST = "72.61.7.126"
USER = "root"
PASSWORD = "bhjhbHBujbxbvxd57272#####"
FILE_PATH = "/root/clawd/secrets/moltbook.json"

try:
    # Create SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Connect
    print(f"Connecting to {USER}@{HOST}...", file=sys.stderr)
    client.connect(HOST, username=USER, password=PASSWORD, timeout=10)

    # Execute command
    stdin, stdout, stderr = client.exec_command(f"cat {FILE_PATH}")

    # Get output
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')

    if error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    # Print the JSON content
    print(output)

    client.close()

except Exception as e:
    print(f"Failed to retrieve claim URL: {e}", file=sys.stderr)
    sys.exit(1)
