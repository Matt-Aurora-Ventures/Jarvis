#!/usr/bin/env python3
"""
Securely open Moltbook claim URL in browser
NO SECRETS PRINTED TO CONSOLE
"""
import subprocess
import json
import webbrowser
import sys

def main():
    try:
        # SSH to VPS and get moltbook.json
        cmd = [
            "ssh", "root@100.66.17.93",
            "docker exec clawdbot-gateway cat /root/clawd/secrets/moltbook.json"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            print(f"[ERROR] Failed to retrieve Moltbook data: {result.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse JSON
        data = json.loads(result.stdout)

        # Extract relevant info (NO SECRETS)
        status = data.get('registration_response', {}).get('status', 'unknown')
        claim_url = data.get('registration_response', {}).get('claim_url')

        print(f"[OK] Status: {status}")

        if not claim_url:
            print("[ERROR] No claim_url found in registration_response", file=sys.stderr)
            sys.exit(1)

        if status != 'pending_claim':
            print(f"[WARNING] Status is '{status}' (expected 'pending_claim')")

        # Open in browser
        print(f"[OK] Opening claim URL in browser...")
        webbrowser.open(claim_url)
        print(f"[OK] Browser opened! Complete the claim process.")

    except subprocess.TimeoutExpired:
        print("[ERROR] SSH command timed out", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
